# Universal TP-Link Agentic Router Suite & MCP Server

<div align="center">

<img src="https://upload.wikimedia.org/wikipedia/commons/e/e0/TP-Link_logo_2016.svg" alt="TP-Link Official Logo" width="220" />
<br><br>

# TP-Link Router Suite & Upstream Builder Core

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Protocol: MCP](https://img.shields.io/badge/Protocol-MCP%202.x-purple.svg)](https://modelcontextprotocol.io/)
[![Platform: Linux | macOS | Windows](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-brightgreen.svg)](https://github.com/dulithdivisekara/tplink-router-builder)
[![CI Tests](https://img.shields.io/badge/CI-Passing-success.svg)](https://github.com/dulithdivisekara/tplink-router-builder/actions)
[![Author: Dulith Divisekara](https://img.shields.io/badge/Author-Dulith%20Divisekara%20(SLIIT)-orange.svg)](https://github.com/dulithdivisekara)

**The central upstream builder, test engine, and protocol specification monorepo for the TP-Link Router ecosystem.**<br>
Maintains core TR-064 reverse engineering, cryptographic engines, multi-environment network safety, and synchronizes to the official downstream distributions: [`tplink-cli`](https://github.com/dulithdivisekara/tplink-cli) and [`tplink-mcp`](https://github.com/dulithdivisekara/tplink-mcp).

</div>

---

## 👨‍💻 Author & Origin Story

> **Created & Maintained by:** [Dulith Divisekara](https://github.com/dulithdivisekara)  
> *Undergraduate in Information Technology, Sri Lanka Institute of Information Technology (SLIIT), Malabe, Sri Lanka.*

### The Sri Lanka Hutch 4G Optimization Origin
This project was born out of a real-world necessity in **Malabe, Sri Lanka (near the SLIIT Campus area)**. Living in boarding accommodation with an active **Hutch 4G LTE unlimited 20 Mbps (90-day)** package inserted into a **TP-Link Archer MR200 v5** gateway, connection stability and speeds fluctuated dramatically due to local tower congestion, radio channel switching, high bufferbloat, and mobile carrier routing delays. 

Furthermore, as a university student frequently transitioning between **SLIIT Campus Wi-Fi**, **personal phone hotspots**, and the **boarding router**, there was an acute risk that running automated scripts or AI agents could mistakenly push configuration updates to university infrastructure or sever active remote sessions.

To solve this, Dulith engineered an **agent-safe, universal system** that:
1. **Pings and inspects live 3GPP RF telemetry** (RSRP, RSRQ, SNR, EARFCN, PCI) in real-time.
2. **Locks the modem to specific high-throughput towers and LTE bands** (e.g. Band 3 1800MHz or Band 8 900MHz for Hutch Sri Lanka) to eliminate erratic tower hopping.
3. **Dispatches an ultra-lightweight 28-byte background keepalive pulse** keeping the cellular radio in active `RRC_CONNECTED` state, eliminating the 80–120ms radio scheduling latency spike.
4. **Applies reversible host-side TCP BBR & Fair Queueing (FQ)** to eliminate bufferbloat and clamps MTU to 1420 to prevent cellular GTP tunnel packet fragmentation.
5. **Employs a strict multi-environment Network Guard** to ensure commands are *never* run when connected to campus Wi-Fi or mobile hotspots.

While conceived to solve this specific challenge, the architecture is designed from the ground up as a **universal cross-platform tool** compatible with any TP-Link router worldwide.

---

## 🌟 Key Highlights

* 🛡️ **Multi-Environment Network Guard**: Automatically inspects default gateways and active Wi-Fi SSIDs on Linux, macOS, and Windows. Prevents AI agents and scripts from mistakenly configuring university or public Wi-Fi networks.
* 🔒 **Atomic Single-Admin Session Leasing**: TP-Link routers only permit a single administrator login at a time. Every command uses an atomic context manager (`SafeSession`) that authenticates, executes, and immediately logs out, preventing the web UI (`192.168.1.1`) from being locked out.
* 🤖 **Native Model Context Protocol (MCP 2.x)**: Exposes 18 typed tools directly to AI copilots (Google Antigravity, Claude Desktop, Cursor) with safety guardrails (`confirm=True` for disruptive actions like reboots or band switches).
* 📡 **4G LTE RF Metrics & Cell Lock**: Live 3GPP-calibrated **RSRP**, **RSRQ**, and **SNR** metrics with EARFCN/PCI cell locking and manual LTE band selection.
* 👥 **Connected LAN Devices & DHCP Reservations**: Enumerate all connected devices (wired & wireless) with IP, MAC, hostname, and lease duration. Add or remove static DHCP address reservations.
* 📊 **Cellular Data Quotas & Monthly Billing Cycle**: Configure monthly data caps in MB/GB, warning alert thresholds, and billing cycle reset dates.
* 📶 **Dual-Band Wi-Fi & Guest Network Control**: Inspect 2.4 GHz and 5 GHz radios, toggle radios on/off, update SSIDs, and isolate guest networks.
* 🌙 **LED Night Mode Schedule**: Disable bright front-panel router LEDs automatically during scheduled nighttime hours.
* 🩺 **Router-Side Diagnostics**: Run physical link, WAN IP, and NCSI internet self-tests directly from the router.
* 💬 **SMS & USSD Gateway**: Query balances via USSD (e.g. `*344#`, `*123#`), read incoming SIM notifications, and send SMS messages.
* 💻 **Interactive REPL Console**: Hold an authenticated administrative lease across sequential commands with `tplink-cli repl`.

---

## 📋 Compatibility Matrix

| Series | Hardware Models | Key Features Supported |
| :--- | :--- | :--- |
| **LTE / 4G Gateways** | Archer MR200 (v1–v5), MR6400, MR600, MR400, MR100 | Full Telemetry, Cell Lock, Band Selection, Signal Metrics (RSRP/RSRQ/SNR), Connected Clients, DHCP Reservations, Data Limits, Wi-Fi Control, Night Mode LEDs, Diagnostic Self-Test, SMS, USSD, DNS, IPv6, Reboot |
| **Wi-Fi 6 & 7 Broadband** | Archer AX10, AX20, AX50, AX53, AX72, BE3600, BE230 | Device Status, Firmware, WAN IPv4/IPv6, DHCP Leases, Client Listing, Reboot |
| **Classic Broadband** | Archer C6, C6U, C7, C80, C1200, C5400X | Client Lists, WAN Configuration, Wireless Telemetry, Reboot |
| **Mesh Systems** | Deco X20, X50, X60, E4R | Status, Topology, Node Enumeration |

---

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- Linux, macOS, or Windows

```bash
# Clone the repository
git clone https://github.com/dulithdivisekara/universal-tplink-mcp.git
cd universal-tplink-mcp

# Install package and dependencies
pip install -e .
```

---

## ⚙️ Configuration & Credentials

Credentials can be passed via CLI flags, environment variables, or stored securely in your user config file (`~/.config/tplink-router/config.json` with POSIX permissions `0600`):

```bash
# 1. Save router password securely:
tplink-cli config set-password "your_admin_password"

# 2. (Recommended) Set expected SSID to guard against executing on University/Public Wi-Fi:
tplink-cli config set-password "your_admin_password" --expected-ssid "dulith.connect"

# 3. View configuration status (passwords are redacted):
tplink-cli config show
```

---

## 🛠️ Complete CLI Command Reference

The `tplink-cli` provides 18 subcommands covering all aspects of router administration:

```bash
# General Telemetry & Live Radio
tplink-cli status                         # Show full device, cellular, and WAN telemetry
tplink-cli status --json                  # Output structured JSON for automation scripts
tplink-cli signal                         # Show live RSRP, RSRQ, SNR, and antenna ratings
tplink-cli profile check                  # Verify active Wi-Fi SSID and Gateway safety

# Cellular & 4G Optimization
tplink-cli cell-lock                      # View current Cell Lock status
tplink-cli cell-lock --enable --earfcn 1550 --pci 58  # Lock to specific LTE tower
tplink-cli cell-lock --disable            # Restore automatic roaming
tplink-cli band 3                         # Lock modem to LTE Band 3 (1800 MHz)
tplink-cli band auto                      # Restore automatic LTE band selection
tplink-cli data-limit                     # Show monthly cellular quota & live bandwidth
tplink-cli data-limit --limit 50000 --day 15  # Set 50GB monthly cap resetting on 15th

# Connected Devices & LAN
tplink-cli clients                        # Display table of connected devices (IP, MAC, Hostname)
tplink-cli reservation list               # List static DHCP IP address reservations
tplink-cli reservation add AA:BB:CC:DD:EE:FF 192.168.1.50   # Add static reservation
tplink-cli reservation del AA:BB:CC:DD:EE:FF               # Remove static reservation

# Wireless & Hardware Management
tplink-cli wifi                           # Show 2.4 GHz and 5 GHz Wi-Fi radio status
tplink-cli wifi --band 5GHz --toggle off  # Disable 5 GHz radio
tplink-cli leds                           # Check router front-panel LED night mode status
tplink-cli leds --night-mode on --start 23:00 --end 07:00   # Auto-disable LEDs at night

# Networking & System Tools
tplink-cli dns set 8.8.8.8 1.1.1.1        # Set custom WAN DNS servers
tplink-cli ipv6 off                       # Disable IPv6 stack (mitigate dual-stack delays)
tplink-cli diag                           # Run router WAN & internet reachability test
tplink-cli reboot                         # Gracefully reboot the router
tplink-cli ussd "*344#"                   # Send interactive USSD balance inquiry
tplink-cli sms list --limit 10            # Read SIM SMS inbox
tplink-cli sms send 078xxxxxxx "Hello!"   # Send SMS message

# Interactive REPL
tplink-cli repl                           # Launch interactive console holding open session
```

---

## 🤖 Model Context Protocol (MCP 2.x) Integration

Connect the router directly to **Google Antigravity**, **Claude Desktop**, or any MCP-compliant AI assistant by configuring `mcpServers`:

```json
{
  "mcpServers": {
    "universal-tplink-mcp": {
      "command": "python3",
      "args": ["-m", "tplink_router.mcp.server"],
      "cwd": "/path/to/universal-tplink-mcp",
      "env": {
        "PYTHONPATH": "/path/to/universal-tplink-mcp",
        "TPLINK_ROUTER_IP": "http://192.168.1.1",
        "TPLINK_PASSWORD": "your_router_password"
      }
    }
  }
}
```

### Complete MCP Tools Catalog (18 Tools)

| Tool Name | Type | Description | Safety Guard |
| :--- | :--- | :--- | :--- |
| `router_profile_check` | Read | Verifies active Wi-Fi SSID & Gateway against target router | Safe |
| `router_get_status` | Read | Full device info, cellular status, and WAN telemetry | Safe |
| `router_get_rf_signal` | Read | Live 3GPP RSRP, RSRQ, SNR, and tower metadata | Safe |
| `router_set_cell_lock` | Write | Locks or unlocks cellular base station (EARFCN + PCI) | Requires `confirm=True` |
| `router_set_lte_band` | Write | Locks modem to specific LTE frequency band (e.g. Band 3) | Requires `confirm=True` |
| `router_get_data_limit` | Read | Returns monthly data quota, billing reset day, and bandwidth | Safe |
| `router_set_data_limit` | Write | Sets monthly data limit in MB and billing cycle day | Requires `confirm=True` |
| `router_get_connected_clients` | Read | Lists all connected LAN devices (hostname, IP, MAC, lease) | Safe |
| `router_manage_dhcp_reservation` | Write | Adds, deletes, or lists static DHCP IP reservations | Requires `confirm=True` (add/del) |
| `router_get_wifi_networks` | Read | Returns 2.4 GHz and 5 GHz radio states, SSIDs, and channels | Safe |
| `router_set_wifi_radio` | Write | Enables/disables Wi-Fi radio or updates SSID | Requires `confirm=True` |
| `router_get_led_status` | Read | Queries front panel LEDs and night mode schedule | Safe |
| `router_set_led_night_mode` | Write | Configures night mode to turn off router LEDs automatically | Safe |
| `router_run_diagnostic` | Exec | Runs router-side WAN, physical link, and internet test | Safe |
| `router_set_dns` | Write | Configures custom WAN DNS resolvers | Safe |
| `router_toggle_ipv6` | Write | Enables or disables IPv6 stack | Safe |
| `router_run_ussd` | Exec | Dispatches interactive USSD query to SIM | Safe |
| `router_read_sms` | Read | Reads incoming or sent SMS messages from SIM card | Safe |
| `router_send_sms` | Write | Sends SMS message through SIM card | Safe |
| `router_reboot` | Exec | Gracefully reboots router hardware | Requires `confirm=True` |

---

## 🗺️ Router Endpoints & TR-064 Catalog

A comprehensive reverse-engineered map of all **95 Web Pages** and **TR-064 Objects** available on `http://192.168.1.1` is documented in:
* 📄 **[docs/router_endpoints_reference.md](docs/router_endpoints_reference.md)**: Full architecture breakdown, action codes (`ACT_GET`, `ACT_SET`, `ACT_GL`, `ACT_OP`), and subsystems.
* 📦 **[docs/endpoints_catalog.json](docs/endpoints_catalog.json)**: Machine-readable schema mapping all OIDs, attributes, and pages.

---

## ⚡ Client-Side Linux Network Optimizer

For Linux workstations operating over cellular 4G links, manual scripts are provided:

```bash
# 1. Enable TCP BBR congestion control, FQ queueing, and MTU 1420 GTP clamping:
sudo ./scripts/optimize-network.sh enable

# 2. Check current network stack status:
./scripts/optimize-network.sh status

# 3. Revert to standard system defaults (e.g. when connecting to Campus Wi-Fi):
sudo ./scripts/optimize-network.sh disable
```

### Cellular RRC Keepalive Pulse
Cellular modems enter dormancy (`RRC_IDLE`) after 10–15 seconds of inactivity, causing a 50–120ms radio scheduling delay on the next request. The keepalive pulse sends a tiny 28-byte heartbeat every 6 seconds to eliminate this lag (< 0.5 KB/min data consumption):

```bash
./scripts/keepalive-pulse.sh start
./scripts/keepalive-pulse.sh status
./scripts/keepalive-pulse.sh stop
```

---

## 🧪 Testing

All 18 unit tests cover authentication handshakes, atomic session leasing, network guards, client detection, data quotas, and diagnostic routines:

```bash
python3 -m unittest discover tests
```

---

## 🔒 Security & Privacy

* Credentials and session cookies are never transmitted externally or written to version control.
* Passwords stored via `tplink-cli config set-password` use POSIX permissions `0600` (readable only by the file owner).
* `.gitignore` excludes all `.env`, `*.json`, and credential files.
* Potentially disruptive actions enforce the `confirm=True` parameter to prevent AI agents from accidentally interrupting internet connectivity.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).  
Created and architected by [Dulith Divisekara](https://github.com/dulithdivisekara).
