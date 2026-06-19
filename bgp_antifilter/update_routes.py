import argparse
import http.client
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

from . import dns_resolver
from . import generate_routes
from .logging import progress
from .runtime_paths import GENERATED_PATH_SPECS, LIST_FILE_SPECS, env_path, env_paths


DEFAULT_CACHE_MAX_AGE = 7 * 24 * 60 * 60
DEFAULT_MIN_PREFIX_LENGTH = 8
DEFAULT_DNS_HTTP_REDIRECTS = 5
COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")
DELEGATED_REGISTRIES = ("afrinic", "apnic", "arin", "lacnic", "ripencc")
DELEGATED_STATS_BASE_URL = "https://ftp.apnic.net/pub/stats"
PROGRESS_STEPS = {
    "collecting-sources": 15,
    "building-routes": 70,
    "writing-routes": 85,
    "writing-status": 95,
    "completed": 100,
}


class CustomDnsHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, connect_host, connect_port, *, server_hostname, timeout):
        super().__init__(server_hostname, connect_port, timeout=timeout)
        self._connect_host = connect_host

    def connect(self):
        sock = socket.create_connection((self._connect_host, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name, str(default))
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer")

    if number <= 0:
        raise SystemExit(f"{name} must be greater than zero")

    return number


def env_float(name, default):
    value = os.environ.get(name, str(default))
    try:
        number = float(value)
    except ValueError:
        raise SystemExit(f"{name} must be a number")
    if number <= 0:
        raise SystemExit(f"{name} must be greater than zero")
    return number


def write_runtime_progress(
    stage,
    message,
    *,
    active=True,
    percent=None,
    items_done=None,
    items_total=None,
    current_kind=None,
    current_name=None,
    current_index=None,
    current_attempt=None,
    current_attempt_total=None,
):
    runtime_file = env_path(*GENERATED_PATH_SPECS["runtime_file"])
    value = PROGRESS_STEPS.get(stage, 0 if active else 100) if percent is None else percent
    try:
        data = json.loads(runtime_file.read_text(encoding="utf-8")) if runtime_file.exists() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    data.update({
        "generation_active": active,
        "generation_stage": stage,
        "generation_stage_message": message,
        "generation_progress_percent": max(0, min(100, int(value))),
        "generation_items_done": items_done,
        "generation_items_total": items_total,
        "generation_current_kind": current_kind,
        "generation_current_name": current_name,
        "generation_current_index": current_index,
        "generation_current_attempt": current_attempt,
        "generation_current_attempt_total": current_attempt_total,
    })
    try:
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = runtime_file.with_suffix(runtime_file.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(runtime_file)
    except OSError:
        # Runtime progress is best-effort and must not break CLI/test execution
        return


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


def fetch_via_custom_dns(url, *, timeout, nameservers):
    current_url = url
    headers = {"User-Agent": "BGP-Antifilter/1.0"}

    for _ in range(DEFAULT_DNS_HTTP_REDIRECTS + 1):
        parts = urlsplit(current_url)
        if parts.scheme not in {"http", "https"}:
            raise RuntimeError(f"unsupported URL scheme: {parts.scheme}")
        if not parts.hostname:
            raise RuntimeError("URL hostname is required")

        port = parts.port or (443 if parts.scheme == "https" else 80)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"

        addresses = dns_resolver.resolve_ipv4_addresses(parts.hostname, nameservers=nameservers, timeout=timeout)
        if not addresses:
            raise RuntimeError(f"no IPv4 addresses returned for {parts.hostname}")
        address = addresses[0]

        if parts.scheme == "https":
            connection = CustomDnsHTTPSConnection(
                address,
                port,
                server_hostname=parts.hostname,
                timeout=timeout,
            )
        else:
            connection = http.client.HTTPConnection(address, port, timeout=timeout)
        try:
            connection.putrequest("GET", path, skip_host=True)
            host_header = parts.hostname if parts.port is None else f"{parts.hostname}:{parts.port}"
            connection.putheader("Host", host_header)
            for key, value in headers.items():
                connection.putheader(key, value)
            connection.endheaders()
            response = connection.getresponse()
            status = response.status

            if status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                response.read()
                if not location:
                    raise RuntimeError(f"redirect {status} without Location header")
                current_url = urljoin(current_url, location)
                continue

            if status >= 400:
                body = response.read(200).decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP Error {status}: {body or response.reason}")

            return response.read().decode("utf-8", errors="replace").replace("\r", "")
        finally:
            connection.close()

    raise RuntimeError("too many HTTP redirects")


def fetch_url(url, timeout=None, attempts=None, delay=None, progress_callback=None, dns_nameservers=None):
    timeout = int(os.environ.get("FETCH_TIMEOUT", "30")) if timeout is None else timeout
    attempts = int(os.environ.get("FETCH_ATTEMPTS", "5")) if attempts is None else attempts
    delay = float(os.environ.get("FETCH_RETRY_DELAY", "5")) if delay is None else delay
    last_error = None
    request = urllib.request.Request(url, headers={"User-Agent": "BGP-Antifilter/1.0"})

    for attempt in range(attempts):
        if progress_callback is not None:
            progress_callback(attempt + 1, attempts)
        try:
            if dns_nameservers:
                return fetch_via_custom_dns(url, timeout=timeout, nameservers=dns_nameservers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace").replace("\r", "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        except RuntimeError as exc:
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


def fetch_text_source(kind, name, url, cache_file, now, max_age, progress_callback=None, dns_nameservers=None):
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
        text = fetch_url(url, progress_callback=progress_callback, dns_nameservers=dns_nameservers)
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


def resolve_domain(kind, domain, cache_file, now, max_age, dns_nameservers=None, dns_timeout=dns_resolver.DEFAULT_TIMEOUT):
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
        addresses = dns_resolver.resolve_ipv4_addresses(
            domain,
            nameservers=dns_nameservers,
            timeout=dns_timeout,
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


def normalize_country_code(value):
    code = str(value or "").strip().upper()
    if not COUNTRY_CODE_RE.fullmatch(code):
        raise ValueError("country code must be a 2-letter ISO code")
    return code


def read_ipv4_prefixes_from_country_json(text, country_code):
    data = json.loads(text)
    resources = data.get("data", {}).get("resources", {})
    prefixes = resources.get("ipv4")
    if not isinstance(prefixes, list):
        raise ValueError(f"country source for {country_code} does not contain an IPv4 prefix list")

    networks = []
    for item in prefixes:
        if not isinstance(item, str):
            continue
        networks.append(ipaddress.ip_network(item, strict=False))

    return generate_routes.collapse_routes(networks)


def read_ipv4_prefixes_from_delegated_stats(text, country_code):
    networks = []

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 7:
            continue
        registry, cc, resource_type, start, value, _date, _status = parts[:7]
        if registry == "version" or value == "summary":
            continue
        if cc.upper() != country_code or resource_type != "ipv4":
            continue
        try:
            start_ip = ipaddress.IPv4Address(start)
            count = int(value)
        except (ipaddress.AddressValueError, ValueError):
            continue
        if count <= 0:
            continue
        end_ip = ipaddress.IPv4Address(int(start_ip) + count - 1)
        networks.extend(ipaddress.summarize_address_range(start_ip, end_ip))

    return generate_routes.collapse_routes(networks)


def fetch_country_prefixes_with_fallback(
    country_code,
    *,
    cache_dir,
    now,
    max_age,
    dns_nameservers,
    progress_callback=None,
):
    primary_url = (
        "https://stat.ripe.net/data/country-resource-list/data.json"
        f"?resource={country_code.lower()}&v4_format=prefix"
    )
    primary_cache = cache_path(cache_dir, "country", country_code)
    primary_text, primary_record, primary_ok = fetch_text_source(
        "country",
        country_code,
        primary_url,
        primary_cache,
        now,
        max_age,
        dns_nameservers=dns_nameservers,
        progress_callback=progress_callback,
    )

    if primary_ok:
        networks = read_ipv4_prefixes_from_country_json(primary_text, country_code)
        primary_record["routes"] = len(networks)
        primary_record["source"] = "ripe-stat"
        return networks, primary_record, True

    fallback_networks = []
    fallback_statuses = []
    fallback_errors = []

    for registry in DELEGATED_REGISTRIES:
        delegated_url = f"{DELEGATED_STATS_BASE_URL}/{registry}/delegated-{registry}-latest"
        delegated_cache = cache_path(cache_dir, "country-registry", registry)
        delegated_text, delegated_record, delegated_ok = fetch_text_source(
            "country-registry",
            registry,
            delegated_url,
            delegated_cache,
            now,
            max_age,
            dns_nameservers=dns_nameservers,
        )
        fallback_statuses.append(delegated_record["status"])
        if not delegated_ok:
            fallback_errors.append(f"{registry}: {delegated_record['error']}")
            continue
        fallback_networks.extend(read_ipv4_prefixes_from_delegated_stats(delegated_text, country_code))

    if fallback_errors:
        primary_record["error"] = "; ".join([primary_record["error"], *fallback_errors] if primary_record["error"] else fallback_errors)
        return [], primary_record, False

    networks = generate_routes.collapse_routes(fallback_networks)
    primary_record["routes"] = len(networks)
    primary_record["status"] = "fresh" if any(status == "fresh" for status in fallback_statuses) else "cache"
    primary_record["source"] = "delegated-stats"
    if primary_record.get("error"):
        primary_record["fallback_error"] = primary_record["error"]
    primary_record["error"] = None
    return networks, primary_record, True


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
    degraded = os.environ.get("DEGRADED", "0") == "1"
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
    require_all_url_sources = env_bool("REQUIRE_ALL_URL_SOURCES", default=False)
    dns_nameservers = dns_resolver.parse_nameservers(os.environ.get("DNS_RESOLVERS", ""))
    dns_timeout = env_float("DNS_RESOLVE_TIMEOUT", dns_resolver.DEFAULT_TIMEOUT)

    sources = []
    errors = []
    source_failed = False
    base_text = []
    include_text = []
    exclude_text = []

    url_sources = read_list(list_files["urls"])
    asn_sources = read_list(list_files["asns"])
    country_sources = read_list(list_files["countries"])
    exclude_domains = read_list(list_files["exclude-domains"])
    include_domains = read_list(list_files["include-domains"])
    total_items = (
        len(url_sources)
        + len(asn_sources)
        + len(country_sources)
        + len(exclude_domains)
        + len(include_domains)
        + (2 if include_google else 0)
    )
    processed_items = 0

    def update_collection_progress(
        message,
        *,
        current_kind=None,
        current_name=None,
        current_index=None,
        current_attempt=None,
        current_attempt_total=None,
        current_step=0.0,
    ):
        if total_items <= 0:
            percent = 65
        else:
            ratio = min(total_items, max(0.0, processed_items + current_step)) / total_items
            percent = 10 + round(ratio * 55)
        write_runtime_progress(
            "collecting-sources",
            message,
            percent=percent,
            items_done=processed_items,
            items_total=total_items,
            current_kind=current_kind,
            current_name=current_name,
            current_index=current_index,
            current_attempt=current_attempt,
            current_attempt_total=current_attempt_total,
        )

    update_collection_progress("Collecting route sources")

    progress(
        "starting update",
        urls=len(url_sources),
        asns=len(asn_sources),
        countries=len(country_sources),
        exclude_domains=len(exclude_domains),
        include_domains=len(include_domains),
        google="enabled" if include_google else "disabled",
    )

    for index, url in enumerate(url_sources, 1):
        current_index = processed_items + 1
        update_collection_progress(
            f"Fetching URL {current_index}/{total_items}",
            current_kind="url",
            current_name=url,
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching url", index=index, total=len(url_sources), url=url)
        text, record, ok = fetch_text_source(
            "url",
            url,
            url,
            cache_path(cache_dir, "url", url),
            now,
            cache_max_age,
            dns_nameservers=dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index, url=url: update_collection_progress(
                f"Fetching URL {current_index}/{total_items}",
                current_kind="url",
                current_name=url,
                current_index=current_index,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.9, attempt / max(1, attempts)),
            ),
        )
        record["required"] = require_all_url_sources
        sources.append(record)
        if require_all_url_sources:
            source_failed = source_failed or not ok
        if ok:
            base_text.append(text)
        else:
            progress(
                "required URL source failed" if require_all_url_sources else "skipping unavailable URL source",
                url=url,
                status="failed",
            )
            errors.append(record)
        processed_items += 1
        update_collection_progress(
            f"Processed URL {processed_items}/{total_items}",
            current_kind="url",
            current_name=url,
            current_index=processed_items,
        )

    for index, asn in enumerate(asn_sources, 1):
        current_index = processed_items + 1
        update_collection_progress(
            f"Fetching ASN {current_index}/{total_items}",
            current_kind="asn",
            current_name=asn,
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching ASN", index=index, total=len(asn_sources), asn=asn)
        asn_number = asn.upper().removeprefix("AS")
        if not asn_number.isdigit():
            record = {"kind": "asn", "name": asn, "status": "failed", "error": "invalid ASN"}
            sources.append(record)
            errors.append(record)
            source_failed = True
            processed_items += 1
            update_collection_progress(
                f"Processed ASN {processed_items}/{total_items}",
                current_kind="asn",
                current_name=asn,
                current_index=processed_items,
            )
            continue

        url = f"https://api.routeviews.org/asn/{asn_number}"
        text, record, ok = fetch_text_source(
            "asn",
            f"AS{asn_number}",
            url,
            cache_path(cache_dir, "asn", asn_number),
            now,
            cache_max_age,
            dns_nameservers=dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index, asn=asn: update_collection_progress(
                f"Fetching ASN {current_index}/{total_items}",
                current_kind="asn",
                current_name=asn,
                current_index=current_index,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.9, attempt / max(1, attempts)),
            ),
        )
        sources.append(record)
        source_failed = source_failed or not ok
        if ok:
            base_text.append(text)
        else:
            errors.append(record)
        processed_items += 1
        update_collection_progress(
            f"Processed ASN {processed_items}/{total_items}",
            current_kind="asn",
            current_name=f"AS{asn_number}",
            current_index=processed_items,
        )

    for index, country in enumerate(country_sources, 1):
        current_index = processed_items + 1
        update_collection_progress(
            f"Fetching country {current_index}/{total_items}",
            current_kind="country",
            current_name=country,
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching country", index=index, total=len(country_sources), country=country)
        try:
            country_code = normalize_country_code(country)
        except ValueError as exc:
            record = {"kind": "country", "name": country, "status": "failed", "error": str(exc)}
            sources.append(record)
            errors.append(record)
            source_failed = True
            processed_items += 1
            update_collection_progress(
                f"Processed country {processed_items}/{total_items}",
                current_kind="country",
                current_name=country,
                current_index=processed_items,
            )
            continue

        try:
            networks, record, ok = fetch_country_prefixes_with_fallback(
                country_code,
                cache_dir=cache_dir,
                now=now,
                max_age=cache_max_age,
                dns_nameservers=dns_nameservers,
                progress_callback=lambda attempt, attempts, current_index=current_index, country_code=country_code: update_collection_progress(
                f"Fetching country {current_index}/{total_items}",
                current_kind="country",
                current_name=country_code,
                current_index=current_index,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.9, attempt / max(1, attempts)),
            ),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            record = {
                "kind": "country",
                "name": country_code,
                "status": "failed",
                "error": str(exc),
                "routes": 0,
            }
            ok = False
            networks = []
        sources.append(record)
        if ok:
            country_text = "\n".join(str(network) for network in networks)
            if country_text:
                base_text.append(country_text + "\n")
            progress(
                "processed country",
                country=country_code,
                routes=len(networks),
                source=record.get("source", "ripe-stat"),
            )
        else:
            errors.append(record)
            source_failed = True
        processed_items += 1
        update_collection_progress(
            f"Processed country {processed_items}/{total_items}",
            current_kind="country",
            current_name=country_code,
            current_index=processed_items,
        )

    if include_google:
        current_index = processed_items + 1
        update_collection_progress(
            f"Fetching Google ranges {current_index}-{current_index + 1}/{total_items}",
            current_kind="google",
            current_name="goog.json / cloud.json",
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching Google ranges")
        google_text, google_record, google_ok = fetch_text_source(
            "google", "goog.json", "https://www.gstatic.com/ipranges/goog.json",
            cache_path(cache_dir, "google", "goog.json", ".json"), now, cache_max_age,
            dns_nameservers=dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index: update_collection_progress(
                f"Fetching Google ranges {current_index}-{current_index + 1}/{total_items}",
                current_kind="google",
                current_name="goog.json",
                current_index=current_index,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.45, attempt / max(1, attempts) * 0.45),
            ),
        )
        cloud_text, cloud_record, cloud_ok = fetch_text_source(
            "google", "cloud.json", "https://www.gstatic.com/ipranges/cloud.json",
            cache_path(cache_dir, "google", "cloud.json", ".json"), now, cache_max_age,
            dns_nameservers=dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index: update_collection_progress(
                f"Fetching Google ranges {current_index}-{current_index + 1}/{total_items}",
                current_kind="google",
                current_name="cloud.json",
                current_index=current_index + 1,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.9, 0.45 + (attempt / max(1, attempts) * 0.45)),
            ),
        )
        sources.extend([google_record, cloud_record])
        source_failed = source_failed or not google_ok or not cloud_ok
        processed_items += 2
        update_collection_progress(
            f"Processed Google ranges {processed_items}/{total_items}",
            current_kind="google",
            current_name="goog.json / cloud.json",
            current_index=processed_items,
        )

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
        current_index = processed_items + 1
        update_collection_progress(
            f"Resolving exclude domain {current_index}/{total_items}",
            current_kind="exclude-domain",
            current_name=domain,
            current_index=current_index,
            current_attempt=1,
            current_attempt_total=1,
            current_step=0.15,
        )
        progress("resolving exclude domain", index=index, total=len(exclude_domains), domain=domain)
        text, record, ok = resolve_domain(
            "exclude-domain",
            domain,
            cache_path(cache_dir, "exclude-domain", domain),
            now,
            cache_max_age,
            dns_nameservers=dns_nameservers,
            dns_timeout=dns_timeout,
        )
        sources.append(record)
        source_failed = source_failed or not ok
        if ok:
            exclude_text.append(text)
        else:
            errors.append(record)
        processed_items += 1
        update_collection_progress(
            f"Processed exclude domain {processed_items}/{total_items}",
            current_kind="exclude-domain",
            current_name=domain,
            current_index=processed_items,
        )

    for index, domain in enumerate(include_domains, 1):
        current_index = processed_items + 1
        update_collection_progress(
            f"Resolving include domain {current_index}/{total_items}",
            current_kind="include-domain",
            current_name=domain,
            current_index=current_index,
            current_attempt=1,
            current_attempt_total=1,
            current_step=0.15,
        )
        progress("resolving include domain", index=index, total=len(include_domains), domain=domain)
        text, record, ok = resolve_domain(
            "include-domain",
            domain,
            cache_path(cache_dir, "include-domain", domain),
            now,
            cache_max_age,
            dns_nameservers=dns_nameservers,
            dns_timeout=dns_timeout,
        )
        if ok:
            include_text.append(text)
        else:
            record["status"] = "skipped"
            record["required"] = False
            progress("skipping optional include domain", domain=domain, status="skipped")
        sources.append(record)
        processed_items += 1
        update_collection_progress(
            f"Processed include domain {processed_items}/{total_items}",
            current_kind="include-domain",
            current_name=domain,
            current_index=processed_items,
        )

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
