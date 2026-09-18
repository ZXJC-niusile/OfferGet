"""
Unit tests for OfferGet Report Generator (tests/test_report_generator.py).
Focuses on report generation, XSS security escaping, dual-track consistency,
bilingual twin validation, SVG dashboards, and fallback handling.
"""

import os
import re
import sys
import tempfile
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.report_generator import generate_report
from core.security_gate import validate_output_security
from core.validator import validate_bilingual_html
from modules.jd_analyst.models import (
    BusinessPainPoint,
    CoreResponsibility,
    CoreSkill,
    DecodedJD,
    HardThreshold,
    ImplicitSignal,
)


class TestReportGenerator(unittest.TestCase):
    """Test suite for core.report_generator."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.template_path = str(PROJECT_ROOT / "templates" / "offer_strategy.html")

        self.sample_decoded_jd = {
            "metadata": {
                "company": "DeepTech AI",
                "role": "大模型系统架构师",
                "department": "推理与算力集群组",
                "level": "P8 / Staff",
                "location": "北京 / 深圳",
                "comp_band": "60k-90k · 16薪",
                "architecture_layer": "AI 基础设施与推理引擎",
            },
            "layers": {
                "layer_1": {
                    "jd_text_zh": "负责大模型分布式推理系统架构演进。",
                    "jd_text_en": "Lead LLM distributed inference architecture.",
                    "reality_zh": "真实业务线当前正面临千卡集群吞吐瓶颈。",
                    "reality_en": "Business faces throughput bottleneck on 1000-GPU cluster.",
                },
                "layer_2": {
                    "jd_text_zh": "精通 vLLM、TensorRT-LLM 与 CUDA 核心算子优化。",
                    "jd_text_en": "Proficient in vLLM, TensorRT-LLM, and CUDA optimization.",
                    "reality_zh": "核心看重算子定制与连续批处理调度能力。",
                    "reality_en": "Values custom kernel optimization and continuous batching.",
                },
                "layer_3": {
                    "jd_text_zh": "优化 P99 延迟至 200ms 以内。",
                    "jd_text_en": "Optimize P99 latency within 200ms.",
                    "reality_zh": "SLA 要求极高。",
                    "reality_en": "High SLA constraints.",
                },
                "layer_4": {
                    "jd_text_zh": "抗压能力强，有强烈的 Owner 意识。",
                    "jd_text_en": "High stress tolerance and ownership.",
                    "reality_zh": "存在版本冲刺加班。",
                    "reality_en": "Overtime expected during major milestones.",
                },
                "layer_5": {
                    "jd_text_zh": "算力成本高昂，需推行极致量化与显存压缩。",
                    "jd_text_en": "High compute cost; extreme quantization required.",
                    "reality_zh": "需推进 FP8/AWQ 量化方案落地。",
                    "reality_en": "Requires FP8/AWQ quantization in production.",
                },
            },
        }

        self.sample_match_result = {
            "candidate_name": "张无忌",
            "overall_match_score": 88.0,
            "interview_prob": 82.0,
            "breakdown": {
                "must_have": 90,
                "nice_have": 85,
                "hidden_fit": 80,
            },
            "verdict": {
                "title_zh": "建议在证据复核后投递",
                "title_en": "Strong Fit (Review Before Applying)",
                "desc_zh": "候选人材料与高并发推理要求高度匹配，建议直接投递。",
                "desc_en": "Profile aligns closely with core requirements.",
            },
        }

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_generate_report_basic(self):
        out_file = os.path.join(self.tmp_dir.name, "basic_report.html")
        result_path = generate_report(
            decoded_jd=self.sample_decoded_jd,
            match_result=self.sample_match_result,
            template_path=self.template_path,
            output_path=out_file,
        )

        self.assertTrue(os.path.exists(result_path))
        content = open(result_path, encoding="utf-8").read()
        self.assertIn("DeepTech AI", content)
        self.assertIn("大模型系统架构师", content)
        self.assertIn("张无忌", content)
        self.assertIn("88", content)
        self.assertIn("82", content)
        self.assertIn("建议在证据复核后投递", content)

        # Check no unreplaced placeholders
        self.assertNotIn("{{COMPANY}}", content)
        self.assertNotIn("{{MATCH_SCORE_NUM}}", content)
        placeholders = re.findall(r"\{\{[A-Z0-9_]+\}\}", content)
        self.assertEqual(placeholders, [], f"Unreplaced placeholders found: {placeholders}")

        # Bilingual twin validation check
        bilingual_res = validate_bilingual_html(result_path)
        self.assertTrue(bilingual_res["passed"], f"Bilingual validation failed: {bilingual_res['errors']}")
        self.assertGreaterEqual(bilingual_res["en_count"], 80)
        self.assertEqual(bilingual_res["en_count"], bilingual_res["zh_count"])

        # Security validation check
        sec_risks = validate_output_security(content, format_type="html")
        self.assertEqual(sec_risks, [], f"Security gate detected risks: {sec_risks}")

        # SVG dashboard check
        self.assertIn("<svg", content)
        self.assertIn("circle", content)
        self.assertIn("stroke-dasharray", content)

    def test_xss_protection(self):
        malicious_jd = {
            "metadata": {
                "company": "EvilCorp <script>alert('pwn_comp')</script>",
                "role": 'Hacker" onmouseover="alert(\'pwn_role\')',
                "department": "Security <iframe src='http://evil.com'>",
            },
            "layers": {
                "layer_1": {
                    "jd_text_zh": "Test <script>alert(1)</script>",
                    "jd_text_en": "Test <img src=x onerror=alert(1)>",
                    "reality_zh": "Reality <script>",
                    "reality_en": "Reality <iframe>",
                }
            },
        }
        malicious_match = {
            "candidate_name": "<script>alert('pwn_name')</script>",
            "overall_match_score": 70,
            "interview_prob": 65,
            "verdict": {
                "title_zh": "Verdict <script>alert('verdict')</script>",
                "desc_zh": "Desc <img src=x onerror=alert('desc')>",
            },
        }

        out_file = os.path.join(self.tmp_dir.name, "xss_test_report.html")
        result_path = generate_report(
            decoded_jd=malicious_jd,
            match_result=malicious_match,
            template_path=self.template_path,
            output_path=out_file,
        )

        content = open(result_path, encoding="utf-8").read()

        # None of the injected script tags should exist in raw unescaped form
        self.assertNotIn("<script>alert('pwn_comp')</script>", content)
        self.assertNotIn("<script>alert('pwn_name')</script>", content)
        self.assertNotIn("<script>alert('verdict')</script>", content)
        self.assertNotIn("<iframe src='http://evil.com'>", content)
        self.assertNotIn("<img src=x onerror=alert(1)>", content)

        # Escaped versions MUST be present safely
        self.assertIn("&lt;script&gt;alert(&#x27;pwn_comp&#x27;)&lt;/script&gt;", content)
        self.assertIn("&lt;script&gt;alert(&#x27;pwn_name&#x27;)&lt;/script&gt;", content)

        # Security gate should report 0 risks
        sec_risks = validate_output_security(content, format_type="html")
        self.assertEqual(sec_risks, [], f"Security gate found risks in XSS output: {sec_risks}")

    def test_dual_track_consistency_hard_veto(self):
        vetoed_match = {
            "candidate_name": "王小二",
            "overall_match_score": 45.0,
            "interview_prob": 20.0,
            "hard_vetoed": True,
        }

        out_file = os.path.join(self.tmp_dir.name, "veto_report.html")
        result_path = generate_report(
            decoded_jd=self.sample_decoded_jd,
            match_result=vetoed_match,
            template_path=self.template_path,
            output_path=out_file,
        )

        content = open(result_path, encoding="utf-8").read()
        self.assertIn("硬门槛未通过，需人工复核", content)
        self.assertIn("Hard Threshold Vetoed", content)

    def test_dual_track_consistency_normalized_float_scores(self):
        normalized_match = {
            "candidate_name": "赵六",
            "final_match_score": 0.92,
            "interview_prob": 0.85,
            "breakdown": {
                "must_have": 0.95,
                "nice_have": 0.88,
                "hidden_fit": 0.90,
            },
        }

        out_file = os.path.join(self.tmp_dir.name, "norm_scores_report.html")
        result_path = generate_report(
            decoded_jd=self.sample_decoded_jd,
            match_result=normalized_match,
            template_path=self.template_path,
            output_path=out_file,
        )

        content = open(result_path, encoding="utf-8").read()
        self.assertIn("92", content)
        self.assertIn("85", content)
        self.assertIn("建议在证据复核后投递", content)

    def test_canonical_decoded_jd_object_support(self):
        canonical_jd = DecodedJD(
            raw_text="岗位：具身智能具象算法专家\n公司：智元具身机器人\n要求：精通强化学习与动力学控制。",
            job_title="具身智能算法专家",
            company_or_dept="智元具身机器人",
            hard_thresholds=[HardThreshold(category="degree", requirement="硕士及以上", is_mandatory=True)],
            core_skills=[CoreSkill(name="强化学习", category="algo", importance="must_have", domain="RL")],
            core_responsibilities=[CoreResponsibility(title="步态控制", description="主导双足步态控制算法研发", domain="机器人控制")],
            implicit_signals=[ImplicitSignal(original_text="抗压强", translated_meaning="需加班攻坚", underlying_risk="负荷重", candidate_countermeasure="确认排期")],
            business_pain_points=[BusinessPainPoint(aspect="步态失稳", description="复杂地形失稳率需低于 1%", evaluation_metric="失稳率 < 1%")],
        )

        out_file = os.path.join(self.tmp_dir.name, "canonical_jd_report.html")
        result_path = generate_report(
            decoded_jd=canonical_jd,
            match_result=self.sample_match_result,
            template_path=self.template_path,
            output_path=out_file,
        )

        self.assertTrue(os.path.exists(result_path))
        content = open(result_path, encoding="utf-8").read()
        self.assertIn("具身智能算法专家", content)
        self.assertIn("智元具身机器人", content)

    def test_bilingual_twin_parity_and_svg_dashboards(self):
        out_file = os.path.join(self.tmp_dir.name, "twin_parity_report.html")
        result_path = generate_report(
            decoded_jd=self.sample_decoded_jd,
            match_result=self.sample_match_result,
            template_path="",
            output_path=out_file,
        )

        content = open(result_path, encoding="utf-8").read()

        # Check required bilingual sections
        self.assertIn("整体匹配度与通关判定", content)
        self.assertIn("/ Match Score & Gate", content)
        self.assertIn("五态差距分布矩阵", content)
        self.assertIn("/ 5-State Gap Radar", content)
        self.assertIn("执行摘要与战略建议", content)
        self.assertIn("/ Executive Summary (TL;DR)", content)
        self.assertIn("JD 五图层深度语义解码", content)
        self.assertIn("/ 5-Layer Semantic Blueprint", content)
        self.assertIn("五态差距细分矩阵与补齐方案", content)
        self.assertIn("/ 5-State Gap Matrix", content)
        self.assertIn("技术岗位红旗与陷阱探测", content)
        self.assertIn("/ Red Flags & Trap Radar", content)
        self.assertIn("拿面概率测算与投递渠道矩阵", content)
        self.assertIn("/ Interview Probability Forecast", content)
        self.assertIn("面试预测 Top 20 深度押题器", content)
        self.assertIn("/ Interview Prediction Top 20", content)
        self.assertIn("6 周通关冲刺行动计划", content)
        self.assertIn("/ 6-Week Strategic Action Plan", content)

        # SVG elements
        self.assertIn("<svg", content)
        self.assertIn("<circle", content)
        self.assertIn("<rect", content)

        # Validation gate audits
        bilingual = validate_bilingual_html(result_path)
        self.assertTrue(bilingual["passed"])
        self.assertGreaterEqual(bilingual["en_count"], 80)
        self.assertEqual(bilingual["en_count"], bilingual["zh_count"])

        security_risks = validate_output_security(content, "html")
        self.assertEqual(security_risks, [])

    def test_custom_template_fallback(self):
        # Create a custom non-default template
        custom_tpl_path = os.path.join(self.tmp_dir.name, "custom_strategy.html")
        custom_tpl_content = """<!DOCTYPE html>
<html>
<head><title>Custom Report</title></head>
<body>
<h1>Custom Report for {{COMPANY}} - {{ROLE}}</h1>
<p>Candidate: {{CANDIDATE_NAME}}</p>
<p>Match Score: {{MATCH_SCORE_NUM}}%</p>
<p>Probability: {{INTERVIEW_PROB_NUM}}%</p>
<p>Verdict: {{VERDICT_TITLE_ZH}} ({{VERDICT_TITLE_EN}})</p>
<p>Must: {{MUST_HAVE_SCORE}}, Nice: {{NICE_HAVE_SCORE}}, Hidden: {{HIDDEN_FIT_SCORE}}</p>
<p>L1: {{L1_JD_TEXT_ZH}} - {{L1_REALITY_ZH}}</p>
<p>L2: {{L2_JD_TEXT_ZH}} - {{L2_REALITY_ZH}}</p>
<p>L3: {{L3_JD_TEXT_ZH}} - {{L3_REALITY_ZH}}</p>
<p>L4: {{L4_JD_TEXT_ZH}} - {{L4_REALITY_ZH}}</p>
<p>L5: {{L5_JD_TEXT_ZH}} - {{L5_REALITY_ZH}}</p>
<div>Date: {{REPORT_DATE}}</div>
<div>Level: {{LEVEL}}, Band: {{COMP_BAND}}, Loc: {{LOCATION}}, Dept: {{DEPARTMENT}}, Arch: {{ARCHITECTURE_LAYER}}</div>
<div>Verdict Desc: {{VERDICT_DESC_ZH}} - {{VERDICT_DESC_EN}}</div>
<div>L1 EN: {{L1_JD_TEXT_EN}} - {{L1_REALITY_EN}}</div>
<div>L2 EN: {{L2_JD_TEXT_EN}} - {{L2_REALITY_EN}}</div>
<div>L3 EN: {{L3_JD_TEXT_EN}} - {{L3_REALITY_EN}}</div>
<div>L4 EN: {{L4_JD_TEXT_EN}} - {{L4_REALITY_EN}}</div>
<div>L5 EN: {{L5_JD_TEXT_EN}} - {{L5_REALITY_EN}}</div>
</body>
</html>"""
        with open(custom_tpl_path, "w", encoding="utf-8") as f:
            f.write(custom_tpl_content)

        out_file = os.path.join(self.tmp_dir.name, "custom_report_out.html")
        result_path = generate_report(
            decoded_jd=self.sample_decoded_jd,
            match_result=self.sample_match_result,
            template_path=custom_tpl_path,
            output_path=out_file,
        )

        self.assertTrue(os.path.exists(result_path))
        content = open(result_path, encoding="utf-8").read()
        self.assertIn("Custom Report for DeepTech AI - 大模型系统架构师", content)
        self.assertIn("Candidate: 张无忌", content)
        self.assertIn("Match Score: 88%", content)
        self.assertNotIn("{{COMPANY}}", content)


if __name__ == "__main__":
    unittest.main()
