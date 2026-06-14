import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bgp_antifilter import updater_server


class UpdaterServerTests(unittest.TestCase):
    def test_validate_version_accepts_plain_and_v_prefixed_values(self):
        self.assertEqual(updater_server.validate_version("0.2.6"), "0.2.6")
        self.assertEqual(updater_server.validate_version("v0.2.7"), "0.2.7")

    def test_validate_version_rejects_invalid_format(self):
        with self.assertRaises(ValueError):
            updater_server.validate_version("latest")

    def test_update_env_version_replaces_existing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("FOO=bar\nBGP_ANTIFILTER_VERSION=0.2.5\n", encoding="utf-8")

            updater_server.update_env_version(path, "0.2.6")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "FOO=bar\nBGP_ANTIFILTER_VERSION=0.2.6\n",
            )

    def test_update_env_version_appends_missing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("FOO=bar\n", encoding="utf-8")

            updater_server.update_env_version(path, "0.2.6")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "FOO=bar\n\nBGP_ANTIFILTER_VERSION=0.2.6\n",
            )

    def test_health_status_requires_docker_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            compose_file = workspace / "docker-compose.yml"
            compose_file.write_text("services: {}\n", encoding="utf-8")

            real_exists = Path.exists

            def exists_side_effect(path_obj):
                if path_obj == Path("/var/run/docker.sock"):
                    return False
                return real_exists(path_obj)

            with mock.patch.object(updater_server, "WORKSPACE_DIR", workspace):
                with mock.patch.object(updater_server, "COMPOSE_FILE", compose_file):
                    with mock.patch.object(updater_server.shutil, "which", return_value="docker-compose"):
                        with mock.patch.object(Path, "exists", autospec=True, side_effect=exists_side_effect):
                            ok, error = updater_server.health_status()

        self.assertFalse(ok)
        self.assertIn("docker socket", error)

    def test_reconcile_runtime_marks_restart_as_completed_after_version_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_file = Path(tmp) / "update-runtime.json"
            runtime_file.write_text(
                '{'
                '"active": true,'
                '"stage": "restarting",'
                '"target_version": "0.3.0",'
                '"current_version": "0.2.9"'
                '}',
                encoding="utf-8",
            )

            with mock.patch.object(updater_server, "UPDATE_RUNTIME_FILE", runtime_file):
                payload = updater_server.reconcile_runtime("0.3.0")

        self.assertFalse(payload["active"])
        self.assertEqual(payload["stage"], "completed")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["current_version"], "0.3.0")


if __name__ == "__main__":
    unittest.main()
