#!/bin/sh

CONFIG_DIR="${CONFIG_DIR:-/etc/bird/config}"
GENERATED_DIR="${GENERATED_DIR:-/etc/bird/generated}"
LISTS_FILE="${LISTS_FILE:-$CONFIG_DIR/lists.txt}"
DOMAIN_LIST_URLS_FILE="${DOMAIN_LIST_URLS_FILE:-$CONFIG_DIR/domain-list-urls.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-$CONFIG_DIR/include-asns.txt}"
INCLUDE_COUNTRIES_FILE="${INCLUDE_COUNTRIES_FILE:-$CONFIG_DIR/include-countries.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-$CONFIG_DIR/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-$CONFIG_DIR/exclude-domains.txt}"
INCLUDE_GOOGLE_RANGES="${INCLUDE_GOOGLE_RANGES:-1}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-1800}"
CACHE_MAX_AGE="${CACHE_MAX_AGE:-604800}"
MY_AS="${MY_AS:-64500}"
MT_AS="${MT_AS:-65455}"
MT_IP="${MT_IP:-192.168.55.1}"
BIRD_IP="${BIRD_IP:-192.168.55.5}"
ROUTER_ID="${ROUTER_ID:-$BIRD_IP}"
BGP_COMMUNITY="${BGP_COMMUNITY:-65432,500}"
BIRD_TEMPLATE="${BIRD_TEMPLATE:-/etc/bird/bird.conf.template}"
BIRD_CONFIG="${BIRD_CONFIG:-/etc/bird/bird.conf}"
ROUTES="${ROUTES_FILE:-/etc/bird/generated/routes.conf}"
LAST_GOOD_ROUTES="${LAST_GOOD_ROUTES_FILE:-/etc/bird/generated/routes.last-good.conf}"
CACHE_DIR="${CACHE_DIR:-/etc/bird/generated/cache}"
STATUS_FILE="${STATUS_FILE:-/etc/bird/generated/status.json}"
METRICS_FILE="${METRICS_FILE:-/etc/bird/generated/metrics.prom}"
RUNTIME_FILE="${RUNTIME_FILE:-/etc/bird/generated/runtime.json}"
NETWORK_STATUS_FILE="${NETWORK_STATUS_FILE:-/etc/bird/generated/network-status.json}"
CONTAINER_LOG_FILE="${CONTAINER_LOG_FILE:-/etc/bird/generated/container.log}"
SETTINGS_FILE="${SETTINGS_FILE:-$CONFIG_DIR/settings.json}"
SETTINGS_ENV_FILE="${SETTINGS_ENV_FILE:-$CONFIG_DIR/settings.env}"
LIST_BACKUP_DIR="${LIST_BACKUP_DIR:-$(dirname "$SETTINGS_FILE")/list-backups}"
ADMIN_ENABLED="${ADMIN_ENABLED:-0}"
ADMIN_PORT="${ADMIN_PORT:-8080}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
DEFAULT_CONFIG_DIR="${DEFAULT_CONFIG_DIR:-/defaults-config}"
STATE_DIR="${STATE_DIR:-/run/bgp-antifilter}"
STARTUP_REFRESH_FLAG="${STATE_DIR}/startup-refresh-needed"
export STARTUP_REFRESH_FLAG

prepare_user_config() {
  export CONFIG_DIR GENERATED_DIR DEFAULT_CONFIG_DIR SETTINGS_FILE SETTINGS_ENV_FILE LIST_BACKUP_DIR
  export LISTS_FILE DOMAIN_LIST_URLS_FILE INCLUDE_ASNS_FILE INCLUDE_COUNTRIES_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
  python3 -m bgp_antifilter.config_migration
}

load_settings_env() {
  if [ -f "$SETTINGS_ENV_FILE" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$SETTINGS_ENV_FILE"
    set +a
  fi
}

validate_env() {
  export MY_AS MT_AS MT_IP BIRD_IP ROUTER_ID BGP_COMMUNITY UPDATE_INTERVAL CACHE_MAX_AGE ADMIN_ENABLED ADMIN_PORT ADMIN_PASSWORD
  python3 -m bgp_antifilter.container_runtime validate-env
}

render_bird_config() {
  export MY_AS MT_AS MT_IP BIRD_IP ROUTER_ID BGP_COMMUNITY
  python3 -m bgp_antifilter.container_runtime render-bird "$BIRD_TEMPLATE" "$BIRD_CONFIG"
}

update_routes() {
  apply="${1:-apply}"
  reason="${2:-manual}"
  load_settings_env

  if [ "$apply" = "apply" ]; then
    update_message="$(python3 -m bgp_antifilter.route_runtime update-message "$reason")"
    ROUTE_UPDATE_REASON="$reason" ROUTE_UPDATE_MESSAGE="$update_message" /reload-routes.sh
    return $?
  fi

  if /update-routes.py --output "$ROUTES" --status "$STATUS_FILE" --metrics "$METRICS_FILE"; then
    if [ ! -s "$ROUTES" ]; then
      echo "Generated route list is empty, restoring previous routes" >&2
      return 1
    fi

    echo "Routes prepared before BIRD startup"
  else
    echo "Route updater failed" >&2
    return 1
  fi
}

write_runtime() {
  next_update="${1:-0}"
  load_settings_env
  export RUNTIME_FILE NETWORK_STATUS_FILE UPDATE_INTERVAL ADMIN_ENABLED ADMIN_PORT
  export GENERATION_ACTIVE="${GENERATION_ACTIVE:-0}"
  export GENERATION_KIND="${GENERATION_KIND:-}"
  export GENERATION_MESSAGE="${GENERATION_MESSAGE:-}"
  export GENERATION_STARTED_AT="${GENERATION_STARTED_AT:-}"
  export GENERATION_PROGRESS_PERCENT="${GENERATION_PROGRESS_PERCENT:-0}"
  export GENERATION_STAGE="${GENERATION_STAGE:-}"
  export GENERATION_STAGE_MESSAGE="${GENERATION_STAGE_MESSAGE:-}"
  export GENERATION_ITEMS_DONE="${GENERATION_ITEMS_DONE:-}"
  export GENERATION_ITEMS_TOTAL="${GENERATION_ITEMS_TOTAL:-}"
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
  python3 -m bgp_antifilter.runtime_state write-schedule "$next_update"
}

runtime_next_update_unix() {
  export RUNTIME_FILE
  python3 -m bgp_antifilter.runtime_state next-update
}

setup_runtime_dirs() {
  mkdir -p "$GENERATED_DIR" "$CACHE_DIR" /run/bird "$STATE_DIR"
}

prepare_runtime_files() {
  touch "$ROUTES" "$LAST_GOOD_ROUTES" "$CONTAINER_LOG_FILE"
}

export_runtime_env() {
  export CONFIG_DIR GENERATED_DIR SETTINGS_FILE LIST_BACKUP_DIR
  export LISTS_FILE DOMAIN_LIST_URLS_FILE INCLUDE_ASNS_FILE INCLUDE_COUNTRIES_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
  export INCLUDE_GOOGLE_RANGES CACHE_DIR CACHE_MAX_AGE STATUS_FILE METRICS_FILE RUNTIME_FILE NETWORK_STATUS_FILE SETTINGS_ENV_FILE
  export ROUTES_FILE="$ROUTES"
  export LAST_GOOD_ROUTES_FILE="$LAST_GOOD_ROUTES"
  export ADMIN_ENABLED ADMIN_PORT ADMIN_PASSWORD
}

write_network_status() {
  NETWORK_STATUS_FILE="$NETWORK_STATUS_FILE" python3 -m bgp_antifilter.container_runtime write-network-status "$BIRD_IP"
}

print_network_status_warning() {
  NETWORK_STATUS_FILE="$NETWORK_STATUS_FILE" python3 -m bgp_antifilter.container_runtime network-warning
}

start_log_stream() {
  name="${1:-service}"
  mkdir -p "$(dirname "$CONTAINER_LOG_FILE")"
  touch "$CONTAINER_LOG_FILE"
  log_dir="$(mktemp -d)"
  mkfifo "$log_dir/output"
  tee -a "$CONTAINER_LOG_FILE" <"$log_dir/output" &
  exec >"$log_dir/output" 2>&1
  rm "$log_dir/output"
  rmdir "$log_dir"
  echo "[$name] started at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
