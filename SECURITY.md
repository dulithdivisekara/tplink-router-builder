# Security Policy

This document outlines the security architecture, session lifecycle invariants, vulnerability disclosure procedures, and local credential hygiene standards for the TP-Link Router Suite.

---

## Supported Versions

Security patches and vulnerability updates are actively maintained on the following branches:

| Version | Status | Security Maintenance |
| :--- | :--- | :--- |
| **1.1.x** | Current Release | Actively Supported |
| **1.0.x** | Legacy Distribution | Critical Fixes Only |
| **< 1.0.0** | Deprecated Prototype | Unsupported |

---

## Architectural Security Invariants

The TP-Link Router Suite operates against embedded physical router hardware and incorporates four strict architectural safeguards to protect network availability and administrative access.

### 1. Atomic Single-Admin Session Leasing

TP-Link router firmware (including Archer MR200, MR6400, MR600, and Archer AX series) permits only a single authenticated administrative web session at any given time. If an automated script maintains a persistent open session, subsequent administrative logins via the local web portal (`http://192.168.1.1`) are denied with concurrency lock errors.

To prevent administrative lockout:
- Every CLI subcommand and MCP tool invocation executes inside an atomic `SafeSession` context manager.
- `SafeSession` acquires a local file lock (`~/.config/tplink-router/.session.lock`), executes the cryptographic handshake (RSA-1024 / AES-128-CBC), transmits the TR-064 payload, and dispatches an immediate atomic logout request (`ACT_OP` with `logout`).
- Even in unhandled exception states, `SafeSession.__exit__` guarantees the logout frame is dispatched and the local lockfile is released.

### 2. Multi-Environment Network Guard

When developing across university campus networks (such as SLIIT Campus Wi-Fi), public co-working hotspots, and private residential router gateways, invoking router administration tools presents an acute risk of broadcasting authentication payloads to unauthorized institutional infrastructure.

The suite enforces an automatic pre-flight check via `NetworkGuard`:
- Inspects the active default gateway IP, MAC address, and active Wi-Fi SSID across Linux (`ip route`, `iwgetid`), macOS (`route -n`, `airport`), and Windows (`netsh wlan`).
- If the current SSID matches an unauthorized network or does not match the configured `expected_ssid`, mutation commands are aborted prior to dispatching network frames.

### 3. Destructive Operation Confirmation Gates

Autonomous AI assistants operating over the Model Context Protocol (MCP) must be prevented from recursively severing their own active network connections. All service-disrupting operations require an explicit confirmation parameter:
- `router_reboot`: Requires `confirm=True`.
- `router_set_cell_lock`: Requires `confirm=True`.
- `router_set_lte_band`: Requires `confirm=True`.
- `router_set_data_limit`: Requires `confirm=True`.

When invoked without explicit confirmation, tools return a structured error response explaining the requirement for user consent.

### 4. Local Credential Isolation

- Router passwords stored via `tplink-cli config set-password` are saved in `~/.config/tplink-router/config.json`.
- The configuration file is strictly written with POSIX `0600` permissions (read/write access restricted solely to the file owner).
- Password strings are automatically redacted (`***REDACTED***`) in terminal outputs, debug logs, and diagnostic dumps.
- Strict `.gitignore` rules prevent `.env`, `credentials.json`, `config.json`, `*.session`, and `*.log` files from being tracked in version control.

---

## Reporting a Vulnerability

If you identify a security vulnerability, credential exposure vector, or concurrency flaw within the TP-Link Router Suite, please disclose it responsibly:

1. **Do not open a public GitHub issue.**
2. Send a detailed report via encrypted email to:
   - **Lead Maintainer**: Dulith Divisekara
   - **Email**: `dulithdivisekara@gmail.com`
3. Include the following details:
   - Specific component or tool affected (`core/auth.py`, `core/session.py`, `mcp/server.py`, or CLI).
   - Target router hardware model and firmware version (if hardware-specific).
   - Step-by-step reproduction steps or minimal proof-of-concept script.
   - Potential impact (e.g., denial of service, session hijacking, unauthorized configuration change).

### Response Timeline
- **Initial Acknowledgment**: Within 48 hours.
- **Triage & Reproduction**: Within 5 business days.
- **Remediation & Patch Release**: Within 14 business days of confirmation.
