"""Router Client Factory with automatic hardware & firmware detection."""

import logging
import requests
from typing import Optional, Union

from tplink_router.clients.mr_client import TPLinkMRClient
from tplink_router.clients.broad_client import TPLinkBroadbandClient

logger = logging.getLogger(__name__)


class RouterClientFactory:
    """Detects router architecture and returns the matching client implementation."""

    @classmethod
    def detect_model_family(cls, host: str, timeout: int = 5) -> str:
        """Probes the router web server to detect if it is an LTE/MR series or Broadband series."""
        host = host.rstrip("/")
        try:
            resp = requests.get(host, headers={"Referer": f"{host}/"}, timeout=timeout)
            text = resp.text.lower()
            if "mr200" in text or "mr6400" in text or "mr600" in text or "mr400" in text or "lte" in text:
                return "mr"
            if "ax" in text or "be" in text or "archer c" in text or "deco" in text:
                return "broadband"
        except Exception as e:
            logger.debug(f"Probing router host {host} raised: {e}")

        # Default to MR-series for cellular 4G routers
        return "mr"

    @classmethod
    def get_client(cls, host: str, password: str, username: str = "admin",
                   force_family: Optional[str] = None, timeout: int = 25,
                   session_cookie: Optional[str] = None) -> Union[TPLinkMRClient, TPLinkBroadbandClient]:
        """Creates an authenticated client instance appropriate for the target hardware."""
        family = force_family or cls.detect_model_family(host, timeout=5)

        if family.lower() == "broadband":
            logger.info("Initializing TP-Link Broadband Client (AX/BE/C/Deco)...")
            return TPLinkBroadbandClient(host=host, password=password, username=username, timeout=timeout)

        logger.info("Initializing TP-Link MR LTE Client (MR200/MR6400/MR600)...")
        return TPLinkMRClient(host=host, password=password, username=username, timeout=timeout, session_cookie=session_cookie)
