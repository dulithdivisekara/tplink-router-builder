"""Unified CLI command-line interface for TP-Link Router Management."""

import argparse
import getpass
import json
import sys
from typing import Any

from tplink_router.clients.factory import RouterClientFactory
from tplink_router.core.config import ConfigManager
from tplink_router.core.network_guard import NetworkGuard
from tplink_router.core.session import SafeSession
from tplink_router.cli.repl import run_repl


def get_client(args: argparse.Namespace) -> Any:
    cfg = ConfigManager().load(
        cli_host=getattr(args, "host", None),
        cli_username=getattr(args, "username", None),
        cli_password=getattr(args, "password", None),
        cli_cookie=getattr(args, "cookie", None),
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
    print(f"  RSRP         : {lte.rf.rsrp_dbm} dBm ({lte.rf.rsrp_rating})")
    print(f"  RSRQ         : {lte.rf.rsrq_db} dB ({lte.rf.rsrq_rating})")
    print(f"  SNR          : {lte.rf.snr_db} dB ({lte.rf.snr_rating})")
    print(f"  Signal Level : {lte.rf.signal_bars} / 4 bars\n")


def cmd_cell_lock(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_cell_lock"):
            print("Cell Lock is only supported on cellular MR models.")
            return

        if args.enable:
            if not args.earfcn or not args.pci:
                print("\033[91mError: Both --earfcn and --pci are required when enabling Cell Lock.\033[0m")
                sys.exit(1)
            client.set_cell_lock(True, args.earfcn, args.pci)
            print(f"\033[92mCell Lock applied to EARFCN {args.earfcn}, PCI {args.pci}!\033[0m")
        elif args.disable:
            client.set_cell_lock(False)
            print("\033[92mCell Lock disabled (Auto roaming restored).\033[0m")
        else:
            lock = client.get_cell_lock()
            print("\n\033[1mCell Lock Status:\033[0m")
            print(f"  Enabled : {lock.enabled}")
            print(f"  EARFCN  : {lock.earfcn}")
            print(f"  PCI     : {lock.pci}")
            print(f"  CID     : {lock.cid}\n")


def cmd_dns(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if args.action == "set":
            primary = args.primary
            secondary = args.secondary or "8.8.8.8"
            client.set_dns(primary, secondary)
            print(f"\033[92mDNS configured to {primary}, {secondary}\033[0m")
        else:
            v4, _ = client.get_wan_config()
            print(f"Active DNS: {v4.dns}")


def cmd_ipv6(args: argparse.Namespace):
    client = get_client(args)
    state = args.state.lower() in ("on", "1", "true", "enable")
    with SafeSession(client):
        client.toggle_ipv6(state)
    print(f"\033[92mIPv6 {'enabled' if state else 'disabled'} successfully.\033[0m")


def cmd_ussd(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "send_ussd"):
            print("USSD commands are only supported on cellular MR models.")
            return
        res = client.send_ussd(args.code)
    print(f"\n\033[1mUSSD Response:\033[0m\n{res.response}\n")


def cmd_sms(args: argparse.Namespace):
    client = get_client(args)
    with SafeSession(client):
        if not hasattr(client, "get_sms"):
            print("SMS is only supported on cellular MR models.")
            return
        if getattr(args, "subcommand", None) == "send":
            client.send_sms(args.recipient, args.message)
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
    print("\033[92mRouter reboot initiated. Releasing session.\033[0m")


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
    if args.subcommand == "set-password":
        pwd = args.password
        if not pwd:
            pwd = getpass.getpass("Enter router admin password to save: ")
        host = args.host or "http://192.168.1.1"
        username = args.username or "admin"
        ssid = args.expected_ssid or ""
        cfg_mgr.save(password=pwd, host=host, username=username, expected_ssid=ssid)
        print(f"\033[92mConfiguration securely saved to {cfg_mgr.config_file} (mode 0600).\033[0m")
    elif args.subcommand == "set-cookie":
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
    elif args.subcommand == "clear-cookie":
        cfg_mgr.save(session_cookie="")
        print(f"\033[92mStored session cookie cleared from {cfg_mgr.config_file}.\033[0m")
    elif args.subcommand == "show":
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

        if args.subcommand == "list" or not getattr(args, "subcommand", None):
            reservations = client.get_dhcp_reservations()
            if getattr(args, "json", False):
                print(json.dumps(reservations, indent=2))
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
        elif args.subcommand == "add":
            client.add_dhcp_reservation(args.mac, args.ip)
            print(f"\033[92mReservation added: {args.mac} -> {args.ip}\033[0m")
        elif args.subcommand == "del":
            client.delete_dhcp_reservation(args.mac)
            print(f"\033[92mReservation deleted for MAC {args.mac}\033[0m")


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

        print("\n" + "=" * 65)
        print("  \033[1mWIRELESS (WI-FI) NETWORKS\033[0m")
        print("=" * 65)
        for net in networks:
            status = "\033[92mEnabled\033[0m" if net["enabled"] else "\033[91mDisabled\033[0m"
            print(f"Band: \033[1m{net['band']}\033[0m  SSID: \033[1m{net['ssid']}\033[0m  State: {status}  Channel: {net['channel']}")
        print("=" * 65 + "\n")


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
        client.set_lte_band(args.band)
    print(f"\033[92mLTE band successfully locked to {args.band.upper()}.\033[0m")


def cmd_calibrate(args: argparse.Namespace):
    from tplink_router.calibration.engine import RouterCalibrator
    from tplink_router.calibration.dashboard import start_dashboard_server

    cfg = ConfigManager().load(cli_host=args.host, cli_username=args.username, cli_password=args.password)
    password = cfg.get("password") or args.password
    host = cfg.get("host") or args.host or "http://192.168.1.1"

    target_bands = [b.strip() for b in args.bands.split(",") if b.strip()]

    calibrator = RouterCalibrator(
        host=host,
        password=password,
        username=args.username or cfg.get("username", "admin"),
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


def main():
    parser = argparse.ArgumentParser(
        prog="tplink-cli",
        description="Universal TP-Link Agentic Router Suite (Cross-Platform)"
    )
    parser.add_argument("--host", help="Router IP/Host (default: http://192.168.1.1)")
    parser.add_argument("--username", help="Admin username (default: admin)")
    parser.add_argument("--password", help="Admin password (overrides stored config)")
    parser.add_argument("--cookie", "--session-id", dest="cookie", help="Browser session cookie (JSESSIONID or Netscape format)")
    parser.add_argument("--force", action="store_true", help="Bypass Network Guard checks")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    p_status = subparsers.add_parser("status", help="Show full router & cellular telemetry")
    p_status.set_defaults(func=cmd_status)

    # signal
    p_sig = subparsers.add_parser("signal", help="Show RF signal metrics (RSRP, RSRQ, SNR)")
    p_sig.set_defaults(func=cmd_signal)

    # cell-lock
    p_lock = subparsers.add_parser("cell-lock", help="View or configure LTE Cell Lock")
    p_lock.add_argument("--enable", action="store_true", help="Enable Cell Lock")
    p_lock.add_argument("--disable", action="store_true", help="Disable Cell Lock")
    p_lock.add_argument("--earfcn", help="Target EARFCN channel (e.g. 1550)")
    p_lock.add_argument("--pci", help="Target Physical Cell Identity (e.g. 58)")
    p_lock.set_defaults(func=cmd_cell_lock)

    # dns
    p_dns = subparsers.add_parser("dns", help="Manage router DNS settings")
    dns_sub = p_dns.add_subparsers(dest="action")
    dns_set = dns_sub.add_parser("set", help="Set DNS servers")
    dns_set.add_argument("primary", help="Primary DNS (e.g. 8.8.8.8)")
    dns_set.add_argument("secondary", nargs="?", default="1.1.1.1", help="Secondary DNS")
    dns_show = dns_sub.add_parser("show", help="Show current DNS")
    p_dns.set_defaults(func=cmd_dns)

    # ipv6
    p_ipv6 = subparsers.add_parser("ipv6", help="Toggle IPv6 stack (on/off)")
    p_ipv6.add_argument("state", choices=["on", "off", "enable", "disable"], help="State to set")
    p_ipv6.set_defaults(func=cmd_ipv6)

    # ussd
    p_ussd = subparsers.add_parser("ussd", help="Execute USSD query (e.g. *344# or *123#)")
    p_ussd.add_argument("code", help="USSD string")
    p_ussd.set_defaults(func=cmd_ussd)

    # sms
    p_sms = subparsers.add_parser("sms", help="Read or send SMS")
    sms_sub = p_sms.add_subparsers(dest="subcommand")
    sms_list = sms_sub.add_parser("list", help="List SMS messages")
    sms_list.add_argument("--limit", type=int, default=10, help="Max messages to fetch")
    sms_list.add_argument("--folder", choices=["inbox", "sent"], default="inbox", help="SMS folder")
    sms_send = sms_sub.add_parser("send", help="Send SMS")
    sms_send.add_argument("recipient", help="Phone number")
    sms_send.add_argument("message", help="Message text")
    p_sms.set_defaults(func=cmd_sms)

    # reboot
    p_reboot = subparsers.add_parser("reboot", help="Reboot the router")
    p_reboot.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p_reboot.set_defaults(func=cmd_reboot)

    # profile check
    p_prof = subparsers.add_parser("profile", help="Check active network profile and gateway safety")
    prof_sub = p_prof.add_subparsers(dest="subcommand")
    prof_check = prof_sub.add_parser("check", help="Check current Wi-Fi SSID and gateway")
    prof_check.set_defaults(func=cmd_profile_check)

    # config
    p_cfg = subparsers.add_parser("config", help="Manage stored credentials")
    cfg_sub = p_cfg.add_subparsers(dest="subcommand")
    cfg_set = cfg_sub.add_parser("set-password", help="Save router admin password securely")
    cfg_set.add_argument("password", nargs="?", help="Admin password (prompts if omitted)")
    cfg_set.add_argument("--expected-ssid", help="Expected Wi-Fi SSID for safety guard")
    cfg_cookie = cfg_sub.add_parser("set-cookie", help="Save browser session cookie (Netscape or JSESSIONID format)")
    cfg_cookie.add_argument("cookie", nargs="?", help="Cookie string, Netscape block, or JSESSIONID")
    cfg_cookie.add_argument("--file", "-f", help="Path to Netscape cookies.txt file")
    cfg_clear = cfg_sub.add_parser("clear-cookie", help="Clear saved session cookie")
    cfg_show = cfg_sub.add_parser("show", help="Show current configuration")
    p_cfg.set_defaults(func=cmd_config)

    # wifi-guard
    p_wguard = subparsers.add_parser("wifi-guard", help="Verify and optimize Wi-Fi link stability (no Ethernet needed)")
    p_wguard.add_argument("--optimize", "--fix", dest="optimize", action="store_true", help="Auto-optimize Wi-Fi stability and elevate NetworkManager priority")
    p_wguard.set_defaults(func=cmd_wifi_guard)

    # clients
    p_clients = subparsers.add_parser("clients", help="List connected LAN devices (IP, MAC, Hostname)")
    p_clients.set_defaults(func=cmd_clients)

    # reservation
    p_resv = subparsers.add_parser("reservation", help="Manage DHCP static IP reservations")
    resv_sub = p_resv.add_subparsers(dest="subcommand")
    resv_list = resv_sub.add_parser("list", help="List all reservations")
    resv_add = resv_sub.add_parser("add", help="Add DHCP static reservation")
    resv_add.add_argument("mac", help="Device MAC address")
    resv_add.add_argument("ip", help="Reserved IP address")
    resv_del = resv_sub.add_parser("del", help="Delete DHCP reservation")
    resv_del.add_argument("mac", help="Device MAC address to remove")
    p_resv.set_defaults(func=cmd_reservation)

    # data-limit
    p_dlim = subparsers.add_parser("data-limit", help="View or set monthly cellular data cap")
    p_dlim.add_argument("--limit", type=int, help="Monthly quota in Megabytes (e.g. 50000 for 50GB)")
    p_dlim.add_argument("--day", type=int, default=1, help="Billing cycle reset day of month (1-31)")
    p_dlim.set_defaults(func=cmd_data_limit)

    # wifi
    p_wifi = subparsers.add_parser("wifi", help="View or configure Wi-Fi radios (2.4GHz / 5GHz)")
    p_wifi.add_argument("--band", choices=["2.4GHz", "5GHz", "2.4", "5"], default="2.4GHz", help="Frequency band")
    p_wifi.add_argument("--toggle", choices=["on", "off", "enable", "disable"], help="Turn radio on/off")
    p_wifi.add_argument("--ssid", help="Set new SSID name")
    p_wifi.set_defaults(func=cmd_wifi)

    # leds
    p_leds = subparsers.add_parser("leds", help="Control router LEDs and Night Mode schedule")
    p_leds.add_argument("--night-mode", choices=["on", "off", "enable", "disable"], help="Toggle night mode schedule")
    p_leds.add_argument("--start", default="22:00", help="Night mode start time (HH:MM)")
    p_leds.add_argument("--end", default="07:00", help="Night mode end time (HH:MM)")
    p_leds.set_defaults(func=cmd_leds)

    # diag
    p_diag = subparsers.add_parser("diag", help="Run router WAN and internet diagnostic test")
    p_diag.set_defaults(func=cmd_diag)

    # band
    p_band = subparsers.add_parser("band", help="Lock modem to specific LTE Band (e.g. 3, 8, 40, auto)")
    p_band.add_argument("band", help="LTE Band (e.g. 3, 8, 40, or auto)")
    p_band.set_defaults(func=cmd_band)

    # calibrate
    p_cal = subparsers.add_parser("calibrate", help="Autonomous RF band calibration & Live Web UI")
    p_cal.add_argument("--web", action="store_true", default=True, help="Launch real-time Web UI dashboard")
    p_cal.add_argument("--no-web", dest="web", action="store_false", help="Run in headless terminal mode")
    p_cal.add_argument("--port", type=int, default=8765, help="Web dashboard port (default: 8765)")
    p_cal.add_argument("--bands", default="8,3,1,40,auto", help="Candidate bands (default: 8,3,1,40,auto)")
    p_cal.add_argument("--timeout", type=int, default=45, help="45s watchdog timeout")
    p_cal.add_argument("--dry-run", action="store_true", help="Simulate without radio detachment")
    p_cal.set_defaults(func=cmd_calibrate)

    # repl
    p_repl = subparsers.add_parser("repl", help="Launch interactive REPL console")
    p_repl.set_defaults(func=cmd_repl)

    parsed_args = parser.parse_args()
    if hasattr(parsed_args, "func"):
        parsed_args.func(parsed_args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
