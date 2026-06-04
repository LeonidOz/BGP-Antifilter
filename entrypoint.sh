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

mkdir -p /etc/bird/generated
mkdir -p /run/bird
touch "$ROUTES"

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
      mv "$tmp_out" "$ROUTES"
      birdc configure || true
    else
      echo "Route list is empty, keeping old routes"
      rm -f "$tmp_out"
    fi
  else
    echo "Failed to download route list"
  fi

  rm -f "$tmp_base" "$tmp_ex" "$tmp_add" "$tmp_out"
}

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
