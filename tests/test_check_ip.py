import json
import tempfile
import unittest
from pathlib import Path

from bgp_antifilter import check_ip


class CheckIpTests(unittest.TestCase):
    def test_main_reports_route_and_source_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "routes.conf"
            cache = root / "source.cache"
            status = root / "status.json"

            routes.write_text("    route 192.0.2.0/24 blackhole;\n", encoding="utf-8")
            cache.write_text("192.0.2.0/24\n", encoding="utf-8")
            status.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "kind": "url",
                                "name": "local",
                                "url": "file:///local",
                                "status": "fresh",
                                "cache_file": str(cache),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = check_ip.main(["192.0.2.10", "--routes", str(routes), "--status", str(status)])

            self.assertEqual(exit_code, 0)

    def test_main_returns_one_when_ip_is_not_in_generated_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "routes.conf"
            status = root / "status.json"

            routes.write_text("    route 192.0.2.0/24 blackhole;\n", encoding="utf-8")
            status.write_text('{"sources":[]}', encoding="utf-8")

            exit_code = check_ip.main(["198.51.100.1", "--routes", str(routes), "--status", str(status)])

            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
