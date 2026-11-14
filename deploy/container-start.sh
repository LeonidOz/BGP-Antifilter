#!/bin/sh
set -eu

/init-config.sh
exec supervisord -n -c /etc/supervisor/conf.d/bgp-antifilter.conf
