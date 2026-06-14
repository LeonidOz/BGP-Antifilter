FROM docker:cli

RUN apk add --no-cache python3

COPY bgp_antifilter /bgp_antifilter
COPY scripts/updater-server.py /updater-server.py

RUN chmod +x /updater-server.py

ENTRYPOINT ["python3", "/updater-server.py"]
