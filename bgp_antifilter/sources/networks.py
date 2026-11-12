"""Network sources: URL lists, ASN prefixes and Google non-Cloud ranges."""

import ipaddress
import json

from ..logging import progress
from ..route_builder import subtract_networks
from .fetch import cache_path, fetch_text_source


def read_ipv4_prefixes_from_google_json(text):
    data = json.loads(text)
    networks = []

    for item in data.get("prefixes", []):
        prefix = item.get("ipv4Prefix")
        if prefix:
            networks.append(ipaddress.ip_network(prefix, strict=False))

    return networks


def collect_url_sources(ctx, url_sources):
    for index, source in enumerate(url_sources, 1):
        url = source["url"]
        source_name = source["name"] or url
        current_index = ctx.processed_items + 1
        ctx.update_progress(
            f"Fetching URL {current_index}/{ctx.total_items}",
            current_kind="url",
            current_name=source_name,
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching url", index=index, total=len(url_sources), name=source_name, url=url)
        text, record, ok = fetch_text_source(
            "url",
            source_name,
            url,
            cache_path(ctx.cache_dir, "url", url),
            ctx.now,
            ctx.cache_max_age,
            dns_nameservers=ctx.dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index, url=url: ctx.update_progress(
                f"Fetching URL {current_index}/{ctx.total_items}",
                current_kind="url",
                current_name=source_name,
                current_index=current_index,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.9, attempt / max(1, attempts)),
            ),
        )
        record["required"] = ctx.require_all_url_sources
        ctx.sources.append(record)
        if ctx.require_all_url_sources:
            ctx.source_failed = ctx.source_failed or not ok
        if ok:
            ctx.base_text.append(text)
        else:
            progress(
                "required URL source failed" if ctx.require_all_url_sources else "skipping unavailable URL source",
                url=url,
                status="failed",
            )
            ctx.errors.append(record)
        ctx.processed_items += 1
        ctx.update_progress(
            f"Processed URL {ctx.processed_items}/{ctx.total_items}",
            current_kind="url",
            current_name=source_name,
            current_index=ctx.processed_items,
        )


def collect_asn_sources(ctx, asn_sources):
    for index, asn in enumerate(asn_sources, 1):
        current_index = ctx.processed_items + 1
        ctx.update_progress(
            f"Fetching ASN {current_index}/{ctx.total_items}",
            current_kind="asn",
            current_name=asn,
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching ASN", index=index, total=len(asn_sources), asn=asn)
        asn_number = asn.upper().removeprefix("AS")
        if not asn_number.isdigit():
            record = {"kind": "asn", "name": asn, "status": "failed", "error": "invalid ASN"}
            ctx.sources.append(record)
            ctx.errors.append(record)
            ctx.source_failed = True
            ctx.processed_items += 1
            ctx.update_progress(
                f"Processed ASN {ctx.processed_items}/{ctx.total_items}",
                current_kind="asn",
                current_name=asn,
                current_index=ctx.processed_items,
            )
            continue

        url = f"https://api.routeviews.org/asn/{asn_number}"
        text, record, ok = fetch_text_source(
            "asn",
            f"AS{asn_number}",
            url,
            cache_path(ctx.cache_dir, "asn", asn_number),
            ctx.now,
            ctx.cache_max_age,
            dns_nameservers=ctx.dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index, asn=asn: ctx.update_progress(
                f"Fetching ASN {current_index}/{ctx.total_items}",
                current_kind="asn",
                current_name=asn,
                current_index=current_index,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.9, attempt / max(1, attempts)),
            ),
        )
        ctx.sources.append(record)
        ctx.source_failed = ctx.source_failed or not ok
        if ok:
            ctx.base_text.append(text)
        else:
            ctx.errors.append(record)
        ctx.processed_items += 1
        ctx.update_progress(
            f"Processed ASN {ctx.processed_items}/{ctx.total_items}",
            current_kind="asn",
            current_name=f"AS{asn_number}",
            current_index=ctx.processed_items,
        )


def collect_google_ranges(ctx, include_google):
    if include_google:
        current_index = ctx.processed_items + 1
        ctx.update_progress(
            f"Fetching Google ranges {current_index}-{current_index + 1}/{ctx.total_items}",
            current_kind="google",
            current_name="goog.json / cloud.json",
            current_index=current_index,
            current_step=0.15,
        )
        progress("fetching Google ranges")
        google_text, google_record, google_ok = fetch_text_source(
            "google", "goog.json", "https://www.gstatic.com/ipranges/goog.json",
            cache_path(ctx.cache_dir, "google", "goog.json", ".json"), ctx.now, ctx.cache_max_age,
            dns_nameservers=ctx.dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index: ctx.update_progress(
                f"Fetching Google ranges {current_index}-{current_index + 1}/{ctx.total_items}",
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
            cache_path(ctx.cache_dir, "google", "cloud.json", ".json"), ctx.now, ctx.cache_max_age,
            dns_nameservers=ctx.dns_nameservers,
            progress_callback=lambda attempt, attempts, current_index=current_index: ctx.update_progress(
                f"Fetching Google ranges {current_index}-{current_index + 1}/{ctx.total_items}",
                current_kind="google",
                current_name="cloud.json",
                current_index=current_index + 1,
                current_attempt=attempt,
                current_attempt_total=attempts,
                current_step=min(0.9, 0.45 + (attempt / max(1, attempts) * 0.45)),
            ),
        )
        ctx.sources.extend([google_record, cloud_record])
        ctx.source_failed = ctx.source_failed or not google_ok or not cloud_ok
        ctx.processed_items += 2
        ctx.update_progress(
            f"Processed Google ranges {ctx.processed_items}/{ctx.total_items}",
            current_kind="google",
            current_name="goog.json / cloud.json",
            current_index=ctx.processed_items,
        )

        if google_ok and cloud_ok:
            try:
                progress("processing Google ranges")
                google = read_ipv4_prefixes_from_google_json(google_text)
                cloud = read_ipv4_prefixes_from_google_json(cloud_text)
                ctx.base_text.append("\n".join(str(network) for network in subtract_networks(google, cloud)) + "\n")
            except (json.JSONDecodeError, ValueError) as exc:
                record = {"kind": "google", "name": "processed-ranges", "status": "failed", "error": str(exc)}
                ctx.sources.append(record)
                ctx.errors.append(record)
                ctx.source_failed = True
        else:
            if not google_ok:
                ctx.errors.append(google_record)
            if not cloud_ok:
                ctx.errors.append(cloud_record)
    else:
        progress("skipping Google ranges", status="disabled")
        ctx.sources.append({"kind": "google", "name": "ranges", "status": "disabled"})
