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
    ProfileEvidenceIndex,
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


if __name__ == "__main__":
    unittest.main()
