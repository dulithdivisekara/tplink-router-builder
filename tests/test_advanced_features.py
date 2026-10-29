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

    def test_system_logs(self):
        sample_log_raw = (
            "2026-10-29 10:48:54 [6] 4G: LTE connected\n"
            "2026-10-29 10:49:41 [6] System: User logged in\n"
        )
        self.client.auth.aes_key = b"0123456789abcdef"
        mock_resp = MagicMock(status_code=200, text="raw_aes")
        with patch.object(self.client.session, "get", return_value=mock_resp) as mock_get, \
             patch.object(self.client.auth, "decrypt_gdpr_data", return_value=sample_log_raw):
            logs = self.client.get_system_logs()
            self.assertEqual(len(logs), 2)
            self.assertEqual(logs[0].module, "4G")
            self.assertEqual(logs[0].level_name, "INFO")
            self.assertEqual(logs[0].message, "LTE connected")

        with patch.object(self.client.session, "get", return_value=MagicMock(status_code=200)) as mock_get:
            self.client.clear_system_logs()
            mock_get.assert_called_once()
            self.assertIn("/cgi/log?clr", mock_get.call_args[0][0])

    def test_guest_wifi(self):
        mock_mssid = {
            "0": [
                {"__stack": "1,1,1,0,0,0", "enable": "1", "SSID": "Guest_2.4G", "beaconType": "11i", "isolateClients": "0"},
                {"__stack": "1,2,1,0,0,0", "enable": "0", "SSID": "Guest_5G", "beaconType": "Basic", "isolateClients": "0"}
            ]
        }
        mock_guest = {"0": [{"LANAccessEnable": "0"}]}
        with patch.object(self.client, "req_act", side_effect=[mock_mssid, mock_guest, {}]) as mock_req:
            gw = self.client.get_guest_wifi()
            self.assertFalse(gw.allow_lan_access)
            self.assertEqual(len(gw.networks), 2)
            self.assertTrue(gw.networks[0].enabled)
            self.assertEqual(gw.networks[0].ssid, "Guest_2.4G")
            self.assertEqual(gw.networks[0].security, "WPA/WPA2-PSK")
            self.assertFalse(gw.networks[1].enabled)

            self.client.set_guest_wifi(band="2.4GHz", enabled=True, ssid="NewGuest", password="Password123")
            all_acts = [act for call in mock_req.call_args_list for act in call[0][0]]
            mssid_call = next((a for a in all_acts if a.oid == "LAN_WLAN_MSSIDENTRY" and a.type == a.SET), None)
            self.assertIsNotNone(mssid_call)
            self.assertIn("SSID=NewGuest", mssid_call.attrs)

    def test_port_forwarding(self):
        mock_wan = {"0": [{"__stack": "2,1,1,0,0,0", "enable": "1"}]}
        mock_pm = {
            "0": [
                {
                    "__stack": "2,1,1,1,0,0",
                    "PortMappingDescription": "web",
                    "externalPort": "8080",
                    "internalPort": "80",
                    "internalClient": "192.168.1.150",
                    "portMappingProtocol": "TCP",
                    "portMappingEnabled": "1",
                }
            ]
        }
        with patch.object(self.client, "req_act", side_effect=[mock_wan, mock_pm, {}, {}]) as mock_req:
            rules = self.client.get_port_forwarding()
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].name, "web")
            self.assertEqual(rules[0].external_port, "8080")
            self.assertEqual(rules[0].internal_port, "80")
            self.assertEqual(rules[0].internal_ip, "192.168.1.150")
            self.assertEqual(rules[0].protocol, "TCP")

            # Add port forwarding
            self.client.add_port_forwarding("ssh", "2222", "192.168.1.100", "22", "TCP")
            add_call = mock_req.call_args_list[2][0][0][0]
            self.assertEqual(add_call.type, ActItem.ADD)
            self.assertEqual(add_call.oid, "WAN_IP_CONN_PORTMAPPING")
            self.assertIn("externalPort=2222", add_call.attrs)

            # Delete port forwarding
            self.client.del_port_forwarding("2,1,1,1,0,0")
            del_call = mock_req.call_args_list[3][0][0][0]
            self.assertEqual(del_call.type, ActItem.DEL)
            self.assertEqual(del_call.stack, "2,1,1,1,0,0")

    def test_dmz(self):
        mock_data = {"0": {"enable": "1", "IPAddress": "192.168.1.120"}}
        with patch.object(self.client, "req_act", return_value=mock_data) as mock_req:
            dmz = self.client.get_dmz()
            self.assertTrue(dmz.enabled)
            self.assertEqual(dmz.ip_address, "192.168.1.120")

            self.client.set_dmz(enabled=False)
            set_call = mock_req.call_args[0][0][0]
            self.assertEqual(set_call.oid, "DMZ_HOST_CFG")
            self.assertIn("enable=0", set_call.attrs)

    def test_upnp(self):
        mock_cfg = {"0": {"enable": "1"}}
        mock_maps = {
            "0": [
                {
                    "__stack": "1,0,0,0,0,0",
                    "PortMappingDescription": "Skype",
                    "externalPort": "45678",
                    "internalPort": "45678",
                    "internalClient": "192.168.1.50",
                    "portMappingProtocol": "UDP",
                    "portMappingEnabled": "1",
                }
            ]
        }
        with patch.object(self.client, "req_act", side_effect=[mock_cfg, mock_maps, {}]) as mock_req:
            upnp = self.client.get_upnp()
            self.assertTrue(upnp.enabled)
            self.assertEqual(len(upnp.mappings), 1)
            self.assertEqual(upnp.mappings[0].description, "Skype")

            self.client.set_upnp(enabled=False)
            set_call = mock_req.call_args[0][0][0]
            self.assertEqual(set_call.oid, "UPNP_CFG")
            self.assertIn("enable=0", set_call.attrs)

    def test_reboot_schedule(self):
        mock_data = {
            "0": {
                "enable": "1",
                "mode": "1",
                "hours": "3",
                "minutes": "30",
                "day": "1",
                "week": "1",
            }
        }
        with patch.object(self.client, "req_act", return_value=mock_data) as mock_req:
            rs = self.client.get_reboot_schedule()
            self.assertTrue(rs.enabled)
            self.assertEqual(rs.hours, 3)
            self.assertEqual(rs.minutes, 30)
            self.assertEqual(rs.mode, "daily")

            self.client.set_reboot_schedule(enabled=True, hours=4, minutes=15, mode="weekly", day_of_week=5)
            set_call = mock_req.call_args[0][0][0]
            self.assertEqual(set_call.oid, "REBOOT_SCHEDULE_CFG")
            self.assertIn("hours=4", set_call.attrs)
            self.assertIn("minutes=15", set_call.attrs)
            self.assertIn("mode=2", set_call.attrs)
            self.assertIn("day=5", set_call.attrs)

    def test_time_and_ddns_and_fw(self):
        mock_time = {
            "0": {
                "currentLocalTime": "2026-10-29 10:00:00",
                "localTimeZone": "+05:30",
                "daylightSavingsUsed": "0",
                "NTPServer1": "time.nist.gov",
                "NTPServer2": "pool.ntp.org",
            }
        }
        with patch.object(self.client, "req_act", return_value=mock_time) as mock_req:
            t = self.client.get_time_config()
            self.assertEqual(t.current_time, "2026-10-29 10:00:00")
            self.assertEqual(t.timezone, "+05:30")
            self.assertEqual(t.ntp_server1, "time.nist.gov")

            self.client.sync_time()
            sync_call = mock_req.call_args[0][0][0]
            self.assertEqual(sync_call.type, ActItem.OP)
            self.assertEqual(sync_call.oid, "ACT_OP_NTP_REQUEST")

        mock_op = {
            "0": {"mode": "LTE", "lteBackupEnable": "0", "LTEDataSwitch": "1"}
        }
        with patch.object(self.client, "req_act", return_value=mock_op):
            op = self.client.get_operation_mode()
            self.assertEqual(op.mode, "3G/4G Router Mode")
            self.assertFalse(op.lte_backup_enabled)
            self.assertTrue(op.cellular_data_switch)

        mock_ddns = {
            "0": {"enable": "1", "state": "0", "userDomain": "test.no-ip.org", "userName": "testuser"},
        }
        with patch.object(self.client, "req_act", return_value=mock_ddns):
            ddns_list = self.client.get_ddns_status()
            self.assertTrue(len(ddns_list) >= 1)
            self.assertEqual(ddns_list[0].provider, "No-IP")
            self.assertTrue(ddns_list[0].enabled)
            self.assertEqual(ddns_list[0].domain, "test.no-ip.org")

        mock_fw = {
            "0": {
                "version": "1.4.0 0.9.1 v0001.0 Build 250916 Rel.67755n",
                "status": "0",
            }
        }
        with patch.object(self.client, "get_device_info") as mock_info, \
             patch.object(self.client, "req_act", return_value=mock_fw):
            from tplink_router.models.device import DeviceInfo
            mock_info.return_value = DeviceInfo(model="Archer MR200", firmware_version="1.4.0 0.9.1 v0001.0 Build 250916 Rel.67755n")
            fw = self.client.check_firmware_update()
            self.assertFalse(fw.has_update)
            self.assertEqual(fw.current_version, "1.4.0 0.9.1 v0001.0 Build 250916 Rel.67755n")


if __name__ == "__main__":
    unittest.main()
