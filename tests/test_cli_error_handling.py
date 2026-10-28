"""Unit tests for professional CLI error handling across offline, timeout, and auth failures."""

import argparse
import io
import json
import sys
import unittest
from unittest.mock import patch
import requests

from tplink_router.cli.main import handle_cli_error


class TestCLIErrorHandling(unittest.TestCase):

    def test_network_unreachable_card(self):
        err = requests.exceptions.ConnectionError(
            "HTTPConnectionPool(host='192.168.1.1', port=80): Failed to establish a new connection: [Errno 101] Network is unreachable"
        )
        args = argparse.Namespace(json=False, host="http://192.168.1.1")

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = handle_cli_error(err, args)

        output = captured.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("ROUTER UNREACHABLE (OFFLINE)", output)
        self.assertIn("Router Rebooting", output)
        self.assertIn("Wi-Fi Dropped", output)
        self.assertIn("http://192.168.1.1", output)

    def test_network_unreachable_json(self):
        err = requests.exceptions.ConnectionError(
            "Failed to establish a new connection: [Errno 101] Network is unreachable"
        )
        args = argparse.Namespace(json=True, host="http://192.168.1.1")

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            code = handle_cli_error(err, args)

        self.assertEqual(code, 1)
        data = json.loads(captured.getvalue())
        self.assertTrue(data["error"])
        self.assertEqual(data["code"], "ROUTER_UNREACHABLE")
        self.assertIn("60–90 seconds", data["hint"])

    def test_timeout_card_and_json(self):
        err = requests.exceptions.Timeout("Connection timed out after 15 seconds")

        # Terminal format
        captured_text = io.StringIO()
        with patch("sys.stdout", captured_text):
            code_text = handle_cli_error(err, argparse.Namespace(json=False, host="http://192.168.1.1"))
        self.assertEqual(code_text, 1)
        self.assertIn("ROUTER CONNECTION TIMED OUT", captured_text.getvalue())

        # JSON format
        captured_json = io.StringIO()
        with patch("sys.stderr", captured_json):
            code_json = handle_cli_error(err, argparse.Namespace(json=True, host="http://192.168.1.1"))
        self.assertEqual(code_json, 1)
        d = json.loads(captured_json.getvalue())
        self.assertEqual(d["code"], "REQUEST_TIMEOUT")

    def test_auth_failed_card_and_json(self):
        err = PermissionError("Incorrect router admin password.")

        # Terminal format
        captured_text = io.StringIO()
        with patch("sys.stdout", captured_text):
            code_text = handle_cli_error(err, argparse.Namespace(json=False, host="http://192.168.1.1"))
        self.assertEqual(code_text, 1)
        self.assertIn("AUTHENTICATION FAILED", captured_text.getvalue())
        self.assertIn("tplink-cli config set-password", captured_text.getvalue())

        # JSON format
        captured_json = io.StringIO()
        with patch("sys.stderr", captured_json):
            code_json = handle_cli_error(err, argparse.Namespace(json=True, host="http://192.168.1.1"))
        self.assertEqual(code_json, 1)
        d = json.loads(captured_json.getvalue())
        self.assertEqual(d["code"], "AUTHENTICATION_FAILED")

    def test_invalid_argument_error(self):
        err = ValueError("Invalid band '99' specified.")
        captured_text = io.StringIO()
        with patch("sys.stdout", captured_text):
            code_text = handle_cli_error(err, argparse.Namespace(json=False))
        self.assertEqual(code_text, 2)
        self.assertIn("CONFIGURATION / ARGUMENT ERROR", captured_text.getvalue())


if __name__ == "__main__":
    unittest.main()
