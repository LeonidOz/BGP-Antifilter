"""Opt-in migration test using temporary named volumes; works on Docker Desktop."""

import json
import os
import shutil
import subprocess
import time
import unittest
import uuid


@unittest.skipUnless(os.environ.get("RUN_DOCKER_CONFIG_MIGRATION") == "1" and shutil.which("docker"),
                     "Requires RUN_DOCKER_CONFIG_MIGRATION=1 and Docker")
class ConfigVolumeTests(unittest.TestCase):
    def setUp(self):
        self.image = os.environ.get("CONFIG_MIGRATION_IMAGE", "bgp-antifilter:config-migration-test")
        self.prefix = "bgp-antifilter-config-test-" + uuid.uuid4().hex[:12]
        self.container = self.prefix + "-app"
        self.data = self.prefix + "-data"
        self.configuration = self.prefix + "-config"
        self.fresh_data = self.prefix + "-fresh-data"
        self.volumes = []
        self.addCleanup(self.cleanup)
        for volume in (self.data, self.configuration, self.fresh_data):
            self.docker("volume", "create", volume)
            self.volumes.append(volume)
        seed = '''
from pathlib import Path
import json
p = Path('/etc/bird/generated')
c = p / 'config'
c.mkdir()
for name in ('domain-list-urls.txt', 'include-asns.txt', 'include-countries.txt', 'include-domains.txt', 'exclude-domains.txt'):
    (c / name).write_text('')
(c / 'lists.txt').write_text('file:///etc/bird/generated/source.txt\\n')
(p / 'source.txt').write_text('192.0.2.0/24\\n')
(p / 'routes.last-good.conf').write_text('    route 192.0.2.0/24 blackhole;\\n')
(p / 'settings.json').write_text(json.dumps({'values': {'UPDATE_INTERVAL': '86400', 'INCLUDE_GOOGLE_RANGES': '0', 'FETCH_TIMEOUT': '11'}}))
(p / 'settings.env').write_text('UPDATE_INTERVAL=86400\\nINCLUDE_GOOGLE_RANGES=0\\nFETCH_TIMEOUT=11\\n')
(p / 'list-backups').mkdir()
(p / 'list-backups/lists.txt.old.bak').write_text('old backup\\n')
(p / 'cache').mkdir()
(p / 'cache/original.cache').write_text('retained cache\\n')
'''
        self.docker("run", "--rm", "-v", f"{self.data}:/etc/bird/generated", "--entrypoint", "python3", self.image, "-c", seed)

    def docker(self, *args, check=True, timeout=120):
        return subprocess.run(["docker", *args], check=check, text=True, capture_output=True, timeout=timeout)

    def cleanup(self):
        self.docker("rm", "-f", self.container, check=False)
        for volume in reversed(self.volumes):
            self.docker("volume", "rm", volume, check=False)

    def start(self, data, image=None, *, legacy_layout=False):
        environment = {
            "CONFIG_DIR": "/etc/bird/config", "MY_AS": "64500", "MT_AS": "65455",
            "MT_IP": "127.0.0.2", "BIRD_IP": "127.0.0.1", "ROUTER_ID": "127.0.0.1",
            "BGP_COMMUNITY": "65432,500", "ADMIN_ENABLED": "1", "ADMIN_PORT": "8080",
            "ADMIN_PASSWORD": "migration-test", "HEALTHCHECK_REQUIRE_BGP": "0",
            "SETTINGS_FILE": "/etc/bird/config/settings.json", "SETTINGS_ENV_FILE": "/etc/bird/config/settings.env",
            "LISTS_FILE": "/etc/bird/config/lists.txt", "DOMAIN_LIST_URLS_FILE": "/etc/bird/config/domain-list-urls.txt",
            "INCLUDE_ASNS_FILE": "/etc/bird/config/include-asns.txt", "INCLUDE_COUNTRIES_FILE": "/etc/bird/config/include-countries.txt",
            "INCLUDE_DOMAINS_FILE": "/etc/bird/config/include-domains.txt", "EXCLUDE_DOMAINS_FILE": "/etc/bird/config/exclude-domains.txt",
        }
        command = ["run", "-d", "--name", self.container, "-v", f"{data}:/etc/bird/generated"]
        if legacy_layout:
            environment.pop("CONFIG_DIR")
            for key in ("LISTS_FILE", "DOMAIN_LIST_URLS_FILE", "INCLUDE_ASNS_FILE", "INCLUDE_COUNTRIES_FILE",
                        "INCLUDE_DOMAINS_FILE", "EXCLUDE_DOMAINS_FILE"):
                environment[key] = environment[key].replace("/etc/bird/config/", "/etc/bird/generated/config/")
            for key in ("SETTINGS_FILE", "SETTINGS_ENV_FILE"):
                environment[key] = environment[key].replace("/etc/bird/config/", "/etc/bird/generated/")
        else:
            command.extend(["-v", f"{self.configuration}:/etc/bird/config"])
        for key, value in environment.items():
            command.extend(["-e", f"{key}={value}"])
        self.docker(*command, image or self.image)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                payload = self.api("/api/status")
                if payload.get("bird", {}).get("ok") and payload.get("status", {}).get("success") and not payload.get("runtime", {}).get("generation_active"):
                    # The admin can clear an apparently idle generation before
                    # the scheduler starts its delayed snapshot refresh. Wait
                    # for the scheduler's completion flag as well.
                    refreshing = self.docker("exec", self.container, "test", "-f",
                                             "/run/bgp-antifilter/startup-refresh-needed", check=False)
                    if refreshing.returncode == 1:
                        return payload
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(0.25)
        logs = self.docker("logs", self.container, check=False)
        self.fail("Container did not become ready:\n" + logs.stdout[-6000:] + logs.stderr[-2000:])

    def api(self, path, method="GET", payload=None):
        code = '''
import http.cookiejar
import json
import sys
import urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
login = urllib.request.Request('http://127.0.0.1:8080/api/login', json.dumps({'password': 'migration-test'}).encode(), {'Content-Type': 'application/json'})
opener.open(login, timeout=3).close()
body = None if sys.argv[3] == 'null' else sys.argv[3].encode()
request = urllib.request.Request('http://127.0.0.1:8080' + sys.argv[1], body, {'Content-Type': 'application/json'}, method=sys.argv[2])
with opener.open(request, timeout=5) as response:
    print(response.read().decode())
'''
        return json.loads(self.docker("exec", self.container, "python3", "-c", code, path, method, json.dumps(payload)).stdout)

    def read(self, path):
        return self.docker("exec", self.container, "cat", path).stdout

    def remove_container(self):
        self.docker("rm", "-f", self.container)

    def test_legacy_stack_paths_survive_image_upgrade_and_later_volume_migration(self):
        self.start(self.data, legacy_layout=True)
        content = "# edited using the old stack\nfile:///etc/bird/generated/source.txt\n"
        saved = self.api("/api/lists/urls", "PUT", {"content": content})
        self.assertTrue(saved["backup"].startswith("/etc/bird/generated/list-backups/"))
        values = self.api("/api/settings")["values"]
        values["FETCH_TIMEOUT"] = "17"
        self.api("/api/settings", "PUT", {"values": values})
        self.remove_container()

        self.start(self.data, legacy_layout=True)
        self.assertEqual(self.api("/api/lists/urls")["content"], content)
        self.assertEqual(self.api("/api/settings")["values"]["FETCH_TIMEOUT"], "17")
        self.remove_container()

        self.start(self.data)
        self.assertEqual(self.api("/api/lists/urls")["content"], content)
        self.assertEqual(self.api("/api/settings")["values"]["FETCH_TIMEOUT"], "17")
        self.assertEqual(self.read("/etc/bird/generated/config/lists.txt"), content)

    def test_old_volume_migrates_and_config_survives_restart_reset_and_image_rollback(self):
        runtime = self.start(self.data)["runtime"]
        self.assertEqual(runtime["update_interval_seconds"], 86400)
        self.assertEqual(runtime["last_update_reason"], "startup")
        self.assertEqual(self.api("/api/settings")["values"]["FETCH_TIMEOUT"], "11")
        for name in ("settings.json", "settings.env"):
            self.assertEqual(self.read("/etc/bird/config/" + name), self.read("/etc/bird/generated/" + name))
        self.assertEqual(self.read("/etc/bird/config/list-backups/lists.txt.old.bak"), "old backup\n")
        self.assertEqual(self.read("/etc/bird/generated/cache/original.cache"), "retained cache\n")
        self.assertEqual(self.read("/etc/bird/config/include-countries.txt"), "")
        self.docker("exec", "-w", "/tmp", self.container, "/healthcheck.sh")
        self.docker("exec", "-w", "/tmp", self.container, "/reload-routes.sh")

        # Move a test-local file source into the persistent config volume so
        # rebuilding all generated state below needs no external network.
        self.docker("exec", self.container, "python3", "-c",
                    "from pathlib import Path; Path('/etc/bird/config/source.txt').write_text('198.51.100.0/24\\n')")
        content = "# edited after migration\nfile:///etc/bird/config/source.txt\n"
        saved = self.api("/api/lists/urls", "PUT", {"content": content})
        self.assertTrue(saved["backup"].startswith("/etc/bird/config/list-backups/"))
        self.assertEqual(self.read("/etc/bird/generated/config/lists.txt"), "file:///etc/bird/generated/source.txt\n")
        values = self.api("/api/settings")["values"]
        values["FETCH_TIMEOUT"] = "15"
        self.api("/api/settings", "PUT", {"values": values})
        self.remove_container()

        self.start(self.data)
        self.assertEqual(self.api("/api/lists/urls")["content"], content)
        self.assertEqual(self.api("/api/settings")["values"]["FETCH_TIMEOUT"], "15")
        self.assertIn("198.51.100.0/24", self.read("/etc/bird/generated/routes.last-good.conf"))
        self.remove_container()

        rollback_image = os.environ.get("CONFIG_ROLLBACK_IMAGE")
        if rollback_image:
            self.start(self.data, rollback_image)
            self.assertEqual(self.api("/api/settings")["values"]["FETCH_TIMEOUT"], "15")
            self.assertEqual(self.api("/api/lists/urls")["content"], content)
            self.remove_container()

        fresh = self.start(self.fresh_data)
        self.assertFalse(fresh["runtime"]["startup_snapshot_used"])
        self.assertEqual(self.api("/api/lists/urls")["content"], content)
        self.assertEqual(self.api("/api/settings")["values"]["FETCH_TIMEOUT"], "15")
        self.assertIn("198.51.100.0/24", self.read("/etc/bird/generated/routes.last-good.conf"))
        self.assertEqual(self.read("/etc/bird/config/list-backups/lists.txt.old.bak"), "old backup\n")
