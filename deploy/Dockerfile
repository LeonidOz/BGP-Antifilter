FROM debian:bookworm-slim

# Keep python -m runtime commands available for docker exec with a custom cwd.
ENV PYTHONPATH=/

LABEL org.opencontainers.image.title="BGP Antifilter" \
      org.opencontainers.image.source="https://github.com/LeonidOz/BGP-Antifilter" \
      org.opencontainers.image.url="https://github.com/LeonidOz/BGP-Antifilter" \
      org.opencontainers.image.documentation="https://github.com/LeonidOz/BGP-Antifilter"

RUN apt-get update \
 && apt-get install -y --no-install-recommends bird2 curl ca-certificates python3 docker.io docker-compose supervisor \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/log/supervisor /run/bgp-antifilter

COPY deploy/container-start.sh /container-start.sh
COPY deploy/entrypoint.sh /entrypoint.sh
COPY deploy/init-config.sh /init-config.sh
COPY deploy/lib.sh /lib.sh
COPY deploy/run-admin.sh /run-admin.sh
COPY deploy/run-bird.sh /run-bird.sh
COPY deploy/run-scheduler.sh /run-scheduler.sh
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
COPY deploy/supervisord.conf /etc/supervisor/conf.d/bgp-antifilter.conf
COPY deploy/bird.conf.template /etc/bird/bird.conf.template
RUN chmod +x /container-start.sh /entrypoint.sh /init-config.sh /lib.sh /run-admin.sh /run-bird.sh /run-scheduler.sh /generate-routes.py /update-routes.py /check-ip.py /admin-server.py /healthcheck.sh /reload-routes.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD /healthcheck.sh

ENTRYPOINT ["/container-start.sh"]
