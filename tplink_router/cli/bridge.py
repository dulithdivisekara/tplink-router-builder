"""
Serialized NDJSON Stdio Router Bridge for the vadimdemedes/ink React TUI.

Why a dedicated serialized bridge?
  1. Keeps the React + Ink UI loop running smoothly at 20-30 FPS in Node.js
     (animations, logo shimmer, Claude-Code spinner, keyboard input never block).
  2. Guarantees strict FIFO single-session serialization against TP-Link
     Archer MR200 / router CGI endpoints so concurrent polls never collide with
     single-admin session locks (error 71233).
"""

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import sys
import time
from typing import Any, Dict, List, Optional

from tplink_router.cli.main import build_parser, get_client, handle_cli_error
from tplink_router.cli.theme import get_palette, render_panel
from tplink_router.core.config import ConfigManager
from tplink_router.core.session import SafeSession


class RouterBridgeWorker:
    """Single-threaded FIFO request processor speaking newline-delimited JSON."""

    def __init__(
        self,
        target_host: Optional[str] = None,
        base_flags: Optional[List[str]] = None,
    ) -> None:
        cfg = ConfigManager().load(cli_host=target_host)
        self.target_host: str = target_host or cfg.get("host", "http://192.168.1.1")
        self.expected_ssid: Optional[str] = cfg.get("expected_ssid")
        self.base_flags: List[str] = list(base_flags or [])
        self._parser = build_parser()

    def _make_ns(self) -> argparse.Namespace:
        return argparse.Namespace(
            host=self.target_host,
            username=None,
            password=None,
            cookie=None,
            force=False,
            json=False,
            legacy=False,
            mono=False,
            no_anim=True,
        )

    def handle_ping(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "host": self.target_host,
            "expected_ssid": self.expected_ssid or "",
            "version": "1.0.0",
        }

    def handle_telemetry(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.monotonic()
        buf = io.StringIO()
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                client = get_client(self._make_ns())
                with SafeSession(client):
                    t = client.get_telemetry()

            lte = t.lte
            v4 = t.ipv4
            v6 = t.ipv6
            v6_en = bool(v6.enabled or v6.ip)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {
                "online": True,
                "elapsed_ms": elapsed_ms,
                "timestamp": time.time(),
                "model": t.device.model or "TP-Link Router",
                "hw_version": t.device.hardware_version or "",
                "fw_version": t.device.firmware_version or "",
                "carrier": lte.isp_name if lte else "WAN",
                "sim_status": lte.sim_status if lte else "N/A",
                "connected": bool(lte.connected) if lte else bool(v4.ip),
                "band": lte.band if lte else "Ethernet",
                "earfcn": (lte.earfcn or "N/A") if lte else "N/A",
                "pci": (lte.pci or "0") if lte else "0",
                "cell_locked": bool(lte.cell_lock.enabled) if (lte and lte.cell_lock) else False,
                "bars": int(lte.rf.signal_bars) if lte else 4,
                "rssi_dbm": float(lte.rf.rssi_dbm) if lte else 0.0,
                "rssi_rating": lte.rf.rssi_rating if lte else "Good",
                "rsrp_dbm": float(lte.rf.rsrp_dbm) if lte else 0.0,
                "rsrp_rating": lte.rf.rsrp_rating if lte else "Good",
                "rsrq_db": float(lte.rf.rsrq_db) if lte else 0.0,
                "rsrq_rating": lte.rf.rsrq_rating if lte else "Good",
                "snr_db": float(lte.rf.snr_db) if lte else 0.0,
                "snr_rating": lte.rf.snr_rating if lte else "Good",
                "rx_kbps": float(lte.rx_speed_kbps) if lte else 0.0,
                "tx_kbps": float(lte.tx_speed_kbps) if lte else 0.0,
                "total_mb": round(lte.total_bytes_transferred / (1024 * 1024), 2) if lte else 0.0,
                "wan_ip": v4.ip or "N/A",
                "gateway": v4.gateway or "N/A",
                "dns": list(v4.dns) if v4.dns else [],
                "ipv6_enabled": v6_en,
                "ipv6_status": v6.status or ("Enabled" if v6_en else "Disabled"),
            }
        except ( Exception, SystemExit ) as exc:
            return {
                "online": False,
                "elapsed_ms": int((time.monotonic() - t0) * 1000),
                "timestamp": time.time(),
                "error": str(exc) or buf.getvalue().strip() or "Router unreachable",
            }

    def _exec_single_argv(self, argv: List[str], mono: bool) -> str:
        buf = io.StringIO()
        full_argv = list(self.base_flags)
        if self.target_host and "--host" not in full_argv and "--host" not in argv:
            full_argv.extend(["--host", self.target_host])
        if mono and "--mono" not in full_argv and "--mono" not in argv:
            full_argv.append("--mono")
        if "--no-anim" not in full_argv and "--no-anim" not in argv:
            full_argv.append("--no-anim")
        full_argv.extend(argv)

        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                parsed = self._parser.parse_args(full_argv)
                for _k, _v in [
                    ("json", False),
                    ("host", self.target_host),
                    ("username", None),
                    ("password", None),
                    ("cookie", None),
                    ("force", False),
                    ("legacy", False),
                    ("mono", mono),
                    ("no_anim", True),
                ]:
                    if not hasattr(parsed, _k):
                        setattr(parsed, _k, _v)
                if hasattr(parsed, "func"):
                    parsed.func(parsed)
        except SystemExit:
            pass
        except Exception as exc:
            with redirect_stdout(buf), redirect_stderr(buf):
                handle_cli_error(
                    exc,
                    argparse.Namespace(
                        json=False, host=self.target_host, mono=mono, legacy=False, no_anim=True
                    ),
                )
        return buf.getvalue().strip("\n")

    def handle_run_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        argv = [str(x) for x in params.get("argv", [])]
        mono = bool(params.get("mono", False))
        t0 = time.monotonic()
        output = self._exec_single_argv(argv, mono=mono)
        return {
            "output": output,
            "command": "tplink-cli " + " ".join(argv),
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
        }

    def handle_run_batch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        commands = params.get("commands", [])
        mono = bool(params.get("mono", False))
        p = get_palette(mono=mono)
        t0 = time.monotonic()
        blocks: List[str] = []
        total = len(commands)
        for idx, raw_cmd in enumerate(commands, 1):
            argv = [str(x) for x in raw_cmd]
            cmd_str = "tplink-cli " + " ".join(argv)
            blocks.append(f"{p.brand_bold}▸ [{idx}/{total}] {cmd_str}{p.reset}")
            out = self._exec_single_argv(argv, mono=mono)
            blocks.append(out or f"{p.muted}(completed with no output){p.reset}")
            blocks.append("")
        return {
            "output": "\n".join(blocks).rstrip(),
            "count": total,
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
        }

    def handle_get_toggles(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        buf = io.StringIO()
        states = {
            "ipv6": False,
            "wifi_2g": True,
            "wifi_5g": True,
            "guest_wifi": False,
            "upnp": False,
            "led_night": False,
        }
        with redirect_stdout(buf), redirect_stderr(buf):
            client = get_client(self._make_ns())
            with SafeSession(client):
                _, v6 = client.get_wan_config()
                states["ipv6"] = bool(v6.enabled or v6.ip)
                if hasattr(client, "get_wifi_status"):
                    for net in client.get_wifi_status():
                        if "2.4" in net.get("band", ""):
                            states["wifi_2g"] = bool(net.get("enabled"))
                        elif "5" in net.get("band", ""):
                            states["wifi_5g"] = bool(net.get("enabled"))
                if hasattr(client, "get_guest_wifi"):
                    gw = client.get_guest_wifi()
                    states["guest_wifi"] = any(n.enabled for n in gw.networks)
                if hasattr(client, "get_upnp"):
                    states["upnp"] = bool(client.get_upnp().enabled)
                if hasattr(client, "get_led_status"):
                    states["led_night"] = bool(client.get_led_status().get("night_mode_enabled"))
        return {"states": states}

    def handle_apply_toggles(self, params: Dict[str, Any]) -> Dict[str, Any]:
        initial: Dict[str, bool] = dict(params.get("initial", {}))
        updated: Dict[str, bool] = dict(params.get("updated", {}))
        mono = bool(params.get("mono", False))
        p = get_palette(mono=mono)

        changed = {k: bool(v) for k, v in updated.items() if bool(initial.get(k)) != bool(v)}
        if not changed:
            panel = render_panel(
                title="QUICK FEATURE SWITCHBOARD",
                sections=[[f"{p.muted}No switches were modified.{p.reset}"]],
                mono=mono,
            )
            return {"output": panel, "changed": 0}

        buf = io.StringIO()
        results: List[str] = []
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                client = get_client(self._make_ns())
                with SafeSession(client):
                    if "ipv6" in changed:
                        client.toggle_ipv6(changed["ipv6"])
                        results.append(f"{p.success}✓{p.reset} IPv6 WAN Stack -> {'ENABLED' if changed['ipv6'] else 'DISABLED'}")
                    if "wifi_2g" in changed and hasattr(client, "set_wifi_radio"):
                        client.set_wifi_radio(band="2.4GHz", enabled=changed["wifi_2g"])
                        results.append(f"{p.success}✓{p.reset} 2.4GHz Wi-Fi Radio -> {'ON' if changed['wifi_2g'] else 'OFF'}")
                    if "wifi_5g" in changed and hasattr(client, "set_wifi_radio"):
                        client.set_wifi_radio(band="5GHz", enabled=changed["wifi_5g"])
                        results.append(f"{p.success}✓{p.reset} 5GHz Wi-Fi Radio -> {'ON' if changed['wifi_5g'] else 'OFF'}")
                    if "guest_wifi" in changed and hasattr(client, "set_guest_wifi"):
                        client.set_guest_wifi(band="both", enabled=changed["guest_wifi"])
                        results.append(f"{p.success}✓{p.reset} Guest Wi-Fi -> {'ENABLED' if changed['guest_wifi'] else 'DISABLED'}")
                    if "upnp" in changed and hasattr(client, "set_upnp"):
                        client.set_upnp(enabled=changed["upnp"])
                        results.append(f"{p.success}✓{p.reset} UPnP Service -> {'ENABLED' if changed['upnp'] else 'DISABLED'}")
                    if "led_night" in changed and hasattr(client, "set_led_night_mode"):
                        client.set_led_night_mode(enabled=changed["led_night"], start_time="22:00", end_time="07:00")
                        results.append(f"{p.success}✓{p.reset} LED Night Mode -> {'ENABLED' if changed['led_night'] else 'DISABLED'}")
            panel = render_panel(
                title="SWITCHBOARD CHANGES APPLIED",
                sections=[results],
                accent="success",
                mono=mono,
            )
            return {"output": panel, "changed": len(changed)}
        except (Exception, SystemExit) as exc:
            panel = render_panel(
                title="SWITCHBOARD ERROR",
                sections=[[f"{p.danger}✖ Failed applying switches: {exc}{p.reset}"]],
                accent="danger",
                mono=mono,
            )
            return {"output": panel, "changed": 0, "error": str(exc)}

    def dispatch(self, req: Dict[str, Any]) -> Dict[str, Any]:
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        handlers = {
            "ping": self.handle_ping,
            "telemetry": self.handle_telemetry,
            "run_command": self.handle_run_command,
            "run_batch": self.handle_run_batch,
            "get_toggles": self.handle_get_toggles,
            "apply_toggles": self.handle_apply_toggles,
        }
        if method not in handlers:
            return {"id": req_id, "ok": False, "error": f"Unknown bridge method: {method}"}

        try:
            result = handlers[method](params)
            return {"id": req_id, "ok": True, "result": result}
        except Exception as exc:
            return {"id": req_id, "ok": False, "error": str(exc)}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="TP-Link Ink TUI JSON-RPC Router Bridge")
    ap.add_argument("--host", default=None, help="Target router gateway URL")
    parsed = ap.parse_args(argv)

    proto_out = sys.stdout
    worker = RouterBridgeWorker(target_host=parsed.host)

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            proto_out.write(json.dumps({"id": None, "ok": False, "error": f"Invalid JSON: {exc}"}) + "\n")
            proto_out.flush()
            continue

        if req.get("method") == "shutdown":
            proto_out.write(json.dumps({"id": req.get("id"), "ok": True, "result": {"bye": True}}) + "\n")
            proto_out.flush()
            return 0

        resp = worker.dispatch(req)
        proto_out.write(json.dumps(resp) + "\n")
        proto_out.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
