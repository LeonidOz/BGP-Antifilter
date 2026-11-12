# Running from source

[Install the prebuilt application](../README.en.md) | [Русский](development.md)

Use this method to modify code or test locally.
For a normal installation, use the prebuilt Docker image from the README.

## Linux

```bash
git clone https://github.com/LeonidOz/BGP-Antifilter.git
cd BGP-Antifilter
cp .env.example .env
```

Set the server and MikroTik addresses in `.env`. For the web panel, set
`ADMIN_ENABLED=1` and your own `ADMIN_PASSWORD`.
Leave `BGP_ANTIFILTER_VERSION` unset for a local build.

```bash
docker compose up -d --build
docker compose logs -f --tail=50
```

The root `docker-compose.yml` builds the local `bgp-antifilter:dev` image.
Source installations keep user lists, settings and their backups in `config/`,
and routes, cache and runtime state in `generated/`.
The first startup copies configuration from the old layout automatically;
see [storage migration](usage.en.md#moving-to-separate-config-storage).
Unlike the prebuilt image stack, this setup mounts the repository and Docker socket.

## Windows and macOS

Use Docker Desktop to test the generator and panel:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

The panel opens at **http://localhost:8080** when enabled in `.env`.
Set `HEALTHCHECK_REQUIRE_BGP=0` to test without BGP.
This mode uses bridge networking; follow the Linux installation for a working BGP session.

## Code structure

| Path | Responsibility |
| --- | --- |
| `scripts/` | CLI entry points calling the Python package and the version update script |
| `bgp_antifilter/update_routes.py` | CLI arguments and route update orchestration |
| `bgp_antifilter/sources/` | Downloads, cache, DNS and URL, ASN, country and domain sources |
| `bgp_antifilter/route_builder.py`, `route_output.py` | Route construction and validation; route, status and metrics output |
| `bgp_antifilter/state_store.py`, `runtime_state.py` | Atomic JSON state operations and generation state transitions |
| `bgp_antifilter/container_runtime.py` | Environment validation, BIRD template rendering, startup diagnostics and healthchecks |
| `bgp_antifilter/config_migration.py`, `runtime_paths.py` | Configuration migration and shared path definitions |
| `bgp_antifilter/admin/server.py` | HTTP routing, authentication boundaries and response serialization |
| `bgp_antifilter/admin/` | Settings, lists, sessions, diagnostics, status and action services; application assembly in `application.py` |
| `bgp_antifilter/updater_server.py` | Compose-based application image updates and rollback |
| `admin-ui/app.js`, `admin-ui/modules/` | Web panel initialization and feature ES modules |
| `deploy/` | Image, Portainer stack, process startup, scheduler and shell wrappers |
| `tests/`, `tests/js/` | Python and JavaScript tests; Docker scenarios are enabled separately |

`bgp_antifilter/admin_server.py` retains the existing HTTP server entry point.
Change admin business logic in services and HTTP status codes/routes in `admin/server.py`.
Shared list parsing and route construction live outside the HTTP layer.

Use `state_store` operations for runtime JSON: they lock the entire read, modify and
atomic publish transaction. Sidecar `*.lock` files remain in place; do not remove
them while processes are running. Source caches and user lists have their own
storage formats and are separate from runtime JSON.

Configure user paths with `CONFIG_DIR`, `SETTINGS_FILE`, `SETTINGS_ENV_FILE`,
`LIST_BACKUP_DIR` and individual list variables such as `LISTS_FILE`.
Explicit paths take priority, including legacy YAML paths.
Inside the image, `PYTHONPATH=/` makes the package available from any working directory.

The panel loads ES modules directly from `admin-ui/`, without a bundler or npm package installation.
Open it through the application's HTTP server rather than `file://`.
Keep imports explicit and avoid circular dependencies when adding modules.

## Checks

Python 3.11 from the Debian image works for Python checks; use Node.js 22 for JavaScript, matching CI.
From the repository root:

```bash
python -m unittest discover -s tests
node --test tests/js/admin-modules.test.mjs
docker compose --env-file .env.example config --quiet
shellcheck -x deploy/*.sh
```

On Windows, use `py -3` in place of `python` if needed.
Run ShellCheck and POSIX shell checks in Linux or a suitable container;
platform-dependent tests are reported as skipped.

To test migration on temporary Docker volumes, build the current image first:

```bash
docker compose --env-file .env.example build
RUN_DOCKER_CONFIG_MIGRATION=1 CONFIG_MIGRATION_IMAGE=bgp-antifilter:dev python -m unittest tests.test_config_volume -v
```

Equivalent test invocation in PowerShell:

```powershell
$env:RUN_DOCKER_CONFIG_MIGRATION = '1'
$env:CONFIG_MIGRATION_IMAGE = 'bgp-antifilter:dev'
py -3 -m unittest tests.test_config_volume -v
Remove-Item Env:RUN_DOCKER_CONFIG_MIGRATION
Remove-Item Env:CONFIG_MIGRATION_IMAGE
```

The test covers legacy paths, list/settings migration, edits surviving container
recreation, rebuilding routes with an empty data volume and running scripts from
another working directory. It creates temporary volumes and removes them after testing.
For an additional rollback check, set `CONFIG_ROLLBACK_IMAGE` to a locally available
previous image supporting path environment variables. Test against an image built from current code.

Run the full container smoke tests on Linux with Docker Engine and Compose available:

```bash
RUN_DOCKER_SMOKE=1 python -m unittest tests.test_smoke_docker -v
```

This suite separately checks Compose, the HTTP panel and the prebuilt Portainer stack.
It does not replace testing a real BGP session with MikroTik.
Commands placing variables before the executable use Linux shell syntax.
CI runs Python/JavaScript tests, Compose validation, image builds, volume migration,
Docker smoke tests and ShellCheck; see the [workflow](../.github/workflows/ci.yml).
Release instructions are in [AGENTS.md](../AGENTS.md).
