FROM docker:29.9.3-cli@sha256:5a7af0dcb0e46c803efe9b45371dd21cb500e5b4453250394ac6f06d49b6e6f1 AS docker-client

FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS curl-builder
ARG CURL_VERSION=8.23.0
ARG CURL_SHA256=8dadd7d2536a314f982ad05a651b713f426bf7d02cc2c76cffb9796f2218e6c5
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libssl-dev zlib1g-dev libnghttp2-dev libbrotli-dev libzstd-dev libpsl-dev \
 && python -c "import urllib.request; urllib.request.urlretrieve('https://curl.se/download/curl-${CURL_VERSION}.tar.xz', '/tmp/curl.tar.xz')" \
 && echo "${CURL_SHA256}  /tmp/curl.tar.xz" | sha256sum -c - \
 && mkdir /tmp/curl-source \
 && tar -xJf /tmp/curl.tar.xz --strip-components=1 -C /tmp/curl-source \
 && cd /tmp/curl-source \
 && ./configure --with-openssl --with-nghttp2 --with-brotli --with-zstd --with-libpsl --disable-static --disable-ldap --disable-ldaps \
 && make -j2 \
 && make install

FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

# Keep python -m runtime commands available for docker exec with a custom cwd.
ENV PYTHONPATH=/

LABEL org.opencontainers.image.title="BGP Antifilter" \
      org.opencontainers.image.source="https://github.com/LeonidOz/BGP-Antifilter" \
      org.opencontainers.image.url="https://github.com/LeonidOz/BGP-Antifilter" \
      org.opencontainers.image.documentation="https://github.com/LeonidOz/BGP-Antifilter"

ARG BIRD_VERSION=3.4.0-cznic.1~trixie
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates libnghttp2-14 libbrotli1 libzstd1 libpsl5t64 \
 && python -c "import urllib.request; urllib.request.urlretrieve('https://pkg.labs.nic.cz/gpg', '/usr/share/keyrings/cznic-labs-pkg.gpg')" \
 && echo 'deb [signed-by=/usr/share/keyrings/cznic-labs-pkg.gpg] https://pkg.labs.nic.cz/bird3 trixie main' > /etc/apt/sources.list.d/bird3.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends "bird3=${BIRD_VERSION}" \
 && rm -rf /var/lib/apt/lists/*

COPY --from=curl-builder /usr/local/bin/curl /usr/local/bin/curl
COPY --from=curl-builder /usr/local/lib/libcurl.so.4.* /usr/local/lib/
RUN ldconfig
COPY deploy/requirements-runtime.txt deploy/requirements-dns.txt /tmp/
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements-runtime.txt \
 && rm /tmp/requirements-runtime.txt /tmp/requirements-dns.txt

RUN mkdir -p /var/log/supervisor /run/bgp-antifilter

# Ship the CLI and its matching Compose plugin for web updates.
COPY --from=docker-client /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-client /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

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
