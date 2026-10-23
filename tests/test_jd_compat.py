"""
Unit test suite for core.jd_compat:
- profile_to_canonical unified SSOT parsing
- Non-hallucination of unknown facts
- Legacy compatibility APIs (decode_legacy, match_legacy, to_canonical)
"""

import copy
import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.jd_compat import (
    decode_legacy,
    match_legacy,
    profile_to_canonical,
    to_canonical,
)
from core.jd_analyst.models import CandidateProfile


class TestJDCompat(unittest.TestCase):

    def setUp(self):
        self.sample_profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        self.sample_jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"

        with open(self.sample_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        with open(self.sample_jd_path, "r", encoding="utf-8") as f:
            self.jd_text = f.read()

    def test_01_profile_to_canonical_standard_profile(self):
        """Test profile_to_canonical with a Track 1 standard structured profile."""
        canonical = profile_to_canonical(self.profile_data)

        self.assertIsInstance(canonical, CandidateProfile)
        self.assertEqual(canonical.name, "张晨曦")
        self.assertEqual(canonical.education_level, "博士")
        self.assertEqual(canonical.years_of_experience, 7.0)
        self.assertIn("Python", canonical.skills)
        self.assertTrue(any("Megatron-LM" in s for s in canonical.skills))
        self.assertGreater(len(canonical.project_descriptions), 0)

    def test_02_profile_to_canonical_flat_profile(self):
        """Test profile_to_canonical with a Track 2 flat profile."""
        flat_profile = {
            "name": "李四",
            "education": {
                "school": "北京大学",
                "major": "微电子",
                "degree": "硕士",
            },
            "years_of_experience": 4,
            "skills": ["C++", "CUDA"],
            "experience": [
                {
                    "company": "算力科技",
                    "role": "算子优化工程师",
                    "bullets": ["开发 FlashAttention-3 Triton Kernel"]
                }
            ]
        }
        canonical = profile_to_canonical(flat_profile)

        self.assertIsInstance(canonical, CandidateProfile)
        self.assertEqual(canonical.name, "李四")
        self.assertEqual(canonical.education_level, "硕士")
        self.assertEqual(canonical.years_of_experience, 4.0)
        self.assertIn("C++", canonical.skills)
        self.assertIn("CUDA", canonical.skills)
        self.assertTrue(any("FlashAttention-3" in desc for desc in canonical.project_descriptions))

    def test_03_profile_to_canonical_unknown_facts_boundary(self):
        """Test that profile_to_canonical does NOT invent unknown education, major, or years."""
        minimal = {"name": "王五"}
        canonical = profile_to_canonical(minimal)

        self.assertEqual(canonical.name, "王五")
        self.assertEqual(canonical.education_level, "")
        self.assertEqual(canonical.years_of_experience, 0.0)
        self.assertEqual(canonical.major, "")
        self.assertEqual(canonical.degree_school, "")

    def test_04_decode_legacy_and_match_legacy(self):
        """Test decode_legacy and match_legacy compatibility functions."""
        decoded = decode_legacy(self.jd_text)
        self.assertIn("metadata", decoded)
        self.assertIn("layers", decoded)
        self.assertIn("requirements", decoded)

        # Match legacy
        match_result = match_legacy(decoded, self.profile_data)
        self.assertIn("overall_match_score", match_result)
        self.assertIn("interview_prob", match_result)
        self.assertIn("breakdown", match_result)
        self.assertIn("verdict", match_result)
        self.assertIn("gaps", match_result)

    def test_06_decoded_jd_compat_contract(self):
        """Test DecodedJDCompat carries canonical object and remains JSON-serializable dict."""
        from core.jd_compat import DecodedJDCompat
        from core.jd_analyst.models import DecodedJD

        decoded = decode_legacy(self.jd_text)
        self.assertIsInstance(decoded, DecodedJDCompat)
        self.assertIsInstance(decoded, dict)
        self.assertIsInstance(decoded.canonical, DecodedJD)

        # Must be cleanly serializable with standard json
        dumped = json.dumps(decoded, ensure_ascii=False)
        self.assertTrue(len(dumped) > 0)
        reloaded = json.loads(dumped)
        self.assertEqual(reloaded["metadata"]["role"], decoded["metadata"]["role"])

    def test_07_to_canonical_all_types(self):
        """Test to_canonical handles DecodedJDCompat, DecodedJD, plain dict, and rejects invalid types."""
        from core.jd_analyst.models import DecodedJD
        from core.jd_compat import DecodedJDCompat

        # 1. From DecodedJDCompat
        compat = decode_legacy(self.jd_text)
        res1 = to_canonical(compat)
        self.assertIs(res1, compat.canonical)

        # 2. From DecodedJD directly
        direct_jd = compat.canonical
        res2 = to_canonical(direct_jd)
        self.assertIs(res2, direct_jd)

        # 3. From plain dict (e.g. legacy json dict)
        plain_dict = dict(compat)
        self.assertNotIsInstance(plain_dict, DecodedJDCompat)
        res3 = to_canonical(plain_dict)
        self.assertIsInstance(res3, DecodedJD)
        self.assertEqual(res3.job_title, compat["metadata"]["role"])

        # 4. Rejection of invalid types
        with self.assertRaises(TypeError):
            to_canonical(12345)
        with self.assertRaises(TypeError):
            to_canonical(None)

    def test_08_empty_jd_handling(self):
        """Test decode_legacy handles empty string gracefully without raising exceptions."""
        empty_decoded = decode_legacy("")
        self.assertIsInstance(empty_decoded, dict)
        self.assertEqual(empty_decoded["metadata"]["role"], "未指定职位")
        self.assertEqual(empty_decoded["metadata"]["company"], "未知团队")
        canonical_empty = to_canonical(empty_decoded)
        self.assertEqual(canonical_empty.job_title, "未指定职位")

    def test_09_match_legacy_units_and_json_contract(self):
        """Test match_legacy scores, probabilities, and JSON contract."""
        decoded = decode_legacy(self.jd_text)
        match_res = match_legacy(decoded, self.profile_data)

        # Integer score in [0, 100]
        score = match_res["overall_match_score"]
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

        # Unknown probabilities remain JSON null, distinct from a measured 0%.
        self.assertIsNone(match_res["interview_prob"])
        self.assertIsNone(match_res["interview_probability_range"])
        self.assertEqual(match_res["probability_status"], "unavailable")
        self.assertTrue(match_res["probability_basis"])

        # JSON serializable
        dumped = json.dumps(match_res, ensure_ascii=False)
        self.assertTrue(len(dumped) > 0)

    def test_10_report_generator_adapt_parity(self):
        """Record parity and behavior between to_canonical and report_generator._adapt_decoded_jd."""
        from core.report_generator import _adapt_decoded_jd

        decoded = decode_legacy(self.jd_text)
        c1 = to_canonical(decoded)
        c2 = _adapt_decoded_jd(decoded)

        # Both return the exact canonical object when DecodedJDCompat is passed
        self.assertIs(c1, decoded.canonical)
        self.assertIs(c2, decoded.canonical)

        # Both produce consistent job_title and company when plain dict is passed
        plain_dict = dict(decoded)
        p1 = to_canonical(plain_dict)
        p2 = _adapt_decoded_jd(plain_dict)
        self.assertEqual(p1.job_title, p2.job_title)
        self.assertIn(p1.job_title, ["大模型算法专家", decoded["metadata"]["role"]])
        self.assertTrue(len(p1.core_skills) > 0)
        self.assertTrue(len(p2.core_skills) > 0)

        # Field-level comparison when raw_text is absent (pure legacy dict rehydration)
        stripped_dict = copy.deepcopy(plain_dict)
        stripped_dict.pop("raw_text", None)
        stripped_dict.pop("clean_text", None)

        s1 = to_canonical(stripped_dict)
        s2 = _adapt_decoded_jd(stripped_dict)
        self.assertEqual(s1.job_title, s2.job_title)
        # Verify both reconstruct hard thresholds and core skills from requirements
        self.assertEqual(len(s1.hard_thresholds), len(s2.hard_thresholds))
        s1_skill_names = {s.name for s in s1.core_skills}
        s2_skill_names = {s.name for s in s2.core_skills}
        self.assertEqual(s1_skill_names, s2_skill_names)


if __name__ == "__main__":
    unittest.main()
