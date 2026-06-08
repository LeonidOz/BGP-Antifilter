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

validate_env() {
  export MY_AS MT_AS MT_IP BIRD_IP ROUTER_ID BGP_COMMUNITY UPDATE_INTERVAL CACHE_MAX_AGE
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


validate_as("MY_AS")
validate_as("MT_AS")
validate_ipv4("MT_IP")
validate_ipv4("BIRD_IP")
validate_ipv4("ROUTER_ID")
validate_update_interval()
validate_community()
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

validate_env

mkdir -p /etc/bird/generated
mkdir -p "$CACHE_DIR"
mkdir -p /run/bird
touch "$ROUTES"

export LISTS_FILE INCLUDE_ASNS_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
export INCLUDE_GOOGLE_RANGES CACHE_DIR CACHE_MAX_AGE STATUS_FILE METRICS_FILE
export ROUTES_FILE="$ROUTES"

render_bird_config
update_routes noapply

if [ ! -s "$ROUTES" ]; then
  echo "No routes are available after initial update, refusing to start BIRD with an empty table" >&2
  exit 1
fi

bird -f -c "$BIRD_CONFIG" &
BIRD_PID="$!"

sleep 2

while true; do
  sleep "$UPDATE_INTERVAL"
  update_routes
done &

wait "$BIRD_PID"
