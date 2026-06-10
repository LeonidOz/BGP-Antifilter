# Changelog

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
