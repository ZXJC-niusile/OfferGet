"""
Unit Test Suite for OfferGet Core Lexicon (core/lexicon.py).
Validates SSOT linguistic dictionaries, role ranks, verb hierarchy,
regex pattern banks, and re-export parity across consumer modules.
"""

import unittest
from pathlib import Path

from core.lexicon import (
    VERB_HIERARCHY,
    STRONG_ACTION_VERBS_ZH,
    STRONG_ACTION_VERBS_EN,
    WEAK_ACTION_VERBS_ZH,
    WEAK_ACTION_VERBS_EN,
    ROLE_RANKS,
    ROLE_RANK_NAMES,
    QUANTIFIED_PATTERNS,
    NON_METRIC_TECH_PATTERNS,
    INFLATION_PATTERNS,
    FORBIDDEN_BUZZWORDS,
    AI_BUZZWORDS_LEXICON,
    detect_role_rank,
    detect_verb_level,
)
import core.ats_checker as ats_mod
import core.fact_guard as fact_mod
import core.asu_modeler as asu_mod


class TestLexiconSSOT(unittest.TestCase):

    def test_verb_hierarchy_levels(self):
        """Ensure all verb hierarchy entries are mapped between Level 1 and Level 5."""
        self.assertGreaterEqual(len(VERB_HIERARCHY), 20)
        for verb, level in VERB_HIERARCHY.items():
            self.assertIn(level, {1, 2, 3, 4, 5}, f"Verb '{verb}' has invalid level {level}")

        # Spot checks for key verbs
        self.assertEqual(VERB_HIERARCHY["支持"], 1)
        self.assertEqual(VERB_HIERARCHY["参与"], 2)
        self.assertEqual(VERB_HIERARCHY["负责"], 3)
        self.assertEqual(VERB_HIERARCHY["推动"], 4)
        self.assertEqual(VERB_HIERARCHY["主导"], 5)
        self.assertEqual(VERB_HIERARCHY["owner"], 5)

    def test_detect_verb_level_helper(self):
        """Ensure detect_verb_level finds the longest matching verb and correct level."""
        level, verb = detect_verb_level("主导完成全网分布式计算系统研发")
        self.assertEqual(level, 5)
        self.assertEqual(verb, "主导")

        level, verb = detect_verb_level("主要负责架构设计")
        self.assertEqual(level, 3)
        self.assertEqual(verb, "主要负责")

        level, verb = detect_verb_level("纯文本没有任何动词")
        self.assertIsNone(level)
        self.assertIsNone(verb)

    def test_action_verbs_sets(self):
        """Verify strong and weak action verbs in both languages."""
        self.assertTrue(len(STRONG_ACTION_VERBS_ZH) >= 20)
        self.assertTrue(len(STRONG_ACTION_VERBS_EN) >= 20)
        self.assertTrue(len(WEAK_ACTION_VERBS_ZH) >= 8)
        self.assertTrue(len(WEAK_ACTION_VERBS_EN) >= 8)

        self.assertIn("主导", STRONG_ACTION_VERBS_ZH)
        self.assertIn("architected", STRONG_ACTION_VERBS_EN)
        self.assertIn("参与", WEAK_ACTION_VERBS_ZH)
        self.assertIn("responsible for", WEAK_ACTION_VERBS_EN)

    def test_role_ranks(self):
        """Verify role ranks adhere to 0~3 hierarchy."""
        for role, rank in ROLE_RANKS.items():
            self.assertIn(rank, {0, 1, 2, 3}, f"Role '{role}' has invalid rank {rank}")

        # Spot checks
        self.assertEqual(ROLE_RANKS["规划"], 0)
        self.assertEqual(ROLE_RANKS["参与"], 1)
        self.assertEqual(ROLE_RANKS["主导"], 2)
        self.assertEqual(ROLE_RANKS["独立负责"], 3)
        self.assertEqual(ROLE_RANKS["owner"], 3)

        # Helper
        rank, matched = detect_role_rank("担任算法策略架构owner")
        self.assertEqual(rank, 2)
        self.assertEqual(matched, "策略架构owner")

    def test_quantified_patterns(self):
        """Ensure QUANTIFIED_PATTERNS correctly identify metrics."""
        self.assertEqual(len(QUANTIFIED_PATTERNS), 9)

        samples = [
            "提升 54.2%",
            "加速 2.8x",
            "预算 ￥3800 万元",
            "延迟 320ms",
            "1024 卡 H800",
            "230B 参数模型",
            "减少 48%",
            "from 100 to 200",
        ]
        for s in samples:
            matched = any(p.search(s) for p in QUANTIFIED_PATTERNS)
            self.assertTrue(matched, f"Expected metric pattern match for: '{s}'")

    def test_non_metric_tech_patterns(self):
        """Ensure NON_METRIC_TECH_PATTERNS match technical tokens and not metrics."""
        self.assertGreaterEqual(len(NON_METRIC_TECH_PATTERNS), 15)

        tech_tokens = [
            "C++20",
            "FlashAttention-2",
            "ZeRO-3",
            "GPT-4o",
            "FP8",
            "GSM8K",
            "BM25",
            "3D Parallel",
            "H800",
            "2020.08 - 2023.02",
            "2024年",
            "EXP-01",
            "RFC-12",
        ]
        for t in tech_tokens:
            matched = any(p.search(t) for p in NON_METRIC_TECH_PATTERNS)
            self.assertTrue(matched, f"Expected non-metric pattern match for: '{t}'")

    def test_inflation_patterns_and_buzzwords(self):
        """Verify inflation patterns and forbidden buzzwords."""
        self.assertIn("P1_SCOPE_INFLATION", INFLATION_PATTERNS)
        self.assertIn("P2_UNBOUNDED_SUPERLATIVE", INFLATION_PATTERNS)
        self.assertIn("P3_TEMPORAL_CONFUSION", INFLATION_PATTERNS)
        self.assertIn("P4_PSEUDO_ZERO_TO_ONE", INFLATION_PATTERNS)

        self.assertGreaterEqual(len(FORBIDDEN_BUZZWORDS), 9)
        self.assertIn("首创", FORBIDDEN_BUZZWORDS)
        self.assertIn("颠覆", FORBIDDEN_BUZZWORDS)

        self.assertGreaterEqual(len(AI_BUZZWORDS_LEXICON), 20)
        self.assertIn("results-driven", AI_BUZZWORDS_LEXICON)
        self.assertIn("全面赋能", AI_BUZZWORDS_LEXICON)

    def test_reexport_parity(self):
        """Verify that consumer modules correctly re-export identical SSOT objects."""
        # ats_checker re-exports
        self.assertIs(ats_mod.STRONG_ACTION_VERBS_ZH, STRONG_ACTION_VERBS_ZH)
        self.assertIs(ats_mod.STRONG_ACTION_VERBS_EN, STRONG_ACTION_VERBS_EN)
        self.assertIs(ats_mod.WEAK_ACTION_VERBS_ZH, WEAK_ACTION_VERBS_ZH)
        self.assertIs(ats_mod.WEAK_ACTION_VERBS_EN, WEAK_ACTION_VERBS_EN)
        self.assertIs(ats_mod.QUANTIFIED_PATTERNS, QUANTIFIED_PATTERNS)
        self.assertIs(ats_mod.AI_BUZZWORDS_LEXICON, AI_BUZZWORDS_LEXICON)

        # fact_guard re-exports
        self.assertIs(fact_mod.NON_METRIC_TECH_PATTERNS, NON_METRIC_TECH_PATTERNS)
        self.assertIs(fact_mod.INFLATION_PATTERNS, INFLATION_PATTERNS)
        self.assertIs(fact_mod.FORBIDDEN_BUZZWORDS, FORBIDDEN_BUZZWORDS)

        # asu_modeler re-exports
        self.assertIs(asu_mod.INFLATION_PATTERNS, INFLATION_PATTERNS)
        self.assertIs(asu_mod.ROLE_RANKS, ROLE_RANKS)
        self.assertIs(asu_mod.VERB_HIERARCHY, VERB_HIERARCHY)
