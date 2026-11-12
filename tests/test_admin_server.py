import tempfile
import unittest
import errno
import socket
from pathlib import Path
from unittest import mock

import os
from http import HTTPStatus
from types import SimpleNamespace

from bgp_antifilter import __version__, dns_resolver
from bgp_antifilter.admin import actions, diagnostics, lists, settings, status, storage, updates
from bgp_antifilter.admin.server import AdminHandler
from tests.admin_support import admin_application


class AdminServerHelperTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = admin_application(Path(temporary.name))

    def test_successful_polls_are_quiet_but_errors_and_writes_are_logged(self):
        handler = object.__new__(AdminHandler)
        handler.server = SimpleNamespace(app=self.app)
        handler.requestline = "GET /api/status HTTP/1.1"
        handler.command = "GET"
        handler.log_message = mock.Mock()
        handler.log_request(200)
        handler.log_message.assert_not_called()
        handler.log_request(503)
        handler.log_message.assert_called_once()
        handler.command = "POST"
        handler.log_request(200)
        self.assertEqual(handler.log_message.call_count, 2)

    def test_parse_resolv_conf_extracts_nameservers_and_search(self):
        payload = diagnostics.parse_resolv_conf(
            "nameserver 1.1.1.1\n"
            "nameserver 8.8.8.8\n"
            "search lan example.local\n"
            "domain corp.local\n"
        )

        self.assertEqual(payload["nameservers"], ["1.1.1.1", "8.8.8.8"])
        self.assertEqual(payload["search"], ["lan", "example.local"])
        self.assertEqual(payload["domain"], "corp.local")

    def test_parse_metrics_reads_numeric_values(self):
        metrics = status.parse_metrics(
            "# comment\n"
            "bgp_antifilter_routes_total 123\n"
            'bgp_antifilter_source_status_total{status="fresh"} 4\n'
        )

        self.assertEqual(metrics["bgp_antifilter_routes_total"], 123)
        self.assertEqual(metrics['bgp_antifilter_source_status_total{status="fresh"}'], 4)

    def test_short_duration_formats_compact_values(self):
        self.assertEqual(status.short_duration(0), "0s")
        self.assertEqual(status.short_duration(59), "59s")
        self.assertEqual(status.short_duration(61), "1m1s")
        self.assertEqual(status.short_duration(3660), "1h1m")
        self.assertEqual(status.short_duration(90000), "1d1h")

    def test_public_status_payload_returns_compact_public_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            status_file = Path(tmp) / "status.json"
            status_file.write_text(
                "{"
                '"updated_at_unix": 1700000000,'
                '"duration_seconds": 125,'
                '"routes": {"final": 321}'
                "}",
                encoding="utf-8",
            )
            old_status_file = self.app.config.status_file
            old_started_at = self.app.status.started_at
            self.app.config.status_file = status_file
            self.app.status.started_at = 1699996400
            try:
                payload = self.app.status.public_status_payload(now=1700003600)
            finally:
                self.app.config.status_file = old_status_file
                self.app.status.started_at = old_started_at

        self.assertEqual(payload["routes"], 321)
        self.assertEqual(payload["last_generation_ago"], "1h")
        self.assertEqual(payload["generation_time"], "2m5s")
        self.assertEqual(payload["uptime"], "2h")

    def test_public_status_payload_uses_defaults_when_status_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_status_file = self.app.config.status_file
            old_started_at = self.app.status.started_at
            self.app.config.status_file = Path(tmp) / "missing.json"
            self.app.status.started_at = 1700000000
            try:
                payload = self.app.status.public_status_payload(now=1700000005)
            finally:
                self.app.config.status_file = old_status_file
                self.app.status.started_at = old_started_at

        self.assertEqual(payload["routes"], 0)
        self.assertIsNone(payload["last_generation_ago"])
        self.assertIsNone(payload["generation_time"])
        self.assertEqual(payload["uptime"], "5s")

    def test_backup_and_atomic_write_preserve_previous_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_generated = self.app.config.generated_dir
            self.app.config.generated_dir = root / "generated"
            target = root / "lists.txt"
            target.write_text("old\n", encoding="utf-8")

            try:
                backup = self.app.lists.backup_file(target)
                storage.write_text_atomic(target, "new\n")
            finally:
                self.app.config.generated_dir = old_generated

            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            self.assertEqual(Path(backup).read_text(encoding="utf-8"), "old\n")

    def test_atomic_write_falls_back_when_replace_target_is_busy(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "include-domains.txt"
            target.write_text("old\n", encoding="utf-8")

            with mock.patch.object(Path, "replace", side_effect=OSError(errno.EBUSY, "busy")):
                storage.write_text_atomic(target, "new\n")

            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            self.assertFalse((Path(tmp) / "include-domains.txt.tmp").exists())

    def test_run_command_reports_missing_executable(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("missing command")):
            result = self.app.actions.run_command(["missing-command"], timeout=1)

        self.assertFalse(result["ok"])
        self.assertIsNone(result["returncode"])
        self.assertEqual(result["stdout"], "")
        self.assertIn("missing command", result["stderr"])

    def test_resolve_ipv4_targets_accepts_ipv4_address(self):
        addresses, error = self.app.diagnostics.resolve_ipv4_targets("192.0.2.10")

        self.assertIsNone(error)
        self.assertEqual(addresses, ["192.0.2.10"])

    def test_resolve_ipv4_targets_rejects_empty_target(self):
        addresses, error = self.app.diagnostics.resolve_ipv4_targets("")

        self.assertEqual(addresses, [])
        self.assertIn("required", error)

    def test_parse_command_status_reads_final_status_from_command_output(self):
        stdout = (
            '{"stage":"source","url":"https://ya.ru/list.txt","status":"failed"}\n'
            '{\n'
            '  "success": false,\n'
            '  "sources": [\n'
            '    {"kind": "url", "url": "https://ya.ru/list.txt", "status": "failed", "error": "HTTP Error 404"}\n'
            '  ],\n'
            '  "routes": {"final": 0}\n'
            '}\n'
        )

        status = actions.parse_command_status(stdout)

        self.assertIsNotNone(status)
        self.assertFalse(status["success"])
        self.assertEqual(status["sources"][0]["url"], "https://ya.ru/list.txt")
        self.assertEqual(status["sources"][0]["status"], "failed")

    def test_read_json_or_error_rejects_invalid_json(self):
        handler = object.__new__(AdminHandler)
        handler.server = SimpleNamespace(app=self.app)
        handler.headers = {"Content-Length": "1"}
        handler.rfile = mock.Mock()
        handler.rfile.read.return_value = b"{"

        with mock.patch.object(handler, "send_json") as send_json:
            result = handler.read_json_or_error()

        self.assertIsNone(result)
        send_json.assert_called_once_with({"error": "invalid json"}, HTTPStatus.BAD_REQUEST)

    def test_do_get_serves_public_status_without_auth(self):
        handler = object.__new__(AdminHandler)
        handler.server = SimpleNamespace(app=self.app)
        handler.path = "/status.json"

        with mock.patch.object(self.app.status, "public_status_payload", return_value={"routes": 1}) as payload_mock:
            with mock.patch.object(handler, "send_json") as send_json:
                handler.do_GET()

        payload_mock.assert_called_once_with()
        send_json.assert_called_once_with({"routes": 1})

    def test_validate_setting_normalizes_bool_and_numbers(self):
        self.assertEqual(settings.validate_setting("INCLUDE_GOOGLE_RANGES", "true"), "1")
        self.assertEqual(settings.validate_setting("REQUIRE_ALL_URL_SOURCES", "yes"), "1")
        self.assertEqual(settings.validate_setting("FETCH_RETRY_DELAY", "2.5"), "2.5")
        self.assertEqual(settings.validate_setting("MIN_PREFIX_LENGTH", "24"), "24")
        self.assertEqual(
            settings.validate_setting("DNS_RESOLVERS", "1.1.1.1, 8.8.8.8"),
            "1.1.1.1,8.8.8.8",
        )

    def test_validate_setting_allows_empty_custom_dns_list(self):
        self.assertEqual(settings.validate_setting("DNS_RESOLVERS", ""), "")

    def test_validate_setting_rejects_invalid_ipv4(self):
        with self.assertRaises(ValueError):
            settings.validate_setting("MT_IP", "999.1.1.1")

    def test_save_settings_writes_json_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_settings = self.app.config.settings_file
            old_env = self.app.config.settings_env_file
            self.app.config.settings_file = root / "settings.json"
            self.app.config.settings_env_file = root / "settings.env"

            try:
                values = self.app.settings.save_settings({
                    "CACHE_MAX_AGE": "3600",
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "DNS_RESOLVERS": "1.1.1.1 8.8.8.8",
                    "BGP_PROTOCOL": "mt_main",
                })
            finally:
                self.app.config.settings_file = old_settings
                self.app.config.settings_env_file = old_env

            self.assertEqual(values["CACHE_MAX_AGE"], "3600")
            self.assertEqual(values["INCLUDE_GOOGLE_RANGES"], "0")
            self.assertEqual(values["DNS_RESOLVERS"], "1.1.1.1,8.8.8.8")
            self.assertIn("BGP_PROTOCOL=mt_main", (root / "settings.env").read_text(encoding="utf-8"))

    def test_resolve_ipv4_targets_uses_effective_custom_dns(self):
        with mock.patch.object(self.app.settings, "effective_settings", return_value={
            "DNS_RESOLVERS": "1.1.1.1,8.8.8.8",
            "DNS_RESOLVE_TIMEOUT": "2.5",
        }):
            with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", return_value=["203.0.113.10"]) as resolve_mock:
                addresses, error = self.app.diagnostics.resolve_ipv4_targets("example.com")

        self.assertIsNone(error)
        self.assertEqual(addresses, ["203.0.113.10"])
        resolve_mock.assert_called_once_with(
            "example.com",
            nameservers=["1.1.1.1", "8.8.8.8"],
            timeout=2.5,
        )

    def test_resolve_ipv4_targets_returns_custom_dns_error(self):
        with mock.patch.object(self.app.settings, "effective_settings", return_value={
            "DNS_RESOLVERS": "1.1.1.1",
            "DNS_RESOLVE_TIMEOUT": "3",
        }):
            with mock.patch.object(
                dns_resolver,
                "resolve_ipv4_addresses",
                side_effect=socket.gaierror(socket.EAI_NONAME, "Name or service not known"),
            ):
                addresses, error = self.app.diagnostics.resolve_ipv4_targets("missing.example")

        self.assertEqual(addresses, [])
        self.assertIn("Name or service not known", error)

    def test_save_settings_keeps_only_values_different_from_environment(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CACHE_MAX_AGE": "604800"}, clear=False):
            root = Path(tmp)
            old_settings = self.app.config.settings_file
            old_env = self.app.config.settings_env_file
            self.app.config.settings_file = root / "settings.json"
            self.app.config.settings_env_file = root / "settings.env"

            try:
                values = self.app.settings.save_settings({
                    "CACHE_MAX_AGE": "604800",
                    "FETCH_TIMEOUT": "45",
                })
            finally:
                self.app.config.settings_file = old_settings
                self.app.config.settings_env_file = old_env

            self.assertNotIn("CACHE_MAX_AGE", values)
            self.assertEqual(values["FETCH_TIMEOUT"], "45")
            self.assertNotIn("CACHE_MAX_AGE", (root / "settings.env").read_text(encoding="utf-8"))

    def test_settings_payload_marks_overridden_only_when_value_differs(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CACHE_MAX_AGE": "604800"}, clear=False):
            root = Path(tmp)
            old_settings = self.app.config.settings_file
            self.app.config.settings_file = root / "settings.json"
            self.app.config.settings_file.write_text(
                '{"values": {"CACHE_MAX_AGE": "604800", "FETCH_TIMEOUT": "45"}}',
                encoding="utf-8",
            )

            try:
                payload = self.app.settings.settings_payload()
            finally:
                self.app.config.settings_file = old_settings

            items = {
                item["key"]: item
                for section in payload["sections"]
                for item in section["items"]
            }
            self.assertFalse(items["CACHE_MAX_AGE"]["overridden"])
            self.assertTrue(items["FETCH_TIMEOUT"]["overridden"])

    def test_settings_payload_hides_google_ranges_from_settings_sections(self):
        payload = self.app.settings.settings_payload()

        visible_keys = {
            item["key"]
            for section in payload["sections"]
            for item in section["items"]
        }

        self.assertNotIn("INCLUDE_GOOGLE_RANGES", visible_keys)
        self.assertEqual(payload["values"]["INCLUDE_GOOGLE_RANGES"], self.app.settings.effective_settings()["INCLUDE_GOOGLE_RANGES"])

    def test_start_reload_starts_background_thread(self):
        thread = mock.Mock()
        thread.is_alive.return_value = False

        with mock.patch.object(self.app.actions, "reload_runtime_active", return_value=False):
            with mock.patch.object(self.app.actions, "reload_thread", thread):
                with mock.patch.object(actions.threading, "Thread") as thread_cls:
                    payload = self.app.actions.start_reload()

        self.assertTrue(payload["accepted"])
        thread_cls.return_value.start.assert_called_once_with()

    def test_start_reload_ignores_reload_result_write_errors(self):
        thread = mock.Mock()
        thread.is_alive.return_value = False

        with mock.patch.object(self.app.actions, "reload_runtime_active", return_value=False):
            with mock.patch.object(self.app.actions, "reload_thread", thread):
                with mock.patch.object(self.app.actions, "write_reload_result", side_effect=OSError("permission denied")):
                    with mock.patch.object(actions.threading, "Thread") as thread_cls:
                        payload = self.app.actions.start_reload()

        self.assertTrue(payload["accepted"])
        thread_cls.return_value.start.assert_called_once_with()

    def test_start_reload_rejects_when_generation_is_already_active(self):
        with mock.patch.object(self.app.actions, "reload_runtime_active", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "reload already running"):
                self.app.actions.start_reload()

    def test_visible_runtime_state_marks_pending_reload_as_active(self):
        thread = mock.Mock()
        thread.is_alive.return_value = True

        with mock.patch.object(self.app.actions, "reload_thread", thread):
            payload = self.app.actions.visible_runtime_state({})

        self.assertTrue(payload["generation_active"])
        self.assertEqual(payload["generation_kind"], "manual")
        self.assertEqual(payload["generation_stage"], "bootstrap")

    def test_visible_runtime_state_keeps_existing_active_runtime(self):
        thread = mock.Mock()
        thread.is_alive.return_value = True
        runtime = {"generation_active": True, "generation_kind": "startup"}

        with mock.patch.object(self.app.actions, "reload_thread", thread):
            payload = self.app.actions.visible_runtime_state(runtime)

        self.assertEqual(payload["generation_kind"], "startup")

    def test_reconcile_runtime_state_clears_stale_active_runtime_without_lock_or_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_file = Path(tmp) / "runtime.json"
            lock_dir = Path(tmp) / "update.lock"
            runtime_file.write_text(
                '{'
                '"generation_active": true,'
                '"generation_kind": "startup",'
                '"generation_message": "Starting with previous routes while refreshing in background",'
                '"generation_started_at_unix": 123,'
                '"generation_stage": "bootstrap",'
                '"generation_stage_message": "Using previous route snapshot until refresh completes"'
                '}',
                encoding="utf-8",
            )

            old_runtime = self.app.config.runtime_file
            old_lock_dir = self.app.config.update_lock_dir
            old_thread = self.app.actions.reload_thread
            self.app.config.runtime_file = runtime_file
            self.app.config.update_lock_dir = lock_dir
            self.app.actions.reload_thread = None
            try:
                payload = self.app.actions.reconcile_runtime_state(storage.json_load(runtime_file, {}))
                stored = storage.json_load(runtime_file, {})
            finally:
                self.app.config.runtime_file = old_runtime
                self.app.config.update_lock_dir = old_lock_dir
                self.app.actions.reload_thread = old_thread

        self.assertFalse(payload["generation_active"])
        self.assertEqual(payload["generation_kind"], "")
        self.assertEqual(payload["generation_stage"], "")
        self.assertFalse(stored["generation_active"])

    def test_reconcile_runtime_state_keeps_active_runtime_when_lock_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_file = Path(tmp) / "runtime.json"
            lock_dir = Path(tmp) / "update.lock"
            runtime_file.write_text('{"generation_active": true, "generation_kind": "startup"}', encoding="utf-8")
            lock_dir.mkdir()

            old_runtime = self.app.config.runtime_file
            old_lock_dir = self.app.config.update_lock_dir
            old_thread = self.app.actions.reload_thread
            self.app.config.runtime_file = runtime_file
            self.app.config.update_lock_dir = lock_dir
            self.app.actions.reload_thread = None
            try:
                payload = self.app.actions.reconcile_runtime_state(storage.json_load(runtime_file, {}))
            finally:
                self.app.config.runtime_file = old_runtime
                self.app.config.update_lock_dir = old_lock_dir
                self.app.actions.reload_thread = old_thread

        self.assertTrue(payload["generation_active"])
        self.assertEqual(payload["generation_kind"], "startup")

    def test_external_ip_summary_parses_success_payload(self):
        body = (
            '{"status":"success","query":"203.0.113.10","country":"Testland",'
            '"city":"Test City","timezone":"UTC","isp":"Example ISP"}'
        ).encode("utf-8")
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = body
        response.__exit__.return_value = False

        with mock.patch("urllib.request.urlopen", return_value=response):
            payload = diagnostics.external_ip_summary()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["query"], "203.0.113.10")
        self.assertEqual(payload["isp"], "Example ISP")

    def test_external_ip_summary_returns_error_payload_on_failure(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("network down")):
            payload = diagnostics.external_ip_summary()

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["source"], "ip-api.com")
        self.assertIn("network down", payload["error"])

    def test_parse_semver_accepts_plain_and_v_prefixed_versions(self):
        self.assertEqual(updates.parse_semver("0.2.6"), (0, 2, 6))
        self.assertEqual(updates.parse_semver("v1.10.3"), (1, 10, 3))

    def test_github_latest_release_extracts_expected_fields(self):
        body = (
            '{"tag_name":"v0.2.7","html_url":"https://github.com/LeonidOz/BGP-Antifilter/releases/tag/v0.2.7",'
            '"published_at":"2026-06-15T10:00:00Z","name":"Release v0.2.7"}'
        ).encode("utf-8")
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = body
        response.__exit__.return_value = False

        with mock.patch("urllib.request.urlopen", return_value=response):
            payload = updates.github_latest_release()

        self.assertEqual(payload["version"], "0.2.7")
        self.assertEqual(payload["tag_name"], "v0.2.7")
        self.assertEqual(payload["name"], "Release v0.2.7")

    def test_update_status_payload_reports_available_release(self):
        old_cache = dict(self.app.updates.cache)
        self.app.updates.cache["checked_at"] = 0.0
        self.app.updates.cache["payload"] = None

        try:
            with mock.patch.object(updates, "github_latest_release", return_value={
                "version": "9.9.9",
                "tag_name": "v9.9.9",
                "html_url": "https://github.com/LeonidOz/BGP-Antifilter/releases/tag/v9.9.9",
                "published_at": "2026-06-15T10:00:00Z",
                "name": "Release v9.9.9",
            }):
                payload = self.app.updates.update_status_payload(force=True)
        finally:
            self.app.updates.cache.clear()
            self.app.updates.cache.update(old_cache)

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["update_available"])
        self.assertEqual(payload["latest_version"], "9.9.9")
        self.assertEqual(payload["current_version"], __version__)

    def test_update_status_payload_returns_error_when_release_check_fails(self):
        old_cache = dict(self.app.updates.cache)
        self.app.updates.cache["checked_at"] = 0.0
        self.app.updates.cache["payload"] = None

        try:
            with mock.patch.object(updates, "github_latest_release", side_effect=OSError("offline")):
                payload = self.app.updates.update_status_payload(force=True)
        finally:
            self.app.updates.cache.clear()
            self.app.updates.cache.update(old_cache)

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["update_available"])
        self.assertIn("offline", payload["error"])


if __name__ == "__main__":
    unittest.main()
