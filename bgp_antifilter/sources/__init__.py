"""Collect route sources in the established order and report progress.

Providers update one collection context. Their records, cache namespaces and
required/optional failure policies remain specific to each source type.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import time

from .. import dns_resolver
from ..logging import progress
from ..runtime_paths import list_paths
from ..runtime_state import write_runtime_progress
from ..update_config import env_bool, env_float
from .countries import collect_country_sources
from .domains import collect_domain_list_sources, collect_exclude_domains, collect_include_domains
from .networks import collect_asn_sources, collect_google_ranges, collect_url_sources


def read_list(path):
    if not path.exists():
        return []

    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            result.append(value)

    return result


def parse_named_url_list(path):
    if not path.exists():
        return []

    result = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", line):
            name, url = line.split("|", 1)
            name = name.strip()
            url = url.strip()
        else:
            name = ""
            url = line
        if not url:
            continue
        result.append({"name": name, "url": url})

    return result


@dataclass
class SourceCollection:
    cache_dir: Path
    cache_max_age: int
    now: int
    require_all_url_sources: bool
    dns_nameservers: list[str]
    dns_timeout: float
    total_items: int
    processed_items: int = 0
    source_failed: bool = False
    sources: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    base_text: list[str] = field(default_factory=list)
    include_text: list[str] = field(default_factory=list)
    exclude_text: list[str] = field(default_factory=list)

    def update_progress(
        self, message, *, current_kind=None, current_name=None,
        current_index=None, current_attempt=None, current_attempt_total=None,
        current_step=0.0,
    ):
        if self.total_items <= 0:
            percent = 65
        else:
            ratio = min(self.total_items, max(0.0, self.processed_items + current_step)) / self.total_items
            percent = 10 + round(ratio * 55)
        write_runtime_progress(
            "collecting-sources", message, percent=percent,
            items_done=self.processed_items, items_total=self.total_items,
            current_kind=current_kind, current_name=current_name,
            current_index=current_index, current_attempt=current_attempt,
            current_attempt_total=current_attempt_total,
        )


def collect_sources(cache_dir, cache_max_age, include_google):
    now = int(time.time())
    list_files = list_paths()
    require_all_url_sources = env_bool("REQUIRE_ALL_URL_SOURCES", default=False)
    dns_nameservers = dns_resolver.parse_nameservers(os.environ.get("DNS_RESOLVERS", ""))
    dns_timeout = env_float("DNS_RESOLVE_TIMEOUT", dns_resolver.DEFAULT_TIMEOUT)
    url_sources = parse_named_url_list(list_files["urls"])
    domain_list_sources = parse_named_url_list(list_files["domain-list-urls"])
    asn_sources = read_list(list_files["asns"])
    country_sources = read_list(list_files["countries"])
    exclude_domains = read_list(list_files["exclude-domains"])
    include_domains = read_list(list_files["include-domains"])
    total_items = (
        len(url_sources) + len(domain_list_sources) + len(asn_sources)
        + len(country_sources) + len(exclude_domains) + len(include_domains)
        + (2 if include_google else 0)
    )
    ctx = SourceCollection(
        cache_dir=cache_dir, cache_max_age=cache_max_age, now=now,
        require_all_url_sources=require_all_url_sources,
        dns_nameservers=dns_nameservers, dns_timeout=dns_timeout, total_items=total_items,
    )
    ctx.update_progress("Collecting route sources")
    progress(
        "starting update", urls=len(url_sources), domain_list_urls=len(domain_list_sources),
        asns=len(asn_sources), countries=len(country_sources),
        exclude_domains=len(exclude_domains), include_domains=len(include_domains),
        google="enabled" if include_google else "disabled",
    )
    collect_url_sources(ctx, url_sources)
    collect_domain_list_sources(ctx, domain_list_sources)
    collect_asn_sources(ctx, asn_sources)
    collect_country_sources(ctx, country_sources)
    collect_google_ranges(ctx, include_google)
    collect_exclude_domains(ctx, exclude_domains)
    collect_include_domains(ctx, include_domains)
    return ctx.source_failed, ctx.sources, ctx.errors, ctx.base_text, ctx.include_text, ctx.exclude_text
