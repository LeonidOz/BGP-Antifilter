import argparse
import json
import time
from pathlib import Path


def route_snapshot_available(path):
    path = Path(path)
    return path.exists() and path.stat().st_size > 0


def snapshot_metadata(path, now=None):
    path = Path(path)
    now = int(time.time()) if now is None else int(now)
    if not route_snapshot_available(path):
        return {
            "startup_snapshot_used": False,
            "startup_snapshot_size_bytes": 0,
            "startup_snapshot_mtime_unix": None,
            "startup_snapshot_age_seconds": None,
        }

    stat = path.stat()
    mtime = int(stat.st_mtime)
    return {
        "startup_snapshot_used": True,
        "startup_snapshot_size_bytes": stat.st_size,
        "startup_snapshot_mtime_unix": mtime,
        "startup_snapshot_age_seconds": max(0, now - mtime),
    }


def startup_strategy(path, now=None):
    metadata = snapshot_metadata(path, now=now)
    if metadata["startup_snapshot_used"]:
        return {
            "mode": "background-refresh",
            "generation_kind": "startup",
            "generation_message": "Starting with previous routes while refreshing in background",
            "generation_stage": "bootstrap",
            "generation_stage_message": "Using previous route snapshot until refresh completes",
            **metadata,
        }

    return {
        "mode": "blocking-bootstrap",
        "generation_kind": "initial",
        "generation_message": "Preparing routes before BIRD startup",
        "generation_stage": "bootstrap",
        "generation_stage_message": "Preparing initial route generation",
        **metadata,
    }


def update_message(reason):
    if reason == "startup":
        return "Refreshing routes after startup using previous route snapshot"
    if reason == "scheduled":
        return "Running scheduled route update"
    return "Running manual route update"


def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    startup_mode = subparsers.add_parser("startup-mode")
    startup_mode.add_argument("routes_path")
    startup_mode.add_argument("--json", action="store_true")

    update_reason = subparsers.add_parser("update-message")
    update_reason.add_argument("reason")

    args = parser.parse_args(argv)

    if args.command == "startup-mode":
        strategy = startup_strategy(args.routes_path)
        if args.json:
            print(json.dumps(strategy, ensure_ascii=False))
        else:
            print(strategy["mode"])
        return 0

    if args.command == "update-message":
        print(update_message(args.reason))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
