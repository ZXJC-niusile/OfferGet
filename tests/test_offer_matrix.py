"""
Comprehensive Unit Test Suite for Offer Matrix & Compensation Negotiation.
Consolidates:
1. Multi-Offer comparison matrix, double-side housing fund, effective hourly rate.
2. Total compensation breakdown, contract trap detection (6 major traps), counter offers.
3. Offer negotiator evidence gating, hallucination prevention, and legal compliance disclaimers.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.offer_comparator import (
    CalculatedOfferMetrics,
    OfferComparator,
    OfferComparisonReport,
    OfferEntity,
)
from core.offer_negotiator import (
    COMPLIANCE_DISCLAIMER,
    OfferNegotiator,
    evaluate_offer_package,
)


# ============================================================================
# 1. Multi-Offer Comparator & Effective Hourly Rate
# ============================================================================

@pytest.fixture
def sample_offers():
    offer_a = OfferEntity(
        company_name="某一线大厂 (996高薪)",
        role_title="高级后端工程师",
        city="北京",
        base_monthly_salary=35000.0,
        salary_months=16.0,
        annual_bonus_expected=70000.0,
        sign_on_bonus=30000.0,
        equity_rsu_annual=80000.0,
        housing_fund_rate=0.12,
        housing_fund_base_capped=True,
        weekly_work_hours=60.0,
        daily_commute_hours=2.0,
        monthly_rent_or_commute_cost=5500.0,
        career_growth_score=8.5,
        stability_score=7.0,
    )
    offer_b = OfferEntity(
        company_name="某外企独角兽 (WLB神仙厂)",
        role_title="研发工程师",
        city="上海",
        base_monthly_salary=28000.0,
        salary_months=15.0,
        annual_bonus_expected=30000.0,
        sign_on_bonus=0.0,
        equity_rsu_annual=20000.0,
        housing_fund_rate=0.12,
        housing_fund_base_capped=True,
        weekly_work_hours=40.0,
        daily_commute_hours=1.0,
        monthly_rent_or_commute_cost=3500.0,
        career_growth_score=8.0,
        stability_score=9.0,
    )
    offer_c = OfferEntity(
        company_name="初创AIGC团队 (期权大包)",
        role_title="核心算法研发",
        city="杭州",
        base_monthly_salary=22000.0,
        salary_months=13.0,
        annual_bonus_expected=20000.0,
        sign_on_bonus=0.0,
        equity_rsu_annual=150000.0,
        housing_fund_rate=0.05,
        housing_fund_base_capped=False,
        weekly_work_hours=55.0,
        daily_commute_hours=1.5,
        monthly_rent_or_commute_cost=3000.0,
        career_growth_score=9.0,
        stability_score=5.0,
    )
    return [offer_a, offer_b, offer_c]


class TestOfferComparator:
    def test_single_offer_evaluation(self, sample_offers):
        comparator = OfferComparator()
        offer_b = sample_offers[1]
        metrics = comparator.evaluate_single_offer(offer_b)

        assert isinstance(metrics, CalculatedOfferMetrics)
        assert metrics.annual_cash_base == 420000.0
        assert metrics.annual_total_cash == 450000.0
        assert metrics.annual_housing_fund_total == 80640.0
        assert metrics.effective_hourly_rate > 150.0
        assert any("工作时间规范" in p for p in metrics.pros)

    def test_compare_multiple_offers(self, sample_offers):
        comparator = OfferComparator()
        report = comparator.compare(sample_offers)

        assert isinstance(report, OfferComparisonReport)
        assert len(report.offers) == 3
        assert len(report.ranked_companies) == 3
        assert "某一线大厂" in report.best_cash_flow
        assert "某外企独角兽" in report.best_hourly_rate
        assert "| 公司与岗位 |" in report.comparison_table_md
        assert report.recommendation_summary

    def test_compare_empty_raises_error(self):
        comparator = OfferComparator()
        with pytest.raises(ValueError, match="至少需要提供一个 Offer"):
            comparator.compare([])


# ============================================================================
# 2. Offer Negotiator, Compensation Breakdown & Trap Detection
# ============================================================================

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

        self.assertIn("90,000", counter["counter_offer_letter"])
        self.assertIn("竞品顶级自动驾驶大厂", counter["counter_offer_letter"])
        self.assertIn("Sign-on Bonus", counter["counter_offer_letter"])

        script = counter["verbal_negotiation_script"]
        self.assertIn("opening_and_anchor", script)
        self.assertIn("leverage_presentation", script)
        self.assertIn("the_ask_compensation", script)
        self.assertIn("trap_rectification_points", script)
        self.assertIn("closing_and_commitment", script)

        self.assertEqual(len(counter["trap_remedy_requests"]), 6)
        self.assertGreaterEqual(len(counter["tactical_leverage_points"]), 3)

    def test_05_convenience_function(self):
        result = evaluate_offer_package(self.offer_data)
        self.assertIn("total_compensation", result)
        self.assertIn("contract_traps", result)
        self.assertIn("overall_score", result)


# ============================================================================
# 3. Evidence Gate & Legal Compliance
# ============================================================================

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

        for buzzword in FORBIDDEN_TECH_BUZZWORDS:
            self.assertNotIn(buzzword, letter_zh)
            self.assertNotIn(buzzword, letter_en)
            for phase_name, text in verbal_script.items():
                self.assertNotIn(buzzword, text)
            for pt in leverage_points:
                self.assertNotIn(buzzword, pt)

        self.assertEqual(counter["grounded_claims"], [])
        self.assertTrue(len(counter["unsupported_claims"]) >= 2)
        self.assertTrue(any("外部竞争 Offer" in c for c in counter["unsupported_claims"]))
        self.assertTrue(any("量化" in c for c in counter["unsupported_claims"]))
        self.assertTrue(len(counter["pending_questions"]) >= 2)

    def test_02_non_llm_product_manager_profile(self):
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
        for buzzword in FORBIDDEN_TECH_BUZZWORDS:
            self.assertNotIn(buzzword, letter_zh)

        self.assertTrue(len(counter["grounded_claims"]) >= 1)
        self.assertIn("支付转化率提升 16.8%", counter["grounded_claims"][0])
        self.assertIn("支付转化率提升 16.8%", letter_zh)
        self.assertIn("4500 万元", letter_zh)

    def test_03_non_llm_operations_profile(self):
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

        self.assertTrue(len(counter["grounded_claims"]) >= 2)
        self.assertTrue(any("30 万 QPS" in c for c in counter["grounded_claims"]))
        self.assertTrue(any("某一线开源云厂商" in c for c in counter["grounded_claims"]))

        letter_zh = counter["counter_offer_letter"]
        self.assertIn("30 万 QPS", letter_zh)
        self.assertIn("某一线开源云厂商", letter_zh)

        for buzzword in FORBIDDEN_TECH_BUZZWORDS:
            self.assertNotIn(buzzword, letter_zh)

    def test_05_competing_offer_evidence_gate(self):
        clean_offer = {
            "company": "某科技集团",
            "role": "架构师",
            "base_salary_monthly": 60000.0,
            "months_per_year": 15.0,
        }
        eval_result = self.negotiator.evaluate_offer(clean_offer)

        counter_with_comp = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=70000.0,
            competing_offers=[{"company": "竞品独角兽公司", "package_annual": 1350000, "base_monthly": 72000}]
        )
        self.assertTrue(any("竞品独角兽公司" in c for c in counter_with_comp["grounded_claims"]))
        self.assertIn("竞品独角兽公司", counter_with_comp["counter_offer_letter"])
        self.assertFalse(any("外部竞争 Offer" in c for c in counter_with_comp["unsupported_claims"]))

        counter_without_comp = self.negotiator.generate_counter_offer(
            eval_result,
            target_base=70000.0,
            competing_offers=[]
        )
        self.assertTrue(any("外部竞争 Offer" in c for c in counter_without_comp["unsupported_claims"]))
        self.assertNotIn("竞品独角兽公司", counter_without_comp["counter_offer_letter"])
        self.assertIn("外部市场分位与行业薪酬带宽", counter_without_comp["counter_offer_letter"])

    def test_06_compliance_disclaimers_and_trap_softening(self):
        result = self.negotiator.evaluate_offer(self.offer_data, self.profile_data)
        counter = self.negotiator.generate_counter_offer(result, target_base=90000.0)

        self.assertIn("compliance_disclaimer", result)
        self.assertEqual(result["compliance_disclaimer"], COMPLIANCE_DISCLAIMER)
        self.assertIn("compliance_disclaimer", counter)
        self.assertEqual(counter["compliance_disclaimer"], COMPLIANCE_DISCLAIMER)

        self.assertIn(COMPLIANCE_DISCLAIMER, result["evaluation_narrative"])

        self.assertEqual(len(result["detected_traps"]), 6)
        for trap in result["detected_traps"]:
            self.assertIn("compliance_disclaimer", trap)
            self.assertEqual(trap["compliance_disclaimer"], COMPLIANCE_DISCLAIMER)
            self.assertNotIn("属于严重违反《社会保险法》的违法条款", trap["issue_summary"])
            self.assertNotIn("该条款涉嫌违法且剥夺劳动者法定补偿权", trap["issue_summary"])
            self.assertNotIn("霸王条款", trap["negotiation_countermeasure"])

    def test_07_full_backward_compatibility_and_aliases(self):
        eval_result = self.negotiator.evaluate_offer(self.offer_data, self.profile_data)
        counter = self.negotiator.generate_counter_offer(eval_result, target_base=90000.0)

        self.assertIn("chinese_letter", counter)
        self.assertIn("english_letter", counter)
        self.assertIn("verbal_script", counter)
        self.assertIn("detected_traps", counter)
        self.assertIn("target_base", counter)
        self.assertIn("grounded_claims", counter)
        self.assertIn("unsupported_claims", counter)
        self.assertIn("pending_questions", counter)
        self.assertIn("compliance_disclaimer", counter)

        self.assertEqual(counter["chinese_letter"], counter["counter_offer_letter"])
        self.assertEqual(counter["english_letter"], counter["counter_offer_letter_en"])
        self.assertEqual(counter["verbal_script"], counter["verbal_negotiation_script"])

        letter_zh = self.negotiator.generate_counter_offer_letter(eval_result, target_base=90000.0, lang="zh")
        letter_en = self.negotiator.generate_counter_offer_letter(eval_result, target_base=90000.0, lang="en")
        self.assertEqual(letter_zh, counter["counter_offer_letter"])
        self.assertEqual(letter_en, counter["counter_offer_letter_en"])


if __name__ == "__main__":
    unittest.main()
