"""Before/after endpoints retain value, metric, unit and source-entry identity."""
import copy

import pytest

from core.fact_guard import FactVerificationGuard


TEXT = "测试覆盖率从 38.5% 提升至 54.2%。"


def profile():
    return {
        "candidate": {"name": "Synthetic Metric Auditor"},
        "experience": [{
            "company": "Synthetic Lab", "role": "Tester",
            "highlights": [{"claim_id": "TEST-COVERAGE", "claim_zh": TEXT,
                            "verified_metrics": {"coverage_before": "38.5%", "coverage_after": "54.2%"}}],
        }],
    }


def test_identical_before_after_statement_matches_its_actual_endpoint():
    guard = FactVerificationGuard(profile())
    result = guard.verify_facts(TEXT, target_scope="experience[0]", target_claim_id="TEST-COVERAGE")
    assert result["passed"], result
    assert not result["drifts"]
    metrics = guard._extract_raw_metrics_from_text(TEXT)
    anchors = [guard._find_matching_anchor(metric, TEXT, target_scope="experience[0]", target_claim_id="TEST-COVERAGE") for metric in metrics]
    assert [anchor["baseline_value"] for anchor in anchors] == [38.5, 54.2]
    assert [anchor["metric_role"] for anchor in anchors] == ["before", "after"]
    assert all(anchor["scope"] == "experience[0]" and anchor["claim_id"] == "TEST-COVERAGE" and anchor["unit"] == "%" for anchor in anchors)
    assert all(anchor["metric_name"] == "测试覆盖率" for anchor in anchors)
    assert guard.verify_facts(profile())["passed"]


@pytest.mark.parametrize("text", [
    "测试覆盖率从 38.5% 提升至 90%。",
    "测试覆盖率从 54.2% 提升至 38.5%。",
    "测试覆盖率从 30% 提升至 54.2%。",
    "测试覆盖率从 38.5% 提升至 54.3%。",
    "测试覆盖率从 38.5% 提升至 54.1%。",
    "测试覆盖率从 38.4% 提升至 54.2%。",
    "测试准确率从 38.5% 提升至 54.2%。",
    "测试覆盖率从 38.5 小时提升至 54.2 小时。",
])
def test_changed_endpoints_metric_name_and_units_do_not_borrow_source_values(text):
    result = FactVerificationGuard(profile()).verify_facts(text, target_scope="experience[0]", target_claim_id="TEST-COVERAGE")
    assert not result["passed"], result
    assert result["drifts"] or result["unverified_claims"]


def test_another_projects_same_unit_value_cannot_ground_the_target():
    baseline = {"candidate": {"name": "Synthetic"}, "projects": [
        {"name": "Project A", "bullets": ["Coverage improved from 38.5% to 54.2%."]},
        {"name": "Project B", "bullets": ["Coverage improved from 38.5% to 90%."]},
    ]}
    guard = FactVerificationGuard(baseline)
    assert guard.verify_facts(baseline)["passed"]
    changed = copy.deepcopy(baseline)
    changed["projects"][0]["bullets"] = ["Coverage improved from 38.5% to 90%."]
    result = guard.verify_facts(changed)
    assert not result["passed"]
    assert any(drift["claimed_metric"] == "90%" and drift["verified_baseline"] == "54.2%" for drift in result["drifts"])


def test_claim_id_prevents_borrowing_from_a_neighboring_highlight():
    baseline = profile()
    baseline["experience"][0]["highlights"].append({"claim_id": "OTHER-COVERAGE", "claim_zh": "测试覆盖率从 38.5% 提升至 90%。"})
    guard = FactVerificationGuard(baseline)
    result = guard.verify_facts("测试覆盖率从 38.5% 提升至 90%。", target_scope="experience[0]", target_claim_id="TEST-COVERAGE")
    assert not result["passed"]
    assert result["drifts"][0]["verified_baseline"] == "54.2%"


@pytest.mark.parametrize("separator", ["; ", ". ", ", "])
def test_neighboring_metric_in_same_bullet_cannot_supply_the_wrong_endpoint(separator):
    text = f"Coverage improved from 38.5% to 54.2%{separator}accuracy improved from 70% to 90%."
    baseline = {"candidate": {"name": "Synthetic"}, "projects": [{"name": "Test Project", "bullets": [text]}]}
    guard = FactVerificationGuard(baseline)
    assert guard.verify_facts(text, target_scope="projects[0]")["passed"]
    changed = text.replace("to 54.2%", "to 90%", 1)
    result = guard.verify_facts(changed, target_scope="projects[0]")
    assert not result["passed"]
    assert any(item["verified_baseline"] == "54.2%" for item in result["drifts"])


def test_record_order_and_metric_index_order_do_not_change_the_result():
    guard = FactVerificationGuard(profile())
    guard.baseline_anchors.reverse()
    assert guard.verify_facts(TEXT, target_scope="experience[0]", target_claim_id="TEST-COVERAGE")["passed"]
    assert not guard.verify_facts("测试覆盖率从 38.5% 提升至 90%。", target_scope="experience[0]", target_claim_id="TEST-COVERAGE")["passed"]
