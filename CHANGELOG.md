# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-28

### Added
- **Cross-Platform Compatibility**: Full support across Linux, macOS, and Windows.
- **Agent-Safe Session Lifecycle (`SafeSession`)**: Atomic login, execution, and immediate logout to prevent locking out the router web UI.
- **Multi-Environment Network Guard (`NetworkGuard`)**: Automatic detection of active Wi-Fi SSID and default gateway to prevent misconfiguring University Wi-Fi (e.g. SLIIT) or mobile hotspots.
- **Universal Router Client Factory (`RouterClientFactory`)**: Auto-detection between LTE/4G series (MR200, MR6400, MR600) and Broadband Wi-Fi 6/7 series (AX, BE, C, Deco).
- **LTE Cell Lock & RF Signal Monitoring**: EARFCN and PCI locking, calibrated 3GPP RSRP, RSRQ, and SNR metrics for optimal tower positioning.
- **SMS & USSD Engine**: Complete SMS inbox/sent inspection, sending, and operator USSD queries (e.g. Hutch `*344#`).
- **Interactive REPL Console (`tplink-cli repl`)**: Command console maintaining an active session for rapid multi-command workflows.
- **Model Context Protocol (MCP 2.x) Server**: 10 typed tools with safety confirmation flags (`confirm=True`) for autonomous AI agents.
- **Client-Side Linux Network Optimizer (`optimize-network.sh`)**: Reversible TCP BBR congestion control, bufferbloat reduction, and MTU 1420 GTP clamping.
- **Cellular Keepalive Pulse (`keepalive-pulse.sh`)**: 28-byte heartbeat keeping cellular modems in `RRC_CONNECTED` state.
