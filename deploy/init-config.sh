#!/bin/sh
set -eu

# shellcheck source=deploy/lib.sh
. /lib.sh

load_settings_env
validate_env
setup_runtime_dirs
prepare_runtime_files
export_runtime_env
write_network_status
print_network_status_warning
render_bird_config
rm -f "$STARTUP_REFRESH_FLAG"

startup_mode="$(python3 -m bgp_antifilter.route_runtime startup-mode "$LAST_GOOD_ROUTES")"
startup_snapshot_json="$(python3 -m bgp_antifilter.route_runtime startup-mode "$LAST_GOOD_ROUTES" --json)"
startup_snapshot_values="$(python3 - "$startup_snapshot_json" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
print("1" if data.get("startup_snapshot_used") else "0")
print(int(data.get("startup_snapshot_size_bytes") or 0))
print("" if data.get("startup_snapshot_mtime_unix") is None else int(data["startup_snapshot_mtime_unix"]))
print("" if data.get("startup_snapshot_age_seconds") is None else int(data["startup_snapshot_age_seconds"]))
PY
)"
STARTUP_SNAPSHOT_USED="$(printf '%s\n' "$startup_snapshot_values" | sed -n '1p')"
STARTUP_SNAPSHOT_SIZE_BYTES="$(printf '%s\n' "$startup_snapshot_values" | sed -n '2p')"
STARTUP_SNAPSHOT_MTIME_UNIX="$(printf '%s\n' "$startup_snapshot_values" | sed -n '3p')"
STARTUP_SNAPSHOT_AGE_SECONDS="$(printf '%s\n' "$startup_snapshot_values" | sed -n '4p')"
export STARTUP_SNAPSHOT_USED STARTUP_SNAPSHOT_SIZE_BYTES STARTUP_SNAPSHOT_MTIME_UNIX STARTUP_SNAPSHOT_AGE_SECONDS

if [ "$startup_mode" = "background-refresh" ]; then
  echo "Starting BIRD with existing route snapshot while refreshing routes in background" >>"$CONTAINER_LOG_FILE"
  cp "$LAST_GOOD_ROUTES" "$ROUTES"
  GENERATION_ACTIVE=1
  GENERATION_KIND="startup"
  GENERATION_MESSAGE="Starting with previous routes while refreshing in background"
  GENERATION_STARTED_AT="$(date +%s)"
  GENERATION_PROGRESS_PERCENT=0
  GENERATION_STAGE="bootstrap"
  GENERATION_STAGE_MESSAGE="Using previous route snapshot until refresh completes"
  GENERATION_ITEMS_DONE=""
  GENERATION_ITEMS_TOTAL=""
  export GENERATION_ACTIVE GENERATION_KIND GENERATION_MESSAGE GENERATION_STARTED_AT GENERATION_PROGRESS_PERCENT GENERATION_STAGE GENERATION_STAGE_MESSAGE GENERATION_ITEMS_DONE GENERATION_ITEMS_TOTAL
  write_runtime 0
  : >"$STARTUP_REFRESH_FLAG"
  exit 0
fi

GENERATION_ACTIVE=1
GENERATION_KIND="initial"
GENERATION_MESSAGE="Preparing routes before BIRD startup"
GENERATION_STARTED_AT="$(date +%s)"
GENERATION_PROGRESS_PERCENT=0
GENERATION_STAGE="bootstrap"
GENERATION_STAGE_MESSAGE="Preparing initial route generation"
GENERATION_ITEMS_DONE=""
GENERATION_ITEMS_TOTAL=""
export GENERATION_ACTIVE GENERATION_KIND GENERATION_MESSAGE GENERATION_STARTED_AT GENERATION_PROGRESS_PERCENT GENERATION_STAGE GENERATION_STAGE_MESSAGE GENERATION_ITEMS_DONE GENERATION_ITEMS_TOTAL
write_runtime 0
update_routes noapply
GENERATION_ACTIVE=0
GENERATION_KIND=""
GENERATION_MESSAGE=""
GENERATION_STARTED_AT=""
GENERATION_PROGRESS_PERCENT=100
GENERATION_STAGE="completed"
GENERATION_STAGE_MESSAGE="Initial route generation complete"
GENERATION_ITEMS_DONE=""
GENERATION_ITEMS_TOTAL=""
LAST_UPDATE_REASON="initial"
LAST_UPDATE_MESSAGE="Initial route generation complete"
LAST_UPDATE_SUCCESS=1
LAST_UPDATE_FINISHED_AT_UNIX="$(date +%s)"
DEGRADED=0
DEGRADED_REASON=""
export GENERATION_ACTIVE GENERATION_KIND GENERATION_MESSAGE GENERATION_STARTED_AT GENERATION_PROGRESS_PERCENT GENERATION_STAGE GENERATION_STAGE_MESSAGE GENERATION_ITEMS_DONE GENERATION_ITEMS_TOTAL
export LAST_UPDATE_REASON LAST_UPDATE_MESSAGE LAST_UPDATE_SUCCESS LAST_UPDATE_FINISHED_AT_UNIX DEGRADED DEGRADED_REASON
cp "$ROUTES" "$LAST_GOOD_ROUTES"
write_runtime 0

if [ ! -s "$ROUTES" ]; then
  echo "No routes are available after initial update, refusing to start BIRD with an empty table" >&2
  exit 1
fi
