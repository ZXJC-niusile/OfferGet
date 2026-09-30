# -*- coding: utf-8 -*-
"""
Tests for OfferGet Role Hierarchy Guard and Metric Scope Drift Guard.

Addresses user-reported AI rewrite defects:
1. Title & Action Inflation:
   - "志愿实践成员" escalated to "Volunteer Field Lead"
   - "推广成员" escalated to "Brand Promotion Specialist"
   - "心理委员" drifted to "Student Affairs Representative"
2. Metric Scope & Entity Drift:
   - Event count vs Asset count: "30+ 场直播" drifted to "30+ custom promo overlays"
   - User scope vs Enterprise lead: "200+ 潜在用户" drifted to "200+ 企业客户线索"
   - Peak metric vs Cumulative aggregation: "单篇最高阅读量 5,000+" drifted to "cumulative 5,000+"
   - Unanchored denominator: "GPA 3.12" drifted to "GPA 3.12 / 4.0"
   - Speculative currency conversion: "80万元" drifted to "$110K USD"
"""

import pytest
from core.registry import QualityRuleRegistry
from core.fact_guard import FactVerificationGuard


# ---------------------------------------------------------------------------
# 1. Role Hierarchy Detection Tests
# ---------------------------------------------------------------------------

def test_detect_role_hierarchy_tiers():
    # Tier 0 (Volunteer / Class committee)
    assert QualityRuleRegistry.detect_role_hierarchy_tier("志愿实践成员")[0] == 0
    assert QualityRuleRegistry.detect_role_hierarchy_tier("心理委员")[0] == 0
    assert QualityRuleRegistry.detect_role_hierarchy_tier("Field Research Volunteer")[0] == 0
    assert QualityRuleRegistry.detect_role_hierarchy_tier("Class Mental Health Representative")[0] == 0

    # Tier 1 (Member / Intern / Associate)
    assert QualityRuleRegistry.detect_role_hierarchy_tier("推广成员")[0] == 1
    assert QualityRuleRegistry.detect_role_hierarchy_tier("编辑部成员")[0] == 1
    assert QualityRuleRegistry.detect_role_hierarchy_tier("直播运营实习生")[0] == 1
    assert QualityRuleRegistry.detect_role_hierarchy_tier("Promotion Team Member")[0] == 1

    # Tier 2 (Specialist / Officer / Coordinator)
    assert QualityRuleRegistry.detect_role_hierarchy_tier("Brand Promotion Specialist")[0] == 2
    assert QualityRuleRegistry.detect_role_hierarchy_tier("新媒体运营专员")[0] == 2
    assert QualityRuleRegistry.detect_role_hierarchy_tier("Operations Specialist")[0] == 2

    # Tier 3 (Lead / Manager / Director / Head)
    assert QualityRuleRegistry.detect_role_hierarchy_tier("Volunteer Field Lead")[0] == 3
    assert QualityRuleRegistry.detect_role_hierarchy_tier("项目负责人")[0] == 3
    assert QualityRuleRegistry.detect_role_hierarchy_tier("Operations Director")[0] == 3
    assert QualityRuleRegistry.detect_role_hierarchy_tier("操盘手")[0] == 3


# ---------------------------------------------------------------------------
# 2. Forbidden Escalation Tests
# ---------------------------------------------------------------------------

def test_role_escalation_forbidden_titles():
    # "志愿实践成员" -> forbidden "Volunteer Field Lead"
    esc = QualityRuleRegistry.check_role_escalation("Volunteer Field Lead", "志愿实践成员")
    assert esc is not None
    assert esc["rule_id"] == "ROLE_HIERARCHY_INFLATION"
    assert "Lead" in esc["reason"] or "forbidden" in esc["reason"]

    # "推广成员" -> forbidden "Brand Promotion Specialist"
    esc = QualityRuleRegistry.check_role_escalation("Brand Promotion Specialist", "推广成员")
    assert esc is not None
    assert esc["rule_id"] == "ROLE_HIERARCHY_INFLATION"

    # "编辑部成员" -> forbidden "Chief Editor"
    esc = QualityRuleRegistry.check_role_escalation("Chief Editor", "编辑部成员")
    assert esc is not None
    assert esc["rule_id"] == "ROLE_HIERARCHY_INFLATION"


# ---------------------------------------------------------------------------
# 3. Protected Domain Drift Tests
# ---------------------------------------------------------------------------

def test_role_domain_drift_psychological_committee():
    # "心理委员" -> "Student Affairs Representative" (drops mental health requirement)
    esc = QualityRuleRegistry.check_role_escalation("Student Affairs Representative", "班级心理委员")
    assert esc is not None
    assert esc["rule_id"] == "ROLE_DOMAIN_DRIFT"

    # "心理委员" -> "Class Mental Health Representative" (preserves mental health anchor)
    ok = QualityRuleRegistry.check_role_escalation("Class Mental Health Representative", "班级心理委员")
    assert ok is None


# ---------------------------------------------------------------------------
# 4. Metric Scope Drift Tests: Currency Conversion
# ---------------------------------------------------------------------------

def test_metric_scope_drift_unauthorized_currency():
    baseline = "创下单场最高 GMV 超 80万元、单场最高同时在线约 600人。"
    claimed_usd = "Achieved single-session peak GMV exceeding ~$110K USD, with 600 peak concurrent viewers."
    claimed_rmb = "Achieved single-session peak GMV exceeding 800,000 RMB, with 600 peak concurrent viewers."

    drifts_usd = QualityRuleRegistry.check_metric_scope_drift(claimed_usd, baseline)
    assert len(drifts_usd) >= 1
    assert any(d["rule_id"] == "SCOPE_UNAUTHORIZED_CURRENCY" for d in drifts_usd)

    drifts_rmb = QualityRuleRegistry.check_metric_scope_drift(claimed_rmb, baseline)
    assert not any(d["rule_id"] == "SCOPE_UNAUTHORIZED_CURRENCY" for d in drifts_rmb)


# ---------------------------------------------------------------------------
# 5. Metric Scope Drift Tests: Unanchored GPA Denominator
# ---------------------------------------------------------------------------

def test_metric_scope_drift_unanchored_denominator():
    baseline = "工学学士在读，土木工程专业，GPA 3.12（专业前15%）"
    claimed_with_denom = "B.Eng. in Civil Engineering | GPA: 3.12 / 4.0 (Top 15%)"
    claimed_clean = "B.Eng. in Civil Engineering | GPA: 3.12 (Top 15%)"

    drifts_denom = QualityRuleRegistry.check_metric_scope_drift(claimed_with_denom, baseline)
    assert len(drifts_denom) >= 1
    assert any(d["rule_id"] == "SCOPE_UNANCHORED_DENOMINATOR" for d in drifts_denom)

    drifts_clean = QualityRuleRegistry.check_metric_scope_drift(claimed_clean, baseline)
    assert not any(d["rule_id"] == "SCOPE_UNANCHORED_DENOMINATOR" for d in drifts_clean)


# ---------------------------------------------------------------------------
# 6. Metric Scope Drift Tests: Event Count to Asset Quantity
# ---------------------------------------------------------------------------

def test_metric_scope_drift_event_to_asset():
    baseline = "独立设计 30+ 场直播专属促单贴片与机制 KT 板"
    claimed_drift = "Independently designed 30+ custom promo overlays and KT boards"
    claimed_grounded = "Designed custom promo overlays and KT boards for 30+ livestream sessions"

    drifts = QualityRuleRegistry.check_metric_scope_drift(claimed_drift, baseline)
    assert any(d["rule_id"] == "SCOPE_EVENT_TO_ASSET" for d in drifts)

    drifts_grounded = QualityRuleRegistry.check_metric_scope_drift(claimed_grounded, baseline)
    assert not any(d["rule_id"] == "SCOPE_EVENT_TO_ASSET" for d in drifts_grounded)


# ---------------------------------------------------------------------------
# 7. Metric Scope Drift Tests: Prospective User to Enterprise Lead
# ---------------------------------------------------------------------------

def test_metric_scope_drift_user_to_enterprise():
    baseline = "落地文创品牌地推执行，单日触达引流潜在用户 200+ 人"
    claimed_drift = "Executed field promotions, acquiring 200+ enterprise clients in a single day"
    claimed_grounded = "Executed field promotions, engaging 200+ prospective users in a single day"

    drifts = QualityRuleRegistry.check_metric_scope_drift(claimed_drift, baseline)
    assert any(d["rule_id"] == "SCOPE_USER_TO_ENTERPRISE" for d in drifts)

    drifts_grounded = QualityRuleRegistry.check_metric_scope_drift(claimed_grounded, baseline)
    assert not any(d["rule_id"] == "SCOPE_USER_TO_ENTERPRISE" for d in drifts_grounded)


# ---------------------------------------------------------------------------
# 8. Metric Scope Drift Tests: Peak Single-Article to Cumulative Total
# ---------------------------------------------------------------------------

def test_metric_scope_drift_peak_to_cumulative():
    baseline = "统筹校官方公众号内容采编与排版，累计输出推文 15+ 篇（单篇最高阅读量 5,000+）"
    claimed_drift = "Published official school WeChat posts with 5,000+ total cumulative readership"
    claimed_grounded = "Published official school WeChat posts, achieving peak readership of 5,000+ for a single article"

    drifts = QualityRuleRegistry.check_metric_scope_drift(claimed_drift, baseline)
    assert any(d["rule_id"] == "SCOPE_PEAK_TO_CUMULATIVE" for d in drifts)

    drifts_grounded = QualityRuleRegistry.check_metric_scope_drift(claimed_grounded, baseline)
    assert not any(d["rule_id"] == "SCOPE_PEAK_TO_CUMULATIVE" for d in drifts_grounded)


# ---------------------------------------------------------------------------
# 9. FactVerificationGuard End-to-End Integration Test
# ---------------------------------------------------------------------------

def test_fact_guard_end_to_end_role_and_scope():
    master_profile = {
        "candidate": {
            "name": "范增煜",
            "education": [
                {
                    "school": "青岛理工大学",
                    "degree": "工学学士在读",
                    "major": "土木工程",
                    "details": "GPA 3.12（专业前15%）"
                }
            ]
        },
        "experience": [
            {
                "company": "交个朋友",
                "role": "直播运营",
                "highlights": [
                    "独立操盘 90+ 场直播全生命周期运营",
                    "独立设计 30+ 场直播专属促单贴片与机制 KT 板",
                    "创下单场最高 GMV 超 80万元、单场最高同时在线约 600人。"
                ]
            },
            {
                "company": "桃蹊礼品",
                "role": "新媒体运营与线下推广",
                "highlights": [
                    "主导线下核心企业客户回访调研 50+ 家，提炼定制礼品需求清单 30+ 份",
                    "落地文创品牌地推执行，单日触达引流潜在用户 200+ 人"
                ]
            }
        ],
        "projects": [
            {
                "name": "洪泽湖沿岸生态保护与居民用水处理探索",
                "role": "志愿实践成员",
                "bullets": [
                    "深入洪泽湖沿岸村落推进实地走访调研，采集水样并输出水质调研报告"
                ]
            },
            {
                "name": "青岛本地文创IP小海鸥谢谢",
                "role": "推广成员",
                "bullets": [
                    "操盘青岛本地文创 IP 线下快闪与地推拓客，触达转化潜在粉丝 500+ 人"
                ]
            },
            {
                "name": "班级心理健康建设",
                "role": "班级心理委员",
                "bullets": [
                    "统筹协调班级信息流转与突发事件响应，建立 40+ 人班集体高效沟通与档案台账机制"
                ]
            }
        ]
    }

    guard = FactVerificationGuard(master_profile)

    # 1. Unconstrained inflated resume (simulating AI rewrite defects)
    inflated_tailored = {
        "experience": [
            {
                "company": "交个朋友",
                "role": "直播运营",
                "highlights": [
                    "Led end-to-end execution for 90+ livestream sessions.",
                    "Independently created 30+ custom promo overlays and KT boards.",  # Event to Asset drift
                    "Achieved peak single-session GMV exceeding ~$110K USD with 600 concurrent viewers."  # Currency drift
                ]
            },
            {
                "company": "桃蹊礼品",
                "role": "新媒体运营与线下推广",
                "highlights": [
                    "Conducted structured interviews with 50+ corporate clients.",
                    "Acquired 200+ enterprise clients through offline marketing."  # User to Enterprise drift
                ]
            }
        ],
        "projects": [
            {
                "name": "洪泽湖沿岸生态保护与居民用水处理探索",
                "role": "Volunteer Field Lead",  # Title inflation Tier 0 -> Tier 3
                "bullets": [
                    "Led field research and water sampling in lakeside villages."
                ]
            },
            {
                "name": "青岛本地文创IP小海鸥谢谢",
                "role": "Brand Promotion Specialist",  # Title inflation Tier 1 -> Tier 2
                "bullets": [
                    "Executed pop-up events and offline marketing, converting 500+ prospective fans."
                ]
            },
            {
                "name": "班级心理健康建设",
                "role": "Student Affairs Representative",  # Domain drift (dropped mental health)
                "bullets": [
                    "Managed communications and student affairs for 40+ students."
                ]
            }
        ]
    }

    result_inflated = guard.verify_facts(inflated_tailored)
    assert result_inflated["passed"] is False
    assert result_inflated["verdict"] == "FACT_DRIFT_DETECTED"
    assert len(result_inflated["role_inflations"]) >= 3
    assert len(result_inflated["drifts"]) >= 3
    assert result_inflated["summary"]["role_inflation_count"] >= 3
    assert result_inflated["summary"]["drift_count"] >= 3

    # 2. Grounded resume (strictly aligned with SSOT baseline)
    grounded_tailored = {
        "experience": [
            {
                "company": "交个朋友",
                "role": "Livestream Operations Intern",
                "highlights": [
                    "Led end-to-end execution for 90+ livestream sessions.",
                    "Designed custom promo overlays and KT boards for 30+ livestream sessions.",
                    "Achieved peak single-session GMV exceeding 800,000 RMB with 600 concurrent viewers."
                ]
            },
            {
                "company": "桃蹊礼品",
                "role": "New Media & Offline Promotion Intern",
                "highlights": [
                    "Conducted structured interviews with 50+ corporate clients.",
                    "Engaged 200+ prospective users in a single day through offline marketing."
                ]
            }
        ],
        "projects": [
            {
                "name": "洪泽湖沿岸生态保护与居民用水处理探索",
                "role": "Field Research Volunteer",  # Grounded Tier 0
                "bullets": [
                    "Conducted field research and water sampling in lakeside villages."
                ]
            },
            {
                "name": "青岛本地文创IP小海鸥谢谢",
                "role": "Promotion Team Member",  # Grounded Tier 1
                "bullets": [
                    "Executed pop-up events and offline marketing, converting 500+ prospective fans."
                ]
            },
            {
                "name": "班级心理健康建设",
                "role": "Class Mental Health Representative",  # Grounded Tier 0 with mental health anchor
                "bullets": [
                    "Managed communications and student mental well-being support for 40+ students."
                ]
            }
        ]
    }

    result_grounded = guard.verify_facts(grounded_tailored)
    assert result_grounded["passed"] is True
    assert result_grounded["verdict"] == "FACT_CHECK_PASSED"
    assert len(result_grounded["role_inflations"]) == 0
    assert len(result_grounded["drifts"]) == 0
    assert result_grounded["score"] == 100.0
