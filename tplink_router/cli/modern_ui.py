"""
Modern Obsidian-Style CLI UI for TP-Link Router Suite.
Provides a clean, aesthetic, grouped terminal interface inspired by obsidian-cli,
with ASCII art, clear categories, and rapid discovery.
"""

import sys
import shutil
from typing import Optional


def get_terminal_width(default: int = 80) -> int:
    try:
        cols, _ = shutil.get_terminal_size((default, 24))
        return max(60, min(cols, 100))
    except Exception:
        return default


def print_modern_ui(target_host: str = "http://192.168.1.1", router_model: str = "Archer MR200 / Universal"):
    """Render modern aesthetic CLI interface."""
    width = get_terminal_width()
    divider = "─" * min(width, 76)

    # ANSI styles
    cyan = "\033[1;36m"
    dim = "\033[90m"
    white = "\033[1;37m"
    green = "\033[1;32m"
    yellow = "\033[1;33m"
    bold = "\033[1m"
    reset = "\033[0m"

    # Logo + metadata side-by-side
    banner = [
        f"      {cyan}/\\{reset}         {cyan}/\\{reset}       {cyan}{bold}TP-Link Router CLI{reset} {dim}v1.0.0{reset}",
        f"     {cyan}/  \\{reset}       {cyan}/  \\{reset}      {white}Universal LTE & Wi-Fi Gateway Engine{reset}",
        f"    {cyan}/ /\\ \\{reset}     {cyan}/ /\\ \\{reset}     {dim}Target:{reset} {cyan}{target_host}{reset} {green}● Ready{reset}",
        f"   {cyan}| |  | |{reset}   {cyan}| |  | |{reset}    {dim}Model:{reset}  {router_model}",
        f"  {dim}[===================]{reset}   {dim}Shell:{reset}  Run {white}tplink-cli repl{reset} for interactive mode",
        f"   {dim}|{reset}   {green}●{reset}   {cyan}●{reset}   {green}●{reset}   {cyan}●{reset}  {dim}|{reset}   {dim}Legacy:{reset} Use {yellow}--legacy{reset} for classic argparse dump",
        f"  {dim}[===================]{reset}",
    ]

    print()
    for line in banner:
        print(line)

    print(f"{dim}{divider}{reset}")
    print(f"{bold}> tplink-cli [command] [options]{reset}\n")

    categories = [
        (
            "CELLULAR & RADIO FREQUENCY (RF)",
            [
                ("signal", "Show real-time RF signal metrics (RSRP, RSRQ, SNR, bars)"),
                ("band", "View or lock LTE Band (e.g. 3, 8, 40, or auto)"),
                ("cell-lock", "Lock modem to EARFCN carrier frequency and PCI cell identity"),
                ("calibrate", "Autonomous RF multi-band calibration & live Web UI"),
                ("diag", "Run hardware diagnostic test (WAN ping, DNS, default gateway)"),
            ],
        ),
        (
            "NETWORK & INTERNET",
            [
                ("status", "Show complete router telemetry (modem, carrier, IP, traffic)"),
                ("dns", "Inspect or customize primary & secondary DNS resolvers"),
                ("ipv6", "Inspect router IPv6 stack state or toggle on/off"),
                ("profile", "Validate active Wi-Fi profile and gateway safety"),
                ("wifi-guard", "Verify and optimize Wi-Fi link stability (no Ethernet needed)"),
                ("clients", "List connected LAN devices (IP, MAC address, hostname)"),
                ("reservation", "Manage DHCP static IP address reservations"),
            ],
        ),
        (
            "WI-FI & ACCESS CONTROL",
            [
                ("wifi", "View or configure 2.4GHz / 5GHz radios and SSIDs"),
                ("guest-wifi", "Configure isolated dual-band Guest Wi-Fi and passwords"),
                ("leds", "Control hardware indicator LEDs and Night Mode schedule"),
                ("data-limit", "Inspect or set monthly cellular data allowance quota"),
                ("reboot-schedule", "Configure automated periodic reboot timer (daily/weekly)"),
            ],
        ),
        (
            "ROUTING & NAT",
            [
                ("port-forward", "Manage NAT virtual server port forwarding rules"),
                ("dmz", "Inspect or configure DMZ host IP forwarding"),
                ("upnp", "Manage Universal Plug and Play (UPnP) service"),
                ("ddns", "Inspect Dynamic DNS providers and connection status"),
                ("op-mode", "View or switch router operating mode (3G/4G vs Wireless)"),
                ("time", "View router clock or trigger network NTP time sync"),
                ("fw-check", "Check for official TP-Link online firmware updates"),
            ],
        ),
        (
            "ADMINISTRATION & TOOLS",
            [
                ("sms", "Read inbox/outbox/drafts, or send SMS text messages"),
                ("ussd", "Execute cellular USSD queries (*344#, *123#, balance)"),
                ("logs", "Read, filter, or clear system and cellular event logs"),
                ("reboot", "Safely reboot the TP-Link hardware router"),
                ("config", "Manage saved router credentials and endpoint settings"),
                ("cookie", "Inspect or update cached browser session cookie"),
                ("repl", "Launch interactive shell with tab auto-completion & history"),
            ],
        ),
    ]

    for cat_title, cmds in categories:
        print(f"{bold}{cyan}{cat_title}{reset}")
        for cmd_name, cmd_desc in cmds:
            print(f"  {green}{cmd_name:<16}{reset} {cmd_desc}")
        print()

    print(f"{bold}{cyan}GLOBAL FLAGS{reset}")
    flags = [
        ("-h, --help", "Show this modern command catalog"),
        ("--legacy", "Show classic standard argparse help output"),
        ("--json", "Output machine-readable JSON for scripts and pipelines"),
        ("--host <url>", f"Override router IP/URL (default: {target_host})"),
        ("--username <u>", "Override router username (default: admin)"),
        ("--password <p>", "Override router password or prompt interactively"),
        ("--force", "Bypass Network Guard security checks"),
    ]
    for flag_name, flag_desc in flags:
        print(f"  {yellow}{flag_name:<16}{reset} {flag_desc}")

    print(f"\n{dim}{divider}{reset}")
    print(f"{bold}Quick Start Examples:{reset}")
    print(f"  {white}tplink-cli status{reset}              {dim}# Inspect full router & cellular telemetry{reset}")
    print(f"  {white}tplink-cli signal{reset}              {dim}# Check live cellular signal metrics & bars{reset}")
    print(f"  {white}tplink-cli band 8{reset}              {dim}# Lock to Band 8 (900 MHz){reset}")
    print(f"  {white}tplink-cli repl{reset}                {dim}# Launch interactive command shell{reset}")
    print(f"  {white}tplink-cli <command> --help{reset}    {dim}# View arguments for a specific command{reset}")
    print(f"  {white}tplink-cli --legacy{reset}            {dim}# Switch to classic argparse help layout{reset}\n")
