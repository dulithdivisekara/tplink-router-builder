# TP-Link Universal CLI - Complete Copy-Paste Live Test Suite

> **Target Device**: TP-Link Archer MR200 / Universal LTE & Wi-Fi Router (`192.168.1.1`)  
> **Auth Mode**: Authenticated via local stored config / session cookie  
> **Author**: Dulith Divisekara (SLIIT Malabe)

---

## Quick Reference / Global UI & Theme Modes

```bash
# 1. Full-Screen Interactive TUI (↑/↓ Scroll • ←/→ Tabs • Space [✔] Select • Enter Run)
tplink-cli
tplink-cli tui

# 2. Monochrome Black & White Theme Mode (TUI, Logo & All Command Outputs)
tplink-cli --mono
tplink-cli --mono status
tplink-cli --mono --help

# 3. Inline Interactive Selectors (Arrow Keys + Spacebar [✔] + Enter)
tplink-cli band -i
tplink-cli calibrate -i --no-web --dry-run
tplink-cli ipv6 -i

# 4. Modern Help Catalog with Half-Block TP-Link Pixel Logo
tplink-cli --help

# 5. Classic / Legacy Argparse Help & Plain-ASCII Output Mode
tplink-cli --legacy
tplink-cli --legacy status

# 6. Persistent Single-Session Interactive REPL Console
tplink-cli repl
```

---

## 1. Cellular Radio Frequency (RF) & Telemetry

### 1.1 Full System & Cellular Telemetry (`status`)
Inspect complete modem connection, signal power, IP, and carrier metrics:
```bash
tplink-cli status
```
*JSON Output mode:*
```bash
tplink-cli status --json
```

---

### 1.2 Radio Signal Snapshot (`signal`)
Live snapshot of RSRP (power), RSRQ (quality), SNR (noise), and signal bars:
```bash
tplink-cli signal
```
*JSON Output mode:*
```bash
tplink-cli signal --json
```

---

### 1.3 LTE Band Switching & Query (`band`)
Display currently active LTE Band:
```bash
tplink-cli band
```
Lock to Band 8 (900 MHz - high penetration & stability for Hutch SL):
```bash
tplink-cli band 8
```
Lock to Band 3 (1800 MHz - high throughput):
```bash
tplink-cli band 3
```
Switch modem back to automatic network selection:
```bash
tplink-cli band auto
```

---

### 1.4 Carrier Cell Lock (`cell-lock`)
View current cell lock state:
```bash
tplink-cli cell-lock
```
Lock modem to a specific tower frequency (EARFCN) and Physical Cell Identity (PCI):
*(Example for Hutch SL Band 8 carrier tower)*:
```bash
tplink-cli cell-lock --enable --earfcn 3738 --pci 0
```
Disable cell lock and return to auto cell roaming:
```bash
tplink-cli cell-lock --disable
```

---

### 1.5 Autonomous RF Band Calibration (`calibrate`)
Simulate/dry-run RF band sweep across bands (Band 8, 3, 1, 40):
```bash
tplink-cli calibrate --dry-run
```
Run live RF sweep in headless terminal mode:
```bash
tplink-cli calibrate --no-web
```

---

### 1.6 Hardware Diagnostics (`diag`)
Run router internet diagnostic test (WAN ping, DNS resolution, default gateway):
```bash
tplink-cli diag
```

---

## 2. Network, WAN & DNS

### 2.1 IPv6 Stack Status & Control (`ipv6`)
Inspect current router IPv6 stack state:
```bash
tplink-cli ipv6
```
Enable router hardware IPv6 stack:
```bash
tplink-cli ipv6 on
```
Disable router hardware IPv6 stack:
```bash
tplink-cli ipv6 off
```

---

### 2.2 DNS Resolver Management (`dns`)
View currently configured DNS resolvers:
```bash
tplink-cli dns show
```
Set Cloudflare DNS (1.1.1.1 & 1.0.0.1):
```bash
tplink-cli dns set 1.1.1.1 1.0.0.1
```
Set Google DNS (8.8.8.8 & 8.8.4.4):
```bash
tplink-cli dns set 8.8.8.8 8.8.4.4
```

---

### 2.3 Connected LAN Devices (`clients`)
List all connected Wi-Fi and Ethernet client devices with IP, MAC, and Hostname:
```bash
tplink-cli clients
```

---

### 2.4 DHCP Static IP Reservations (`reservation`)
List all active DHCP reservations:
```bash
tplink-cli reservation list
```
Add a static IP reservation for a device MAC address:
```bash
tplink-cli reservation add 00:11:22:33:44:55 192.168.1.150
```
Delete a static IP reservation:
```bash
tplink-cli reservation del 00:11:22:33:44:55
```

---

### 2.5 Monthly Cellular Data Allowance (`data-limit`)
View current monthly data usage and quota:
```bash
tplink-cli data-limit
```
Set monthly data limit to 50 GB (50,000 MB) resetting on the 1st of every month:
```bash
tplink-cli data-limit --limit 50000 --day 1
```

---

### 2.6 Wi-Fi Stability Guard (`wifi-guard`)
Verify Wi-Fi link stability without Ethernet cable:
```bash
tplink-cli wifi-guard
```
Auto-optimize Wi-Fi interface and elevate NetworkManager priority:
```bash
tplink-cli wifi-guard --optimize
```

---

### 2.7 Network Profile Safety Check (`profile`)
Verify active router gateway and Wi-Fi SSID safety:
```bash
tplink-cli profile check
```

---

## 3. Wi-Fi & Hardware Management

### 3.1 Wi-Fi Radios & SSIDs (`wifi`)
View active 2.4GHz Wi-Fi configuration:
```bash
tplink-cli wifi --band 2.4GHz
```
View active 5GHz Wi-Fi configuration:
```bash
tplink-cli wifi --band 5GHz
```
Turn 5GHz Wi-Fi radio off:
```bash
tplink-cli wifi --band 5GHz --toggle off
```
Turn 5GHz Wi-Fi radio back on:
```bash
tplink-cli wifi --band 5GHz --toggle on
```

---

### 3.2 Guest Wi-Fi Network (`guest-wifi`)
View current Guest Wi-Fi status and settings:
```bash
tplink-cli guest-wifi
```
Enable Guest Wi-Fi with custom SSID and password:
```bash
tplink-cli guest-wifi --toggle on --ssid "TP-Link_Guest" --key "WelcomeGuest2026"
```
Disable Guest Wi-Fi:
```bash
tplink-cli guest-wifi --toggle off
```

---

### 3.3 Hardware Indicator LEDs & Night Mode (`leds`)
Inspect LED status and Night Mode schedule:
```bash
tplink-cli leds
```
Enable Night Mode schedule (turn off LEDs from 23:00 to 07:00):
```bash
tplink-cli leds --night-mode on --start 23:00 --end 07:00
```
Disable Night Mode schedule (keep LEDs active):
```bash
tplink-cli leds --night-mode off
```

---

### 3.4 Automated Reboot Schedule (`reboot-schedule`)
View current automated reboot schedule:
```bash
tplink-cli reboot-schedule
```
Enable daily reboot at 04:00 AM:
```bash
tplink-cli reboot-schedule on --time 04:00 --mode daily
```
Disable automated reboot schedule:
```bash
tplink-cli reboot-schedule off
```

---

## 4. NAT, Routing & System Services

### 4.1 NAT Port Forwarding (`port-forward`)
List all active NAT virtual server port forwarding rules:
```bash
tplink-cli port-forward list
```
Add a port forward rule (forward external port 8080 to internal IP `192.168.1.150:80`):
```bash
tplink-cli port-forward add web 8080 192.168.1.150 80 --proto TCP
```
Remove a port forward rule:
```bash
tplink-cli port-forward del 2,1,1,1,0,0
```

---

### 4.2 DMZ Host Forwarding (`dmz`)
Inspect current DMZ state:
```bash
tplink-cli dmz
```
Enable DMZ for a specific internal host IP:
```bash
tplink-cli dmz on 192.168.1.100
```
Disable DMZ forwarding:
```bash
tplink-cli dmz off
```

---

### 4.3 Universal Plug and Play (`upnp`)
Inspect UPnP status:
```bash
tplink-cli upnp
```
Toggle UPnP on:
```bash
tplink-cli upnp on
```
Toggle UPnP off:
```bash
tplink-cli upnp off
```

---

### 4.4 Dynamic DNS Providers (`ddns`)
Inspect Dynamic DNS (DDNS) providers and connection status:
```bash
tplink-cli ddns
```

---

### 4.5 System Clock & NTP Sync (`time`)
View router system clock:
```bash
tplink-cli time
```
Trigger network NTP time synchronization:
```bash
tplink-cli time --sync
```

---

### 4.6 Operation Mode (`op-mode`)
View router operating mode (3G/4G Router Mode vs Wireless Router Mode):
```bash
tplink-cli op-mode
```

---

### 4.7 Online Firmware Check (`fw-check`)
Check TP-Link cloud servers for available official firmware updates:
```bash
tplink-cli fw-check
```

---

## 5. Messaging, Logs & Administration

### 5.1 Cellular USSD Queries (`ussd`)
Execute Hutch SL account balance query:
```bash
tplink-cli ussd "*344#"
```
Execute Hutch SL menu / package query:
```bash
tplink-cli ussd "*123#"
```

---

### 5.2 SMS Text Messaging (`sms`)
List recent incoming SMS messages:
```bash
tplink-cli sms list --limit 5
```
List sent SMS messages:
```bash
tplink-cli sms list --folder sent --limit 5
```
Send an SMS message:
```bash
tplink-cli sms send 0781234567 "Hello from TP-Link CLI"
```

---

### 5.3 System & Cellular Event Logs (`logs`)
Read recent 20 router event log entries:
```bash
tplink-cli logs --lines 20
```
Filter logs for cellular 4G modem events:
```bash
tplink-cli logs --module 4G --lines 20
```
Filter logs for warnings and errors:
```bash
tplink-cli logs --level WARN --lines 20
```

---

### 5.4 Saved Credentials & Config (`config` / `cookie`)
Display stored endpoint configuration:
```bash
tplink-cli config show
```
View active cached browser session cookie:
```bash
tplink-cli cookie
```
Update saved router admin password:
```bash
tplink-cli config set-password
```

---

### 5.5 Router Hardware Reboot (`reboot`)
Safely reboot the router hardware:
```bash
tplink-cli reboot
```
Reboot skipping confirmation prompt:
```bash
tplink-cli reboot -y
```

---

## 6. Global Flags & Overrides

```bash
# Override target host per command
tplink-cli --host http://192.168.1.1 status

# Output machine-readable JSON
tplink-cli --json signal

# Bypass Wi-Fi safety guard checks
tplink-cli --force status
```
