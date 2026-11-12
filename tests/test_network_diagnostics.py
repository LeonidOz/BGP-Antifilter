import json
import unittest
from unittest import mock

from bgp_antifilter import network_diagnostics


class NetworkDiagnosticsTests(unittest.TestCase):
    def test_bird_ip_diagnostic_reports_assigned_address(self):
        payload = network_diagnostics.bird_ip_diagnostic("192.168.55.5", addresses=["127.0.0.1", "192.168.55.5"])

        self.assertTrue(payload["bird_ip_assigned"])
        self.assertTrue(payload["supported_for_bgp"])
        self.assertEqual(payload["mode"], "linux-host-bgp")
        self.assertEqual(payload["message"], "")

    def test_bird_ip_diagnostic_reports_missing_address_with_clear_message(self):
        payload = network_diagnostics.bird_ip_diagnostic("192.168.77.111", addresses=["127.0.0.1", "192.168.65.6"])

        self.assertFalse(payload["bird_ip_assigned"])
        self.assertFalse(payload["supported_for_bgp"])
        self.assertEqual(payload["mode"], "dev-only")
        self.assertIn("configured BIRD_IP 192.168.77.111 is not assigned inside container", payload["message"])
        self.assertIn("192.168.65.6", payload["message"])

    def test_cli_returns_non_zero_when_assignment_is_required(self):
        with mock.patch.object(network_diagnostics, "local_ipv4_addresses", return_value=["127.0.0.1", "192.168.65.6"]):
            exit_code = network_diagnostics.main(["--bird-ip", "192.168.77.111", "--require-assigned"])

        self.assertEqual(exit_code, 1)
