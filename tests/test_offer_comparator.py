"""Housing-fund accounting regressions for the offer comparator."""

import pytest

from core.offer_comparator import OfferComparator, OfferEntity


@pytest.mark.parametrize(
    ("salary", "rate", "capped", "cap", "employer_fund"),
    [
        (20000.0, 0.12, True, 33891.0, 28800.0),
        (22200.0, 0.05, True, 33891.0, 13320.0),
        (40000.0, 0.12, True, 30000.0, 43200.0),
        (40000.0, 0.12, False, 30000.0, 57600.0),
        (20000.0, 0.0, True, 33891.0, 0.0),
    ],
)
def test_housing_fund_adds_only_employer_benefit(salary, rate, capped, cap, employer_fund):
    offer = OfferEntity(
        company_name="Test",
        role_title="Engineer",
        base_monthly_salary=salary,
        salary_months=14.0,
        annual_bonus_expected=10000.0,
        sign_on_bonus=5000.0,
        equity_rsu_annual=20000.0,
        housing_fund_rate=rate,
        housing_fund_base_capped=capped,
        city_housing_fund_cap_base=cap,
        weekly_work_hours=40.0,
        daily_commute_hours=0.0,
        monthly_rent_or_commute_cost=1000.0,
    )
    metrics = OfferComparator().evaluate_single_offer(offer)
    gross_cash = salary * 14.0 + 15000.0

    assert metrics.annual_cash_base == salary * 14.0
    assert metrics.annual_total_cash == gross_cash
    assert metrics.annual_housing_fund_total == employer_fund * 2.0
    assert metrics.annual_total_package == gross_cash + 20000.0 + employer_fund
    assert metrics.effective_hourly_rate == round(
        (gross_cash + employer_fund - 12000.0) / 2000.0, 1
    )
    assert metrics.dimension_scores["total_package"] == pytest.approx(
        min(100.0, max(20.0, metrics.annual_total_package / 6000.0))
    )
    assert metrics.dimension_scores["benefits_housing_fund"] == pytest.approx(
        min(100.0, max(20.0, employer_fund / 80000.0 * 100.0))
    )


def test_bilateral_fund_does_not_reverse_hourly_or_package_ranking():
    offers = [
        OfferEntity(
            company_name=name,
            role_title="Engineer",
            base_monthly_salary=salary,
            salary_months=12.0,
            housing_fund_rate=rate,
            weekly_work_hours=40.0,
            daily_commute_hours=0.0,
            monthly_rent_or_commute_cost=0.0,
        )
        for name, salary, rate in [("A", 20000.0, 0.12), ("B", 22200.0, 0.05)]
    ]
    report = OfferComparator().compare(offers)
    metrics_a, metrics_b = [metrics for _, metrics in report.offers]

    assert metrics_a.annual_housing_fund_total == 57600.0
    assert metrics_b.annual_housing_fund_total == 26640.0
    assert metrics_a.annual_total_package == 268800.0
    assert metrics_b.annual_total_package == 279720.0
    assert metrics_a.effective_hourly_rate == 134.4
    assert metrics_b.effective_hourly_rate == 139.9
    assert report.best_hourly_rate == "B"
    assert report.best_cash_flow == "B"

    # Benefit preferences may favor A; cash/package/hourly preferences must not.
    weights = {key: 0.0 for key in OfferComparator.DEFAULT_WEIGHTS}
    weights.update(immediate_cash=0.25, total_package=0.25, effective_hourly_rate=0.5)
    assert OfferComparator(weights=weights).compare(offers).best_overall == "B"
