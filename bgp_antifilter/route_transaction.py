"""Generate, preview and apply exact route snapshots; publish success after BIRD."""

import argparse
from contextlib import contextmanager
import json
import ipaddress
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from .check_ip import parse_networks_from_text
from .route_output import write_metrics, write_text
from .route_snapshot import digest, read_confirmed, route_text, snapshot_path
from .runtime_state import IDLE_GENERATION
from .state_store import patch_state, read_state, state_lock, write_state


class GenerationFailed(RuntimeError):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


@contextmanager
def operation_lock(config):
    # The OS lock releases on crashes; update.lock also protects legacy exporters.
    try:
        with state_lock(config.generated_dir / ".route-operation", timeout=0):
            config.update_lock_dir.mkdir(parents=True, exist_ok=True)
            try:
                yield
            finally:
                config.update_lock_dir.rmdir()
    except TimeoutError as exc:
        raise RuntimeError("route operation already running") from exc


class RouteManager:
    def __init__(self, config, environment):
        self.config = config
        from .runtime_paths import GENERATED_PATH_SPECS, LIST_FILE_SPECS
        self.environment = {**environment,
                            **{variable: str(getattr(config, key)) for key, (variable, _) in GENERATED_PATH_SPECS.items() if hasattr(config, key)},
                            **{variable: str(config.list_files[key]) for key, (variable, _) in LIST_FILE_SPECS.items()},
                            "LAST_GOOD_ROUTES_FILE": str(config.last_good_routes_file),
                            "UPDATE_LOCK_DIR": str(config.update_lock_dir)}
        self.environment.setdefault("CACHE_DIR", str(config.generated_dir / "cache"))
        self.environment.setdefault("NETWORK_STATUS_FILE", str(config.generated_dir / "network-status.json"))
        self.previews = config.generated_dir / "previews"

    def fingerprint(self):
        from .admin.settings import SETTINGS_BY_KEY
        contents = {name: path.read_text(encoding="utf-8") if path.exists() else ""
                    for name, path in self.config.list_files.items()}
        # Include settings and effective defaults, not only settings.json.
        contents["settings"] = {key: self.environment.get(key, spec["default"]) for key, spec in SETTINGS_BY_KEY.items()}
        for path in (self.config.settings_file, self.config.settings_env_file):
            contents[str(path)] = path.read_text(encoding="utf-8") if path.exists() else ""
        return digest(json.dumps(contents, sort_keys=True))

    def baseline(self):
        try:
            return digest(self.config.last_good_routes_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return digest("")

    def generate(self, directory, *, preview=False):
        directory = Path(directory)
        env = {**self.environment, "STATUS_FILE": str(directory / "status.json"),
               "METRICS_FILE": str(directory / "metrics.prom")}
        if preview:
            env["RUNTIME_FILE"] = str(directory / "runtime.json")
        command = [sys.executable, "-m", "bgp_antifilter.update_routes", "--output", str(directory / "routes.conf"),
                   "--status", env["STATUS_FILE"], "--metrics", env["METRICS_FILE"], "--snapshot", str(directory / "snapshot.json")]
        try:
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=600, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("route generation timed out after 600 seconds") from exc
        if result.stdout:
            print(result.stdout, end="", flush=True)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr, flush=True)
        snapshot = read_state(directory / "snapshot.json")
        if result.returncode or not snapshot.get("prefixes"):
            status = read_state(directory / "status.json")
            errors = [item.get("error", "") for item in status.get("errors", [])]
            raise GenerationFailed("Route update failed: " + ("; ".join(errors) or result.stderr[-2000:] or "empty route snapshot"), status)
        return snapshot

    def create_preview(self):
        with operation_lock(self.config), tempfile.TemporaryDirectory(prefix="preview-", dir=self.config.generated_dir) as directory:
            fingerprint = self.fingerprint()
            snapshot = self.generate(directory, preview=True)
            if fingerprint != self.fingerprint():
                raise RuntimeError("configuration changed while preparing preview; try again")
            old = self.config.last_good_routes_file
            old_prefixes = {str(net) for net in parse_networks_from_text(old.read_text(encoding="utf-8") if old.exists() else "", extract=True)}
            new_prefixes = set(snapshot["prefixes"])
            snapshot.update(id=uuid.uuid4().hex, created_at_unix=int(time.time()),
                            fingerprint=fingerprint, baseline=self.baseline(),
                            added=sorted(new_prefixes - old_prefixes), removed=sorted(old_prefixes - new_prefixes))
            self.previews.mkdir(parents=True, exist_ok=True)
            # Remove only expired preview artifacts owned by this service.
            for path in self.previews.glob("*.json"):
                if path.stat().st_mtime < time.time() - 86400:
                    path.unlink(missing_ok=True)
            write_state(self.previews / (snapshot["id"] + ".json"), snapshot)
            return self.preview(snapshot["id"])

    def read_preview(self, identifier):
        if not isinstance(identifier, str) or len(identifier) != 32 or any(char not in "0123456789abcdef" for char in identifier):
            raise ValueError("invalid preview id")
        snapshot = read_state(self.previews / (identifier + ".json"))
        if not snapshot or time.time() - snapshot["created_at_unix"] > 3600:
            raise ValueError("preview expired; prepare a new preview")
        if snapshot["fingerprint"] != self.fingerprint() or snapshot["baseline"] != self.baseline():
            raise ValueError("preview is stale: configuration or active routes changed")
        return snapshot

    def preview(self, identifier, search="", offset=0):
        snapshot = self.read_preview(identifier)
        try:
            query = ipaddress.IPv4Network(search, strict=False) if search else None
        except ValueError:
            query = None
        def matches(prefix):
            return ipaddress.IPv4Network(prefix).overlaps(query) if query else search.lower() in prefix.lower()
        added = [prefix for prefix in snapshot["added"] if matches(prefix)]
        removed = [prefix for prefix in snapshot["removed"] if matches(prefix)]
        offset = max(0, int(offset))
        return {"id": identifier, "created_at_unix": snapshot["created_at_unix"],
                "total": len(snapshot["prefixes"]), "added_count": len(snapshot["added"]), "removed_count": len(snapshot["removed"]),
                "added": added[offset:offset + 100], "removed": removed[offset:offset + 100],
                "added_matches": len(added), "removed_matches": len(removed), "offset": offset, "page_size": 100}

    def configure(self):
        result = subprocess.run(["birdc", "configure"], capture_output=True, text=True, timeout=30, check=False)
        print(result.stdout, end="", flush=True)
        if result.returncode or "Reconfigured" not in result.stdout:
            raise RuntimeError("BIRD rejected updated routes: " + (result.stderr or result.stdout)[-2000:])

    def publish(self, snapshot):
        now = int(time.time())
        snapshot = {**snapshot, "applied_at_unix": now}
        status = {**snapshot["status"], "success": True, "generation_success": True, "apply_success": True,
                  "degraded": False, "degraded_reason": "", "last_successful_apply_timestamp_seconds": now}
        snapshot["status"] = status
        write_text(self.config.last_good_routes_file, route_text(snapshot["prefixes"]))
        write_state(snapshot_path(self.config.last_good_routes_file), snapshot)
        write_state(self.config.status_file, status)
        write_metrics(self.config.metrics_file, status)

    def failed(self, error, *, generation_success=False, attempt_status=None):
        previous = read_state(self.config.status_file)
        confirmed = read_confirmed(self.config.last_good_routes_file)
        attempt = getattr(error, "status", None) or attempt_status or {}
        status = {**previous, "success": False, "generation_success": generation_success, "apply_success": False,
                  "degraded": True, "degraded_reason": str(error) + "; previous route snapshot remains active",
                  "updated_at_unix": int(time.time()),
                  "sources": attempt.get("sources", previous.get("sources", [])),
                  "duration_seconds": attempt.get("duration_seconds", previous.get("duration_seconds", 0)),
                  "errors": [*attempt.get("errors", []), {"kind": "runtime", "name": "apply", "error": str(error)}]}
        status["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(status["updated_at_unix"]))
        status["run_reason"] = self.environment.get("ROUTE_UPDATE_REASON", "manual")
        status.setdefault("duration_seconds", 0)
        status.setdefault("sources", [])
        status["routes"] = confirmed.get("status", {}).get("routes", previous.get("routes", {"final": 0}))
        status["routes"] = {"invalid": 0, "exclude_rules_applied": 0, **status["routes"]}
        if not self.config.last_good_routes_file.exists() or not self.config.last_good_routes_file.stat().st_size:
            status["routes"]["final"] = 0
        write_state(self.config.status_file, status)
        write_metrics(self.config.metrics_file, status)

    def apply(self, identifier=None):
        with operation_lock(self.config):
            snapshot = self.read_preview(identifier) if identifier else None
            config = self.config
            previous_files = {path: path.read_bytes() if path.exists() else None for path in
                              (config.routes_file, config.last_good_routes_file, snapshot_path(config.last_good_routes_file), config.status_file, config.metrics_file)}
            started = int(time.time())
            reason = self.environment.get("ROUTE_UPDATE_REASON", "manual")
            patch_state(config.runtime_file, generation_active=True, generation_kind=reason,
                        generation_started_at_unix=started, generation_stage="bootstrap", generation_progress_percent=0)
            configured = False
            generated = snapshot is not None
            error = None
            try:
                if snapshot is None:
                    with tempfile.TemporaryDirectory(prefix="routes-", dir=config.generated_dir) as directory:
                        fingerprint = self.fingerprint()
                        snapshot = self.generate(directory)
                        if fingerprint != self.fingerprint():
                            raise RuntimeError("configuration changed during generation; retry update")
                    generated = True
                patch_state(config.runtime_file, generation_active=True, generation_stage="applying-routes",
                            generation_progress_percent=90, generation_stage_message="Waiting for BIRD to accept routes")
                write_text(config.routes_file, route_text(snapshot["prefixes"]))
                configured = True
                self.configure()
                self.publish(snapshot)
                if identifier:
                    (self.previews / (identifier + ".json")).unlink(missing_ok=True)
            except Exception as exc:
                error = exc
                for path, content in previous_files.items():
                    if content is None:
                        path.unlink(missing_ok=True)
                    else:
                        write_text(path, content.decode("utf-8"))
                if configured:
                    try:
                        self.configure()
                    except Exception as rollback_error:
                        error = RuntimeError(f"{exc}; rollback failed: {rollback_error}")
                self.failed(error, generation_success=generated, attempt_status=snapshot.get("status") if snapshot else None)
                raise error
            finally:
                finished = int(time.time())
                patch_state(config.runtime_file, **IDLE_GENERATION, last_update_reason=reason,
                            last_update_success=error is None, last_update_finished_at_unix=finished,
                            degraded=error is not None, degraded_reason=str(error) if error else "",
                            next_scheduled_update_unix=finished + int(self.environment.get("UPDATE_INTERVAL", 1800)))

    def prepare(self):
        with operation_lock(self.config), tempfile.TemporaryDirectory(prefix="initial-", dir=self.config.generated_dir) as directory:
            snapshot = self.generate(directory)
            write_text(self.config.routes_file, route_text(snapshot["prefixes"]))
            write_state(self.config.generated_dir / "routes.prepared.json", snapshot)
            status = {**snapshot["status"], "success": False, "apply_success": None}
            write_state(self.config.status_file, status)
            write_metrics(self.config.metrics_file, status)

    def confirm_startup(self):
        path = self.config.generated_dir / "routes.prepared.json"
        snapshot = read_state(path)
        if not snapshot:
            return
        with operation_lock(self.config):
            if digest(self.config.routes_file.read_text(encoding="utf-8")) != snapshot["routes_sha256"]:
                raise RuntimeError("prepared routes changed before BIRD startup")
            for _ in range(30):
                result = subprocess.run(["birdc", "show", "status"], capture_output=True, timeout=5, check=False)
                if result.returncode == 0:
                    self.publish(snapshot)
                    now = int(time.time())
                    patch_state(self.config.runtime_file, **IDLE_GENERATION, last_update_reason="initial",
                                last_update_message="BIRD accepted initial routes", last_update_success=True,
                                last_update_finished_at_unix=now, degraded=False, degraded_reason="",
                                next_scheduled_update_unix=now + int(self.environment.get("UPDATE_INTERVAL", 1800)))
                    path.unlink()
                    return
                time.sleep(1)
            self.failed("BIRD did not accept initial routes", generation_success=True, attempt_status=snapshot.get("status"))
            patch_state(self.config.runtime_file, **IDLE_GENERATION, last_update_success=False,
                        degraded=True, degraded_reason="BIRD did not accept initial routes")
            raise RuntimeError("BIRD startup confirmation timed out")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("apply", "prepare", "confirm-startup"))
    parser.add_argument("--preview-id")
    args = parser.parse_args(argv)
    from .admin.config import AdminConfig
    manager = RouteManager(AdminConfig.from_env(), os.environ.copy())
    try:
        if args.command == "apply":
            manager.apply(args.preview_id)
        elif args.command == "prepare":
            manager.prepare()
        else:
            manager.confirm_startup()
        return 0
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
