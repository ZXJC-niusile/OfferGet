"""Arithmetic consistency checks integrated into FactVerificationGuard."""

from __future__ import annotations

import pytest

from core.fact_guard import FactVerificationGuard


def _verify_self(bullet: str) -> dict:
    profile = {
        "candidate": {"name": "Test Candidate"},
        "experience": [{"company": "Org", "role": "Engineer", "bullets": [bullet]}],
    }
    return FactVerificationGuard(profile).verify_facts(bullet)


@pytest.mark.parametrize("bullet", [
    "对 200 / 2000 项任务进行了优化，实现了 10% 的完成率。",
    "在 2000 项中有 200 项通过，通过率为 10%。",
    "对 200 / 2000 项任务进行了优化，实现了 10% 的完成率，同时吞吐量提升 30%。",
    "将延迟从 100ms 降至 80ms，吞吐量提升了 30%。",
    "将延迟从 100ms 降至 80ms，延迟降低了 20%。",
    "将 QPS 从 100 提升至 125，提升了 25%。",
    "从 3 提升至 4，提升了 33%。",
    "将转化率从 60% 提升至 70%，提升了 10 个百分点。",
    "从 100ms 优化至 20ms，降低了 80%。",
    "首字延迟从 500ms 降至 200ms，降低了 60%。",
    "在校期间 GPA 3.8/4.0，优化系统后吞吐量提升 20%。",
    "在 2024/03 完成服务重构，延迟降低 20%。",
])
def test_consistent_ratios_changes_and_non_ratio_slashes_pass(bullet):
    result = _verify_self(bullet)
    assert result["passed"], result


@pytest.mark.parametrize("bullet,expected_reason_fragment", [
    ("对 200 / 2000 项任务进行了优化，实现了 38% 的完成率。", "分子分母不一致"),
    ("在 2000 项中有 200 项通过，通过率为 38%。", "分子分母不一致"),
    ("对 200 / 2000 项任务进行了优化，实现了 38% 的完成率，同时吞吐量提升 30%。", "分子分母不一致"),
    ("完成了 200 / 0 项任务，占比 10%。", "分母不能为 0"),
    ("将 QPS 从 100 提升至 125，提升了 20%。", "相对变化百分比不一致"),
    ("将延迟从 100ms 降至 80ms，延迟降低了 50%。", "相对变化百分比不一致"),
    ("将转化率从 60% 提升至 70%，提升了 10%。", "相对变化百分比不一致"),
    ("将转化率从 60% 提升至 70%，提升了 20 个百分点。", "百分点变化不一致"),
    ("将产量从 0 提升至 125，提升了 25%。", "baseline 不能为 0"),
    ("从 100ms 降至 20ms，降低了 50%。", "相对变化百分比不一致"),
    ("从 100ms 提升至 200ms，降低了 50%。", "变化方向矛盾"),
])
def test_inconsistent_ratios_and_changes_are_caught_by_fact_verify(bullet, expected_reason_fragment):
    result = _verify_self(bullet)
    assert not result["passed"]
    assert any(
        d.get("metric_type") == "METRIC_ARITHMETIC_INCONSISTENCY"
        and expected_reason_fragment in d.get("verified_baseline", "")
        for d in result["drifts"]
    ), result


def test_multi_percentage_bullet_matches_each_metric_to_its_own_clause_baseline():
    baseline_bullet = "对 200 / 2000 项任务进行了优化，实现了 10% 的完成率，同时吞吐量提升 30%。"
    profile = {
        "candidate": {"name": "Test Candidate"},
        "experience": [{"company": "Org", "role": "Engineer", "bullets": [baseline_bullet]}],
    }
    guard = FactVerificationGuard(profile)

    inflated_second = "对 200 / 2000 项任务进行了优化，实现了 10% 的完成率，同时吞吐量提升 50%。"
    res_second = guard.verify_facts(inflated_second)
    assert not res_second["passed"], res_second
    assert any(
        d.get("claimed_metric") == "50%" and d.get("verified_baseline") == "30%"
        for d in res_second["drifts"]
    ), res_second

    inflated_first = "对 200 / 2000 项任务进行了优化，实现了 30% 的完成率，同时吞吐量提升 10%。"
    res_first = guard.verify_facts(inflated_first)
    assert not res_first["passed"], res_first
    assert any(
        d.get("claimed_metric") == "30%" and d.get("verified_baseline") == "10%"
        for d in res_first["drifts"]
    ), res_first
