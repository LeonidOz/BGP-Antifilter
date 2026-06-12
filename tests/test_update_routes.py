import contextlib
import io
import ipaddress
import json
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from bgp_antifilter import update_routes


def net(value):
    return ipaddress.ip_network(value)


def run_main_quiet(argv):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        exit_code = update_routes.main(argv)
    return exit_code, stdout.getvalue()


def parse_first_json_object(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "sources" in value and "routes" in value:
            return value
    raise AssertionError("JSON object not found in output")


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


class SourceRouteCountTests(unittest.TestCase):
    def test_count_source_routes_extracts_valid_ipv4_entries(self):
        count = update_routes.count_source_routes(
            "plain 192.0.2.1 and cidr 198.51.100.0/24\n"
            "bad 999.1.1.1\n"
            '{"cidr4":["203.0.113.0/24"]}\n'
        )

        self.assertEqual(count, 3)


class MainTests(unittest.TestCase):
    def test_dry_run_status_includes_run_reason_and_message(self):
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
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "CACHE_DIR": str(root / "cache"),
                    "CACHE_MAX_AGE": "604800",
                    "ROUTE_UPDATE_REASON": "startup",
                    "ROUTE_UPDATE_MESSAGE": "Refreshing routes after startup using previous route snapshot",
                }
            )

            try:
                exit_code, output_text = run_main_quiet([
                    "--dry-run",
                    "--output",
                    str(output),
                    "--status",
                    str(status),
                    "--metrics",
                    str(metrics),
                ])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            payload = parse_first_json_object(output_text)
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["run_reason"], "startup")
            self.assertEqual(
                payload["run_message"],
                "Refreshing routes after startup using previous route snapshot",
            )

    def test_dry_run_status_can_report_degraded_state(self):
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
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "CACHE_DIR": str(root / "cache"),
                    "CACHE_MAX_AGE": "604800",
                    "DEGRADED": "1",
                    "DEGRADED_REASON": "Previous snapshot remains active",
                }
            )

            try:
                exit_code, output_text = run_main_quiet([
                    "--dry-run",
                    "--output",
                    str(output),
                    "--status",
                    str(status),
                    "--metrics",
                    str(metrics),
                ])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            payload = parse_first_json_object(output_text)
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["degraded"])
            self.assertEqual(payload["degraded_reason"], "Previous snapshot remains active")

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
                    "FETCH_ATTEMPTS": "1",
                    "FETCH_RETRY_DELAY": "0",
                }
            )
            argv = [
                "--output",
                str(output),
                "--status",
                str(status),
                "--metrics",
                str(metrics),
            ]
            socket.getaddrinfo = fake_getaddrinfo

            try:
                exit_code, _ = run_main_quiet(argv)
            finally:
                os.environ.clear()
                os.environ.update(old_env)
                socket.getaddrinfo = old_getaddrinfo

            self.assertEqual(exit_code, 0)
            self.assertIn("route 192.0.2.0/24 blackhole;", output.read_text(encoding="utf-8"))
            self.assertIn('"status": "skipped"', status.read_text(encoding="utf-8"))
            self.assertIn('status="skipped"', metrics.read_text(encoding="utf-8"))

    def test_required_url_without_cache_fails_and_does_not_write_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists = root / "lists.txt"
            include_asns = root / "include-asns.txt"
            include_domains = root / "include-domains.txt"
            exclude_domains = root / "exclude-domains.txt"
            output = root / "routes.conf"
            status = root / "status.json"
            metrics = root / "metrics.prom"

            lists.write_text("file:///missing/source.txt\n", encoding="utf-8")
            include_asns.write_text("", encoding="utf-8")
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "CACHE_DIR": str(root / "cache"),
                    "CACHE_MAX_AGE": "604800",
                    "FETCH_ATTEMPTS": "1",
                    "FETCH_RETRY_DELAY": "0",
                }
            )

            try:
                exit_code, _ = run_main_quiet(["--output", str(output), "--status", str(status), "--metrics", str(metrics)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertEqual(exit_code, 1)
            self.assertFalse(output.exists())
            self.assertIn('"success": false', status.read_text(encoding="utf-8"))

    def test_unavailable_url_source_is_skipped_by_default_when_other_sources_work(self):
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
            missing_url = "file:///missing/source.txt"

            source.write_text("192.0.2.0/24\n", encoding="utf-8")
            lists.write_text(f"{missing_url}\n{source.as_uri()}\n", encoding="utf-8")
            include_asns.write_text("", encoding="utf-8")
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "CACHE_DIR": str(root / "cache"),
                    "CACHE_MAX_AGE": "604800",
                    "FETCH_ATTEMPTS": "1",
                    "FETCH_RETRY_DELAY": "0",
                }
            )

            try:
                exit_code, _ = run_main_quiet(["--output", str(output), "--status", str(status), "--metrics", str(metrics)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            status_text = status.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("route 192.0.2.0/24 blackhole;", output.read_text(encoding="utf-8"))
            self.assertIn('"success": true', status_text)
            self.assertIn('"status": "failed"', status_text)
            self.assertIn('"required": false', status_text)

    def test_unavailable_url_source_fails_in_strict_mode_even_when_other_sources_work(self):
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
            missing_url = "file:///missing/source.txt"

            source.write_text("192.0.2.0/24\n", encoding="utf-8")
            lists.write_text(f"{missing_url}\n{source.as_uri()}\n", encoding="utf-8")
            include_asns.write_text("", encoding="utf-8")
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "REQUIRE_ALL_URL_SOURCES": "1",
                    "CACHE_DIR": str(root / "cache"),
                    "CACHE_MAX_AGE": "604800",
                    "FETCH_ATTEMPTS": "1",
                    "FETCH_RETRY_DELAY": "0",
                }
            )

            try:
                exit_code, _ = run_main_quiet(["--output", str(output), "--status", str(status), "--metrics", str(metrics)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            status_text = status.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 1)
            self.assertFalse(output.exists())
            self.assertIn('"success": false', status_text)
            self.assertIn('"status": "failed"', status_text)
            self.assertIn('"required": true', status_text)

    def test_required_url_uses_fresh_cache_when_fetch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists = root / "lists.txt"
            include_asns = root / "include-asns.txt"
            include_domains = root / "include-domains.txt"
            exclude_domains = root / "exclude-domains.txt"
            output = root / "routes.conf"
            status = root / "status.json"
            metrics = root / "metrics.prom"
            cache = root / "cache"
            url = "file:///missing/source.txt"

            cache.mkdir()
            update_routes.cache_path(cache, "url", url).write_text("192.0.2.0/24\n", encoding="utf-8")
            lists.write_text(f"{url}\n", encoding="utf-8")
            include_asns.write_text("", encoding="utf-8")
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "CACHE_DIR": str(cache),
                    "CACHE_MAX_AGE": "604800",
                    "FETCH_ATTEMPTS": "1",
                    "FETCH_RETRY_DELAY": "0",
                }
            )

            try:
                exit_code, _ = run_main_quiet(["--output", str(output), "--status", str(status), "--metrics", str(metrics)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertEqual(exit_code, 0)
            self.assertIn("route 192.0.2.0/24 blackhole;", output.read_text(encoding="utf-8"))
            self.assertIn('"status": "cache"', status.read_text(encoding="utf-8"))

    def test_exclude_domain_without_cache_fails_update(self):
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
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("missing.example.invalid\n", encoding="utf-8")

            old_env = os.environ.copy()
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
            socket.getaddrinfo = fake_getaddrinfo

            try:
                exit_code, _ = run_main_quiet(["--output", str(output), "--status", str(status), "--metrics", str(metrics)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)
                socket.getaddrinfo = old_getaddrinfo

            self.assertEqual(exit_code, 1)
            self.assertFalse(output.exists())
            self.assertIn('"kind": "exclude-domain"', status.read_text(encoding="utf-8"))

    def test_broad_route_guard_rejects_default_route(self):
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

            source.write_text("0.0.0.0/0\n", encoding="utf-8")
            lists.write_text(f"{source.as_uri()}\n", encoding="utf-8")
            include_asns.write_text("", encoding="utf-8")
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
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

            try:
                exit_code, _ = run_main_quiet(["--output", str(output), "--status", str(status), "--metrics", str(metrics)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertEqual(exit_code, 1)
            self.assertIn("refusing broad IPv4 routes", status.read_text(encoding="utf-8"))

    def test_dry_run_does_not_write_output_status_or_metrics(self):
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
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
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

            try:
                exit_code, _ = run_main_quiet(["--dry-run", "--output", str(output), "--status", str(status), "--metrics", str(metrics)])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertEqual(exit_code, 0)
            self.assertFalse(output.exists())
            self.assertFalse(status.exists())
            self.assertFalse(metrics.exists())

    def test_check_sources_does_not_write_route_status_or_metrics_files(self):
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
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
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

            try:
                exit_code, output_text = run_main_quiet([
                    "--check-sources",
                    "--output",
                    str(output),
                    "--status",
                    str(status),
                    "--metrics",
                    str(metrics),
                ])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertEqual(exit_code, 0)
            self.assertIn('"check_sources": true', output_text)
            self.assertFalse(output.exists())
            self.assertFalse(status.exists())
            self.assertFalse(metrics.exists())

    def test_check_sources_fails_when_required_source_has_no_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists = root / "lists.txt"
            include_asns = root / "include-asns.txt"
            include_domains = root / "include-domains.txt"
            exclude_domains = root / "exclude-domains.txt"

            lists.write_text("file:///missing/source.txt\n", encoding="utf-8")
            include_asns.write_text("", encoding="utf-8")
            include_domains.write_text("", encoding="utf-8")
            exclude_domains.write_text("", encoding="utf-8")

            old_env = os.environ.copy()
            os.environ.update(
                {
                    "LISTS_FILE": str(lists),
                    "INCLUDE_ASNS_FILE": str(include_asns),
                    "INCLUDE_DOMAINS_FILE": str(include_domains),
                    "EXCLUDE_DOMAINS_FILE": str(exclude_domains),
                    "INCLUDE_GOOGLE_RANGES": "0",
                    "CACHE_DIR": str(root / "cache"),
                    "CACHE_MAX_AGE": "604800",
                    "FETCH_ATTEMPTS": "1",
                    "FETCH_RETRY_DELAY": "0",
                }
            )

            try:
                exit_code, output_text = run_main_quiet(["--check-sources"])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertEqual(exit_code, 1)
            self.assertIn('"success": false', output_text)


if __name__ == "__main__":
    unittest.main()
