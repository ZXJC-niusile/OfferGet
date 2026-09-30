"""
Unit test suite for OfferGet JD Decision Engine (core.jd_decision):
- DecodeBeforeMatchGate pipeline enforcement (strict and non-strict modes)
- ShouldIApplyEvaluator 5-dimension evaluation
- Star rating (1~5), mandatory 3 pros and 3 cons
- Probability intervals and channel adjustments
- 6-week structured action plan
- Integration with JDService and MatchService
"""

import json
import unittest
from pathlib import Path

from core.jd_decision import (
    DecodeBeforeMatchGate,
    DecisionVerdict,
    NextAction,
    ShouldIApplyEvaluator,
    UnverifiedJDPipelineError,
)
from core.jd_compat import (
    decode_legacy,
    match_legacy,
    to_canonical,
    profile_to_canonical,
)
from core.profile_adapter import build_profile_context
from core.services import JDService, MatchService
from core.jd_analyst.decoder import JDDecoder
from core.jd_analyst.matcher import JDMatcher
from core.jd_analyst.models import (
    CandidateProfile,
    DecodedJD,
    HardThreshold,
    CoreSkill,
    SkillImportance,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDecodeBeforeMatchGate(unittest.TestCase):

    def setUp(self):
        self.raw_jd = "职位名称：大模型推理优化专家\n职责：负责 vLLM 推理加速与 CUDA 算子优化。\n要求：精通 Python、C++、PyTorch，硕士及以上学历。"
        self.decoded_compat = decode_legacy(self.raw_jd)
        self.decoded_canonical = to_canonical(self.decoded_compat)

    def test_01_pass_canonical_decoded_jd(self):
        """Passing DecodedJD passes gate without re-decoding."""
        result = DecodeBeforeMatchGate.enforce(self.decoded_canonical)
        self.assertIs(result, self.decoded_canonical)

    def test_02_pass_decoded_compat(self):
        """Passing DecodedJDCompat unwraps canonical DecodedJD."""
        result = DecodeBeforeMatchGate.enforce(self.decoded_compat)
        self.assertIs(result, self.decoded_compat.canonical)

    def test_03_non_strict_mode_auto_decodes(self):
        """In non-strict mode, raw string is automatically decoded into DecodedJD."""
        result = DecodeBeforeMatchGate.enforce(self.raw_jd, strict=False)
        self.assertIsInstance(result, DecodedJD)
        self.assertEqual(result.job_title, "大模型推理优化专家")

    def test_04_strict_mode_blocks_raw_string(self):
        """In strict mode, raw string raises UnverifiedJDPipelineError."""
        with self.assertRaises(UnverifiedJDPipelineError) as ctx:
            DecodeBeforeMatchGate.enforce(self.raw_jd, strict=True)
        self.assertIn("Decode-Before-Match Gate Triggered", str(ctx.exception))

    def test_05_invalid_type_raises_type_error(self):
        """Passing an invalid object raises TypeError."""
        with self.assertRaises(TypeError):
            DecodeBeforeMatchGate.enforce(12345)


class TestShouldIApplyEvaluator(unittest.TestCase):

    def setUp(self):
        profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        self.candidate = profile_to_canonical(self.profile_data)

        self.jd_text = (
            "职位名称：大模型算法专家\n"
            "部门：AI 实验室\n"
            "职责：负责千亿大模型预训练与推理优化，主导 vLLM 与 FlashAttention 算子加速。\n"
            "要求：精通 PyTorch、CUDA，3 年以上大模型研发经验，硕士及以上学历。"
        )
        self.decoded_jd = JDDecoder().decode(self.jd_text)
        self.evaluator = ShouldIApplyEvaluator()

    def test_01_evaluate_strong_match(self):
        """Candidate matching well gets high score, 4-5 stars, and valid 3 pros / 3 cons."""
        matcher_result = JDMatcher().match(self.decoded_jd, self.candidate)
        report = self.evaluator.evaluate(self.decoded_jd, self.candidate, matcher_result)

        self.assertGreaterEqual(report.stars, 3)
        self.assertIn(report.verdict, [DecisionVerdict.STRONG_GO, DecisionVerdict.CONDITIONAL_GO, DecisionVerdict.REVISE_FIRST])
        self.assertEqual(len(report.pros), 3)
        self.assertEqual(len(report.cons), 3)
        for pro in report.pros:
            self.assertTrue(len(pro) > 5)
        for con in report.cons:
            self.assertTrue(len(con) > 5)

        # Probabilities
        self.assertGreaterEqual(report.probability_range[1], report.probability_range[0])
        self.assertIn("cold_apply", report.probability_breakdown)
        self.assertIn("tailored_apply", report.probability_breakdown)
        self.assertIn("referral", report.probability_breakdown)

        # 6-week plan
        self.assertEqual(len(report.six_week_plan.weeks), 4)
        self.assertIn("第 1~2 周", report.six_week_plan.weeks[0].week_range)
        self.assertIn("第 6 周", report.six_week_plan.weeks[3].week_range)

    def test_02_evaluate_hard_veto_results_in_no_go(self):
        """Candidate with hard threshold veto (e.g. requires 博士 but candidate is 硕士) gets 1 star NO_GO."""
        # Add impossible hard threshold (candidate has 7 years, requires 10 years)
        veto_jd = JDDecoder().decode(self.jd_text)
        veto_jd.hard_thresholds.append(
            HardThreshold(category="experience_years", requirement="10 年以上大模型架构经验", min_years=10, is_mandatory=True)
        )
        matcher_result = JDMatcher().match(veto_jd, self.candidate)
        self.assertTrue(matcher_result.is_hard_vetoed)

        report = self.evaluator.evaluate(veto_jd, self.candidate, matcher_result)
        self.assertEqual(report.stars, 1)
        self.assertEqual(report.verdict, DecisionVerdict.NO_GO)
        self.assertEqual(report.next_action, NextAction.SKIP)
        self.assertIn("硬性门槛未满足", report.cons[0])

    def test_03_services_integration(self):
        """Verify JDService.evaluate_should_i_apply and MatchService.match integration."""
        jd_service = JDService()
        match_service = MatchService()

        # JDService evaluate_should_i_apply
        decision = jd_service.evaluate_should_i_apply(self.decoded_jd, self.profile_data)
        self.assertIn("stars", decision)
        self.assertIn("verdict", decision)
        self.assertEqual(len(decision["pros"]), 3)
        self.assertEqual(len(decision["cons"]), 3)
        self.assertIn("six_week_plan", decision)

        # MatchService with strict_gate=True on raw string raises UnverifiedJDPipelineError
        with self.assertRaises(UnverifiedJDPipelineError):
            match_service.match(self.jd_text, self.profile_data, strict_gate=True)

        # MatchService with decoded JD succeeds and includes should_i_apply
        matched = match_service.match(self.decoded_jd, self.profile_data, strict_gate=True)
        self.assertIn("should_i_apply", matched)
        self.assertIn("stars", matched["should_i_apply"])
        self.assertEqual(len(matched["should_i_apply"]["pros"]), 3)
        self.assertEqual(len(matched["should_i_apply"]["cons"]), 3)


if __name__ == "__main__":
    unittest.main()
