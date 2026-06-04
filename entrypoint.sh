#!/bin/sh
set -eu

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-/etc/bird/include-asns.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-/etc/bird/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-/etc/bird/exclude-domains.txt}"
INCLUDE_GOOGLE_RANGES="${INCLUDE_GOOGLE_RANGES:-1}"
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

read_non_comment_lines() {
  source_file="$1"
  output_file="$2"

  if [ -f "$source_file" ]; then
    grep -Ev '^[[:space:]]*($|#)' "$source_file" > "$output_file" || true
  else
    : > "$output_file"
  fi
}

update_routes() {
  apply="${1:-apply}"
  tmp_base="$(mktemp)"
  tmp_ex="$(mktemp)"
  tmp_add="$(mktemp)"
  tmp_out="$(mktemp)"
  tmp_old="$(mktemp)"
  tmp_urls="$(mktemp)"
  tmp_asns="$(mktemp)"
  tmp_fetch="$(mktemp)"
  tmp_google="$(mktemp)"
  tmp_google_cloud="$(mktemp)"
  download_failed=0

  echo "Updating routes from $LISTS_FILE"

  read_non_comment_lines "$LISTS_FILE" "$tmp_urls"

  if [ ! -s "$tmp_urls" ]; then
    echo "No route sources configured, keeping old routes" >&2
    download_failed=1
  fi

  : > "$tmp_base"

  while IFS= read -r url; do
      echo "Fetching $url" >&2
      if curl -4 --retry 5 --retry-delay 5 -fsSL "$url" -o "$tmp_fetch"; then
        tr -d '\r' < "$tmp_fetch" >> "$tmp_base"
        printf '\n' >> "$tmp_base"
      else
        echo "Failed to fetch $url" >&2
        download_failed=1
      fi
  done < "$tmp_urls"

  read_non_comment_lines "$INCLUDE_ASNS_FILE" "$tmp_asns"

  while IFS= read -r asn; do
    asn_number="$(printf '%s' "$asn" | sed 's/^[Aa][Ss]//')"

    case "$asn_number" in
      ''|*[!0-9]*)
        echo "Skipping invalid include ASN $asn" >&2
        continue
        ;;
    esac

    echo "Fetching include ASN AS$asn_number prefixes" >&2
    if curl -4 --retry 5 --retry-delay 5 -fsSL "https://api.routeviews.org/asn/$asn_number" -o "$tmp_fetch"; then
      tr -d '\r' < "$tmp_fetch" >> "$tmp_base"
      printf '\n' >> "$tmp_base"
    else
      echo "Failed to fetch include ASN AS$asn_number prefixes" >&2
      download_failed=1
    fi
  done < "$tmp_asns"

  if [ "$INCLUDE_GOOGLE_RANGES" = "1" ]; then
    echo "Fetching Google default service ranges" >&2

    if curl -4 --retry 5 --retry-delay 5 -fsSL "https://www.gstatic.com/ipranges/goog.json" -o "$tmp_google" \
      && curl -4 --retry 5 --retry-delay 5 -fsSL "https://www.gstatic.com/ipranges/cloud.json" -o "$tmp_google_cloud"; then
      if python3 - "$tmp_google" "$tmp_google_cloud" >> "$tmp_base" <<'PY'
import ipaddress
import json
import sys


def read_ipv4_prefixes(path):
    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    networks = []
    for item in data.get("prefixes", []):
        prefix = item.get("ipv4Prefix")
        if prefix:
            networks.append(ipaddress.ip_network(prefix, strict=False))

    return networks


google = read_ipv4_prefixes(sys.argv[1])
cloud = read_ipv4_prefixes(sys.argv[2])
result = []

for network in google:
    remaining = [network]

    for excluded in cloud:
        next_remaining = []

        for candidate in remaining:
            if not candidate.overlaps(excluded):
                next_remaining.append(candidate)
            elif candidate.subnet_of(excluded):
                continue
            elif excluded.subnet_of(candidate):
                next_remaining.extend(candidate.address_exclude(excluded))
            else:
                next_remaining.append(candidate)

        remaining = next_remaining

    result.extend(remaining)

for network in sorted(set(result), key=lambda net: (int(net.network_address), net.prefixlen)):
    print(network)
PY
      then
        :
      else
        echo "Failed to process Google ranges, keeping old routes" >&2
        download_failed=1
      fi
    else
      echo "Failed to fetch Google ranges, keeping old routes" >&2
      download_failed=1
    fi
  fi

  : > "$tmp_ex"
  : > "$tmp_add"

  read_non_comment_lines "$EXCLUDE_DOMAINS_FILE" "$tmp_urls"

  while IFS= read -r domain; do
    echo "Resolving exclude domain $domain" >&2
    if getent ahostsv4 "$domain" > "$tmp_fetch" && [ -s "$tmp_fetch" ]; then
      awk '{print $1 "/32"}' "$tmp_fetch" >> "$tmp_ex"
    else
      echo "Failed to resolve exclude domain $domain, keeping old routes" >&2
      download_failed=1
    fi
  done < "$tmp_urls"

  read_non_comment_lines "$INCLUDE_DOMAINS_FILE" "$tmp_urls"

  while IFS= read -r domain; do
    echo "Resolving include domain $domain" >&2
    if getent ahostsv4 "$domain" > "$tmp_fetch" && [ -s "$tmp_fetch" ]; then
      awk '{print $1 "/32"}' "$tmp_fetch" >> "$tmp_add"
    else
      echo "Failed to resolve include domain $domain, keeping old routes" >&2
      download_failed=1
    fi
  done < "$tmp_urls"

  if [ "$download_failed" -eq 0 ]; then
    sort -u -o "$tmp_ex" "$tmp_ex"
    sort -u -o "$tmp_add" "$tmp_add"

    /generate-routes.py "$tmp_base" "$tmp_ex" "$tmp_add" "$tmp_out"

    count="$(wc -l < "$tmp_out")"
    echo "Generated $count routes after include/exclude"

    if [ "$count" -gt 0 ]; then
      cp "$ROUTES" "$tmp_old"
      mv "$tmp_out" "$ROUTES"

      if [ "$apply" = "apply" ]; then
        if birdc configure; then
          echo "BIRD accepted updated routes"
        else
          echo "BIRD rejected updated routes, restoring previous routes" >&2
          cp "$tmp_old" "$ROUTES"
          birdc configure || true
        fi
      else
        echo "Routes prepared before BIRD startup"
      fi
    else
      echo "Route list is empty, keeping old routes"
      rm -f "$tmp_out"
    fi
  else
    echo "Route update failed, keeping old routes" >&2
  fi

  rm -f "$tmp_base" "$tmp_ex" "$tmp_add" "$tmp_out" "$tmp_old" "$tmp_urls" "$tmp_asns" "$tmp_fetch" "$tmp_google" "$tmp_google_cloud"
}

validate_env

mkdir -p /etc/bird/generated
mkdir -p /run/bird
touch "$ROUTES"

render_bird_config
update_routes noapply

bird -f -c "$BIRD_CONFIG" &
BIRD_PID="$!"

sleep 2

while true; do
  sleep "$UPDATE_INTERVAL"
  update_routes
done &

wait "$BIRD_PID"
