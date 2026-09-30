"""
Unit and Integration Test Suite for OfferGet.
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

from core.jd_compat import decode_jd
from core.jd_compat import match_profile_to_jd
from core.report_generator import generate_report
from core.validator import validate_bilingual_html, validate_anti_ai_slop
from core.ats_checker import audit_resume_ats
from core.gap_roi import calculate_gap_roi, SkillGapROIEngine
from core.offer_negotiator import evaluate_offer_package, OfferNegotiator
from core.anonymizer import PrivacyAnonymizer, anonymize_profile, deanonymize_text
from core.fact_guard import FactVerificationGuard, verify_resume_facts


class TestOfferGet(unittest.TestCase):

    def setUp(self):
        self.sample_jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"
        self.sample_profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        self.template_path = PROJECT_ROOT / "templates" / "offer_strategy.html"
        self.test_output = PROJECT_ROOT / "tests" / "temp_report.html"

        with open(self.sample_jd_path, "r", encoding="utf-8") as f:
            self.jd_text = f.read()

        with open(self.sample_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

    def tearDown(self):
        if self.test_output.exists():
            self.test_output.unlink()

    def test_01_jd_decoder_layers(self):
        decoded = decode_jd(self.jd_text)
        self.assertIn("metadata", decoded)
        self.assertIn("layers", decoded)
        self.assertEqual(len(decoded["layers"]), 5)
        self.assertIn("layer_1", decoded["layers"])
        self.assertIn("layer_5", decoded["layers"])
        self.assertTrue(len(decoded["detected_signals"]) >= 3)

    def test_02_jd_matcher_scores(self):
        decoded = decode_jd(self.jd_text)
        match_res = match_profile_to_jd(decoded, self.profile_data)
        self.assertGreaterEqual(match_res["overall_match_score"], 80)
        self.assertGreaterEqual(match_res["interview_prob"], 75)
        self.assertEqual(len(match_res["must_have_matches"]), 5)
        self.assertEqual(len(match_res["gaps"]), 3)

    def test_03_report_generator_and_bilingual_twin(self):
        decoded = decode_jd(self.jd_text)
        match_res = match_profile_to_jd(decoded, self.profile_data)
        generate_report(decoded, match_res, str(self.template_path), str(self.test_output))
        self.assertTrue(self.test_output.exists())

        val = validate_bilingual_html(str(self.test_output))
        self.assertTrue(val["passed"])
        self.assertTrue(val["root_lang_en"])
        self.assertEqual(val["en_count"], val["zh_count"])
        self.assertGreaterEqual(val["en_count"], 80)

    def test_04_validator_catches_invalid_html(self):
        bad_html_1 = "<html><body><span data-lang='en'>Hi</span></body></html>"
        val_1 = validate_bilingual_html(bad_html_1)
        self.assertFalse(val_1["passed"])

        bad_html_2 = "<html lang='en'><body><span data-lang='en'>Hi</span></body></html>"
        val_2 = validate_bilingual_html(bad_html_2)
        self.assertFalse(val_2["passed"])
        self.assertIn("Language twin mismatch", str(val_2["errors"]))

    def test_05_anti_ai_slop_auditor(self):
        clean_text = "负责大规模分布式训练工程，单机吞吐量提升 35%，P99 延迟降至 320ms。"
        res_clean = validate_anti_ai_slop(clean_text)
        self.assertTrue(res_clean["passed"])

        slop_text = "作为一名深耕大模型的专家——不仅极大推动了技术，而且深度赋能了业务，更彻底重塑了生态。"
        res_slop = validate_anti_ai_slop(slop_text)
        self.assertFalse(res_slop["passed"])
        self.assertGreaterEqual(res_slop["violation_count"], 2)

    def test_06_apexresume_subsystem_intact(self):
        apex_dir = PROJECT_ROOT / "ApexResume"
        self.assertTrue((apex_dir / "cli.py").exists())
        self.assertTrue((apex_dir / "core").is_dir())
        self.assertTrue((apex_dir / "tests").is_dir())
        self.assertTrue((apex_dir / "SKILL.md").exists())
        self.assertTrue((apex_dir / "README.md").exists())

    def test_07_ats_auditor_and_skill_ledger(self):
        res = audit_resume_ats(str(self.sample_profile_path), str(self.sample_jd_path))
        self.assertGreaterEqual(res["overall_score"], 75.0)
        self.assertEqual(res["verdict"], "READY_TO_SEND")
        self.assertIn("skill_ledger", res)
        self.assertGreater(len(res["skill_ledger"]["present"]), 0)
        self.assertIn("dimensions", res)
        self.assertIn("impact", res["dimensions"])
        self.assertIn("ats_readiness", res["dimensions"])

    def test_08_gap_roi_engine(self):
        gap_res = calculate_gap_roi(self.profile_data, [str(self.sample_jd_path)])
        self.assertIn("total_near_miss_jobs", gap_res)
        self.assertIn("missing_skills_ranking", gap_res)
        self.assertIn("top_recommendations", gap_res)
        self.assertIn("strategic_summary", gap_res)
        self.assertGreaterEqual(len(gap_res["top_recommendations"]), 1)
        top1 = gap_res["top_recommendations"][0]
        self.assertIn("skill", top1)
        self.assertIn("roi_score", top1)
        self.assertIn("actionable_plan", top1)

    def test_09_offer_negotiator_and_sample_offer(self):
        sample_offer_file = PROJECT_ROOT / "examples" / "sample_offer.json"
        self.assertTrue(sample_offer_file.exists())
        with open(sample_offer_file, "r", encoding="utf-8") as f:
            offer_dict = json.load(f)

        eval_res = evaluate_offer_package(offer_dict, self.profile_data)
        self.assertEqual(eval_res["trap_count"], 6)
        self.assertEqual(eval_res["risk_level"], "CRITICAL")
        self.assertGreater(eval_res["total_compensation"]["total_annual_package"], 1500000)

        negotiator = OfferNegotiator()
        counter = negotiator.generate_counter_offer(eval_res, target_base=90000)
        self.assertEqual(counter["target_base"], 90000)
        self.assertIn("verbal_negotiation_script", counter)
        self.assertEqual(len(counter["trap_remedy_requests"]), 6)

    def test_10_privacy_anonymizer(self):
        anon_profile, deanon_map = anonymize_profile(self.profile_data, level="strict")
        self.assertEqual(anon_profile["candidate"]["name"], "Dr. Alex Chen")
        self.assertEqual(anon_profile["candidate"]["phone"], "+86 138-0000-0000")
        self.assertEqual(anon_profile["candidate"]["email"], "candidate.ai@example.com")
        self.assertNotIn("张晨曦", str(anon_profile))

        # Reversible de-anonymization restores original profile exactly
        restored = deanonymize_text(anon_profile, deanon_map)
        self.assertEqual(restored, self.profile_data)

    def test_11_fact_verification_guard(self):
        # Grounded bullet passes
        bullet = "主导 64B 及 230B MoE 基座大模型在 1024 卡 H800 集群上的预训练，端到端 MFU 从 38.5% 优化至 54.2%，提前 3 周交付。"
        res_pass = verify_resume_facts(bullet, self.profile_data)
        self.assertTrue(res_pass["passed"])
        self.assertEqual(res_pass["verdict"], "FACT_CHECK_PASSED")

        # Exaggerated bullet fails
        inflated_bullet = "主导 230B MoE 基座大模型在 2048 卡 H800 集群上的预训练，端到端 MFU 从 38.5% 优化至 85%。"
        res_fail = verify_resume_facts(inflated_bullet, self.profile_data)
        self.assertFalse(res_fail["passed"])
        self.assertEqual(res_fail["verdict"], "FACT_DRIFT_DETECTED")
        self.assertGreater(len(res_fail["drifts"]), 0)


if __name__ == "__main__":
    unittest.main()
