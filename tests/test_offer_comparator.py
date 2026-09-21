"""
Tests for Multi-Offer Comparison Matrix (core/offer_comparator.py)
==================================================================
Validates:
1. Single offer compensation breakdown, housing fund double-side calculation.
2. Effective hourly rate computation factoring in work hours and commute.
3. Multi-offer comparison, ranking, and decision summary generation.
"""

import pytest
from core.offer_comparator import (
    CalculatedOfferMetrics,
    OfferComparator,
    OfferComparisonReport,
    OfferEntity,
)


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
        weekly_work_hours=60.0,  # 996
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
        weekly_work_hours=40.0,  # 965
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
        housing_fund_rate=0.05,  # 最低比例公积金
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
        # Cash base = 28,000 * 15 = 420,000
        assert metrics.annual_cash_base == 420000.0
        # Total cash = 420,000 + 30,000 = 450,000
        assert metrics.annual_total_cash == 450000.0
        # Housing fund = 28,000 * 0.12 * 2 * 12 = 80,640
        assert metrics.annual_housing_fund_total == 80640.0
        # Effective hourly rate should be positive and high for 40h/week
        assert metrics.effective_hourly_rate > 150.0
        assert any("工作时间规范" in p for p in metrics.pros)

    def test_compare_multiple_offers(self, sample_offers):
        comparator = OfferComparator()
        report = comparator.compare(sample_offers)

        assert isinstance(report, OfferComparisonReport)
        assert len(report.offers) == 3
        assert len(report.ranked_companies) == 3
        # Best cash should be offer A
        assert "某一线大厂" in report.best_cash_flow
        # Best hourly rate should be offer B (due to 40h WLB)
        assert "某外企独角兽" in report.best_hourly_rate
        # Comparison table generated
        assert "| 公司与岗位 |" in report.comparison_table_md
        assert report.recommendation_summary

    def test_compare_empty_raises_error(self):
        comparator = OfferComparator()
        with pytest.raises(ValueError, match="至少需要提供一个 Offer"):
            comparator.compare([])
