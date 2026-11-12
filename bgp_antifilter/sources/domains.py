"""Domain normalization, DNS cache and include/exclude domain sources."""

import ipaddress
import re
import socket

from .. import dns_resolver
from ..logging import progress
from .fetch import cache_path, fetch_text_source, read_cache

DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def normalize_domain_name(value):
    domain = str(value or "").strip().rstrip(".").lower()
    if not domain or any(char.isspace() for char in domain):
        return None
    if "://" in domain or "/" in domain or ":" in domain or domain.startswith("."):
        return None
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if len(domain) > 253:
        return None
    labels = domain.split(".")
    if any(not DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        return None
    return domain


def parse_domain_list(text):
    domains = []
    seen = set()
    invalid = 0
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        domain = normalize_domain_name(line)
        if domain is None:
            invalid += 1
            continue
        if domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains, invalid


def parse_ipv4_literal(value):
    try:
        return str(ipaddress.IPv4Address(str(value).strip()))
    except ipaddress.AddressValueError:
        return None


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
        literal_ipv4 = parse_ipv4_literal(domain)
        if literal_ipv4 is not None:
            addresses = [literal_ipv4]
        else:
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


def collect_domain_list_sources(ctx, domain_list_sources):
    for index, source in enumerate(domain_list_sources, 1):
        url = source["url"]
        source_name = source["name"] or url
        current_index = ctx.processed_items + 1
        ctx.update_progress(
            f"Fetching domain list URL {current_index}/{ctx.total_items}",
            current_kind="domain-list-url",
            current_name=source_name,
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching domain list url", index=index, total=len(domain_list_sources), name=source_name, url=url)
        text, record, ok = fetch_text_source(
            "domain-list-url",
            source_name,
            url,
            cache_path(ctx.cache_dir, "domain-list-url", url),
            ctx.now,
            ctx.cache_max_age,
            dns_nameservers=ctx.dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index, url=url: ctx.update_progress(
                f"Fetching domain list URL {current_index}/{ctx.total_items}",
                current_kind="domain-list-url",
                current_name=source_name,
                current_index=current_index,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.45, 0.1 + (attempt / max(1, attempts)) * 0.35),
            ),
        )
        record["required"] = ctx.require_all_url_sources
        record["domains"] = 0
        record["resolved_domains"] = 0
        record["cached_domains"] = 0
        record["skipped_domains"] = 0
        record["invalid_lines"] = 0
        record["routes"] = 0

        if ok:
            domains, invalid_lines = parse_domain_list(text)
            record["domains"] = len(domains)
            record["invalid_lines"] = invalid_lines
            resolved_routes = []
            skipped_domains = []

            for domain_index, domain in enumerate(domains, 1):
                domain_text, _domain_record, domain_ok = resolve_domain(
                    "domain-list-domain",
                    domain,
                    cache_path(ctx.cache_dir, "domain-list-domain", domain),
                    ctx.now,
                    ctx.cache_max_age,
                    dns_nameservers=ctx.dns_nameservers,
                    dns_timeout=ctx.dns_timeout,
                )
                if domain_ok:
                    if _domain_record["status"] == "cache":
                        record["cached_domains"] += 1
                    resolved_routes.append(domain_text)
                    record["resolved_domains"] += 1
                    record["routes"] += len([line for line in domain_text.splitlines() if line.strip()])
                else:
                    record["skipped_domains"] += 1
                    if len(skipped_domains) < 10:
                        skipped_domains.append(domain)
                ctx.update_progress(
                    f"Resolving domains from list {current_index}/{ctx.total_items}: {domain_index}/{max(1, len(domains))}",
                    current_kind="domain-list-url",
                    current_name=source_name,
                    current_index=current_index,
                    current_step=0.45 + 0.5 * (domain_index / max(1, len(domains))),
                )

            if skipped_domains:
                record["skipped_domain_samples"] = skipped_domains
            if record["cached_domains"]:
                record["download_status"] = record["status"]
                record["status"] = "cache"
            if domains:
                resolved_cache_file = cache_path(ctx.cache_dir, "domain-list-routes", url)
                resolved_cache_file.write_text("".join(resolved_routes), encoding="utf-8")
                record["resolved_cache_file"] = str(resolved_cache_file)
                ctx.include_text.extend(resolved_routes)
            else:
                ok = False
                record["status"] = "failed"
                record["error"] = "domain list contains no valid domains"

        if not ok:
            if ctx.require_all_url_sources:
                ctx.source_failed = True
            ctx.errors.append(record)
            progress(
                "required domain list URL failed" if ctx.require_all_url_sources else "skipping unavailable domain list URL",
                url=url,
                status="failed",
            )

        ctx.sources.append(record)
        ctx.processed_items += 1
        ctx.update_progress(
            f"Processed domain list URL {ctx.processed_items}/{ctx.total_items}",
            current_kind="domain-list-url",
            current_name=source_name,
            current_index=ctx.processed_items,
        )


def collect_exclude_domains(ctx, exclude_domains):
    for index, domain in enumerate(exclude_domains, 1):
        current_index = ctx.processed_items + 1
        ctx.update_progress(
            f"Resolving exclude domain {current_index}/{ctx.total_items}",
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
            cache_path(ctx.cache_dir, "exclude-domain", domain),
            ctx.now,
            ctx.cache_max_age,
            dns_nameservers=ctx.dns_nameservers,
            dns_timeout=ctx.dns_timeout,
        )
        ctx.sources.append(record)
        ctx.source_failed = ctx.source_failed or not ok
        if ok:
            ctx.exclude_text.append(text)
        else:
            ctx.errors.append(record)
        ctx.processed_items += 1
        ctx.update_progress(
            f"Processed exclude domain {ctx.processed_items}/{ctx.total_items}",
            current_kind="exclude-domain",
            current_name=domain,
            current_index=ctx.processed_items,
        )


def collect_include_domains(ctx, include_domains):
    for index, domain in enumerate(include_domains, 1):
        current_index = ctx.processed_items + 1
        ctx.update_progress(
            f"Resolving include domain {current_index}/{ctx.total_items}",
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
            cache_path(ctx.cache_dir, "include-domain", domain),
            ctx.now,
            ctx.cache_max_age,
            dns_nameservers=ctx.dns_nameservers,
            dns_timeout=ctx.dns_timeout,
        )
        if ok:
            ctx.include_text.append(text)
        else:
            record["status"] = "skipped"
            record["required"] = False
            progress("skipping optional include domain", domain=domain, status="skipped")
        ctx.sources.append(record)
        ctx.processed_items += 1
        ctx.update_progress(
            f"Processed include domain {ctx.processed_items}/{ctx.total_items}",
            current_kind="include-domain",
            current_name=domain,
            current_index=ctx.processed_items,
        )
