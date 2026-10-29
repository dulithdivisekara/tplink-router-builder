"""Unified CLI command-line interface for TP-Link Router Management."""

import argparse
import getpass
import json
import sys
import time
from typing import Any, Optional
import requests

from tplink_router.clients.factory import RouterClientFactory
from tplink_router.core.config import ConfigManager
from tplink_router.core.network_guard import NetworkGuard
from tplink_router.core.session import SafeSession
from tplink_router.cli.repl import run_repl


def get_client(args: argparse.Namespace) -> Any:
    raw_cookie = getattr(args, "cookie", None)
    if raw_cookie == "PROMPT":
        print("Paste your browser session cookie or Netscape cookie block below:")
        try:
            raw_cookie = input("Cookie: ").strip()
        except EOFError:
            raw_cookie = None

    cfg = ConfigManager().load(
        cli_host=getattr(args, "host", None),
        cli_username=getattr(args, "username", None),
        cli_password=getattr(args, "password", None),
        cli_cookie=raw_cookie,
    )

    host = cfg["host"]
    username = cfg["username"]
    password = cfg["password"]
    session_cookie = cfg.get("session_cookie")
    expected_ssid = cfg.get("expected_ssid")
    force = getattr(args, "force", False)

    # Run Network Guard safety check
    is_safe, msg = NetworkGuard.check_safety(target_host=host, expected_ssid=expected_ssid, force=force)
    if not is_safe:
        if getattr(args, "json", False):
            print(json.dumps({
                "error": True,
                "code": "NETWORK_GUARD_BLOCKED",
                "message": msg
            }, indent=2), file=sys.stderr)
        else:
            print(f"\033[91m[Network Guard Alert] {msg}\033[0m")
        sys.exit(2)

    if not password and not session_cookie:
        print(f"No password or session cookie configured for router at {host}.")
        password = getpass.getpass("Enter router admin password: ")

    return RouterClientFactory.get_client(
        host=host, password=password, username=username, session_cookie=session_cookie
    )


def cmd_status(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        telemetry = client.get_telemetry()

    if getattr(args, "json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(telemetry), indent=2))
        return

    dev = telemetry.device
    lte = telemetry.lte
    v4 = telemetry.ipv4
    v6 = telemetry.ipv6

    print("\n" + "=" * 65)
    print(f"  \033[1mTP-LINK ROUTER TELEMETRY\033[0m  ({dev.model})")
    print("=" * 65)
    print(f"Hardware / Firmware : {dev.hardware_version} | {dev.firmware_version}")
    if lte:
        print(f"Cellular Operator   : \033[1m{lte.isp_name}\033[0m (SIM: {lte.sim_status})")
        print(f"Connection State    : {'\033[92mCONNECTED\033[0m' if lte.connected else '\033[91mDISCONNECTED\033[0m'}")
        print(f"LTE Band / EARFCN   : {lte.band} (EARFCN: {lte.earfcn or 'N/A'}, PCI: {lte.pci or 'N/A'})")
        lock = lte.cell_lock
        print(f"Cell Lock Status    : {'\033[92mLOCKED to EARFCN ' + lock.earfcn + ' PCI ' + lock.pci + '\033[0m' if lock.enabled else 'Disabled (Auto roaming)'}")
        print("-" * 65)
        print("  \033[1mRADIO FREQUENCY (RF) METRICS\033[0m")
        print(f"Signal Strength     : {lte.rf.signal_bars} / 4 bars")
        print(f"RSRP (Signal Power) : {lte.rf.rsrp_dbm} dBm (\033[1m{lte.rf.rsrp_rating}\033[0m)")
        print(f"RSRQ (Quality/Load) : {lte.rf.rsrq_db} dB (\033[1m{lte.rf.rsrq_rating}\033[0m)")
        print(f"SNR (Signal-to-Noise: {lte.rf.snr_db} dB (\033[1m{lte.rf.snr_rating}\033[0m)")
        print("-" * 65)
        print("  \033[1mTHROUGHPUT & USAGE\033[0m")
        print(f"Downlink / Uplink   : {lte.rx_speed_kbps} Kbps / {lte.tx_speed_kbps} Kbps")
        print(f"Total Transferred   : {round(lte.total_bytes_transferred / (1024 * 1024), 2)} MB")

    print("-" * 65)
    print("  \033[1mWAN NETWORK CONFIGURATION\033[0m")
    print(f"WAN IPv4 Address    : {v4.ip or 'N/A'} (Gateway: {v4.gateway or 'N/A'})")
    print(f"Active DNS Servers  : {', '.join(v4.dns) if v4.dns else 'Default ISP'}")
    print(f"IPv6 Enabled        : {'\033[92mYes\033[0m (' + v6.status + ')' if v6.enabled else '\033[93mDisabled\033[0m'}")
    print("=" * 65 + "\n")


def cmd_signal(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_lte_status"):
            print("Signal metrics are only available on cellular MR models.")
            return
        lte = client.get_lte_status()

    if getattr(args, "json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(lte.rf), indent=2))
        return

    print("\n\033[1mCurrent LTE RF Signal:\033[0m")
    print(f"  Carrier      : {lte.isp_name}")
    print(f"  Active Band  : {lte.band} (EARFCN: {lte.earfcn}, PCI: {lte.pci})")
    print(f"  Signal Level : {lte.rf.signal_bars} / 4 bars")
    if lte.rf.rssi_dbm != 0:
        print(f"  RSSI         : {lte.rf.rssi_dbm} dBm ({lte.rf.rssi_rating})")
    if lte.rf.rsrp_dbm != 0:
        print(f"  RSRP         : {lte.rf.rsrp_dbm} dBm ({lte.rf.rsrp_rating})")
    else:
        print(f"  RSRP         : N/A (Modem raw: 0 dBm)")
    if lte.rf.rsrq_db != 0:
        print(f"  RSRQ         : {lte.rf.rsrq_db} dB ({lte.rf.rsrq_rating})")
    if lte.rf.snr_db != 0:
        print(f"  SNR          : {lte.rf.snr_db} dB ({lte.rf.snr_rating})")
    print()


def cmd_cell_lock(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_cell_lock"):
            print("Cell Lock is only supported on cellular MR models.")
            return

        if getattr(args, "enable", False):
            if not getattr(args, "earfcn", None) or not getattr(args, "pci", None):
                print("\033[91mError: Both --earfcn and --pci are required when enabling Cell Lock.\033[0m")
                sys.exit(1)
            client.set_cell_lock(True, args.earfcn, args.pci)
            print(f"\033[92mCell Lock applied to EARFCN {args.earfcn}, PCI {args.pci}!\033[0m")
        elif getattr(args, "disable", False):
            client.set_cell_lock(False)
            print("\033[92mCell Lock disabled (Auto roaming restored).\033[0m")
        else:
            lock = client.get_cell_lock()
            if getattr(args, "json", False):
                import dataclasses
                print(json.dumps(dataclasses.asdict(lock), indent=2))
                return
            print("\n" + "=" * 55)
            print("  \033[1mLTE CELL LOCK STATUS\033[0m")
            print("=" * 55)
            if lock.enabled:
                print(f"Status        : \033[92mLOCKED (Targeting Cell Tower)\033[0m")
                print(f"Target EARFCN : {lock.earfcn}")
                print(f"Target PCI    : {lock.pci}")
                if lock.cid:
                    print(f"Cell ID (CID) : {lock.cid}")
                if lock.freq:
                    print(f"Frequency     : {lock.freq}")
            else:
                print(f"Status        : \033[93mDisabled (Auto-Roaming Active)\033[0m")
                print("Router automatically chooses the strongest carrier cell.")
            print("-" * 55)
            print("Commands:")
            print("  Lock tower   : tplink-cli cell-lock --enable --earfcn <earfcn> --pci <pci>")
            print("  Restore auto : tplink-cli cell-lock --disable")
            print("=" * 55 + "\n")


def cmd_dns(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        action = getattr(args, "action", None)
        if action == "set":
            primary = getattr(args, "primary", None)
            if not primary:
                print("\nUsage: tplink-cli dns set <primary_dns> [secondary_dns]")
                print("Examples:")
                print("  tplink-cli dns set 1.1.1.1 1.0.0.1    (Cloudflare)")
                print("  tplink-cli dns set 8.8.8.8 8.8.4.4    (Google)\n")
                return
            secondary = getattr(args, "secondary", "8.8.8.8") or "8.8.8.8"
            client.set_dns(primary, secondary)
            print(f"\033[92mDNS configured to {primary}, {secondary}\033[0m")
        else:
            v4, v6 = client.get_wan_config()
            if getattr(args, "json", False):
                print(json.dumps({
                    "ipv4_dns": v4.dns,
                    "ipv6_dns": v6.dns,
                    "gateway": v4.gateway,
                    "wan_ip": v4.ip
                }, indent=2))
                return
            print("\n" + "=" * 55)
            print("  \033[1mROUTER DNS CONFIGURATION\033[0m")
            print("=" * 55)
            if v4.dns:
                print(f"Active IPv4 DNS : \033[1m{', '.join(v4.dns)}\033[0m")
            else:
                print("Active IPv4 DNS : Default ISP Assigned")
            if v6.dns:
                print(f"Active IPv6 DNS : {', '.join(v6.dns)}")
            print(f"WAN IP Address  : {v4.ip or 'Disconnected'}")
            print(f"Default Gateway : {v4.gateway or 'N/A'}")
            print("-" * 55)
            print("To customize DNS servers:")
            print("  tplink-cli dns set 1.1.1.1 1.0.0.1    (Cloudflare)")
            print("  tplink-cli dns set 8.8.8.8 8.8.4.4    (Google)")
            print("=" * 55 + "\n")


def cmd_ipv6(args: argparse.Namespace):
    client = get_client(args)
    state_str = getattr(args, "state", None)
    with SafeSession(client):
        if not state_str:
            v4, v6 = client.get_wan_config()
            is_enabled = bool(v6.ip or (v6.dns and any(d != "0.0.0.0" for d in v6.dns)))
            if getattr(args, "json", False):
                print(json.dumps({
                    "ipv6_enabled": is_enabled,
                    "ipv6_address": v6.ip or None,
                    "ipv6_dns": v6.dns or [],
                    "gateway": v6.gateway or None
                }, indent=2))
                return
            print("\n" + "=" * 55)
            print("  \033[1mROUTER IPv6 STACK STATUS\033[0m")
            print("=" * 55)
            status_str = "\033[92mENABLED\033[0m" if is_enabled else "\033[90mDISABLED\033[0m"
            print(f"IPv6 Stack State   : {status_str}")
            if v6.ip:
                print(f"IPv6 WAN Address   : {v6.ip}")
            if v6.dns:
                print(f"IPv6 DNS Resolvers : {', '.join(v6.dns)}")
            print("-" * 55)
            print("To toggle IPv6:")
            print("  tplink-cli ipv6 on")
            print("  tplink-cli ipv6 off")
            print("=" * 55 + "\n")
            return

        state = state_str.lower() in ("on", "1", "true", "enable")
        client.toggle_ipv6(state)
    print(f"\033[92mIPv6 {'enabled' if state else 'disabled'} successfully.\033[0m")


def cmd_ussd(args: argparse.Namespace):
    code = getattr(args, "code", None)
    if not code:
        if sys.stdin.isatty():
            try:
                code = input("Enter USSD query code (e.g. *344#, *123#): ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return
        if not code:
            if getattr(args, "json", False):
                print(json.dumps({"error": "No USSD code provided"}))
                return
            print("\n" + "=" * 55)
            print("  \033[1mCELLULAR USSD QUERY\033[0m")
            print("=" * 55)
            print("Usage: tplink-cli ussd <code>")
            print("-" * 55)
            print("Common Carrier USSD Codes in Sri Lanka:")
            print("  • \033[1mHutch\033[0m   : *344# (Balance & Data Quota), *123# (Self-Care)")
            print("  • \033[1mDialog\033[0m  : *123# (Account Balance), *456# (Data Balance)")
            print("  • \033[1mMobitel\033[0m : *100# (Account Balance), *145# (Self-Care)")
            print("  • \033[1mAirtel\033[0m  : *550# (Balance & Data)")
            print("-" * 55)
            print("Example:")
            print("  tplink-cli ussd *344#")
            print("=======================================================\n")
            return

    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "send_ussd"):
            print("USSD commands are only supported on cellular MR models.")
            return
        res = client.send_ussd(code)

    if getattr(args, "json", False):
        print(json.dumps({"code": code, "response": res.response}))
        return
    print(f"\n\033[1mUSSD Response:\033[0m\n{res.response}\n")


def cmd_sms(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_sms"):
            print("SMS is only supported on cellular MR models.")
            return
        if getattr(args, "subcommand", None) == "send":
            recip = getattr(args, "recipient", None)
            msg = getattr(args, "message", None)
            if not recip or not msg:
                if sys.stdin.isatty():
                    try:
                        if not recip:
                            recip = input("Enter recipient phone number: ").strip()
                        if not msg:
                            msg = input("Enter SMS message text: ").strip()
                    except (KeyboardInterrupt, EOFError):
                        print()
                        return
            if not recip or not msg:
                print("\nUsage: tplink-cli sms send <phone_number> <message>")
                print("Example: tplink-cli sms send +94771234567 'Hello from router'\n")
                return
            client.send_sms(recip, msg)
            print("\033[92mSMS sent successfully.\033[0m")
        else:
            limit = getattr(args, "limit", 10) or 10
            folder = getattr(args, "folder", "inbox") or "inbox"
            msgs = client.get_sms(limit=limit, folder=folder)
            if getattr(args, "json", False):
                import dataclasses
                print(json.dumps([dataclasses.asdict(m) for m in msgs], indent=2))
                return
            print(f"\n\033[1mSMS ({len(msgs)} messages in {folder}):\033[0m")
            print("-" * 65)
            for m in msgs:
                unread = "\033[93m[NEW]\033[0m " if m.unread else ""
                print(f"{unread}From: {m.sender} | Date: {m.received_time}")
                print(f"Content: {m.content}")
                print("-" * 65)
            print()


def cmd_reboot(args: argparse.Namespace):
    if not args.yes:
        confirm = input("Are you sure you want to reboot the TP-Link router? (y/N): ")
        if confirm.lower() != "y":
            print("Reboot cancelled.")
            return
    client = get_client(args)
    with SafeSession(client):
        client.reboot()
    if getattr(args, "json", False):
        print(json.dumps({"success": True, "message": "Router reboot initiated. Reconnect in 60-90 seconds."}, indent=2))
    else:
        print("\n\033[92m✓ Router reboot initiated successfully.\033[0m")
        print("  ℹ  The router is restarting. Wi-Fi & Internet will temporarily drop for \033[1m~60–90 seconds\033[0m.")
        print("  ℹ  Please wait until router LEDs turn solid before executing subsequent commands.\n")


def cmd_profile_check(args: argparse.Namespace):
    """Verifies which network the host machine is currently connected to."""
    gw = NetworkGuard.get_current_gateway()
    ssid = NetworkGuard.get_current_ssid()
    cfg = ConfigManager().load()
    is_safe, msg = NetworkGuard.check_safety(target_host=cfg["host"], expected_ssid=cfg.get("expected_ssid"))

    print("\n" + "=" * 60)
    print("  \033[1mHOST NETWORK ENVIRONMENT CHECK\033[0m")
    print("=" * 60)
    print(f"Current Wi-Fi SSID : \033[1m{ssid or 'Wired / Hotspot'}\033[0m")
    print(f"Default Gateway    : \033[1m{gw or 'Unknown'}\033[0m")
    print(f"Target Router Host : {cfg['host']}")
    print(f"Network Guard State: {'\033[92mMATCH / SAFE\033[0m' if is_safe else '\033[93mMISMATCH / PROTECTED\033[0m'}")
    print(f"Detail             : {msg}")
    print("=" * 60 + "\n")


def cmd_config(args: argparse.Namespace):
    cfg_mgr = ConfigManager()
    subcommand = getattr(args, "subcommand", None) or "show"
    if subcommand == "set-password":
        pwd = args.password
        if not pwd:
            pwd = getpass.getpass("Enter router admin password to save: ")
        host = args.host or "http://192.168.1.1"
        username = args.username or "admin"
        ssid = args.expected_ssid or ""
        cfg_mgr.save(password=pwd, host=host, username=username, expected_ssid=ssid)
        print(f"\033[92mConfiguration securely saved to {cfg_mgr.config_file} (mode 0600).\033[0m")
    elif subcommand == "set-cookie":
        cookie_input = getattr(args, "cookie", None)
        cookie_file = getattr(args, "file", None)
        if cookie_file:
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    cookie_input = f.read()
            except Exception as e:
                print(f"\033[91mError reading cookie file {cookie_file}: {e}\033[0m")
                sys.exit(1)
        elif not cookie_input:
            print("Paste your browser session cookie, Netscape cookie block, or JSESSIONID:")
            print("(Paste content, then press Enter or Ctrl+D when finished)")
            lines = []
            try:
                while True:
                    line = input()
                    if not line and lines:
                        break
                    lines.append(line)
            except EOFError:
                pass
            cookie_input = "\n".join(lines).strip()

        from tplink_router.core.cookie_parser import extract_jsessionid
        extracted = extract_jsessionid(cookie_input)
        if not extracted:
            print("\033[91mFailed to extract valid JSESSIONID from the provided text.\033[0m")
            print("Expected format: Netscape cookie file, 'Cookie: JSESSIONID=...', or 30-32 character hex token.")
            sys.exit(1)

        cfg_mgr.save(session_cookie=extracted)
        masked = f"{extracted[:6]}...{extracted[-6:]}" if len(extracted) > 12 else extracted
        print(f"\033[92mSession cookie (JSESSIONID: {masked}) successfully saved to {cfg_mgr.config_file}.\033[0m")
    elif subcommand == "clear-cookie":
        cfg_mgr.save(session_cookie="")
        print(f"\033[92mStored session cookie cleared from {cfg_mgr.config_file}.\033[0m")
    elif subcommand == "show":
        cfg = cfg_mgr.load()
        has_pwd = bool(cfg.get("password"))
        cookie_val = cfg.get("session_cookie")
        has_cookie = bool(cookie_val)
        masked_cookie = f"{cookie_val[:6]}...{cookie_val[-6:]}" if (cookie_val and len(cookie_val) > 12) else "[SET]"
        print(f"Config File    : {cfg_mgr.config_file}")
        print(f"Router Host    : {cfg['host']}")
        print(f"Username       : {cfg['username']}")
        print(f"Expected SSID  : {cfg.get('expected_ssid') or '[Any]'}")
        print(f"Password       : {'[STORED - ' + str(len(cfg['password'])) + ' chars]' if has_pwd else '[NOT SET]'}")
        print(f"Session Cookie : {masked_cookie if has_cookie else '[NOT SET]'}")


def cmd_cookie(args: argparse.Namespace):
    cfg_mgr = ConfigManager()
    cookie_val = getattr(args, "cookie_val", None)
    if not cookie_val:
        cfg = cfg_mgr.load()
        c = cfg.get("session_cookie")
        if c:
            masked = f"{c[:6]}...{c[-6:]}" if len(c) > 12 else c
            print(f"\n\033[1mCurrent Session Cookie:\033[0m {masked} (JSESSIONID)")
            print(f"Saved in: {cfg_mgr.config_file}\n")
        else:
            print("\n\033[93mNo session cookie currently stored.\033[0m")
        print("To save a new cookie:")
        print("  tplink-cli cookie <cookie_string_or_netscape_block>")
        print("  tplink-cli config set-cookie --file <cookies.txt>\n")
        return

    from tplink_router.core.cookie_parser import extract_jsessionid
    extracted = extract_jsessionid(cookie_val)
    if not extracted:
        print("\033[91mError: Could not extract valid JSESSIONID from input.\033[0m")
        sys.exit(1)
    cfg_mgr.save(session_cookie=extracted)
    masked = f"{extracted[:6]}...{extracted[-6:]}" if len(extracted) > 12 else extracted
    print(f"\033[92mSession cookie (JSESSIONID: {masked}) successfully saved to {cfg_mgr.config_file}.\033[0m")


def cmd_wifi_guard(args: argparse.Namespace):
    """Diagnoses and prepares wireless connection for calibration without Ethernet."""
    import subprocess
    import shutil

    print("\n" + "=" * 65)
    print("  \033[1mWI-FI ONLY OPERATION & LINK STABILITY GUARD\033[0m")
    print("=" * 65)

    ssid = NetworkGuard.get_current_ssid()
    gw = NetworkGuard.get_current_gateway()

    print(f"Connected Wi-Fi SSID : \033[1m{ssid or 'Unknown'}\033[0m")
    print(f"Default Gateway      : {gw or 'Unknown'}")

    # Check power save on wireless interface
    ps_status = "Unknown"
    wlan_iface = "wlo1"
    try:
        res = subprocess.run(["iw", "dev"], capture_output=True, text=True, check=False)
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("Interface "):
                wlan_iface = line.split()[1]
                break
        res_ps = subprocess.run(["iw", "dev", wlan_iface, "get", "power_save"], capture_output=True, text=True, check=False)
        if "Power save: on" in res_ps.stdout:
            ps_status = "ON (Power Saving Active)"
        elif "Power save: off" in res_ps.stdout:
            ps_status = "OFF (High Performance)"
    except Exception:
        pass

    print(f"Wireless Interface   : {wlan_iface}")
    print(f"Wi-Fi Power Save     : {ps_status}")

    # Check autoconnect priority
    nm_priority = "N/A"
    if ssid and shutil.which("nmcli"):
        try:
            res_nm = subprocess.run(
                ["nmcli", "-t", "-f", "connection.autoconnect-priority", "connection", "show", ssid],
                capture_output=True, text=True, check=False
            )
            for line in res_nm.stdout.splitlines():
                if "connection.autoconnect-priority" in line:
                    nm_priority = line.split(":")[-1].strip()
                    break
        except Exception:
            pass

    print(f"Autoconnect Priority : {nm_priority}")
    print("-" * 65)

    if getattr(args, "fix", False) or getattr(args, "optimize", False):
        print("\033[93mApplying Wi-Fi Stability Optimizations...\033[0m")
        # 1. Set expected SSID in config
        if ssid:
            cfg_mgr = ConfigManager()
            cfg_mgr.save(expected_ssid=ssid)
            print(f"  ✓ Locked Network Guard to expected SSID: {ssid}")

        # 2. Elevate autoconnect priority if nmcli is available
        if ssid and shutil.which("nmcli"):
            try:
                subprocess.run(
                    ["nmcli", "connection", "modify", ssid, "connection.autoconnect-priority", "50"],
                    capture_output=True, text=True, check=False
                )
                print(f"  ✓ Elevated NetworkManager autoconnect-priority for '{ssid}' to 50")
            except Exception as e:
                print(f"  ! Could not set autoconnect-priority: {e}")

        # 3. Disable power save if iw is available
        try:
            subprocess.run(["iw", "dev", wlan_iface, "set", "power_save", "off"], capture_output=True, text=True, check=False)
            print(f"  ✓ Requested Wi-Fi power save OFF on {wlan_iface}")
        except Exception:
            pass

        print("\n\033[92m[READY] System is optimized for wireless-only calibration without Ethernet!\033[0m\n")
    else:
        print("💡 \033[1mHow Wi-Fi Only Mode Works:\033[0m")
        print("  1. The Archer MR200's Wi-Fi Access Point radio remains RUNNING even when")
        print("     cellular LTE frequency bands are switched or cell locked.")
        print("  2. Local Wi-Fi ping/HTTP to 192.168.1.1 will NOT disconnect.")
        print("  3. Only upstream internet traffic pauses for 5-15s during cell attach.")
        print("  4. Run `tplink-cli wifi-guard --optimize` to prevent NetworkManager from")
        print("     roaming to campus Wi-Fi or hotspot during calibration pauses.")
        print("=" * 65 + "\n")


def cmd_repl(args: argparse.Namespace):
    client = get_client(args)
    run_repl(client)


def cmd_clients(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_connected_clients"):
            print("Connected clients list is only supported on MR cellular models.")
            return
        clients = client.get_connected_clients()

    if getattr(args, "json", False):
        print(json.dumps(clients, indent=2))
        return

    print("\n" + "=" * 70)
    print("  \033[1mCONNECTED LAN CLIENTS\033[0m")
    print("=" * 70)
    print(f"{'HOSTNAME':<22} {'IP ADDRESS':<16} {'MAC ADDRESS':<18} {'LEASE REMAINING':<12}")
    print("-" * 70)
    for c in clients:
        print(f"{c['hostname']:<22} {c['ip']:<16} {c['mac']:<18} {c['lease_remaining']:<12}")
    print("=" * 70 + f"\nTotal connected clients: {len(clients)}\n")


def cmd_reservation(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_dhcp_reservations"):
            print("DHCP reservations are only supported on MR cellular models.")
            return

        sub = getattr(args, "subcommand", None) or "list"
        if sub == "list":
            reservations = client.get_dhcp_reservations()
            if getattr(args, "json", False):
                print(json.dumps(reservations, indent=2))
                return
            if not reservations:
                print("\n  \033[93mNo static DHCP reservations configured.\033[0m\n")
                return
            print("\n" + "=" * 55)
            print("  \033[1mSTATIC DHCP RESERVATIONS\033[0m")
            print("=" * 55)
            print(f"{'MAC ADDRESS':<20} {'RESERVED IP':<18} {'STATUS':<10}")
            print("-" * 55)
            for r in reservations:
                status = "\033[92mEnabled\033[0m" if r["enabled"] else "\033[93mDisabled\033[0m"
                print(f"{r['mac']:<20} {r['ip']:<18} {status:<10}")
            print("=" * 55 + "\n")
        elif sub == "add":
            mac = getattr(args, "mac", None)
            ip = getattr(args, "ip", None)
            if not mac or not ip:
                print("\nUsage: tplink-cli reservation add <mac_address> <ip_address>")
                print("Example: tplink-cli reservation add AA-BB-CC-DD-EE-FF 192.168.1.50\n")
                return
            client.add_dhcp_reservation(mac, ip)
            print(f"\033[92mReservation added: {mac} -> {ip}\033[0m")
        elif sub == "del":
            mac = getattr(args, "mac", None)
            if not mac:
                print("\nUsage: tplink-cli reservation del <mac_address>")
                print("Run 'tplink-cli reservation list' to view active reservations.\n")
                return
            client.delete_dhcp_reservation(mac)
            print(f"\033[92mReservation deleted for MAC {mac}\033[0m")


def cmd_data_limit(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_data_limit"):
            print("Data limits are only supported on cellular MR models.")
            return

        if getattr(args, "limit", None) is not None:
            payment_day = getattr(args, "day", 1) or 1
            client.set_data_limit(enabled=True, limit_mb=args.limit, payment_day=payment_day)
            print(f"\033[92mData limit set to {args.limit} MB (Billing reset day: {payment_day})\033[0m")
            return

        data = client.get_data_limit()
        if getattr(args, "json", False):
            print(json.dumps(data, indent=2))
            return

        print("\n" + "=" * 55)
        print("  \033[1mCELLULAR DATA LIMITS & USAGE\033[0m")
        print("=" * 55)
        print(f"Quota Enforcement   : {'\033[92mActive\033[0m' if data['limit_enabled'] else 'Disabled'}")
        print(f"Monthly Limit       : {data['limit_mb']} MB ({round(data['limit_mb'] / 1024, 2)} GB)")
        print(f"Billing Reset Day   : Day {data['billing_day']} of month")
        print(f"Warning Alert At    : {data['warning_percent']}%")
        print(f"Current Period Used : {round(data['current_period_bytes'] / (1024*1024), 2)} MB")
        print(f"Total Transferred   : {round(data['total_bytes'] / (1024*1024), 2)} MB")
        print(f"Current Throughput  : {data['rx_speed_kbps']} Kbps DL / {data['tx_speed_kbps']} Kbps UL")
        print("=" * 55 + "\n")


def cmd_wifi(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_wifi_status"):
            print("Wi-Fi control is only supported on MR cellular models.")
            return

        if getattr(args, "toggle", None):
            band = "2.4GHz" if "2" in args.band else "5GHz"
            enabled = args.toggle in ("on", "enable")
            client.set_wifi_radio(band=band, enabled=enabled, ssid=getattr(args, "ssid", None))
            print(f"\033[92mWi-Fi {band} radio set to {'ON' if enabled else 'OFF'}\033[0m")
            return

        networks = client.get_wifi_status()
        if getattr(args, "json", False):
            print(json.dumps(networks, indent=2))
            return

        print("\n" + "=" * 70)
        print("  \033[1mWIRELESS (WI-FI) NETWORKS\033[0m")
        print("=" * 70)
        print(f"{'BAND':<10} {'SSID':<24} {'STATE':<12} {'CHANNEL':<10} {'DEVICES':<8}")
        print("-" * 70)
        for net in networks:
            state_str = "\033[92mEnabled\033[0m" if net["enabled"] else "\033[91mDisabled\033[0m"
            devs = str(net.get("connected_clients", 0))
            print(f"{net['band']:<10} {net['ssid']:<24} {state_str:<21} {str(net['channel']):<10} {devs:<8}")
        print("=" * 70 + "\n")


def cmd_leds(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_led_status"):
            print("LED control is only supported on MR cellular models.")
            return

        if getattr(args, "night_mode", None):
            enable = args.night_mode in ("on", "enable")
            start = getattr(args, "start", "22:00") or "22:00"
            end = getattr(args, "end", "07:00") or "07:00"
            client.set_led_night_mode(enabled=enable, start_time=start, end_time=end)
            print(f"\033[92mNight mode {'enabled' if enable else 'disabled'} (LEDs OFF {start} - {end})\033[0m")
            return

        leds = client.get_led_status()
        if getattr(args, "json", False):
            print(json.dumps(leds, indent=2))
            return

        print("\n\033[1mRouter Front Panel LED Status:\033[0m")
        print(f"  LEDs Active        : {'\033[92mYes\033[0m' if leds['leds_on'] else '\033[93mOff\033[0m'}")
        print(f"  Night Mode Schedule: {'\033[92mEnabled\033[0m' if leds['night_mode_enabled'] else 'Disabled'}")
        if leds["night_mode_enabled"]:
            print(f"  Off Schedule Hours : {leds['night_mode_start']} -> {leds['night_mode_end']}")


def cmd_diag(args: argparse.Namespace):
    client = get_client(args)
    print("Initiating router WAN & NCSI diagnostic self-test...")
    with SafeSession(client):
        if not hasattr(client, "run_wan_diagnostic"):
            print("Router diagnostic is only supported on MR cellular models.")
            return
        res = client.run_wan_diagnostic()

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
        return

    status_color = "\033[92m" if res["status"] == "Passed" else "\033[91m"
    print(f"\nDiagnostic Result: {status_color}\033[1m{res['status']}\033[0m (Code {res['result_code']})")
    print(f"Message          : {res['message']}\n")


def cmd_band(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "set_lte_band"):
            print("Band selection is only supported on MR cellular models.")
            return

        target_band = getattr(args, "band", None)
        if not target_band:
            if hasattr(client, "get_band_config"):
                b_cfg = client.get_band_config()
                active_mode = b_cfg.get("configured_str", "Auto")
                connected_band = b_cfg.get("connected_band", "Auto / LTE")
                earfcn = b_cfg.get("earfcn")
                pci = b_cfg.get("pci")
                supported_bands = b_cfg.get("supported_bands", [1, 3, 7, 8, 20, 38, 40, 41])
            else:
                lte = client.get_lte_status()
                active_mode = "Auto"
                connected_band = lte.band
                earfcn = lte.earfcn
                pci = lte.pci
                supported_bands = [1, 3, 7, 8, 20, 38, 40, 41]

            if getattr(args, "json", False):
                print(json.dumps({
                    "mode": active_mode,
                    "connected_band": connected_band,
                    "earfcn": earfcn,
                    "pci": pci,
                    "supported_bands": supported_bands
                }, indent=2))
                return

            print("\n" + "=" * 62)
            print("  \033[1mACTIVE LTE BAND CONFIGURATION\033[0m")
            print("=" * 62)
            print(f"Configured Band Mode : \033[1m{active_mode}\033[0m")
            print(f"Connected RF Link    : \033[1m{connected_band}\033[0m")
            if earfcn:
                print(f"Channel (EARFCN)     : {earfcn} (PCI: {pci or '0'})")
            print("-" * 62)
            print("Hardware Supported Bands (Sri Lanka Context):")
            band_descriptions = {
                1: "2100 MHz (FDD - Dialog / Mobitel 4G)",
                3: "1800 MHz (FDD - High-speed Hutch / Dialog primary)",
                7: "2600 MHz (FDD - High-capacity metro)",
                8: "900 MHz  (FDD - Best rain penetration & indoor reach)",
                20: "800 MHz  (FDD - Sub-1GHz rural)",
                38: "2600 MHz (TDD)",
                40: "2300 MHz (TDD - Dialog high-capacity)",
                41: "2500 MHz (TDD)"
            }
            for b in supported_bands:
                desc = band_descriptions.get(b, "LTE Carrier")
                print(f"  Band {b:<2} : {desc}")
            print("  auto    : Automatic network roaming selection")
            print("-" * 62)
            print("To lock modem onto a band:")
            print("  tplink-cli band 3")
            print("  tplink-cli band 8")
            print("  tplink-cli band auto")
            print("=" * 62 + "\n")
            return

        print(f"Locking hardware modem to band '{target_band}'...")
        client.set_lte_band(target_band)
    print(f"\033[92m✓ LTE band successfully configured to '{target_band}'.\033[0m")
    print("\033[90mCellular modem is retuning RF hardware. Signal LEDs will cycle.\033[0m")


def cmd_logs(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_system_logs"):
            print("System logs are only supported on MR cellular models.")
            return

        if getattr(args, "clear", False):
            client.clear_system_logs()
            if getattr(args, "json", False):
                print(json.dumps({"cleared": True}))
            else:
                print("\033[92m✓ System event logs successfully cleared.\033[0m")
            return

        limit = getattr(args, "lines", 30) or 30
        module = getattr(args, "module", None)
        min_level = getattr(args, "level", None)

        logs = client.get_system_logs(limit=limit, module=module, min_level=min_level)

        if getattr(args, "json", False):
            print(json.dumps([{
                "timestamp": l.timestamp,
                "level": l.level_name,
                "module": l.module,
                "message": l.message
            } for l in logs], indent=2))
            return

        print("\n" + "=" * 78)
        print("  \033[1mROUTER SYSTEM & CELLULAR EVENT LOGS\033[0m")
        print("=" * 78)
        if not logs:
            print("  (No log entries found matching criteria)")
        else:
            lvl_colors = {
                "EMERG": "\033[91m", "ALERT": "\033[91m", "CRIT": "\033[91m", "ERROR": "\033[91m",
                "WARN": "\033[93m", "NOTICE": "\033[96m", "INFO": "\033[37m", "DEBUG": "\033[90m"
            }
            for l in logs:
                c = lvl_colors.get(l.level_name, "")
                print(f"[{l.timestamp}] {c}[{l.level_name:<5}]\033[0m \033[1m{l.module:<8}\033[0m : {l.message}")
        print("-" * 78)
        print(f"Showing {len(logs)} entries. Filter with: tplink-cli logs --lines 50 --module 4G --level ERROR")
        print("=" * 78 + "\n")


def cmd_guest_wifi(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_guest_wifi"):
            print("Guest Wi-Fi is only supported on MR cellular models.")
            return

        toggle = getattr(args, "toggle", None)
        band = getattr(args, "band", "both")
        ssid = getattr(args, "ssid", None)
        password = getattr(args, "guest_password", None) or getattr(args, "key", None)
        allow_lan = getattr(args, "allow_lan", None)

        if toggle or ssid or password or allow_lan is not None:
            is_en = toggle in ("on", "enable") if toggle else True
            client.set_guest_wifi(band=band, enabled=is_en, ssid=ssid, password=password, allow_lan=allow_lan)
            action_desc = f"{'enabled' if is_en else 'disabled'}"
            if ssid:
                action_desc += f", SSID set to '{ssid}'"
            print(f"\033[92m✓ Guest Wi-Fi ({band}) successfully {action_desc}.\033[0m")
            return

        gw = client.get_guest_wifi()
        if getattr(args, "json", False):
            print(json.dumps({
                "allow_lan_access": gw.allow_lan_access,
                "networks": [{
                    "band": n.band,
                    "enabled": n.enabled,
                    "ssid": n.ssid,
                    "security": n.security,
                    "isolate_clients": n.isolate_clients
                } for n in gw.networks]
            }, indent=2))
            return

        print("\n" + "=" * 60)
        print("  \033[1mDUAL-BAND GUEST WI-FI NETWORKS\033[0m")
        print("=" * 60)
        print(f"Local Network Access : \033[1m{'Allowed' if gw.allow_lan_access else 'Isolated (Secure)'}\033[0m")
        print("-" * 60)
        for net in gw.networks:
            en_str = "\033[92mENABLED\033[0m" if net.enabled else "\033[90mDISABLED\033[0m"
            print(f"\033[1m{net.band:<7}\033[0m : {en_str}")
            print(f"  SSID     : \033[1m{net.ssid}\033[0m")
            print(f"  Security : {net.security}")
            print("-" * 60)
        print("To configure Guest Wi-Fi:")
        print("  tplink-cli guest-wifi --toggle on --ssid GuestNetwork --password GuestPass123")
        print("  tplink-cli guest-wifi --toggle off")
        print("=" * 60 + "\n")


def cmd_port_forward(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_port_forwarding"):
            print("Port forwarding is only supported on MR cellular models.")
            return

        action = getattr(args, "subcommand", None) or "list"
        if action == "add":
            name = getattr(args, "name", None)
            ext_port = getattr(args, "ext_port", None)
            int_ip = getattr(args, "int_ip", None)
            if not name or not ext_port or not int_ip:
                print("\nUsage: tplink-cli port-forward add <name> <ext_port> <int_ip> [int_port] [--proto TCP|UDP|ALL]")
                print("Example: tplink-cli port-forward add web 8080 192.168.1.150 80 --proto TCP\n")
                return
            int_port = getattr(args, "int_port", None) or ext_port
            proto = getattr(args, "proto", "ALL")
            client.add_port_forwarding(name=name, external_port=ext_port, internal_ip=int_ip, internal_port=int_port, protocol=proto)
            print(f"\033[92m✓ Port forwarding rule '{name}' added: Port {ext_port} -> {int_ip}:{int_port} ({proto})\033[0m")
            return
        elif action == "del":
            stack = getattr(args, "stack", None)
            if not stack:
                print("\nUsage: tplink-cli port-forward del <rule_stack>")
                print("Run 'tplink-cli port-forward list' to view active rule stacks.\n")
                return
            client.del_port_forwarding(rule_stack=stack)
            print(f"\033[92m✓ Port forwarding rule at stack '{stack}' deleted.\033[0m")
            return

        rules = client.get_port_forwarding()
        if getattr(args, "json", False):
            print(json.dumps([{
                "index": r.index,
                "name": r.name,
                "external_port": r.external_port,
                "internal_ip": r.internal_ip,
                "internal_port": r.internal_port,
                "protocol": r.protocol,
                "enabled": r.enabled
            } for r in rules], indent=2))
            return

        print("\n" + "=" * 65)
        print("  \033[1mNAT VIRTUAL SERVER PORT FORWARDING RULES\033[0m")
        print("=" * 65)
        if not rules:
            print("  (No active port forwarding rules)")
        else:
            print(f"{'#':<3} {'Service Name':<18} {'Ext Port':<10} {'Internal Target':<22} {'Proto':<6} {'State'}")
            print("-" * 65)
            for r in rules:
                st = "\033[92mON\033[0m" if r.enabled else "\033[90mOFF\033[0m"
                target = f"{r.internal_ip}:{r.internal_port}"
                print(f"{r.index:<3} {r.name:<18} {r.external_port:<10} {target:<22} {r.protocol:<6} {st}")
        print("-" * 65)
        print("To add a port forward rule:")
        print("  tplink-cli port-forward add web 8080 192.168.1.150 80 --proto TCP")
        print("=" * 65 + "\n")


def cmd_dmz(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_dmz"):
            print("DMZ Host is only supported on MR cellular models.")
            return

        state = getattr(args, "state", None)
        ip = getattr(args, "ip", None)

        if state or ip:
            is_en = state in ("on", "enable") if state else bool(ip)
            target_ip = ip or ""
            client.set_dmz(enabled=is_en, ip_address=target_ip)
            print(f"\033[92m✓ DMZ Host {'enabled -> ' + target_ip if is_en else 'disabled'}.\033[0m")
            return

        dmz = client.get_dmz()
        if getattr(args, "json", False):
            print(json.dumps({"enabled": dmz.enabled, "ip_address": dmz.ip_address}, indent=2))
            return

        print("\n" + "=" * 50)
        print("  \033[1mDMZ HOST CONFIGURATION\033[0m")
        print("=" * 50)
        st = "\033[92mENABLED\033[0m" if dmz.enabled else "\033[90mDISABLED\033[0m"
        print(f"Status        : {st}")
        if dmz.enabled:
            print(f"DMZ Host IP   : \033[1m{dmz.ip_address}\033[0m")
        print("-" * 50)
        print("To configure DMZ:")
        print("  tplink-cli dmz on 192.168.1.100")
        print("  tplink-cli dmz off")
        print("=" * 50 + "\n")


def cmd_upnp(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_upnp"):
            print("UPnP is only supported on MR cellular models.")
            return

        toggle = getattr(args, "toggle", None)
        if toggle:
            is_en = toggle in ("on", "enable")
            client.set_upnp(enabled=is_en)
            print(f"\033[92m✓ UPnP successfully {'enabled' if is_en else 'disabled'}.\033[0m")
            return

        upnp = client.get_upnp()
        if getattr(args, "json", False):
            print(json.dumps({
                "enabled": upnp.enabled,
                "mappings": [{
                    "protocol": m.protocol,
                    "external_port": m.external_port,
                    "internal_ip": m.internal_ip,
                    "internal_port": m.internal_port,
                    "description": m.description,
                    "enabled": m.enabled
                } for m in upnp.mappings]
            }, indent=2))
            return

        print("\n" + "=" * 65)
        print("  \033[1mUNIVERSAL PLUG AND PLAY (UPnP)\033[0m")
        print("=" * 65)
        st = "\033[92mENABLED\033[0m" if upnp.enabled else "\033[90mDISABLED\033[0m"
        print(f"UPnP Status           : {st}")
        print(f"Dynamic Port Mappings : {len(upnp.mappings)}")
        print("-" * 65)
        if upnp.mappings:
            print(f"{'Description':<20} {'Proto':<6} {'Ext Port':<10} {'Internal Target'}")
            print("-" * 65)
            for m in upnp.mappings:
                print(f"{m.description:<20} {m.protocol:<6} {m.external_port:<10} {m.internal_ip}:{m.internal_port}")
        else:
            print("  (No dynamic UPnP port mappings currently registered)")
        print("-" * 65)
        print("To toggle UPnP: tplink-cli upnp on | tplink-cli upnp off")
        print("=" * 65 + "\n")


def cmd_reboot_schedule(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_reboot_schedule"):
            print("Reboot schedule is only supported on MR cellular models.")
            return

        toggle = getattr(args, "toggle", None)
        r_time = getattr(args, "time", None)
        mode = getattr(args, "mode", "daily")
        day = getattr(args, "day", 1)

        if toggle or r_time:
            is_en = toggle in ("on", "enable") if toggle else True
            hours, minutes = 3, 0
            if r_time:
                try:
                    parts = r_time.split(":")
                    hours = int(parts[0])
                    minutes = int(parts[1]) if len(parts) > 1 else 0
                except ValueError:
                    pass
            client.set_reboot_schedule(enabled=is_en, hours=hours, minutes=minutes, mode=mode, day_of_week=day)
            print(f"\033[92m✓ Automated reboot schedule {'enabled for ' + f'{hours:02d}:{minutes:02d} ({mode})' if is_en else 'disabled'}.\033[0m")
            return

        rs = client.get_reboot_schedule()
        if getattr(args, "json", False):
            print(json.dumps({
                "enabled": rs.enabled,
                "mode": rs.mode,
                "time": f"{rs.hours:02d}:{rs.minutes:02d}",
                "day_name": rs.day_name
            }, indent=2))
            return

        print("\n" + "=" * 55)
        print("  \033[1mAUTOMATED REBOOT SCHEDULE\033[0m")
        print("=" * 55)
        st = "\033[92mENABLED\033[0m" if rs.enabled else "\033[90mDISABLED\033[0m"
        print(f"Status         : {st}")
        print(f"Scheduled Time : \033[1m{rs.hours:02d}:{rs.minutes:02d}\033[0m")
        print(f"Frequency      : Every {rs.mode.capitalize()}" + (f" ({rs.day_name})" if rs.mode == "weekly" else ""))
        print("-" * 55)
        print("To configure auto-reboot:")
        print("  tplink-cli reboot-schedule on --time 03:30 --mode daily")
        print("  tplink-cli reboot-schedule off")
        print("=" * 55 + "\n")


def cmd_time(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_time_config"):
            print("System time is only supported on MR cellular models.")
            return

        if getattr(args, "sync", False):
            client.sync_time()
            print("\033[92m✓ Router NTP synchronization requested.\033[0m")
            return

        tc = client.get_time_config()
        if getattr(args, "json", False):
            print(json.dumps({
                "current_time": tc.current_time,
                "timezone": tc.timezone,
                "daylight_savings": tc.daylight_savings,
                "ntp_server1": tc.ntp_server1,
                "ntp_server2": tc.ntp_server2
            }, indent=2))
            return

        print("\n" + "=" * 50)
        print("  \033[1mROUTER SYSTEM TIME & NTP\033[0m")
        print("=" * 50)
        print(f"Current Local Time : \033[1m{tc.current_time}\033[0m")
        print(f"Time Zone          : {tc.timezone}")
        print(f"Daylight Savings   : {'Active' if tc.daylight_savings else 'Standard'}")
        if tc.ntp_server1:
            print(f"NTP Server 1       : {tc.ntp_server1}")
        if tc.ntp_server2:
            print(f"NTP Server 2       : {tc.ntp_server2}")
        print("-" * 50)
        print("To synchronize time via NTP: tplink-cli time --sync")
        print("=" * 50 + "\n")


def cmd_op_mode(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_operation_mode"):
            print("Operation mode is only supported on MR cellular models.")
            return

        om = client.get_operation_mode()
        if getattr(args, "json", False):
            print(json.dumps({
                "mode": om.mode,
                "raw_mode": om.raw_mode,
                "lte_backup": om.lte_backup_enabled,
                "cellular_data_switch": om.cellular_data_switch
            }, indent=2))
            return

        print("\n" + "=" * 55)
        print("  \033[1mROUTER OPERATION MODE\033[0m")
        print("=" * 55)
        print(f"Active Mode     : \033[1m{om.mode}\033[0m")
        print(f"LTE Failover    : {'Enabled (4G WAN fallback active)' if om.lte_backup_enabled else 'Disabled'}")
        print(f"Cellular Switch : {'Online / Enabled' if om.cellular_data_switch else 'Disabled'}")
        print("=" * 55 + "\n")


def cmd_ddns(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_ddns_status"):
            print("DDNS is only supported on MR cellular models.")
            return

        providers = client.get_ddns_status()
        if getattr(args, "json", False):
            print(json.dumps([{
                "provider": p.provider,
                "enabled": p.enabled,
                "domain": p.domain,
                "username": p.username,
                "status": p.status
            } for p in providers], indent=2))
            return

        print("\n" + "=" * 60)
        print("  \033[1mDYNAMIC DNS (DDNS) SERVICES\033[0m")
        print("=" * 60)
        for p in providers:
            st = "\033[92mENABLED\033[0m" if p.enabled else "\033[90mDISABLED\033[0m"
            print(f"\033[1m{p.provider:<20}\033[0m : {st}")
            if p.domain:
                print(f"  Domain : \033[1m{p.domain}\033[0m (State: {p.status})")
            else:
                print(f"  Status : {p.status}")
            print("-" * 60)
        print("=" * 60 + "\n")


def cmd_fw_check(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "check_firmware_update"):
            print("Firmware check is only supported on MR cellular models.")
            return

        fw = client.check_firmware_update()
        if getattr(args, "json", False):
            print(json.dumps({
                "current_version": fw.current_version,
                "latest_version": fw.latest_version,
                "has_update": fw.has_update,
                "release_date": fw.release_date,
                "release_log": fw.release_log
            }, indent=2))
            return

        print("\n" + "=" * 60)
        print("  \033[1mTP-LINK OFFICIAL FIRMWARE UPDATE STATUS\033[0m")
        print("=" * 60)
        print(f"Installed Version : \033[1m{fw.current_version}\033[0m")
        if fw.has_update:
            print(f"Available Update  : \033[92m\033[1m{fw.latest_version}\033[0m (Released: {fw.release_date})")
            if fw.release_log:
                print(f"Changelog         :\n{fw.release_log}")
        else:
            print("Update Status     : \033[92m✓ Router is running the latest firmware release.\033[0m")
        print("=" * 60 + "\n")


def cmd_calibrate(args: argparse.Namespace):
    from tplink_router.calibration.engine import RouterCalibrator
    from tplink_router.calibration.dashboard import start_dashboard_server

    raw_cookie = getattr(args, "cookie", None)
    if raw_cookie == "PROMPT":
        print("Paste your browser session cookie or Netscape cookie block below:")
        try:
            raw_cookie = input("Cookie: ").strip()
        except EOFError:
            raw_cookie = None

    cfg = ConfigManager().load(
        cli_host=getattr(args, "host", None),
        cli_username=getattr(args, "username", None),
        cli_password=getattr(args, "password", None),
        cli_cookie=raw_cookie,
    )

    host = cfg.get("host") or getattr(args, "host", None) or "http://192.168.1.1"
    username = getattr(args, "username", None) or cfg.get("username", "admin")
    password = cfg.get("password") or getattr(args, "password", None)
    session_cookie = cfg.get("session_cookie")
    expected_ssid = cfg.get("expected_ssid")
    force = getattr(args, "force", False)

    # Run Network Guard safety check
    is_safe, msg = NetworkGuard.check_safety(target_host=host, expected_ssid=expected_ssid, force=force)
    if not is_safe:
        if getattr(args, "json", False):
            print(json.dumps({
                "error": True,
                "code": "NETWORK_GUARD_BLOCKED",
                "message": msg
            }, indent=2), file=sys.stderr)
        else:
            print(f"\033[91m[Network Guard Alert] {msg}\033[0m")
        sys.exit(2)

    target_bands = [b.strip() for b in args.bands.split(",") if b.strip()]

    calibrator = RouterCalibrator(
        host=host,
        password=password,
        session_cookie=session_cookie,
        username=username,
        bands=target_bands,
        watchdog_timeout=args.timeout,
        dry_run=args.dry_run,
    )

    if args.web:
        print(f"\n🌐 Live Calibration Dashboard running at: \033[96mhttp://localhost:{args.port}/\033[0m")
        server = start_dashboard_server(calibrator=calibrator, port=args.port, blocking=False)
        print("👉 Calibrator is ready! Open the Web UI and click [▶ Start Calibration] or let the sweep begin.")
        try:
            calibrator.run_sweep()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down dashboard...")
            server.shutdown()
    else:
        calibrator.run_sweep()


def build_parser() -> argparse.ArgumentParser:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output machine-readable JSON")
    common_parser.add_argument("--host", nargs="?", const="SHOW", default=argparse.SUPPRESS, help="Router IP/Host (default: http://192.168.1.1)")
    common_parser.add_argument("--username", nargs="?", const="SHOW", default=argparse.SUPPRESS, help="Admin username (default: admin)")
    common_parser.add_argument("--password", nargs="?", const="PROMPT", default=argparse.SUPPRESS, help="Admin password (overrides stored config)")
    common_parser.add_argument("--cookie", "--session-id", dest="cookie", nargs="?", const="PROMPT", default=argparse.SUPPRESS, help="Browser session cookie (JSESSIONID or Netscape format)")
    common_parser.add_argument("--force", action="store_true", default=argparse.SUPPRESS, help="Bypass Network Guard checks")

    parser = argparse.ArgumentParser(
        prog="tplink-cli",
        description="Universal TP-Link Agentic Router Suite (Cross-Platform)",
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    p_status = subparsers.add_parser("status", parents=[common_parser], help="Show full router & cellular telemetry")
    p_status.set_defaults(func=cmd_status)

    # signal
    p_sig = subparsers.add_parser("signal", parents=[common_parser], help="Show RF signal metrics (RSRP, RSRQ, SNR)")
    p_sig.set_defaults(func=cmd_signal)

    # cell-lock
    p_lock = subparsers.add_parser("cell-lock", parents=[common_parser], help="View or configure LTE Cell Lock")
    p_lock.add_argument("--enable", action="store_true", help="Enable Cell Lock")
    p_lock.add_argument("--disable", action="store_true", help="Disable Cell Lock")
    p_lock.add_argument("--earfcn", help="Target EARFCN channel (e.g. 1550)")
    p_lock.add_argument("--pci", help="Target Physical Cell Identity (e.g. 58)")
    p_lock.set_defaults(func=cmd_cell_lock)

    # dns
    p_dns = subparsers.add_parser("dns", parents=[common_parser], help="Manage router DNS settings")
    dns_sub = p_dns.add_subparsers(dest="action")
    dns_set = dns_sub.add_parser("set", parents=[common_parser], help="Set DNS servers")
    dns_set.add_argument("primary", nargs="?", help="Primary DNS (e.g. 8.8.8.8)")
    dns_set.add_argument("secondary", nargs="?", default="1.1.1.1", help="Secondary DNS")
    dns_show = dns_sub.add_parser("show", parents=[common_parser], help="Show current DNS")
    p_dns.set_defaults(func=cmd_dns)

    # ipv6
    p_ipv6 = subparsers.add_parser("ipv6", parents=[common_parser], help="Toggle IPv6 stack (on/off)")
    p_ipv6.add_argument("state", nargs="?", choices=["on", "off", "enable", "disable"], help="State to set (if omitted, shows current status)")
    p_ipv6.set_defaults(func=cmd_ipv6)

    # ussd
    p_ussd = subparsers.add_parser("ussd", parents=[common_parser], help="Execute USSD query (e.g. *344# or *123#)")
    p_ussd.add_argument("code", nargs="?", help="USSD string (e.g. *344# or *123#)")
    p_ussd.set_defaults(func=cmd_ussd)

    # sms
    p_sms = subparsers.add_parser("sms", parents=[common_parser], help="Read or send SMS")
    p_sms.add_argument("--limit", type=int, default=10, help="Max messages to fetch")
    p_sms.add_argument("--folder", choices=["inbox", "sent"], default="inbox", help="SMS folder")
    sms_sub = p_sms.add_subparsers(dest="subcommand")
    sms_list = sms_sub.add_parser("list", parents=[common_parser], help="List SMS messages")
    sms_list.add_argument("--limit", type=int, default=10, help="Max messages to fetch")
    sms_list.add_argument("--folder", choices=["inbox", "sent"], default="inbox", help="SMS folder")
    sms_send = sms_sub.add_parser("send", parents=[common_parser], help="Send SMS")
    sms_send.add_argument("recipient", nargs="?", help="Phone number")
    sms_send.add_argument("message", nargs="?", help="Message text")
    p_sms.set_defaults(func=cmd_sms)

    # reboot
    p_reboot = subparsers.add_parser("reboot", parents=[common_parser], help="Reboot the router")
    p_reboot.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p_reboot.set_defaults(func=cmd_reboot)

    # profile check
    p_prof = subparsers.add_parser("profile", parents=[common_parser], help="Check active network profile and gateway safety")
    prof_sub = p_prof.add_subparsers(dest="subcommand")
    prof_check = prof_sub.add_parser("check", parents=[common_parser], help="Check current Wi-Fi SSID and gateway")
    prof_check.set_defaults(func=cmd_profile_check)
    p_prof.set_defaults(func=cmd_profile_check)

    # config
    p_cfg = subparsers.add_parser("config", parents=[common_parser], help="Manage stored credentials")
    cfg_sub = p_cfg.add_subparsers(dest="subcommand")
    cfg_set = cfg_sub.add_parser("set-password", parents=[common_parser], help="Save router admin password securely")
    cfg_set.add_argument("password", nargs="?", help="Admin password (prompts if omitted)")
    cfg_set.add_argument("--expected-ssid", help="Expected Wi-Fi SSID for safety guard")
    cfg_cookie = cfg_sub.add_parser("set-cookie", parents=[common_parser], help="Save browser session cookie (Netscape or JSESSIONID format)")
    cfg_cookie.add_argument("cookie", nargs="?", help="Cookie string, Netscape block, or JSESSIONID")
    cfg_cookie.add_argument("--file", "-f", help="Path to Netscape cookies.txt file")
    cfg_clear = cfg_sub.add_parser("clear-cookie", parents=[common_parser], help="Clear saved session cookie")
    cfg_show = cfg_sub.add_parser("show", parents=[common_parser], help="Show current configuration")
    p_cfg.set_defaults(func=cmd_config)

    # cookie (convenient top-level alias)
    p_cookie = subparsers.add_parser("cookie", parents=[common_parser], help="View or save browser session cookie")
    p_cookie.add_argument("cookie_val", nargs="?", help="Cookie string, Netscape block, or JSESSIONID")
    p_cookie.set_defaults(func=cmd_cookie)

    # wifi-guard
    p_wguard = subparsers.add_parser("wifi-guard", parents=[common_parser], help="Verify and optimize Wi-Fi link stability (no Ethernet needed)")
    p_wguard.add_argument("--optimize", "--fix", dest="optimize", action="store_true", help="Auto-optimize Wi-Fi stability and elevate NetworkManager priority")
    p_wguard.set_defaults(func=cmd_wifi_guard)

    # clients
    p_clients = subparsers.add_parser("clients", parents=[common_parser], help="List connected LAN devices (IP, MAC, Hostname)")
    p_clients.set_defaults(func=cmd_clients)

    # reservation
    p_resv = subparsers.add_parser("reservation", parents=[common_parser], help="Manage DHCP static IP reservations")
    resv_sub = p_resv.add_subparsers(dest="subcommand")
    resv_list = resv_sub.add_parser("list", parents=[common_parser], help="List all reservations")
    resv_list.set_defaults(func=cmd_reservation)
    resv_add = resv_sub.add_parser("add", parents=[common_parser], help="Add DHCP static reservation")
    resv_add.add_argument("mac", nargs="?", help="Device MAC address")
    resv_add.add_argument("ip", nargs="?", help="Reserved IP address")
    resv_del = resv_sub.add_parser("del", parents=[common_parser], help="Delete DHCP reservation")
    resv_del.add_argument("mac", nargs="?", help="Device MAC address to remove")
    p_resv.set_defaults(func=cmd_reservation)

    # data-limit
    p_dlim = subparsers.add_parser("data-limit", parents=[common_parser], help="View or set monthly cellular data cap")
    p_dlim.add_argument("--limit", type=int, help="Monthly quota in Megabytes (e.g. 50000 for 50GB)")
    p_dlim.add_argument("--day", type=int, default=1, help="Billing cycle reset day of month (1-31)")
    p_dlim.set_defaults(func=cmd_data_limit)

    # wifi
    p_wifi = subparsers.add_parser("wifi", parents=[common_parser], help="View or configure Wi-Fi radios (2.4GHz / 5GHz)")
    p_wifi.add_argument("--band", choices=["2.4GHz", "5GHz", "2.4", "5"], default="2.4GHz", help="Frequency band")
    p_wifi.add_argument("--toggle", choices=["on", "off", "enable", "disable"], help="Turn radio on/off")
    p_wifi.add_argument("--ssid", help="Set new SSID name")
    p_wifi.set_defaults(func=cmd_wifi)

    # leds
    p_leds = subparsers.add_parser("leds", parents=[common_parser], help="Control router LEDs and Night Mode schedule")
    p_leds.add_argument("--night-mode", choices=["on", "off", "enable", "disable"], help="Toggle night mode schedule")
    p_leds.add_argument("--start", default="22:00", help="Night mode start time (HH:MM)")
    p_leds.add_argument("--end", default="07:00", help="Night mode end time (HH:MM)")
    p_leds.set_defaults(func=cmd_leds)

    # diag
    p_diag = subparsers.add_parser("diag", parents=[common_parser], help="Run router WAN and internet diagnostic test")
    p_diag.set_defaults(func=cmd_diag)

    # band
    p_band = subparsers.add_parser("band", parents=[common_parser], help="View or lock LTE Band (e.g. 3, 8, 40, auto)")
    p_band.add_argument("band", nargs="?", help="LTE Band (e.g. 3, 8, 40, or auto). If omitted, displays active band.")
    p_band.set_defaults(func=cmd_band)

    # calibrate
    p_cal = subparsers.add_parser("calibrate", parents=[common_parser], help="Autonomous RF band calibration & Live Web UI")
    p_cal.add_argument("--web", action="store_true", default=True, help="Launch real-time Web UI dashboard")
    p_cal.add_argument("--no-web", dest="web", action="store_false", help="Run in headless terminal mode")
    p_cal.add_argument("--port", type=int, default=8765, help="Web dashboard port (default: 8765)")
    p_cal.add_argument("--bands", default="8,3,1,40,auto", help="Candidate bands (default: 8,3,1,40,auto)")
    p_cal.add_argument("--timeout", type=int, default=45, help="45s watchdog timeout")
    p_cal.add_argument("--dry-run", action="store_true", help="Simulate without radio detachment")
    p_cal.set_defaults(func=cmd_calibrate)

    # logs
    p_logs = subparsers.add_parser("logs", parents=[common_parser], help="Read or clear system & cellular event logs")
    p_logs.add_argument("--lines", "-n", type=int, default=30, help="Number of log entries to display (default: 30)")
    p_logs.add_argument("--module", "-m", help="Filter logs by module (e.g. 4G, DHCP, System)")
    p_logs.add_argument("--level", "-l", help="Minimum log severity (EMERG, ALERT, CRIT, ERROR, WARN, NOTICE, INFO, DEBUG)")
    p_logs.add_argument("--clear", action="store_true", help="Clear all stored event logs")
    p_logs.set_defaults(func=cmd_logs)

    # guest-wifi
    p_gw = subparsers.add_parser("guest-wifi", parents=[common_parser], help="View or configure dual-band Guest Wi-Fi")
    p_gw.add_argument("--toggle", choices=["on", "off", "enable", "disable"], help="Turn Guest Wi-Fi on/off")
    p_gw.add_argument("--band", choices=["2.4GHz", "5GHz", "both", "2.4", "5"], default="both", help="Target band (default: both)")
    p_gw.add_argument("--ssid", help="Set Guest Wi-Fi network name (SSID)")
    p_gw.add_argument("--key", "--guest-password", dest="guest_password", help="Set Guest Wi-Fi WPA2 password (min 8 chars, or '' for Open)")
    p_gw.add_argument("--allow-lan", action="store_true", default=None, help="Allow guests to access local LAN devices")
    p_gw.add_argument("--isolate-lan", dest="allow_lan", action="store_false", help="Block guests from accessing local LAN devices")
    p_gw.set_defaults(func=cmd_guest_wifi)

    # port-forward
    p_pf = subparsers.add_parser("port-forward", parents=[common_parser], help="Manage NAT virtual server port forwarding rules")
    pf_sub = p_pf.add_subparsers(dest="subcommand")
    pf_list = pf_sub.add_parser("list", parents=[common_parser], help="List all port forwarding rules")
    pf_list.set_defaults(func=cmd_port_forward)
    pf_add = pf_sub.add_parser("add", parents=[common_parser], help="Add a new port forwarding rule")
    pf_add.add_argument("name", nargs="?", help="Service or application name (e.g. web, ssh)")
    pf_add.add_argument("ext_port", nargs="?", help="External incoming WAN port (e.g. 8080)")
    pf_add.add_argument("int_ip", nargs="?", help="Internal target device IP (e.g. 192.168.1.150)")
    pf_add.add_argument("int_port", nargs="?", help="Internal destination port (defaults to ext_port)")
    pf_add.add_argument("--proto", choices=["TCP", "UDP", "ALL"], default="ALL", help="Transport protocol (default: ALL)")
    pf_add.set_defaults(func=cmd_port_forward)
    pf_del = pf_sub.add_parser("del", parents=[common_parser], help="Delete port forwarding rule")
    pf_del.add_argument("stack", nargs="?", help="Rule stack ID to remove (e.g. 2,1,1,1,0,0)")
    pf_del.set_defaults(func=cmd_port_forward)
    p_pf.set_defaults(func=cmd_port_forward)

    # dmz
    p_dmz = subparsers.add_parser("dmz", parents=[common_parser], help="View or configure DMZ host forwarding")
    p_dmz.add_argument("state", nargs="?", choices=["on", "off", "enable", "disable"], help="Turn DMZ on/off")
    p_dmz.add_argument("ip", nargs="?", help="Internal DMZ host IP address (e.g. 192.168.1.100)")
    p_dmz.set_defaults(func=cmd_dmz)

    # upnp
    p_upnp = subparsers.add_parser("upnp", parents=[common_parser], help="Manage Universal Plug and Play (UPnP)")
    p_upnp.add_argument("toggle", nargs="?", choices=["on", "off", "enable", "disable"], help="Turn UPnP on/off")
    p_upnp.set_defaults(func=cmd_upnp)

    # reboot-schedule
    p_rs = subparsers.add_parser("reboot-schedule", parents=[common_parser], help="Manage automated periodic reboot schedule")
    p_rs.add_argument("toggle", nargs="?", choices=["on", "off", "enable", "disable"], help="Turn auto-reboot on/off")
    p_rs.add_argument("--time", help="Reboot time in 24h format (e.g. 03:00)")
    p_rs.add_argument("--mode", choices=["daily", "weekly"], default="daily", help="Repeat interval")
    p_rs.add_argument("--day", type=int, default=1, help="Day of week (1=Mon, 7=Sun) for weekly mode")
    p_rs.set_defaults(func=cmd_reboot_schedule)

    # time
    p_time = subparsers.add_parser("time", parents=[common_parser], help="View router system clock or trigger NTP sync")
    p_time.add_argument("--sync", action="store_true", help="Trigger NTP network time synchronization")
    p_time.set_defaults(func=cmd_time)

    # op-mode
    p_om = subparsers.add_parser("op-mode", parents=[common_parser], help="View router operation mode (3G/4G vs Wireless)")
    p_om.set_defaults(func=cmd_op_mode)

    # ddns
    p_ddns = subparsers.add_parser("ddns", parents=[common_parser], help="View Dynamic DNS (DDNS) providers and status")
    p_ddns.set_defaults(func=cmd_ddns)

    # fw-check
    p_fw = subparsers.add_parser("fw-check", parents=[common_parser], help="Check for official TP-Link online firmware updates")
    p_fw.set_defaults(func=cmd_fw_check)

    # repl
    p_repl = subparsers.add_parser("repl", parents=[common_parser], help="Launch interactive REPL console")
    p_repl.set_defaults(func=cmd_repl)

    return parser


def main(args=None):
    parser = build_parser()
    parsed_args = parser.parse_args(args)
    for _k, _v in [("json", False), ("host", None), ("username", None), ("password", None), ("cookie", None), ("force", False)]:
        if not hasattr(parsed_args, _k):
            setattr(parsed_args, _k, _v)

    # Handle --password PROMPT
    if parsed_args.password == "PROMPT":
        import getpass
        try:
            parsed_args.password = getpass.getpass("Enter router admin password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(130)

    # If no subcommand given, check for top-level options passed without command
    if not hasattr(parsed_args, "func"):
        cfg_mgr = ConfigManager()
        cfg = cfg_mgr.load()

        if parsed_args.host == "SHOW":
            if parsed_args.json:
                print(json.dumps({"target_host": cfg.get("host", "http://192.168.1.1")}))
            else:
                print("\n" + "=" * 55)
                print("  \033[1mTARGET ROUTER HOST\033[0m")
                print("=" * 55)
                print(f"Current Target Host : \033[1m{cfg.get('host', 'http://192.168.1.1')}\033[0m")
                print("-" * 55)
                print("To configure default host:")
                print("  tplink-cli config set-host http://192.168.0.1")
                print("Or pass per-command:")
                print("  tplink-cli --host http://192.168.1.1 <command>")
                print("=======================================================\n")
            return 0

        if parsed_args.username == "SHOW":
            if parsed_args.json:
                print(json.dumps({"username": cfg.get("username", "admin")}))
            else:
                print(f"Current Router Username : {cfg.get('username', 'admin')}")
            return 0

        if parsed_args.cookie == "PROMPT":
            c = cfg.get("session_cookie")
            if c:
                masked = f"{c[:6]}...{c[-6:]}" if len(c) > 12 else c
                print(f"\n\033[1mActive Browser Session Cookie:\033[0m {masked}")
            else:
                print("\n\033[93mNo browser session cookie currently stored.\033[0m")
            print("To store a new session cookie:")
            print("  tplink-cli cookie <cookie_string_or_jsessionid>\n")
            return 0

        parser.print_help()
        return 0

    # If subcommand IS given, but user passed bare --host or --username without value, normalize
    if parsed_args.host == "SHOW":
        parsed_args.host = None
    if parsed_args.username == "SHOW":
        parsed_args.username = None

    try:
        parsed_args.func(parsed_args)
    except KeyboardInterrupt:
        print("\n\033[93m[Aborted] Operation cancelled by user.\033[0m")
        sys.exit(130)
    except Exception as e:
        sys.exit(handle_cli_error(e, parsed_args))


def handle_cli_error(e: Exception, args: Optional[argparse.Namespace] = None) -> int:
    is_json = getattr(args, "json", False) if args else False
    host = getattr(args, "host", None) or "http://192.168.1.1"

    err_str = str(e)
    err_type = type(e).__name__

    # 1. Authentication / Password errors (Check before OSError since PermissionError inherits from OSError)
    if isinstance(e, PermissionError) or "password" in err_str.lower() or "71233" in err_str:
        if is_json:
            print(json.dumps({
                "error": True,
                "code": "AUTHENTICATION_FAILED",
                "message": "Router authentication failed.",
                "detail": err_str or "Incorrect admin password or session expired.",
                "hint": "Update your password with 'tplink-cli config set-password' or set an active session cookie with 'tplink-cli cookie'."
            }, indent=2), file=sys.stderr)
        else:
            print()
            print("======================================================================")
            print("  🔒  \033[1mAUTHENTICATION FAILED\033[0m")
            print("======================================================================")
            print(f"Target Router : \033[94m{host}\033[0m")
            print(f"Reason        : \033[91m{err_str or 'Incorrect admin password or session expired.'}\033[0m")
            print("----------------------------------------------------------------------")
            print("To fix this:")
            print("  1. Update stored password:")
            print("       \033[1mtplink-cli config set-password <password>\033[0m")
            print("  2. Or set an active browser session cookie:")
            print("       \033[1mtplink-cli cookie\033[0m")
            print("======================================================================")
            print()
        return 1

    # 2. Timeout error (Check before OSError since TimeoutError inherits from OSError)
    if isinstance(e, (requests.exceptions.Timeout, TimeoutError)) or "timed out" in err_str.lower():
        if is_json:
            print(json.dumps({
                "error": True,
                "code": "REQUEST_TIMEOUT",
                "message": f"Connection to {host} timed out.",
                "hint": "The router may be busy rebooting, switching LTE bands, or under high load."
            }, indent=2), file=sys.stderr)
        else:
            print()
            print("======================================================================")
            print("  ⏱️   \033[1mROUTER CONNECTION TIMED OUT\033[0m")
            print("======================================================================")
            print(f"Target Router : \033[94m{host}\033[0m")
            print("Detail        : Request timed out waiting for router response.")
            print("----------------------------------------------------------------------")
            print("The router is taking too long to respond. It may be rebooting,")
            print("renegotiating cellular frequencies, or experiencing packet loss.")
            print("Please wait a few seconds and try again.")
            print("======================================================================")
            print()
        return 1

    # 3. Connection / Network errors (Offline / Rebooting)
    is_network_err = (
        isinstance(e, (requests.exceptions.ConnectionError, ConnectionError, OSError))
        or any(phrase in err_str for phrase in [
            "Network is unreachable",
            "Connection refused",
            "Failed to establish a new connection",
            "Max retries exceeded",
            "No route to host",
            "Name or service not known",
        ])
    )

    if is_network_err:
        if is_json:
            print(json.dumps({
                "error": True,
                "code": "ROUTER_UNREACHABLE",
                "message": f"Unable to reach TP-Link router at {host}.",
                "detail": "Network is unreachable (host is offline or Wi-Fi is reconnecting).",
                "hint": "If you recently rebooted the router, wait 60–90 seconds for it to finish starting up. Ensure your device is connected to the router Wi-Fi or Ethernet."
            }, indent=2), file=sys.stderr)
        else:
            print()
            print("======================================================================")
            print("  ⚠️   \033[1mROUTER UNREACHABLE (OFFLINE)\033[0m")
            print("======================================================================")
            print(f"Target Router : \033[94m{host}\033[0m")
            print("Status        : \033[91mConnection Failed (Host is offline or unreachable)\033[0m")
            print("----------------------------------------------------------------------")
            print("Troubleshooting & Possible Causes:")
            print("  • \033[1mRouter Rebooting\033[0m : If you just ran 'tplink-cli reboot', the hardware")
            print("                       takes ~60 to 90 seconds to restart. Wait a moment and retry.")
            print("  • \033[1mWi-Fi Dropped\033[0m    : Verify that your computer has reconnected to the")
            print("                       router Wi-Fi (e.g. 'dulith.connect') or Ethernet LAN cable.")
            print("  • \033[1mIP Gateway Check\033[0m : Ensure your default gateway is 192.168.1.1.")
            print("                       Run 'tplink-cli profile' to inspect the active gateway.")
            print("======================================================================")
            print()
        return 1

    # 4. Argument / Config error
    if isinstance(e, ValueError):
        if is_json:
            print(json.dumps({
                "error": True,
                "code": "INVALID_ARGUMENT",
                "message": err_str,
            }, indent=2), file=sys.stderr)
        else:
            print()
            print("======================================================================")
            print("  ⚠️   \033[1mCONFIGURATION / ARGUMENT ERROR\033[0m")
            print("======================================================================")
            print(f"Error : {err_str}")
            print("======================================================================")
            print()
        return 2

    # 5. Generic unhandled exception fallback
    if is_json:
        print(json.dumps({
            "error": True,
            "code": "UNEXPECTED_ERROR",
            "type": err_type,
            "message": err_str,
        }, indent=2), file=sys.stderr)
    else:
        print()
        print("======================================================================")
        print("  ⚠️   \033[1mCOMMAND ERROR\033[0m")
        print("======================================================================")
        print(f"Type    : {err_type}")
        print(f"Message : {err_str}")
        print("======================================================================")
        print()
    return 1


if __name__ == "__main__":
    main()
