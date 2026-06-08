#!/usr/bin/env python3
import argparse
import ipaddress
import json
import re
from pathlib import Path
import sys


IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\d.])")


def parse_networks_from_text(text, *, extract):
    networks = []
    values = IPV4_RE.findall(text) if extract else text.splitlines()

    for value in values:
        value = value.strip()
        if not value:
            continue

        if "/" not in value:
            value = f"{value}/32"

        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue

    return networks


def read_networks(path, *, extract):
    if not path.exists():
        return []

    return parse_networks_from_text(path.read_text(encoding="utf-8", errors="replace"), extract=extract)


def matching_networks(address, networks):
    return [network for network in networks if address in network]


def describe_source(source):
    kind = source.get("kind", "source")
    name = source.get("name", "")
    url = source.get("url")
    status = source.get("status", "unknown")

    if url and url != name:
        return f"{kind} {name} ({status}) - {url}"

    return f"{kind} {name} ({status})"


def source_matches(address, source):
    kind = source.get("kind")
    cache_file = source.get("cache_file")

    if not cache_file or source.get("status") in {"failed", "skipped", "disabled"}:
        return []

    path = Path(cache_file)
    extract = kind in {"url", "asn", "google"}
    networks = read_networks(path, extract=extract)
    return matching_networks(address, networks)


def google_default_matches(address, sources):
    google = next((source for source in sources if source.get("kind") == "google" and source.get("name") == "goog.json"), None)
    cloud = next((source for source in sources if source.get("kind") == "google" and source.get("name") == "cloud.json"), None)

    if not google or not cloud:
        return []

    google_matches = source_matches(address, google)
    cloud_matches = source_matches(address, cloud)

    if google_matches and not cloud_matches:
        return google_matches

    return []


def find_sources(address, status):
    result = []
    sources = status.get("sources", [])

    for source in sources:
        if source.get("kind") == "google":
            continue

        matches = source_matches(address, source)
        if matches:
            result.append((source, matches))

    google_matches = google_default_matches(address, sources)
    if google_matches:
        result.append((
            {"kind": "google", "name": "default ranges minus cloud", "status": "derived"},
            google_matches,
        ))

    return result


def load_status(path):
    if not path.exists():
        return {"sources": []}

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def main():
    parser = argparse.ArgumentParser(description="Check whether an IPv4 address is present in generated BIRD routes.")
    parser.add_argument("ip", help="IPv4 address to check")
    parser.add_argument("--routes", default="/etc/bird/generated/routes.conf")
    parser.add_argument("--status", default="/etc/bird/generated/status.json")
    args = parser.parse_args()

    try:
        address = ipaddress.ip_address(args.ip)
    except ValueError as exc:
        print(f"Invalid IP address: {exc}", file=sys.stderr)
        return 2

    if address.version != 4:
        print("Only IPv4 addresses are supported by this project", file=sys.stderr)
        return 2

    routes = read_networks(Path(args.routes), extract=True)
    route_matches = matching_networks(address, routes)
    status = load_status(Path(args.status))
    source_results = find_sources(address, status)

    print(f"IP: {address}")

    if route_matches:
        print("Generated routes: yes")
        for network in route_matches:
            print(f"  - {network}")
    else:
        print("Generated routes: no")

    if source_results:
        print("Sources:")
        for source, matches in source_results:
            print(f"  - {describe_source(source)}")
            for network in matches[:5]:
                print(f"    match: {network}")
            if len(matches) > 5:
                print(f"    ... and {len(matches) - 5} more")
    else:
        print("Sources: no cache match found")

    return 0 if route_matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
