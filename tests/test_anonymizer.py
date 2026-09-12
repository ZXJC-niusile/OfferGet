"""
Unit Test Suite for OfferGet Privacy Anonymizer Module.
Tests reversible pseudonymization, standard vs strict sensitivity levels,
deterministic token mappings, and map file serialization.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.anonymizer import (
    PrivacyAnonymizer,
    anonymize_profile,
    deanonymize_text,
    PREDEFINED_STANDARD_MAPPINGS,
    PREDEFINED_STRICT_MAPPINGS
)


class TestPrivacyAnonymizer(unittest.TestCase):

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        self.anonymizer = PrivacyAnonymizer()

    def test_01_standard_level_string_anonymization(self):
        sample_text = (
            "候选人：张晨曦，邮箱：alex.zhang.ai@alumni.tsinghua.edu.cn，"
            "电话：+86 186-0000-8899，GitHub: https://github.com/alex-zhang-ai，"
            "毕业于清华大学，曾就职于智谱前沿 AI 实验室。"
        )

        anon_text, deanon_map = self.anonymizer.anonymize(sample_text, level="standard")

        # PII should be masked
        self.assertNotIn("张晨曦", anon_text)
        self.assertNotIn("alex.zhang.ai@alumni.tsinghua.edu.cn", anon_text)
        self.assertNotIn("+86 186-0000-8899", anon_text)
        self.assertNotIn("https://github.com/alex-zhang-ai", anon_text)

        # Expected aliases
        self.assertIn("Dr. Alex Chen", anon_text)
        self.assertIn("candidate.ai@example.com", anon_text)
        self.assertIn("+86 138-0000-0000", anon_text)

        # In standard mode, institution and company should NOT be masked
        self.assertIn("清华大学", anon_text)
        self.assertIn("智谱前沿 AI 实验室", anon_text)

        # Reversible de-anonymization
        restored = self.anonymizer.deanonymize(anon_text, deanon_map)
        self.assertEqual(restored, sample_text)

    def test_02_strict_level_string_anonymization(self):
        sample_text = (
            "张晨曦在 1024 卡 H800 集群上主导训练，曾供职于智谱前沿 AI 实验室与字节跳动，"
            "毕业于清华大学 (Tsinghua University)，联系方式 +86 186-0000-8899。"
        )

        anon_text, deanon_map = self.anonymizer.anonymize(sample_text, level="strict")

        # Candidate PII masked
        self.assertNotIn("张晨曦", anon_text)
        self.assertNotIn("+86 186-0000-8899", anon_text)
        self.assertIn("Dr. Alex Chen", anon_text)
        self.assertIn("+86 138-0000-0000", anon_text)

        # Companies & Institutions masked
        self.assertNotIn("智谱前沿 AI 实验室", anon_text)
        self.assertNotIn("字节跳动", anon_text)
        self.assertNotIn("清华大学 (Tsinghua University)", anon_text)
        self.assertIn("Frontier AI Lab Alpha", anon_text)
        self.assertIn("Tech Conglomerate Beta", anon_text)

        # Cluster masked
        self.assertNotIn("1024 卡 H800 集群", anon_text)
        self.assertIn("1024-Card Confidential Accelerator Cluster", anon_text)

        # Reversible de-anonymization
        restored = self.anonymizer.deanonymize(anon_text, deanon_map)
        self.assertEqual(restored, sample_text)

    def test_03_dict_anonymize_and_deanonymize_profile_strict(self):
        anon_profile, deanon_map = self.anonymizer.anonymize(self.profile_data, level="strict")

        # Verify candidate dictionary fields masked
        cand = anon_profile["candidate"]
        self.assertEqual(cand["name"], "Dr. Alex Chen")
        self.assertEqual(cand["phone"], "+86 138-0000-0000")
        self.assertEqual(cand["email"], "candidate.ai@example.com")
        self.assertEqual(cand["github"], "https://github.com/candidate-ai")
        self.assertEqual(cand["linkedin"], "https://linkedin.com/in/candidate-ai")
        self.assertNotIn("清华大学", cand["institution"])

        # Verify experience companies masked
        for exp in anon_profile["experience"]:
            self.assertNotIn("智谱前沿 AI 实验室", exp["company"])
            self.assertNotIn("字节跳动", exp["company"])

        # Reversible de-anonymization must match original profile 100%
        restored_profile = self.anonymizer.deanonymize(anon_profile, deanon_map)
        self.assertEqual(restored_profile, self.profile_data)

    def test_04_dict_anonymize_and_deanonymize_profile_standard(self):
        anon_profile, deanon_map = self.anonymizer.anonymize(self.profile_data, level="standard")

        # PII masked
        cand = anon_profile["candidate"]
        self.assertEqual(cand["name"], "Dr. Alex Chen")
        self.assertEqual(cand["phone"], "+86 138-0000-0000")
        self.assertEqual(cand["email"], "candidate.ai@example.com")

        # Companies preserved in standard mode
        self.assertIn("智谱前沿 AI 实验室", anon_profile["experience"][0]["company"])
        self.assertIn("字节跳动", anon_profile["experience"][1]["company"])

        # Reversible de-anonymization must match original profile 100%
        restored_profile = self.anonymizer.deanonymize(anon_profile, deanon_map)
        self.assertEqual(restored_profile, self.profile_data)

    def test_05_save_and_load_map(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            anon_profile, deanon_map = self.anonymizer.anonymize(self.profile_data, level="strict")
            self.anonymizer.save_map(deanon_map, tmp_path)

            self.assertTrue(os.path.exists(tmp_path))
            loaded_map = self.anonymizer.load_map(tmp_path)
            self.assertEqual(loaded_map, deanon_map)

            # Deanonymize using loaded map
            restored = self.anonymizer.deanonymize(anon_profile, loaded_map)
            self.assertEqual(restored, self.profile_data)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_06_top_level_convenience_functions(self):
        text = "联系人：张晨曦，电话：+86 186-0000-8899"
        anon, mapping = anonymize_profile(text, level="strict")
        self.assertIn("Dr. Alex Chen", anon)
        self.assertIn("+86 138-0000-0000", anon)

        restored = deanonymize_text(anon, mapping)
        self.assertEqual(restored, text)

    def test_07_invalid_level_and_type_handling(self):
        with self.assertRaises(ValueError):
            self.anonymizer.anonymize("Hello", level="super_ultra_secret")

        with self.assertRaises(TypeError):
            self.anonymizer.anonymize(12345)  # Not dict or str

        with self.assertRaises(TypeError):
            self.anonymizer.deanonymize(12345, {})


if __name__ == "__main__":
    unittest.main()
