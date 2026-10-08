# -*- coding: utf-8 -*-
"""Diff ledger regressions: actual source values, detections, and unknown layout."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest

from core.diff_ledger import (
    DiffCategory,
    DiffSeverity,
    DiffEntry,
    DiffLedger,
    DIFF_CATEGORY_META,
    DIFF_SEVERITY_BADGES,
)
from core.fact_guard import FactVerificationGuard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_candidate_profile():
    return {
        "candidate": {
            "name": "张明",
            "education": [
                {
                    "school": "华东理工大学",
                    "degree": "工学学士在读",
                    "major": "土木工程",
                    "details": "GPA 3.12（专业前15%）",
                    "coursework": [
                        "概率论与数理统计",
                        "工程经济学",
                        "工程项目管理",
                        "基础工程",
                    ],
                }
            ],
            "certifications": [
                "全国计算机等级考试二级（WPS Office）",
                "普通话二级乙等",
            ],
        },
        "experience": [
            {
                "company": "交个朋友",
                "role": "直播运营",
                "highlights": [
                    "独立操盘 90+ 场直播全生命周期运营",
                    "独立设计 30+ 场直播专属促单贴片与机制 KT 板",
                    "创下单场最高 GMV 超 80万元、单场最高同时在线约 600人。",
                ],
            },
            {
                "company": "桃蹊礼品",
                "role": "编辑部成员",
                "highlights": [
                    "主导线下核心企业客户回访调研 50+ 家，提炼定制礼品需求清单 30+ 份",
                    "落地文创品牌地推执行，单日触达引流潜在用户 200+ 人",
                    "统筹校官方公众号内容采编与排版，累计输出推文 15+ 篇（单篇最高阅读量 5,000+）",
                ],
            },
        ],
        "projects": [
            {
                "name": "洪泽湖沿岸生态保护与居民用水处理探索",
                "role": "志愿实践成员",
                "bullets": [
                    "深入洪泽湖沿岸村落推进实地走访调研，采集水样并输出水质调研报告"
                ],
            },
            {
                "name": "青岛本地文创IP小海鸥谢谢",
                "role": "推广成员",
                "bullets": [
                    "操盘青岛本地文创 IP 线下快闪与地推拓客，触达转化潜在粉丝 500+ 人"
                ],
            },
            {
                "name": "班级心理健康建设",
                "role": "班级心理委员",
                "bullets": [
                    "统筹协调班级信息流转与突发事件响应，建立 40+ 人班集体高效沟通与心理关怀机制"
                ],
            },
        ],
    }


@pytest.fixture
def sample_inflated_tailored():
    return {
        "experience": [
            {
                "company": "交个朋友",
                "role": "直播运营",
                "highlights": [
                    "Led end-to-end execution for 90+ livestream sessions.",
                    "Independently created 30+ custom promo overlays and KT boards.",  # Event to Asset drift
                    "Achieved peak single-session GMV exceeding ~$110K USD with 600 concurrent viewers.",  # Currency drift
                ],
            },
            {
                "company": "桃蹊礼品",
                "role": "编辑部成员",
                "highlights": [
                    "Conducted structured interviews with 50+ corporate clients.",
                    "Acquired 200+ enterprise clients through offline marketing.",  # User to Enterprise drift
                    "Published official school WeChat posts with 5,000+ total cumulative readership.",  # Peak to Cumulative drift
                ],
            },
        ],
        "projects": [
            {
                "name": "洪泽湖沿岸生态保护与居民用水处理探索",
                "role": "Volunteer Field Lead",  # Title inflation Tier 0 -> Tier 3
                "bullets": [
                    "Led field research and water sampling in lakeside villages."
                ],
            },
            {
                "name": "青岛本地文创IP小海鸥谢谢",
                "role": "Brand Promotion Specialist",  # Title inflation Tier 1 -> Tier 2
                "bullets": [
                    "Executed pop-up events and offline marketing, converting 500+ prospective fans."
                ],
            },
            {
                "name": "班级心理健康建设",
                "role": "Student Affairs Representative",  # Domain drift (dropped mental health)
                "bullets": [
                    "Managed communications and student affairs for 40+ students."
                ],
            },
        ],
    }


@pytest.fixture
def sample_grounded_tailored():
    return {
        "candidate": {
            "education": [
                {
                    "details": "B.Eng. in Civil Engineering | GPA: 3.12 (Top 15%)",  # Denominator /4.0 avoided
                    "coursework": (
                        "Probability and Mathematical Statistics; Engineering Economics; "
                        "Engineering Project Management; Foundation Engineering"
                    ),
                }
            ],
            "certifications": [
                "National Computer Rank Examination (NCRE) Level 2 — WPS Office",
            ],
        },
        "experience": [
            {
                "company": "交个朋友",
                "role": "Livestream Operations Intern",
                "highlights": [
                    "Led end-to-end execution for 90+ livestream sessions.",
                    "Designed custom promo overlays and KT boards for 30+ livestream sessions.",
                    "Achieved peak single-session GMV exceeding RMB 800,000 with 600 concurrent viewers.",
                ],
            },
            {
                "company": "桃蹊礼品",
                "role": "Editorial Team Member",  # Grounded Tier 1
                "highlights": [
                    "Conducted structured interviews with 50+ corporate clients.",
                    "Engaged 200+ prospective users in a single day through offline marketing.",
                    "Published official school WeChat posts, achieving peak readership of 5,000+ for a single article.",
                ],
            },
        ],
        "projects": [
            {
                "name": "洪泽湖沿岸生态保护与居民用水处理探索",
                "role": "Field Research Volunteer",  # Grounded Tier 0
                "bullets": [
                    "Conducted field research and water sampling in lakeside villages."
                ],
            },
            {
                "name": "青岛本地文创IP小海鸥谢谢",
                "role": "Promotion Team Member",  # Grounded Tier 1
                "bullets": [
                    "Executed pop-up events and offline marketing, converting 500+ prospective fans."
                ],
            },
            {
                "name": "班级心理健康建设",
                "role": "Class Mental Health Representative",  # Grounded Tier 0 with mental health anchor
                "bullets": [
                    "Managed communications and student mental well-being support for 40+ students."
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_01_diff_entry_creation_and_attributes():
    """Test DiffEntry instantiation, enum normalization, and dict serialization."""
    entry = DiffEntry(
        category=DiffCategory.ROLE_HIERARCHY,
        field="projects[0].role",
        baseline_zh="志愿实践成员",
        tailored_en="Field Research Volunteer",
        severity=DiffSeverity.INFLATION_PREVENTED,
        explanation="拦截越级 'Lead'，采纳客观对齐英文",
        action_taken="拦截越级词汇，保持志愿成员身份",
        metadata={"scope": "projects[0]"},
    )

    assert entry.category == DiffCategory.ROLE_HIERARCHY
    assert entry.severity == DiffSeverity.INFLATION_PREVENTED
    assert entry.field == "projects[0].role"
    assert entry.baseline_zh == "志愿实践成员"
    assert entry.tailored_en == "Field Research Volunteer"

    # Test serialization to dict
    d = entry.to_dict()
    assert d["category"] == "ROLE_HIERARCHY"
    assert d["severity"] == "INFLATION_PREVENTED"
    assert d["baseline_zh"] == "志愿实践成员"
    assert d["metadata"] == {"scope": "projects[0]"}

    # Test deserialization from dict
    restored = DiffEntry.from_dict(d)
    assert restored.category == DiffCategory.ROLE_HIERARCHY
    assert restored.severity == DiffSeverity.INFLATION_PREVENTED
    assert restored.field == entry.field


def test_02_diff_ledger_add_entry_variants():
    """Test adding entries to DiffLedger via instance, positional, and keyword args."""
    ledger = DiffLedger(candidate_name="测试候选人")

    # 1. Via DiffEntry object
    e1 = DiffEntry(
        category=DiffCategory.ROLE_HIERARCHY,
        field="role.editorial",
        baseline_zh="编辑部成员",
        tailored_en="Editorial Team Member",
        severity=DiffSeverity.ALIGNED,
        explanation="未越级提拔",
        action_taken="核验通过",
    )
    ledger.add_entry(e1)

    # 2. Via keyword arguments
    ledger.add_entry(
        category=DiffCategory.METRIC_SCOPE,
        field="metric.livestream_sessions",
        baseline_zh="30+ 场直播",
        tailored_en="for 30+ livestream sessions",
        severity=DiffSeverity.INFLATION_PREVENTED,
        explanation="场次限定",
        action_taken="消除物料歧义",
    )

    # 3. Via positional arguments
    ledger.add_entry(
        DiffCategory.LAYOUT_ACTION,
        "layout.font_size",
        ">=9.5pt",
        "Body font 10pt",
        DiffSeverity.ALIGNED,
        "遵守字号底线",
        "排版微调",
    )

    assert len(ledger.entries) == 3
    assert ledger.count_by_category()["ROLE_HIERARCHY"] == 1
    assert ledger.count_by_category()["METRIC_SCOPE"] == 1
    assert ledger.count_by_category()["LAYOUT_ACTION"] == 1


def test_03_diff_ledger_filtering_and_counts():
    """Test entry filtering by category and severity, as well as summary stats."""
    ledger = DiffLedger(candidate_name="张三")

    ledger.add_entry(category=DiffCategory.ROLE_HIERARCHY, field="r1", baseline_zh="a", tailored_en="b", severity=DiffSeverity.ALIGNED, explanation="", action_taken="")
    ledger.add_entry(category=DiffCategory.ROLE_HIERARCHY, field="r2", baseline_zh="c", tailored_en="d", severity=DiffSeverity.INFLATION_PREVENTED, explanation="", action_taken="")
    ledger.add_entry(category=DiffCategory.METRIC_SCOPE, field="m1", baseline_zh="e", tailored_en="f", severity=DiffSeverity.INFLATION_PREVENTED, explanation="", action_taken="")
    ledger.add_entry(category=DiffCategory.CREDENTIAL_FIDELITY, field="c1", baseline_zh="g", tailored_en="h", severity=DiffSeverity.ALIGNED, explanation="", action_taken="")
    ledger.add_entry(category=DiffCategory.LAYOUT_ACTION, field="l1", baseline_zh="i", tailored_en="j", severity=DiffSeverity.INFO, explanation="", action_taken="")
    ledger.add_entry(category=DiffCategory.GENERAL_FACT, field="g1", baseline_zh="k", tailored_en="l", severity=DiffSeverity.CAUTION, explanation="", action_taken="")

    # Category filtering
    role_entries = ledger.get_entries_by_category(DiffCategory.ROLE_HIERARCHY)
    assert len(role_entries) == 2
    assert [e.field for e in role_entries] == ["r1", "r2"]

    # Severity filtering
    prevented = ledger.get_entries_by_severity(DiffSeverity.INFLATION_PREVENTED)
    assert len(prevented) == 2
    assert [e.field for e in prevented] == ["r2", "m1"]

    # Counts
    sev_counts = ledger.count_by_severity()
    assert sev_counts["INFLATION_PREVENTED"] == 2
    assert sev_counts["ALIGNED"] == 2
    assert sev_counts["INFO"] == 1
    assert sev_counts["CAUTION"] == 1

    cat_counts = ledger.count_by_category()
    assert cat_counts["ROLE_HIERARCHY"] == 2
    assert cat_counts["METRIC_SCOPE"] == 1
    assert cat_counts["CREDENTIAL_FIDELITY"] == 1
    assert cat_counts["LAYOUT_ACTION"] == 1
    assert cat_counts["GENERAL_FACT"] == 1


def test_04_from_fact_guard_result_inflated_resume(sample_candidate_profile, sample_inflated_tailored):
    """Test that FactVerificationGuard audit results on inflated resume populate DiffLedger correctly."""
    guard = FactVerificationGuard(sample_candidate_profile)
    guard_result = guard.verify_facts(sample_inflated_tailored)

    assert guard_result["passed"] is False
    assert len(guard_result["role_inflations"]) >= 3
    assert len(guard_result["drifts"]) >= 3

    ledger = DiffLedger.from_fact_guard_result(
        guard_result=guard_result,
        baseline_profile=sample_candidate_profile,
        tailored_data=sample_inflated_tailored,
    )

    assert ledger.candidate_name == "张明"
    assert len(ledger.entries) > 0

    # Verify that title escalations were captured
    role_entries = ledger.get_entries_by_category(DiffCategory.ROLE_HIERARCHY)
    claimed_roles = [e.tailored_en for e in role_entries]
    assert any("Volunteer Field Lead" in r for r in claimed_roles)
    assert any("Brand Promotion Specialist" in r for r in claimed_roles)
    assert any("Student Affairs Representative" in r for r in claimed_roles)

    # Verify that scope drifts were captured
    metric_entries = ledger.get_entries_by_category(DiffCategory.METRIC_SCOPE)
    metric_fields = [e.field for e in metric_entries]
    assert "metric.livestream_sessions" in metric_fields
    assert "metric.prospective_users" in metric_fields
    assert "metric.gmv_currency" in metric_fields

    # Detection does not mean the input was corrected or an inflation prevented
    for e in role_entries:
        if e.tailored_en in ["Volunteer Field Lead", "Brand Promotion Specialist", "Student Affairs Representative"]:
            assert e.severity == DiffSeverity.CAUTION
    assert ledger.to_dict()["summary"]["inflations_prevented"] == 0
    assert ledger.to_dict()["summary"]["issues_detected"] > 0


def test_05_from_fact_guard_result_substantive_coverage(sample_candidate_profile, sample_grounded_tailored):
    """Actual translations are observed differences, not invented corrections."""
    ledger = DiffLedger.from_fact_guard_result(
        guard_result=FactVerificationGuard(sample_candidate_profile).verify_facts(sample_grounded_tailored),
        baseline_profile=sample_candidate_profile,
        tailored_data=sample_grounded_tailored,
    )
    entries = {e.field: e for e in ledger.entries}
    for index in range(3):
        entry = entries[f"projects[{index}].role"]
        assert entry.baseline_zh == sample_candidate_profile["projects"][index]["role"]
        assert entry.tailored_en == sample_grounded_tailored["projects"][index]["role"]
        assert entry.severity == DiffSeverity.CAUTION
        assert entry.metadata["change_type"] == "modified"
    assert entries["experience[1].role"].tailored_en == "Editorial Team Member"
    assert entries["candidate.education[0].details"].baseline_zh == "GPA 3.12（专业前15%）"
    assert entries["candidate.education[0].details"].tailored_en == sample_grounded_tailored["candidate"]["education"][0]["details"]
    assert entries["candidate.certifications[0]"].tailored_en == sample_grounded_tailored["candidate"]["certifications"][0]
    assert entries["candidate.education[0].coursework[0]"].metadata["change_type"] == "removed"
    assert entries["candidate.education[0].coursework"].metadata["change_type"] == "added"
    assert ledger.to_dict()["summary"]["inflations_prevented"] == 0
    assert ledger.to_dict()["summary"]["actions_applied"] == 0
    assert ledger.metadata["layout_verification"] == "unknown"
    assert "layout.font_size_floor" not in entries
    assert "layout.orphan_elimination" not in entries


def test_06_markdown_output_format(sample_candidate_profile, sample_grounded_tailored):
    """Test Markdown generation format, alert tags, KPI table, and categorized headers."""
    ledger = DiffLedger.from_fact_guard_result(
        guard_result={"passed": True, "drifts": [], "role_inflations": []},
        baseline_profile=sample_candidate_profile,
        tailored_data=sample_grounded_tailored,
    )
    md = ledger.generate_markdown()

    # Title & Candidate Header
    assert "# 改动溯源与口径对齐报告" in md
    assert "张明" in md

    # GitHub Alerts
    assert "> [!NOTE]" in md
    assert "> [!IMPORTANT]" in md
    assert "> [!TIP]" in md

    # Executive Summary Table
    assert "## 📊 审计概览 (Executive Summary)" in md
    assert "| **审计条目总数 (Total Entries Audited)** |" in md
    assert "| **拦截虚假拔高/范围漂移 (Inflations Prevented)** |" in md
    assert "| **输入值相同 (Input Values Match)** |" in md

    # Categorized Tables
    assert "## 🎖️ 1. 职务与头衔层级对齐 (Role Hierarchy Alignment)" in md
    assert "## 📊 2. 数据统计口径与边界核验 (Metric Scope & Fidelity)" in md
    assert "## 📜 3. 证书与课程保真性 (Credential & Coursework Fidelity)" in md
    assert "## 📐 4. 排版自适应微调动作 (Adaptive Layout Micro-adjustments)" in md

    # Badges
    assert "🛡️ 拦截虚高" in md or "✅ 基线对齐" in md


def test_07_json_output_and_serialization(sample_candidate_profile, sample_grounded_tailored):
    """Test structured JSON output, schema compliance, and deserialization."""
    ledger = DiffLedger.from_fact_guard_result(
        guard_result={"passed": True},
        baseline_profile=sample_candidate_profile,
        tailored_data=sample_grounded_tailored,
    )
    json_str = ledger.generate_json(indent=2)
    assert isinstance(json_str, str)

    data = json.loads(json_str)
    assert data["title"] == "改动溯源与口径对齐报告 (Diff Ledger)"
    assert data["candidate_name"] == "张明"
    assert "summary" in data
    assert "total_entries" in data["summary"]
    assert data["summary"]["total_entries"] == len(ledger.entries)
    assert "category_counts" in data
    assert "entries" in data
    assert len(data["entries"]) == len(ledger.entries)

    # Check entry format
    first_entry = data["entries"][0]
    for required_key in ["category", "field", "baseline_zh", "tailored_en", "severity", "explanation", "action_taken"]:
        assert required_key in first_entry


def test_08_cli_summary_format(sample_candidate_profile, sample_grounded_tailored):
    """Test CLI summary box formatting and readability."""
    ledger = DiffLedger.from_fact_guard_result(
        guard_result={"passed": True},
        baseline_profile=sample_candidate_profile,
        tailored_data=sample_grounded_tailored,
    )
    cli = ledger.generate_cli_summary()

    assert "=" * 80 in cli
    assert "-" * 80 in cli
    assert "张明" in cli
    assert "Diff Ledger Summary" in cli
    assert "[🎖️ 职务层级对齐 (Role Hierarchy)]" in cli
    assert "[📊 数据口径对齐 (Metric Scope)]" in cli
    assert "[📜 证书课程保真 (Credential & Coursework)]" in cli
    assert "[📐 排版自适应动作 (Adaptive Layout)]" in cli


def test_09_save_to_disk(sample_candidate_profile):
    """Test saving ledger as .md and .json to output directory."""
    ledger = DiffLedger(candidate_name="张明")
    ledger.add_entry(
        category=DiffCategory.ROLE_HIERARCHY,
        field="role.editorial",
        baseline_zh="编辑部成员",
        tailored_en="Editorial Team Member",
        severity=DiffSeverity.ALIGNED,
        explanation="职务保真",
        action_taken="核验合规",
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        # Default base_name
        paths = ledger.save(temp_dir)
        assert "markdown" in paths and "json" in paths
        assert paths["markdown"].name == "resume_diff_ledger.md"
        assert paths["json"].name == "resume_diff_ledger.json"
        assert paths["markdown"].exists()
        assert paths["json"].exists()

        md_content = paths["markdown"].read_text(encoding="utf-8")
        json_content = paths["json"].read_text(encoding="utf-8")
        assert "编辑部成员" in md_content
        assert "Editorial Team Member" in json_content

        # Custom base_name
        custom_paths = ledger.save(temp_dir, base_name="custom_fan")
        assert custom_paths["markdown"].name == "custom_fan_diff_ledger.md"
        assert custom_paths["json"].name == "custom_fan_diff_ledger.json"
        assert custom_paths["markdown"].exists()
        assert custom_paths["json"].exists()


def test_10_empty_and_minimal_ledger():
    """Test ledger behavior with empty entries and default values."""
    empty_ledger = DiffLedger()
    assert len(empty_ledger.entries) == 0
    assert empty_ledger.count_by_severity()["ALIGNED"] == 0
    assert empty_ledger.count_by_category()["ROLE_HIERARCHY"] == 0

    md = empty_ledger.generate_markdown()
    assert "# 改动溯源与口径对齐报告" in md
    assert "**0**" in md  # 0 entries

    json_data = json.loads(empty_ledger.generate_json())
    assert json_data["summary"]["total_entries"] == 0
    assert len(json_data["entries"]) == 0

    cli = empty_ledger.generate_cli_summary()
    assert "审计总计: 0" in cli


def test_11_custom_entries_and_metadata():
    """Test that custom metadata attached to entries is preserved across export formats."""
    ledger = DiffLedger(candidate_name="李四", metadata={"batch_id": "BATCH-2026"})
    e = ledger.add_entry(
        category=DiffCategory.GENERAL_FACT,
        field="projects[0].bullet[0]",
        baseline_zh="负责分布式缓存设计",
        tailored_en="Designed high-throughput distributed caching architecture",
        severity=DiffSeverity.ALIGNED,
        explanation="技术术语完全对齐 SSOT 事实",
        action_taken="核验通过",
        metadata={"fingerprint": "abc123xyz", "confidence": 0.99},
    )

    assert e.metadata["fingerprint"] == "abc123xyz"
    assert e.metadata["confidence"] == 0.99

    d = ledger.to_dict()
    assert d["metadata"]["batch_id"] == "BATCH-2026"
    assert d["entries"][0]["metadata"]["fingerprint"] == "abc123xyz"


def test_12_cmd_diff_audit_cli(sample_candidate_profile, capsys):
    """Test cmd_diff_audit presentation command with terminal output, --json, and --output-dir."""
    import argparse
    from presentation.commands.diff_cmd import cmd_diff_audit

    with tempfile.TemporaryDirectory() as temp_dir:
        t_dir = Path(temp_dir)
        baseline_file = t_dir / "baseline.json"
        tailored_file = t_dir / "tailored.json"
        out_sub = t_dir / "out_diff"

        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(sample_candidate_profile, f, ensure_ascii=False)
        with open(tailored_file, "w", encoding="utf-8") as f:
            json.dump(sample_candidate_profile, f, ensure_ascii=False)

        # 1. Test markdown terminal output & writing to --output-dir
        args = argparse.Namespace(
            baseline_file=str(baseline_file),
            tailored_file=str(tailored_file),
            output_dir=str(out_sub),
            json=False,
        )
        cmd_diff_audit(args)
        captured = capsys.readouterr()
        assert "# 改动溯源与口径对齐报告" in captured.out
        assert "Diff Ledger report saved" in captured.out

        # Verify files on disk
        md_file = out_sub / "resume_diff_ledger.md"
        json_file = out_sub / "resume_diff_ledger.json"
        assert md_file.exists()
        assert json_file.exists()
        assert "张明" in md_file.read_text(encoding="utf-8")

        # 2. Test --json flag
        args_json = argparse.Namespace(
            baseline_file=str(baseline_file),
            tailored_file=str(tailored_file),
            output_dir=None,
            json=True,
        )
        cmd_diff_audit(args_json)
        captured_json = capsys.readouterr()
        parsed = json.loads(captured_json.out)
        assert "summary" in parsed
        assert parsed["candidate_name"] == "张明"
        assert parsed["summary"]["total_entries"] > 0



@pytest.mark.parametrize("trigger", [
    "Maintained 30+ services.", "GPA 3.8/4.0", "Processed 800,000 records.",
    "Served 5,000+ requests.", "推广成员", "志愿实践成员", "班级心理委员",
    "WPS spreadsheet user", "NCRE Python", "工程经济学",
])
def test_identical_profile_never_invents_example_facts(trigger):
    profile = {"candidate": {"name": "Synthetic Auditor", "details": trigger}}
    ledger = DiffLedger.from_fact_guard_result({}, profile, profile)
    source_entries = [e for e in ledger.entries if e.category != DiffCategory.LAYOUT_ACTION]
    assert [e.field for e in source_entries] == ["candidate.details", "candidate.name"]
    assert source_entries[0].baseline_zh == trigger
    assert source_entries[0].tailored_en == trigger
    assert all(e.metadata["event_status"] == "unchanged" for e in source_entries)
    assert ledger.to_dict()["summary"]["observed_changes"] == 0
    assert ledger.to_dict()["summary"]["inflations_prevented"] == 0
    assert len(ledger.get_entries_by_category(DiffCategory.LAYOUT_ACTION)) == 1


def test_reports_exact_additions_deletions_and_typed_values():
    before = {"candidate": {"school": "Synthetic School", "gpa": 3.8, "empty": None}, "skills": ["Python"], "flag": False}
    after = {"candidate": {"school": "Different School", "gpa": 3.9, "empty": ""}, "skills": ["Python", "Rust"], "flag": 0}
    ledger = DiffLedger.from_fact_guard_result({}, before, after)
    entries = {e.field: e for e in ledger.entries}
    assert entries["candidate.school"].baseline_zh == "Synthetic School"
    assert entries["candidate.school"].tailored_en == "Different School"
    assert entries["candidate.gpa"].metadata["baseline_value"] == 3.8
    assert entries["candidate.empty"].metadata["change_type"] == "modified"
    assert entries["flag"].metadata["change_type"] == "modified"
    added = entries["skills[1]"]
    assert added.metadata["baseline_present"] is False
    assert added.metadata["tailored_value"] == "Rust"
    removed = DiffLedger.from_fact_guard_result({}, after, before)
    assert next(e for e in removed.entries if e.field == "skills[1]").metadata["change_type"] == "removed"


def test_guard_suggestions_remain_detected_and_do_not_mutate_inputs():
    import copy
    before = {"role": "Member"}
    after = {"role": "Lead"}
    result = {"role_inflations": [{"claimed_role": "Lead", "baseline_role": "Member", "fix_suggestion": "Member"}],
              "drifts": [{"rule_id": "METRIC_DRIFT", "claimed_metric": 20, "verified_baseline": 0, "fix_suggestion": "Use 0"}]}
    original = copy.deepcopy((before, after, result))
    ledger = DiffLedger.from_fact_guard_result(result, before, after)
    assert (before, after, result) == original
    assert ledger.to_dict()["summary"]["issues_detected"] == 2
    assert ledger.to_dict()["summary"]["inflations_prevented"] == 0
    assert ledger.to_dict()["summary"]["actions_applied"] == 0
    detected = [e for e in ledger.entries if e.metadata["event_status"] == "detected"]
    assert all(e.severity == DiffSeverity.CAUTION for e in detected)
    assert detected[1].baseline_zh == "0"
    assert "Member" in detected[0].action_taken
    assert "未应用" in detected[0].action_taken
    assert "🛡️ 口径校准" not in ledger.generate_cli_summary()
    assert "✅ 对齐: 原“Member”" not in ledger.generate_cli_summary()


@pytest.mark.parametrize("metadata", [None, {}, {"body_font_pt": 8.0}, {"solved": False, "orphans_mitigated": 0},
                                        {"solved": True, "body_font_pt": 10.5, "applied_compressions": ["Synthetic action"]}])
def test_layout_metadata_never_implies_render_verification(metadata):
    ledger = DiffLedger.from_fact_guard_result({}, {}, {}, layout_metadata=metadata)
    entries = ledger.get_entries_by_category(DiffCategory.LAYOUT_ACTION)
    assert ledger.metadata["layout_verification"] == "unknown"
    assert entries[0].field == "layout.verification"
    assert entries[0].severity == DiffSeverity.CAUTION
    assert all(e.severity != DiffSeverity.ALIGNED for e in entries)
    assert len(entries) == 1 + len(metadata or {})
    for entry in entries[1:]:
        key = entry.field.removeprefix("layout.")
        assert entry.metadata["reported_value"] == metadata[key]
        assert entry.metadata["event_status"] == "reported"
    report = ledger.generate_markdown()
    assert "微调完成" not in report
    assert "排版自适应微调完成" not in report
    assert ledger.to_dict()["summary"]["actions_applied"] == 0


def test_missing_inputs_or_text_comparison_have_explicit_limits():
    unknown = DiffLedger.from_fact_guard_result()
    assert unknown.metadata["comparison"]["status"] == "unknown"
    assert unknown.metadata["fact_verification"]["status"] == "unknown"
    text = DiffLedger.from_fact_guard_result(None, {"school": "Synthetic School"}, "A different school")
    assert text.metadata["comparison"]["status"] == "text_only"
    assert text.entries[0].field == "document"
    assert text.entries[0].baseline_zh == '{"school": "Synthetic School"}'
    assert text.entries[0].tailored_en == "A different school"
    assert text.entries[0].severity == DiffSeverity.CAUTION
