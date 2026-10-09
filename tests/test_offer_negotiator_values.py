"""Zero amounts and ratios must survive offer input defaults and aliases."""

import pytest

from core.offer_negotiator import OfferNegotiator


def evaluate(**fields):
    return OfferNegotiator().evaluate_offer({"base_salary_monthly": 20000, **fields})


@pytest.mark.parametrize("fund", [
    0, 0.0, {"rate": 0}, {"rate": "0"}, {"monthly_amount": 0},
    {"monthly_employer_amount": 0, "monthly_amount": 1000, "rate": 0.12},
])
def test_explicit_zero_housing_fund_is_not_estimated(fund):
    comp = evaluate(housing_fund=fund)["total_compensation"]
    assert comp["employer_housing_fund_annual"] == 0
    assert comp["total_annual_package"] == 240000


@pytest.mark.parametrize("key", ["salary_discount_rate", "salary_ratio", "discount_ratio"])
@pytest.mark.parametrize("zero", [0, "0"])
def test_zero_probation_ratio_triggers_existing_detector(key, zero):
    probation = {"duration_months": 3, key: zero}
    if key == "salary_discount_rate":
        probation["salary_ratio"] = 1.0
    trap = evaluate(probation=probation)["contract_traps"][0]
    assert trap["detected"] and trap["severity"] == "CRITICAL"
    assert "【0%】" in trap["issue_summary"]


@pytest.mark.parametrize("fund", [None, {}, {"rate": None}, {"rate": ""}])
def test_missing_housing_value_retains_existing_estimate(fund):
    assert evaluate(housing_fund=fund)["total_compensation"]["employer_housing_fund_annual"] == 28800


@pytest.mark.parametrize("probation", [None, {}, {"salary_discount_rate": None}, {"salary_discount_rate": ""}])
def test_missing_probation_ratio_keeps_default(probation):
    assert not evaluate(probation=probation)["contract_traps"][0]["detected"]


def test_null_alias_falls_through_but_zero_base_stays_zero():
    result = evaluate(housing_fund={"monthly_employer_amount": None, "monthly_amount": 1000})
    assert result["total_compensation"]["employer_housing_fund_annual"] == 12000
    for fields in ({}, {"base_salary_monthly": 0, "monthly_base": 20000}):
        comp = OfferNegotiator().evaluate_offer(fields)["total_compensation"]
        assert comp["monthly_base"] == comp["employer_housing_fund_annual"] == 0
    assert evaluate(base_salary_monthly=None, monthly_base=20000)["total_compensation"]["monthly_base"] == 20000


@pytest.mark.parametrize("section,key", [("housing_fund", "rate"), ("probation", "salary_discount_rate")])
@pytest.mark.parametrize("value", [-0.1, float("nan"), float("inf"), True, "bad", []])
def test_invalid_rates_fail_instead_of_fabricating_values(section, key, value):
    with pytest.raises(ValueError, match=key):
        evaluate(**{section: {key: value}})


def test_higher_probation_salary_is_not_invalid():
    assert not evaluate(probation={"salary_ratio": 1.1})["contract_traps"][0]["detected"]
    with pytest.raises(ValueError, match="rate"):
        evaluate(housing_fund={"rate": 1.1})


@pytest.mark.parametrize("fund", [False, -1, float("nan"), {"monthly_amount": -1}])
def test_invalid_housing_amounts_fail(fund):
    with pytest.raises(ValueError, match="monthly_employer_amount"):
        evaluate(housing_fund=fund)


@pytest.mark.parametrize("section", ["housing_fund", "probation"])
def test_invalid_nested_objects_fail(section):
    with pytest.raises(ValueError, match="Expected an object"):
        evaluate(**{section: []})
