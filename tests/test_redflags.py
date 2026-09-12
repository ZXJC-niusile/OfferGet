"""
Unit tests for Red Flags & Career Traps Detector module.
"""

import unittest
import os
import sys

# Ensure OfferGet root is in sys.path
OFFERGET_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if OFFERGET_ROOT not in sys.path:
    sys.path.insert(0, OFFERGET_ROOT)

from modules.jd_analyst.models import DecodedJD, RedFlagType
from modules.jd_analyst.redflags import RedFlagDetector


class TestRedFlagDetector(unittest.TestCase):

    def setUp(self):
        self.detector = RedFlagDetector()

    def test_detect_one_man_fullstack(self):
        jd = DecodedJD(
            raw_text="""
            招聘：全栈大模型开发工程师
            职责：一人负责端到端全流程上线，包含大模型算法训练、数据清洗、后端Java接口以及Vue前端页面开发，并负责K8s运维。
            """,
            job_title="全栈大模型开发",
            company_or_dept="初创团队",
        )
        report = self.detector.detect(jd)
        flag_types = [f.flag_type for f in report.flags]
        self.assertIn(RedFlagType.ONE_MAN_FULLSTACK, flag_types)
        fullstack_flag = next(f for f in report.flags if f.flag_type == RedFlagType.ONE_MAN_FULLSTACK)
        self.assertEqual(fullstack_flag.severity, "HIGH")
        self.assertIn("反问", fullstack_flag.interview_defense)

    def test_detect_compute_shortage(self):
        jd = DecodedJD(
            raw_text="""
            招聘大模型预训练专家，负责千亿模型自研。
            目前实验室配备几张4090消费级显卡，按需申请公有云单卡进行实验。
            """,
            job_title="大模型预训练专家",
            company_or_dept="实验室",
        )
        report = self.detector.detect(jd)
        flag_types = [f.flag_type for f in report.flags]
        self.assertIn(RedFlagType.COMPUTE_SHORTAGE, flag_types)

    def test_detect_department_disconnect(self):
        jd = DecodedJD(
            raw_text="""
            职位：前沿探索小组大模型研究员
            属于集团创新实验室，不考核短期营收，负责纯学术通用大模型预研。
            """,
            job_title="研究员",
            company_or_dept="创新实验室",
        )
        report = self.detector.detect(jd)
        flag_types = [f.flag_type for f in report.flags]
        self.assertIn(RedFlagType.DEPARTMENT_DISCONNECT, flag_types)

    def test_detect_infinite_equity_pie(self):
        jd = DecodedJD(
            raw_text="""
            早期合伙人招募：提供极具诱惑力的期权池，薪资可灵活按期权调整，期权代替现金，期望具备不计得失的创业精神。
            """,
            job_title="算法合伙人",
            company_or_dept="早期项目",
        )
        report = self.detector.detect(jd)
        flag_types = [f.flag_type for f in report.flags]
        self.assertIn(RedFlagType.INFINITE_EQUITY_PIE, flag_types)

    def test_detect_pseudo_llm_wrapper(self):
        jd = DecodedJD(
            raw_text="""
            职位：AI超级应用架构师
            职责：熟练调用三方API与OpenAI接口，熟练编写Prompt工程，基于已有开源工具简单封装交付客户。
            """,
            job_title="AI架构师",
            company_or_dept="外包方案部",
        )
        report = self.detector.detect(jd)
        flag_types = [f.flag_type for f in report.flags]
        self.assertIn(RedFlagType.PSEUDO_LLM_WRAPPER, flag_types)

    def test_detect_architecture_regression(self):
        jd = DecodedJD(
            raw_text="""
            职位：底层引擎研发
            要求：坚持自主研发底层框架，从底层重写PyTorch，不依赖现有成熟开源生态，开发纯自研矩阵运算库。
            """,
            job_title="底座研发",
            company_or_dept="基础平台",
        )
        report = self.detector.detect(jd)
        flag_types = [f.flag_type for f in report.flags]
        self.assertIn(RedFlagType.ARCHITECTURE_REGRESSION, flag_types)

    def test_detect_unbounded_overtime(self):
        jd = DecodedJD(
            raw_text="""
            任职要求：抗压能力极强，24小时响应业务召唤，工作生活融为一体，狼性文化，全天候待命。
            """,
            job_title="算法工程师",
            company_or_dept="核心商业化",
        )
        report = self.detector.detect(jd)
        flag_types = [f.flag_type for f in report.flags]
        self.assertIn(RedFlagType.UNBOUNDED_OVERTIME, flag_types)

    def test_clean_jd_no_redflags(self):
        """A professional well-scoped JD should have 0 red flags."""
        clean_jd = DecodedJD(
            raw_text="""
            职位：大模型推理优化工程师
            部门：云基础设施研发中心
            职责：负责 vLLM 与 TensorRT-LLM 高性能推理引擎优化，优化 GPU 显存与 P99 延迟。
            任职要求：计算机专业硕士，精通 C++ 和 Python，深入理解 CUDA 算子优化与 PagedAttention 机制。
            """,
            job_title="大模型推理优化工程师",
            company_or_dept="云基础设施研发中心",
        )
        report = self.detector.detect(clean_jd)
        self.assertEqual(len(report.flags), 0)
        self.assertEqual(report.overall_risk_level, "LOW")
        self.assertEqual(report.risk_score, 0)
        self.assertIn("未检测到明显的岗位红旗", report.summary)

    def test_severe_multi_flag_scoring(self):
        """Multiple high severity flags should result in SEVERE risk level."""
        terrible_jd = DecodedJD(
            raw_text="""
            职位：全栈算法合伙人
            要求一人负责端到端全流程上线，包含前端Vue开发、后端开发、算法训练与K8s运维。
            几张4090消费级显卡，极具诱惑力的期权池与早期合伙人期权代替现金，抗压能力极强，24小时响应。
            """,
            job_title="全栈算法合伙人",
            company_or_dept="黑作坊",
        )
        report = self.detector.detect(terrible_jd)
        self.assertGreaterEqual(len(report.flags), 3)
        self.assertGreaterEqual(report.risk_score, 60)
        self.assertEqual(report.overall_risk_level, "SEVERE")


if __name__ == "__main__":
    unittest.main()
