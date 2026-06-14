import errno
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
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
_TOP_LEVEL_NAME_RE = re.compile(r"^name:\s*(['\"]?)([^#\n]+?)\1\s*(?:#.*)?$", re.MULTILINE)


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


def configured_version():
    try:
        text = ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        return version_value()
    for line in text.splitlines():
        current = line.strip()
        if not current or current.startswith("#"):
            continue
        if not current.startswith("BGP_ANTIFILTER_VERSION="):
            continue
        value = current.split("=", 1)[1].strip().strip("'\"")
        if not value:
            break
        try:
            return validate_version(value)
        except ValueError:
            break
    return version_value()


def validate_version(value):
    raw = str(value or "").strip()
    if raw.lower().startswith("v"):
        raw = raw[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+", raw):
        raise ValueError("version must use MAJOR.MINOR.PATCH format")
    return raw


def runtime_payload():
    return read_json(UPDATE_RUNTIME_FILE, {})


def compose_project_name(compose_file):
    try:
        text = compose_file.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = _TOP_LEVEL_NAME_RE.search(text)
    if not match:
        return ""
    return match.group(2).strip()


def strip_top_level_name(text):
    return _TOP_LEVEL_NAME_RE.sub("", text, count=1).lstrip("\ufeff").lstrip("\n")


def docker_compose_v2_command():
    docker = shutil.which("docker")
    if not docker:
        return None
    try:
        completed = subprocess.run(
            [docker, "compose", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return docker


def compose_base_command():
    docker = docker_compose_v2_command()
    if docker:
        return [docker, "compose", "-f", str(COMPOSE_FILE)], None

    docker_compose = shutil.which("docker-compose")
    if docker_compose:
        project_name = compose_project_name(COMPOSE_FILE)
        command = [docker_compose]
        if project_name:
            command.extend(["-p", project_name])
        try:
            compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
        except OSError:
            compose_text = ""
        if project_name and _TOP_LEVEL_NAME_RE.search(compose_text):
            temp_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yml", delete=False)
            with temp_file:
                temp_file.write(strip_top_level_name(compose_text))
            command.extend(["-f", temp_file.name])
            return command, Path(temp_file.name)
        command.extend(["-f", str(COMPOSE_FILE)])
        return command, None

    raise FileNotFoundError("docker compose executable is not available inside admin container")


def health_status():
    if not WORKSPACE_DIR.exists():
        return False, f"workspace directory not found: {WORKSPACE_DIR}"
    if not COMPOSE_FILE.exists():
        return False, f"compose file not found: {COMPOSE_FILE}"
    try:
        _, cleanup_path = compose_base_command()
    except OSError as exc:
        return False, str(exc)
    finally:
        if "cleanup_path" in locals() and cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)
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
    cleanup_path = None
    try:
        base_command, cleanup_path = compose_base_command()
        command = [*base_command, *args]
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
    finally:
        if cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)


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
    previous_version = configured_version()
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
    active = bool(runtime.get("active"))
    target_version = str(runtime.get("target_version") or "")
    if target_version == str(current_version or "") and (active or runtime.get("success") is False):
        write_runtime(
            active=False,
            stage="completed",
            message=f"Update to v{target_version} completed",
            finished_at_unix=int(time.time()),
            success=True,
            current_version=target_version,
            error="",
            rollback={},
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
        "current_version": configured_version(),
    }
