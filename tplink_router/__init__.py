"""Universal TP-Link Agentic Router Suite & MCP Server.

A cross-platform (Linux, macOS, Windows) CLI and Model Context Protocol (MCP) tool
for autonomous AI agents and users to monitor, configure, and optimize TP-Link routers.
"""

from tplink_router.clients.factory import RouterClientFactory
from tplink_router.core.session import SafeSession
from tplink_router.core.config import ConfigManager

__version__ = "1.0.0"
__all__ = ["RouterClientFactory", "SafeSession", "ConfigManager"]
