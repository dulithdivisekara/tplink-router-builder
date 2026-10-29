"""
Unit tests for Claude-Code-style CLI Animator (animator.py) and
Serialized NDJSON Ink Router Bridge (bridge.py).
"""

import argparse
import io
import os
import time
import unittest
from unittest.mock import MagicMock, patch

from tplink_router.cli.animator import (
    AnimatedSpinner,
    STARBURST_FRAMES,
    clear_active_spinner,
    format_spinner_frame,
    router_spinner,
    shimmer_text,
    should_animate,
)
from tplink_router.cli.bridge import RouterBridgeWorker
from tplink_router.cli.theme import strip_ansi


class FakeTTYBuffer(io.StringIO):
    def isatty(self) -> bool:
        return True


class TestCLIAnimatorAndBridge(unittest.TestCase):
    def test_shimmer_text_cyan_mono_and_nocolor(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NO_COLOR", None)
            cyan_out = shimmer_text("Polling Archer MR200 telemetry…", tick=3, mono=False)
            mono_out = shimmer_text("Polling Archer MR200 telemetry…", tick=3, mono=True)
            self.assertEqual(strip_ansi(cyan_out), "Polling Archer MR200 telemetry…")
            self.assertEqual(strip_ansi(mono_out), "Polling Archer MR200 telemetry…")
            self.assertIn("38;2;", cyan_out)
            self.assertNotIn("77;204;213", mono_out)

        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            plain = shimmer_text("Polling…", tick=2, mono=False)
            self.assertEqual(plain, "Polling…")

    def test_format_spinner_frame_rotates_starburst(self):
        f0 = strip_ansi(format_spinner_frame("Negotiating RSA-1024…", tick=0, elapsed_s=0.4))
        f2 = strip_ansi(format_spinner_frame("Negotiating RSA-1024…", tick=2, elapsed_s=1.2))
        self.assertIn(STARBURST_FRAMES[0], f0)
        self.assertIn("0.4s", f0)
        self.assertIn(STARBURST_FRAMES[2], f2)
        self.assertIn("1.2s", f2)

    def test_should_animate_suppression_rules(self):
        tty_buf = FakeTTYBuffer()
        non_tty_buf = io.StringIO()

        with patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("CI", None)
            os.environ.pop("TPLINK_NO_ANIM", None)

            self.assertTrue(should_animate(argparse.Namespace(json=False, legacy=False, no_anim=False), stream=tty_buf))
            self.assertFalse(should_animate(argparse.Namespace(json=True, legacy=False, no_anim=False), stream=tty_buf))
            self.assertFalse(should_animate(argparse.Namespace(json=False, legacy=True, no_anim=False), stream=tty_buf))
            self.assertFalse(should_animate(argparse.Namespace(json=False, legacy=False, no_anim=True), stream=tty_buf))
            self.assertFalse(should_animate(argparse.Namespace(json=False, legacy=False, no_anim=False), stream=non_tty_buf))

        with patch.dict(os.environ, {"TERM": "dumb"}):
            self.assertFalse(should_animate(None, stream=tty_buf))

        with patch.dict(os.environ, {"CI": "true"}):
            self.assertFalse(should_animate(None, stream=tty_buf))

    def test_animated_spinner_lifecycle_and_clean_erasure(self):
        tty_buf = FakeTTYBuffer()
        sp = AnimatedSpinner("Testing router handshake…", mono=False, enabled=True, stream=tty_buf, interval=0.02)
        with sp:
            time.sleep(0.06)
            sp.update("Retuning LTE band…")
            time.sleep(0.05)

        raw = tty_buf.getvalue()
        self.assertIn("\033[?25l", raw)
        self.assertIn("\r\033[2K", raw)
        self.assertTrue(raw.endswith("\033[?25h"))
        clear_active_spinner()

    def test_router_spinner_noop_when_non_tty(self):
        non_tty = io.StringIO()
        with router_spinner("Should not print", stream=non_tty):
            pass
        self.assertEqual(non_tty.getvalue(), "")

    def test_bridge_worker_ndjson_dispatch(self):
        worker = RouterBridgeWorker(target_host="http://192.168.1.1")

        ping_resp = worker.dispatch({"id": 1, "method": "ping"})
        self.assertTrue(ping_resp["ok"])
        self.assertEqual(ping_resp["result"]["host"], "http://192.168.1.1")

        unknown_resp = worker.dispatch({"id": 2, "method": "nonexistent"})
        self.assertFalse(unknown_resp["ok"])

        mock_client = MagicMock()
        mock_client.get_wan_config.return_value = (
            MagicMock(ip="100.80.1.5", gateway="100.80.1.1", dns=["1.1.1.1"]),
            MagicMock(enabled=True, ip="", dns=[], gateway="", status="Enabled"),
        )
        mock_client.get_wifi_status.return_value = [
            {"band": "2.4GHz", "enabled": True},
            {"band": "5GHz", "enabled": True},
        ]
        mock_client.get_guest_wifi.return_value = MagicMock(networks=[MagicMock(enabled=False)])
        mock_client.get_upnp.return_value = MagicMock(enabled=True)
        mock_client.get_led_status.return_value = {"night_mode_enabled": False}

        with patch("tplink_router.cli.bridge.get_client", return_value=mock_client), patch(
            "tplink_router.cli.bridge.SafeSession"
        ), patch("tplink_router.cli.main.get_client", return_value=mock_client), patch(
            "tplink_router.cli.main.SafeSession"
        ):
            toggles_resp = worker.dispatch({"id": 3, "method": "get_toggles"})
            self.assertTrue(toggles_resp["ok"])
            self.assertTrue(toggles_resp["result"]["states"]["ipv6"])
            self.assertTrue(toggles_resp["result"]["states"]["upnp"])

            cmd_resp = worker.dispatch({
                "id": 4,
                "method": "run_command",
                "params": {"argv": ["ipv6"], "mono": False},
            })
            self.assertTrue(cmd_resp["ok"])
            self.assertIn("ROUTER IPv6 STACK STATUS", strip_ansi(cmd_resp["result"]["output"]))


if __name__ == "__main__":
    unittest.main()
