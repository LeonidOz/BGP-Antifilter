#!/bin/sh
set -eu

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-/etc/bird/include-asns.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-/etc/bird/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-/etc/bird/exclude-domains.txt}"
INCLUDE_GOOGLE_RANGES="${INCLUDE_GOOGLE_RANGES:-1}"
CACHE_MAX_AGE="${CACHE_MAX_AGE:-604800}"
ROUTES="${ROUTES_FILE:-/etc/bird/generated/routes.conf}"
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

tmp_old="$(mktemp)"
cp "$ROUTES" "$tmp_old"
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
})
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
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
  rm -f "$tmp_old"
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

export LISTS_FILE INCLUDE_ASNS_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
export INCLUDE_GOOGLE_RANGES CACHE_DIR CACHE_MAX_AGE STATUS_FILE METRICS_FILE RUNTIME_FILE SETTINGS_ENV_FILE
export ROUTES_FILE="$ROUTES"

if ! /update-routes.py --output "$ROUTES" --status "$STATUS_FILE" --metrics "$METRICS_FILE"; then
  echo "Route updater failed, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  exit 1
fi

if [ ! -s "$ROUTES" ]; then
  echo "Generated route list is empty, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  exit 1
fi

if birdc configure; then
  echo "BIRD accepted updated routes"
else
  echo "BIRD rejected updated routes, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  birdc configure || true
  exit 1
fi
