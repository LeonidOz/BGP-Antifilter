import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from bgp_antifilter import route_runtime


def run_main(argv):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        exit_code = route_runtime.main(argv)
    return exit_code, stdout.getvalue().strip()


class RouteRuntimeTests(unittest.TestCase):
    def test_startup_strategy_uses_background_refresh_for_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = Path(tmp) / "routes.conf"
            routes.write_text("route 192.0.2.0/24 blackhole;\n", encoding="utf-8")

            strategy = route_runtime.startup_strategy(routes)

        self.assertEqual(strategy["mode"], "background-refresh")
        self.assertEqual(strategy["generation_kind"], "startup")
        self.assertTrue(strategy["startup_snapshot_used"])
        self.assertGreater(strategy["startup_snapshot_size_bytes"], 0)
        self.assertIsInstance(strategy["startup_snapshot_mtime_unix"], int)

    def test_startup_strategy_requires_blocking_bootstrap_without_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = Path(tmp) / "routes.conf"

            strategy = route_runtime.startup_strategy(routes)

        self.assertEqual(strategy["mode"], "blocking-bootstrap")
        self.assertEqual(strategy["generation_kind"], "initial")
        self.assertFalse(strategy["startup_snapshot_used"])
        self.assertEqual(strategy["startup_snapshot_size_bytes"], 0)
        self.assertIsNone(strategy["startup_snapshot_mtime_unix"])

    def test_startup_strategy_requires_blocking_bootstrap_for_empty_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = Path(tmp) / "routes.conf"
            routes.write_text("", encoding="utf-8")

            strategy = route_runtime.startup_strategy(routes)

        self.assertEqual(strategy["mode"], "blocking-bootstrap")
        self.assertFalse(strategy["startup_snapshot_used"])

    def test_snapshot_metadata_reports_age_for_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = Path(tmp) / "routes.conf"
            routes.write_text("route 192.0.2.0/24 blackhole;\n", encoding="utf-8")

            metadata = route_runtime.snapshot_metadata(routes, now=routes.stat().st_mtime + 42)

        self.assertTrue(metadata["startup_snapshot_used"])
        self.assertEqual(metadata["startup_snapshot_age_seconds"], 42)

    def test_update_message_covers_startup_scheduled_and_manual_modes(self):
        self.assertEqual(
            route_runtime.update_message("startup"),
            "Refreshing routes after startup using previous route snapshot",
        )
        self.assertEqual(route_runtime.update_message("scheduled"), "Running scheduled route update")
        self.assertEqual(route_runtime.update_message("manual"), "Running manual route update")
        self.assertEqual(route_runtime.update_message("unexpected"), "Running manual route update")

    def test_cli_startup_mode_prints_background_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = Path(tmp) / "routes.conf"
            routes.write_text("route 192.0.2.0/24 blackhole;\n", encoding="utf-8")

            exit_code, output = run_main(["startup-mode", str(routes)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "background-refresh")

    def test_cli_update_message_prints_reason_specific_text(self):
        exit_code, output = run_main(["update-message", "startup"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "Refreshing routes after startup using previous route snapshot")


if __name__ == "__main__":
    unittest.main()
