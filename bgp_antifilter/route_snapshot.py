"""Self-contained route snapshots and explanations independent of mutable caches."""

import hashlib
import ipaddress
import json
from pathlib import Path

from .check_ip import parse_networks_from_text
from .generate_routes import collapse_routes
from .state_store import read_state


def snapshot_path(routes):
    return Path(routes).with_suffix(".json")


def route_text(prefixes):
    return "".join(f"    route {prefix} blackhole;\n" for prefix in prefixes)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze_sources(sources):
    records = []
    for source in sources:
        if source.get("status") not in {"fresh", "cache"}:
            continue
        text = source.get("_text", "")
        if source.get("kind") == "google":
            try:
                prefixes = [item["ipv4Prefix"] for item in json.loads(text).get("prefixes", []) if "ipv4Prefix" in item]
            except (ValueError, TypeError):
                prefixes = []
        else:
            prefixes = [str(net) for net in collapse_routes(parse_networks_from_text(text, extract=True))]
        records.append({
            "kind": source["kind"], "name": source.get("name", ""),
            "url": source.get("url"), "status": source["status"],
            "role": "exclude" if source["kind"] == "exclude-domain" else "include",
            "prefixes": prefixes, "domains": source.get("_domain_addresses", {}),
        })
    return records


def make_snapshot(networks, status, sources):
    prefixes = [str(network) for network in networks]
    return {"schema": 1, "prefixes": prefixes, "routes_sha256": digest(route_text(prefixes)),
            "status": status, "provenance": freeze_sources(sources)}


def read_confirmed(routes):
    """Refuse mismatched metadata, including partially published/crashed updates."""
    routes = Path(routes)
    snapshot = read_state(snapshot_path(routes))
    try:
        text = routes.read_text(encoding="utf-8")
    except OSError:
        return {}
    if snapshot.get("routes_sha256") != digest(text):
        return {}
    return snapshot


def explain(address, snapshot):
    address = ipaddress.IPv4Address(address)
    matches = lambda prefixes: [value for value in prefixes if address in ipaddress.IPv4Network(value)]
    routes = matches(snapshot.get("prefixes", []))
    sources, exclusions = [], []
    provenance = snapshot.get("provenance", [])
    cloud = next((source for source in provenance if source["kind"] == "google" and source["name"] == "cloud.json"), {})
    for source in provenance:
        if source["kind"] == "google" and (source["name"] != "goog.json" or matches(cloud.get("prefixes", []))):
            continue
        matched = matches(source.get("prefixes", []))
        if not matched:
            continue
        record = {key: source.get(key) for key in ("kind", "name", "url", "status", "role")}
        record.update(matches=matched, domains=[domain for domain, prefixes in source.get("domains", {}).items() if matches(prefixes)])
        (exclusions if source["role"] == "exclude" else sources).append(record)
    return {"ip": str(address), "matched": bool(routes), "routes": routes, "sources": sources,
            "exclusions": exclusions, "decision": "included" if routes else "excluded" if exclusions else "absent",
            "snapshot_applied_at_unix": snapshot.get("applied_at_unix"), "confirmed": True}
