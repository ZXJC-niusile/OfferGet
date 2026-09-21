"""
Tests for OfferGet Evidence Metric Recalculator and Schema Validator.
Migrated and expanded from ASu-resume-skills (Apache-2.0).
"""

import pytest

from core.evidence.metrics import MetricRecalculator
from core.evidence.models import AuditClaim, AuditReport, AuditSource, MetricCheck
from core.evidence.schema import validate_report_data


def make_report(metric_dict=None, source_url="https://example.com/evidence"):
    claim = {
        "id": "C-001",
        "normalized_claim": "付费转化率",
        "status": "unverifiable",
        "risk": "medium",
        "confidence": "medium",
        "analysis": "等待补充指标口径。",
        "evidence_for": ["S-001"],
        "evidence_against": [],
    }
    if metric_dict is not None:
        claim["metric"] = metric_dict

    return {
        "metadata": {
            "title": "测试报告",
            "subject": "匿名候选人",
            "generated_at": "2026-08-14T00:00:00+08:00",
        },
        "sources": [{"id": "S-001", "title": "来源", "url": source_url}],
        "claims": [claim],
    }


class TestMetricConsistency:
    """Direct parity tests with ASu test_validate_report.py."""

    def validate(self, metric=None, source_url="https://example.com"):
        return validate_report_data(make_report(metric, source_url))

    def test_matching_ratio_passes(self):
        errors = self.validate({"numerator": 200, "denominator": 2000, "displayed_percent": 10})
        assert errors == []

    def test_mismatched_ratio_fails(self):
        errors = self.validate({"numerator": 200, "denominator": 2000, "displayed_percent": 38})
        assert any("百分比与分子分母不一致" in error for error in errors)

    def test_non_numeric_metric_fails(self):
        errors = self.validate({"numerator": "two hundred", "denominator": 2000, "displayed_percent": 10})
        assert any("指标字段无法计算" in error for error in errors)

    def test_zero_denominator_fails(self):
        errors = self.validate({"numerator": 200, "denominator": 0, "displayed_percent": 10})
        assert any("指标字段无法计算" in error for error in errors)

    def test_matching_relative_change_passes(self):
        errors = self.validate({
            "baseline": 100,
            "result": 125,
            "change_type": "relative_percent",
            "displayed_change": 25,
        })
        assert errors == []

    def test_mismatched_relative_change_fails(self):
        errors = self.validate({
            "baseline": 100,
            "result": 125,
            "change_type": "relative_percent",
            "displayed_change": 20,
        })
        assert any("变化值与基线结果不一致" in error for error in errors)

    def test_zero_relative_change_baseline_fails(self):
        errors = self.validate({
            "baseline": 0,
            "result": 125,
            "change_type": "relative_percent",
            "displayed_change": 25,
        })
        assert any("baseline 不能为 0" in error for error in errors)

    def test_non_numeric_change_values_fail(self):
        errors = self.validate({
            "baseline": "one hundred",
            "result": 125,
            "change_type": "relative_percent",
            "displayed_change": 25,
        })
        assert any("变化字段无法计算" in error for error in errors)

    def test_matching_percentage_point_change_passes(self):
        errors = self.validate({
            "baseline": 60,
            "result": 70,
            "change_type": "percentage_points",
            "displayed_change": 10,
        })
        assert errors == []

    def test_relative_change_is_not_percentage_points(self):
        errors = self.validate({
            "baseline": 60,
            "result": 70,
            "change_type": "relative_percent",
            "displayed_change": 10,
        })
        assert any("变化值与基线结果不一致" in error for error in errors)

    def test_change_rounding_tolerance_passes(self):
        errors = self.validate({
            "baseline": 3,
            "result": 4,
            "change_type": "relative_percent",
            "displayed_change": 33,
        })
        assert errors == []

    def test_baseline_result_without_change_semantics_remains_valid(self):
        errors = self.validate({"baseline": 100, "result": 125})
        assert errors == []

    def test_claim_without_metric_remains_valid(self):
        errors = self.validate()
        assert errors == []


class TestAuditSourceUrl:
    """Direct parity tests with ASu test_validators.py."""

    def test_accepts_http_and_https_sources(self):
        assert validate_report_data(make_report(source_url="https://example.com/evidence")) == []
        assert validate_report_data(make_report(source_url="http://example.com/evidence")) == []

    def test_rejects_executable_source_url(self):
        errors = validate_report_data(make_report(source_url="javascript:alert(document.domain)"))
        assert any("URL 必须使用 http 或 https" in error for error in errors)

    def test_rejects_relative_source_url(self):
        errors = validate_report_data(make_report(source_url="/local/evidence"))
        assert any("URL 必须使用 http 或 https" in error for error in errors)


class TestReferentialIntegrity:
    """Tests for cross-referencing between claims, sources, and patterns."""

    def test_unreferenced_source_in_claim_fails(self):
        rep = make_report()
        rep["claims"][0]["evidence_for"] = ["S-999"]
        errors = validate_report_data(rep)
        assert any("引用了不存在的 source id：S-999" in error for error in errors)

    def test_unreferenced_claim_in_pattern_fails(self):
        rep = make_report()
        rep["patterns"] = [{
            "name": "角色升格",
            "claim_ids": ["C-999"],
        }]
        errors = validate_report_data(rep)
        assert any("引用了不存在的 claim id：C-999" in error for error in errors)
