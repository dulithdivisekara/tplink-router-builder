"""Comprehensive unit tests for universal TP-Link MCP server tools.

Validates all 21 MCP tool definitions, parameters, safety warnings, and execution paths.
"""

import unittest
from unittest.mock import MagicMock, patch

from tplink_router.models.device import (
    DeviceInfo, RFMetrics, CellLockStatus, LTEStatus, IPv4Config, IPv6Config, RouterTelemetry
)
from tplink_router.models.sms import SMSMessage, USSDResult
from tplink_router.mcp.server import (
    router_profile_check,
    router_get_status,
    router_get_rf_signal,
    router_set_cell_lock,
    router_set_dns,
    router_toggle_ipv6,
    router_run_ussd,
    router_read_sms,
    router_send_sms,
    router_get_connected_clients,
    router_manage_dhcp_reservation,
    router_get_data_limit,
    router_set_data_limit,
    router_get_wifi_networks,
    router_set_wifi_radio,
    router_get_led_status,
    router_set_led_night_mode,
    router_run_diagnostic,
    router_set_lte_band,
    router_calibrate,
    router_reboot,
    router_get_system_logs,
    router_clear_system_logs,
    router_get_guest_wifi,
    router_set_guest_wifi,
    router_get_port_forwarding,
    router_add_port_forwarding,
    router_del_port_forwarding,
    router_get_dmz,
    router_set_dmz,
    router_get_upnp,
    router_set_upnp,
    router_get_reboot_schedule,
    router_set_reboot_schedule,
    router_get_time,
    router_sync_time,
    router_get_operation_mode,
    router_get_ddns,
    router_check_firmware,
)
from tplink_router.models.advanced import (
    SystemLogEntry, GuestWiFiNetwork, GuestWiFiStatus, PortForwardRule,
    DMZConfig, UPnPPortMapping, UPnPStatus, RebootScheduleConfig,
    TimeConfig, OperationMode, DDNSStatus, FirmwareUpdateInfo
)


class TestMCPServerTools(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.patcher_verify = patch("tplink_router.mcp.server._get_client_and_verify", return_value=self.mock_client)
        self.patcher_verify.start()

    def tearDown(self):
        self.patcher_verify.stop()

    def test_router_profile_check(self):
        with patch("tplink_router.core.network_guard.NetworkGuard.get_current_gateway", return_value="192.168.1.1"), \
             patch("tplink_router.core.network_guard.NetworkGuard.get_current_ssid", return_value="dulith.connect"), \
             patch("tplink_router.core.network_guard.NetworkGuard.check_safety", return_value=(True, "Safe")):
            res = router_profile_check()
            self.assertTrue(res["is_safe_to_configure"])
            self.assertEqual(res["default_gateway"], "192.168.1.1")
            self.assertEqual(res["current_ssid"], "dulith.connect")

    def test_router_get_status(self):
        self.mock_client.get_telemetry.return_value = RouterTelemetry(
            device=DeviceInfo(model="Archer MR200", firmware_version="1.4.0"),
            lte=LTEStatus(connected=True, isp_name="Hutch"),
            ipv4=IPv4Config(ip="10.185.240.77", status="Connected"),
            connected_clients_count=2,
        )
        res = router_get_status(force=True)
        self.assertEqual(res["device"]["model"], "Archer MR200")
        self.assertEqual(res["lte"]["isp_name"], "Hutch")
        self.assertEqual(res["ipv4"]["ip"], "10.185.240.77")
        self.assertEqual(res["connected_clients_count"], 2)

    def test_router_get_rf_signal(self):
        self.mock_client.get_lte_status.return_value = LTEStatus(
            isp_name="Hutch Internet",
            band="Band 8 (900 MHz)",
            earfcn="10638",
            pci="58",
            rf=RFMetrics(rsrp_dbm=-85, signal_bars=4),
        )
        res = router_get_rf_signal(force=True)
        self.assertEqual(res["carrier"], "Hutch Internet")
        self.assertEqual(res["band"], "Band 8 (900 MHz)")
        self.assertEqual(res["metrics"]["signal_bars"], 4)

    def test_router_set_cell_lock(self):
        # Unconfirmed safety warning
        warn = router_set_cell_lock(enable=True, earfcn="1550", pci="58", confirm=False)
        self.assertIn("SAFETY WARNING", warn)
        self.mock_client.set_cell_lock.assert_not_called()

        # Confirmed execution
        ok = router_set_cell_lock(enable=True, earfcn="1550", pci="58", confirm=True)
        self.assertIn("Cell Lock successfully applied", ok)
        self.mock_client.set_cell_lock.assert_called_once_with(enable=True, earfcn="1550", pci="58")

    def test_router_set_dns(self):
        res = router_set_dns("1.1.1.1", "1.0.0.1")
        self.mock_client.set_dns.assert_called_once_with("1.1.1.1", "1.0.0.1")
        self.assertIn("updated to 1.1.1.1, 1.0.0.1", res)

    def test_router_toggle_ipv6(self):
        res = router_toggle_ipv6(enable=False)
        self.mock_client.toggle_ipv6.assert_called_once_with(False)
        self.assertIn("disabled", res)

    def test_router_run_ussd(self):
        self.mock_client.send_ussd.return_value = USSDResult(command="*344#", response="Data Balance: 45GB", success=True)
        res = router_run_ussd("*344#")
        self.mock_client.send_ussd.assert_called_once_with("*344#")
        self.assertEqual(res, "Data Balance: 45GB")

    def test_router_read_sms(self):
        self.mock_client.get_sms.return_value = [
            SMSMessage(index=1, sender="+94770000000", content="Welcome to 4G", received_time="2026-10-28 10:00:00")
        ]
        res = router_read_sms(limit=5, folder="inbox")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["sender"], "+94770000000")
        self.assertEqual(res[0]["content"], "Welcome to 4G")

    def test_router_send_sms(self):
        res = router_send_sms("+94701234567", "Antigravity MCP Test")
        self.mock_client.send_sms.assert_called_once_with("+94701234567", "Antigravity MCP Test")
        self.assertIn("successfully sent", res)

    def test_router_get_connected_clients(self):
        self.mock_client.get_connected_clients.return_value = [
            {"hostname": "dulith-pc", "ip": "192.168.1.100", "mac": "28-CD-C4-63-81-39"}
        ]
        res = router_get_connected_clients()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["hostname"], "dulith-pc")

    def test_router_manage_dhcp_reservation(self):
        # List action with 0 / None mac
        self.mock_client.get_dhcp_reservations.return_value = []
        res = router_manage_dhcp_reservation(action="list")
        self.assertEqual(res, "No static DHCP reservations configured.")

        # Missing MAC on add
        err = router_manage_dhcp_reservation(action="add")
        self.assertIn("Error: MAC address is required", err)

        # Unconfirmed add
        warn = router_manage_dhcp_reservation(action="add", mac="AA:BB:CC:DD:EE:FF", ip="192.168.1.150", confirm=False)
        self.assertIn("SAFETY WARNING", warn)

        # Confirmed add
        ok = router_manage_dhcp_reservation(action="add", mac="AA:BB:CC:DD:EE:FF", ip="192.168.1.150", confirm=True)
        self.assertIn("reservation added", ok)
        self.mock_client.add_dhcp_reservation.assert_called_once_with("AA:BB:CC:DD:EE:FF", "192.168.1.150")

        # Confirmed delete
        del_ok = router_manage_dhcp_reservation(action="delete", mac="AA:BB:CC:DD:EE:FF", confirm=True)
        self.assertIn("reservation deleted", del_ok)
        self.mock_client.delete_dhcp_reservation.assert_called_once_with("AA:BB:CC:DD:EE:FF")

    def test_router_get_data_limit(self):
        self.mock_client.get_data_limit.return_value = {"limit_enabled": False, "limit_mb": 0}
        res = router_get_data_limit()
        self.assertFalse(res["limit_enabled"])

    def test_router_set_data_limit(self):
        warn = router_set_data_limit(limit_mb=50000, confirm=False)
        self.assertIn("Confirm setting", warn)

        ok = router_set_data_limit(limit_mb=50000, confirm=True)
        self.assertIn("Monthly data limit updated", ok)
        self.mock_client.set_data_limit.assert_called_once_with(
            enabled=True, limit_mb=50000, warning_percent=90, payment_day=1
        )

    def test_router_get_wifi_networks(self):
        self.mock_client.get_wifi_status.return_value = [
            {"band": "2.4GHz", "ssid": "dulith.connect", "enabled": True}
        ]
        res = router_get_wifi_networks()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["ssid"], "dulith.connect")

    def test_router_set_wifi_radio(self):
        warn = router_set_wifi_radio(band="5GHz", enable=False, confirm=False)
        self.assertIn("SAFETY WARNING", warn)

        ok = router_set_wifi_radio(band="5GHz", enable=True, confirm=True)
        self.assertIn("Wi-Fi 5GHz radio updated", ok)
        self.mock_client.set_wifi_radio.assert_called_once_with(band="5GHz", enabled=True, ssid=None)

    def test_router_get_led_status(self):
        self.mock_client.get_led_status.return_value = {"leds_on": True, "night_mode_enabled": False}
        res = router_get_led_status()
        self.assertTrue(res["leds_on"])

    def test_router_set_led_night_mode(self):
        res = router_set_led_night_mode(enable=True, start_time="22:30", end_time="06:30")
        self.mock_client.set_led_night_mode.assert_called_once_with(enabled=True, start_time="22:30", end_time="06:30")
        self.assertIn("Night mode enabled", res)

    def test_router_run_diagnostic(self):
        self.mock_client.run_wan_diagnostic.return_value = {"status": "Passed", "result_code": 1}
        res = router_run_diagnostic()
        self.assertEqual(res["status"], "Passed")

    def test_router_set_lte_band(self):
        warn = router_set_lte_band(band="3", confirm=False)
        self.assertIn("SAFETY WARNING", warn)

        ok = router_set_lte_band(band="3", confirm=True)
        self.assertIn("LTE band lock set to 3", ok)
        self.mock_client.set_lte_band.assert_called_once_with(band="3")

    def test_router_calibrate_unconfirmed(self):
        notice = router_calibrate(confirm=False, dry_run=False)
        self.assertIn("NOTICE: Cellular calibration", notice)

    def test_router_reboot(self):
        warn = router_reboot(confirm=False)
        self.assertIn("SAFETY WARNING", warn)

        ok = router_reboot(confirm=True)
        self.assertIn("Reboot command sent", ok)
        self.mock_client.reboot.assert_called_once()

    def test_router_system_logs(self):
        self.mock_client.get_system_logs.return_value = [
            SystemLogEntry(timestamp="2026-10-29 10:00:00", level_num=6, level_name="INFO", module="4G", message="Connected")
        ]
        logs = router_get_system_logs(lines=10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["module"], "4G")

        warn = router_clear_system_logs(confirm=False)
        self.assertIn("SAFETY NOTICE", warn)

        ok = router_clear_system_logs(confirm=True)
        self.assertIn("cleared", ok)
        self.mock_client.clear_system_logs.assert_called_once()

    def test_router_guest_wifi(self):
        self.mock_client.get_guest_wifi.return_value = GuestWiFiStatus(
            allow_lan_access=False,
            networks=[
                GuestWiFiNetwork("2.4GHz", True, "GuestNet", "WPA2-PSK", True),
                GuestWiFiNetwork("5GHz", False, "GuestNet_5G", "Open", True),
            ]
        )
        gw = router_get_guest_wifi()
        self.assertFalse(gw["allow_lan_access"])
        self.assertEqual(len(gw["networks"]), 2)

        warn = router_set_guest_wifi(band="2.4GHz", enabled=True, confirm=False)
        self.assertIn("SAFETY NOTICE", warn)

        ok = router_set_guest_wifi(band="2.4GHz", enabled=True, confirm=True)
        self.assertIn("enabled", ok)
        self.mock_client.set_guest_wifi.assert_called_once()

    def test_router_port_forwarding(self):
        self.mock_client.get_port_forwarding.return_value = [
            PortForwardRule("2,1,1,1,0,0", "web", "8080", "80", "192.168.1.150", "TCP", True)
        ]
        pf = router_get_port_forwarding()
        self.assertEqual(len(pf), 1)
        self.assertEqual(pf[0]["name"], "web")

        warn = router_add_port_forwarding("ssh", "22", "192.168.1.100", confirm=False)
        self.assertIn("SAFETY NOTICE", warn)

        ok = router_add_port_forwarding("ssh", "22", "192.168.1.100", confirm=True)
        self.assertIn("successfully created", ok)
        self.mock_client.add_port_forwarding.assert_called_once()

        del_warn = router_del_port_forwarding("2,1,1,1,0,0", confirm=False)
        self.assertIn("SAFETY NOTICE", del_warn)

        del_ok = router_del_port_forwarding("2,1,1,1,0,0", confirm=True)
        self.assertIn("successfully deleted", del_ok)
        self.mock_client.del_port_forwarding.assert_called_once()

    def test_router_dmz(self):
        self.mock_client.get_dmz.return_value = DMZConfig(enabled=False, ip_address="")
        dmz = router_get_dmz()
        self.assertFalse(dmz["enabled"])

        warn = router_set_dmz(enabled=True, ip_address="192.168.1.200", confirm=False)
        self.assertIn("SAFETY WARNING", warn)

        ok = router_set_dmz(enabled=True, ip_address="192.168.1.200", confirm=True)
        self.assertIn("enabled for 192.168.1.200", ok)
        self.mock_client.set_dmz.assert_called_once_with(enabled=True, ip_address="192.168.1.200")

    def test_router_upnp(self):
        self.mock_client.get_upnp.return_value = UPnPStatus(enabled=True, mappings=[])
        upnp = router_get_upnp()
        self.assertTrue(upnp["enabled"])

        warn = router_set_upnp(enabled=False, confirm=False)
        self.assertIn("SAFETY NOTICE", warn)

        ok = router_set_upnp(enabled=False, confirm=True)
        self.assertIn("disabled", ok)
        self.mock_client.set_upnp.assert_called_once_with(enabled=False)

    def test_router_reboot_schedule(self):
        self.mock_client.get_reboot_schedule.return_value = RebootScheduleConfig(
            enabled=True, hours=3, minutes=0, mode="daily", day_of_week=1
        )
        rs = router_get_reboot_schedule()
        self.assertTrue(rs["enabled"])
        self.assertEqual(rs["hours"], 3)

        warn = router_set_reboot_schedule(enabled=True, hours=4, minutes=0, confirm=False)
        self.assertIn("SAFETY NOTICE", warn)

        ok = router_set_reboot_schedule(enabled=True, hours=4, minutes=0, confirm=True)
        self.assertIn("enabled", ok)
        self.mock_client.set_reboot_schedule.assert_called_once()

    def test_router_time_and_op_and_ddns_and_fw(self):
        self.mock_client.get_time_config.return_value = TimeConfig(
            current_time="2026-10-29 10:00:00", timezone="+05:30", daylight_savings=False,
            ntp_server1="time.nist.gov", ntp_server2="pool.ntp.org"
        )
        t = router_get_time()
        self.assertEqual(t["current_time"], "2026-10-29 10:00:00")

        sync_res = router_sync_time()
        self.assertIn("dispatched successfully", sync_res)
        self.mock_client.sync_time.assert_called_once()

        self.mock_client.get_operation_mode.return_value = OperationMode(
            mode="3G/4G Router Mode", raw_mode="LTE", lte_backup_enabled=False, cellular_data_switch=True
        )
        om = router_get_operation_mode()
        self.assertEqual(om["mode"], "3G/4G Router Mode")

        self.mock_client.get_ddns_status.return_value = [
            DDNSStatus(provider="TP-Link Cloud", enabled=True, domain="test.tplinkdns.com", username="user", status="Bound"),
            DDNSStatus(provider="No-IP", enabled=False, domain="", username="", status="Disabled"),
        ]
        ddns = router_get_ddns()
        self.assertEqual(len(ddns), 2)
        self.assertEqual(ddns[0]["provider"], "TP-Link Cloud")

        self.mock_client.check_firmware_update.return_value = FirmwareUpdateInfo(
            current_version="1.4.0", latest_version="1.4.0", release_date="2026-10-29",
            release_log="", has_update=False
        )
        fw = router_check_firmware()
        self.assertFalse(fw["has_update"])


if __name__ == "__main__":
    unittest.main()
