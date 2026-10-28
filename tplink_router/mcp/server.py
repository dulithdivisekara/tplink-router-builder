"""Universal Agent-Safe MCP (Model Context Protocol) Server for TP-Link Routers.

Provides typed router management tools to AI agents (Antigravity, Claude, Cursor)
with built-in disconnection safeguards, atomic single-admin session leasing,
and multi-environment network safety verification.
"""

from typing import Optional, Dict, Any, List
from mcp.server.mcpserver import MCPServer

from tplink_router.clients.factory import RouterClientFactory
from tplink_router.core.config import ConfigManager
from tplink_router.core.network_guard import NetworkGuard
from tplink_router.core.session import SafeSession

server = MCPServer("universal-tplink-mcp")


def _get_client_and_verify(force: bool = False):
    cfg = ConfigManager().load()
    if not cfg.get("password"):
        raise ValueError(
            "No password configured for TP-Link router. "
            "Please configure using `tplink-cli config set-password` or set $TPLINK_PASSWORD."
        )

    # Check network safety (protect against sending commands while on Campus Wi-Fi or Hotspot)
    is_safe, msg = NetworkGuard.check_safety(target_host=cfg["host"], expected_ssid=cfg.get("expected_ssid"), force=force)
    if not is_safe:
        raise ConnectionError(f"Network Guard blocked execution: {msg}")

    return RouterClientFactory.get_client(host=cfg["host"], password=cfg["password"], username=cfg["username"])


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
def router_manage_dhcp_reservation(action: str, mac: str, ip: Optional[str] = None,
                                  confirm: bool = False, force: bool = False) -> str:
    """Manages static DHCP IP address reservations on the router.

    Args:
        action: 'add', 'delete', or 'list'.
        mac: Hardware MAC address (e.g. 'AA:BB:CC:DD:EE:FF').
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
            return str(res)

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


if __name__ == "__main__":
    server.run()
