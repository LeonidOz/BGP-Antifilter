import subprocess
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

    def test_configured_version_prefers_env_value_over_workspace_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            version_file = Path(tmp) / "VERSION"
            env_file.write_text("BGP_ANTIFILTER_VERSION=v0.2.5\n", encoding="utf-8")
            version_file.write_text("0.3.2\n", encoding="utf-8")

            with mock.patch.object(updater_server, "ENV_FILE", env_file):
                with mock.patch.object(updater_server, "VERSION_FILE", version_file):
                    self.assertEqual(updater_server.configured_version(), "0.2.5")

    def test_configured_version_falls_back_to_workspace_version_for_invalid_env_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            version_file = Path(tmp) / "VERSION"
            env_file.write_text("BGP_ANTIFILTER_VERSION=latest\n", encoding="utf-8")
            version_file.write_text("0.3.2\n", encoding="utf-8")

            with mock.patch.object(updater_server, "ENV_FILE", env_file):
                with mock.patch.object(updater_server, "VERSION_FILE", version_file):
                    self.assertEqual(updater_server.configured_version(), "0.3.2")

    def test_compose_project_name_reads_top_level_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            compose_file = Path(tmp) / "docker-compose.yml"
            compose_file.write_text('name: "bgp-antifilter"\nservices: {}\n', encoding="utf-8")

            self.assertEqual(updater_server.compose_project_name(compose_file), "bgp-antifilter")

    def test_strip_top_level_name_removes_only_project_name(self):
        source = "name: bgp-antifilter\n\nservices:\n  app:\n    environment:\n      APP_NAME: demo\n"
        stripped = updater_server.strip_top_level_name(source)

        self.assertTrue(stripped.startswith("services:\n"))
        self.assertIn("APP_NAME: demo", stripped)
        self.assertNotIn("name: bgp-antifilter", stripped)

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

    def test_compose_base_command_uses_docker_compose_v2_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            compose_file = Path(tmp) / "docker-compose.yml"
            compose_file.write_text("name: bgp-antifilter\nservices: {}\n", encoding="utf-8")

            completed = subprocess.CompletedProcess(args=["docker", "compose", "version"], returncode=0, stdout="", stderr="")

            with mock.patch.object(updater_server, "COMPOSE_FILE", compose_file):
                with mock.patch.object(updater_server.shutil, "which", side_effect=lambda cmd: {"docker": "docker", "docker-compose": "docker-compose"}.get(cmd)):
                    with mock.patch.object(updater_server.subprocess, "run", return_value=completed):
                        command, cleanup_path = updater_server.compose_base_command()

        self.assertEqual(command, ["docker", "compose", "-f", str(compose_file)])
        self.assertIsNone(cleanup_path)

    def test_compose_base_command_falls_back_to_legacy_compose_with_project_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            compose_file = Path(tmp) / "docker-compose.yml"
            compose_file.write_text("name: bgp-antifilter\nservices: {}\n", encoding="utf-8")

            completed = subprocess.CompletedProcess(args=["docker", "compose", "version"], returncode=1, stdout="", stderr="missing")

            with mock.patch.object(updater_server, "COMPOSE_FILE", compose_file):
                with mock.patch.object(updater_server.shutil, "which", side_effect=lambda cmd: {"docker": "docker", "docker-compose": "docker-compose"}.get(cmd)):
                    with mock.patch.object(updater_server.subprocess, "run", return_value=completed):
                        command, cleanup_path = updater_server.compose_base_command()

                        self.assertEqual(command[:3], ["docker-compose", "-p", "bgp-antifilter"])
                        self.assertEqual(command[3], "-f")
                        self.assertIsNotNone(cleanup_path)
                        self.assertTrue(cleanup_path.exists())
                        self.assertEqual(cleanup_path.read_text(encoding="utf-8"), "services: {}\n")

                        cleanup_path.unlink(missing_ok=True)

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

    def test_reconcile_runtime_marks_any_active_stage_completed_when_target_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_file = Path(tmp) / "update-runtime.json"
            runtime_file.write_text(
                '{'
                '"active": true,'
                '"stage": "pulling",'
                '"target_version": "0.3.1",'
                '"current_version": "0.3.0"'
                '}',
                encoding="utf-8",
            )

            with mock.patch.object(updater_server, "UPDATE_RUNTIME_FILE", runtime_file):
                payload = updater_server.reconcile_runtime("0.3.1")

        self.assertFalse(payload["active"])
        self.assertEqual(payload["stage"], "completed")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["current_version"], "0.3.1")

    def test_reconcile_runtime_clears_failed_status_after_external_upgrade_to_target_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_file = Path(tmp) / "update-runtime.json"
            runtime_file.write_text(
                '{'
                '"active": false,'
                '"stage": "failed",'
                '"target_version": "0.3.4",'
                '"current_version": "0.3.3",'
                '"success": false,'
                '"error": "docker compose up failed",'
                '"rollback": {"ok": false, "error": "rollback failed"}'
                '}',
                encoding="utf-8",
            )

            with mock.patch.object(updater_server, "UPDATE_RUNTIME_FILE", runtime_file):
                payload = updater_server.reconcile_runtime("0.3.4")

        self.assertFalse(payload["active"])
        self.assertEqual(payload["stage"], "completed")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["current_version"], "0.3.4")
        self.assertEqual(payload["error"], "")
        self.assertEqual(payload["rollback"], {})

    def test_apply_update_rolls_back_to_version_from_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            version_file = Path(tmp) / "VERSION"
            runtime_file = Path(tmp) / "update-runtime.json"
            env_file.write_text("BGP_ANTIFILTER_VERSION=0.2.8\n", encoding="utf-8")
            version_file.write_text("0.3.2\n", encoding="utf-8")

            compose_calls = []

            def fake_run_compose(*args, timeout=1800):
                compose_calls.append(args)
                if args and args[0] == "pull":
                    return {"ok": False, "stderr": "pull failed", "stdout": "", "returncode": 1}
                return {"ok": True, "stderr": "", "stdout": "", "returncode": 0}

            with mock.patch.object(updater_server, "ENV_FILE", env_file):
                with mock.patch.object(updater_server, "VERSION_FILE", version_file):
                    with mock.patch.object(updater_server, "UPDATE_RUNTIME_FILE", runtime_file):
                        with mock.patch.object(updater_server, "run_compose", side_effect=fake_run_compose):
                            updater_server.apply_update("0.3.3")

            self.assertEqual(compose_calls[0], ("pull", *updater_server.COMPOSE_SERVICES))
            self.assertEqual(compose_calls[1], ("up", "-d", *updater_server.COMPOSE_SERVICES))
            self.assertIn("BGP_ANTIFILTER_VERSION=0.2.8\n", env_file.read_text(encoding="utf-8"))
            runtime = updater_server.read_json(runtime_file, {})
            self.assertFalse(runtime["success"])
            self.assertTrue(runtime["rollback"]["ok"])
            self.assertEqual(runtime["rollback"]["version"], "0.2.8")

    def test_start_update_reports_current_version_from_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            version_file = Path(tmp) / "VERSION"
            env_file.write_text("BGP_ANTIFILTER_VERSION=0.2.8\n", encoding="utf-8")
            version_file.write_text("0.3.2\n", encoding="utf-8")

            thread = mock.Mock()
            thread.is_alive.return_value = False

            with mock.patch.object(updater_server, "ENV_FILE", env_file):
                with mock.patch.object(updater_server, "VERSION_FILE", version_file):
                    with mock.patch.object(updater_server, "health_status", return_value=(True, "")):
                        with mock.patch.object(updater_server, "UPDATE_THREAD", thread):
                            with mock.patch.object(updater_server.threading, "Thread") as thread_cls:
                                payload = updater_server.start_update("0.3.3")

            self.assertEqual(payload["current_version"], "0.2.8")
            self.assertEqual(payload["target_version"], "0.3.3")
            thread_cls.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
