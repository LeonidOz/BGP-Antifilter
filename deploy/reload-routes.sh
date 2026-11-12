#!/bin/sh
set -eu

CONFIG_DIR="${CONFIG_DIR:-/etc/bird/config}"
LISTS_FILE="${LISTS_FILE:-$CONFIG_DIR/lists.txt}"
DOMAIN_LIST_URLS_FILE="${DOMAIN_LIST_URLS_FILE:-$CONFIG_DIR/domain-list-urls.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-$CONFIG_DIR/include-asns.txt}"
INCLUDE_COUNTRIES_FILE="${INCLUDE_COUNTRIES_FILE:-$CONFIG_DIR/include-countries.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-$CONFIG_DIR/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-$CONFIG_DIR/exclude-domains.txt}"
INCLUDE_GOOGLE_RANGES="${INCLUDE_GOOGLE_RANGES:-1}"
CACHE_MAX_AGE="${CACHE_MAX_AGE:-604800}"
ROUTES="${ROUTES_FILE:-/etc/bird/generated/routes.conf}"
LAST_GOOD_ROUTES="${LAST_GOOD_ROUTES_FILE:-/etc/bird/generated/routes.last-good.conf}"
CACHE_DIR="${CACHE_DIR:-/etc/bird/generated/cache}"
STATUS_FILE="${STATUS_FILE:-/etc/bird/generated/status.json}"
METRICS_FILE="${METRICS_FILE:-/etc/bird/generated/metrics.prom}"
RUNTIME_FILE="${RUNTIME_FILE:-/etc/bird/generated/runtime.json}"
NETWORK_STATUS_FILE="${NETWORK_STATUS_FILE:-/etc/bird/generated/network-status.json}"
LOCK_DIR="${UPDATE_LOCK_DIR:-/etc/bird/generated/update.lock}"
SETTINGS_ENV_FILE="${SETTINGS_ENV_FILE:-$CONFIG_DIR/settings.env}"

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
  export RUNTIME_FILE NETWORK_STATUS_FILE UPDATE_INTERVAL ADMIN_ENABLED ADMIN_PORT
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
  python3 -m bgp_antifilter.runtime_state write-reload
}

write_degraded_status() {
  reason="${1:-Route update failed; previous route snapshot remains active}"
  export STATUS_FILE NETWORK_STATUS_FILE LAST_UPDATE_REASON LAST_UPDATE_MESSAGE
  export DEGRADED_REASON="$reason"
  python3 -m bgp_antifilter.runtime_state write-degraded-status
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

export LISTS_FILE DOMAIN_LIST_URLS_FILE INCLUDE_ASNS_FILE INCLUDE_COUNTRIES_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
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
