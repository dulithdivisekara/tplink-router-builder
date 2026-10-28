"""Hierarchical configuration manager for TP-Link routers across all platforms."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "tplink-router"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_HOST = "http://192.168.1.1"
DEFAULT_USERNAME = "admin"


class ConfigManager:
    """Manages credentials and settings with hierarchical resolution."""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or DEFAULT_CONFIG_FILE

    def _read_env_file(self, env_path: Path) -> Dict[str, str]:
        """Reads simple KEY=VALUE pairs from an .env file."""
        res = {}
        if not env_path.exists():
            return res
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    res[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass
        return res

    def load(self, cli_host: Optional[str] = None,
             cli_username: Optional[str] = None,
             cli_password: Optional[str] = None) -> Dict[str, Any]:
        """Resolves configuration with precedence:
        1. CLI arguments
        2. Environment variables (TPLINK_ROUTER_IP, TPLINK_PASSWORD, etc.)
        3. Local project .env or $TPLINK_ENV
        4. User configuration file (~/.config/tplink-router/config.json)
        5. Defaults
        """
        # Start with defaults
        config = {
            "host": DEFAULT_HOST,
            "username": DEFAULT_USERNAME,
            "password": "",
            "expected_ssid": "",
            "auto_detect": True,
        }

        # 4. User config file
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config.update({k: v for k, v in data.items() if v is not None})
            except Exception:
                pass

        # Also support legacy config file if present
        legacy_cfg = Path.home() / ".config" / "tplink-mr200" / "config.json"
        if not config.get("password") and legacy_cfg.exists():
            try:
                with open(legacy_cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config.update({k: v for k, v in data.items() if v is not None})
            except Exception:
                pass

        # 3. Project .env or custom env file
        env_file = Path(os.environ.get("TPLINK_ENV", ".env"))
        env_vars = self._read_env_file(env_file)
        if "ROUTER_IP" in env_vars or "TPLINK_ROUTER_IP" in env_vars:
            config["host"] = env_vars.get("ROUTER_IP") or env_vars.get("TPLINK_ROUTER_IP")
        if "ROUTER_USERNAME" in env_vars or "TPLINK_USERNAME" in env_vars:
            config["username"] = env_vars.get("ROUTER_USERNAME") or env_vars.get("TPLINK_USERNAME")
        if "ROUTER_PASSWORD" in env_vars or "TPLINK_PASSWORD" in env_vars:
            config["password"] = env_vars.get("ROUTER_PASSWORD") or env_vars.get("TPLINK_PASSWORD")
        if "EXPECTED_SSID" in env_vars:
            config["expected_ssid"] = env_vars["EXPECTED_SSID"]

        # 2. OS Environment variables
        if os.environ.get("TPLINK_ROUTER_IP"):
            config["host"] = os.environ["TPLINK_ROUTER_IP"]
        if os.environ.get("TPLINK_USERNAME"):
            config["username"] = os.environ["TPLINK_USERNAME"]
        if os.environ.get("TPLINK_PASSWORD"):
            config["password"] = os.environ["TPLINK_PASSWORD"]
        if os.environ.get("TPLINK_EXPECTED_SSID"):
            config["expected_ssid"] = os.environ["TPLINK_EXPECTED_SSID"]

        # 1. CLI Arguments
        if cli_host:
            config["host"] = cli_host
        if cli_username:
            config["username"] = cli_username
        if cli_password:
            config["password"] = cli_password

        # Normalize host URL
        if not config["host"].startswith("http"):
            config["host"] = f"http://{config['host']}"

        return config

    def save(self, password: str, host: str = DEFAULT_HOST,
             username: str = DEFAULT_USERNAME, expected_ssid: str = ""):
        """Saves configuration with owner-only (0600) permissions."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        if not host.startswith("http"):
            host = f"http://{host}"

        payload = {
            "host": host,
            "username": username,
            "password": password,
            "expected_ssid": expected_ssid,
        }

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        try:
            os.chmod(self.config_file, 0o600)
            os.chmod(self.config_file.parent, 0o700)
        except OSError:
            pass
