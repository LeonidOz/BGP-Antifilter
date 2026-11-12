import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bgp_antifilter import runtime_state, update_routes, updater_server
from bgp_antifilter.state_store import read_state, write_state


class RuntimeStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "runtime.json"
        self.status = self.root / "status.json"
        self.network = self.root / "network.json"
        self.env = {
            "RUNTIME_FILE": str(self.path),
            "STATUS_FILE": str(self.status),
            "NETWORK_STATUS_FILE": str(self.network),
            "UPDATE_INTERVAL": "1800",
            "ADMIN_ENABLED": "1",
            "ADMIN_PORT": "8080",
        }
        patch = mock.patch.dict(os.environ, self.env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_initial_schedule_keeps_existing_schema_and_nullable_fields(self):
        write_state(self.network, {"bird_ip_assigned": True})
        data = runtime_state.write_schedule(2800, now=1000)
        self.assertEqual(data, {
            "updated_at_unix": 1000,
            "update_interval_seconds": 1800,
            "next_scheduled_update_unix": 2800,
            "admin_enabled": True,
            "admin_port": 8080,
            **runtime_state.IDLE_GENERATION,
            "startup_snapshot_used": False,
            "startup_snapshot_size_bytes": 0,
            "startup_snapshot_mtime_unix": None,
            "startup_snapshot_age_seconds": None,
            "last_update_reason": "",
            "last_update_message": "",
            "last_update_success": None,
            "last_update_finished_at_unix": None,
            "degraded": False,
            "degraded_reason": "",
            "network": {"bird_ip_assigned": True},
        })

    def test_scheduler_preserves_generation_snapshot_and_result_but_replaces_other_fields(self):
        previous = {
            "generation_active": True, "generation_current_name": "example.test",
            "generation_progress_percent": 55, "startup_snapshot_used": True,
            "startup_snapshot_age_seconds": 42, "last_update_success": False,
            "degraded": True, "degraded_reason": "old snapshot", "obsolete": True,
        }
        write_state(self.path, previous)
        with mock.patch.dict(os.environ, {"RUNTIME_PRESERVE_STATE": "1"}):
            data = runtime_state.write_schedule(3000, now=1000)
        self.assertNotIn("obsolete", data)
        self.assertEqual({key: data[key] for key in previous if key != "obsolete"},
                         {key: value for key, value in previous.items() if key != "obsolete"})
        self.assertEqual(data["next_scheduled_update_unix"], 3000)
        self.assertEqual(data["updated_at_unix"], 1000)

    def test_reload_keeps_next_update_while_active_and_reschedules_on_completion(self):
        write_state(self.path, {"next_scheduled_update_unix": 9000, "custom": "keep"})
        with mock.patch.dict(os.environ, {
            "generation_active": "1", "generation_kind": "manual", "generation_started_at": "1000",
            "LAST_UPDATE_FINISHED_AT_UNIX": "1100", "LAST_UPDATE_SUCCESS": "1",
            "STARTUP_SNAPSHOT_USED": "1", "STARTUP_SNAPSHOT_SIZE_BYTES": "512",
            "STARTUP_SNAPSHOT_MTIME_UNIX": "900", "STARTUP_SNAPSHOT_AGE_SECONDS": "100",
        }):
            active = runtime_state.write_reload(now=1000)
            self.assertEqual(active["next_scheduled_update_unix"], 9000)
            self.assertTrue(active["generation_active"])
            self.assertEqual(active["generation_started_at_unix"], 1000)
            self.assertEqual(active["startup_snapshot_age_seconds"], 100)
            with mock.patch.dict(os.environ, {"generation_active": "0", "generation_started_at": ""}):
                done = runtime_state.write_reload(now=1100)
        self.assertFalse(done["generation_active"])
        self.assertIsNone(done["generation_started_at_unix"])
        self.assertTrue(done["last_update_success"])
        self.assertEqual(done["next_scheduled_update_unix"], 2900)
        self.assertEqual(done["custom"], "keep")

    def test_reload_uses_previous_interval_and_port_if_not_exported(self):
        write_state(self.path, {"update_interval_seconds": 60, "admin_port": 9000})
        os.environ.pop("UPDATE_INTERVAL")
        os.environ.pop("ADMIN_PORT")
        with mock.patch.dict(os.environ, {"LAST_UPDATE_FINISHED_AT_UNIX": "1000", "LAST_UPDATE_SUCCESS": "0"}):
            data = runtime_state.write_reload(now=1000)
        self.assertEqual(data["next_scheduled_update_unix"], 1060)
        self.assertEqual(data["admin_port"], 9000)
        self.assertFalse(data["last_update_success"])

    def test_generator_progress_preserves_schedule_and_snapshot_and_clamps_percent(self):
        write_state(self.path, {"next_scheduled_update_unix": 9000, "startup_snapshot_used": True})
        update_routes.write_runtime_progress("building-routes", "Building", percent=150, items_done=2, items_total=3)
        data = read_state(self.path)
        self.assertEqual(data["next_scheduled_update_unix"], 9000)
        self.assertTrue(data["startup_snapshot_used"])
        self.assertEqual(data["generation_progress_percent"], 100)
        self.assertEqual(data["generation_items_done"], 2)

    def test_progress_remains_best_effort_on_io_failure(self):
        with mock.patch.object(runtime_state, "patch_state", side_effect=OSError("read-only")):
            update_routes.write_runtime_progress("completed", "Done", active=False)

    def test_degraded_status_retains_route_snapshot_and_deduplicates_errors(self):
        write_state(self.status, {"routes": {"final": 42}, "sources": [{"kind": "url"}], "run_reason": "scheduled"})
        with mock.patch.dict(os.environ, {"DEGRADED_REASON": "BIRD rejected updated routes"}):
            runtime_state.write_degraded_status(now=1000)
            data = runtime_state.write_degraded_status(now=1100)
        self.assertFalse(data["success"])
        self.assertTrue(data["degraded"])
        self.assertEqual(data["routes"], {"final": 42})
        self.assertEqual(data["sources"], [{"kind": "url"}])
        self.assertEqual(data["run_reason"], "scheduled")
        self.assertEqual(len(data["errors"]), 1)
        self.assertEqual(data["updated_at"], "1970-01-01T00:18:20Z")

    def test_reconcile_preserves_new_fields_written_since_admin_read(self):
        stale = {"generation_active": True, "next_scheduled_update_unix": 100}
        write_state(self.path, {**stale, "next_scheduled_update_unix": 200, "custom": True})
        result = runtime_state.reconcile_generation(self.path, stale, lambda: False)
        self.assertFalse(result["generation_active"])
        self.assertEqual(result["next_scheduled_update_unix"], 200)
        self.assertTrue(result["custom"])

    def test_reconcile_rechecks_reload_lock_before_clearing_active_generation(self):
        current = {"generation_active": True, "generation_kind": "scheduled"}
        write_state(self.path, current)
        active = mock.Mock(side_effect=[False, True])
        self.assertEqual(runtime_state.reconcile_generation(self.path, current, active), current)
        self.assertEqual(read_state(self.path), current)

    def test_update_reconcile_does_not_complete_a_newer_target(self):
        write_state(self.path, {"active": True, "target_version": "2.0.0"})
        with mock.patch.object(updater_server, "UPDATE_RUNTIME_FILE", self.path):
            with mock.patch.object(updater_server, "runtime_payload", return_value={"active": True, "target_version": "1.0.0"}):
                data = updater_server.reconcile_runtime("1.0.0")
        self.assertTrue(data["active"])
        self.assertEqual(data["target_version"], "2.0.0")

    def test_cli_next_update_handles_missing_corrupt_and_present_state(self):
        for content, expected in ((None, "\n"), ("{bad", "\n"), (json.dumps({"next_scheduled_update_unix": 42}), "42\n")):
            with self.subTest(content=content):
                if content is not None:
                    self.path.write_text(content, encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(runtime_state.main(["next-update"]), 0)
                self.assertEqual(output.getvalue(), expected)


if __name__ == "__main__":
    unittest.main()
