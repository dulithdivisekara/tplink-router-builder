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

    def set_lte_band(self, band: str) -> bool:
        """Manually locks router to specific LTE band (e.g. '3', '8', '40', or 'auto')."""
        if band.lower() == "auto":
            attrs = ["enable=0", "selectedBand=0"]
        else:
            clean_band = band.upper().replace("BAND", "").strip()
            attrs = ["enable=1", f"selectedBand={clean_band}"]
        acts = [ActItem(ActItem.SET, "LTE_BAND_SEL", attrs=attrs)]
        self.req_act(acts)
        return True
