"""Netscape HTTP Cookie File and JSESSIONID Parser for TP-Link Routers.

Supports parsing:
1. Netscape HTTP Cookie File format (exported by browser extensions like Cookie-Editor / Get cookies.txt)
2. Raw HTTP Cookie header string (e.g. 'JSESSIONID=c545185b9d...; loginErrorShow=3')
3. Plain hexadecimal session string (e.g. 'c545185b9d1e49721ec951838574c0')
4. File path pointing to a saved cookie file.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict


def extract_jsessionid(raw_input: str) -> Optional[str]:
    """Extracts the 20-64 char hexadecimal JSESSIONID from any format."""
    if not raw_input:
        return None

    raw_input = raw_input.strip()

    # If input is a file path that exists, read its contents
    if "\n" not in raw_input and (Path(raw_input).expanduser().is_file() or os.path.isfile(raw_input)):
        try:
            with open(Path(raw_input).expanduser(), "r", encoding="utf-8") as f:
                raw_input = f.read().strip()
        except Exception:
            pass

    # 1. Check if the input is already a clean hex session ID
    if re.match(r"^[a-fA-F0-9]{20,64}$", raw_input):
        return raw_input

    # 2. Check for Netscape Cookie format (tab or space separated lines)
    # Format: domain flag path secure expiration name value
    # e.g.: 192.168.1.1 FALSE / FALSE 0 JSESSIONID c545185b9d1e49721ec951838574c0
    for line in raw_input.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[\t\s]+", line)
        if len(parts) >= 7 and parts[5] == "JSESSIONID":
            val = parts[6].strip()
            if re.match(r"^[a-fA-F0-9]{20,64}$", val):
                return val

    # 3. Regex match for JSESSIONID in any Netscape or text block
    m = re.search(r"\bJSESSIONID[\t\s=]+([a-fA-F0-9]{20,64})\b", raw_input)
    if m:
        return m.group(1)

    # 4. Standard Cookie header format (key=value; key2=value2)
    m2 = re.search(r"JSESSIONID=([a-fA-F0-9]+)", raw_input)
    if m2:
        return m2.group(1)

    return None


def parse_cookie_file(file_path: Path) -> Dict[str, str]:
    """Parses all cookies from a Netscape cookie file into a key-value dictionary."""
    cookies = {}
    if not file_path.exists():
        return cookies

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return parse_netscape_cookie_file(f.read())
    except Exception:
        pass
    return cookies


def parse_netscape_cookie_file(raw_content: str) -> Dict[str, str]:
    """Parses raw Netscape cookie format content into a key-value dictionary."""
    cookies = {}
    for line in raw_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[\t]+", line)
        if len(parts) >= 7:
            cookies[parts[5].strip()] = parts[6].strip()
        elif len(parts) >= 2 and "\t" not in line:
            # Fallback for space separated
            sp = line.split()
            if len(sp) >= 7:
                cookies[sp[5].strip()] = sp[6].strip()
    return cookies
