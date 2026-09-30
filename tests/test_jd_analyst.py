"""
Unit test suite for OfferGet JD Analyst modules (decoder, matcher, redflags, predictor, gap_roi).
Consolidated test suite covering the full 5-layer JD analysis pipeline.
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Ensure OfferGet root is in sys.path
OFFERGET_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if OFFERGET_ROOT not in sys.path:
    sys.path.insert(0, OFFERGET_ROOT)

from modules.jd_analyst.decoder import JDDecoder
from modules.jd_analyst.matcher import JDMatcher
from modules.jd_analyst.models import (
    BusinessPainPoint,
    CandidateProfile,
    ChannelType,
    CoreResponsibility,
    CoreSkill,
    DecodedJD,
    GapItem,
    GapState,
    HardThreshold,
    ImplicitSignal,
    MatcherResult,
    QuestionCategory,
    RedFlagItem,
    RedFlagReport,
    RedFlagType,
    SkillImportance,
    TechDomain,
)
from modules.jd_analyst.predictor import (
    InterviewProbabilityCalculator,
    InterviewTop20Predictor,
    JDPredictor,
)
from modules.jd_analyst.redflags import RedFlagDetector
from core.gap_roi import SkillGapROIEngine, calculate_gap_roi


# ============================================================================
# 1. JD Decoder Tests
# ============================================================================
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


# ============================================================================
# 2. JD Matcher Tests
# ============================================================================
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
            skills=["vLLM", "DeepSpeed", "FSDP"],
            project_descriptions=[
                "使用 vLLM 部署千亿模型，并发吞吐提升 3x，首字延迟降低 45%。",
                "使用 DeepSpeed 进行模型微调训练。",
                "参与 PyTorch FSDP 训练集群优化。",
            ],
        )

        result = self.matcher.match(jd, candidate)
        gap_map = {g.requirement_name: g for g in result.gap_matrix}

        self.assertEqual(gap_map["技能-vLLM"].score, 1.0)
        self.assertEqual(gap_map["技能-vLLM"].state, GapState.MATCHED)

        self.assertEqual(gap_map["技能-DeepSpeed"].score, 0.5)
        self.assertEqual(gap_map["技能-DeepSpeed"].state, GapState.INSUFFICIENT_EVIDENCE)

        self.assertEqual(gap_map["技能-Megatron-LM"].score, 0.5)
        self.assertEqual(gap_map["技能-Megatron-LM"].state, GapState.EXPRESSION_GAP)

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
            skills=["PyTorch", "vLLM", "DeepSpeed"],
            project_descriptions=[
                "vLLM 优化推理服务，吞吐提升 3x，降低延迟 40%。",
                "PyTorch 模型开发。",
                "DeepSpeed 分布式训练调优。",
                "具备通用算法与深度学习背景。",
            ],
            raw_resume_text="经历过紧急攻坚上线保障。",
        )

        result = self.matcher.match(jd, candidate)

        states_present = {g.state for g in result.gap_matrix}
        self.assertIn(GapState.MATCHED, states_present)
        self.assertIn(GapState.EXPRESSION_GAP, states_present)
        self.assertIn(GapState.INSUFFICIENT_EVIDENCE, states_present)
        self.assertIn(GapState.REAL_GAP, states_present)

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


# ============================================================================
# 3. Red Flags Detector Tests
# ============================================================================
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


# ============================================================================
# 4. Predictor Tests (Probability & Top 20 Questions)
# ============================================================================
class TestPredictor(unittest.TestCase):

    def setUp(self):
        self.calc = InterviewProbabilityCalculator()
        self.top20 = InterviewTop20Predictor()
        self.pipeline = JDPredictor()

    def test_probability_calculation_channels(self):
        """Test channel multiplier differences (Internal referral vs Cold application)."""
        matcher_high = MatcherResult(
            must_have_score=1.0,
            nice_to_have_score=1.0,
            hidden_signal_fit=0.8,
            raw_match_score=0.96,
            final_match_score=0.90,
            is_hard_vetoed=False,
        )

        forecast = self.calc.calculate(matcher_high, listing_age_days=10)
        self.assertEqual(forecast.base_min_prob, 60.0)
        self.assertEqual(forecast.base_max_prob, 85.0)
        self.assertEqual(forecast.age_decay_multiplier, 1.0)
        self.assertFalse(forecast.is_ghost_job_risk)

        channels = forecast.channel_forecasts
        internal = channels[ChannelType.INTERNAL_REFERRAL.value]
        cold = channels[ChannelType.COLD_APPLICATION.value]
        recruiter = channels[ChannelType.RECRUITER_DIRECT.value]

        self.assertGreater(internal.min_prob, 80.0)
        self.assertLessEqual(internal.max_prob, 96.0)
        self.assertAlmostEqual(cold.min_prob, 18.0, delta=1.0)
        self.assertAlmostEqual(cold.max_prob, 25.5, delta=1.0)
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

        # Fresh job (5 days)
        fc_fresh = self.calc.calculate(matcher_mid, listing_age_days=5)
        self.assertEqual(fc_fresh.age_decay_multiplier, 1.1)
        self.assertFalse(fc_fresh.is_ghost_job_risk)

        # Ghost job (75 days)
        fc_ghost = self.calc.calculate(matcher_mid, listing_age_days=75)
        self.assertEqual(fc_ghost.age_decay_multiplier, 0.4)
        self.assertTrue(fc_ghost.is_ghost_job_risk)
        self.assertIn("幽灵职位", fc_ghost.strategic_summary)

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
        self.assertEqual(len(questions), 20)

        arch_qs = [q for q in questions if q.category_type == QuestionCategory.ARCHITECTURE]
        princ_qs = [q for q in questions if q.category_type == QuestionCategory.PRINCIPLES]
        bq_qs = [q for q in questions if q.category_type == QuestionCategory.BQ]
        rev_qs = [q for q in questions if q.category_type == QuestionCategory.REVERSE]

        self.assertEqual(len(arch_qs), 5)
        self.assertEqual(len(princ_qs), 5)
        self.assertEqual(len(bq_qs), 5)
        self.assertEqual(len(rev_qs), 5)

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


# ============================================================================
# 5. Skill Gap ROI Engine Tests
# ============================================================================
class TestSkillGapROIEngine(unittest.TestCase):

    def setUp(self):
        project_root = Path(OFFERGET_ROOT)
        self.sample_profile_path = project_root / "examples" / "candidate_profile.json"
        self.sample_jd_path = project_root / "examples" / "sample_ai_jd.txt"

        with open(self.sample_profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        with open(self.sample_jd_path, "r", encoding="utf-8") as f:
            self.jd_text = f.read()

        self.engine = SkillGapROIEngine()

    def test_01_analyze_gap_roi_structure(self):
        result = self.engine.analyze_gap_roi(self.profile_data, [self.jd_text])
        self.assertIn("total_near_miss_jobs", result)
        self.assertIn("missing_skills_ranking", result)
        self.assertIn("top_recommendations", result)
        self.assertIn("strategic_summary", result)
        self.assertIn("assumptions", result)
        self.assertIn("unknown_fields", result)
        self.assertIn("evidence_status", result)
        self.assertIsInstance(result["total_near_miss_jobs"], int)
        self.assertIsInstance(result["missing_skills_ranking"], list)
        self.assertIsInstance(result["top_recommendations"], list)
        self.assertIsInstance(result["strategic_summary"], str)
        self.assertLessEqual(len(result["top_recommendations"]), 5)

        if result["missing_skills_ranking"]:
            first = result["missing_skills_ranking"][0]
            required_keys = [
                "skill",
                "frequency_in_near_miss",
                "jobs_unlocked_estimate",
                "difficulty",
                "rampup_estimate",
                "roi_score",
                "actionable_plan",
            ]
            for k in required_keys:
                self.assertIn(k, first)
            self.assertIn(first["difficulty"], ("Low", "Medium", "High"))
            self.assertGreater(first["roi_score"], 0.0)

    def test_02_convenience_function(self):
        result = calculate_gap_roi(self.profile_data, [str(self.sample_jd_path)])
        self.assertIn("total_near_miss_jobs", result)
        self.assertIn("top_recommendations", result)
        self.assertGreaterEqual(len(result["top_recommendations"]), 1)

    def test_03_roi_formula_ordering(self):
        result = self.engine.analyze_gap_roi(self.profile_data, [self.jd_text])
        ranking = result["missing_skills_ranking"]
        if len(ranking) >= 2:
            for i in range(len(ranking) - 1):
                self.assertGreaterEqual(ranking[i]["roi_score"], ranking[i + 1]["roi_score"])

    def test_04_multiple_jds(self):
        jd_2 = """
        【岗位名称】大模型推理部署架构师
        【所属部门】AI工程部
        【薪资范围】120W - 180W
        【任职要求】
        1. 精通 vLLM 与 PagedAttention，具备 C++/CUDA 算子开发经验；
        2. 熟悉 FP8 量化与 Speculative Decoding 投机采样；
        3. 熟练掌握 SGLang 与 RadixAttention，具备高并发线上服务保障经验。
        """
        result = self.engine.analyze_gap_roi(self.profile_data, [self.jd_text, jd_2])
        self.assertGreaterEqual(result["total_near_miss_jobs"], 1)
        self.assertTrue(len(result["strategic_summary"]) > 50)

    def test_05_unknown_facts_boundary_and_assumptions(self):
        minimal_profile = {"name": "未知候选人", "skills": ["Python"]}
        result = self.engine.analyze_gap_roi(minimal_profile, [self.jd_text])
        self.assertIn("unknown_fields", result)
        self.assertIn("education", result["unknown_fields"])
        self.assertIn("years_of_experience", result["unknown_fields"])
        self.assertIn("major", result["unknown_fields"])
        self.assertEqual(result["evidence_status"], "partial")
        self.assertTrue(result["input_quality"]["unknown_experience"])
        self.assertTrue(result["input_quality"]["unknown_education"])
        self.assertTrue(result["input_quality"]["unknown_major"])
        self.assertGreaterEqual(len(result["assumptions"]), 3)


if __name__ == "__main__":
    unittest.main()
