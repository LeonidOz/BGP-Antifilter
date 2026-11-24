"""Download and resolve concurrently, then aggregate in source order.

Providers update one collection context. Their records, cache namespaces and
required/optional failure policies remain specific to each source type.
"""

from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, SimpleQueue
import os
import re
import time

from .. import dns_resolver
from ..logging import progress
from ..runtime_paths import list_paths
from ..runtime_state import write_runtime_progress
from ..update_config import env_bool, env_float, env_int
from .countries import (
    DELEGATED_REGISTRIES, DELEGATED_STATS_BASE_URL, collect_country_sources,
    normalize_country_code,
)
from .domains import (
    collect_domain_list_sources, collect_exclude_domains, collect_include_domains,
    normalize_domain_name, parse_domain_list, parse_ipv4_literal,
)
from .fetch import cache_path, fetch_text_source
from .networks import collect_asn_sources, collect_google_ranges, collect_url_sources
from .parallel import bounded_results


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
    fetched: dict = field(default_factory=dict)
    dns_results: dict = field(default_factory=dict)

    def fetch_source(self, kind, name, url, cache_file, now, max_age,
                     progress_callback=None, dns_nameservers=None):
        text, cached_record, ok = self.fetched[str(cache_file)]
        # Each configured source owns its status even if the download was shared.
        record = dict(cached_record, kind=kind, name=name)
        return text, record, ok

    def preparation_progress(self, message, done, total, start, span, *,
                             current_kind=None, current_name=None,
                             current_attempt=None, current_attempt_total=None):
        write_runtime_progress(
            "collecting-sources", message,
            percent=start + round(span * done / max(1, total)),
            items_done=0, items_total=self.total_items,
            current_kind=current_kind, current_name=current_name,
            current_attempt=current_attempt, current_attempt_total=current_attempt_total,
        )

    def update_progress(
        self, message, *, current_kind=None, current_name=None,
        current_index=None, current_attempt=None, current_attempt_total=None,
        current_step=0.0,
    ):
        if self.total_items <= 0:
            percent = 65
        else:
            ratio = min(self.total_items, max(0.0, self.processed_items + current_step)) / self.total_items
            percent = 60 + round(ratio * 5)
        write_runtime_progress(
            "collecting-sources", message, percent=percent,
            items_done=self.processed_items, items_total=self.total_items,
            current_kind=current_kind, current_name=current_name,
            current_index=current_index, current_attempt=current_attempt,
            current_attempt_total=current_attempt_total,
        )


def prepare_downloads(ctx, url_sources, domain_list_sources, asn_sources,
                      country_sources, include_google, workers, limiter):
    jobs = {}

    def add(kind, name, url, value, suffix=".cache"):
        path = cache_path(ctx.cache_dir, kind, value, suffix)
        jobs.setdefault(str(path), (kind, name, url, path))

    for kind, entries in (("url", url_sources), ("domain-list-url", domain_list_sources)):
        for source in entries:
            add(kind, source["name"] or source["url"], source["url"], source["url"])
    for asn in asn_sources:
        number = asn.upper().removeprefix("AS")
        if number.isdigit():
            add("asn", f"AS{number}", f"https://api.routeviews.org/asn/{number}", number)
    for country in country_sources:
        try:
            code = normalize_country_code(country)
        except ValueError:
            continue
        url = f"https://stat.ripe.net/data/country-resource-list/data.json?resource={code.lower()}&v4_format=prefix"
        add("country", code, url, code)
    if include_google:
        for name in ("goog.json", "cloud.json"):
            add("google", name, f"https://www.gstatic.com/ipranges/{name}", name, ".json")

    events = SimpleQueue()
    total = len(jobs) + (len(DELEGATED_REGISTRIES) if country_sources else 0)

    def report_attempts():
        while True:
            try:
                kind, name, attempt, attempts = events.get_nowait()
            except Empty:
                break
            ctx.preparation_progress(
                "Downloading sources", len(ctx.fetched), total, 10, 20,
                current_kind=kind, current_name=name,
                current_attempt=attempt, current_attempt_total=attempts,
            )

    def download(job):
        kind, name, url, path = job
        with dns_resolver.use_rate_limiter(limiter):
            text, record, ok = fetch_text_source(
                kind, name, url, path, ctx.now, ctx.cache_max_age,
                dns_nameservers=ctx.dns_nameservers,
                progress_callback=lambda attempt, total: events.put((kind, name, attempt, total)),
            )
        return text, record, ok

    def run_jobs():
        for job, result in bounded_results(download, jobs.values(), workers, report_attempts):
            ctx.fetched[str(job[3])] = result
            ctx.preparation_progress(
                f"Downloaded source {len(ctx.fetched)}", len(ctx.fetched), total, 10, 20,
                current_kind=job[0], current_name=job[1],
            )

    run_jobs()
    # Registry files are shared by all countries and fetched once, concurrently.
    if any(job[0] == "country" and not ctx.fetched[key][2] for key, job in jobs.items()):
        jobs.clear()
        for registry in DELEGATED_REGISTRIES:
            url = f"{DELEGATED_STATS_BASE_URL}/{registry}/delegated-{registry}-latest"
            add("country-registry", registry, url, registry)
        run_jobs()
    ctx.preparation_progress("Source downloads complete", 1, 1, 10, 20)


def prepare_domains(ctx, domain_list_sources, exclude_domains, include_domains, workers, limiter):
    domains = {}
    for source in domain_list_sources:
        path = cache_path(ctx.cache_dir, "domain-list-url", source["url"])
        text, _record, ok = ctx.fetched[str(path)]
        if ok:
            parsed, _invalid = parse_domain_list(text)
            domains.update((domain, None) for domain in parsed)
    for value in [*exclude_domains, *include_domains]:
        domain = normalize_domain_name(value)
        if domain is not None:
            domains[domain] = None

    def resolve(domain):
        literal = parse_ipv4_literal(domain)
        if literal is not None:
            return [literal], None
        try:
            with dns_resolver.use_rate_limiter(limiter):
                addresses = dns_resolver.resolve_ipv4_addresses(
                    domain, nameservers=ctx.dns_nameservers, timeout=ctx.dns_timeout,
                )
            if not addresses:
                raise RuntimeError("no IPv4 addresses returned")
            return addresses, None
        except (OSError, RuntimeError, ValueError) as exc:
            return None, str(exc)

    progress("resolving unique domains", domains=len(domains), workers=workers)
    last_report = 0.0
    for domain, result in bounded_results(resolve, domains, workers):
        ctx.dns_results[domain] = result
        now = time.monotonic()
        if now - last_report >= 0.1 or len(ctx.dns_results) == len(domains):
            ctx.preparation_progress(
                f"Resolved unique domains {len(ctx.dns_results)}/{len(domains)}",
                len(ctx.dns_results), len(domains), 30, 30,
                current_kind="domain", current_name=domain,
            )
            last_report = now
    ctx.preparation_progress("Domain resolution complete", 1, 1, 30, 30)


def collect_sources(cache_dir, cache_max_age, include_google):
    now = int(time.time())
    list_files = list_paths()
    require_all_url_sources = env_bool("REQUIRE_ALL_URL_SOURCES", default=False)
    dns_nameservers = dns_resolver.parse_nameservers(os.environ.get("DNS_RESOLVERS", ""))
    dns_timeout = env_float("DNS_RESOLVE_TIMEOUT", dns_resolver.DEFAULT_TIMEOUT)
    dns_workers = env_int("DNS_WORKERS", 16, minimum=16, maximum=128)
    dns_qps = env_int("DNS_QPS", 50, maximum=1000)
    fetch_workers = env_int("FETCH_WORKERS", 8, maximum=32)
    limiter = dns_resolver.QueryRateLimiter(dns_qps)
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
    ctx.preparation_progress("Collecting route sources", 0, 1, 10, 0)
    progress(
        "starting update", urls=len(url_sources), domain_list_urls=len(domain_list_sources),
        asns=len(asn_sources), countries=len(country_sources),
        exclude_domains=len(exclude_domains), include_domains=len(include_domains),
        google="enabled" if include_google else "disabled",
    )
    prepare_downloads(ctx, url_sources, domain_list_sources, asn_sources,
                      country_sources, include_google, fetch_workers, limiter)
    prepare_domains(ctx, domain_list_sources, exclude_domains, include_domains,
                    dns_workers, limiter)
    collect_url_sources(ctx, url_sources)
    collect_domain_list_sources(ctx, domain_list_sources)
    collect_asn_sources(ctx, asn_sources)
    collect_country_sources(ctx, country_sources)
    collect_google_ranges(ctx, include_google)
    collect_exclude_domains(ctx, exclude_domains)
    collect_include_domains(ctx, include_domains)
    return ctx.source_failed, ctx.sources, ctx.errors, ctx.base_text, ctx.include_text, ctx.exclude_text
