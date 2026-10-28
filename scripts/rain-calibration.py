#!/usr/bin/env python3
"""Rain Weather RF & Network Calibration Engine.

Analyzes real-time connection stability, bufferbloat jitter, packet loss,
and Path MTU fragmentation during wet weather / rain conditions in Sri Lanka.
Provides carrier band switching recommendations (Band 8 900MHz vs Band 3 1800MHz).

Author: Dulith Divisekara (SLIIT Malabe)
"""

import os
import re
import subprocess
import sys
import time

GATEWAY_IP = "192.168.1.1"
REMOTE_TARGETS = ["1.1.1.1", "8.8.8.8"]


def run_ping(target, count=20, payload_size=56, dont_fragment=False):
    cmd = ["ping", "-c", str(count), "-s", str(payload_size)]
    if dont_fragment:
        cmd.extend(["-M", "do"])
    cmd.append(target)

    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stdout

    # Parse packet loss
    loss_match = re.search(r"(\d+(?:\.\d+)?)%\s+packet loss", out)
    loss = float(loss_match.group(1)) if loss_match else 100.0

    # Parse rtt min/avg/max/mdev
    rtt_match = re.search(r"rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)\s+ms", out)
    if rtt_match:
        rtt_min = float(rtt_match.group(1))
        rtt_avg = float(rtt_match.group(2))
        rtt_max = float(rtt_match.group(3))
        rtt_mdev = float(rtt_match.group(4))
    else:
        rtt_min = rtt_avg = rtt_max = rtt_mdev = 0.0

    return {
        "success": res.returncode == 0,
        "loss_pct": loss,
        "min_ms": rtt_min,
        "avg_ms": rtt_avg,
        "max_ms": rtt_max,
        "jitter_ms": rtt_mdev,
        "raw": out
    }


def evaluate_mtu():
    print("\n[PROBE] Testing Path MTU Fragmentation under Rain Conditions...")
    sizes = [
        (1472, "1500 MTU (Standard Ethernet)"),
        (1392, "1420 MTU (Recommended GTP Tunnel Clamping)"),
        (1352, "1380 MTU (Conservative Cellular Payload)")
    ]
    results = {}
    for size, label in sizes:
        res = run_ping("1.1.1.1", count=3, payload_size=size, dont_fragment=True)
        fragmented = res["loss_pct"] == 100.0 or "Frag needed" in res["raw"]
        status = "\033[91mFRAGMENTED / DROPPED\033[0m" if fragmented else "\033[92mPASS (0% DROP)\033[0m"
        print(f"  • Packet Size {size + 28}B ({label}): {status}")
        results[size + 28] = not fragmented
    return results


def main():
    print("=" * 65)
    print("  🌧️ TP-Link Router Rain Weather & RF Calibration Engine")
    print("  Location: Malabe, Sri Lanka (SLIIT Campus Zone)")
    print("=" * 65)

    # 1. Test Gateway LAN
    print(f"\n[1/4] Probing Local Gateway ({GATEWAY_IP}) over Wi-Fi...")
    gw_stats = run_ping(GATEWAY_IP, count=5)
    print(f"  • Gateway Latency: avg {gw_stats['avg_ms']} ms | jitter: {gw_stats['jitter_ms']} ms | loss: {gw_stats['loss_pct']}%")

    if gw_stats["loss_pct"] > 0:
        print("  \033[93m[WARN] Local Wi-Fi packet loss detected. Local RF interference present.\033[0m")
    else:
        print("  \033[92m[✓] Local Wi-Fi link is clean and stable.\033[0m")

    # 2. Test WAN Cellular Link
    print("\n[2/4] Probing Cellular WAN Link (Cloudflare 1.1.1.1, 20 packets)...")
    wan_stats = run_ping("1.1.1.1", count=20)
    print(f"  • Cellular Latency: min {wan_stats['min_ms']} ms | avg {wan_stats['avg_ms']} ms | max {wan_stats['max_ms']} ms")
    print(f"  • Jitter (mdev): {wan_stats['jitter_ms']} ms")
    print(f"  • Packet Loss: {wan_stats['loss_pct']}%")

    # 3. Path MTU Evaluation
    mtu_results = evaluate_mtu()

    # 4. Calibration Assessment & Band Recommendation
    print("\n[4/4] 📊 Weather-Specific Radio Calibration Analysis:")
    print("-" * 65)

    # Physics logic for Sri Lankan cellular bands:
    # Hutch Sri Lanka operates primarily on:
    # - LTE Band 3 (1800 MHz): ~15MHz bandwidth, highest peak throughput (20-40Mbps), high rain attenuation.
    # - LTE Band 8 (900 MHz): ~5-10MHz bandwidth, lower frequency, superior rain and wet obstacle penetration.
    # - LTE Band 40 (2300 MHz): TDD, extreme rain fade vulnerability.

    avg_lat = wan_stats["avg_ms"]
    loss = wan_stats["loss_pct"]
    jitter = wan_stats["jitter_ms"]

    if loss > 5.0 or jitter > 50.0:
        recommended_band = "Band 8 (900 MHz FDD)"
        band_reason = "Elevated rain fade / packet loss detected. Sub-1GHz Band 8 offers superior rain and wet canopy penetration."
        action_cmd = "tplink-cli cell-lock --band 8"
    else:
        recommended_band = "Band 3 (1800 MHz FDD)"
        band_reason = "Radio conditions are currently stable. Band 3 delivers maximum channel bandwidth (up to 20Mbps cap)."
        action_cmd = "tplink-cli cell-lock --band 3"

    print(f"  • Recommended Carrier Band: \033[92m{recommended_band}\033[0m")
    print(f"  • Technical Reason:         {band_reason}")
    print(f"  • Recommended Action:       \033[96m{action_cmd}\033[0m")
    print(f"  • Clamping Recommendation:  Set MTU to 1420 bytes on active Wi-Fi interface (prevents cellular GTP fragmentation)")
    print("-" * 65)

    # Check active TCP congestion control
    try:
        with open("/proc/sys/net/ipv4/tcp_congestion_control", "r") as f:
            cc = f.read().strip()
        print(f"  • Host TCP Congestion Control: \033[94m{cc}\033[0m {'(BBR active ✓)' if cc == 'bbr' else '(Run optimize-network to enable BBR)'}")
    except Exception:
        pass

    print("\n[✓] Calibration analysis complete.\n")


if __name__ == "__main__":
    main()
