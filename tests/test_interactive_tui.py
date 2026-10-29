"""
Comprehensive unit tests for Flagship TP-Link Interactive TUI (interactive_tui.py):
  - Catalog completeness & fuzzy search filtering
  - Arrow key scrolling (UP/DOWN/LEFT/RIGHT/TAB/1-6)
  - Spacebar multi-select [✔] checkboxes & Enter batch execution
  - Interactive modals (Feature Switchboard toggles, Band Picker, Multi-Band Calibration, USSD input)
  - Monochrome B&W live theme toggle [m] & frame column-width alignment
"""

import unittest
from tplink_router.cli.interactive_tui import (
    COMMAND_CATALOG,
    LiveTelemetrySummary,
    TUIState,
    TUI_TABS,
    filter_commands,
)
from tplink_router.cli.theme import strip_ansi, visible_len


class TestInteractiveTUI(unittest.TestCase):
    def test_catalog_completeness(self):
        self.assertGreaterEqual(len(COMMAND_CATALOG), 31)
        names = [c[0] for c in COMMAND_CATALOG]
        for expected in (
            "status", "signal", "band", "cell-lock", "ipv6", "dns",
            "clients", "wifi", "leds", "sms", "ussd", "reboot", "calibrate",
        ):
            self.assertIn(expected, names)

    def test_empty_query_returns_all(self):
        self.assertEqual(len(filter_commands("")), len(COMMAND_CATALOG))
        self.assertEqual(len(filter_commands("   ")), len(COMMAND_CATALOG))

    def test_prefix_and_fuzzy_filtering(self):
        self.assertEqual(filter_commands("sig")[0][0], "signal")
        self.assertEqual(filter_commands("band")[0][0], "band")
        self.assertIn("status", [c[0] for c in filter_commands("telemetry")])

    def test_arrows_tabs_spacebar_multiselect_and_batch_enter(self):
        executed = []

        def fake_runner(argv, mono):
            executed.append((list(argv), mono))
            return f"╭─ OUTPUT {argv[0]} ─╮\n│ OK │\n╰──────────────────╯"

        st = TUIState(target_host="http://192.168.1.1", runner=fake_runner)

        # Switch tabs using RIGHT and LEFT and number keys
        self.assertEqual(st.tab_idx, 0)
        st.handle_key("RIGHT")
        self.assertEqual(st.tab_idx, 1)
        st.handle_key("LEFT")
        self.assertEqual(st.tab_idx, 0)
        st.handle_key("3")  # Tab 3: WAN & LAN (status, dns, ipv6, clients...)
        self.assertEqual(st.tab_idx, 2)

        # Scroll with DOWN and select 'status' and 'ipv6' with SPACE
        self.assertEqual(st.current_items()[st.cursor].name, "status")
        st.handle_key("SPACE")
        st.handle_key("DOWN")  # dns
        st.handle_key("DOWN")  # ipv6
        self.assertEqual(st.current_items()[st.cursor].name, "ipv6")
        st.handle_key("SPACE")
        self.assertEqual(st.checked, ["status", "ipv6"])

        # Press ENTER to execute checked batch
        st.handle_key("ENTER")
        self.assertEqual(st.view_mode, "output")
        self.assertEqual(executed, [(["status"], False), (["ipv6"], False)])

        # Return to workspace with ESC and clear selections with 'c'
        st.handle_key("ESC")
        self.assertEqual(st.view_mode, "workspace")
        st.handle_key("c")
        self.assertEqual(st.checked, [])

    def test_interactive_modals_band_calibrate_and_toggles(self):
        executed = []
        applied_switches = []

        def fake_runner(argv, mono):
            executed.append(list(argv))
            return "OK"

        def fake_toggle_fetcher():
            return {"ipv6": False, "wifi_2g": True, "wifi_5g": True, "guest_wifi": False, "upnp": True, "led_night": False}

        def fake_toggle_applier(initial, updated, mono):
            applied_switches.append((initial, updated, mono))
            return "Applied switches!"

        st = TUIState(
            runner=fake_runner,
            toggle_fetcher=fake_toggle_fetcher,
            toggle_applier=fake_toggle_applier,
        )

        # 1. Open Quick Feature Switchboard (cursor=0 on Tab 1), flip IPv6 ON with SPACE, apply with ENTER
        self.assertEqual(st.current_items()[st.cursor].name, "wizard:toggles")
        st.handle_key("ENTER")
        self.assertIsNotNone(st.modal)
        self.assertEqual(st.modal.kind, "toggles")
        self.assertFalse(st.modal.options[0].checked)
        st.handle_key("SPACE")  # Flip IPv6 to True
        self.assertTrue(st.modal.options[0].checked)
        st.handle_key("ENTER")
        self.assertEqual(len(applied_switches), 1)
        self.assertTrue(applied_switches[0][1]["ipv6"])
        st.handle_key("ESC")  # Exit output view

        # 2. Open Multi-Band Calibration Wizard, toggle Band 1 ON with SPACE, run with ENTER
        st.handle_key("DOWN")  # wizard:band
        st.handle_key("DOWN")  # wizard:calibrate
        st.handle_key("ENTER")
        self.assertIsNotNone(st.modal)
        self.assertEqual(st.modal.kind, "multi")
        st.handle_key("DOWN")
        st.handle_key("DOWN")  # Band 1
        st.handle_key("SPACE")
        st.handle_key("ENTER")
        self.assertIn(["calibrate", "--no-web", "--bands", "8,3,1,auto", "--dry-run"], executed)

    def test_monochrome_toggle_and_frame_geometry(self):
        st = TUIState()
        st.telemetry = LiveTelemetrySummary(
            polled=True, online=True, model="Archer MR200",
            carrier="Hutch", band="Band 8", bars=4, wan_ip="100.80.1.5",
        )
        for cols, rows in [(100, 30), (88, 26), (72, 24)]:
            frame = st.render_frame(cols=cols, rows=rows)
            widths = {visible_len(line) for line in frame}
            self.assertEqual(len(widths), 1, f"Inconsistent widths {widths} at {cols}x{rows}")

        # Toggle Monochrome B&W mode with 'm'
        self.assertFalse(st.mono)
        st.handle_key("m")
        self.assertTrue(st.mono)
        mono_frame = "\n".join(st.render_frame(cols=96, rows=28))
        self.assertIn("[MONO B&W]", strip_ansi(mono_frame))
        self.assertNotIn("77;204;213", mono_frame)


if __name__ == "__main__":
    unittest.main()
