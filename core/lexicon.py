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
from typing import Any, Dict, List, Optional, Set, Tuple

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
# 7. Helper Lookup & Normalization Functions (Re-exported from QualityRuleRegistry)
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
    "detect_role_rank",
    "detect_verb_level",
]
