"""
Unit tests for Offer Strategy Reporter module (HTML generation & bilingual outputs).
"""

import unittest
import os
import sys
import tempfile

# Ensure OfferGet root is in sys.path
OFFERGET_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if OFFERGET_ROOT not in sys.path:
    sys.path.insert(0, OFFERGET_ROOT)

from modules.jd_analyst.models import (
    DecodedJD,
    CandidateProfile,
    MatcherResult,
    RedFlagReport,
    RedFlagItem,
    RedFlagType,
    HardThreshold,
    CoreSkill,
    CoreResponsibility,
    ImplicitSignal,
    BusinessPainPoint,
    GapItem,
    GapState,
)
from modules.jd_analyst.predictor import JDPredictor
from modules.jd_analyst.reporter import OfferStrategyReporter
from modules.jd_analyst import analyze_jd


class TestReporter(unittest.TestCase):

    def setUp(self):
        self.reporter = OfferStrategyReporter()
        self.predictor = JDPredictor()

        self.jd = DecodedJD(
            raw_text="sample raw text",
            job_title="大模型强化学习算法专家",
            company_or_dept="核心商业化算法部",
            hard_thresholds=[
                HardThreshold(category="education", requirement="硕士及以上", min_degree="硕士"),
                HardThreshold(category="experience_years", requirement="3年以上", min_years=3.0),
            ],
            core_responsibilities=[
                CoreResponsibility(title="大模型RLHF/DPO对齐", description="负责千亿模型对齐", domain="评测对齐"),
            ],
            core_skills=[
                CoreSkill(name="PyTorch", category="framework", importance="must_have", domain="通用"),
                CoreSkill(name="vLLM", category="framework", importance="must_have", domain="推理"),
                CoreSkill(name="DPO", category="algorithm", importance="must_have", domain="对齐"),
            ],
            implicit_signals=[
                ImplicitSignal(
                    original_text="抗压能力强",
                    translated_meaning="常态化加班",
                    underlying_risk="负荷重",
                    candidate_countermeasure="问排期",
                )
            ],
            business_pain_points=[
                BusinessPainPoint(
                    aspect="推理时延瓶颈",
                    description="高并发P99过长",
                    evaluation_metric="P99 < 500ms",
                )
            ],
            tech_domains=["算力基础设施", "评测对齐", "推理加速"],
        )

        self.candidate = CandidateProfile(
            name="李四",
            education_level="硕士",
            years_of_experience=4.0,
            skills=["PyTorch", "vLLM", "DPO"],
            project_descriptions=[
                "主导千亿大模型推理部署，基于 vLLM 实现吞吐提升 3x，QPS 达 500。"
            ],
        )

        self.matcher = MatcherResult(
            must_have_score=0.88,
            nice_to_have_score=1.0,
            hidden_signal_fit=0.85,
            raw_match_score=0.90,
            final_match_score=0.90,
            is_hard_vetoed=False,
            gap_matrix=[
                GapItem(
                    requirement_name="技能-vLLM",
                    category="skill",
                    importance="must_have",
                    state=GapState.MATCHED,
                    score=1.0,
                    candidate_evidence="具备明确量化指标",
                    gap_explanation="高度匹配",
                    actionable_advice="准备深入架构细节",
                ),
                GapItem(
                    requirement_name="技能-DPO",
                    category="skill",
                    importance="must_have",
                    state=GapState.INSUFFICIENT_EVIDENCE,
                    score=0.5,
                    candidate_evidence="提及但无指标",
                    gap_explanation="缺少定量数据",
                    actionable_advice="依照STAR原则补齐数据",
                ),
            ],
            matched_count=1,
            insufficient_evidence_count=1,
        )

        self.redflags = RedFlagReport(
            flags=[
                RedFlagItem(
                    flag_type=RedFlagType.UNBOUNDED_OVERTIME,
                    title_cn="权责不清/无底线加班陷阱",
                    title_en="Extreme Overtime",
                    severity="MEDIUM",
                    trigger_snippet="抗压能力强",
                    risk_analysis="排期紧凑",
                    interview_defense="反问值班制度",
                )
            ],
            overall_risk_level="MODERATE",
            risk_score=20,
            summary="中等提示，需注意排期",
        )

        self.prediction = self.predictor.predict(self.jd, self.matcher, listing_age_days=12)

    def test_generate_html_content_and_bilingual_labels(self):
        """Verify HTML is self-contained and contains all required bilingual sections."""
        html = self.reporter.generate_html(
            self.jd, self.candidate, self.matcher, self.redflags, self.prediction
        )

        # Structure checks
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("</html>", html)

        # Bilingual headers checks
        self.assertIn("整体匹配度与通关判定", html)
        self.assertIn("/ Match Score & Gate", html)
        self.assertIn("五态差距分布矩阵", html)
        self.assertIn("/ 5-State Gap Radar", html)
        self.assertIn("执行摘要与战略建议", html)
        self.assertIn("/ Executive Summary (TL;DR)", html)
        self.assertIn("JD 五图层深度语义解码", html)
        self.assertIn("/ 5-Layer Semantic Blueprint", html)
        self.assertIn("五态差距细分矩阵与补齐方案", html)
        self.assertIn("/ 5-State Gap Matrix", html)
        self.assertIn("技术岗位红旗与陷阱探测", html)
        self.assertIn("/ Red Flags & Trap Radar", html)
        self.assertIn("拿面概率测算与投递渠道矩阵", html)
        self.assertIn("/ Interview Probability Forecast", html)
        self.assertIn("面试预测 Top 20 深度押题器", html)
        self.assertIn("/ Interview Prediction Top 20", html)
        self.assertIn("6 周通关冲刺行动计划", html)
        self.assertIn("/ 6-Week Strategic Action Plan", html)

        # SVG check
        self.assertIn("<svg", html)
        self.assertIn("circle", html)
        self.assertIn("stroke-dasharray", html)

        # Top 20 questions rendered
        self.assertIn("#1.", html)
        self.assertIn("#20.", html)

        # 6-Week Action Plan phases
        self.assertIn("第 1-2 周", html)
        self.assertIn("第 3-4 周", html)
        self.assertIn("第 5 周", html)
        self.assertIn("第 6 周", html)

    def test_save_report_to_disk(self):
        """Test saving report to actual file on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_offer_report.html")
            saved_path = self.reporter.save_report(
                file_path, self.jd, self.candidate, self.matcher, self.redflags, self.prediction
            )
            self.assertTrue(os.path.exists(saved_path))
            size = os.path.getsize(saved_path)
            self.assertGreater(size, 8000)

    def test_hard_vetoed_report_rendering(self):
        """Test that vetoed status renders the warning and breakthrough channel."""
        vetoed_matcher = MatcherResult(
            must_have_score=0.9,
            nice_to_have_score=0.9,
            hidden_signal_fit=0.9,
            raw_match_score=0.9,
            final_match_score=0.45,
            is_hard_vetoed=True,
            hard_veto_reasons=["学历门槛拦截：岗位硬性要求硕士，候选人为本科"],
            breakthrough_advice=["【学历破局通道】：顶会论文或开源代表作绕过初筛"],
        )
        html = self.reporter.generate_html(
            self.jd, self.candidate, vetoed_matcher, self.redflags, self.prediction
        )
        self.assertIn("一票否决拦截触发", html)
        self.assertIn("学历破局通道", html)

    def test_analyze_jd_pipeline(self):
        """Test the all-in-one analyze_jd high-level function."""
        jd_text = """
        职位：大模型预训练专家
        任职要求：计算机硕士，3年以上工作经验，精通 PyTorch、vLLM 和 NCCL。
        抗压能力强，负责从0到1搭建。
        """
        cand = CandidateProfile(
            education_level="硕士",
            years_of_experience=4.0,
            skills=["PyTorch", "vLLM"],
            project_descriptions=["基于 vLLM 部署，性能提升 2.5x。"],
        )
        output = analyze_jd(jd_text, candidate=cand, listing_age_days=10)

        self.assertIn("decoded_jd", output)
        self.assertIn("matcher_result", output)
        self.assertIn("redflag_report", output)
        self.assertIn("prediction_result", output)
        self.assertIn("html_report", output)
        self.assertTrue(len(output["html_report"]) > 5000)


if __name__ == "__main__":
    unittest.main()
