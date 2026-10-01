"""
Unit test suite for OfferGet Core Registry (core.registry):
- AliasRegistry: canonicalization, alias management, boundary-accurate matching, immutability, versioning
- TaxonomyRegistry: role trees, keyword matching, immutability, classification
- MetricPatternRegistry: quantified pattern detection, metric extraction, tech whitelist, topic mapping
- QualityRuleRegistry: verb hierarchy, role ranks, inflation rules, buzzword checking
- Consumer module integration: profile_adapter, jd_compat, fact_guard, and lexicon compatibility
"""

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.registry import (
    AliasRegistry,
    TaxonomyRegistry,
    MetricPatternRegistry,
    QualityRuleRegistry,
)
import core.profile_adapter as profile_adapter
import core.jd_compat as jd_compat
import core.fact_guard as fact_guard
import core.lexicon as lexicon
from core.profile_adapter import ProfileEvidenceIndex
from core.fact_guard import FactVerificationGuard


class TestAliasRegistry(unittest.TestCase):

    def test_01_version_and_metadata(self):
        """Verify AliasRegistry metadata, ID, and version."""
        self.assertEqual(AliasRegistry.REGISTRY_ID, "REG_SKILL_ALIAS")
        self.assertEqual(AliasRegistry.VERSION, "1.5.0")
        self.assertEqual(AliasRegistry.RULE_ID_PREFIX, "ALIAS")

    def test_02_canonical_resolution(self):
        """Verify canonical resolution for aliases and unknown terms."""
        # Known aliases resolving to canonical
        self.assertEqual(AliasRegistry.get_canonical("torch"), "pytorch")
        self.assertEqual(AliasRegistry.get_canonical("pytorch"), "pytorch")
        self.assertEqual(AliasRegistry.get_canonical("cpp"), "c++")
        self.assertEqual(AliasRegistry.get_canonical("c++"), "c++")
        self.assertEqual(AliasRegistry.get_canonical("megatron"), "megatron-lm")
        self.assertEqual(AliasRegistry.get_canonical("tensorrt llm"), "tensorrt-llm")
        self.assertEqual(AliasRegistry.get_canonical("model context protocol"), "mcp")
        self.assertEqual(AliasRegistry.get_canonical("graph rag"), "graphrag")
        self.assertEqual(AliasRegistry.get_canonical("flashattention-2"), "flashattention")
        self.assertEqual(AliasRegistry.get_canonical("flashattention-3"), "flashattention")
        self.assertEqual(AliasRegistry.get_canonical("multi-head latent attention"), "mla")

        # Case-insensitive resolution
        self.assertEqual(AliasRegistry.get_canonical("PyTorch"), "pytorch")
        self.assertEqual(AliasRegistry.get_canonical("C++"), "c++")
        self.assertEqual(AliasRegistry.get_canonical("VLLM"), "vllm")
        self.assertEqual(AliasRegistry.get_canonical("DPO"), "dpo")
        self.assertEqual(AliasRegistry.get_canonical("GRPO"), "grpo")

        # Unknown terms stay lowercased
        self.assertEqual(AliasRegistry.get_canonical("Rust"), "rust")
        self.assertEqual(AliasRegistry.get_canonical("kubernetes"), "kubernetes")

        # Empty or whitespace handling
        self.assertEqual(AliasRegistry.get_canonical(""), "")
        self.assertEqual(AliasRegistry.get_canonical("   "), "")

    def test_03_aliases_retrieval(self):
        """Verify get_aliases returns the correct alias set."""
        pytorch_aliases = AliasRegistry.get_aliases("pytorch")
        self.assertIn("pytorch", pytorch_aliases)
        self.assertIn("torch", pytorch_aliases)

        # Querying with an alias should also resolve to canonical aliases
        torch_aliases = AliasRegistry.get_aliases("torch")
        self.assertEqual(torch_aliases, pytorch_aliases)

        cpp_aliases = AliasRegistry.get_aliases("c++")
        self.assertIn("c++", cpp_aliases)
        self.assertIn("cpp", cpp_aliases)

        # Unknown terms return empty set
        self.assertEqual(AliasRegistry.get_aliases("nonexistent_skill"), set())
        self.assertEqual(AliasRegistry.get_aliases(""), set())

    def test_04_immutability_and_readonly(self):
        """Verify that external mutation of returned aliases dictionary/sets does not affect internal registry."""
        all_al = AliasRegistry.all_aliases()
        self.assertIn("pytorch", all_al)

        # Mutate returned dictionary
        all_al["pytorch"].add("fake_torch_mutation")
        all_al["brand_new_fake_skill"] = {"fake"}

        # Check internal registry remained pristine
        fresh_pytorch = AliasRegistry.get_aliases("pytorch")
        self.assertNotIn("fake_torch_mutation", fresh_pytorch)
        self.assertNotIn("brand_new_fake_skill", AliasRegistry.all_aliases())

    def test_05_claim_matches_word_boundary(self):
        """Verify claim_matches enforces word boundaries and handles aliases/casing."""
        # 1. Matches canonical or alias with word boundary
        self.assertTrue(AliasRegistry.claim_matches("torch", "Pretrained models with PyTorch on GPUs"))
        self.assertTrue(AliasRegistry.claim_matches("pytorch", "Proficient in Torch and Triton"))
        self.assertTrue(AliasRegistry.claim_matches("vllm", "Deployed vLLM serving engine"))
        self.assertTrue(AliasRegistry.claim_matches("c++", "Proficient in C++ and Python"))
        self.assertTrue(AliasRegistry.claim_matches("mcp", "Built with Model Context Protocol standard"))
        self.assertTrue(AliasRegistry.claim_matches("graphrag", "Constructed hybrid graph rag architecture"))

        # 2. Word boundary avoids false positive on sub-tokens (e.g. c++ matching c++20)
        self.assertFalse(AliasRegistry.claim_matches("c++", "Proficient in C++17 and C++20"))
        self.assertFalse(AliasRegistry.claim_matches("vllm", "random_vllm_not_isolated"))

        # 3. Chinese terms
        self.assertTrue(AliasRegistry.claim_matches("大模型", "主导千亿大模型研发落地"))
        self.assertFalse(AliasRegistry.claim_matches("大模型", "纯后端服务"))

        # 4. Empty boundaries
        self.assertFalse(AliasRegistry.claim_matches("", "Some text"))
        self.assertFalse(AliasRegistry.claim_matches("python", ""))


class TestTaxonomyRegistry(unittest.TestCase):

    def test_01_version_and_metadata(self):
        """Verify TaxonomyRegistry metadata and version."""
        self.assertEqual(TaxonomyRegistry.REGISTRY_ID, "REG_ROLE_TAXONOMY")
        self.assertEqual(TaxonomyRegistry.VERSION, "1.5.0")
        self.assertEqual(TaxonomyRegistry.RULE_ID_PREFIX, "TAXONOMY")

    def test_02_list_and_get_taxonomies(self):
        """Verify role taxonomy retrieval, expected roles, and dimension structure."""
        taxonomies = TaxonomyRegistry.list_taxonomies()
        expected_roles = {
            "ai_algorithm", "backend_distributed", "frontend_fullstack", "client_mobile",
            "bigdata_infra", "cloudnative_sre", "product", "operations",
            "marketing_sales", "project_management", "general"
        }
        for role in expected_roles:
            self.assertIn(role, taxonomies)

        ai_tax = TaxonomyRegistry.get_taxonomy("ai_algorithm")
        self.assertIsNotNone(ai_tax)
        self.assertEqual(ai_tax["title"], "AI / 大模型与算法架构")
        self.assertIn("Transformer", ai_tax["keywords"])
        self.assertIn("vLLM", ai_tax["keywords"])

        # Dimensions check
        dims = ai_tax["dimensions"]
        self.assertGreater(len(dims), 0)
        total_weight = sum(weight for _, weight in dims)
        self.assertAlmostEqual(total_weight, 1.0, places=2)

        # Nonexistent role
        self.assertIsNone(TaxonomyRegistry.get_taxonomy("unknown_role_id"))

    def test_03_immutability(self):
        """Verify mutating returned taxonomy copies does not alter the registry."""
        ai_tax = TaxonomyRegistry.get_taxonomy("ai_algorithm")
        ai_tax["keywords"].append("FAKE_KEYWORD")

        fresh_ai = TaxonomyRegistry.get_taxonomy("ai_algorithm")
        self.assertNotIn("FAKE_KEYWORD", fresh_ai["keywords"])

    def test_04_classify_role(self):
        """Verify classification of JD texts into taxonomies."""
        ai_jd = "负责大模型预训练，熟悉 Transformer、Megatron-LM 与 vLLM 推理优化。"
        res = TaxonomyRegistry.classify_role(ai_jd)
        self.assertEqual(res["role_key"], "ai_algorithm")
        self.assertEqual(res["taxonomy"]["title"], "AI / 大模型与算法架构")

        backend_jd = "负责高并发分布式后端架构，精通 Java、Go、gRPC、Kafka 和微服务。"
        res_backend = TaxonomyRegistry.classify_role(backend_jd)
        self.assertEqual(res_backend["role_key"], "backend_distributed")

        general_jd = "日常办公室行政事务与文件整理。"
        res_general = TaxonomyRegistry.classify_role(general_jd)
        self.assertEqual(res_general["role_key"], "general")


class TestMetricPatternRegistry(unittest.TestCase):

    def test_01_version_and_metadata(self):
        """Verify MetricPatternRegistry metadata and version."""
        self.assertEqual(MetricPatternRegistry.REGISTRY_ID, "REG_METRIC_PATTERN")
        self.assertEqual(MetricPatternRegistry.VERSION, "1.5.0")
        self.assertEqual(MetricPatternRegistry.RULE_ID_PREFIX, "METRIC")

    def test_02_is_bullet_quantified(self):
        """Verify is_bullet_quantified detects metrics correctly."""
        self.assertTrue(MetricPatternRegistry.is_bullet_quantified("端到端 MFU 从 38.5% 优化至 54.2%"))
        self.assertTrue(MetricPatternRegistry.is_bullet_quantified("年均节省云算力开销 3800 万元"))
        self.assertTrue(MetricPatternRegistry.is_bullet_quantified("TTFT 首字延迟从 1.8s 下降至 320ms"))
        self.assertTrue(MetricPatternRegistry.is_bullet_quantified("单卡有效中断时间从 2.4 小时压减至 8 分钟"))
        self.assertTrue(MetricPatternRegistry.is_bullet_quantified("在 1024 卡 H800 集群上完成预训练"))
        self.assertTrue(MetricPatternRegistry.is_bullet_quantified("GitHub 累计获得 3400 stars"))

        # Non-quantified text
        self.assertFalse(MetricPatternRegistry.is_bullet_quantified("负责深度学习算法研究与架构设计"))
        self.assertFalse(MetricPatternRegistry.is_bullet_quantified(""))

    def test_03_extract_raw_metrics_and_whitelist(self):
        """Verify extraction of metrics and proper masking of whitelisted technical tokens."""
        text = (
            "熟练使用 C++20 与 FlashAttention-2，在 1024 卡 H800 集群上将端到端 MFU 从 38.5% 提升至 54.2%，"
            "年均节省云算力开销 3800 万元，首字延迟 320ms。"
        )
        extracted = MetricPatternRegistry.extract_raw_metrics(text)
        types = {m["type"] for m in extracted}
        self.assertIn("cluster_size", types)
        self.assertIn("percentage", types)
        self.assertIn("currency", types)
        self.assertIn("time_ms", types)

        values = {m["value"] for m in extracted}
        self.assertIn(1024.0, values)
        self.assertIn(38.5, values)
        self.assertIn(54.2, values)
        self.assertIn(3800.0, values)
        self.assertIn(320.0, values)

        # C++20 and FlashAttention-2 must NOT be falsely extracted as numbers 20 or 2
        self.assertNotIn(20.0, values)
        self.assertNotIn(2.0, values)

    def test_04_metric_type_to_topics_immutability(self):
        """Verify metric type mapping and copy safety."""
        mapping = MetricPatternRegistry.get_metric_type_to_topics()
        self.assertIn("percentage", mapping)
        self.assertIn("mfu", mapping["percentage"])
        self.assertIn("currency", mapping)
        self.assertIn("savings", mapping["currency"])

        # Mutate copy
        mapping["percentage"].add("fake_topic")
        fresh_mapping = MetricPatternRegistry.get_metric_type_to_topics()
        self.assertNotIn("fake_topic", fresh_mapping["percentage"])


class TestQualityRuleRegistry(unittest.TestCase):

    def test_01_version_and_metadata(self):
        """Verify QualityRuleRegistry metadata and version."""
        self.assertEqual(QualityRuleRegistry.REGISTRY_ID, "REG_QUALITY_RULE")
        self.assertEqual(QualityRuleRegistry.VERSION, "1.5.0")
        self.assertEqual(QualityRuleRegistry.RULE_ID_PREFIX, "RULE")

    def test_02_verb_hierarchy_and_detection(self):
        """Verify verb hierarchy detection (levels 1~5)."""
        self.assertEqual(QualityRuleRegistry.VERB_HIERARCHY["支持"], 1)
        self.assertEqual(QualityRuleRegistry.VERB_HIERARCHY["参与"], 2)
        self.assertEqual(QualityRuleRegistry.VERB_HIERARCHY["负责"], 3)
        self.assertEqual(QualityRuleRegistry.VERB_HIERARCHY["推动"], 4)
        self.assertEqual(QualityRuleRegistry.VERB_HIERARCHY["主导"], 5)

        level, verb = QualityRuleRegistry.detect_verb_level("主导完成高并发分布式系统研发")
        self.assertEqual(level, 5)
        self.assertEqual(verb, "主导")

        level, verb = QualityRuleRegistry.detect_verb_level("参与日常模块开发")
        self.assertEqual(level, 2)
        self.assertEqual(verb, "参与")

    def test_03_role_ranks(self):
        """Verify role rank detection (ranks 0~3)."""
        rank, matched = QualityRuleRegistry.detect_role_rank("担任算法策略架构owner")
        self.assertEqual(rank, 2)
        self.assertEqual(matched, "策略架构owner")

        rank, matched = QualityRuleRegistry.detect_role_rank("负责从0到1搭建数据平台")
        self.assertEqual(rank, 3)
        self.assertEqual(matched, "从0到1")

    def test_04_inflation_rules_and_buzzwords(self):
        """Verify inflation pattern rules and forbidden buzzwords."""
        rules = QualityRuleRegistry.list_inflation_rules()
        self.assertIn("P1_SCOPE_INFLATION", rules)
        self.assertIn("P2_UNBOUNDED_SUPERLATIVE", rules)
        self.assertIn("P3_TEMPORAL_CONFUSION", rules)
        self.assertIn("P4_PSEUDO_ZERO_TO_ONE", rules)

        self.assertTrue(QualityRuleRegistry.is_forbidden_buzzword("首创"))
        self.assertTrue(QualityRuleRegistry.is_forbidden_buzzword("世界一流"))
    def test_05_unified_constants_and_accessors(self):
        """Verify newly unified constants, accessors, and type safety."""
        # ApexResume standards
        depths = QualityRuleRegistry.get_data_depth_levels()
        self.assertIn("D0", depths)
        self.assertIn("D4", depths)
        results = QualityRuleRegistry.get_result_evidence_levels()
        self.assertIn("R0", results)
        self.assertIn("R3", results)
        decisions = QualityRuleRegistry.get_decision_planning_keywords()
        self.assertIn("架构设计", decisions)
        self.assertIn("选型", decisions)

        # Validator patterns
        slop = QualityRuleRegistry.get_banned_slop_patterns()
        self.assertGreater(len(slop), 0)

        # ATS sections and risks
        sections = QualityRuleRegistry.get_standard_sections()
        self.assertIn("Experience", sections)
        self.assertIn("Skills", sections)
        risks = QualityRuleRegistry.get_formatting_risks()
        risk_names = [r[0] for r in risks]
        self.assertIn("table", risk_names)
        self.assertIn("multi_column", risk_names)

        # Baoyan standards
        ranges = QualityRuleRegistry.get_baoyan_spec_ranges()
        self.assertEqual(ranges["摘要版"], (40, 60))
        self.assertIn("——", QualityRuleRegistry.FORBIDDEN_DASHES)
        self.assertIn("万卡集群", QualityRuleRegistry.REAL_CLUSTER_TERMS)
        self.assertIn("gazebo", QualityRuleRegistry.SIMULATION_TERMS)


class TestConsumerModuleIntegration(unittest.TestCase):

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

    def test_01_profile_adapter_consumes_registry(self):
        """Verify profile_adapter aliases and claim matching integrate with AliasRegistry."""
        # ALIASES re-exported matches registry
        self.assertEqual(profile_adapter.ALIASES, AliasRegistry.all_aliases())

        # claim_matches correctly delegates
        self.assertTrue(profile_adapter.claim_matches("torch", "PyTorch deep learning"))
        self.assertTrue(profile_adapter.claim_matches("c++", "Proficient in C++"))
        self.assertFalse(profile_adapter.claim_matches("c++", "Proficient in C++20"))

        # canonical_terms correctly delegates
        self.assertEqual(profile_adapter.canonical_terms("torch"), {"pytorch", "torch"})

    def test_02_jd_compat_consumes_registry(self):
        """Verify jd_compat taxonomies integrate with TaxonomyRegistry."""
        self.assertEqual(jd_compat.ROLE_TAXONOMIES, TaxonomyRegistry.list_taxonomies())

        classification = jd_compat.classify_role_taxonomy("大模型 Transformer PyTorch")
        self.assertEqual(classification["role_key"], "ai_algorithm")

    def test_03_lexicon_reexport_parity(self):
        """Verify lexicon.py directly re-exports SSOT objects from registry."""
        self.assertIs(lexicon.VERB_HIERARCHY, QualityRuleRegistry.VERB_HIERARCHY)
        self.assertIs(lexicon.QUANTIFIED_PATTERNS, MetricPatternRegistry.QUANTIFIED_PATTERNS)
        self.assertIs(lexicon.NON_METRIC_TECH_PATTERNS, MetricPatternRegistry.NON_METRIC_TECH_PATTERNS)
        self.assertIs(lexicon.INFLATION_PATTERNS, QualityRuleRegistry.INFLATION_PATTERNS)
        self.assertIs(lexicon.FORBIDDEN_BUZZWORDS, QualityRuleRegistry.FORBIDDEN_BUZZWORDS)
        self.assertIs(lexicon.DECISION_PLANNING_KEYWORDS, QualityRuleRegistry.DECISION_PLANNING_KEYWORDS)
        self.assertIs(lexicon.DATA_DEPTH_LEVELS, QualityRuleRegistry.DATA_DEPTH_LEVELS)
        self.assertIs(lexicon.RESULT_EVIDENCE_LEVELS, QualityRuleRegistry.RESULT_EVIDENCE_LEVELS)
        self.assertIs(lexicon.BANNED_SLOP_PATTERNS, QualityRuleRegistry.BANNED_SLOP_PATTERNS)
        self.assertIs(lexicon.STANDARD_SECTIONS, QualityRuleRegistry.STANDARD_SECTIONS)
        self.assertIs(lexicon.FORMATTING_RISKS, QualityRuleRegistry.FORMATTING_RISKS)
        self.assertIs(lexicon.DEFENSE_GUIDE_TEMPLATES, QualityRuleRegistry.DEFENSE_GUIDE_TEMPLATES)
        self.assertIs(lexicon.BAOYAN_SPEC_RANGES, QualityRuleRegistry.BAOYAN_SPEC_RANGES)
        self.assertIs(lexicon.SIMULATION_TERMS, QualityRuleRegistry.SIMULATION_TERMS)
        self.assertIs(lexicon.REAL_CLUSTER_TERMS, QualityRuleRegistry.REAL_CLUSTER_TERMS)
        self.assertIs(lexicon.detect_role_rank, QualityRuleRegistry.detect_role_rank)
        self.assertIs(lexicon.detect_verb_level, QualityRuleRegistry.detect_verb_level)

    def test_04_fact_guard_consumes_evidence_index_and_registry(self):
        """Verify FactVerificationGuard creates ProfileEvidenceIndex and uses MetricPatternRegistry."""
        guard = FactVerificationGuard(self.profile_data)

        # ProfileEvidenceIndex was constructed
        self.assertIsNotNone(guard.evidence_index)
        self.assertIsInstance(guard.evidence_index, ProfileEvidenceIndex)
        self.assertGreater(len(guard.evidence_index.skills), 0)
        self.assertGreater(len(guard.evidence_index.bullets), 0)

        # METRIC_TYPE_TO_TOPICS and NON_METRIC_TECH_PATTERNS match MetricPatternRegistry
        self.assertIs(fact_guard.METRIC_TYPE_TO_TOPICS, MetricPatternRegistry.METRIC_TYPE_TO_TOPICS)
        self.assertIs(fact_guard.NON_METRIC_TECH_PATTERNS, MetricPatternRegistry.NON_METRIC_TECH_PATTERNS)

        # _extract_raw_metrics_from_text delegates to MetricPatternRegistry
        metrics = guard._extract_raw_metrics_from_text("年均节省云算力开销 3800 万元")
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["value"], 3800.0)
        self.assertEqual(metrics[0]["type"], "currency")

    def test_05_apex_audit_and_validator_coverage_check(self):
        """Verify full SSOT identity and parity across QualityRuleRegistry, ApexResume, Validator, ATS, and Baoyan."""
        import core.resume_auditor as apex_audit
        import core.validator as validator
        import core.ats_checker as ats_checker
        import core.baoyan_auditor as baoyan_auditor

        # 1. ApexResume SSOT identity check
        self.assertIs(apex_audit.ROLE_RANKS, QualityRuleRegistry.ROLE_RANKS)
        self.assertIs(apex_audit.VERB_HIERARCHY, QualityRuleRegistry.VERB_HIERARCHY)
        self.assertEqual(apex_audit.STRONG_VERBS_THRESHOLD, QualityRuleRegistry.STRONG_VERBS_THRESHOLD)
        self.assertIs(apex_audit.DECISION_PLANNING_KEYWORDS, QualityRuleRegistry.DECISION_PLANNING_KEYWORDS)
        self.assertIs(apex_audit.DATA_DEPTH_LEVELS, QualityRuleRegistry.DATA_DEPTH_LEVELS)
        self.assertIs(apex_audit.RESULT_EVIDENCE_LEVELS, QualityRuleRegistry.RESULT_EVIDENCE_LEVELS)
        self.assertIs(apex_audit.COMPLETED_VERBS_FORBIDDEN_IN_PLANNING, QualityRuleRegistry.COMPLETED_VERBS_FORBIDDEN_IN_PLANNING)
        self.assertIs(apex_audit.SUPERLATIVES, QualityRuleRegistry.SUPERLATIVES)

        # 2. Validator SSOT identity check
        self.assertIs(validator.BANNED_SLOP_PATTERNS, QualityRuleRegistry.BANNED_SLOP_PATTERNS)

        # 3. ATS Checker SSOT identity check
        self.assertIs(ats_checker.STANDARD_SECTIONS, QualityRuleRegistry.STANDARD_SECTIONS)
        self.assertIs(ats_checker.FORMATTING_RISKS, QualityRuleRegistry.FORMATTING_RISKS)
        self.assertIs(ats_checker.DEFENSE_GUIDE_TEMPLATES, QualityRuleRegistry.DEFENSE_GUIDE_TEMPLATES)

        # 4. Baoyan Auditor SSOT identity check
        self.assertIs(baoyan_auditor.SPEC_RANGES, QualityRuleRegistry.BAOYAN_SPEC_RANGES)
        self.assertIs(baoyan_auditor.SPEC_ALIASES, QualityRuleRegistry.BAOYAN_SPEC_ALIASES)
        self.assertIs(baoyan_auditor.FORBIDDEN_DASHES, QualityRuleRegistry.FORBIDDEN_DASHES)
        self.assertIs(baoyan_auditor.FORBIDDEN_QUOTES, QualityRuleRegistry.FORBIDDEN_QUOTES)
        self.assertIs(baoyan_auditor.SIMULATION_TERMS, QualityRuleRegistry.SIMULATION_TERMS)
        self.assertIs(baoyan_auditor.REAL_CLUSTER_TERMS, QualityRuleRegistry.REAL_CLUSTER_TERMS)
        self.assertIs(baoyan_auditor.EXPECTED_OUTCOME_TERMS, QualityRuleRegistry.EXPECTED_OUTCOME_TERMS)
        self.assertIs(baoyan_auditor.ACQUIRED_OUTCOME_TERMS, QualityRuleRegistry.ACQUIRED_OUTCOME_TERMS)


if __name__ == "__main__":
    unittest.main()
