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
    )

    host = cfg["host"]
    username = cfg["username"]
    password = cfg["password"]
    expected_ssid = cfg.get("expected_ssid")
    force = getattr(args, "force", False)

    # Run Network Guard safety check
    is_safe, msg = NetworkGuard.check_safety(target_host=host, expected_ssid=expected_ssid, force=force)
    if not is_safe:
        print(f"\033[91m[Network Guard Alert] {msg}\033[0m")
        sys.exit(2)

    if not password:
        print(f"No password configured for router at {host}.")
        password = getpass.getpass("Enter router admin password: ")

    return RouterClientFactory.get_client(host=host, password=password, username=username)


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
        if args.subcommand == "send":
            client.send_sms(args.recipient, args.message)
            print("\033[92mSMS sent successfully.\033[0m")
        else:
            msgs = client.get_sms(limit=args.limit or 10, folder=args.folder or "inbox")
            if getattr(args, "json", False):
                import dataclasses
                print(json.dumps([dataclasses.asdict(m) for m in msgs], indent=2))
                return
            print(f"\n\033[1mSMS ({len(msgs)} messages in {args.folder or 'inbox'}):\033[0m")
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
    elif args.subcommand == "show":
        cfg = cfg_mgr.load()
        has_pwd = bool(cfg["password"])
        print(f"Config File   : {cfg_mgr.config_file}")
        print(f"Router Host   : {cfg['host']}")
        print(f"Username      : {cfg['username']}")
        print(f"Expected SSID : {cfg.get('expected_ssid') or '[Any]'}")
        print(f"Password      : {'[STORED - ' + str(len(cfg['password'])) + ' chars]' if has_pwd else '[NOT SET]'}")


def cmd_repl(args: argparse.Namespace):
    client = get_client(args)
    run_repl(client)


def main():
    parser = argparse.ArgumentParser(
        prog="tplink-cli",
        description="Universal TP-Link Agentic Router Suite (Cross-Platform)"
    )
    parser.add_argument("--host", help="Router IP/Host (default: http://192.168.1.1)")
    parser.add_argument("--username", help="Admin username (default: admin)")
    parser.add_argument("--password", help="Admin password (overrides stored config)")
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
    cfg_show = cfg_sub.add_parser("show", help="Show current configuration")
    p_cfg.set_defaults(func=cmd_config)

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
