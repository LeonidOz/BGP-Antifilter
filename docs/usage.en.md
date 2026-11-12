# Lists, settings, and maintenance

[Installation](../README.en.md) | [MikroTik](mikrotik.en.md) | [Русский](usage.md)

This guide assumes the prebuilt image installation from the README.
Run commands in the directory containing `compose.yaml` and `.env`.
For Portainer, perform container operations through its interface.

## Editing lists

Open **Lists** in the web panel, edit a list, and click **Save**.
On the dashboard, click **Validate changes**, then **Reload routes**.
The first action checks the result without applying it; the second downloads lists and applies new routes.
Automatic route updates run every 30 minutes.

| What to add | Where | Example |
| --- | --- | --- |
| An IP/subnet list | IP sources, `lists.txt` | URL of a text or JSON list |
| A domain list | Sources in the include-domains tab, `domain-list-urls.txt` | URL of a file with one domain per line |
| A single domain | Include domains, `include-domains.txt` | `example.org` |
| An organization's prefixes by ASN | ASNs, `include-asns.txt` | `AS32934` |
| A country's prefixes | Countries, `include-countries.txt` | Select in the panel; the file stores a code such as `DE` |
| A domain to exclude | Exclude domains, `exclude-domains.txt` | `example.net` |

Use one value per line in text lists. Blank lines and lines starting with `#` are ignored.
URL sources may include a name: `Name | https://example.org/list.txt`.

Use plain domain names without `https://`, paths, or `*.`.
Downloaded domain lists must also contain plain names; Adblock and hosts formats are not supported.
The application adds resolved IPv4 addresses; it does not discover every subdomain of a site.
Use **Tools** to check a specific IP or domain.

Default lists are created on first startup.
Save your changes through the panel; they are retained when updating the application.
Google service ranges, excluding Google Cloud ranges, are also enabled by default.

### When a source is unavailable

The application uses cached data up to 7 days old. Without a usable cache:

- An unavailable IP list or domain list is skipped; other data can still produce an update.
- An unresolved include domain is skipped.
- An unresolved exclude domain stops the update to avoid reintroducing its address.
- With `REQUIRE_ALL_URL_SOURCES=1`, an unavailable URL list also stops the update.

If new routes cannot be prepared or applied, the previous working set stays active.
On first startup, no previous set exists; source and DNS access are required.

## Settings

Set initial BGP addresses and the password in `.env` or Portainer variables.
After editing `.env`, run `docker compose up -d`; a plain `restart`
does not reload Docker environment values.

Other options are easier to change under **Settings** in the web panel:

| Setting | Default | Purpose |
| --- | --- | --- |
| `UPDATE_INTERVAL` | `1800` | Update interval in seconds |
| `CACHE_MAX_AGE` | `604800` | Maximum cache age in seconds: 7 days |
| `REQUIRE_ALL_URL_SOURCES` | `0` | Set to `1` to require every URL source or its fresh cache |
| `DNS_RESOLVERS` | System DNS | Custom IPv4 DNS servers, separated by spaces or commas |
| `DNS_RESOLVE_TIMEOUT` | `3` | DNS timeout in seconds |
| `FETCH_TIMEOUT` | `30` | Source download timeout in seconds |
| `FETCH_ATTEMPTS` | `5` | Source download attempts |
| `FETCH_RETRY_DELAY` | `5` | Delay between attempts in seconds |
| `MIN_PREFIX_LENGTH` | `8` | Guard against overly broad routes |
| `ALLOW_BROAD_ROUTES` | `0` | Keep the guard enabled |

Save settings and click **Apply now**.
BGP options marked “restart” require a container restart;
for the README installation, use `docker compose restart`.
Values saved in the panel take priority over matching environment values:
continue editing a setting in the panel once you have changed it there.

Additional `.env` options:

| Setting | Default | When to change |
| --- | --- | --- |
| `ADMIN_PORT` | `8080` | The panel port is already in use |
| `HEALTHCHECK_REQUIRE_BGP` | `1` | Set to `0` when using only Address List export |
| `HEALTHCHECK_FAIL_ON_DEGRADED` | `0` | Set to `1` to mark Docker unhealthy after a failed update |
| `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` | No proxy | Source downloads require a proxy |

List local addresses explicitly in `NO_PROXY`.
Custom `DNS_RESOLVERS` enable direct source downloads using custom DNS resolution,
bypassing HTTP proxies.

## Updating the application

Route lists update automatically. Install new application versions separately.

For the README installation:

1. Back up your data as described below.
2. Change `BGP_ANTIFILTER_VERSION` in `.env` to the desired version.
3. Run:

```bash
docker compose pull
docker compose up -d
docker compose ps
```

Lists and settings are retained in `bgp-antifilter-config`,
while routes and cache remain in `bgp-antifilter-data`.
To return to the previous image, select its version and repeat these commands.
In Portainer, change `BGP_ANTIFILTER_IMAGE` and update the stack with image re-pulling.
Panel-based application updates are disabled for this stack.

Use a version tag or `latest`, the latest stable release, for a normal installation.
`edge` and `sha-<commit>` are for testing changes.

### Data locations

This table describes the storage layout starting with [0.5.2](../CHANGELOG.md#052---2026-11-13).
For older installations, see [moving to separate config storage](#moving-to-separate-config-storage).

| Container path | Contents | Prebuilt image / source installation |
| --- | --- | --- |
| `/etc/bird/config` | User lists, `settings.json`, `settings.env`, `list-backups/` and the migration marker | `bgp-antifilter-config` volume / `config/` directory |
| `/etc/bird/generated` | Routes, the last working snapshot, cache, update state, metrics and logs | `bgp-antifilter-data` volume / `generated/` directory |

`settings.json` stores panel settings; `settings.env` passes them to runtime scripts.
Back up and restore both files together. Manual editing is usually unnecessary.
The server's `.env` and Compose file live outside the volumes and are also required for recovery.
Override volume names with `BGP_CONFIG_VOLUME` and `BGP_DATA_VOLUME`.

### Backups

Run from the installation directory. Use a new backup directory for each copy:

```bash
docker compose stop
mkdir -p backup
docker compose cp bgp-antifilter:/etc/bird/config ./backup/config
docker compose cp bgp-antifilter:/etc/bird/generated ./backup/generated
cp .env compose.yaml ./backup/
docker compose start
```

Keep the entire `backup` directory, including the hidden `.env` file.
Moving an installation requires connection settings and both volumes: `bgp-antifilter-config`
for user lists/settings and `bgp-antifilter-data` for routes and cache.
For source installations, these are the `config/` and `generated/` directories respectively.

Use `docker compose down` to stop the application.
**Do not add `-v` if you want to keep your data:** it deletes the stack's volumes.

To restore a README installation, put the saved `.env` and `compose.yaml` back in
the installation directory. Create the container and volumes, copy data into the
stopped container, then start the application:

```bash
docker compose pull
docker compose create
docker compose stop
docker compose cp ./backup/config/. bgp-antifilter:/etc/bird/config
docker compose cp ./backup/generated/. bgp-antifilter:/etc/bird/generated
docker compose start
docker compose ps
```

Restore into empty volumes or back up their current contents first:
`docker compose cp` replaces matching files but does not remove extra files.
Copy complete directories, including `.migration-v1.json`, then check settings and routes in the panel.

### Moving to separate config storage

Automatic migration is available starting with [0.5.2](../CHANGELOG.md#052---2026-11-13).
The `0.5.1` image does not include it: use an image tagged `0.5.2` or newer
and the two-volume Compose file as described below.

Before upgrading an older installation, stop it and copy `/etc/bird/generated` from
the container into a separate backup directory. Also retain `.env` and the Compose
file or exported Portainer stack. Upgrade to an image supporting migration and update
the YAML to mount both `/etc/bird/config` and `/etc/bird/generated`.
For Portainer, use the [updated stack](../deploy/portainer-stack.yml).
Keep the existing `BGP_DATA_VOLUME` name. The new configuration volume is selected
with `BGP_CONFIG_VOLUME`, defaulting to `bgp-antifilter-config`.
For source installations, retain `generated/`; the new Compose creates `config/` alongside it.

On first startup, before loading settings or defaults, the application copies:

- lists and additional files from the old `generated/config/`;
- `generated/settings.json` and `generated/settings.env`;
- backups from `generated/list-backups/`.

Existing destination files, including empty lists, take priority. Originals remain
untouched; route snapshots and cache keep their paths. A `.migration-v1.json` marker
records completion. Keep it when resetting settings to avoid importing old values again.
Verify lists/settings in the panel, then startup, route updates and backups.

To roll back the image, retain the new YAML and both volumes. Previous images that
support `LISTS_FILE`, `SETTINGS_FILE` and `SETTINGS_ENV_FILE` honor those new paths.
Restoring the old YAML selects the old config copies, without edits made after migration.
Updating only the image with an old YAML continues to honor explicit legacy paths;
separate storage takes effect when the stack itself is updated.

Custom `file://` sources retain the paths recorded in your lists.
If a source lives in `generated/`, move it to `/etc/bird/config` and update its URL
in the panel before clearing that directory. Removing caches and working route
snapshots makes the next startup depend on the required sources and DNS again.

## Troubleshooting

Start with source status and logs in the web panel.
If the panel is unavailable:

```bash
docker compose ps
docker compose logs --tail=100
```

| Problem | What to check |
| --- | --- |
| Panel does not open | Has the first download finished? Check server address, `ADMIN_PORT`, password, and firewall access |
| `BIRD_IP is not assigned` | `BIRD_IP` must be assigned to the Linux server; check `ip -4 addr` |
| BGP does not connect | Compare addresses and AS numbers with MikroTik; check TCP 179 between the server and router |
| Container is `unhealthy` | Check route generation and BGP state; for Address List use `HEALTHCHECK_REQUIRE_BGP=0` |
| New routes were not applied | Inspect URL/DNS errors, exclude domains, and the last operation's details |
| Routes exist but a site is unavailable | Check whether the IP is listed, the MikroTik VPN gateway, VPN connectivity, NAT, and FastTrack rules |

Additional checks:

```bash
docker compose exec bgp-antifilter birdc show protocols
docker compose exec bgp-antifilter /check-ip.py 1.2.3.4
docker compose exec bgp-antifilter /update-routes.py --check-sources
docker compose exec bgp-antifilter /update-routes.py --dry-run
docker compose exec bgp-antifilter /reload-routes.sh
```

The last command applies routes; the others inspect status and data.
`--dry-run` may refresh source caches but does not apply routes.

Diagnostic files are in `/etc/bird/generated` inside the container:
`status.json` holds source and update results, `runtime.json` tracks progress,
`network-status.json` lists server addresses, and `metrics.prom` contains metrics.
`routes.last-good.conf` retains the confirmed route set until a new set is successfully applied.
