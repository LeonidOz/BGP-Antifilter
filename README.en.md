# BGP Antifilter
![Python](https://img.shields.io/badge/python-3.x-blue)
![Debian](https://img.shields.io/badge/debian-bookworm-a81d33)
![BIRD](https://img.shields.io/badge/BIRD-2.x-green)
![RouterOS](https://img.shields.io/badge/RouterOS-7-blue)
![IPv4](https://img.shields.io/badge/IP-IPv4-blueviolet)

English | [Русский](README.md)

BGP Antifilter is a containerized BIRD 2 configuration for announcing blocked IPv4 routes and prefixes to MikroTik via BGP.

The project downloads route lists from public sources, enriches them with IPv4 addresses resolved from manually configured domains, removes routes for excluded domains, and generates BIRD `blackhole` static routes.

## Project Contents

- `Dockerfile` - Debian-based image with BIRD 2, curl, tini, and Python.
- `docker-compose.yml` - runs BIRD in host network mode.
- `bird.conf.template` - BIRD configuration template rendered from environment variables.
- `.env.example` - example AS, IP, update interval, cache, and healthcheck settings.
- `entrypoint.sh` - renders BIRD config, starts BIRD, and periodically refreshes routes.
- `generate-routes.py` - route generator and validator.
- `update-routes.py` - source refresh, caching, status, and metrics.
- `healthcheck.sh` - checks BIRD, route availability, and optionally the BGP session.
- `lists.txt` - source URLs for IP/CIDR lists.
- `include-asns.txt` - ASNs whose announced IPv4 prefixes should be added.
- `include-domains.txt` - domains whose IPv4 addresses should be added.
- `exclude-domains.txt` - domains whose IPv4 addresses should be excluded.
- `generated/` - generated route cache, not stored in git.

## How It Works

1. The container renders `/etc/bird/bird.conf` from `bird.conf.template`.
2. BIRD starts with the rendered configuration.
3. `entrypoint.sh` calls `update-routes.py`.
4. URLs from `lists.txt` are fetched and cached.
5. ASNs from `include-asns.txt` are loaded from the RouteViews API.
6. If `INCLUDE_GOOGLE_RANGES=1`, Google `goog.json` and `cloud.json` are fetched; Cloud prefixes are subtracted from the general Google list.
7. `generate-routes.py` extracts and validates IPv4/CIDR routes from text or JSON sources.
8. Domains from `include-domains.txt` are resolved to IPv4 and added as `/32`.
9. Domains from `exclude-domains.txt` are resolved to IPv4 and subtracted from the final route set.
10. `generated/routes.conf` is included by BIRD as static `blackhole` routes.
11. BIRD exports the routes to MikroTik via BGP.

## Configuration

Copy the example environment file and adjust it for your network:

```bash
cp .env.example .env
```

Main settings:

```dotenv
MY_AS=64500
MT_AS=65455
MT_IP=192.168.55.1
BIRD_IP=192.168.55.5
ROUTER_ID=192.168.55.5
BGP_COMMUNITY=65432,500
UPDATE_INTERVAL=1800
CACHE_MAX_AGE=604800
INCLUDE_GOOGLE_RANGES=1
HEALTHCHECK_REQUIRE_BGP=1
BGP_PROTOCOL=mikrotik
```

- `MY_AS` - AS number used by the BIRD container.
- `MT_AS` - MikroTik AS number.
- `MT_IP` - MikroTik IP address.
- `BIRD_IP` - host/interface IP used by BIRD for the BGP session.
- `ROUTER_ID` - BIRD router ID, usually the same as `BIRD_IP`.
- `BGP_COMMUNITY` - community added to exported routes.
- `UPDATE_INTERVAL` - route refresh interval in seconds.
- `CACHE_MAX_AGE` - maximum source cache age in seconds; defaults to 7 days.
- `INCLUDE_GOOGLE_RANGES` - `1` adds default Google service ranges from `goog.json` excluding Google Cloud from `cloud.json`; `0` disables this source.
- `HEALTHCHECK_REQUIRE_BGP` - `1` requires an established BGP session in Docker healthcheck; `0` checks only BIRD and routes.
- `BGP_PROTOCOL` - BIRD BGP protocol name used by healthcheck; defaults to `mikrotik`.

If `.env` is missing, defaults from `docker-compose.yml` are used.

At startup, the container validates environment values before starting BIRD:

- `MY_AS` and `MT_AS` must be integer AS numbers.
- `MT_IP`, `BIRD_IP`, and `ROUTER_ID` must be valid IPv4 addresses.
- `BGP_COMMUNITY` must use the `AS,VALUE` tuple format, for example `65432,500`.
- `UPDATE_INTERVAL` must be a positive number of seconds.
- `CACHE_MAX_AGE` must be a positive number of seconds.

## Running

```bash
docker compose up -d --build
```

Show logs:

```bash
docker compose logs -f bird
```

Check container status:

```bash
docker compose ps
```

Stop:

```bash
docker compose down
```

## Managing Lists

Add new IP/CIDR sources to `lists.txt`, one URL per line.

Sources may be plain text or JSON. The generator extracts IPv4/CIDR values from source content, so URLs such as `format=json&data=cidr4` are supported. Example:

```text
https://iplist.opencck.org/?format=json&data=cidr4&site=claude.ai&site=chatgpt.com&site=copilot&site=deepseek.com&site=grok.com
```

If you have multiple lists, add each URL as a separate line in `lists.txt`.

ASNs whose announced IPv4 prefixes should be force-added go into `include-asns.txt`. For example, `AS32934` adds Meta routes for Facebook, Instagram, WhatsApp, and Messenger.

For YouTube, a dedicated Google ranges source is enabled: with `INCLUDE_GOOGLE_RANGES=1`, the container uses `https://www.gstatic.com/ipranges/goog.json`, subtracts `https://www.gstatic.com/ipranges/cloud.json`, and adds the remaining IPv4 prefixes. YouTube domains in `include-domains.txt` remain an additional point source.

Domains to force-add go into `include-domains.txt`. These domains are best-effort: if a domain temporarily does not resolve and has no cache, it is marked as `skipped`, but route updates continue.

Domains to exclude go into `exclude-domains.txt`. These domains are strict: if an exclude domain cannot be resolved and has no fresh cache, the new `routes.conf` is not applied. If an excluded IP is inside a larger prefix, the generator splits the prefix into smaller routes without that IP.

Before writing the final file, the generator removes exact duplicates, drops routes already covered by larger prefixes, and collapses adjacent networks when doing so does not reintroduce excluded addresses.

Blank lines and lines starting with `#` are ignored.

## Verification And Rollback

Before applying a new `generated/routes.conf`, the container keeps a copy of the previous file. Every network source has a separate cache in `generated/cache`: URLs from `lists.txt`, ASN prefixes, Google ranges, and DNS results for include/exclude domains. If a source is temporarily unavailable, the generator uses its last cache and continues updating other sources.

Cache is used only while it is younger than `CACHE_MAX_AGE`; the default is 604800 seconds, or 7 days. If an unavailable source has no fresh cache, the final route file is not updated and the old `routes.conf` stays in place. If `birdc configure` rejects the new configuration, `entrypoint.sh` restores the previous route file and asks BIRD to apply the working version again.

On startup, the container prepares routes before starting BIRD. This reduces the chance of briefly advertising an empty table after restart.

After each update attempt, diagnostic files are written:

- `generated/status.json` - update result, route counts, per-source status (`fresh`, `cache`, `skipped`, `failed`, `disabled`), and errors.
- `generated/metrics.prom` - Prometheus text format metrics: route count, update success, last attempt time, and source status summary.

Docker healthcheck checks `birdc show status`, non-empty `generated/routes.conf`, non-zero route count in `status.json`, and, if `HEALTHCHECK_REQUIRE_BGP=1`, the BGP protocol state from `BGP_PROTOCOL`.

Check BIRD status inside the container:

```bash
docker compose exec bird birdc show status
```

Show the number of exported static routes:

```bash
docker compose exec bird birdc show route protocol static_antifilter count
```

Run local tests without Docker:

```bash
python -m unittest discover -s tests
```

## MikroTik Example

Minimal RouterOS 7 example:

```routeros
/routing bgp template
add name=antifilter-template as=65455 routing-table=main

/routing bgp connection
add name=antifilter-bird \
    template=antifilter-template \
    remote.address=192.168.55.5 \
    remote.as=64500 \
    local.address=192.168.55.1 \
    multihop=yes \
    input.filter=antifilter-in

/routing filter rule
add chain=antifilter-in rule="if (bgp-communities includes 65432:500) { accept } else { reject }"
```

AS and IP parameters must match the values in `.env`.
