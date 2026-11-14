"""Real image pull, self-replacement and rollback through the admin HTTP API.

Opt in with RUN_DOCKER_WEB_UPDATE=1. Only GitHub release discovery is replaced
with a local fixture; Docker, Compose, BIRD, health checks and HTTP are real.
All containers, image tags and volumes belong to a unique temporary project.
"""

import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("RUN_DOCKER_WEB_UPDATE") == "1" and shutil.which("docker") and os.name != "nt",
                     "requires RUN_DOCKER_WEB_UPDATE=1 and a Linux Docker engine")
class WebUpdateDockerTests(unittest.TestCase):
    def docker(self, *args, check=True, input=None):
        result = subprocess.run(["docker", *args], text=True, input=input, capture_output=True, timeout=240)
        if check and result.returncode:
            self.fail(f"docker {' '.join(args)} failed:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
        return result.stdout.strip()

    def compose(self, *args, check=True):
        options = ["--env-file", str(self.env_file), "-p", self.project,
                   "-f", str(self.root / "compose.yaml"), *args]
        if self.compose_v2:
            return self.docker("compose", *options, check=check)
        result = subprocess.run(["docker-compose", *options], text=True, capture_output=True, timeout=240)
        if check and result.returncode:
            self.fail(f"compose failed:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
        return result.stdout.strip()

    def wait(self, predicate, message, timeout=90):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value:
                    return value
            except (OSError, ValueError, urllib.error.URLError) as exc:
                last = exc
            time.sleep(0.5)
        runtime = (self.root / "generated/update-runtime.json")
        details = runtime.read_text(encoding="utf-8") if runtime.exists() else "no update runtime"
        self.fail(f"{message}: {last}\n{details}\n{self.compose('logs', '--tail=50', check=False)}")

    def setUp(self):
        self.compose_v2 = subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0
        self.project = "bgp-web-test-" + uuid.uuid4().hex[:10]
        self.tags = []
        self.registry_name = self.project + "-registry"
        self.temporary = tempfile.TemporaryDirectory(prefix=self.project)
        self.root = Path(self.temporary.name)
        self.env_file = self.root / ".env"
        self.addCleanup(self.cleanup)
        if self.docker("info", "--format", "{{.OSType}}") != "linux":
            self.skipTest("requires a Linux Docker engine")
        base = os.environ.get("WEB_UPDATE_TEST_IMAGE", "bgp-antifilter:web-update-test")
        if "WEB_UPDATE_TEST_IMAGE" not in os.environ:
            self.docker("build", "-t", base, "-f", str(ROOT / "deploy/Dockerfile"), str(ROOT))
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.registry_port = reservation.getsockname()[1]
        self.docker("run", "-d", "--rm", "--name", self.registry_name, "--network", "host",
                    "-e", f"REGISTRY_HTTP_ADDR=127.0.0.1:{self.registry_port}", "registry:2")
        self.repository = f"127.0.0.1:{self.registry_port}/{self.project}"
        # The admin uses the real application, with deterministic release metadata.
        (self.root / "admin-fixture.py").write_text(
            "#!/usr/bin/env python3\nfrom pathlib import Path\n"
            "from bgp_antifilter.admin import updates\n"
            "from bgp_antifilter.admin.server import main\n"
            "def latest():\n"
            "    v = Path('/workspace/latest').read_text().strip()\n"
            "    return dict(version=v, tag_name='v'+v, html_url='https://example.test/release', name='Test', published_at='')\n"
            "updates.github_latest_release = latest\nraise SystemExit(main())\n", encoding="utf-8")
        for version in ("1.0.0", "1.0.1", "1.0.3"):
            tag = f"{self.repository}:{version}"
            self.tags.append(tag)
            broken = "RUN printf '#!/bin/sh\\nexit 1\\n' > /healthcheck.sh\n" if version == "1.0.3" else ""
            dockerfile = (f"FROM {base}\nCOPY admin-fixture.py /admin-server.py\n"
                          f"RUN chmod +x /admin-server.py && echo {version} > /VERSION\n" + broken)
            self.docker("build", "-t", tag, "-f", "-", str(self.root), input=dockerfile)
            self.docker("push", tag)
        # The target image must actually be pulled from the registry during update.
        for tag in self.tags[1:]:
            self.docker("image", "rm", tag)
        self.env_file.write_text("# preserve this file on rollback\nBGP_ANTIFILTER_VERSION=1.0.0\n", encoding="utf-8")
        (self.root / "latest").write_text("1.0.1", encoding="utf-8")
        config = self.root / "config"
        config.mkdir()
        (self.root / "generated").mkdir()
        (config / "source.txt").write_text("192.0.2.0/24\n", encoding="utf-8")
        (config / "lists.txt").write_text("file:///etc/bird/config/source.txt\n", encoding="utf-8")
        for name in ("domain-list-urls", "include-asns", "include-countries", "include-domains", "exclude-domains"):
            (config / f"{name}.txt").write_text("# retain user data\n", encoding="utf-8")
        self.marker = (config / "include-domains.txt").read_bytes()
        (self.root / "compose.yaml").write_text(
            f"services:\n  bgp-antifilter:\n    image: '{self.repository}:${{BGP_ANTIFILTER_VERSION}}'\n"
            "    ports: ['127.0.0.1::8080']\n"
            "    volumes:\n      - './:/workspace'\n      - './config:/etc/bird/config'\n"
            "      - './generated:/etc/bird/generated'\n      - '/var/run/docker.sock:/var/run/docker.sock'\n"
            "    environment:\n      ADMIN_ENABLED: '1'\n      ADMIN_PASSWORD: test-password\n"
            "      HEALTHCHECK_REQUIRE_BGP: '0'\n      INCLUDE_GOOGLE_RANGES: '0'\n"
            "      BIRD_IP: '127.0.0.1'\n      ROUTER_ID: '127.0.0.1'\n      UPDATE_INTERVAL: '86400'\n"
            "      COMPOSE_FILE: /workspace/compose.yaml\n      UPDATER_HEALTH_TIMEOUT: '8'\n"
            "      UPDATE_RUNTIME_FILE: /etc/bird/generated/update-runtime.json\n"
            "    healthcheck:\n      test: ['CMD', '/healthcheck.sh']\n      interval: 1s\n"
            "      timeout: 3s\n      retries: 1\n      start_period: 1s\n", encoding="utf-8")
        self.compose("up", "-d")
        self.wait(lambda: self.info()["State"].get("Health", {}).get("Status") == "healthy", "initial image unhealthy")
        self.login()

    def cleanup(self):
        if (self.root / "compose.yaml").exists():
            self.docker("rm", "-f", self.project + "-image-updater", check=False)
            self.compose("down", "--volumes", "--remove-orphans", check=False)
        self.docker("rm", "-f", self.registry_name, check=False)
        for tag in self.tags:
            self.docker("image", "rm", tag, check=False)
        if os.name != "nt":
            # The application writes as root in an isolated temporary directory.
            base = os.environ.get("WEB_UPDATE_TEST_IMAGE", "bgp-antifilter:web-update-test")
            self.docker("run", "--rm", "--entrypoint", "chown", "-v", f"{self.root}:/test",
                        base, "-R", f"{os.getuid()}:{os.getgid()}", "/test", check=False)
        self.temporary.cleanup()

    def info(self):
        cid = self.compose("ps", "-q", "bgp-antifilter")
        if not cid:
            raise ValueError("application is restarting")
        return json.loads(self.docker("inspect", cid))[0]

    def api(self, path, data=None):
        info = self.info()
        if os.environ.get("WEB_UPDATE_TEST_INTERNAL") == "1":
            host = next(iter(info["NetworkSettings"]["Networks"].values()))["IPAddress"]
            port = "8080"
        else:
            host = "127.0.0.1"
            port = info["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"]
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(f"http://{host}:{port}{path}", body,
                                         {"Content-Type": "application/json"})
        with self.opener.open(request, timeout=20) as response:
            return response.status, json.load(response)

    def login(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                  urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.wait(lambda: self.api("/api/login", {"password": "test-password"})[1].get("ok"), "login failed")

    def finished(self):
        path = self.root / "generated/update-runtime.json"
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if value.get("active") is False else None

    def test_real_http_upgrade_pull_failure_and_unhealthy_rollback(self):
        original_id = self.info()["Id"]
        code, payload = self.api("/api/update/status?force=1")
        self.assertTrue(payload["apply_available"], payload)
        self.assertEqual(self.api("/api/update/apply", {"version": "1.0.1"})[0], 202)
        result = self.wait(self.finished, "upgrade did not finish")
        self.assertTrue(result["success"], result)
        self.assertNotEqual(self.info()["Id"], original_id)
        self.assertTrue(self.info()["Config"]["Image"].endswith(":1.0.1"))
        self.assertEqual(self.info()["State"]["Health"]["Status"], "healthy")
        self.assertEqual((self.root / "config/include-domains.txt").read_bytes(), self.marker)
        self.login()
        self.assertEqual(self.api("/api/update/status?force=1")[1]["current_version"], "1.0.1")

        stable_id = self.info()["Id"]
        stable_env = self.env_file.read_bytes()
        (self.root / "latest").write_text("1.0.2", encoding="utf-8")  # missing registry tag
        self.assertEqual(self.api("/api/update/apply", {"version": "1.0.2"})[0], 202)
        result = self.wait(self.finished, "pull failure did not finish")
        self.assertFalse(result["success"], result)
        self.assertTrue(result["rollback"]["ok"], result)
        self.assertEqual(self.info()["Id"], stable_id, "failed pull must not restart the working container")
        self.assertEqual(self.env_file.read_bytes(), stable_env)

        (self.root / "latest").write_text("1.0.3", encoding="utf-8")  # starts, but fails health check
        self.assertEqual(self.api("/api/update/apply", {"version": "1.0.3"})[0], 202)
        result = self.wait(self.finished, "unhealthy upgrade did not roll back")
        self.assertFalse(result["success"], result)
        self.assertIn("health verification failed", result["error"])
        self.assertTrue(result["rollback"]["ok"], result)
        self.assertTrue(self.info()["Config"]["Image"].endswith(":1.0.1"))
        self.assertEqual(self.info()["State"]["Health"]["Status"], "healthy")
        self.assertEqual(self.env_file.read_bytes(), stable_env)
        self.assertEqual((self.root / "config/include-domains.txt").read_bytes(), self.marker)
        self.login()
        payload = self.api("/api/update/status?force=1")[1]
        self.assertEqual(payload["current_version"], "1.0.1")
        self.assertFalse(payload["runtime"]["success"])


@unittest.skipUnless(os.environ.get("RUN_DOCKER_WEB_UPDATE") == "1" and shutil.which("docker") and os.name == "nt",
                     "Windows launcher for the Linux integration test")
class WindowsWebUpdateDockerTests(unittest.TestCase):
    def test_update_in_linux_workspace(self):
        base = os.environ.get("WEB_UPDATE_TEST_IMAGE", "bgp-antifilter:web-update-test")
        if "WEB_UPDATE_TEST_IMAGE" not in os.environ:
            subprocess.run(["docker", "build", "-t", base, "-f", str(ROOT / "deploy/Dockerfile"), str(ROOT)], check=True)
        volume = "bgp-web-test-workspace-" + uuid.uuid4().hex[:10]
        runner = volume + "-runner"
        subprocess.run(["docker", "volume", "create", volume], check=True, capture_output=True)
        mountpoint = json.loads(subprocess.check_output(["docker", "volume", "inspect", volume], text=True))[0]["Mountpoint"]
        try:
            result = subprocess.run([
                "docker", "run", "--rm", "--name", runner, "--network", "host", "--entrypoint", "python3",
                "-v", f"{ROOT}:/test-repo:ro", "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "-v", f"{volume}:{mountpoint}", "-e", f"TMPDIR={mountpoint}",
                "-e", "PYTHONPATH=/test-repo:/", "-e", "RUN_DOCKER_WEB_UPDATE=1",
                "-e", "WEB_UPDATE_TEST_INTERNAL=1",
                "-e", f"WEB_UPDATE_TEST_IMAGE={base}", "-w", "/test-repo", base,
                "-m", "unittest", "tests.test_web_update_docker.WebUpdateDockerTests", "-v",
            ], text=True, capture_output=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-6000:])
        finally:
            subprocess.run(["docker", "rm", "-f", runner], capture_output=True)
            subprocess.run(["docker", "volume", "rm", volume], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
