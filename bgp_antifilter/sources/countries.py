"""Country prefixes from RIPE Stat with delegated registry fallback."""

import ipaddress
import json
import re

from .. import generate_routes
from ..logging import progress
from .fetch import cache_path, fetch_text_source

COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")
DELEGATED_REGISTRIES = ("afrinic", "apnic", "arin", "lacnic", "ripencc")
DELEGATED_STATS_BASE_URL = "https://ftp.apnic.net/pub/stats"


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


def collect_country_sources(ctx, country_sources):
    for index, country in enumerate(country_sources, 1):
        current_index = ctx.processed_items + 1
        ctx.update_progress(
            f"Fetching country {current_index}/{ctx.total_items}",
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
            ctx.sources.append(record)
            ctx.errors.append(record)
            ctx.source_failed = True
            ctx.processed_items += 1
            ctx.update_progress(
                f"Processed country {ctx.processed_items}/{ctx.total_items}",
                current_kind="country",
                current_name=country,
                current_index=ctx.processed_items,
            )
            continue

        try:
            networks, record, ok = fetch_country_prefixes_with_fallback(
                country_code,
                cache_dir=ctx.cache_dir,
                now=ctx.now,
                max_age=ctx.cache_max_age,
                dns_nameservers=ctx.dns_nameservers,
                progress_callback=lambda attempt, attempts, current_index=current_index, country_code=country_code: ctx.update_progress(
                    f"Fetching country {current_index}/{ctx.total_items}",
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
        ctx.sources.append(record)
        if ok:
            country_text = "\n".join(str(network) for network in networks)
            if country_text:
                ctx.base_text.append(country_text + "\n")
            progress(
                "processed country",
                country=country_code,
                routes=len(networks),
                source=record.get("source", "ripe-stat"),
            )
        else:
            ctx.errors.append(record)
            ctx.source_failed = True
        ctx.processed_items += 1
        ctx.update_progress(
            f"Processed country {ctx.processed_items}/{ctx.total_items}",
            current_kind="country",
            current_name=country_code,
            current_index=ctx.processed_items,
        )
