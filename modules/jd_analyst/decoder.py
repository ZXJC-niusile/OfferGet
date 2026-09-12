"""
JD Decoder: 5-Layer Deep Semantic Decoding for AI/LLM/Agent/Algorithm Roles.
"""

import re
from typing import List, Dict, Tuple, Optional, Any
from .models import (
    DecodedJD,
    HardThreshold,
    CoreResponsibility,
    CoreSkill,
    ImplicitSignal,
    BusinessPainPoint,
    BoilerplateFiltered,
    TechDomain,
    SkillImportance,
)


class JDDecoder:
    """
    Decodes job descriptions into 5 semantic layers:
    1. Hard Thresholds (Education, Experience years, Major, etc.)
    2. Core Responsibilities
    3. Core Skills (Must Have & Nice To Have, specialized for AI/LLM/Agent)
    4. Implicit Signals & Jargon Translation
    5. Business Pain Points & KPIs
    Also strips PR fluff and boilerplate text.
    """

    # Big Tech Jargon & Implicit Signal Dictionary
    JARGON_MAPPING: List[Dict[str, str]] = [
        {
            "pattern": r"(抗压能力强|抗压能力极强|能承受较强的工作压力|具备良好的抗压能力)",
            "meaning": "业务需求变动频繁，常态化高强度加班，项目交付排期极紧或存在高频突发On-Call。",
            "risk": "生理与心理负荷高，极易陷入业务消防员恶性循环，技术沉淀时间被严重压缩。",
            "countermeasure": "面试中重点反问团队日常发版节奏、On-Call轮值机制与过去三个月加班频次，评估心理预期。",
        },
        {
            "pattern": r"(自驱力强|极强的主观能动性|自主性高|强自驱)",
            "meaning": "团队缺乏体系化文档、完备的开发规范与带教导师机制，需要员工独立野蛮生长并自我推进。",
            "risk": "工作容易抓瞎且边界模糊，新人落地期无抓手，若遇到考核可能因无序探索而背锅。",
            "countermeasure": "面试反问团队的项目立项流程、资源申请权限以及对新人的前90天明确产出考核预期。",
        },
        {
            "pattern": r"(拥抱变化|能适应快速变化|敏捷应变)",
            "meaning": "业务方向不确定性极高，团队战略规划经常摇摆，项目随时可能推倒重来或中途夭折换道。",
            "risk": "长期无法产出完整的业务上线成果，简历上只有停留在PoC阶段的半成品，缺乏线上商业战功。",
            "countermeasure": "向主管深入探究该业务在公司大盘的战略定位、预算周期与管理层允许试错的窗口期长度。",
        },
        {
            "pattern": r"(从0到1|负责0到1搭建|开拓性业务)",
            "meaning": "几乎没有基础设施沉淀，缺乏现成的数据管道、训练算力底座和标注工具链，需要候选人肉身铺路。",
            "risk": "大量时间消耗在修网络、配显卡驱动、搭K8s集群等繁琐工程脏活累活上，算法核心研发受阻。",
            "countermeasure": "反问算力集群实际卡数、是否有专职Infra/DevOps支持、数据标注预算及现有工程代码资产基座。",
        },
        {
            "pattern": r"(商业化落地|业务闭环|对业务结果负责|结果导向|背负业务指标)",
            "meaning": "不接受纯学术玩具研究或离线榜单自嗨，背负直接的商业转化、成本削减(ROI)或营收增长硬性考核。",
            "risk": "若模型短期无法见效提振业务大盘，部门面临首当其冲被削减预算甚至整条线裁撤的风险。",
            "countermeasure": "准备好端到端量化商业战功案例（如降低Token成本X%、提升转化率Y%），证明商业工程双修能力。",
        },
        {
            "pattern": r"(扁平化管理|团队氛围扁平)",
            "meaning": "管理层级虽少但职能边界极为模糊，每个人都需要兼顾边缘杂活，且缺乏清晰透明的职级晋升通道。",
            "risk": "缺乏明确的职级锚点和带人梯队，工作职责容易无限蔓延变成多面打杂。",
            "countermeasure": "了解团队汇报线架构、是否有明确的晋升窗口、技术职级评审委员会与薪酬调整机制。",
        },
        {
            "pattern": r"(复合型人才|一专多能|全栈思维)",
            "meaning": "团队编制预算有限或人手严重紧缺，期望一人包揽算法、后端、工程、测试乃至产品设计。",
            "risk": "精力被碎片化严重稀释，深度技术难以专精，成为业务全栈救火队员。",
            "countermeasure": "明确岗位第一核心产出到底偏向算法深度还是工程交付，梳理日常时间分配比例预期。",
        },
        {
            "pattern": r"(创业激情|具有创业者精神|不计较个人得失)",
            "meaning": "薪酬中现金Base可能偏低，倾向于用期权份额画饼，且期望员工全天候投入无节制奉献。",
            "risk": "期权兑现周期长且流动性存疑，高强度消耗下可能面临兑现前被稀释或业务停摆的不可抗力风险。",
            "countermeasure": "核实期权归属协议(Vesting Schedule)、公司最新融资轮次、估值基准及现金Base底线。",
        },
        {
            "pattern": r"(快速响应|即时响应业务需求|随时待命)",
            "meaning": "存在非工作时间、节假日突发On-Call或即时回复飞书/钉钉群消息的高压要求。",
            "risk": "个人生活边界彻底瓦解，长期处于紧绷状态易导致严重职业倦怠。",
            "countermeasure": "确认值班轮换制度、告警分级机制以及是否有合理的调休或补偿规范。",
        },
    ]

    # PR Boilerplate & Fluff Patterns (To be identified and removed)
    BOILERPLATE_PATTERNS: List[Tuple[str, str]] = [
        (r"(我们提供业界领先的薪酬福利待遇|极具竞争力的薪资|高额期权激励)", "薪酬福利宣传套话"),
        (r"(五险一金|定期体检|带薪年假|年度健康体检|节日礼品|生日礼券)", "法定福利与常规人事套话"),
        (r"(免费零食下午茶|咖啡无限畅饮|水果点心|晚餐餐补|夜宵福利)", "行政生活福利套话"),
        (r"(与充满激情的小伙伴一同成长|大牛带队|技术氛围浓厚|定期技术分享)", "团队氛围宣传套话"),
        (r"(广阔的职业发展空间|晋升通道通畅|快速成长平台|赋能个人价值)", "职业发展泛化宣传套话"),
        (r"(为全球用户创造极具价值的体验|赋能千行百业|推动人工智能革命|引领未来变革)", "宏大叙事与公关口号"),
        (r"(扁平化管理，杜绝办公室政治|轻松活跃的团队文化|不提倡无效内卷)", "文化价值观口号"),
        (r"(提供健身房|定期团建旅游|丰富多彩的俱乐部活动|德州扑克/桌游活动)", "业余文娱福利套话"),
    ]

    # AI / LLM / Agent Domain Specific Taxonomy
    DOMAIN_TAXONOMY: Dict[TechDomain, List[Dict[str, Any]]] = {
        TechDomain.COMPUTE_INFRA: [
            {"keywords": ["NCCL", "InfiniBand", "RoCE", "RDMA", "Slurm", "Ray", "K8s", "Kubernetes", "GPU集群", "万卡", "千卡", "A100", "H100", "H800", "B200", "昇腾", "910B"], "category": "infra"},
            {"keywords": ["Megatron-LM", "Megatron", "DeepSpeed", "ColossalAI", "PaddleNLP"], "category": "framework"},
        ],
        TechDomain.TRAINING_COMM: [
            {"keywords": ["3D并行", "张量并行", "流水线并行", "数据并行", "TP", "PP", "DP", "SP", "EP", "序列并行", "专家并行"], "category": "theory"},
            {"keywords": ["ZeRO-1", "ZeRO-2", "ZeRO-3", "ZeRO-Offload", "FSDP", "Fully Sharded Data Parallel"], "category": "framework"},
            {"keywords": ["通信优化", "Overlap", "梯度累积", "算子融合", "FP8", "BF16", "混合精度", "流水线气泡"], "category": "algorithm"},
        ],
        TechDomain.ALIGNMENT_EVAL: [
            {"keywords": ["RLHF", "DPO", "PPO", "GRPO", "KTO", "ORPO", "SimPO", "SFT", "指令微调", "对齐", "Alignment", "奖励模型", "Reward Model"], "category": "algorithm"},
            {"keywords": ["评测体系", "MMLU", "GSM8K", "MATH", "HumanEval", "AlpacaEval", "Arena", "LMSYS", "红队攻防", "Red Teaming", "安全对齐", "Safety Guardrails", "幻觉检测", "Hallucination"], "category": "theory"},
        ],
        TechDomain.LONG_CONTEXT: [
            {"keywords": ["长上下文", "长文本", "Long Context", "RoPE", "YaRN", "RoPE Scaling", "外推", "内插"], "category": "theory"},
            {"keywords": ["RingAttention", "Chunked Attention", "FlashAttention", "FlashAttention-2", "FlashAttention-3"], "category": "algorithm"},
            {"keywords": ["KV Cache压缩", "PagedAttention", "StreamingLLM", "LongBench", "Ruler"], "category": "infra"},
        ],
        TechDomain.INFERENCE_ACCEL: [
            {"keywords": ["vLLM", "TensorRT-LLM", "TGI", "SGLang", "Triton Server", "LightLLM"], "category": "framework"},
            {"keywords": ["投机采样", "Speculative Decoding", "Continuous Batching", "Prefix Caching", "Chunked Prefill"], "category": "algorithm"},
            {"keywords": ["AWQ", "GPTQ", "SmoothQuant", "INT4", "INT8", "FP8", "量化", "模型蒸馏", "Distillation", "剪枝"], "category": "algorithm"},
            {"keywords": ["Triton", "CUDA", "C++", "C++11", "Kernel优化", "算子编写"], "category": "language"},
        ],
        TechDomain.AGENT_WORKFLOW: [
            {"keywords": ["Agent", "智能体", "Multi-Agent", "多智能体", "ReAct", "Tool Use", "Function Calling", "Plan-and-Solve"], "category": "algorithm"},
            {"keywords": ["LangChain", "LlamaIndex", "LangGraph", "AutoGen", "CrewAI", "MetaGPT"], "category": "framework"},
            {"keywords": ["MCP", "Model Context Protocol", "向量检索", "RAG", "Milvus", "Qdrant", "Pinecone", "Chroma", "GraphRAG"], "category": "infra"},
            {"keywords": ["Memory系统", "状态机", "工作流编排", "Workflow", "Prompt Engineering"], "category": "theory"},
        ],
        TechDomain.GENERAL_ML: [
            {"keywords": ["PyTorch", "TensorFlow", "JAX"], "category": "framework"},
            {"keywords": ["Python", "C++", "Golang", "Rust", "Shell", "Linux"], "category": "language"},
            {"keywords": ["Transformer", "Attention", "CNN", "RNN", "Diffusion", "多模态", "Multimodal", "CLIP", "ViT"], "category": "theory"},
        ]
    }

    def decode(self, jd_text: str, job_title_hint: str = "", company_hint: str = "") -> DecodedJD:
        """Main entry point to perform 5-layer decoding on JD text."""
        raw_text = jd_text.strip() if jd_text else ""
        if not raw_text:
            return DecodedJD(
                raw_text="",
                job_title=job_title_hint or "未指定职位",
                company_or_dept=company_hint or "未知团队",
                clean_text="",
            )

        # 1. Filter PR fluff and boilerplates
        clean_text, filtered_boilerplates = self._filter_boilerplates(raw_text)

        # Extract title and company if not given
        job_title = job_title_hint or self._extract_job_title(clean_text)
        company_or_dept = company_hint or self._extract_company_dept(clean_text)

        # Layer 1: Hard Thresholds
        hard_thresholds = self._extract_hard_thresholds(clean_text)

        # Layer 2: Core Responsibilities
        core_responsibilities = self._extract_responsibilities(clean_text)

        # Layer 3: Core Skills (Must Have & Nice To Have) with domain enhancement
        core_skills, active_domains = self._extract_skills(clean_text)

        # Layer 4: Implicit Signals & Jargon Translation
        implicit_signals = self._extract_implicit_signals(clean_text)

        # Layer 5: Business Pain Points & Evaluation Targets (KPIs)
        business_pain_points = self._extract_pain_points(clean_text)

        return DecodedJD(
            raw_text=raw_text,
            job_title=job_title,
            company_or_dept=company_or_dept,
            hard_thresholds=hard_thresholds,
            core_responsibilities=core_responsibilities,
            core_skills=core_skills,
            implicit_signals=implicit_signals,
            business_pain_points=business_pain_points,
            filtered_boilerplates=filtered_boilerplates,
            clean_text=clean_text,
            tech_domains=[d.value if isinstance(d, TechDomain) else str(d) for d in active_domains],
        )

    def _filter_boilerplates(self, text: str) -> Tuple[str, List[BoilerplateFiltered]]:
        """Identify and strip PR buzzwords and boilerplate lines."""
        filtered: List[BoilerplateFiltered] = []
        lines = text.split("\n")
        retained_lines: List[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                retained_lines.append("")
                continue

            matched_reasons = []
            for pat, reason in self.BOILERPLATE_PATTERNS:
                if re.search(pat, line_str, re.IGNORECASE):
                    matched_reasons.append(reason)

            if matched_reasons:
                for reason in matched_reasons:
                    filtered.append(BoilerplateFiltered(text=line_str, reason=reason))
            else:
                retained_lines.append(line)

        clean_text = "\n".join(retained_lines).strip()
        return clean_text, filtered

    def _extract_job_title(self, text: str) -> str:
        """Extract or infer job title from first few lines or explicit tags."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return "AI / 大模型算法工程师"

        first_line = lines[0]
        # Match common title patterns: e.g. 职位：大模型算法专家
        m = re.search(r"(?:职位(?:名称)?|岗位(?:名称)?|招聘岗位|Job\s*Title)[：:\s]+([^\n,，;；]{2,30})", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # If first line looks like a title
        if any(keyword in first_line for keyword in ["算法", "大模型", "LLM", "Agent", "工程", "研发", "架构师", "专家", "研究员"]):
            return first_line.strip("# -*")

        return "AI/大模型核心算法工程师"

    def _extract_company_dept(self, text: str) -> str:
        """Extract company or department info if available."""
        m = re.search(r"(?:公司|部门|所属部门|团队)[：:\s]+([^\n,，;；]{2,30})", text)
        if m:
            return m.group(1).strip()
        return "核心技术业务部"

    def _extract_hard_thresholds(self, text: str) -> List[HardThreshold]:
        """Extract education, experience years, major, and certifications."""
        thresholds: List[HardThreshold] = []

        # 1. Education
        degree_patterns = [
            (r"(博士(?:及以上|研究生)?)", "博士", "博士研究生及以上学历"),
            (r"(硕士(?:及以上|研究生)?|硕士以上|硕士研究生)", "硕士", "硕士研究生及以上学历"),
            (r"(统招本科|本科及以上|本科以上|大学本科|统招统分本科)", "本科", "统招本科及以上学历"),
            (r"(大专及以上|大专以上|专科及以上)", "大专", "大专及以上学历"),
        ]
        degree_found = False
        for pat, deg_code, desc in degree_patterns:
            if re.search(pat, text):
                thresholds.append(
                    HardThreshold(
                        category="education",
                        requirement=desc,
                        is_mandatory=True,
                        min_degree=deg_code,
                    )
                )
                degree_found = True
                break

        if not degree_found:
            # Check for generic "学历" mention
            if re.search(r"(硕士|研究生)", text):
                thresholds.append(HardThreshold(category="education", requirement="硕士及以上", min_degree="硕士"))
            elif re.search(r"(本科)", text):
                thresholds.append(HardThreshold(category="education", requirement="本科及以上", min_degree="本科"))

        # 2. Years of Experience
        exp_patterns = [
            (r"(\d+)\s*(?:年|Years?)(?:及以上|以上|\+)(?:工作经验|经验|算法经验|开发经验)?", "min_years"),
            (r"(\d+)\s*(?:年|Years?)(?:工作经验|经验|算法经验|开发经验)", "min_years"),
            (r"(\d+)[-~至到](\d+)\s*年(?:工作经验|经验)?", "range_years"),
            (r"(应届生|应届毕业生|202[4-7]届|无工作年限要求)", "fresh_grad"),
        ]
        exp_found = False
        for pat, kind in exp_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                if kind == "min_years":
                    yrs = float(m.group(1))
                    thresholds.append(
                        HardThreshold(
                            category="experience_years",
                            requirement=f"{int(yrs)}年及以上相关领域工作经验",
                            is_mandatory=True,
                            min_years=yrs,
                        )
                    )
                    exp_found = True
                    break
                elif kind == "range_years":
                    min_yrs = float(m.group(1))
                    thresholds.append(
                        HardThreshold(
                            category="experience_years",
                            requirement=f"{int(min_yrs)}-{int(m.group(2))}年相关领域工作经验",
                            is_mandatory=True,
                            min_years=min_yrs,
                        )
                    )
                    exp_found = True
                    break
                elif kind == "fresh_grad":
                    thresholds.append(
                        HardThreshold(
                            category="experience_years",
                            requirement="应届毕业生 / 无硬性年限要求",
                            is_mandatory=False,
                            min_years=0.0,
                        )
                    )
                    exp_found = True
                    break

        if not exp_found:
            # Default fallback if text implies senior
            if re.search(r"(资深|专家|Staff|Principal|Leader|负责人)", text, re.IGNORECASE):
                thresholds.append(
                    HardThreshold(
                        category="experience_years",
                        requirement="5年及以上算法研发经验（资深/专家岗推定）",
                        is_mandatory=True,
                        min_years=5.0,
                    )
                )

        # 3. Major
        major_pat = r"(计算机|软件工程|人工智能|数学|应用数学|统计学|自动化|电子信息|通信工程)"
        matched_majors = list(set(re.findall(major_pat, text)))
        if matched_majors:
            thresholds.append(
                HardThreshold(
                    category="major",
                    requirement=f"{'/'.join(matched_majors[:4])}等理工科相关专业优先",
                    is_mandatory=False,
                    required_majors=matched_majors,
                )
            )

        # 4. Mandatory papers or open source
        if re.search(r"(NeurIPS|ICML|ICLR|ACL|EMNLP|CVPR|ICCV|KDD|AAAI)", text, re.IGNORECASE):
            thresholds.append(
                HardThreshold(
                    category="publication",
                    requirement="有顶会论文（NeurIPS/ICML/ICLR/ACL等）发表者优先",
                    is_mandatory=False,
                )
            )

        return thresholds

    def _extract_responsibilities(self, text: str) -> List[CoreResponsibility]:
        """Extract core responsibilities from JD."""
        responsibilities: List[CoreResponsibility] = []

        # Find section for responsibilities
        resp_section = ""
        m = re.search(r"(?:岗位职责|工作职责|主要职责|职责描述|Responsibilities)[\s：:]*([\s\S]*?)(?=(?:任职要求|任职资格|任职条件|岗位要求|加分项|优先条件|Requirements|$))", text, re.IGNORECASE)
        if m:
            resp_section = m.group(1)
        else:
            resp_section = text

        lines = [l.strip() for l in resp_section.split("\n") if l.strip()]
        for line in lines:
            # Ignore headers
            if re.match(r"^(?:岗位职责|工作职责|主要职责|职责描述|Responsibilities)", line, re.IGNORECASE):
                continue
            # Look for numbered or bullet points
            cleaned_line = re.sub(r"^[0-9一二三四五六七八九十\.\、\-\*•\(\)（）\s]+", "", line).strip()
            if len(cleaned_line) >= 8:
                # Infer domain
                domain = self._infer_domain_for_text(cleaned_line)
                responsibilities.append(
                    CoreResponsibility(
                        title=cleaned_line[:30] + ("..." if len(cleaned_line) > 30 else ""),
                        description=cleaned_line,
                        domain=domain.value,
                        weight=1.0,
                    )
                )

        # If too few responsibilities detected, synthesize from AI domain keywords
        if len(responsibilities) < 2:
            if re.search(r"(预训练|Pre-train|对齐|RLHF|SFT)", text, re.IGNORECASE):
                responsibilities.append(
                    CoreResponsibility(
                        title="大模型预训练与指令微调对齐",
                        description="负责亿级至千亿级参数大模型预训练、SFT微调及RLHF/DPO强化学习对齐策略研发与落地。",
                        domain=TechDomain.TRAINING_COMM.value,
                    )
                )
            if re.search(r"(推理|Inference|vLLM|量化|加速)", text, re.IGNORECASE):
                responsibilities.append(
                    CoreResponsibility(
                        title="大模型高性能推理引擎架构与算子加速",
                        description="负责大模型线上服务吞吐提升、P99时延优化、量化压缩与投机采样等工程加速方案落地。",
                        domain=TechDomain.INFERENCE_ACCEL.value,
                    )
                )
            if re.search(r"(Agent|智能体|工作流|RAG|Tool Use)", text, re.IGNORECASE):
                responsibilities.append(
                    CoreResponsibility(
                        title="AI Agent 智能体架构设计与工具调用落地",
                        description="负责复杂长流程Agent规划能力设计、多工具函数调用(Function Calling)、状态管理与企业级RAG知识增强体系研发。",
                        domain=TechDomain.AGENT_WORKFLOW.value,
                    )
                )

        return responsibilities

    def _infer_domain_for_text(self, snippet: str) -> TechDomain:
        """Infer the closest tech domain for a snippet."""
        snippet_upper = snippet.upper()
        scores: Dict[TechDomain, int] = {d: 0 for d in TechDomain}

        for domain, group in self.DOMAIN_TAXONOMY.items():
            for item in group:
                for kw in item["keywords"]:
                    if kw.upper() in snippet_upper:
                        scores[domain] += 2

        best_domain = max(scores, key=scores.get)
        if scores[best_domain] > 0:
            return best_domain
        return TechDomain.GENERAL_ML

    def _extract_skills(self, text: str) -> Tuple[List[CoreSkill], List[TechDomain]]:
        """Extract core skills, dividing into Must Have and Nice to Have."""
        skills: List[CoreSkill] = []
        seen_names = set()
        active_domains: set = set()

        # Split into requirements vs nice-to-have sections if possible
        must_section = text
        nice_section = ""
        nice_match = re.search(r"(?:加分项|优先考虑|具备以下条件者优先|加分条件|Preferred|Nice to have)[\s：:]*([\s\S]*?)(?=(?:福利待遇|关于我们|$))", text, re.IGNORECASE)
        if nice_match:
            nice_section = nice_match.group(1)

        # Scan domain taxonomy
        for domain, items in self.DOMAIN_TAXONOMY.items():
            for item in items:
                category = item["category"]
                for kw in item["keywords"]:
                    # Exact word boundary or case check for acronyms
                    if kw.upper() == "C++":
                        pat = r"(?<!\w)C\+\+(?!\w)"
                    elif kw.isupper() and len(kw) <= 4:
                        pat = rf"\b{re.escape(kw)}\b"
                    else:
                        pat = rf"(?i)\b{re.escape(kw)}\b"

                    if re.search(pat, text):
                        active_domains.add(domain)
                        is_nice = False
                        if nice_section and re.search(pat, nice_section):
                            is_nice = True
                        elif re.search(rf"(?:优先|plus|加分).*?{re.escape(kw)}|{re.escape(kw)}.*?(?:优先|加分)", text, re.IGNORECASE):
                            is_nice = True

                        skill_name = kw
                        if skill_name not in seen_names:
                            seen_names.add(skill_name)
                            skills.append(
                                CoreSkill(
                                    name=skill_name,
                                    category=category,
                                    importance=SkillImportance.NICE_TO_HAVE.value if is_nice else SkillImportance.MUST_HAVE.value,
                                    domain=domain.value,
                                    context=f"匹配到关键词: {kw}",
                                )
                            )

        # Sort skills: must have first, then nice to have
        skills.sort(key=lambda s: 0 if s.importance == SkillImportance.MUST_HAVE.value else 1)
        return skills, list(active_domains)

    def _extract_implicit_signals(self, text: str) -> List[ImplicitSignal]:
        """Detect big tech jargon and translate implicit subtext."""
        signals: List[ImplicitSignal] = []
        for mapping in self.JARGON_MAPPING:
            m = re.search(mapping["pattern"], text)
            if m:
                signals.append(
                    ImplicitSignal(
                        original_text=m.group(0),
                        translated_meaning=mapping["meaning"],
                        underlying_risk=mapping["risk"],
                        candidate_countermeasure=mapping["countermeasure"],
                    )
                )
        return signals

    def _extract_pain_points(self, text: str) -> List[BusinessPainPoint]:
        """Extract business pain points, performance bottlenecks, and target KPIs."""
        pain_points: List[BusinessPainPoint] = []

        # Patterns for pain points and KPIs
        indicators = [
            (
                r"(推理延迟|低延迟|P99|TTFT|吞吐|高并发|QPS|显存优化|显存瓶颈)",
                "推理成本与高并发延迟痛点",
                "线上大模型服务显存开销极大、并发吞吐受限、首字时延(TTFT)过长，亟需深度量化、PagedAttention及算子级极致优化降低百万Token推理成本。",
                "TTFT < 80ms, P99 Latency < 500ms, 单卡并发吞吐提升 3x, GPU显存碎片率 < 10%",
            ),
            (
                r"(长文本|长上下文|Long Context|大海捞针|Needle in a Haystack|128k|1M)",
                "长上下文与大海捞针召回痛点",
                "长文本推理显存二次方爆炸、注意力弥散与有效信息召回精度急剧衰减，需要RoPE外推、RingAttention及有效KV Cache压缩技术攻坚。",
                "128k/1M 上下文下 Needle In A Haystack 准确率达到 99%+, KV Cache显存占用减少 50%",
            ),
            (
                r"(幻觉|对齐|安全性|红队|准确率|GSM8K|MATH|评测)",
                "模型幻觉消除与垂直领域精度对齐",
                "基础开源模型在垂直专业领域回答准确率低、存在严重编造幻觉及指令跟随偏移，需要构建高质量DPO/RLHF与自动化红队评测流水线。",
                "通用基准(MMLU/GSM8K)对齐精度领先基线 5%+, 线上核心问答真实幻觉率 < 2%",
            ),
            (
                r"(集群稳定|万卡|千卡|故障恢复|断点续训|Checkpoint|MTBF|通信开销)",
                "超大规模集群训练稳定性与算力利用率(MFU)",
                "大规模分布式训练频繁遭遇硬件掉卡、慢节点卡顿与通信瓶颈，导致MFU低下与断点频繁重启，严重消耗昂贵GPU算力预算。",
                "千卡集群 MFU (Model FLOPs Utilization) > 45%, 自动故障检测与热重启时间 < 5分钟",
            ),
            (
                r"(Agent|工作流|调用成功率|复杂任务|工具调用|Function Call)",
                "多步长流程Agent任务规划与工具调用可靠性",
                "复杂多步任务中Agent容易陷入无限死循环、参数传递格式错误或意图解析漂移，无法达到企业级生产可用标准。",
                "复杂多工具调用端到端成功率 (Success Rate) > 92%, 意图分发准确率 > 95%",
            ),
        ]

        for pat, aspect, desc, metric in indicators:
            if re.search(pat, text, re.IGNORECASE):
                pain_points.append(
                    BusinessPainPoint(
                        aspect=aspect,
                        description=desc,
                        evaluation_metric=metric,
                    )
                )

        # Fallback if none explicitly detected
        if not pain_points:
            pain_points.append(
                BusinessPainPoint(
                    aspect="大模型工业化落地与生产可用性",
                    description="将离线前沿算法成果转化为稳定、高效、可度量的线上生产力，平衡技术先进性与商业落地ROI。",
                    evaluation_metric="算法迭代周期缩短30%，核心业务线上转化率/留存率提升 5%+",
                )
            )

        return pain_points
