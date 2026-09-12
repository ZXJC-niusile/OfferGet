"""
Unit test suite for Offer Negotiator (core.offer_negotiator).
"""

import os
import sys
import json
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.offer_negotiator import OfferNegotiator, evaluate_offer_package


class TestOfferNegotiator(unittest.TestCase):

    def setUp(self):
        self.sample_offer_path = PROJECT_ROOT / "examples" / "sample_offer.json"
        self.sample_profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"

        with open(self.sample_offer_path, "r", encoding="utf-8") as f:
            self.offer_data = json.load(f)

        with open(self.sample_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        self.negotiator = OfferNegotiator()

    def test_01_total_compensation_breakdown(self):
        result = self.negotiator.evaluate_offer(self.offer_data, self.profile_data)
        comp = result["total_compensation"]

        self.assertEqual(comp["monthly_base"], 75000.0)
        self.assertEqual(comp["months_per_year"], 15.0)
        self.assertEqual(comp["annual_base"], 1125000.0)
        self.assertEqual(comp["monthly_guaranteed_base"], 37500.0)
        self.assertEqual(comp["monthly_floating_kpi"], 37500.0)
        self.assertEqual(comp["guaranteed_annual_cash"], 562500.0)
        self.assertEqual(comp["target_bonus_annual"], 225000.0)
        self.assertEqual(comp["sign_on_bonus"], 50000.0)
        self.assertEqual(comp["stock_rsu_total"], 800000.0)
        self.assertEqual(comp["stock_rsu_annualized"], 200000.0)
        self.assertEqual(comp["total_annual_cash"], 1400000.0)
        self.assertGreater(comp["total_annual_package"], 1600000.0)
        self.assertGreater(comp["cash_ratio"], 0.7)

    def test_02_all_six_contract_traps_detected(self):
        result = self.negotiator.evaluate_offer(self.offer_data, self.profile_data)
        detected_ids = [t["trap_id"] for t in result["detected_traps"]]

        self.assertIn("TRAP_01_PROBATION", detected_ids)
        self.assertIn("TRAP_02_NON_COMPETE", detected_ids)
        self.assertIn("TRAP_03_SALARY_SPLIT", detected_ids)
        self.assertIn("TRAP_04_EQUITY_CLIFF", detected_ids)
        self.assertIn("TRAP_05_OVERTIME", detected_ids)
        self.assertIn("TRAP_06_SALARY_DISCREPANCY", detected_ids)

        self.assertEqual(result["trap_count"], 6)
        self.assertEqual(result["risk_level"], "CRITICAL")
        self.assertLessEqual(result["overall_score"], 40.0)

    def test_03_clean_offer_no_false_positives(self):
        clean_offer = {
            "company": "标杆头部科技集团",
            "role": "资深算法架构师",
            "base_salary_monthly": 90000.0,
            "months_per_year": 16.0,
            "performance_split": {
                "fixed_ratio": 0.85,
                "floating_ratio": 0.15,
            },
            "target_bonus_months": 4.0,
            "sign_on_bonus": 100000.0,
            "stock_rsu": {
                "total_grant_value": 1200000.0,
                "vesting_years": 4,
                "cliff_years": 1,
                "vesting_schedule": "标准 1 年 Cliff，后续按季度均摊归属",
                "repurchase_clause": "离职时已归属期权可由员工保留或按公允市场价值由公司回购",
            },
            "probation": {
                "duration_months": 3,
                "salary_discount_rate": 1.0,
                "pay_social_insurance": True,
            },
            "non_compete": {
                "applies": True,
                "duration_months": 12,
                "monthly_compensation_rate": 0.35,
                "compensation_included_in_salary": False,
                "scope": "双方约定的 3 家直接竞品公司名单",
            },
            "working_hours_overtime": {
                "system": "standard",
                "overtime_pay": "statutory",
            },
            "candidate_expected": {
                "expected_base_monthly": 90000.0,
            }
        }
        result = self.negotiator.evaluate_offer(clean_offer)
        self.assertEqual(result["trap_count"], 0)
        self.assertEqual(result["risk_level"], "LOW")
        self.assertGreaterEqual(result["overall_score"], 90.0)

    def test_04_counter_offer_generation(self):
        eval_result = self.negotiator.evaluate_offer(self.offer_data, self.profile_data)
        counter = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=90000.0,
            competing_offers=[{
                "company": "竞品顶级自动驾驶大厂",
                "package_annual": 1850000,
                "base_monthly": 95000
            }]
        )

        self.assertEqual(counter["target_base"], 90000.0)
        self.assertEqual(counter["base_increment"], 15000)
        self.assertEqual(counter["base_increment_pct"], 20.0)

        # Counter offer letter
        self.assertIn("90,000", counter["counter_offer_letter"])
        self.assertIn("竞品顶级自动驾驶大厂", counter["counter_offer_letter"])
        self.assertIn("Sign-on Bonus", counter["counter_offer_letter"])

        # Verbal script
        script = counter["verbal_negotiation_script"]
        self.assertIn("opening_and_anchor", script)
        self.assertIn("leverage_presentation", script)
        self.assertIn("the_ask_compensation", script)
        self.assertIn("trap_rectification_points", script)
        self.assertIn("closing_and_commitment", script)

        # Trap remedy requests
        self.assertEqual(len(counter["trap_remedy_requests"]), 6)
        self.assertGreaterEqual(len(counter["tactical_leverage_points"]), 3)

    def test_05_convenience_function(self):
        result = evaluate_offer_package(self.offer_data)
        self.assertIn("total_compensation", result)
        self.assertIn("contract_traps", result)
        self.assertIn("overall_score", result)


if __name__ == "__main__":
    unittest.main()
