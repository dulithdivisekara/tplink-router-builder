# Universal TP-Link Agentic Router Suite & MCP Server

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Protocol: MCP](https://img.shields.io/badge/Protocol-MCP%202.x-purple.svg)](https://modelcontextprotocol.io/)
[![Platform: Linux | macOS | Windows](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-brightgreen.svg)](https://github.com/dulithdivisekara/universal-tplink-mcp)
[![CI Tests](https://img.shields.io/badge/CI-Passing-success.svg)](https://github.com/dulithdivisekara/universal-tplink-mcp/actions)

**A universal, cross-platform CLI and Model Context Protocol (MCP) server for TP-Link routers.**<br>
Built for both human power-users and autonomous AI agents (Google Antigravity, Claude, Cursor) with built-in network safety guards, atomic session management, and cellular optimization.

</div>

---

## 🌟 Key Highlights

* 🛡️ **Multi-Environment Network Guard**: Automatically detects whether your machine is connected to your home router, campus Wi-Fi (e.g. SLIIT Campus), or a mobile hotspot. Rejects accidental router commands if the active Wi-Fi / Gateway does not match.
* 🔒 **Single-Admin Lock Avoidance**: TP-Link routers only permit a single administrator login at a time. Every action uses atomic session leasing—authenticating, executing, and logging out immediately so your web browser UI (`192.168.1.1`) is never locked out.
* ⚡ **Agent-Safe Guardrails**: AI agents cannot accidentally sever their own connection; disruptive actions like router reboots or LTE cell locking require an explicit confirmation parameter (`confirm=True`).
* 📡 **4G LTE RF Metrics & Cell Lock**: Live 3GPP-calibrated **RSRP**, **RSRQ**, and **SNR** telemetry with EARFCN/PCI locking to prevent band flapping on mobile networks (tested with Hutch Sri Lanka).
* 💬 **SMS & USSD Gateway**: Query cellular balances via USSD (e.g. `*344#`, `*123#`), read incoming operator quota notifications, and dispatch SMS.
* 💻 **Interactive REPL Console**: Hold an active session during interactive troubleshooting sessions with `tplink-cli repl`.
* 🤖 **Native Model Context Protocol (MCP 2.x)**: Exposes 10 typed tools directly to AI copilots.
* 🐧 **Linux Client Optimizer**: One-command reversible script enabling **Google BBR**, bufferbloat mitigation (`fq`), and MTU `1420` GTP-clamping for cellular connections.

---

## 📋 Compatibility Matrix

| Series | Hardware Models | Key Features Supported |
| :--- | :--- | :--- |
| **LTE / 4G Gateways** | Archer MR200 (v1–v5), MR6400, MR600, MR400 | Full Telemetry, Cell Lock, Band Selection, Signal Metrics (RSRP/RSRQ/SNR), SMS, USSD, DNS, IPv6, Reboot |
| **Wi-Fi 6 & 7 Broadband** | Archer AX10, AX20, AX50, AX53, AX72, BE3600, BE230 | Device Status, Firmware, WAN IPv4/IPv6, DHCP Leases, Reboot |
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

# Install in editable mode
pip install -e .
```

---

## ⚙️ Configuration & Precedence

Credentials can be passed via CLI arguments, environment variables, or a local secure config file (mode `0600`). Resolution precedence:

1. CLI Arguments (`--host`, `--username`, `--password`)
2. Environment Variables (`TPLINK_ROUTER_IP`, `TPLINK_PASSWORD`, `TPLINK_USERNAME`)
3. Project `.env` file
4. User Config File (`~/.config/tplink-router/config.json`)

```bash
# Save your router password securely (owner read/write only):
tplink-cli config set-password "your_admin_password"

# Optional: set an expected SSID to prevent running commands on university/public Wi-Fi:
tplink-cli config set-password "your_admin_password" --expected-ssid "dulith.connect"

# View current configuration (passwords are redacted):
tplink-cli config show
```

---

## 🛠️ CLI Usage Guide

### 1. View Complete Router Telemetry
```bash
tplink-cli status
# Machine-readable output for scripts:
tplink-cli status --json
```

### 2. Live Signal & Antenna Alignment Mode
Move or rotate your 4G router to maximize RSRP and SNR:
```bash
tplink-cli signal
```

### 3. LTE Cell Lock (Locking to Best Base Station)
Lock to a high-capacity tower (for example, Band 3 on EARFCN `1550` and PCI `58`):
```bash
# Lock to specific cell:
tplink-cli cell-lock --enable --earfcn 1550 --pci 58

# Check lock state:
tplink-cli cell-lock

# Unlock / restore automatic roaming:
tplink-cli cell-lock --disable
```

### 4. Network Environment Guard
Check whether your machine is connected to your router or another network (e.g. SLIIT Campus Wi-Fi):
```bash
tplink-cli profile check
```

### 5. DNS & IPv6 Optimization
```bash
# Set low-latency DNS (e.g. Google DNS):
tplink-cli dns set 8.8.8.8 1.1.1.1

# Toggle IPv6 on/off:
tplink-cli ipv6 off
```

### 6. USSD & SMS Utilities
```bash
# Check Hutch balance or quota:
tplink-cli ussd "*344#"

# Read SMS inbox:
tplink-cli sms list --limit 10

# Send SMS:
tplink-cli sms send "078xxxxxxx" "Hello from TP-Link Router CLI"
```

### 7. Interactive REPL Console
Hold an open session across multiple rapid commands without re-authenticating:
```bash
tplink-cli repl
```

---

## 🤖 Model Context Protocol (MCP) Setup

To connect this tool to **Google Antigravity**, **Claude Desktop**, or any MCP-compatible AI agent, add the server to your MCP configuration:

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

### Registered Agent Tools

| Tool Name | Type | Description | Safety Guard |
| :--- | :--- | :--- | :--- |
| `router_profile_check` | Read | Verifies active Wi-Fi SSID & Gateway | Safe |
| `router_get_status` | Read | Full device, LTE, and WAN telemetry | Safe |
| `router_get_rf_signal` | Read | Live RSRP, RSRQ, SNR metrics | Safe |
| `router_set_cell_lock` | Write | Locks or unlocks cellular base station | Requires `confirm=True` |
| `router_set_dns` | Write | Configures custom WAN DNS servers | Safe |
| `router_toggle_ipv6` | Write | Enables or disables IPv6 stack | Safe |
| `router_run_ussd` | Exec | Executes USSD query on SIM | Safe |
| `router_read_sms` | Read | Reads incoming or sent SMS messages | Safe |
| `router_send_sms` | Write | Sends SMS message through SIM | Safe |
| `router_reboot` | Exec | Gracefully reboots router | Requires `confirm=True` |

---

## ⚡ Client-Side Linux Network Optimizer

For Linux systems on cellular 4G links, a manual, fully reversible optimization script is provided:

```bash
# Apply BBR congestion control, FQ queueing, and MTU 1420 GTP clamping:
sudo ./scripts/optimize-network.sh enable

# Check current network parameters & latency:
./scripts/optimize-network.sh status

# Revert to standard Ubuntu defaults (when connecting to Campus Wi-Fi):
sudo ./scripts/optimize-network.sh disable
```

### Cellular RRC Keepalive Pulse
Cellular modems enter dormancy (`RRC_IDLE`) after 10–15 seconds of silence, incurring a 50–120ms radio scheduling lag upon resumption. The keepalive pulse sends a tiny 28-byte heartbeat every 6 seconds to eliminate this lag without consuming significant data (< 0.5 KB/min):

```bash
./scripts/keepalive-pulse.sh start
./scripts/keepalive-pulse.sh status
./scripts/keepalive-pulse.sh stop
```

---

## 🔒 Security & Privacy

* Credentials are never logged or transmitted externally.
* Passwords stored via `config set-password` use POSIX file permissions `0600` (accessible only by the current user).
* `.gitignore` strictly excludes all `.env`, `*.json`, and credential files from Git.
* Disruption-causing operations require an explicit `confirm=True` flag to prevent autonomous agent disconnects.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
Created and maintained by [Dulith Divisekara](https://github.com/dulithdivisekara).
