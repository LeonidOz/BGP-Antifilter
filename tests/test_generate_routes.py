import contextlib
import io
import ipaddress
import sys
import tempfile
import unittest
from pathlib import Path

from bgp_antifilter import generate_routes


def net(value):
    return ipaddress.ip_network(value)


def run_quiet(func, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args, **kwargs)


class ReadNetworksTests(unittest.TestCase):
    def test_extracts_ipv4_and_skips_invalid_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.txt"
            source.write_text(
                "plain 192.0.2.10 and cidr 198.51.100.0/24\n"
                "bad 999.1.1.1 and malformed 203.0.113.1/99\n",
                encoding="utf-8",
            )

            networks, invalid = run_quiet(generate_routes.read_networks, source, extract=True)

        self.assertEqual(networks, [net("192.0.2.10/32"), net("198.51.100.0/24")])
        self.assertEqual(invalid, 2)

    def test_extracts_cidr_routes_from_json_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.json"
            source.write_text(
                '{"site":"chatgpt.com","cidr4":["192.0.2.0/24","198.51.100.10/32"]}',
                encoding="utf-8",
            )

            networks, invalid = generate_routes.read_networks(source, extract=True)

        self.assertEqual(networks, [net("192.0.2.0/24"), net("198.51.100.10/32")])
        self.assertEqual(invalid, 0)

    def test_reads_one_network_per_line_without_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.txt"
            source.write_text("192.0.2.1\n198.51.100.0/24\n\n", encoding="utf-8")

            networks, invalid = generate_routes.read_networks(source)

        self.assertEqual(networks, [net("192.0.2.1/32"), net("198.51.100.0/24")])
        self.assertEqual(invalid, 0)


class BuildRoutesTests(unittest.TestCase):
    def test_excludes_single_address_from_larger_network(self):
        routes, applied = generate_routes.build_routes(
            [net("192.0.2.0/30")],
            [net("192.0.2.1/32")],
            [],
        )

        self.assertEqual(routes, [net("192.0.2.0/32"), net("192.0.2.2/31")])
        self.assertEqual(applied, 1)

    def test_drops_network_fully_covered_by_exclude(self):
        routes, applied = generate_routes.build_routes(
            [net("192.0.2.0/24")],
            [net("192.0.2.0/24")],
            [],
        )

        self.assertEqual(routes, [])
        self.assertEqual(applied, 1)

    def test_deduplicates_and_sorts_routes(self):
        routes, applied = generate_routes.build_routes(
            [net("198.51.100.2/32"), net("192.0.2.0/24")],
            [],
            [net("198.51.100.2/32")],
        )

        self.assertEqual(routes, [net("192.0.2.0/24"), net("198.51.100.2/32")])
        self.assertEqual(applied, 0)

    def test_removes_routes_covered_by_larger_networks(self):
        routes, applied = generate_routes.build_routes(
            [net("192.0.2.0/24"), net("192.0.2.10/32")],
            [],
            [net("192.0.2.20/32")],
        )

        self.assertEqual(routes, [net("192.0.2.0/24")])
        self.assertEqual(applied, 0)

    def test_collapses_adjacent_networks(self):
        routes, applied = generate_routes.build_routes(
            [net("192.0.2.0/25"), net("192.0.2.128/25")],
            [],
            [],
        )

        self.assertEqual(routes, [net("192.0.2.0/24")])
        self.assertEqual(applied, 0)

    def test_build_routes_with_stats_explains_final_count(self):
        routes, applied, stats = generate_routes.build_routes_with_stats(
            [net("192.0.2.0/25"), net("192.0.2.128/25"), net("198.51.100.0/24")],
            [net("198.51.100.10/32")],
            [net("192.0.2.1/32")],
        )

        self.assertEqual(routes, [net("192.0.2.0/24"), net("198.51.100.0/29"), net("198.51.100.8/31"), net("198.51.100.11/32"), net("198.51.100.12/30"), net("198.51.100.16/28"), net("198.51.100.32/27"), net("198.51.100.64/26"), net("198.51.100.128/25")])
        self.assertEqual(applied, 1)
        self.assertEqual(stats["candidate"], 4)
        self.assertEqual(stats["after_exclusions"], 11)
        self.assertEqual(stats["collapsed_removed"], 2)

    def test_does_not_collapse_across_excluded_addresses(self):
        routes, applied = generate_routes.build_routes(
            [net("192.0.2.0/30")],
            [net("192.0.2.1/32")],
            [],
        )

        self.assertEqual(routes, [net("192.0.2.0/32"), net("192.0.2.2/31")])
        self.assertEqual(applied, 1)


class MainTests(unittest.TestCase):
    def test_main_writes_bird_static_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base.txt"
            exclude = tmp_path / "exclude.txt"
            include = tmp_path / "include.txt"
            output = tmp_path / "routes.conf"

            base.write_text("192.0.2.0/30\n", encoding="utf-8")
            exclude.write_text("192.0.2.1\n", encoding="utf-8")
            include.write_text("198.51.100.10\n", encoding="utf-8")

            old_argv = sys.argv
            sys.argv = ["generate-routes.py"]
            try:
                exit_code = run_quiet(generate_routes.main, [str(base), str(exclude), str(include), str(output)])
            finally:
                sys.argv = old_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "    route 192.0.2.0/32 blackhole;\n"
                "    route 192.0.2.2/31 blackhole;\n"
                "    route 198.51.100.10/32 blackhole;\n",
            )


if __name__ == "__main__":
    unittest.main()
