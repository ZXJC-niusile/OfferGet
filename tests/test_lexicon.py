"""Behavior checks for linguistic helpers, metric tokens and role KPIs.

Registry contents and consumer alias identity are owned by test_registry.py.
"""

import unittest

from core.lexicon import (
    QUANTIFIED_PATTERNS,
    NON_METRIC_TECH_PATTERNS,
    detect_verb_level,
)


class TestLexiconSSOT(unittest.TestCase):


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


    def test_role_kpi_lexicon(self):
        from core.lexicon import ROLE_KPI_LEXICON
        from core.registry import QualityRuleRegistry

        self.assertIn("product", ROLE_KPI_LEXICON)
        self.assertIn("ai_product", ROLE_KPI_LEXICON)
        self.assertIn("technical", ROLE_KPI_LEXICON)
        self.assertIn("data_analyst", ROLE_KPI_LEXICON)

        self.assertIn("DAU", ROLE_KPI_LEXICON["product"])
        self.assertIn("QPS", ROLE_KPI_LEXICON["technical"])
        self.assertIn("看板数量", ROLE_KPI_LEXICON["data_analyst"])
        self.assertIn("任务成功率", ROLE_KPI_LEXICON["ai_product"])

        lex_copy = QualityRuleRegistry.get_role_kpi_lexicon()
        self.assertEqual(lex_copy["technical"], ROLE_KPI_LEXICON["technical"])

