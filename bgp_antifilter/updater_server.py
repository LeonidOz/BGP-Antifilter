import errno
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time


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


def runtime_payload():
    return read_json(UPDATE_RUNTIME_FILE, {})


def compose_base_command():
    docker_compose = shutil.which("docker-compose")
    if docker_compose:
        return [docker_compose, "-f", str(COMPOSE_FILE)]
    docker = shutil.which("docker")
    if docker:
        return [docker, "compose", "-f", str(COMPOSE_FILE)]
    raise FileNotFoundError("docker compose executable is not available inside admin container")


def health_status():
    if not WORKSPACE_DIR.exists():
        return False, f"workspace directory not found: {WORKSPACE_DIR}"
    if not COMPOSE_FILE.exists():
        return False, f"compose file not found: {COMPOSE_FILE}"
    try:
        compose_base_command()
    except OSError as exc:
        return False, str(exc)
    docker_socket = Path("/var/run/docker.sock")
    if not docker_socket.exists():
        return False, "docker socket is not mounted"
    return True, ""


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
    command = [*compose_base_command(), *args]
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
            current_version=version,
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

def reconcile_runtime(current_version):
    runtime = runtime_payload()
    if not runtime:
        return runtime
    stage = str(runtime.get("stage") or "")
    target_version = str(runtime.get("target_version") or "")
    if stage == "restarting" and target_version == str(current_version or ""):
        write_runtime(
            active=False,
            stage="completed",
            message=f"Update to v{target_version} completed",
            finished_at_unix=int(time.time()),
            success=True,
            current_version=target_version,
            error="",
        )
        return runtime_payload()
    return runtime


def start_update(version):
    global UPDATE_THREAD
    target_version = validate_version(version)
    ok, error = health_status()
    if not ok:
        raise RuntimeError(error)
    with UPDATE_LOCK:
        if UPDATE_THREAD is not None and UPDATE_THREAD.is_alive():
            raise RuntimeError("update already running")
        UPDATE_THREAD = threading.Thread(target=apply_update, args=(target_version,), daemon=True)
        UPDATE_THREAD.start()
    return {
        "ok": True,
        "accepted": True,
        "target_version": target_version,
        "current_version": version_value(),
    }
