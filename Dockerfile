FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends bird2 curl ca-certificates tini python3 \
 && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
COPY generate-routes.py /generate-routes.py
COPY bird.conf.template /etc/bird/bird.conf.template
RUN chmod +x /entrypoint.sh /generate-routes.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD birdc show status >/dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
