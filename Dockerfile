FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends bird2 curl ca-certificates tini python3 \
 && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
