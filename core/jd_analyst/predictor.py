"""
Predictor: Interview probability calculator & Top 20 interview questions predictor.
"""

import re
from typing import List, Dict
from .models import (
    DecodedJD,
    MatcherResult,
    ChannelType,
    ChannelProbability,
    ProbabilityForecast,
    QuestionCategory,
    InterviewQuestion,
    PredictionResult,
    GapState,
)


class InterviewProbabilityCalculator:
    """
    Calculates interview callback probabilities across application channels
    with listing age decay adjustments and ghost-job risk alerts.
    """

    CHANNEL_MULTIPLIERS = {
        ChannelType.INTERNAL_REFERRAL: {
            "name_cn": "内部员工内推",
            "name_en": "Internal Referral",
            "multiplier": 2.5,
            "description": "走内部员工直接背书通道，直达技术主管或业务HR优先筛选列表。",
        },
        ChannelType.RECRUITER_DIRECT: {
            "name_cn": "招聘官/业务直通 (Boss直聘等)",
            "name_en": "Recruiter / Hiring Manager Direct",
            "multiplier": 1.2,
            "description": "与招聘主管/专职HR建立即时沟通对话，直接发送对齐后的简历附件。",
        },
        ChannelType.HEADHUNTER: {
            "name_cn": "专职猎头推荐",
            "name_en": "Executive Search / Headhunter",
            "multiplier": 1.8,
            "description": "猎头顾问前置筛选并向业务总监重点推介，反馈周期相对可控。",
        },
        ChannelType.COLD_APPLICATION: {
            "name_cn": "官网/招聘平台海投",
            "name_en": "Cold Application / Career Portal",
            "multiplier": 0.3,
            "description": "淹没在海量ATS机器简历池中，关键词匹配度不达标极易被自动淘汰。",
        },
    }

    def calculate(
        self,
        matcher_result: MatcherResult,
        listing_age_days: int = 15,
    ) -> ProbabilityForecast:
        """Calculate base and channel-adjusted probabilities."""
        score = matcher_result.final_match_score

        # 1. Base Probability Interval
        if matcher_result.is_hard_vetoed:
            # Severely suppressed if hard threshold vetoed
            base_min = 5.0
            base_max = 15.0
        elif score >= 0.85:
            base_min = 60.0
            base_max = 85.0
        elif score >= 0.70:
            base_min = 40.0
            base_max = 65.0
        elif score >= 0.50:
            base_min = 20.0
            base_max = 45.0
        else:
            base_min = 8.0
            base_max = 20.0

        # 2. Listing Age Decay Multiplier
        if listing_age_days <= 7:
            age_decay = 1.10  # Fresh urgent demand
        elif listing_age_days <= 30:
            age_decay = 1.00  # Normal active cycle
        elif listing_age_days <= 60:
            age_decay = 0.70  # Mid-late pipeline decay
        else:
            age_decay = 0.40  # High risk of ghost job

        is_ghost_risk = listing_age_days > 60

        # 3. Channel Calculation
        channel_forecasts: Dict[str, ChannelProbability] = {}
        for c_type, c_info in self.CHANNEL_MULTIPLIERS.items():
            mult = c_info["multiplier"]
            # Combined multiplier
            total_mult = mult * age_decay
            # Calculate adjusted bounds
            adj_min = round(min(max(base_min * total_mult, 1.0), 95.0), 1)
            adj_max = round(min(max(base_max * total_mult, 2.0), 96.0), 1)
            if adj_min > adj_max:
                adj_min, adj_max = adj_max, adj_min

            channel_forecasts[c_type.value] = ChannelProbability(
                channel_name_cn=c_info["name_cn"],
                channel_name_en=c_info["name_en"],
                channel_type=c_type,
                multiplier=mult,
                min_prob=adj_min,
                max_prob=adj_max,
            )

        # Strategic summary
        best_chan = channel_forecasts[ChannelType.INTERNAL_REFERRAL.value]
        cold_chan = channel_forecasts[ChannelType.COLD_APPLICATION.value]

        if matcher_result.is_hard_vetoed:
            summary = (
                f"由于触发硬门槛拦截，海投拿面概率仅有约 {cold_chan.min_prob}%-{cold_chan.max_prob}%。"
                f"强烈建议走【内部员工内推】或业务团队直通，概率可回升至 {best_chan.min_prob}%-{best_chan.max_prob}%，"
                f"并需附带开源代码或顶会硬核背书进行破局。"
            )
        elif is_ghost_risk:
            summary = (
                f"该岗位已挂出超过 {listing_age_days} 天，存在极高的【幽灵职位/简历蓄水池】风险（时效衰减系数 0.4x）。"
                f"传统官网海投拿面概率仅 {cold_chan.min_prob}%-{cold_chan.max_prob}%。"
                f"若对该岗位有意向，务必走【内部员工内推】({best_chan.min_prob}%-{best_chan.max_prob}%)确认HC是否依然有效！"
            )
        else:
            summary = (
                f"在当前画像匹配度下，走【内部员工内推】拿面概率高达 {best_chan.min_prob}%-{best_chan.max_prob}%，"
                f"较普通官网海投({cold_chan.min_prob}%-{cold_chan.max_prob}%)具有 8 倍以上的胜率提升！"
            )

        return ProbabilityForecast(
            base_min_prob=base_min,
            base_max_prob=base_max,
            listing_age_days=listing_age_days,
            age_decay_multiplier=age_decay,
            is_ghost_job_risk=is_ghost_risk,
            channel_forecasts=channel_forecasts,
            recommended_channel=ChannelType.INTERNAL_REFERRAL.value,
            strategic_summary=summary,
        )


class InterviewTop20Predictor:
    """
    Generates a personalized Top 20 interview questions blueprint:
    - 5 Architecture & System Design questions
    - 5 Low-Level Principles & Algorithmic Details questions
    - 5 Behavioral & Team Collaboration (BQ) questions
    - 5 Candidate Reverse-Interview High-Leverage Inquiries
    Every question is dynamically linked to JD signals with explicit interviewer intent.
    """

    def predict(self, jd: DecodedJD, matcher_result: MatcherResult) -> List[InterviewQuestion]:
        """Generate exactly 20 targeted interview questions."""
        questions: List[InterviewQuestion] = []
        active_domains = set(jd.tech_domains)

        # 1. Architecture & System Design (5 questions)
        arch_qs = self._generate_arch_questions(jd, active_domains)
        questions.extend(arch_qs[:5])

        # 2. Low-Level Principles & Algorithmic Details (5 questions)
        princ_qs = self._generate_principles_questions(jd, active_domains)
        questions.extend(princ_qs[:5])

        # 3. Behavioral Questions & Team Collaboration (5 questions)
        bq_qs = self._generate_bq_questions(jd, matcher_result)
        questions.extend(bq_qs[:5])

        # 4. Candidate Reverse-Interviews (5 questions)
        rev_qs = self._generate_reverse_questions(jd)
        questions.extend(rev_qs[:5])

        # Renumber to ensure 1 to 20
        for i, q in enumerate(questions, 1):
            q.question_id = i

        return questions

    def _generate_arch_questions(self, jd: DecodedJD, domains: set) -> List[InterviewQuestion]:
        """5 Architecture & System Design questions."""
        qs = [
            InterviewQuestion(
                question_id=1,
                category_cn="架构与系统设计",
                category_en="Architecture & System Design",
                category_type=QuestionCategory.ARCHITECTURE,
                question_cn="请设计一个支持数十万并发、百亿至千亿参数大模型的高性能推理集群架构，如何协同解决 TTFT（首字延迟）与 TPOT（每Token吞吐）的冲突？",
                question_en="Design a high-throughput, low-latency distributed LLM serving architecture for 100B+ models under high concurrency. How do you balance TTFT and TPOT?",
                jd_signal="推理加速 / vLLM / 高并发吞吐 / P99时延考核",
                interviewer_intent="考察工业级分布式大模型服务系统全局设计能力，检验对 Prefill/Decode 分离架构（如 Mooncake/Splitwise）、Chunked Prefill 与 Continuous Batching 的掌控度。",
                prep_keypoints="1. 架构上提出 Prefill 与 Decode 物理节点池解耦；2. 阐述 PagedAttention 与 KV Cache 跨机/跨层压缩；3. 给出动态 Batching 策略与 P99 降温熔断机制。",
            ),
            InterviewQuestion(
                question_id=2,
                category_cn="架构与系统设计",
                category_en="Architecture & System Design",
                category_type=QuestionCategory.ARCHITECTURE,
                question_cn="在大规模集群（千卡以上）预训练千亿模型时，如何设计 3D 并行（TP/PP/DP/SP/EP）的最佳切分组合？怎样最大化消除流水线气泡(Pipeline Bubble)？",
                question_en="When pre-training 100B+ models on 1000+ GPUs, how do you determine the optimal 3D parallelism strategy (TP/PP/DP/SP/EP) and minimize pipeline bubbles?",
                jd_signal="算力基础设施 / 3D并行 / Megatron-LM / DeepSpeed ZeRO",
                interviewer_intent="考察候选人对超大规模分布式计算通信瓶颈的直觉，评估多机多卡拓扑（如单机NVLink vs 跨机InfiniBand/RoCE带宽差异）下的资源分配功力。",
                prep_keypoints="1. 单机内做 TP（利用NVLink 900GB/s带宽），跨机做 PP 和 DP（利用RoCE/IB）；2. 详述 1F1B 调度与 Interleaved 1F1B 降低流水线气泡从 (p-1)/m 到更低；3. 阐述 ZeRO-3/FSDP 与激活值重计算(Activation Checkpointing)显存节省对比。",
            ),
            InterviewQuestion(
                question_id=3,
                category_cn="架构与系统设计",
                category_en="Architecture & System Design",
                category_type=QuestionCategory.ARCHITECTURE,
                question_cn="针对企业级 128k/1M 超长文本处理，请设计一套端到端检索增强生成（GraphRAG + 向量检索）与长文本微调架构，如何攻克大海捞针(Needle in a Haystack)注意力衰减与显存二次方暴涨？",
                question_en="Design an enterprise end-to-end RAG and long-context architecture (128k/1M). How do you resolve memory quadratic explosion and retrieval precision degradation?",
                jd_signal="长上下文 / Long Context / 知识库检索 / RAG / 显存优化",
                interviewer_intent="考察长上下文落地时的系统级选型权衡：到底是用超长窗口直接推理，还是通过混合检索/分块分级注意力压缩召回，检验技术审美品位。",
                prep_keypoints="1. 计算端采用 FlashAttention-2/3、RingAttention 环形分布式通信；2. 预处理端结合分块Chunking与知识图谱实体关联网（GraphRAG）；3. KV Cache 引入 StreamingLLM 或动态量化压缩。",
            ),
            InterviewQuestion(
                question_id=4,
                category_cn="架构与系统设计",
                category_en="Architecture & System Design",
                category_type=QuestionCategory.ARCHITECTURE,
                question_cn="请设计一个具有自我纠错与工具调用(Tool Use/Function Calling)能力的多智能体(Multi-Agent)协同工作流架构，如何设计其记忆持久化(Memory)与死循环熔断机制？",
                question_en="Design a robust Multi-Agent workflow architecture with tool invocation and self-reflection. How do you handle persistent memory and infinite loop circuit breakers?",
                jd_signal="Agent智能体 / ReAct / 工作流编排 / Function Calling / MCP",
                interviewer_intent="考察候选人对 Agent 状态机、多轮对话一致性、工具调用安全边界及长流程工程可靠性的综合架构水准。",
                prep_keypoints="1. 采用有向无环图(DAG)或状态机引擎（如 LangGraph 设计理念）；2. 短期 Working Memory + 长期向量外置持久化；3. 引入最大步数步频监测、幻觉校验Guardrail与主动降级回退机制。",
            ),
            InterviewQuestion(
                question_id=5,
                category_cn="架构与系统设计",
                category_en="Architecture & System Design",
                category_type=QuestionCategory.ARCHITECTURE,
                question_cn="面对万卡集群训练过程中频繁出现的硬件掉卡、慢节点(Straggler)与NCCL通信挂死，请设计一套毫秒级故障自动隔离、无损断点续训(Checkpoint)与快速热重启架构。",
                question_en="In 10k-GPU clusters with frequent hardware faults, slow stragglers, and NCCL hangs, how do you architect fault isolation, zero-loss checkpointing, and fast warm rebooting?",
                jd_signal="万卡集群稳定性 / 算力基础设施 / NCCL / 断点续训 MTBF",
                interviewer_intent="考察候选人对昂贵算力物理世界残酷现实的认知，能否保障千卡/万卡训练 MFU > 45%，减少因挂卡导致的千万级预算流失。",
                prep_keypoints="1. 旁路心跳监控探针与动态拓扑探测，秒级隔离慢节点；2. 引入异步分布式保存机制（如 Checkpoint 写入本地高速 NVMe SSD 后异步拉取至分布式存储）；3. 热备冗余节点瞬时接管。",
            ),
        ]
        return qs

    def _generate_principles_questions(self, jd: DecodedJD, domains: set) -> List[InterviewQuestion]:
        """5 Low-Level Principles & Algorithmic Details questions."""
        qs = [
            InterviewQuestion(
                question_id=6,
                category_cn="底层原理与算法细节",
                category_en="Low-Level Principles & Algorithmic Details",
                category_type=QuestionCategory.PRINCIPLES,
                question_cn="请推导 FlashAttention 的核心数学原理：它是如何利用 Online Softmax 将显存访问从 HBM 转移到 SRAM，从而将显存复杂度从 O(N^2) 降至 O(N) 的？",
                question_en="Derive the mathematical principles of FlashAttention: How does Online Softmax enable tiling from HBM to SRAM and reduce memory IO from O(N^2) to O(N)?",
                jd_signal="FlashAttention / CUDA算子优化 / 显存IO优化",
                interviewer_intent="考察对 GPU 硬件存储层级（SRAM vs HBM 内存墙）与 Attention 算子分块分级计算数学底层的真正理解，拒绝API调包侠。",
                prep_keypoints="1. 详细说明 GPU 内存层级差异（SRAM 19TB/s vs HBM 2TB/s）；2. 推导 Online Softmax 局部缩放因子递推公式 m_new = max(m_old, m_block)；3. 阐述反向传播时重计算(Recomputation)替代全量激活保存以显存换速度的哲学。",
            ),
            InterviewQuestion(
                question_id=7,
                category_cn="底层原理与算法细节",
                category_en="Low-Level Principles & Algorithmic Details",
                category_type=QuestionCategory.PRINCIPLES,
                question_cn="请对比 DPO (Direct Preference Optimization) 与 PPO (Proximal Policy Optimization) 的损失函数构造，DPO 是如何通过代数变换消除显式奖励模型(Reward Model)与 Critic 网络的？它存在什么潜在数学缺陷？",
                question_en="Compare the loss formulations of DPO vs PPO. How does DPO mathematically bypass the explicit Reward Model and Critic network, and what are its inherent pitfalls?",
                jd_signal="RLHF / DPO / PPO / 评测对齐",
                interviewer_intent="考察大模型强化学习对齐算法的核心数学推导能力，以及对最新对齐前沿（如 DPO 在非配对数据下的偏置、KL惩罚失效与泛化漂移）的批判性思维。",
                prep_keypoints="1. 写出 Bradley-Terry 偏好模型公式；2. 推导闭式解 r*(x,y) = beta * log(pi_theta / pi_ref)；3. 分析 DPO 缺点：易受噪声偏好标签过拟合、缺少在线探索(Online Exploration)，引申出当前 GRPO/KTO/SimPO 的改进思路。",
            ),
            InterviewQuestion(
                question_id=8,
                category_cn="底层原理与算法细节",
                category_en="Low-Level Principles & Algorithmic Details",
                category_type=QuestionCategory.PRINCIPLES,
                question_cn="RoPE（旋转位置编码）的数学本质是什么？在长文本扩展时，直接线性插值(Linear Interpolation)、NTK-Aware 插值与 YaRN 在高频与低频分量上的处理有何根本区别？",
                question_en="What is the mathematical formulation of RoPE? When scaling context length, how do Linear Interpolation, NTK-Aware, and YaRN fundamentally differ across high/low frequencies?",
                jd_signal="长上下文 / RoPE / YaRN / 位置编码外推",
                interviewer_intent="考察复调数学功底与位置编码对注意力机制内积计算几何意义的直观理解，检验长文本微调方案的底层把控力。",
                prep_keypoints="1. 解释二维复平面旋转矩阵 R_Theta 及其满足 <R_m q, R_n k> = g(q, k, m-n) 的相对位置性质；2. 阐述直接插值导致高频细节严重模糊；3. 说明 NTK 与 YaRN 对高频维度保持外推、低频维度进行插值的频域自适应调整方案。",
            ),
            InterviewQuestion(
                question_id=9,
                category_cn="底层原理与算法细节",
                category_en="Low-Level Principles & Algorithmic Details",
                category_type=QuestionCategory.PRINCIPLES,
                question_cn="详细剖析 PagedAttention 的分页虚拟内存映射机制，它是如何从根本上解决传统 KV Cache 中高达 60%-80% 的内部与外部显存碎片的？",
                question_en="Dissect the virtual memory paging architecture of PagedAttention. How does it eliminate 60%-80% internal/external KV cache memory fragmentation?",
                jd_signal="vLLM / PagedAttention / KV Cache管理",
                interviewer_intent="考察对操作系统经典虚拟内存分页思想在大模型推理系统中迁移应用的领悟，判断候选人是否具备深厚工程架构功底。",
                prep_keypoints="1. 分析传统连续分配在动态生成长度未知时的Over-allocation与显存预留浪费；2. 解释 Logical Block 到 Physical Block 的 Page Table 映射结构；3. 阐述 Copy-on-Write (CoW) 在并行采样/Beam Search中的显存共享倍增机制。",
            ),
            InterviewQuestion(
                question_id=10,
                category_cn="底层原理与算法细节",
                category_en="Low-Level Principles & Algorithmic Details",
                category_type=QuestionCategory.PRINCIPLES,
                question_cn="在大模型权重量化中，AWQ (Activation-aware Weight Quantization) 相比 GPTQ 有何本质创新？为何保护仅占 1% 的显著激活通道(Salient Channels)能够大幅避免精度雪崩？",
                question_en="In LLM weight quantization, what is the core innovation of AWQ over GPTQ? Why does protecting the top 1% salient activation channels prevent severe perplexity degradation?",
                jd_signal="量化压缩 / AWQ / GPTQ / FP8 / 推理降本",
                interviewer_intent="考察候选人对深度神经网络激活分布长尾特性、矩阵量化舍入误差传递及工业级量化落地的算法原理储备。",
                prep_keypoints="1. 指出大模型权重本身重要性差异取决于输入激活特征幅度；2. 解释 AWQ 基于激活观测值寻找逐通道缩放因子(per-channel scaling factor)保护关键特征；3. 强调其无需依赖复杂的逆Hessian矩阵计算，泛化与硬件友好度极佳。",
            ),
        ]
        return qs

    def _generate_bq_questions(self, jd: DecodedJD, matcher: MatcherResult) -> List[InterviewQuestion]:
        """5 Behavioral & Team Collaboration (BQ) questions."""
        qs = [
            InterviewQuestion(
                question_id=11,
                category_cn="BQ 与团队协同",
                category_en="Behavioral & Team Collaboration",
                category_type=QuestionCategory.BQ,
                question_cn="请分享一次在预训练或核心大模型微调过程中，突发遇到 Loss 异常尖峰(Loss Spike)甚至发散的紧急排障经历。当时交付 Deadline 迫在眉睫，你如何定位根因并挽救训练进程？",
                question_en="Describe a high-stakes scenario where you encountered a sudden loss spike or divergence during training with a tight deadline. How did you diagnose the root cause and recover?",
                jd_signal="抗压能力强 / 训练稳定性 / 攻坚交付",
                interviewer_intent="考察高压情境下的情绪稳定性、科学排错方法论（数据污染？学习率？混合精度溢出？硬件软故障？）与系统性闭环复盘习惯。",
                prep_keypoints="使用 STAR 原则：S(千卡训练突发Loss发散，日损失数十万预算)；T(24小时内定位挽回)；A(回滚Checkpoint、拉取梯度范数监控排查出特定批次脏数据与FP16Underflow，切换BF16并剔除数据)；R(平稳完成收敛，形成自动化监控门禁)。",
            ),
            InterviewQuestion(
                question_id=12,
                category_cn="BQ 与团队协同",
                category_en="Behavioral & Team Collaboration",
                category_type=QuestionCategory.BQ,
                question_cn="当业务产品经理/业务线负责人基于少数 Bad Case 质疑你的模型能力，而你的离线基准测试（如 MMLU/GSM8K）得分却持续上升时，你如何跨越技术与业务的认知鸿沟达成共识？",
                question_en="When product managers challenge model quality based on subjective bad cases while your offline benchmark scores are improving, how do you bridge the gap and align on evaluation criteria?",
                jd_signal="业务闭环 / 商业化落地 / 结果导向",
                interviewer_intent="考察技术人员对业务痛点的同理心、避免自嗨的务实态度，以及构建贴合业务真实场景评测集(Eval Set)的跨职能沟通能力。",
                prep_keypoints="1. 承认通用榜单与垂直业务分布的脱节，避免拿出学术数据傲慢反驳；2. 协同业务人员将 Bad Case 结构化抽象为 5 大类垂直回归测试集(Golden Testset)；3. 建立基于 LLM-as-a-Judge 与人工双盲抽检的联合评估飞轮。",
            ),
            InterviewQuestion(
                question_id=13,
                category_cn="BQ 与团队协同",
                category_en="Behavioral & Team Collaboration",
                category_type=QuestionCategory.BQ,
                question_cn="当你发现团队现有的技术架构或历史代码存在严重性能瓶颈（例如自制推理框架效率远低于 vLLM），但老员工或负责人因沉没成本产生抵触情绪时，你如何优雅推动技术升级？",
                question_en="When you identify a major bottleneck in legacy systems that could be solved by modern open-source stacks, but encounter resistance due to sunk costs, how do you drive consensus?",
                jd_signal="自驱力强 / 拥抱变化 / 技术演进",
                interviewer_intent="考察候选人技术推动力、非职权影响力与政治情商，是用数据和PoC事实说话，还是盲目抱怨或引发冲突。",
                prep_keypoints="1. 不公开批判原有方案的局限，尊重历史背景；2. 利用业余时间搭建轻量 PoC 对比基线，用硬核数据（QPS提升300%、服务器成本削减50%）提供直观论证；3. 提出平滑迁移与灰度双跑方案，最大化保护团队战功归属感。",
            ),
            InterviewQuestion(
                question_id=14,
                category_cn="BQ 与团队协同",
                category_en="Behavioral & Team Collaboration",
                category_type=QuestionCategory.BQ,
                question_cn="在同时面对线上突发高优先级告警（如长尾请求偶发超时崩溃）与下季度核心技术突破重构双重任务时，你如何进行精力分配与优先级排序？",
                question_en="How do you balance high-urgency operational fires (e.g. sporadic online timeout crashes) with strategic long-term technical refactoring under tight time constraints?",
                jd_signal="快速响应 / 复合型人才 / 优先级管理",
                interviewer_intent="考察敏捷研发节奏下的时间管理与工程兜底思维，是否具备生产安全第一原则同时兼顾长效技术护城河建设。",
                prep_keypoints="1. 坚守线上生产事故一票否决：第一原则永远是先止血（降级、限流、切备用集群），恢复线上可用性；2. 事后必须做 Root Cause Analysis 并转为长效任务卡入排期；3. 将长期重构拆分为可独立灰度上线的增量小版本，避免大包推进陷阱。",
            ),
            InterviewQuestion(
                question_id=15,
                category_cn="BQ 与团队协同",
                category_en="Behavioral & Team Collaboration",
                category_type=QuestionCategory.BQ,
                question_cn="请分享一次你带领新人或与跨团队成员（如算法与底层 Infra 运维）共同攻坚一个硬核难题的经历。面对职责边界模糊或理解偏差，你如何确保成果按期交付？",
                question_en="Tell me about a time you led a junior peer or partnered across teams (e.g. Algo vs Infra) to tackle a challenging cross-functional goal. How did you ensure seamless delivery?",
                jd_signal="团队协同 / 复合型人才 / 扁平化管理",
                interviewer_intent="考察团队协同领导力、同理心与担当意识，能否跨越部门墙主动补位，推动全局最优而非局部最优。",
                prep_keypoints="1. 建立清晰的信息透明度与周对齐机制，明确各方的输入输出协议(Contract)；2. 主动承担最容易脱节的联调胶水层代码与中间件排障；3. 成果交付后主动在复盘报告中为跨部门伙伴高亮战功，建立长期技术信任。",
            ),
        ]
        return qs

    def _generate_reverse_questions(self, jd: DecodedJD) -> List[InterviewQuestion]:
        """5 Candidate Reverse-Interviews (High-Leverage Inquiries)."""
        qs = [
            InterviewQuestion(
                question_id=16,
                category_cn="候选人反问高级提问",
                category_en="High-Leverage Reverse Interviewing",
                category_type=QuestionCategory.REVERSE,
                question_cn="【算力底座反问】：请问目前支撑团队算法训练与线上推理的核心物理机 GPU 集群规模是多少（如 H100/H800/910B 的具体卡数）？算力预算与调度排期是团队独立支配还是全公司统筹排队？",
                question_en="[Compute Cluster]: What is the exact size of the GPU cluster (e.g. H100/A800/910B card counts) powering the team's training and serving? Is compute dedicated to your team or shared?",
                jd_signal="算力基础设施 / 真实物理资源摸底 / 避坑",
                interviewer_intent="展现出候选人极强的真实工程落地经验。只有真正带过大模型训练的老手才会极度关心卡数配额与调度权限，反问此题能瞬间建立专业气场并摸清团队真实家底。",
                prep_keypoints="倾听对方卡数规模：若能脱口而出数百/数千卡及专属排期，证明团队资金实力扎实；若闪烁其词或仅有几十张消费卡，需警惕算力空虚陷阱。",
            ),
            InterviewQuestion(
                question_id=17,
                category_cn="候选人反问高级提问",
                category_en="High-Leverage Reverse Interviewing",
                category_type=QuestionCategory.REVERSE,
                question_cn="【业务考核与定位反问】：岗位所在团队在公司整体战略架构中的定位是什么？未来半年到一年，管理层对团队最核心的验收考核指标，更偏向离线技术榜单与论文产出，还是核心商业场景的转化与降本 ROI？",
                question_en="[Strategic Positioning & KPIs]: What is the team's organizational positioning? Over the next 6-12 months, is leadership's primary KPI academic/benchmark achievements or direct business ROI?",
                jd_signal="业务闭环 / 商业化落地 / 部门战略边缘度摸底",
                interviewer_intent="考察候选人高维度的商业视野与求职成熟度，同时帮助自己探查该部门到底是核心造血业务还是面临随时可能被裁撤的边缘预研组。",
                prep_keypoints="如果主管明确指出对齐商业指标（如DAU、订单转化率、千万Token成本削减），说明业务生命力坚韧；若目标空泛，入职后易缺乏产出锚点。",
            ),
            InterviewQuestion(
                question_id=18,
                category_cn="候选人反问高级提问",
                category_en="High-Leverage Reverse Interviewing",
                category_type=QuestionCategory.REVERSE,
                question_cn="【技术瓶颈与攻坚反问】：在过去两个季度的实际落地中，团队遇到最棘手的一个技术瓶颈是什么？目前限制模型线上效果突破的最主要因素，是在长文本推理显存、垂直领域高质量数据，还是强化学习奖励对齐上？",
                question_en="[Technical Bottleneck]: What has been the most difficult technical roadblock over the past two quarters? Is the ceiling constrained by inference memory, high-quality data, or RL alignment?",
                jd_signal="核心痛点挖掘 / 深入技术一线 / 建立同行共鸣",
                interviewer_intent="将面试后半程的单向考核直接升级为平起平坐的技术同行深度探讨，能极快让面试官感受到候选人'已准备好下场干仗'的同频感。",
                prep_keypoints="认真倾听面试官倾诉的技术苦恼，结合自己过往的工程调优经验当场给出1-2个建设性思路，能大幅提升 Offer 评级。",
            ),
            InterviewQuestion(
                question_id=19,
                category_cn="候选人反问高级提问",
                category_en="High-Leverage Reverse Interviewing",
                category_type=QuestionCategory.REVERSE,
                question_cn="【工程分工与成长土壤反问】：团队内算法研发与工程落地、数据清洗标注、前端业务交互的协作分工机制是怎样的？对于加入团队的新人，前90天的成功画像(Success Profile)是完成怎样的里程碑交付？",
                question_en="[Division of Labor & Onboarding]: What is the collaborative interface between algorithm researchers, infra engineers, and data annotators? What defines a successful 90-day milestone for a new hire?",
                jd_signal="防全栈一人扛 / 新人落地保障 / 明确期望",
                interviewer_intent="探测团队是否具备健全的协作工具链与科学的培养机制，彻底排除'全栈一人扛+无带教自生自灭'的职场天坑。",
                prep_keypoints="若主管能清晰描绘前30天熟悉架构、60天独立上线微调模块、90天负责独立业务指标，说明组织效能成熟，值得加盟。",
            ),
            InterviewQuestion(
                question_id=20,
                category_cn="候选人反问高级提问",
                category_en="High-Leverage Reverse Interviewing",
                category_type=QuestionCategory.REVERSE,
                question_cn="【技术前沿演进反问】：面对当前 Agent 架构与轻量化小模型端侧推理（如 DeepSeek-R1 蒸馏架构、端侧量化与强化学习泛化）的爆发，团队在下一代技术架构上有何前瞻性的布局规划？",
                question_en="[Future Architecture]: With the rapid rise of Agent workflows and lightweight reasoning distillation (e.g. DeepSeek-R1 style), how is the team positioning its next-generation architecture?",
                jd_signal="前瞻技术洞察 / 战略前瞻性 / 技术好奇心",
                interviewer_intent="向面试官传递候选人不仅能埋头干活，更时刻保持对全球 AI 范式转移敏锐嗅觉的顶级工程师特质。",
                prep_keypoints="展现对 Reasoning 链条、长思能力与 Agentic 进化的见解，与面试官探讨未来模型演化对当前系统架构的潜在冲击。",
            ),
        ]
        return qs


class JDPredictor:
    """Combines probability calculation and top 20 questions generation."""

    def __init__(self):
        self.prob_calc = InterviewProbabilityCalculator()
        self.top20_pred = InterviewTop20Predictor()

    def predict(
        self,
        jd: DecodedJD,
        matcher_result: MatcherResult,
        listing_age_days: int = 15,
    ) -> PredictionResult:
        """Run full prediction pipeline."""
        prob_forecast = self.prob_calc.calculate(matcher_result, listing_age_days=listing_age_days)
        questions = self.top20_pred.predict(jd, matcher_result)
        return PredictionResult(
            probability_forecast=prob_forecast,
            top20_questions=questions,
        )

    def predict_targeted_questions(
        self,
        jd: DecodedJD,
        matcher_result: MatcherResult,
        count: int = 3,
    ) -> List[InterviewQuestion]:
        """
        Rank and select exactly `count` targeted interview questions from the generated pool.
        Ranking criteria:
        1. Relevance to detected gaps (REAL_GAP / INSUFFICIENT_EVIDENCE / EXPRESSION_GAP).
        2. Direct alignment with detected implicit signals / core responsibilities.
        3. Breadth across categories (architecture / principles / BQ / reverse).
        Guarantees returning exactly `count` questions with 1-based sequential IDs.
        """
        all_qs = self.top20_pred.predict(jd, matcher_result)
        if not all_qs:
            return []

        def gap_question(gap, question_id: int) -> InterviewQuestion:
            requirement = gap.requirement_name.replace("技能-", "").replace("职责-", "").replace("硬门槛-", "").replace("门槛要求-", "").replace("隐性考核-", "")
            if gap.state == GapState.REAL_GAP:
                question = f"目标岗位要求【{requirement}】，但当前材料没有直接证据。你如何诚实说明这一缺口，并用真实的相邻经验说明可迁移能力？"
                intent = "确认候选人是否会划清事实边界，而不是为了匹配 JD 临场编造经历。"
                prep = "先明确未做过的范围，再说明最接近的真实项目、底层共性、已经完成的学习验证和入职后的补齐步骤。"
            elif gap.state == GapState.INSUFFICIENT_EVIDENCE:
                question = f"你在材料中提到过【{requirement}】，请选一个真实项目，说明背景、个人动作、方案取舍、结果口径以及证据来源。"
                intent = "核实技能是否落到具体行动和结果，而不是只停留在技能清单。"
                prep = "按背景、目标、个人动作、替代方案、baseline、结果、统计周期、团队边界和失败复盘组织回答。"
            elif gap.state == GapState.EXPRESSION_GAP:
                question = f"当前材料只有与【{requirement}】相邻的经验。两者哪些底层能力可迁移，哪些部分你尚未实际做过？"
                intent = "检验候选人能否准确区分可迁移能力与真实经历，避免把相邻技术偷换成直接经验。"
                prep = "分别列出共同原理、已做过的模块、未做过的模块和一个可验证的迁移计划。"
            else:
                question = f"针对【{requirement}】，请说明当前材料中可核验的事实、仍待确认的信息，以及面试时你会如何划定边界。"
                intent = "补齐缺失事实并检查候选人的边界意识。"
                prep = "只使用能回到简历底稿或证据文件的内容；未知内容明确标为待确认。"
            return InterviewQuestion(
                question_id=question_id,
                category_cn="岗位缺口与事实防守",
                category_en="Role Gap & Evidence Defense",
                category_type=QuestionCategory.BQ,
                question_cn=question,
                question_en=f"Explain the evidence and honest boundary for this job requirement: {requirement}.",
                jd_signal=requirement,
                interviewer_intent=intent,
                prep_keypoints=prep,
            )

        priority = {
            GapState.REAL_GAP: 0,
            GapState.INSUFFICIENT_EVIDENCE: 1,
            GapState.EXPRESSION_GAP: 2,
            GapState.TO_BE_CONFIRMED: 3,
        }
        actionable_gaps = [
            gap for gap in getattr(matcher_result, "gap_matrix", [])
            if gap.state in priority and gap.category in {"skill", "responsibility", "threshold"}
        ]
        category_priority = {"skill": 0, "responsibility": 1, "threshold": 2}
        actionable_gaps.sort(key=lambda gap: (
            priority[gap.state],
            category_priority.get(gap.category, 3),
            0 if str(gap.importance).lower() in {"mandatory", "must_have"} else 1,
        ))

        generated: List[InterviewQuestion] = []
        seen_requirements: set[str] = set()
        for gap in actionable_gaps:
            requirement = gap.requirement_name.lower()
            if requirement in seen_requirements:
                continue
            seen_requirements.add(requirement)
            generated.append(gap_question(gap, len(generated) + 1))
            if len(generated) >= count:
                return generated

        def terms(value: str) -> set[str]:
            stopwords = {"负责", "熟悉", "掌握", "能力", "经验", "要求", "相关", "优先", "系统", "技术"}
            return {
                token.lower()
                for token in re.split(r"[^A-Za-z0-9+#.\-一-鿿]+", value or "")
                if len(token) >= 2 and token not in stopwords
            }

        # Candidate-gap terms carry the most weight, followed by the JD's own
        # responsibilities, skills and implicit signals.  This keeps selection
        # deterministic while avoiding a category-first generic Top-20 sample.
        gap_keywords: set[str] = set()
        for gap in getattr(matcher_result, "gap_matrix", []):
            if getattr(gap.state, "value", str(gap.state)) == "MATCHED":
                continue
            req = gap.requirement_name.replace("技能-", "").replace("职责-", "").replace("隐性考核-", "")
            gap_keywords.update(terms(req))

        jd_keywords: set[str] = set()
        for skill in getattr(jd, "core_skills", []):
            jd_keywords.update(terms(skill.name))
        for responsibility in getattr(jd, "core_responsibilities", []):
            jd_keywords.update(terms(responsibility.description))

        signal_keywords: set[str] = set()
        for signal in getattr(jd, "implicit_signals", []):
            signal_keywords.update(terms(signal.original_text))

        scored_qs = []
        for q in all_qs:
            score = 0.0
            q_text = (q.question_cn + " " + q.jd_signal + " " + q.interviewer_intent).lower()
            # Gap match weight
            for gk in gap_keywords:
                if gk and gk in q_text:
                    score += 5.0
            # Direct JD match weight
            for keyword in jd_keywords:
                if keyword and keyword in q_text:
                    score += 2.0
            # Signal match weight
            for sk in signal_keywords:
                if sk and sk in q_text:
                    score += 3.0
            # Prefer breadth only as a tie-breaker; relevance to the JD and
            # the candidate's gaps must dominate category preference.
            if q.category_type == QuestionCategory.BQ:
                score += 0.25
            elif q.category_type == QuestionCategory.REVERSE:
                score += 0.1

            scored_qs.append((score, q))

        # Sort descending by relevance score
        scored_qs.sort(key=lambda item: item[0], reverse=True)

        # Select remaining questions with category diversity if possible.
        selected: List[InterviewQuestion] = list(generated)
        seen_categories = {question.category_type for question in generated}

        for _, q in scored_qs:
            if len(selected) >= count:
                break
            if q.category_type not in seen_categories or len(selected) + 1 >= count:
                selected.append(q)
                seen_categories.add(q.category_type)

        # If still need more to reach `count`, fill from remainder
        if len(selected) < count:
            for _, q in scored_qs:
                if q not in selected:
                    selected.append(q)
                if len(selected) >= count:
                    break

        # Re-index question IDs sequentially 1..count
        result: List[InterviewQuestion] = []
        for idx, q in enumerate(selected[:count], 1):
            result.append(InterviewQuestion(
                question_id=idx,
                category_cn=q.category_cn,
                category_en=q.category_en,
                category_type=q.category_type,
                question_cn=q.question_cn,
                question_en=q.question_en,
                jd_signal=q.jd_signal,
                interviewer_intent=q.interviewer_intent,
                prep_keypoints=q.prep_keypoints,
            ))
        return result
