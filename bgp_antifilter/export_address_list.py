"""Export a confirmed BIRD snapshot as a managed RouterOS IPv4 address list."""

import argparse
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import sys


DEFAULT_LIST_NAME = "bgp-antifilter"
MANAGED_PREFIX = "bgp-antifilter:managed:"
LIST_NAME_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
ROUTE_RE = re.compile(r"route\s+(\S+)\s+blackhole\s*;")


def validate_list_name(name):
    if not LIST_NAME_RE.fullmatch(name):
        raise ValueError("list name must contain 1-64 ASCII letters, digits, dots, underscores or hyphens")
    return name


def parse_routes(text):
    networks = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ROUTE_RE.fullmatch(line)
        if not match:
            raise ValueError(f"invalid BIRD route at line {number}")
        network = ipaddress.ip_network(match[1], strict=True)
        if network.version != 4:
            raise ValueError("Address List export supports IPv4 routes only")
        networks.add(network)
    if not networks:
        raise ValueError("refusing to export an empty route snapshot")
    return sorted(networks, key=lambda net: (int(net.network_address), net.prefixlen))


def read_snapshot(path, lock_dir=None):
    lock_dir = Path(lock_dir or os.environ.get("UPDATE_LOCK_DIR", "/etc/bird/generated/update.lock"))
    if lock_dir.exists():
        raise ValueError("route update is in progress; retry after it finishes")
    path = Path(path)
    before = path.stat()
    text = path.read_text(encoding="utf-8")
    after = path.stat()
    if lock_dir.exists() or (before.st_ino, before.st_mtime_ns, before.st_size) != (
        after.st_ino, after.st_mtime_ns, after.st_size
    ):
        raise ValueError("route snapshot changed during export; retry")
    return text


def export_rsc(text, list_name=DEFAULT_LIST_NAME):
    validate_list_name(list_name)
    networks = parse_routes(text)
    digest = hashlib.sha256("\n".join(map(str, networks)).encode("ascii")).hexdigest()[:16]
    marker = MANAGED_PREFIX + digest
    target = f'list="{list_name}"'
    managed = f'comment~"^{MANAGED_PREFIX}"'
    lines = [
        "# BGP Antifilter: managed IPv4 Address List",
        f"# List: {list_name}; prefixes: {len(networks)}; snapshot: {digest}",
        f"# Reserved comment prefix: {MANAGED_PREFIX}",
        "# Import the complete file. Do not run concurrent imports for the same list.",
        "# Adds/refreshes entries first, then removes stale managed entries only.",
        "# Unmanaged entries are preserved. Import is not transactional.",
    ]
    menu = "/ip firewall address-list"
    for network in networks:
        address = str(network.network_address) if network.prefixlen == 32 else str(network)
        selector = f"{target} and address={address}"
        lines.append(
            f":if ([:len [{menu} find where {selector}]] = 0) do={{ "
            f'{menu} add {target} address={address} comment="{marker}" '
            f"}} else={{ :local owned [{menu} find where {selector} and {managed}]; "
            f":if ([:len $owned] > 0) do={{ {menu} set $owned comment=\"{marker}\" }} }}"
        )
    lines.append(f'{menu} remove [find where {target} and {managed} and comment!="{marker}"]')
    return "\r\n".join(lines) + "\r\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=Path, default=Path(os.environ.get(
        "LAST_GOOD_ROUTES_FILE", "/etc/bird/generated/routes.last-good.conf")))
    parser.add_argument("--list-name", default=DEFAULT_LIST_NAME)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = export_rsc(read_snapshot(args.routes), args.list_name)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.output:
        args.output.write_bytes(result.encode("utf-8"))
    else:
        sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
