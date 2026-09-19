"""
Unit test suite for core.profile_adapter:
- ProfileEvidenceIndex generation, immutability, and field access
- Immutability / copy-protection of raw_profile
- Idempotence of normalize_candidate_profile
- Unknown fields (education, experience, major) boundary governance
- Title boundary governance (no hallucinated '运营岗')
"""

import copy
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.profile_adapter import (
    EvidenceClaim,
    ProfileContext,
    ProfileEvidenceIndex,
    build_profile_context,
    build_profile_evidence_index,
    normalize_candidate_profile,
)
from core.gap_roi import SkillGapROIEngine


class TestProfileAdapter(unittest.TestCase):

    def setUp(self):
        self.sample_profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.sample_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

    def test_01_profile_evidence_index_generation_and_fields(self):
        """Test ProfileEvidenceIndex generation, typing, and frozen immutability."""
        index = build_profile_evidence_index(self.profile_data)

        self.assertIsInstance(index, ProfileEvidenceIndex)
        self.assertIsInstance(index.profile, dict)
        self.assertIsInstance(index.claims, tuple)
        self.assertIsInstance(index.skills, tuple)
        self.assertIsInstance(index.bullets, tuple)
        self.assertIsInstance(index.metric_anchors, tuple)
        self.assertIsInstance(index.claim_by_id, dict)
        self.assertIsInstance(index.source_paths, tuple)
        self.assertIsInstance(index.input_quality, dict)

        # Verify claims
        self.assertGreater(len(index.claims), 0)
        self.assertTrue(all(isinstance(c, EvidenceClaim) for c in index.claims))

        # Verify skills and bullets
        self.assertGreater(len(index.skills), 0)
        self.assertIn("Python", index.skills)
        self.assertGreater(len(index.bullets), 0)

        # Verify metric anchors
        self.assertGreater(len(index.metric_anchors), 0)
        first_metric = index.metric_anchors[0]
        self.assertIn("source_path", first_metric)
        self.assertIn("claim_id", first_metric)
        self.assertIn("name", first_metric)
        self.assertIn("value", first_metric)

        # Verify claim_by_id indexing
        for claim_id, claim in index.claim_by_id.items():
            self.assertIsInstance(claim_id, str)
            self.assertIsInstance(claim, EvidenceClaim)

        # Verify source_paths
        self.assertEqual(len(index.source_paths), len(index.claims))

        # Verify input_quality
        self.assertEqual(index.input_quality["evidence_claim_count"], len(index.claims))
        self.assertEqual(index.input_quality["profile_fact_policy"], "missing facts remain unknown")

        # Verify frozen immutability
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            index.skills = ()  # type: ignore

    def test_02_raw_profile_not_mutated(self):
        """Test that passing raw_profile to adapter functions never mutates the original dict."""
        raw = {
            "name": "测试候选人",
            "education": {
                "school": "测试大学",
                "major": "软件工程",
                "degree": "学士",
                "education_badges": ["985", "优秀毕业生"]
            },
            "experience": [
                {
                    "company": "测试科技",
                    "role": "研发工程师",
                    "highlights": [
                        {"claim_id": "EXP-01", "claim_zh": "负责核心模块研发", "verified_metrics": {"qps": 5000}}
                    ]
                }
            ],
            "skills": ["Python", "Rust"]
        }
        original = copy.deepcopy(raw)

        # Run normalization and index building
        _ = normalize_candidate_profile(raw)
        _ = build_profile_evidence_index(raw)

        self.assertEqual(raw, original)

    def test_03_idempotence(self):
        """Test idempotence: normalize(normalize(p)) == normalize(p) for Track 1 and Track 2."""
        # Track 1: Standard structured profile with top-level 'candidate'
        p1 = normalize_candidate_profile(self.profile_data)
        p2 = normalize_candidate_profile(p1)
        self.assertEqual(p1, p2)

        # Track 2: Flat minimal profile
        flat = {
            "name": "李四",
            "intent": "后端架构师",
            "education": {
                "school": "复旦大学",
                "major": "软件工程",
                "degree": "本科"
            },
            "experience": [
                {
                    "company": "字节跳动",
                    "role": "后端开发",
                    "time": "2021-2024",
                    "bullets": ["重构高并发网关", "接入微服务治理"]
                }
            ],
            "skills": ["Go", "Kafka", "Redis"]
        }
        p1_flat = normalize_candidate_profile(flat)
        p2_flat = normalize_candidate_profile(p1_flat)
        self.assertEqual(p1_flat, p2_flat)

    def test_04_unknown_fields_not_hallucinated(self):
        """Test that missing education, experience years, and major are NOT hallucinated as 硕士/3.0/计算机."""
        minimal = {"name": "王五"}

        # 1. Profile adapter normalization
        norm = normalize_candidate_profile(minimal)
        cand = norm["candidate"]
        self.assertEqual(cand.get("degree", ""), "")
        self.assertNotIn("硕士", cand.get("degree", ""))
        self.assertNotIn("本科", cand.get("degree", ""))
        self.assertEqual(cand.get("major", ""), "")
        self.assertNotEqual(cand.get("major", ""), "计算机科学与技术")

        # 2. Evidence index input_quality markers
        index = build_profile_evidence_index(minimal)
        self.assertTrue(index.input_quality["unknown_education"])
        self.assertTrue(index.input_quality["unknown_experience"])
        self.assertTrue(index.input_quality["unknown_major"])
        self.assertIn("education", index.input_quality["unknown_fields"])
        self.assertIn("years_of_experience", index.input_quality["unknown_fields"])
        self.assertIn("major", index.input_quality["unknown_fields"])

        # 3. Gap ROI engine _normalize_profile governance
        engine = SkillGapROIEngine()
        cand_obj = engine._normalize_profile(minimal)
        self.assertEqual(cand_obj.education_level, "")
        self.assertEqual(cand_obj.years_of_experience, 0.0)
        self.assertEqual(cand_obj.major, "")
        self.assertTrue(engine.last_input_quality["unknown_experience"])
        self.assertTrue(engine.last_input_quality["unknown_education"])
        self.assertTrue(engine.last_input_quality["unknown_major"])

    def test_05_missing_title_not_hallucinated_to_yunying(self):
        """Test that missing title/intent is NOT hallucinated to '运营岗'."""
        # Case B (flat)
        flat_no_title = {"name": "赵六"}
        norm_b = normalize_candidate_profile(flat_no_title)
        self.assertEqual(norm_b["candidate"].get("title"), "")
        self.assertNotEqual(norm_b["candidate"].get("title"), "运营岗")

        # Case A (candidate dict without title)
        cand_no_title = {"candidate": {"name": "赵六"}}
        norm_a = normalize_candidate_profile(cand_no_title)
        self.assertEqual(norm_a["candidate"].get("title"), "")
        self.assertNotEqual(norm_a["candidate"].get("title"), "运营岗")

    def test_06_profile_context_creation_and_fields(self):
        """Test ProfileContext holds SSOT data, claims, index, and projections."""
        ctx = build_profile_context(self.profile_data)
        self.assertIsInstance(ctx, ProfileContext)
        self.assertIsInstance(ctx.raw_profile, dict)
        self.assertIsInstance(ctx.normalized_profile, dict)
        self.assertIsInstance(ctx.evidence_index, ProfileEvidenceIndex)
        self.assertIsInstance(ctx.claims, tuple)
        self.assertIsInstance(ctx.skills, tuple)
        self.assertIsInstance(ctx.bullets, tuple)
        self.assertIsInstance(ctx.metric_anchors, tuple)
        self.assertIsInstance(ctx.input_quality, dict)

        # Ensure raw_profile was deep-copied (mutating source does not corrupt ctx.raw_profile)
        source = copy.deepcopy(self.profile_data)
        ctx2 = build_profile_context(source)
        source["candidate"]["name"] = "MODIFIED_NAME"
        self.assertNotEqual(ctx2.raw_profile["candidate"]["name"], "MODIFIED_NAME")

    def test_07_profile_context_idempotence_and_caching(self):
        """Test ProfileContext is idempotent and skips redundant normalization."""
        ctx1 = build_profile_context(self.profile_data)
        # Passing ProfileContext to build_profile_context returns the same context
        ctx2 = build_profile_context(ctx1)
        self.assertIs(ctx1, ctx2)

        # Passing ProfileContext to from_profile returns the same context
        ctx3 = ProfileContext.from_profile(ctx1)
        self.assertIs(ctx1, ctx3)

        # normalize_candidate_profile accepts ProfileContext without recalculation
        norm = normalize_candidate_profile(ctx1)
        self.assertEqual(norm, ctx1.normalized_profile)

        # build_profile_evidence_index accepts ProfileContext and returns existing index
        idx = build_profile_evidence_index(ctx1)
        self.assertIs(idx, ctx1.evidence_index)

    def test_08_profile_context_integration_with_fact_guard_and_canonical(self):
        """Test ProfileContext with FactVerificationGuard and profile_to_canonical."""
        from core.fact_guard import FactVerificationGuard
        from core.jd_compat import profile_to_canonical

        ctx = build_profile_context(self.profile_data)

        # Canonical profile lazy evaluation & defensive copies
        cand1 = ctx.get_canonical_profile()
        cand2 = ctx.get_canonical_profile()
        self.assertEqual(cand1, cand2)
        self.assertIsNot(cand1, cand2)  # Defensive copy on every get
        self.assertEqual(cand1.name, ctx.normalized_profile["candidate"]["name"])

        # Mutating cand1 does not mutate ctx internal canonical profile
        cand1.skills.clear()
        self.assertEqual(len(cand1.skills), 0)
        self.assertGreater(len(ctx.get_canonical_profile().skills), 0)
        self.assertGreater(len(ctx.canonical_profile_copy().skills), 0)

        # profile_to_canonical directly on ctx returns identical data
        cand3 = profile_to_canonical(ctx)
        self.assertEqual(cand2.name, cand3.name)

        # FactVerificationGuard reuses ctx.evidence_index directly
        guard = FactVerificationGuard(ctx)
        self.assertIs(guard.evidence_index, ctx.evidence_index)
        self.assertEqual(guard.master_profile, ctx.normalized_profile)
        self.assertGreater(len(guard.baseline_anchors), 0)

    def test_09_profile_context_immutability_and_defensive_copies(self):
        """Test that ProfileContext and ProfileEvidenceIndex protect internal state from external mutation."""
        ctx = build_profile_context(self.profile_data)

        # 1. Mutating returned normalized_profile does not affect ctx
        p1 = ctx.normalized_profile
        orig_exp_count = len(p1["experience"])
        p1["experience"].clear()
        self.assertEqual(len(p1["experience"]), 0)
        self.assertEqual(len(ctx.normalized_profile["experience"]), orig_exp_count)
        self.assertEqual(len(ctx.profile_copy()["experience"]), orig_exp_count)

        # 2. Mutating returned raw_profile does not affect ctx
        raw = ctx.raw_profile
        raw["name"] = "Malicious Modification"
        self.assertNotEqual(ctx.raw_profile.get("name"), "Malicious Modification")
        self.assertNotEqual(ctx.raw_profile_copy().get("name"), "Malicious Modification")

        # 3. Mutating evidence_index.profile does not affect index
        idx_p = ctx.evidence_index.profile
        idx_p["skills"] = ["Hacker"]
        self.assertNotIn("Hacker", ctx.evidence_index.profile.get("skills", []))
        self.assertNotIn("Hacker", ctx.evidence_index.skills)

        # 4. Attempting to overwrite attributes on ctx or evidence_index raises AttributeError
        with self.assertRaises(AttributeError):
            ctx.skills = ()  # type: ignore

        with self.assertRaises(AttributeError):
            ctx.normalized_profile = {}  # type: ignore

        with self.assertRaises(AttributeError):
            ctx.evidence_index.bullets = ()  # type: ignore

        with self.assertRaises(AttributeError):
            ctx.evidence_index.profile = {}  # type: ignore

        # 5. Mutating metric_anchors dictionaries does not affect ctx or evidence_index
        self.assertGreater(len(ctx.metric_anchors), 0)
        orig_val = ctx.metric_anchors[0].get("value")
        ctx.metric_anchors[0]["value"] = "POISON_VALUE"
        self.assertEqual(ctx.metric_anchors[0].get("value"), orig_val)

        orig_idx_val = ctx.evidence_index.metric_anchors[0].get("value")
        ctx.evidence_index.metric_anchors[0]["value"] = "POISON_VALUE"
        self.assertEqual(ctx.evidence_index.metric_anchors[0].get("value"), orig_idx_val)

    def test_10_profile_context_rejection_of_private_and_cache_tampering(self):
        """Test that ProfileContext unconditionally rejects any attribute assignment (including private fields)."""
        ctx = build_profile_context(self.profile_data)

        # 1. Private fields tampering must be blocked
        with self.assertRaises(AttributeError):
            ctx._canonical_profile = "malicious_override"

        with self.assertRaises(AttributeError):
            ctx._raw_profile = {}

        with self.assertRaises(AttributeError):
            ctx._normalized_profile = {}

        with self.assertRaises(AttributeError):
            ctx._metric_anchors = ()

        with self.assertRaises(AttributeError):
            ctx.new_unknown_attr = 999

        # 2. Canonical profile mutations do not corrupt subsequent reads
        canonical = ctx.get_canonical_profile()
        original_skills = list(canonical.skills)
        canonical.skills.append("POISON_SKILL")
        canonical.name = "POISON_NAME"

        fresh_canonical = ctx.get_canonical_profile()
        self.assertEqual(fresh_canonical.skills, original_skills)
        self.assertNotIn("POISON_SKILL", fresh_canonical.skills)
        self.assertNotEqual(fresh_canonical.name, "POISON_NAME")

        # 3. Context version alignment: evidence_index, claims, and canonical_profile reflect the same version
        self.assertEqual(fresh_canonical.name, ctx.normalized_profile["candidate"]["name"])
        self.assertEqual(set(fresh_canonical.skills), set(ctx.evidence_index.skills))
        self.assertEqual(len(ctx.claims), len(ctx.evidence_index.claims))


if __name__ == "__main__":
    unittest.main()

