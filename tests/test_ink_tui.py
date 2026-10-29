"""
Integration & Headless Render Tests for the Bundled vadimdemedes/ink React TUI.

Verifies that `tui.mjs` mounts React 19 + Ink 6.8 + Yoga 3.2 cleanly in Node.js
and renders:
  1. Shimmering Half-Block TP-Link P+T Emblem & Split-Pane Workspace
  2. Claude-Code-Style Thinking / RSA-1024 Activity Spinner
  3. Live RF & Throughput Sparkline Stream Dashboard
  4. Spacebar Feature Switchboard & Monochrome B&W Mode (--mono)
  5. Pure-Python fallback delegation (--python-tui)
"""

import os
import shutil
import subprocess
import unittest
from unittest.mock import patch

from tplink_router.cli.ink_ui import get_ink_bundle_path, is_ink_available
from tplink_router.cli.main import launch_best_tui
from tplink_router.cli.theme import strip_ansi


@unittest.skipUnless(shutil.which("node"), "Node.js is required for Ink headless render tests")
class TestInkAnimatedTUI(unittest.TestCase):
    def _render_scene(self, *extra_args: str, force_color: str = "3") -> str:
        bundle = get_ink_bundle_path()
        self.assertTrue(bundle.is_file(), f"Missing Ink bundle at {bundle}")
        env = dict(os.environ)
        env.pop("NO_COLOR", None)
        env["FORCE_COLOR"] = force_color
        res = subprocess.run(
            ["node", str(bundle), "--test-render", *extra_args],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        self.assertEqual(res.returncode, 0, f"Ink render failed:\n{res.stderr}")
        return res.stdout

    def test_ink_bundle_availability(self):
        self.assertTrue(is_ink_available())
        self.assertGreater(get_ink_bundle_path().stat().st_size, 100_000)

    def test_workspace_scene_logo_shimmer_and_batch_queue(self):
        raw_t0 = self._render_scene("--test-scene=workspace", "--tick=0")
        raw_t4 = self._render_scene("--test-scene=workspace", "--tick=4")
        plain = strip_ansi(raw_t0)

        # Verify Half-Block TP-Link emblem silhouette & workspace structure
        self.assertIn("▄▄██████▄▄", plain)
        self.assertIn("Router & LTE RF Control", plain)
        self.assertIn("Ink React UI", plain)
        self.assertIn("7 Admin", plain)
        self.assertIn("q Quit", plain)
        self.assertIn("QUICK ACTIONS", plain)
        self.assertIn("Spacebar Batch Queue (2)", plain)
        self.assertIn("status → signal", plain)

        # Verify diagonal logo shimmer changes ANSI color stops across ticks while keeping geometry identical
        self.assertEqual(plain, strip_ansi(raw_t4))
        self.assertNotEqual(raw_t0, raw_t4)

    def test_claude_code_busy_activity_bar_scene(self):
        raw = self._render_scene("--test-scene=busy", "--tick=3")
        plain = strip_ansi(raw)
        self.assertIn("Negotiating RSA-1024 session lease", plain)
        self.assertIn("[RSA-1024 Session]", plain)
        self.assertIn("✻", plain)

    def test_live_rf_sparkline_monitor_scene(self):
        raw = self._render_scene("--test-scene=live", "--tick=4")
        plain = strip_ansi(raw)
        self.assertIn("LIVE RF STREAM", plain)
        self.assertIn("CELLULAR BASEBAND", plain)
        self.assertIn("RF SIGNAL QUALITY", plain)
        self.assertIn("REAL-TIME THROUGHPUT & RF STABILITY WAVEFORMS", plain)
        self.assertIn("↓ Downlink", plain)
        self.assertIn("↑ Uplink", plain)
        self.assertIn("▲ RF Bars", plain)

    def test_switchboard_modal_and_monochrome_mode(self):
        raw_mono = self._render_scene("--test-scene=switchboard", "--mono", "--tick=2")
        plain_mono = strip_ansi(raw_mono)
        self.assertIn("QUICK FEATURE SWITCHBOARD", plain_mono)
        self.assertIn("[● ON ] IPv6 WAN Stack", plain_mono)
        self.assertIn("[MONO B&W:m]", plain_mono)
        # Ensure TP-Link Brand Cyan RGB (77;204;213) is completely absent in Monochrome mode
        self.assertNotIn("77;204;213", raw_mono)

    def test_python_tui_fallback_flag(self):
        with patch("tplink_router.cli.interactive_tui.launch_tui", return_value=None) as mock_py:
            res = launch_best_tui(target_host="http://192.168.1.1", mono=True, prefer_python=True)
            self.assertIsNone(res)
            mock_py.assert_called_once_with(target_host="http://192.168.1.1", mono=True)


if __name__ == "__main__":
    unittest.main()
