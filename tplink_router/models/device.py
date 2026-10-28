"""Data models for router hardware, telemetry, cellular RF, and network state."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class DeviceInfo:
    model: str = "Unknown TP-Link Router"
    hardware_version: str = "v1"
    firmware_version: str = "1.0.0"
    description: str = ""
    mac_address: str = ""
    imei: Optional[str] = None


@dataclass
class RFMetrics:
    rsrp_dbm: int = 0
    rsrq_db: int = 0
    snr_db: int = 0
    rssi_dbm: int = 0
    signal_bars: int = 0

    @property
    def rsrp_rating(self) -> str:
        if self.rsrp_dbm >= -85:
            return "Excellent"
        elif self.rsrp_dbm >= -95:
            return "Good"
        elif self.rsrp_dbm >= -105:
            return "Fair / Mid-Cell"
        return "Poor / Cell Edge"

    @property
    def rsrq_rating(self) -> str:
        if self.rsrq_db >= -9:
            return "Excellent"
        elif self.rsrq_db >= -12:
            return "Good"
        elif self.rsrq_db >= -15:
            return "Fair / Moderate Congestion"
        return "Poor / Heavy Congestion"

    @property
    def snr_rating(self) -> str:
        if self.snr_db >= 13:
            return "Excellent"
        elif self.snr_db >= 7:
            return "Good"
        elif self.snr_db >= 0:
            return "Fair"
        return "Poor / High Noise"


@dataclass
class CellLockStatus:
    enabled: bool = False
    earfcn: str = ""
    pci: str = ""
    cid: str = ""
    freq: str = ""


@dataclass
class LTEStatus:
    connected: bool = False
    sim_status: str = "Unknown"
    isp_name: str = "Auto"
    band: str = "Auto"
    earfcn: Optional[str] = None
    pci: Optional[str] = None
    rf: RFMetrics = field(default_factory=RFMetrics)
    rx_speed_kbps: float = 0.0
    tx_speed_kbps: float = 0.0
    total_bytes_transferred: int = 0
    unread_sms_count: int = 0
    cell_lock: CellLockStatus = field(default_factory=CellLockStatus)


@dataclass
class IPv4Config:
    ip: str = ""
    subnet: str = ""
    gateway: str = ""
    dns: List[str] = field(default_factory=list)
    status: str = "Connected"


@dataclass
class IPv6Config:
    enabled: bool = False
    ip: str = ""
    gateway: str = ""
    dns: List[str] = field(default_factory=list)
    status: str = "Disconnected"


@dataclass
class RouterTelemetry:
    device: DeviceInfo = field(default_factory=DeviceInfo)
    lte: Optional[LTEStatus] = None
    ipv4: IPv4Config = field(default_factory=IPv4Config)
    ipv6: IPv6Config = field(default_factory=IPv6Config)
    connected_clients_count: int = 0
