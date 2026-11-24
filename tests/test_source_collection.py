import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
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
        percentages = [call.kwargs["percent"] for call in progress.call_args_list]
        self.assertEqual(percentages, sorted(percentages))
        self.assertIn(30, percentages)
        self.assertIn(60, percentages)

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

    def test_all_lists_are_downloaded_before_globally_deduplicated_dns(self):
        self.files["domain-list-urls"].write_text(
            "First | https://sources.test/one\nSecond | https://sources.test/two\n", encoding="utf-8")
        self.files["include-domains"].write_text("SHARED.TEST.\nПример.РФ\n192.0.2.9\n", encoding="utf-8")
        self.files["exclude-domains"].write_text("shared.test\n", encoding="utf-8")
        downloaded = set()

        def download(url, **_kwargs):
            downloaded.add(url)
            return "Shared.Test.\nshared.test\nxn--e1afmkfd.xn--p1ai\nmissing.test\n"

        def resolve(domain, **_kwargs):
            self.assertEqual(len(downloaded), 2)
            if domain == "missing.test":
                raise OSError("DNS unavailable")
            return ["192.0.2.10"]

        with mock.patch.object(fetch, "fetch_url", side_effect=download):
            with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", side_effect=resolve) as resolver:
                failed, records, errors, _base, include, exclude = self.collect(False)
        self.assertFalse(failed)
        self.assertEqual(errors, [])
        self.assertCountEqual([call.args[0] for call in resolver.call_args_list],
                              ["shared.test", "xn--e1afmkfd.xn--p1ai", "missing.test"])
        for record in records[:2]:
            self.assertEqual(record["domains"], 3)
            self.assertEqual(record["resolved_domains"], 2)
            self.assertEqual(record["skipped_domains"], 1)
            self.assertEqual(set(record["_domain_addresses"]), {"shared.test", "xn--e1afmkfd.xn--p1ai"})
        self.assertIn("192.0.2.9/32\n", include)
        self.assertEqual(exclude, ["192.0.2.10/32\n"])

    def test_shared_dns_failure_keeps_source_specific_legacy_caches(self):
        self.files["domain-list-urls"].write_text("https://sources.test/domains\n", encoding="utf-8")
        self.files["include-domains"].write_text("shared.test\n", encoding="utf-8")
        self.files["exclude-domains"].write_text("shared.test\n", encoding="utf-8")
        for kind, address in (("domain-list-domain", "192.0.2.1"),
                              ("include-domain", "192.0.2.2"), ("exclude-domain", "192.0.2.3")):
            fetch.cache_path(self.cache, kind, "shared.test").write_text(address + "/32\n", encoding="utf-8")
        with mock.patch.object(fetch, "fetch_url", return_value="shared.test\n"):
            with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", side_effect=OSError("offline")) as resolver:
                failed, records, errors, _base, include, exclude = self.collect(False)
        self.assertFalse(failed)
        self.assertEqual(errors, [])
        resolver.assert_called_once()
        self.assertEqual(include, ["192.0.2.1/32\n", "192.0.2.2/32\n"])
        self.assertEqual(exclude, ["192.0.2.3/32\n"])
        self.assertEqual(records[0]["cached_domains"], 1)

    def test_dns_workers_are_parallel_and_bounded(self):
        self.files["include-domains"].write_text(
            "".join(f"host-{index}.test\n" for index in range(80)), encoding="utf-8")
        for workers in (16, 32):
            with self.subTest(workers=workers):
                lock = threading.Lock()
                reached_limit = threading.Event()
                active = 0
                peak = 0

                def resolve(_domain, **_kwargs):
                    nonlocal active, peak
                    with lock:
                        active += 1
                        peak = max(peak, active)
                        if active == workers:
                            reached_limit.set()
                    self.assertTrue(reached_limit.wait(5), "DNS work was not concurrent")
                    time.sleep(0.002)
                    with lock:
                        active -= 1
                    return ["192.0.2.10"]

                with mock.patch.dict(os.environ, {"DNS_WORKERS": str(workers)}):
                    with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", side_effect=resolve):
                        failed, *_rest = self.collect(False)
                self.assertFalse(failed)
                self.assertEqual(peak, workers)

    def test_download_workers_are_parallel_bounded_and_share_duplicate_cache(self):
        self.files["urls"].write_text(
            "".join(f"Source {index} | https://sources.test/{index}\n" for index in range(8))
            + "Duplicate | https://sources.test/0\n", encoding="utf-8")
        lock = threading.Lock()
        reached_limit = threading.Event()
        active = 0
        peak = 0

        def download(_url, **_kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 3:
                    reached_limit.set()
            self.assertTrue(reached_limit.wait(5), "Downloads were not concurrent")
            time.sleep(0.002)
            with lock:
                active -= 1
            return "192.0.2.0/24\n"

        with mock.patch.dict(os.environ, {"FETCH_WORKERS": "3"}):
            with mock.patch.object(fetch, "fetch_url", side_effect=download) as downloads:
                failed, records, errors, base, _include, _exclude = self.collect(False)
        self.assertFalse(failed)
        self.assertEqual(errors, [])
        self.assertEqual(peak, 3)
        self.assertEqual(downloads.call_count, 8)
        self.assertEqual(len(base), 9)
        self.assertEqual([record["name"] for record in records[:9]],
                         [f"Source {index}" for index in range(8)] + ["Duplicate"])

    def test_invalid_concurrency_settings_fail_before_network_work(self):
        for key, invalid in (("DNS_WORKERS", "15"), ("DNS_WORKERS", "129"),
                             ("DNS_QPS", "0"), ("DNS_QPS", "1001"),
                             ("FETCH_WORKERS", "0"), ("FETCH_WORKERS", "33"),
                             ("DNS_RESOLVE_TIMEOUT", "nan"), ("DNS_RESOLVE_TIMEOUT", "inf")):
            with self.subTest(key=key, invalid=invalid), mock.patch.dict(os.environ, {key: invalid}):
                with mock.patch.object(fetch, "fetch_url") as download:
                    with self.assertRaises(SystemExit):
                        self.collect(False)
                    download.assert_not_called()

    def test_cached_include_cannot_hide_required_exclude_failure(self):
        self.files["include-domains"].write_text("shared.test\n", encoding="utf-8")
        self.files["exclude-domains"].write_text("shared.test\n", encoding="utf-8")
        fetch.cache_path(self.cache, "include-domain", "shared.test").write_text("192.0.2.1/32\n", encoding="utf-8")
        with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", side_effect=OSError("offline")) as resolver:
            failed, records, errors, _base, include, exclude = self.collect(False)
        self.assertTrue(failed)
        resolver.assert_called_once()
        self.assertEqual(include, ["192.0.2.1/32\n"])
        self.assertEqual(exclude, [])
        self.assertEqual([record["kind"] for record in errors], ["exclude-domain"])

    def test_country_fallback_downloads_are_shared_between_countries(self):
        self.files["countries"].write_text("ru\nus\n", encoding="utf-8")

        def download(url, **_kwargs):
            if "stat.ripe.net" in url:
                raise RuntimeError("offline")
            return "arin|US|ipv4|192.0.2.0|256|20260101|allocated\nripencc|RU|ipv4|198.51.100.0|256|20260101|allocated\n"

        with mock.patch.object(fetch, "fetch_url", side_effect=download) as downloads:
            failed, records, errors, base, _include, _exclude = self.collect(False)
        self.assertFalse(failed)
        self.assertEqual(errors, [])
        self.assertEqual(downloads.call_count, 7)
        self.assertEqual([record["source"] for record in records[:2]], ["delegated-stats", "delegated-stats"])
        self.assertEqual(base, ["198.51.100.0/24\n", "192.0.2.0/24\n"])

    def test_custom_source_dns_uses_dns_timeout_independently_of_http_timeout(self):
        connection = mock.MagicMock()
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = b"192.0.2.0/24\n"
        with mock.patch.dict(os.environ, {"DNS_RESOLVE_TIMEOUT": "0.5", "FETCH_TIMEOUT": "30"}):
            with mock.patch.object(dns_resolver, "resolve_ipv4_addresses", return_value=["203.0.113.5"]) as resolve:
                with mock.patch.object(fetch.http.client, "HTTPConnection", return_value=connection) as http:
                    text = fetch.fetch_url("http://sources.test/routes", dns_nameservers=["1.1.1.1"])
        self.assertEqual(text, "192.0.2.0/24\n")
        resolve.assert_called_once_with("sources.test", nameservers=["1.1.1.1"], timeout=0.5)
        http.assert_called_once_with("203.0.113.5", 80, timeout=30)


if __name__ == "__main__":
    unittest.main()
