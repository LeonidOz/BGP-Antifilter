import ipaddress
import re
import sys


IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\d.])")


def read_networks(path, *, extract=False):
    networks = []
    invalid = 0

    with open(path, encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            values = IPV4_RE.findall(line) if extract else [line.strip()]

            for value in values:
                if not value:
                    continue

                if "/" not in value:
                    value = f"{value}/32"

                try:
                    networks.append(ipaddress.ip_network(value, strict=False))
                except ValueError:
                    invalid += 1
                    print(f"Skipping invalid network in {path}:{line_number}: {value}", file=sys.stderr)

    return networks, invalid


def build_routes_with_stats(base, exclude, extra):
    combined = base + extra
    kept = []
    exclude_rules_applied = 0

    for network in combined:
        remaining = [network]

        for excluded in exclude:
            next_remaining = []

            for candidate in remaining:
                if excluded.version != candidate.version or not candidate.overlaps(excluded):
                    next_remaining.append(candidate)
                    continue

                exclude_rules_applied += 1

                if candidate.subnet_of(excluded):
                    continue

                if excluded.subnet_of(candidate):
                    next_remaining.extend(candidate.address_exclude(excluded))
                    continue

                next_remaining.append(candidate)

            remaining = next_remaining

        kept.extend(remaining)

    collapsed = collapse_routes(kept)
    stats = {
        "candidate": len(combined),
        "after_exclusions": len(kept),
        "collapsed_removed": len(kept) - len(collapsed),
    }
    return collapsed, exclude_rules_applied, stats


def build_routes(base, exclude, extra):
    networks, exclude_rules_applied, _ = build_routes_with_stats(base, exclude, extra)
    return networks, exclude_rules_applied


def collapse_routes(networks):
    collapsed = []

    for version in (4, 6):
        same_version = [network for network in networks if network.version == version]
        collapsed.extend(ipaddress.collapse_addresses(same_version))

    return sorted(collapsed, key=lambda net: (net.version, int(net.network_address), net.prefixlen))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    if len(argv) != 4:
        print("Usage: generate-routes.py BASE_FILE EXCLUDE_FILE INCLUDE_FILE OUT_FILE", file=sys.stderr)
        return 2

    base_file, exclude_file, include_file, out_file = argv

    base, base_invalid = read_networks(base_file, extract=True)
    exclude, exclude_invalid = read_networks(exclude_file)
    extra, extra_invalid = read_networks(include_file)

    unique, exclude_rules_applied = build_routes(base, exclude, extra)

    with open(out_file, "w", encoding="utf-8") as file:
        for network in unique:
            file.write(f"    route {network} blackhole;\n")

    print(f"Base routes: {len(base)}")
    print(f"Added domain routes: {len(extra)}")
    print(f"Exclude rules applied: {exclude_rules_applied}")
    print(f"Invalid entries skipped: {base_invalid + exclude_invalid + extra_invalid}")
    print(f"Final routes: {len(unique)}")

    return 0
