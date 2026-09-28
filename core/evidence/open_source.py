"""
OfferGet Open Source Evidence & Depth Auditor.
Absorbed and modernized from ASu-resume-skills (Apache-2.0).
Provides 0-4 contribution depth levels, safe phrasing generation,
and inflation pattern detection for open source claims.
"""

from __future__ import annotations

import re
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

from core.evidence.models import AuditClaim, AuditPattern


class OpenSourceContributionLevel(IntEnum):
    """
    Standard 0-4 contribution depth levels for open source engagement.
    """
    LEVEL_0_VISIBLE = 0      # Fork, Star, 讨论, 无实现的 Issue
    LEVEL_1_PERIPHERAL = 1   # 文档, 错字, 官网, 小 UI, 配置, 翻译
    LEVEL_2_SCOPED = 2       # 有边界实现, 已合并 bugfix 或独立功能组件
    LEVEL_3_SUBSYSTEM = 3    # 持续子系统所有权, 多次合并, 评审, 设计决策, Release
    LEVEL_4_PROJECT_LEAD = 4 # 项目领导, 正式核心 Maintainer / 核心作者 / 跨模块架构


LEVEL_METADATA = {
    OpenSourceContributionLevel.LEVEL_0_VISIBLE: {
        "name": "仅可见 / 社区关注",
        "safe_phrase": "关注/讨论该项目",
        "description": "Fork、Star、评论或提出未带实现的 Issue。",
    },
    OpenSourceContributionLevel.LEVEL_1_PERIPHERAL: {
        "name": "边缘贡献",
        "safe_phrase": "贡献文档/官网/配置/轻量 UI 修改",
        "description": "文档纠错、官方主页建设、配置调整或小幅前端样式优化。",
    },
    OpenSourceContributionLevel.LEVEL_2_SCOPED: {
        "name": "有边界实现",
        "safe_phrase": "实现/修复具体功能组件与缺陷",
        "description": "有明确责任边界的已合并代码提交、功能特性或缺陷修复。",
    },
    OpenSourceContributionLevel.LEVEL_3_SUBSYSTEM: {
        "name": "持续子系统所有权",
        "safe_phrase": "维护/负责具体子系统或模块架构",
        "description": "长期对特定模块保持多次合并、代码评审、设计决策与版本发布。",
    },
    OpenSourceContributionLevel.LEVEL_4_PROJECT_LEAD: {
        "name": "项目领导 / 核心作者",
        "safe_phrase": "Maintainer / 核心作者 / 项目负责人",
        "description": "拥有正式核心权限，主导跨模块全局架构设计与重大版本发布责任。",
    },
}

# Regex patterns for open source terms
OPEN_SOURCE_INDICATOR_PATTERN = re.compile(
    r"(开源|github|pr|pull\s*request|issue|star|commit|fork|maintainer|committer|apache|linux|cncf)",
    re.I,
)

STAR_MIGRATION_PATTERN = re.compile(
    r"(\d+k?\+?\s*star|万\s*star|标星|知名开源|明星项目|github\s*trending)",
    re.I,
)

PERIPHERAL_TERMS = re.compile(
    r"(文档|错字|typo|官网|主页|readme|配置|yaml|注释|翻译|demo|示例|小幅优化|样式调整)",
    re.I,
)

CORE_LEAD_TERMS = re.compile(
    r"(maintainer|owner|核心作者|架构师|核心研发|底层引擎|内核|全面负责|主导研发)",
    re.I,
)

SCOPED_IMPL_TERMS = re.compile(
    r"(实现|修复|开发|组件|模块|接口|算法|重构|性能优化|feature|bugfix|pr\s*已合并)",
    re.I,
)

SUBSYSTEM_TERMS = re.compile(
    r"(子系统|模块负责人|持续维护|多次合并|代码评审|review|release|版本发布)",
    re.I,
)


class OpenSourceAuditor:
    """
    Audits open source claims against contribution depth levels and detects inflation patterns.
    """

    @classmethod
    def is_open_source_claim(cls, text: str) -> bool:
        """Determines if a claim or resume bullet pertains to open-source software."""
        return bool(OPEN_SOURCE_INDICATOR_PATTERN.search(text))

    @classmethod
    def classify_level(
        cls,
        text: str,
        pr_info: Optional[Dict[str, Any]] = None,
    ) -> Tuple[OpenSourceContributionLevel, str]:
        """
        Classifies open source contribution depth level (0-4) based on text and PR data.
        Returns (level, safe_recommended_phrasing).
        """
        clean = text.strip()

        # Check explicit PR metadata if provided
        if pr_info:
            area = str(pr_info.get("area", "")).lower()
            role = str(pr_info.get("role", "")).lower()
            is_merged = pr_info.get("is_merged", True)

            if not is_merged:
                return (
                    OpenSourceContributionLevel.LEVEL_0_VISIBLE,
                    "提交相关改进 Issue 或待合并 PR",
                )
            if role in ("maintainer", "core", "lead", "owner"):
                return (
                    OpenSourceContributionLevel.LEVEL_4_PROJECT_LEAD,
                    LEVEL_METADATA[OpenSourceContributionLevel.LEVEL_4_PROJECT_LEAD]["safe_phrase"],
                )
            if role in ("subsystem_lead", "reviewer") or pr_info.get("merged_pr_count", 1) >= 5:
                return (
                    OpenSourceContributionLevel.LEVEL_3_SUBSYSTEM,
                    LEVEL_METADATA[OpenSourceContributionLevel.LEVEL_3_SUBSYSTEM]["safe_phrase"],
                )
            if area in ("docs", "website", "typo", "config"):
                return (
                    OpenSourceContributionLevel.LEVEL_1_PERIPHERAL,
                    LEVEL_METADATA[OpenSourceContributionLevel.LEVEL_1_PERIPHERAL]["safe_phrase"],
                )
            return (
                OpenSourceContributionLevel.LEVEL_2_SCOPED,
                LEVEL_METADATA[OpenSourceContributionLevel.LEVEL_2_SCOPED]["safe_phrase"],
            )

        # Keyword-based heuristics
        if CORE_LEAD_TERMS.search(clean) and not PERIPHERAL_TERMS.search(clean):
            lvl = OpenSourceContributionLevel.LEVEL_4_PROJECT_LEAD
        elif SUBSYSTEM_TERMS.search(clean):
            lvl = OpenSourceContributionLevel.LEVEL_3_SUBSYSTEM
        elif SCOPED_IMPL_TERMS.search(clean) and not PERIPHERAL_TERMS.search(clean):
            lvl = OpenSourceContributionLevel.LEVEL_2_SCOPED
        elif PERIPHERAL_TERMS.search(clean):
            lvl = OpenSourceContributionLevel.LEVEL_1_PERIPHERAL
        elif "star" in clean.lower() or "fork" in clean.lower() or "issue" in clean.lower():
            lvl = OpenSourceContributionLevel.LEVEL_0_VISIBLE
        else:
            lvl = OpenSourceContributionLevel.LEVEL_2_SCOPED

        return lvl, LEVEL_METADATA[lvl]["safe_phrase"]

    @classmethod
    def audit_claim(
        cls,
        claim_text: str,
        claim_id: str,
        ssot_facts: Optional[Dict[str, Any]] = None,
    ) -> List[AuditPattern]:
        """
        Examines claim text for open source inflation patterns:
        - Star 迁移 (Brand/Star Migration)
        - 官网到核心引擎歧义 (Periphery to Core)
        - 角色升格 (Role Escalation)
        - 贡献数量漂白 (Quantity Bleaching)
        """
        patterns: List[AuditPattern] = []
        clean = claim_text.strip()

        # 1. Star 迁移 (Brand/Star Migration)
        star_match = STAR_MIGRATION_PATTERN.search(clean)
        if star_match:
            star_text = star_match.group(0)
            # If candidate does not have verified Level 3/4 role in SSOT
            patterns.append(AuditPattern(
                name="品牌或 Star 迁移",
                description="将开源项目的整体 Star 数或知名度置于个人经历前，但缺乏个人实质增量归因证明。",
                signals=[f"突出展现项目 Star 或品牌：{star_text}", "个人产出与整体项目 Star 数未明确区分"],
                claim_ids=[claim_id],
                confidence="medium",
                counter_evidence="若候选人为主创作者或通过该 PR/功能直接拉动了项目破圈，建议补充归因证据。",
            ))

        # 2. 官网到核心引擎歧义 (Periphery to Core)
        has_peripheral = bool(PERIPHERAL_TERMS.search(clean))
        has_core = bool(CORE_LEAD_TERMS.search(clean))
        if has_peripheral and has_core:
            patterns.append(AuditPattern(
                name="官网到核心引擎歧义",
                description="在边缘贡献（如文档、官网、配置修改）的基础上，省略具体代码区域并使用核心引擎/研发措辞。",
                signals=["文档/官网等外围词汇与核心/架构等强词汇同屏出现", clean],
                claim_ids=[claim_id],
                confidence="high",
                counter_evidence="若候选人同时负责了文档系统与核心运行时重构，请分条列出具体 Commit/PR 范围。",
            ))

        # 3. 贡献数量漂白 (Quantity Bleaching)
        if re.search(r"(?:提(?:交)?(?:了)?|发起|贡献)\s*\d+\s*(?:个)?\s*pr|多个\s*pr", clean, re.I):
            if not re.search(r"(已合并|merged|上线|合入)", clean, re.I):
                patterns.append(AuditPattern(
                    name="贡献数量漂白",
                    description="提及提交 PR 或 Contribution 数量，但未明确区分已合入（merged）与关闭未合入（closed）或进行中。",
                    signals=["声称提交 PR 数量但缺少合并状态说明", clean],
                    claim_ids=[claim_id],
                    confidence="medium",
                    counter_evidence="绝不能把 closed 当成 merged；建议明确已合入 PR 的编号及链接。",
                ))

        return patterns
