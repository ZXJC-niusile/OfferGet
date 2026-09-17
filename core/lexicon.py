"""
OfferGet Core Lexicon (core/lexicon.py)
=======================================
Single Source of Truth (SSOT) for linguistic, audit, and resume feature dictionaries.

Standardized Dictionaries:
1. Verb Hierarchy (1~5 levels: Support < Participate < Responsible < Drive < Lead)
2. Strong and Weak Action Verbs (Chinese & English)
3. Role Ranks (0~3 levels: Planning / Participant / Lead / Independent Owner)
4. Quantified Metrics Regex Patterns
5. Technology & Version Whitelist (Non-metric identifiers)
6. Inflation Identification Patterns (P1 Scope, P2 Superlative, P3 Temporal, P4 0->1, etc.)
7. Forbidden Buzzwords & AI Cliches (Superlatives, Hyperbolic words, Academic & Industry cliches)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


# ============================================================================
# 1. Verb Hierarchy (1 ~ 5 Levels)
# ============================================================================
# Level 1: 支持 / 协助 (Support / Assist)
# Level 2: 参与 / 共建 (Participate / Contribute)
# Level 3: 负责 / 研发落地 (Responsible / Implement)
# Level 4: 推动 / 牵引 (Drive / Advance)
# Level 5: 主导 / 统筹架构 (Lead / Architect / Owner)

VERB_HIERARCHY: Dict[str, int] = {
    # Level 1: 支持 / 协助
    "支持": 1, "协助": 1, "配合": 1, "辅助": 1,
    "assisted in": 1, "helped with": 1, "supported": 1, "aided": 1,

    # Level 2: 参与 / 共建
    "参与": 2, "共建": 2, "贡献": 2, "contribute": 2, "contributed to": 2,
    "participated in": 2, "collaborated on": 2, "took part in": 2, "参编": 2,

    # Level 3: 负责 / 研发落地
    "负责": 3, "主要负责": 3, "承担": 3, "落地": 3, "实现": 3, "搭建": 3,
    "开发": 3, "设计并实现": 3, "responsible for": 3, "implemented": 3,
    "built": 3, "engineered": 3, "deployed": 3, "customized": 3,

    # Level 4: 推动 / 牵引
    "推动": 4, "推进": 4, "牵引": 4, "促进": 4, "带动": 4,
    "drove": 4, "accelerated": 4, "streamlined": 4, "scaled": 4, "optimized": 4,

    # Level 5: 主导 / 统筹架构
    "主导": 5, "统筹": 5, "引领": 5, "主持": 5, "从0到1": 5, "独立负责": 5,
    "owner": 5, "architected": 5, "spearheaded": 5, "pioneered": 5, "led": 5,
    "orchestrated": 5, "overhauled": 5, "invented": 5,
}

STRONG_VERBS_THRESHOLD: int = 4  # Level 4 (推动) and Level 5 (主导) are strong verbs


# ============================================================================
# 2. Strong and Weak Action Verbs (ZH & EN)
# ============================================================================

# Action verbs - Strong (reward in ATS & Impact scoring)
STRONG_ACTION_VERBS_EN: Set[str] = {
    "built", "architected", "engineered", "spearheaded", "shipped", "optimized",
    "deployed", "pioneered", "led", "scaled", "accelerated", "authored",
    "designed", "implemented", "streamlined", "delivered", "orchestrated",
    "formulated", "executed", "overhauled", "customized", "refactored",
    "automated", "established", "invented", "slashed", "drove"
}

STRONG_ACTION_VERBS_ZH: Set[str] = {
    "主导", "架构", "研发", "搭建", "攻坚", "优化", "实现", "交付",
    "推进", "开源", "设计", "落地", "首创", "降低", "提升", "节省",
    "自研", "定制", "重构", "重塑", "打通", "构建", "牵引", "主持"
}

# Action verbs - Weak (penalize in ATS scoring)
WEAK_ACTION_VERBS_EN: Set[str] = {
    "responsible for", "assisted in", "helped with", "worked on",
    "participated in", "contributed to", "handled", "involved in",
    "tasked with", "supported", "aided", "collaborated on", "took part in"
}

WEAK_ACTION_VERBS_ZH: Set[str] = {
    "负责", "参与", "协助", "配合", "辅助", "支持", "做过", "了解", "接触过", "跟进"
}


# ============================================================================
# 3. Role Ranks (0 ~ 3 Levels)
# ============================================================================
# Rank 0: 规划 / 探索 (Planning / Exploratory)
# Rank 1: 参与 / 协助 (Contributor / Participant)
# Rank 2: 主导 / 负责人 (Lead / Maintainer)
# Rank 3: 独立Owner / 从0到1 (Independent Owner)

ROLE_RANKS: Dict[str, int] = {
    # Rank 0: Planning / Exploratory
    "计划": 0, "规划": 0, "探索": 0, "预研": 0, "当前方向": 0, "拟": 0,
    # Rank 1: Contributor / Participant
    "参与": 1, "协助": 1, "支持": 1, "共建者": 1, "配合": 1, "contributor": 1,
    # Rank 2: Lead / Maintainer
    "主导": 2, "主要负责": 2, "策略架构owner": 2, "策略owner": 2, "架构负责人": 2, "maintainer": 2, "方向负责人": 2,
    # Rank 3: Independent Owner
    "独立负责": 3, "从0到1": 3, "端到端负责": 3, "完全负责": 3, "owner": 3,
}

ROLE_RANK_NAMES: Dict[int, str] = {
    0: "规划/探索 (Planning / Exploratory)",
    1: "参与/协作 (Contributor / Participant)",
    2: "主导/负责 (Lead / Maintainer)",
    3: "独立Owner (Independent Owner)",
}


# ============================================================================
# 4. Quantified Metrics Regex Patterns
# ============================================================================

QUANTIFIED_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b\d+(?:\.\d+)?%"),                                                  # 54.2%, 62%, 100%
    re.compile(r"\b\d+(?:\.\d+)?x\b", re.IGNORECASE),                                  # 2.8x, 3x
    re.compile(r"[$¥￥]\s*\d+(?:,\d+)*(?:\.\d+)?"),                                   # $100k, ￥3800
    re.compile(r"\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:万|亿元|万元|k|m|b|billion|million|rmb|usd)\b", re.IGNORECASE), # 3800 万元, 38M RMB
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds?|min|minutes?|hours?|h|周|天|小时|分钟|秒|weeks?|days?|months?)\b", re.IGNORECASE), # 320ms, 8 分钟
    re.compile(r"\b\d+(?:,\d+)?\s*(?:卡|gpus?|nodes?|tps|qps|tokens?/s|gb|tb|pb|stars?|citations?|条|篇)\b", re.IGNORECASE), # 1024 卡, 3400 stars
    re.compile(r"\b\d+[bm]\b", re.IGNORECASE),                                         # 230B, 64B
    re.compile(r"[+上下降提升增加缩短减少压减削减]\s*\d+(?:\.\d+)?%?"),                      # 提升 14.2%, 减少 48%
    re.compile(r"\b(?:from|slashing|reducing|increasing|boosting)\b[^\n,;]+?\b\d+"),   # English metric phrasing
]


# ============================================================================
# 5. Technology & Version Whitelist (Non-metric Identifiers)
# ============================================================================

NON_METRIC_TECH_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bC\+\+[0-9]{2}\b", re.IGNORECASE),                         # C++17, C++20
    re.compile(r"\bFlashAttention-[23](?:/[23])?\b", re.IGNORECASE),        # FlashAttention-2/3
    re.compile(r"\bZeRO-[123]\b", re.IGNORECASE),                           # ZeRO-3
    re.compile(r"\bGPT-[34](?:o|\.5)?\b", re.IGNORECASE),                   # GPT-4o, GPT-3.5
    re.compile(r"\b(?:FP8|INT8|INT4|FP16|BF16)\b", re.IGNORECASE),           # Quantization formats
    re.compile(r"\b(?:E4M3|E5M2)\b", re.IGNORECASE),                        # FP8 sub-types
    re.compile(r"\bGSM8K\b", re.IGNORECASE),                                # Benchmark name
    re.compile(r"\bBM25\b", re.IGNORECASE),                                 # Algorithm name
    re.compile(r"\b[34]D\s*(?:Parallel|并[行度])?\b", re.IGNORECASE),        # 3D/4D Parallel
    re.compile(r"\b(?:P[78]|L[56])\b", re.IGNORECASE),                      # Job grade labels
    re.compile(r"\b(?:H800|H100|A800|A100|V100|RTX\s*4090)\b", re.IGNORECASE), # Accelerator models
    # Realistic calendar date ranges: e.g. 2020.08 - 2023.02, 2020 - 至今
    re.compile(r"\b(?:19[7-9]\d|20[0-2]\d)\s*(?:\.\s*\d{1,2})?\s*[-~–—到至]\s*(?:(?:19[7-9]\d|20[0-2]\d)(?:\.\s*\d{1,2})?|至今|present)\b", re.IGNORECASE),
    # Standalone dates with dot month: e.g. 2023.03
    re.compile(r"\b(?:19[7-9]\d|20[0-2]\d)\.\d{1,2}\b", re.IGNORECASE),
    # Calendar year e.g. 2024年
    re.compile(r"\b(?:19[7-9]\d|20[0-2]\d)\s*年", re.IGNORECASE),
    re.compile(r"\bEXP-\d{2}\b", re.IGNORECASE),                            # Claim IDs
    re.compile(r"\bRFC[-\s]?\d+\b", re.IGNORECASE),                         # RFC IDs
]


# ============================================================================
# 6. Inflation Identification Patterns & Buzzwords
# ============================================================================

STRONG_ROLE_TERMS: re.Pattern = re.compile(
    r"核心作者|maintainer|owner|主导|完全负责|总负责人|架构师|committer",
    re.IGNORECASE
)
MODULE_QUALIFIERS: re.Pattern = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9_]+(?:模块|链路|子系统|组件|策略|引擎))\s*(?:Owner|负责人|主导|开发)",
    re.IGNORECASE
)
PLANNED_MARKERS: re.Pattern = re.compile(
    r"计划|规划|当前方向|拟|探索|聚焦|下一阶段|展望",
    re.IGNORECASE
)
FORBIDDEN_SUPERLATIVES: re.Pattern = re.compile(
    r"全球最[强快好年轻]|业内首个|第一人|全网最[快强]|绝对最优",
    re.IGNORECASE
)

COMPLETED_VERBS_FORBIDDEN_IN_PLANNING: List[str] = [
    "已上线", "已达成", "完成", "实现", "主导", "owner", "核心作者", "提升约", "降低约", "突破"
]

SUPERLATIVES: List[str] = [
    "全网第一", "全国第一", "全球第一", "业界第一", "唯一", "最优", "顶尖", "首个"
]

# Structured definition of Core Inflation Patterns (SSOT)
INFLATION_PATTERNS: Dict[str, Dict[str, Any]] = {
    "P1_SCOPE_INFLATION": {
        "name": "范围与角色夸大 (Scope Inflation / Role Elevation)",
        "pattern_terms": STRONG_ROLE_TERMS,
        "qualifier": MODULE_QUALIFIERS,
        "detail": "使用全盘架构强词（如 Owner/主导/完全负责），但未限定具体闭环模块名称",
        "fix_suggestion": "限定至具体责任单元，改写为 '[具体模块名] Owner' 或 '负责 [具体组件] 研发'",
    },
    "P2_UNBOUNDED_SUPERLATIVE": {
        "name": "排他性最高级 (Unbounded Superlative)",
        "pattern": FORBIDDEN_SUPERLATIVES,
        "superlatives": SUPERLATIVES,
        "detail": "命中排他性最高级词汇，缺乏第三方官方全集背书",
        "fix_suggestion": "删除绝对化最高级，采用限定客观场景或具体指标对比表达",
    },
    "P3_TEMPORAL_CONFUSION": {
        "name": "时态混淆 / 规划期完成态 (Temporal Confusion)",
        "planned_markers": PLANNED_MARKERS,
        "completed_verbs": COMPLETED_VERBS_FORBIDDEN_IN_PLANNING,
        "detail": "处于探索/规划阶段（Planned）却使用了过去完成时强主导动词（如主导/已实现）",
        "fix_suggestion": "保留时态边界，使用 '当前规划'、'重点探索'，禁止声称已产生确定性生产收益",
    },
    "P4_PSEUDO_ZERO_TO_ONE": {
        "name": "伪从0到1 (Pseudo Zero to One)",
        "trigger_term": "从0到1",
        "conflicting_terms": ["重构", "优化", "演进"],
        "detail": "存量系统重构/优化与'从0到1'叙事冲突",
        "fix_suggestion": "改写为 '[原架构] → [新架构] 架构演进' 或 '核心指标跃迁'",
    },
}

# Academic & Professional Forbidden Buzzwords
FORBIDDEN_BUZZWORDS: List[str] = [
    "首创", "颠覆", "国际先进", "世界一流", "填补空白", "独家", "最优解", "全能", "领先"
]

# AI Cliches & Buzzword Lexicon (English & Chinese)
AI_BUZZWORDS_LEXICON: List[str] = [
    # English buzzwords
    "results-driven", "results driven", "dynamic", "synergy", "passionate",
    "proven track record", "deeply passionate", "testament to", "delve into",
    "pivotal role", "game-changing transformation", "intricate tapestry",
    "fast-paced environment", "thought leader", "go-getter", "team player",
    "seasoned professional", "cutting-edge solutions", "groundbreaking",
    "spearheading transformative", "holistic approach", "seamlessly integrate",
    "unwavering commitment", "strategic vision", "value proposition",
    # Chinese buzzwords
    "具有深厚底蕴", "全面赋能", "深度赋能", "全面革新", "强力驱动", "革命性突破",
    "显著提高", "大幅优化", "卓越成效", "顶层设计", "无缝打通", "全方位重塑",
    "作为一名深耕", "深耕.*领域", "不仅.*而且.*更.*"
]


# ============================================================================
# 7. Helper Lookup & Normalization Functions
# ============================================================================

def detect_role_rank(text: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Finds role rank using longest-prefix matching to avoid substring collision.
    Returns (rank, matched_term) or (None, None).
    """
    lower = text.lower()
    sorted_keys = sorted(ROLE_RANKS.keys(), key=lambda k: len(k), reverse=True)
    for k in sorted_keys:
        if k.lower() in lower:
            return ROLE_RANKS[k], k
    return None, None


def detect_verb_level(text: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Detects verb level (1~5) using longest-match first.
    Returns (level, matched_verb) or (None, None).
    """
    lower = text.lower()
    sorted_verbs = sorted(VERB_HIERARCHY.keys(), key=lambda k: len(k), reverse=True)
    for v in sorted_verbs:
        if v.lower() in lower:
            return VERB_HIERARCHY[v], v
    return None, None
