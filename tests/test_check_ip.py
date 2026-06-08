import importlib.util
import ipaddress
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "check-ip.py"

spec = importlib.util.spec_from_file_location("check_ip", MODULE_PATH)
check_ip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_ip)


class CheckIpTests(unittest.TestCase):
    def test_finds_final_route_and_url_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "routes.conf"
            cache = root / "url.cache"
            status = {
                "sources": [
                    {
                        "kind": "url",
                        "name": "https://example.test/list.json",
                        "url": "https://example.test/list.json",
                        "status": "fresh",
                        "cache_file": str(cache),
                    }
                ]
            }

            routes.write_text("    route 192.0.2.0/24 blackhole;\n", encoding="utf-8")
            cache.write_text('{"cidr4":["192.0.2.0/24"]}', encoding="utf-8")

            address = ipaddress.ip_address("192.0.2.10")
            route_matches = check_ip.matching_networks(
                address,
                check_ip.read_networks(routes, extract=True),
            )
            source_matches = check_ip.find_sources(address, status)

        self.assertEqual(route_matches, [ipaddress.ip_network("192.0.2.0/24")])
        self.assertEqual(source_matches[0][0]["kind"], "url")
        self.assertEqual(source_matches[0][1], [ipaddress.ip_network("192.0.2.0/24")])

    def test_google_match_is_ignored_when_address_is_in_cloud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            google = root / "goog.json"
            cloud = root / "cloud.json"
            status = {
                "sources": [
                    {
                        "kind": "google",
                        "name": "goog.json",
                        "status": "fresh",
                        "cache_file": str(google),
                    },
                    {
                        "kind": "google",
                        "name": "cloud.json",
                        "status": "fresh",
                        "cache_file": str(cloud),
                    },
                ]
            }

            google.write_text(json.dumps({"prefixes": [{"ipv4Prefix": "192.0.2.0/24"}]}), encoding="utf-8")
            cloud.write_text(json.dumps({"prefixes": [{"ipv4Prefix": "192.0.2.0/25"}]}), encoding="utf-8")

            matches = check_ip.find_sources(ipaddress.ip_address("192.0.2.10"), status)

        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
