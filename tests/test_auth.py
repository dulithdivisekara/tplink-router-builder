"""Unit tests for TP-Link Archer MR200 cryptographic authentication and client helpers."""

import unittest
from tplink_router.core.auth import pkcs7_pad, pkcs7_unpad, tp_rsa_encrypt
from tplink_router.clients.mr_client import escape_act_val, unescape_act_val, TPLinkMRClient


class TestTPLinkAuth(unittest.TestCase):

    def test_pkcs7_padding(self):
        data = b"admin\n12345"
        padded = pkcs7_pad(data, 16)
        self.assertEqual(len(padded) % 16, 0)
        self.assertEqual(pkcs7_unpad(padded), data)

    def test_escape_act_val(self):
        raw = "code=*344#&status=1\n"
        escaped = escape_act_val(raw)
        self.assertIn("&#61;", escaped)
        self.assertIn("&amp;", escaped)
        self.assertIn("&#10;", escaped)
        self.assertEqual(unescape_act_val(escaped), raw)

    def test_tp_rsa_encryption_format(self):
        # 512-bit test modulus and exponent
        nn = "8532A444BA023C047BA4C5C7D1B9DB1699AE733E8AF8A5CD0E398761F4A78546AA35C3FAD83F2F6936D575A6B732A885AC55843138934C208F6A436B1B29A845"
        ee = "010001"
        plaintext = "key=test123456789012&iv=test123456789012&h=d41d8cd98f00b204e9800998ecf8427e&s=12345678"
        cipher_hex = tp_rsa_encrypt(plaintext, nn, ee, rsa_bits=512, flag=0)
        # 512 bits / 4 = 128 hex chars per 64-byte chunk. Length 89 chars spans 2 chunks = 256 hex chars.
        self.assertEqual(len(cipher_hex), 256)
        self.assertTrue(all(c in "0123456789abcdefABCDEF" for c in cipher_hex))

    def test_oid_response_parser(self):
        sample_response = (
            "[0,0,0,0,0,0]0\r\n"
            "enable=1\r\n"
            "connectStatus=1\r\n"
            "networkType=4\r\n"
            "[0,0,0,0,0,0]1\r\n"
            "curRxSpeed=154200\r\n"
            "curTxSpeed=32100\r\n"
        )
        parsed = TPLinkMRClient._parse_oid_response(sample_response)
        self.assertEqual(parsed["0"]["enable"], "1")
        self.assertEqual(parsed["0"]["connectStatus"], "1")
        self.assertEqual(parsed["1"]["curRxSpeed"], "154200")


if __name__ == "__main__":
    unittest.main()
