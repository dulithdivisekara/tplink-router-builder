"""Unit tests for Autonomous Router Calibration, Dashboard Server, and AGY Decision Engine."""

import unittest
from unittest.mock import patch

from tplink_router.calibration.engine import RouterCalibrator
from tplink_router.calibration.agy_agent import AGYDecisionAgent


class TestCalibrationEngine(unittest.TestCase):

    def setUp(self):
        self.calibrator = RouterCalibrator(
            host="http://192.168.1.1",
            bands=["8", "3", "auto"],
            watchdog_timeout=5,
            dry_run=True
        )

    def test_rain_resilience_scoring(self):
        # Band 8 in rain (low loss, moderate jitter, good SINR, sub-1GHz bonus)
        score_b8 = self.calibrator.calculate_rain_resilience_score(
            loss_pct=0.0,
            jitter_ms=5.0,
            sinr_db=18.0,
            avg_lat_ms=30.0,
            band="8"
        )
        self.assertGreaterEqual(score_b8, 90.0)

        # Band 40 in rain (high loss, severe jitter, rain attenuation penalty)
        score_b40 = self.calibrator.calculate_rain_resilience_score(
            loss_pct=25.0,
            jitter_ms=120.0,
            sinr_db=5.0,
            avg_lat_ms=350.0,
            band="40"
        )
        self.assertLess(score_b40, 30.0)

    def test_agy_decision_agent(self):
        agent = AGYDecisionAgent()
        bands_data = [
            {
                "band": "8",
                "name": "Band 8 (900 MHz FDD)",
                "frequency": "900 MHz",
                "loss_pct": 0.0,
                "jitter_ms": 6.2,
                "latency_avg_ms": 32.5,
                "sinr": 18.0,
                "rain_score": 95.0
            },
            {
                "band": "3",
                "name": "Band 3 (1800 MHz FDD)",
                "frequency": "1800 MHz",
                "loss_pct": 20.0,
                "jitter_ms": 95.0,
                "latency_avg_ms": 180.0,
                "sinr": 8.0,
                "rain_score": 15.0
            }
        ]
        decision = agent.evaluate_and_decide(bands_data, {})
        self.assertEqual(decision["winning_band"], "8")
        self.assertIn("Band 8", decision["winning_band_name"])
        self.assertTrue(decision["rain_attenuation_detected"])
        self.assertIn("Autonomous Calibration Report", decision["markdown_report"])
        self.assertIn("tplink-cli band 8", decision["actions_recommended"])

    @patch.object(RouterCalibrator, "run_ping")
    def test_calibrator_dry_run_sweep(self, mock_ping):
        mock_ping.return_value = {
            "success": True,
            "loss_pct": 0.0,
            "min_ms": 25.0,
            "avg_ms": 32.0,
            "max_ms": 45.0,
            "jitter_ms": 4.0,
            "raw": "mock"
        }
        res = self.calibrator.run_sweep()
        self.assertEqual(res["status"], "COMPLETED")
        self.assertIsNotNone(res["recommendation"])
        self.assertEqual(len(res["bands_evaluated"]), 3)

    def test_revert_to_auto(self):
        success = self.calibrator.revert_to_auto()
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
