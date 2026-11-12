#!/bin/sh
set -eu

/init-config.sh
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/bgp-antifilter.conf
