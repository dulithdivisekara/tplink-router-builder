"""Broadband Client for TP-Link Archer C, AX, BE, and Deco routers using tplinkrouterc6u."""

import logging
from typing import Optional
from tplink_router.models.device import DeviceInfo, IPv4Config, IPv6Config, RouterTelemetry

logger = logging.getLogger(__name__)


class TPLinkBroadbandClient:
    """Client for TP-Link standard broadband/Wi-Fi routers (non-cellular)."""

    def __init__(self, host: str, password: str, username: str = "admin", timeout: int = 25):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client = None
        self.is_authenticated = False

    def _get_inner_client(self):
        if self._client is None:
            try:
                from tplinkrouterc6u import TplinkRouterProvider
                self._client = TplinkRouterProvider.get_client(
                    self.host, self.password, self.username, timeout=self.timeout
                )
            except Exception as e:
                logger.error(f"Failed to initialize tplinkrouterc6u provider: {e}")
                raise
        return self._client

    def login(self) -> bool:
        client = self._get_inner_client()
        client.authorize()
        self.is_authenticated = True
        return True

    def logout(self):
        if self._client and self.is_authenticated:
            try:
                self._client.logout()
            except Exception:
                pass
            finally:
                self.is_authenticated = False

    def get_device_info(self) -> DeviceInfo:
        client = self._get_inner_client()
        firmware = client.get_firmware()
        return DeviceInfo(
            model=getattr(client, "ROUTER_NAME", "Archer Broadband Router"),
            hardware_version=getattr(firmware, "hardware_version", "v1"),
            firmware_version=getattr(firmware, "firmware_version", "1.0.0"),
            description="TP-Link Broadband Router",
        )

    def get_telemetry(self) -> RouterTelemetry:
        dev = self.get_device_info()
        client = self._get_inner_client()
        v4_status = client.get_ipv4_status()
        v6_status = client.get_ipv6_status()

        v4 = IPv4Config(
            ip=getattr(v4_status, "wan_ipv4_ipaddr", ""),
            subnet=getattr(v4_status, "wan_ipv4_netmask", ""),
            gateway=getattr(v4_status, "wan_ipv4_gateway", ""),
            dns=getattr(v4_status, "wan_ipv4_dns", []),
        )
        v6 = IPv6Config(
            enabled=getattr(v6_status, "enable", False),
            ip=getattr(v6_status, "wan_ipv6_ipaddr", ""),
            dns=getattr(v6_status, "wan_ipv6_dns", []),
        )
        return RouterTelemetry(device=dev, lte=None, ipv4=v4, ipv6=v6)

    def reboot(self) -> bool:
        client = self._get_inner_client()
        client.reboot()
        return True
