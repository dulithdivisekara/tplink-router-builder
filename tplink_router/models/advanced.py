"""Data models for advanced router features (Logs, Guest Wi-Fi, Port Forwarding, DMZ, UPnP, etc.)."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class SystemLogEntry:
    timestamp: str
    level_num: int
    level_name: str
    module: str
    message: str


@dataclass
class GuestWiFiNetwork:
    band: str  # "2.4GHz" or "5GHz"
    enabled: bool
    ssid: str
    security: str
    isolate_clients: bool = False
    allow_lan_access: bool = False


@dataclass
class GuestWiFiStatus:
    networks: List[GuestWiFiNetwork] = field(default_factory=list)
    allow_lan_access: bool = False


@dataclass
class PortForwardRule:
    index: int
    name: str
    external_port: str
    internal_port: str
    internal_ip: str
    protocol: str  # TCP, UDP, ALL
    enabled: bool = True


@dataclass
class DMZConfig:
    enabled: bool = False
    ip_address: str = ""


@dataclass
class UPnPPortMapping:
    protocol: str
    external_port: int
    internal_ip: str
    internal_port: int
    description: str = ""
    enabled: bool = True


@dataclass
class UPnPStatus:
    enabled: bool = True
    mappings: List[UPnPPortMapping] = field(default_factory=list)


@dataclass
class RebootScheduleConfig:
    enabled: bool = False
    mode: str = "daily"  # "daily", "weekly"
    hours: int = 3
    minutes: int = 0
    day_of_week: int = 1  # 1 = Mon, 7 = Sun
    day_name: str = "Monday"


@dataclass
class TimeConfig:
    current_time: str
    timezone: str
    daylight_savings: bool = False
    ntp_server1: str = ""
    ntp_server2: str = ""


@dataclass
class OperationMode:
    mode: str  # "3G/4G Router Mode" or "Wireless Router Mode"
    raw_mode: str  # "LTE" or "ETH"
    lte_backup_enabled: bool = True
    cellular_data_switch: bool = True


@dataclass
class DDNSStatus:
    provider: str  # "No-IP", "DynDNS", "TP-Link Cloud"
    enabled: bool
    domain: str
    username: str
    status: str  # "Connected", "Disconnected", "Authenticating", "Unknown"


@dataclass
class FirmwareUpdateInfo:
    current_version: str
    has_update: bool = False
    latest_version: str = ""
    release_date: str = ""
    release_log: str = ""
