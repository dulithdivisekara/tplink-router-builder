"""Interactive REPL session for running sequential router commands without re-authenticating."""

import sys
import shlex
from typing import Any

try:
    import readline
    REPL_COMMANDS = [
        "status", "signal", "cell-lock", "dns", "ipv6", "clients", "data-limit",
        "wifi", "guest-wifi", "leds", "diag", "band", "logs", "sms", "ussd",
        "reboot", "help", "exit", "quit"
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

from tplink_router.core.session import SafeSession


def run_repl(client: Any):
    """Runs an interactive command loop holding a single admin session lease."""
    print("\n" + "=" * 60)
    print("  \033[1mTP-Link Router Interactive Console\033[0m")
    print("  Type 'help' for commands, 'exit' or Ctrl-D to quit.")
    print("=" * 60)

    try:
        with SafeSession(client):
            print("\033[92m[✓] Authenticated session established.\033[0m\n")
            while True:
                try:
                    line = input("\033[1mtplink>\033[0m ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nLogging out...")
                    break

                if not line:
                    continue

                parts = shlex.split(line)
                cmd = parts[0].lower()

                if cmd in ("exit", "quit", "q"):
                    print("Logging out...")
                    break

                elif cmd == "help":
                    print("""
Available commands in REPL:
  status               Show full router & cellular telemetry
  signal               Snapshot RF signal metrics (RSRP, RSRQ, SNR)
  cell-lock            Show cell lock status
  cell-lock lock <E> <P> Lock to EARFCN and PCI
  cell-lock unlock     Disable cell lock
  dns set <p> [s]      Set WAN DNS
  ipv6 on|off          Toggle IPv6
  clients              List connected LAN clients
  data-limit           Show cellular quota & usage
  wifi                 Show Wi-Fi radios & status
  leds                 Show LED night mode status
  diag                 Run router WAN & internet test
  sms list             List incoming SMS
  sms send <num> <msg> Send an SMS
  ussd <code>          Execute USSD code (e.g. *344#)
  reboot               Reboot router
  exit / quit          Exit console and release session
""")

                elif cmd == "status":
                    try:
                        dev = client.get_device_info()
                        print(f"Device: {dev.model} ({dev.firmware_version})")
                        if hasattr(client, "get_lte_status"):
                            lte = client.get_lte_status()
                            print(f"LTE Status : {'CONNECTED' if lte.connected else 'DISCONNECTED'}")
                            print(f"Carrier    : {lte.isp_name} | Band: {lte.band}")
                            print(f"Signal     : {lte.rf.signal_bars}/4 bars | RSRP: {lte.rf.rsrp_dbm} dBm ({lte.rf.rsrp_rating})")
                            print(f"RSRQ       : {lte.rf.rsrq_db} dB ({lte.rf.rsrq_rating}) | SNR: {lte.rf.snr_db} dB ({lte.rf.snr_rating})")
                            print(f"Speeds     : Down: {lte.rx_speed_kbps} Kbps, Up: {lte.tx_speed_kbps} Kbps")
                    except Exception as e:
                        print(f"\033[91mError: {e}\033[0m")

                elif cmd == "signal":
                    if hasattr(client, "get_lte_status"):
                        lte = client.get_lte_status()
                        print(f"RSRP: {lte.rf.rsrp_dbm} dBm ({lte.rf.rsrp_rating}) | SNR: {lte.rf.snr_db} dB ({lte.rf.snr_rating}) | RSRQ: {lte.rf.rsrq_db} dB")
                    else:
                        print("Signal metrics only available on cellular MR models.")

                elif cmd == "cell-lock":
                    if not hasattr(client, "get_cell_lock"):
                        print("Cell lock only supported on MR cellular models.")
                    elif len(parts) >= 4 and parts[1] == "lock":
                        earfcn, pci = parts[2], parts[3]
                        client.set_cell_lock(True, earfcn, pci)
                        print(f"\033[92mLocked to EARFCN {earfcn}, PCI {pci}\033[0m")
                    elif len(parts) >= 2 and parts[1] == "unlock":
                        client.set_cell_lock(False)
                        print("\033[92mCell lock disabled (Auto roaming).\033[0m")
                    else:
                        lock = client.get_cell_lock()
                        print(f"Cell Lock: {'Enabled' if lock.enabled else 'Disabled'} (EARFCN: {lock.earfcn}, PCI: {lock.pci})")

                elif cmd == "dns" and len(parts) >= 3 and parts[1] == "set":
                    p = parts[2]
                    s = parts[3] if len(parts) > 3 else "8.8.8.8"
                    client.set_dns(p, s)
                    print(f"\033[92mDNS set to {p}, {s}\033[0m")

                elif cmd == "ipv6" and len(parts) >= 2:
                    st = parts[1].lower() in ("on", "true", "enable")
                    client.toggle_ipv6(st)
                    print(f"\033[92mIPv6 {'enabled' if st else 'disabled'}\033[0m")

                elif cmd == "clients":
                    if hasattr(client, "get_connected_clients"):
                        clients = client.get_connected_clients()
                        print(f"{'HOSTNAME':<20} {'IP ADDRESS':<16} {'MAC':<18} {'LEASE':<10}")
                        print("-" * 65)
                        for c in clients:
                            print(f"{c['hostname']:<20} {c['ip']:<16} {c['mac']:<18} {c['lease_remaining']:<10}")
                        print(f"Total: {len(clients)} clients")
                    else:
                        print("Connected clients only supported on MR cellular models.")

                elif cmd == "data-limit":
                    if hasattr(client, "get_data_limit"):
                        data = client.get_data_limit()
                        print(f"Quota Active: {data['limit_enabled']} | Limit: {data['limit_mb']} MB | Reset Day: {data['billing_day']}")
                        print(f"Used: {round(data['current_period_bytes']/(1024*1024), 2)} MB | Total: {round(data['total_bytes']/(1024*1024), 2)} MB")
                    else:
                        print("Data limit only supported on MR cellular models.")

                elif cmd == "wifi":
                    if hasattr(client, "get_wifi_status"):
                        nets = client.get_wifi_status()
                        for n in nets:
                            print(f"{n['band']}: {n['ssid']} (State: {'Enabled' if n['enabled'] else 'Disabled'}, Channel: {n['channel']})")
                    else:
                        print("Wi-Fi control only supported on MR cellular models.")

                elif cmd == "leds":
                    if hasattr(client, "get_led_status"):
                        leds = client.get_led_status()
                        print(f"LEDs: {'ON' if leds['leds_on'] else 'OFF'} | Night Mode: {'Enabled' if leds['night_mode_enabled'] else 'Disabled'} ({leds['night_mode_start']} - {leds['night_mode_end']})")
                    else:
                        print("LED control only supported on MR cellular models.")

                elif cmd == "diag":
                    if hasattr(client, "run_wan_diagnostic"):
                        print("Running diagnostic...")
                        res = client.run_wan_diagnostic()
                        print(f"Diagnostic Result: {res['status']} ({res['message']})")
                    else:
                        print("Diagnostics only supported on MR cellular models.")

                elif cmd == "sms":
                    if not hasattr(client, "get_sms"):
                        print("SMS only available on cellular MR models.")
                    elif len(parts) >= 4 and parts[1] == "send":
                        client.send_sms(parts[2], parts[3])
                        print("\033[92mSMS sent.\033[0m")
                    else:
                        msgs = client.get_sms(limit=10)
                        for m in msgs:
                            print(f"[{m.index}] From: {m.sender} ({m.received_time}): {m.content}")

                elif cmd == "ussd" and len(parts) >= 2:
                    res = client.send_ussd(parts[1])
                    print(f"\nUSSD Response:\n{res.response}\n")

                elif cmd == "reboot":
                    confirm = input("Confirm reboot? (y/N): ")
                    if confirm.lower() == "y":
                        client.reboot()
                        print("\033[92mReboot sent. Exiting console.\033[0m")
                        break

                else:
                    print(f"Unknown command '{cmd}'. Type 'help' for available commands.")

    except Exception as e:
        print(f"\033[91mSession error: {e}\033[0m")
    finally:
        print("\033[92m[✓] Console closed. Single-admin session released.\033[0m")
