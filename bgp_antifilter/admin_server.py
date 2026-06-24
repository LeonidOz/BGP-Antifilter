import base64
import errno
import hashlib
import hmac
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__
from . import dns_resolver
from .runtime_paths import GENERATED_PATH_SPECS, LIST_FILE_SPECS, env_path, env_paths
from . import updater_server


ROOT = env_path("ADMIN_STATIC_DIR", "/admin-ui")
PATHS = env_paths(GENERATED_PATH_SPECS)
GENERATED_DIR = PATHS["generated_dir"]
ROUTES_FILE = PATHS["routes_file"]
STATUS_FILE = PATHS["status_file"]
METRICS_FILE = PATHS["metrics_file"]
RUNTIME_FILE = PATHS["runtime_file"]
UPDATE_RUNTIME_FILE = PATHS["update_runtime_file"]
CONTAINER_LOG_FILE = PATHS["container_log_file"]
SETTINGS_FILE = PATHS["settings_file"]
SETTINGS_ENV_FILE = PATHS["settings_env_file"]
UPDATE_LOCK_DIR = env_path("UPDATE_LOCK_DIR", "/etc/bird/generated/update.lock")
RELOAD_RESULT_FILE = GENERATED_DIR / "reload-result.json"

LIST_FILES = env_paths(LIST_FILE_SPECS)

SESSIONS = {}
LOGIN_ATTEMPTS = {}

SETTINGS_SECTIONS = [
    {
        "id": "update",
        "title": "Обновление",
        "items": [
            {"key": "UPDATE_INTERVAL", "type": "int", "default": "1800", "min": 30, "max": 86400, "unit": "sec"},
            {"key": "CACHE_MAX_AGE", "type": "int", "default": "604800", "min": 60, "max": 2592000, "unit": "sec"},
            {"key": "FETCH_TIMEOUT", "type": "int", "default": "30", "min": 1, "max": 300, "unit": "sec"},
            {"key": "FETCH_ATTEMPTS", "type": "int", "default": "5", "min": 1, "max": 20},
            {"key": "FETCH_RETRY_DELAY", "type": "number", "default": "5", "min": 0, "max": 120, "unit": "sec"},
            {"key": "INCLUDE_GOOGLE_RANGES", "type": "bool", "default": "1", "hidden": True},
            {"key": "REQUIRE_ALL_URL_SOURCES", "type": "bool", "default": "0"},
            {"key": "DNS_RESOLVE_TIMEOUT", "type": "number", "default": "3", "min": 0.1, "max": 30, "unit": "sec"},
            {"key": "DNS_RESOLVERS", "type": "dns_list", "default": "", "allow_empty": True},
        ],
    },
    {
        "id": "security",
        "title": "Безопасность генерации",
        "items": [
            {"key": "MIN_PREFIX_LENGTH", "type": "int", "default": "8", "min": 1, "max": 32},
            {"key": "ALLOW_BROAD_ROUTES", "type": "bool", "default": "0"},
        ],
    },
    {
        "id": "bird",
        "title": "BIRD / BGP",
        "items": [
            {"key": "MY_AS", "type": "asn", "default": "64500", "requires_restart": True},
            {"key": "MT_AS", "type": "asn", "default": "65455", "requires_restart": True},
            {"key": "MT_IP", "type": "ipv4", "default": "192.168.55.1", "requires_restart": True},
            {"key": "BIRD_IP", "type": "ipv4", "default": "192.168.55.5", "requires_restart": True},
            {"key": "ROUTER_ID", "type": "ipv4", "default": "192.168.55.5", "requires_restart": True},
            {"key": "BGP_COMMUNITY", "type": "community", "default": "65432,500", "requires_restart": True},
            {"key": "BGP_PROTOCOL", "type": "string", "default": "mikrotik"},
            {"key": "HEALTHCHECK_REQUIRE_BGP", "type": "bool", "default": "1"},
        ],
    },
]

SETTINGS_BY_KEY = {item["key"]: item for section in SETTINGS_SECTIONS for item in section["items"]}
IP_API_URL = (
    "http://ip-api.com/json/?fields="
    "status,message,query,country,countryCode,region,regionName,city,district,zip,"
    "lat,lon,timezone,offset,isp,org,as,asname,mobile,proxy,hosting"
)
REPOSITORY_URL = "https://github.com/LeonidOz/BGP-Antifilter"
LATEST_RELEASE_API_URL = "https://api.github.com/repos/LeonidOz/BGP-Antifilter/releases/latest"
UPDATE_CHECK_TTL_SECONDS = 15 * 60
UPDATE_CHECK_CACHE = {
    "checked_at": 0.0,
    "payload": None,
}
RELOAD_LOCK = threading.Lock()
RELOAD_THREAD = None


def json_load(path, default):
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def text_load(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def settings_overrides():
    data = json_load(SETTINGS_FILE, {})
    if not isinstance(data, dict):
        return {}
    values = data.get("values", data)
    if not isinstance(values, dict):
        return {}
    return {key: str(value) for key, value in values.items() if key in SETTINGS_BY_KEY}


def effective_settings():
    overrides = settings_overrides()
    result = {}
    for key, spec in SETTINGS_BY_KEY.items():
        base = os.environ.get(key, spec["default"])
        result[key] = overrides.get(key, str(base))
    return result


def base_setting_value(key):
    spec = SETTINGS_BY_KEY[key]
    return validate_setting(key, os.environ.get(key, spec["default"]))


def command_environment():
    env = os.environ.copy()
    env.update(effective_settings())
    return env


def validate_setting(key, value):
    spec = SETTINGS_BY_KEY.get(key)
    if not spec:
        raise ValueError(f"unknown setting: {key}")
    raw = str(value).strip()
    if raw == "" and spec.get("allow_empty"):
        return ""
    if raw == "":
        raise ValueError(f"{key} must not be empty")
    setting_type = spec["type"]
    if setting_type == "bool":
        if raw.lower() in {"1", "true", "yes", "on"}:
            return "1"
        if raw.lower() in {"0", "false", "no", "off"}:
            return "0"
        raise ValueError(f"{key} must be 0 or 1")
    if setting_type in {"int", "asn"}:
        try:
            number = int(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must be an integer") from exc
        if setting_type == "asn" and not 1 <= number <= 4294967295:
            raise ValueError(f"{key} must be between 1 and 4294967295")
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{key} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{key} must be at most {spec['max']}")
        return str(number)
    if setting_type == "number":
        try:
            number = float(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must be a number") from exc
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{key} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{key} must be at most {spec['max']}")
        return str(int(number)) if number.is_integer() else str(number)
    if setting_type == "dns_list":
        try:
            values = dns_resolver.parse_nameservers(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must contain IPv4 DNS servers separated by spaces or commas") from exc
        if not values:
            raise ValueError(f"{key} must contain at least one IPv4 address")
        return ",".join(values)
    if setting_type == "ipv4":
        try:
            return str(ipaddress.IPv4Address(raw))
        except ValueError as exc:
            raise ValueError(f"{key} must be a valid IPv4 address") from exc
    if setting_type == "community":
        parts = raw.split(",")
        if len(parts) != 2:
            raise ValueError(f"{key} must use AS,VALUE format")
        numbers = []
        for part in parts:
            try:
                number = int(part.strip())
            except ValueError as exc:
                raise ValueError(f"{key} parts must be integers") from exc
            if not 0 <= number <= 65535:
                raise ValueError(f"{key} parts must be between 0 and 65535")
            numbers.append(number)
        return f"{numbers[0]},{numbers[1]}"
    if setting_type == "string":
        if not raw.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"{key} contains unsupported characters")
        return raw
    raise ValueError(f"{key} has unsupported type")


def save_settings(values):
    normalized = {}
    for key, value in values.items():
        if key not in SETTINGS_BY_KEY:
            continue
        setting_value = validate_setting(key, value)
        if setting_value != base_setting_value(key):
            normalized[key] = setting_value
    payload = {
        "updated_at": int(time.time()),
        "values": normalized,
    }
    write_text_atomic(SETTINGS_FILE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    env_lines = [f"{key}={shlex.quote(value)}" for key, value in sorted(normalized.items())]
    write_text_atomic(SETTINGS_ENV_FILE, "\n".join(env_lines) + ("\n" if env_lines else ""))
    return normalized


def settings_payload():
    overrides = settings_overrides()
    effective = effective_settings()
    sections = []
    for section in SETTINGS_SECTIONS:
        section_items = []
        for item in section["items"]:
            if item.get("hidden"):
                continue
            key = item["key"]
            base_value = base_setting_value(key)
            value = validate_setting(key, effective[key])
            section_items.append({
                **item,
                "value": value,
                "env_value": base_value,
                "overridden": value != base_value,
            })
        sections.append({**section, "items": section_items})
    return {
        "sections": sections,
        "values": effective,
        "overrides": overrides,
        "settings_file": str(SETTINGS_FILE),
        "settings_env_file": str(SETTINGS_ENV_FILE),
    }


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
        with path.open("w", encoding="utf-8") as file:
            file.write(text)


def append_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(text)


def write_reload_result(payload):
    write_text_atomic(RELOAD_RESULT_FILE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_reload_result():
    data = json_load(RELOAD_RESULT_FILE, {})
    return data if isinstance(data, dict) else {}


def backup_file(path):
    if not path.exists():
        return None
    backup_dir = GENERATED_DIR / "list-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = backup_dir / f"{path.name}.{stamp}.bak"
    shutil.copy2(path, backup)
    return str(backup)


def run_command(command, timeout=120):
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=command_environment(),
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "duration_seconds": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"command timed out after {timeout} seconds",
            "duration_seconds": round(time.time() - started, 3),
        }
    except OSError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "duration_seconds": round(time.time() - started, 3),
        }


def reload_runtime_active():
    runtime = reconcile_runtime_state(json_load(RUNTIME_FILE, {}))
    return bool(runtime.get("generation_active"))


def reload_thread_active():
    return RELOAD_THREAD is not None and RELOAD_THREAD.is_alive()


def reload_lock_active():
    return UPDATE_LOCK_DIR.exists()


def reconcile_runtime_state(runtime):
    state = dict(runtime or {})
    if not state.get("generation_active"):
        return state
    if reload_thread_active() or reload_lock_active():
        return state

    state.update({
        "generation_active": False,
        "generation_kind": "",
        "generation_message": "",
        "generation_started_at_unix": None,
        "generation_progress_percent": 0,
        "generation_stage": "",
        "generation_stage_message": "",
        "generation_items_done": None,
        "generation_items_total": None,
        "updated_at_unix": int(time.time()),
    })
    try:
        write_text_atomic(RUNTIME_FILE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        pass
    return state


def apply_reload():
    started_at = int(time.time())
    result = run_command(["/reload-routes.sh"], timeout=600)
    finished_at = int(time.time())
    payload = {
        "active": False,
        "started_at_unix": started_at,
        "finished_at_unix": finished_at,
        **result,
    }
    try:
        write_reload_result(payload)
    except OSError:
        pass
    try:
        lines = [
            f"[manual-reload] started={started_at} finished={finished_at} ok={result.get('ok')} returncode={result.get('returncode')}\n",
        ]
        if result.get("stdout"):
            lines.append("[manual-reload][stdout]\n")
            lines.append(result["stdout"])
            if not result["stdout"].endswith("\n"):
                lines.append("\n")
        if result.get("stderr"):
            lines.append("[manual-reload][stderr]\n")
            lines.append(result["stderr"])
            if not result["stderr"].endswith("\n"):
                lines.append("\n")
        append_text(CONTAINER_LOG_FILE, "".join(lines))
    except OSError:
        pass


def start_reload():
    global RELOAD_THREAD
    with RELOAD_LOCK:
        if reload_runtime_active() or (RELOAD_THREAD is not None and RELOAD_THREAD.is_alive()):
            raise RuntimeError("reload already running")
        write_reload_result({
            "active": True,
            "accepted": True,
            "ok": None,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "duration_seconds": 0,
            "started_at_unix": int(time.time()),
            "finished_at_unix": None,
        })
        RELOAD_THREAD = threading.Thread(target=apply_reload, daemon=True)
        RELOAD_THREAD.start()
    return {
        "ok": True,
        "accepted": True,
        "message": "reload started",
    }


def visible_runtime_state(runtime):
    state = reconcile_runtime_state(runtime)
    if state.get("generation_active") or not reload_thread_active():
        return state
    state.update({
        "generation_active": True,
        "generation_kind": state.get("generation_kind") or "manual",
        "generation_message": state.get("generation_message") or "Starting manual route update",
        "generation_stage": state.get("generation_stage") or "bootstrap",
        "generation_stage_message": state.get("generation_stage_message") or "Waiting for route generator to publish progress",
    })
    return state


def parse_command_status(stdout):
    decoder = json.JSONDecoder()
    parsed = None
    text = stdout or ""
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "sources" in value and "routes" in value:
            parsed = value
    return parsed


def parse_metrics(text):
    values = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or " " not in line:
            continue
        key, value = line.rsplit(" ", 1)
        try:
            values[key] = float(value)
        except ValueError:
            continue
    return values


def route_count_from_file():
    if not ROUTES_FILE.exists():
        return 0
    return sum(1 for line in ROUTES_FILE.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def tail_text(path, max_bytes=250_000):
    try:
        with path.open("rb") as file:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(max(0, size - max_bytes))
            data = file.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def resolve_ipv4_targets(value):
    target = str(value or "").strip()
    if not target:
        return [], "target is required"
    try:
        address = socket.inet_pton(socket.AF_INET, target)
        return [socket.inet_ntop(socket.AF_INET, address)], None
    except OSError:
        pass
    if any(char.isspace() for char in target):
        return [], "target must be an IPv4 address or domain"
    try:
        settings = effective_settings()
        addresses = dns_resolver.resolve_ipv4_addresses(
            target,
            nameservers=dns_resolver.parse_nameservers(settings.get("DNS_RESOLVERS", "")),
            timeout=float(settings.get("DNS_RESOLVE_TIMEOUT", dns_resolver.DEFAULT_TIMEOUT)),
        )
    except (socket.gaierror, OSError, RuntimeError, ValueError) as exc:
        return [], str(exc)
    if not addresses:
        return [], "domain has no IPv4 addresses"
    return addresses, None


def parse_resolv_conf(text):
    nameservers = []
    search = []
    domain = None
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        key, values = parts[0].lower(), parts[1:]
        if key == "nameserver":
            nameservers.extend(values)
        elif key == "search":
            search.extend(values)
        elif key == "domain":
            domain = values[0]
    return {
        "nameservers": nameservers,
        "search": search,
        "domain": domain,
    }


def local_ipv4_addresses():
    addresses = set()
    for host in {socket.gethostname(), socket.getfqdn(), "localhost"}:
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        for info in infos:
            address = info[4][0]
            if address:
                addresses.add(address)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(addresses)


def external_ip_summary(timeout=5):
    try:
        with urllib.request.urlopen(IP_API_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return {
            "ok": False,
            "source": "ip-api.com",
            "error": str(exc),
        }
    if payload.get("status") != "success":
        return {
            "ok": False,
            "source": "ip-api.com",
            "error": payload.get("message", "lookup failed"),
            "payload": payload,
        }
    return {
        "ok": True,
        "source": "ip-api.com",
        **payload,
    }


def parse_semver(value):
    raw = str(value or "").strip()
    if raw.lower().startswith("v"):
        raw = raw[1:]
    parts = raw.split(".")
    if len(parts) != 3:
        raise ValueError("version must use MAJOR.MINOR.PATCH")
    numbers = tuple(int(part) for part in parts)
    return numbers


def github_latest_release(timeout=5):
    request = urllib.request.Request(
        LATEST_RELEASE_API_URL,
        headers={
            "User-Agent": "BGP-Antifilter-Admin/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tag_name = str(payload.get("tag_name") or "").strip()
    version = tag_name[1:] if tag_name.lower().startswith("v") else tag_name
    if not version:
        raise ValueError("latest release payload does not include tag_name")
    return {
        "tag_name": tag_name or f"v{version}",
        "version": version,
        "html_url": str(payload.get("html_url") or REPOSITORY_URL),
        "published_at": str(payload.get("published_at") or ""),
        "name": str(payload.get("name") or ""),
    }


def update_status_payload(force=False):
    now = time.time()
    cached = UPDATE_CHECK_CACHE.get("payload")
    checked_at = float(UPDATE_CHECK_CACHE.get("checked_at") or 0.0)
    if not force and cached is not None and now - checked_at < UPDATE_CHECK_TTL_SECONDS:
        return cached

    current_version = __version__
    payload = {
        "ok": False,
        "repository_url": REPOSITORY_URL,
        "current_version": current_version,
        "latest_version": current_version,
        "latest_tag": f"v{current_version}",
        "release_url": REPOSITORY_URL,
        "release_name": "",
        "published_at": "",
        "update_available": False,
        "error": "",
        "checked_at_unix": int(now),
    }
    try:
        latest = github_latest_release()
        payload.update({
            "ok": True,
            "latest_version": latest["version"],
            "latest_tag": latest["tag_name"],
            "release_url": latest["html_url"],
            "release_name": latest["name"],
            "published_at": latest["published_at"],
            "update_available": parse_semver(latest["version"]) > parse_semver(current_version),
        })
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError) as exc:
        payload["error"] = str(exc)

    UPDATE_CHECK_CACHE["checked_at"] = now
    UPDATE_CHECK_CACHE["payload"] = payload
    return payload


def updater_health():
    return updater_server.health_status()


def network_summary():
    settings = effective_settings()
    resolv = parse_resolv_conf(text_load(Path("/etc/resolv.conf")))
    custom_resolvers = dns_resolver.parse_nameservers(settings.get("DNS_RESOLVERS", ""))
    addresses = local_ipv4_addresses()
    return {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "local_ipv4": addresses,
        "primary_ipv4": next((address for address in addresses if not address.startswith("127.")), addresses[0] if addresses else ""),
        "dns": resolv,
        "custom_dns": {
            "nameservers": custom_resolvers,
            "timeout_seconds": float(settings.get("DNS_RESOLVE_TIMEOUT", dns_resolver.DEFAULT_TIMEOUT)),
            "enabled": bool(custom_resolvers),
        },
        "bird": {
            "router_id": settings.get("ROUTER_ID", ""),
            "bird_ip": settings.get("BIRD_IP", ""),
            "mikrotik_ip": settings.get("MT_IP", ""),
            "bgp_protocol": settings.get("BGP_PROTOCOL", ""),
            "my_as": settings.get("MY_AS", ""),
            "mt_as": settings.get("MT_AS", ""),
        },
        "admin": {
            "port": os.environ.get("ADMIN_PORT", "8080"),
        },
        "external": external_ip_summary(),
        "fetched_at": int(time.time()),
    }


def login_network_payload():
    settings = effective_settings()
    labels = []
    for key in ("ROUTER_ID", "BIRD_IP", "MT_IP"):
        value = settings.get(key, "").strip()
        if value and value not in labels:
            labels.append(value)
    for value in local_ipv4_addresses():
        if not value.startswith("127.") and value not in labels:
            labels.append(value)
    if not labels:
        labels.append("127.0.0.1")
    return {
        "labels": labels[:4],
    }


def cookie_header(name, value, max_age=None):
    parts = [f"{name}={value}", "Path=/", "HttpOnly", "SameSite=Strict"]
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    return "; ".join(parts)


def get_cookie(headers, name):
    raw = headers.get("Cookie", "")
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        if key == name:
            return value
    return None


def new_session():
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"created_at": time.time()}
    return token


def clean_sessions():
    now = time.time()
    expired = [token for token, data in SESSIONS.items() if now - data["created_at"] > 24 * 60 * 60]
    for token in expired:
        SESSIONS.pop(token, None)


def is_login_limited(client):
    now = time.time()
    attempts = [ts for ts in LOGIN_ATTEMPTS.get(client, []) if now - ts < 60]
    LOGIN_ATTEMPTS[client] = attempts
    return len(attempts) >= 8


def record_login_failure(client):
    LOGIN_ATTEMPTS.setdefault(client, []).append(time.time())


def public_compare(left, right):
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "BGPAntifilterAdmin/0.1"

    def log_message(self, fmt, *args):
        print(f"admin {self.address_string()} - {fmt % args}", flush=True)

    def send_json(self, data, status=HTTPStatus.OK, headers=None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_text(self, text, content_type="text/plain; charset=utf-8", status=HTTPStatus.OK):
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_file_text(self, text, filename):
        payload = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body) if body else {}

    def read_json_or_error(self):
        try:
            return self.read_json()
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return None

    def authenticated(self):
        clean_sessions()
        token = get_cookie(self.headers, "bgp_admin_session")
        return token in SESSIONS

    def require_auth(self):
        if self.authenticated():
            return True
        self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self.handle_api_get(path, parsed)
            return

        self.serve_static(path)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            return

        target = ROOT / "index.html"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(target.stat().st_size if target.exists() else 0))
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self.handle_api_post(parsed.path)

    def do_PUT(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self.handle_api_put(parsed.path)

    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        target = (ROOT / path.lstrip("/")).resolve()
        try:
            target.relative_to(ROOT.resolve())
        except ValueError:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        if not target.exists() or not target.is_file():
            target = ROOT / "index.html"
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_api_get(self, path, parsed):
        if path == "/api/session":
            self.send_json({
                "authenticated": self.authenticated(),
                "version": __version__,
                "login_network": login_network_payload(),
            })
            return

        if not self.require_auth():
            return

        if path == "/api/status":
            status = json_load(STATUS_FILE, {})
            runtime = visible_runtime_state(json_load(RUNTIME_FILE, {}))
            reload_result = read_reload_result()
            metrics = parse_metrics(text_load(METRICS_FILE))
            bird = run_command(["birdc", "show", "status"], timeout=5)
            bgp_protocol = effective_settings().get("BGP_PROTOCOL", "mikrotik")
            bgp = run_command(["birdc", "show", "protocols", bgp_protocol], timeout=5)
            self.send_json({
                "version": __version__,
                "status": status,
                "runtime": runtime,
                "metrics": metrics,
                "routes_file_count": route_count_from_file(),
                "bird": bird,
                "bgp": bgp,
                "reload_result": reload_result,
            })
            return

        if path == "/api/metrics":
            self.send_text(text_load(METRICS_FILE))
            return

        if path == "/api/routes":
            self.send_text(text_load(ROUTES_FILE))
            return

        if path == "/api/routes/download":
            self.send_file_text(text_load(ROUTES_FILE), "routes.conf")
            return

        if path == "/api/logs":
            self.send_text(tail_text(CONTAINER_LOG_FILE))
            return

        if path == "/api/settings":
            self.send_json(settings_payload())
            return

        if path == "/api/tools/network":
            self.send_json(network_summary())
            return

        if path == "/api/update/status":
            query = parse_qs(parsed.query or "")
            force = query.get("force", ["0"])[0].strip().lower() in {"1", "true", "yes", "on"}
            payload = update_status_payload(force=force)
            runtime = updater_server.reconcile_runtime(__version__)
            updater_ok, updater_error = updater_health()
            payload.update({
                "runtime": runtime,
                "updater_ok": updater_ok,
                "updater_error": updater_error,
                "apply_available": bool(payload.get("ok")) and bool(payload.get("update_available")) and updater_ok and not runtime.get("active", False),
            })
            self.send_json(payload)
            return

        if path == "/api/lists":
            self.send_json({
                name: {"path": str(path), "bytes": path.stat().st_size if path.exists() else 0}
                for name, path in LIST_FILES.items()
            })
            return

        if path.startswith("/api/lists/"):
            name = path.rsplit("/", 1)[-1]
            list_path = LIST_FILES.get(name)
            if not list_path:
                self.send_json({"error": "unknown list"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"name": name, "path": str(list_path), "content": text_load(list_path)})
            return

        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self, path):
        if path == "/api/login":
            if is_login_limited(self.client_address[0]):
                self.send_json({"error": "too many attempts"}, HTTPStatus.TOO_MANY_REQUESTS)
                return
            data = self.read_json_or_error()
            if data is None:
                return
            password = os.environ.get("ADMIN_PASSWORD", "")
            if password and public_compare(data.get("password", ""), password):
                token = new_session()
                self.send_json({"ok": True}, headers={"Set-Cookie": cookie_header("bgp_admin_session", token)})
                return
            record_login_failure(self.client_address[0])
            self.send_json({"error": "invalid password"}, HTTPStatus.UNAUTHORIZED)
            return

        if path == "/api/logout":
            token = get_cookie(self.headers, "bgp_admin_session")
            if token:
                SESSIONS.pop(token, None)
            self.send_json({"ok": True}, headers={"Set-Cookie": cookie_header("bgp_admin_session", "", max_age=0)})
            return

        if not self.require_auth():
            return

        if path == "/api/actions/dry-run":
            result = run_command(["/update-routes.py", "--dry-run"], timeout=300)
            parsed_status = parse_command_status(result.get("stdout", ""))
            if parsed_status is not None:
                result["status"] = parsed_status
            self.send_json(result)
            return
        if path == "/api/actions/check-sources":
            result = run_command(["/update-routes.py", "--check-sources"], timeout=300)
            parsed_status = parse_command_status(result.get("stdout", ""))
            if parsed_status is not None:
                result["status"] = parsed_status
            self.send_json(result)
            return
        if path == "/api/actions/reload":
            try:
                payload = start_reload()
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
                return
            self.send_json(payload, HTTPStatus.ACCEPTED)
            return
        if path == "/api/update/apply":
            data = self.read_json_or_error()
            if data is None:
                return
            version = str(data.get("version") or "").strip()
            if not version:
                self.send_json({"error": "version is required"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                payload = updater_server.start_update(version)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except RuntimeError as exc:
                status = HTTPStatus.CONFLICT if "already running" in str(exc) else HTTPStatus.SERVICE_UNAVAILABLE
                self.send_json({"error": str(exc)}, status)
                return
            self.send_json(payload, HTTPStatus.ACCEPTED)
            return
        if path == "/api/tools/check-ip":
            data = self.read_json_or_error()
            if data is None:
                return
            target = str(data.get("target") or data.get("ip") or "").strip()
            addresses, error = resolve_ipv4_targets(target)
            if error:
                self.send_json({"error": error}, HTTPStatus.BAD_REQUEST)
                return
            results = []
            ok = True
            for address in addresses:
                result = run_command(["/check-ip.py", address, "--json"], timeout=30)
                parsed = None
                if result["stdout"]:
                    try:
                        parsed = json.loads(result["stdout"])
                    except json.JSONDecodeError:
                        parsed = None
                result["result"] = parsed
                results.append(result)
                ok = ok and result["ok"]
            self.send_json({
                "ok": ok,
                "target": target,
                "addresses": addresses,
                "result": results[0]["result"] if len(results) == 1 else None,
                "results": results,
            })
            return

        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def handle_api_put(self, path):
        if not self.require_auth():
            return

        if path == "/api/settings":
            data = self.read_json_or_error()
            if data is None:
                return
            values = data.get("values")
            if not isinstance(values, dict):
                self.send_json({"error": "values must be an object"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                save_settings(values)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except OSError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_json({"ok": True, **settings_payload()})
            return

        if not path.startswith("/api/lists/"):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        name = path.rsplit("/", 1)[-1]
        list_path = LIST_FILES.get(name)
        if not list_path:
            self.send_json({"error": "unknown list"}, HTTPStatus.NOT_FOUND)
            return

        data = self.read_json_or_error()
        if data is None:
            return
        content = data.get("content")
        if not isinstance(content, str):
            self.send_json({"error": "content must be a string"}, HTTPStatus.BAD_REQUEST)
            return
        if "\x00" in content:
            self.send_json({"error": "content contains NUL byte"}, HTTPStatus.BAD_REQUEST)
            return

        backup = backup_file(list_path)
        if content and not content.endswith("\n"):
            content += "\n"
        try:
            write_text_atomic(list_path, content)
        except OSError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self.send_json({"ok": True, "backup": backup, "bytes": len(content.encode("utf-8"))})


def main():
    if os.environ.get("ADMIN_ENABLED", "0") != "1":
        print("admin server is disabled (ADMIN_ENABLED != 1)", flush=True)
        return 0

    port = int(os.environ.get("ADMIN_PORT", "8080"))
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        print("ADMIN_PASSWORD must be set when admin server is enabled", flush=True)
        return 1

    ROOT.mkdir(parents=True, exist_ok=True)
    updater_server.reconcile_runtime(__version__)
    server = ThreadingHTTPServer(("", port), AdminHandler)
    print(f"admin server listening on port {port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
