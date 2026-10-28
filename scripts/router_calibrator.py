#!/usr/bin/env python3
"""Autonomous TP-Link Router Cellular Calibration & Web Dashboard Daemon.

Executes disconnection-safe RF calibration across LTE bands (Band 8, 3, 1, 40, Auto),
serves the real-time live Web UI on http://localhost:8765, and applies the Google
Antigravity (AGY) SDK decision model to lock the highest-performing carrier band.

Usage:
    # 1. Run with live Web UI (Recommended):
    python3 scripts/router_calibrator.py --web

    # 2. Run with automated start:
    python3 scripts/router_calibrator.py --web --auto-start

    # 3. Dry-run simulation mode (safe testing):
    python3 scripts/router_calibrator.py --web --dry-run

Author: Dulith Divisekara (SLIIT Malabe)
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure root package is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tplink_router.calibration.engine import RouterCalibrator, DEFAULT_BANDS, DEFAULT_WATCHDOG_SEC
from tplink_router.calibration.dashboard import start_dashboard_server
from tplink_router.core.config import ConfigManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("router_calibrator")


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous TP-Link Cellular Calibration & Web Dashboard (SLIIT Malabe)"
    )
    parser.add_argument("--host", default=os.getenv("TPLINK_ROUTER_IP", "http://192.168.1.1"), help="Router IP")
    parser.add_argument("--password", default=os.getenv("TPLINK_PASSWORD"), help="Router Admin Password")
    parser.add_argument("--username", default=os.getenv("TPLINK_USERNAME", "admin"), help="Router Admin Username")
    parser.add_argument("--web", action="store_true", default=True, help="Launch real-time Web UI dashboard")
    parser.add_argument("--port", type=int, default=8765, help="Web Dashboard Port (default: 8765)")
    parser.add_argument("--bands", default=",".join(DEFAULT_BANDS), help="Comma-separated bands (default: 8,3,1,40,auto)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_WATCHDOG_SEC, help="Watchdog timeout in seconds (default: 45)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate band switches without modem detachment")
    parser.add_argument("--auto-start", action="store_true", help="Automatically trigger sweep upon start")

    args = parser.parse_args()

    # Resolve credentials via ConfigManager if not passed
    cfg = ConfigManager().load(cli_host=args.host, cli_username=args.username, cli_password=args.password)
    password = cfg.get("password") or args.password

    target_bands = [b.strip() for b in args.bands.split(",") if b.strip()]

    print("=" * 70)
    print("  🛰️  TP-LINK AUTONOMOUS CELLULAR CALIBRATION & AGY DECISION ENGINE")
    print("  Location: Malabe, Sri Lanka (SLIIT Campus Zone) • Hutch 20Mbps LTE")
    print("  Author  : Dulith Divisekara (https://dulith.me)")
    print("=" * 70)
    print(f"  • Gateway Target       : {args.host}")
    print(f"  • Candidate Bands      : {', '.join(target_bands)}")
    print(f"  • 45s Watchdog Guard   : ACTIVE (Auto-revert to AUTO on WAN drop)")
    print(f"  • Live Web Dashboard   : http://localhost:{args.port}/")
    print(f"  • Dry-Run Simulation   : {'ON' if args.dry_run else 'OFF (Live Hardware Mode)'}")
    print("-" * 70)

    # Initialize Calibrator
    calibrator = RouterCalibrator(
        host=args.host,
        password=password,
        username=args.username,
        bands=target_bands,
        watchdog_timeout=args.timeout,
        dry_run=args.dry_run,
    )

    if args.web:
        print(f"\n🌐 Starting Live Web Dashboard at: \033[96mhttp://localhost:{args.port}/\033[0m")
        print("   You can watch real-time RF gauges, latency oscilloscopes, and matrix updates live!")
        server = start_dashboard_server(calibrator=calibrator, port=args.port, blocking=False)

        if args.auto_start:
            print("\n▶ Auto-start flag specified. Beginning autonomous calibration sweep...")
            calibrator.run_sweep()
            print(f"\n✓ Sweep complete! Dashboard remains live at http://localhost:{args.port}/ (Press Ctrl+C to stop)")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down dashboard...")
                server.shutdown()
        else:
            print("\n👉 Calibrator is ready and awaiting instructions!")
            print(f"   Open \033[96mhttp://localhost:{args.port}/\033[0m in your browser and click \033[92m[▶ Start Calibration]\033[0m")
            print("   (Or press Ctrl+C to exit)\n")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down dashboard...")
                server.shutdown()
    else:
        print("\n▶ Running in headless terminal mode...")
        calibrator.run_sweep()


if __name__ == "__main__":
    main()
