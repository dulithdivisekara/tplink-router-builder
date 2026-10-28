# TP-Link Gateway & Router Endpoints Reference Catalog

> **Author & Architect**: [Dulith Divisekara](https://github.com/dulithdivisekara) (IT Undergraduate, SLIIT Malabe, Sri Lanka)  
> **Target Target**: TP-Link Archer MR Series (MR200, MR6400, MR600, MR100) & Archer Broadband Series (C6, C6U, AX10, AX50)  
> **Firmware Platform**: TP-Link HTTPd / `uhttpd` TR-064 API Engine with GDPR RSA-512 + AES-128-CBC Session Encryption

---

## Architecture & Authentication Overview

Modern TP-Link gateways enforce a single-admin concurrency lock and protect all administrative endpoints behind multi-tiered authentication.

```
       [ Client / Agent ]
               |
  1. POST /cgi/getParm (Extract RSA pubkey `nn`, `ee`, sequence `seq`)
               |
  2. Encrypt AES-128-CBC key + iv with RSA-512 (custom 64-byte null-padded blocks)
               |
  3. POST /cgi/login?data={aes_b64}&sign={rsa_sign}&Action=1
               |
  4. Acquire session cookie (JSESSIONID) + TokenID
               |
  5. Subsequent Calls:
     - Plain / Modern Fallback: POST /cgi?{action_id_list}
     - GDPR Encrypted: POST /cgi_gdpr? with AES-encrypted payload
```

### Action Types (`$.act`)
Every request to the router's TR-064 backend sends one or more action codes:

| Action Code | Name | Function |
|---|---|---|
| `1` | `ACT_GET` | Query single instance attributes of an OID |
| `2` | `ACT_SET` | Modify attributes of a targeted object stack |
| `3` | `ACT_ADD` | Create a new table instance (e.g. DHCP reservation, Port Forward) |
| `4` | `ACT_DEL` | Delete an existing table instance by its stack ID |
| `5` | `ACT_GL` | Get List: queries all entries in a multi-instance table (e.g. connected hosts) |
| `6` | `ACT_GS` | Get Substack: queries instances childed under a specific stack |
| `7` | `ACT_OP` | Execute an action operation (e.g. Reboot, Start Diagnostic) |
| `8` | `ACT_CGI` | Invoke a specialized CGI binary handler |

---

## Complete Subsystems & OID Matrix

### 1. Cellular & LTE Modem Control
*Target Pages*: `/main/basicLte.htm`, `/main/advanceLte.htm`, `/main/ltecelllock.htm`, `/main/dataSettings.htm`

| TR-064 OID | Supported Actions | Key Attributes | Description |
|---|---|---|---|
| `LTE_CELL_LOCK` | `ACT_GET`, `ACT_SET` | `enable`, `earfcn`, `pci`, `cid`, `freq` | Locks modern modem to a specific cell tower to avoid erratic cell handover. |
| `LTE_BAND_SEL` | `ACT_GET`, `ACT_SET` | `enable`, `bandList`, `selectedBand` | Locks modem to specific LTE bands (B3 1800MHz, B8 900MHz, B40 2300MHz, etc.). |
| `LTE_BANDINFO` | `ACT_GET` | `band`, `earfcn`, `pci`, `rsrp`, `rsrq`, `snr` | Live RF physical layer performance telemetry. |
| `LTE_NET_STATUS` | `ACT_GET` | `sigLevel`, `networkType`, `simStatus`, `smsUnreadCount` | Network registration and signal strength (bars). |
| `WAN_LTE_LINK_CFG` | `ACT_GET`, `ACT_GL` | `enable`, `connectStatus`, `networkType`, `simStatus` | Cellular link state and SIM detection. |
| `WAN_LTE_INTF_CFG` | `ACT_GET`, `ACT_SET`, `ACT_GL` | `enableDataLimit`, `limitation`, `paymentDay`, `curStatistics`, `totalStatistics`, `curRxSpeed`, `curTxSpeed` | Monthly data cap in MB, billing day, and live bandwidth monitor. |
| `LTE_WAN_CFG` | `ACT_GET`, `ACT_SET` | `profileName`, `dataSwitchStatus`, `networkPreferredMode`, `roamingEnabled` | APN profile configuration and mobile data roaming switch. |
| `MOBILEDOG_CFG` | `ACT_GET`, `ACT_SET` | `enable`, `pingHost`, `interval`, `maxFailCount` | Cellular link watchdog that pings remote host and re-establishes connection if frozen. |

### 2. SMS & USSD Messaging
*Target Pages*: `/main/lteSmsInbox.htm`, `/main/lteSmsOutbox.htm`, `/main/lteSmsNewMsg.htm`, `/main/lteUssd.htm`

| TR-064 OID | Supported Actions | Key Attributes | Description |
|---|---|---|---|
| `LTE_SMS_RECVMSGBOX` | `ACT_GET`, `ACT_SET` | `PageNumber`, `TotalCount`, `UnreadCount` | Sets inbox page number for pagination. |
| `LTE_SMS_RECVMSGENTRY` | `ACT_GL`, `ACT_DEL` | `index`, `from`, `content`, `receivedTime`, `unread` | Fetches SMS inbox messages with sender and timestamp. |
| `LTE_SMS_SENDNEWMSG` | `ACT_SET`, `ACT_GET` | `index`, `to`, `textContent`, `sendResult` | Sends a new SMS message and queries delivery result. |
| `LTE_USSD` | `ACT_SET`, `ACT_GET` | `action`, `reqContent`, `sessionStatus`, `response`, `ussdStatus` | Sends interactive USSD commands (e.g. `*130#`) and reads operator balance. |

### 3. LAN & Client Management
*Target Pages*: `/main/dhcp.htm`, `/main/networkMap.htm`, `/main/arpBind.htm`

| TR-064 OID | Supported Actions | Key Attributes | Description |
|---|---|---|---|
| `LAN_HOST_ENTRY` | `ACT_GL` | `hostName`, `IPAddress`, `MACAddress`, `leaseTimeRemaining`, `addressSource` | Returns all active wired and wireless clients on the LAN. |
| `LAN_DHCP_STATIC_ADDR` | `ACT_GL`, `ACT_SET`, `ACT_ADD`, `ACT_DEL` | `enable`, `chaddr`, `yiaddr` | Manages DHCP static IP address reservations by MAC. |
| `LAN_HOST_CFG` | `ACT_GET`, `ACT_SET` | `DHCPServerEnable`, `minAddress`, `maxAddress`, `DHCPLeaseTime` | Configures router DHCP server scope and lease duration. |
| `LAN_IP_INTF` | `ACT_GET`, `ACT_GS`, `ACT_SET` | `IPInterfaceIPAddress`, `IPInterfaceSubnetMask` | Router gateway IP (`192.168.1.1`) and subnet mask. |

### 4. Wireless & Guest Network
*Target Pages*: `/main/wirelessBasic.htm`, `/main/wirelessSettings.htm`, `/main/wlGuestDulBandBasic.htm`, `/main/oneMesh.htm`

| TR-064 OID | Supported Actions | Key Attributes | Description |
|---|---|---|---|
| `LAN_WLAN` | `ACT_GL`, `ACT_GS`, `ACT_SET`, `ACT_GET` | `Name`, `Enable`, `SSID`, `X_TP_Band`, `Channel`, `X_TP_PreSharedKey` | Controls 2.4 GHz and 5 GHz Wi-Fi radios and SSIDs. |
| `LAN_WLAN_ASSOC_DEV` | `ACT_GL`, `ACT_GS` | `AssociatedDeviceMACAddress`, `X_TP_TotalPacketsSent`, `X_TP_TotalPacketsReceived` | Wireless station associations and traffic packet counters. |
| `LAN_WLAN_MSSIDENTRY` | `ACT_GS`, `ACT_SET` | `Name`, `Enable`, `SSID`, `isolateClients`, `PreSharedKey` | Guest Wi-Fi network and client AP isolation. |
| `ONEMESH` | `ACT_GET`, `ACT_SET` | `enableSmartConnect` | Unified Smart Connect steering devices across 2.4G & 5G bands. |

### 5. Diagnostics, System & Tools
*Target Pages*: `/main/diagnostic.htm`, `/main/ledSchedule.htm`, `/main/restart.htm`, `/main/time.htm`

| TR-064 OID | Supported Actions | Key Attributes | Description |
|---|---|---|---|
| `DIAG_TOOL` | `ACT_GET`, `ACT_OP` | `LastResult` | Router WAN and NCSI self-test status. |
| `ACT_OP_DIAG_STARTDIAG` | `ACT_OP` | - | Triggers full end-to-end diagnostic test on router. |
| `IPPING_DIAG` | `ACT_GET`, `ACT_SET`, `ACT_OP` | `host`, `numberOfRepetitions`, `successCount`, `averageResponseTime` | Built-in router ICMP Ping engine. |
| `TRACEROUTE_DIAG` | `ACT_GET`, `ACT_SET`, `ACT_OP` | `host`, `maxHopCount`, `timeout`, `responseTime` | Built-in router Traceroute engine. |
| `LED_BUTTON` | `ACT_GET`, `ACT_SET` | `enable` | Turns router physical front panel LEDs on or off. |
| `LED_SCHEDULE_CFG` | `ACT_GET`, `ACT_SET` | `enable`, `startTime`, `endTime` | Night mode schedule: automatically turns off LEDs at night (in minutes from midnight). |
| `ACT_OP_REBOOT` | `ACT_OP` | - | Triggers immediate hardware restart. |
| `REBOOT_SCHEDULE_CFG` | `ACT_GET`, `ACT_SET` | `enable`, `mode`, `time`, `day` | Scheduled automatic weekly or daily reboot. |
| `IGD_DEV_INFO` | `ACT_GET` | `modelName`, `description`, `softwareVersion`, `hardwareVersion` | Device hardware and firmware identifiers. |

---

## Complete Catalog of 95 Router Web Pages

The TP-Link Archer MR200 v5 exposes 95 operational pages accessible under `http://192.168.1.1/main/`:

| Subsystem | Web Pages (`.htm`) |
|---|---|
| **Cellular & LTE** | `basicLte.htm`, `advanceLte.htm`, `ltecelllock.htm`, `dataSettings.htm`, `PINManagement.htm`, `lteIspUpdate.htm`, `basic3g.htm`, `usb3g.htm` |
| **Messaging** | `lteSmsInbox.htm`, `lteSmsOutbox.htm`, `lteSmsDraftbox.htm`, `lteSmsNewMsg.htm`, `lteSmsSettings.htm`, `lteUssd.htm` |
| **Network & WAN** | `status.htm`, `networkMap.htm`, `wanBasic.htm`, `wan.htm`, `ethWan.htm`, `ethWanBasic.htm`, `dhcp.htm`, `ddns.htm`, `sysMode.htm`, `route.htm`, `iptv.htm`, `iptvEth.htm`, `iptvDsl.htm` |
| **Wireless** | `wirelessBasic.htm`, `wirelessSettings.htm`, `wirelessAdv.htm`, `wirelessSchedule.htm`, `wirelessStat.htm`, `wlGuestDulBandBasic.htm`, `wlGuestDulBandAdv.htm`, `wps.htm`, `oneMesh.htm` |
| **Security & NAT** | `accessControl.htm`, `ddos.htm`, `arpBind.htm`, `ipv6Firewall.htm`, `virtualServer.htm`, `portTrigger.htm`, `portFiltering.htm`, `dmz.htm`, `upnp.htm`, `natBoost.htm`, `alg.htm`, `parentCtrl.htm` |
| **VPN Services** | `vpnClient.htm`, `vpnStatus.htm`, `openvpnServer.htm`, `pptpvpnServer.htm`, `l2tpv2VpnServer.htm`, `ipsec.htm` |
| **System Tools** | `diagnostic.htm`, `ledSchedule.htm`, `restart.htm`, `time.htm`, `log.htm`, `softup.htm`, `backNRestore.htm`, `manageCtrl.htm`, `manageCtrl_remote.htm`, `snmp.htm`, `cwmp.htm` |
| **VoIP / USB** | `usbManage.htm`, `folderSharing.htm`, `printSrv.htm`, `voice_advance.htm`, `voice_basic.htm`, `voice_telephony.htm`, `voice_calllog.htm` |
