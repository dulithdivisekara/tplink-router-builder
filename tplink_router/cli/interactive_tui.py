"""
Interactive Terminal User Interface (TUI) for TP-Link Router Suite.
Provides a live, interactive arrow-key selector with real-time fuzzy filtering,
tab autocompletion, and execution, modeled after obsidian-cli.
"""

import os
import select
import shutil
import sys
import termios
import tty
from typing import List, Optional, Tuple

COMMAND_CATALOG: List[Tuple[str, str]] = [
    ("status", "Show complete router telemetry (modem, carrier, IP, traffic)"),
    ("signal", "Show real-time RF signal metrics (RSRP, RSRQ, SNR, bars)"),
    ("band", "View or lock LTE Band (e.g. 3, 8, 40, auto)"),
    ("cell-lock", "Lock modem to EARFCN carrier frequency and PCI cell identity"),
    ("calibrate", "Autonomous RF multi-band calibration & live Web UI"),
    ("diag", "Run hardware diagnostic test (WAN ping, DNS, default gateway)"),
    ("dns", "Inspect or customize primary & secondary DNS resolvers"),
    ("ipv6", "Inspect router IPv6 stack state or toggle on/off"),
    ("profile", "Validate active Wi-Fi profile and gateway safety"),
    ("wifi-guard", "Verify and optimize Wi-Fi link stability (no Ethernet needed)"),
    ("clients", "List connected LAN devices (IP, MAC address, hostname)"),
    ("reservation", "Manage DHCP static IP address reservations"),
    ("wifi", "View or configure 2.4GHz / 5GHz radios and SSIDs"),
    ("guest-wifi", "Configure isolated dual-band Guest Wi-Fi and passwords"),
    ("leds", "Control hardware indicator LEDs and Night Mode schedule"),
    ("data-limit", "Inspect or set monthly cellular data allowance quota"),
    ("reboot-schedule", "Configure automated periodic reboot timer (daily/weekly)"),
    ("port-forward", "Manage NAT virtual server port forwarding rules"),
    ("dmz", "Inspect or configure DMZ host IP forwarding"),
    ("upnp", "Manage Universal Plug and Play (UPnP) service"),
    ("ddns", "Inspect Dynamic DNS providers and connection status"),
    ("op-mode", "View or switch router operating mode (3G/4G vs Wireless)"),
    ("time", "View router clock or trigger network NTP time sync"),
    ("fw-check", "Check for official TP-Link online firmware updates"),
    ("sms", "Read inbox/outbox/drafts, or send SMS text messages"),
    ("ussd", "Execute cellular USSD queries (*344#, *123#, balance)"),
    ("logs", "Read, filter, or clear system and cellular event logs"),
    ("reboot", "Safely reboot the TP-Link hardware router"),
    ("config", "Manage saved router credentials and endpoint settings"),
    ("cookie", "Inspect or update cached browser session cookie"),
    ("repl", "Launch interactive shell with tab auto-completion & history"),
]


def filter_commands(query: str) -> List[Tuple[str, str]]:
    """Filter catalog using prefix, substring, and description match priorities."""
    if not query:
        return list(COMMAND_CATALOG)
    q = query.lower().strip()
    prefix = [c for c in COMMAND_CATALOG if c[0].lower().startswith(q)]
    name_contain = [c for c in COMMAND_CATALOG if q in c[0].lower() and c not in prefix]
    desc_contain = [c for c in COMMAND_CATALOG if q in c[1].lower() and c not in prefix and c not in name_contain]
    return prefix + name_contain + desc_contain


def read_key(fd: int) -> str:
    """Read a single key or escape sequence from stdin in raw mode."""
    ch = os.read(fd, 1).decode("utf-8", errors="ignore")
    if ch == "\x1b":
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            seq = os.read(fd, 2).decode("utf-8", errors="ignore")
            if seq == "[A":
                return "UP"
            elif seq == "[B":
                return "DOWN"
            elif seq == "[C":
                return "RIGHT"
            elif seq == "[D":
                return "LEFT"
            elif seq in ("[5", "[6"):
                # Page Up/Down consume trailing tilde
                os.read(fd, 1)
                return "PGUP" if seq == "[5" else "PGDN"
            return "ESC"
        return "ESC"
    elif ch in ("\r", "\n"):
        return "ENTER"
    elif ch in ("\x7f", "\x08"):
        return "BACKSPACE"
    elif ch == "\t":
        return "TAB"
    elif ch == "\x03":
        return "CTRL_C"
    elif ch == "\x04":
        return "CTRL_D"
    return ch


def launch_tui(target_host: str = "http://192.168.1.1", router_model: str = "Archer MR200 / Universal") -> Optional[str]:
    """Run interactive TUI selection loop. Returns selected command name or None if aborted."""
    if not sys.stdin.isatty():
        return None

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    cyan = "\033[1;36m"
    purple = "\033[1;35m"
    white = "\033[1;37m"
    dim = "\033[90m"
    green = "\033[1;32m"
    bold = "\033[1m"
    inv = "\033[7m"
    reset = "\033[0m"

    query = ""
    selected_idx = 0
    page_size = 9
    prev_line_count = 0

    try:
        tty.setraw(fd)
        sys.stdout.write("\033[?25l")  # Hide cursor
        sys.stdout.flush()

        while True:
            filtered = filter_commands(query)
            if selected_idx >= len(filtered):
                selected_idx = max(0, len(filtered) - 1)

            # Calculate scroll window
            start_idx = 0
            if selected_idx >= page_size:
                start_idx = selected_idx - page_size + 1
            visible_items = filtered[start_idx : start_idx + page_size]
            remaining = len(filtered) - (start_idx + len(visible_items))

            cols, _ = shutil.get_terminal_size((80, 24))
            term_w = max(60, min(cols, 100))
            divider = "─" * min(term_w, 74)

            # Build buffer
            lines: List[str] = [
                "",
                f"      {cyan}/\\{reset}         {cyan}/\\{reset}       {cyan}{bold}TP-Link Router CLI{reset} {dim}v1.0.0{reset}",
                f"     {cyan}/  \\{reset}       {cyan}/  \\{reset}      {white}Universal LTE & Wi-Fi Gateway Engine{reset}",
                f"    {cyan}/ /\\ \\{reset}     {cyan}/ /\\ \\{reset}     {dim}Target:{reset} {cyan}{target_host}{reset} {green}● Ready{reset}",
                f"   {cyan}| |  | |{reset}   {cyan}| |  | |{reset}    {dim}Model:{reset}  {router_model}",
                f"  {dim}[===================]{reset}   {dim}Tab to autocomplete, ↑/↓ to navigate, Enter to select{reset}",
                f"   {dim}|{reset}   {green}●{reset}   {cyan}●{reset}   {green}●{reset}   {cyan}●{reset}  {dim}|{reset}   {dim}Ctrl+C or Esc to quit{reset}",
                f"  {dim}[===================]{reset}",
                f"{dim}{divider}{reset}",
                f"{purple}{bold}> {reset}{white}{query}{reset}{inv} {reset}",
            ]

            if not visible_items:
                lines.append(f"  {dim}No commands matching '{query}'{reset}")
            else:
                for idx, (cmd_name, cmd_desc) in enumerate(visible_items):
                    actual_idx = start_idx + idx
                    if actual_idx == selected_idx:
                        # Highlighted item matching obsidian-cli
                        lines.append(f"  {purple}{bold}> {cmd_name:<16}{reset}  {white}{cmd_desc}{reset}")
                    else:
                        lines.append(f"    {dim}{cmd_name:<16}  {cmd_desc}{reset}")

            if remaining > 0:
                lines.append(f"  {dim}{remaining} more{reset}")
            else:
                lines.append("")

            # In-place redraw
            if prev_line_count > 0:
                sys.stdout.write(f"\033[{prev_line_count}A\r")

            for line in lines:
                sys.stdout.write(f"\033[2K{line}\r\n")
            sys.stdout.flush()

            prev_line_count = len(lines)

            # Read user input
            key = read_key(fd)

            if key in ("CTRL_C", "CTRL_D", "ESC"):
                return None

            elif key == "UP":
                if selected_idx > 0:
                    selected_idx -= 1

            elif key == "DOWN":
                if selected_idx < len(filtered) - 1:
                    selected_idx += 1

            elif key == "PGUP":
                selected_idx = max(0, selected_idx - page_size)

            elif key == "PGDN":
                selected_idx = min(len(filtered) - 1, selected_idx + page_size)

            elif key == "TAB":
                if filtered:
                    query = filtered[selected_idx][0]
                    selected_idx = 0

            elif key == "BACKSPACE":
                if query:
                    query = query[:-1]
                    selected_idx = 0

            elif key == "ENTER":
                if filtered:
                    selected_cmd = filtered[selected_idx][0]
                    return selected_cmd
                return None

            elif len(key) == 1 and key.isprintable():
                query += key
                selected_idx = 0

    finally:
        # Restore terminal state completely
        sys.stdout.write("\033[?25h")  # Show cursor
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
