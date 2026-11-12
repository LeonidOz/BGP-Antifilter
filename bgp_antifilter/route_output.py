"""Route files, status snapshots and Prometheus metrics."""

import json
import os
import time

from .runtime_paths import GENERATED_PATH_SPECS, env_path
from .state_store import write_state


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_routes(path, networks):
    text = "".join(f"    route {network} blackhole;\n" for network in networks)
    write_text(path, text)


def write_json(path, data):
    write_state(path, data)


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
    degraded = os.environ.get("DEGRADED", "0") == "1"
    network_status_file = env_path(*GENERATED_PATH_SPECS["network_status_file"])
    try:
        network = json.loads(network_status_file.read_text(encoding="utf-8")) if network_status_file.exists() else {}
    except (OSError, json.JSONDecodeError):
        network = {}
    return {
        "success": success,
        "degraded": degraded,
        "degraded_reason": os.environ.get("DEGRADED_REASON", "") if degraded else "",
        "dry_run": dry_run,
        "check_sources": check_sources,
        "run_reason": os.environ.get("ROUTE_UPDATE_REASON", "manual"),
        "run_message": os.environ.get("ROUTE_UPDATE_MESSAGE", ""),
        "updated_at_unix": now,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "duration_seconds": round(time.time() - started_at, 3),
        "cache_max_age_seconds": cache_max_age,
        "routes": routes,
        "sources": sources,
        "errors": errors,
        "network": network,
    }
