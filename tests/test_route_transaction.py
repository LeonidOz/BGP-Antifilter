"""Route previews, BIRD rejection and immutable source provenance."""

import ipaddress
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bgp_antifilter.route_snapshot import explain, read_confirmed, snapshot_path
from bgp_antifilter.route_transaction import RouteManager, operation_lock
from bgp_antifilter.state_store import read_state, write_state
from tests.admin_support import admin_application


class RouteTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.app = admin_application(self.root)
        self.source = self.root / "source.txt"
        self.source.write_text("192.0.2.0/24\n", encoding="utf-8")
        for path in self.app.config.list_files.values():
            path.write_text("", encoding="utf-8")
        self.app.config.list_files["urls"].write_text("Example | " + self.source.as_uri() + "\n", encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
               "INCLUDE_GOOGLE_RANGES": "0", "FETCH_ATTEMPTS": "1", "FETCH_RETRY_DELAY": "0"}
        self.manager = RouteManager(self.app.config, env)
        self.configure = mock.patch.object(self.manager, "configure").start()
        self.addCleanup(mock.patch.stopall)

    def test_preview_applies_exact_reviewed_routes_without_refetch(self):
        self.manager.apply()
        self.source.write_text("198.51.100.0/24\n", encoding="utf-8")
        preview = self.manager.create_preview()
        self.assertEqual(preview["added"], ["198.51.100.0/24"])
        self.assertEqual(preview["removed"], ["192.0.2.0/24"])
        self.assertEqual(self.manager.preview(preview["id"], "198.51.100.7")["added"], ["198.51.100.0/24"])
        self.assertEqual(self.manager.preview(preview["id"], "198.51.100.7")["removed"], [])
        self.source.write_text("203.0.113.0/24\n", encoding="utf-8")
        with mock.patch.object(self.manager, "generate", side_effect=AssertionError("must not regenerate")):
            self.manager.apply(preview["id"])
        snapshot = read_confirmed(self.app.config.last_good_routes_file)
        self.assertEqual(snapshot["prefixes"], ["198.51.100.0/24"])
        self.assertTrue(snapshot["status"]["apply_success"])
        with self.assertRaisesRegex(ValueError, "expired"):
            self.manager.read_preview(preview["id"])

    def test_bird_rejection_restores_confirmed_state_and_corrects_metrics(self):
        self.manager.apply()
        snapshot = snapshot_path(self.app.config.last_good_routes_file).read_bytes()
        timestamp = read_state(self.app.config.status_file)["last_successful_apply_timestamp_seconds"]
        self.source.write_text("198.51.100.0/24\n", encoding="utf-8")
        self.configure.side_effect = [RuntimeError("BIRD rejected updated routes"), None]
        with self.assertRaisesRegex(RuntimeError, "BIRD rejected"):
            self.manager.apply()
        self.assertEqual(snapshot_path(self.app.config.last_good_routes_file).read_bytes(), snapshot)
        self.assertIn("192.0.2.0/24", self.app.config.routes_file.read_text())
        status = read_state(self.app.config.status_file)
        self.assertFalse(status["success"])
        self.assertTrue(status["generation_success"])
        self.assertFalse(status["apply_success"])
        self.assertEqual(status["last_successful_apply_timestamp_seconds"], timestamp)
        metrics = self.app.config.metrics_file.read_text()
        self.assertIn("bgp_antifilter_apply_success 0\n", metrics)
        self.assertIn("bgp_antifilter_update_success 0\n", metrics)
        self.assertFalse(read_state(self.app.config.runtime_file)["generation_active"])

    def test_failed_source_preserves_active_route_count(self):
        self.manager.apply()
        self.source.write_text("0.0.0.0/0\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "broad IPv4"):
            self.manager.apply()
        status = read_state(self.app.config.status_file)
        self.assertEqual(status["routes"]["final"], 1)
        self.assertFalse(status["generation_success"])
        self.assertTrue(any("broad IPv4" in item.get("error", "") for item in status["errors"]))
        self.assertEqual(self.configure.call_count, 1)

    def test_stale_expired_and_invalid_previews_are_rejected(self):
        preview = self.manager.create_preview()
        self.app.config.list_files["include-domains"].write_text("198.51.100.10\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.manager.apply(preview["id"])
        self.assertFalse(self.configure.called)
        self.app.config.list_files["include-domains"].write_text("")
        path = self.manager.previews / (preview["id"] + ".json")
        snapshot = read_state(path)
        snapshot["created_at_unix"] = 1
        write_state(path, snapshot)
        with self.assertRaisesRegex(ValueError, "expired"):
            self.manager.read_preview(preview["id"])
        with self.assertRaisesRegex(ValueError, "invalid"):
            self.manager.read_preview("../../config/settings")

    def test_provenance_and_exclusions_survive_cache_replacement(self):
        self.app.config.list_files["exclude-domains"].write_text("192.0.2.10\n", encoding="utf-8")
        self.manager.apply()
        snapshot = read_confirmed(self.app.config.last_good_routes_file)
        for cache in self.app.config.generated_dir.glob("cache_dir/*"):
            cache.write_text("203.0.113.0/24\n", encoding="utf-8")
        excluded = explain("192.0.2.10", snapshot)
        self.assertEqual(excluded["decision"], "excluded")
        self.assertEqual(excluded["exclusions"][0]["name"], "192.0.2.10")
        included = explain("192.0.2.11", snapshot)
        self.assertEqual(included["decision"], "included")
        self.assertEqual(included["sources"][0]["name"], "Example")
        self.app.config.last_good_routes_file.write_text("changed\n")
        self.assertEqual(read_confirmed(self.app.config.last_good_routes_file), {})

    def test_operation_lock_rejects_concurrent_work_and_recovers_abandoned_directory(self):
        with operation_lock(self.app.config):
            with self.assertRaisesRegex(RuntimeError, "already running"):
                with operation_lock(self.app.config):
                    self.fail("acquired twice")
        self.app.config.update_lock_dir.mkdir()
        with operation_lock(self.app.config):
            self.assertTrue(self.app.config.update_lock_dir.exists())
        self.assertFalse(self.app.config.update_lock_dir.exists())

    def test_initial_routes_are_confirmed_only_after_bird_starts(self):
        self.manager.prepare()
        self.assertFalse(self.app.config.last_good_routes_file.exists())
        self.assertIsNone(read_state(self.app.config.status_file)["apply_success"])
        self.assertIn("bgp_antifilter_update_success 0\n", self.app.config.metrics_file.read_text())
        with mock.patch("bgp_antifilter.route_transaction.subprocess.run", return_value=mock.Mock(returncode=0)):
            self.manager.confirm_startup()
        self.assertTrue(read_confirmed(self.app.config.last_good_routes_file)["status"]["apply_success"])
        self.assertTrue(read_state(self.app.config.runtime_file)["last_update_success"])
        self.assertFalse(read_state(self.app.config.runtime_file)["generation_active"])

    def test_provenance_retains_domain_to_ip_mapping(self):
        from bgp_antifilter.route_snapshot import make_snapshot
        snapshot = make_snapshot([ipaddress.ip_network("192.0.2.10/32")], {}, [{
            "kind": "domain-list-url", "name": "Video", "status": "fresh", "_text": "192.0.2.10/32\n",
            "_domain_addresses": {"video.example": ["192.0.2.10/32"]}}])
        self.assertEqual(explain("192.0.2.10", snapshot)["sources"][0]["domains"], ["video.example"])

    def test_failed_initial_confirmation_never_reports_active_routes_or_success(self):
        self.manager.prepare()
        with mock.patch("bgp_antifilter.route_transaction.subprocess.run", return_value=mock.Mock(returncode=1)), \
             mock.patch("bgp_antifilter.route_transaction.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                self.manager.confirm_startup()
        status = read_state(self.app.config.status_file)
        self.assertFalse(status["apply_success"])
        self.assertEqual(status["routes"]["final"], 0)
        self.assertFalse(read_state(self.app.config.runtime_file)["last_update_success"])
