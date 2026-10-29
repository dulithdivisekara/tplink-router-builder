"""
Flagship Interactive Terminal User Interface (TUI) for TP-Link Router Suite.

Inspired by binsider (Ratatui), Ink / Claude Code, OpenClaw CLI, and awesome-tuis:
  - Authentic Half-Block TP-Link Brand Logo (Brand Cyan #4DCCD5 + Monochrome B&W [m])
  - Multi-Tab Domain Navigation (← / → / Tab / 1-6)
  - Split-Pane Workspace: Navigable Action List + Live Command Inspector
  - Full Keyboard Ergonomics:
      * ↑ / ↓ (or j / k) : Scroll options & parameters
      * ← / → (or Tab)   : Switch router subsystem tabs
      * Spacebar         : Toggle [✔] multi-select checkboxes & [● ON / ○ OFF] switches
      * Enter            : Confirm, open interactive parameter wizard, or run command/batch
      * /                : Live fuzzy search across all 31 router tools & wizards
      * m                : Toggle TP-Link Cyan <-> Black & White Monochrome theme live
      * r                : Poll live router RF & gateway telemetry into header strip
      * q / Esc / Ctrl+C : Back / Quit cleanly restoring terminal screen
"""

from dataclasses import dataclass, field
import io
import os
import select
import shutil
import sys
import termios
import tty
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from tplink_router.cli.logo import get_logo_width, render_logo_lines
from tplink_router.cli.theme import (
    get_palette,
    pad_right,
    render_panel,
    signal_bars,
    status_badge,
    strip_ansi,
    truncate_ansi,
    visible_len,
)


@dataclass(frozen=True)
class CommandEntry:
    name: str
    summary: str
    category: str
    details: str
    examples: Tuple[str, ...]
    batchable: bool = True
    is_wizard: bool = False
    interactive_mode: Optional[str] = None  # None, 'band', 'ipv6', 'upnp', 'wifi', 'leds', 'dns', 'sms', 'ussd', 'reboot', 'calibrate', 'toggles'


COMMAND_SPECS: List[CommandEntry] = [
    # Wizards (Featured in Tab 1)
    CommandEntry(
        name="wizard:toggles",
        summary="Quick Feature Switchboard (Spacebar ON/OFF toggles)",
        category="quick",
        details="Interactive live switchboard for toggling IPv6 Stack, 2.4GHz Wi-Fi, 5GHz Wi-Fi, Guest Wi-Fi, UPnP, and LED Night Mode using Spacebar and Enter.",
        examples=("Space : Flip [● ON] / [○ OFF]", "Enter : Apply modified switches to router"),
        batchable=False,
        is_wizard=True,
        interactive_mode="toggles",
    ),
    CommandEntry(
        name="wizard:band",
        summary="Interactive LTE Band Lock Picker (Band 1/3/8/40/Auto)",
        category="quick",
        details="Visual frequency band selector for locking the cellular modem onto Band 8 (900MHz), Band 3 (1800MHz), Band 1 (2100MHz), Band 40 (2300MHz), or Auto.",
        examples=("tplink-cli band 8", "tplink-cli band 3", "tplink-cli band auto"),
        batchable=False,
        is_wizard=True,
        interactive_mode="band_picker",
    ),
    CommandEntry(
        name="wizard:calibrate",
        summary="Multi-Band RF Calibration Checklist (Spacebar picker)",
        category="quick",
        details="Select multiple candidate LTE bands with Spacebar [✔] and run an automated latency, packet-loss, and signal sweep to find the fastest tower.",
        examples=("Space : Toggle candidate bands [✔]", "Enter : Run RF calibration sweep"),
        batchable=False,
        is_wizard=True,
        interactive_mode="calibrate",
    ),
    # 31 Standard CLI Commands
    CommandEntry(
        name="status",
        summary="Show complete router telemetry (modem, carrier, IP, traffic)",
        category="network",
        details="Polls full hardware, firmware, LTE carrier, active band/EARFCN, RSRP/RSRQ/SNR signal ratings, throughput, and WAN IPv4/IPv6 state.",
        examples=("tplink-cli status", "tplink-cli --mono status", "tplink-cli status --json"),
        batchable=True,
    ),
    CommandEntry(
        name="signal",
        summary="Show real-time RF signal metrics (RSRP, RSRQ, SNR, bars)",
        category="cellular",
        details="Instant cellular radio snapshot displaying visual signal bars (▂▄▆█), RSRP power (dBm), RSRQ load (dB), and SNR clarity.",
        examples=("tplink-cli signal", "tplink-cli signal --json"),
        batchable=True,
    ),
    CommandEntry(
        name="band",
        summary="View or lock LTE Band (e.g. 3, 8, 40, auto)",
        category="cellular",
        details="Inspect active LTE frequency band or lock the cellular modem hardware onto a specific carrier band (Band 3, Band 8, Band 40, or Auto).",
        examples=("tplink-cli band", "tplink-cli band 8", "tplink-cli band auto"),
        batchable=True,
        interactive_mode="band",
    ),
    CommandEntry(
        name="cell-lock",
        summary="Lock modem to EARFCN carrier frequency and PCI cell identity",
        category="cellular",
        details="Inspect or pin the cellular modem to a specific cell sector (EARFCN + Physical Cell ID) to prevent tower-hopping.",
        examples=("tplink-cli cell-lock", "tplink-cli cell-lock --enable --earfcn 3738 --pci 0", "tplink-cli cell-lock --disable"),
        batchable=True,
    ),
    CommandEntry(
        name="calibrate",
        summary="Autonomous RF multi-band calibration & live Web UI",
        category="cellular",
        details="Benchmarks candidate LTE bands with watchdog safety rollback and recommends the highest-scoring frequency for throughput and latency.",
        examples=("tplink-cli calibrate --no-web --dry-run", "tplink-cli calibrate --bands 8,3,auto"),
        batchable=False,
        interactive_mode="calibrate",
    ),
    CommandEntry(
        name="diag",
        summary="Run hardware diagnostic test (WAN ping, DNS, default gateway)",
        category="cellular",
        details="Triggers the router's internal WAN & NCSI internet connectivity self-diagnostic check and reports pass/fail status.",
        examples=("tplink-cli diag", "tplink-cli diag --json"),
        batchable=True,
    ),
    CommandEntry(
        name="data-limit",
        summary="Inspect or set monthly cellular data allowance quota",
        category="cellular",
        details="Displays monthly SIM data cap enforcement, billing cycle reset day, warning threshold, and current period data consumption.",
        examples=("tplink-cli data-limit", "tplink-cli data-limit --limit 50000 --day 1"),
        batchable=True,
    ),
    CommandEntry(
        name="dns",
        summary="Inspect or customize primary & secondary DNS resolvers",
        category="network",
        details="View active WAN IPv4/IPv6 DNS servers or switch quickly to Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9), or custom resolvers.",
        examples=("tplink-cli dns", "tplink-cli dns set 1.1.1.1 1.0.0.1"),
        batchable=True,
        interactive_mode="dns",
    ),
    CommandEntry(
        name="ipv6",
        summary="Inspect router IPv6 stack state or toggle on/off",
        category="network",
        details="Checks router IPv6 WAN bearer state, SLAAC/address assignment, and toggles IPv6 stack enabled or disabled.",
        examples=("tplink-cli ipv6", "tplink-cli ipv6 on", "tplink-cli ipv6 off"),
        batchable=True,
        interactive_mode="ipv6",
    ),
    CommandEntry(
        name="clients",
        summary="List connected LAN devices (IP, MAC address, hostname)",
        category="network",
        details="Enumerates all connected Wi-Fi and Ethernet LAN clients with hostname, assigned IPv4 address, MAC address, and DHCP lease timer.",
        examples=("tplink-cli clients", "tplink-cli clients --json"),
        batchable=True,
    ),
    CommandEntry(
        name="reservation",
        summary="Manage DHCP static IP address reservations",
        category="network",
        details="List, bind, or remove static MAC-to-IPv4 DHCP reservations so servers and local devices always receive fixed LAN addresses.",
        examples=("tplink-cli reservation list", "tplink-cli reservation add AA:BB:CC:DD:EE:FF 192.168.1.50"),
        batchable=True,
    ),
    CommandEntry(
        name="profile",
        summary="Validate active Wi-Fi profile and gateway safety",
        category="network",
        details="Verifies your host machine's connected Wi-Fi SSID, default gateway IP, and Network Guard safety match against the target router.",
        examples=("tplink-cli profile", "tplink-cli profile check"),
        batchable=True,
    ),
    CommandEntry(
        name="wifi-guard",
        summary="Verify and optimize Wi-Fi link stability (no Ethernet needed)",
        category="network",
        details="Audits wireless interface power-save and NetworkManager autoconnect priority so LTE band changes never drop local Wi-Fi.",
        examples=("tplink-cli wifi-guard", "tplink-cli wifi-guard --optimize"),
        batchable=True,
    ),
    CommandEntry(
        name="wifi",
        summary="View or configure 2.4GHz / 5GHz radios and SSIDs",
        category="wifi",
        details="Inspects dual-band 2.4GHz and 5GHz wireless radios, SSIDs, channels, and client counts, or toggles radio power state.",
        examples=("tplink-cli wifi", "tplink-cli wifi --band 5GHz --toggle on"),
        batchable=True,
        interactive_mode="wifi",
    ),
    CommandEntry(
        name="guest-wifi",
        summary="Configure isolated dual-band Guest Wi-Fi and passwords",
        category="wifi",
        details="Inspects or configures isolated 2.4GHz/5GHz Guest Wi-Fi networks, LAN isolation security, and WPA2 passphrases.",
        examples=("tplink-cli guest-wifi", "tplink-cli guest-wifi --toggle off"),
        batchable=True,
    ),
    CommandEntry(
        name="leds",
        summary="Control hardware indicator LEDs and Night Mode schedule",
        category="wifi",
        details="Checks front-panel LED state and configures Night Mode quiet hours so status LEDs automatically turn off overnight.",
        examples=("tplink-cli leds", "tplink-cli leds --night-mode on --start 22:00 --end 07:00"),
        batchable=True,
        interactive_mode="leds",
    ),
    CommandEntry(
        name="reboot-schedule",
        summary="Configure automated periodic reboot timer (daily/weekly)",
        category="wifi",
        details="Inspects or schedules unattended periodic router maintenance reboots at a specified 24-hour clock time.",
        examples=("tplink-cli reboot-schedule", "tplink-cli reboot-schedule on --time 03:30 --mode daily"),
        batchable=True,
    ),
    CommandEntry(
        name="op-mode",
        summary="View or switch router operating mode (3G/4G vs Wireless)",
        category="wifi",
        details="Displays active router operating mode (3G/4G Cellular Router vs Wireless Router) and 4G WAN backup failover switch.",
        examples=("tplink-cli op-mode", "tplink-cli op-mode --json"),
        batchable=True,
    ),
    CommandEntry(
        name="port-forward",
        summary="Manage NAT virtual server port forwarding rules",
        category="nat",
        details="Lists, creates, or deletes external-to-internal TCP/UDP NAT virtual server port forwarding rules.",
        examples=("tplink-cli port-forward list", "tplink-cli port-forward add web 8080 192.168.1.150 80 --proto TCP"),
        batchable=True,
    ),
    CommandEntry(
        name="dmz",
        summary="Inspect or configure DMZ host IP forwarding",
        category="nat",
        details="Checks DMZ exposed host state or forwards all unmatched incoming WAN traffic to a designated LAN IP.",
        examples=("tplink-cli dmz", "tplink-cli dmz off"),
        batchable=True,
    ),
    CommandEntry(
        name="upnp",
        summary="Manage Universal Plug and Play (UPnP) service",
        category="nat",
        details="Displays UPnP service state and active dynamic port mappings requested by LAN applications, or toggles UPnP on/off.",
        examples=("tplink-cli upnp", "tplink-cli upnp on", "tplink-cli upnp off"),
        batchable=True,
        interactive_mode="upnp",
    ),
    CommandEntry(
        name="ddns",
        summary="Inspect Dynamic DNS providers and connection status",
        category="nat",
        details="Checks configured Dynamic DNS (TP-Link, No-IP, DynDNS) domain bindings and registration state.",
        examples=("tplink-cli ddns", "tplink-cli ddns --json"),
        batchable=True,
    ),
    CommandEntry(
        name="time",
        summary="View router clock or trigger network NTP time sync",
        category="nat",
        details="Displays router local clock, timezone, DST status, configured NTP servers, or triggers an immediate NTP sync.",
        examples=("tplink-cli time", "tplink-cli time --sync"),
        batchable=True,
    ),
    CommandEntry(
        name="fw-check",
        summary="Check for official TP-Link online firmware updates",
        category="nat",
        details="Queries TP-Link cloud metadata via the router to verify whether a newer official firmware build is available.",
        examples=("tplink-cli fw-check", "tplink-cli fw-check --json"),
        batchable=True,
    ),
    CommandEntry(
        name="sms",
        summary="Read inbox/outbox/drafts, or send SMS text messages",
        category="admin",
        details="Reads cellular SIM SMS messages (inbox or sent folder) with unread badges, or sends a new SMS message.",
        examples=("tplink-cli sms", "tplink-cli sms --folder sent", "tplink-cli sms send +94771234567 'Hello'"),
        batchable=True,
        interactive_mode="sms",
    ),
    CommandEntry(
        name="ussd",
        summary="Execute cellular USSD queries (*344#, *123#, balance)",
        category="admin",
        details="Sends live GSM/LTE USSD session codes (e.g., Hutch *344#, Dialog *123#, Mobitel *100#) and displays carrier response.",
        examples=("tplink-cli ussd '*344#'", "tplink-cli ussd '*123#'"),
        batchable=False,
        interactive_mode="ussd",
    ),
    CommandEntry(
        name="logs",
        summary="Read, filter, or clear system and cellular event logs",
        category="admin",
        details="Fetches severity-colored router system, DHCP, and 4G LTE event logs with optional module/level filtering.",
        examples=("tplink-cli logs", "tplink-cli logs --lines 50 --module 4G"),
        batchable=True,
    ),
    CommandEntry(
        name="config",
        summary="Manage saved router credentials and endpoint settings",
        category="admin",
        details="Displays encrypted configuration file location, target host, username, stored password status, and expected SSID.",
        examples=("tplink-cli config show", "tplink-cli config set-password"),
        batchable=True,
    ),
    CommandEntry(
        name="cookie",
        summary="Inspect or update cached browser session cookie",
        category="admin",
        details="Shows active masked JSESSIONID browser session token or imports a fresh cookie string.",
        examples=("tplink-cli cookie", "tplink-cli cookie <JSESSIONID>"),
        batchable=True,
    ),
    CommandEntry(
        name="repl",
        summary="Launch interactive shell with tab auto-completion & history",
        category="admin",
        details="Exits full-screen TUI into a persistent single-session readline console (`tplink>`) holding an authenticated lease.",
        examples=("tplink-cli repl",),
        batchable=False,
    ),
    CommandEntry(
        name="reboot",
        summary="Safely reboot the TP-Link hardware router",
        category="admin",
        details="Protected hardware restart with explicit safety confirmation. Temporarily drops Wi-Fi & LTE for ~60-90 seconds.",
        examples=("tplink-cli reboot", "tplink-cli reboot --yes"),
        batchable=False,
        interactive_mode="reboot",
    ),
]

# Backward-compatible catalog list of 31 CLI commands for unit tests & quick lookup
COMMAND_CATALOG: List[Tuple[str, str]] = [
    (spec.name, spec.summary) for spec in COMMAND_SPECS if not spec.is_wizard
]

SPEC_BY_NAME: Dict[str, CommandEntry] = {spec.name: spec for spec in COMMAND_SPECS}

TUI_TABS: List[Tuple[str, str, Tuple[str, ...]]] = [
    (
        "quick",
        "1 ★ Quick",
        (
            "wizard:toggles",
            "wizard:band",
            "wizard:calibrate",
            "status",
            "signal",
            "band",
            "clients",
            "wifi",
            "ipv6",
            "diag",
        ),
    ),
    (
        "cellular",
        "2 Cellular & RF",
        ("signal", "band", "wizard:band", "cell-lock", "calibrate", "wizard:calibrate", "data-limit", "diag"),
    ),
    (
        "network",
        "3 WAN & LAN",
        ("status", "dns", "ipv6", "clients", "reservation", "profile", "wifi-guard"),
    ),
    (
        "wifi",
        "4 Wi-Fi & HW",
        ("wifi", "guest-wifi", "leds", "reboot-schedule", "op-mode", "wizard:toggles"),
    ),
    (
        "nat",
        "5 NAT & Sys",
        ("port-forward", "dmz", "upnp", "ddns", "time", "fw-check"),
    ),
    (
        "admin",
        "6 SMS & Admin",
        ("sms", "ussd", "logs", "config", "cookie", "repl", "reboot"),
    ),
]


def filter_commands(query: str) -> List[Tuple[str, str]]:
    """Filter standard command catalog using prefix, substring, and description match priorities."""
    if not query or not query.strip():
        return list(COMMAND_CATALOG)
    q = query.lower().strip()
    prefix = [c for c in COMMAND_CATALOG if c[0].lower().startswith(q)]
    name_contain = [c for c in COMMAND_CATALOG if q in c[0].lower() and c not in prefix]
    desc_contain = [
        c for c in COMMAND_CATALOG if q in c[1].lower() and c not in prefix and c not in name_contain
    ]
    return prefix + name_contain + desc_contain


def filter_specs(query: str) -> List[CommandEntry]:
    """Filter all CommandEntry specs (including wizards) by fuzzy query."""
    if not query or not query.strip():
        return list(COMMAND_SPECS)
    q = query.lower().strip()
    prefix = [s for s in COMMAND_SPECS if s.name.lower().startswith(q)]
    name_contain = [s for s in COMMAND_SPECS if q in s.name.lower() and s not in prefix]
    desc_contain = [
        s
        for s in COMMAND_SPECS
        if (q in s.summary.lower() or q in s.details.lower())
        and s not in prefix
        and s not in name_contain
    ]
    return prefix + name_contain + desc_contain


def read_key(fd: int) -> str:
    """Read a single keystroke or ANSI escape sequence from raw terminal fd."""
    ch = os.read(fd, 1).decode("utf-8", errors="ignore")
    if ch == "\x1b":
        r, _, _ = select.select([fd], [], [], 0.04)
        if r:
            seq1 = os.read(fd, 1).decode("utf-8", errors="ignore")
            if seq1 == "[":
                r2, _, _ = select.select([fd], [], [], 0.04)
                if r2:
                    seq2 = os.read(fd, 1).decode("utf-8", errors="ignore")
                    if seq2 == "A":
                        return "UP"
                    if seq2 == "B":
                        return "DOWN"
                    if seq2 == "C":
                        return "RIGHT"
                    if seq2 == "D":
                        return "LEFT"
                    if seq2 == "Z":
                        return "SHIFT_TAB"
                    if seq2 in ("5", "6"):
                        r3, _, _ = select.select([fd], [], [], 0.02)
                        if r3:
                            os.read(fd, 1)
                        return "PGUP" if seq2 == "5" else "PGDN"
            return "ESC"
        return "ESC"
    if ch in ("\r", "\n"):
        return "ENTER"
    if ch == " ":
        return "SPACE"
    if ch in ("\x7f", "\x08"):
        return "BACKSPACE"
    if ch == "\t":
        return "TAB"
    if ch == "\x03":
        return "CTRL_C"
    if ch == "\x04":
        return "CTRL_D"
    return ch


@dataclass
class LiveTelemetrySummary:
    polled: bool = False
    online: bool = False
    model: str = "Archer MR200 / Universal"
    carrier: str = "Press [r] to poll"
    band: str = "—"
    bars: int = 0
    wan_ip: str = "—"
    status_note: str = "Ready"


@dataclass
class ModalOption:
    key: str
    label: str
    hint: str = ""
    checked: bool = False


@dataclass
class ActiveModal:
    kind: str  # 'single', 'multi', 'toggles', 'input'
    title: str
    subtitle: str
    command_name: str
    options: List[ModalOption] = field(default_factory=list)
    cursor: int = 0
    input_value: str = ""
    input_placeholder: str = ""
    initial_states: Dict[str, bool] = field(default_factory=dict)


class TUIState:
    """
    Pure, deterministic Model-View-Update state container for the TP-Link TUI.
    Decoupled from raw termios I/O for 100% unit-testability and clean rendering.
    """

    def __init__(
        self,
        target_host: str = "http://192.168.1.1",
        router_model: str = "Archer MR200 / Universal",
        mono: bool = False,
        runner: Optional[Callable[[List[str], bool], str]] = None,
        telemetry_fetcher: Optional[Callable[[], LiveTelemetrySummary]] = None,
        toggle_fetcher: Optional[Callable[[], Dict[str, bool]]] = None,
        toggle_applier: Optional[Callable[[Dict[str, bool], Dict[str, bool], bool], str]] = None,
    ) -> None:
        self.target_host = target_host
        self.mono = mono
        self.tab_idx = 0
        self.cursor = 0
        self.checked: List[str] = []  # Preserves selection order
        self.search_active = False
        self.search_query = ""
        self.telemetry = LiveTelemetrySummary(model=router_model)
        self.modal: Optional[ActiveModal] = None

        # Output viewport state
        self.view_mode = "workspace"  # 'workspace' | 'output'
        self.output_title = ""
        self.output_lines: List[str] = []
        self.output_scroll = 0
        self.last_status_msg = "Tip: Use ↑/↓ to browse, Space to check [✔], Enter to run."

        # Exit / handoff signals
        self.should_quit = False
        self.exit_command: Optional[List[str]] = None
        self.print_on_exit: Optional[str] = None

        # Injectable callbacks for live router actions
        self.runner = runner
        self.telemetry_fetcher = telemetry_fetcher
        self.toggle_fetcher = toggle_fetcher
        self.toggle_applier = toggle_applier

    def current_items(self) -> List[CommandEntry]:
        if self.search_active or self.search_query.strip():
            return filter_specs(self.search_query)
        _, _, names = TUI_TABS[self.tab_idx]
        return [SPEC_BY_NAME[n] for n in names if n in SPEC_BY_NAME]

    def clamp_cursor(self) -> None:
        items = self.current_items()
        if not items:
            self.cursor = 0
        elif self.cursor >= len(items):
            self.cursor = len(items) - 1
        elif self.cursor < 0:
            self.cursor = 0

    def toggle_check(self, name: str) -> None:
        spec = SPEC_BY_NAME.get(name)
        if not spec or not spec.batchable:
            self.last_status_msg = f"'{name}' is interactive — press Enter to launch it."
            return
        if name in self.checked:
            self.checked.remove(name)
            self.last_status_msg = f"Unchecked [{name}] ({len(self.checked)} selected)"
        else:
            self.checked.append(name)
            self.last_status_msg = f"Selected [✔ {name}] ({len(self.checked)} queued — press Enter to run batch)"

    def refresh_telemetry(self) -> None:
        if self.telemetry_fetcher:
            self.telemetry = self.telemetry_fetcher()
            if self.telemetry.online:
                self.last_status_msg = (
                    f"Live RF synced: {self.telemetry.carrier} • {self.telemetry.band} ({self.telemetry.bars}/4 bars)"
                )
            else:
                self.last_status_msg = f"Telemetry check: {self.telemetry.status_note}"
        else:
            self.last_status_msg = "Telemetry poller unavailable in offline mode."

    def _open_modal_for_spec(self, spec: CommandEntry) -> bool:
        mode = spec.interactive_mode
        if not mode:
            return False

        if mode in ("band", "band_picker"):
            opts = [
                ModalOption("status", "Inspect Current Active Band", "Read-only RF & EARFCN check"),
                ModalOption("8", "Lock Band 8  (900 MHz FDD)", "Best indoor reach & rain stability"),
                ModalOption("3", "Lock Band 3  (1800 MHz FDD)", "High-speed primary LTE carrier"),
                ModalOption("1", "Lock Band 1  (2100 MHz FDD)", "Standard 4G capacity layer"),
                ModalOption("40", "Lock Band 40 (2300 MHz TDD)", "High-capacity TDD urban carrier"),
                ModalOption("7", "Lock Band 7  (2600 MHz FDD)", "Ultra-dense metro carrier"),
                ModalOption("20", "Lock Band 20 (800 MHz FDD)", "Long-range rural sub-1GHz"),
                ModalOption("auto", "Automatic Network Selection", "Restore carrier auto-roaming"),
            ]
            if mode == "band_picker":
                opts = opts[1:]  # Direct band lock options
            self.modal = ActiveModal(
                kind="single",
                title="LTE FREQUENCY BAND SELECTOR",
                subtitle="↑/↓ Move • Space/Enter Confirm • Esc Cancel",
                command_name="band",
                options=opts,
                cursor=0,
            )
            return True

        if mode == "calibrate":
            opts = [
                ModalOption("8", "Band 8  (900 MHz)", "Extended range / indoor penetration", checked=True),
                ModalOption("3", "Band 3  (1800 MHz)", "High-throughput FDD primary", checked=True),
                ModalOption("1", "Band 1  (2100 MHz)", "Mid-band 4G layer", checked=False),
                ModalOption("40", "Band 40 (2300 MHz)", "High-capacity TDD band", checked=False),
                ModalOption("auto", "Auto Mode Baseline", "Compare against automatic roaming", checked=True),
                ModalOption("__dry_run__", "Dry-Run Simulation Mode", "Test safely without radio detach", checked=True),
            ]
            self.modal = ActiveModal(
                kind="multi",
                title="MULTI-BAND RF CALIBRATION SWEEP",
                subtitle="↑/↓ Move • Space Toggle [✔] • Enter Run Sweep • Esc Cancel",
                command_name="calibrate",
                options=opts,
                cursor=0,
            )
            return True

        if mode == "toggles":
            live_states = {
                "ipv6": False,
                "wifi_2g": True,
                "wifi_5g": True,
                "guest_wifi": False,
                "upnp": True,
                "led_night": False,
            }
            if self.toggle_fetcher:
                try:
                    fetched = self.toggle_fetcher()
                    live_states.update(fetched)
                except Exception:
                    pass
            opts = [
                ModalOption("ipv6", "IPv6 WAN Stack", "Dual-stack IPv6 router bearer", checked=live_states["ipv6"]),
                ModalOption("wifi_2g", "2.4 GHz Wi-Fi Radio", "Primary long-range WLAN AP", checked=live_states["wifi_2g"]),
                ModalOption("wifi_5g", "5 GHz Wi-Fi Radio", "High-speed 802.11ac WLAN AP", checked=live_states["wifi_5g"]),
                ModalOption("guest_wifi", "Isolated Guest Wi-Fi", "Dual-band visitor network", checked=live_states["guest_wifi"]),
                ModalOption("upnp", "UPnP Port Mapping", "Universal Plug and Play NAT", checked=live_states["upnp"]),
                ModalOption("led_night", "LED Night Mode (22:00-07:00)", "Dim front-panel LEDs overnight", checked=live_states["led_night"]),
            ]
            self.modal = ActiveModal(
                kind="toggles",
                title="ROUTER QUICK FEATURE SWITCHBOARD",
                subtitle="↑/↓ Move • Space Flip [● ON / ○ OFF] • Enter Apply Changes • Esc Cancel",
                command_name="wizard:toggles",
                options=opts,
                cursor=0,
                initial_states=dict(live_states),
            )
            return True

        if mode == "ipv6":
            self.modal = ActiveModal(
                kind="single",
                title="ROUTER IPv6 STACK CONTROL",
                subtitle="↑/↓ Move • Space/Enter Confirm • Esc Cancel",
                command_name="ipv6",
                options=[
                    ModalOption("status", "Inspect Current IPv6 Status", "View stack state, IP & DNS"),
                    ModalOption("on", "Enable IPv6 Stack (ON)", "Activate dual-stack IPv6 WAN"),
                    ModalOption("off", "Disable IPv6 Stack (OFF)", "Use IPv4-only WAN mode"),
                ],
            )
            return True

        if mode == "upnp":
            self.modal = ActiveModal(
                kind="single",
                title="UPnP NAT SERVICE CONTROL",
                subtitle="↑/↓ Move • Space/Enter Confirm • Esc Cancel",
                command_name="upnp",
                options=[
                    ModalOption("status", "Inspect UPnP Status & Port Leases", "Read active dynamic mappings"),
                    ModalOption("on", "Enable UPnP Service (ON)", "Allow automatic LAN port leases"),
                    ModalOption("off", "Disable UPnP Service (OFF)", "Strict manual NAT forwarding only"),
                ],
            )
            return True

        if mode == "wifi":
            self.modal = ActiveModal(
                kind="single",
                title="WI-FI RADIO MANAGEMENT",
                subtitle="↑/↓ Move • Space/Enter Confirm • Esc Cancel",
                command_name="wifi",
                options=[
                    ModalOption("status", "Inspect 2.4GHz & 5GHz Wi-Fi Status", "Show SSIDs, channels & clients"),
                    ModalOption("2.4_on", "Enable 2.4GHz Radio (ON)", "Turn 2.4GHz access point on"),
                    ModalOption("5_on", "Enable 5GHz Radio (ON)", "Turn 5GHz access point on"),
                    ModalOption("5_off", "Disable 5GHz Radio (OFF)", "Turn 5GHz access point off"),
                ],
            )
            return True

        if mode == "leds":
            self.modal = ActiveModal(
                kind="single",
                title="FRONT-PANEL LED & NIGHT MODE",
                subtitle="↑/↓ Move • Space/Enter Confirm • Esc Cancel",
                command_name="leds",
                options=[
                    ModalOption("status", "Inspect Current LED Status", "Check LEDs & schedule hours"),
                    ModalOption("night_on", "Enable Night Mode (22:00 -> 07:00)", "Turn LEDs off automatically at night"),
                    ModalOption("night_off", "Disable Night Mode", "Keep status LEDs active 24/7"),
                ],
            )
            return True

        if mode == "dns":
            self.modal = ActiveModal(
                kind="single",
                title="WAN DNS RESOLVER PROFILES",
                subtitle="↑/↓ Move • Space/Enter Confirm • Esc Cancel",
                command_name="dns",
                options=[
                    ModalOption("show", "Inspect Current Active DNS", "Show active WAN DNS servers"),
                    ModalOption("1.1.1.1,1.0.0.1", "Cloudflare 1.1.1.1 + 1.0.0.1", "Fastest low-latency privacy DNS"),
                    ModalOption("8.8.8.8,8.8.4.4", "Google Public DNS 8.8.8.8 + 8.8.4.4", "High-reliability global resolvers"),
                    ModalOption("9.9.9.9,149.112.112.112", "Quad9 Security DNS 9.9.9.9", "Malware & phishing domain filtering"),
                ],
            )
            return True

        if mode == "sms":
            self.modal = ActiveModal(
                kind="single",
                title="CELLULAR SMS MESSAGING",
                subtitle="↑/↓ Move • Space/Enter Confirm • Esc Cancel",
                command_name="sms",
                options=[
                    ModalOption("inbox", "Read SMS Inbox (Latest 10)", "Fetch incoming carrier & OTP texts"),
                    ModalOption("sent", "Read Sent SMS Folder", "Inspect outgoing messages"),
                ],
            )
            return True

        if mode == "ussd":
            self.modal = ActiveModal(
                kind="input",
                title="EXECUTE CARRIER USSD CODE",
                subtitle="Type USSD code (or press Enter for *344#) • Esc Cancel",
                command_name="ussd",
                input_value="*344#",
                input_placeholder="e.g. *344# (Hutch), *123# (Dialog), *100# (Mobitel)",
            )
            return True

        if mode == "reboot":
            self.modal = ActiveModal(
                kind="single",
                title="CONFIRM HARDWARE REBOOT",
                subtitle="↑/↓ Move • Enter Confirm • Esc Cancel",
                command_name="reboot",
                options=[
                    ModalOption("cancel", "Cancel (Keep Router Online)", "Return safely to TUI workspace"),
                    ModalOption("confirm", "Reboot TP-Link Router Now", "Drops Wi-Fi & LTE for ~60-90 seconds"),
                ],
            )
            return True

        return False

    def _execute_cli_batch(self, arg_lists: List[List[str]], title: str) -> None:
        if not self.runner:
            # Fallback if no in-TUI runner was injected: exit TUI with first command
            if arg_lists:
                self.exit_command = arg_lists[0]
                self.should_quit = True
            return

        rendered_chunks: List[str] = []
        for argv in arg_lists:
            out = self.runner(argv, self.mono)
            if out.strip():
                rendered_chunks.append(out.strip("\n"))

        combined = "\n\n".join(rendered_chunks) if rendered_chunks else "(Command completed with no output)"
        self.output_title = title
        self.output_lines = combined.splitlines()
        self.output_scroll = 0
        self.view_mode = "output"

    def _confirm_modal(self) -> None:
        m = self.modal
        if not m:
            return
        self.modal = None

        if m.kind == "single":
            if not m.options:
                return
            chosen = m.options[m.cursor]
            cname = m.command_name
            if cname == "band":
                argv = ["band"] if chosen.key == "status" else ["band", chosen.key]
                self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")
            elif cname == "ipv6":
                argv = ["ipv6"] if chosen.key == "status" else ["ipv6", chosen.key]
                self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")
            elif cname == "upnp":
                argv = ["upnp"] if chosen.key == "status" else ["upnp", chosen.key]
                self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")
            elif cname == "wifi":
                if chosen.key == "status":
                    argv = ["wifi"]
                elif chosen.key == "2.4_on":
                    argv = ["wifi", "--band", "2.4GHz", "--toggle", "on"]
                elif chosen.key == "5_on":
                    argv = ["wifi", "--band", "5GHz", "--toggle", "on"]
                else:
                    argv = ["wifi", "--band", "5GHz", "--toggle", "off"]
                self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")
            elif cname == "leds":
                if chosen.key == "status":
                    argv = ["leds"]
                elif chosen.key == "night_on":
                    argv = ["leds", "--night-mode", "on", "--start", "22:00", "--end", "07:00"]
                else:
                    argv = ["leds", "--night-mode", "off"]
                self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")
            elif cname == "dns":
                if chosen.key == "show":
                    argv = ["dns", "show"]
                else:
                    p_ip, s_ip = chosen.key.split(",", 1)
                    argv = ["dns", "set", p_ip, s_ip]
                self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")
            elif cname == "sms":
                argv = ["sms", "--folder", chosen.key]
                self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")
            elif cname == "reboot":
                if chosen.key == "confirm":
                    self._execute_cli_batch([["reboot", "--yes"]], "tplink-cli reboot --yes")
                else:
                    self.last_status_msg = "Reboot cancelled."

        elif m.kind == "multi" and m.command_name == "calibrate":
            bands = [o.key for o in m.options if o.checked and not o.key.startswith("__")]
            dry = any(o.checked and o.key == "__dry_run__" for o in m.options)
            if not bands:
                bands = ["8", "3", "auto"]
            argv = ["calibrate", "--no-web", "--bands", ",".join(bands)]
            if dry:
                argv.append("--dry-run")
            self._execute_cli_batch([argv], f"tplink-cli {' '.join(argv)}")

        elif m.kind == "toggles":
            new_states = {o.key: o.checked for o in m.options}
            if self.toggle_applier:
                out = self.toggle_applier(m.initial_states, new_states, self.mono)
                self.output_title = "Quick Feature Switchboard Result"
                self.output_lines = out.strip("\n").splitlines()
                self.output_scroll = 0
                self.view_mode = "output"
            else:
                changed = [k for k, v in new_states.items() if m.initial_states.get(k) != v]
                self.last_status_msg = (
                    f"Toggles updated: {', '.join(changed)}" if changed else "No toggle changes to apply."
                )

        elif m.kind == "input" and m.command_name == "ussd":
            code = m.input_value.strip()
            if code:
                self._execute_cli_batch([["ussd", code]], f"tplink-cli ussd {code}")

    def handle_key(self, key: str) -> None:
        """Process a single logical key event under MVU architecture."""
        if key in ("CTRL_C", "CTRL_D"):
            self.should_quit = True
            return

        # 1. Output Viewport Mode
        if self.view_mode == "output":
            if key in ("ESC", "BACKSPACE", "ENTER", "q", "b"):
                self.view_mode = "workspace"
                return
            if key == "p":
                self.print_on_exit = "\n".join(self.output_lines)
                self.should_quit = True
                return
            if key in ("UP", "k"):
                self.output_scroll = max(0, self.output_scroll - 1)
            elif key in ("DOWN", "j"):
                self.output_scroll = min(max(0, len(self.output_lines) - 5), self.output_scroll + 1)
            elif key == "PGUP":
                self.output_scroll = max(0, self.output_scroll - 10)
            elif key == "PGDN":
                self.output_scroll = min(max(0, len(self.output_lines) - 5), self.output_scroll + 10)
            elif key == "m":
                self.mono = not self.mono
            return

        # 2. Modal Mode (Interactive Spacebar / Arrow / Enter Dialog)
        if self.modal is not None:
            m = self.modal
            if key == "ESC":
                self.modal = None
                self.last_status_msg = "Cancelled dialog."
                return
            if m.kind == "input":
                if key == "ENTER":
                    self._confirm_modal()
                elif key == "BACKSPACE":
                    m.input_value = m.input_value[:-1]
                elif len(key) == 1 and key.isprintable():
                    m.input_value += key
                return

            # single / multi / toggles
            if key in ("UP", "k"):
                m.cursor = (m.cursor - 1) % max(1, len(m.options))
            elif key in ("DOWN", "j"):
                m.cursor = (m.cursor + 1) % max(1, len(m.options))
            elif key == "SPACE":
                if m.kind in ("multi", "toggles") and m.options:
                    m.options[m.cursor].checked = not m.options[m.cursor].checked
                elif m.kind == "single":
                    self._confirm_modal()
            elif key == "ENTER":
                self._confirm_modal()
            elif key == "q":
                self.modal = None
            return

        # 3. Search Input Mode
        if self.search_active:
            if key == "ESC":
                self.search_active = False
                self.search_query = ""
                self.cursor = 0
                return
            if key == "ENTER":
                self.search_active = False
                self._activate_current()
                return
            if key == "BACKSPACE":
                if self.search_query:
                    self.search_query = self.search_query[:-1]
                    self.cursor = 0
                else:
                    self.search_active = False
                return
            if key == "UP":
                self.cursor = max(0, self.cursor - 1)
                return
            if key == "DOWN":
                items = self.current_items()
                self.cursor = min(max(0, len(items) - 1), self.cursor + 1)
                return
            if key == "TAB":
                self.search_active = False
                return
            if len(key) == 1 and key.isprintable():
                self.search_query += key
                self.cursor = 0
                return
            return

        # 4. Main Workspace Mode
        items = self.current_items()
        self.clamp_cursor()

        if key in ("q", "ESC"):
            if self.search_query:
                self.search_query = ""
                self.cursor = 0
            else:
                self.should_quit = True
            return

        if key == "/":
            self.search_active = True
            self.cursor = 0
            return

        if key == "m":
            self.mono = not self.mono
            mode_lbl = "Monochrome B&W" if self.mono else "TP-Link Brand Cyan"
            self.last_status_msg = f"Switched theme to {mode_lbl}."
            return

        if key == "r":
            self.refresh_telemetry()
            return

        if key == "c":
            self.checked.clear()
            self.last_status_msg = "Cleared all [✔] batch selections."
            return

        if key == "a":
            added = 0
            for it in items:
                if it.batchable and it.name not in self.checked:
                    self.checked.append(it.name)
                    added += 1
            self.last_status_msg = f"Checked {added} commands in tab ({len(self.checked)} total selected)."
            return

        if key in ("1", "2", "3", "4", "5", "6"):
            idx = int(key) - 1
            if 0 <= idx < len(TUI_TABS):
                self.tab_idx = idx
                self.search_query = ""
                self.cursor = 0
            return

        if key in ("RIGHT", "TAB"):
            self.tab_idx = (self.tab_idx + 1) % len(TUI_TABS)
            self.search_query = ""
            self.cursor = 0
            return

        if key in ("LEFT", "SHIFT_TAB"):
            self.tab_idx = (self.tab_idx - 1) % len(TUI_TABS)
            self.search_query = ""
            self.cursor = 0
            return

        if key in ("UP", "k"):
            if items:
                self.cursor = (self.cursor - 1) % len(items)
            return

        if key in ("DOWN", "j"):
            if items:
                self.cursor = (self.cursor + 1) % len(items)
            return

        if key == "PGUP":
            self.cursor = max(0, self.cursor - 6)
            return

        if key == "PGDN":
            self.cursor = min(max(0, len(items) - 1), self.cursor + 6)
            return

        if key == "SPACE":
            if not items:
                return
            cur = items[self.cursor]
            if cur.is_wizard:
                self._open_modal_for_spec(cur)
            else:
                self.toggle_check(cur.name)
            return

        if key == "ENTER":
            self._activate_current()

    def _activate_current(self) -> None:
        items = self.current_items()
        if not items:
            return
        cur = items[self.cursor]

        # If batch checkboxes are selected and current isn't an exclusive wizard, run batch!
        if self.checked and not cur.is_wizard:
            batch_cmds = [[name] for name in self.checked]
            title = f"Batch Execution ({len(batch_cmds)} commands: {', '.join(self.checked)})"
            self._execute_cli_batch(batch_cmds, title)
            return

        if cur.name == "repl":
            self.exit_command = ["repl"]
            self.should_quit = True
            return

        if cur.interactive_mode and self._open_modal_for_spec(cur):
            return

        self._execute_cli_batch([[cur.name]], f"tplink-cli {cur.name}")

    # ------------------------------------------------------------------
    # Rendering Engine
    # ------------------------------------------------------------------
    def render_frame(self, cols: int = 96, rows: int = 28) -> List[str]:
        """Render full TUI frame fitting within (cols x rows) terminal dimensions."""
        p = get_palette(mono=self.mono)
        w = max(62, min(cols - 1, 114))
        bdr = p.border

        lines: List[str] = []

        # 1. Header Card: Official TP-Link Pixel Emblem + Live Telemetry
        logo_variant = "compact" if rows >= 25 else "mini"
        logo_lines = render_logo_lines(logo_variant, mono=self.mono)
        lw = get_logo_width(logo_variant)

        theme_pill = (
            f"{p.white}[MONO B&W]{p.reset}"
            if self.mono
            else f"{p.brand_bold}[TP-LINK CYAN]{p.reset}"
        )
        conn_badge = (
            status_badge(True, "ONLINE", "OFFLINE", mono=self.mono)
            if self.telemetry.online
            else f"{p.brand_bold}● GATEWAY READY{p.reset}"
        )
        bars_str = (
            signal_bars(self.telemetry.bars, mono=self.mono)
            if self.telemetry.polled and self.telemetry.online
            else f"{p.muted}▁▁▁▁ (Press [r]){p.reset}"
        )

        right_w = max(36, w - lw - 7)
        meta_rows = [
            f"{p.brand_bold}tp-link{p.reset} {p.white}ROUTER & MODEM TUI{p.reset} {p.muted}v1.0.0{p.reset}  {theme_pill}",
            f"{p.muted}Universal Cellular LTE & Dual-Band Wi-Fi Command Center{p.reset}",
            f"{bdr}{'─' * min(right_w, 58)}{p.reset}",
            f"{p.muted}Gateway :{p.reset} {p.white}{self.target_host}{p.reset}   {conn_badge}",
            f"{p.muted}Device  :{p.reset} {p.text}{self.telemetry.model}{p.reset}",
            f"{p.muted}Carrier :{p.reset} {p.white}{self.telemetry.carrier}{p.reset}  {p.muted}Band:{p.reset} {p.brand_bold}{self.telemetry.band}{p.reset}",
            f"{p.muted}RF Link :{p.reset} {bars_str}   {p.muted}WAN:{p.reset} {p.text}{self.telemetry.wan_ip}{p.reset}",
            f"{p.muted}Batch   :{p.reset} {p.brand_bold}{len(self.checked)} checked [✔]{p.reset} {p.muted}(Space toggle • c clear • a all){p.reset}",
        ]

        hdr_height = max(len(logo_lines), len(meta_rows))
        lines.append(f"{bdr}╭─{p.reset}{p.brand_bold} ◆ TP-LINK TERMINAL CONTROL CENTER {p.reset}{bdr}{'─' * max(1, w - 38)}╮{p.reset}")
        for i in range(hdr_height):
            l_col = logo_lines[i] if i < len(logo_lines) else (" " * lw)
            r_col = meta_rows[i] if i < len(meta_rows) else ""
            combined = f" {l_col}   {pad_right(r_col, w - lw - 7)}"
            lines.append(f"{bdr}│{p.reset}{pad_right(combined, w - 2)}{bdr}│{p.reset}")

        # 2. If in Output Viewport Mode, render scrollable output box
        if self.view_mode == "output":
            lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")
            title_bar = (
                f" {p.brand_bold}▸ OUTPUT:{p.reset} {p.white}{self.output_title}{p.reset}"
            )
            lines.append(f"{bdr}│{p.reset}{pad_right(title_bar, w - 2)}{bdr}│{p.reset}")
            lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")

            avail_h = max(8, rows - len(lines) - 3)
            slice_lines = self.output_lines[self.output_scroll : self.output_scroll + avail_h]
            for ol in slice_lines:
                lines.append(f"{bdr}│{p.reset} {pad_right(ol, w - 4)} {bdr}│{p.reset}")
            for _ in range(max(0, avail_h - len(slice_lines))):
                lines.append(f"{bdr}│{p.reset}{' ' * (w - 2)}{bdr}│{p.reset}")

            total_l = len(self.output_lines)
            pos_info = f"Lines {min(total_l, self.output_scroll + 1)}-{min(total_l, self.output_scroll + len(slice_lines))}/{total_l}"
            foot = (
                f" {p.brand_bold}↑/↓{p.reset} Scroll  "
                f"{p.brand_bold}Esc/Enter{p.reset} Back to TUI  "
                f"{p.brand_bold}p{p.reset} Print to Shell & Exit  "
                f"{p.brand_bold}m{p.reset} Color/B&W   {p.muted}{pos_info}{p.reset}"
            )
            lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")
            lines.append(f"{bdr}│{p.reset}{pad_right(foot, w - 2)}{bdr}│{p.reset}")
            lines.append(f"{bdr}╰{'─' * (w - 2)}╯{p.reset}")
            return lines

        # 3. Tabs & Search Bar
        lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")
        tab_pills: List[str] = []
        for idx, (_, label, _) in enumerate(TUI_TABS):
            if idx == self.tab_idx and not (self.search_active or self.search_query):
                if p.mono:
                    tab_pills.append(f"{p.inverse}{p.white} {label} {p.reset}")
                else:
                    tab_pills.append(f"{p.brand_bold}[{label}]{p.reset}")
            else:
                tab_pills.append(f"{p.muted} {label} {p.reset}")
        tab_str = " " + " ".join(tab_pills)
        lines.append(f"{bdr}│{p.reset}{pad_right(tab_str, w - 2)}{bdr}│{p.reset}")

        if self.search_active or self.search_query:
            cursor_blk = f"{p.inverse} {p.reset}" if self.search_active else ""
            s_bar = (
                f" {p.brand_bold}⌕ Filter:{p.reset} {p.white}{self.search_query}{p.reset}{cursor_blk}"
                f"  {p.muted}(Esc to clear • ↑/↓ select • Enter run){p.reset}"
            )
            lines.append(f"{bdr}│{p.reset}{pad_right(s_bar, w - 2)}{bdr}│{p.reset}")

        # 4. Modal Overlay OR Split-Pane Workspace
        if self.modal is not None:
            m = self.modal
            lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")
            m_hdr = f" {p.brand_bold}◆ {m.title}{p.reset}   {p.muted}{m.subtitle}{p.reset}"
            lines.append(f"{bdr}│{p.reset}{pad_right(m_hdr, w - 2)}{bdr}│{p.reset}")
            lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")

            body_h = max(8, rows - len(lines) - 4)
            modal_rows: List[str] = []
            if m.kind == "input":
                modal_rows.append("")
                modal_rows.append(f"  {p.muted}{m.input_placeholder}{p.reset}")
                modal_rows.append("")
                modal_rows.append(
                    f"  {p.brand_bold}❯ {p.white}{m.input_value}{p.inverse} {p.reset}"
                )
            else:
                for idx, opt in enumerate(m.options):
                    focused = idx == m.cursor
                    ptr = f"{p.brand_bold}❯{p.reset}" if focused else " "
                    if m.kind == "multi":
                        box = (
                            f"{p.success}[✔]{p.reset}"
                            if opt.checked
                            else f"{p.muted}[ ]{p.reset}"
                        )
                    elif m.kind == "toggles":
                        box = (
                            status_badge(True, "ON ", "OFF", mono=self.mono)
                            if opt.checked
                            else status_badge(False, "ON ", "OFF", mono=self.mono)
                        )
                    else:
                        box = f"{p.brand_bold}(●){p.reset}" if focused else f"{p.muted}( ){p.reset}"

                    lbl_col = p.white if focused else p.text
                    lbl_padded = pad_right(f"{lbl_col}{opt.label}{p.reset}", 32)
                    modal_rows.append(f" {ptr} {box}  {lbl_padded}  {p.muted}{opt.hint}{p.reset}")

            for i in range(body_h):
                r_txt = modal_rows[i] if i < len(modal_rows) else ""
                lines.append(f"{bdr}│{p.reset}{pad_right(r_txt, w - 2)}{bdr}│{p.reset}")
        else:
            items = self.current_items()
            self.clamp_cursor()
            body_h = max(8, rows - len(lines) - 4)

            if w >= 84:
                # 2-Pane Split Layout (Left Action List │ Right Inspector)
                left_w = max(36, int((w - 3) * 0.48))
                right_w_pane = (w - 3) - left_w
                lines.append(f"{bdr}├{'─' * left_w}┬{'─' * right_w_pane}┤{p.reset}")

                # Left pane scrolling window
                start_i = 0
                if self.cursor >= body_h:
                    start_i = self.cursor - body_h + 1
                vis_items = items[start_i : start_i + body_h]

                left_rows: List[str] = []
                if not vis_items:
                    left_rows.append(f" {p.muted}No matching tools for '{self.search_query}'{p.reset}")
                else:
                    for off, spec in enumerate(vis_items):
                        actual = start_i + off
                        is_sel = actual == self.cursor
                        is_chk = spec.name in self.checked

                        ptr = f"{p.brand_bold}❯{p.reset}" if is_sel else " "
                        if spec.is_wizard:
                            chk = f"{p.warning}[★]{p.reset}" if not p.mono else f"{p.white}[★]{p.reset}"
                        elif not spec.batchable:
                            chk = f"{p.muted}[▸]{p.reset}"
                        elif is_chk:
                            chk = f"{p.success}[✔]{p.reset}" if not p.mono else f"{p.white}[✔]{p.reset}"
                        else:
                            chk = f"{p.muted}[ ]{p.reset}"

                        display_name = spec.name.replace("wizard:", "★ ")
                        name_col = p.brand_bold if is_sel else (p.white if is_chk else p.text)
                        sum_col = p.white if is_sel else p.muted
                        name_pad = pad_right(f"{name_col}{display_name}{p.reset}", 15)
                        left_rows.append(
                            truncate_ansi(f" {ptr} {chk} {name_pad} {sum_col}{spec.summary}{p.reset}", left_w)
                        )

                # Right pane inspector for focused command
                right_rows: List[str] = []
                if items:
                    cur = items[self.cursor]
                    disp_title = cur.name.replace("wizard:", "WIZARD: ").upper()
                    kind_tag = (
                        "INTERACTIVE WIZARD"
                        if cur.is_wizard
                        else ("BATCHABLE [✔]" if cur.batchable else "INTERACTIVE TOOL")
                    )
                    right_rows.append(f" {p.brand_bold}◆ {disp_title}{p.reset}")
                    right_rows.append(f" {p.muted}Type:{p.reset} {p.white}{kind_tag}{p.reset}")
                    right_rows.append(f" {bdr}{'─' * max(10, right_w_pane - 3)}{p.reset}")

                    # Word-wrap details cleanly into right pane
                    words = cur.details.split(" ")
                    cur_line = ""
                    max_rw = right_w_pane - 3
                    for wd in words:
                        cand = f"{cur_line} {wd}".strip() if cur_line else wd
                        if len(cand) <= max_rw:
                            cur_line = cand
                        else:
                            right_rows.append(f" {p.text}{cur_line}{p.reset}")
                            cur_line = wd
                    if cur_line:
                        right_rows.append(f" {p.text}{cur_line}{p.reset}")

                    right_rows.append("")
                    right_rows.append(f" {p.brand_bold}▸ Usage & Controls{p.reset}")
                    for ex in cur.examples[:3]:
                        right_rows.append(f"   {p.white}{ex}{p.reset}")

                    if self.checked:
                        right_rows.append("")
                        q_str = ", ".join(self.checked[:4])
                        if len(self.checked) > 4:
                            q_str += f" (+{len(self.checked) - 4})"
                        right_rows.append(f" {p.success}✔ Queued ({len(self.checked)}):{p.reset} {p.text}{q_str}{p.reset}")

                for i in range(body_h):
                    lr = left_rows[i] if i < len(left_rows) else ""
                    rr = right_rows[i] if i < len(right_rows) else ""
                    lines.append(
                        f"{bdr}│{p.reset}{pad_right(lr, left_w)}{bdr}│{p.reset}{pad_right(rr, right_w_pane)}{bdr}│{p.reset}"
                    )
                lines.append(f"{bdr}├{'─' * left_w}┴{'─' * right_w_pane}┤{p.reset}")
            else:
                # Compact Single-Column Layout (< 84 cols)
                lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")
                list_h = max(5, body_h - 3)
                start_i = max(0, self.cursor - list_h + 1) if self.cursor >= list_h else 0
                vis_items = items[start_i : start_i + list_h]
                for i in range(list_h):
                    if i < len(vis_items):
                        spec = vis_items[i]
                        actual = start_i + i
                        is_sel = actual == self.cursor
                        is_chk = spec.name in self.checked
                        ptr = f"{p.brand_bold}❯{p.reset}" if is_sel else " "
                        chk = f"{p.success}[✔]{p.reset}" if is_chk else (f"{p.warning}[★]{p.reset}" if spec.is_wizard else f"{p.muted}[ ]{p.reset}")
                        dn = pad_right(spec.name.replace("wizard:", "★ "), 15)
                        row_s = f" {ptr} {chk} {p.white if is_sel else p.text}{dn}{p.reset} {p.muted}{spec.summary}{p.reset}"
                    else:
                        row_s = ""
                    lines.append(f"{bdr}│{p.reset}{pad_right(row_s, w - 2)}{bdr}│{p.reset}")
                lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")
                cur_hint = items[self.cursor].details if items else ""
                lines.append(f"{bdr}│{p.reset} {pad_right(f'{p.text}{cur_hint}{p.reset}', w - 4)} {bdr}│{p.reset}")
                lines.append(f"{bdr}├{'─' * (w - 2)}┤{p.reset}")

        # 5. Status & Keybindings Footer Bar
        status_line = f" {p.brand}▸{p.reset} {p.muted}{self.last_status_msg}{p.reset}"
        if w >= 86:
            keys_line = (
                f" {p.brand_bold}↑↓{p.reset} Move  "
                f"{p.brand_bold}←→{p.reset} Tabs  "
                f"{p.brand_bold}Space{p.reset} [✔] Select  "
                f"{p.brand_bold}Enter{p.reset} Run  "
                f"{p.brand_bold}/{p.reset} Search  "
                f"{p.brand_bold}m{p.reset} Color/B&W  "
                f"{p.brand_bold}r{p.reset} Poll RF  "
                f"{p.brand_bold}q{p.reset} Quit"
            )
        else:
            keys_line = (
                f" {p.brand_bold}↑↓{p.reset} Move "
                f"{p.brand_bold}←→{p.reset} Tab "
                f"{p.brand_bold}Space{p.reset} [✔] "
                f"{p.brand_bold}Enter{p.reset} Run "
                f"{p.brand_bold}/{p.reset} Find "
                f"{p.brand_bold}m{p.reset} B&W "
                f"{p.brand_bold}r{p.reset} RF "
                f"{p.brand_bold}q{p.reset} Quit"
            )
        lines.append(f"{bdr}│{p.reset}{pad_right(status_line, w - 2)}{bdr}│{p.reset}")
        lines.append(f"{bdr}│{p.reset}{pad_right(keys_line, w - 2)}{bdr}│{p.reset}")
        lines.append(f"{bdr}╰{'─' * (w - 2)}╯{p.reset}")
        return lines


# ----------------------------------------------------------------------
# Live Router Hooks for In-TUI Execution & Quick Toggles
# ----------------------------------------------------------------------
def _make_live_callbacks(
    target_host: str,
    base_flags: Optional[List[str]] = None,
) -> Tuple[
    Callable[[List[str], bool], str],
    Callable[[], LiveTelemetrySummary],
    Callable[[], Dict[str, bool]],
    Callable[[Dict[str, bool], Dict[str, bool], bool], str],
]:
    flags = list(base_flags or [])

    def poll_telemetry() -> LiveTelemetrySummary:
        try:
            import argparse
            from tplink_router.cli.main import get_client
            from tplink_router.core.session import SafeSession

            ns = argparse.Namespace(
                host=target_host,
                username=None,
                password=None,
                cookie=None,
                force=False,
                json=False,
                mono=False,
            )
            client = get_client(ns)
            with SafeSession(client):
                tel = client.get_telemetry()
            dev_model = tel.device.model or "TP-Link Router"
            if tel.lte:
                return LiveTelemetrySummary(
                    polled=True,
                    online=True,
                    model=f"{dev_model} ({tel.device.hardware_version})",
                    carrier=tel.lte.isp_name or "LTE Carrier",
                    band=str(tel.lte.band or "Auto"),
                    bars=int(tel.lte.rf.signal_bars or 0),
                    wan_ip=tel.ipv4.ip or "Connected",
                    status_note="Synced",
                )
            return LiveTelemetrySummary(
                polled=True,
                online=True,
                model=dev_model,
                carrier="Broadband WAN",
                band="N/A",
                bars=4,
                wan_ip=tel.ipv4.ip or "Connected",
                status_note="Synced",
            )
        except Exception as exc:
            return LiveTelemetrySummary(
                polled=True,
                online=False,
                model="TP-Link Gateway",
                carrier="Unreachable / Auth Needed",
                band="—",
                bars=0,
                wan_ip="Offline",
                status_note=str(exc)[:48],
            )

    def run_cli_captured(cmd_argv: List[str], mono: bool) -> str:
        from tplink_router.cli.main import build_parser, handle_cli_error

        full_argv = list(flags)
        if mono and "--mono" not in full_argv:
            full_argv.append("--mono")
        full_argv.extend(cmd_argv)

        buf = io.StringIO()
        parser = build_parser()
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                parsed = parser.parse_args(full_argv)
                for _k, _v in [
                    ("json", False),
                    ("host", None),
                    ("username", None),
                    ("password", None),
                    ("cookie", None),
                    ("force", False),
                    ("legacy", False),
                    ("mono", mono),
                ]:
                    if not hasattr(parsed, _k):
                        setattr(parsed, _k, _v)
                if hasattr(parsed, "func"):
                    parsed.func(parsed)
        except SystemExit:
            pass
        except Exception as exc:
            with redirect_stdout(buf), redirect_stderr(buf):
                handle_cli_error(exc, argparse.Namespace(json=False, host=target_host, mono=mono))
        return buf.getvalue()

    def fetch_toggles() -> Dict[str, bool]:
        import argparse
        from tplink_router.cli.main import get_client
        from tplink_router.core.session import SafeSession

        ns = argparse.Namespace(
            host=target_host, username=None, password=None, cookie=None, force=False, json=False
        )
        states = {
            "ipv6": False,
            "wifi_2g": True,
            "wifi_5g": True,
            "guest_wifi": False,
            "upnp": False,
            "led_night": False,
        }
        client = get_client(ns)
        with SafeSession(client):
            _, v6 = client.get_wan_config()
            states["ipv6"] = bool(v6.enabled or v6.ip)
            if hasattr(client, "get_wifi_status"):
                for net in client.get_wifi_status():
                    if "2.4" in net.get("band", ""):
                        states["wifi_2g"] = bool(net.get("enabled"))
                    elif "5" in net.get("band", ""):
                        states["wifi_5g"] = bool(net.get("enabled"))
            if hasattr(client, "get_guest_wifi"):
                gw = client.get_guest_wifi()
                states["guest_wifi"] = any(n.enabled for n in gw.networks)
            if hasattr(client, "get_upnp"):
                states["upnp"] = bool(client.get_upnp().enabled)
            if hasattr(client, "get_led_status"):
                states["led_night"] = bool(client.get_led_status().get("night_mode_enabled"))
        return states

    def apply_toggles(
        initial: Dict[str, bool], updated: Dict[str, bool], mono: bool
    ) -> str:
        import argparse
        from tplink_router.cli.main import get_client
        from tplink_router.core.session import SafeSession

        changed = {k: v for k, v in updated.items() if initial.get(k) != v}
        p = get_palette(mono=mono)
        if not changed:
            return render_panel(
                title="QUICK FEATURE SWITCHBOARD",
                sections=[[f"{p.muted}No switches were modified.{p.reset}"]],
                mono=mono,
            )

        ns = argparse.Namespace(
            host=target_host, username=None, password=None, cookie=None, force=False, json=False
        )
        results: List[str] = []
        try:
            client = get_client(ns)
            with SafeSession(client):
                if "ipv6" in changed:
                    client.toggle_ipv6(changed["ipv6"])
                    results.append(f"{p.success}✓{p.reset} IPv6 WAN Stack -> {'ENABLED' if changed['ipv6'] else 'DISABLED'}")
                if "wifi_2g" in changed and hasattr(client, "set_wifi_radio"):
                    client.set_wifi_radio(band="2.4GHz", enabled=changed["wifi_2g"])
                    results.append(f"{p.success}✓{p.reset} 2.4GHz Wi-Fi Radio -> {'ON' if changed['wifi_2g'] else 'OFF'}")
                if "wifi_5g" in changed and hasattr(client, "set_wifi_radio"):
                    client.set_wifi_radio(band="5GHz", enabled=changed["wifi_5g"])
                    results.append(f"{p.success}✓{p.reset} 5GHz Wi-Fi Radio -> {'ON' if changed['wifi_5g'] else 'OFF'}")
                if "guest_wifi" in changed and hasattr(client, "set_guest_wifi"):
                    client.set_guest_wifi(band="both", enabled=changed["guest_wifi"])
                    results.append(f"{p.success}✓{p.reset} Guest Wi-Fi -> {'ENABLED' if changed['guest_wifi'] else 'DISABLED'}")
                if "upnp" in changed and hasattr(client, "set_upnp"):
                    client.set_upnp(enabled=changed["upnp"])
                    results.append(f"{p.success}✓{p.reset} UPnP Service -> {'ENABLED' if changed['upnp'] else 'DISABLED'}")
                if "led_night" in changed and hasattr(client, "set_led_night_mode"):
                    client.set_led_night_mode(enabled=changed["led_night"], start_time="22:00", end_time="07:00")
                    results.append(f"{p.success}✓{p.reset} LED Night Mode -> {'ENABLED' if changed['led_night'] else 'DISABLED'}")
            return render_panel(
                title="SWITCHBOARD CHANGES APPLIED",
                sections=[results],
                accent="success",
                mono=mono,
            )
        except Exception as exc:
            return render_panel(
                title="SWITCHBOARD ERROR",
                sections=[[f"{p.danger}✖ Failed applying switches: {exc}{p.reset}"]],
                accent="danger",
                mono=mono,
            )

    return run_cli_captured, poll_telemetry, fetch_toggles, apply_toggles


def launch_tui(
    target_host: str = "http://192.168.1.1",
    router_model: str = "Archer MR200 / Universal",
    mono: bool = False,
    base_flags: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Launch full-screen alternate-buffer TP-Link Interactive TUI.

    Returns an optional command string to hand off to main shell (e.g. 'repl'),
    or None when user exits cleanly after running commands inside the TUI.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None

    runner, poller, toggle_fetcher, toggle_applier = _make_live_callbacks(
        target_host=target_host, base_flags=base_flags
    )
    state = TUIState(
        target_host=target_host,
        router_model=router_model,
        mono=mono,
        runner=runner,
        telemetry_fetcher=poller,
        toggle_fetcher=toggle_fetcher,
        toggle_applier=toggle_applier,
    )

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        # Enter alternate screen buffer + hide cursor
        sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
        sys.stdout.flush()

        while not state.should_quit:
            cols, rows = shutil.get_terminal_size((96, 28))
            frame_lines = state.render_frame(cols=cols, rows=rows)

            buf_out = ["\033[H"]
            max_rows = max(1, rows - 1)
            for idx in range(max_rows):
                line = frame_lines[idx] if idx < len(frame_lines) else ""
                buf_out.append(f"\033[2K{line}\r\n")
            sys.stdout.write("".join(buf_out))
            sys.stdout.flush()

            key = read_key(fd)
            state.handle_key(key)

    finally:
        # Show cursor + leave alternate screen buffer + restore terminal discipline
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if state.print_on_exit:
        print()
        print(state.print_on_exit)
        print()

    if state.exit_command:
        return " ".join(state.exit_command)
    return None


# ----------------------------------------------------------------------
# Reusable Inline Arrow + Spacebar + Enter Widgets for CLI Subcommands
# ----------------------------------------------------------------------
def inline_select(
    title: str,
    options: Sequence[Tuple[str, str, str]],
    default_idx: int = 0,
    mono: bool = False,
) -> Optional[str]:
    """
    Inline Ink/Claude-Code style single-choice selector (↑/↓ + Space/Enter).
    options: sequence of (value, label, hint).
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty() or not options:
        return None

    p = get_palette(mono=mono)
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    cursor = max(0, min(default_idx, len(options) - 1))
    prev_lines = 0

    try:
        tty.setraw(fd)
        sys.stdout.write("\033[?25l")
        while True:
            rows = [f"{p.muted}↑/↓ Move • Space/Enter Confirm • Esc Cancel{p.reset}", ""]
            for idx, (_, label, hint) in enumerate(options):
                foc = idx == cursor
                ptr = f"{p.brand_bold}❯ (●){p.reset}" if foc else f"  {p.muted}( ){p.reset}"
                lcol = p.white if foc else p.text
                rows.append(f"{ptr} {pad_right(f'{lcol}{label}{p.reset}', 30)} {p.muted}{hint}{p.reset}")

            panel_str = render_panel(title=title, sections=[rows], mono=mono)
            panel_lines = panel_str.splitlines()

            if prev_lines > 0:
                sys.stdout.write(f"\033[{prev_lines}A\r")
            for pl in panel_lines:
                sys.stdout.write(f"\033[2K{pl}\r\n")
            sys.stdout.flush()
            prev_lines = len(panel_lines)

            key = read_key(fd)
            if key in ("CTRL_C", "CTRL_D", "ESC", "q"):
                return None
            if key in ("UP", "k"):
                cursor = (cursor - 1) % len(options)
            elif key in ("DOWN", "j"):
                cursor = (cursor + 1) % len(options)
            elif key in ("SPACE", "ENTER"):
                return options[cursor][0]
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def inline_multiselect(
    title: str,
    options: Sequence[Tuple[str, str, str, bool]],
    mono: bool = False,
) -> Optional[List[str]]:
    """
    Inline Ink/Claude-Code style multi-select checklist (↑/↓ + Space [✔] + Enter).
    options: sequence of (value, label, hint, initial_checked).
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty() or not options:
        return None

    p = get_palette(mono=mono)
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    cursor = 0
    checked: Set[int] = {i for i, o in enumerate(options) if o[3]}
    prev_lines = 0

    try:
        tty.setraw(fd)
        sys.stdout.write("\033[?25l")
        while True:
            rows = [f"{p.muted}↑/↓ Move • Space Toggle [✔] • Enter Accept ({len(checked)} selected) • Esc Cancel{p.reset}", ""]
            for idx, (_, label, hint, _) in enumerate(options):
                foc = idx == cursor
                is_c = idx in checked
                ptr = f"{p.brand_bold}❯{p.reset}" if foc else " "
                box = f"{p.success}[✔]{p.reset}" if is_c else f"{p.muted}[ ]{p.reset}"
                lcol = p.white if foc else p.text
                rows.append(f"{ptr} {box} {pad_right(f'{lcol}{label}{p.reset}', 30)} {p.muted}{hint}{p.reset}")

            panel_str = render_panel(title=title, sections=[rows], mono=mono)
            panel_lines = panel_str.splitlines()

            if prev_lines > 0:
                sys.stdout.write(f"\033[{prev_lines}A\r")
            for pl in panel_lines:
                sys.stdout.write(f"\033[2K{pl}\r\n")
            sys.stdout.flush()
            prev_lines = len(panel_lines)

            key = read_key(fd)
            if key in ("CTRL_C", "CTRL_D", "ESC", "q"):
                return None
            if key in ("UP", "k"):
                cursor = (cursor - 1) % len(options)
            elif key in ("DOWN", "j"):
                cursor = (cursor + 1) % len(options)
            elif key == "SPACE":
                if cursor in checked:
                    checked.remove(cursor)
                else:
                    checked.add(cursor)
            elif key == "ENTER":
                return [options[i][0] for i in range(len(options)) if i in checked]
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
