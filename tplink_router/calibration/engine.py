"""Autonomous Disconnection-Safe Router Calibration Engine.

Sweeps cellular bands (Band 8 900MHz, Band 3 1800MHz, Band 1 2100MHz, Band 40 2300MHz, Auto),
measures live RF metrics, ping jitter, packet loss, Path MTU, and applies an
autonomous 45-second watchdog auto-revert to safeguard against WAN blackouts.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from tplink_router.clients.factory import RouterClientFactory
from tplink_router.core.session import SafeSession

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = Path("/tmp/tplink_calibration_state.json")
DEFAULT_BANDS = ["8", "3", "1", "40", "auto"]
DEFAULT_WATCHDOG_SEC = 45


BAND_METADATA = {
    "8": {
        "name": "Band 8 (900 MHz FDD)",
        "frequency": "900 MHz",
        "type": "FDD",
        "hutch_bw": "5 - 10 MHz",
        "rain_penetration": "Superior (★★★★★)",
        "desc": "Sub-1GHz carrier. Highest penetration through monsoon rain, wet foliage, and thick walls in Malabe."
    },
    "3": {
        "name": "Band 3 (1800 MHz FDD)",
        "frequency": "1800 MHz",
        "type": "FDD",
        "hutch_bw": "15 MHz Contiguous",
        "rain_penetration": "Moderate (★★★☆☆)",
        "desc": "Primary Hutch 4G carrier. Max peak throughput (up to 20Mbps cap) in clear weather."
    },
    "1": {
        "name": "Band 1 (2100 MHz FDD)",
        "frequency": "2100 MHz",
        "type": "FDD",
        "hutch_bw": "5 - 10 MHz",
        "rain_penetration": "Moderate-Low (★★☆☆☆)",
        "desc": "Refarmed 3G carrier for urban micro-cell capacity."
    },
    "40": {
        "name": "Band 40 (2300 MHz TDD)",
        "frequency": "2300 MHz",
        "type": "TDD",
        "hutch_bw": "10 - 20 MHz",
        "rain_penetration": "Poor (★☆☆☆☆)",
        "desc": "High frequency TDD. Extreme rain fade vulnerability; prone to packet drops during rain."
    },
    "auto": {
        "name": "AUTO (Dynamic Roaming)",
        "frequency": "Multi-Band Aggregated",
        "type": "Dynamic",
        "hutch_bw": "Variable",
        "rain_penetration": "Dynamic (★★★☆☆)",
        "desc": "Default modem behavior. Roams between towers based on factory RSSI thresholds."
    }
}


class RouterCalibrator:
    """Manages the autonomous calibration sweep across LTE bands with watchdog safeguards."""

    def __init__(
        self,
        host: str = "http://192.168.1.1",
        password: Optional[str] = None,
        session_cookie: Optional[str] = None,
        username: str = "admin",
        bands: Optional[List[str]] = None,
        watchdog_timeout: int = DEFAULT_WATCHDOG_SEC,
        state_file: Path = DEFAULT_STATE_FILE,
        dry_run: bool = False,
        echo_stdout: bool = False,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.host = host.rstrip("/")
        self.password = password
        self.session_cookie = session_cookie
        self.username = username
        self.bands = [b.lower().replace("band", "").strip() for b in (bands or DEFAULT_BANDS)]
        self.watchdog_timeout = watchdog_timeout
        self.state_file = Path(state_file)
        self.dry_run = dry_run
        self.echo_stdout = echo_stdout
        self.on_update = on_update

        self.running = False
        self.stop_requested = False
        self._lock = threading.Lock()
        self.client = None

        self.state: Dict[str, Any] = {
            "status": "IDLE",
            "current_phase": "READY",
            "current_band": "auto",
            "progress_pct": 0,
            "message": "Calibrator initialized. Ready to begin sweep.",
            "watchdog_remaining_sec": 0,
            "last_updated": time.time(),
            "last_updated_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "host": self.host,
            "active_metrics": {
                "band": "auto",
                "rsrp": 0,
                "rsrq": 0,
                "sinr": 0,
                "latency_ms": 0.0,
                "jitter_ms": 0.0,
                "loss_pct": 0.0,
                "mtu_clamped": 1500,
            },
            "live_pings": [],
            "bands_evaluated": [],
            "logs": [],
            "recommendation": None,
        }
        self._write_state()

    def _log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{level}] {msg}"
        with self._lock:
            self.state["logs"].append(entry)
            # Keep last 100 log lines
            if len(self.state["logs"]) > 100:
                self.state["logs"].pop(0)
            self.state["message"] = msg
        logger.info(entry)
        if self.echo_stdout:
            color = "\033[93m" if level == "WARN" else ("\033[91m" if level == "ERROR" else "\033[96m")
            print(f"{color}[{timestamp}] [{level}]\033[0m {msg}")
        self._write_state()

    def _write_state(self):
        """Atomically saves calibration state to disk."""
        with self._lock:
            self.state["last_updated"] = time.time()
            self.state["last_updated_str"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data = json.dumps(self.state, indent=2)

        tmp_file = self.state_file.with_suffix(".tmp")
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(data)
            tmp_file.replace(self.state_file)
        except Exception as e:
            logger.warning(f"Failed to write state file: {e}")

        if self.on_update:
            try:
                self.on_update(self.state)
            except Exception:
                pass

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.state)

    def _init_client(self) -> bool:
        """Initializes client session if credentials are supplied."""
        if self.dry_run or (not self.password and not self.session_cookie):
            self._log("Running in unauthenticated / read-only network probe mode.", "WARN")
            return False
        try:
            self.client = RouterClientFactory.get_client(
                host=self.host,
                password=self.password,
                username=self.username,
                session_cookie=self.session_cookie,
                timeout=10,
            )
            return True
        except Exception as e:
            self._log(f"Router authentication failed: {e}. Falling back to passive probe.", "WARN")
            self.client = None
            return False

    def run_ping(
        self,
        target: str = "1.1.1.1",
        count: int = 20,
        payload_size: int = 56,
        dont_fragment: bool = False,
        timeout_sec: int = 25
    ) -> Dict[str, Any]:
        """Executes a ping burst and extracts min/avg/max/jitter/loss."""
        cmd = ["ping", "-c", str(count), "-s", str(payload_size), "-W", "1"]
        if dont_fragment:
            cmd.extend(["-M", "do"])
        cmd.append(target)

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
            out = res.stdout
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "loss_pct": 100.0,
                "min_ms": 0.0,
                "avg_ms": 0.0,
                "max_ms": 0.0,
                "jitter_ms": 0.0,
                "raw": "Ping timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "loss_pct": 100.0,
                "min_ms": 0.0,
                "avg_ms": 0.0,
                "max_ms": 0.0,
                "jitter_ms": 0.0,
                "raw": str(e)
            }

        loss_match = re.search(r"(\d+(?:\.\d+)?)%\s+packet loss", out)
        loss = float(loss_match.group(1)) if loss_match else 100.0

        rtt_match = re.search(
            r"rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)\s+ms", out
        )
        if rtt_match:
            rtt_min = float(rtt_match.group(1))
            rtt_avg = float(rtt_match.group(2))
            rtt_max = float(rtt_match.group(3))
            rtt_mdev = float(rtt_match.group(4))
        else:
            rtt_min = rtt_avg = rtt_max = rtt_mdev = 0.0

        return {
            "success": res.returncode == 0 and loss < 100.0,
            "loss_pct": loss,
            "min_ms": rtt_min,
            "avg_ms": rtt_avg,
            "max_ms": rtt_max,
            "jitter_ms": rtt_mdev,
            "raw": out
        }

    def check_wan_connectivity(self, targets: Optional[List[str]] = None) -> bool:
        """Quick check to see if remote WAN is reachable."""
        targets = targets or ["1.1.1.1", "8.8.8.8"]
        for t in targets:
            res = self.run_ping(t, count=2, payload_size=32, timeout_sec=3)
            if res["success"]:
                return True
        return False

    def probe_rf_telemetry(self) -> Dict[str, Any]:
        """Queries router for live RF metrics (RSRP, RSRQ, SNR, EARFCN, PCI, Band)."""
        metrics = {
            "rsrp": -85,
            "rsrq": -10,
            "sinr": 15,
            "earfcn": "N/A",
            "pci": "N/A",
            "band": "auto"
        }
        if not self.client:
            return metrics

        try:
            with SafeSession(self.client):
                if hasattr(self.client, "get_lte_status"):
                    lte = self.client.get_lte_status()
                    rf = getattr(lte, "rf", None)
                    if rf:
                        metrics["rsrp"] = getattr(rf, "rsrp_dbm", getattr(rf, "rsrp", -85))
                        metrics["rsrq"] = getattr(rf, "rsrq_db", getattr(rf, "rsrq", -10))
                        metrics["sinr"] = getattr(rf, "snr_db", getattr(rf, "snr", 15))
                    metrics["earfcn"] = getattr(lte, "earfcn", "N/A")
                    metrics["pci"] = getattr(lte, "pci", "N/A")
                    metrics["band"] = getattr(lte, "band", "auto")
        except Exception as e:
            logger.debug(f"Failed to query RF telemetry: {e}")
        return metrics

    def probe_path_mtu(self) -> Dict[str, Any]:
        """Evaluates Path MTU fragmentation over cellular GTP tunnel."""
        sizes = [
            (1472, 1500, "1500 Standard Ethernet"),
            (1392, 1420, "1420 Clamped GTP Cellular"),
            (1352, 1380, "1380 Conservative Payload")
        ]
        results = {}
        for payload, mtu, label in sizes:
            p = self.run_ping("1.1.1.1", count=2, payload_size=payload, dont_fragment=True, timeout_sec=4)
            frag = p["loss_pct"] == 100.0 or "Frag needed" in p.get("raw", "")
            results[str(mtu)] = {
                "mtu": mtu,
                "label": label,
                "passed": not frag,
                "loss_pct": p["loss_pct"]
            }
        return results

    def calculate_rain_resilience_score(
        self,
        loss_pct: float,
        jitter_ms: float,
        sinr_db: float,
        avg_lat_ms: float,
        band: str
    ) -> float:
        """Calculates multi-objective Rain Resilience Score (0 to 100)."""
        # Base penalty for loss and jitter
        score = 100.0
        score -= (loss_pct * 8.0)
        score -= (jitter_ms * 0.5)

        # Reward for high SINR (cleaner carrier-to-interference)
        score += max(0, min(20.0, sinr_db * 1.0))

        # Latency penalty if exceeding 50ms
        if avg_lat_ms > 40:
            score -= (avg_lat_ms - 40) * 0.25

        # Sub-1GHz physics bonus for tropical monsoon rain
        if band == "8":
            score += 15.0  # 900MHz penetration advantage
        elif band == "40":
            score -= 20.0  # High rain attenuation penalty
        elif band == "1":
            score -= 10.0

        return round(max(0.0, min(100.0, score)), 1)

    def set_band_safe(self, target_band: str) -> bool:
        """Applies band lock to router with hardware detachment handling and 45s watchdog."""
        self._log(f"Requesting band change to Band {target_band.upper()}...")
        if self.dry_run or not self.client:
            self._log(f"[SIMULATION] Mocking switch to Band {target_band.upper()} (4s sleep)...")
            time.sleep(3)
            return True

        # Pre-switch verification
        try:
            with SafeSession(self.client):
                if hasattr(self.client, "set_lte_band"):
                    self.client.set_lte_band(target_band)
                else:
                    self._log("Router client does not support set_lte_band.", "ERROR")
                    return False
        except Exception as e:
            self._log(f"Failed to execute set_lte_band({target_band}): {e}", "ERROR")
            return False

        # Allow modem 3s to initiate radio detachment and RF PLL retuning
        time.sleep(3)

        # 45s Watchdog loop
        self._log(f"Modem detached. Initiating {self.watchdog_timeout}s Watchdog timer...")
        start_time = time.time()
        recovered = False

        while time.time() - start_time < self.watchdog_timeout:
            if self.stop_requested:
                self._log("Stop requested during band transition.", "WARN")
                return False

            elapsed = int(time.time() - start_time)
            remaining = max(0, self.watchdog_timeout - elapsed)
            with self._lock:
                self.state["watchdog_remaining_sec"] = remaining
            self._write_state()

            # Sleep short pulse
            time.sleep(3)

            # Test WAN ping
            if self.check_wan_connectivity():
                recovered = True
                self._log(f"✓ WAN connection successfully re-established on Band {target_band} after {elapsed}s!")
                break
            else:
                self._log(f"Waiting for cellular re-attachment ({elapsed}s elapsed, {remaining}s left)...")

        with self._lock:
            self.state["watchdog_remaining_sec"] = 0
        self._write_state()

        if not recovered:
            self._log(f"⚠️ WATCHDOG TRIGGERED: Band {target_band} failed to restore WAN within {self.watchdog_timeout}s!", "ERROR")
            self._log("Triggering AUTOMATIC FAIL-SAFE ROLLBACK to AUTO roaming mode...", "WARN")
            self.revert_to_auto()
            return False

        return True

    def revert_to_auto(self) -> bool:
        """Emergency revert to default AUTO band roaming."""
        self._log("Reverting router to default AUTO mode...")
        if self.dry_run or not self.client:
            self._log("[SIMULATION] Router set to AUTO mode.")
            return True
        try:
            with SafeSession(self.client):
                if hasattr(self.client, "set_lte_band"):
                    self.client.set_lte_band("auto")
                elif hasattr(self.client, "set_cell_lock"):
                    self.client.set_cell_lock(False)
            self._log("✓ Router successfully reverted to AUTO roaming.")
            return True
        except Exception as e:
            self._log(f"Failed to revert router to auto: {e}", "ERROR")
            return False

    def run_sweep(self) -> Dict[str, Any]:
        """Main calibration sweep executing across all target bands."""
        self.running = True
        self.stop_requested = False

        with self._lock:
            self.state["status"] = "RUNNING"
            self.state["progress_pct"] = 0
            self.state["bands_evaluated"] = []
            self.state["recommendation"] = None
        self._write_state()

        self._log("=" * 60)
        self._log("🚀 Starting Autonomous LTE Band Calibration Sweep")
        self._log(f"Target Gateway: {self.host} | Location: Malabe, Sri Lanka")
        self._log("=" * 60)

        # Step 1: Initialize router client
        self._init_client()

        # Step 2: Gateway LAN Pre-flight check
        self._log("[Phase 1/4] Probing Local Gateway LAN link...")
        gw_ping = self.run_ping("192.168.1.1", count=4, timeout_sec=5)
        if gw_ping["loss_pct"] > 25.0:
            self._log("High local Wi-Fi packet loss to 192.168.1.1. Check local wireless link.", "WARN")
        else:
            self._log(f"Local LAN Wi-Fi link is healthy (avg latency {gw_ping['avg_ms']} ms).")

        # Step 3: Sweep Bands
        total_bands = len(self.bands)
        results = []

        for idx, band in enumerate(self.bands):
            if self.stop_requested:
                self._log("Calibration cancelled by user.", "WARN")
                break

            pct = int(((idx) / total_bands) * 80)
            meta = BAND_METADATA.get(band, {
                "name": f"Band {band}",
                "frequency": "Unknown",
                "rain_penetration": "Unknown",
                "desc": "LTE Carrier"
            })

            with self._lock:
                self.state["current_phase"] = f"EVALUATING_BAND_{band.upper()}"
                self.state["current_band"] = band
                self.state["progress_pct"] = pct
            self._write_state()

            self._log(f"\n[{idx + 1}/{total_bands}] Evaluating {meta['name']} ({meta['frequency']})...")

            # Apply Band Lock
            switch_success = self.set_band_safe(band)
            if not switch_success:
                results.append({
                    "band": band,
                    "name": meta["name"],
                    "frequency": meta["frequency"],
                    "status": "UNAVAILABLE / NO SIGNAL",
                    "loss_pct": 100.0,
                    "jitter_ms": 0.0,
                    "latency_avg_ms": 0.0,
                    "sinr": 0,
                    "rsrp": 0,
                    "rsrq": 0,
                    "rain_score": 0.0,
                    "pass": False
                })
                continue

            # Give connection 3s stabilization after WAN returns
            time.sleep(3)

            # Measure RF Telemetry
            rf = self.probe_rf_telemetry()

            # Measure WAN Latency & Jitter (20-packet burst)
            self._log(f"Benchmarking Cloudflare 1.1.1.1 WAN Link (20 ping samples on Band {band})...")
            ping_stats = self.run_ping("1.1.1.1", count=20, timeout_sec=25)

            # Record live ping point
            live_entry = {
                "band": band,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "latency_ms": ping_stats["avg_ms"],
                "jitter_ms": ping_stats["jitter_ms"],
                "loss_pct": ping_stats["loss_pct"],
                "rsrp": rf["rsrp"],
                "sinr": rf["sinr"]
            }
            with self._lock:
                self.state["live_pings"].append(live_entry)
                if len(self.state["live_pings"]) > 50:
                    self.state["live_pings"].pop(0)
                self.state["active_metrics"] = {
                    "band": band,
                    "rsrp": rf["rsrp"],
                    "rsrq": rf["rsrq"],
                    "sinr": rf["sinr"],
                    "latency_ms": ping_stats["avg_ms"],
                    "jitter_ms": ping_stats["jitter_ms"],
                    "loss_pct": ping_stats["loss_pct"],
                    "mtu_clamped": 1420
                }
            self._write_state()

            # Calculate Rain Score
            rain_score = self.calculate_rain_resilience_score(
                loss_pct=ping_stats["loss_pct"],
                jitter_ms=ping_stats["jitter_ms"],
                sinr_db=rf["sinr"],
                avg_lat_ms=ping_stats["avg_ms"],
                band=band
            )

            record = {
                "band": band,
                "name": meta["name"],
                "frequency": meta["frequency"],
                "status": "ONLINE (TESTED)",
                "loss_pct": ping_stats["loss_pct"],
                "jitter_ms": ping_stats["jitter_ms"],
                "latency_avg_ms": ping_stats["avg_ms"],
                "min_ms": ping_stats["min_ms"],
                "max_ms": ping_stats["max_ms"],
                "sinr": rf["sinr"],
                "rsrp": rf["rsrp"],
                "rsrq": rf["rsrq"],
                "rain_score": rain_score,
                "pass": ping_stats["loss_pct"] < 50.0
            }
            results.append(record)

            with self._lock:
                self.state["bands_evaluated"] = list(results)
            self._write_state()

            self._log(f"  • {meta['name']} -> Loss: {ping_stats['loss_pct']}% | Latency: {ping_stats['avg_ms']}ms | Jitter: {ping_stats['jitter_ms']}ms | Rain Score: {rain_score}/100")

        # Step 4: MTU Testing
        self._log("\n[Phase 3/4] Testing Path MTU Clamping under current weather...")
        mtu_results = self.probe_path_mtu()

        # Step 5: AGY SDK Decision Handoff
        self._log("\n[Phase 4/4] Ingesting Telemetry into Google Antigravity (AGY) Decision Engine...")
        with self._lock:
            self.state["current_phase"] = "AGY_DECISION_SYNTHESIS"
            self.state["progress_pct"] = 90
        self._write_state()

        # Run AGY Decision
        from tplink_router.calibration.agy_agent import AGYDecisionAgent
        agent = AGYDecisionAgent()
        recommendation = agent.evaluate_and_decide(results, mtu_results)

        with self._lock:
            self.state["recommendation"] = recommendation
            self.state["current_phase"] = "COMPLETED"
            self.state["progress_pct"] = 100
            self.state["status"] = "COMPLETED"
        self._write_state()

        # Apply winning band
        winning_band = recommendation["winning_band"]
        self._log(f"\n🏆 AGY Engine Selected: {recommendation['winning_band_name']}!")
        self._log(f"Reasoning: {recommendation['reasoning_summary']}")

        if not self.dry_run and self.client:
            self._log(f"Applying final reconfiguration lock to {winning_band}...")
            self.set_band_safe(winning_band)

        self.running = False
        self._log("✓ Full calibration cycle completed successfully.")
        return self.state

    def stop(self):
        self.stop_requested = True
        self.running = False
        with self._lock:
            self.state["status"] = "STOPPED"
            self.state["message"] = "Calibration sweep cancelled."
        self._write_state()
