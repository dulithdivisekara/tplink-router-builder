"""Safe atomic session manager ensuring immediate release of router admin lock."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SafeSession:
    """Context manager that guarantees login on entry and immediate logout on exit.

    TP-Link routers allow only ONE administrator session at a time.
    By using SafeSession, commands will not lock out web browsers or other tools.
    """

    def __init__(self, client: Any):
        self.client = client

    def __enter__(self):
        self.client.login()
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.client.logout()
        except Exception as e:
            logger.debug(f"Error during graceful logout: {e}")
        return False  # Don't suppress exceptions
