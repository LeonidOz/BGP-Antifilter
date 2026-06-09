FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends bird2 curl ca-certificates tini python3 \
 && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
COPY VERSION /VERSION
COPY bgp_antifilter /bgp_antifilter
COPY generate-routes.py /generate-routes.py
COPY update-routes.py /update-routes.py
COPY check-ip.py /check-ip.py
COPY healthcheck.sh /healthcheck.sh
COPY reload-routes.sh /reload-routes.sh
COPY bird.conf.template /etc/bird/bird.conf.template
RUN chmod +x /entrypoint.sh /generate-routes.py /update-routes.py /check-ip.py /healthcheck.sh /reload-routes.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD /healthcheck.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
