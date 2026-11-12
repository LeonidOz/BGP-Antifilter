import argparse
import json
import socket
import sys


def local_ipv4_addresses():
    addresses = set()
    for host in {socket.gethostname(), socket.getfqdn(), "localhost"}:
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        for info in infos:
            address = info[4][0]
            if address:
                addresses.add(address)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(addresses)


def bird_ip_diagnostic(configured_ip, addresses=None):
    configured = str(configured_ip or "").strip()
    local_ipv4 = sorted({str(item).strip() for item in (addresses or local_ipv4_addresses()) if str(item).strip()})
    assigned = bool(configured) and configured in local_ipv4
    payload = {
        "configured_bird_ip": configured,
        "local_ipv4": local_ipv4,
        "bird_ip_assigned": assigned,
        "supported_for_bgp": assigned,
        "mode": "linux-host-bgp" if assigned else "dev-only",
        "message": "",
    }

    if assigned:
        return payload

    visible = ", ".join(local_ipv4) if local_ipv4 else "none"
    payload["message"] = (
        f"configured BIRD_IP {configured or '<empty>'} is not assigned inside container; visible IPv4 addresses: {visible}. "
        "On Linux host deployment set BIRD_IP to an address owned by the host/container network namespace. "
        "On Docker Desktop for Windows/macOS real BGP is typically unsupported; use this container only for route generation and the admin UI."
    )
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bird-ip", default="", help="Configured BIRD_IP value to validate")
    parser.add_argument("--require-assigned", action="store_true", help="Exit with code 1 when BIRD_IP is not assigned inside the container")
    args = parser.parse_args(argv)

    payload = bird_ip_diagnostic(args.bird_ip)
    print(json.dumps(payload, ensure_ascii=False))
    if args.require_assigned and not payload["bird_ip_assigned"]:
        print(payload["message"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
