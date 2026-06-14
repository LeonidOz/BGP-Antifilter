import errno
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
ENV_FILE = Path(os.environ.get("ENV_FILE", str(WORKSPACE_DIR / ".env")))
VERSION_FILE = Path(os.environ.get("VERSION_FILE", str(WORKSPACE_DIR / "VERSION")))
COMPOSE_FILE = Path(os.environ.get("COMPOSE_FILE", str(WORKSPACE_DIR / "docker-compose.yml")))
UPDATE_RUNTIME_FILE = Path(os.environ.get("UPDATE_RUNTIME_FILE", str(WORKSPACE_DIR / "generated" / "update-runtime.json")))
COMPOSE_SERVICES = tuple(
    item.strip()
    for item in os.environ.get("UPDATER_COMPOSE_SERVICES", "bird admin").split()
    if item.strip()
)
UPDATE_LOCK = threading.Lock()
UPDATE_THREAD = None


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_text_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(path)
    except OSError as exc:
        if exc.errno not in (errno.EBUSY, errno.EACCES, errno.EPERM):
            raise
        tmp.unlink(missing_ok=True)
        path.write_text(text, encoding="utf-8")


def write_runtime(**updates):
    current = read_json(UPDATE_RUNTIME_FILE, {})
    current.update(updates)
    write_text_atomic(UPDATE_RUNTIME_FILE, json.dumps(current, indent=2, ensure_ascii=False) + "\n")


def version_value():
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def validate_version(value):
    raw = str(value or "").strip()
    if raw.lower().startswith("v"):
        raw = raw[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+", raw):
        raise ValueError("version must use MAJOR.MINOR.PATCH format")
    return raw


def update_env_version(path, version):
    line = f"BGP_ANTIFILTER_VERSION={version}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    lines = text.splitlines()
    replaced = False
    result = []
    for current in lines:
        if current.startswith("BGP_ANTIFILTER_VERSION="):
            result.append(line)
            replaced = True
        else:
            result.append(current)
    if not replaced:
        if result and result[-1] != "":
            result.append("")
        result.append(line)
    write_text_atomic(path, "\n".join(result) + "\n")


def run_compose(*args, timeout=1800):
    started = time.time()
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    completed = subprocess.run(
        command,
        cwd=str(WORKSPACE_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": round(time.time() - started, 3),
        "command": command,
    }


def rollback(previous_version):
    try:
        update_env_version(ENV_FILE, previous_version)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    result = run_compose("up", "-d", *COMPOSE_SERVICES, timeout=1800)
    if result["ok"]:
        return {"ok": True, "version": previous_version}
    return {
        "ok": False,
        "version": previous_version,
        "error": result.get("stderr") or result.get("stdout") or f"compose returned {result.get('returncode')}",
    }


def apply_update(version):
    previous_version = version_value()
    write_runtime(
        active=True,
        stage="preparing",
        message=f"Preparing update to v{version}",
        started_at_unix=int(time.time()),
        finished_at_unix=None,
        current_version=previous_version,
        target_version=version,
        success=None,
        error="",
        rollback={},
    )
    try:
        update_env_version(ENV_FILE, version)
        write_runtime(stage="pulling", message=f"Pulling images for v{version}")
        pull_result = run_compose("pull", *COMPOSE_SERVICES, timeout=1800)
        if not pull_result["ok"]:
            raise RuntimeError(pull_result.get("stderr") or pull_result.get("stdout") or "docker compose pull failed")

        write_runtime(stage="restarting", message=f"Restarting services with v{version}")
        up_result = run_compose("up", "-d", *COMPOSE_SERVICES, timeout=1800)
        if not up_result["ok"]:
            raise RuntimeError(up_result.get("stderr") or up_result.get("stdout") or "docker compose up failed")

        write_runtime(
            active=False,
            stage="completed",
            message=f"Update to v{version} completed",
            finished_at_unix=int(time.time()),
            success=True,
        )
    except Exception as exc:
        rollback_result = rollback(previous_version) if previous_version else {"ok": False, "error": "previous version is unknown"}
        write_runtime(
            active=False,
            stage="failed",
            message=f"Update to v{version} failed",
            finished_at_unix=int(time.time()),
            success=False,
            error=str(exc),
            rollback=rollback_result,
        )


class UpdaterHandler(BaseHTTPRequestHandler):
    server_version = "BGPAntifilterUpdater/0.1"

    def log_message(self, fmt, *args):
        print(f"updater {self.address_string()} - {fmt % args}", flush=True)

    def send_json(self, data, status=HTTPStatus.OK):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body) if body else {}

    def do_GET(self):
        if self.path == "/health":
            active = bool(read_json(UPDATE_RUNTIME_FILE, {}).get("active"))
            self.send_json({"ok": True, "active": active})
            return
        if self.path == "/api/update/runtime":
            self.send_json(read_json(UPDATE_RUNTIME_FILE, {}))
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        global UPDATE_THREAD
        if self.path != "/api/update/apply":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            data = self.read_json()
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            version = validate_version(data.get("version"))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        with UPDATE_LOCK:
            if UPDATE_THREAD is not None and UPDATE_THREAD.is_alive():
                self.send_json({"error": "update already running"}, HTTPStatus.CONFLICT)
                return
            UPDATE_THREAD = threading.Thread(target=apply_update, args=(version,), daemon=True)
            UPDATE_THREAD.start()
        self.send_json({
            "ok": True,
            "accepted": True,
            "target_version": version,
            "current_version": version_value(),
        }, HTTPStatus.ACCEPTED)


def main():
    port = int(os.environ.get("UPDATER_PORT", "8091"))
    UPDATE_RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("", port), UpdaterHandler)
    print(f"updater server listening on port {port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0

