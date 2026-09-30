"""
Unit tests for JD Matcher module.
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
    HardThreshold,
    CoreSkill,
    CoreResponsibility,
    ImplicitSignal,
    CandidateProfile,
    GapState,
    SkillImportance,
)
from modules.jd_analyst.matcher import JDMatcher


class TestJDMatcher(unittest.TestCase):

    def setUp(self):
        self.matcher = JDMatcher()

    def test_weighted_matching_formula(self):
        """Test formula: Match Score = 0.6*Must + 0.2*Nice + 0.2*Hidden."""
        jd = DecodedJD(
            raw_text="sample",
            job_title="大模型工程师",
            company_or_dept="AI部",
            hard_thresholds=[
                HardThreshold(category="education", requirement="统招本科及以上", min_degree="本科"),
                HardThreshold(category="experience_years", requirement="3年以上", min_years=3.0),
            ],
            core_skills=[
                CoreSkill(name="Python", category="language", importance=SkillImportance.MUST_HAVE.value, domain="通用"),
                CoreSkill(name="vLLM", category="framework", importance=SkillImportance.MUST_HAVE.value, domain="推理加速"),
                CoreSkill(name="Triton", category="language", importance=SkillImportance.NICE_TO_HAVE.value, domain="推理加速"),
            ],
            core_responsibilities=[],
            implicit_signals=[
                ImplicitSignal(
                    original_text="自驱力强",
                    translated_meaning="需要独立探索",
                    underlying_risk="缺乏文档",
                    candidate_countermeasure="反问立项流程",
                )
            ],
        )

        candidate = CandidateProfile(
            name="张三",
            education_level="本科",
            years_of_experience=4.0,
            skills=["Python", "vLLM", "CUDA"],
            project_descriptions=[
                "主导搭建基于 Python 与 vLLM 的大模型线上推理服务，实现吞吐提升 3.5x，QPS 达到 650，独立推进从零到一架构探索。"
            ],
            raw_resume_text="Python 精通，熟悉 vLLM 与 CUDA 开发，具备强自驱探索能力。",
        )

        result = self.matcher.match(jd, candidate)

        # Candidate has Python (with context/metrics) & vLLM (with metrics 3.5x, 650 QPS) -> MustHave = 1.0
        # Candidate has CUDA (adjacent to Triton) -> NiceToHave = 0.5
        # Candidate has "独立推进/自驱" -> HiddenSignalFit = 1.0
        # Expected Raw Score = 0.6*1.0 + 0.2*0.5 + 0.2*1.0 = 0.6 + 0.1 + 0.2 = 0.90
        self.assertAlmostEqual(result.must_have_score, 1.0, places=2)
        self.assertAlmostEqual(result.nice_to_have_score, 0.5, places=2)
        self.assertAlmostEqual(result.hidden_signal_fit, 1.0, places=2)
        self.assertAlmostEqual(result.raw_match_score, 0.90, places=2)
        self.assertFalse(result.is_hard_vetoed)
        self.assertAlmostEqual(result.final_match_score, 0.90, places=2)

    def test_single_item_scores(self):
        """Test 1.0 (Matched with metrics), 0.5 (insufficient evidence or expression gap), 0.0 (unmatched)."""
        jd = DecodedJD(
            raw_text="sample",
            job_title="LLM Infra",
            company_or_dept="Infra",
            hard_thresholds=[],
            core_skills=[
                CoreSkill(name="vLLM", category="framework", importance="must_have", domain="推理"),
                CoreSkill(name="DeepSpeed", category="framework", importance="must_have", domain="训练"),
                CoreSkill(name="Megatron-LM", category="framework", importance="must_have", domain="训练"),
                CoreSkill(name="Rust", category="language", importance="must_have", domain="语言"),
            ],
        )

        candidate = CandidateProfile(
            skills=["vLLM", "DeepSpeed", "FSDP"],  # FSDP is adjacent to Megatron-LM; DeepSpeed has no metrics; Rust is missing
            project_descriptions=[
                "使用 vLLM 部署千亿模型，并发吞吐提升 3x，首字延迟降低 45%。",  # vLLM has metrics -> 1.0
                "使用 DeepSpeed 进行模型微调训练。",  # DeepSpeed no metrics -> 0.5 (Insufficient Evidence)
                "参与 PyTorch FSDP 训练集群优化。",  # FSDP is adjacent to Megatron-LM -> 0.5 (Expression Gap)
                # Rust is completely missing -> 0.0 (Real Gap)
            ],
        )

        result = self.matcher.match(jd, candidate)
        gap_map = {g.requirement_name: g for g in result.gap_matrix}

        # vLLM: 1.0 Matched
        self.assertEqual(gap_map["技能-vLLM"].score, 1.0)
        self.assertEqual(gap_map["技能-vLLM"].state, GapState.MATCHED)

        # DeepSpeed: 0.5 Insufficient Evidence
        self.assertEqual(gap_map["技能-DeepSpeed"].score, 0.5)
        self.assertEqual(gap_map["技能-DeepSpeed"].state, GapState.INSUFFICIENT_EVIDENCE)

        # Megatron-LM: 0.5 Expression Gap (matched via FSDP adjacent)
        self.assertEqual(gap_map["技能-Megatron-LM"].score, 0.5)
        self.assertEqual(gap_map["技能-Megatron-LM"].state, GapState.EXPRESSION_GAP)

        # Rust: 0.0 Real Gap
        self.assertEqual(gap_map["技能-Rust"].score, 0.0)
        self.assertEqual(gap_map["技能-Rust"].state, GapState.REAL_GAP)

    def test_hard_threshold_veto_rule(self):
        """Test hard threshold veto on degree and experience years."""
        # Scenario 1: Degree veto
        jd_edu = DecodedJD(
            raw_text="sample",
            job_title="研究员",
            company_or_dept="实验室",
            hard_thresholds=[
                HardThreshold(category="education", requirement="硕士及以上", min_degree="硕士", is_mandatory=True),
            ],
            core_skills=[
                CoreSkill(name="Python", category="language", importance="must_have", domain="通用")
            ],
        )

        cand_bachelor = CandidateProfile(
            education_level="本科",
            years_of_experience=5.0,
            skills=["Python"],
            project_descriptions=["Python 深入开发，性能提升 2x。"],
        )

        res_edu = self.matcher.match(jd_edu, cand_bachelor)
        self.assertTrue(res_edu.is_hard_vetoed)
        self.assertGreaterEqual(len(res_edu.hard_veto_reasons), 1)
        self.assertIn("学历门槛拦截", res_edu.hard_veto_reasons[0])
        self.assertGreaterEqual(len(res_edu.breakthrough_advice), 1)
        self.assertIn("学历破局通道", res_edu.breakthrough_advice[0])
        # Score penalized
        self.assertLessEqual(res_edu.final_match_score, 0.45)

        # Scenario 2: Years veto
        jd_yrs = DecodedJD(
            raw_text="sample",
            job_title="架构师",
            company_or_dept="架构部",
            hard_thresholds=[
                HardThreshold(category="experience_years", requirement="5年以上经验", min_years=5.0, is_mandatory=True),
            ],
            core_skills=[
                CoreSkill(name="Python", category="language", importance="must_have", domain="通用")
            ],
        )

        cand_junior = CandidateProfile(
            education_level="硕士",
            years_of_experience=2.0,
            skills=["Python"],
            project_descriptions=["Python 研发 2x 加速。"],
        )

        res_yrs = self.matcher.match(jd_yrs, cand_junior)
        self.assertTrue(res_yrs.is_hard_vetoed)
        self.assertIn("年限门槛拦截", res_yrs.hard_veto_reasons[0])
        self.assertIn("年限破局通道", res_yrs.breakthrough_advice[0])
        self.assertLessEqual(res_yrs.final_match_score, 0.45)

    def test_five_state_gap_matrix(self):
        """Verify the 5-state Gap Matrix covers all 5 states."""
        jd = DecodedJD(
            raw_text="sample",
            job_title="AI 专家",
            company_or_dept="AI部",
            hard_thresholds=[
                HardThreshold(category="education", requirement="硕士及以上", min_degree="硕士"),
            ],
            core_skills=[
                CoreSkill(name="PyTorch", category="framework", importance="must_have", domain="通用"),
                CoreSkill(name="vLLM", category="framework", importance="must_have", domain="推理"),
                CoreSkill(name="Megatron-LM", category="framework", importance="must_have", domain="训练"),
                CoreSkill(name="Rust", category="language", importance="must_have", domain="语言"),
                CoreSkill(name="Triton", category="framework", importance="nice_to_have", domain="算子"),
            ],
            implicit_signals=[
                ImplicitSignal(
                    original_text="抗压能力强",
                    translated_meaning="高强度加班",
                    underlying_risk="负荷重",
                    candidate_countermeasure="面试时深入反问业务团队日常发版节奏与加班频次",
                )
            ]
        )

        candidate = CandidateProfile(
            education_level="硕士",
            years_of_experience=4.0,
            skills=["PyTorch", "vLLM", "DeepSpeed"],  # PyTorch (no metric: insufficient), vLLM (with metric: matched), DeepSpeed (adjacent to Megatron: expr gap), Rust (missing: real gap)
            project_descriptions=[
                "vLLM 优化推理服务，吞吐提升 3x，降低延迟 40%。",
                "PyTorch 模型开发。",
                "DeepSpeed 分布式训练调优。",
                "具备通用算法与深度学习背景。",  # hints at Triton -> To Be Confirmed
            ],
            raw_resume_text="经历过紧急攻坚上线保障。",  # hints at 抗压 -> Matched signal
        )

        result = self.matcher.match(jd, candidate)

        # Check that we have items across multiple states
        states_present = {g.state for g in result.gap_matrix}
        self.assertIn(GapState.MATCHED, states_present)
        self.assertIn(GapState.EXPRESSION_GAP, states_present)
        self.assertIn(GapState.INSUFFICIENT_EVIDENCE, states_present)
        self.assertIn(GapState.REAL_GAP, states_present)

        # Verify all gap items have actionable advice
        for g in result.gap_matrix:
            self.assertTrue(len(g.actionable_advice) > 5)
            self.assertTrue(len(g.gap_explanation) > 3)

    def test_expanded_adjacent_skills_matching(self):
        """Test non-AI adjacent stacks (Kafka/RocketMQ, Vue/React, etc.) provide partial credit."""
        matcher = self.matcher
        self.assertIn("rocketmq", matcher.ADJACENT_SKILLS["kafka"])
        self.assertIn("vue", matcher.ADJACENT_SKILLS["react"])
        self.assertIn("spark streaming", matcher.ADJACENT_SKILLS["flink"])
        self.assertIn("powerbi", matcher.ADJACENT_SKILLS["tableau"])

        jd = DecodedJD(
            raw_text="需要精通 Kafka 消息队列",
            job_title="后端工程师",
            company_or_dept="基础架构部",
            hard_thresholds=[],
            core_skills=[
                CoreSkill(name="Kafka", category="middleware", importance="must_have", domain="后端开发")
            ],
            implicit_signals=[],
        )
        cand = CandidateProfile(
            name="李四",
            education_level="本科",
            years_of_experience=3.0,
            skills=["RocketMQ", "Java", "MySQL"],
            project_descriptions=["基于 RocketMQ 实现异步解耦与流量削峰"],
            raw_resume_text="熟练掌握 RocketMQ 消息队列中间件",
        )

        res = matcher.match(jd, cand)
        self.assertGreater(res.must_have_score, 0.4)
        self.assertLess(res.must_have_score, 0.9)


if __name__ == "__main__":
    unittest.main()

