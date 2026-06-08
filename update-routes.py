#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request


DEFAULT_CACHE_MAX_AGE = 7 * 24 * 60 * 60
ROOT = Path(__file__).resolve().parent


def load_generator():
    module_path = ROOT / "generate-routes.py"
    spec = importlib.util.spec_from_file_location("generate_routes", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate_routes = load_generator()


def progress(message):
    print(f"[progress] {message}", flush=True)


def env_path(name, default):
    return Path(os.environ.get(name, default))


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


def fetch_url(url, timeout=30, attempts=5, delay=5):
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
    }

    try:
        text = fetch_url(url)
        cache_file.write_text(text, encoding="utf-8")
        record["status"] = "fresh"
        record["bytes"] = len(text.encode("utf-8"))
        record["cache_age_seconds"] = 0
        print(f"Fetched {kind} {name}", file=sys.stderr)
        return text, record, True
    except RuntimeError as exc:
        text, age = read_cache(cache_file, now, max_age)
        record["cache_age_seconds"] = age

        if text is not None:
            record["status"] = "cache"
            record["error"] = str(exc)
            record["bytes"] = len(text.encode("utf-8"))
            print(f"Failed to fetch {kind} {name}, using cache", file=sys.stderr)
            return text, record, True

        record["status"] = "failed"
        record["error"] = str(exc) if age is None else f"{exc}; cache expired after {age} seconds"
        print(f"Failed to fetch {kind} {name} and no valid cache is available", file=sys.stderr)
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
        print(f"Resolved {kind} {domain}", file=sys.stderr)
        return text, record, True
    except (socket.gaierror, OSError, RuntimeError) as exc:
        text, age = read_cache(cache_file, now, max_age)
        record["cache_age_seconds"] = age

        if text is not None:
            record["status"] = "cache"
            record["error"] = str(exc)
            record["routes"] = len([line for line in text.splitlines() if line.strip()])
            print(f"Failed to resolve {kind} {domain}, using cache", file=sys.stderr)
            return text, record, True

        record["status"] = "failed"
        record["error"] = str(exc) if age is None else f"{exc}; cache expired after {age} seconds"
        print(f"Failed to resolve {kind} {domain} and no valid cache is available", file=sys.stderr)
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
        "# HELP bgp_antifilter_source_status_total Sources grouped by last status.",
        "# TYPE bgp_antifilter_source_status_total gauge",
    ]

    for state, count in sorted(states.items()):
        lines.append(f'bgp_antifilter_source_status_total{{status="{state}"}} {count}')

    write_text(path, "\n".join(lines) + "\n")


def build_status(success, started_at, sources, routes, errors, cache_max_age):
    now = int(time.time())
    return {
        "success": success,
        "updated_at_unix": now,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "duration_seconds": round(time.time() - started_at, 3),
        "cache_max_age_seconds": cache_max_age,
        "routes": routes,
        "sources": sources,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=os.environ.get("ROUTES_FILE", "/etc/bird/generated/routes.conf"))
    parser.add_argument("--status", default=os.environ.get("STATUS_FILE", "/etc/bird/generated/status.json"))
    parser.add_argument("--metrics", default=os.environ.get("METRICS_FILE", "/etc/bird/generated/metrics.prom"))
    args = parser.parse_args()

    started_at = time.time()
    now = int(started_at)
    cache_max_age = env_int("CACHE_MAX_AGE", DEFAULT_CACHE_MAX_AGE)
    cache_dir = env_path("CACHE_DIR", "/etc/bird/generated/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    lists_file = env_path("LISTS_FILE", "/etc/bird/lists.txt")
    include_asns_file = env_path("INCLUDE_ASNS_FILE", "/etc/bird/include-asns.txt")
    include_domains_file = env_path("INCLUDE_DOMAINS_FILE", "/etc/bird/include-domains.txt")
    exclude_domains_file = env_path("EXCLUDE_DOMAINS_FILE", "/etc/bird/exclude-domains.txt")
    include_google = os.environ.get("INCLUDE_GOOGLE_RANGES", "1") == "1"

    sources = []
    errors = []
    source_failed = False
    base_text = []
    include_text = []
    exclude_text = []

    url_sources = read_list(lists_file)
    asn_sources = read_list(include_asns_file)
    exclude_domains = read_list(exclude_domains_file)
    include_domains = read_list(include_domains_file)

    progress(
        "starting update: "
        f"urls={len(url_sources)}, asns={len(asn_sources)}, "
        f"exclude_domains={len(exclude_domains)}, include_domains={len(include_domains)}, "
        f"google={'enabled' if include_google else 'disabled'}"
    )

    for index, url in enumerate(url_sources, 1):
        progress(f"fetching url {index}/{len(url_sources)}: {url}")
        text, record, ok = fetch_text_source("url", url, url, cache_path(cache_dir, "url", url), now, cache_max_age)
        sources.append(record)
        source_failed = source_failed or not ok
        if ok:
            base_text.append(text)
        else:
            errors.append(record)

    for index, asn in enumerate(asn_sources, 1):
        progress(f"fetching ASN {index}/{len(asn_sources)}: {asn}")
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
        progress("fetching Google ranges: goog.json and cloud.json")
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
                progress("processing Google ranges: subtracting cloud prefixes")
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
        progress("skipping Google ranges: disabled")
        sources.append({"kind": "google", "name": "ranges", "status": "disabled"})

    for index, domain in enumerate(exclude_domains, 1):
        progress(f"resolving exclude domain {index}/{len(exclude_domains)}: {domain}")
        text, record, ok = resolve_domain("exclude-domain", domain, cache_path(cache_dir, "exclude-domain", domain), now, cache_max_age)
        sources.append(record)
        source_failed = source_failed or not ok
        if ok:
            exclude_text.append(text)
        else:
            errors.append(record)

    for index, domain in enumerate(include_domains, 1):
        progress(f"resolving include domain {index}/{len(include_domains)}: {domain}")
        text, record, ok = resolve_domain("include-domain", domain, cache_path(cache_dir, "include-domain", domain), now, cache_max_age)
        if ok:
            include_text.append(text)
        else:
            record["status"] = "skipped"
            record["required"] = False
            print(f"Skipping optional include-domain {domain}", file=sys.stderr)
        sources.append(record)

    output = Path(args.output)
    status_file = Path(args.status)
    metrics_file = Path(args.metrics)
    routes = {"base": 0, "include": 0, "exclude": 0, "final": 0, "exclude_rules_applied": 0, "invalid": 0}

    if not source_failed:
        progress("parsing and validating collected routes")
        tmp_dir = output.parent
        tmp_base = tmp_dir / ".routes-base.tmp"
        tmp_include = tmp_dir / ".routes-include.tmp"
        tmp_exclude = tmp_dir / ".routes-exclude.tmp"

        write_text(tmp_base, "\n".join(base_text))
        write_text(tmp_include, "\n".join(include_text))
        write_text(tmp_exclude, "\n".join(exclude_text))

        base, base_invalid = generate_routes.read_networks(tmp_base, extract=True)
        exclude, exclude_invalid = generate_routes.read_networks(tmp_exclude)
        extra, extra_invalid = generate_routes.read_networks(tmp_include)
        progress(f"building final route set: base={len(base)}, include={len(extra)}, exclude={len(exclude)}")
        networks, applied = generate_routes.build_routes(base, exclude, extra)

        routes = {
            "base": len(base),
            "include": len(extra),
            "exclude": len(exclude),
            "final": len(networks),
            "exclude_rules_applied": applied,
            "invalid": base_invalid + exclude_invalid + extra_invalid,
        }

        if networks:
            progress(f"writing generated routes: final={len(networks)}")
            write_routes(output, networks)
        else:
            record = {"kind": "routes", "name": "generated", "status": "failed", "error": "generated route list is empty"}
            errors.append(record)
            source_failed = True

        for path in (tmp_base, tmp_include, tmp_exclude):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    success = not source_failed
    status = build_status(success, started_at, sources, routes, errors, cache_max_age)
    progress("writing status and metrics")
    write_json(status_file, status)
    write_metrics(metrics_file, status)

    progress(f"done: success={success}, final_routes={routes['final']}, duration={status['duration_seconds']}s")
    print(f"Final routes: {routes['final']}")
    print(
        f"Source statuses: fresh={sum(1 for s in sources if s['status'] == 'fresh')} "
        f"cache={sum(1 for s in sources if s['status'] == 'cache')} "
        f"skipped={sum(1 for s in sources if s['status'] == 'skipped')} "
        f"failed={sum(1 for s in sources if s['status'] == 'failed')}"
    )

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
