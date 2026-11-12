"""HTTP routing, authentication boundaries and response serialization."""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from urllib.parse import parse_qs, urlparse

from .. import __version__, updater_server
from ..export_address_list import DEFAULT_LIST_NAME
from .application import AdminApplication
from .auth import cookie_header, get_cookie
from .lists import ListWriteError, SnapshotUnavailable, UnknownListError


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "BGPAntifilterAdmin/0.1"

    @property
    def app(self):
        return self.server.app

    def log_request(self, code="-", size="-"):
        if self.command in {"GET", "HEAD"} and str(code).isdigit() and 200 <= int(code) < 400:
            return
        super().log_request(code, size)

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
        return self.app.auth.authenticated(get_cookie(self.headers, "bgp_admin_session"))

    def require_auth(self):
        if self.authenticated():
            return True
        self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/status.json":
            self.send_json(self.app.status.public_status_payload())
            return
        if path.startswith("/api/"):
            self.handle_api_get(path, parsed)
            return
        self.serve_static(path)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path == "/status.json":
            payload = json.dumps(self.app.status.public_status_payload(), ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            return
        if parsed.path.startswith("/api/"):
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            return
        target = self.app.config.static_root / "index.html"
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
        root = self.app.config.static_root
        if path == "/":
            path = "/index.html"
        target = (root / path.lstrip("/")).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        if not target.exists() or not target.is_file():
            target = root / "index.html"
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
                "authenticated": self.authenticated(), "version": __version__,
                "login_network": self.app.diagnostics.login_network_payload(),
            })
            return
        if not self.require_auth():
            return
        if path == "/api/status":
            self.send_json(self.app.status.status_payload())
        elif path == "/api/metrics":
            self.send_text(self.app.status.metrics())
        elif path == "/api/routes":
            self.send_text(self.app.status.routes())
        elif path == "/api/routes/download":
            self.send_file_text(self.app.status.routes(), "routes.conf")
        elif path == "/api/routes/address-list.rsc":
            name = parse_qs(parsed.query, keep_blank_values=True).get("list", [DEFAULT_LIST_NAME])[0]
            try:
                script = self.app.lists.address_list(name)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except SnapshotUnavailable as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self.send_file_text(script, f"{name}.rsc")
        elif path == "/api/logs":
            self.send_text(self.app.status.logs())
        elif path == "/api/settings":
            self.send_json(self.app.settings.settings_payload())
        elif path == "/api/tools/network":
            self.send_json(self.app.diagnostics.network_summary())
        elif path == "/api/update/status":
            force = parse_qs(parsed.query or "").get("force", ["0"])[0].strip().lower() in {"1", "true", "yes", "on"}
            self.send_json(self.app.updates.status_payload(force=force))
        elif path == "/api/lists":
            self.send_json(self.app.lists.index())
        elif path.startswith("/api/lists/"):
            try:
                payload = self.app.lists.read(path.rsplit("/", 1)[-1])
            except UnknownListError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(payload)
        else:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self, path):
        if path == "/api/login":
            if self.app.auth.is_login_limited(self.client_address[0]):
                self.send_json({"error": "too many attempts"}, HTTPStatus.TOO_MANY_REQUESTS)
                return
            data = self.read_json_or_error()
            if data is None:
                return
            token = self.app.auth.login(self.client_address[0], data.get("password", ""))
            if token:
                self.send_json({"ok": True}, headers={"Set-Cookie": cookie_header("bgp_admin_session", token)})
                return
            self.send_json({"error": "invalid password"}, HTTPStatus.UNAUTHORIZED)
            return
        if path == "/api/logout":
            self.app.auth.logout(get_cookie(self.headers, "bgp_admin_session"))
            self.send_json({"ok": True}, headers={"Set-Cookie": cookie_header("bgp_admin_session", "", max_age=0)})
            return
        if not self.require_auth():
            return
        if path in {"/api/actions/dry-run", "/api/actions/check-sources"}:
            self.send_json(self.app.actions.run_route_check("--" + path.rsplit("/", 1)[-1]))
        elif path == "/api/actions/reload":
            try:
                payload = self.app.actions.start_reload()
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
                return
            self.send_json(payload, HTTPStatus.ACCEPTED)
        elif path == "/api/update/apply":
            data = self.read_json_or_error()
            if data is None:
                return
            version = str(data.get("version") or "").strip()
            if not version:
                self.send_json({"error": "version is required"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                payload = self.app.updates.start_update(version)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except RuntimeError as exc:
                status = HTTPStatus.CONFLICT if "already running" in str(exc) else HTTPStatus.SERVICE_UNAVAILABLE
                self.send_json({"error": str(exc)}, status)
                return
            self.send_json(payload, HTTPStatus.ACCEPTED)
        elif path == "/api/tools/check-ip":
            data = self.read_json_or_error()
            if data is None:
                return
            target = str(data.get("target") or data.get("ip") or "").strip()
            try:
                payload = self.app.actions.check_target(target, self.app.diagnostics)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json(payload)
        else:
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
                self.app.settings.save_settings(values)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except OSError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_json({"ok": True, **self.app.settings.settings_payload()})
            return
        if not path.startswith("/api/lists/"):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        name = path.rsplit("/", 1)[-1]
        try:
            self.app.lists.list_path(name)
        except UnknownListError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        data = self.read_json_or_error()
        if data is None:
            return
        try:
            payload = self.app.lists.save(name, data.get("content"))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except ListWriteError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_json(payload)


class AdminHTTPServer(ThreadingHTTPServer):
    def __init__(self, address, app=None):
        self.app = AdminApplication() if app is None else app
        super().__init__(address, AdminHandler)


def main():
    if os.environ.get("ADMIN_ENABLED", "0") != "1":
        print("admin server is disabled (ADMIN_ENABLED != 1)", flush=True)
        return 0
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    if not os.environ.get("ADMIN_PASSWORD", ""):
        print("ADMIN_PASSWORD must be set when admin server is enabled", flush=True)
        return 1
    app = AdminApplication()
    app.config.static_root.mkdir(parents=True, exist_ok=True)
    updater_server.reconcile_runtime(__version__)
    server = AdminHTTPServer(("", port), app)
    print(f"admin server listening on port {port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
