import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bgp_antifilter import dns_resolver, sources
from bgp_antifilter.sources import fetch
from bgp_antifilter.runtime_paths import LIST_FILE_SPECS


class SourceCollectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.files = {}
        environment = {
            "RUNTIME_FILE": str(self.root / "runtime.json"),
            "FETCH_ATTEMPTS": "1", "FETCH_RETRY_DELAY": "0",
        }
        for name, (variable, _default) in LIST_FILE_SPECS.items():
            path = self.root / f"{name}.txt"
            path.write_text("", encoding="utf-8")
            self.files[name] = path
            environment[variable] = str(path)
        patch = mock.patch.dict(os.environ, environment, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def collect(self, include_google):
        with contextlib.redirect_stdout(io.StringIO()):
            return sources.collect_sources(self.cache, 604800, include_google)

    def test_mixed_sources_keep_order_progress_and_route_roles(self):
        contents = {
            "urls": "Primary | https://sources.test/ips.txt\n",
            "domain-list-urls": "Domains | https://sources.test/domains.txt\n",
            "asns": "AS64500\n", "countries": "ru\n",
            "exclude-domains": "192.0.2.10\n",
            "include-domains": "198.51.100.11\noptional.test\n",
        }
        for name, text in contents.items():
            self.files[name].write_text(text, encoding="utf-8")
        payloads = {
            "https://sources.test/ips.txt": "192.0.2.0/24\n",
            "https://sources.test/domains.txt": "alpha.test\nbeta.test\ninvalid/domain\n",
            "https://api.routeviews.org/asn/64500": "203.0.113.0/24\n",
            "https://stat.ripe.net/data/country-resource-list/data.json?resource=ru&v4_format=prefix":
                json.dumps({"data": {"resources": {"ipv4": ["10.0.0.0/24"]}}}),
            "https://www.gstatic.com/ipranges/goog.json": json.dumps({"prefixes": [{"ipv4Prefix": "10.1.0.0/16"}]}),
            "https://www.gstatic.com/ipranges/cloud.json": json.dumps({"prefixes": [{"ipv4Prefix": "10.1.0.0/17"}]}),
        }

        def download(url, progress_callback=None, **_kwargs):
            if progress_callback:
                progress_callback(1, 2)
                progress_callback(2, 2)
            return payloads[url]

        def resolve(domain, **_kwargs):
            if domain == "alpha.test":
                return ["198.51.100.10"]
            raise OSError("DNS unavailable")

        with mock.patch.object(fetch, "fetch_url", side_effect=download) as downloads:
            with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", side_effect=resolve):
                with mock.patch.object(sources, "write_runtime_progress") as progress:
                    failed, records, errors, base, include, exclude = self.collect(True)

        self.assertFalse(failed)
        self.assertEqual(errors, [])
        self.assertEqual([record["kind"] for record in records], [
            "url", "domain-list-url", "asn", "country", "google", "google",
            "exclude-domain", "include-domain", "include-domain",
        ])
        self.assertEqual(base, ["192.0.2.0/24\n", "203.0.113.0/24\n", "10.0.0.0/24\n", "10.1.128.0/17\n"])
        self.assertEqual(include, ["198.51.100.10/32\n", "198.51.100.11/32\n"])
        self.assertEqual(exclude, ["192.0.2.10/32\n"])
        self.assertEqual(records[1]["resolved_domains"], 1)
        self.assertEqual(records[1]["skipped_domain_samples"], ["beta.test"])
        self.assertEqual(records[1]["invalid_lines"], 1)
        self.assertEqual(Path(records[1]["resolved_cache_file"]).read_text(encoding="utf-8"), "198.51.100.10/32\n")
        self.assertEqual(records[-1]["status"], "skipped")
        self.assertFalse(records[-1]["required"])
        self.assertEqual(downloads.call_count, 6)
        self.assertEqual(progress.call_args.kwargs["items_done"], 9)
        self.assertEqual(progress.call_args.kwargs["items_total"], 9)
        self.assertEqual(progress.call_args.kwargs["percent"], 65)
        self.assertTrue(any(call.kwargs.get("current_attempt") == 2 for call in progress.call_args_list))

    def test_required_failures_accumulate_while_optional_domains_remain_skipped(self):
        contents = {
            "urls": "https://sources.test/offline\n",
            "domain-list-urls": "https://sources.test/domains\n",
            "asns": "invalid\n", "countries": "invalid\n",
            "exclude-domains": "exclude.test\n", "include-domains": "optional.test\n",
        }
        for name, text in contents.items():
            self.files[name].write_text(text, encoding="utf-8")

        def download(url, **_kwargs):
            if url.endswith("/domains"):
                return "invalid/domain\n"
            raise RuntimeError("offline")

        with mock.patch.dict(os.environ, {"REQUIRE_ALL_URL_SOURCES": "1"}):
            with mock.patch.object(fetch, "fetch_url", side_effect=download):
                with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", side_effect=OSError("DNS unavailable")):
                    failed, records, errors, base, include, exclude = self.collect(False)

        self.assertTrue(failed)
        self.assertEqual((base, include, exclude), ([], [], []))
        self.assertEqual([error["kind"] for error in errors], ["url", "domain-list-url", "asn", "country", "exclude-domain"])
        self.assertEqual(records[1]["error"], "domain list contains no valid domains")
        self.assertEqual(records[-2]["status"], "failed")
        self.assertEqual(records[-1]["status"], "skipped")
        self.assertNotIn(records[-1], errors)


if __name__ == "__main__":
    unittest.main()
