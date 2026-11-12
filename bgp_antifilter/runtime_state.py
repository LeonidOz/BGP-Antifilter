"""Runtime schema and transitions used by shell, generator and admin."""

import argparse
import os
import time

from .runtime_paths import GENERATED_PATH_SPECS, env_path
from .state_store import mutate_state, patch_state, read_state


PRESERVED_PREFIXES = ("generation_", "startup_snapshot_", "last_update_", "degraded")
IDLE_GENERATION = {
    "generation_active": False,
    "generation_kind": "",
    "generation_message": "",
    "generation_started_at_unix": None,
    "generation_progress_percent": 0,
    "generation_stage": "",
    "generation_stage_message": "",
    "generation_items_done": None,
    "generation_items_total": None,
}


def state_path(key):
    return env_path(*GENERATED_PATH_SPECS[key])


def optional_int(value):
    return int(value) if value else None


def generation_fields(env, *, reload=False):
    def value(name, default=""):
        key = name.lower() if reload else name
        return env.get(key, default)

    return {
        "generation_active": value("GENERATION_ACTIVE", "0") == "1",
        "generation_kind": value("GENERATION_KIND"),
        "generation_message": value("GENERATION_MESSAGE"),
        "generation_started_at_unix": optional_int(value("GENERATION_STARTED_AT")),
        "generation_progress_percent": int(value("GENERATION_PROGRESS_PERCENT", "0") or 0),
        "generation_stage": value("GENERATION_STAGE"),
        "generation_stage_message": value("GENERATION_STAGE_MESSAGE"),
        "generation_items_done": optional_int(value("GENERATION_ITEMS_DONE")),
        "generation_items_total": optional_int(value("GENERATION_ITEMS_TOTAL")),
    }


def snapshot_and_result_fields(env):
    return {
        "startup_snapshot_used": env.get("STARTUP_SNAPSHOT_USED", "0") == "1",
        "startup_snapshot_size_bytes": int(env.get("STARTUP_SNAPSHOT_SIZE_BYTES", "0") or 0),
        "startup_snapshot_mtime_unix": optional_int(env.get("STARTUP_SNAPSHOT_MTIME_UNIX")),
        "startup_snapshot_age_seconds": optional_int(env.get("STARTUP_SNAPSHOT_AGE_SECONDS")),
        "last_update_reason": env.get("LAST_UPDATE_REASON", ""),
        "last_update_message": env.get("LAST_UPDATE_MESSAGE", ""),
        "last_update_success": None if env.get("LAST_UPDATE_SUCCESS", "") == "" else env["LAST_UPDATE_SUCCESS"] == "1",
        "last_update_finished_at_unix": optional_int(env.get("LAST_UPDATE_FINISHED_AT_UNIX")),
        "degraded": env.get("DEGRADED", "0") == "1",
        "degraded_reason": env.get("DEGRADED_REASON", "") if env.get("DEGRADED", "0") == "1" else "",
    }


def write_schedule(next_update, *, env=None, now=None):
    env = os.environ if env is None else env
    now = int(time.time()) if now is None else int(now)

    def update(previous):
        data = {
            "updated_at_unix": now,
            "update_interval_seconds": int(env["UPDATE_INTERVAL"]),
            "next_scheduled_update_unix": int(next_update),
            "admin_enabled": env["ADMIN_ENABLED"] == "1",
            "admin_port": int(env["ADMIN_PORT"]),
            **generation_fields(env),
            **snapshot_and_result_fields(env),
            "network": read_state(state_path("network_status_file")),
        }
        if env.get("RUNTIME_PRESERVE_STATE") == "1":
            data.update({key: value for key, value in previous.items() if key.startswith(PRESERVED_PREFIXES)})
        return data

    return mutate_state(state_path("runtime_file"), update)


def write_reload(*, env=None, now=None):
    env = os.environ if env is None else env
    now = int(time.time()) if now is None else int(now)

    def update(data):
        result = snapshot_and_result_fields(env)
        interval = int(env.get("UPDATE_INTERVAL") or data.get("update_interval_seconds") or 1800)
        generation = generation_fields(env, reload=True)
        next_update = int(data.get("next_scheduled_update_unix") or 0)
        if not generation["generation_active"] and result["last_update_finished_at_unix"] is not None:
            next_update = result["last_update_finished_at_unix"] + interval
        return {
            **data,
            "updated_at_unix": now,
            "update_interval_seconds": interval,
            "next_scheduled_update_unix": next_update,
            "admin_enabled": env.get("ADMIN_ENABLED", "0") == "1",
            "admin_port": int(env.get("ADMIN_PORT") or data.get("admin_port") or 8080),
            **generation,
            **result,
            "network": read_state(state_path("network_status_file")),
        }

    return mutate_state(state_path("runtime_file"), update)


def write_degraded_status(*, env=None, now=None):
    env = os.environ if env is None else env
    now = int(time.time()) if now is None else int(now)

    def update(data):
        reason = env.get("DEGRADED_REASON", "")
        data.update({
            "success": False,
            "degraded": True,
            "degraded_reason": reason,
            "run_reason": env.get("LAST_UPDATE_REASON", data.get("run_reason", "manual")),
            "run_message": env.get("LAST_UPDATE_MESSAGE", data.get("run_message", "")),
            "updated_at_unix": now,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "network": read_state(state_path("network_status_file")),
        })
        data.setdefault("routes", {})
        data.setdefault("sources", [])
        data.setdefault("errors", [])
        if reason and not any(isinstance(item, dict) and item.get("error") == reason for item in data["errors"]):
            data["errors"].append({"kind": "runtime", "name": "apply", "status": "failed", "error": reason})
        return data

    return mutate_state(state_path("status_file"), update)


def write_progress(path, **fields):
    # Progress reporting must never break route generation or CLI checks.
    try:
        return patch_state(path, **fields)
    except OSError:
        return None


PROGRESS_STEPS = {
    "collecting-sources": 15,
    "building-routes": 70,
    "writing-routes": 85,
    "writing-status": 95,
    "completed": 100,
}


def write_runtime_progress(
    stage,
    message,
    *,
    active=True,
    percent=None,
    items_done=None,
    items_total=None,
    current_kind=None,
    current_name=None,
    current_index=None,
    current_attempt=None,
    current_attempt_total=None,
):
    runtime_file = env_path(*GENERATED_PATH_SPECS["runtime_file"])
    value = PROGRESS_STEPS.get(stage, 0 if active else 100) if percent is None else percent
    write_progress(runtime_file, **{
        "generation_active": active,
        "generation_stage": stage,
        "generation_stage_message": message,
        "generation_progress_percent": max(0, min(100, int(value))),
        "generation_items_done": items_done,
        "generation_items_total": items_total,
        "generation_current_kind": current_kind,
        "generation_current_name": current_name,
        "generation_current_index": current_index,
        "generation_current_attempt": current_attempt,
        "generation_current_attempt_total": current_attempt_total,
    })


def reconcile_generation(path, runtime, active):
    state = dict(runtime or {})
    if not state.get("generation_active") or active():
        return state

    def reconcile(current):
        # Recheck after acquiring the lock; another process may have started.
        if active():
            return None
        if not current:
            current = dict(state)
        if not current.get("generation_active"):
            return None
        return {**current, **IDLE_GENERATION, "updated_at_unix": int(time.time())}

    try:
        return mutate_state(path, reconcile)
    except OSError:
        return {**state, **IDLE_GENERATION, "updated_at_unix": int(time.time())}


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    schedule = commands.add_parser("write-schedule")
    schedule.add_argument("next_update", type=int)
    commands.add_parser("write-reload")
    commands.add_parser("write-degraded-status")
    commands.add_parser("next-update")
    args = parser.parse_args(argv)
    if args.command == "write-schedule":
        write_schedule(args.next_update)
    elif args.command == "write-reload":
        write_reload()
    elif args.command == "write-degraded-status":
        write_degraded_status()
    elif args.command == "next-update":
        value = read_state(state_path("runtime_file")).get("next_scheduled_update_unix")
        print("" if value in (None, "") else int(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
