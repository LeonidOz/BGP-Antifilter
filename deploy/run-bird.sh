#!/bin/sh
set -eu

# shellcheck source=deploy/lib.sh
. /lib.sh
start_log_stream "bird"
write_network_status
print_network_status_warning
exec bird -f -c "$BIRD_CONFIG"
