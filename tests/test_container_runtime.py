import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from bgp_antifilter import container_runtime
from bgp_antifilter.state_store import read_state


ROOT = Path(__file__).resolve().parents[1]
VALID_ENV = {
    "MY_AS": "64500", "MT_AS": "65455", "MT_IP": "192.168.55.1",
    "BIRD_IP": "192.168.55.5", "ROUTER_ID": "192.168.55.5",
    "BGP_COMMUNITY": "65432,500", "UPDATE_INTERVAL": "1800",
    "CACHE_MAX_AGE": "604800", "ADMIN_ENABLED": "0", "ADMIN_PORT": "8080",
    "ADMIN_PASSWORD": "",
}


class ContainerRuntimeTests(unittest.TestCase):
    def test_env_validation_accepts_disabled_admin_and_enabled_admin_with_password(self):
        with mock.patch.dict(os.environ, VALID_ENV, clear=True):
            self.assertEqual(container_runtime.main(["validate-env"]), 0)
            with mock.patch.dict(os.environ, {"ADMIN_ENABLED": "1", "ADMIN_PASSWORD": "test"}):
                self.assertEqual(container_runtime.main(["validate-env"]), 0)

    def test_env_validation_retains_error_messages_and_exit_code(self):
        cases = (
            ("MY_AS", "bad", "MY_AS must be an integer AS number"),
            ("MT_AS", "0", "MT_AS must be between 1 and 4294967295"),
            ("BIRD_IP", "bad", "BIRD_IP must be a valid IPv4 address"),
            ("UPDATE_INTERVAL", "0", "UPDATE_INTERVAL must be greater than zero"),
            ("CACHE_MAX_AGE", "bad", "CACHE_MAX_AGE must be an integer number of seconds"),
            ("BGP_COMMUNITY", "1:2", "BGP_COMMUNITY must use the BIRD tuple format AS,VALUE"),
            ("BGP_COMMUNITY", "1,bad", "BGP_COMMUNITY parts must be integers"),
            ("BGP_COMMUNITY", "1,65536", "BGP_COMMUNITY parts must be between 0 and 65535"),
            ("ADMIN_ENABLED", "yes", "ADMIN_ENABLED must be 0 or 1"),
            ("ADMIN_PORT", "bad", "ADMIN_PORT must be an integer"),
            ("ADMIN_PORT", "65536", "ADMIN_PORT must be between 1 and 65535"),
            ("ADMIN_ENABLED", "1", "ADMIN_PASSWORD must be set when ADMIN_ENABLED=1"),
        )
        for key, value, message in cases:
            with self.subTest(key=key, value=value), mock.patch.dict(os.environ, {**VALID_ENV, key: value}, clear=True):
                output = io.StringIO()
                with contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as raised:
                    container_runtime.main(["validate-env"])
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual(output.getvalue(), f"Invalid environment: {message}\n")

    def test_render_keeps_safe_substitution_for_unknown_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "bird.template"
            target = Path(tmp) / "bird.conf"
            template.write_text("router id $ROUTER_ID; # $UNKNOWN\n", encoding="utf-8")
            with mock.patch.dict(os.environ, VALID_ENV, clear=True):
                self.assertEqual(container_runtime.main(["render-bird", str(template), str(target)]), 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "router id 192.168.55.5; # $UNKNOWN\n")

    def test_health_checks_keep_failure_codes_and_default_network_behavior(self):
        cases = (
            ("status", {"routes": {"final": 1}}, 0, ""),
            ("status", {}, 1, "status reports zero routes\n"),
            ("runtime", {"degraded": False}, 0, ""),
            ("runtime", {"degraded": True}, 1, "runtime is degraded\n"),
            ("runtime", {"degraded": True, "degraded_reason": "old snapshot"}, 1, "old snapshot\n"),
            ("network", {}, 0, ""),
            ("network", {"bird_ip_assigned": False}, 1, "configured BIRD_IP is not assigned inside container\n"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "health.json"
            for kind, payload, code, message in cases:
                with self.subTest(kind=kind, payload=payload):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    output = io.StringIO()
                    with contextlib.redirect_stderr(output):
                        self.assertEqual(container_runtime.main(["check-health", kind, str(path)]), code)
                    self.assertEqual(output.getvalue(), message)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                container_runtime.main(["check-health", "status", str(path)])

    def test_snapshot_shell_values_preserve_empty_lines_and_zero_age(self):
        for payload, expected in (
            ({}, "0\n0\n\n\n"),
            ({"startup_snapshot_used": True, "startup_snapshot_size_bytes": 42,
              "startup_snapshot_mtime_unix": 1000, "startup_snapshot_age_seconds": 0}, "1\n42\n1000\n0\n"),
        ):
            with self.subTest(payload=payload):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(container_runtime.main(["snapshot-values", json.dumps(payload)]), 0)
                self.assertEqual(output.getvalue(), expected)

    def test_network_warning_is_optional_but_prints_unassigned_ip_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "network.json"
            with mock.patch.dict(os.environ, {"NETWORK_STATUS_FILE": str(path)}):
                for content, expected in (("{bad", ""), ('{"message":"wrong IP","bird_ip_assigned":false}', "wrong IP\n"),
                                          ('{"message":"wrong IP","bird_ip_assigned":true}', "")):
                    path.write_text(content, encoding="utf-8")
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        self.assertEqual(container_runtime.main(["network-warning"]), 0)
                    self.assertEqual(output.getvalue(), expected)

    def test_network_status_uses_configured_path_and_retains_diagnostic_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "network.json"
            diagnostic = {"bird_ip_assigned": False, "message": "wrong IP", "local_ipv4": ["127.0.0.1"]}
            with mock.patch.dict(os.environ, {"NETWORK_STATUS_FILE": str(path)}):
                with mock.patch.object(container_runtime, "bird_ip_diagnostic", return_value=diagnostic) as diagnose:
                    self.assertEqual(container_runtime.main(["write-network-status", "192.0.2.1"]), 0)
            diagnose.assert_called_once_with("192.0.2.1")
            self.assertEqual(read_state(path), diagnostic)


@unittest.skipUnless(os.name != "nt" and shutil.which("sh"), "Shell integration requires POSIX sh")
class ShellRuntimeTests(unittest.TestCase):
    def test_shell_library_calls_python_and_keeps_generator_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            env = {
                **os.environ, **VALID_ENV, "PYTHONPATH": str(ROOT),
                "RUNTIME_FILE": str(path), "NETWORK_STATUS_FILE": str(Path(tmp) / "network.json"),
                "SETTINGS_ENV_FILE": str(Path(tmp) / "settings.env"),
            }
            script = '''
. "$1"
validate_env
GENERATION_ACTIVE=1
GENERATION_KIND=startup
write_runtime 1000
export RUNTIME_PRESERVE_STATE=1
GENERATION_ACTIVE=0
write_runtime 2000
runtime_next_update_unix
'''
            result = subprocess.run(["sh", "-eu", "-c", script, "runtime-test", str(ROOT / "deploy/lib.sh")],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "2000\n")
            state = read_state(path)
            self.assertTrue(state["generation_active"])
            self.assertEqual(state["generation_kind"], "startup")

    def test_shell_healthcheck_propagates_python_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            birdc = root / "birdc"
            birdc.write_text("#!/bin/sh\necho Established\n", encoding="utf-8")
            birdc.chmod(0o755)
            routes = root / "routes.conf"
            routes.write_text("route 192.0.2.0/24 blackhole;\n", encoding="utf-8")
            status = root / "status.json"
            env = {
                **os.environ, "PYTHONPATH": str(ROOT), "PATH": f"{root}{os.pathsep}{os.environ['PATH']}",
                "ADMIN_ENABLED": "0", "HEALTHCHECK_REQUIRE_BGP": "0", "HEALTHCHECK_FAIL_ON_DEGRADED": "0",
                "ROUTES_FILE": str(routes), "STATUS_FILE": str(status),
            }
            for final_count, expected in ((1, 0), (0, 1)):
                status.write_text(json.dumps({"routes": {"final": final_count}}), encoding="utf-8")
                result = subprocess.run(["sh", str(ROOT / "deploy/healthcheck.sh")],
                                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected:
                    self.assertIn("status reports zero routes", result.stderr)


if __name__ == "__main__":
    unittest.main()
