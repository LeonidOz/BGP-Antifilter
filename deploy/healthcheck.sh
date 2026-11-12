#!/bin/sh
set -eu

ROUTES="${ROUTES_FILE:-/etc/bird/generated/routes.conf}"
STATUS_FILE="${STATUS_FILE:-/etc/bird/generated/status.json}"
NETWORK_STATUS_FILE="${NETWORK_STATUS_FILE:-/etc/bird/generated/network-status.json}"
BGP_PROTOCOL="${BGP_PROTOCOL:-mikrotik}"
HEALTHCHECK_REQUIRE_BGP="${HEALTHCHECK_REQUIRE_BGP:-1}"
HEALTHCHECK_FAIL_ON_DEGRADED="${HEALTHCHECK_FAIL_ON_DEGRADED:-0}"

if [ "${ADMIN_ENABLED:-0}" = "1" ]; then
  curl -fsS "http://127.0.0.1:${ADMIN_PORT:-8080}/api/session" >/dev/null
fi

birdc show status >/dev/null

if [ ! -s "$ROUTES" ]; then
  echo "routes file is empty" >&2
  exit 1
fi

if [ -f "$STATUS_FILE" ]; then
  python3 -m bgp_antifilter.container_runtime check-health status "$STATUS_FILE"
fi

if [ "$HEALTHCHECK_FAIL_ON_DEGRADED" = "1" ] && [ -f "${RUNTIME_FILE:-/etc/bird/generated/runtime.json}" ]; then
  python3 -m bgp_antifilter.container_runtime check-health runtime "${RUNTIME_FILE:-/etc/bird/generated/runtime.json}"
fi

if [ "$HEALTHCHECK_REQUIRE_BGP" = "1" ]; then
  if [ -f "$NETWORK_STATUS_FILE" ]; then
    python3 -m bgp_antifilter.container_runtime check-health network "$NETWORK_STATUS_FILE"
  fi
  if ! birdc show protocols "$BGP_PROTOCOL" | grep -q Established; then
    echo "BGP protocol $BGP_PROTOCOL is not established" >&2
    exit 1
  fi
fi
