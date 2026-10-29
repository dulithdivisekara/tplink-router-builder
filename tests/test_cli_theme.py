"""
Unit tests for TP-Link Half-Block Pixel Logo (logo.py), Theme Engine (theme.py),
and Modern / Monochrome / Legacy / JSON CLI command formatting.
"""

import argparse
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from tplink_router.cli.logo import get_logo_width, render_logo_lines
from tplink_router.cli.main import cmd_band, cmd_clients, cmd_ipv6, cmd_signal, cmd_status
from tplink_router.cli.modern_ui import print_modern_ui
from tplink_router.cli.theme import (
    progress_meter,
    rating_badge,
    render_kv_rows,
    render_panel,
    render_table_lines,
    signal_bars,
    status_badge,
    strip_ansi,
    visible_len,
)


class TestTPLinkLogoAndTheme(unittest.TestCase):
    def test_logo_variants_exact_width_and_modes(self):
        for variant, expected_lines in [("full", 10), ("compact", 8), ("mini", 6)]:
            w = get_logo_width(variant)
            for mono, plain in [(False, False), (True, False), (False, True)]:
                lines = render_logo_lines(variant=variant, mono=mono, plain=plain)
                self.assertEqual(len(lines), expected_lines)
                for line in lines:
                    self.assertEqual(visible_len(line), w)
                    if plain:
                        self.assertNotIn("\x1b[", line)

        # Verify TP-Link Brand Cyan RGB escape is present in color mode and absent in mono mode
        color_full = "\n".join(render_logo_lines("full", mono=False))
        mono_full = "\n".join(render_logo_lines("full", mono=True))
        self.assertIn("77;204;213", color_full)
        self.assertNotIn("77;204;213", mono_full)
        self.assertIn("█", color_full)

    def test_panel_and_table_exact_border_alignment(self):
        kv = render_kv_rows([
            ("Gateway", "http://192.168.1.1"),
            ("RF Signal", signal_bars(4)),
            ("Quota", progress_meter(65, 100)),
            ("State", status_badge(True, "CONNECTED", "OFFLINE")),
            ("Quality", rating_badge("Excellent")),
        ])
        tbl = render_table_lines(
            ["HOSTNAME", "IP ADDRESS", "MAC ADDRESS", "STATE"],
            [
                ["dulith-pc", "192.168.1.100", "AA:BB:CC:DD:EE:FF", status_badge(True)],
                ["iphone-15-pro-max-long-name", "192.168.1.101", "11:22:33:44:55:66", status_badge(False)],
            ],
            max_width=68,
        )
        panel = render_panel(
            title="ALIGNMENT TEST PANEL",
            sections=[kv, tbl],
            subtitle="Archer MR200",
            footer="tplink-cli status",
            width=76,
        )
        lines = panel.splitlines()
        self.assertTrue(lines[0].startswith("╭") or strip_ansi(lines[0]).startswith("╭"))
        self.assertTrue(strip_ansi(lines[-1]).endswith("╯"))
        for line in lines:
            self.assertEqual(visible_len(line), 76, f"Misaligned line: {strip_ansi(line)!r}")

    def test_modern_ui_catalog_renders_cleanly(self):
        for mono in (False, True):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                print_modern_ui("http://192.168.1.1", mono=mono)
            out = strip_ansi(buf.getvalue())
            self.assertIn("TP-LINK CLI OVERVIEW", out)
            self.assertIn("COMMAND CATALOG", out)
            self.assertIn("--mono", out)
            self.assertIn("--legacy", out)

    def test_command_outputs_modern_mono_legacy_and_json(self):
        mock_client = MagicMock()
        mock_client.get_wan_config.return_value = (
            MagicMock(ip="100.80.1.5", gateway="100.80.1.1", dns=["1.1.1.1", "8.8.8.8"]),
            MagicMock(enabled=True, ip="", dns=[], gateway="", status="Enabled"),
        )
        mock_client.get_connected_clients.return_value = [
            {"hostname": "dulith-pc", "ip": "192.168.1.100", "mac": "AA:BB:CC:11:22:33", "lease_remaining": "23:59:10"}
        ]
        mock_client.get_band_config.return_value = {
            "configured_str": "Band 8",
            "connected_band": "Band 8 (900 MHz)",
            "earfcn": "3738",
            "pci": "0",
            "supported_bands": [1, 3, 8, 40],
        }

        with patch("tplink_router.cli.main.get_client", return_value=mock_client), patch(
            "tplink_router.cli.main.SafeSession"
        ):
            # 1. Modern themed output (rounded borders)
            buf_mod = io.StringIO()
            with patch("sys.stdout", buf_mod):
                cmd_ipv6(argparse.Namespace(state=None, json=False, legacy=False, mono=False, interactive=False))
                cmd_clients(argparse.Namespace(json=False, legacy=False, mono=False))
                cmd_band(argparse.Namespace(band=None, json=False, legacy=False, mono=False, interactive=False))
            out_mod = strip_ansi(buf_mod.getvalue())
            self.assertIn("╭─ ◆ ROUTER IPv6 STACK STATUS", out_mod)
            self.assertIn("● ENABLED", out_mod)
            self.assertIn("╭─ ◆ CONNECTED LAN & WI-FI CLIENTS", out_mod)
            self.assertIn("dulith-pc", out_mod)
            self.assertIn("╭─ ◆ ACTIVE LTE BAND CONFIGURATION", out_mod)

            # 2. Monochrome B&W mode (--mono)
            buf_mono = io.StringIO()
            with patch("sys.stdout", buf_mono):
                cmd_ipv6(argparse.Namespace(state=None, json=False, legacy=False, mono=True, interactive=False))
            raw_mono = buf_mono.getvalue()
            self.assertNotIn("77;204;213", raw_mono)
            self.assertIn("[● ENABLED]", strip_ansi(raw_mono))

            # 3. Legacy mode (--legacy preserves === dividers)
            buf_leg = io.StringIO()
            with patch("sys.stdout", buf_leg):
                cmd_ipv6(argparse.Namespace(state=None, json=False, legacy=True, mono=False, interactive=False))
            out_leg = strip_ansi(buf_leg.getvalue())
            self.assertIn("=======================================================", out_leg)
            self.assertNotIn("╭─", out_leg)

            # 4. JSON mode (--json untouched)
            buf_json = io.StringIO()
            with patch("sys.stdout", buf_json):
                cmd_ipv6(argparse.Namespace(state=None, json=True, legacy=False, mono=False, interactive=False))
            parsed = json.loads(buf_json.getvalue())
            self.assertTrue(parsed["ipv6_enabled"])


if __name__ == "__main__":
    unittest.main()
