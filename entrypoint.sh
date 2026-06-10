#!/bin/sh
set -eu

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-/etc/bird/include-asns.txt}"
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
ROUTES="/etc/bird/generated/routes.conf"
CACHE_DIR="${CACHE_DIR:-/etc/bird/generated/cache}"
STATUS_FILE="${STATUS_FILE:-/etc/bird/generated/status.json}"
METRICS_FILE="${METRICS_FILE:-/etc/bird/generated/metrics.prom}"
RUNTIME_FILE="${RUNTIME_FILE:-/etc/bird/generated/runtime.json}"
CONTAINER_LOG_FILE="${CONTAINER_LOG_FILE:-/etc/bird/generated/container.log}"
SETTINGS_ENV_FILE="${SETTINGS_ENV_FILE:-/etc/bird/generated/settings.env}"
ADMIN_ENABLED="${ADMIN_ENABLED:-0}"
ADMIN_PORT="${ADMIN_PORT:-8080}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

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
  load_settings_env

  if [ "$apply" = "apply" ]; then
    /reload-routes.sh
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
  export RUNTIME_FILE UPDATE_INTERVAL ADMIN_ENABLED ADMIN_PORT
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
data = {
    "updated_at_unix": now,
    "update_interval_seconds": int(os.environ["UPDATE_INTERVAL"]),
    "next_scheduled_update_unix": next_update,
    "admin_enabled": os.environ["ADMIN_ENABLED"] == "1",
    "admin_port": int(os.environ["ADMIN_PORT"]),
}
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

load_settings_env
validate_env

mkdir -p /etc/bird/generated
mkdir -p "$CACHE_DIR"
mkdir -p /run/bird
touch "$ROUTES"
touch "$CONTAINER_LOG_FILE"
exec >>"$CONTAINER_LOG_FILE" 2>&1
echo "container log started at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

export LISTS_FILE INCLUDE_ASNS_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
export INCLUDE_GOOGLE_RANGES CACHE_DIR CACHE_MAX_AGE STATUS_FILE METRICS_FILE RUNTIME_FILE SETTINGS_ENV_FILE
export ROUTES_FILE="$ROUTES"
export ADMIN_ENABLED ADMIN_PORT ADMIN_PASSWORD

render_bird_config
update_routes noapply
write_runtime 0

if [ ! -s "$ROUTES" ]; then
  echo "No routes are available after initial update, refusing to start BIRD with an empty table" >&2
  exit 1
fi

if [ "$ADMIN_ENABLED" = "1" ]; then
  /admin-server.py &
fi

bird -f -c "$BIRD_CONFIG" &
BIRD_PID="$!"

sleep 2

while true; do
  load_settings_env
  now="$(date +%s)"
  current_interval="$UPDATE_INTERVAL"
  next_update=$((now + current_interval))
  write_runtime "$next_update"

  while true; do
    load_settings_env
    now="$(date +%s)"
    if [ "$UPDATE_INTERVAL" != "$current_interval" ]; then
      current_interval="$UPDATE_INTERVAL"
      next_update=$((now + current_interval))
      write_runtime "$next_update"
    fi
    remaining=$((next_update - now))
    if [ "$remaining" -le 0 ]; then
      break
    fi
    if [ "$remaining" -gt 10 ]; then
      sleep 10
    else
      sleep "$remaining"
    fi
  done

  update_routes
done &

wait "$BIRD_PID"
