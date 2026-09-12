"""
Unit tests for JD Decoder module.
"""

import unittest
import os
import sys

# Ensure OfferGet root is in sys.path
OFFERGET_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if OFFERGET_ROOT not in sys.path:
    sys.path.insert(0, OFFERGET_ROOT)

from modules.jd_analyst.decoder import JDDecoder
from modules.jd_analyst.models import (
    DecodedJD,
    HardThreshold,
    SkillImportance,
    TechDomain,
)


class TestJDDecoder(unittest.TestCase):

    def setUp(self):
        self.decoder = JDDecoder()

    def test_decode_5_layers(self):
        sample_jd = """
        职位：资深大模型算法专家
        部门：AI基础模型研发部

        【岗位职责】
        1. 负责百亿/千亿参数规模大模型的预训练与持续预训练，优化分布式训练通信效率。
        2. 负责构建基于 RLHF 与 DPO 的对齐微调流水线，提升大模型在垂直领域的指令遵循与问答准确率。
        3. 负责大模型高性能推理引擎架构搭建，通过 vLLM 与 TensorRT-LLM 优化 P99 时延与吞吐。

        【任职要求】
        1. 统招硕士及以上学历，计算机、软件工程或人工智能相关专业。
        2. 3年以上大模型或深度学习算法研发经验，精通 Python 和 PyTorch。
        3. 深入理解 3D并行 (TP/PP/DP)、Megatron-LM 与 DeepSpeed ZeRO 架构。
        4. 熟练掌握 FlashAttention-2、PagedAttention 以及 AWQ 量化技术。
        5. 具备极强的主观能动性与抗压能力强，能适应快速变化，具有从0到1搭建系统的经验。

        【加分项】
        1. 在 NeurIPS/ICML/ICLR 等顶会有高质量论文者优先。
        2. 具备 NCCL 算子优化或 Triton/CUDA 编写经验者优先。

        【福利待遇】
        五险一金，定期体检，免费零食下午茶，业界领先的薪酬福利待遇。
        """

        decoded: DecodedJD = self.decoder.decode(sample_jd)

        # Basic metadata
        self.assertEqual(decoded.job_title, "资深大模型算法专家")
        self.assertEqual(decoded.company_or_dept, "AI基础模型研发部")

        # Layer 1: Hard Thresholds
        threshold_categories = [t.category for t in decoded.hard_thresholds]
        self.assertIn("education", threshold_categories)
        self.assertIn("experience_years", threshold_categories)
        edu_th = next(t for t in decoded.hard_thresholds if t.category == "education")
        self.assertEqual(edu_th.min_degree, "硕士")
        exp_th = next(t for t in decoded.hard_thresholds if t.category == "experience_years")
        self.assertEqual(exp_th.min_years, 3.0)

        # Layer 2: Core Responsibilities
        self.assertGreaterEqual(len(decoded.core_responsibilities), 2)
        resp_text = " ".join([r.description for r in decoded.core_responsibilities])
        self.assertTrue("预训练" in resp_text or "对齐" in resp_text or "推理" in resp_text)

        # Layer 3: Core Skills
        skill_names = [s.name.lower() for s in decoded.core_skills]
        self.assertIn("pytorch", skill_names)
        self.assertIn("python", skill_names)
        self.assertIn("vllm", skill_names)
        self.assertIn("megatron-lm", skill_names)
        self.assertIn("deepspeed", skill_names)
        self.assertIn("dpo", skill_names)
        self.assertIn("rlhf", skill_names)

        # Nice to have recognition
        nccl_skill = next((s for s in decoded.core_skills if s.name.lower() == "nccl"), None)
        if nccl_skill:
            self.assertEqual(nccl_skill.importance, SkillImportance.NICE_TO_HAVE.value)

        # Layer 4: Implicit Signals & Jargon
        self.assertGreaterEqual(len(decoded.implicit_signals), 3)
        signal_texts = [s.original_text for s in decoded.implicit_signals]
        self.assertTrue(any("抗压" in t for t in signal_texts))
        self.assertTrue(any("主观能动性" in t or "自驱" in t for t in signal_texts))
        self.assertTrue(any("0到1" in t for t in signal_texts))
        self.assertTrue(any("变化" in t for t in signal_texts))

        # Check subtext translation
        press_sig = next(s for s in decoded.implicit_signals if "抗压" in s.original_text)
        self.assertIn("加班", press_sig.translated_meaning)

        # Layer 5: Business Pain Points & KPIs
        self.assertGreaterEqual(len(decoded.business_pain_points), 1)
        pain_aspects = [p.aspect for p in decoded.business_pain_points]
        self.assertTrue(any("推理成本" in a or "时延" in a or "对齐" in a or "集群" in a for a in pain_aspects))

        # PR Boilerplate Filtering
        self.assertGreaterEqual(len(decoded.filtered_boilerplates), 2)
        filtered_text = " ".join([b.text for b in decoded.filtered_boilerplates])
        self.assertIn("五险一金", filtered_text)
        self.assertIn("免费零食下午茶", filtered_text)
        self.assertNotIn("免费零食下午茶", decoded.clean_text)

    def test_ai_llm_domain_specialization(self):
        """Verify specialized detection for AI/LLM domain areas."""
        jd_text = """
        【大模型 Agent 与算力基建工程师】
        职责：
        1. 优化万卡 GPU 集群与 InfiniBand RoCE 网络，搭建 Slurm 作业调度与 Ray 分布式计算。
        2. 基于 Megatron-LM 实现 TP/PP/DP/EP 3D 并行，开发 ZeRO-3 显存优化与流水线气泡抑制。
        3. 推进 1M 超长文本长上下文技术，使用 RoPE scaling、YaRN 以及 RingAttention 算子。
        4. 基于 Speculative Decoding (投机采样) 和 Continuous Batching 加速线上推理。
        5. 设计 ReAct 架构与 Multi-Agent 工具调用 (Function Calling)，支持 MCP 协议与 GraphRAG。
        """

        decoded = self.decoder.decode(jd_text)
        skill_names = [s.name.lower() for s in decoded.core_skills]

        # Check domain coverage
        self.assertIn("infiniband", skill_names)
        self.assertIn("roce", skill_names)
        self.assertIn("slurm", skill_names)
        self.assertIn("ray", skill_names)
        self.assertIn("rope", skill_names)
        self.assertIn("yarn", skill_names)
        self.assertIn("ringattention", skill_names)
        self.assertIn("speculative decoding", skill_names)
        self.assertIn("continuous batching", skill_names)
        self.assertIn("react", skill_names)
        self.assertIn("multi-agent", skill_names)
        self.assertIn("mcp", skill_names)

        # Check tech domains identified
        self.assertIn(TechDomain.COMPUTE_INFRA.value, decoded.tech_domains)
        self.assertIn(TechDomain.TRAINING_COMM.value, decoded.tech_domains)
        self.assertIn(TechDomain.LONG_CONTEXT.value, decoded.tech_domains)
        self.assertIn(TechDomain.INFERENCE_ACCEL.value, decoded.tech_domains)
        self.assertIn(TechDomain.AGENT_WORKFLOW.value, decoded.tech_domains)

    def test_pr_boilerplate_filtering(self):
        jd_with_fluff = """
        职位：算法工程师
        我们提供业界领先的薪酬福利待遇
        五险一金、带薪年假、年度健康体检
        与充满激情的小伙伴一同成长，大牛带队
        广阔的职业发展空间，提供免费零食下午茶
        引领未来变革，推动人工智能革命
        任职要求：计算机本科，熟练 Python
        """
        clean_text, filtered = self.decoder._filter_boilerplates(jd_with_fluff)
        self.assertGreaterEqual(len(filtered), 5)
        self.assertNotIn("薪酬福利待遇", clean_text)
        self.assertNotIn("免费零食下午茶", clean_text)
        self.assertIn("任职要求", clean_text)

    def test_edge_cases(self):
        # Empty input
        empty_res = self.decoder.decode("")
        self.assertEqual(empty_res.raw_text, "")
        self.assertEqual(len(empty_res.hard_thresholds), 0)

        # Minimal input
        mini_res = self.decoder.decode("Python算法工程师，本科，3年经验")
        self.assertEqual(len(mini_res.hard_thresholds), 2)
        self.assertTrue(any(t.min_degree == "本科" for t in mini_res.hard_thresholds))
        self.assertTrue(any(t.min_years == 3.0 for t in mini_res.hard_thresholds))


if __name__ == "__main__":
    unittest.main()
