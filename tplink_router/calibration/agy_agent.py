"""Google Antigravity (AGY) SDK Decision Engine for Cellular Band Optimization.

Evaluates multi-band RF and ping telemetry matrix under Sri Lanka rain weather conditions,
weighs rain attenuation penalties vs carrier bandwidth, and autonomously selects the
highest-performing LTE band.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class AGYDecisionAgent:
    """Agentic Decision Engine implementing the Google Antigravity SDK decision model."""

    def __init__(self, location: str = "Malabe, Sri Lanka (SLIIT Campus Zone)"):
        self.location = location
        self.carrier = "Hutch Sri Lanka (20 Mbps Unlimited LTE)"

    def evaluate_and_decide(
        self,
        bands_data: List[Dict[str, Any]],
        mtu_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculates multi-objective utility scores and synthesizes AGY reasoning."""
        if not bands_data:
            return {
                "winning_band": "auto",
                "winning_band_name": "AUTO Roaming",
                "utility_score": 50.0,
                "reasoning_summary": "No band telemetry available. Defaulting to AUTO.",
                "markdown_report": "No measurements collected.",
                "actions_recommended": ["tplink-cli band auto"]
            }

        scored_candidates = []

        for b in bands_data:
            band_id = str(b.get("band", "auto"))
            loss = float(b.get("loss_pct", 100.0))
            jitter = float(b.get("jitter_ms", 999.0))
            lat = float(b.get("latency_avg_ms", 999.0))
            sinr = float(b.get("sinr", 0.0))
            rain_score = float(b.get("rain_score", 0.0))

            if loss >= 80.0:
                # Carrier unavailable
                utility = 0.0
            else:
                # Multi-objective utility calculation tailored for Hutch 20Mbps throttled plan
                # Since speed is capped at 20Mbps, stability & low jitter vastly outweigh raw bandwidth!
                w_loss = 0.40
                w_jitter = 0.30
                w_rain = 0.20
                w_lat = 0.10

                loss_term = max(0.0, 100.0 - loss)
                jitter_term = min(100.0, 50.0 / (1.0 + (jitter / 10.0)) * 2.0)
                lat_term = min(100.0, (100.0 / max(25.0, lat)) * 40.0)

                utility = (
                    (w_loss * loss_term) +
                    (w_jitter * jitter_term) +
                    (w_rain * rain_score) +
                    (w_lat * lat_term)
                )

            scored_candidates.append({
                "band": band_id,
                "name": b.get("name", f"Band {band_id}"),
                "frequency": b.get("frequency", "Unknown"),
                "utility": round(utility, 1),
                "rain_score": rain_score,
                "loss_pct": loss,
                "jitter_ms": jitter,
                "latency_avg_ms": lat,
                "sinr": sinr,
                "raw": b
            })

        # Sort by utility score descending
        scored_candidates.sort(key=lambda x: x["utility"], reverse=True)
        winner = scored_candidates[0]

        # Determine if rain condition is active
        high_band_failures = [c for c in scored_candidates if c["band"] in ["3", "40"] and c["loss_pct"] > 5.0]
        rain_attenuation_detected = len(high_band_failures) > 0

        # Construct Agentic Reasoning Synthesis
        winning_band = winner["band"]
        winning_name = winner["name"]

        if winning_band == "8":
            reasoning = (
                f"Sub-1GHz Band 8 (900 MHz) selected as the winning carrier with a top utility score of {winner['utility']}/100. "
                f"During rainy weather in Malabe, 900 MHz exhibits superior rain penetration with {winner['loss_pct']}% packet loss "
                f"and {winner['jitter_ms']}ms jitter, vastly outperforming high-frequency carriers experiencing rain fade."
            )
        elif winning_band == "3":
            reasoning = (
                f"Band 3 (1800 MHz) selected as the winning carrier with a top utility score of {winner['utility']}/100. "
                f"Radio link telemetry indicates favorable channel conditions with low packet loss ({winner['loss_pct']}%) "
                f"and stable latency ({winner['latency_avg_ms']}ms), allowing maximum utilization of Hutch's 20 Mbps unlimited tier."
            )
        else:
            reasoning = (
                f"{winning_name} demonstrated the best overall link stability (Utility {winner['utility']}/100) "
                f"with {winner['loss_pct']}% packet loss and {winner['jitter_ms']}ms jitter."
            )

        # Markdown Report Generation
        md_lines = [
            f"# 🧠 Google Antigravity (AGY) Autonomous Calibration Report",
            f"",
            f"- **Location**: {self.location}",
            f"- **Carrier**: {self.carrier}",
            f"- **Rain Attenuation Status**: {'🌧️ ACTIVE (High-frequency bands degraded)' if rain_attenuation_detected else '☀️ MINIMAL (Clear line of sight)'}",
            f"- **Winning Carrier**: **{winning_name}** (Utility: `{winner['utility']}/100`)",
            f"",
            f"### 📊 Multi-Band Telemetry & Utility Ranking",
            f"",
            f"| Rank | Band | Frequency | Packet Loss | Avg Latency | Jitter | Rain Score | Utility Score |",
            f"| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
        ]

        for rank, c in enumerate(scored_candidates, start=1):
            star = "🏆 " if rank == 1 else ""
            md_lines.append(
                f"| {star}#{rank} | {c['name']} | {c['frequency']} | {c['loss_pct']}% | {c['latency_avg_ms']} ms | {c['jitter_ms']} ms | {c['rain_score']}/100 | **{c['utility']}** |"
            )

        md_lines.extend([
            f"",
            f"### 💡 AGY Decision Engine Reasoning",
            f"> {reasoning}",
            f"",
            f"### ⚙️ Recommended Autonomous Actions",
            f"1. **Lock Router Band**: `tplink-cli band {winning_band}`",
            f"2. **Enable Path MTU Clamping (1420 bytes)**: Clamps Wi-Fi interface to match cellular GTP encapsulation.",
            f"3. **Enable Linux TCP BBR**: `sudo ./scripts/optimize-network.sh enable` for bufferbloat mitigation.",
            f"4. **DNS Server Locking**: Primary `8.8.8.8`, Secondary `1.1.1.1`.",
        ])

        markdown_report = "\n".join(md_lines)

        return {
            "winning_band": winning_band,
            "winning_band_name": winning_name,
            "utility_score": winner["utility"],
            "reasoning_summary": reasoning,
            "candidates_ranking": scored_candidates,
            "rain_attenuation_detected": rain_attenuation_detected,
            "markdown_report": markdown_report,
            "actions_recommended": [
                f"tplink-cli band {winning_band}",
                "tplink-cli dns set 8.8.8.8 1.1.1.1",
                "sudo ./scripts/optimize-network.sh enable"
            ]
        }
