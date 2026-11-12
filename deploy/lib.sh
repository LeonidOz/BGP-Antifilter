#!/bin/sh

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
DOMAIN_LIST_URLS_FILE="${DOMAIN_LIST_URLS_FILE:-/etc/bird/domain-list-urls.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-/etc/bird/include-asns.txt}"
INCLUDE_COUNTRIES_FILE="${INCLUDE_COUNTRIES_FILE:-/etc/bird/include-countries.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-/etc/bird/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-/etc/bird/exclude-domains.txt}"
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
SETTINGS_ENV_FILE="${SETTINGS_ENV_FILE:-/etc/bird/generated/settings.env}"
ADMIN_ENABLED="${ADMIN_ENABLED:-0}"
ADMIN_PORT="${ADMIN_PORT:-8080}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
DEFAULT_CONFIG_DIR="${DEFAULT_CONFIG_DIR:-/defaults-config}"
STATE_DIR="${STATE_DIR:-/run/bgp-antifilter}"
STARTUP_REFRESH_FLAG="${STATE_DIR}/startup-refresh-needed"
export STARTUP_REFRESH_FLAG

ensure_runtime_config_file() {
  target="$1"
  default_name="$2"
  target_dir="$(dirname "$target")"
  default_path="$DEFAULT_CONFIG_DIR/$default_name"

  mkdir -p "$target_dir"
  if [ -f "$target" ]; then
    return 0
  fi
  if [ -f "$default_path" ]; then
    cp "$default_path" "$target"
    echo "initialized runtime config $(basename "$target") from defaults"
    return 0
  fi
  : >"$target"
  echo "initialized empty runtime config $(basename "$target")"
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
  python3 - <<'PY'
import ipaddress
import os
import sys


def fail(message):
    print(f"Invalid environment: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_as(name):
    value = os.environ[name]
    try:
        number = int(value)
    except ValueError:
        fail(f"{name} must be an integer AS number")

    if not 1 <= number <= 4294967295:
        fail(f"{name} must be between 1 and 4294967295")


def validate_ipv4(name):
    value = os.environ[name]
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        fail(f"{name} must be a valid IPv4 address")


def validate_update_interval():
    for name in ("UPDATE_INTERVAL", "CACHE_MAX_AGE"):
        value = os.environ[name]
        try:
            seconds = int(value)
        except ValueError:
            fail(f"{name} must be an integer number of seconds")

        if seconds <= 0:
            fail(f"{name} must be greater than zero")


def validate_community():
    value = os.environ["BGP_COMMUNITY"]
    parts = value.split(",")

    if len(parts) != 2:
        fail("BGP_COMMUNITY must use the BIRD tuple format AS,VALUE")

    for part in parts:
        try:
            number = int(part)
        except ValueError:
            fail("BGP_COMMUNITY parts must be integers")

        if not 0 <= number <= 65535:
            fail("BGP_COMMUNITY parts must be between 0 and 65535")


def validate_admin():
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


validate_as("MY_AS")
validate_as("MT_AS")
validate_ipv4("MT_IP")
validate_ipv4("BIRD_IP")
validate_ipv4("ROUTER_ID")
validate_update_interval()
validate_community()
validate_admin()
PY
}

render_bird_config() {
  export MY_AS MT_AS MT_IP BIRD_IP ROUTER_ID BGP_COMMUNITY
  python3 - "$BIRD_TEMPLATE" "$BIRD_CONFIG" <<'PY'
import os
import string
import sys

template_file, config_file = sys.argv[1:3]

with open(template_file, encoding="utf-8") as file:
    template = string.Template(file.read())

with open(config_file, "w", encoding="utf-8") as file:
    file.write(template.safe_substitute(os.environ))
PY
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
  python3 - "$next_update" <<'PY'
import json
import os
from pathlib import Path
import sys
import time

path = Path(os.environ["RUNTIME_FILE"])
path.parent.mkdir(parents=True, exist_ok=True)
now = int(time.time())
next_update = int(sys.argv[1])
network_status_file = Path(os.environ["NETWORK_STATUS_FILE"])
try:
    network = json.loads(network_status_file.read_text(encoding="utf-8")) if network_status_file.exists() else {}
except (OSError, json.JSONDecodeError):
    network = {}
data = {
    "updated_at_unix": now,
    "update_interval_seconds": int(os.environ["UPDATE_INTERVAL"]),
    "next_scheduled_update_unix": next_update,
    "admin_enabled": os.environ["ADMIN_ENABLED"] == "1",
    "admin_port": int(os.environ["ADMIN_PORT"]),
    "generation_active": os.environ.get("GENERATION_ACTIVE", "0") == "1",
    "generation_kind": os.environ.get("GENERATION_KIND", ""),
    "generation_message": os.environ.get("GENERATION_MESSAGE", ""),
    "generation_started_at_unix": int(os.environ["GENERATION_STARTED_AT"]) if os.environ.get("GENERATION_STARTED_AT") else None,
    "generation_progress_percent": int(os.environ.get("GENERATION_PROGRESS_PERCENT", "0") or 0),
    "generation_stage": os.environ.get("GENERATION_STAGE", ""),
    "generation_stage_message": os.environ.get("GENERATION_STAGE_MESSAGE", ""),
    "generation_items_done": int(os.environ["GENERATION_ITEMS_DONE"]) if os.environ.get("GENERATION_ITEMS_DONE") else None,
    "generation_items_total": int(os.environ["GENERATION_ITEMS_TOTAL"]) if os.environ.get("GENERATION_ITEMS_TOTAL") else None,
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
    "network": network,
}
if os.environ.get("RUNTIME_PRESERVE_STATE") == "1":
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    for key, value in previous.items():
        if key.startswith(("generation_", "startup_snapshot_", "last_update_", "degraded")):
            data[key] = value
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

runtime_next_update_unix() {
  export RUNTIME_FILE
  python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RUNTIME_FILE"])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("")
    raise SystemExit(0)

value = data.get("next_scheduled_update_unix")
if value in (None, ""):
    print("")
else:
    print(int(value))
PY
}

setup_runtime_dirs() {
  mkdir -p /etc/bird/generated "$CACHE_DIR" /run/bird "$STATE_DIR"
}

prepare_runtime_files() {
  ensure_runtime_config_file "$LISTS_FILE" "lists.txt"
  ensure_runtime_config_file "$DOMAIN_LIST_URLS_FILE" "domain-list-urls.txt"
  ensure_runtime_config_file "$INCLUDE_ASNS_FILE" "include-asns.txt"
  ensure_runtime_config_file "$INCLUDE_COUNTRIES_FILE" "include-countries.txt"
  ensure_runtime_config_file "$INCLUDE_DOMAINS_FILE" "include-domains.txt"
  ensure_runtime_config_file "$EXCLUDE_DOMAINS_FILE" "exclude-domains.txt"
  touch "$ROUTES" "$LAST_GOOD_ROUTES" "$CONTAINER_LOG_FILE"
}

export_runtime_env() {
  export LISTS_FILE DOMAIN_LIST_URLS_FILE INCLUDE_ASNS_FILE INCLUDE_COUNTRIES_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
  export INCLUDE_GOOGLE_RANGES CACHE_DIR CACHE_MAX_AGE STATUS_FILE METRICS_FILE RUNTIME_FILE NETWORK_STATUS_FILE SETTINGS_ENV_FILE
  export ROUTES_FILE="$ROUTES"
  export LAST_GOOD_ROUTES_FILE="$LAST_GOOD_ROUTES"
  export ADMIN_ENABLED ADMIN_PORT ADMIN_PASSWORD
}

write_network_status() {
  NETWORK_STATUS_FILE="$NETWORK_STATUS_FILE" python3 -m bgp_antifilter.network_diagnostics --bird-ip "$BIRD_IP" >"$NETWORK_STATUS_FILE.tmp"
  mv "$NETWORK_STATUS_FILE.tmp" "$NETWORK_STATUS_FILE"
}

print_network_status_warning() {
  NETWORK_STATUS_FILE="$NETWORK_STATUS_FILE" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["NETWORK_STATUS_FILE"])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)
message = str(payload.get("message") or "").strip()
if message and not payload.get("bird_ip_assigned", False):
    print(message)
PY
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
