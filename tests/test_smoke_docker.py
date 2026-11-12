import http.cookiejar
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from unittest import mock
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class RouteSourceServer(ThreadingHTTPServer):
    def __init__(self, server_address, request_handler_class, state):
        super().__init__(server_address, request_handler_class)
        self.state = state


class RouteSourceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/routes.txt", "/domains.txt"}:
            self.send_error(404)
            return

        time.sleep(self.server.state["delay"])
        body = ("domains.example.test\n" if self.path == "/domains.txt" else self.server.state["body"]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


@unittest.skipUnless(
    os.environ.get("RUN_DOCKER_SMOKE") == "1"
    and sys.platform.startswith("linux")
    and shutil.which("docker"),
    "Docker smoke test requires RUN_DOCKER_SMOKE=1 on Linux with docker installed",
)
class DockerSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.generated_dir = self.root / "generated"
        self.config_dir = self.generated_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        for name in ("domain-list-urls.txt", "include-asns.txt", "include-domains.txt", "exclude-domains.txt"):
            (self.config_dir / name).write_text("", encoding="utf-8")

        self.repo_root = Path(__file__).resolve().parents[1]
        self.compose_file = self.root / "docker-compose.smoke.yml"
        self.project_name = f"bgp-antifilter-smoke-{os.getpid()}-{int(time.time())}"
        self.server_state = {"body": "192.0.2.0/24\n", "delay": 0}
        self.server = RouteSourceServer(("127.0.0.1", 0), RouteSourceHandler, self.server_state)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.port = self.server.server_address[1]
        (self.config_dir / "lists.txt").write_text(
            f"http://127.0.0.1:{self.port}/routes.txt\n",
            encoding="utf-8",
        )
        self.compose_file.write_text(self.compose_yaml(), encoding="utf-8")

    def tearDown(self):
        try:
            self.compose("down", "--remove-orphans", check=False)
            self.restore_generated_permissions()
        finally:
            self.server.shutdown()
            self.server.server_close()
            self.server_thread.join(timeout=5)
            self.tmp.cleanup()

    def compose_yaml(self):
        generated = self.generated_dir.as_posix()
        template = (self.repo_root / "deploy" / "bird.conf.template").as_posix()
        context = self.repo_root.as_posix()
        return textwrap.dedent(
            f"""
            services:
              bgp-antifilter:
                container_name: bgp-antifilter-smoke
                image: "bgp-antifilter:smoke"
                build:
                  context: "{context}"
                  dockerfile: deploy/Dockerfile
                network_mode: host
                restart: "no"
                volumes:
                  - "{template}:/etc/bird/bird.conf.template:ro"
                  - "{generated}:/etc/bird/generated"
                  - bird-run:/run/bird
                environment:
                  MY_AS: "64500"
                  MT_AS: "65455"
                  MT_IP: "192.168.55.1"
                  BIRD_IP: "192.168.55.5"
                  ROUTER_ID: "192.168.55.5"
                  BGP_COMMUNITY: "65432,500"
                  LISTS_FILE: /etc/bird/generated/config/lists.txt
                  DOMAIN_LIST_URLS_FILE: /etc/bird/generated/config/domain-list-urls.txt
                  INCLUDE_ASNS_FILE: /etc/bird/generated/config/include-asns.txt
                  INCLUDE_DOMAINS_FILE: /etc/bird/generated/config/include-domains.txt
                  EXCLUDE_DOMAINS_FILE: /etc/bird/generated/config/exclude-domains.txt
                  INCLUDE_GOOGLE_RANGES: "0"
                  UPDATE_INTERVAL: "86400"
                  CACHE_MAX_AGE: "604800"
                  MIN_PREFIX_LENGTH: "8"
                  ALLOW_BROAD_ROUTES: "0"
                  UPDATE_LOCK_DIR: /etc/bird/generated/update.lock
                  HEALTHCHECK_REQUIRE_BGP: "0"
                  BGP_PROTOCOL: "mikrotik"
                  ADMIN_ENABLED: "0"
                  ADMIN_PORT: "18080"
                  RUNTIME_FILE: /etc/bird/generated/runtime.json
                  CONTAINER_LOG_FILE: /etc/bird/generated/container.log
                  SETTINGS_FILE: /etc/bird/generated/settings.json
                  SETTINGS_ENV_FILE: /etc/bird/generated/settings.env
            volumes:
              bird-run:
            """
        ).strip() + "\n"

    def compose(self, *args, check=True):
        return subprocess.run(
            ["docker", "compose", "-p", self.project_name, "-f", str(self.compose_file), *args],
            cwd=self.repo_root,
            check=check,
            capture_output=True,
            text=True,
        )

    def restore_generated_permissions(self):
        if not self.generated_dir.exists() or not sys.platform.startswith("linux"):
            return
        uid = os.getuid()
        gid = os.getgid()
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "sh",
                "-v",
                f"{self.root.as_posix()}:/work",
                "bgp-antifilter:smoke",
                "-c",
                f"chown -R {uid}:{gid} /work || true",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def wait_until(self, predicate, timeout, message, interval=0.25):
        deadline = time.time() + timeout
        last_error = None
        while time.time() < deadline:
            try:
                if predicate():
                    return
            except AssertionError as exc:
                last_error = exc
            time.sleep(interval)
        logs = self.compose("logs", "bgp-antifilter", check=False)
        details = logs.stdout[-4000:] if logs.stdout else ""
        if last_error is not None:
            raise AssertionError(f"{message}: {last_error}\n{details}".strip())
        raise AssertionError(f"{message}\n{details}".strip())

    def read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_portainer_stack_loads_domains_and_shares_persistent_data(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            admin_port = reservation.getsockname()[1]
        volume = self.project_name + "-data"
        settings = {"BGP_ANTIFILTER_IMAGE": "bgp-antifilter:smoke", "ADMIN_PASSWORD": "smoke-test",
                    "BGP_DATA_VOLUME": volume, "BGP_DATA_EXTERNAL": "false", "ADMIN_PORT": str(admin_port),
                    "HEALTHCHECK_REQUIRE_BGP": "0", "INCLUDE_GOOGLE_RANGES": "0",
                    "HTTP_PROXY": "", "HTTPS_PROXY": "", "NO_PROXY": "localhost,127.0.0.1"}
        stack = (self.repo_root / "deploy/portainer-stack.yml").read_text()
        stack = stack.replace("    container_name: bgp-antifilter", f"    container_name: {self.project_name}", 1)
        stack = stack.replace("  bgp-antifilter:\n", "  bgp-antifilter:\n    extra_hosts: ['domains.example.test:198.51.100.10']\n", 1)
        self.compose_file.write_text(stack, encoding="utf-8")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                             urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

        def api(path, method="GET", data=None):
            body = json.dumps(data).encode() if data is not None else None
            request = urllib.request.Request(f"http://127.0.0.1:{admin_port}{path}", body,
                                             {"Content-Type": "application/json"}, method=method)
            with opener.open(request, timeout=5) as response:
                return json.load(response)

        def login():
            try:
                return api("/api/login", "POST", {"password": "smoke-test"}).get("ok")
            except urllib.error.URLError:
                return False

        with mock.patch.dict(os.environ, settings):
            try:
                subprocess.run(["docker", "build", "-q", "-t", "bgp-antifilter:smoke", "-f", "deploy/Dockerfile", "."],
                               cwd=self.repo_root, check=True, capture_output=True, text=True)
                seed = ("from pathlib import Path; p=Path('/etc/bird/generated/config'); p.mkdir(parents=True, exist_ok=True); "
                        "[(p/n).write_text('') for n in ('include-asns.txt','include-countries.txt','include-domains.txt','exclude-domains.txt')]; "
                        f"(p/'lists.txt').write_text('http://127.0.0.1:{self.port}/routes.txt\\n'); "
                        f"(p/'domain-list-urls.txt').write_text('Test domains | http://127.0.0.1:{self.port}/domains.txt\\n')")
                self.compose("run", "--rm", "--no-deps", "--entrypoint", "python3", "bgp-antifilter", "-c", seed)
                self.compose("up", "-d")
                self.wait_until(lambda: "198.51.100.10/32" in self.compose("exec", "-T", "bgp-antifilter", "birdc", "show", "route", check=False).stdout,
                                60, "Domain-list address did not reach BIRD")
                self.wait_until(login, 30, "Portainer admin did not start")
                self.assertIn("Test domains", api("/api/lists/domain-list-urls")["content"])
                with opener.open(f"http://127.0.0.1:{admin_port}/api/routes/address-list.rsc?list=smoke-vpn", timeout=5) as export:
                    self.assertIn('filename="smoke-vpn.rsc"', export.headers["Content-Disposition"])
                    script = export.read().decode("utf-8")
                    self.assertIn('list="smoke-vpn" address=198.51.100.10', script)
                    self.assertIn("bgp-antifilter:managed:", script)
                api("/api/lists/domain-list-urls", "PUT", {"content": "# saved from panel\n"})
                saved = self.compose("exec", "-T", "bgp-antifilter", "cat", "/etc/bird/generated/config/domain-list-urls.txt").stdout
                self.assertEqual(saved, "# saved from panel\n")
                with opener.open(f"http://127.0.0.1:{admin_port}/assets/vendor/lucide.min.js", timeout=3) as asset:
                    self.assertIn("javascript", asset.headers["Content-Type"])
                    self.assertGreater(len(asset.read()), 10000)
                self.assertIn("starting update", self.compose("logs", "bgp-antifilter").stdout)
                self.assertEqual(len(self.compose("ps", "-q").stdout.split()), 1)
                for service in ("bgp-antifilter",):
                    cid = self.compose("ps", "-q", service).stdout.strip()
                    info = json.loads(subprocess.check_output(["docker", "inspect", cid], text=True))[0]
                    mounted = next(m for m in info["Mounts"] if m["Destination"] == "/etc/bird/generated")
                    self.assertEqual(mounted["Name"], volume)
                    self.assertFalse(info["HostConfig"]["Privileged"])
                    self.assertIn("NET_ADMIN", [cap.removeprefix("CAP_") for cap in info["HostConfig"]["CapDrop"]])
                    self.assertFalse(any(m["Destination"] == "/var/run/docker.sock" for m in info["Mounts"]))
                self.compose("down", "--remove-orphans")
                self.compose("up", "-d")
                self.wait_until(login, 30, "Portainer admin did not restart")
                self.assertEqual(api("/api/lists/domain-list-urls")["content"], "# saved from panel\n")
            finally:
                self.compose("down", "--volumes", "--remove-orphans", check=False)

    def test_restart_uses_previous_snapshot_until_background_refresh_completes(self):
        old_route = "route 192.0.2.0/24 blackhole;"
        new_route = "route 198.51.100.0/24 blackhole;"

        self.compose("up", "-d", "--build", "bgp-antifilter")

        routes_file = self.generated_dir / "routes.conf"
        last_good_file = self.generated_dir / "routes.last-good.conf"
        status_file = self.generated_dir / "status.json"
        runtime_file = self.generated_dir / "runtime.json"

        self.wait_until(
            lambda: routes_file.exists() and old_route in routes_file.read_text(encoding="utf-8"),
            timeout=60,
            message="Initial startup did not generate the first route snapshot",
        )
        self.wait_until(
            lambda: last_good_file.exists() and old_route in last_good_file.read_text(encoding="utf-8"),
            timeout=30,
            message="Initial startup did not persist the last-known-good snapshot",
        )
        self.wait_until(
            lambda: status_file.exists() and self.read_json(status_file)["success"] is True,
            timeout=30,
            message="Initial startup did not finish with success status",
        )
        self.assertTrue((self.config_dir / "domain-list-urls.txt").exists())

        self.server_state["body"] = "198.51.100.0/24\n"
        self.server_state["delay"] = 5

        self.compose("down", "--remove-orphans")
        self.compose("up", "-d", "bgp-antifilter")

        self.wait_until(
            lambda: runtime_file.exists() and self.read_json(runtime_file).get("generation_kind") == "startup",
            timeout=10,
            message="Restart did not enter startup background refresh mode",
        )
        runtime_during_refresh = self.read_json(runtime_file)
        self.assertTrue(runtime_during_refresh.get("startup_snapshot_used"))
        self.assertEqual(runtime_during_refresh.get("last_update_reason", ""), "")
        self.assertIn(old_route, routes_file.read_text(encoding="utf-8"))
        self.assertIn(old_route, last_good_file.read_text(encoding="utf-8"))

        self.wait_until(
            lambda: new_route in routes_file.read_text(encoding="utf-8"),
            timeout=45,
            message="Background refresh did not replace the route snapshot",
        )
        self.wait_until(
            lambda: new_route in last_good_file.read_text(encoding="utf-8"),
            timeout=15,
            message="Background refresh did not update the last-known-good snapshot",
        )
        self.wait_until(
            lambda: status_file.exists() and self.read_json(status_file)["success"] is True,
            timeout=15,
            message="Background refresh did not finish successfully",
        )
        runtime = self.read_json(runtime_file)
        self.assertFalse(runtime.get("generation_active"))
        self.assertEqual(runtime.get("last_update_reason"), "startup")
        self.assertTrue(runtime.get("last_update_success"))

    def test_failed_refresh_keeps_last_known_good_snapshot_and_sets_degraded_state(self):
        old_route = "route 192.0.2.0/24 blackhole;"

        self.compose("up", "-d", "--build", "bgp-antifilter")

        routes_file = self.generated_dir / "routes.conf"
        last_good_file = self.generated_dir / "routes.last-good.conf"
        status_file = self.generated_dir / "status.json"
        runtime_file = self.generated_dir / "runtime.json"

        self.wait_until(
            lambda: last_good_file.exists() and old_route in last_good_file.read_text(encoding="utf-8"),
            timeout=60,
            message="Initial startup did not persist the last-known-good snapshot",
        )

        self.server_state["body"] = "0.0.0.0/0\n"
        result = self.compose("exec", "-T", "bgp-antifilter", "/reload-routes.sh", check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

        self.wait_until(
            lambda: status_file.exists() and self.read_json(status_file).get("degraded") is True,
            timeout=15,
            message="Failed refresh did not set degraded state in status.json",
        )
        self.wait_until(
            lambda: runtime_file.exists() and self.read_json(runtime_file).get("degraded") is True,
            timeout=15,
            message="Failed refresh did not set degraded state in runtime.json",
        )

        status = self.read_json(status_file)
        runtime = self.read_json(runtime_file)
        self.assertFalse(status.get("success"))
        self.assertTrue(status.get("degraded"))
        self.assertIn("previous route snapshot remains active", status.get("degraded_reason", ""))
        self.assertEqual(runtime.get("last_update_reason"), "manual")
        self.assertFalse(runtime.get("last_update_success"))
        self.assertTrue(runtime.get("degraded"))
        self.assertIn(old_route, routes_file.read_text(encoding="utf-8"))
        self.assertIn(old_route, last_good_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
