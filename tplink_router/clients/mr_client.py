"""TP-Link Archer MR Series (MR200, MR6400, MR600) 4G LTE Client."""

import logging
import re
import time
from typing import Dict, Any, List, Optional, Union

import requests
from tplink_router.core.auth import MultiProtocolAuth
from tplink_router.models.device import (
    DeviceInfo, RFMetrics, CellLockStatus, LTEStatus, IPv4Config, IPv6Config, RouterTelemetry
)
from tplink_router.models.sms import SMSMessage, USSDResult

logger = logging.getLogger(__name__)


def escape_act_val(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    return s.replace("&", "&amp;").replace("=", "&#61;").replace("\n", "&#10;").replace("\r", "&#13;")


def unescape_act_val(val: Optional[str]) -> str:
    if not val:
        return ""
    return val.replace("&#61;", "=").replace("&#10;", "\n").replace("&#13;", "\r").replace("&amp;", "&")


class ActItem:
    GET = 1
    SET = 2
    ADD = 3
    DEL = 4
    GL = 5
    GS = 6
    OP = 7
    CGI = 8

    def __init__(self, action_type: int, oid: str, stack: str = "0,0,0,0,0,0",
                 pstack: str = "0,0,0,0,0,0", attrs: Optional[List[str]] = None):
        self.type = action_type
        self.oid = oid
        self.stack = stack
        self.pstack = pstack
        self.attrs = attrs or []


class TPLinkMRClient:
    """Specialized client for TP-Link 4G/LTE gateway routers."""

    def __init__(self, host: str, password: str, username: str = "admin", timeout: int = 25):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.auth = MultiProtocolAuth(self.host, self.session)

    def login(self) -> bool:
        return self.auth.login(self.username, self.password)

    def logout(self):
        self.auth.logout()

    def req_act(self, acts: List[ActItem]) -> Dict[str, Any]:
        """Executes a batch of OID actions via the router's /cgi endpoint."""
        if not self.auth.is_authenticated:
            self.login()

        act_types = []
        act_data = []

        for i, act in enumerate(acts):
            act_types.append(str(act.type))
            act_data.append(
                f"[{act.oid}#{act.stack}#{act.pstack}]{i},{len(act.attrs)}\r\n"
                + "\r\n".join(act.attrs) + "\r\n"
            )

        data = "".join(act_data)
        url = f"{self.host}/cgi?" + "&".join(act_types)

        resp = self.session.post(url, data=data, timeout=self.timeout)
        if resp.status_code == 403 or "login.htm" in resp.text:
            self.login()
            resp = self.session.post(url, data=data, timeout=self.timeout)

        if resp.status_code != 200:
            raise ConnectionError(f"Router returned HTTP {resp.status_code}")

        return self._parse_oid_response(resp.text)

    @staticmethod
    def _parse_oid_response(text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        current_obj: Dict[str, str] = {}
        current_idx: Optional[str] = None

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            match = re.match(r"\[[^\]]+\](\d+)", line)
            if match:
                current_idx = match.group(1)
                current_obj = {}
                if current_idx in result:
                    if not isinstance(result[current_idx], list):
                        result[current_idx] = [result[current_idx]]
                    result[current_idx].append(current_obj)
                else:
                    result[current_idx] = current_obj
                continue

            if "=" in line and current_idx is not None:
                key, val = line.split("=", 1)
                current_obj[key.strip()] = unescape_act_val(val.strip())

        return result

    def get_device_info(self) -> DeviceInfo:
        acts = [
            ActItem(ActItem.GET, "IGD_DEV_INFO", attrs=["modelName", "description", "softwareVersion", "hardwareVersion"]),
        ]
        res = self.req_act(acts)
        dev = res.get("0", {}) if isinstance(res.get("0"), dict) else {}
        return DeviceInfo(
            model=dev.get("modelName", "Archer MR200"),
            description=dev.get("description", ""),
            firmware_version=dev.get("softwareVersion", ""),
            hardware_version=dev.get("hardwareVersion", "v5"),
        )

    def get_lte_status(self) -> LTEStatus:
        acts = [
            ActItem(ActItem.GET, "WAN_LTE_LINK_CFG", stack="2,1,0,0,0,0",
                    attrs=["enable", "connectStatus", "networkType", "simStatus", "signalStrength"]),
            ActItem(ActItem.GET, "WAN_LTE_INTF_CFG", stack="2,0,0,0,0,0",
                    attrs=["curRxSpeed", "curTxSpeed", "totalStatistics"]),
            ActItem(ActItem.GET, "LTE_WAN_CFG", stack="2,1,0,0,0,0", attrs=["profileName"]),
            ActItem(ActItem.GET, "LTE_BANDINFO", attrs=["band", "earfcn", "pci", "rsrp", "rsrq", "snr"]),
            ActItem(ActItem.GET, "LTE_NET_STATUS", attrs=[
                "smsUnreadCount", "sigLevel", "rfInfoRsrp", "rfInfoRsrq", "rfInfoSnr"
            ]),
            ActItem(ActItem.GET, "LTE_CELL_LOCK", attrs=["enable", "earfcn", "pci", "cid", "freq"]),
        ]
        res = self.req_act(acts)

        link_cfg = res.get("0", {}) if isinstance(res.get("0"), dict) else {}
        intf_cfg = res.get("1", {}) if isinstance(res.get("1"), dict) else {}
        wan_cfg = res.get("2", {}) if isinstance(res.get("2"), dict) else {}
        band_info = res.get("3", {}) if isinstance(res.get("3"), dict) else {}
        net_status = res.get("4", {}) if isinstance(res.get("4"), dict) else {}
        lock_info = res.get("5", {}) if isinstance(res.get("5"), dict) else {}

        rsrp = int(band_info.get("rsrp") or net_status.get("rfInfoRsrp") or 0)
        rsrq = int(band_info.get("rsrq") or net_status.get("rfInfoRsrq") or 0)
        snr = int(band_info.get("snr") or net_status.get("rfInfoSnr") or 0)
        bars = int(link_cfg.get("signalStrength") or net_status.get("sigLevel") or 0)

        earfcn = band_info.get("earfcn")
        pci = band_info.get("pci")
        band = band_info.get("band")

        if earfcn and not band:
            try:
                ef = int(earfcn)
                if 1200 <= ef <= 1949:
                    band = "Band 3 (1800 MHz)"
                elif 3450 <= ef <= 3799:
                    band = "Band 8 (900 MHz)"
                elif 0 <= ef <= 599:
                    band = "Band 1 (2100 MHz)"
                elif 38650 <= ef <= 39649:
                    band = "Band 40 (2300 MHz)"
            except ValueError:
                pass

        rx_speed = int(intf_cfg.get("curRxSpeed", 0))
        tx_speed = int(intf_cfg.get("curTxSpeed", 0))

        rf = RFMetrics(rsrp_dbm=rsrp, rsrq_db=rsrq, snr_db=snr, signal_bars=bars)
        cell_lock = CellLockStatus(
            enabled=lock_info.get("enable") == "1",
            earfcn=lock_info.get("earfcn", ""),
            pci=lock_info.get("pci", ""),
            cid=lock_info.get("cid", ""),
            freq=lock_info.get("freq", ""),
        )

        return LTEStatus(
            connected=link_cfg.get("connectStatus") == "1",
            sim_status="Ready" if link_cfg.get("simStatus") == "1" else "No SIM / Locked",
            isp_name=wan_cfg.get("profileName", "Hutch"),
            band=band or "Auto / LTE",
            earfcn=earfcn,
            pci=pci,
            rf=rf,
            rx_speed_kbps=round(rx_speed * 8 / 1024, 2) if rx_speed > 0 else 0.0,
            tx_speed_kbps=round(tx_speed * 8 / 1024, 2) if tx_speed > 0 else 0.0,
            total_bytes_transferred=int(float(intf_cfg.get("totalStatistics", 0))),
            unread_sms_count=int(net_status.get("smsUnreadCount", 0)),
            cell_lock=cell_lock,
        )

    def set_cell_lock(self, enable: bool, earfcn: Optional[Union[str, int]] = None,
                      pci: Optional[Union[str, int]] = None) -> bool:
        attrs = [f"enable={'1' if enable else '0'}"]
        if enable:
            if not earfcn or not pci:
                raise ValueError("Both EARFCN and PCI are required to lock a cell.")
            attrs.append(f"earfcn={earfcn}")
            attrs.append(f"pci={pci}")

        acts = [ActItem(ActItem.SET, "LTE_CELL_LOCK", attrs=attrs)]
        self.req_act(acts)
        return True

    def get_wan_config(self) -> Tuple[IPv4Config, IPv6Config]:
        acts = [
            ActItem(ActItem.GL, "WAN_IP_CONN", attrs=["connectionStatus", "externalIPAddress", "subnetMask", "defaultGateway", "DNSServers"]),
            ActItem(ActItem.GL, "WAN_IPv6_CONN", attrs=["enable", "connectionStatus", "IPv6Address", "DNSServers"]),
        ]
        res = self.req_act(acts)
        v4 = res.get("0", {}) if isinstance(res.get("0"), dict) else {}
        v6 = res.get("1", {}) if isinstance(res.get("1"), dict) else {}

        dns_servers = [d.strip() for d in v4.get("DNSServers", "").split(",") if d.strip()]
        dns_v6 = [d.strip() for d in v6.get("DNSServers", "").split(",") if d.strip()]

        ipv4 = IPv4Config(
            ip=v4.get("externalIPAddress", ""),
            subnet=v4.get("subnetMask", ""),
            gateway=v4.get("defaultGateway", ""),
            dns=dns_servers,
            status=v4.get("connectionStatus", "Connected"),
        )
        ipv6 = IPv6Config(
            enabled=v6.get("enable") == "1",
            ip=v6.get("IPv6Address", ""),
            dns=dns_v6,
            status=v6.get("connectionStatus", "Disconnected"),
        )
        return ipv4, ipv6

    def set_dns(self, primary_dns: str, secondary_dns: str = "8.8.8.8") -> bool:
        dns_str = f"{primary_dns},{secondary_dns}"
        acts = [
            ActItem(ActItem.SET, "WAN_IP_CONN", stack="1,1,1,0,0,0",
                    attrs=["DNSOverrideAllowed=1", f"DNSServers={dns_str}"]),
        ]
        self.req_act(acts)
        return True

    def toggle_ipv6(self, enable: bool) -> bool:
        acts = [
            ActItem(ActItem.SET, "WAN_IPv6_CONN", stack="1,1,1,0,0,0",
                    attrs=[f"enable={'1' if enable else '0'}"]),
        ]
        self.req_act(acts)
        return True

    def get_telemetry(self) -> RouterTelemetry:
        dev = self.get_device_info()
        lte = self.get_lte_status()
        v4, v6 = self.get_wan_config()
        return RouterTelemetry(device=dev, lte=lte, ipv4=v4, ipv6=v6)

    def get_sms(self, limit: int = 10, folder: str = "inbox") -> List[SMSMessage]:
        box_oid = "LTE_SMS_SENDMSGBOX" if folder == "sent" else "LTE_SMS_RECVMSGBOX"
        entry_oid = "LTE_SMS_SENDMSGENTRY" if folder == "sent" else "LTE_SMS_RECVMSGENTRY"

        acts = [
            ActItem(ActItem.SET, box_oid, attrs=["PageNumber=1"]),
            ActItem(ActItem.GL, entry_oid, attrs=["index", "from", "to", "content", "receivedTime", "unread"]),
        ]
        res = self.req_act(acts)
        entries = res.get("1", [])
        if isinstance(entries, dict):
            entries = [entries]

        messages = []
        for e in entries[:limit]:
            messages.append(SMSMessage(
                index=int(e.get("index", 0)),
                sender=e.get("from") or e.get("to") or "Unknown",
                content=e.get("content", ""),
                received_time=e.get("receivedTime", ""),
                unread=e.get("unread") == "1",
                folder=folder,
            ))
        return messages

    def send_sms(self, to_phone: str, message: str) -> bool:
        if "\n" in to_phone or "\r" in to_phone:
            raise ValueError("Phone number contains illegal newline")
        acts = [
            ActItem(ActItem.SET, "LTE_SMS_SENDNEWMSG", attrs=[
                "index=1",
                f"to={to_phone}",
                f"textContent={escape_act_val(message)}",
            ])
        ]
        self.req_act(acts)
        return True

    def send_ussd(self, code: str, max_wait_sec: int = 15) -> USSDResult:
        acts = [
            ActItem(ActItem.SET, "LTE_USSD", attrs=[
                "action=1",
                f"reqContent={escape_act_val(code)}",
            ])
        ]
        self.req_act(acts)

        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            time.sleep(1.2)
            res = self.req_act([
                ActItem(ActItem.GET, "LTE_USSD", attrs=["sessionStatus", "sendResult", "response", "ussdStatus"]),
            ])
            data = res.get("0", {}) if isinstance(res.get("0"), dict) else {}
            status = data.get("ussdStatus")
            if status == "1":
                return USSDResult(command=code, response=data.get("response", ""), success=True)
            elif status == "2":
                return USSDResult(command=code, response="", success=False, error_message="USSD failed on operator")

        raise TimeoutError("USSD command timed out")

    def reboot(self) -> bool:
        acts = [ActItem(ActItem.OP, "ACT_REBOOT")]
        self.req_act(acts)
        return True
