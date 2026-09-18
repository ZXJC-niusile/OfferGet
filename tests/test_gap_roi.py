"""
Unit test suite for Skill Gap ROI Engine (core.gap_roi).
"""

import os
import sys
import json
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.gap_roi import SkillGapROIEngine, calculate_gap_roi


class TestSkillGapROIEngine(unittest.TestCase):

    def setUp(self):
        self.sample_profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        self.sample_jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"

        with open(self.sample_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        with open(self.sample_jd_path, "r", encoding="utf-8") as f:
            self.jd_text = f.read()

        self.engine = SkillGapROIEngine()

    def test_01_analyze_gap_roi_structure(self):
        result = self.engine.analyze_gap_roi(self.profile_data, [self.jd_text])

        self.assertIn("total_near_miss_jobs", result)
        self.assertIn("missing_skills_ranking", result)
        self.assertIn("top_recommendations", result)
        self.assertIn("strategic_summary", result)
        self.assertIn("assumptions", result)
        self.assertIn("unknown_fields", result)
        self.assertIn("evidence_status", result)

        self.assertIsInstance(result["total_near_miss_jobs"], int)
        self.assertIsInstance(result["missing_skills_ranking"], list)
        self.assertIsInstance(result["top_recommendations"], list)
        self.assertIsInstance(result["strategic_summary"], str)
        self.assertIsInstance(result["assumptions"], list)
        self.assertIsInstance(result["unknown_fields"], list)
        self.assertIsInstance(result["evidence_status"], str)

        self.assertLessEqual(len(result["top_recommendations"]), 5)

        if result["missing_skills_ranking"]:
            first = result["missing_skills_ranking"][0]
            required_keys = [
                "skill",
                "frequency_in_near_miss",
                "jobs_unlocked_estimate",
                "difficulty",
                "rampup_estimate",
                "roi_score",
                "actionable_plan",
            ]
            for k in required_keys:
                self.assertIn(k, first)
            self.assertIn(first["difficulty"], ("Low", "Medium", "High"))
            self.assertGreater(first["roi_score"], 0.0)

    def test_02_convenience_function(self):
        result = calculate_gap_roi(self.profile_data, [str(self.sample_jd_path)])
        self.assertIn("total_near_miss_jobs", result)
        self.assertIn("top_recommendations", result)
        self.assertGreaterEqual(len(result["top_recommendations"]), 1)

    def test_03_roi_formula_ordering(self):
        result = self.engine.analyze_gap_roi(self.profile_data, [self.jd_text])
        ranking = result["missing_skills_ranking"]
        if len(ranking) >= 2:
            for i in range(len(ranking) - 1):
                self.assertGreaterEqual(ranking[i]["roi_score"], ranking[i + 1]["roi_score"])

    def test_04_multiple_jds(self):
        jd_2 = """
        【岗位名称】大模型推理部署架构师
        【所属部门】AI工程部
        【薪资范围】120W - 180W
        【任职要求】
        1. 精通 vLLM 与 PagedAttention，具备 C++/CUDA 算子开发经验；
        2. 熟悉 FP8 量化与 Speculative Decoding 投机采样；
        3. 熟练掌握 SGLang 与 RadixAttention，具备高并发线上服务保障经验。
        """
        result = self.engine.analyze_gap_roi(self.profile_data, [self.jd_text, jd_2])
        self.assertGreaterEqual(result["total_near_miss_jobs"], 1)
        self.assertTrue(len(result["strategic_summary"]) > 50)

    def test_05_unknown_facts_boundary_and_assumptions(self):
        """Test missing facts (education, experience, major) are tracked without hallucination."""
        minimal_profile = {"name": "未知候选人", "skills": ["Python"]}
        result = self.engine.analyze_gap_roi(minimal_profile, [self.jd_text])

        self.assertIn("unknown_fields", result)
        self.assertIn("education", result["unknown_fields"])
        self.assertIn("years_of_experience", result["unknown_fields"])
        self.assertIn("major", result["unknown_fields"])

        self.assertEqual(result["evidence_status"], "partial")
        self.assertTrue(result["input_quality"]["unknown_experience"])
        self.assertTrue(result["input_quality"]["unknown_education"])
        self.assertTrue(result["input_quality"]["unknown_major"])
        self.assertGreaterEqual(len(result["assumptions"]), 3)


if __name__ == "__main__":
    unittest.main()
