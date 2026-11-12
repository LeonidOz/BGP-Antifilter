import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from bgp_antifilter.admin import auth
from bgp_antifilter.admin import server as admin_http
from bgp_antifilter.admin.server import AdminHTTPServer
from tests.admin_support import admin_application


class AdminHttpTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.app = admin_application(self.root)
        self.app.config.static_root.mkdir()
        (self.app.config.static_root / "index.html").write_text("<html>admin</html>", encoding="utf-8")
        self.app.config.routes_file.write_text("route 192.0.2.0/24 blackhole;\n", encoding="utf-8")
        self.app.config.last_good_routes_file.write_text("route 198.51.100.0/24 blackhole;\n", encoding="utf-8")
        self.app.config.status_file.write_text('{"routes":{"final":1}}', encoding="utf-8")
        for path in self.app.config.list_files.values():
            path.write_text("# previous\n", encoding="utf-8")
        patches = [
            mock.patch.dict(os.environ, {"ADMIN_PASSWORD": "test-password", "FETCH_TIMEOUT": "30"}),
            mock.patch.object(self.app.diagnostics, "login_network_payload", return_value={"labels": ["192.0.2.1"]}),
            mock.patch.object(self.app.actions, "run_command", return_value={"ok": True, "returncode": 0, "stdout": "", "stderr": "", "duration_seconds": 0}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.server = AdminHTTPServer(("127.0.0.1", 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, payload=None, cookie=None, raw=None):
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        if payload is not None:
            raw = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body=raw, headers=headers)
            response = connection.getresponse()
            body = response.read()
            data = json.loads(body) if body and response.getheader("Content-Type", "").startswith("application/json") else body
            return response.status, dict(response.getheaders()), data
        finally:
            connection.close()

    def login(self):
        status, headers, payload = self.request("POST", "/api/login", {"password": "test-password"})
        self.assertEqual((status, payload), (200, {"ok": True}))
        self.assertIn("HttpOnly; SameSite=Strict", headers["Set-Cookie"])
        return headers["Set-Cookie"].split(";", 1)[0]

    def test_public_status_static_fallback_and_head_keep_http_contract(self):
        code, headers, payload = self.request("GET", "/status.json")
        self.assertEqual(code, 200)
        self.assertEqual(payload["routes"], 1)
        self.assertEqual(set(payload), {"routes", "last_generation_ago", "generation_time", "uptime"})
        self.assertEqual(self.request("GET", "/api/status")[0], 401)
        self.assertEqual(self.request("GET", "/missing.js")[2], b"<html>admin</html>")
        self.assertEqual(self.request("GET", "/../outside")[0], 404)
        code, head_headers, body = self.request("HEAD", "/status.json")
        self.assertEqual(code, 200)
        self.assertEqual(body, b"")
        self.assertEqual(head_headers["Content-Length"], headers["Content-Length"])
        # Preserve the existing API HEAD behavior even for unauthenticated calls.
        self.assertEqual(self.request("HEAD", "/api/unknown")[0], 200)

    def test_real_admin_module_assets_are_served_with_javascript_mime_types(self):
        self.app.config.static_root = Path(__file__).resolve().parents[1] / "admin-ui"
        code, _headers, html = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b'<script type="module" src="/app.js"></script>', html)
        for path in ["/app.js", *["/modules/" + file.name for file in (self.app.config.static_root / "modules").glob("*.js")]]:
            with self.subTest(path=path):
                code, headers, body = self.request("GET", path)
                self.assertEqual(code, 200)
                self.assertIn(headers["Content-Type"].split(";", 1)[0], {"text/javascript", "application/javascript"})
                self.assertNotIn(b"<!doctype html", body.lower())

    def test_login_logout_expiry_and_sessions_are_isolated_between_applications(self):
        cookie = self.login()
        self.assertTrue(self.request("GET", "/api/session", cookie=cookie)[2]["authenticated"])
        token = cookie.split("=", 1)[1]
        other = admin_application(self.root / "other")
        self.assertFalse(other.auth.authenticated(token))
        self.assertEqual(self.request("GET", "/api/settings", cookie=cookie)[0], 200)
        self.assertEqual(self.request("POST", "/api/logout", cookie=cookie)[1]["Set-Cookie"],
                         auth.cookie_header("bgp_admin_session", "", max_age=0))
        self.assertEqual(self.request("GET", "/api/settings", cookie=cookie)[0], 401)
        cookie = self.login()
        self.app.auth.sessions[cookie.split("=", 1)[1]]["created_at"] = time.time() - 86401
        self.assertEqual(self.request("GET", "/api/settings", cookie=cookie)[0], 401)

    def test_login_rate_limit_and_invalid_json_keep_error_responses(self):
        self.assertEqual(self.request("POST", "/api/login", raw=b"{")[2], {"error": "invalid json"})
        for _ in range(8):
            self.assertEqual(self.request("POST", "/api/login", {"password": "wrong"})[0], 401)
        code, _headers, data = self.request("POST", "/api/login", {"password": "test-password"})
        self.assertEqual((code, data), (429, {"error": "too many attempts"}))

    def test_list_writes_keep_backups_newlines_and_validation(self):
        cookie = self.login()
        code, _headers, payload = self.request("PUT", "/api/lists/urls", {"content": "новый список"}, cookie)
        self.assertEqual(code, 200)
        self.assertEqual(self.app.config.list_files["urls"].read_text(encoding="utf-8"), "новый список\n")
        self.assertEqual(Path(payload["backup"]).read_text(encoding="utf-8"), "# previous\n")
        self.assertEqual(payload["bytes"], len("новый список\n".encode("utf-8")))
        for content in (None, 42, "bad\x00value"):
            self.assertEqual(self.request("PUT", "/api/lists/urls", {"content": content}, cookie)[0], 400)
        self.assertEqual(self.request("PUT", "/api/lists/missing", raw=b"{", cookie=cookie)[0], 404)
        self.assertEqual(self.request("GET", "/api/lists/missing", cookie=cookie)[0], 404)

    def test_settings_validation_persistence_and_instance_isolation(self):
        cookie = self.login()
        self.assertEqual(self.request("PUT", "/api/settings", {"values": []}, cookie)[0], 400)
        self.assertEqual(self.request("PUT", "/api/settings", {"values": {"MT_IP": "bad"}}, cookie)[0], 400)
        code, _headers, payload = self.request("PUT", "/api/settings", {"values": {"FETCH_TIMEOUT": "45"}}, cookie)
        self.assertEqual(code, 200)
        self.assertEqual(payload["values"]["FETCH_TIMEOUT"], "45")
        self.assertIn("FETCH_TIMEOUT=45", self.app.config.settings_env_file.read_text(encoding="utf-8"))
        other = admin_application(self.root / "other")
        self.assertNotEqual(other.settings.effective_settings()["FETCH_TIMEOUT"], "45")
        self.app.updates.cache["payload"] = {"ok": True}
        self.assertIsNone(other.updates.cache["payload"])
        self.assertIsNot(other.actions.reload_lock, self.app.actions.reload_lock)

    def test_status_and_route_export_use_existing_payloads_and_confirmed_snapshot(self):
        cookie = self.login()
        code, _headers, payload = self.request("GET", "/api/status", cookie=cookie)
        self.assertEqual(code, 200)
        self.assertEqual(set(payload), {"version", "status", "runtime", "metrics", "routes_file_count", "bird", "bgp", "reload_result"})
        code, headers, body = self.request("GET", "/api/routes/address-list.rsc?list=vpn", cookie=cookie)
        self.assertEqual(code, 200)
        self.assertIn("198.51.100.0/24", body.decode("utf-8"))
        self.assertNotIn("192.0.2.0/24", body.decode("utf-8"))
        self.assertEqual(headers["Content-Disposition"], 'attachment; filename="vpn.rsc"')
        self.app.config.update_lock_dir.mkdir()
        self.assertEqual(self.request("GET", "/api/routes/address-list.rsc", cookie=cookie)[0], 503)
        self.assertEqual(self.request("GET", "/api/routes/address-list.rsc?list=", cookie=cookie)[0], 400)

    def test_route_checks_attach_status_and_reload_keeps_accepted_and_conflict_codes(self):
        cookie = self.login()
        self.app.actions.run_command.return_value["stdout"] = '{"sources":[],"routes":{"final":1}}'
        for mode in ("dry-run", "check-sources"):
            code, _headers, payload = self.request("POST", "/api/actions/" + mode, cookie=cookie)
            self.assertEqual(code, 200)
            self.assertEqual(payload["status"]["routes"]["final"], 1)
            self.app.actions.run_command.assert_called_with(["/update-routes.py", "--" + mode], timeout=300)
        with mock.patch.object(self.app.actions, "start_reload", return_value={"accepted": True}):
            self.assertEqual(self.request("POST", "/api/actions/reload", cookie=cookie)[0], 202)
        with mock.patch.object(self.app.actions, "start_reload", side_effect=RuntimeError("reload already running")):
            self.assertEqual(self.request("POST", "/api/actions/reload", cookie=cookie)[0], 409)

    def test_target_results_and_updater_failures_keep_response_shapes_and_codes(self):
        cookie = self.login()
        self.assertEqual(self.request("POST", "/api/tools/check-ip", {"target": ""}, cookie)[0], 400)
        with mock.patch.object(self.app.diagnostics, "resolve_ipv4_targets", return_value=(["192.0.2.1", "192.0.2.2"], None)):
            code, _headers, payload = self.request("POST", "/api/tools/check-ip", {"ip": "example.test"}, cookie)
        self.assertEqual(code, 200)
        self.assertEqual(payload["addresses"], ["192.0.2.1", "192.0.2.2"])
        self.assertEqual(len(payload["results"]), 2)
        self.assertIsNone(payload["result"])
        self.assertEqual(self.request("POST", "/api/update/apply", {}, cookie)[0], 400)
        for error, expected in ((ValueError("bad version"), 400), (RuntimeError("update already running"), 409),
                                (RuntimeError("not available"), 503)):
            with mock.patch.object(self.app.updates, "start_update", side_effect=error):
                self.assertEqual(self.request("POST", "/api/update/apply", {"version": "1.0.0"}, cookie)[0], expected)
        for method in ("GET", "POST", "PUT"):
            self.assertEqual(self.request(method, "/api/unknown", cookie=cookie)[0], 404)

    def test_main_keeps_disabled_and_missing_password_startup_guards(self):
        with mock.patch.object(admin_http, "AdminHTTPServer") as server:
            with mock.patch.dict(os.environ, {"ADMIN_ENABLED": "0"}):
                self.assertEqual(admin_http.main(), 0)
            with mock.patch.dict(os.environ, {"ADMIN_ENABLED": "1", "ADMIN_PASSWORD": ""}):
                self.assertEqual(admin_http.main(), 1)
            server.assert_not_called()

    def test_main_keeps_port_binding_and_update_reconciliation(self):
        with mock.patch.dict(os.environ, {"ADMIN_ENABLED": "1", "ADMIN_PORT": "18080"}):
            with mock.patch.object(admin_http, "AdminApplication", return_value=self.app):
                with mock.patch.object(admin_http.updater_server, "reconcile_runtime") as reconcile:
                    with mock.patch.object(admin_http, "AdminHTTPServer") as server:
                        server.return_value.serve_forever.side_effect = KeyboardInterrupt
                        self.assertEqual(admin_http.main(), 0)
        server.assert_called_once_with(("", 18080), self.app)
        reconcile.assert_called_once_with(admin_http.__version__)


if __name__ == "__main__":
    unittest.main()
