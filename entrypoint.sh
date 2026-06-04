#!/bin/sh
set -eu

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-/etc/bird/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-/etc/bird/exclude-domains.txt}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-1800}"
MY_AS="${MY_AS:-64500}"
MT_AS="${MT_AS:-65455}"
MT_IP="${MT_IP:-192.168.55.1}"
BIRD_IP="${BIRD_IP:-192.168.55.5}"
ROUTER_ID="${ROUTER_ID:-$BIRD_IP}"
BGP_COMMUNITY="${BGP_COMMUNITY:-65432,500}"
BIRD_TEMPLATE="${BIRD_TEMPLATE:-/etc/bird/bird.conf.template}"
BIRD_CONFIG="${BIRD_CONFIG:-/etc/bird/bird.conf}"
ROUTES="/etc/bird/generated/routes.conf"

validate_env() {
  export MY_AS MT_AS MT_IP BIRD_IP ROUTER_ID BGP_COMMUNITY UPDATE_INTERVAL
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
    value = os.environ["UPDATE_INTERVAL"]
    try:
        seconds = int(value)
    except ValueError:
        fail("UPDATE_INTERVAL must be an integer number of seconds")

    if seconds <= 0:
        fail("UPDATE_INTERVAL must be greater than zero")


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
  tmp_base="$(mktemp)"
  tmp_ex="$(mktemp)"
  tmp_add="$(mktemp)"
  tmp_out="$(mktemp)"
  tmp_old="$(mktemp)"

  echo "Updating routes from $LISTS_FILE"

  if grep -Ev '^[[:space:]]*($|#)' "$LISTS_FILE" | while read -r url; do
      echo "Fetching $url" >&2
      curl -4 --retry 5 --retry-delay 5 -fsSL "$url"
    done \
    | tr -d '\r' > "$tmp_base"; then

    : > "$tmp_ex"
    : > "$tmp_add"

    grep -Ev '^[[:space:]]*($|#)' "$EXCLUDE_DOMAINS_FILE" | while read -r domain; do
      echo "Resolving exclude domain $domain" >&2
      getent ahostsv4 "$domain" | awk '{print $1 "/32"}' >> "$tmp_ex" || true
    done

    grep -Ev '^[[:space:]]*($|#)' "$INCLUDE_DOMAINS_FILE" | while read -r domain; do
      echo "Resolving include domain $domain" >&2
      getent ahostsv4 "$domain" | awk '{print $1 "/32"}' >> "$tmp_add" || true
    done

    sort -u -o "$tmp_ex" "$tmp_ex"
    sort -u -o "$tmp_add" "$tmp_add"

    /generate-routes.py "$tmp_base" "$tmp_ex" "$tmp_add" "$tmp_out"

    count="$(wc -l < "$tmp_out")"
    echo "Generated $count routes after include/exclude"

    if [ "$count" -gt 0 ]; then
      cp "$ROUTES" "$tmp_old"
      mv "$tmp_out" "$ROUTES"
      if birdc configure; then
        echo "BIRD accepted updated routes"
      else
        echo "BIRD rejected updated routes, restoring previous routes" >&2
        cp "$tmp_old" "$ROUTES"
        birdc configure || true
      fi
    else
      echo "Route list is empty, keeping old routes"
      rm -f "$tmp_out"
    fi
  else
    echo "Failed to download route list"
  fi

  rm -f "$tmp_base" "$tmp_ex" "$tmp_add" "$tmp_out" "$tmp_old"
}

validate_env

mkdir -p /etc/bird/generated
mkdir -p /run/bird
touch "$ROUTES"

render_bird_config

bird -f -c "$BIRD_CONFIG" &
BIRD_PID="$!"

sleep 2
update_routes

while true; do
  sleep "$UPDATE_INTERVAL"
  update_routes
done &

wait "$BIRD_PID"
