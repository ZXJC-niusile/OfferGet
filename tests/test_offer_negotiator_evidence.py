"""
Unit test suite for Offer Negotiator Evidence Gate & Legal Compliance (core.offer_negotiator).
P0.5 Evidence Gate, fact grounding, softened legal assertions, and backward compatibility.
"""

import json
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.offer_negotiator import (
    OfferNegotiator,
    evaluate_offer_package,
    COMPLIANCE_DISCLAIMER,
)

FORBIDDEN_TECH_BUZZWORDS = [
    "千卡",
    "万卡",
    "3800万",
    "GRPO",
    "vLLM",
    "NCCL",
]


class TestOfferNegotiatorEvidenceGate(unittest.TestCase):

    def setUp(self):
        self.negotiator = OfferNegotiator()

        self.sample_offer_path = PROJECT_ROOT / "examples" / "sample_offer.json"
        self.sample_profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"

        with open(self.sample_offer_path, "r", encoding="utf-8") as f:
            self.offer_data = json.load(f)

        with open(self.sample_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

    def test_01_empty_profile_no_hallucinated_claims(self):
        """Test that an empty candidate profile produces zero hallucinated tech buzzwords."""
        generic_offer = {
            "company": "泛互联网科技公司",
            "role": "通用研发工程师",
            "base_salary_monthly": 30000.0,
            "months_per_year": 14.0,
        }
        eval_result = self.negotiator.evaluate_offer(generic_offer, candidate_profile={})
        counter = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=35000.0,
            competing_offers=[],
            candidate_profile={},
        )

        letter_zh = counter["counter_offer_letter"]
        letter_en = counter["counter_offer_letter_en"]
        verbal_script = counter["verbal_negotiation_script"]
        leverage_points = counter["tactical_leverage_points"]

        # Absolutely none of the forbidden buzzwords should appear anywhere in the generated letters/script
        for buzzword in FORBIDDEN_TECH_BUZZWORDS:
            self.assertNotIn(buzzword, letter_zh, f"Found '{buzzword}' in Chinese letter for empty profile!")
            self.assertNotIn(buzzword, letter_en, f"Found '{buzzword}' in English letter for empty profile!")
            for phase_name, text in verbal_script.items():
                self.assertNotIn(buzzword, text, f"Found '{buzzword}' in verbal_script phase '{phase_name}'!")
            for pt in leverage_points:
                self.assertNotIn(buzzword, pt, f"Found '{buzzword}' in tactical_leverage_points!")

        # Check Evidence Gate signals
        self.assertEqual(counter["grounded_claims"], [])
        self.assertTrue(len(counter["unsupported_claims"]) >= 2)
        self.assertTrue(any("外部竞争 Offer" in c for c in counter["unsupported_claims"]))
        self.assertTrue(any("量化" in c for c in counter["unsupported_claims"]))
        self.assertTrue(len(counter["pending_questions"]) >= 2)

    def test_02_non_llm_product_manager_profile(self):
        """Test that a Product Manager profile with real metrics only cites PM metrics and no LLM buzzwords."""
        pm_profile = {
            "candidate": {
                "name": "林青",
                "title_zh": "资深产品经理 / 产品专家",
            },
            "experience": [
                {
                    "company": "某知名电商平台",
                    "role": "用户增长产品专家",
                    "highlights": [
                        {
                            "claim_zh": "主导裂变交易漏斗重构，支付转化率提升 16.8%，季度带动 GMV 增长 4500 万元。",
                            "verified_metrics": {"conversion_rate": "+16.8%", "gmv": "4500万"}
                        }
                    ]
                }
            ]
        }
        pm_offer = {
            "company": "某生活消费巨头",
            "role": "增长产品总监",
            "base_salary_monthly": 55000.0,
            "months_per_year": 15.0,
        }

        eval_result = self.negotiator.evaluate_offer(pm_offer, candidate_profile=pm_profile)
        counter = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=65000.0,
            competing_offers=[],
            candidate_profile=pm_profile,
        )

        letter_zh = counter["counter_offer_letter"]

        # Absolutely no LLM tech buzzwords
        for buzzword in FORBIDDEN_TECH_BUZZWORDS:
            self.assertNotIn(buzzword, letter_zh, f"PM letter contains unexpected buzzword: '{buzzword}'!")

        # Grounded claims must capture the PM's real verified metrics
        self.assertTrue(len(counter["grounded_claims"]) >= 1)
        self.assertIn("支付转化率提升 16.8%", counter["grounded_claims"][0])
        self.assertIn("支付转化率提升 16.8%", letter_zh)
        self.assertIn("4500 万元", letter_zh)

    def test_03_non_llm_operations_profile(self):
        """Test that an operations manager profile has real ops claims extracted and zero LLM buzzwords."""
        ops_profile = {
            "candidate": {
                "name": "陈晓",
                "title_zh": "高级私域运营专家",
            },
            "experience": [
                {
                    "company": "某数字零售公司",
                    "role": "私域用户运营负责人",
                    "highlights": [
                        "主导百万级私域社群精细化运营，高价值用户次月复购率提升 24.5%，客单价同比提升 32%"
                    ]
                }
            ]
        }
        ops_offer = {
            "company": "新零售独角兽",
            "role": "用户运营总监",
            "base_salary_monthly": 45000.0,
            "months_per_year": 14.0,
        }

        eval_result = self.negotiator.evaluate_offer(ops_offer, candidate_profile=ops_profile)
        counter = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=52000.0,
            competing_offers=[],
            candidate_profile=ops_profile,
        )

        letter_zh = counter["counter_offer_letter"]
        for buzzword in FORBIDDEN_TECH_BUZZWORDS:
            self.assertNotIn(buzzword, letter_zh)

        self.assertTrue(len(counter["grounded_claims"]) >= 1)
        self.assertIn("次月复购率提升 24.5%", counter["grounded_claims"][0])
        self.assertIn("复购率提升 24.5%", letter_zh)

    def test_04_real_high_concurrency_backend_grounded_claims(self):
        """Test that real high concurrency backend architecture claims are correctly grounded."""
        backend_profile = {
            "candidate": {
                "name": "周建国",
                "title_zh": "资深高并发基础架构师",
            },
            "experience": [
                {
                    "company": "某一线云计算大厂",
                    "role": "分布式网关架构师",
                    "highlights": [
                        {
                            "claim_zh": "重构API网关核心集群，单集群吞吐达 30 万 QPS，核心路径延迟下降 45%，全年保持 99.999% 可用性。",
                            "verified_metrics": {"qps": 300000, "latency_reduction": "45%", "sla": "99.999%"}
                        }
                    ]
                }
            ]
        }
        backend_offer = {
            "company": "某金融科技公司",
            "role": "基础架构负责人",
            "base_salary_monthly": 70000.0,
            "months_per_year": 16.0,
        }

        eval_result = self.negotiator.evaluate_offer(backend_offer, candidate_profile=backend_profile)
        counter = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=80000.0,
            competing_offers=[{
                "company": "某一线开源云厂商",
                "package_annual": 1600000,
                "base_monthly": 85000,
            }],
            candidate_profile=backend_profile,
        )

        # Cites real backend metrics
        self.assertTrue(len(counter["grounded_claims"]) >= 2)
        self.assertTrue(any("30 万 QPS" in c for c in counter["grounded_claims"]))
        self.assertTrue(any("某一线开源云厂商" in c for c in counter["grounded_claims"]))

        letter_zh = counter["counter_offer_letter"]
        self.assertIn("30 万 QPS", letter_zh)
        self.assertIn("某一线开源云厂商", letter_zh)

        # Zero forbidden LLM buzzwords (千卡, 3800万, GRPO, vLLM, NCCL)
        for buzzword in FORBIDDEN_TECH_BUZZWORDS:
            self.assertNotIn(buzzword, letter_zh)

    def test_05_competing_offer_evidence_gate(self):
        """Test competing offers properly gate claims between grounded and unsupported."""
        clean_offer = {
            "company": "某科技集团",
            "role": "架构师",
            "base_salary_monthly": 60000.0,
            "months_per_year": 15.0,
        }
        eval_result = self.negotiator.evaluate_offer(clean_offer)

        # Scenario A: Has competing offers
        counter_with_comp = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=70000.0,
            competing_offers=[{"company": "竞品独角兽公司", "package_annual": 1350000, "base_monthly": 72000}]
        )
        self.assertTrue(any("竞品独角兽公司" in c for c in counter_with_comp["grounded_claims"]))
        self.assertIn("竞品独角兽公司", counter_with_comp["counter_offer_letter"])
        self.assertFalse(any("外部竞争 Offer" in c for c in counter_with_comp["unsupported_claims"]))

        # Scenario B: No competing offers
        counter_without_comp = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=70000.0,
            competing_offers=[]
        )
        self.assertTrue(any("外部竞争 Offer" in c for c in counter_without_comp["unsupported_claims"]))
        self.assertNotIn("竞品独角兽公司", counter_without_comp["counter_offer_letter"])
        self.assertIn("外部市场分位与行业薪酬带宽", counter_without_comp["counter_offer_letter"])

    def test_06_compliance_disclaimers_and_trap_softening(self):
        """Test compliance disclaimers are properly attached and legal assertions are softened."""
        result = self.negotiator.evaluate_offer(self.offer_data, self.profile_data)
        counter = self.negotiator.generate_counter_offer(result, target_base=90000.0)

        # Top-level disclaimers
        self.assertIn("compliance_disclaimer", result)
        self.assertEqual(result["compliance_disclaimer"], COMPLIANCE_DISCLAIMER)
        self.assertIn("compliance_disclaimer", counter)
        self.assertEqual(counter["compliance_disclaimer"], COMPLIANCE_DISCLAIMER)

        # Narrative contains disclaimer
        self.assertIn(COMPLIANCE_DISCLAIMER, result["evaluation_narrative"])

        # Every detected trap contains the disclaimer
        self.assertEqual(len(result["detected_traps"]), 6)
        for trap in result["detected_traps"]:
            self.assertIn("compliance_disclaimer", trap)
            self.assertEqual(trap["compliance_disclaimer"], COMPLIANCE_DISCLAIMER)
            # Ensure absolutist aggressive assertions are removed
            self.assertNotIn("属于严重违反《社会保险法》的违法条款", trap["issue_summary"])
            self.assertNotIn("该条款涉嫌违法且剥夺劳动者法定补偿权", trap["issue_summary"])
            self.assertNotIn("霸王条款", trap["negotiation_countermeasure"])

    def test_07_full_backward_compatibility_and_aliases(self):
        """Test that all historical return keys and aliases exist and match."""
        eval_result = self.negotiator.evaluate_offer(self.offer_data, self.profile_data)
        counter = self.negotiator.generate_counter_offer(eval_result, target_base=90000.0)

        # Required fields in prompt
        self.assertIn("chinese_letter", counter)
        self.assertIn("english_letter", counter)
        self.assertIn("verbal_script", counter)
        self.assertIn("detected_traps", counter)
        self.assertIn("target_base", counter)
        self.assertIn("grounded_claims", counter)
        self.assertIn("unsupported_claims", counter)
        self.assertIn("pending_questions", counter)
        self.assertIn("compliance_disclaimer", counter)

        # Aliases equality
        self.assertEqual(counter["chinese_letter"], counter["counter_offer_letter"])
        self.assertEqual(counter["english_letter"], counter["counter_offer_letter_en"])
        self.assertEqual(counter["verbal_script"], counter["verbal_negotiation_script"])

        # Method generate_counter_offer_letter works
        letter_zh = self.negotiator.generate_counter_offer_letter(eval_result, target_base=90000.0, lang="zh")
        letter_en = self.negotiator.generate_counter_offer_letter(eval_result, target_base=90000.0, lang="en")
        self.assertEqual(letter_zh, counter["counter_offer_letter"])
        self.assertEqual(letter_en, counter["counter_offer_letter_en"])


if __name__ == "__main__":
    unittest.main()
