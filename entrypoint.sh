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
CACHE_DIR="${CACHE_DIR:-/etc/bird/generated/cache}"

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

cache_path() {
  cache_namespace="$1"
  cache_value="$2"
  cache_key="$(printf '%s' "$cache_value" | cksum | awk '{print $1}')"

  printf '%s/%s-%s.cache\n' "$CACHE_DIR" "$cache_namespace" "$cache_key"
}

append_fetch_with_cache() {
  url="$1"
  cache_file="$2"
  output_file="$3"
  tmp_file="$4"

  if curl -4 --retry 5 --retry-delay 5 -fsSL "$url" -o "$tmp_file"; then
    cp "$tmp_file" "$cache_file"
    tr -d '\r' < "$tmp_file" >> "$output_file"
    printf '\n' >> "$output_file"
    echo "Updated cache for $url" >&2
    return 0
  fi

  if [ -s "$cache_file" ]; then
    echo "Failed to fetch $url, using cache $cache_file" >&2
    tr -d '\r' < "$cache_file" >> "$output_file"
    printf '\n' >> "$output_file"
    return 0
  fi

  echo "Failed to fetch $url and no cache is available" >&2
  return 1
}

resolve_domain_with_cache() {
  domain="$1"
  cache_namespace="$2"
  output_file="$3"
  tmp_file="$4"
  cache_file="$(cache_path "$cache_namespace" "$domain")"

  if getent ahostsv4 "$domain" > "$tmp_file" && [ -s "$tmp_file" ]; then
    awk '{print $1 "/32"}' "$tmp_file" | sort -u > "$cache_file"
    cat "$cache_file" >> "$output_file"
    echo "Updated DNS cache for $domain" >&2
    return 0
  fi

  if [ -s "$cache_file" ]; then
    echo "Failed to resolve $domain, using DNS cache $cache_file" >&2
    cat "$cache_file" >> "$output_file"
    return 0
  fi

  echo "Failed to resolve $domain and no DNS cache is available" >&2
  return 1
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
  source_failed=0

  echo "Updating routes from $LISTS_FILE"

  read_non_comment_lines "$LISTS_FILE" "$tmp_urls"

  if [ ! -s "$tmp_urls" ]; then
    echo "No URL route sources configured" >&2
  fi

  : > "$tmp_base"

  while IFS= read -r url; do
      echo "Fetching $url" >&2
      if ! append_fetch_with_cache "$url" "$(cache_path url "$url")" "$tmp_base" "$tmp_fetch"; then
        source_failed=1
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
    asn_url="https://api.routeviews.org/asn/$asn_number"
    if ! append_fetch_with_cache "$asn_url" "$(cache_path asn "$asn_number")" "$tmp_base" "$tmp_fetch"; then
      source_failed=1
    fi
  done < "$tmp_asns"

  if [ "$INCLUDE_GOOGLE_RANGES" = "1" ]; then
    echo "Fetching Google default service ranges" >&2
    google_cache="$(cache_path google goog.json)"
    google_cloud_cache="$(cache_path google cloud.json)"

    if curl -4 --retry 5 --retry-delay 5 -fsSL "https://www.gstatic.com/ipranges/goog.json" -o "$tmp_google"; then
      cp "$tmp_google" "$google_cache"
      echo "Updated cache for Google goog.json" >&2
    elif [ -s "$google_cache" ]; then
      echo "Failed to fetch Google goog.json, using cache $google_cache" >&2
      cp "$google_cache" "$tmp_google"
    else
      echo "Failed to fetch Google goog.json and no cache is available" >&2
      source_failed=1
    fi

    if curl -4 --retry 5 --retry-delay 5 -fsSL "https://www.gstatic.com/ipranges/cloud.json" -o "$tmp_google_cloud"; then
      cp "$tmp_google_cloud" "$google_cloud_cache"
      echo "Updated cache for Google cloud.json" >&2
    elif [ -s "$google_cloud_cache" ]; then
      echo "Failed to fetch Google cloud.json, using cache $google_cloud_cache" >&2
      cp "$google_cloud_cache" "$tmp_google_cloud"
    else
      echo "Failed to fetch Google cloud.json and no cache is available" >&2
      source_failed=1
    fi

    if [ -s "$tmp_google" ] && [ -s "$tmp_google_cloud" ]; then
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
        source_failed=1
      fi
    fi
  fi

  : > "$tmp_ex"
  : > "$tmp_add"

  read_non_comment_lines "$EXCLUDE_DOMAINS_FILE" "$tmp_urls"

  while IFS= read -r domain; do
    echo "Resolving exclude domain $domain" >&2
    if ! resolve_domain_with_cache "$domain" exclude-domain "$tmp_ex" "$tmp_fetch"; then
      source_failed=1
    fi
  done < "$tmp_urls"

  read_non_comment_lines "$INCLUDE_DOMAINS_FILE" "$tmp_urls"

  while IFS= read -r domain; do
    echo "Resolving include domain $domain" >&2
    if ! resolve_domain_with_cache "$domain" include-domain "$tmp_add" "$tmp_fetch"; then
      source_failed=1
    fi
  done < "$tmp_urls"

  if [ "$source_failed" -eq 0 ]; then
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
    echo "Route update failed because at least one source has no fresh data or cache, keeping old routes" >&2
  fi

  rm -f "$tmp_base" "$tmp_ex" "$tmp_add" "$tmp_out" "$tmp_old" "$tmp_urls" "$tmp_asns" "$tmp_fetch" "$tmp_google" "$tmp_google_cloud"
}

validate_env

mkdir -p /etc/bird/generated
mkdir -p "$CACHE_DIR"
mkdir -p /run/bird
touch "$ROUTES"

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
