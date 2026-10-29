"""Interactive REPL session for running sequential router commands without re-authenticating."""

import shlex
from typing import Any

try:
    import readline

    REPL_COMMANDS = [
        "status",
        "signal",
        "cell-lock",
        "dns",
        "ipv6",
        "clients",
        "data-limit",
        "wifi",
        "guest-wifi",
        "leds",
        "diag",
        "band",
        "logs",
        "sms",
        "ussd",
        "reboot",
        "help",
        "exit",
        "quit",
    ]

    def _completer(text, state):
        options = [c for c in REPL_COMMANDS if c.startswith(text)]
        if state < len(options):
            return options[state]
        return None

    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")
except Exception:
    pass

from tplink_router.cli.logo import get_logo_width, render_logo_lines
from tplink_router.cli.theme import (
    get_palette,
    print_panel,
    print_toast,
    rating_badge,
    render_kv_rows,
    render_table_lines,
    signal_bars,
    status_badge,
)
from tplink_router.core.session import SafeSession


def run_repl(client: Any, mono: bool = False, legacy: bool = False):
    """Runs an interactive command loop holding a single admin session lease."""
    p = get_palette(mono=mono)

    if legacy:
        print("\n" + "=" * 60)
        print("  \033[1mTP-Link Router Interactive Console\033[0m")
        print("  Type 'help' for commands, 'exit' or Ctrl-D to quit.")
        print("=" * 60)
    else:
        logo = render_logo_lines("mini", mono=mono)
        lw = get_logo_width("mini")
        info = [
            f"{p.brand_bold}tp-link{p.reset} {p.white}INTERACTIVE SESSION REPL{p.reset}",
            f"{p.muted}Single-Admin Persistent Router Lease{p.reset}",
            "",
            f"{p.text}Tab{p.reset} {p.muted}autocomplete •{p.reset} {p.text}help{p.reset} {p.muted}commands •{p.reset} {p.text}exit{p.reset} {p.muted}release lease{p.reset}",
        ]
        rows = []
        for i in range(max(len(logo), len(info))):
            lp = logo[i] if i < len(logo) else (" " * lw)
            rp = info[i] if i < len(info) else ""
            rows.append(f"{lp}   {rp}")
        print_panel("TP-LINK INTERACTIVE CONSOLE", [rows], subtitle="REPL", mono=mono)

    try:
        with SafeSession(client):
            print(f"{p.success}  ✓ Authenticated router session established.{p.reset}\n")
            prompt_str = (
                "\033[1mtplink>\033[0m "
                if (legacy or mono)
                else f"{p.brand_bold}tplink{p.reset} {p.white}❯{p.reset} "
            )
            while True:
                try:
                    line = input(prompt_str).strip()
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{p.muted}Releasing session...{p.reset}")
                    break

                if not line:
                    continue

                try:
                    parts = shlex.split(line)
                except ValueError as ve:
                    print(f"{p.danger}Parse error: {ve}{p.reset}")
                    continue

                cmd = parts[0].lower()

                if cmd in ("exit", "quit", "q"):
                    print(f"{p.muted}Releasing session...{p.reset}")
                    break

                elif cmd == "help":
                    cmds = [
                        ("status", "Show full router & cellular telemetry"),
                        ("signal", "Snapshot RF signal metrics (RSRP, RSRQ, SNR, bars)"),
                        ("band [3|8|40|auto]", "Inspect or lock LTE frequency band"),
                        ("cell-lock [lock E P|unlock]", "Inspect, lock, or unlock EARFCN/PCI tower"),
                        ("dns set <p> [s]", "Configure primary & secondary WAN DNS"),
                        ("ipv6 <on|off>", "Toggle router IPv6 stack"),
                        ("clients", "List connected LAN & Wi-Fi devices"),
                        ("data-limit", "Inspect cellular monthly quota & usage"),
                        ("wifi", "Show 2.4GHz & 5GHz Wi-Fi status"),
                        ("leds", "Show front-panel LED & Night Mode status"),
                        ("diag", "Run WAN internet connectivity test"),
                        ("sms [list|send <n> <m>]", "Read inbox or send SMS message"),
                        ("ussd <code>", "Execute carrier USSD code (e.g. *344#)"),
                        ("reboot", "Safely reboot hardware router"),
                        ("exit / quit", "Close console and release admin session"),
                    ]
                    print_panel("REPL COMMANDS", [render_kv_rows(cmds, key_width=24, mono=mono)], mono=mono)

                elif cmd == "status":
                    try:
                        dev = client.get_device_info()
                        rows = [("Device", f"{dev.model} ({dev.firmware_version})")]
                        if hasattr(client, "get_lte_status"):
                            lte = client.get_lte_status()
                            rows.extend([
                                ("Connection", status_badge(lte.connected, "CONNECTED", "DISCONNECTED", mono=mono)),
                                ("Carrier / Band", f"{lte.isp_name}  •  {lte.band}"),
                                ("Signal", f"{signal_bars(lte.rf.signal_bars, mono=mono)}  •  RSRP {lte.rf.rsrp_dbm} dBm ({rating_badge(lte.rf.rsrp_rating, mono=mono)})"),
                                ("RSRQ / SNR", f"{lte.rf.rsrq_db} dB ({lte.rf.rsrq_rating})  •  SNR {lte.rf.snr_db} dB ({lte.rf.snr_rating})"),
                                ("Throughput", f"↓ {lte.rx_speed_kbps} Kbps   ↑ {lte.tx_speed_kbps} Kbps"),
                            ])
                        print_panel("ROUTER STATUS", [render_kv_rows(rows, mono=mono)], subtitle=dev.model, mono=mono)
                    except Exception as e:
                        print(f"{p.danger}✖ Error: {e}{p.reset}")

                elif cmd == "signal":
                    if hasattr(client, "get_lte_status"):
                        lte = client.get_lte_status()
                        rows = [
                            ("Carrier / Band", f"{lte.isp_name}  •  {lte.band}"),
                            ("Signal Level", signal_bars(lte.rf.signal_bars, mono=mono)),
                            ("RSRP / RSRQ / SNR", f"{lte.rf.rsrp_dbm} dBm ({rating_badge(lte.rf.rsrp_rating, mono=mono)})  •  {lte.rf.rsrq_db} dB  •  {lte.rf.snr_db} dB"),
                        ]
                        print_panel("LTE RF SIGNAL", [render_kv_rows(rows, mono=mono)], mono=mono)
                    else:
                        print("Signal metrics only available on cellular MR models.")

                elif cmd == "band":
                    if not hasattr(client, "set_lte_band"):
                        print("Band control only available on cellular MR models.")
                    elif len(parts) >= 2:
                        client.set_lte_band(parts[1])
                        print_toast("success", f"LTE band configured to '{parts[1]}'", "Modem is retuning RF hardware.", mono=mono)
                    elif hasattr(client, "get_band_config"):
                        b = client.get_band_config()
                        rows = [
                            ("Configured Mode", b.get("configured_str", "Auto")),
                            ("Connected RF", b.get("connected_band", "Auto")),
                            ("EARFCN / PCI", f"{b.get('earfcn')} / {b.get('pci')}"),
                        ]
                        print_panel("LTE BAND", [render_kv_rows(rows, mono=mono)], mono=mono)

                elif cmd == "cell-lock":
                    if not hasattr(client, "get_cell_lock"):
                        print("Cell lock only supported on MR cellular models.")
                    elif len(parts) >= 4 and parts[1] == "lock":
                        earfcn, pci = parts[2], parts[3]
                        client.set_cell_lock(True, earfcn, pci)
                        print_toast("success", f"Locked to EARFCN {earfcn}, PCI {pci}", mono=mono)
                    elif len(parts) >= 2 and parts[1] == "unlock":
                        client.set_cell_lock(False)
                        print_toast("success", "Cell lock disabled (Auto roaming)", mono=mono)
                    else:
                        lock = client.get_cell_lock()
                        rows = [
                            ("Status", status_badge(lock.enabled, "LOCKED", "AUTO-ROAMING", mono=mono)),
                            ("EARFCN / PCI", f"{lock.earfcn or 'Auto'} / {lock.pci or 'Auto'}"),
                        ]
                        print_panel("CELL LOCK", [render_kv_rows(rows, mono=mono)], mono=mono)

                elif cmd == "dns" and len(parts) >= 3 and parts[1] == "set":
                    pr = parts[2]
                    sc = parts[3] if len(parts) > 3 else "8.8.8.8"
                    client.set_dns(pr, sc)
                    print_toast("success", f"DNS configured to {pr}, {sc}", mono=mono)

                elif cmd == "ipv6" and len(parts) >= 2:
                    st = parts[1].lower() in ("on", "true", "enable")
                    client.toggle_ipv6(st)
                    print_toast("success", f"IPv6 {'enabled' if st else 'disabled'} successfully", mono=mono)

                elif cmd == "clients":
                    if hasattr(client, "get_connected_clients"):
                        clients = client.get_connected_clients()
                        t_rows = [[c["hostname"], c["ip"], c["mac"], c["lease_remaining"]] for c in clients]
                        print_panel(
                            "CONNECTED CLIENTS",
                            [render_table_lines(["HOSTNAME", "IP ADDRESS", "MAC", "LEASE"], t_rows, mono=mono)],
                            subtitle=f"{len(clients)} Active",
                            mono=mono,
                        )
                    else:
                        print("Connected clients only supported on MR cellular models.")

                elif cmd == "data-limit":
                    if hasattr(client, "get_data_limit"):
                        data = client.get_data_limit()
                        rows = [
                            ("Quota Active", status_badge(bool(data["limit_enabled"]), "ACTIVE", "DISABLED", mono=mono)),
                            ("Monthly Limit", f"{data['limit_mb']} MB (Reset Day {data['billing_day']})"),
                            ("Period / Total", f"{round(data['current_period_bytes']/(1024*1024), 2)} MB  /  {round(data['total_bytes']/(1024*1024), 2)} MB"),
                        ]
                        print_panel("DATA QUOTA", [render_kv_rows(rows, mono=mono)], mono=mono)
                    else:
                        print("Data limit only supported on MR cellular models.")

                elif cmd == "wifi":
                    if hasattr(client, "get_wifi_status"):
                        nets = client.get_wifi_status()
                        t_rows = [
                            [n["band"], n["ssid"], status_badge(bool(n["enabled"]), "ON", "OFF", mono=mono), str(n["channel"])]
                            for n in nets
                        ]
                        print_panel("WI-FI NETWORKS", [render_table_lines(["BAND", "SSID", "STATE", "CHANNEL"], t_rows, mono=mono)], mono=mono)
                    else:
                        print("Wi-Fi control only supported on MR cellular models.")

                elif cmd == "leds":
                    if hasattr(client, "get_led_status"):
                        leds = client.get_led_status()
                        rows = [
                            ("LEDs Active", status_badge(bool(leds["leds_on"]), "ON", "OFF", mono=mono)),
                            ("Night Mode", f"{'Enabled' if leds['night_mode_enabled'] else 'Disabled'} ({leds['night_mode_start']} - {leds['night_mode_end']})"),
                        ]
                        print_panel("FRONT-PANEL LEDS", [render_kv_rows(rows, mono=mono)], mono=mono)
                    else:
                        print("LED control only supported on MR cellular models.")

                elif cmd == "diag":
                    if hasattr(client, "run_wan_diagnostic"):
                        res = client.run_wan_diagnostic()
                        ok = res["status"] == "Passed"
                        print_toast("success" if ok else "danger", f"Diagnostic: {res['status']}", res["message"], mono=mono)
                    else:
                        print("Diagnostics only supported on MR cellular models.")

                elif cmd == "sms":
                    if not hasattr(client, "get_sms"):
                        print("SMS only available on cellular MR models.")
                    elif len(parts) >= 4 and parts[1] == "send":
                        client.send_sms(parts[2], parts[3])
                        print_toast("success", f"SMS sent to {parts[2]}", mono=mono)
                    else:
                        msgs = client.get_sms(limit=10)
                        s_rows = [f"[{m.index}] {m.sender} ({m.received_time}): {m.content}" for m in msgs] or ["(No SMS messages)"]
                        print_panel("SMS INBOX", [s_rows], mono=mono)

                elif cmd == "ussd" and len(parts) >= 2:
                    res = client.send_ussd(parts[1])
                    print_panel("USSD RESPONSE", [[res.response]], subtitle=parts[1], mono=mono)

                elif cmd == "reboot":
                    confirm = input("Confirm reboot? (y/N): ")
                    if confirm.lower() == "y":
                        client.reboot()
                        print_toast("warning", "Router reboot initiated", "Exiting console.", mono=mono)
                        break

                else:
                    print(f"{p.warning}Unknown command '{cmd}'. Type 'help' for available commands.{p.reset}")

    except Exception as e:
        print(f"{p.danger}✖ Session error: {e}{p.reset}")
    finally:
        print(f"{p.success}  ✓ Console closed. Single-admin session released.{p.reset}")
