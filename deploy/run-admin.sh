#!/bin/sh
set -eu

# shellcheck source=deploy/lib.sh
. /lib.sh
start_log_stream "admin"

if [ "${ADMIN_ENABLED:-0}" != "1" ]; then
  echo "admin server disabled; idling"
  exec tail -f /dev/null
fi

exec python3 /admin-server.py
