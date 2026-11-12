"""Command-line orchestration for source collection and route publication."""

import argparse
import json
import os
from pathlib import Path
import time

from .logging import progress
from .runtime_paths import GENERATED_PATH_SPECS, env_path
from .update_config import DEFAULT_CACHE_MAX_AGE, DEFAULT_MIN_PREFIX_LENGTH, env_bool, env_float, env_int
from .runtime_state import PROGRESS_STEPS, write_runtime_progress
from .route_builder import cleanup_paths, parse_and_build_routes, subtract_networks, unsafe_broad_routes
from .route_output import build_status, write_json, write_metrics, write_routes, write_text
from .sources import collect_sources, parse_named_url_list, read_list

# Retain helper imports for callers of the former single-module updater.
# Implementations and their dependencies now live in the owning modules.
from . import dns_resolver
from .sources.fetch import (
    DEFAULT_DNS_HTTP_REDIRECTS, CustomDnsHTTPSConnection, cache_age, cache_path,
    count_source_routes, fetch_text_source, fetch_url, fetch_via_custom_dns, read_cache,
)
from .sources.domains import (
    DOMAIN_LABEL_RE, normalize_domain_name, parse_domain_list, parse_ipv4_literal, resolve_domain,
)
from .sources.countries import (
    COUNTRY_CODE_RE, DELEGATED_REGISTRIES, DELEGATED_STATS_BASE_URL,
    fetch_country_prefixes_with_fallback, normalize_country_code,
    read_ipv4_prefixes_from_country_json, read_ipv4_prefixes_from_delegated_stats,
)
from .sources.networks import read_ipv4_prefixes_from_google_json


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=os.environ.get("ROUTES_FILE", "/etc/bird/generated/routes.conf"))
    parser.add_argument("--status", default=os.environ.get("STATUS_FILE", "/etc/bird/generated/status.json"))
    parser.add_argument("--metrics", default=os.environ.get("METRICS_FILE", "/etc/bird/generated/metrics.prom"))
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize routes without writing routes, status or metrics files.")
    parser.add_argument("--check-sources", action="store_true", help="Fetch/resolve sources and print their status without building or writing route files.")
    parser.add_argument("--allow-broad-routes", action="store_true", default=os.environ.get("ALLOW_BROAD_ROUTES", "0") == "1")
    parser.add_argument("--min-prefix-length", type=int, default=int(os.environ.get("MIN_PREFIX_LENGTH", DEFAULT_MIN_PREFIX_LENGTH)))
    args = parser.parse_args(argv)

    started_at = time.time()
    cache_max_age = env_int("CACHE_MAX_AGE", DEFAULT_CACHE_MAX_AGE)
    cache_dir = env_path(*GENERATED_PATH_SPECS["cache_dir"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    include_google = os.environ.get("INCLUDE_GOOGLE_RANGES", "1") == "1"

    output = Path(args.output)
    status_file = Path(args.status)
    metrics_file = Path(args.metrics)
    routes = {
        "base": 0,
        "include": 0,
        "exclude": 0,
        "candidate": 0,
        "after_exclusions": 0,
        "final": 0,
        "collapsed_removed": 0,
        "exclude_rules_applied": 0,
        "invalid": 0,
    }

    source_failed, sources, errors, base_text, include_text, exclude_text = collect_sources(
        cache_dir, cache_max_age, include_google
    )

    if args.check_sources:
        write_runtime_progress("completed", "Source check complete", active=False, items_done=len(sources), items_total=len(sources))
        success = not errors
        status = build_status(
            success,
            started_at,
            sources,
            routes,
            errors,
            cache_max_age,
            dry_run=args.dry_run,
            check_sources=True,
        )
        progress("source check complete", success=success)
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0 if success else 1

    if not source_failed:
        try:
            progress("parsing and validating collected routes")
            write_runtime_progress("building-routes", "Building final route set", items_done=len(sources), items_total=len(sources))
            networks, routes = parse_and_build_routes(
                output,
                base_text,
                include_text,
                exclude_text,
                args.min_prefix_length,
                args.allow_broad_routes,
            )

            if not networks:
                record = {"kind": "routes", "name": "generated", "status": "failed", "error": "generated route list is empty"}
                errors.append(record)
                source_failed = True
            elif not args.dry_run:
                progress("writing generated routes", final=len(networks))
                write_runtime_progress("writing-routes", "Writing generated routes", items_done=len(sources), items_total=len(sources))
                write_routes(output, networks)
        except RuntimeError as exc:
            record = {"kind": "routes", "name": "validation", "status": "failed", "error": str(exc)}
            errors.append(record)
            source_failed = True

    success = not source_failed
    status = build_status(success, started_at, sources, routes, errors, cache_max_age, dry_run=args.dry_run)

    if args.dry_run:
        write_runtime_progress("completed", "Dry run complete", active=False, items_done=len(sources), items_total=len(sources))
        progress("dry run complete", success=success, final_routes=routes["final"])
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        progress("writing status and metrics")
        write_runtime_progress("writing-status", "Writing status and metrics", items_done=len(sources), items_total=len(sources))
        write_json(status_file, status)
        write_metrics(metrics_file, status)

    progress("done", success=success, final_routes=routes["final"], duration_seconds=status["duration_seconds"])
    write_runtime_progress("completed", "Route update complete", active=False, items_done=len(sources), items_total=len(sources))
    print(f"Final routes: {routes['final']}")
    print(
        f"Source statuses: fresh={sum(1 for s in sources if s['status'] == 'fresh')} "
        f"cache={sum(1 for s in sources if s['status'] == 'cache')} "
        f"skipped={sum(1 for s in sources if s['status'] == 'skipped')} "
        f"failed={sum(1 for s in sources if s['status'] == 'failed')}"
    )

    return 0 if success else 1
