"""Multi-protocol authentication handler for TP-Link routers across models and firmware versions."""

import base64
import hashlib
import json
import random
import re
import string
import urllib.parse
from typing import Dict, Any, Optional
import requests


def pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return b""
    pad_len = data[-1]
    if pad_len > 16:
        return data
    return data[:-pad_len]


def tp_rsa_encrypt(text: str, nn_hex: str, ee_hex: str, rsa_bits: int = 512, flag: int = 0) -> str:
    """Implements TP-Link's specific chunked RSA encryption algorithm (encrypt.js)."""
    n = int(nn_hex, 16)
    e = int(ee_hex, 16)
    str_en_len = rsa_bits // 4  # 128 hex chars
    str_de_len = rsa_bits // 8  # 64 bytes
    step = (str_de_len - 11) if flag else str_de_len

    result = []
    start = 0
    while start < len(text):
        chunk = text[start:start + step]
        raw_bytes = chunk.encode("utf-8")
        if len(raw_bytes) > str_de_len:
            raise ValueError(f"Chunk size {len(raw_bytes)} exceeds block size {str_de_len}")
        padded = raw_bytes + b"\x00" * (str_de_len - len(raw_bytes))
        m = int.from_bytes(padded, byteorder="big")
        c = pow(m, e, n)
        c_hex = f"{c:x}"
        if len(c_hex) < str_en_len:
            c_hex = "0" * (str_en_len - len(c_hex)) + c_hex
        result.append(c_hex)
        start += step

    return "".join(result)


class MultiProtocolAuth:
    """Manages authentication, token tracking, and clean session logout."""

    def __init__(self, host: str, session: Optional[requests.Session] = None, session_cookie: Optional[str] = None):
        self.host = host.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({
            "Referer": f"{self.host}/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })
        self.session_cookie = session_cookie
        self.stok: Optional[str] = None
        self.token_id: Optional[str] = None
        self.is_authenticated = False

        # GDPR encryption session context
        self.aes_key: Optional[str] = None
        self.aes_iv: Optional[str] = None
        self.h: Optional[str] = None
        self.seq: int = 0
        self.nn: Optional[str] = None
        self.ee: Optional[str] = None

    def login(self, username: str, password: str) -> bool:
        """Attempts multi-protocol login: session cookie bypass first, modern GDPR second, legacy third."""
        # 1. Try session cookie bypass if provided
        if self.session_cookie:
            if self._verify_session_cookie(self.session_cookie):
                return True

        # 2. Modern GDPR encryption handshake
        try:
            return self._login_modern_gdpr(username, password)
        except Exception as e:
            if "Incorrect" in str(e) or "71233" in str(e):
                raise
            # 3. Try legacy login fallback
            return self._login_legacy(username, password)

    def _verify_session_cookie(self, cookie: str) -> bool:
        """Tests if a supplied browser JSESSIONID cookie is alive and valid."""
        host_domain = urllib.parse.urlparse(self.host).hostname or "192.168.1.1"
        self.session.cookies.set("JSESSIONID", cookie, domain=host_domain, path="/")
        try:
            resp = self.session.get(f"{self.host}/", timeout=5)
            if resp.status_code == 200:
                token_match = re.search(r'var token=\"([a-f0-9]+)\"', resp.text)
                if token_match:
                    self.token_id = token_match.group(1)
                    self.is_authenticated = True
                    return True
        except Exception:
            pass
        return False

    def _login_modern_gdpr(self, username: str, password: str) -> bool:
        """Modern TP-Link GDPR encryption handshake."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        # 1. getParm
        url = f"{self.host}/cgi/getParm"
        resp = self.session.post(url, data="", timeout=15)
        if resp.status_code != 200:
            raise ConnectionError(f"Router returned status {resp.status_code} on getParm")

        parms = resp.json()
        seq = int(parms.get("seq", 0))
        nn = parms["nn"]
        ee = parms["ee"]

        # 2. Generate random 16-char key and iv
        charset = string.ascii_letters + string.digits
        aes_key = "".join(random.choices(charset, k=16))
        aes_iv = "".join(random.choices(charset, k=16))
        h = hashlib.md5((username + password).encode("utf-8")).hexdigest()

        # 3. AES-128-CBC
        plain = f"{username}\n{password}".encode("utf-8")
        cipher = Cipher(algorithms.AES(aes_key.encode("utf-8")), modes.CBC(aes_iv.encode("utf-8")), backend=default_backend())
        encryptor = cipher.encryptor()
        aes_cipher_bytes = encryptor.update(pkcs7_pad(plain)) + encryptor.finalize()
        aes_data_b64 = base64.b64encode(aes_cipher_bytes).decode("utf-8")

        # 4. Signature
        sig_str = f"key={aes_key}&iv={aes_iv}&h={h}&s={seq + len(aes_data_b64)}"
        rsa_sign = tp_rsa_encrypt(sig_str, nn, ee, rsa_bits=512, flag=0)

        # 5. POST /cgi/login
        login_url = (
            f"{self.host}/cgi/login?data={urllib.parse.quote(aes_data_b64)}"
            f"&sign={rsa_sign}&Action=1&LoginStatus=0"
        )
        login_resp = self.session.post(login_url, data="", timeout=15)
        if login_resp.status_code != 200:
            raise ConnectionError(f"Login failed with HTTP {login_resp.status_code}")

        res_data = login_resp.json()
        ret = res_data.get("ret")
        if ret == 0:
            self.is_authenticated = True
            self.aes_key = aes_key
            self.aes_iv = aes_iv
            self.h = h
            self.seq = seq
            self.nn = nn
            self.ee = ee

            # Extract TokenID from root page
            try:
                root_resp = self.session.get(f"{self.host}/", timeout=5)
                token_match = re.search(r'var token=\"([a-f0-9]+)\"', root_resp.text)
                if token_match:
                    self.token_id = token_match.group(1)
            except Exception:
                pass

            # Check for stok
            if "stok" in login_resp.text:
                m = re.search(r'stok=([a-zA-Z0-9%_-]+)', login_resp.text)
                if m:
                    self.stok = m.group(1)
            return True
        elif ret == 71233:
            raise PermissionError("Incorrect router admin password.")
        else:
            raise PermissionError(f"Router login rejected with code {ret}")

    def encrypt_gdpr_data(self, data_str: str) -> tuple[str, str]:
        """Encrypts payload for /cgi_gdpr endpoint and generates RSA signature."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        c = Cipher(algorithms.AES(self.aes_key.encode("utf-8")), modes.CBC(self.aes_iv.encode("utf-8")), backend=default_backend())
        enc_bytes = c.encryptor().update(pkcs7_pad(data_str.encode("utf-8"))) + c.encryptor().finalize()
        enc_b64 = base64.b64encode(enc_bytes).decode("utf-8")

        sig_str = f"h={self.h}&s={self.seq + len(enc_b64)}"
        rsa_sig = tp_rsa_encrypt(sig_str, self.nn, self.ee, rsa_bits=512, flag=0)
        return rsa_sig, enc_b64

    def decrypt_gdpr_data(self, enc_b64: str) -> str:
        """Decrypts base64 AES data from /cgi_gdpr response."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        c = Cipher(algorithms.AES(self.aes_key.encode("utf-8")), modes.CBC(self.aes_iv.encode("utf-8")), backend=default_backend())
        dec_bytes = c.decryptor().update(base64.b64decode(enc_b64)) + c.decryptor().finalize()
        return pkcs7_unpad(dec_bytes).decode("utf-8", errors="replace")

    def _login_legacy(self, username: str, password: str) -> bool:
        """Legacy TP-Link plain or basic encoded authentication."""
        url = f"{self.host}/cgi/login?UserName={username}&Passwd={password}&Action=1&LoginStatus=0"
        resp = self.session.post(url, data="", timeout=15)
        if resp.status_code == 200 and "error" not in resp.text.lower():
            self.is_authenticated = True
            return True
        raise ConnectionError("Legacy login failed.")

    def logout(self):
        """Releases the router's single-admin lock so other sessions (like browser) remain working."""
        if not self.is_authenticated:
            return
        try:
            logout_url = f"{self.host}/cgi/logout"
            self.session.post(logout_url, data="", timeout=5)
        except Exception:
            pass
        finally:
            self.is_authenticated = False
