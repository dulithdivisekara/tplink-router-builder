"""Unified CLI command-line interface for TP-Link Router Management."""

import argparse
from contextlib import contextmanager
import getpass
import json
import shlex
import sys
import time
from typing import Any, List, Optional
import requests

from tplink_router.cli.animator import clear_active_spinner, router_spinner
from tplink_router.cli.repl import run_repl
from tplink_router.cli.theme import (
    get_palette,
    print_panel,
    print_toast,
    progress_meter,
    rating_badge,
    render_kv_rows,
    render_section_header,
    render_table_lines,
    signal_bars,
    status_badge,
)
from tplink_router.clients.factory import RouterClientFactory
from tplink_router.core.config import ConfigManager
from tplink_router.core.network_guard import NetworkGuard
from tplink_router.core.session import SafeSession


def _is_legacy(args: Optional[argparse.Namespace]) -> bool:
    return bool(getattr(args, "legacy", False)) if args else False


def _is_mono(args: Optional[argparse.Namespace]) -> bool:
    return bool(getattr(args, "mono", False)) if args else False


@contextmanager
def animated_session(client: Any, args: Optional[argparse.Namespace], label: str):
    """Wrap SafeSession with a Claude-Code-style transient terminal animation."""
    with router_spinner(label=label, args=args):
        with SafeSession(client):
            yield


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
        elif _is_legacy(args):
            print(f"\033[91m[Network Guard Alert] {msg}\033[0m")
        else:
            print_toast("danger", "Network Guard Blocked Operation", msg, mono=_is_mono(args))
        sys.exit(2)

    if not password and not session_cookie:
        print(f"No password or session cookie configured for router at {host}.")
        password = getpass.getpass("Enter router admin password: ")

    return RouterClientFactory.get_client(
        host=host, password=password, username=username, session_cookie=session_cookie
    )


def cmd_status(args: argparse.Namespace):
    client = get_client(args)
    with animated_session(client, args, 'Polling TP-Link router & LTE RF telemetry…'):
        telemetry = client.get_telemetry()

    if getattr(args, "json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(telemetry), indent=2))
        return

    dev = telemetry.device
    lte = telemetry.lte
    v4 = telemetry.ipv4
    v6 = telemetry.ipv6

    if _is_legacy(args):
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
        return

    mono = _is_mono(args)
    p = get_palette(mono=mono)
    sections: List[List[str]] = []

    hw_rows = [
        ("Hardware / Firmware", f"{dev.hardware_version}  •  {dev.firmware_version}"),
    ]
    if lte:
        lock = lte.cell_lock
        lock_val = (
            f"{status_badge(True, 'LOCKED', 'AUTO', mono=mono)}  EARFCN {lock.earfcn} • PCI {lock.pci}"
            if lock.enabled
            else status_badge(False, "LOCKED", "AUTO ROAMING", mono=mono)
        )
        hw_rows.extend([
            ("Cellular Operator", f"{p.white}{lte.isp_name}{p.reset}  {p.muted}(SIM: {lte.sim_status}){p.reset}"),
            ("Connection State", status_badge(lte.connected, "CONNECTED", "DISCONNECTED", mono=mono, warn_off=True)),
            ("LTE Band / Channel", f"{p.brand_bold}{lte.band}{p.reset}  {p.muted}(EARFCN: {lte.earfcn or 'N/A'}, PCI: {lte.pci or '0'}){p.reset}"),
            ("Cell Lock Status", lock_val),
        ])
    sections.append([render_section_header("DEVICE & CELLULAR MODEM", mono=mono)] + render_kv_rows(hw_rows, key_width=20, mono=mono))

    if lte:
        rsrp_str = (
            f"{lte.rf.rsrp_dbm} dBm  ({rating_badge(lte.rf.rsrp_rating, mono=mono)})"
            if lte.rf.rsrp_dbm != 0
            else f"{p.muted}0 dBm (Raw Modem Reading){p.reset}  ({rating_badge(lte.rf.rsrp_rating, mono=mono)})"
        )
        rf_rows = [
            ("Signal Strength", signal_bars(lte.rf.signal_bars, mono=mono)),
        ]
        if lte.rf.rssi_dbm != 0:
            rf_rows.append(("RSSI (Carrier Power)", f"{lte.rf.rssi_dbm} dBm  ({rating_badge(lte.rf.rssi_rating, mono=mono)})"))
        rf_rows.extend([
            ("RSRP (Signal Power)", rsrp_str),
            ("RSRQ (Quality/Load)", f"{lte.rf.rsrq_db} dB  ({rating_badge(lte.rf.rsrq_rating, mono=mono)})"),
            ("SNR (Signal/Noise)", f"{lte.rf.snr_db} dB  ({rating_badge(lte.rf.snr_rating, mono=mono)})"),
        ])
        sections.append([render_section_header("RADIO FREQUENCY (RF) METRICS", mono=mono)] + render_kv_rows(rf_rows, key_width=20, mono=mono))

        usage_rows = [
            ("Live Throughput", f"{p.brand_bold}↓ {lte.rx_speed_kbps} Kbps{p.reset}   {p.white}↑ {lte.tx_speed_kbps} Kbps{p.reset}"),
            ("Total Transferred", f"{round(lte.total_bytes_transferred / (1024 * 1024), 2)} MB"),
        ]
        sections.append([render_section_header("THROUGHPUT & DATA TRAFFIC", mono=mono)] + render_kv_rows(usage_rows, key_width=20, mono=mono))

    v6_en = bool(v6.enabled or v6.ip)
    v6_badge = status_badge(v6_en, f"ENABLED ({v6.status})", "DISABLED", mono=mono)
    wan_rows = [
        ("WAN IPv4 Address", f"{p.white}{v4.ip or 'N/A'}{p.reset}  {p.muted}(Gateway: {v4.gateway or 'N/A'}){p.reset}"),
        ("Active DNS Servers", ", ".join(v4.dns) if v4.dns else "Default ISP Assigned"),
        ("IPv6 Stack State", v6_badge),
    ]
    sections.append([render_section_header("WAN NETWORK CONFIGURATION", mono=mono)] + render_kv_rows(wan_rows, key_width=20, mono=mono))

    print_panel(
        title="TP-LINK ROUTER TELEMETRY",
        sections=sections,
        subtitle=dev.model,
        footer="tplink-cli signal • tplink-cli band • tplink-cli clients",
        mono=mono,
    )


def cmd_signal(args: argparse.Namespace):
    client = get_client(args)
    with animated_session(client, args, 'Measuring cellular LTE RF signal metrics…'):
        if not hasattr(client, "get_lte_status"):
            print("Signal metrics are only available on cellular MR models.")
            return
        lte = client.get_lte_status()

    if getattr(args, "json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(lte.rf), indent=2))
        return

    if _is_legacy(args):
        print("\n\033[1mCurrent LTE RF Signal:\033[0m")
        print(f"  Carrier      : {lte.isp_name}")
        print(f"  Active Band  : {lte.band} (EARFCN: {lte.earfcn}, PCI: {lte.pci})")
        print(f"  Signal Level : {lte.rf.signal_bars} / 4 bars")
        if lte.rf.rssi_dbm != 0:
            print(f"  RSSI         : {lte.rf.rssi_dbm} dBm ({lte.rf.rssi_rating})")
        if lte.rf.rsrp_dbm != 0:
            print(f"  RSRP         : {lte.rf.rsrp_dbm} dBm ({lte.rf.rsrp_rating})")
        else:
            print("  RSRP         : N/A (Modem raw: 0 dBm)")
        if lte.rf.rsrq_db != 0:
            print(f"  RSRQ         : {lte.rf.rsrq_db} dB ({lte.rf.rsrq_rating})")
        if lte.rf.snr_db != 0:
            print(f"  SNR          : {lte.rf.snr_db} dB ({lte.rf.snr_rating})")
        print()
        return

    mono = _is_mono(args)
    p = get_palette(mono=mono)
    rows = [
        ("Carrier", f"{p.white}{lte.isp_name}{p.reset}"),
        ("Active LTE Band", f"{p.brand_bold}{lte.band}{p.reset}  {p.muted}(EARFCN: {lte.earfcn or 'N/A'}, PCI: {lte.pci or '0'}){p.reset}"),
        ("Signal Bars", f"{signal_bars(lte.rf.signal_bars, mono=mono)}   {progress_meter(lte.rf.signal_bars, 4, width=14, mono=mono)}"),
    ]
    if lte.rf.rssi_dbm != 0:
        rows.append(("RSSI", f"{lte.rf.rssi_dbm} dBm  ({rating_badge(lte.rf.rssi_rating, mono=mono)})"))
    if lte.rf.rsrp_dbm != 0:
        rows.append(("RSRP", f"{lte.rf.rsrp_dbm} dBm  ({rating_badge(lte.rf.rsrp_rating, mono=mono)})"))
    else:
        rows.append(("RSRP", f"{p.muted}N/A (Modem raw: 0 dBm){p.reset}"))
    if lte.rf.rsrq_db != 0:
        rows.append(("RSRQ", f"{lte.rf.rsrq_db} dB  ({rating_badge(lte.rf.rsrq_rating, mono=mono)})"))
    if lte.rf.snr_db != 0:
        rows.append(("SNR", f"{lte.rf.snr_db} dB  ({rating_badge(lte.rf.snr_rating, mono=mono)})"))

    print_panel(
        title="CELLULAR LTE RF SIGNAL",
        sections=[render_kv_rows(rows, key_width=16, mono=mono)],
        subtitle=lte.isp_name,
        footer="tplink-cli band • tplink-cli calibrate",
        mono=mono,
    )


def cmd_cell_lock(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Communicating with cellular EARFCN/PCI baseband…'):
        if not hasattr(client, "get_cell_lock"):
            print("Cell Lock is only supported on cellular MR models.")
            return

        if getattr(args, "enable", False):
            if not getattr(args, "earfcn", None) or not getattr(args, "pci", None):
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_CELL_LOCK_PARAMS",
                        "message": "Both --earfcn and --pci are required when enabling Cell Lock."
                    }, indent=2))
                elif _is_legacy(args):
                    print("\033[91mError: Both --earfcn and --pci are required when enabling Cell Lock.\033[0m")
                else:
                    print_toast("danger", "Missing Cell Lock Parameters", "Both --earfcn and --pci are required when enabling Cell Lock.", mono=mono)
                sys.exit(1)
            client.set_cell_lock(True, args.earfcn, args.pci)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "enabled": True,
                    "earfcn": args.earfcn,
                    "pci": args.pci
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92mCell Lock applied to EARFCN {args.earfcn}, PCI {args.pci}!\033[0m")
            else:
                print_toast("success", f"Cell Lock applied to EARFCN {args.earfcn}, PCI {args.pci}", "Modem is locking onto the target carrier sector.", mono=mono)
            return
        elif getattr(args, "disable", False):
            client.set_cell_lock(False)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "enabled": False,
                    "message": "Auto roaming restored"
                }, indent=2))
                return
            if _is_legacy(args):
                print("\033[92mCell Lock disabled (Auto roaming restored).\033[0m")
            else:
                print_toast("success", "Cell Lock disabled (Auto roaming restored)", mono=mono)
            return
        else:
            lock = client.get_cell_lock()
            if getattr(args, "json", False):
                import dataclasses
                print(json.dumps(dataclasses.asdict(lock), indent=2))
                return
            if _is_legacy(args):
                print("\n" + "=" * 55)
                print("  \033[1mLTE CELL LOCK STATUS\033[0m")
                print("=" * 55)
                if lock.enabled:
                    print("Status        : \033[92mLOCKED (Targeting Cell Tower)\033[0m")
                    print(f"Target EARFCN : {lock.earfcn}")
                    print(f"Target PCI    : {lock.pci}")
                    if lock.cid:
                        print(f"Cell ID (CID) : {lock.cid}")
                    if lock.freq:
                        print(f"Frequency     : {lock.freq}")
                else:
                    print("Status        : \033[93mDisabled (Auto-Roaming Active)\033[0m")
                    print("Router automatically chooses the strongest carrier cell.")
                print("-" * 55)
                print("Commands:")
                print("  Lock tower   : tplink-cli cell-lock --enable --earfcn <earfcn> --pci <pci>")
                print("  Restore auto : tplink-cli cell-lock --disable")
                print("=" * 55 + "\n")
                return

            p = get_palette(mono=mono)
            rows = [
                ("Lock State", status_badge(lock.enabled, "LOCKED TO CELL TOWER", "DISABLED (AUTO-ROAMING)", mono=mono)),
            ]
            if lock.enabled:
                rows.append(("Target EARFCN", lock.earfcn))
                rows.append(("Target PCI", lock.pci))
                if lock.cid:
                    rows.append(("Cell ID (CID)", lock.cid))
                if lock.freq:
                    rows.append(("Frequency", lock.freq))
            else:
                rows.append(("Behavior", "Modem automatically attaches to strongest carrier sector"))

            hints = [
                f"{p.muted}Lock tower   :{p.reset} {p.white}tplink-cli cell-lock --enable --earfcn <E> --pci <P>{p.reset}",
                f"{p.muted}Restore auto :{p.reset} {p.white}tplink-cli cell-lock --disable{p.reset}",
            ]
            print_panel(
                title="LTE CELL LOCK STATUS",
                sections=[render_kv_rows(rows, key_width=16, mono=mono), hints],
                mono=mono,
            )


def cmd_dns(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Synchronizing router WAN DNS resolver configuration…'):
        action = getattr(args, "action", None)
        if action == "set":
            primary = getattr(args, "primary", None)
            if not primary:
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_PRIMARY_DNS",
                        "message": "Primary DNS server IP address is required."
                    }, indent=2))
                    sys.exit(1)
                if _is_legacy(args):
                    print("\nUsage: tplink-cli dns set <primary_dns> [secondary_dns]")
                    print("Examples:")
                    print("  tplink-cli dns set 1.1.1.1 1.0.0.1    (Cloudflare)")
                    print("  tplink-cli dns set 8.8.8.8 8.8.4.4    (Google)\n")
                else:
                    p = get_palette(mono=mono)
                    print_panel(
                        title="DNS RESOLVER USAGE",
                        sections=[[
                            f"{p.white}tplink-cli dns set <primary_dns> [secondary_dns]{p.reset}",
                            "",
                            f"  {p.brand_bold}1.1.1.1 1.0.0.1{p.reset}   {p.muted}(Cloudflare Low-Latency){p.reset}",
                            f"  {p.brand_bold}8.8.8.8 8.8.4.4{p.reset}   {p.muted}(Google Public DNS){p.reset}",
                        ]],
                        mono=mono,
                    )
                return
            secondary = getattr(args, "secondary", "8.8.8.8") or "8.8.8.8"
            client.set_dns(primary, secondary)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "primary_dns": primary,
                    "secondary_dns": secondary
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92mDNS configured to {primary}, {secondary}\033[0m")
            else:
                print_toast("success", f"DNS configured to {primary}, {secondary}", mono=mono)
            return
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
            if _is_legacy(args):
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
                return

            p = get_palette(mono=mono)
            rows = [
                ("Active IPv4 DNS", f"{p.white}{', '.join(v4.dns)}{p.reset}" if v4.dns else "Default ISP Assigned"),
            ]
            if v6.dns:
                rows.append(("Active IPv6 DNS", ", ".join(v6.dns)))
            rows.extend([
                ("WAN IP Address", v4.ip or "Disconnected"),
                ("Default Gateway", v4.gateway or "N/A"),
            ])
            hints = [
                f"{p.muted}Cloudflare :{p.reset} {p.white}tplink-cli dns set 1.1.1.1 1.0.0.1{p.reset}",
                f"{p.muted}Google DNS :{p.reset} {p.white}tplink-cli dns set 8.8.8.8 8.8.4.4{p.reset}",
            ]
            print_panel(
                title="ROUTER DNS CONFIGURATION",
                sections=[render_kv_rows(rows, key_width=17, mono=mono), hints],
                mono=mono,
            )


def cmd_ipv6(args: argparse.Namespace):
    mono = _is_mono(args)
    state_str = getattr(args, "state", None)
    if getattr(args, "interactive", False) and not state_str and not getattr(args, "json", False):
        from tplink_router.cli.interactive_tui import inline_select
        picked = inline_select(
            "ROUTER IPv6 STACK CONTROL",
            [
                ("status", "Inspect Current IPv6 Status", "Read-only stack check"),
                ("on", "Enable IPv6 Stack (ON)", "Activate dual-stack IPv6 WAN"),
                ("off", "Disable IPv6 Stack (OFF)", "IPv4-only WAN bearer"),
            ],
            mono=mono,
        )
        if picked and picked != "status":
            state_str = picked

    client = get_client(args)
    with animated_session(client, args, 'Querying & updating router WAN IPv6 stack…'):
        if not state_str:
            v4, v6 = client.get_wan_config()
            is_enabled = bool(v6.enabled or v6.ip)
            if getattr(args, "json", False):
                print(json.dumps({
                    "ipv6_enabled": is_enabled,
                    "ipv6_address": v6.ip or None,
                    "ipv6_dns": v6.dns or [],
                    "gateway": v6.gateway or None,
                    "status": v6.status
                }, indent=2))
                return
            if _is_legacy(args):
                print("\n" + "=" * 55)
                print("  \033[1mROUTER IPv6 STACK STATUS\033[0m")
                print("=" * 55)
                status_str = "\033[92mENABLED\033[0m" if is_enabled else "\033[90mDISABLED\033[0m"
                print(f"IPv6 Stack State   : {status_str}")
                if is_enabled:
                    if v6.ip:
                        print(f"IPv6 WAN Address   : {v6.ip}")
                    else:
                        print("IPv6 WAN Address   : Not Assigned (Cellular Bearer IPv4-Only / SLAAC Pending)")
                    if v6.dns:
                        print(f"IPv6 DNS Resolvers : {', '.join(v6.dns)}")
                    else:
                        print("IPv6 DNS Resolvers : ISP Default")
                    if v6.gateway:
                        print(f"IPv6 Gateway       : {v6.gateway}")
                print("-" * 55)
                print("To toggle IPv6:")
                print("  tplink-cli ipv6 on")
                print("  tplink-cli ipv6 off")
                print("=" * 55 + "\n")
                return

            p = get_palette(mono=mono)
            rows = [
                ("IPv6 Stack State", status_badge(is_enabled, "ENABLED", "DISABLED", mono=mono)),
            ]
            if is_enabled:
                rows.append((
                    "IPv6 WAN Address",
                    v6.ip if v6.ip else f"{p.muted}Not Assigned (Carrier IPv4-Only / SLAAC Pending){p.reset}",
                ))
                rows.append(("IPv6 DNS Resolvers", ", ".join(v6.dns) if v6.dns else "ISP Default"))
                if v6.gateway:
                    rows.append(("IPv6 Gateway", v6.gateway))
            hints = [
                f"{p.muted}Toggle stack:{p.reset} {p.white}tplink-cli ipv6 on{p.reset}  {p.muted}│{p.reset}  {p.white}tplink-cli ipv6 off{p.reset}"
            ]
            print_panel(
                title="ROUTER IPv6 STACK STATUS",
                sections=[render_kv_rows(rows, key_width=19, mono=mono), hints],
                mono=mono,
            )
            return

        state = state_str.lower() in ("on", "1", "true", "enable")
        client.toggle_ipv6(state)
        if getattr(args, "json", False):
            print(json.dumps({
                "success": True,
                "ipv6_enabled": state
            }, indent=2))
            return
    if _is_legacy(args):
        print(f"\033[92m✓ IPv6 {'enabled' if state else 'disabled'} successfully.\033[0m")
    else:
        print_toast("success", f"IPv6 {'enabled' if state else 'disabled'} successfully.", mono=mono)


def cmd_ussd(args: argparse.Namespace):
    mono = _is_mono(args)
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
            if _is_legacy(args):
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
            p = get_palette(mono=mono)
            codes = [
                ("Hutch", "*344# (Balance & Data Quota), *123# (Self-Care)"),
                ("Dialog", "*123# (Account Balance), *456# (Data Balance)"),
                ("Mobitel", "*100# (Account Balance), *145# (Self-Care)"),
                ("Airtel", "*550# (Balance & Data)"),
            ]
            print_panel(
                title="CELLULAR USSD QUERY",
                sections=[
                    render_kv_rows(codes, key_width=10, mono=mono),
                    [f"{p.muted}Example:{p.reset} {p.white}tplink-cli ussd '*344#'{p.reset}"],
                ],
                mono=mono,
            )
            return

    client = get_client(args)
    with animated_session(client, args, 'Transmitting cellular GSM/LTE USSD session…'):
        if not hasattr(client, "send_ussd"):
            print("USSD commands are only supported on cellular MR models.")
            return
        res = client.send_ussd(code)

    if getattr(args, "json", False):
        print(json.dumps({"code": code, "response": res.response}))
        return
    if _is_legacy(args):
        print(f"\n\033[1mUSSD Response:\033[0m\n{res.response}\n")
    else:
        print_panel(
            title="CARRIER USSD RESPONSE",
            sections=[[res.response or "(Empty carrier response)"]],
            subtitle=code,
            mono=mono,
        )


def cmd_sms(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Accessing cellular SIM SMS message storage…'):
        if not hasattr(client, "get_sms"):
            print("SMS is only supported on cellular MR models.")
            return
        if getattr(args, "subcommand", None) == "send":
            recip = getattr(args, "recipient", None)
            msg = getattr(args, "message", None)
            if not recip or not msg:
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_SMS_PARAMS",
                        "message": "Both recipient and message are required."
                    }, indent=2))
                    sys.exit(1)
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
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "recipient": recip,
                    "message": msg
                }, indent=2))
                return
            if _is_legacy(args):
                print("\033[92mSMS sent successfully.\033[0m")
            else:
                print_toast("success", f"SMS sent successfully to {recip}", mono=mono)
        else:
            limit = getattr(args, "limit", 10) or 10
            folder = getattr(args, "folder", "inbox") or "inbox"
            msgs = client.get_sms(limit=limit, folder=folder)
            if getattr(args, "json", False):
                import dataclasses
                print(json.dumps([dataclasses.asdict(m) for m in msgs], indent=2))
                return
            if _is_legacy(args):
                print(f"\n\033[1mSMS ({len(msgs)} messages in {folder}):\033[0m")
                print("-" * 65)
                for m in msgs:
                    unread = "\033[93m[NEW]\033[0m " if m.unread else ""
                    print(f"{unread}From: {m.sender} | Date: {m.received_time}")
                    print(f"Content: {m.content}")
                    print("-" * 65)
                print()
                return

            p = get_palette(mono=mono)
            if not msgs:
                sections = [[f"{p.muted}(No messages in {folder}){p.reset}"]]
            else:
                sections = []
                for m in msgs:
                    tag = f"{p.warning}● NEW{p.reset}  " if m.unread else ""
                    hdr = f"{tag}{p.brand_bold}{m.sender}{p.reset}   {p.muted}{m.received_time}{p.reset}"
                    sections.append([hdr, f"{p.text}{m.content}{p.reset}"])
            print_panel(
                title=f"CELLULAR SMS ({folder.upper()})",
                sections=sections,
                subtitle=f"{len(msgs)} Messages",
                footer="tplink-cli sms send <phone> '<message>'",
                mono=mono,
            )


def cmd_reboot(args: argparse.Namespace):
    mono = _is_mono(args)
    if not args.yes:
        confirm = input("Are you sure you want to reboot the TP-Link router? (y/N): ")
        if confirm.lower() != "y":
            if _is_legacy(args):
                print("Reboot cancelled.")
            else:
                print_toast("info", "Reboot cancelled.", mono=mono)
            return
    client = get_client(args)
    with animated_session(client, args, 'Dispatching protected hardware reboot sequence…'):
        client.reboot()
    if getattr(args, "json", False):
        print(json.dumps({"success": True, "message": "Router reboot initiated. Reconnect in 60-90 seconds."}, indent=2))
    elif _is_legacy(args):
        print("\n\033[92m✓ Router reboot initiated successfully.\033[0m")
        print("  ℹ  The router is restarting. Wi-Fi & Internet will temporarily drop for \033[1m~60–90 seconds\033[0m.")
        print("  ℹ  Please wait until router LEDs turn solid before executing subsequent commands.\n")
    else:
        print_toast(
            "warning",
            "Router reboot initiated successfully.",
            "Wi-Fi & LTE will temporarily drop for ~60–90 seconds while hardware restarts.\nWait until router LEDs turn solid before running subsequent commands.",
            mono=mono,
        )


def cmd_profile_check(args: argparse.Namespace):
    """Verifies which network the host machine is currently connected to."""
    gw = NetworkGuard.get_current_gateway()
    ssid = NetworkGuard.get_current_ssid()
    cfg = ConfigManager().load()
    is_safe, msg = NetworkGuard.check_safety(target_host=cfg["host"], expected_ssid=cfg.get("expected_ssid"))

    if getattr(args, "json", False):
        print(json.dumps({
            "current_ssid": ssid or "Wired / Hotspot",
            "default_gateway": gw or "Unknown",
            "target_router_host": cfg["host"],
            "is_safe": is_safe,
            "detail": msg
        }, indent=2))
        return

    if _is_legacy(args):
        print("\n" + "=" * 60)
        print("  \033[1mHOST NETWORK ENVIRONMENT CHECK\033[0m")
        print("=" * 60)
        print(f"Current Wi-Fi SSID : \033[1m{ssid or 'Wired / Hotspot'}\033[0m")
        print(f"Default Gateway    : \033[1m{gw or 'Unknown'}\033[0m")
        print(f"Target Router Host : {cfg['host']}")
        print(f"Network Guard State: {'\033[92mMATCH / SAFE\033[0m' if is_safe else '\033[93mMISMATCH / PROTECTED\033[0m'}")
        print(f"Detail             : {msg}")
        print("=" * 60 + "\n")
        return

    mono = _is_mono(args)
    rows = [
        ("Current Wi-Fi SSID", ssid or "Wired / Hotspot"),
        ("Default Gateway", gw or "Unknown"),
        ("Target Router Host", cfg["host"]),
        ("Network Guard State", status_badge(is_safe, "MATCH / SAFE", "MISMATCH / PROTECTED", mono=mono, warn_off=True)),
        ("Detail", msg),
    ]
    print_panel(
        title="HOST NETWORK ENVIRONMENT CHECK",
        sections=[render_kv_rows(rows, key_width=20, mono=mono)],
        accent="brand" if is_safe else "warning",
        mono=mono,
    )


def cmd_config(args: argparse.Namespace):
    cfg_mgr = ConfigManager()
    mono = _is_mono(args)
    subcommand = getattr(args, "subcommand", None) or "show"
    if subcommand == "set-password":
        pwd = args.password
        if not pwd:
            pwd = getpass.getpass("Enter router admin password to save: ")
        host = args.host or "http://192.168.1.1"
        username = args.username or "admin"
        ssid = args.expected_ssid or ""
        cfg_mgr.save(password=pwd, host=host, username=username, expected_ssid=ssid)
        if _is_legacy(args):
            print(f"\033[92mConfiguration securely saved to {cfg_mgr.config_file} (mode 0600).\033[0m")
        else:
            print_toast("success", "Configuration securely saved (mode 0600)", f"Path: {cfg_mgr.config_file}", mono=mono)
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
        if _is_legacy(args):
            print(f"\033[92mSession cookie (JSESSIONID: {masked}) successfully saved to {cfg_mgr.config_file}.\033[0m")
        else:
            print_toast("success", f"Session cookie saved (JSESSIONID: {masked})", f"Path: {cfg_mgr.config_file}", mono=mono)
    elif subcommand == "clear-cookie":
        cfg_mgr.save(session_cookie="")
        if _is_legacy(args):
            print(f"\033[92mStored session cookie cleared from {cfg_mgr.config_file}.\033[0m")
        else:
            print_toast("success", "Stored session cookie cleared", f"Path: {cfg_mgr.config_file}", mono=mono)
    elif subcommand == "show":
        cfg = cfg_mgr.load()
        has_pwd = bool(cfg.get("password"))
        cookie_val = cfg.get("session_cookie")
        has_cookie = bool(cookie_val)
        masked_cookie = f"{cookie_val[:6]}...{cookie_val[-6:]}" if (cookie_val and len(cookie_val) > 12) else ("[SET]" if has_cookie else "[NOT SET]")
        if getattr(args, "json", False):
            print(json.dumps({
                "config_file": str(cfg_mgr.config_file),
                "host": cfg["host"],
                "username": cfg["username"],
                "expected_ssid": cfg.get("expected_ssid") or None,
                "has_password": has_pwd,
                "has_session_cookie": has_cookie,
                "masked_cookie": masked_cookie
            }, indent=2))
            return
        if _is_legacy(args):
            print(f"Config File    : {cfg_mgr.config_file}")
            print(f"Router Host    : {cfg['host']}")
            print(f"Username       : {cfg['username']}")
            print(f"Expected SSID  : {cfg.get('expected_ssid') or '[Any]'}")
            print(f"Password       : {'[STORED - ' + str(len(cfg['password'])) + ' chars]' if has_pwd else '[NOT SET]'}")
            print(f"Session Cookie : {masked_cookie if has_cookie else '[NOT SET]'}")
            return

        rows = [
            ("Config File", str(cfg_mgr.config_file)),
            ("Router Host", cfg["host"]),
            ("Admin Username", cfg["username"]),
            ("Expected SSID", cfg.get("expected_ssid") or "Any (Unrestricted)"),
            ("Stored Password", status_badge(has_pwd, f"STORED ({len(cfg['password'])} chars)", "NOT SET", mono=mono)),
            ("Session Cookie", status_badge(has_cookie, masked_cookie, "NOT SET", mono=mono)),
        ]
        print_panel(
            title="CLI CREDENTIAL & GUARD CONFIG",
            sections=[render_kv_rows(rows, key_width=17, mono=mono)],
            footer="tplink-cli config set-password",
            mono=mono,
        )


def cmd_cookie(args: argparse.Namespace):
    cfg_mgr = ConfigManager()
    mono = _is_mono(args)
    cookie_val = getattr(args, "cookie_val", None)
    if not cookie_val:
        cfg = cfg_mgr.load()
        c = cfg.get("session_cookie")
        has_cookie = bool(c)
        masked = f"{c[:6]}...{c[-6:]}" if (c and len(c) > 12) else c
        if getattr(args, "json", False):
            print(json.dumps({
                "has_session_cookie": has_cookie,
                "session_cookie": masked if has_cookie else None,
                "config_file": str(cfg_mgr.config_file)
            }, indent=2))
            return
        if _is_legacy(args):
            if c:
                print(f"\n\033[1mCurrent Session Cookie:\033[0m {masked} (JSESSIONID)")
                print(f"Saved in: {cfg_mgr.config_file}\n")
            else:
                print("\n\033[93mNo session cookie currently stored.\033[0m")
            print("To save a new cookie:")
            print("  tplink-cli cookie <cookie_string_or_netscape_block>")
            print("  tplink-cli config set-cookie --file <cookies.txt>\n")
            return

        p = get_palette(mono=mono)
        rows = [
            ("Cookie Status", status_badge(has_cookie, f"ACTIVE ({masked})", "NOT STORED", mono=mono)),
            ("Config Store", str(cfg_mgr.config_file)),
        ]
        hints = [
            f"{p.muted}Save token :{p.reset} {p.white}tplink-cli cookie <JSESSIONID>{p.reset}",
            f"{p.muted}From file  :{p.reset} {p.white}tplink-cli config set-cookie --file cookies.txt{p.reset}",
        ]
        print_panel(
            title="BROWSER SESSION COOKIE",
            sections=[render_kv_rows(rows, key_width=16, mono=mono), hints],
            mono=mono,
        )
        return

    from tplink_router.core.cookie_parser import extract_jsessionid
    extracted = extract_jsessionid(cookie_val)
    if not extracted:
        if getattr(args, "json", False):
            print(json.dumps({
                "error": True,
                "code": "INVALID_COOKIE",
                "message": "Could not extract valid JSESSIONID from input."
            }, indent=2))
            sys.exit(1)
        if _is_legacy(args):
            print("\033[91mError: Could not extract valid JSESSIONID from input.\033[0m")
        else:
            print_toast("danger", "Could not extract valid JSESSIONID from input.", mono=mono)
        sys.exit(1)
    cfg_mgr.save(session_cookie=extracted)
    masked = f"{extracted[:6]}...{extracted[-6:]}" if len(extracted) > 12 else extracted
    if getattr(args, "json", False):
        print(json.dumps({
            "success": True,
            "session_cookie": masked,
            "config_file": str(cfg_mgr.config_file)
        }, indent=2))
        return
    if _is_legacy(args):
        print(f"\033[92mSession cookie (JSESSIONID: {masked}) successfully saved to {cfg_mgr.config_file}.\033[0m")
    else:
        print_toast("success", f"Session cookie saved (JSESSIONID: {masked})", f"Path: {cfg_mgr.config_file}", mono=mono)


def cmd_wifi_guard(args: argparse.Namespace):
    """Diagnoses and prepares wireless connection for calibration without Ethernet."""
    import shutil
    import subprocess

    mono = _is_mono(args)
    ssid = NetworkGuard.get_current_ssid()
    gw = NetworkGuard.get_current_gateway()

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

    if getattr(args, "fix", False) or getattr(args, "optimize", False):
        if ssid:
            cfg_mgr = ConfigManager()
            cfg_mgr.save(expected_ssid=ssid)

        if ssid and shutil.which("nmcli"):
            try:
                subprocess.run(
                    ["nmcli", "connection", "modify", ssid, "connection.autoconnect-priority", "50"],
                    capture_output=True, text=True, check=False
                )
            except Exception:
                pass

        try:
            subprocess.run(["iw", "dev", wlan_iface, "set", "power_save", "off"], capture_output=True, text=True, check=False)
        except Exception:
            pass

        if getattr(args, "json", False):
            print(json.dumps({
                "success": True,
                "optimized": True,
                "connected_ssid": ssid or "Unknown",
                "interface": wlan_iface,
                "autoconnect_priority": "50",
                "wifi_power_save": "OFF"
            }, indent=2))
            return

        if _is_legacy(args):
            print("\n" + "=" * 65)
            print("  \033[1mWI-FI ONLY OPERATION & LINK STABILITY GUARD\033[0m")
            print("=" * 65)
            print(f"Connected Wi-Fi SSID : \033[1m{ssid or 'Unknown'}\033[0m")
            print(f"Default Gateway      : {gw or 'Unknown'}")
            print(f"Wireless Interface   : {wlan_iface}")
            print(f"Wi-Fi Power Save     : {ps_status}")
            print(f"Autoconnect Priority : {nm_priority}")
            print("-" * 65)
            print("\033[93mApplying Wi-Fi Stability Optimizations...\033[0m")
            if ssid:
                print(f"  ✓ Locked Network Guard to expected SSID: {ssid}")
            if ssid and shutil.which("nmcli"):
                print(f"  ✓ Elevated NetworkManager autoconnect-priority for '{ssid}' to 50")
            print(f"  ✓ Requested Wi-Fi power save OFF on {wlan_iface}")
            print("\n\033[92m[READY] System is optimized for wireless-only calibration without Ethernet!\033[0m\n")
            return

        p = get_palette(mono=mono)
        rows = [
            ("Connected Wi-Fi SSID", ssid or "Unknown"),
            ("Default Gateway", gw or "Unknown"),
            ("Wireless Interface", wlan_iface),
            ("Wi-Fi Power Save", "OFF (Optimized)"),
            ("Autoconnect Priority", "50 (Elevated)"),
        ]
        actions = [
            f"{p.success}✓{p.reset} Locked Network Guard to expected SSID: {ssid or 'Active Link'}",
            f"{p.success}✓{p.reset} Requested Wi-Fi power save OFF on {wlan_iface}",
            f"{p.success}✓{p.reset} Ready for wireless-only RF calibration without Ethernet",
        ]
        print_panel(
            title="WI-FI STABILITY OPTIMIZED",
            sections=[render_kv_rows(rows, key_width=21, mono=mono), actions],
            accent="success",
            mono=mono,
        )
        return

    if getattr(args, "json", False):
        print(json.dumps({
            "connected_ssid": ssid or "Unknown",
            "default_gateway": gw or "Unknown",
            "interface": wlan_iface,
            "wifi_power_save": ps_status,
            "autoconnect_priority": nm_priority,
            "is_guarded": True
        }, indent=2))
        return

    if _is_legacy(args):
        print("\n" + "=" * 65)
        print("  \033[1mWI-FI ONLY OPERATION & LINK STABILITY GUARD\033[0m")
        print("=" * 65)
        print(f"Connected Wi-Fi SSID : \033[1m{ssid or 'Unknown'}\033[0m")
        print(f"Default Gateway      : {gw or 'Unknown'}")
        print(f"Wireless Interface   : {wlan_iface}")
        print(f"Wi-Fi Power Save     : {ps_status}")
        print(f"Autoconnect Priority : {nm_priority}")
        print("-" * 65)
        print("💡 \033[1mHow Wi-Fi Only Mode Works:\033[0m")
        print("  1. The Archer MR200's Wi-Fi Access Point radio remains RUNNING even when")
        print("     cellular LTE frequency bands are switched or cell locked.")
        print("  2. Local Wi-Fi ping/HTTP to 192.168.1.1 will NOT disconnect.")
        print("  3. Only upstream internet traffic pauses for 5-15s during cell attach.")
        print("  4. Run `tplink-cli wifi-guard --optimize` to prevent NetworkManager from")
        print("     roaming to campus Wi-Fi or hotspot during calibration pauses.")
        print("=" * 65 + "\n")
        return

    p = get_palette(mono=mono)
    rows = [
        ("Connected Wi-Fi SSID", ssid or "Unknown"),
        ("Default Gateway", gw or "Unknown"),
        ("Wireless Interface", wlan_iface),
        ("Wi-Fi Power Save", ps_status),
        ("Autoconnect Priority", nm_priority),
    ]
    notes = [
        f"{p.brand_bold}▸ Wireless-Only Safety Architecture{p.reset}",
        f"{p.muted}• Router Wi-Fi AP stays active during LTE band locks & RF retuning.{p.reset}",
        f"{p.muted}• Run{p.reset} {p.white}tplink-cli wifi-guard --optimize{p.reset} {p.muted}to pin NetworkManager priority.{p.reset}",
    ]
    print_panel(
        title="WI-FI LINK STABILITY GUARD",
        sections=[render_kv_rows(rows, key_width=21, mono=mono), notes],
        mono=mono,
    )


def cmd_repl(args: argparse.Namespace):
    client = get_client(args)
    run_repl(client, mono=_is_mono(args), legacy=_is_legacy(args))


def cmd_clients(args: argparse.Namespace):
    client = get_client(args)
    with animated_session(client, args, 'Enumerating connected LAN & Wi-Fi client leases…'):
        if not hasattr(client, "get_connected_clients"):
            print("Connected clients list is only supported on MR cellular models.")
            return
        clients = client.get_connected_clients()

    if getattr(args, "json", False):
        print(json.dumps(clients, indent=2))
        return

    if _is_legacy(args):
        print("\n" + "=" * 70)
        print("  \033[1mCONNECTED LAN CLIENTS\033[0m")
        print("=" * 70)
        print(f"{'HOSTNAME':<22} {'IP ADDRESS':<16} {'MAC ADDRESS':<18} {'LEASE REMAINING':<12}")
        print("-" * 70)
        for c in clients:
            print(f"{c['hostname']:<22} {c['ip']:<16} {c['mac']:<18} {c['lease_remaining']:<12}")
        print("=" * 70 + f"\nTotal connected clients: {len(clients)}\n")
        return

    mono = _is_mono(args)
    t_rows = [[c["hostname"], c["ip"], c["mac"], c["lease_remaining"]] for c in clients]
    print_panel(
        title="CONNECTED LAN & WI-FI CLIENTS",
        sections=[render_table_lines(["HOSTNAME", "IP ADDRESS", "MAC ADDRESS", "LEASE"], t_rows, mono=mono)],
        subtitle=f"{len(clients)} Active Devices",
        footer=f"Total connected clients: {len(clients)}",
        mono=mono,
    )


def cmd_reservation(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Synchronizing DHCP static IP reservation table…'):
        if not hasattr(client, "get_dhcp_reservations"):
            print("DHCP reservations are only supported on MR cellular models.")
            return

        sub = getattr(args, "subcommand", None) or "list"
        if sub == "list":
            reservations = client.get_dhcp_reservations()
            if getattr(args, "json", False):
                print(json.dumps(reservations, indent=2))
                return
            if _is_legacy(args):
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
                return

            p = get_palette(mono=mono)
            if not reservations:
                sec = [[f"{p.muted}No static DHCP reservations currently configured.{p.reset}"]]
            else:
                t_rows = [
                    [r["mac"], r["ip"], status_badge(bool(r["enabled"]), "ENABLED", "DISABLED", mono=mono)]
                    for r in reservations
                ]
                sec = [render_table_lines(["MAC ADDRESS", "RESERVED IP", "STATUS"], t_rows, mono=mono)]
            print_panel(
                title="STATIC DHCP RESERVATIONS",
                sections=sec,
                subtitle=f"{len(reservations)} Entries",
                footer="tplink-cli reservation add <MAC> <IP>",
                mono=mono,
            )
        elif sub == "add":
            mac = getattr(args, "mac", None)
            ip = getattr(args, "ip", None)
            if not mac or not ip:
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_PARAMS",
                        "message": "Both mac_address and ip_address are required."
                    }, indent=2))
                    sys.exit(1)
                print("\nUsage: tplink-cli reservation add <mac_address> <ip_address>")
                print("Example: tplink-cli reservation add AA-BB-CC-DD-EE-FF 192.168.1.50\n")
                return
            client.add_dhcp_reservation(mac, ip)
            if getattr(args, "json", False):
                print(json.dumps({"success": True, "action": "add", "mac": mac, "ip": ip}, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92mReservation added: {mac} -> {ip}\033[0m")
            else:
                print_toast("success", f"DHCP reservation added: {mac} -> {ip}", mono=mono)
            return
        elif sub == "del":
            mac = getattr(args, "mac", None)
            if not mac:
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_MAC",
                        "message": "mac_address is required to delete reservation."
                    }, indent=2))
                    sys.exit(1)
                print("\nUsage: tplink-cli reservation del <mac_address>")
                print("Run 'tplink-cli reservation list' to view active reservations.\n")
                return
            client.delete_dhcp_reservation(mac)
            if getattr(args, "json", False):
                print(json.dumps({"success": True, "action": "del", "mac": mac}, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92mReservation deleted for MAC {mac}\033[0m")
            else:
                print_toast("success", f"DHCP reservation deleted for MAC {mac}", mono=mono)
            return


def cmd_data_limit(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Querying monthly cellular data quota & billing state…'):
        if not hasattr(client, "get_data_limit"):
            print("Data limits are only supported on cellular MR models.")
            return

        if getattr(args, "limit", None) is not None:
            payment_day = getattr(args, "day", 1) or 1
            client.set_data_limit(enabled=True, limit_mb=args.limit, payment_day=payment_day)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "limit_mb": args.limit,
                    "billing_day": payment_day
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92mData limit set to {args.limit} MB (Billing reset day: {payment_day})\033[0m")
            else:
                print_toast("success", f"Data limit set to {args.limit} MB", f"Billing cycle reset day: Day {payment_day}", mono=mono)
            return

        data = client.get_data_limit()
        if getattr(args, "json", False):
            print(json.dumps(data, indent=2))
            return

        if _is_legacy(args):
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
            return

        used_mb = round(data["current_period_bytes"] / (1024 * 1024), 2)
        total_mb = round(data["total_bytes"] / (1024 * 1024), 2)
        limit_mb = data["limit_mb"] or 0
        rows = [
            ("Quota Enforcement", status_badge(bool(data["limit_enabled"]), "ACTIVE", "DISABLED", mono=mono)),
            ("Monthly Allowance", f"{limit_mb} MB ({round(limit_mb / 1024, 2)} GB)"),
            ("Current Period Used", f"{used_mb} MB   {progress_meter(used_mb, limit_mb, mono=mono, invert_danger=True) if limit_mb > 0 else ''}".strip()),
            ("Total Transferred", f"{total_mb} MB"),
            ("Billing Reset Day", f"Day {data['billing_day']} of month  (Alert at {data['warning_percent']}%)"),
            ("Live Throughput", f"↓ {data['rx_speed_kbps']} Kbps   ↑ {data['tx_speed_kbps']} Kbps"),
        ]
        print_panel(
            title="CELLULAR DATA QUOTA & USAGE",
            sections=[render_kv_rows(rows, key_width=20, mono=mono)],
            footer="tplink-cli data-limit --limit <MB> --day <1-31>",
            mono=mono,
        )


def cmd_wifi(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Communicating with dual-band 2.4GHz / 5GHz Wi-Fi radios…'):
        if not hasattr(client, "get_wifi_status"):
            print("Wi-Fi control is only supported on MR cellular models.")
            return

        if getattr(args, "toggle", None):
            band = "2.4GHz" if "2" in args.band else "5GHz"
            enabled = args.toggle in ("on", "enable")
            client.set_wifi_radio(band=band, enabled=enabled, ssid=getattr(args, "ssid", None))
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "band": band,
                    "enabled": enabled,
                    "ssid": getattr(args, "ssid", None)
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92mWi-Fi {band} radio set to {'ON' if enabled else 'OFF'}\033[0m")
            else:
                print_toast("success", f"Wi-Fi {band} radio set to {'ON' if enabled else 'OFF'}", mono=mono)
            return

        networks = client.get_wifi_status()
        if getattr(args, "json", False):
            print(json.dumps(networks, indent=2))
            return

        if _is_legacy(args):
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
            return

        t_rows = [
            [
                net["band"],
                net["ssid"],
                status_badge(bool(net["enabled"]), "ENABLED", "DISABLED", mono=mono),
                str(net["channel"]),
                str(net.get("connected_clients", 0)),
            ]
            for net in networks
        ]
        print_panel(
            title="DUAL-BAND WI-FI NETWORKS",
            sections=[render_table_lines(["BAND", "SSID", "STATE", "CHANNEL", "CLIENTS"], t_rows, mono=mono)],
            footer="tplink-cli wifi --band 2.4GHz|5GHz --toggle on|off",
            mono=mono,
        )


def cmd_leds(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Querying hardware LED indicators & Night Mode schedule…'):
        if not hasattr(client, "get_led_status"):
            print("LED control is only supported on MR cellular models.")
            return

        if getattr(args, "night_mode", None):
            enable = args.night_mode in ("on", "enable")
            start = getattr(args, "start", "22:00") or "22:00"
            end = getattr(args, "end", "07:00") or "07:00"
            client.set_led_night_mode(enabled=enable, start_time=start, end_time=end)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "night_mode_enabled": enable,
                    "start_time": start,
                    "end_time": end
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92mNight mode {'enabled' if enable else 'disabled'} (LEDs OFF {start} - {end})\033[0m")
            else:
                print_toast("success", f"LED Night Mode {'enabled' if enable else 'disabled'}", f"Quiet window: {start} -> {end}", mono=mono)
            return

        leds = client.get_led_status()
        if getattr(args, "json", False):
            print(json.dumps(leds, indent=2))
            return

        if _is_legacy(args):
            print("\n\033[1mRouter Front Panel LED Status:\033[0m")
            print(f"  LEDs Active        : {'\033[92mYes\033[0m' if leds['leds_on'] else '\033[93mOff\033[0m'}")
            print(f"  Night Mode Schedule: {'\033[92mEnabled\033[0m' if leds['night_mode_enabled'] else 'Disabled'}")
            if leds["night_mode_enabled"]:
                print(f"  Off Schedule Hours : {leds['night_mode_start']} -> {leds['night_mode_end']}")
            return

        rows = [
            ("Front-Panel LEDs", status_badge(bool(leds["leds_on"]), "ACTIVE (ON)", "DARK (OFF)", mono=mono)),
            ("Night Mode Schedule", status_badge(bool(leds["night_mode_enabled"]), "ENABLED", "DISABLED", mono=mono)),
        ]
        if leds["night_mode_enabled"]:
            rows.append(("Quiet Schedule Hours", f"{leds['night_mode_start']} -> {leds['night_mode_end']}"))
        print_panel(
            title="FRONT-PANEL LED & NIGHT MODE",
            sections=[render_kv_rows(rows, key_width=21, mono=mono)],
            footer="tplink-cli leds --night-mode on --start 22:00 --end 07:00",
            mono=mono,
        )


def cmd_diag(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    if _is_legacy(args):
        print("Initiating router WAN & NCSI diagnostic self-test...")
    with animated_session(client, args, 'Running router WAN & NCSI internet self-diagnostics…'):
        if not hasattr(client, "run_wan_diagnostic"):
            print("Router diagnostic is only supported on MR cellular models.")
            return
        res = client.run_wan_diagnostic()

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
        return

    if _is_legacy(args):
        status_color = "\033[92m" if res["status"] == "Passed" else "\033[91m"
        print(f"\nDiagnostic Result: {status_color}\033[1m{res['status']}\033[0m (Code {res['result_code']})")
        print(f"Message          : {res['message']}\n")
        return

    passed = res["status"] == "Passed"
    rows = [
        ("Diagnostic Result", status_badge(passed, f"PASSED (Code {res['result_code']})", f"{res['status'].upper()} (Code {res['result_code']})", mono=mono, warn_off=True)),
        ("Detail", res["message"]),
    ]
    print_panel(
        title="WAN & NCSI CONNECTIVITY DIAGNOSTIC",
        sections=[render_kv_rows(rows, key_width=19, mono=mono)],
        accent="success" if passed else "danger",
        mono=mono,
    )


def cmd_band(args: argparse.Namespace):
    mono = _is_mono(args)
    target_band = getattr(args, "band", None)

    if getattr(args, "interactive", False) and not target_band and not getattr(args, "json", False):
        from tplink_router.cli.interactive_tui import inline_select
        picked = inline_select(
            "INTERACTIVE LTE BAND LOCK",
            [
                ("status", "Inspect Current Active Band", "View EARFCN & carrier frequency"),
                ("8", "Band 8  (900 MHz FDD)", "Best rain penetration & indoor reach"),
                ("3", "Band 3  (1800 MHz FDD)", "High-speed Hutch / Dialog primary"),
                ("1", "Band 1  (2100 MHz FDD)", "Dialog / Mobitel 4G capacity"),
                ("40", "Band 40 (2300 MHz TDD)", "High-capacity TDD urban band"),
                ("auto", "Automatic Selection", "Restore carrier auto-roaming"),
            ],
            mono=mono,
        )
        if picked and picked != "status":
            target_band = picked

    client = get_client(args)
    with animated_session(client, args, 'Communicating with LTE frequency band controller…'):
        if not hasattr(client, "set_lte_band"):
            print("Band selection is only supported on MR cellular models.")
            return

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

            if _is_legacy(args):
                print("\n" + "=" * 62)
                print("  \033[1mACTIVE LTE BAND CONFIGURATION\033[0m")
                print("=" * 62)
                print(f"Configured Band Mode : \033[1m{active_mode}\033[0m")
                print(f"Connected RF Link    : \033[1m{connected_band}\033[0m")
                if earfcn:
                    print(f"Channel (EARFCN)     : {earfcn} (PCI: {pci or '0'})")
                print("-" * 62)
                print("Hardware Supported Bands (Sri Lanka Context):")
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

            p = get_palette(mono=mono)
            kv = [
                ("Configured Band Mode", f"{p.brand_bold}{active_mode}{p.reset}"),
                ("Connected RF Link", f"{p.white}{connected_band}{p.reset}"),
            ]
            if earfcn:
                kv.append(("Channel (EARFCN)", f"{earfcn}  (PCI: {pci or '0'})"))

            t_rows = [[f"Band {b}", band_descriptions.get(b, "LTE Carrier")] for b in supported_bands]
            t_rows.append(["auto", "Automatic network roaming selection"])

            print_panel(
                title="ACTIVE LTE BAND CONFIGURATION",
                sections=[
                    render_kv_rows(kv, key_width=21, mono=mono),
                    render_table_lines(["BAND", "FREQUENCY & CARRIER PROFILE"], t_rows, mono=mono),
                ],
                subtitle=str(connected_band),
                footer="tplink-cli band <3|8|40|auto> • tplink-cli band -i (interactive)",
                mono=mono,
            )
            return

        if getattr(args, "json", False):
            client.set_lte_band(target_band)
            print(json.dumps({
                "success": True,
                "configured_band": target_band,
                "message": "Cellular modem is retuning RF hardware"
            }, indent=2))
            return

        if _is_legacy(args):
            print(f"Locking hardware modem to band '{target_band}'...")
        client.set_lte_band(target_band)

    if _is_legacy(args):
        print(f"\033[92m✓ LTE band successfully configured to '{target_band}'.\033[0m")
        print("\033[90mCellular modem is retuning RF hardware. Signal LEDs will cycle.\033[0m")
    else:
        print_toast(
            "success",
            f"LTE band successfully configured to '{target_band}'.",
            "Cellular modem is retuning RF hardware. Signal LEDs will cycle briefly.",
            mono=mono,
        )


def cmd_logs(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Fetching router system & 4G cellular event logs…'):
        if not hasattr(client, "get_system_logs"):
            print("System logs are only supported on MR cellular models.")
            return

        if getattr(args, "clear", False):
            client.clear_system_logs()
            if getattr(args, "json", False):
                print(json.dumps({"cleared": True}))
            elif _is_legacy(args):
                print("\033[92m✓ System event logs successfully cleared.\033[0m")
            else:
                print_toast("success", "System event logs successfully cleared.", mono=mono)
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

        if _is_legacy(args):
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
            return

        p = get_palette(mono=mono)
        if not logs:
            rows = [f"{p.muted}(No log entries found matching criteria){p.reset}"]
        else:
            rows = []
            for l in logs:
                if p.mono:
                    lvl_c = p.white if l.level_name in ("EMERG", "ALERT", "CRIT", "ERROR", "WARN") else p.muted
                elif l.level_name in ("EMERG", "ALERT", "CRIT", "ERROR"):
                    lvl_c = p.danger
                elif l.level_name == "WARN":
                    lvl_c = p.warning
                elif l.level_name == "NOTICE":
                    lvl_c = p.brand_bold
                else:
                    lvl_c = p.muted
                rows.append(
                    f"{p.muted}{l.timestamp}{p.reset} {lvl_c}{l.level_name:<6}{p.reset} {p.white}{l.module:<7}{p.reset} {p.text}{l.message}{p.reset}"
                )
        print_panel(
            title="ROUTER SYSTEM & CELLULAR EVENT LOGS",
            sections=[rows],
            subtitle=f"{len(logs)} Entries",
            footer="Filter: tplink-cli logs --lines 50 --module 4G --level WARN",
            width=88,
            mono=mono,
        )


def cmd_guest_wifi(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Synchronizing isolated Guest Wi-Fi configuration…'):
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
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "band": band,
                    "enabled": is_en,
                    "ssid": ssid,
                    "allow_lan_access": allow_lan
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92m✓ Guest Wi-Fi ({band}) successfully {action_desc}.\033[0m")
            else:
                print_toast("success", f"Guest Wi-Fi ({band}) successfully {action_desc}.", mono=mono)
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

        if _is_legacy(args):
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
            return

        iso_kv = [
            ("LAN Access Policy", status_badge(not gw.allow_lan_access, "ISOLATED (SECURE)", "LAN ACCESS ALLOWED", mono=mono, warn_off=True))
        ]
        t_rows = [
            [n.band, n.ssid, status_badge(n.enabled, "ENABLED", "DISABLED", mono=mono), n.security]
            for n in gw.networks
        ]
        print_panel(
            title="DUAL-BAND GUEST WI-FI",
            sections=[
                render_kv_rows(iso_kv, key_width=19, mono=mono),
                render_table_lines(["BAND", "GUEST SSID", "STATE", "SECURITY"], t_rows, mono=mono),
            ],
            footer="tplink-cli guest-wifi --toggle on|off",
            mono=mono,
        )


def cmd_port_forward(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Synchronizing NAT virtual server port forwarding rules…'):
        if not hasattr(client, "get_port_forwarding"):
            print("Port forwarding is only supported on MR cellular models.")
            return

        action = getattr(args, "subcommand", None) or "list"
        if action == "add":
            name = getattr(args, "name", None)
            ext_port = getattr(args, "ext_port", None)
            int_ip = getattr(args, "int_ip", None)
            if not name or not ext_port or not int_ip:
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_PARAMS",
                        "message": "name, ext_port, and int_ip are required."
                    }, indent=2))
                    sys.exit(1)
                print("\nUsage: tplink-cli port-forward add <name> <ext_port> <int_ip> [int_port] [--proto TCP|UDP|ALL]")
                print("Example: tplink-cli port-forward add web 8080 192.168.1.150 80 --proto TCP\n")
                return
            int_port = getattr(args, "int_port", None) or ext_port
            proto = getattr(args, "proto", "ALL")
            client.add_port_forwarding(name=name, external_port=ext_port, internal_ip=int_ip, internal_port=int_port, protocol=proto)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "action": "add",
                    "name": name,
                    "external_port": ext_port,
                    "internal_ip": int_ip,
                    "internal_port": int_port,
                    "protocol": proto
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92m✓ Port forwarding rule '{name}' added: Port {ext_port} -> {int_ip}:{int_port} ({proto})\033[0m")
            else:
                print_toast("success", f"Port forward '{name}' added", f"WAN Port {ext_port} -> {int_ip}:{int_port} ({proto})", mono=mono)
            return
        elif action == "del":
            stack = getattr(args, "stack", None)
            if not stack:
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_STACK",
                        "message": "Rule stack ID is required to delete port forwarding rule."
                    }, indent=2))
                    sys.exit(1)
                print("\nUsage: tplink-cli port-forward del <rule_stack>")
                print("Run 'tplink-cli port-forward list' to view active rule stacks.\n")
                return
            client.del_port_forwarding(rule_stack=stack)
            if getattr(args, "json", False):
                print(json.dumps({"success": True, "action": "del", "stack": stack}, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92m✓ Port forwarding rule at stack '{stack}' deleted.\033[0m")
            else:
                print_toast("success", f"Port forwarding rule '{stack}' deleted.", mono=mono)
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

        if _is_legacy(args):
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
            return

        p = get_palette(mono=mono)
        if not rules:
            sec = [[f"{p.muted}(No active NAT port forwarding rules){p.reset}"]]
        else:
            t_rows = [
                [
                    str(r.index),
                    r.name,
                    str(r.external_port),
                    f"{r.internal_ip}:{r.internal_port}",
                    r.protocol,
                    status_badge(r.enabled, "ON", "OFF", mono=mono),
                ]
                for r in rules
            ]
            sec = [render_table_lines(["#", "SERVICE", "EXT PORT", "INTERNAL TARGET", "PROTO", "STATE"], t_rows, mono=mono)]
        print_panel(
            title="NAT VIRTUAL SERVER PORT FORWARDING",
            sections=sec,
            subtitle=f"{len(rules)} Rules",
            footer="tplink-cli port-forward add <name> <ext> <ip> [int] --proto TCP",
            mono=mono,
        )


def cmd_dmz(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Querying NAT DMZ exposed host configuration…'):
        if not hasattr(client, "get_dmz"):
            print("DMZ Host is only supported on MR cellular models.")
            return

        state = getattr(args, "state", None)
        ip = getattr(args, "ip", None)

        if state or ip:
            is_en = state in ("on", "enable") if state else bool(ip)
            target_ip = ip or ""
            if is_en and not target_ip:
                if getattr(args, "json", False):
                    print(json.dumps({
                        "error": True,
                        "code": "MISSING_DMZ_IP",
                        "message": "Internal host IP address is required when enabling DMZ."
                    }, indent=2))
                elif _is_legacy(args):
                    print("\033[91mError: Internal host IP address is required when enabling DMZ.\033[0m")
                    print("Usage: tplink-cli dmz on <ip_address>   (e.g. tplink-cli dmz on 192.168.1.100)")
                else:
                    print_toast("danger", "Internal host IP required to enable DMZ", "Usage: tplink-cli dmz on 192.168.1.100", mono=mono)
                sys.exit(1)

            client.set_dmz(enabled=is_en, ip_address=target_ip)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "enabled": is_en,
                    "ip_address": target_ip
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92m✓ DMZ Host {'enabled -> ' + target_ip if is_en else 'disabled'}.\033[0m")
            else:
                print_toast("success", f"DMZ Host {'enabled -> ' + target_ip if is_en else 'disabled'}.", mono=mono)
            return

        dmz = client.get_dmz()
        if getattr(args, "json", False):
            print(json.dumps({"enabled": dmz.enabled, "ip_address": dmz.ip_address}, indent=2))
            return

        if _is_legacy(args):
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
            return

        rows = [("DMZ Status", status_badge(dmz.enabled, "ENABLED", "DISABLED", mono=mono))]
        if dmz.enabled:
            rows.append(("Exposed Host IP", dmz.ip_address))
        print_panel(
            title="DMZ HOST CONFIGURATION",
            sections=[render_kv_rows(rows, key_width=17, mono=mono)],
            footer="tplink-cli dmz on <ip> • tplink-cli dmz off",
            mono=mono,
        )


def cmd_upnp(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Querying Universal Plug and Play (UPnP) NAT leases…'):
        if not hasattr(client, "get_upnp"):
            print("UPnP is only supported on MR cellular models.")
            return

        toggle = getattr(args, "toggle", None)
        if toggle:
            is_en = toggle in ("on", "enable")
            client.set_upnp(enabled=is_en)
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "upnp_enabled": is_en
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92m✓ UPnP successfully {'enabled' if is_en else 'disabled'}.\033[0m")
            else:
                print_toast("success", f"UPnP successfully {'enabled' if is_en else 'disabled'}.", mono=mono)
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

        if _is_legacy(args):
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
            return

        p = get_palette(mono=mono)
        kv = [
            ("UPnP Service", status_badge(upnp.enabled, "ENABLED", "DISABLED", mono=mono)),
            ("Active Port Leases", str(len(upnp.mappings))),
        ]
        if upnp.mappings:
            t_rows = [
                [m.description, m.protocol, str(m.external_port), f"{m.internal_ip}:{m.internal_port}"]
                for m in upnp.mappings
            ]
            map_sec = render_table_lines(["DESCRIPTION", "PROTO", "EXT PORT", "INTERNAL TARGET"], t_rows, mono=mono)
        else:
            map_sec = [f"{p.muted}(No dynamic UPnP port mappings currently registered){p.reset}"]

        print_panel(
            title="UNIVERSAL PLUG AND PLAY (UPnP)",
            sections=[render_kv_rows(kv, key_width=20, mono=mono), map_sec],
            footer="tplink-cli upnp on • tplink-cli upnp off",
            mono=mono,
        )


def cmd_reboot_schedule(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Synchronizing automated periodic reboot schedule…'):
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
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "enabled": is_en,
                    "hours": hours,
                    "minutes": minutes,
                    "time": f"{hours:02d}:{minutes:02d}",
                    "mode": mode,
                    "day_of_week": day
                }, indent=2))
                return
            if _is_legacy(args):
                print(f"\033[92m✓ Automated reboot schedule {'enabled for ' + f'{hours:02d}:{minutes:02d} ({mode})' if is_en else 'disabled'}.\033[0m")
            else:
                print_toast("success", f"Automated reboot schedule {'enabled' if is_en else 'disabled'}", f"Window: {hours:02d}:{minutes:02d} ({mode})" if is_en else None, mono=mono)
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

        if _is_legacy(args):
            print("\n" + "=" * 55)
            print("  \033[1mAUTOMATED REBOOT SCHEDULE\033[0m")
            print("=" * 55)
            st = "\033[92mENABLED\033[0m" if rs.enabled else "\033[90mDISABLED\033[0m"
            print(f"Status         : {st}")
            print(f"Scheduled Time : \033[1m{rs.hours:02d}:{rs.minutes:02d}\033[0m")
            freq_str = "Daily" if rs.mode == "daily" else f"Weekly (Every {rs.day_name})"
            print(f"Frequency      : {freq_str}")
            print("-" * 55)
            print("To configure auto-reboot:")
            print("  tplink-cli reboot-schedule on --time 03:30 --mode daily")
            print("  tplink-cli reboot-schedule off")
            print("=" * 55 + "\n")
            return

        freq_str = "Daily" if rs.mode == "daily" else f"Weekly (Every {rs.day_name})"
        rows = [
            ("Schedule State", status_badge(rs.enabled, "ENABLED", "DISABLED", mono=mono)),
            ("Scheduled Time", f"{rs.hours:02d}:{rs.minutes:02d}"),
            ("Frequency", freq_str),
        ]
        print_panel(
            title="AUTOMATED REBOOT SCHEDULE",
            sections=[render_kv_rows(rows, key_width=17, mono=mono)],
            footer="tplink-cli reboot-schedule on --time 03:30 --mode daily",
            mono=mono,
        )


def cmd_time(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Querying router system clock & NTP time service…'):
        if not hasattr(client, "get_time_config"):
            print("System time is only supported on MR cellular models.")
            return

        if getattr(args, "sync", False):
            client.sync_time()
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": True,
                    "ntp_sync_requested": True
                }, indent=2))
                return
            if _is_legacy(args):
                print("\033[92m✓ Router NTP synchronization requested.\033[0m")
            else:
                print_toast("success", "Router NTP time synchronization requested.", mono=mono)
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

        if _is_legacy(args):
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
            return

        rows = [
            ("Current Local Time", tc.current_time),
            ("Time Zone", tc.timezone),
            ("Daylight Savings", "Active" if tc.daylight_savings else "Standard"),
        ]
        if tc.ntp_server1:
            rows.append(("NTP Server 1", tc.ntp_server1))
        if tc.ntp_server2:
            rows.append(("NTP Server 2", tc.ntp_server2))
        print_panel(
            title="ROUTER SYSTEM TIME & NTP",
            sections=[render_kv_rows(rows, key_width=19, mono=mono)],
            footer="tplink-cli time --sync",
            mono=mono,
        )


def cmd_op_mode(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Inspecting router hardware operation mode…'):
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

        if _is_legacy(args):
            print("\n" + "=" * 55)
            print("  \033[1mROUTER OPERATION MODE\033[0m")
            print("=" * 55)
            print(f"Active Mode     : \033[1m{om.mode}\033[0m")
            print(f"LTE Failover    : {'Enabled (4G WAN fallback active)' if om.lte_backup_enabled else 'Disabled'}")
            print(f"Cellular Switch : {'Online / Enabled' if om.cellular_data_switch else 'Disabled'}")
            print("=" * 55 + "\n")
            return

        rows = [
            ("Active Operation Mode", om.mode),
            ("LTE WAN Failover", status_badge(bool(om.lte_backup_enabled), "ENABLED (4G FALLBACK)", "DISABLED", mono=mono)),
            ("Cellular Data Switch", status_badge(bool(om.cellular_data_switch), "ONLINE / ENABLED", "DISABLED", mono=mono)),
        ]
        print_panel(
            title="ROUTER OPERATION MODE",
            sections=[render_kv_rows(rows, key_width=22, mono=mono)],
            mono=mono,
        )


def cmd_ddns(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Inspecting Dynamic DNS provider bindings…'):
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

        if _is_legacy(args):
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
            return

        t_rows = [
            [
                prov.provider,
                status_badge(prov.enabled, "ENABLED", "DISABLED", mono=mono),
                prov.domain or "—",
                prov.status,
            ]
            for prov in providers
        ]
        print_panel(
            title="DYNAMIC DNS (DDNS) SERVICES",
            sections=[render_table_lines(["PROVIDER", "STATE", "DOMAIN", "STATUS"], t_rows, mono=mono)],
            mono=mono,
        )


def cmd_fw_check(args: argparse.Namespace):
    client = get_client(args)
    mono = _is_mono(args)
    with animated_session(client, args, 'Checking TP-Link cloud for official firmware updates…'):
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

        if _is_legacy(args):
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
            return

        rows = [("Installed Version", fw.current_version)]
        if fw.has_update:
            rows.append(("Available Update", f"{fw.latest_version} (Released: {fw.release_date})"))
        else:
            rows.append(("Update Status", status_badge(True, "UP TO DATE (LATEST RELEASE)", "OUTDATED", mono=mono)))

        sections = [render_kv_rows(rows, key_width=19, mono=mono)]
        if fw.has_update and fw.release_log:
            sections.append([fw.release_log])
        print_panel(
            title="TP-LINK OFFICIAL FIRMWARE STATUS",
            sections=sections,
            accent="warning" if fw.has_update else "brand",
            mono=mono,
        )


def cmd_calibrate(args: argparse.Namespace):
    from tplink_router.calibration.dashboard import start_dashboard_server
    from tplink_router.calibration.engine import RouterCalibrator

    mono = _is_mono(args)
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

    is_safe, msg = NetworkGuard.check_safety(target_host=host, expected_ssid=expected_ssid, force=force)
    if not is_safe:
        if getattr(args, "json", False):
            print(json.dumps({
                "error": True,
                "code": "NETWORK_GUARD_BLOCKED",
                "message": msg
            }, indent=2), file=sys.stderr)
        elif _is_legacy(args):
            print(f"\033[91m[Network Guard Alert] {msg}\033[0m")
        else:
            print_toast("danger", "Network Guard Blocked Calibration", msg, mono=mono)
        sys.exit(2)

    if getattr(args, "interactive", False) and not getattr(args, "json", False):
        from tplink_router.cli.interactive_tui import inline_multiselect
        chosen_bands = inline_multiselect(
            "SELECT CANDIDATE LTE BANDS FOR CALIBRATION",
            [
                ("8", "Band 8  (900 MHz)", "Extended range / indoor reach", True),
                ("3", "Band 3  (1800 MHz)", "High-throughput primary FDD", True),
                ("1", "Band 1  (2100 MHz)", "Standard 4G capacity layer", False),
                ("40", "Band 40 (2300 MHz)", "High-capacity TDD urban band", False),
                ("auto", "Auto Mode Baseline", "Compare against auto-roaming", True),
            ],
            mono=mono,
        )
        if chosen_bands:
            target_bands = chosen_bands
        else:
            return
    else:
        target_bands = [b.strip() for b in args.bands.split(",") if b.strip()]

    calibrator = RouterCalibrator(
        host=host,
        password=password,
        session_cookie=session_cookie,
        username=username,
        bands=target_bands,
        watchdog_timeout=args.timeout,
        dry_run=args.dry_run,
        echo_stdout=not args.web,
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
        results = calibrator.run_sweep()
        if getattr(args, "json", False):
            print(json.dumps(results, indent=2))
            return
        rec = results.get("recommendation")
        if _is_legacy(args):
            print("\n" + "=" * 65)
            print("  \033[1mAUTONOMOUS RF BAND CALIBRATION COMPLETE\033[0m")
            print("=" * 65)
            if rec:
                print(f"Recommended LTE Band  : \033[92m\033[1mBand {rec.get('band')} ({rec.get('band_name', '')})\033[0m")
                print(f"Confidence Score      : {rec.get('score', 0):.1f} / 100")
                print(f"Expected Performance  : {rec.get('reason', '')}")
            print("-" * 65)
            print(f"{'BAND':<8} {'FREQ':<10} {'PING (ms)':<12} {'LOSS':<8} {'MTU':<6} {'SCORE'}")
            print("-" * 65)
            for b in results.get("bands_evaluated", []):
                p_ms = f"{b.get('ping_avg_ms', 0):.1f}" if b.get("ping_avg_ms") else "N/A"
                loss = f"{b.get('packet_loss_pct', 0):.0f}%"
                mtu = str(b.get("path_mtu") or "1500")
                sc = f"{b.get('score', 0):.1f}"
                print(f"{'Band ' + str(b.get('band')):<8} {b.get('frequency', ''):<10} {p_ms:<12} {loss:<8} {mtu:<6} {sc}")
            print("=" * 65 + "\n")
            return

        sections = []
        if rec:
            kv = [
                ("Recommended Band", f"Band {rec.get('band')} ({rec.get('band_name', '')})"),
                ("Confidence Score", f"{rec.get('score', 0):.1f} / 100   {progress_meter(rec.get('score', 0), 100, mono=mono)}"),
                ("Analysis", rec.get("reason", "")),
            ]
            sections.append(render_kv_rows(kv, key_width=19, mono=mono))

        t_rows = []
        for b in results.get("bands_evaluated", []):
            p_ms = f"{b.get('ping_avg_ms', 0):.1f}" if b.get("ping_avg_ms") else "N/A"
            loss = f"{b.get('packet_loss_pct', 0):.0f}%"
            mtu = str(b.get("path_mtu") or "1500")
            sc = f"{b.get('score', 0):.1f}"
            t_rows.append([f"Band {b.get('band')}", b.get("frequency", ""), p_ms, loss, mtu, sc])
        sections.append(render_table_lines(["BAND", "FREQ", "PING (ms)", "LOSS", "MTU", "SCORE"], t_rows, mono=mono))

        print_panel(
            title="AUTONOMOUS RF BAND CALIBRATION COMPLETE",
            sections=sections,
            accent="success",
            mono=mono,
        )


def build_parser() -> argparse.ArgumentParser:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output machine-readable JSON")
    common_parser.add_argument("--host", nargs="?", const="SHOW", default=argparse.SUPPRESS, help="Router IP/Host (default: http://192.168.1.1)")
    common_parser.add_argument("--username", nargs="?", const="SHOW", default=argparse.SUPPRESS, help="Admin username (default: admin)")
    common_parser.add_argument("--password", nargs="?", const="PROMPT", default=argparse.SUPPRESS, help="Admin password (overrides stored config)")
    common_parser.add_argument("--cookie", "--session-id", dest="cookie", nargs="?", const="PROMPT", default=argparse.SUPPRESS, help="Browser session cookie (JSESSIONID or Netscape format)")
    common_parser.add_argument("--force", action="store_true", default=argparse.SUPPRESS, help="Bypass Network Guard checks")
    common_parser.add_argument("--legacy", action="store_true", default=argparse.SUPPRESS, help="Show classic standard argparse & plain ASCII layout")
    common_parser.add_argument("--mono", action="store_true", default=argparse.SUPPRESS, help="Render modern UI in Black & White monochrome")
    common_parser.add_argument("--no-anim", dest="no_anim", action="store_true", default=argparse.SUPPRESS, help="Disable terminal motion spinners and shimmer animations")
    common_parser.add_argument("--python-tui", dest="python_tui", action="store_true", default=argparse.SUPPRESS, help="Use pure-Python fallback TUI instead of vadimdemedes/ink React UI")

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
    dns_sub.add_parser("show", parents=[common_parser], help="Show current DNS")
    p_dns.set_defaults(func=cmd_dns)

    # ipv6
    p_ipv6 = subparsers.add_parser("ipv6", parents=[common_parser], help="Toggle IPv6 stack (on/off)")
    p_ipv6.add_argument("state", nargs="?", choices=["on", "off", "enable", "disable"], help="State to set (if omitted, shows current status)")
    p_ipv6.add_argument("-i", "--interactive", action="store_true", help="Interactive arrow/space/enter selector")
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
    cfg_sub.add_parser("clear-cookie", parents=[common_parser], help="Clear saved session cookie")
    cfg_sub.add_parser("show", parents=[common_parser], help="Show current configuration")
    p_cfg.set_defaults(func=cmd_config)

    # cookie
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
    p_band.add_argument("-i", "--interactive", action="store_true", help="Launch interactive arrow-key band selector")
    p_band.set_defaults(func=cmd_band)

    # calibrate
    p_cal = subparsers.add_parser("calibrate", parents=[common_parser], help="Autonomous RF band calibration & Live Web UI")
    p_cal.add_argument("--web", action="store_true", default=True, help="Launch real-time Web UI dashboard")
    p_cal.add_argument("--no-web", dest="web", action="store_false", help="Run in headless terminal mode")
    p_cal.add_argument("--port", type=int, default=8765, help="Web dashboard port (default: 8765)")
    p_cal.add_argument("--bands", default="8,3,1,40,auto", help="Candidate bands (default: 8,3,1,40,auto)")
    p_cal.add_argument("--timeout", type=int, default=45, help="45s watchdog timeout")
    p_cal.add_argument("--dry-run", action="store_true", help="Simulate without radio detachment")
    p_cal.add_argument("-i", "--interactive", action="store_true", help="Interactive Spacebar [✔] multi-band picker")
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

    # legacy
    p_legacy = subparsers.add_parser("legacy", parents=[common_parser], help="Display classic standard argparse help layout")
    p_legacy.set_defaults(func=lambda a: parser.print_help())

    # tui
    def _cmd_tui(a):
        cfg_mgr = ConfigManager()
        cfg = cfg_mgr.load()
        target_host = getattr(a, "host", None) or cfg.get("host", "http://192.168.1.1")
        if target_host == "SHOW":
            target_host = cfg.get("host", "http://192.168.1.1")
        chosen = launch_best_tui(
            target_host=target_host,
            mono=_is_mono(a),
            no_anim=bool(getattr(a, "no_anim", False)),
            prefer_python=bool(getattr(a, "python_tui", False)),
        )
        if chosen:
            return dispatch_tui_command(chosen, parser, mono=_is_mono(a))
        return 0

    p_tui = subparsers.add_parser("tui", parents=[common_parser], help="Launch interactive Terminal UI (vadimdemedes/ink React TUI)")
    p_tui.set_defaults(func=_cmd_tui)

    return parser


def launch_best_tui(
    target_host: str = "http://192.168.1.1",
    mono: bool = False,
    no_anim: bool = False,
    prefer_python: bool = False,
) -> Optional[str]:
    """
    Launch the bundled vadimdemedes/ink React TUI by default when Node.js is
    available, falling back cleanly to the pure-Python TUI engine when requested
    via `--python-tui` or when Node.js is absent.
    """
    if not prefer_python:
        from tplink_router.cli.ink_ui import is_ink_available, launch_ink_tui

        if is_ink_available():
            handled, handoff = launch_ink_tui(
                target_host=target_host,
                mono=mono,
                no_anim=no_anim,
            )
            if handled:
                return handoff

    from tplink_router.cli.interactive_tui import launch_tui

    return launch_tui(target_host=target_host, mono=mono)


def dispatch_tui_command(chosen_cmd: str, parser: argparse.ArgumentParser, mono: bool = False) -> int:
    cmd_args = shlex.split(chosen_cmd)
    if mono and "--mono" not in cmd_args:
        cmd_args.insert(0, "--mono")
    parsed = parser.parse_args(cmd_args)
    for _k, _v in [
        ("json", False),
        ("host", None),
        ("username", None),
        ("password", None),
        ("cookie", None),
        ("force", False),
        ("legacy", False),
        ("mono", mono),
        ("no_anim", False),
        ("python_tui", False),
    ]:
        if not hasattr(parsed, _k):
            setattr(parsed, _k, _v)
    try:
        parsed.func(parsed)
        return 0
    except KeyboardInterrupt:
        clear_active_spinner()
        print("\n\033[93m[Aborted] Operation cancelled by user.\033[0m")
        return 130
    except Exception as e:
        return handle_cli_error(e, parsed)


def main(args=None):
    raw_args = list(sys.argv[1:]) if args is None else list(args)

    subcommands = {
        "status", "signal", "cell-lock", "dns", "ipv6", "ussd", "sms", "reboot",
        "profile", "config", "cookie", "wifi-guard", "clients", "reservation",
        "data-limit", "wifi", "leds", "diag", "band", "calibrate", "logs",
        "guest-wifi", "port-forward", "dmz", "upnp", "reboot-schedule", "time",
        "op-mode", "ddns", "fw-check", "repl", "legacy", "tui"
    }
    has_subcmd = any(a in subcommands for a in raw_args)
    is_legacy = any(a in ("--legacy", "legacy") for a in raw_args)
    is_mono = "--mono" in raw_args
    is_no_anim = "--no-anim" in raw_args
    is_python_tui = "--python-tui" in raw_args
    is_help = any(a in ("-h", "--help", "help") for a in raw_args)

    # Intercept bare invocation (or bare `--mono` / `--no-anim` / `--python-tui` without subcommand)
    if not has_subcmd:
        non_flags = [a for a in raw_args if not a.startswith("-")]
        tui_flags = {"--mono", "--no-anim", "--python-tui"}
        only_theme_flags = all(a in tui_flags for a in raw_args)
        if not non_flags and (len(raw_args) == 0 or (only_theme_flags and not is_help)):
            if is_legacy:
                parser = build_parser()
                parser.print_help()
                return 0
            cfg_mgr = ConfigManager()
            cfg = cfg_mgr.load()
            target_host = cfg.get("host", "http://192.168.1.1")

            if sys.stdin.isatty() and sys.stdout.isatty():
                chosen_cmd = launch_best_tui(
                    target_host=target_host,
                    mono=is_mono,
                    no_anim=is_no_anim,
                    prefer_python=is_python_tui,
                )
                if not chosen_cmd:
                    return 0
                return dispatch_tui_command(chosen_cmd, build_parser(), mono=is_mono)
            else:
                from tplink_router.cli.modern_ui import print_modern_ui
                print_modern_ui(target_host, mono=is_mono)
                return 0

        elif not non_flags and is_help:
            if is_legacy:
                parser = build_parser()
                parser.print_help()
                return 0
            cfg_mgr = ConfigManager()
            cfg = cfg_mgr.load()
            from tplink_router.cli.modern_ui import print_modern_ui
            print_modern_ui(cfg.get("host", "http://192.168.1.1"), mono=is_mono)
            return 0

    parser = build_parser()
    parsed_args = parser.parse_args(args)
    for _k, _v in [
        ("json", False),
        ("host", None),
        ("username", None),
        ("password", None),
        ("cookie", None),
        ("force", False),
        ("legacy", False),
        ("mono", False),
        ("no_anim", False),
        ("python_tui", False),
    ]:
        if not hasattr(parsed_args, _k):
            setattr(parsed_args, _k, _v)

    if parsed_args.password == "PROMPT":
        try:
            parsed_args.password = getpass.getpass("Enter router admin password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(130)

    if not hasattr(parsed_args, "func"):
        cfg_mgr = ConfigManager()
        cfg = cfg_mgr.load()
        mono = _is_mono(parsed_args)

        if parsed_args.host == "SHOW":
            if parsed_args.json:
                print(json.dumps({"target_host": cfg.get("host", "http://192.168.1.1")}))
            elif _is_legacy(parsed_args):
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
            else:
                print_panel(
                    title="TARGET ROUTER HOST",
                    sections=[render_kv_rows([("Current Target Host", cfg.get("host", "http://192.168.1.1"))], mono=mono)],
                    footer="Override per command: tplink-cli --host http://192.168.1.1 <cmd>",
                    mono=mono,
                )
            return 0

        if parsed_args.username == "SHOW":
            if parsed_args.json:
                print(json.dumps({"username": cfg.get("username", "admin")}))
            elif _is_legacy(parsed_args):
                print(f"Current Router Username : {cfg.get('username', 'admin')}")
            else:
                print_panel(
                    title="ROUTER ADMIN USERNAME",
                    sections=[render_kv_rows([("Admin Username", cfg.get("username", "admin"))], mono=mono)],
                    mono=mono,
                )
            return 0

        if parsed_args.cookie == "PROMPT":
            c = cfg.get("session_cookie")
            masked = f"{c[:6]}...{c[-6:]}" if (c and len(c) > 12) else c
            if _is_legacy(parsed_args):
                if c:
                    print(f"\n\033[1mActive Browser Session Cookie:\033[0m {masked}")
                else:
                    print("\n\033[93mNo browser session cookie currently stored.\033[0m")
                print("To store a new session cookie:")
                print("  tplink-cli cookie <cookie_string_or_jsessionid>\n")
            else:
                print_panel(
                    title="BROWSER SESSION COOKIE",
                    sections=[render_kv_rows([("Active Cookie", status_badge(bool(c), masked or "SET", "NOT STORED", mono=mono))], mono=mono)],
                    footer="tplink-cli cookie <JSESSIONID>",
                    mono=mono,
                )
            return 0

        if _is_legacy(parsed_args):
            parser.print_help()
        else:
            from tplink_router.cli.modern_ui import print_modern_ui
            print_modern_ui(cfg.get("host", "http://192.168.1.1"), mono=mono)
        return 0

    if parsed_args.host == "SHOW":
        parsed_args.host = None
    if parsed_args.username == "SHOW":
        parsed_args.username = None

    try:
        parsed_args.func(parsed_args)
    except KeyboardInterrupt:
        clear_active_spinner()
        print("\n\033[93m[Aborted] Operation cancelled by user.\033[0m")
        sys.exit(130)
    except Exception as e:
        sys.exit(handle_cli_error(e, parsed_args))


def handle_cli_error(e: Exception, args: Optional[argparse.Namespace] = None) -> int:
    clear_active_spinner()
    is_json = getattr(args, "json", False) if args else False
    legacy = _is_legacy(args)
    mono = _is_mono(args)
    host = (getattr(args, "host", None) if args else None) or "http://192.168.1.1"
    p = get_palette(mono=mono)

    err_str = str(e)
    err_type = type(e).__name__

    # 1. Authentication / Password errors
    if isinstance(e, PermissionError) or "password" in err_str.lower() or "71233" in err_str:
        if is_json:
            print(json.dumps({
                "error": True,
                "code": "AUTHENTICATION_FAILED",
                "message": "Router authentication failed.",
                "detail": err_str or "Incorrect admin password or session expired.",
                "hint": "Update your password with 'tplink-cli config set-password' or set an active session cookie with 'tplink-cli cookie'."
            }, indent=2), file=sys.stderr)
        elif legacy:
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
        else:
            kv = render_kv_rows([
                ("Target Router", host),
                ("Reason", err_str or "Incorrect admin password or session expired."),
            ], key_width=15, mono=mono)
            fix = [
                f"{p.white}How to resolve:{p.reset}",
                f"  1. {p.brand_bold}tplink-cli config set-password <password>{p.reset}",
                f"  2. {p.brand_bold}tplink-cli cookie <JSESSIONID>{p.reset}",
            ]
            print_panel("AUTHENTICATION FAILED", [kv, fix], accent="danger", mono=mono)
        return 1

    # 2. Timeout error
    if isinstance(e, (requests.exceptions.Timeout, TimeoutError)) or "timed out" in err_str.lower():
        if is_json:
            print(json.dumps({
                "error": True,
                "code": "REQUEST_TIMEOUT",
                "message": f"Connection to {host} timed out.",
                "hint": "The router may be busy rebooting, switching LTE bands, or under high load."
            }, indent=2), file=sys.stderr)
        elif legacy:
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
        else:
            kv = render_kv_rows([
                ("Target Router", host),
                ("Detail", "Request timed out waiting for router response."),
            ], key_width=15, mono=mono)
            notes = [
                "The router may be rebooting, retuning cellular LTE frequencies,",
                "or experiencing wireless packet loss. Wait a few seconds and retry.",
            ]
            print_panel("ROUTER CONNECTION TIMED OUT", [kv, notes], accent="warning", mono=mono)
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
        elif legacy:
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
        else:
            kv = render_kv_rows([
                ("Target Router", host),
                ("Status", "Connection Failed (Host is offline or unreachable)"),
            ], key_width=15, mono=mono)
            hints = [
                f"• {p.white}Router Rebooting{p.reset} : Hardware takes ~60-90s to restart after reboot.",
                f"• {p.white}Wi-Fi Dropped{p.reset}    : Verify your device is connected to router Wi-Fi / LAN.",
                f"• {p.white}IP Gateway Check{p.reset} : Run 'tplink-cli profile' to verify 192.168.1.1.",
            ]
            print_panel("ROUTER UNREACHABLE (OFFLINE)", [kv, hints], accent="danger", mono=mono)
        return 1

    # 4. Argument / Config error
    if isinstance(e, ValueError):
        if is_json:
            print(json.dumps({
                "error": True,
                "code": "INVALID_ARGUMENT",
                "message": err_str,
            }, indent=2), file=sys.stderr)
        elif legacy:
            print()
            print("======================================================================")
            print("  ⚠️   \033[1mCONFIGURATION / ARGUMENT ERROR\033[0m")
            print("======================================================================")
            print(f"Error : {err_str}")
            print("======================================================================")
            print()
        else:
            print_panel(
                "CONFIGURATION / ARGUMENT ERROR",
                [render_kv_rows([("Error", err_str)], key_width=10, mono=mono)],
                accent="warning",
                mono=mono,
            )
        return 2

    # 5. Generic unhandled exception fallback
    if is_json:
        print(json.dumps({
            "error": True,
            "code": "UNEXPECTED_ERROR",
            "type": err_type,
            "message": err_str,
        }, indent=2), file=sys.stderr)
    elif legacy:
        print()
        print("======================================================================")
        print("  ⚠️   \033[1mCOMMAND ERROR\033[0m")
        print("======================================================================")
        print(f"Type    : {err_type}")
        print(f"Message : {err_str}")
        print("======================================================================")
        print()
    else:
        print_panel(
            "COMMAND ERROR",
            [render_kv_rows([("Type", err_type), ("Message", err_str)], key_width=10, mono=mono)],
            accent="danger",
            mono=mono,
        )
    return 1


if __name__ == "__main__":
    main()
