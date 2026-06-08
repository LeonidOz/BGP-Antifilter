#!/bin/sh
set -eu

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
INCLUDE_ASNS_FILE="${INCLUDE_ASNS_FILE:-/etc/bird/include-asns.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-/etc/bird/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-/etc/bird/exclude-domains.txt}"
INCLUDE_GOOGLE_RANGES="${INCLUDE_GOOGLE_RANGES:-1}"
CACHE_MAX_AGE="${CACHE_MAX_AGE:-604800}"
ROUTES="${ROUTES_FILE:-/etc/bird/generated/routes.conf}"
CACHE_DIR="${CACHE_DIR:-/etc/bird/generated/cache}"
STATUS_FILE="${STATUS_FILE:-/etc/bird/generated/status.json}"
METRICS_FILE="${METRICS_FILE:-/etc/bird/generated/metrics.prom}"
LOCK_DIR="${UPDATE_LOCK_DIR:-/etc/bird/generated/update.lock}"

mkdir -p /etc/bird/generated "$CACHE_DIR"
touch "$ROUTES"

tmp_old="$(mktemp)"
cp "$ROUTES" "$tmp_old"
lock_acquired=0

cleanup() {
  if [ "$lock_acquired" = "1" ]; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  rm -f "$tmp_old"
}
trap cleanup EXIT

if mkdir "$LOCK_DIR" 2>/dev/null; then
  lock_acquired=1
else
  echo "Another route update is already running: $LOCK_DIR" >&2
  exit 1
fi

export LISTS_FILE INCLUDE_ASNS_FILE INCLUDE_DOMAINS_FILE EXCLUDE_DOMAINS_FILE
export INCLUDE_GOOGLE_RANGES CACHE_DIR CACHE_MAX_AGE STATUS_FILE METRICS_FILE
export ROUTES_FILE="$ROUTES"

if ! /update-routes.py --output "$ROUTES" --status "$STATUS_FILE" --metrics "$METRICS_FILE"; then
  echo "Route updater failed, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  exit 1
fi

if [ ! -s "$ROUTES" ]; then
  echo "Generated route list is empty, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  exit 1
fi

if birdc configure; then
  echo "BIRD accepted updated routes"
else
  echo "BIRD rejected updated routes, restoring previous routes" >&2
  cp "$tmp_old" "$ROUTES"
  birdc configure || true
  exit 1
fi
