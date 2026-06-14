FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="BGP Antifilter" \
      org.opencontainers.image.source="https://github.com/LeonidOz/BGP-Antifilter" \
      org.opencontainers.image.url="https://github.com/LeonidOz/BGP-Antifilter" \
      org.opencontainers.image.documentation="https://github.com/LeonidOz/BGP-Antifilter"

RUN apt-get update \
 && apt-get install -y --no-install-recommends bird2 curl ca-certificates tini python3 docker.io docker-compose \
 && rm -rf /var/lib/apt/lists/*

COPY deploy/entrypoint.sh /entrypoint.sh
COPY VERSION /VERSION
COPY bgp_antifilter /bgp_antifilter
COPY admin-ui /admin-ui
COPY default-lists /defaults-config
COPY scripts/generate-routes.py /generate-routes.py
COPY scripts/update-routes.py /update-routes.py
COPY scripts/check-ip.py /check-ip.py
COPY scripts/admin-server.py /admin-server.py
COPY deploy/healthcheck.sh /healthcheck.sh
COPY deploy/reload-routes.sh /reload-routes.sh
COPY deploy/bird.conf.template /etc/bird/bird.conf.template
RUN chmod +x /entrypoint.sh /generate-routes.py /update-routes.py /check-ip.py /admin-server.py /healthcheck.sh /reload-routes.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD /healthcheck.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
