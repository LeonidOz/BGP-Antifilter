import importlib.util
import ipaddress
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "update-routes.py"

spec = importlib.util.spec_from_file_location("update_routes", MODULE_PATH)
update_routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_routes)


def net(value):
    return ipaddress.ip_network(value)


class CacheTests(unittest.TestCase):
    def test_read_cache_rejects_expired_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "source.cache"
            cache_file.write_text("192.0.2.0/24\n", encoding="utf-8")
            old = time.time() - 10
            os.utime(cache_file, (old, old))

            text, age = update_routes.read_cache(cache_file, int(time.time()), max_age=5)

        self.assertIsNone(text)
        self.assertGreater(age, 5)

    def test_read_cache_accepts_fresh_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "source.cache"
            cache_file.write_text("192.0.2.0/24\n", encoding="utf-8")

            text, age = update_routes.read_cache(cache_file, int(time.time()), max_age=60)

        self.assertEqual(text, "192.0.2.0/24\n")
        self.assertGreaterEqual(age, 0)


class GoogleRangeTests(unittest.TestCase):
    def test_subtract_networks_removes_cloud_ranges(self):
        result = update_routes.subtract_networks(
            [net("192.0.2.0/24")],
            [net("192.0.2.0/25")],
        )

        self.assertEqual(result, [net("192.0.2.128/25")])


class MainTests(unittest.TestCase):
    def test_missing_include_domain_is_skipped_without_failing_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            lists = root / "lists.txt"
            include_asns = root / "include-asns.txt"
            include_domains = root / "include-domains.txt"
            exclude_domains = root / "exclude-domains.txt"
            output = root / "routes.conf"
            status = root / "status.json"
            metrics = root / "metrics.prom"

            source.write_text("192.0.2.0/24\n", encoding="utf-8")
            lists.write_text(f"{source.as_uri()}\n", encoding="utf-8")
            include_asns.write_text("", encoding="utf-8")
            include_domains.write_text("missing.example.invalid\n", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            old_argv = update_routes.sys.argv
            old_getaddrinfo = socket.getaddrinfo

            def fake_getaddrinfo(*args, **kwargs):
                raise socket.gaierror("not found")

            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "CACHE_DIR": str(root / "cache"),
                    "CACHE_MAX_AGE": "604800",
                }
            )
            update_routes.sys.argv = [
                "update-routes.py",
                "--output",
                str(output),
                "--status",
                str(status),
                "--metrics",
                str(metrics),
            ]
            socket.getaddrinfo = fake_getaddrinfo

            try:
                exit_code = update_routes.main()
            finally:
                os.environ.clear()
                os.environ.update(old_env)
                update_routes.sys.argv = old_argv
                socket.getaddrinfo = old_getaddrinfo

            self.assertEqual(exit_code, 0)
            self.assertIn("route 192.0.2.0/24 blackhole;", output.read_text(encoding="utf-8"))
            self.assertIn('"status": "skipped"', status.read_text(encoding="utf-8"))
            self.assertIn('status="skipped"', metrics.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
