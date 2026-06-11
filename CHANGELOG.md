# Changelog

## 0.2.3 - 2026-06-12

- Improved startup and reload progress reporting in the admin UI with a live banner, progress bar, current source details, and fetch attempt counters.
- Fixed `update_routes.py` runtime progress writes to stay best-effort outside the container, so local and CI unit tests continue to pass without `/etc/bird` access.
- Deduplicated identical `/24` network labels in the login canvas so multiple IPs from the same subnet no longer render as duplicate network nodes.

## 0.2.2 - 2026-06-12

- Added `REQUIRE_ALL_URL_SOURCES` to control whether missing URL sources fail the update or are skipped when other inputs can still produce routes.
- Improved the admin UI during long-running startup and reloads: the dashboard now shows an active generation state, elapsed time, a progress bar, and per-source progress counters instead of looking stalled.
- Extended runtime state tracking between shell scripts and the route updater so the UI can distinguish initial startup generation from manual or scheduled refreshes.

## 0.2.1 - 2026-06-11

- Reworked the repository layout: `admin-ui/` now holds the web assets, `deploy/` contains runtime shell/BIRD files, `scripts/` contains Python entrypoints, and the root `docker-compose.yml` remains the single convenient Compose entrypoint.
- Split the admin UI into a dedicated `admin` Compose service so the web interface starts independently from BIRD route generation and Docker logs for `bird` remain available.
- Moved tracked list defaults into `default-lists/` and runtime user-editable lists into `generated/config/`, with first-start bootstrap from defaults to avoid `git pull` conflicts on customized lists.
- Added shared runtime path helpers and aligned Compose, CI, release workflow, Makefile, and documentation around the new runtime file locations.
- Expanded the admin UI with network diagnostics, resolver visibility, external IP/location/provider lookup, clearer generation timing, improved check-IP loading states, dynamic login page network labels, and refreshed logo/favicon branding.
- Added admin server test coverage for the new diagnostics helpers and list-writing behavior under the updated runtime layout.

## 0.2.0 - 2026-06-11

- Added a GitHub Actions CI workflow for unit tests, Docker Compose validation, Docker image build, and ShellCheck.
- Moved Python implementation into the `bgp_antifilter` package while keeping existing CLI entrypoints compatible.
- Added a web admin UI with login, dashboard, list editor, diagnostics tools, logs, settings, and route download.
- Added README project preview screenshots for the admin login and dashboard.
- Added route update locking to prevent parallel scheduled and manual refreshes.
- Added `--dry-run` validation mode for route updates.
- Added structured JSON progress logs and additional Prometheus metrics.
- Added a safety guard that rejects overly broad IPv4 prefixes by default.
- Expanded unit coverage for cache fallback, required source failures, exclude-domain failures, dry-run behavior, broad-route validation, and `check-ip`.
- Added operational documentation, risk notes, and Makefile helper commands.
- Added project versioning through `VERSION`, `bgp_antifilter.__version__`, and the Docker image tag.
- Added JSON output for `/check-ip.py --json`.
- Added `/update-routes.py --check-sources` to validate source availability without building routes.
- Added tag-driven GitHub Release and GHCR Docker image publishing workflow.
