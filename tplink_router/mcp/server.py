"""Universal Agent-Safe MCP (Model Context Protocol) Server for TP-Link Routers.

Provides typed router management tools to AI agents (Antigravity, Claude, Cursor)
with built-in disconnection safeguards, atomic single-admin session leasing,
and multi-environment network safety verification.
"""

import dataclasses
from typing import Optional, Dict, Any, List
from mcp.server.mcpserver import MCPServer

from tplink_router.clients.factory import RouterClientFactory
from tplink_router.core.config import ConfigManager
from tplink_router.core.network_guard import NetworkGuard
from tplink_router.core.session import SafeSession

server = MCPServer("tplink-mcp")


def _get_client_and_verify(force: bool = False):
    cfg = ConfigManager().load()
    if not cfg.get("password") and not cfg.get("session_cookie"):
        raise ValueError(
            "No password or session cookie configured for TP-Link router. "
            "Please configure using `tplink-cli config set-password`, `tplink-cli config set-cookie`, "
            "or set $TPLINK_PASSWORD or $TPLINK_SESSION_COOKIE."
        )

    # Check network safety (protect against sending commands while on Campus Wi-Fi or Hotspot)
    is_safe, msg = NetworkGuard.check_safety(target_host=cfg["host"], expected_ssid=cfg.get("expected_ssid"), force=force)
    if not is_safe:
        raise ConnectionError(f"Network Guard blocked execution: {msg}")

    return RouterClientFactory.get_client(
        host=cfg["host"],
        password=cfg.get("password", ""),
        username=cfg.get("username", "admin"),
        session_cookie=cfg.get("session_cookie")
    )


@server.tool()
def router_profile_check() -> Dict[str, Any]:
    """Inspects the current host network environment (SSID, Gateway) to ensure connection safety.

    Use this tool before applying configuration changes to confirm that the host is connected
    to the target router and not University Wi-Fi (e.g. SLIIT) or a mobile hotspot.
    """
    gw = NetworkGuard.get_current_gateway()
    ssid = NetworkGuard.get_current_ssid()
    cfg = ConfigManager().load()
    is_safe, msg = NetworkGuard.check_safety(target_host=cfg["host"], expected_ssid=cfg.get("expected_ssid"))
    return {
        "current_ssid": ssid or "Wired / Hotspot",
        "default_gateway": gw or "Unknown",
        "target_router_host": cfg["host"],
        "is_safe_to_configure": is_safe,
        "detail": msg,
    }


@server.tool()
def router_get_status(force: bool = False) -> Dict[str, Any]:
    """Retrieves full device, cellular LTE, RF signal metrics, and WAN network status.

    Args:
        force: Set to True to bypass Network Guard SSID/Gateway validation.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        telemetry = client.get_telemetry()

    import dataclasses
    return dataclasses.asdict(telemetry)


@server.tool()
def router_get_rf_signal(force: bool = False) -> Dict[str, Any]:
    """Retrieves real-time 4G LTE RF signal metrics (RSRP, RSRQ, SNR, EARFCN, PCI, Signal Bars).

    Guides router placement and antenna alignment for maximum 4G speed in Sri Lanka (e.g. Malabe/SLIIT).
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_lte_status"):
            return {"error": "RF metrics are only available on cellular MR series models."}
        lte = client.get_lte_status()

    import dataclasses
    return {
        "carrier": lte.isp_name,
        "band": lte.band,
        "earfcn": lte.earfcn,
        "pci": lte.pci,
        "metrics": dataclasses.asdict(lte.rf),
    }


@server.tool()
def router_set_cell_lock(enable: bool, earfcn: Optional[str] = None, pci: Optional[str] = None,
                        confirm: bool = False, force: bool = False) -> str:
    """Locks or unlocks the router to a specific cellular base station tower (EARFCN + PCI).

    IMPORTANT: Changing the cell tower momentarily drops and renegotiates the cellular link.
    You MUST provide confirm=True to execute.

    Args:
        enable: True to lock to cell, False to unlock (return to auto roaming).
        earfcn: E-UTRA Absolute Radio Frequency Channel Number (e.g. '1550' for Band 3).
        pci: Physical Cell Identity (e.g. '58').
        confirm: Safety confirmation. Set to True to proceed with connection renegotiation.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            "SAFETY WARNING: Locking or switching cell towers will momentarily interrupt "
            "the 4G LTE connection for 10-20 seconds while the radio renegotiates. "
            "If you intend to proceed, call this tool again with confirm=True."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_cell_lock"):
            return "Error: Cell Lock is only supported on cellular MR series models."
        client.set_cell_lock(enable=enable, earfcn=earfcn, pci=pci)

    if enable:
        return f"Cell Lock successfully applied to EARFCN {earfcn}, PCI {pci}. The modem is reconnecting."
    return "Cell Lock disabled. Router is roaming automatically."


@server.tool()
def router_set_dns(primary_dns: str, secondary_dns: str = "8.8.8.8", force: bool = False) -> str:
    """Configures custom DNS resolvers on the router's WAN connection.

    Args:
        primary_dns: Primary DNS IP (e.g. '8.8.8.8' for Google DNS, '1.1.1.1' for Cloudflare).
        secondary_dns: Secondary DNS IP (default '8.8.8.8').
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        client.set_dns(primary_dns, secondary_dns)
    return f"Router WAN DNS updated to {primary_dns}, {secondary_dns}."


@server.tool()
def router_toggle_ipv6(enable: bool, force: bool = False) -> str:
    """Enables or disables the IPv6 stack on the router's cellular connection.

    Disabling IPv6 is recommended if Hutch IPv6 routing is introducing dual-stack timeout delays.

    Args:
        enable: True to enable IPv6, False to disable.
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        client.toggle_ipv6(enable)
    return f"IPv6 stack has been {'enabled' if enable else 'disabled'} on the router."


@server.tool()
def router_run_ussd(code: str, force: bool = False) -> str:
    """Executes a USSD query on the cellular SIM card (e.g. '*344#' for Hutch quota, '*123#' for balance).

    Args:
        code: USSD string to send.
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "send_ussd"):
            return "USSD commands are only supported on cellular MR series models."
        res = client.send_ussd(code)
    return res.response if res.success else f"USSD Error: {res.error_message}"


@server.tool()
def router_read_sms(limit: int = 10, folder: str = "inbox", force: bool = False) -> List[Dict[str, Any]]:
    """Reads incoming or sent SMS messages from the router SIM inbox (e.g. package expiry alerts).

    Args:
        limit: Maximum number of SMS messages to retrieve (default 10).
        folder: Message folder ('inbox' or 'sent').
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_sms"):
            return [{"error": "SMS is only supported on cellular MR series models."}]
        msgs = client.get_sms(limit=limit, folder=folder)

    import dataclasses
    return [dataclasses.asdict(m) for m in msgs]


@server.tool()
def router_send_sms(to_phone: str, message: str, force: bool = False) -> str:
    """Sends an SMS message through the router SIM card.

    Args:
        to_phone: Recipient phone number.
        message: Message text content.
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "send_sms"):
            return "SMS is only supported on cellular MR series models."
        client.send_sms(to_phone, message)
    return f"SMS successfully sent to {to_phone}."


@server.tool()
def router_get_connected_clients(force: bool = False) -> List[Dict[str, Any]]:
    """Retrieves all connected wired and wireless devices currently on the router LAN.

    Returns hostnames, IP addresses, MAC addresses, and lease durations.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_connected_clients"):
            return [{"error": "Client listing is only supported on MR cellular models."}]
        return client.get_connected_clients()


@server.tool()
def router_manage_dhcp_reservation(action: str, mac: Optional[str] = None, ip: Optional[str] = None,
                                  confirm: bool = False, force: bool = False) -> str:
    """Manages static DHCP IP address reservations on the router.

    Args:
        action: 'add', 'delete', or 'list'.
        mac: Hardware MAC address (e.g. 'AA:BB:CC:DD:EE:FF', required for 'add' or 'delete').
        ip: Desired reserved IP address (required for 'add').
        confirm: Confirmation required for 'add' or 'delete'.
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_dhcp_reservations"):
            return "DHCP reservation is only supported on MR cellular models."

        if action == "list":
            res = client.get_dhcp_reservations()
            if not res:
                return "No static DHCP reservations configured."
            import json
            return json.dumps(res, indent=2)

        if not mac:
            return f"Error: MAC address is required when performing action '{action}'."

        if not confirm:
            return f"SAFETY WARNING: Modifying DHCP reservations alters LAN routing. Call again with confirm=True to {action} reservation for MAC {mac}."

        if action == "add":
            if not ip:
                return "Error: IP address is required when adding a reservation."
            client.add_dhcp_reservation(mac, ip)
            return f"DHCP static reservation added for MAC {mac} -> IP {ip}."
        elif action == "delete":
            client.delete_dhcp_reservation(mac)
            return f"DHCP reservation deleted for MAC {mac}."
        return f"Unknown action: {action}"


@server.tool()
def router_get_data_limit(force: bool = False) -> Dict[str, Any]:
    """Retrieves monthly cellular data allowance, billing cycle start day, and live bandwidth."""
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_data_limit"):
            return {"error": "Data limits are only supported on cellular MR series models."}
        return client.get_data_limit()


@server.tool()
def router_set_data_limit(limit_mb: int, payment_day: int = 1, warning_percent: int = 90,
                          enable: bool = True, confirm: bool = False, force: bool = False) -> str:
    """Configures monthly cellular data quota, billing day reset, and usage alert threshold.

    Args:
        limit_mb: Total monthly data allowance in Megabytes (e.g. 50000 for 50GB).
        payment_day: Day of month when billing cycle resets (1-31).
        warning_percent: Threshold percent to trigger alert (e.g. 90).
        enable: True to enforce quota, False to disable.
        confirm: Confirmation required to apply data quota limits.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return f"Confirm setting monthly cellular quota to {limit_mb} MB (billing day {payment_day}) by passing confirm=True."

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_data_limit"):
            return "Data limit configuration is only supported on cellular MR series models."
        client.set_data_limit(enabled=enable, limit_mb=limit_mb, warning_percent=warning_percent, payment_day=payment_day)
    return f"Monthly data limit updated: {limit_mb} MB, reset on day {payment_day} of month."


@server.tool()
def router_get_wifi_networks(force: bool = False) -> List[Dict[str, Any]]:
    """Retrieves status, SSIDs, channels, and operational state of 2.4 GHz and 5 GHz Wi-Fi radios."""
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_wifi_status"):
            return [{"error": "Wi-Fi status listing is only supported on MR cellular models."}]
        return client.get_wifi_status()


@server.tool()
def router_set_wifi_radio(band: str, enable: bool, ssid: Optional[str] = None,
                          confirm: bool = False, force: bool = False) -> str:
    """Enables or disables a Wi-Fi radio (2.4GHz or 5GHz) and optionally updates its SSID.

    IMPORTANT: Disabling the Wi-Fi band you are currently connected to will disconnect your host!
    You MUST provide confirm=True to execute.

    Args:
        band: '2.4GHz' or '5GHz'.
        enable: True to enable radio, False to disable.
        ssid: Optional new SSID name.
        confirm: Safety confirmation. Set to True to apply radio changes.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            f"SAFETY WARNING: Changing Wi-Fi radio '{band}' state (enable={enable}) will disconnect "
            f"any devices currently connected to that frequency band. Provide confirm=True to proceed."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_wifi_radio"):
            return "Wi-Fi radio configuration is only supported on MR cellular models."
        client.set_wifi_radio(band=band, enabled=enable, ssid=ssid)
    return f"Wi-Fi {band} radio updated (enable={enable}, ssid={ssid or 'unchanged'})."


@server.tool()
def router_get_led_status(force: bool = False) -> Dict[str, Any]:
    """Retrieves the physical LED status and night mode schedule."""
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_led_status"):
            return {"error": "LED control is only supported on MR cellular models."}
        return client.get_led_status()


@server.tool()
def router_set_led_night_mode(enable: bool, start_time: str = "22:00", end_time: str = "07:00",
                              force: bool = False) -> str:
    """Configures night mode to turn off router front panel LEDs automatically during sleeping hours.

    Args:
        enable: True to activate night mode schedule, False to disable.
        start_time: 'HH:MM' time when LEDs turn OFF (e.g. '22:00').
        end_time: 'HH:MM' time when LEDs turn back ON (e.g. '07:00').
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_led_night_mode"):
            return "LED schedule is only supported on MR cellular models."
        client.set_led_night_mode(enabled=enable, start_time=start_time, end_time=end_time)
    return f"Night mode {'enabled' if enable else 'disabled'} (LEDs OFF from {start_time} to {end_time})."


@server.tool()
def router_run_diagnostic(force: bool = False) -> Dict[str, Any]:
    """Runs a router-side diagnostic self-test verifying physical link, WAN IP, and Internet NCSI reachability."""
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "run_wan_diagnostic"):
            return {"error": "Router diagnostic is only supported on MR cellular models."}
        return client.run_wan_diagnostic()


@server.tool()
def router_set_lte_band(band: str, confirm: bool = False, force: bool = False) -> str:
    """Manually locks router to a specific LTE band (e.g. '3' for 1800MHz, '8' for 900MHz, '40' for 2300MHz, or 'auto').

    Essential for locking to optimal Hutch/Dialog 4G towers in Sri Lanka (e.g. Malabe).
    IMPORTANT: Changing bands triggers cellular radio renegotiation.

    Args:
        band: LTE Band number (e.g. '3', '8', '40') or 'auto'.
        confirm: Safety confirmation. Set to True to execute band change.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            f"SAFETY WARNING: Switching LTE band to '{band}' will momentarily drop and reconnect the 4G link "
            f"for 10-15 seconds. Call again with confirm=True to execute."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_lte_band"):
            return "Band lock is only supported on MR cellular models."
        client.set_lte_band(band=band)
    return f"LTE band lock set to {band.upper()}. Cellular radio is reconnecting to selected frequency."


@server.tool()
def router_calibrate(web: bool = True, port: int = 8765, dry_run: bool = False, confirm: bool = False) -> str:
    """Runs autonomous RF band calibration across LTE frequencies (Band 8, 3, 1, 40, Auto) with 45s watchdog fail-safe.

    Launches a real-time Live Web Dashboard on http://localhost:8765.
    During band switches, the router modem temporarily detaches for 5-15 seconds.
    The local daemon safeguards against permanent disconnection by auto-reverting if WAN drops for >45s.

    Args:
        web: Launch real-time Web UI on localhost:8765 (default: True).
        port: Web dashboard port (default: 8765).
        dry_run: Simulate band switches without modem detachment.
        confirm: Confirmation flag to execute calibration.
    """
    if not confirm and not dry_run:
        return (
            "NOTICE: Cellular calibration sweeps multiple LTE bands. Switching bands causes "
            "temporary WAN disconnections (5-15 seconds per band). A 45-second watchdog auto-reverts "
            "if signal is lost. To proceed, call this tool with confirm=True or dry_run=True."
        )

    from tplink_router.calibration.engine import RouterCalibrator
    from tplink_router.calibration.dashboard import start_dashboard_server

    cfg = ConfigManager().load()
    calibrator = RouterCalibrator(
        host=cfg.get("host", "http://192.168.1.1"),
        password=cfg.get("password"),
        username=cfg.get("username", "admin"),
        watchdog_timeout=45,
        dry_run=dry_run,
    )

    if web:
        start_dashboard_server(calibrator=calibrator, port=port, blocking=False)

    res = calibrator.run_sweep()
    rec = res.get("recommendation", {})
    return (
        f"Calibration completed!\n"
        f"Winning Carrier: {rec.get('winning_band_name')} (Utility: {rec.get('utility_score')}/100)\n"
        f"Reasoning: {rec.get('reasoning_summary')}\n"
        f"Live Dashboard: http://localhost:{port}/"
    )


@server.tool()
def router_reboot(confirm: bool = False, force: bool = False) -> str:
    """Initiates a graceful reboot of the TP-Link router.

    IMPORTANT: Rebooting will terminate the host's internet and Wi-Fi connection for ~60-90 seconds.
    You MUST provide confirm=True to execute.

    Args:
        confirm: Safety confirmation. Set to True to trigger the restart.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            "SAFETY WARNING: Rebooting the router will sever your active internet connection "
            "for 60 to 90 seconds. Call this tool again with confirm=True if you wish to proceed."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        client.reboot()
    return "Reboot command sent to router. The router is restarting."


@server.tool()
def router_get_system_logs(lines: int = 50, module: Optional[str] = None, min_level: Optional[str] = None, force: bool = False) -> List[Dict[str, Any]]:
    """Retrieves system and cellular event logs from the TP-Link router.

    Args:
        lines: Maximum number of recent log entries to return (default: 50).
        module: Optional filter by subsystem (e.g. '4G', 'DHCP', 'System', 'DNS').
        min_level: Optional minimum severity filter ('EMERG', 'ALERT', 'CRIT', 'ERROR', 'WARN', 'NOTICE', 'INFO', 'DEBUG').
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_system_logs"):
            return [{"error": "System logs are only supported on MR cellular models."}]
        logs = client.get_system_logs(limit=lines, module=module, min_level=min_level)
    return [dataclasses.asdict(l) for l in logs]


@server.tool()
def router_clear_system_logs(confirm: bool = False, force: bool = False) -> str:
    """Clears the internal system event log buffer on the router.

    Args:
        confirm: Safety confirmation. Set to True to clear logs.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return "SAFETY NOTICE: Clearing logs will permanently erase all system audit entries. Call with confirm=True to proceed."

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "clear_system_logs"):
            return "System logs are only supported on MR cellular models."
        client.clear_system_logs()
    return "System event logs successfully cleared."


@server.tool()
def router_get_guest_wifi(force: bool = False) -> Dict[str, Any]:
    """Retrieves current dual-band (2.4GHz / 5GHz) Guest Wi-Fi status, SSIDs, and isolation settings.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_guest_wifi"):
            return {"error": "Guest Wi-Fi is only supported on MR cellular models."}
        gw = client.get_guest_wifi()
    return dataclasses.asdict(gw)


@server.tool()
def router_set_guest_wifi(band: str = "both", enabled: bool = True, ssid: Optional[str] = None,
                          password: Optional[str] = None, allow_lan: Optional[bool] = None,
                          confirm: bool = False, force: bool = False) -> str:
    """Configures or toggles dual-band Guest Wi-Fi networks and local LAN isolation.

    Args:
        band: Target band ('2.4GHz', '5GHz', or 'both').
        enabled: Enable (True) or disable (False) Guest Wi-Fi on selected band.
        ssid: Custom SSID name for the guest network.
        password: WPA2-PSK password (minimum 8 characters, or empty string '' for open network).
        allow_lan: If True, guests can reach LAN devices; if False, guests are isolated to Internet-only.
        confirm: Confirmation flag to apply configuration.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            f"SAFETY NOTICE: Modifying Guest Wi-Fi (band={band}, enabled={enabled}) will update router radio parameters. "
            f"Call with confirm=True to apply."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_guest_wifi"):
            return "Guest Wi-Fi is only supported on MR cellular models."
        client.set_guest_wifi(band=band, enabled=enabled, ssid=ssid, password=password, allow_lan=allow_lan)
    return f"Guest Wi-Fi ({band}) successfully {'enabled' if enabled else 'disabled'}."


@server.tool()
def router_get_port_forwarding(force: bool = False) -> List[Dict[str, Any]]:
    """Lists active NAT Virtual Server port forwarding rules on the cellular WAN interface.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_port_forwarding"):
            return [{"error": "Port forwarding is only supported on MR cellular models."}]
        rules = client.get_port_forwarding()
    return [dataclasses.asdict(r) for r in rules]


@server.tool()
def router_add_port_forwarding(name: str, external_port: str, internal_ip: str,
                               internal_port: Optional[str] = None, protocol: str = "ALL",
                               confirm: bool = False, force: bool = False) -> str:
    """Creates a new NAT virtual server port forwarding rule on the router.

    Args:
        name: Service or descriptive name (e.g. 'web', 'ssh', 'minecraft').
        external_port: Incoming WAN port or port range (e.g. '8080' or '8000-8010').
        internal_ip: LAN destination IP address (e.g. '192.168.1.150').
        internal_port: LAN destination port (defaults to external_port if omitted).
        protocol: Transport protocol ('TCP', 'UDP', or 'ALL').
        confirm: Confirmation flag to add rule.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            f"SAFETY NOTICE: Adding port forward '{name}' ({external_port} -> {internal_ip}:{internal_port or external_port} {protocol}) "
            f"opens an incoming WAN port. Call with confirm=True to execute."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "add_port_forwarding"):
            return "Port forwarding is only supported on MR cellular models."
        client.add_port_forwarding(
            name=name,
            external_port=external_port,
            internal_ip=internal_ip,
            internal_port=internal_port,
            protocol=protocol
        )
    return f"Port forward rule '{name}' ({external_port} -> {internal_ip}) successfully created."


@server.tool()
def router_del_port_forwarding(rule_stack: str, confirm: bool = False, force: bool = False) -> str:
    """Deletes an existing NAT virtual server port forwarding rule by stack ID.

    Args:
        rule_stack: Stack identifier of the rule to remove (e.g. '2,1,1,1,0,0').
        confirm: Confirmation flag to delete rule.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return f"SAFETY NOTICE: Deleting port forward rule {rule_stack}. Call with confirm=True to execute."

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "del_port_forwarding"):
            return "Port forwarding is only supported on MR cellular models."
        client.del_port_forwarding(rule_stack=rule_stack)
    return f"Port forward rule {rule_stack} successfully deleted."


@server.tool()
def router_get_dmz(force: bool = False) -> Dict[str, Any]:
    """Retrieves DMZ (Demilitarized Zone) host forwarding status and destination IP.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_dmz"):
            return {"error": "DMZ is only supported on MR cellular models."}
        dmz = client.get_dmz()
    return dataclasses.asdict(dmz)


@server.tool()
def router_set_dmz(enabled: bool, ip_address: str = "", confirm: bool = False, force: bool = False) -> str:
    """Enables or disables DMZ host forwarding to an internal IP address.

    Args:
        enabled: True to enable DMZ, False to disable.
        ip_address: Internal IP address to receive all unmapped incoming traffic.
        confirm: Confirmation flag to modify DMZ.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            f"SAFETY WARNING: Setting DMZ to {enabled} (IP: {ip_address}) exposes all unmapped ports to that host. "
            f"Call with confirm=True to execute."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_dmz"):
            return "DMZ is only supported on MR cellular models."
        client.set_dmz(enabled=enabled, ip_address=ip_address)
    return f"DMZ successfully {'enabled for ' + ip_address if enabled else 'disabled'}."


@server.tool()
def router_get_upnp(force: bool = False) -> Dict[str, Any]:
    """Retrieves Universal Plug and Play (UPnP) status and active dynamic port mappings.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_upnp"):
            return {"error": "UPnP is only supported on MR cellular models."}
        upnp = client.get_upnp()
    return dataclasses.asdict(upnp)


@server.tool()
def router_set_upnp(enabled: bool, confirm: bool = False, force: bool = False) -> str:
    """Enables or disables UPnP dynamic port forwarding on the router.

    Args:
        enabled: True to enable UPnP, False to disable.
        confirm: Confirmation flag to modify UPnP.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return f"SAFETY NOTICE: Toggling UPnP to {'enabled' if enabled else 'disabled'}. Call with confirm=True to apply."

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_upnp"):
            return "UPnP is only supported on MR cellular models."
        client.set_upnp(enabled=enabled)
    return f"UPnP service successfully {'enabled' if enabled else 'disabled'}."


@server.tool()
def router_get_reboot_schedule(force: bool = False) -> Dict[str, Any]:
    """Retrieves the automated periodic reboot schedule settings.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_reboot_schedule"):
            return {"error": "Reboot schedule is only supported on MR cellular models."}
        rs = client.get_reboot_schedule()
    return dataclasses.asdict(rs)


@server.tool()
def router_set_reboot_schedule(enabled: bool, hours: int = 3, minutes: int = 0,
                               mode: str = "daily", day_of_week: int = 1,
                               confirm: bool = False, force: bool = False) -> str:
    """Configures or disables automated daily or weekly periodic router reboots.

    Args:
        enabled: True to enable auto-reboot, False to disable.
        hours: Hour of the day in 24h format (0-23, default: 3).
        minutes: Minute of the hour (0-59, default: 0).
        mode: Repeat frequency ('daily' or 'weekly').
        day_of_week: Day of week for weekly mode (1=Mon, 2=Tue, ..., 7=Sun).
        confirm: Confirmation flag to apply schedule.
        force: Set to True to bypass Network Guard safety check.
    """
    if not confirm:
        return (
            f"SAFETY NOTICE: Configuring reboot schedule (enabled={enabled}, time={hours:02d}:{minutes:02d}, mode={mode}). "
            f"Call with confirm=True to apply."
        )

    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "set_reboot_schedule"):
            return "Reboot schedule is only supported on MR cellular models."
        client.set_reboot_schedule(enabled=enabled, hours=hours, minutes=minutes, mode=mode, day_of_week=day_of_week)
    return f"Reboot schedule successfully {'enabled (' + f'{hours:02d}:{minutes:02d}' + ')' if enabled else 'disabled'}."


@server.tool()
def router_get_time(force: bool = False) -> Dict[str, Any]:
    """Retrieves current router system clock, time zone, daylight savings, and NTP server status.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_time_config"):
            return {"error": "Time config is only supported on MR cellular models."}
        tc = client.get_time_config()
    return dataclasses.asdict(tc)


@server.tool()
def router_sync_time(force: bool = False) -> str:
    """Triggers an immediate NTP network time synchronization on the router.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "sync_time"):
            return "Time sync is only supported on MR cellular models."
        client.sync_time()
    return "NTP time synchronization request dispatched successfully."


@server.tool()
def router_get_operation_mode(force: bool = False) -> Dict[str, Any]:
    """Retrieves the active router operation mode (3G/4G Router Mode vs Wireless Router Mode).

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_operation_mode"):
            return {"error": "Operation mode is only supported on MR cellular models."}
        om = client.get_operation_mode()
    return dataclasses.asdict(om)


@server.tool()
def router_get_ddns(force: bool = False) -> List[Dict[str, Any]]:
    """Retrieves Dynamic DNS (DDNS) provider configurations (TP-Link Cloud, No-IP, DynDNS).

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "get_ddns_status"):
            return [{"error": "DDNS status is only supported on MR cellular models."}]
        ddns_list = client.get_ddns_status()
    return [dataclasses.asdict(d) for d in ddns_list]


@server.tool()
def router_check_firmware(force: bool = False) -> Dict[str, Any]:
    """Checks for available online official TP-Link firmware updates.

    Args:
        force: Set to True to bypass Network Guard safety check.
    """
    client = _get_client_and_verify(force=force)
    with SafeSession(client):
        if not hasattr(client, "check_firmware_update"):
            return {"error": "Firmware check is only supported on MR cellular models."}
        fw = client.check_firmware_update()
    return dataclasses.asdict(fw)


def main():
    server.run()


if __name__ == "__main__":
    main()
