#!/bin/sh
set -eu
CONFIG_DIR="${CONFIG_DIR:-/etc/bird/config}"
SETTINGS_ENV_FILE="${SETTINGS_ENV_FILE:-$CONFIG_DIR/settings.env}"
if [ -f "$SETTINGS_ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$SETTINGS_ENV_FILE"
  set +a
fi
exec python3 -m bgp_antifilter.route_transaction apply "$@"
