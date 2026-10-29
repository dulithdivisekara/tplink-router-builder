"""Unit tests for newly added advanced router management features."""

import unittest
from unittest.mock import MagicMock, patch

from tplink_router.clients.mr_client import TPLinkMRClient, ActItem


class TestAdvancedMRFeatures(unittest.TestCase):

    def setUp(self):
        self.client = TPLinkMRClient("http://192.168.1.1", "secret")
        self.client.auth.is_authenticated = True

    def test_get_connected_clients(self):
        mock_response = {
            "0": [
                {
                    "hostName": "Dulith-Laptop",
                    "IPAddress": "192.168.1.100",
                    "MACAddress": "AA:BB:CC:DD:EE:01",
                    "leaseTimeRemaining": "7200",
                    "addressSource": "DHCP",
                },
                {
                    "hostName": "Pixel-Phone",
                    "IPAddress": "192.168.1.101",
                    "MACAddress": "AA:BB:CC:DD:EE:02",
                    "leaseTimeRemaining": "-1",
                    "addressSource": "Static",
                }
            ]
        }
        with patch.object(self.client, "req_act", return_value=mock_response):
            clients = self.client.get_connected_clients()
            self.assertEqual(len(clients), 2)
            self.assertEqual(clients[0]["hostname"], "Dulith-Laptop")
            self.assertEqual(clients[0]["ip"], "192.168.1.100")
            self.assertEqual(clients[0]["mac"], "AA-BB-CC-DD-EE-01")
            self.assertEqual(clients[0]["lease_remaining"], "02:00:00")
            self.assertEqual(clients[1]["lease_remaining"], "Permanent")

    def test_dhcp_reservations(self):
        mock_list = {
            "0": [
                {"__stack": "1,0,0,0,0,0", "chaddr": "AA:BB:CC:11:22:33", "yiaddr": "192.168.1.50", "enable": "1"}
            ]
        }
        with patch.object(self.client, "req_act", return_value=mock_list) as mock_req:
            reservations = self.client.get_dhcp_reservations()
            self.assertEqual(len(reservations), 1)
            self.assertEqual(reservations[0]["ip"], "192.168.1.50")
            self.assertTrue(reservations[0]["enabled"])

            # Test add reservation
            self.client.add_dhcp_reservation("AA-BB-CC-44-55-66", "192.168.1.60")
            add_call = mock_req.call_args[0][0][0]
            self.assertEqual(add_call.type, ActItem.ADD)
            self.assertEqual(add_call.oid, "LAN_DHCP_STATIC_ADDR")

            # Test delete reservation
            self.client.delete_dhcp_reservation("AA:BB:CC:11:22:33")
            del_call = mock_req.call_args[0][0][0]
            self.assertEqual(del_call.type, ActItem.DEL)
            self.assertEqual(del_call.stack, "1,0,0,0,0,0")

    def test_data_limits(self):
        mock_data = {
            "0": {
                "enableDataLimit": "1",
                "limitation": "50000",
                "warningPercent": "90",
                "enablePaymentDay": "1",
                "paymentDay": "15",
                "curStatistics": "104857600",
                "totalStatistics": "209715200",
                "curRxSpeed": "128000",
                "curTxSpeed": "64000",
            }
        }
        with patch.object(self.client, "req_act", return_value=mock_data) as mock_req:
            d = self.client.get_data_limit()
            self.assertTrue(d["limit_enabled"])
            self.assertEqual(d["limit_mb"], 50000)
            self.assertEqual(d["billing_day"], 15)
            self.assertEqual(d["current_period_bytes"], 104857600)

            # Test set_data_limit
            self.client.set_data_limit(enabled=True, limit_mb=60000, warning_percent=85, payment_day=1)
            set_call = mock_req.call_args[0][0][0]
            self.assertEqual(set_call.type, ActItem.SET)
            self.assertEqual(set_call.oid, "WAN_LTE_INTF_CFG")
            self.assertIn("limitation=60000", set_call.attrs)

    def test_wifi_and_leds(self):
        mock_wifi = {
            "0": [
                {"Name": "wlan0", "X_TP_Band": "2.4GHz", "SSID": "Hutch_4G_WiFi", "Channel": "6", "Enable": "1", "Standard": "11n"},
                {"Name": "wlan1", "X_TP_Band": "5GHz", "SSID": "Hutch_4G_5G", "Channel": "36", "Enable": "1", "Standard": "11ac"}
            ]
        }
        with patch.object(self.client, "req_act", return_value=mock_wifi) as mock_req:
            nets = self.client.get_wifi_status()
            self.assertEqual(len(nets), 2)
            self.assertEqual(nets[0]["ssid"], "Hutch_4G_WiFi")
            self.assertEqual(nets[1]["band"], "5GHz")

            self.client.set_wifi_radio(band="2.4GHz", enabled=False)
            set_call = mock_req.call_args[0][0][0]
            self.assertEqual(set_call.oid, "LAN_WLAN")
            self.assertIn("Enable=0", set_call.attrs)

        mock_led = {
            "0": {"enable": "1"},
            "1": {"enable": "1", "startTime": "1320", "endTime": "420"}
        }
        with patch.object(self.client, "req_act", return_value=mock_led) as mock_req:
            leds = self.client.get_led_status()
            self.assertTrue(leds["leds_on"])
            self.assertTrue(leds["night_mode_enabled"])
            self.assertEqual(leds["night_mode_start"], "22:00")
            self.assertEqual(leds["night_mode_end"], "07:00")

            self.client.set_led_night_mode(enabled=True, start_time="23:30", end_time="06:30")
            led_call = mock_req.call_args[0][0][0]
            self.assertEqual(led_call.oid, "LED_SCHEDULE_CFG")
            self.assertIn("startTime=1410", led_call.attrs)  # 23*60 + 30 = 1410
            self.assertIn("endTime=390", led_call.attrs)    # 6*60 + 30 = 390

    def test_band_lock_and_diag(self):
        with patch.object(self.client, "req_act", return_value={"0": {"LastResult": "1"}}) as mock_req:
            self.client.set_lte_band("3")
            # Collect all ActItems passed across mock_req calls
            all_acts = [act for call in mock_req.call_args_list for act in call[0][0]]
            wan_call = next((a for a in all_acts if a.oid == "LTE_WAN_CFG" and a.type == a.SET), None)
            self.assertIsNotNone(wan_call)
            self.assertIn("bandSelectSwitch=1", wan_call.attrs)
            self.assertIn("bandSelectedMaskL=4", wan_call.attrs)
            self.assertIn("bandSelectedMaskH=0", wan_call.attrs)

            res = self.client.run_wan_diagnostic(max_wait_sec=2)
            self.assertEqual(res["status"], "Passed")

    def test_get_band_config(self):
        sample_wan_cfg = {
            "0": {
                "bandSelectSwitch": "1",
                "bandSelectedMaskL": "128",
                "bandSelectedMaskH": "0",
                "bandSupportMaskL": "524485",
                "bandSupportMaskH": "416",
            }
        }
        with patch.object(self.client, "req_act", return_value=sample_wan_cfg):
            with patch.object(self.client, "get_lte_status") as mock_status:
                from tplink_router.models.device import LTEStatus, RFMetrics
                mock_status.return_value = LTEStatus(
                    connected=True,
                    sim_status="Ready",
                    isp_name="Hutch",
                    band="Band 8 (900 MHz)",
                    earfcn="10638",
                    pci="0",
                    rf=RFMetrics(0, 0, 0, -85, 3),
                    rx_speed_kbps=0.0,
                    tx_speed_kbps=0.0
                )
                b_cfg = self.client.get_band_config()
                self.assertEqual(b_cfg["mode"], "manual")
                self.assertEqual(b_cfg["configured_bands"], [8])
                self.assertIn("Manual (B8)", b_cfg["configured_str"])
                self.assertIn(8, b_cfg["supported_bands"])
                self.assertIn(3, b_cfg["supported_bands"])
                self.assertIn(40, b_cfg["supported_bands"])
                self.assertEqual(b_cfg["connected_band"], "Band 8 (900 MHz)")


if __name__ == "__main__":
    unittest.main()
