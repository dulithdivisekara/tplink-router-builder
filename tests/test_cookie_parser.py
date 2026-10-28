"""Tests for Netscape cookie parsing and session cookie extraction."""

import unittest
from tplink_router.core.cookie_parser import extract_jsessionid, parse_netscape_cookie_file


class TestCookieParser(unittest.TestCase):

    def test_netscape_format(self):
        sample = """# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.

192.168.1.1\tFALSE\t/\tFALSE\t0\tloginErrorShow\t3
192.168.1.1\tFALSE\t/\tFALSE\t0\tJSESSIONID\tc545185b9d1e49721ec951838574c0
"""
        token = extract_jsessionid(sample)
        self.assertEqual(token, "c545185b9d1e49721ec951838574c0")

    def test_cookie_header_format(self):
        header = "Cookie: loginErrorShow=3; JSESSIONID=b32bd522e6870382d2775da470517c; other=val"
        token = extract_jsessionid(header)
        self.assertEqual(token, "b32bd522e6870382d2775da470517c")

    def test_raw_token(self):
        raw = "c545185b9d1e49721ec951838574c0"
        token = extract_jsessionid(raw)
        self.assertEqual(token, "c545185b9d1e49721ec951838574c0")

    def test_parse_netscape_dict(self):
        sample = "192.168.1.1\tFALSE\t/\tFALSE\t0\tJSESSIONID\ttoken123\n192.168.1.1\tFALSE\t/\tFALSE\t0\tloginErrorShow\t1"
        cookies = parse_netscape_cookie_file(sample)
        self.assertEqual(cookies.get("JSESSIONID"), "token123")
        self.assertEqual(cookies.get("loginErrorShow"), "1")


if __name__ == "__main__":
    unittest.main()
