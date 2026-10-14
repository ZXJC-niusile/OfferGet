"""
OfferGet Core Lexicon (core/lexicon.py)
=======================================
Single Source of Truth (SSOT) compatibility re-exporter.

All dictionaries, patterns, and linguistic rules are centrally governed in
`core.registry` (MetricPatternRegistry, QualityRuleRegistry). This module
re-exports them directly to prevent dictionary duplication and maintain
100% backward compatibility for all consumer modules and tests.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from core.registry import (
    MetricPatternRegistry,
    QualityRuleRegistry,
)

# ============================================================================
# 1. Verb Hierarchy (Re-exported from QualityRuleRegistry)
# ============================================================================
VERB_HIERARCHY: Dict[str, int] = QualityRuleRegistry.VERB_HIERARCHY
STRONG_VERBS_THRESHOLD: int = QualityRuleRegistry.STRONG_VERBS_THRESHOLD

# ============================================================================
# 2. Strong and Weak Action Verbs (Re-exported from QualityRuleRegistry)
# ============================================================================
STRONG_ACTION_VERBS_EN: Set[str] = QualityRuleRegistry.STRONG_ACTION_VERBS_EN
STRONG_ACTION_VERBS_ZH: Set[str] = QualityRuleRegistry.STRONG_ACTION_VERBS_ZH
WEAK_ACTION_VERBS_EN: Set[str] = QualityRuleRegistry.WEAK_ACTION_VERBS_EN
WEAK_ACTION_VERBS_ZH: Set[str] = QualityRuleRegistry.WEAK_ACTION_VERBS_ZH

# ============================================================================
# 3. Role Ranks (Re-exported from QualityRuleRegistry)
# ============================================================================
ROLE_RANKS: Dict[str, int] = QualityRuleRegistry.ROLE_RANKS
ROLE_RANK_NAMES: Dict[int, str] = QualityRuleRegistry.ROLE_RANK_NAMES

# ============================================================================
# 4. Quantified Metrics Regex Patterns (Re-exported from MetricPatternRegistry)
# ============================================================================
QUANTIFIED_PATTERNS: List[re.Pattern] = MetricPatternRegistry.QUANTIFIED_PATTERNS

# ============================================================================
# 5. Technology & Version Whitelist (Re-exported from MetricPatternRegistry)
# ============================================================================
NON_METRIC_TECH_PATTERNS: List[re.Pattern] = MetricPatternRegistry.NON_METRIC_TECH_PATTERNS

# ============================================================================
# 6. Inflation Identification Patterns & Buzzwords (Re-exported from QualityRuleRegistry)
# ============================================================================
STRONG_ROLE_TERMS: re.Pattern = QualityRuleRegistry.STRONG_ROLE_TERMS
MODULE_QUALIFIERS: re.Pattern = QualityRuleRegistry.MODULE_QUALIFIERS
PLANNED_MARKERS: re.Pattern = QualityRuleRegistry.PLANNED_MARKERS
FORBIDDEN_SUPERLATIVES: re.Pattern = QualityRuleRegistry.FORBIDDEN_SUPERLATIVES
COMPLETED_VERBS_FORBIDDEN_IN_PLANNING: List[str] = QualityRuleRegistry.COMPLETED_VERBS_FORBIDDEN_IN_PLANNING
SUPERLATIVES: List[str] = QualityRuleRegistry.SUPERLATIVES
INFLATION_PATTERNS: Dict[str, Dict[str, Any]] = QualityRuleRegistry.INFLATION_PATTERNS
FORBIDDEN_BUZZWORDS: List[str] = QualityRuleRegistry.FORBIDDEN_BUZZWORDS
AI_BUZZWORDS_LEXICON: List[str] = QualityRuleRegistry.AI_BUZZWORDS_LEXICON

# ============================================================================
# 7. Decision, Depth, Evidence & Anti-Slop (Re-exported from QualityRuleRegistry)
# ============================================================================
DECISION_PLANNING_KEYWORDS: List[str] = QualityRuleRegistry.DECISION_PLANNING_KEYWORDS
DATA_DEPTH_LEVELS: Dict[str, str] = QualityRuleRegistry.DATA_DEPTH_LEVELS
RESULT_EVIDENCE_LEVELS: Dict[str, str] = QualityRuleRegistry.RESULT_EVIDENCE_LEVELS
BANNED_SLOP_PATTERNS: List[Tuple[str, str]] = QualityRuleRegistry.BANNED_SLOP_PATTERNS
ROLE_KPI_LEXICON: Dict[str, List[str]] = QualityRuleRegistry.ROLE_KPI_LEXICON

# ============================================================================
# 8. ATS Formats & Defense Guidance (Re-exported from QualityRuleRegistry)
# ============================================================================
STANDARD_SECTIONS: Dict[str, List[str]] = QualityRuleRegistry.STANDARD_SECTIONS
FORMATTING_RISKS: List[Tuple[str, re.Pattern, str]] = QualityRuleRegistry.FORMATTING_RISKS
DEFENSE_GUIDE_TEMPLATES: Dict[str, str] = QualityRuleRegistry.DEFENSE_GUIDE_TEMPLATES

# ============================================================================
# 9. Baoyan Academic Integrity & Typography (Re-exported from QualityRuleRegistry)
# ============================================================================
BAOYAN_SPEC_RANGES: Dict[str, Tuple[int, int]] = QualityRuleRegistry.BAOYAN_SPEC_RANGES
BAOYAN_SPEC_ALIASES: Dict[str, str] = QualityRuleRegistry.BAOYAN_SPEC_ALIASES
FORBIDDEN_DASHES: Dict[str, str] = QualityRuleRegistry.FORBIDDEN_DASHES
FORBIDDEN_QUOTES: Dict[str, str] = QualityRuleRegistry.FORBIDDEN_QUOTES
FORBIDDEN_DOUBLE_HYPHEN: str = QualityRuleRegistry.FORBIDDEN_DOUBLE_HYPHEN
BAOYAN_LEAD_ROLES: Set[str] = QualityRuleRegistry.BAOYAN_LEAD_ROLES
BAOYAN_CORE_ROLES: Set[str] = QualityRuleRegistry.BAOYAN_CORE_ROLES
BAOYAN_LEAD_OR_CORE_ROLES: Set[str] = QualityRuleRegistry.BAOYAN_LEAD_OR_CORE_ROLES
BAOYAN_NON_LEAD_ROLES: Set[str] = QualityRuleRegistry.BAOYAN_NON_LEAD_ROLES
BAOYAN_ESCALATED_VERBS: List[str] = QualityRuleRegistry.BAOYAN_ESCALATED_VERBS
BAOYAN_LEADER_ONLY_VERBS: List[str] = QualityRuleRegistry.BAOYAN_LEADER_ONLY_VERBS
SIMULATION_TERMS: List[str] = QualityRuleRegistry.SIMULATION_TERMS
REAL_CLUSTER_TERMS: List[str] = QualityRuleRegistry.REAL_CLUSTER_TERMS
EXPECTED_OUTCOME_TERMS: List[str] = QualityRuleRegistry.EXPECTED_OUTCOME_TERMS
ACQUIRED_OUTCOME_TERMS: List[str] = QualityRuleRegistry.ACQUIRED_OUTCOME_TERMS

# ============================================================================
# 10. Helper Lookup & Normalization Functions (Re-exported from QualityRuleRegistry)
# ============================================================================
detect_role_rank = QualityRuleRegistry.detect_role_rank
detect_verb_level = QualityRuleRegistry.detect_verb_level

__all__ = [
    "VERB_HIERARCHY",
    "STRONG_VERBS_THRESHOLD",
    "STRONG_ACTION_VERBS_EN",
    "STRONG_ACTION_VERBS_ZH",
    "WEAK_ACTION_VERBS_EN",
    "WEAK_ACTION_VERBS_ZH",
    "ROLE_RANKS",
    "ROLE_RANK_NAMES",
    "QUANTIFIED_PATTERNS",
    "NON_METRIC_TECH_PATTERNS",
    "STRONG_ROLE_TERMS",
    "MODULE_QUALIFIERS",
    "PLANNED_MARKERS",
    "FORBIDDEN_SUPERLATIVES",
    "COMPLETED_VERBS_FORBIDDEN_IN_PLANNING",
    "SUPERLATIVES",
    "INFLATION_PATTERNS",
    "FORBIDDEN_BUZZWORDS",
    "AI_BUZZWORDS_LEXICON",
    "DECISION_PLANNING_KEYWORDS",
    "DATA_DEPTH_LEVELS",
    "RESULT_EVIDENCE_LEVELS",
    "BANNED_SLOP_PATTERNS",
    "ROLE_KPI_LEXICON",
    "STANDARD_SECTIONS",
    "FORMATTING_RISKS",
    "DEFENSE_GUIDE_TEMPLATES",
    "BAOYAN_SPEC_RANGES",
    "BAOYAN_SPEC_ALIASES",
    "FORBIDDEN_DASHES",
    "FORBIDDEN_QUOTES",
    "FORBIDDEN_DOUBLE_HYPHEN",
    "BAOYAN_LEAD_ROLES",
    "BAOYAN_CORE_ROLES",
    "BAOYAN_LEAD_OR_CORE_ROLES",
    "BAOYAN_NON_LEAD_ROLES",
    "BAOYAN_ESCALATED_VERBS",
    "BAOYAN_LEADER_ONLY_VERBS",
    "SIMULATION_TERMS",
    "REAL_CLUSTER_TERMS",
    "EXPECTED_OUTCOME_TERMS",
    "ACQUIRED_OUTCOME_TERMS",
    "detect_role_rank",
    "detect_verb_level",
]
