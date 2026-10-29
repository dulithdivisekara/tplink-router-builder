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
from tplink_router.models.advanced import (
    SystemLogEntry, GuestWiFiNetwork, GuestWiFiStatus, PortForwardRule,
    DMZConfig, UPnPPortMapping, UPnPStatus, RebootScheduleConfig,
    TimeConfig, OperationMode, DDNSStatus, FirmwareUpdateInfo
)

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


def bands_to_masks(bands: Union[int, str, List[Union[int, str]]]) -> tuple[int, int]:
    """Converts LTE band numbers into TP-Link 32-bit low and high bitmasks."""
    if isinstance(bands, (int, str)):
        # Split on commas in case a multi-band string is passed, e.g. "3,8"
        bands_list = [b.strip() for b in str(bands).split(",") if b.strip()]
    else:
        bands_list = [str(b).strip() for b in bands if str(b).strip()]

    mask_l = 0
    mask_h = 0
    for b in bands_list:
        clean = b.lower().replace("band", "").replace("b", "").strip()
        if not clean or clean in ("auto", "0"):
            continue
        try:
            b_num = int(clean)
        except ValueError:
            continue
        if 1 <= b_num <= 32:
            mask_l |= (1 << (b_num - 1))
        elif 33 <= b_num <= 64:
            mask_h |= (1 << (b_num - 33))
    return mask_l, mask_h


def masks_to_bands(mask_l: int, mask_h: int) -> List[int]:
    """Decodes TP-Link 32-bit low and high bitmasks into a sorted list of band integers."""
    bands = []
    for i in range(32):
        if mask_l & (1 << i):
            bands.append(i + 1)
    for i in range(32):
        if mask_h & (1 << i):
            bands.append(i + 33)
    return sorted(bands)


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

    def __init__(self, host: str, password: str, username: str = "admin", timeout: int = 25,
                 session_cookie: Optional[str] = None):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.auth = MultiProtocolAuth(self.host, self.session, session_cookie=session_cookie)

    def login(self) -> bool:
        return self.auth.login(self.username, self.password)

    def logout(self):
        self.auth.logout()

    def req_act(self, acts: List[ActItem]) -> Dict[str, Any]:
        """Executes a batch of OID actions via modern GDPR encrypted or legacy /cgi endpoint."""
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

        data = "&".join(act_types) + "\r\n" + "".join(act_data)

        headers = {
            "Referer": f"{self.host}/",
            "Content-Type": "text/plain",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
        }
        if self.auth.token_id:
            headers["TokenID"] = self.auth.token_id

        # Use modern GDPR encryption if session AES key was negotiated
        if self.auth.aes_key:
            sig, enc_data = self.auth.encrypt_gdpr_data(data)
            post_body = f"sign={sig}\r\ndata={enc_data}\r\n"
            url = f"{self.host}/cgi_gdpr?_={int(time.time() * 1000)}"

            resp = self.session.post(url, data=post_body, headers=headers, timeout=self.timeout)
            if resp.status_code == 500 or resp.status_code == 403 or "login.htm" in resp.text:
                self.login()
                if self.auth.token_id:
                    headers["TokenID"] = self.auth.token_id
                sig, enc_data = self.auth.encrypt_gdpr_data(data)
                post_body = f"sign={sig}\r\ndata={enc_data}\r\n"
                url = f"{self.host}/cgi_gdpr?_={int(time.time() * 1000)}"
                resp = self.session.post(url, data=post_body, headers=headers, timeout=self.timeout)

            if resp.status_code != 200:
                raise ConnectionError(f"Router returned HTTP {resp.status_code}")

            decrypted_text = self.auth.decrypt_gdpr_data(resp.text)
            return self._parse_oid_response(decrypted_text)
        else:
            # Legacy unencrypted fallback
            url = f"{self.host}/cgi?" + "&".join(act_types)
            resp = self.session.post(url, data="".join(act_data), headers=headers, timeout=self.timeout)
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

            match = re.match(r"\[([^\]]+)\](\d+)", line)
            if match:
                tag = match.group(1)
                idx = match.group(2)
                if tag.lower() == "error":
                    result["error"] = idx
                    continue
                current_idx = idx
                stack = tag.split("#")[1] if "#" in tag else tag
                current_obj = {"__stack": stack}
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
            ActItem(ActItem.GET, "IGD_DEV_INFO", attrs=["modelName", "description", "softwareVersion", "hardwareVersion", "serialNumber"]),
        ]
        res = self.req_act(acts)
        raw_dev = res.get("0", {})
        if isinstance(raw_dev, list) and raw_dev:
            dev = raw_dev[0]
        elif isinstance(raw_dev, dict):
            dev = raw_dev
        else:
            dev = {}

        mac = ""
        sn = dev.get("serialNumber", "")
        if sn and len(sn) == 12 and all(c in "0123456789ABCDEFabcdef" for c in sn):
            mac = ":".join(sn[i:i+2] for i in range(0, 12, 2)).upper()

        return DeviceInfo(
            model=dev.get("modelName", "Archer MR200"),
            description=dev.get("description", ""),
            firmware_version=dev.get("softwareVersion", ""),
            hardware_version=dev.get("hardwareVersion", "v5"),
            mac_address=mac,
        )

    def get_lte_status(self) -> LTEStatus:
        acts = [
            ActItem(ActItem.GET, "WAN_LTE_LINK_CFG", stack="2,1,0,0,0,0",
                    attrs=["enable", "connectStatus", "networkType", "simStatus", "signalStrength"]),
            ActItem(ActItem.GET, "WAN_LTE_INTF_CFG", stack="2,0,0,0,0,0",
                    attrs=["curRxSpeed", "curTxSpeed", "totalStatistics"]),
            ActItem(ActItem.GET, "LTE_WAN_CFG", stack="2,1,0,0,0,0", attrs=["profileName"]),
            ActItem(ActItem.GET, "LTE_NET_STATUS", stack="2,1,0,0,0,0"),
        ]
        res = self.req_act(acts)

        raw_link = res.get("0", {})
        link_cfg = raw_link[0] if isinstance(raw_link, list) and raw_link else (raw_link if isinstance(raw_link, dict) else {})
        raw_intf = res.get("1", {})
        intf_cfg = raw_intf[0] if isinstance(raw_intf, list) and raw_intf else (raw_intf if isinstance(raw_intf, dict) else {})
        raw_wan = res.get("2", {})
        wan_cfg = raw_wan[0] if isinstance(raw_wan, list) and raw_wan else (raw_wan if isinstance(raw_wan, dict) else {})
        raw_net = res.get("3", {})
        net_status = raw_net[0] if isinstance(raw_net, list) and raw_net else (raw_net if isinstance(raw_net, dict) else {})

        # Optional band_info for older firmware models
        band_info = {}
        try:
            b_res = self.req_act([ActItem(ActItem.GET, "LTE_BANDINFO", stack="2,1,0,0,0,0", attrs=["band", "earfcn", "pci", "rsrp", "rsrq", "snr"])])
            b_raw = b_res.get("0", {})
            if isinstance(b_raw, list) and b_raw:
                band_info = b_raw[0]
            elif isinstance(b_raw, dict):
                band_info = b_raw
        except Exception:
            pass

        # Query cell lock independently to avoid stack batching collisions
        lock_info = {}
        try:
            lock_res = self.req_act([ActItem(ActItem.GET, "LTE_CELL_LOCK")])
            lock_raw = lock_res.get("0", {})
            if isinstance(lock_raw, list) and lock_raw:
                lock_info = lock_raw[0]
            elif isinstance(lock_raw, dict):
                lock_info = lock_raw
        except Exception:
            pass

        rsrp = int(band_info.get("rsrp") or net_status.get("rfInfoRsrp") or 0)
        rsrq = int(band_info.get("rsrq") or net_status.get("rfInfoRsrq") or 0)
        snr = int(band_info.get("snr") or net_status.get("rfInfoSnr") or 0)
        rssi = int(net_status.get("rfInfoRssi") or 0)
        bars = int(link_cfg.get("signalStrength") or net_status.get("sigLevel") or 0)

        earfcn = band_info.get("earfcn") or net_status.get("rfInfoChannel")
        pci = band_info.get("pci") or net_status.get("rfInfoPCellChannel")
        band = band_info.get("band")

        if earfcn and not band:
            try:
                ef = int(earfcn)
                if 1200 <= ef <= 1949 or 9612 <= ef <= 9888:
                    band = "Band 3 (1800 MHz)"
                elif 3450 <= ef <= 3799 or 2937 <= ef <= 3088 or 10562 <= ef <= 10838:
                    band = "Band 8 (900 MHz)"
                elif 0 <= ef <= 599 or 10050 <= ef <= 10125:
                    band = "Band 1 (2100 MHz)"
                elif 38650 <= ef <= 39649:
                    band = "Band 40 (2300 MHz)"
            except ValueError:
                pass

        rx_speed = int(intf_cfg.get("curRxSpeed", 0))
        tx_speed = int(intf_cfg.get("curTxSpeed", 0))

        rf = RFMetrics(rsrp_dbm=rsrp, rsrq_db=rsrq, snr_db=snr, rssi_dbm=rssi, signal_bars=bars)
        is_locked = (
            lock_info.get("rfInfoCellIDLock") == "1"
            or lock_info.get("enable") == "1"
        )
        cell_lock = CellLockStatus(
            enabled=is_locked,
            earfcn=lock_info.get("rfInfoEARFCN") or lock_info.get("earfcn", ""),
            pci=lock_info.get("rfInfoPCI") or lock_info.get("pci", ""),
            cid=lock_info.get("rfInfoCellID") or lock_info.get("cid", ""),
            freq=lock_info.get("rfInfoFreq") or lock_info.get("freq", ""),
        )

        return LTEStatus(
            connected=link_cfg.get("connectStatus") in ("1", "4"),
            sim_status="Ready" if link_cfg.get("simStatus") in ("1", "3") else "No SIM / Locked",
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

    def get_cell_lock(self) -> CellLockStatus:
        """Returns the current LTE Cell Lock status."""
        return self.get_lte_status().cell_lock

    def set_cell_lock(self, enable: bool, earfcn: Optional[Union[str, int]] = None,
                      pci: Optional[Union[str, int]] = None) -> bool:
        lock_val = "1" if enable else "0"
        attrs = [f"rfInfoCellIDLock={lock_val}", f"enable={lock_val}"]
        if enable:
            if not earfcn or not pci:
                raise ValueError("Both EARFCN and PCI are required to lock a cell.")
            attrs.extend([
                f"rfInfoEARFCN={earfcn}", f"earfcn={earfcn}",
                f"rfInfoPCI={pci}", f"pci={pci}"
            ])

        acts = [ActItem(ActItem.SET, "LTE_CELL_LOCK", attrs=attrs)]
        self.req_act(acts)
        return True

    def get_wan_config(self) -> Tuple[IPv4Config, IPv6Config]:
        acts = [
            ActItem(ActItem.GL, "WAN_IP_CONN", attrs=[
                "connectionStatus", "name", "enable", "externalIPAddress", "subnetMask",
                "defaultGateway", "DNSServers", "MACAddress",
                "X_TP_IPv6Enabled", "X_TP_IPv6ConnStatus", "X_TP_ExternalIPv6Address",
                "X_TP_DefaultIPv6Gateway", "X_TP_IPv6DNSServers"
            ]),
        ]
        res = self.req_act(acts)
        raw_v4 = res.get("0", [])
        if isinstance(raw_v4, dict):
            raw_v4 = [raw_v4]

        v4 = {}
        for entry in raw_v4:
            if not isinstance(entry, dict):
                continue
            if entry.get("name") == "LTE" or entry.get("connectionStatus") == "Connected" or entry.get("enable") == "1":
                v4 = entry
                if entry.get("connectionStatus") == "Connected":
                    break

        v6_enabled = v4.get("X_TP_IPv6Enabled") == "1"
        v6_ip = v4.get("X_TP_ExternalIPv6Address", "")
        if v6_ip == "::":
            v6_ip = ""
        v6_gw = v4.get("X_TP_DefaultIPv6Gateway", "")
        if v6_gw == "::":
            v6_gw = ""
        v6_status = v4.get("X_TP_IPv6ConnStatus", "Disconnected")

        raw_dns_v6 = v4.get("X_TP_IPv6DNSServers", "")
        dns_v6 = [d.strip() for d in raw_dns_v6.split(",") if d.strip() and d.strip() != "::"]

        if not v6_enabled and not v6_ip:
            try:
                res_v6 = self.req_act([ActItem(ActItem.GL, "WAN_IPv6_CONN", attrs=["enable", "connectionStatus", "name", "IPv6Address", "DNSServers"])])
                raw_v6 = res_v6.get("0", [])
                if isinstance(raw_v6, dict):
                    raw_v6 = [raw_v6]
                for entry in raw_v6:
                    if isinstance(entry, dict) and (entry.get("enable") == "1" or entry.get("connectionStatus") == "Connected"):
                        v6_enabled = entry.get("enable") == "1"
                        v6_ip = entry.get("IPv6Address", "")
                        v6_status = entry.get("connectionStatus", "Disconnected")
                        dns_v6 = [d.strip() for d in entry.get("DNSServers", "").split(",") if d.strip() and d.strip() != "::"]
                        break
            except Exception:
                pass

        dns_servers = [d.strip() for d in v4.get("DNSServers", "").split(",") if d.strip() and d.strip() != "0.0.0.0"]

        ipv4 = IPv4Config(
            ip=v4.get("externalIPAddress", ""),
            subnet=v4.get("subnetMask", ""),
            gateway=v4.get("defaultGateway", ""),
            dns=dns_servers,
            status=v4.get("connectionStatus", "Connected" if v4.get("externalIPAddress") else "Disconnected"),
        )
        ipv6 = IPv6Config(
            enabled=v6_enabled,
            ip=v6_ip,
            gateway=v6_gw,
            dns=dns_v6,
            status=v6_status,
        )
        return ipv4, ipv6

    def set_dns(self, primary_dns: str, secondary_dns: str = "8.8.8.8") -> bool:
        dns_str = f"{primary_dns},{secondary_dns}"
        for stack in ["2,1,1,0,0,0", "1,1,1,0,0,0"]:
            try:
                self.req_act([
                    ActItem(ActItem.SET, "WAN_IP_CONN", stack=stack,
                            attrs=["DNSOverrideAllowed=1", f"DNSServers={dns_str}"]),
                ])
            except Exception:
                pass
        return True

    def toggle_ipv6(self, enable: bool) -> bool:
        flag = "1" if enable else "0"
        for stack in ["2,1,1,0,0,0", "1,1,1,0,0,0"]:
            try:
                self.req_act([
                    ActItem(ActItem.SET, "WAN_IP_CONN", stack=stack,
                            attrs=[f"X_TP_IPv6Enabled={flag}"]),
                ])
            except Exception:
                pass
        try:
            self.req_act([
                ActItem(ActItem.SET, "WAN_IPv6_CONN", stack="1,1,1,0,0,0",
                        attrs=[f"enable={flag}"]),
            ])
        except Exception:
            pass
        return True

    def get_telemetry(self) -> RouterTelemetry:
        dev = self.get_device_info()
        lte = self.get_lte_status()
        v4, v6 = self.get_wan_config()
        clients = []
        try:
            clients = self.get_connected_clients()
        except Exception:
            pass
        return RouterTelemetry(
            device=dev,
            lte=lte,
            ipv4=v4,
            ipv6=v6,
            connected_clients_count=len(clients)
        )

    def get_sms(self, limit: int = 10, folder: str = "inbox") -> List[SMSMessage]:
        box_oid = "LTE_SMS_SENDMSGBOX" if folder == "sent" else "LTE_SMS_RECVMSGBOX"
        entry_oid = "LTE_SMS_SENDMSGENTRY" if folder == "sent" else "LTE_SMS_RECVMSGENTRY"

        # 1. Optionally select page 1 on the target message box
        try:
            self.req_act([ActItem(ActItem.SET, box_oid, attrs=["PageNumber=1"])])
        except Exception:
            pass

        # 2. Query entries via standalone GL (Get List) request
        # Note: SET and GL cannot be batched together in TP-Link CGI or it returns error 9003
        if folder == "sent":
            attrs = ["index", "to", "content", "sendTime"]
        else:
            attrs = ["index", "from", "content", "receivedTime", "unread"]

        res = self.req_act([ActItem(ActItem.GL, entry_oid, attrs=attrs)])
        entries = res.get("0", [])
        if isinstance(entries, dict):
            entries = [entries]

        messages = []
        for e in entries:
            if not isinstance(e, dict) or not e.get("index"):
                continue
            time_val = e.get("receivedTime") or e.get("sendTime") or ""
            phone_val = e.get("from") or e.get("to") or "Unknown"
            messages.append(SMSMessage(
                index=int(e.get("index", 0)),
                sender=phone_val,
                content=unescape_act_val(e.get("content", "")),
                received_time=time_val,
                unread=e.get("unread") == "1",
                folder=folder,
            ))
            if len(messages) >= limit:
                break
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

    def get_connected_clients(self) -> List[Dict[str, Any]]:
        """Queries all active wired and wireless clients on the LAN."""
        acts = [
            ActItem(ActItem.GL, "LAN_HOST_ENTRY", attrs=["hostName", "IPAddress", "MACAddress", "leaseTimeRemaining", "addressSource"]),
        ]
        res = self.req_act(acts)
        entries = res.get("0", [])
        if isinstance(entries, dict):
            entries = [entries]

        clients = []
        for e in entries:
            if not isinstance(e, dict) or (not e.get("MACAddress") and not e.get("IPAddress")):
                continue
            lease_sec = int(e.get("leaseTimeRemaining", 0))
            if lease_sec == -1:
                lease_str = "Permanent"
            else:
                h = lease_sec // 3600
                m = (lease_sec % 3600) // 60
                s = lease_sec % 60
                lease_str = f"{h:02d}:{m:02d}:{s:02d}"

            clients.append({
                "hostname": e.get("hostName") or "Unknown",
                "ip": e.get("IPAddress", ""),
                "mac": (e.get("MACAddress") or "").replace(":", "-").upper(),
                "lease_remaining": lease_str,
                "source": e.get("addressSource", "DHCP"),
            })
        return clients

    def get_dhcp_reservations(self) -> List[Dict[str, Any]]:
        """Returns static IP address reservations."""
        acts = [
            ActItem(ActItem.GL, "LAN_DHCP_STATIC_ADDR", attrs=["enable", "chaddr", "yiaddr"]),
        ]
        res = self.req_act(acts)
        entries = res.get("0", [])
        if isinstance(entries, dict):
            entries = [entries]

        reservations = []
        for e in entries:
            if not isinstance(e, dict) or not e.get("chaddr"):
                continue
            reservations.append({
                "stack": e.get("__stack", "0,0,0,0,0,0"),
                "mac": (e.get("chaddr") or "").upper(),
                "ip": e.get("yiaddr", ""),
                "enabled": e.get("enable") == "1",
            })
        return reservations

    def add_dhcp_reservation(self, mac: str, ip: str, enable: bool = True) -> bool:
        """Adds a static DHCP reservation."""
        clean_mac = mac.replace("-", ":").lower()
        acts = [
            ActItem(ActItem.ADD, "LAN_DHCP_STATIC_ADDR", attrs=[
                f"enable={'1' if enable else '0'}",
                f"chaddr={clean_mac}",
                f"yiaddr={ip}",
            ])
        ]
        self.req_act(acts)
        return True

    def delete_dhcp_reservation(self, mac: str) -> bool:
        """Deletes a static DHCP reservation matching the given MAC."""
        reservations = self.get_dhcp_reservations()
        clean_target = mac.replace(":", "-").upper()
        target_stack = None
        for r in reservations:
            if r["mac"].replace(":", "-").upper() == clean_target:
                target_stack = r["stack"]
                break
        if not target_stack:
            raise ValueError(f"No reservation found for MAC {mac}")

        acts = [ActItem(ActItem.DEL, "LAN_DHCP_STATIC_ADDR", stack=target_stack)]
        self.req_act(acts)
        return True

    def get_data_limit(self) -> Dict[str, Any]:
        """Returns cellular data quota, monthly cycle, and bandwidth counters."""
        acts = [
            ActItem(ActItem.GET, "WAN_LTE_INTF_CFG", stack="2,0,0,0,0,0", attrs=[
                "enableDataLimit", "limitation", "warningPercent", "enablePaymentDay",
                "paymentDay", "curStatistics", "totalStatistics", "curRxSpeed", "curTxSpeed"
            ])
        ]
        res = self.req_act(acts)
        data = res.get("0", {}) if isinstance(res.get("0"), dict) else {}
        return {
            "limit_enabled": data.get("enableDataLimit") == "1",
            "limit_mb": int(data.get("limitation", 0)),
            "warning_percent": int(data.get("warningPercent", 90)),
            "billing_day_enabled": data.get("enablePaymentDay") == "1",
            "billing_day": int(data.get("paymentDay", 1)),
            "current_period_bytes": int(float(data.get("curStatistics", 0))),
            "total_bytes": int(float(data.get("totalStatistics", 0))),
            "rx_speed_kbps": round(int(data.get("curRxSpeed", 0)) * 8 / 1024, 2),
            "tx_speed_kbps": round(int(data.get("curTxSpeed", 0)) * 8 / 1024, 2),
        }

    def set_data_limit(self, enabled: bool, limit_mb: int, warning_percent: int = 90, payment_day: int = 1) -> bool:
        """Sets monthly cellular data cap and billing cycle reset date."""
        attrs = [
            f"enableDataLimit={'1' if enabled else '0'}",
            f"limitation={limit_mb}",
            f"warningPercent={warning_percent}",
            "enablePaymentDay=1",
            f"paymentDay={payment_day}",
        ]
        acts = [ActItem(ActItem.SET, "WAN_LTE_INTF_CFG", stack="2,0,0,0,0,0", attrs=attrs)]
        self.req_act(acts)
        return True

    def get_wifi_status(self) -> List[Dict[str, Any]]:
        """Queries Wi-Fi radios (2.4 GHz and 5 GHz)."""
        acts = [
            ActItem(ActItem.GL, "LAN_WLAN", attrs=[
                "name", "standard", "SSID", "X_TP_Band", "channel", "enable",
                "SSIDAdvertisementEnabled", "totalAssociations", "status"
            ]),
        ]
        res = self.req_act(acts)
        entries = res.get("0", [])
        if isinstance(entries, dict):
            entries = [entries]

        networks = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            ssid = e.get("SSID") or ""
            band = e.get("X_TP_Band") or ""
            name = e.get("name") or e.get("Name") or ""
            # Filter out trailing empty sentinel
            if not ssid and not band and not name:
                continue

            is_enabled = (
                e.get("enable") == "1" or
                e.get("Enable") == "1" or
                str(e.get("status", "")).lower() == "up"
            )

            assoc = e.get("totalAssociations", "0")
            try:
                assoc_count = int(assoc)
            except ValueError:
                assoc_count = 0

            networks.append({
                "name": name,
                "band": band or ("5GHz" if "5" in name else "2.4GHz"),
                "ssid": ssid,
                "channel": e.get("channel") or e.get("Channel") or "Auto",
                "standard": e.get("standard") or e.get("Standard") or "",
                "enabled": is_enabled,
                "broadcast_ssid": e.get("SSIDAdvertisementEnabled") == "1",
                "connected_clients": assoc_count,
            })
        return networks

    def set_wifi_radio(self, band: str, enabled: bool, ssid: Optional[str] = None) -> bool:
        """Toggles Wi-Fi radio (2.4GHz or 5GHz) and optionally renames SSID."""
        target_stack = "1,1,0,0,0,0" if "2" in band else "1,2,0,0,0,0"
        flag = "1" if enabled else "0"
        attrs = [f"enable={flag}", f"Enable={flag}"]
        if ssid:
            attrs.extend([f"SSID={ssid}", f"ssid={ssid}"])
        acts = [ActItem(ActItem.SET, "LAN_WLAN", stack=target_stack, attrs=attrs)]
        self.req_act(acts)
        return True

    def get_led_status(self) -> Dict[str, Any]:
        """Queries physical LEDs and night mode schedule."""
        acts = [
            ActItem(ActItem.GET, "LED_BUTTON"),
            ActItem(ActItem.GET, "LED_SCHEDULE_CFG"),
        ]
        res = self.req_act(acts)
        btn = res.get("0", {}) if isinstance(res.get("0"), dict) else {}
        sched = res.get("1", {}) if isinstance(res.get("1"), dict) else {}

        start_min = int(sched.get("startTime", 0))
        end_min = int(sched.get("endTime", 0))

        return {
            "leds_on": btn.get("enable") == "1",
            "night_mode_enabled": sched.get("enable") == "1",
            "night_mode_start": f"{start_min // 60:02d}:{start_min % 60:02d}",
            "night_mode_end": f"{end_min // 60:02d}:{end_min % 60:02d}",
        }

    def set_led_night_mode(self, enabled: bool, start_time: str = "22:00", end_time: str = "07:00") -> bool:
        """Configures night mode schedule to turn off front panel router LEDs."""
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em

        attrs = [
            f"enable={'1' if enabled else '0'}",
            f"startTime={start_min}",
            f"endTime={end_min}",
        ]
        acts = [ActItem(ActItem.SET, "LED_SCHEDULE_CFG", attrs=attrs)]
        self.req_act(acts)
        return True

    def run_wan_diagnostic(self, max_wait_sec: int = 12) -> Dict[str, Any]:
        """Runs the router-side WAN and NCSI internet reachability diagnostic self-test."""
        acts = [ActItem(ActItem.OP, "ACT_OP_DIAG_STARTDIAG")]
        self.req_act(acts)

        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            time.sleep(1.5)
            res = self.req_act([ActItem(ActItem.GET, "DIAG_TOOL", attrs=["lastResult", "LastResult"])])
            raw_data = res.get("0", {})
            if isinstance(raw_data, list) and raw_data:
                data = raw_data[0]
            elif isinstance(raw_data, dict):
                data = raw_data
            else:
                data = {}

            last_res = data.get("lastResult") or data.get("LastResult")
            if last_res == "1":
                return {"status": "Passed", "result_code": 1, "message": "Physical link, WAN IP, and Internet NCSI reachable."}
            elif last_res in ("2", "4"):
                return {"status": "Failed", "result_code": int(last_res), "message": "WAN or DNS resolution failed."}

        return {"status": "Running", "result_code": 3, "message": "Diagnostic still in progress."}

    def _resolve_lte_wan_stack(self) -> str:
        """Resolves the active LTE WAN configuration stack (e.g. 2,1,0,0,0,0)."""
        try:
            res = self.req_act([
                ActItem(ActItem.GL, "WAN_COMMON_INTF_CFG"),
                ActItem(ActItem.GL, "LTE_WAN_CFG"),
            ])
            raw_wans = res.get("0", [])
            if isinstance(raw_wans, dict):
                raw_wans = [raw_wans]

            lte_prefix = "2"
            for w in raw_wans:
                if w.get("WANAccessType") == "LTE":
                    stk = w.get("__stack", "")
                    if stk:
                        lte_prefix = stk.split(",")[0]
                    break

            raw_cfgs = res.get("1", [])
            if isinstance(raw_cfgs, dict):
                raw_cfgs = [raw_cfgs]
            for c in raw_cfgs:
                stk = c.get("__stack", "")
                if stk and stk.startswith(f"{lte_prefix},"):
                    return stk
        except Exception as e:
            logger.debug(f"Failed to auto-detect LTE WAN stack: {e}")
        return "2,1,0,0,0,0"

    def get_band_config(self) -> Dict[str, Any]:
        """Returns the active LTE band configuration, manual/auto mode, and supported bands."""
        wan_stack = self._resolve_lte_wan_stack()
        acts = [
            ActItem(ActItem.GET, "LTE_WAN_CFG", stack=wan_stack, attrs=[
                "bandSelectSwitch", "bandSelectedMaskL", "bandSelectedMaskH",
                "bandSupportMaskL", "bandSupportMaskH"
            ])
        ]
        res = self.req_act(acts)
        raw = res.get("0", {})
        if isinstance(raw, list) and raw:
            cfg = raw[0]
        elif isinstance(raw, dict):
            cfg = raw
        else:
            cfg = {}

        switch = cfg.get("bandSelectSwitch", "0")
        is_manual = str(switch) == "1"
        try:
            mask_l = int(cfg.get("bandSelectedMaskL", 0))
            mask_h = int(cfg.get("bandSelectedMaskH", 0))
        except (ValueError, TypeError):
            mask_l, mask_h = 0, 0

        try:
            supp_l = int(cfg.get("bandSupportMaskL", 0))
            supp_h = int(cfg.get("bandSupportMaskH", 0))
        except (ValueError, TypeError):
            supp_l, supp_h = 0, 0

        configured = masks_to_bands(mask_l, mask_h) if is_manual else []
        supported = masks_to_bands(supp_l, supp_h)

        lte_status = self.get_lte_status()

        return {
            "mode": "manual" if is_manual else "auto",
            "configured_bands": configured,
            "configured_str": f"Manual ({', '.join('B' + str(b) for b in configured)})" if is_manual and configured else "Auto",
            "supported_bands": supported or [1, 3, 7, 8, 20, 38, 40, 41],
            "connected_band": lte_status.band,
            "earfcn": lte_status.earfcn,
            "pci": lte_status.pci,
            "signal_bars": lte_status.rf.signal_bars,
            "rsrp": lte_status.rf.rsrp_dbm,
            "rsrq": lte_status.rf.rsrq_db,
            "snr": lte_status.rf.snr_db,
        }

    def set_lte_band(self, band: str) -> bool:
        """Manually locks router to specific LTE band (e.g. '3', '8', '40', or 'auto').
        
        Controls true hardware modem carrier selection via LTE_WAN_CFG bitmasks (stack 2,1,0,0,0,0),
        matching the official Archer MR Web UI mechanism and triggering RF modem retuning.
        """
        band_str = str(band).lower().replace("band", "").strip()
        is_auto = band_str in ("auto", "0", "")

        if is_auto:
            switch = 0
            mask_l = 0
            mask_h = 0
        else:
            switch = 1
            mask_l, mask_h = bands_to_masks(band_str)
            if mask_l == 0 and mask_h == 0:
                raise ValueError(f"Invalid or unsupported LTE Band: {band}")

        wan_stack = self._resolve_lte_wan_stack()

        # Primary Archer MR OID: LTE_WAN_CFG on resolved stack (wanCfgStk)
        acts = [
            ActItem(
                ActItem.SET,
                "LTE_WAN_CFG",
                stack=wan_stack,
                attrs=[
                    f"bandSelectSwitch={switch}",
                    f"bandSelectedMaskL={mask_l}",
                    f"bandSelectedMaskH={mask_h}",
                ],
            )
        ]
        self.req_act(acts)

        # Secondary fallback: LTE_BAND_SEL for legacy MR models (swallow 9005 error if rejected)
        try:
            legacy_attrs = [
                f"bandPrefMaskL={mask_l}",
                f"bandPrefMaskH={mask_h}",
                f"enable={1 if switch == 1 else 0}",
                f"selectedBand={int(band_str) if not is_auto and band_str.isdigit() else 0}",
            ]
            self.req_act([ActItem(ActItem.SET, "LTE_BAND_SEL", attrs=legacy_attrs)])
        except Exception:
            pass

        return True

    def get_system_logs(self, limit: int = 50, module: Optional[str] = None,
                        min_level: Optional[str] = None) -> List[SystemLogEntry]:
        """Fetches and parses decrypted kernel/system event logs."""
        if not self.auth.is_authenticated:
            self.login()
        headers = {
            "Referer": f"{self.host}/mainFrame.htm",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if self.auth.token_id:
            headers["TokenID"] = self.auth.token_id

        resp = self.session.get(f"{self.host}/cgi/log", headers=headers, timeout=self.timeout)
        if resp.status_code != 200:
            raise ConnectionError(f"Router returned HTTP {resp.status_code} fetching logs")

        decrypted = self.auth.decrypt_gdpr_data(resp.text) if self.auth.aes_key else resp.text

        level_map = {
            0: "EMERG", 1: "ALERT", 2: "CRIT", 3: "ERROR",
            4: "WARN", 5: "NOTICE", 6: "INFO", 7: "DEBUG"
        }
        name_to_level = {v.upper(): k for k, v in level_map.items()}
        max_level_num = name_to_level.get(min_level.upper(), 7) if min_level else 7

        entries: List[SystemLogEntry] = []
        pattern = re.compile(r"^([\d-]+\s+[\d:]+)\s+\[(\d)\]\s+([\w\s]+?):\s+(.*)$")

        for line in decrypted.splitlines():
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if not match:
                continue
            ts, lvl_str, mod, msg = match.groups()
            lvl = int(lvl_str)
            if lvl > max_level_num:
                continue
            if module and mod.upper() != module.upper():
                continue
            entries.append(SystemLogEntry(
                timestamp=ts,
                level_num=lvl,
                level_name=level_map.get(lvl, f"LVL{lvl}"),
                module=mod,
                message=msg
            ))

        return entries[-limit:]

    def clear_system_logs(self) -> bool:
        """Clears all buffered router system event logs."""
        if not self.auth.is_authenticated:
            self.login()
        headers = {
            "Referer": f"{self.host}/mainFrame.htm",
        }
        if self.auth.token_id:
            headers["TokenID"] = self.auth.token_id
        resp = self.session.get(f"{self.host}/cgi/log?clr", headers=headers, timeout=self.timeout)
        return resp.status_code == 200

    def get_guest_wifi(self) -> GuestWiFiStatus:
        """Returns the dual-band Guest Wi-Fi configuration (2.4GHz & 5GHz)."""
        res_mssid = self.req_act([ActItem(ActItem.GL, "LAN_WLAN_MSSIDENTRY")])
        res_guest = self.req_act([ActItem(ActItem.GL, "LAN_WLAN_GUESTNET")])

        raw_guests = res_guest.get("0", [])
        if isinstance(raw_guests, dict):
            raw_guests = [raw_guests]

        allow_lan = False
        if raw_guests and raw_guests[0].get("LANAccessEnable") == "1":
            allow_lan = True

        raw_mssids = res_mssid.get("0", [])
        if isinstance(raw_mssids, dict):
            raw_mssids = [raw_mssids]

        networks: List[GuestWiFiNetwork] = []
        for m in raw_mssids:
            stk = m.get("__stack", "")
            if stk == "1,1,1,0,0,0":
                networks.append(GuestWiFiNetwork(
                    band="2.4GHz",
                    enabled=m.get("enable") == "1",
                    ssid=m.get("SSID", "TP-Link_Guest"),
                    security="WPA/WPA2-PSK" if m.get("beaconType") == "11i" else "Open",
                    isolate_clients=m.get("isolateClients") == "1",
                    allow_lan_access=allow_lan
                ))
            elif stk == "1,2,1,0,0,0":
                networks.append(GuestWiFiNetwork(
                    band="5GHz",
                    enabled=m.get("enable") == "1",
                    ssid=m.get("SSID", "TP-Link_Guest_5G"),
                    security="WPA/WPA2-PSK" if m.get("beaconType") == "11i" else "Open",
                    isolate_clients=m.get("isolateClients") == "1",
                    allow_lan_access=allow_lan
                ))

        return GuestWiFiStatus(networks=networks, allow_lan_access=allow_lan)

    def set_guest_wifi(self, band: str = "both", enabled: bool = True,
                       ssid: Optional[str] = None, password: Optional[str] = None,
                       allow_lan: Optional[bool] = None) -> bool:
        """Configures 2.4GHz and/or 5GHz Guest Wi-Fi networks."""
        targets = []
        b_clean = band.lower()
        if "2" in b_clean or "both" in b_clean:
            targets.append(("1,1,0,0,0,0", "1,1,1,0,0,0", "2.4GHz"))
        if "5" in b_clean or "both" in b_clean:
            targets.append(("1,2,0,0,0,0", "1,2,1,0,0,0", "5GHz"))

        acts = []
        for g_stk, m_stk, b_name in targets:
            g_attrs = [f"enable={'1' if enabled else '0'}"]
            if allow_lan is not None:
                g_attrs.append(f"LANAccessEnable={'1' if allow_lan else '0'}")
            acts.append(ActItem(ActItem.SET, "LAN_WLAN_GUESTNET", stack=g_stk, attrs=g_attrs))

            m_attrs = [f"enable={'1' if enabled else '0'}"]
            if ssid:
                band_suffix = "_5G" if b_name == "5GHz" and not ssid.endswith("_5G") and band == "both" else ""
                m_attrs.append(f"SSID={escape_act_val(ssid + band_suffix)}")
            if password is not None:
                if password and len(password) >= 8:
                    m_attrs.extend([
                        "beaconType=11i",
                        "WPAAuthenticationMode=PSKAuthentication",
                        "IEEE11iAuthenticationMode=PSKAuthentication",
                        f"preSharedKey={escape_act_val(password)}",
                        "WPAEncryptionModes=TKIPandAESEncryption",
                        "IEEE11iEncryptionModes=TKIPandAESEncryption"
                    ])
                else:
                    m_attrs.extend(["beaconType=Basic", "basicEncryptionModes=None", "preSharedKey="])
            acts.append(ActItem(ActItem.SET, "LAN_WLAN_MSSIDENTRY", stack=m_stk, attrs=m_attrs))

        self.req_act(acts)
        return True

    def get_port_forwarding(self) -> List[PortForwardRule]:
        """Lists active NAT virtual server port forwarding rules."""
        wan_stack = "2,1,1,0,0,0"
        try:
            res_wan = self.req_act([ActItem(ActItem.GL, "WAN_IP_CONN")])
            raw_wans = res_wan.get("0", [])
            if isinstance(raw_wans, dict):
                raw_wans = [raw_wans]
            for w in raw_wans:
                if w.get("enable") == "1" and w.get("__stack"):
                    wan_stack = w["__stack"]
                    break
        except Exception:
            pass

        try:
            res = self.req_act([ActItem(ActItem.GL, "WAN_IP_CONN_PORTMAPPING", pstack=wan_stack)])
            raw_rules = res.get("0", [])
            if isinstance(raw_rules, dict):
                raw_rules = [raw_rules]
            rules: List[PortForwardRule] = []
            for idx, r in enumerate(raw_rules):
                if not r.get("__stack"):
                    continue
                rules.append(PortForwardRule(
                    index=idx + 1,
                    name=r.get("PortMappingDescription") or r.get("name") or f"rule_{idx+1}",
                    external_port=str(r.get("externalPort") or ""),
                    internal_port=str(r.get("internalPort") or ""),
                    internal_ip=r.get("internalClient") or "",
                    protocol=r.get("portMappingProtocol") or "ALL",
                    enabled=r.get("portMappingEnabled") == "1",
                ))
            return rules
        except Exception as e:
            logger.debug(f"Failed to query port forwarding: {e}")
            return []

    def add_port_forwarding(self, name: str, external_port: Union[int, str], internal_ip: str,
                            internal_port: Optional[Union[int, str]] = None,
                            protocol: str = "ALL") -> bool:
        """Adds a new NAT virtual server port forwarding rule."""
        wan_stack = "2,1,1,0,0,0"
        int_port = internal_port or external_port
        proto = protocol.upper()
        if proto not in ("TCP", "UDP", "ALL"):
            proto = "ALL"

        attrs = [
            f"PortMappingDescription={escape_act_val(name)}",
            f"externalPort={external_port}",
            f"X_TP_ExternalPortEnd={external_port}",
            f"internalPort={int_port}",
            f"X_TP_InternalPortEnd={int_port}",
            f"internalClient={internal_ip}",
            f"portMappingProtocol={proto}",
            "portMappingEnabled=1",
        ]
        self.req_act([ActItem(ActItem.ADD, "WAN_IP_CONN_PORTMAPPING", pstack=wan_stack, attrs=attrs)])
        return True

    def del_port_forwarding(self, rule_stack: str) -> bool:
        """Deletes a port forwarding rule by stack ID (e.g. '2,1,1,1,0,0')."""
        self.req_act([ActItem(ActItem.DEL, "WAN_IP_CONN_PORTMAPPING", stack=rule_stack)])
        return True

    def get_dmz(self) -> DMZConfig:
        """Returns DMZ Host configuration."""
        res = self.req_act([ActItem(ActItem.GET, "DMZ_HOST_CFG")])
        raw = res.get("0", {})
        data = raw[0] if isinstance(raw, list) and raw else raw
        return DMZConfig(
            enabled=data.get("enable") == "1",
            ip_address=data.get("IPAddress", "")
        )

    def set_dmz(self, enabled: bool, ip_address: str = "") -> bool:
        """Enables or disables DMZ host forwarding to an internal IP address."""
        attrs = [
            f"enable={'1' if enabled else '0'}",
            f"IPAddress={ip_address if enabled else ''}"
        ]
        self.req_act([ActItem(ActItem.SET, "DMZ_HOST_CFG", attrs=attrs)])
        return True

    def get_upnp(self) -> UPnPStatus:
        """Returns UPnP status and active dynamic port mappings."""
        res_cfg = self.req_act([ActItem(ActItem.GET, "UPNP_CFG")])
        raw_cfg = res_cfg.get("0", {})
        cfg_data = raw_cfg[0] if isinstance(raw_cfg, list) and raw_cfg else raw_cfg
        is_enabled = cfg_data.get("enable") == "1"

        mappings: List[UPnPPortMapping] = []
        try:
            res_maps = self.req_act([ActItem(ActItem.GL, "UPNP_PORTMAPPING")])
            raw_maps = res_maps.get("0", [])
            if isinstance(raw_maps, dict):
                raw_maps = [raw_maps]
            for m in raw_maps:
                if not m.get("__stack"):
                    continue
                mappings.append(UPnPPortMapping(
                    protocol=m.get("portMappingProtocol", "TCP"),
                    external_port=int(m.get("externalPort", 0)),
                    internal_ip=m.get("internalClient", ""),
                    internal_port=int(m.get("internalPort", 0)),
                    description=m.get("PortMappingDescription", ""),
                    enabled=m.get("portMappingEnabled") == "1"
                ))
        except Exception:
            pass

        return UPnPStatus(enabled=is_enabled, mappings=mappings)

    def set_upnp(self, enabled: bool) -> bool:
        """Enables or disables Universal Plug and Play (UPnP)."""
        self.req_act([ActItem(ActItem.SET, "UPNP_CFG", attrs=[f"enable={'1' if enabled else '0'}"])])
        return True

    def get_reboot_schedule(self) -> RebootScheduleConfig:
        """Returns automated router reboot schedule."""
        res = self.req_act([ActItem(ActItem.GET, "REBOOT_SCHEDULE_CFG")])
        raw = res.get("0", {})
        data = raw[0] if isinstance(raw, list) and raw else raw

        days = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
        mode_val = data.get("mode", "1")
        mode_name = "weekly" if mode_val == "2" else ("monthly" if mode_val == "3" else "daily")
        day_num = int(data.get("week") or data.get("day") or 1)

        return RebootScheduleConfig(
            enabled=data.get("enable") == "1",
            mode=mode_name,
            hours=int(data.get("hours", 3)),
            minutes=int(data.get("minutes", 0)),
            day_of_week=day_num,
            day_name=days.get(day_num, "Monday")
        )

    def set_reboot_schedule(self, enabled: bool, hours: int = 3, minutes: int = 0,
                            mode: str = "daily", day_of_week: int = 1) -> bool:
        """Configures automated periodic router reboot schedule."""
        mode_num = "2" if mode.lower() == "weekly" else ("3" if mode.lower() == "monthly" else "1")
        attrs = [
            f"enable={'1' if enabled else '0'}",
            f"mode={mode_num}",
            f"hours={hours}",
            f"minutes={minutes}",
            f"day={day_of_week}",
            f"week={day_of_week}",
        ]
        self.req_act([ActItem(ActItem.SET, "REBOOT_SCHEDULE_CFG", attrs=attrs)])
        return True

    def get_time_config(self) -> TimeConfig:
        """Returns router system time, timezone, and NTP configuration."""
        res = self.req_act([ActItem(ActItem.GET, "TIME")])
        raw = res.get("0", {})
        data = raw[0] if isinstance(raw, list) and raw else raw

        return TimeConfig(
            current_time=data.get("currentLocalTime", ""),
            timezone=data.get("localTimeZone", ""),
            daylight_savings=data.get("daylightSavingsUsed") == "1",
            ntp_server1=data.get("NTPServer1", ""),
            ntp_server2=data.get("NTPServer2", "")
        )

    def sync_time(self) -> bool:
        """Synchronizes router system clock via NTP."""
        try:
            self.req_act([ActItem(ActItem.OP, "ACT_OP_NTP_REQUEST")])
            return True
        except Exception:
            return False

    def get_operation_mode(self) -> OperationMode:
        """Returns the current operation mode (3G/4G Router vs Wireless Router)."""
        res = self.req_act([ActItem(ActItem.GET, "SYS_MODE")])
        raw = res.get("0", {})
        data = raw[0] if isinstance(raw, list) and raw else raw

        raw_mode = data.get("mode", "LTE")
        friendly = "3G/4G Router Mode" if raw_mode == "LTE" else "Wireless Router Mode (Ethernet WAN)"

        return OperationMode(
            mode=friendly,
            raw_mode=raw_mode,
            lte_backup_enabled=data.get("lteBackupEnable") == "1",
            cellular_data_switch=data.get("LTEDataSwitch") == "1"
        )

    def get_ddns_status(self) -> List[DDNSStatus]:
        """Returns configured Dynamic DNS (DDNS) providers and status."""
        providers = []
        try:
            r_noip = self.req_act([ActItem(ActItem.GET, "NOIP_DNS_CFG")])
            data = r_noip.get("0", {})
            if isinstance(data, list) and data:
                data = data[0]
            state_map = {"0": "Connected", "1": "Connecting", "2": "Auth Error", "3": "Disconnected"}
            providers.append(DDNSStatus(
                provider="No-IP",
                enabled=data.get("enable") == "1",
                domain=data.get("userDomain", ""),
                username=data.get("userName", ""),
                status=state_map.get(data.get("state", "3"), "Unknown")
            ))
        except Exception:
            pass

        try:
            r_dyn = self.req_act([ActItem(ActItem.GET, "DYN_DNS_CFG")])
            data = r_dyn.get("0", {})
            if isinstance(data, list) and data:
                data = data[0]
            state_map = {"0": "Connected", "1": "Connecting", "2": "Auth Error", "3": "Disconnected"}
            providers.append(DDNSStatus(
                provider="DynDNS",
                enabled=data.get("enable") == "1",
                domain=data.get("userDomain", ""),
                username=data.get("userName", ""),
                status=state_map.get(data.get("state", "3"), "Unknown")
            ))
        except Exception:
            pass

        try:
            r_tp = self.req_act([ActItem(ActItem.GET, "CLOUD_DDNS")])
            data = r_tp.get("0", {})
            if isinstance(data, list) and data:
                data = data[0]
            providers.append(DDNSStatus(
                provider="TP-Link Cloud DDNS",
                enabled=data.get("enable") == "1",
                domain=data.get("boundDomain", ""),
                username="TP-Link ID",
                status="Connected" if data.get("boundDomain") else "Unbound"
            ))
        except Exception:
            pass

        return providers

    def check_firmware_update(self) -> FirmwareUpdateInfo:
        """Checks for official online firmware updates via TP-Link Cloud."""
        dev_info = self.get_device_info()
        cur_ver = dev_info.firmware_version

        try:
            self.req_act([ActItem(ActItem.OP, "ACT_CLOUD_CHECKNEWFWINFO_BY_USER")])
        except Exception:
            pass

        res = self.req_act([ActItem(ActItem.GET, "FW_UPGRADE_INFO")])
        raw = res.get("0", {})
        data = raw[0] if isinstance(raw, list) and raw else raw

        latest = data.get("version", "")
        has_new = bool(latest and latest != cur_ver and data.get("status") in ("1", "3"))

        return FirmwareUpdateInfo(
            current_version=cur_ver,
            has_update=has_new,
            latest_version=latest or cur_ver,
            release_date=data.get("releaseDate", ""),
            release_log=data.get("releaseLog", data.get("informMessage", ""))
        )
