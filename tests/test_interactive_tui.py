"""
Unit tests for interactive_tui.py
"""
import unittest
from tplink_router.cli.interactive_tui import filter_commands, COMMAND_CATALOG


class TestInteractiveTUI(unittest.TestCase):
    def test_catalog_completeness(self):
        self.assertGreaterEqual(len(COMMAND_CATALOG), 30)
        names = [c[0] for c in COMMAND_CATALOG]
        self.assertIn("status", names)
        self.assertIn("signal", names)
        self.assertIn("band", names)
        self.assertIn("cell-lock", names)
        self.assertIn("ipv6", names)
        self.assertIn("dns", names)
        self.assertIn("clients", names)
        self.assertIn("wifi", names)
        self.assertIn("leds", names)
        self.assertIn("sms", names)
        self.assertIn("ussd", names)
        self.assertIn("reboot", names)

    def test_empty_query_returns_all(self):
        self.assertEqual(len(filter_commands("")), len(COMMAND_CATALOG))
        self.assertEqual(len(filter_commands("   ")), len(COMMAND_CATALOG))

    def test_prefix_filtering(self):
        res = filter_commands("sig")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0][0], "signal")

    def test_substring_filtering(self):
        res = filter_commands("band")
        names = [c[0] for c in res]
        self.assertEqual(names[0], "band")

    def test_fuzzy_desc_filtering(self):
        res = filter_commands("telemetry")
        names = [c[0] for c in res]
        self.assertIn("status", names)


if __name__ == "__main__":
    unittest.main()
