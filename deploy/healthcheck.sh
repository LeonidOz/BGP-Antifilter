#!/bin/sh
set -eu

ROUTES="${ROUTES_FILE:-/etc/bird/generated/routes.conf}"
STATUS_FILE="${STATUS_FILE:-/etc/bird/generated/status.json}"
BGP_PROTOCOL="${BGP_PROTOCOL:-mikrotik}"
HEALTHCHECK_REQUIRE_BGP="${HEALTHCHECK_REQUIRE_BGP:-1}"

birdc show status >/dev/null

if [ ! -s "$ROUTES" ]; then
  echo "routes file is empty" >&2
  exit 1
fi

if [ -f "$STATUS_FILE" ]; then
  python3 - "$STATUS_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as file:
    status = json.load(file)

if status.get("routes", {}).get("final", 0) <= 0:
    print("status reports zero routes", file=sys.stderr)
    raise SystemExit(1)
PY
fi

if [ "$HEALTHCHECK_REQUIRE_BGP" = "1" ]; then
  if ! birdc show protocols "$BGP_PROTOCOL" | grep -q Established; then
    echo "BGP protocol $BGP_PROTOCOL is not established" >&2
    exit 1
  fi
fi
