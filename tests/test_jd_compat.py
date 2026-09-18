"""
Unit test suite for core.jd_compat:
- profile_to_canonical unified SSOT parsing
- Non-hallucination of unknown facts
- Legacy compatibility APIs (decode_legacy, match_legacy, to_canonical)
"""

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
from modules.jd_analyst.models import CandidateProfile


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

    def test_05_to_canonical(self):
        """Test to_canonical conversion from DecodedJDCompat."""
        decoded = decode_legacy(self.jd_text)
        canonical_jd = to_canonical(decoded)
        self.assertEqual(canonical_jd.job_title, decoded["metadata"]["role"])


if __name__ == "__main__":
    unittest.main()
