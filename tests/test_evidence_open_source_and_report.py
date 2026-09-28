"""
Tests for OfferGet Evidence Open Source Auditor and HTML Report Renderer.
Verifies contribution depth levels (0-4), open source inflation patterns,
and self-contained HTML audit report rendering.
"""

import json
from pathlib import Path
import pytest

from core.evidence.auditor import EvidenceAuditor
from core.evidence.extractor import ClaimExtractor
from core.evidence.models import AuditClaim, AuditReport
from core.evidence.open_source import (
    OpenSourceAuditor,
    OpenSourceContributionLevel,
    LEVEL_METADATA,
)
from core.evidence.report_renderer import (
    render_audit_report_html,
    save_audit_report_html,
)
from core.fact_guard import FactVerificationGuard


SAMPLE_PROFILE = {
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
    """Verifies that 0-4 contribution levels correctly classify diverse inputs."""
    # Level 0: Visible
    lvl0, safe0 = OpenSourceAuditor.classify_level("在 GitHub 上给项目点了 Star 并提交了一个未复现的 Issue")
    assert lvl0 == OpenSourceContributionLevel.LEVEL_0_VISIBLE
    assert "关注" in safe0 or "Issue" in safe0

    # Level 1: Peripheral
    lvl1, safe1 = OpenSourceAuditor.classify_level("优化官方网站 UI，修复了 README 中的错字与文档格式")
    assert lvl1 == OpenSourceContributionLevel.LEVEL_1_PERIPHERAL
    assert "文档" in safe1 or "官网" in safe1

    # Level 2: Scoped implementation
    lvl2, safe2 = OpenSourceAuditor.classify_level("修复网络重试组件中的超时竞争缺陷，提交 PR 已合并")
    assert lvl2 == OpenSourceContributionLevel.LEVEL_2_SCOPED
    assert "组件" in safe2 or "缺陷" in safe2

    # Level 3: Subsystem ownership
    lvl3, safe3 = OpenSourceAuditor.classify_level("作为存储子系统模块负责人，持续维护并负责多次合并与代码评审")
    assert lvl3 == OpenSourceContributionLevel.LEVEL_3_SUBSYSTEM
    assert "子系统" in safe3 or "模块" in safe3

    # Level 4: Project lead / maintainer
    lvl4, safe4 = OpenSourceAuditor.classify_level("作为该开源项目的核心 Maintainer，负责底层内核架构与主导研发")
    assert lvl4 == OpenSourceContributionLevel.LEVEL_4_PROJECT_LEAD
    assert "Maintainer" in safe4 or "核心作者" in safe4


def test_open_source_pr_metadata_classification():
    """Verifies PR metadata override takes precedence over generic text."""
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
    """Verifies detection of Star migration, periphery-to-core ambiguity, and quantity bleaching."""
    # Star migration
    patterns_star = OpenSourceAuditor.audit_claim(
        "在知名开源项目中贡献代码，项目在 GitHub 斩获 15k+ Star",
        claim_id="C-101",
    )
    p_names = [p.name for p in patterns_star]
    assert "品牌或 Star 迁移" in p_names

    # Periphery to core
    patterns_core = OpenSourceAuditor.audit_claim(
        "修改项目官网与文档错字，深度参与核心研发与内核底层架构",
        claim_id="C-102",
    )
    p_names_core = [p.name for p in patterns_core]
    assert "官网到核心引擎歧义" in p_names_core

    # Quantity bleaching (unmerged PRs)
    patterns_pr = OpenSourceAuditor.audit_claim(
        "在开源社区积极活跃，提交了 12 个 PR 进行全方位建设",
        claim_id="C-103",
    )
    p_names_pr = [p.name for p in patterns_pr]
    assert "贡献数量漂白" in p_names_pr


def test_extractor_and_auditor_open_source_integration():
    """Verifies ClaimExtractor and EvidenceAuditor recognize and flag open source claims."""
    bullet = "参与知名开源项目开发，获得 20k Star，修复官网文档并负责核心研发"
    claims = ClaimExtractor.extract_claims_from_bullet(bullet, "C-001")
    
    # Should contain main claim and open source sub claim
    os_claims = [c for c in claims if c.category == "open_source"]
    assert len(os_claims) >= 1
    assert "开源贡献" in os_claims[0].normalized_claim

    # Audit with EvidenceAuditor
    auditor = EvidenceAuditor(SAMPLE_PROFILE)
    report = auditor.audit([bullet], subject_name="李四")
    
    pattern_names = [p.name for p in report.patterns]
    assert "品牌或 Star 迁移" in pattern_names
    assert "官网到核心引擎歧义" in pattern_names

    # Check actionable next steps
    assert any("Star 数" in s or "Commit" in s for s in report.next_steps)


def test_deep_inflation_patterns():
    """Verifies detection of Terminology Adjacency, Team Results, and Social Adjacency."""
    auditor = EvidenceAuditor(SAMPLE_PROFILE)
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
    """Verifies that AuditReport renders into valid, self-contained HTML."""
    import tempfile

    auditor = EvidenceAuditor(SAMPLE_PROFILE)
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

    # Test file saving
    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / "test_report.html"
        saved_path = save_audit_report_html(report, out_file)
        assert saved_path.is_file()
        content = saved_path.read_text(encoding="utf-8")
        assert "OfferGet Evidence Auditor" in content


def test_fact_guard_html_convenience():
    """Verifies FactVerificationGuard generates and saves HTML reports."""
    import tempfile

    guard = FactVerificationGuard(SAMPLE_PROFILE)
    
    html_text = guard.generate_audit_report_html("参与开源项目建设，累计提交 5 个 PR", subject_name="李四")
    assert "李四" in html_text
    assert "report-data" in html_text

    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / "guard_report.html"
        p = guard.save_audit_report_html("参与开源项目建设", output_path=out_file, subject_name="李四")
        assert p.is_file()
