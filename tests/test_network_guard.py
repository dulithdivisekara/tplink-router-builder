"""Unit tests for NetworkGuard location and Wi-Fi protection."""

import unittest
from unittest.mock import patch
from tplink_router.core.network_guard import NetworkGuard


class TestNetworkGuard(unittest.TestCase):

    @patch.object(NetworkGuard, "get_current_gateway", return_value="192.168.1.1")
    @patch.object(NetworkGuard, "get_current_ssid", return_value="dulith.connect")
    def test_matching_connection_safe(self, mock_ssid, mock_gw):
        is_safe, msg = NetworkGuard.check_safety("http://192.168.1.1", expected_ssid="dulith.connect")
        self.assertTrue(is_safe)
        self.assertIn("Verified", msg)

    @patch.object(NetworkGuard, "get_current_gateway", return_value="172.16.50.1")
    @patch.object(NetworkGuard, "get_current_ssid", return_value="SLIIT-WIFI")
    def test_sliit_campus_wifi_protection(self, mock_ssid, mock_gw):
        is_safe, msg = NetworkGuard.check_safety("http://192.168.1.1", expected_ssid="dulith.connect")
        self.assertFalse(is_safe)
        self.assertIn("Network mismatch", msg)

    @patch.object(NetworkGuard, "get_current_gateway", return_value="192.168.43.1")
    @patch.object(NetworkGuard, "get_current_ssid", return_value="AndroidHotspot")
    def test_mobile_hotspot_gateway_mismatch(self, mock_ssid, mock_gw):
        is_safe, msg = NetworkGuard.check_safety("http://192.168.1.1")
        self.assertFalse(is_safe)
        self.assertIn("Gateway mismatch", msg)

    @patch.object(NetworkGuard, "get_current_gateway", return_value="172.16.50.1")
    def test_force_override(self, mock_gw):
        is_safe, msg = NetworkGuard.check_safety("http://192.168.1.1", force=True)
        self.assertTrue(is_safe)
        self.assertIn("bypassed", msg)


if __name__ == "__main__":
    unittest.main()
