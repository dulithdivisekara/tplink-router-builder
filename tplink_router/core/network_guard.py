"""Cross-platform Network Guard to prevent accidental router misconfiguration.

Protects against applying changes when connected to non-target networks
(such as University Wi-Fi, Coffee Shop hotspots, or Mobile Hotspots).
Works across Linux, macOS, and Windows.
"""

import os
import platform
import re
import subprocess
import urllib.parse
from typing import Tuple, Optional


class NetworkGuard:
    """Verifies that the PC is connected to the intended router before sending commands."""

    @staticmethod
    def get_current_gateway() -> Optional[str]:
        """Detects the current default IPv4 gateway across Linux, macOS, and Windows."""
        system = platform.system()
        try:
            if system == "Linux":
                out = subprocess.check_output(["ip", "route", "show", "default"], stderr=subprocess.DEVNULL, timeout=2).decode()
                # default via 192.168.1.1 dev wlo1 ...
                match = re.search(r"default via ([0-9.]+)", out)
                if match:
                    return match.group(1)
            elif system == "Darwin":  # macOS
                out = subprocess.check_output(["route", "-n", "get", "default"], stderr=subprocess.DEVNULL, timeout=2).decode()
                match = re.search(r"gateway:\s*([0-9.]+)", out)
                if match:
                    return match.group(1)
            elif system == "Windows":
                out = subprocess.check_output(["route", "print", "0.0.0.0"], stderr=subprocess.DEVNULL, timeout=2).decode()
                match = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+([0-9.]+)", out)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    @staticmethod
    def get_current_ssid() -> Optional[str]:
        """Detects the current connected Wi-Fi SSID across Linux, macOS, and Windows."""
        system = platform.system()
        try:
            if system == "Linux":
                # Try nmcli first
                try:
                    out = subprocess.check_output(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], stderr=subprocess.DEVNULL, timeout=2).decode()
                    for line in out.splitlines():
                        if line.startswith("yes:"):
                            return line.split(":", 1)[1].strip()
                except Exception:
                    pass

                # Fallback to iw link
                out = subprocess.check_output(["iw", "dev"], stderr=subprocess.DEVNULL, timeout=2).decode()
                ifaces = re.findall(r"Interface\s+([a-zA-Z0-9_]+)", out)
                for iface in ifaces:
                    try:
                        link_out = subprocess.check_output(["iw", "dev", iface, "link"], stderr=subprocess.DEVNULL, timeout=2).decode()
                        match = re.search(r"SSID:\s*(.+)", link_out)
                        if match:
                            return match.group(1).strip()
                    except Exception:
                        continue

            elif system == "Darwin":  # macOS
                try:
                    out = subprocess.check_output(
                        ["/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport", "-I"],
                        stderr=subprocess.DEVNULL, timeout=2
                    ).decode()
                    match = re.search(r"\bSSID:\s*(.+)", out)
                    if match:
                        return match.group(1).strip()
                except Exception:
                    pass

            elif system == "Windows":
                out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], stderr=subprocess.DEVNULL, timeout=2).decode()
                match = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
                if match:
                    return match.group(1).strip()
        except Exception:
            pass
        return None

    @classmethod
    def check_safety(cls, target_host: str, expected_ssid: Optional[str] = None,
                     force: bool = False) -> Tuple[bool, str]:
        """Validates connection safety before router operations are dispatched.

        Returns:
            (is_safe, message)
        """
        if force:
            return True, "Force mode enabled; bypassed network guard."

        parsed = urllib.parse.urlparse(target_host)
        target_ip = parsed.hostname or target_host.replace("http://", "").replace("https://", "").split("/")[0]

        curr_gw = cls.get_current_gateway()
        curr_ssid = cls.get_current_ssid()

        # If gateway cannot be resolved, allow with notice
        if not curr_gw:
            return True, f"Could not determine default gateway. Target is {target_ip}."

        # Verify SSID if configured
        if expected_ssid and curr_ssid and curr_ssid.lower() != expected_ssid.lower():
            return False, (
                f"Network mismatch: Connected to Wi-Fi '{curr_ssid}', "
                f"but router expects SSID '{expected_ssid}'. "
                f"Aborting to protect current network (use --force to override)."
            )

        # Check if gateway matches target router IP (or common router subnets)
        if curr_gw != target_ip:
            # If target is 192.168.1.1 and gateway is different (e.g. 172.16.x for SLIIT Campus)
            return False, (
                f"Gateway mismatch: Your active gateway is {curr_gw} (SSID: '{curr_ssid or 'Wired/Unknown'}'), "
                f"which does not match the target router at {target_ip}. "
                f"Skipping router operation to avoid disrupting this network (use --force to override)."
            )

        return True, f"Verified connection to {target_ip} (SSID: '{curr_ssid or 'Unknown'}', Gateway: {curr_gw})."
