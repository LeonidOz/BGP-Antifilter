"""Release discovery, update transactions and recovery at external boundaries."""

import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from bgp_antifilter import updater_server as updater
from bgp_antifilter.admin import updates


def release(version="9.9.9"):
    return {"version": version, "tag_name": f"v{version}", "html_url": "https://example.test/release",
            "name": "Test release", "published_at": "2026-11-15T00:00:00Z"}


class ReleaseChecksTests(unittest.TestCase):
    def setUp(self):
        self.service = updates.UpdatesService()

    def test_cache_ttl_force_and_response_mutations(self):
        with mock.patch.object(updates, "github_latest_release", return_value=release()) as fetch, \
             mock.patch.object(updates.time, "time", return_value=1000) as now:
            first = self.service.update_status_payload()
            first["ok"] = False
            now.return_value = 1001
            self.assertTrue(self.service.update_status_payload()["ok"])
            self.assertEqual(fetch.call_count, 1)
            self.service.update_status_payload(force=True)
            now.return_value += updates.UPDATE_CHECK_TTL_SECONDS
            self.service.update_status_payload()
            self.assertEqual(fetch.call_count, 3)

    def test_failed_or_invalid_release_never_enables_apply(self):
        for result in (OSError("offline"), release("1.2.3-rc1"), release("-1.2.3")):
            with self.subTest(result=result), \
                 mock.patch.object(updates, "github_latest_release", **(
                     {"side_effect": result} if isinstance(result, Exception) else {"return_value": result})), \
                 mock.patch.object(updater, "reconcile_runtime", return_value={}), \
                 mock.patch.object(updates, "updater_health", return_value=(True, "")):
                payload = self.service.status_payload(force=True)
                self.assertFalse(payload["ok"])
                self.assertFalse(payload["apply_available"])
                self.assertTrue(payload["error"])

    def test_github_rejects_non_objects_missing_tags_and_non_release_versions(self):
        for value in ([], None, {}, {"tag_name": "v1.0.0-rc1"}):
            with self.subTest(value=value):
                response = mock.MagicMock()
                response.__enter__.return_value.read.return_value = json.dumps(value).encode()
                with mock.patch.object(updates.urllib.request, "urlopen", return_value=response), \
                     self.assertRaises(ValueError):
                    updates.github_latest_release()

    def test_runtime_and_updater_availability_are_not_cached_with_github_result(self):
        with mock.patch.object(updates, "github_latest_release", return_value=release()) as fetch, \
             mock.patch.object(updater, "reconcile_runtime", side_effect=[{}, {"active": True}, {}]), \
             mock.patch.object(updates, "updater_health", side_effect=[(True, ""), (True, ""), (False, "no socket")]):
            self.assertTrue(self.service.status_payload()["apply_available"])
            self.assertFalse(self.service.status_payload()["apply_available"])
            last = self.service.status_payload()
            self.assertFalse(last["apply_available"])
            self.assertEqual(last["updater_error"], "no socket")
            self.assertEqual(fetch.call_count, 1)

    def test_apply_rechecks_release_and_rejects_stale_or_unpublished_targets(self):
        with mock.patch.object(updates, "github_latest_release", return_value=release()), \
             mock.patch.object(updater, "start_update", return_value={"accepted": True}) as start:
            self.assertEqual(self.service.start_update("v9.9.9"), {"accepted": True})
            for version in ("0.0.1", "10.0.0", "latest", "9.9.9;id"):
                with self.subTest(version=version), self.assertRaises(ValueError):
                    self.service.start_update(version)
            start.assert_called_once_with("9.9.9")
        with mock.patch.object(updates, "github_latest_release", side_effect=OSError("offline")), \
             mock.patch.object(updater, "start_update") as start, self.assertRaises(RuntimeError):
            self.service.start_update("9.9.9")
        start.assert_not_called()


class UpdateTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = self.root / ".env"
        self.original = "# keep comments and other settings\nADMIN_PASSWORD='test value'\n  BGP_ANTIFILTER_VERSION='1.0.0'\n"
        self.env.write_text(self.original, encoding="utf-8")
        self.context = {"container": "old-id", "image": "sha256:old", "project": "test",
                        "directory": "/srv/test", "worker": "test-image-updater"}
        for patch in (
            mock.patch.object(updater, "ENV_FILE", self.env),
            mock.patch.object(updater, "UPDATE_RUNTIME_FILE", self.root / "update.json"),
            mock.patch.object(updater, "COMPOSE_SERVICES", ("bgp-antifilter",)),
            mock.patch.object(updater, "uses_legacy_docker_compose", return_value=False),
            mock.patch.object(updater, "health_status", return_value=(True, "")),
            mock.patch.object(updater, "deployment_context", return_value=self.context),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def ok(self, *args, **kwargs):
        return {"ok": True, "stdout": "", "stderr": ""}

    def test_success_is_published_only_after_health_and_version_verification(self):
        def verify(version):
            self.assertEqual(version, "1.0.1")
            runtime = updater.runtime_payload()
            self.assertTrue(runtime["active"])
            self.assertIsNone(runtime["success"])
            self.assertEqual(runtime["stage"], "verifying")
        with mock.patch.object(updater, "run_compose", side_effect=self.ok) as compose, \
             mock.patch.object(updater, "wait_for_services", side_effect=verify):
            updater.apply_update("1.0.1")
        self.assertEqual(compose.call_args_list, [mock.call("pull", "bgp-antifilter", timeout=1800),
                                                mock.call("up", "-d", "--no-build", "bgp-antifilter", timeout=1800)])
        self.assertTrue(updater.runtime_payload()["success"])
        self.assertEqual(updater.configured_version(), "1.0.1")

    def test_pull_timeout_restores_exact_env_without_restarting_running_application(self):
        with mock.patch.object(updater, "run_compose", side_effect=subprocess.TimeoutExpired("pull", 1)) as compose, \
             mock.patch.object(updater, "wait_for_services") as verify:
            updater.apply_update("1.0.1")
        self.assertEqual(compose.call_count, 1)
        verify.assert_not_called()
        self.assertEqual(self.env.read_text(encoding="utf-8"), self.original)
        runtime = updater.runtime_payload()
        self.assertFalse(runtime["active"])
        self.assertFalse(runtime["success"])
        self.assertTrue(runtime["rollback"]["ok"])

    def test_startup_or_health_failure_rolls_back_and_checks_previous_version(self):
        for failure in ("startup", "health"):
            with self.subTest(failure=failure):
                calls = 0

                def compose(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    return {"ok": False, "stderr": "startup failed"} if failure == "startup" and calls == 2 else self.ok()

                checks = [RuntimeError("unhealthy"), None] if failure == "health" else [None]
                with mock.patch.object(updater, "run_compose", side_effect=compose), \
                     mock.patch.object(updater, "wait_for_services", side_effect=checks) as verify:
                    updater.apply_update("1.0.1")
                self.assertEqual(verify.call_args, mock.call("1.0.0"))
                self.assertTrue(updater.runtime_payload()["rollback"]["ok"])
                self.assertFalse(updater.runtime_payload()["success"])
                self.assertEqual(self.env.read_text(encoding="utf-8"), self.original)

    def test_rollback_exception_is_recorded_and_does_not_leave_active_state(self):
        with mock.patch.object(updater, "run_compose", side_effect=[self.ok(), RuntimeError("start failed"),
                                                                  OSError("daemon unavailable")]):
            updater.apply_update("1.0.1")
        runtime = updater.runtime_payload()
        self.assertFalse(runtime["active"])
        self.assertEqual(runtime["error"], "start failed")
        self.assertFalse(runtime["rollback"]["ok"])
        self.assertIn("daemon unavailable", runtime["rollback"]["error"])

    def test_concurrent_requests_launch_exactly_one_independent_worker(self):
        results = []
        errors = []
        def start():
            try:
                results.append(updater.start_update("1.0.1"))
            except RuntimeError as exc:
                errors.append(str(exc))
        with mock.patch.object(updater, "run_docker", return_value="worker-id") as docker, \
             mock.patch.object(updater, "inspect_container", return_value={"State": {"Running": True}}):
            threads = [threading.Thread(target=start) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(5)
        self.assertEqual(len(results), 1)
        self.assertEqual(errors, ["update already running"] * 3)
        docker.assert_called_once()
        self.assertTrue(updater.runtime_payload()["active"])

    def test_launch_failure_and_invalid_targets_do_not_change_env(self):
        with mock.patch.object(updater, "run_docker", side_effect=OSError("daemon unavailable")):
            with self.assertRaisesRegex(RuntimeError, "could not start updater"):
                updater.start_update("1.0.1")
        self.assertFalse(updater.runtime_payload()["active"])
        for version in ("1.0.0", "0.9.9", "1.0.1; touch /tmp/x", "١.٢.٣"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                updater.start_update(version)
        self.assertEqual(self.env.read_text(encoding="utf-8"), self.original)

    def test_lost_launch_response_keeps_operation_reserved_for_reconciliation(self):
        with mock.patch.object(updater, "run_docker", side_effect=subprocess.TimeoutExpired("docker run", 30)):
            result = updater.start_update("1.0.1")
        self.assertTrue(result["accepted"])
        self.assertTrue(updater.runtime_payload()["active"])
        with mock.patch.object(updater, "inspect_container", return_value={"State": {"Running": True}}):
            with self.assertRaisesRegex(RuntimeError, "already running"):
                updater.start_update("1.0.1")

    def test_rollback_restores_original_line_endings_and_file_permissions(self):
        original = b"ADMIN_PASSWORD=test\r\nBGP_ANTIFILTER_VERSION=1.0.0\r\n"
        self.env.write_bytes(original)
        self.env.chmod(0o600)
        mode = self.env.stat().st_mode & 0o777
        with mock.patch.object(updater, "run_compose", return_value={"ok": False, "stderr": "pull failed"}):
            updater.apply_update("1.0.1")
        self.assertEqual(self.env.read_bytes(), original)
        self.assertEqual(self.env.stat().st_mode & 0o777, mode)


    def test_managed_worker_success_cannot_be_inferred_from_version_alone(self):
        updater.write_runtime(active=True, stage="verifying", target_version="1.0.1",
                              worker="test-image-updater", started_at_unix=1, success=None)
        with mock.patch.object(updater, "inspect_container", return_value={"State": {"Running": True}}):
            self.assertTrue(updater.reconcile_runtime("1.0.1")["active"])
        with mock.patch.object(updater, "inspect_container", side_effect=RuntimeError("No such container")), \
             mock.patch.object(updater, "run_docker", return_value="daemon-id"):
            runtime = updater.reconcile_runtime("1.0.1")
        self.assertFalse(runtime["success"])
        self.assertFalse(runtime["active"])
        self.assertIn("stopped before verification", runtime["error"])

    def test_daemon_outage_does_not_invent_failure_or_success(self):
        updater.write_runtime(active=True, target_version="1.0.1", worker="test-image-updater", started_at_unix=1)
        with mock.patch.object(updater, "inspect_container", side_effect=RuntimeError("unreachable")), \
             mock.patch.object(updater, "run_docker", side_effect=RuntimeError("unreachable")):
            self.assertTrue(updater.reconcile_runtime("1.0.1")["active"])

    def test_health_requires_running_healthy_container_with_expected_version(self):
        for state, version in (({"Running": False}, "1.0.1"),
                               ({"Running": True, "Health": {"Status": "starting"}}, "1.0.1"),
                               ({"Running": True, "Health": {"Status": "healthy"}}, "1.0.0")):
            with self.subTest(state=state, version=version), \
                 mock.patch.object(updater, "run_compose", return_value={"ok": True, "stdout": "new-id"}), \
                 mock.patch.object(updater, "inspect_container", return_value={"State": state}), \
                 mock.patch.object(updater, "run_docker", return_value=version), self.assertRaises(RuntimeError):
                updater.wait_for_services("1.0.1", timeout=0)
        with mock.patch.object(updater, "run_compose", return_value={"ok": True, "stdout": "new-id"}), \
             mock.patch.object(updater, "inspect_container", return_value={"State": {"Running": True, "Health": {"Status": "healthy"}}}), \
             mock.patch.object(updater, "run_docker", return_value="1.0.1"):
            updater.wait_for_services("1.0.1", timeout=0)


class DeploymentContextTests(unittest.TestCase):
    def info(self):
        return {"Id": "self-id", "Image": "sha256:immutable", "Config": {"Labels": {
            "com.docker.compose.project": "custom-project", "com.docker.compose.service": "bgp-antifilter",
            "com.docker.compose.project.config_files": "/srv/custom/docker-compose.yml"}},
            "Mounts": [{"Type": "bind", "Source": "/srv/custom", "Destination": str(updater.WORKSPACE_DIR), "RW": True}]}

    def test_uses_original_project_name_host_path_and_immutable_image(self):
        with mock.patch.object(updater, "inspect_container", return_value=self.info()):
            self.assertEqual(updater.deployment_context(), {
                "container": "self-id", "image": "sha256:immutable", "project": "custom-project",
                "directory": "/srv/custom", "worker": "custom-project-image-updater"})

    def test_rejects_unsupported_deployments_before_replacing_application(self):
        for kind in ("portainer", "overrides", "readonly", "volume", "windows"):
            info = self.info()
            if kind == "portainer":
                info["Config"]["Labels"] = {}
            elif kind == "overrides":
                info["Config"]["Labels"]["com.docker.compose.project.config_files"] += ",/srv/custom/override.yml"
            elif kind == "readonly":
                info["Mounts"][0]["RW"] = False
            elif kind == "volume":
                info["Mounts"][0]["Type"] = "volume"
            else:
                info["Mounts"][0]["Source"] = "C:\\deployment"
            with self.subTest(kind=kind), mock.patch.object(updater, "inspect_container", return_value=info), \
                 self.assertRaises(RuntimeError):
                updater.deployment_context()


if __name__ == "__main__":
    unittest.main()
