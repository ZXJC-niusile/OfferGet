"""
Tests for OfferGet Evidence Models.
Verifies data structures, serialization/deserialization, and schema alignment.
"""

import pytest

from core.evidence.models import (
    ALLOWED_CONFIDENCE,
    ALLOWED_RISKS,
    ALLOWED_SOURCE_RELIABILITY,
    ALLOWED_STATUSES,
    AuditClaim,
    AuditPattern,
    AuditReport,
    AuditSource,
    AuditTimelineItem,
    MetricCheck,
)


def test_metric_check_serialization():
    mc = MetricCheck(
        numerator=200,
        denominator=2000,
        displayed_percent=10,
        baseline=100,
        result=125,
        change_type="relative_percent",
        displayed_change=25,
    )
    d = mc.to_dict()
    assert d["numerator"] == 200
    assert d["denominator"] == 2000
    assert d["displayed_percent"] == 10
    assert d["baseline"] == 100
    assert d["result"] == 125
    assert d["change_type"] == "relative_percent"
    assert d["displayed_change"] == 25

    mc_restored = MetricCheck.from_dict(d)
    assert mc_restored is not None
    assert mc_restored.numerator == 200
    assert mc_restored.displayed_change == 25


def test_audit_source_serialization():
    src = AuditSource(
        id="S-001",
        title="官方项目 README",
        url="https://example.com/repo",
        type="official_record",
        publisher="项目组织",
        accessed_at="2026-08-13",
        reliability="A",
        notes="同期公开记录",
    )
    d = src.to_dict()
    assert d["id"] == "S-001"
    assert d["reliability"] == "A"
    assert d["url"] == "https://example.com/repo"

    src_restored = AuditSource.from_dict(d)
    assert src_restored.id == "S-001"
    assert src_restored.url == "https://example.com/repo"
    assert src_restored.reliability == "A"


def test_audit_claim_serialization():
    claim = AuditClaim(
        id="C-001",
        category="open_source_role",
        resume_text="作为核心作者主导开源项目",
        normalized_claim="担任核心作者并主导项目",
        status="partially_corroborated",
        risk="high",
        confidence="high",
        evidence_for=["S-002"],
        evidence_against=["S-001"],
        metric=MetricCheck(numerator=200, denominator=2000, displayed_percent=10),
        analysis="事实锚点真实，但存在角色升格。",
        verification_steps=["要求提供正式 Maintainer 任命记录"],
        page_break_before=False,
    )
    d = claim.to_dict()
    assert d["id"] == "C-001"
    assert d["status"] in ALLOWED_STATUSES
    assert d["risk"] in ALLOWED_RISKS
    assert d["confidence"] in ALLOWED_CONFIDENCE
    assert d["metric"]["displayed_percent"] == 10

    claim_restored = AuditClaim.from_dict(d)
    assert claim_restored.id == "C-001"
    assert claim_restored.status == "partially_corroborated"
    assert claim_restored.metric is not None
    assert claim_restored.metric.numerator == 200


def test_audit_pattern_serialization():
    pat = AuditPattern(
        name="角色升格",
        description="Contributor 活动被描述为核心作者身份。",
        signals=["核心作者措辞", "已合并工件有限"],
        claim_ids=["C-001"],
        counter_evidence="存在一个有意义的已合并 PR。",
        confidence="medium",
        page_break_before=False,
    )
    d = pat.to_dict()
    assert d["name"] == "角色升格"
    assert d["claim_ids"] == ["C-001"]

    pat_restored = AuditPattern.from_dict(d)
    assert pat_restored.name == "角色升格"
    assert pat_restored.counter_evidence == "存在一个有意义的已合并 PR。"


def test_audit_report_full_roundtrip():
    report = AuditReport(
        metadata={
            "title": "测试审计报告",
            "subject": "张三",
            "generated_at": "2026-08-14T00:00:00+08:00",
            "scope": "公开来源简历主张审计",
            "analyst": "OfferGet",
            "disclaimer": "结论仅供参考。",
        },
        summary={
            "conclusion": "主张部分证实。",
            "highest_risk": ["C-001"],
            "limitations": ["无内部记录"],
        },
        sources=[AuditSource(id="S-001", title="官方名册", url="https://example.com")],
        claims=[
            AuditClaim(
                id="C-001",
                normalized_claim="付费转化率10%",
                status="corroborated",
                risk="low",
                confidence="high",
                evidence_for=["S-001"],
                analysis="符合官方记录。",
            )
        ],
        patterns=[AuditPattern(name="正常主张", claim_ids=["C-001"])],
        timeline=[AuditTimelineItem(date="2025.01", title="入职", source_ids=["S-001"])],
        next_steps=["正常推进面试"],
    )

    d = report.to_dict()
    assert d["metadata"]["subject"] == "张三"
    assert len(d["sources"]) == 1
    assert len(d["claims"]) == 1
    assert d["claims"][0]["id"] == "C-001"

    restored = AuditReport.from_dict(d)
    assert restored.metadata["subject"] == "张三"
    assert len(restored.sources) == 1
    assert restored.claims[0].id == "C-001"
    assert restored.timeline[0].title == "入职"
