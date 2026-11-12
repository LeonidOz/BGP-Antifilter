#!/bin/sh
set -eu

. /lib.sh
start_log_stream "scheduler"
load_settings_env
export_runtime_env
export RUNTIME_PRESERVE_STATE=1

if [ -f "$STARTUP_REFRESH_FLAG" ]; then
  echo "startup refresh requested"
  sleep 2
  if update_routes apply startup; then
    echo "startup refresh completed"
  else
    echo "startup refresh failed; scheduler will continue" >&2
  fi
  rm -f "$STARTUP_REFRESH_FLAG"
fi

while true; do
  load_settings_env
  now="$(date +%s)"
  current_interval="$UPDATE_INTERVAL"
  next_update=$((now + current_interval))
  runtime_next_update="$(runtime_next_update_unix)"
  if [ -n "$runtime_next_update" ] && [ "$runtime_next_update" -gt "$next_update" ]; then
    next_update="$runtime_next_update"
  fi
  write_runtime "$next_update"

  while true; do
    load_settings_env
    now="$(date +%s)"
    if [ "$UPDATE_INTERVAL" != "$current_interval" ]; then
      current_interval="$UPDATE_INTERVAL"
      next_update=$((now + current_interval))
      write_runtime "$next_update"
    fi
    runtime_next_update="$(runtime_next_update_unix)"
    if [ -n "$runtime_next_update" ] && [ "$runtime_next_update" -gt "$next_update" ]; then
      next_update="$runtime_next_update"
    fi
    remaining=$((next_update - now))
    if [ "$remaining" -le 0 ]; then
      break
    fi
    if [ "$remaining" -gt 10 ]; then
      sleep 10
    else
      sleep "$remaining"
    fi
  done

  if ! update_routes apply scheduled; then
    echo "Scheduled route update failed; keeping scheduler alive for the next interval" >&2
  fi
done
