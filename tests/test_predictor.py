"""
Unit tests for Interview Predictor module (Probability & Top 20 Questions).
"""

import unittest
import os
import sys

# Ensure OfferGet root is in sys.path
OFFERGET_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if OFFERGET_ROOT not in sys.path:
    sys.path.insert(0, OFFERGET_ROOT)

from modules.jd_analyst.models import (
    DecodedJD,
    MatcherResult,
    ChannelType,
    QuestionCategory,
)
from modules.jd_analyst.predictor import (
    InterviewProbabilityCalculator,
    InterviewTop20Predictor,
    JDPredictor,
)


class TestPredictor(unittest.TestCase):

    def setUp(self):
        self.calc = InterviewProbabilityCalculator()
        self.top20 = InterviewTop20Predictor()
        self.pipeline = JDPredictor()

    def test_probability_calculation_channels(self):
        """Test channel multiplier differences (Internal referral vs Cold application)."""
        # High match result (score = 0.90, not vetoed)
        matcher_high = MatcherResult(
            must_have_score=1.0,
            nice_to_have_score=1.0,
            hidden_signal_fit=0.8,
            raw_match_score=0.96,
            final_match_score=0.90,
            is_hard_vetoed=False,
        )

        forecast = self.calc.calculate(matcher_high, listing_age_days=10)

        # Base should be [60.0, 85.0]
        self.assertEqual(forecast.base_min_prob, 60.0)
        self.assertEqual(forecast.base_max_prob, 85.0)
        self.assertEqual(forecast.age_decay_multiplier, 1.0)
        self.assertFalse(forecast.is_ghost_job_risk)

        channels = forecast.channel_forecasts
        internal = channels[ChannelType.INTERNAL_REFERRAL.value]
        cold = channels[ChannelType.COLD_APPLICATION.value]
        recruiter = channels[ChannelType.RECRUITER_DIRECT.value]

        # Internal referral (x2.5) should be clamped up to 95.0%
        self.assertGreater(internal.min_prob, 80.0)
        self.assertLessEqual(internal.max_prob, 96.0)

        # Cold application (x0.3): base 60*0.3 = 18.0, 85*0.3 = 25.5
        self.assertAlmostEqual(cold.min_prob, 18.0, delta=1.0)
        self.assertAlmostEqual(cold.max_prob, 25.5, delta=1.0)

        # Recruiter direct (x1.2): base 60*1.2 = 72.0, 85*1.2 = 95.0 clamped
        self.assertGreater(recruiter.min_prob, cold.max_prob)

    def test_listing_age_decay_and_ghost_job(self):
        """Test listing age decay and ghost job trigger (> 60 days)."""
        matcher_mid = MatcherResult(
            must_have_score=0.7,
            nice_to_have_score=0.7,
            hidden_signal_fit=0.7,
            raw_match_score=0.70,
            final_match_score=0.70,
            is_hard_vetoed=False,
        )

        # 1. Fresh job (5 days) -> decay multiplier 1.1
        fc_fresh = self.calc.calculate(matcher_mid, listing_age_days=5)
        self.assertEqual(fc_fresh.age_decay_multiplier, 1.1)
        self.assertFalse(fc_fresh.is_ghost_job_risk)

        # 2. Ghost job (75 days) -> decay multiplier 0.4 and flag is True
        fc_ghost = self.calc.calculate(matcher_mid, listing_age_days=75)
        self.assertEqual(fc_ghost.age_decay_multiplier, 0.4)
        self.assertTrue(fc_ghost.is_ghost_job_risk)
        self.assertIn("幽灵职位", fc_ghost.strategic_summary)

        # Probability should be significantly lower for ghost job
        internal_fresh = fc_fresh.channel_forecasts[ChannelType.INTERNAL_REFERRAL.value]
        internal_ghost = fc_ghost.channel_forecasts[ChannelType.INTERNAL_REFERRAL.value]
        self.assertGreater(internal_fresh.min_prob, internal_ghost.min_prob)

    def test_hard_veto_suppression(self):
        """Hard veto should suppress base probabilities to [5%, 15%]."""
        matcher_vetoed = MatcherResult(
            must_have_score=0.9,
            nice_to_have_score=0.9,
            hidden_signal_fit=0.9,
            raw_match_score=0.90,
            final_match_score=0.45,
            is_hard_vetoed=True,
            hard_veto_reasons=["学历门槛拦截"],
        )

        fc = self.calc.calculate(matcher_vetoed, listing_age_days=15)
        self.assertEqual(fc.base_min_prob, 5.0)
        self.assertEqual(fc.base_max_prob, 15.0)
        cold = fc.channel_forecasts[ChannelType.COLD_APPLICATION.value]
        self.assertLessEqual(cold.max_prob, 10.0)

    def test_top20_interview_questions_structure(self):
        """Test that Top 20 predictor returns exactly 20 questions, 4 categories x 5 questions."""
        jd = DecodedJD(
            raw_text="sample",
            job_title="大模型推理加速工程师",
            company_or_dept="AI实验室",
            tech_domains=["算力基础设施", "推理加速", "评测对齐", "长上下文"],
        )
        matcher = MatcherResult(
            must_have_score=0.8,
            nice_to_have_score=0.8,
            hidden_signal_fit=0.8,
            raw_match_score=0.8,
            final_match_score=0.8,
            is_hard_vetoed=False,
        )

        questions = self.top20.predict(jd, matcher)

        # Exactly 20 questions
        self.assertEqual(len(questions), 20)

        # Categorization check: 4 categories x 5 questions
        arch_qs = [q for q in questions if q.category_type == QuestionCategory.ARCHITECTURE]
        princ_qs = [q for q in questions if q.category_type == QuestionCategory.PRINCIPLES]
        bq_qs = [q for q in questions if q.category_type == QuestionCategory.BQ]
        rev_qs = [q for q in questions if q.category_type == QuestionCategory.REVERSE]

        self.assertEqual(len(arch_qs), 5)
        self.assertEqual(len(princ_qs), 5)
        self.assertEqual(len(bq_qs), 5)
        self.assertEqual(len(rev_qs), 5)

        # Verify every question has signal, intent, keypoints and bilingual translations
        for i, q in enumerate(questions, 1):
            self.assertEqual(q.question_id, i)
            self.assertTrue(len(q.question_cn) > 10)
            self.assertTrue(len(q.question_en) > 10)
            self.assertTrue(len(q.jd_signal) > 3)
            self.assertTrue(len(q.interviewer_intent) > 10)
            self.assertTrue(len(q.prep_keypoints) > 10)

    def test_end_to_end_jd_predictor(self):
        """Test full JDPredictor pipeline execution."""
        jd = DecodedJD(raw_text="sample", job_title="AI Agent 专家", company_or_dept="AI部")
        matcher = MatcherResult(
            must_have_score=0.85,
            nice_to_have_score=0.85,
            hidden_signal_fit=0.85,
            raw_match_score=0.85,
            final_match_score=0.85,
            is_hard_vetoed=False,
        )

        pred_res = self.pipeline.predict(jd, matcher, listing_age_days=10)
        self.assertEqual(len(pred_res.top20_questions), 20)
        self.assertIn("INTERNAL_REFERRAL", pred_res.probability_forecast.channel_forecasts)


if __name__ == "__main__":
    unittest.main()
