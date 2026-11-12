import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import urlparse

from bgp_antifilter import admin_server
from bgp_antifilter import export_address_list as exporter


ROUTES = "route 192.0.2.0/24 blackhole;\nroute 198.51.100.7/32 blackhole;\n"


class AddressListExportTests(unittest.TestCase):
    def test_export_preserves_prefixes_and_emits_host_addresses(self):
        script = exporter.export_rsc(ROUTES, "vpn-list")
        self.assertIn('add list="vpn-list" address=192.0.2.0/24', script)
        self.assertIn('add list="vpn-list" address=198.51.100.7 comment=', script)
        self.assertNotIn("/ip route", script)
        self.assertEqual(script.count(" do={ /ip firewall address-list add "), 2)

    def test_cleanup_is_last_and_scoped_to_owned_entries_and_list(self):
        script = exporter.export_rsc(ROUTES)
        lines = script.splitlines()
        self.assertIn('remove [find where list="bgp-antifilter" and comment~"^bgp-antifilter:managed:"', lines[-1])
        self.assertIn("and comment!=", lines[-1])
        self.assertEqual(script.count(" remove "), 1)
        self.assertIn('else={ :local owned [', script)
        self.assertIn('and comment~"^bgp-antifilter:managed:"]', script)
        self.assertIn("set $owned comment=", script)

    def test_reordered_and_duplicate_routes_have_identical_export(self):
        other = "\n# snapshot\n" + "\n".join(reversed(ROUTES.splitlines())) + "\n" + ROUTES
        self.assertEqual(exporter.export_rsc(ROUTES), exporter.export_rsc(other))
        self.assertNotEqual(exporter.export_rsc(ROUTES), exporter.export_rsc("route 203.0.113.0/24 blackhole;"))

    def test_rejects_empty_invalid_and_ipv6_snapshots(self):
        for text in ("", "# empty", "route 192.0.2.0/24 blackhole;\nbroken", "route 999.0.0.0/24 blackhole;", "route 192.0.2.7/24 blackhole;", "route 2001:db8::/32 blackhole;"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                exporter.export_rsc(text)

    def test_rejects_script_injection_in_list_name(self):
        for name in ("", "a" * 65, 'a"; /system reboot;', "$var", "a\nb", "a\\b", "vpn list"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                exporter.export_rsc(ROUTES, name)
        self.assertIn('list="VPN_1.edge-2"', exporter.export_rsc(ROUTES, "VPN_1.edge-2"))

    def test_cli_writes_crlf_and_does_not_overwrite_output_on_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "routes.conf", Path(tmp) / "vpn.rsc"
            source.write_text(ROUTES, encoding="utf-8")
            self.assertEqual(exporter.main(["--routes", str(source), "--output", str(output)]), 0)
            previous = output.read_bytes()
            self.assertIn(b"\r\n", previous)
            source.write_text("", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                exporter.main(["--routes", str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), previous)

    def test_snapshot_rejects_active_update_or_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, lock = Path(tmp) / "routes.conf", Path(tmp) / "update.lock"
            source.write_text(ROUTES, encoding="utf-8")
            self.assertEqual(exporter.read_snapshot(source, lock), ROUTES)
            lock.mkdir()
            with self.assertRaisesRegex(ValueError, "in progress"):
                exporter.read_snapshot(source, lock)
            with mock.patch.object(Path, "exists", return_value=False), mock.patch.object(Path, "stat", side_effect=[mock.Mock(st_ino=1, st_mtime_ns=1, st_size=1), mock.Mock(st_ino=1, st_mtime_ns=2, st_size=1)]):
                with self.assertRaisesRegex(ValueError, "changed"):
                    exporter.read_snapshot(source, lock)

    def test_api_requires_authentication(self):
        handler = object.__new__(admin_server.AdminHandler)
        handler.require_auth = mock.Mock(return_value=False)
        handler.send_file_text = mock.Mock()
        path = "/api/routes/address-list.rsc"
        handler.handle_api_get(path, urlparse(path))
        handler.send_file_text.assert_not_called()
        handler.require_auth.assert_called_once()

    def test_api_uses_confirmed_snapshot_not_candidate_and_custom_name(self):
        handler = object.__new__(admin_server.AdminHandler)
        handler.require_auth = mock.Mock(return_value=True)
        handler.send_file_text = mock.Mock()
        with mock.patch.object(admin_server, "read_snapshot", return_value=ROUTES) as read:
            handler.handle_api_get("/api/routes/address-list.rsc", urlparse("/api/routes/address-list.rsc?list=vpn"))
        read.assert_called_once_with(admin_server.LAST_GOOD_ROUTES_FILE, admin_server.UPDATE_LOCK_DIR)
        handler.send_file_text.assert_called_once_with(exporter.export_rsc(ROUTES, "vpn"), "vpn.rsc")

    def test_api_rejects_invalid_name_and_unavailable_snapshots(self):
        handler = object.__new__(admin_server.AdminHandler)
        handler.require_auth = mock.Mock(return_value=True)
        handler.send_json = mock.Mock()
        for query in ("?list=", "?list=%22%3Bbad"):
            with self.subTest(query=query):
                handler.handle_api_get("/api/routes/address-list.rsc", urlparse("/api/routes/address-list.rsc" + query))
                self.assertEqual(handler.send_json.call_args.args[1], 400)
        for error in (FileNotFoundError("missing"), ValueError("empty")):
            with self.subTest(error=error), mock.patch.object(admin_server, "read_snapshot", side_effect=error):
                handler.handle_api_get("/api/routes/address-list.rsc", urlparse("/api/routes/address-list.rsc"))
                self.assertEqual(handler.send_json.call_args.args[1], 503)


if __name__ == "__main__":
    unittest.main()
