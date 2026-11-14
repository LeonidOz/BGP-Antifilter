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

from .state_store import mutate_state, patch_state, read_state, state_lock

WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
ENV_FILE = Path(os.environ.get("ENV_FILE", str(WORKSPACE_DIR / ".env")))
VERSION_FILE = Path(os.environ.get("VERSION_FILE", str(WORKSPACE_DIR / "VERSION")))
COMPOSE_FILE = Path(os.environ.get("COMPOSE_FILE", str(WORKSPACE_DIR / "docker-compose.yml")))
UPDATE_RUNTIME_FILE = Path(os.environ.get("UPDATE_RUNTIME_FILE", str(WORKSPACE_DIR / "generated" / "update-runtime.json")))
COMPOSE_SERVICES = tuple(
    item.strip()
    for item in os.environ.get("UPDATER_COMPOSE_SERVICES", "bgp-antifilter").split()
    if item.strip()
)
SELF_SERVICE = os.environ.get("UPDATER_SELF_SERVICE", "bgp-antifilter").strip()
UPDATE_LOCK = threading.Lock()
PROJECT_NAME = os.environ.get("UPDATER_PROJECT_NAME", "")
PROJECT_DIRECTORY = os.environ.get("UPDATER_PROJECT_DIRECTORY", "")
HEALTH_TIMEOUT = int(os.environ.get("UPDATER_HEALTH_TIMEOUT", "180"))
_TOP_LEVEL_NAME_RE = re.compile(r"^name:\s*(['\"]?)([^#\n]+?)\1\s*(?:#.*)?$", re.MULTILINE)
_LEGACY_UNSUPPORTED_NETWORK_FIELDS_RE = re.compile(r"(?m)^[ \t]+enable_ipv4:\s*.+\n?")


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_text_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as file:
        tmp = Path(file.name)
        file.write(text)
    try:
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o777)
        tmp.replace(path)
    except OSError as exc:
        if exc.errno not in (errno.EBUSY, errno.EACCES, errno.EPERM):
            raise
        tmp.unlink(missing_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            file.write(text)
    finally:
        tmp.unlink(missing_ok=True)


def write_runtime(**updates):
    patch_state(UPDATE_RUNTIME_FILE, **updates)


def version_value():
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def configured_version_setting():
    try:
        text = ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""
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
    return ""


def configured_version():
    configured = configured_version_setting()
    if configured:
        return configured
    return version_value()


def validate_version(value):
    raw = str(value or "").strip()
    if raw.lower().startswith("v"):
        raw = raw[1:]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", raw):
        raise ValueError("version must use MAJOR.MINOR.PATCH format")
    return raw


def runtime_payload():
    return read_state(UPDATE_RUNTIME_FILE)


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


def sanitize_legacy_compose_text(text):
    stripped = strip_top_level_name(text)
    return _LEGACY_UNSUPPORTED_NETWORK_FIELDS_RE.sub("", stripped)


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
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return docker


def compose_base_command():
    options = ["--env-file", str(ENV_FILE)]
    if PROJECT_NAME:
        options.extend(["-p", PROJECT_NAME])
    if PROJECT_DIRECTORY:
        options.extend(["--project-directory", PROJECT_DIRECTORY])
    docker = docker_compose_v2_command()
    if docker:
        return [docker, "compose", *options, "-f", str(COMPOSE_FILE)], None

    docker_compose = shutil.which("docker-compose")
    if docker_compose:
        project_name = PROJECT_NAME or compose_project_name(COMPOSE_FILE)
        command = [docker_compose, *options]
        if project_name and not PROJECT_NAME:
            command.extend(["-p", project_name])
        try:
            compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
        except OSError:
            compose_text = ""
        if project_name and _TOP_LEVEL_NAME_RE.search(compose_text):
            temp_file = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yml", delete=False)
            with temp_file:
                temp_file.write(sanitize_legacy_compose_text(compose_text))
            command.extend(["-f", temp_file.name])
            return command, Path(temp_file.name)
        command.extend(["-f", str(COMPOSE_FILE)])
        return command, None

    raise FileNotFoundError("docker compose executable is not available inside container")


def uses_legacy_docker_compose():
    command, cleanup_path = compose_base_command()
    try:
        return Path(command[0]).name == "docker-compose"
    finally:
        if cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)


def restart_services_for_update():
    # The temporary updater lives outside the Compose project and survives rm/up.
    return COMPOSE_SERVICES


def run_docker(*args, timeout=30):
    completed = subprocess.run(
        ["docker", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "docker command failed")
    return completed.stdout.strip()


def inspect_container(name):
    return json.loads(run_docker("inspect", name))[0]


def deployment_context():
    info = inspect_container(os.environ.get("HOSTNAME", ""))
    labels = info.get("Config", {}).get("Labels") or {}
    project = labels.get("com.docker.compose.project", "")
    files = labels.get("com.docker.compose.project.config_files", "").split(",")
    if not project or labels.get("com.docker.compose.service") != SELF_SERVICE:
        raise RuntimeError("self-update requires a Compose-managed application container")
    if len(files) != 1:
        raise RuntimeError("self-update requires a single Compose file; update this deployment manually")
    mount = next((m for m in info.get("Mounts", []) if m["Destination"] == str(WORKSPACE_DIR)), None)
    if not mount or mount.get("Type") != "bind" or not mount.get("RW"):
        raise RuntimeError("self-update requires a writable workspace bind mount")
    host_workspace = mount["Source"]
    if not host_workspace.startswith("/"):
        raise RuntimeError("self-update requires Linux host paths")
    # Resolve relative bind mounts on the Docker host, rather than /workspace.
    return {"container": info["Id"], "image": info["Image"], "project": project,
            "directory": host_workspace, "worker": f"{project}-image-updater"}


def health_status():
    if os.environ.get("PORTAINER_MANAGED", "0") == "1":
        return False, "Image updates are managed by Portainer; update the stack image there"
    if not WORKSPACE_DIR.exists():
        return False, f"workspace directory not found: {WORKSPACE_DIR}"
    if not COMPOSE_FILE.exists():
        return False, f"compose file not found: {COMPOSE_FILE}"
    if not configured_version_setting():
        return False, "self-update is disabled for local dev builds; set BGP_ANTIFILTER_VERSION in .env to pin a release image tag"
    try:
        _, cleanup_path = compose_base_command()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    finally:
        if "cleanup_path" in locals() and cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)
    docker_socket = Path("/var/run/docker.sock")
    if not docker_socket.exists():
        return False, "docker socket is not mounted"
    try:
        deployment_context()
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
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
        if current.strip().startswith("BGP_ANTIFILTER_VERSION="):
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
            # Container settings must not override the newly written .env pin.
            env={key: value for key, value in os.environ.items()
                 if key in {"PATH", "HOME", "SYSTEMROOT", "DOCKER_HOST", "DOCKER_API_VERSION"}},
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


def recreate_services(*services, timeout=1800):
    target_services = tuple(service for service in services if service)
    if not target_services:
        return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}
    remove_result = run_compose("rm", "-f", "-s", *target_services, timeout=timeout)
    if remove_result["ok"]:
        return run_compose("up", "-d", "--no-build", *target_services, timeout=timeout)

    combined_output = f'{remove_result.get("stderr", "")}\n{remove_result.get("stdout", "")}'
    if "No stopped containers" not in combined_output and "No such service" not in combined_output:
        return remove_result
    return run_compose("up", "-d", "--no-build", *target_services, timeout=timeout)


def wait_for_services(version, timeout=None):
    deadline = time.monotonic() + (HEALTH_TIMEOUT if timeout is None else timeout)
    last_error = "application did not become healthy"
    while True:
        try:
            for service in COMPOSE_SERVICES:
                result = run_compose("ps", "-q", service, timeout=15)
                ids = result.get("stdout", "").split()
                if not result["ok"] or len(ids) != 1:
                    raise RuntimeError(f"{service}: expected one running container")
                info = inspect_container(ids[0])
                state = info.get("State", {})
                if not state.get("Running") or state.get("Health", {}).get("Status") != "healthy":
                    raise RuntimeError(f"{service}: container is not healthy")
                if service == SELF_SERVICE:
                    actual = run_docker("exec", ids[0], "python3", "-c",
                                        "import json, os, urllib.request; "
                                        "from bgp_antifilter import __version__; "
                                        "port = os.environ.get('ADMIN_PORT', '8080'); "
                                        "response = urllib.request.urlopen('http://127.0.0.1:' + port + '/api/session', timeout=5); "
                                        "assert json.load(response)['version'] == __version__; print(__version__)")
                    if actual != version:
                        raise RuntimeError(f"running version {actual} does not match {version}")
            return
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            raise RuntimeError(f"health verification failed: {last_error}")
        time.sleep(2)


def rollback(previous_version, previous_env=None, restart=True):
    try:
        if previous_env is None:
            update_env_version(ENV_FILE, previous_version)
        else:
            write_text_atomic(ENV_FILE, previous_env)
        if restart:
            services = restart_services_for_update()
            if uses_legacy_docker_compose():
                result = recreate_services(*services, timeout=1800)
            else:
                result = run_compose("up", "-d", "--no-build", *services, timeout=1800)
            if not result["ok"]:
                raise RuntimeError(result.get("stderr") or result.get("stdout") or "rollback compose up failed")
            wait_for_services(previous_version)
        return {"ok": True, "version": previous_version}
    except Exception as exc:
        return {"ok": False, "version": previous_version, "error": str(exc)}


def apply_update(version):
    previous_version = configured_version()
    services = restart_services_for_update()
    previous_env = None
    restart_attempted = False
    try:
        version = validate_version(version)
        with ENV_FILE.open(encoding="utf-8", newline="") as file:
            previous_env = file.read()
        write_runtime(active=True, stage="preparing", current_version=previous_version,
                      target_version=version, success=None, error="", rollback={})
        update_env_version(ENV_FILE, version)
        write_runtime(stage="pulling", message=f"Pulling images for v{version}")
        pull_result = run_compose("pull", *COMPOSE_SERVICES, timeout=1800)
        if not pull_result["ok"]:
            raise RuntimeError(pull_result.get("stderr") or pull_result.get("stdout") or "docker compose pull failed")

        write_runtime(stage="restarting", message=f"Restarting services with v{version}")
        restart_attempted = True
        if uses_legacy_docker_compose():
            up_result = recreate_services(*services, timeout=1800)
        else:
            up_result = run_compose("up", "-d", "--no-build", *services, timeout=1800)
        if not up_result["ok"]:
            raise RuntimeError(up_result.get("stderr") or up_result.get("stdout") or "docker compose up failed")

        write_runtime(stage="verifying", message=f"Checking application health for v{version}")
        wait_for_services(version)

        write_runtime(
            active=False,
            stage="completed",
            message=f"Update to v{version} completed",
            finished_at_unix=int(time.time()),
            success=True,
            current_version=version,
        )
    except Exception as exc:
        write_runtime(stage="rolling_back", message="Restoring previous version", error=str(exc))
        rollback_result = (rollback(previous_version, previous_env, restart=restart_attempted)
                           if previous_version and previous_env is not None
                           else {"ok": False, "error": "previous configuration is unavailable"})
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
    worker = runtime.get("worker")
    if worker:
        # Only the independent worker can declare a verified update successful.
        if active:
            try:
                if inspect_container(worker).get("State", {}).get("Running"):
                    return runtime
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
                # Do not report failure while the daemon is temporarily unreachable.
                try:
                    run_docker("info", "--format", "{{.ID}}", timeout=10)
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    return runtime
            if time.time() - float(runtime.get("started_at_unix") or 0) < 30:
                return runtime

            def interrupted(current):
                if not current.get("active") or current.get("started_at_unix") != runtime.get("started_at_unix"):
                    return None
                return {**current, "active": False, "success": False, "stage": "failed",
                        "error": "updater container stopped before verification; check the deployment and retry",
                        "finished_at_unix": int(time.time())}
            return mutate_state(UPDATE_RUNTIME_FILE, interrupted)
        return runtime
    target_version = str(runtime.get("target_version") or "")
    if target_version == str(current_version or "") and (active or runtime.get("success") is False):
        def reconcile(current):
            # A newer update may have started after runtime_payload was read.
            if str(current.get("target_version") or "") != target_version:
                return None
            if not current.get("active") and current.get("success") is not False:
                return None
            return {
                **current,
                "active": False,
                "stage": "completed",
                "message": f"Update to v{target_version} completed",
                "finished_at_unix": int(time.time()),
                "success": True,
                "current_version": target_version,
                "error": "",
                "rollback": {},
            }

        return mutate_state(UPDATE_RUNTIME_FILE, reconcile)
    return runtime


def start_update(version):
    target_version = validate_version(version)
    ok, error = health_status()
    if not ok:
        raise RuntimeError(error)
    with UPDATE_LOCK, state_lock(UPDATE_RUNTIME_FILE.with_name("update-launch")):
        if reconcile_runtime(configured_version()).get("active"):
            raise RuntimeError("update already running")
        previous_version = configured_version()
        if tuple(map(int, target_version.split("."))) <= tuple(map(int, validate_version(previous_version).split("."))):
            raise ValueError("target version must be newer than the configured version")
        context = deployment_context()
        # A deterministic Docker name also prevents duplicate workers across restarts.
        command = ["run", "-d", "--rm", "--no-healthcheck", "--name", context["worker"],
                   "--label", "bgp-antifilter.updater=true", "--volumes-from", context["container"],
                   "--volume", f'{context["directory"]}:{context["directory"]}',
                   "--entrypoint", "python3"]
        settings = {"WORKSPACE_DIR": str(WORKSPACE_DIR), "ENV_FILE": str(ENV_FILE),
                    "VERSION_FILE": str(VERSION_FILE), "COMPOSE_FILE": str(COMPOSE_FILE),
                    "UPDATE_RUNTIME_FILE": str(UPDATE_RUNTIME_FILE),
                    "UPDATER_PROJECT_NAME": context["project"], "UPDATER_PROJECT_DIRECTORY": context["directory"],
                    "UPDATER_COMPOSE_SERVICES": " ".join(COMPOSE_SERVICES), "UPDATER_SELF_SERVICE": SELF_SERVICE,
                    "UPDATER_HEALTH_TIMEOUT": str(HEALTH_TIMEOUT)}
        for key, value in settings.items():
            command.extend(["-e", f"{key}={value}"])
        command.extend([context["image"], "-m", "bgp_antifilter.updater_server", target_version])
        write_runtime(active=True, stage="preparing", message=f"Preparing update to v{target_version}",
                      started_at_unix=int(time.time()), finished_at_unix=None, success=None, error="", rollback={},
                      current_version=previous_version, target_version=target_version, worker=context["worker"])
        try:
            run_docker(*command)
        except subprocess.TimeoutExpired:
            # The daemon may have started the worker before its response was lost.
            # Keep the operation reserved until reconciliation observes its state.
            pass
        except (OSError, RuntimeError) as exc:
            write_runtime(active=False, stage="failed", success=False, error=str(exc),
                          finished_at_unix=int(time.time()))
            raise RuntimeError(f"could not start updater: {exc}") from exc
    return {
        "ok": True,
        "accepted": True,
        "target_version": target_version,
        "current_version": previous_version,
    }


if __name__ == "__main__":
    import sys
    apply_update(validate_version(sys.argv[1]))
