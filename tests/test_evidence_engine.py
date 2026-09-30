"""
Unit Test Suite for OfferGet Evidence Engine.
Consolidates evidence models, metric consistency checks, evidence auditor,
open-source depth classification, and HTML audit report rendering.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

from core.evidence.auditor import EvidenceAuditor
from core.evidence.extractor import ClaimExtractor
from core.evidence.metrics import MetricRecalculator
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
from core.evidence.open_source import (
    LEVEL_METADATA,
    OpenSourceAuditor,
    OpenSourceContributionLevel,
)
from core.evidence.report_renderer import (
    render_audit_report_html,
    save_audit_report_html,
)
from core.evidence.schema import validate_report_data
from core.fact_guard import FactVerificationGuard, audit_resume_evidence


# ============================================================================
# 1. Models & Serialization Tests
# ============================================================================

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


# ============================================================================
# 2. Metric Consistency & Referential Integrity Tests
# ============================================================================

def _make_metric_report(metric_dict=None, source_url="https://example.com/evidence"):
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
    def validate(self, metric=None, source_url="https://example.com"):
        return validate_report_data(_make_metric_report(metric, source_url))

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
    def test_accepts_http_and_https_sources(self):
        assert validate_report_data(_make_metric_report(source_url="https://example.com/evidence")) == []
        assert validate_report_data(_make_metric_report(source_url="http://example.com/evidence")) == []

    def test_rejects_executable_source_url(self):
        errors = validate_report_data(_make_metric_report(source_url="javascript:alert(document.domain)"))
        assert any("URL 必须使用 http 或 https" in error for error in errors)

    def test_rejects_relative_source_url(self):
        errors = validate_report_data(_make_metric_report(source_url="/local/evidence"))
        assert any("URL 必须使用 http 或 https" in error for error in errors)


class TestReferentialIntegrity:
    def test_unreferenced_source_in_claim_fails(self):
        rep = _make_metric_report()
        rep["claims"][0]["evidence_for"] = ["S-999"]
        errors = validate_report_data(rep)
        assert any("引用了不存在的 source id：S-999" in error for error in errors)

    def test_unreferenced_claim_in_pattern_fails(self):
        rep = _make_metric_report()
        rep["patterns"] = [{
            "name": "角色升格",
            "claim_ids": ["C-999"],
        }]
        errors = validate_report_data(rep)
        assert any("引用了不存在的 claim id：C-999" in error for error in errors)


# ============================================================================
# 3. Evidence Auditor & Fact Guard Integration
# ============================================================================

@pytest.fixture
def sample_profile():
    return {
        "candidate": {
            "name": "李小华",
            "years_of_experience": 3,
            "github": "xiaohua-lee",
        },
        "experience": [
            {
                "company": "字节跳动",
                "role": "算法工程师",
                "dates": "2024.03 - 2026.06",
                "highlights": [
                    {
                        "claim_id": "EXP-0",
                        "claim_zh": "基于 Ray 优化分布式训练调度，集群规模 1024 卡，MFU 达到 54.2%",
                        "verified_metrics": {
                            "cluster_size": 1024,
                            "mfu_after": "54.2%",
                        },
                    }
                ],
                "bullets": [
                    "参与分布式数据管线清洗与性能测试。",
                ],
            }
        ],
        "projects": [
            {
                "name": "FastInfer",
                "role": "主要开发者",
                "dates": "2023.09 - 2024.02",
                "stars": 1200,
                "description": "开源推理加速库，在 GSM8K 上达到 85% 准确率。",
            }
        ],
    }


class TestClaimExtractor:
    def test_extract_from_bullet_with_role_and_superlative(self):
        bullet = "作为核心作者主导开源项目，打造了业内最先进的分布式推理引擎，将首字延迟从 500ms 降至 200ms。"
        claims = ClaimExtractor.extract_claims_from_bullet(bullet, "C-001")
        assert len(claims) >= 3

        cat_set = {c.category for c in claims}
        assert "role_boundary" in cat_set
        assert "superlative" in cat_set

    def test_extract_from_resume_dict(self, sample_profile):
        resume_dict = {
            "experience": [
                {
                    "company": "字节跳动",
                    "role": "算法工程师",
                    "bullets": [
                        "负责集群调度优化，提升 MFU 至 54.2%。",
                        "主导全系统架构从0到1研发。",
                    ],
                }
            ],
            "projects": [
                {
                    "name": "FastInfer",
                    "bullets": ["作为核心作者开源该项目。"],
                }
            ],
        }
        claims = ClaimExtractor.extract_from_resume_dict(resume_dict)
        assert len(claims) >= 3
        ids = [c.id for c in claims]
        assert "C-001" in ids


class TestEvidenceAuditor:
    def test_role_escalation_detection(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullet = "作为核心作者与 Owner，全面负责字节跳动万卡集群大模型底座架构从0到1研发。"
        report = auditor.audit([bullet], subject_name="李小华")

        assert report.metadata["subject"] == "李小华"
        assert len(report.claims) >= 2

        role_claims = [c for c in report.claims if c.category == "role_boundary"]
        assert len(role_claims) > 0
        rc = role_claims[0]
        assert rc.status == "partially_corroborated"
        assert rc.risk == "high"
        assert "角色升格" in [p.name for p in report.patterns]

    def test_superlative_detection(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullet = "研发了全球最先进的自适应算子调度器。"
        report = auditor.audit([bullet])

        sup_claims = [c for c in report.claims if c.category == "superlative"]
        assert len(sup_claims) > 0
        sc = sup_claims[0]
        assert sc.status == "unsupported"
        assert sc.risk == "high"
        assert "没有比较全集的最高级" in [p.name for p in report.patterns]

    def test_corroborated_grounded_bullet(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullet = "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。"
        report = auditor.audit([bullet])

        main_claim = report.claims[0]
        assert main_claim.status == "corroborated"
        assert main_claim.risk == "low"
        assert main_claim.confidence == "high"

    def test_metric_contradiction_detection(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullet = "对 200 / 2000 项任务进行了优化，实现了 38% 的完成率。"
        report = auditor.audit([bullet])

        metric_claims = [c for c in report.claims if c.category == "metric"]
        assert len(metric_claims) > 0
        mc = metric_claims[0]
        assert mc.status == "contradicted"
        assert mc.risk == "critical"
        assert "伪精确" in [p.name for p in report.patterns]

    def test_full_report_schema_validity(self, sample_profile):
        auditor = EvidenceAuditor(sample_profile)
        bullets = [
            "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。",
            "作为核心作者主导开源项目 FastInfer，获得 1200 stars。",
            "研发业内首个自适应通信算子。",
        ]
        report = auditor.audit(bullets)
        report_dict = report.to_dict()

        errors = validate_report_data(report_dict)
        assert errors == [], f"Report schema validation failed: {errors}"


class TestFactVerificationGuardIntegration:
    def test_guard_audit_claims_and_generate_report(self, sample_profile):
        guard = FactVerificationGuard(sample_profile)

        bullets = [
            "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。",
            "作为架构师主导全链路系统重构。",
        ]
        report = guard.audit_claims(bullets)
        assert hasattr(report, "metadata")
        assert len(report.claims) >= 2

        report_dict = guard.generate_audit_report(bullets)
        assert isinstance(report_dict, dict)
        errors = validate_report_data(report_dict)
        assert errors == []

    def test_top_level_audit_resume_evidence(self, sample_profile):
        report_dict = audit_resume_evidence(
            "基于 Ray 优化分布式训练调度，在 1024 卡集群上 MFU 达到 54.2%。",
            sample_profile,
            subject_name="李小华",
        )
        assert report_dict["metadata"]["subject"] == "李小华"
        errors = validate_report_data(report_dict)
        assert errors == []


# ============================================================================
# 4. Open-Source Depth Classification & HTML Report Rendering
# ============================================================================

OPEN_SOURCE_PROFILE = {
    "candidate": {
        "name": "李四",
        "github": "lisi-dev",
    },
    "experience": [
        {
            "company": "开源创新实验室",
            "role": "后端开发工程师",
            "dates": "2023.07 - 2024.08",
            "bullets": [
                "参与分布式消息中间件研发，优化批量拉取模块性能 15%。",
            ],
        }
    ],
    "projects": [
        {
            "name": "FastFlow",
            "role": "核心贡献者",
            "dates": "2023.01 - 2023.06",
            "bullets": [
                "主导核心流处理引擎，实现事件驱动调度。",
            ],
        }
    ],
}


def test_open_source_levels_classification():
    lvl0, safe0 = OpenSourceAuditor.classify_level("在 GitHub 上给项目点了 Star 并提交了一个未复现的 Issue")
    assert lvl0 == OpenSourceContributionLevel.LEVEL_0_VISIBLE
    assert "关注" in safe0 or "Issue" in safe0

    lvl1, safe1 = OpenSourceAuditor.classify_level("优化官方网站 UI，修复了 README 中的错字与文档格式")
    assert lvl1 == OpenSourceContributionLevel.LEVEL_1_PERIPHERAL
    assert "文档" in safe1 or "官网" in safe1

    lvl2, safe2 = OpenSourceAuditor.classify_level("修复网络重试组件中的超时竞争缺陷，提交 PR 已合并")
    assert lvl2 == OpenSourceContributionLevel.LEVEL_2_SCOPED
    assert "组件" in safe2 or "缺陷" in safe2

    lvl3, safe3 = OpenSourceAuditor.classify_level("作为存储子系统模块负责人，持续维护并负责多次合并与代码评审")
    assert lvl3 == OpenSourceContributionLevel.LEVEL_3_SUBSYSTEM
    assert "子系统" in safe3 or "模块" in safe3

    lvl4, safe4 = OpenSourceAuditor.classify_level("作为该开源项目的核心 Maintainer，负责底层内核架构与主导研发")
    assert lvl4 == OpenSourceContributionLevel.LEVEL_4_PROJECT_LEAD
    assert "Maintainer" in safe4 or "核心作者" in safe4


def test_open_source_pr_metadata_classification():
    pr_meta = {
        "area": "docs",
        "role": "contributor",
        "is_merged": True,
    }
    lvl, safe = OpenSourceAuditor.classify_level("主导大规模系统", pr_info=pr_meta)
    assert lvl == OpenSourceContributionLevel.LEVEL_1_PERIPHERAL

    unmerged_meta = {"is_merged": False}
    lvl_unmerged, _ = OpenSourceAuditor.classify_level("完成了重大功能重构", pr_info=unmerged_meta)
    assert lvl_unmerged == OpenSourceContributionLevel.LEVEL_0_VISIBLE


def test_open_source_inflation_patterns():
    patterns_star = OpenSourceAuditor.audit_claim(
        "在知名开源项目中贡献代码，项目在 GitHub 斩获 15k+ Star",
        claim_id="C-101",
    )
    p_names = [p.name for p in patterns_star]
    assert "品牌或 Star 迁移" in p_names

    patterns_core = OpenSourceAuditor.audit_claim(
        "修改项目官网与文档错字，深度参与核心研发与内核底层架构",
        claim_id="C-102",
    )
    p_names_core = [p.name for p in patterns_core]
    assert "官网到核心引擎歧义" in p_names_core

    patterns_pr = OpenSourceAuditor.audit_claim(
        "在开源社区积极活跃，提交了 12 个 PR 进行全方位建设",
        claim_id="C-103",
    )
    p_names_pr = [p.name for p in patterns_pr]
    assert "贡献数量漂白" in p_names_pr


def test_extractor_and_auditor_open_source_integration():
    bullet = "参与知名开源项目开发，获得 20k Star，修复官网文档并负责核心研发"
    claims = ClaimExtractor.extract_claims_from_bullet(bullet, "C-001")
    
    os_claims = [c for c in claims if c.category == "open_source"]
    assert len(os_claims) >= 1
    assert "开源贡献" in os_claims[0].normalized_claim

    auditor = EvidenceAuditor(OPEN_SOURCE_PROFILE)
    report = auditor.audit([bullet], subject_name="李四")
    
    pattern_names = [p.name for p in report.patterns]
    assert "品牌或 Star 迁移" in pattern_names
    assert "官网到核心引擎歧义" in pattern_names
    assert any("Star 数" in s or "Commit" in s for s in report.next_steps)


def test_deep_inflation_patterns():
    auditor = EvidenceAuditor(OPEN_SOURCE_PROFILE)
    report = auditor.audit(
        [
            "负责 AI Infra 算法中台建设，优化前端页面表单展示与数据清洗脚本",
            "支撑产品实现千万级日活与数亿元流水增长，完成技术攻坚",
            "在社区与项目 Maintainer 共同探讨，获得知名架构师点赞与肯定",
        ],
        subject_name="李四",
    )
    p_names = [p.name for p in report.patterns]
    assert "术语邻接" in p_names
    assert "团队结果个人化" in p_names
    assert "社交邻接转技术授权" in p_names
    assert any("AI Infra" in s for s in report.next_steps)
    assert any("大盘宏观指标" in s for s in report.next_steps)
    assert any("社交互动" in s for s in report.next_steps)


def test_html_audit_report_rendering():
    auditor = EvidenceAuditor(OPEN_SOURCE_PROFILE)
    report = auditor.audit(
        ["参与知名开源项目开发，获得 20k Star，负责全系统高并发重构，从 100ms 优化至 20ms，提升了 80%"],
        subject_name="李四",
    )

    html_str = render_audit_report_html(report)
    assert "<!doctype html>" in html_str.lower()
    assert "OfferGet 简历主张真实性审计报告" in html_str
    assert "李四" in html_str
    assert "品牌或 Star 迁移" in html_str
    assert '<script id="report-data" type="application/json">' in html_str

    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / "test_report.html"
        saved_path = save_audit_report_html(report, out_file)
        assert saved_path.is_file()
        content = saved_path.read_text(encoding="utf-8")
        assert "OfferGet Evidence Auditor" in content


def test_fact_guard_html_convenience():
    guard = FactVerificationGuard(OPEN_SOURCE_PROFILE)
    
    html_text = guard.generate_audit_report_html("参与开源项目建设，累计提交 5 个 PR", subject_name="李四")
    assert "李四" in html_text
    assert "report-data" in html_text

    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / "guard_report.html"
        p = guard.save_audit_report_html("参与开源项目建设", output_path=out_file, subject_name="李四")
        assert p.is_file()
