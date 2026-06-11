import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request

from . import generate_routes
from .logging import progress
from .runtime_paths import GENERATED_PATH_SPECS, LIST_FILE_SPECS, env_path, env_paths


DEFAULT_CACHE_MAX_AGE = 7 * 24 * 60 * 60
DEFAULT_MIN_PREFIX_LENGTH = 8

def env_int(name, default):
    value = os.environ.get(name, str(default))
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer")

    if number <= 0:
        raise SystemExit(f"{name} must be greater than zero")

    return number


def read_list(path):
    if not path.exists():
        return []

    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            result.append(value)

    return result


def cache_path(cache_dir, namespace, value, suffix=".cache"):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{namespace}-{digest}{suffix}"


def cache_age(cache_file, now):
    if not cache_file.exists():
        return None
    return max(0, int(now - cache_file.stat().st_mtime))


def read_cache(cache_file, now, max_age):
    age = cache_age(cache_file, now)
    if age is None or age > max_age or cache_file.stat().st_size == 0:
        return None, age
    return cache_file.read_text(encoding="utf-8"), age


def fetch_url(url, timeout=None, attempts=None, delay=None):
    timeout = int(os.environ.get("FETCH_TIMEOUT", "30")) if timeout is None else timeout
    attempts = int(os.environ.get("FETCH_ATTEMPTS", "5")) if attempts is None else attempts
    delay = float(os.environ.get("FETCH_RETRY_DELAY", "5")) if delay is None else delay
    last_error = None
    request = urllib.request.Request(url, headers={"User-Agent": "BGP-Antifilter/1.0"})

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace").replace("\r", "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay)

    raise RuntimeError(str(last_error))


def count_source_routes(text, *, extract=True):
    count = 0
    for line in text.splitlines():
        values = generate_routes.IPV4_RE.findall(line) if extract else [line.strip()]
        for value in values:
            if not value:
                continue
            if "/" not in value:
                value = f"{value}/32"
            try:
                ipaddress.ip_network(value, strict=False)
            except ValueError:
                continue
            count += 1
    return count


def fetch_text_source(kind, name, url, cache_file, now, max_age):
    record = {
        "kind": kind,
        "name": name,
        "url": url,
        "cache_file": str(cache_file),
        "status": "unknown",
        "cache_age_seconds": None,
        "error": None,
        "bytes": 0,
        "routes": 0,
    }

    try:
        text = fetch_url(url)
        cache_file.write_text(text, encoding="utf-8")
        record["status"] = "fresh"
        record["bytes"] = len(text.encode("utf-8"))
        record["routes"] = count_source_routes(text)
        record["cache_age_seconds"] = 0
        progress("fetched source", kind=kind, name=name, status="fresh")
        return text, record, True
    except RuntimeError as exc:
        text, age = read_cache(cache_file, now, max_age)
        record["cache_age_seconds"] = age

        if text is not None:
            record["status"] = "cache"
            record["error"] = str(exc)
            record["bytes"] = len(text.encode("utf-8"))
            record["routes"] = count_source_routes(text)
            progress("using cached source", kind=kind, name=name, status="cache", cache_age_seconds=age)
            return text, record, True

        record["status"] = "failed"
        record["error"] = str(exc) if age is None else f"{exc}; cache expired after {age} seconds"
        progress("source failed without usable cache", kind=kind, name=name, status="failed")
        return "", record, False


def resolve_domain(kind, domain, cache_file, now, max_age):
    record = {
        "kind": kind,
        "name": domain,
        "cache_file": str(cache_file),
        "status": "unknown",
        "cache_age_seconds": None,
        "error": None,
        "routes": 0,
    }

    try:
        addresses = sorted(
            {
                item[4][0]
                for item in socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
            }
        )
        if not addresses:
            raise RuntimeError("no IPv4 addresses returned")

        lines = [f"{address}/32" for address in addresses]
        text = "\n".join(lines) + "\n"
        cache_file.write_text(text, encoding="utf-8")
        record["status"] = "fresh"
        record["cache_age_seconds"] = 0
        record["routes"] = len(lines)
        progress("resolved domain", kind=kind, name=domain, routes=len(lines))
        return text, record, True
    except (socket.gaierror, OSError, RuntimeError) as exc:
        text, age = read_cache(cache_file, now, max_age)
        record["cache_age_seconds"] = age

        if text is not None:
            record["status"] = "cache"
            record["error"] = str(exc)
            record["routes"] = len([line for line in text.splitlines() if line.strip()])
            progress("using cached domain", kind=kind, name=domain, status="cache", cache_age_seconds=age)
            return text, record, True

        record["status"] = "failed"
        record["error"] = str(exc) if age is None else f"{exc}; cache expired after {age} seconds"
        progress("domain failed without usable cache", kind=kind, name=domain, status="failed")
        return "", record, False


def read_ipv4_prefixes_from_google_json(text):
    data = json.loads(text)
    networks = []

    for item in data.get("prefixes", []):
        prefix = item.get("ipv4Prefix")
        if prefix:
            networks.append(ipaddress.ip_network(prefix, strict=False))

    return networks


def subtract_networks(networks, excluded_networks):
    result = []

    for network in networks:
        remaining = [network]

        for excluded in excluded_networks:
            next_remaining = []

            for candidate in remaining:
                if not candidate.overlaps(excluded):
                    next_remaining.append(candidate)
                elif candidate.subnet_of(excluded):
                    continue
                elif excluded.subnet_of(candidate):
                    next_remaining.extend(candidate.address_exclude(excluded))
                else:
                    next_remaining.append(candidate)

            remaining = next_remaining

        result.extend(remaining)

    return generate_routes.collapse_routes(result)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_routes(path, networks):
    text = "".join(f"    route {network} blackhole;\n" for network in networks)
    write_text(path, text)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_metrics(path, status):
    states = {"fresh": 0, "cache": 0, "failed": 0, "skipped": 0, "disabled": 0}
    for source in status["sources"]:
        states[source["status"]] = states.get(source["status"], 0) + 1

    lines = [
        "# HELP bgp_antifilter_routes_total Number of generated BIRD static routes.",
        "# TYPE bgp_antifilter_routes_total gauge",
        f"bgp_antifilter_routes_total {status['routes']['final']}",
        "# HELP bgp_antifilter_last_update_timestamp_seconds Last update attempt Unix timestamp.",
        "# TYPE bgp_antifilter_last_update_timestamp_seconds gauge",
        f"bgp_antifilter_last_update_timestamp_seconds {status['updated_at_unix']}",
        "# HELP bgp_antifilter_update_success Whether the last route update succeeded.",
        "# TYPE bgp_antifilter_update_success gauge",
        f"bgp_antifilter_update_success {1 if status['success'] else 0}",
        "# HELP bgp_antifilter_update_duration_seconds Last update duration in seconds.",
        "# TYPE bgp_antifilter_update_duration_seconds gauge",
        f"bgp_antifilter_update_duration_seconds {status['duration_seconds']}",
        "# HELP bgp_antifilter_invalid_entries_total Invalid network entries skipped during the last update.",
        "# TYPE bgp_antifilter_invalid_entries_total gauge",
        f"bgp_antifilter_invalid_entries_total {status['routes']['invalid']}",
        "# HELP bgp_antifilter_exclude_rules_applied_total Exclude rules applied during the last update.",
        "# TYPE bgp_antifilter_exclude_rules_applied_total gauge",
        f"bgp_antifilter_exclude_rules_applied_total {status['routes']['exclude_rules_applied']}",
        "# HELP bgp_antifilter_source_status_total Sources grouped by last status.",
        "# TYPE bgp_antifilter_source_status_total gauge",
    ]

    for state, count in sorted(states.items()):
        lines.append(f'bgp_antifilter_source_status_total{{status="{state}"}} {count}')

    lines.extend([
        "# HELP bgp_antifilter_source_cache_age_seconds Cache age for sources that used cached data.",
        "# TYPE bgp_antifilter_source_cache_age_seconds gauge",
    ])
    for source in status["sources"]:
        age = source.get("cache_age_seconds")
        if age is not None:
            kind = str(source.get("kind", "source")).replace('"', "")
            name = str(source.get("name", "")).replace('"', "")
            lines.append(f'bgp_antifilter_source_cache_age_seconds{{kind="{kind}",name="{name}"}} {age}')

    write_text(path, "\n".join(lines) + "\n")


def build_status(success, started_at, sources, routes, errors, cache_max_age, dry_run=False, check_sources=False):
    now = int(time.time())
    return {
        "success": success,
        "dry_run": dry_run,
        "check_sources": check_sources,
        "updated_at_unix": now,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "duration_seconds": round(time.time() - started_at, 3),
        "cache_max_age_seconds": cache_max_age,
        "routes": routes,
        "sources": sources,
        "errors": errors,
    }


def unsafe_broad_routes(networks, min_prefix_length):
    return [
        network
        for network in networks
        if network.version == 4 and network.prefixlen < min_prefix_length
    ]


def cleanup_paths(paths):
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def parse_and_build_routes(output, base_text, include_text, exclude_text, min_prefix_length, allow_broad_routes):
    tmp_dir = output.parent
    tmp_base = tmp_dir / ".routes-base.tmp"
    tmp_include = tmp_dir / ".routes-include.tmp"
    tmp_exclude = tmp_dir / ".routes-exclude.tmp"
    tmp_paths = (tmp_base, tmp_include, tmp_exclude)

    try:
        write_text(tmp_base, "\n".join(base_text))
        write_text(tmp_include, "\n".join(include_text))
        write_text(tmp_exclude, "\n".join(exclude_text))

        base, base_invalid = generate_routes.read_networks(tmp_base, extract=True)
        exclude, exclude_invalid = generate_routes.read_networks(tmp_exclude)
        extra, extra_invalid = generate_routes.read_networks(tmp_include)

        broad = unsafe_broad_routes(base + extra, min_prefix_length)
        if broad and not allow_broad_routes:
            examples = ", ".join(str(network) for network in broad[:5])
            raise RuntimeError(
                f"refusing broad IPv4 routes shorter than /{min_prefix_length}: {examples}"
            )

        progress("building final route set", base=len(base), include=len(extra), exclude=len(exclude))
        networks, applied, route_stats = generate_routes.build_routes_with_stats(base, exclude, extra)
        routes = {
            "base": len(base),
            "include": len(extra),
            "exclude": len(exclude),
            "candidate": route_stats["candidate"],
            "after_exclusions": route_stats["after_exclusions"],
            "final": len(networks),
            "collapsed_removed": route_stats["collapsed_removed"],
            "exclude_rules_applied": applied,
            "invalid": base_invalid + exclude_invalid + extra_invalid,
        }
        return networks, routes
    finally:
        cleanup_paths(tmp_paths)


def collect_sources(cache_dir, cache_max_age, include_google):
    now = int(time.time())
    list_files = env_paths(LIST_FILE_SPECS)

    sources = []
    errors = []
    source_failed = False
    base_text = []
    include_text = []
    exclude_text = []

    url_sources = read_list(list_files["urls"])
    asn_sources = read_list(list_files["asns"])
    exclude_domains = read_list(list_files["exclude-domains"])
    include_domains = read_list(list_files["include-domains"])

    progress(
        "starting update",
        urls=len(url_sources),
        asns=len(asn_sources),
        exclude_domains=len(exclude_domains),
        include_domains=len(include_domains),
        google="enabled" if include_google else "disabled",
    )

    for index, url in enumerate(url_sources, 1):
        progress("fetching url", index=index, total=len(url_sources), url=url)
        text, record, ok = fetch_text_source("url", url, url, cache_path(cache_dir, "url", url), now, cache_max_age)
        sources.append(record)
        if ok:
            base_text.append(text)
        else:
            record["required"] = False
            progress("skipping unavailable URL source", url=url, status="failed")
            errors.append(record)

    for index, asn in enumerate(asn_sources, 1):
        progress("fetching ASN", index=index, total=len(asn_sources), asn=asn)
        asn_number = asn.upper().removeprefix("AS")
        if not asn_number.isdigit():
            record = {"kind": "asn", "name": asn, "status": "failed", "error": "invalid ASN"}
            sources.append(record)
            errors.append(record)
            source_failed = True
            continue

        url = f"https://api.routeviews.org/asn/{asn_number}"
        text, record, ok = fetch_text_source("asn", f"AS{asn_number}", url, cache_path(cache_dir, "asn", asn_number), now, cache_max_age)
        sources.append(record)
        source_failed = source_failed or not ok
        if ok:
            base_text.append(text)
        else:
            errors.append(record)

    if include_google:
        progress("fetching Google ranges")
        google_text, google_record, google_ok = fetch_text_source(
            "google", "goog.json", "https://www.gstatic.com/ipranges/goog.json",
            cache_path(cache_dir, "google", "goog.json", ".json"), now, cache_max_age
        )
        cloud_text, cloud_record, cloud_ok = fetch_text_source(
            "google", "cloud.json", "https://www.gstatic.com/ipranges/cloud.json",
            cache_path(cache_dir, "google", "cloud.json", ".json"), now, cache_max_age
        )
        sources.extend([google_record, cloud_record])
        source_failed = source_failed or not google_ok or not cloud_ok

        if google_ok and cloud_ok:
            try:
                progress("processing Google ranges")
                google = read_ipv4_prefixes_from_google_json(google_text)
                cloud = read_ipv4_prefixes_from_google_json(cloud_text)
                base_text.append("\n".join(str(network) for network in subtract_networks(google, cloud)) + "\n")
            except (json.JSONDecodeError, ValueError) as exc:
                record = {"kind": "google", "name": "processed-ranges", "status": "failed", "error": str(exc)}
                sources.append(record)
                errors.append(record)
                source_failed = True
        else:
            if not google_ok:
                errors.append(google_record)
            if not cloud_ok:
                errors.append(cloud_record)
    else:
        progress("skipping Google ranges", status="disabled")
        sources.append({"kind": "google", "name": "ranges", "status": "disabled"})

    for index, domain in enumerate(exclude_domains, 1):
        progress("resolving exclude domain", index=index, total=len(exclude_domains), domain=domain)
        text, record, ok = resolve_domain("exclude-domain", domain, cache_path(cache_dir, "exclude-domain", domain), now, cache_max_age)
        sources.append(record)
        source_failed = source_failed or not ok
        if ok:
            exclude_text.append(text)
        else:
            errors.append(record)

    for index, domain in enumerate(include_domains, 1):
        progress("resolving include domain", index=index, total=len(include_domains), domain=domain)
        text, record, ok = resolve_domain("include-domain", domain, cache_path(cache_dir, "include-domain", domain), now, cache_max_age)
        if ok:
            include_text.append(text)
        else:
            record["status"] = "skipped"
            record["required"] = False
            progress("skipping optional include domain", domain=domain, status="skipped")
        sources.append(record)

    return source_failed, sources, errors, base_text, include_text, exclude_text


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
                write_routes(output, networks)
        except RuntimeError as exc:
            record = {"kind": "routes", "name": "validation", "status": "failed", "error": str(exc)}
            errors.append(record)
            source_failed = True

    success = not source_failed
    status = build_status(success, started_at, sources, routes, errors, cache_max_age, dry_run=args.dry_run)

    if args.dry_run:
        progress("dry run complete", success=success, final_routes=routes["final"])
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        progress("writing status and metrics")
        write_json(status_file, status)
        write_metrics(metrics_file, status)

    progress("done", success=success, final_routes=routes["final"], duration_seconds=status["duration_seconds"])
    print(f"Final routes: {routes['final']}")
    print(
        f"Source statuses: fresh={sum(1 for s in sources if s['status'] == 'fresh')} "
        f"cache={sum(1 for s in sources if s['status'] == 'cache')} "
        f"skipped={sum(1 for s in sources if s['status'] == 'skipped')} "
        f"failed={sum(1 for s in sources if s['status'] == 'failed')}"
    )

    return 0 if success else 1
