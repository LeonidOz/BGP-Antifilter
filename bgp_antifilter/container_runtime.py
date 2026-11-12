"""Container configuration and health commands formerly embedded in shell."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import string
import sys

from .runtime_state import state_path
from .state_store import read_state, write_state
from .network_diagnostics import bird_ip_diagnostic


def fail(message):
    print(f"Invalid environment: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_env():
    for name in ("MY_AS", "MT_AS"):
        try:
            number = int(os.environ[name])
        except ValueError:
            fail(f"{name} must be an integer AS number")
        if not 1 <= number <= 4294967295:
            fail(f"{name} must be between 1 and 4294967295")

    for name in ("MT_IP", "BIRD_IP", "ROUTER_ID"):
        try:
            ipaddress.IPv4Address(os.environ[name])
        except ValueError:
            fail(f"{name} must be a valid IPv4 address")

    for name in ("UPDATE_INTERVAL", "CACHE_MAX_AGE"):
        try:
            seconds = int(os.environ[name])
        except ValueError:
            fail(f"{name} must be an integer number of seconds")
        if seconds <= 0:
            fail(f"{name} must be greater than zero")

    parts = os.environ["BGP_COMMUNITY"].split(",")
    if len(parts) != 2:
        fail("BGP_COMMUNITY must use the BIRD tuple format AS,VALUE")
    for part in parts:
        try:
            number = int(part)
        except ValueError:
            fail("BGP_COMMUNITY parts must be integers")
        if not 0 <= number <= 65535:
            fail("BGP_COMMUNITY parts must be between 0 and 65535")

    enabled = os.environ["ADMIN_ENABLED"]
    if enabled not in {"0", "1"}:
        fail("ADMIN_ENABLED must be 0 or 1")
    try:
        port = int(os.environ["ADMIN_PORT"])
    except ValueError:
        fail("ADMIN_PORT must be an integer")
    if not 1 <= port <= 65535:
        fail("ADMIN_PORT must be between 1 and 65535")
    if enabled == "1" and not os.environ["ADMIN_PASSWORD"]:
        fail("ADMIN_PASSWORD must be set when ADMIN_ENABLED=1")


def render_bird_config(template_file, config_file):
    template = string.Template(Path(template_file).read_text(encoding="utf-8"))
    Path(config_file).write_text(template.safe_substitute(os.environ), encoding="utf-8")


def print_snapshot_values(payload):
    data = json.loads(payload)
    print("1" if data.get("startup_snapshot_used") else "0")
    print(int(data.get("startup_snapshot_size_bytes") or 0))
    print("" if data.get("startup_snapshot_mtime_unix") is None else int(data["startup_snapshot_mtime_unix"]))
    print("" if data.get("startup_snapshot_age_seconds") is None else int(data["startup_snapshot_age_seconds"]))


def print_network_warning():
    payload = read_state(state_path("network_status_file"))
    message = str(payload.get("message") or "").strip()
    if message and not payload.get("bird_ip_assigned", False):
        print(message)


def write_network_status(bird_ip):
    write_state(state_path("network_status_file"), bird_ip_diagnostic(bird_ip))


def check_health(kind, path):
    # Unlike optional runtime reads, health checks must fail on malformed JSON.
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    message = None
    if kind == "status" and data.get("routes", {}).get("final", 0) <= 0:
        message = "status reports zero routes"
    elif kind == "runtime" and data.get("degraded"):
        message = data.get("degraded_reason") or "runtime is degraded"
    elif kind == "network" and not data.get("bird_ip_assigned", True):
        message = data.get("message") or "configured BIRD_IP is not assigned inside container"
    if message:
        print(message, file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-env")
    render = commands.add_parser("render-bird")
    render.add_argument("template_file")
    render.add_argument("config_file")
    snapshot = commands.add_parser("snapshot-values")
    snapshot.add_argument("payload")
    commands.add_parser("network-warning")
    network = commands.add_parser("write-network-status")
    network.add_argument("bird_ip")
    health = commands.add_parser("check-health")
    health.add_argument("kind", choices=("status", "runtime", "network"))
    health.add_argument("path")
    args = parser.parse_args(argv)
    if args.command == "validate-env":
        validate_env()
    elif args.command == "render-bird":
        render_bird_config(args.template_file, args.config_file)
    elif args.command == "snapshot-values":
        print_snapshot_values(args.payload)
    elif args.command == "network-warning":
        print_network_warning()
    elif args.command == "write-network-status":
        write_network_status(args.bird_ip)
    elif args.command == "check-health":
        return check_health(args.kind, args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
