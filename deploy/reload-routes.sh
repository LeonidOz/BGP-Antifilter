#!/bin/sh
set -eu

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-/etc/bird/include-asns.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-/etc/bird/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-/etc/bird/exclude-domains.txt}"
INCLUDE_GOOGLE_RANGES="${INCLUDE_GOOGLE_RANGES:-1}"
CACHE_MAX_AGE="${CACHE_MAX_AGE:-604800}"
ROUTES="${ROUTES_FILE:-/etc/bird/generated/routes.conf}"
LAST_GOOD_ROUTES="${LAST_GOOD_ROUTES_FILE:-/etc/bird/generated/routes.last-good.conf}"
CACHE_DIR="${CACHE_DIR:-/etc/bird/generated/cache}"
STATUS_FILE="${STATUS_FILE:-/etc/bird/generated/status.json}"
METRICS_FILE="${METRICS_FILE:-/etc/bird/generated/metrics.prom}"
RUNTIME_FILE="${RUNTIME_FILE:-/etc/bird/generated/runtime.json}"
LOCK_DIR="${UPDATE_LOCK_DIR:-/etc/bird/generated/update.lock}"
SETTINGS_ENV_FILE="${SETTINGS_ENV_FILE:-/etc/bird/generated/settings.env}"

if [ -f "$SETTINGS_ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$SETTINGS_ENV_FILE"
  set +a
fi

mkdir -p /etc/bird/generated "$CACHE_DIR"
touch "$ROUTES"
touch "$LAST_GOOD_ROUTES"

tmp_old="$(mktemp)"
tmp_new="$(mktemp)"
if [ -s "$LAST_GOOD_ROUTES" ]; then
  cp "$LAST_GOOD_ROUTES" "$tmp_old"
else
  cp "$ROUTES" "$tmp_old"
fi
lock_acquired=0
runtime_state_written=0

write_runtime_state() {
  generation_active="${1:-0}"
  generation_kind="${2:-}"
  generation_message="${3:-}"
  generation_started_at="${4:-}"
  generation_progress_percent="${5:-0}"
  generation_stage="${6:-}"
  generation_stage_message="${7:-}"
  generation_items_done="${8:-}"
  generation_items_total="${9:-}"
  export RUNTIME_FILE UPDATE_INTERVAL ADMIN_ENABLED ADMIN_PORT
  export generation_active generation_kind generation_message generation_started_at
  export generation_progress_percent generation_stage generation_stage_message
  export generation_items_done generation_items_total
  export STARTUP_SNAPSHOT_USED="${STARTUP_SNAPSHOT_USED:-0}"
  export STARTUP_SNAPSHOT_SIZE_BYTES="${STARTUP_SNAPSHOT_SIZE_BYTES:-0}"
  export STARTUP_SNAPSHOT_MTIME_UNIX="${STARTUP_SNAPSHOT_MTIME_UNIX:-}"
  export STARTUP_SNAPSHOT_AGE_SECONDS="${STARTUP_SNAPSHOT_AGE_SECONDS:-}"
  export LAST_UPDATE_REASON="${LAST_UPDATE_REASON:-}"
  export LAST_UPDATE_MESSAGE="${LAST_UPDATE_MESSAGE:-}"
  export LAST_UPDATE_SUCCESS="${LAST_UPDATE_SUCCESS:-}"
  export LAST_UPDATE_FINISHED_AT_UNIX="${LAST_UPDATE_FINISHED_AT_UNIX:-}"
  export DEGRADED="${DEGRADED:-0}"
  export DEGRADED_REASON="${DEGRADED_REASON:-}"
  python3 - <<'PY'
import json
import os
import time
from pathlib import Path

path = Path(os.environ["RUNTIME_FILE"])
path.parent.mkdir(parents=True, exist_ok=True)
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    data = {}

now = int(time.time())
data.update({
    "updated_at_unix": now,
    "update_interval_seconds": int(os.environ.get("UPDATE_INTERVAL") or data.get("update_interval_seconds") or 1800),
    "next_scheduled_update_unix": int(data.get("next_scheduled_update_unix") or 0),
    "admin_enabled": os.environ.get("ADMIN_ENABLED", "0") == "1",
    "admin_port": int(os.environ.get("ADMIN_PORT") or data.get("admin_port") or 8080),
    "generation_active": os.environ.get("generation_active", "0") == "1",
    "generation_kind": os.environ.get("generation_kind", ""),
    "generation_message": os.environ.get("generation_message", ""),
    "generation_started_at_unix": int(os.environ["generation_started_at"]) if os.environ.get("generation_started_at") else None,
    "generation_progress_percent": int(os.environ.get("generation_progress_percent", "0") or 0),
    "generation_stage": os.environ.get("generation_stage", ""),
    "generation_stage_message": os.environ.get("generation_stage_message", ""),
    "generation_items_done": int(os.environ["generation_items_done"]) if os.environ.get("generation_items_done") else None,
    "generation_items_total": int(os.environ["generation_items_total"]) if os.environ.get("generation_items_total") else None,
    "startup_snapshot_used": os.environ.get("STARTUP_SNAPSHOT_USED", "0") == "1",
    "startup_snapshot_size_bytes": int(os.environ.get("STARTUP_SNAPSHOT_SIZE_BYTES", "0") or 0),
    "startup_snapshot_mtime_unix": int(os.environ["STARTUP_SNAPSHOT_MTIME_UNIX"]) if os.environ.get("STARTUP_SNAPSHOT_MTIME_UNIX") else None,
    "startup_snapshot_age_seconds": int(os.environ["STARTUP_SNAPSHOT_AGE_SECONDS"]) if os.environ.get("STARTUP_SNAPSHOT_AGE_SECONDS") else None,
    "last_update_reason": os.environ.get("LAST_UPDATE_REASON", ""),
    "last_update_message": os.environ.get("LAST_UPDATE_MESSAGE", ""),
    "last_update_success": None if os.environ.get("LAST_UPDATE_SUCCESS", "") == "" else os.environ.get("LAST_UPDATE_SUCCESS") == "1",
    "last_update_finished_at_unix": int(os.environ["LAST_UPDATE_FINISHED_AT_UNIX"]) if os.environ.get("LAST_UPDATE_FINISHED_AT_UNIX") else None,
    "degraded": os.environ.get("DEGRADED", "0") == "1",
    "degraded_reason": os.environ.get("DEGRADED_REASON", "") if os.environ.get("DEGRADED", "0") == "1" else "",
})
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

write_degraded_status() {
  reason="${1:-Route update failed; previous route snapshot remains active}"
  export STATUS_FILE LAST_UPDATE_REASON LAST_UPDATE_MESSAGE
  export DEGRADED_REASON="$reason"
  python3 - <<'PY'
import json
import os
import time
from pathlib import Path

path = Path(os.environ["STATUS_FILE"])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    data = {}

now = int(time.time())
data["success"] = False
data["degraded"] = True
data["degraded_reason"] = os.environ.get("DEGRADED_REASON", "")
data["run_reason"] = os.environ.get("LAST_UPDATE_REASON", data.get("run_reason", "manual"))
data["run_message"] = os.environ.get("LAST_UPDATE_MESSAGE", data.get("run_message", ""))
data["updated_at_unix"] = now
data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
data.setdefault("routes", {})
data.setdefault("sources", [])
data.setdefault("errors", [])
if data["degraded_reason"] and not any(
    isinstance(item, dict) and item.get("error") == data["degraded_reason"]
    for item in data["errors"]
):
    data["errors"].append({
        "kind": "runtime",
        "name": "apply",
        "status": "failed",
        "error": data["degraded_reason"],
    })

path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

cleanup() {
  if [ "$runtime_state_written" = "1" ]; then
    write_runtime_state 0 "" "" ""
  fi
  if [ "$lock_acquired" = "1" ]; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  rm -f "$tmp_old" "$tmp_new"
}
trap cleanup EXIT

if mkdir "$LOCK_DIR" 2>/dev/null; then
  lock_acquired=1
else
  echo "Another route update is already running: $LOCK_DIR" >&2
  exit 1
fi

write_runtime_state 1 "${ROUTE_UPDATE_REASON:-manual}" "${ROUTE_UPDATE_MESSAGE:-Running manual route update}" "$(date +%s)" 0 "bootstrap" "Preparing route update"
runtime_state_written=1
LAST_UPDATE_REASON="${ROUTE_UPDATE_REASON:-manual}"
LAST_UPDATE_MESSAGE="${ROUTE_UPDATE_MESSAGE:-Running manual route update}"
LAST_UPDATE_SUCCESS=""
LAST_UPDATE_FINISHED_AT_UNIX=""
DEGRADED=0
DEGRADED_REASON=""

export LISTS_FILE INCLUDE_ASNS_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
export INCLUDE_GOOGLE_RANGES CACHE_DIR CACHE_MAX_AGE STATUS_FILE METRICS_FILE RUNTIME_FILE SETTINGS_ENV_FILE
export ROUTES_FILE="$tmp_new"

if ! /update-routes.py --output "$tmp_new" --status "$STATUS_FILE" --metrics "$METRICS_FILE"; then
  echo "Route updater failed, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  LAST_UPDATE_SUCCESS=0
  LAST_UPDATE_FINISHED_AT_UNIX="$(date +%s)"
  DEGRADED=1
  DEGRADED_REASON="Route update failed; previous route snapshot remains active"
  write_degraded_status "$DEGRADED_REASON"
  write_runtime_state 0 "" "" ""
  exit 1
fi

if [ ! -s "$tmp_new" ]; then
  echo "Generated route list is empty, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  LAST_UPDATE_SUCCESS=0
  LAST_UPDATE_FINISHED_AT_UNIX="$(date +%s)"
  DEGRADED=1
  DEGRADED_REASON="Generated route list was empty; previous route snapshot remains active"
  write_degraded_status "$DEGRADED_REASON"
  write_runtime_state 0 "" "" ""
  exit 1
fi

cp "$tmp_new" "$ROUTES"

if birdc configure; then
  echo "BIRD accepted updated routes"
  cp "$tmp_new" "$LAST_GOOD_ROUTES"
  LAST_UPDATE_SUCCESS=1
  LAST_UPDATE_FINISHED_AT_UNIX="$(date +%s)"
  DEGRADED=0
  DEGRADED_REASON=""
else
  echo "BIRD rejected updated routes, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  birdc configure || true
  LAST_UPDATE_SUCCESS=0
  LAST_UPDATE_FINISHED_AT_UNIX="$(date +%s)"
  DEGRADED=1
  DEGRADED_REASON="BIRD rejected updated routes; previous route snapshot remains active"
  write_degraded_status "$DEGRADED_REASON"
  write_runtime_state 0 "" "" ""
  exit 1
fi
