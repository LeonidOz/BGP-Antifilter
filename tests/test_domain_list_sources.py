import ipaddress
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bgp_antifilter import update_routes
from bgp_antifilter.runtime_paths import LIST_FILE_SPECS


class DomainListSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.files = {name: self.root / f"{name}.txt" for name in LIST_FILE_SPECS}
        for path in self.files.values():
            path.write_text("", encoding="utf-8")
        environment = {spec[0]: str(self.files[name]) for name, spec in LIST_FILE_SPECS.items()}
        environment.update(DNS_RESOLVERS="", REQUIRE_ALL_URL_SOURCES="0",
                           FETCH_ATTEMPTS="1", FETCH_RETRY_DELAY="0",
                           RUNTIME_FILE=str(self.root / "runtime.json"))
        patch = mock.patch.dict(os.environ, environment)
        patch.start()
        self.addCleanup(patch.stop)
        self.source = self.root / "downloaded-domains.txt"
        self.source.write_text("alpha.example\nbeta.example\n", encoding="utf-8")
        self.files["domain-list-urls"].write_text(f"Test list | {self.source.as_uri()}\n", encoding="utf-8")

    def collect(self):
        return update_routes.collect_sources(self.cache, 604800, include_google=False)

    def test_idn_and_invalid_formats(self):
        domains, invalid = update_routes.parse_domain_list(
            "Пример.РФ\nxn--e1afmkfd.xn--p1ai.\n*.example.org\n"
            "0.0.0.0 example.org\n||example.org^\nhttps://example.org\n"
        )
        self.assertEqual(domains, ["xn--e1afmkfd.xn--p1ai"])
        self.assertEqual(invalid, 4)

    def test_plain_url_with_pipe_in_query_keeps_its_address(self):
        url = "https://example.org/list?groups=video|chat"
        self.files["urls"].write_text(url + "\nNamed | " + url + "\n", encoding="utf-8")
        self.assertEqual(update_routes.parse_named_url_list(self.files["urls"]),
                         [{"name": "", "url": url}, {"name": "Named", "url": url}])

    def test_cached_download_and_domain_answers_survive_source_failure(self):
        with mock.patch.object(update_routes.dns_resolver, "resolve_ipv4_addresses", return_value=["192.0.2.10"]):
            self.collect()
        self.source.unlink()
        with mock.patch.object(update_routes.dns_resolver, "resolve_ipv4_addresses", side_effect=OSError("DNS unavailable")):
            failed, sources, errors, _base, include, _exclude = self.collect()
        record = next(source for source in sources if source["kind"] == "domain-list-url")
        self.assertFalse(failed)
        self.assertEqual(errors, [])
        self.assertEqual(record["status"], "cache")
        self.assertEqual(record["resolved_domains"], 2)
        self.assertIn("192.0.2.10/32", "".join(include))

    def test_partial_dns_failure_does_not_drop_working_domains(self):
        def resolve(domain, **_kwargs):
            if domain == "beta.example":
                raise OSError("DNS unavailable")
            return ["192.0.2.10"]
        with mock.patch.object(update_routes.dns_resolver, "resolve_ipv4_addresses", side_effect=resolve):
            failed, sources, _errors, _base, include, _exclude = self.collect()
        record = next(source for source in sources if source["kind"] == "domain-list-url")
        self.assertFalse(failed)
        self.assertEqual(record["resolved_domains"], 1)
        self.assertEqual(record["skipped_domains"], 1)
        self.assertEqual("".join(include), "192.0.2.10/32\n")

    def test_exclusion_wins_over_downloaded_domain(self):
        self.files["exclude-domains"].write_text("192.0.2.10\n", encoding="utf-8")
        with mock.patch.object(update_routes.dns_resolver, "resolve_ipv4_addresses", return_value=["192.0.2.10", "192.0.2.11"]):
            failed, _sources, _errors, base, include, exclude = self.collect()
        routes, _stats = update_routes.parse_and_build_routes(self.root / "routes.conf", base, include, exclude, 8, False)
        self.assertFalse(failed)
        self.assertEqual(routes, [ipaddress.IPv4Network("192.0.2.11/32")])

    def test_unavailable_required_list_stops_update(self):
        self.source.unlink()
        for required in ("0", "1"):
            with self.subTest(required=required), mock.patch.dict(os.environ, {"REQUIRE_ALL_URL_SOURCES": required}):
                failed, _sources, errors, _base, _include, _exclude = self.collect()
                self.assertEqual(failed, required == "1")
                self.assertEqual(errors[0]["kind"], "domain-list-url")

    def test_empty_list_is_reported_as_failed(self):
        self.source.write_text("# empty\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"REQUIRE_ALL_URL_SOURCES": "1"}):
            failed, _sources, errors, _base, _include, _exclude = self.collect()
        self.assertTrue(failed)
        self.assertEqual(errors[0]["error"], "domain list contains no valid domains")
