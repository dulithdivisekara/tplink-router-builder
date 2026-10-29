"""
Modern Themed Command Catalog & Help View for TP-Link Router Suite.

Renders the authentic TP-Link Half-Block Pixel Logo alongside categorized,
rounded-border command panels and global flags. Supports both TP-Link Brand
Cyan (#4DCCD5) and Monochrome Black & White (--mono / NO_COLOR) modes.
"""

import shutil
from typing import List, Tuple

from tplink_router.cli.logo import get_logo_width, render_logo_lines
from tplink_router.cli.theme import (
    get_palette,
    get_ui_width,
    pad_right,
    render_panel,
    status_badge,
)

CATEGORIES: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "CELLULAR & RADIO FREQUENCY (RF)",
        [
            ("signal", "Real-time RF signal metrics (RSRP, RSRQ, SNR, step-bars)"),
            ("band", "View or lock LTE Band (1, 3, 8, 40, auto) or interactive picker"),
            ("cell-lock", "Lock modem to specific EARFCN carrier & PCI tower identity"),
            ("calibrate", "Autonomous multi-band RF sweep & live Web Dashboard"),
            ("data-limit", "Inspect or set monthly cellular data quota & billing day"),
            ("diag", "Run WAN internet & NCSI self-diagnostic connectivity check"),
        ],
    ),
    (
        "WAN, LAN & NETWORK GUARD",
        [
            ("status", "Complete router telemetry (modem, carrier, RF, WAN IP, usage)"),
            ("dns", "Inspect or customize primary & secondary WAN DNS resolvers"),
            ("ipv6", "Inspect router IPv6 stack state or toggle on/off"),
            ("clients", "List active LAN & Wi-Fi devices (Hostname, IP, MAC, Lease)"),
            ("reservation", "Manage static DHCP IP address reservations"),
            ("profile", "Validate active host Wi-Fi SSID and gateway safety"),
            ("wifi-guard", "Verify & optimize wireless-only link stability (no Ethernet)"),
        ],
    ),
    (
        "WI-FI RADIOS & HARDWARE",
        [
            ("wifi", "Inspect or toggle 2.4GHz / 5GHz Wi-Fi radios and SSIDs"),
            ("guest-wifi", "Configure isolated dual-band Guest Wi-Fi & WPA2 keys"),
            ("leds", "Control front-panel LEDs and Night Mode quiet hours"),
            ("reboot-schedule", "Configure automated daily/weekly hardware reboot timer"),
            ("op-mode", "Inspect operation mode (3G/4G Router vs Wireless Router)"),
        ],
    ),
    (
        "NAT, ROUTING & SYSTEM SERVICES",
        [
            ("port-forward", "Manage NAT virtual server port forwarding rules"),
            ("dmz", "Inspect or configure DMZ exposed internal host IP"),
            ("upnp", "Inspect or toggle Universal Plug and Play (UPnP) mappings"),
            ("ddns", "Inspect Dynamic DNS providers and domain binding state"),
            ("time", "Inspect router system clock, timezone, or trigger NTP sync"),
            ("fw-check", "Check for official TP-Link online firmware releases"),
        ],
    ),
    (
        "MESSAGING, LOGS & INTERACTIVE CONSOLES",
        [
            ("tui", "Launch full-screen interactive Terminal UI (Arrows/Space/Enter)"),
            ("sms", "Read inbox/sent messages or send cellular SMS texts"),
            ("ussd", "Execute carrier USSD codes (*344#, *123#, balance/data)"),
            ("logs", "Read, filter, or clear system & 4G cellular event logs"),
            ("config", "Manage encrypted router credentials and expected SSID"),
            ("cookie", "Inspect or save browser JSESSIONID / Netscape cookie"),
            ("repl", "Launch persistent single-session interactive shell"),
            ("reboot", "Safely reboot the TP-Link hardware router"),
        ],
    ),
]


def print_modern_ui(
    target_host: str = "http://192.168.1.1",
    router_model: str = "Archer MR200 / Universal",
    mono: bool = False,
) -> None:
    """Render modern TP-Link branded command reference with pixel-block logo."""
    p = get_palette(mono=mono)
    cols, _ = shutil.get_terminal_size((84, 24))
    box_w = get_ui_width(default=82, min_w=62, max_w=92)

    print()
    if cols >= 72:
        logo_lines = render_logo_lines("full", mono=mono)
        for line in logo_lines:
            print(f"  {line}")
        print()
        badge = status_badge(True, "READY", "OFFLINE", mono=mono)
        meta_lines = [
            f"{p.brand_bold}Universal Cellular & Wi-Fi Router Command Suite{p.reset}  {p.muted}v1.0.0{p.reset}",
            f"{p.muted}Gateway:{p.reset} {p.white}{target_host}{p.reset}  {badge}   {p.muted}Target:{p.reset} {p.text}{router_model}{p.reset}",
            f"{p.muted}Interactive TUI:{p.reset} Run {p.white}tplink-cli{p.reset} or {p.white}tplink-cli tui{p.reset} {p.muted}(↑/↓ scroll • Space select • Enter run){p.reset}",
        ]
        print(
            render_panel(
                title="TP-LINK CLI OVERVIEW",
                sections=[meta_lines],
                subtitle="Modern UI",
                footer="Use --mono for B&W theme • --legacy for classic argparse",
                mono=mono,
                width=box_w,
            )
        )
    else:
        logo_lines = render_logo_lines("compact", mono=mono)
        lw = get_logo_width("compact")
        badge = status_badge(True, "READY", "OFFLINE", mono=mono)
        info = [
            f"{p.brand_bold}TP-Link Router CLI{p.reset} {p.muted}v1.0.0{p.reset}",
            f"{p.text}Universal LTE & Wi-Fi Engine{p.reset}",
            f"{p.muted}Host:{p.reset}  {p.white}{target_host}{p.reset}",
            f"{p.muted}Model:{p.reset} {p.text}{router_model}{p.reset}",
            f"{p.muted}State:{p.reset} {badge}",
            f"{p.muted}TUI:{p.reset}   {p.white}tplink-cli tui{p.reset}",
            f"{p.muted}Mono:{p.reset}  {p.white}tplink-cli --mono{p.reset}",
            f"{p.muted}Old:{p.reset}   {p.white}tplink-cli --legacy{p.reset}",
        ]
        for i in range(max(len(logo_lines), len(info))):
            l_part = logo_lines[i] if i < len(logo_lines) else (" " * lw)
            r_part = info[i] if i < len(info) else ""
            print(f"  {l_part}   {r_part}")

    # Render command categories inside a clean multi-section panel
    cat_sections: List[List[str]] = []
    for cat_title, cmds in CATEGORIES:
        sec_lines = [f"{p.brand_bold}▸ {cat_title}{p.reset}"]
        for cmd_name, cmd_desc in cmds:
            cname = pad_right(cmd_name, 16)
            cmd_col = p.white if p.mono else p.brand_bold
            sec_lines.append(f"  {cmd_col}{cname}{p.reset} {p.text}{cmd_desc}{p.reset}")
        cat_sections.append(sec_lines)

    flags_sec = [f"{p.brand_bold}▸ GLOBAL OPTIONS{p.reset}"]
    flags = [
        ("-h, --help", "Display this modern TP-Link command reference"),
        ("--mono", "Render logo, TUI, and command cards in Black & White monochrome"),
        ("--no-anim", "Disable terminal motion spinners and shimmer animations"),
        ("--python-tui", "Use pure-Python TUI engine instead of vadimdemedes/ink React UI"),
        ("--legacy", "Use classic plain-ASCII layout and standard argparse help"),
        ("--json", "Emit machine-readable JSON for scripts & CI pipelines"),
        ("--host <url>", f"Override target gateway URL (default: {target_host})"),
        ("--username <u>", "Override admin username (default: admin)"),
        ("--password <p>", "Override admin password or prompt interactively"),
        ("--cookie <c>", "Authenticate using active browser JSESSIONID cookie"),
        ("--force", "Bypass Network Guard Wi-Fi SSID safety check"),
    ]
    for f_name, f_desc in flags:
        fn = pad_right(f_name, 16)
        fcol = p.white if p.mono else p.warning
        flags_sec.append(f"  {fcol}{fn}{p.reset} {p.muted}{f_desc}{p.reset}")
    cat_sections.append(flags_sec)

    print()
    print(
        render_panel(
            title="COMMAND CATALOG",
            sections=cat_sections,
            subtitle="31 Router Tools",
            footer="tplink-cli <command> --help for command-specific flags",
            mono=mono,
            width=box_w,
        )
    )
    print()
