"""
JD Matcher: Weighted matching with hard threshold veto, 5-state gap matrix, and breakthrough strategies.
"""

import re
from typing import List, Dict, Set, Tuple
from core.registry import AliasRegistry
from .models import (
    DecodedJD,
    CandidateProfile,
    MatcherResult,
    GapItem,
    GapState,
    HardThreshold,
    CoreSkill,
    CoreResponsibility,
    ImplicitSignal,
    SkillImportance,
)


class JDMatcher:
    """
    Evaluates Candidate alignment against a Decoded JD:
    - Base dimension weights are 0.6 / 0.2 / 0.2; absent JD dimensions are excluded and the remaining weights are normalized.
    - Single item score: 1.0 (Fully matched), 0.5 (Partially matched / adjacent), 0.0 (Unmatched)
    - Hard threshold veto rule (degree, years of experience, etc.) with automatic penalty and breakthrough advice
    - 5-State Gap Matrix:
      1. 已匹配 (Matched)
      2. 表达缺口 (Expression Gap)
      3. 证据不足 (Insufficient Evidence)
      4. 真实缺口 (Real Gap)
      5. 待确认 (To Be Confirmed)
    """

    DEGREE_RANK = {
        "博士": 4,
        "博士研究生": 4,
        "硕士": 3,
        "硕士研究生": 3,
        "本科": 2,
        "统招本科": 2,
        "大专": 1,
        "专科": 1,
        "高中及以下": 0,
    }

    # Adjacent / synonymous tech stack mapping
    ADJACENT_SKILLS: Dict[str, Set[str]] = {
        "vllm": {"tgi", "tensorrt-llm", "sglang", "triton server", "lightllm", "llm-serving", "推理加速"},
        "tensorrt-llm": {"vllm", "tgi", "triton", "fastertransformer"},
        "deepspeed": {"megatron-lm", "colossalai", "fsdp", "zero", "分布式训练"},
        "megatron-lm": {"deepspeed", "colossalai", "fsdp", "3d并行", "megatron"},
        "rlhf": {"dpo", "ppo", "grpo", "kto", "sft", "强化学习", "对齐"},
        "dpo": {"rlhf", "ppo", "grpo", "kto", "orpo", "sft"},
        "flashattention": {"flashattention-2", "flashattention-3", "pagedattention", "ringattention", "attention优化"},
        "pagedattention": {"vllm", "kv cache", "flashattention"},
        "cuda": {"triton", "c++", "kernel优化", "算子优化", "gpu编程"},
        "triton": {"cuda", "openai triton", "算子编写", "kernel"},
        "nccl": {"infiniband", "roce", "rdma", "分布式通信", "通信优化"},
        "langchain": {"llamaindex", "langgraph", "autogen", "agent", "智能体"},
        "rag": {"向量检索", "milvus", "qdrant", "pinecone", "chroma", "graphrag", "知识库"},
        "awq": {"gptq", "smoothquant", "int4", "fp8", "量化", "模型压缩"},
        # Backend & Distributed Messaging / Cache / Storage
        "kafka": {"rocketmq", "rabbitmq", "pulsar", "mq", "消息队列"},
        "rocketmq": {"kafka", "rabbitmq", "pulsar", "mq", "消息队列"},
        "rabbitmq": {"kafka", "rocketmq", "pulsar", "mq", "消息队列"},
        "redis": {"memcached", "tair", "kv存储", "分布式缓存", "缓存"},
        "mysql": {"postgresql", "tidb", "oceanbase", "polardb", "关系型数据库"},
        "postgresql": {"mysql", "tidb", "oceanbase", "pg", "关系型数据库"},
        "grpc": {"thrift", "rpc", "dubbo", "brpc", "微服务通信"},
        "springboot": {"spring", "spring boot", "springcloud", "spring cloud", "mybatis"},
        "spring boot": {"spring", "springboot", "springcloud", "spring cloud", "mybatis"},
        "fastapi": {"flask", "django", "tornado", "sanic", "python web"},
        "django": {"fastapi", "flask", "python web"},
        # Frontend & Engineering
        "react": {"vue", "next.js", "angular", "前端框架"},
        "vue": {"react", "nuxt.js", "vue3", "pinia"},
        "webpack": {"vite", "rollup", "rspack", "turbopack", "前端工程化"},
        "typescript": {"javascript", "ts", "js"},
        # Big Data & Real-time OLAP
        "flink": {"spark streaming", "storm", "实时计算", "流计算"},
        "spark": {"flink", "hadoop", "hive", "mapreduce", "分布式计算"},
        "clickhouse": {"starrocks", "doris", "druid", "olap", "实时数仓"},
        "starrocks": {"clickhouse", "doris", "olap", "实时数仓"},
        "doris": {"clickhouse", "starrocks", "olap", "实时数仓"},
        "hive": {"spark", "hadoop", "离线计算", "数据仓库"},
        # Cloud Native, DevOps & SRE
        "k8s": {"kubernetes", "docker", "containerd", "helm", "容器编排"},
        "kubernetes": {"k8s", "docker", "containerd", "helm", "容器编排"},
        "docker": {"containerd", "podman", "容器化"},
        "prometheus": {"grafana", "opentelemetry", "skywalking", "监控告警"},
        # Data Analytics & BI
        "tableau": {"powerbi", "looker", "finebi", "quickbi", "数据看板", "bi"},
        "powerbi": {"tableau", "looker", "finebi", "quickbi", "数据看板", "bi"},
        # Deep Learning Frameworks
        "pytorch": {"tensorflow", "jax", "paddlepaddle", "深度学习框架"},
        "tensorflow": {"pytorch", "jax", "paddlepaddle", "深度学习框架"},
    }

    def match(self, jd: DecodedJD, candidate: CandidateProfile) -> MatcherResult:
        """Execute comprehensive matching and gap analysis."""
        # 1. Hard Thresholds Verification (Veto check)
        is_vetoed, veto_reasons, breakthrough_advice = self._check_hard_thresholds(jd, candidate)

        # 2. Score Must-Have items
        must_have_items = [
            s for s in jd.core_skills
            if str(s.importance).upper() in (SkillImportance.MUST_HAVE.value, "MUST_HAVE", "MUST")
        ]
        # Include core responsibilities into must-have evaluation
        must_scores, must_gaps = self._evaluate_must_haves(must_have_items, jd.core_responsibilities, candidate)
        must_have_score = sum(must_scores) / max(len(must_scores), 1)

        # 3. Score Nice-To-Have items
        nice_have_items = [
            s for s in jd.core_skills
            if str(s.importance).upper() in (SkillImportance.NICE_TO_HAVE.value, "NICE_TO_HAVE", "NICE")
        ]
        if nice_have_items:
            nice_scores, nice_gaps = self._evaluate_skills(nice_have_items, candidate, default_importance="nice_to_have")
            nice_to_have_score = sum(nice_scores) / max(len(nice_scores), 1)
        else:
            # No preferred requirements should not create a fictitious perfect
            # match. It contributes neutrally to the weighted score.
            nice_to_have_score = 0.0
            nice_gaps = []

        # 4. Score Hidden Signals & Culture Fit
        hidden_score, signal_gaps = self._evaluate_hidden_signals(jd.implicit_signals, candidate)

        # Missing JD dimensions are unavailable, not successes or failures.
        dimensions = {
            "must_have": (0.6, must_have_score, bool(must_scores)),
            "nice_have": (0.2, nice_to_have_score, bool(nice_have_items)),
            "hidden_fit": (0.2, hidden_score, bool(jd.implicit_signals)),
        }
        total_weight = sum(weight for weight, _, present in dimensions.values() if present)
        dimension_weights = {
            name: weight / total_weight
            for name, (weight, _, present) in dimensions.items() if present
        }
        raw_match_score = round(sum(
            dimension_weights.get(name, 0.0) * value
            for name, (_, value, _) in dimensions.items()
        ), 4)

        # 6. Apply Hard Veto Penalty
        if is_vetoed:
            # Automatic score penalty: halved and capped at 0.45
            final_match_score = round(min(raw_match_score * 0.5, 0.45), 4)
        else:
            final_match_score = raw_match_score

        # 7. Aggregate 5-State Gap Matrix
        all_gaps: List[GapItem] = []
        # Add threshold gap items
        for th in jd.hard_thresholds:
            all_gaps.append(self._threshold_to_gap(th, candidate))
        all_gaps.extend(must_gaps)
        all_gaps.extend(nice_gaps)
        all_gaps.extend(signal_gaps)

        # Counts
        matched_count = sum(1 for g in all_gaps if g.state == GapState.MATCHED)
        expr_count = sum(1 for g in all_gaps if g.state == GapState.EXPRESSION_GAP)
        insuff_count = sum(1 for g in all_gaps if g.state == GapState.INSUFFICIENT_EVIDENCE)
        real_count = sum(1 for g in all_gaps if g.state == GapState.REAL_GAP)
        tbc_count = sum(1 for g in all_gaps if g.state == GapState.TO_BE_CONFIRMED)

        return MatcherResult(
            must_have_score=round(must_have_score, 4),
            nice_to_have_score=round(nice_to_have_score, 4),
            hidden_signal_fit=round(hidden_score, 4),
            raw_match_score=raw_match_score,
            final_match_score=final_match_score,
            is_hard_vetoed=is_vetoed,
            hard_veto_reasons=veto_reasons,
            breakthrough_advice=breakthrough_advice,
            gap_matrix=all_gaps,
            matched_count=matched_count,
            expression_gap_count=expr_count,
            insufficient_evidence_count=insuff_count,
            real_gap_count=real_count,
            to_be_confirmed_count=tbc_count,
            dimension_weights=dimension_weights,
            unavailable_dimensions=[name for name, (_, _, present) in dimensions.items() if not present],
        )

    def _check_hard_thresholds(
        self, jd: DecodedJD, candidate: CandidateProfile
    ) -> Tuple[bool, List[str], List[str]]:
        """Evaluate hard threshold gates: degree, years, major."""
        is_vetoed = False
        reasons: List[str] = []
        breakthrough: List[str] = []

        cand_degree_str = candidate.education_level.strip()
        cand_degree_rank = self.DEGREE_RANK.get(cand_degree_str)
        if cand_degree_rank is None:
            if "博士" in cand_degree_str or "ph.d" in cand_degree_str.lower():
                cand_degree_rank = 4
            elif "硕士" in cand_degree_str or "master" in cand_degree_str.lower():
                cand_degree_rank = 3
            elif "本" in cand_degree_str or "bachelor" in cand_degree_str.lower():
                cand_degree_rank = 2
            elif "专" in cand_degree_str:
                cand_degree_rank = 1
            else:
                cand_degree_rank = None

        for th in jd.hard_thresholds:
            if not th.is_mandatory:
                continue

            # Degree check
            if th.category == "education" and th.min_degree:
                req_rank = self.DEGREE_RANK.get(th.min_degree.strip())
                if cand_degree_rank is None or req_rank is None:
                    continue
                if cand_degree_rank < req_rank:
                    is_vetoed = True
                    reasons.append(
                        f"学历门槛拦截：岗位硬性要求 {th.requirement}，候选人当前学历为【{candidate.education_level}】。"
                    )
                    breakthrough.append(
                        "【学历破局通道】：顶尖大模型开源项目（GitHub 1k+ Stars）、国际顶会（NeurIPS/ICLR/ACL/KDD）代表作、或高含金量算法竞赛（Kaggle/天池）Top名次。以碾压级战绩绕过HR初筛，通过技术团队Leader或脉脉/知乎直推。"
                    )

            # Years check. Zero means the profile did not provide a value;
            # it must not be treated as an explicit zero-year claim.
            if th.category == "experience_years" and th.min_years:
                if candidate.years_of_experience <= 0:
                    continue
                if candidate.years_of_experience < th.min_years:
                    is_vetoed = True
                    reasons.append(
                        f"年限门槛拦截：岗位硬性要求 {th.requirement}，候选人累计经验仅为【{candidate.years_of_experience}年】。"
                    )
                    breakthrough.append(
                        "【年限破局通道】：在简历中用高密度实操复杂度抵消年限劣势（例如主导过千卡集群全流程预训练对齐、千万级DAU高并发Agent业务上线）；在自荐信/Cover Letter中开门见山说明个人交付产出已达高阶工程师水平，争取直面业务一轮主管。"
                    )

            # Major check
            if th.category == "major" and th.required_majors:
                cand_major = candidate.major.lower()
                major_match = any(m.lower() in cand_major for m in th.required_majors)
                if not major_match and th.is_mandatory:
                    is_vetoed = True
                    reasons.append(
                        f"专业背景门槛拦截：岗位要求 {th.requirement}，候选人专业为【{candidate.major}】。"
                    )
                    breakthrough.append(
                        "【专业跨界破局】：以纯正计算机系统底层与大模型硬核工程成果（如手写高性能CUDA算子、深入Megatron源码改造）消除非科班顾虑。"
                    )

        return is_vetoed, reasons, breakthrough

    def _threshold_to_gap(self, th: HardThreshold, candidate: CandidateProfile) -> GapItem:
        """Convert a hard threshold to a GapItem."""
        cand_degree_str = candidate.education_level.strip()
        cand_degree_rank = self.DEGREE_RANK.get(cand_degree_str)
        if cand_degree_rank is None:
            if "博士" in cand_degree_str or "ph.d" in cand_degree_str.lower():
                cand_degree_rank = 4
            elif "硕士" in cand_degree_str or "master" in cand_degree_str.lower():
                cand_degree_rank = 3
            elif "本" in cand_degree_str or "bachelor" in cand_degree_str.lower():
                cand_degree_rank = 2
            elif "专" in cand_degree_str:
                cand_degree_rank = 1
            else:
                cand_degree_rank = None

        if th.category == "education" and th.min_degree:
            req_rank = self.DEGREE_RANK.get(th.min_degree.strip())
            if cand_degree_rank is None or req_rank is None:
                return GapItem(
                    requirement_name=f"硬门槛-{th.requirement}",
                    category="threshold",
                    importance="mandatory",
                    state=GapState.TO_BE_CONFIRMED,
                    score=0.5,
                    candidate_evidence="候选人学历未提供，无法判断是否达标",
                    gap_explanation="缺少学历事实，不能按默认学历推断",
                    actionable_advice="补充真实学历与学位授予院校后再判断",
                )
            if cand_degree_rank >= req_rank:
                return GapItem(
                    requirement_name=f"硬门槛-{th.requirement}",
                    category="threshold",
                    importance="mandatory",
                    state=GapState.MATCHED,
                    score=1.0,
                    candidate_evidence=f"候选人学历为 {candidate.education_level}，符合或超越标准",
                    gap_explanation="学历背景符合硬性门槛",
                    actionable_advice="无需调整，保持真实填写即可",
                )
            else:
                return GapItem(
                    requirement_name=f"硬门槛-{th.requirement}",
                    category="threshold",
                    importance="mandatory",
                    state=GapState.REAL_GAP,
                    score=0.0,
                    candidate_evidence=f"候选人学历为 {candidate.education_level}",
                    gap_explanation=f"低于要求的 {th.requirement}",
                    actionable_advice="走开源代表作或业务主管直推破局通道，避开自动简历筛选",
                )

        if th.category == "experience_years" and th.min_years:
            if candidate.years_of_experience <= 0:
                return GapItem(
                    requirement_name=f"硬门槛-{th.requirement}",
                    category="threshold",
                    importance="mandatory",
                    state=GapState.TO_BE_CONFIRMED,
                    score=0.5,
                    candidate_evidence="候选人工作年限未提供，无法判断是否达标",
                    gap_explanation="缺少工作年限事实，不能按默认值推断",
                    actionable_advice="补充可核验的工作年限和相关经验范围后再判断",
                )
            if candidate.years_of_experience >= th.min_years:
                return GapItem(
                    requirement_name=f"硬门槛-{th.requirement}",
                    category="threshold",
                    importance="mandatory",
                    state=GapState.MATCHED,
                    score=1.0,
                    candidate_evidence=f"候选人工作年限 {candidate.years_of_experience}年",
                    gap_explanation="工作年限达标",
                    actionable_advice="保持当前时间线叙述清晰连贯",
                )
            else:
                return GapItem(
                    requirement_name=f"硬门槛-{th.requirement}",
                    category="threshold",
                    importance="mandatory",
                    state=GapState.REAL_GAP,
                    score=0.0,
                    candidate_evidence=f"候选人工作年限 {candidate.years_of_experience}年",
                    gap_explanation=f"少于要求的 {th.min_years}年",
                    actionable_advice="强化项目规模量化数据，重点突出超过普通年限的技术密度",
                )

        # Other thresholds (e.g. Major)
        return GapItem(
            requirement_name=f"门槛要求-{th.requirement}",
            category="threshold",
            importance="mandatory" if th.is_mandatory else "nice_to_have",
            state=GapState.MATCHED if th.category != "major" or any(m in candidate.major for m in th.required_majors) else GapState.EXPRESSION_GAP,
            score=1.0 if th.category != "major" or any(m in candidate.major for m in th.required_majors) else 0.5,
            candidate_evidence=f"候选人专业: {candidate.major}",
            gap_explanation="专业背景相关度检查",
            actionable_advice="在简历抬头清晰注明计算机相关课程或研究方向",
        )

    def _evaluate_must_haves(
        self,
        must_skills: List[CoreSkill],
        responsibilities: List[CoreResponsibility],
        candidate: CandidateProfile,
    ) -> Tuple[List[float], List[GapItem]]:
        """Evaluate must-have skills and core responsibilities."""
        scores: List[float] = []
        gaps: List[GapItem] = []

        # Skills evaluation
        skill_scores, skill_gaps = self._evaluate_skills(must_skills, candidate, default_importance="must_have")
        scores.extend(skill_scores)
        gaps.extend(skill_gaps)

        # Responsibilities evaluation
        for resp in responsibilities:
            score, gap = self._evaluate_single_responsibility(resp, candidate)
            scores.append(score)
            gaps.append(gap)

        return scores, gaps

    def _evaluate_skills(
        self,
        skills: List[CoreSkill],
        candidate: CandidateProfile,
        default_importance: str = "must_have",
    ) -> Tuple[List[float], List[GapItem]]:
        """Evaluate a list of skills against candidate profile."""
        scores: List[float] = []
        gaps: List[GapItem] = []

        cand_text = (
            candidate.raw_resume_text
            + "。\n"
            + "。\n".join(candidate.skills)
            + "。\n"
            + "。\n".join(candidate.project_descriptions)
        ).lower()

        for sk in skills:
            sk_lower = sk.name.lower()
            exact_match = AliasRegistry.claim_matches(sk.name, cand_text)

            if exact_match:
                # Check if evidence has metrics
                # Find the sentence containing the skill
                mention_sentences = [
                    s.strip() for s in re.split(r"[。\n;；]", cand_text) if AliasRegistry.claim_matches(sk.name, s)
                ]
                evidence_sentences = [
                    sent for sent in mention_sentences
                    if re.search(r"开发|设计|实现|搭建|部署|交付|维护|负责|编写|完成|修复|优化|建设|上线|build|built|develop|implement|deploy|deliver|maintain", sent)
                    and re.search(r"\d+%|\d+x|\d+\s*(?:qps|ms|token|万|亿|gb|tb|卡)|上线|交付|验收|采用|发布|合并|通过|报告|文档|系统|平台|服务|工具|接口|流程|测试|deployed|delivered|released|merged|adopted|service|report|test", sent)
                ]
                has_contextual_evidence = bool(evidence_sentences)
                chosen_sent = evidence_sentences[0] if evidence_sentences else (mention_sentences[0] if mention_sentences else "")

                if has_contextual_evidence:
                    # Fully matched
                    scores.append(1.0)
                    gaps.append(
                        GapItem(
                            requirement_name=f"技能-{sk.name}",
                            category="skill",
                            importance=sk.importance,
                            state=GapState.MATCHED,
                            score=1.0,
                            candidate_evidence=f"简历中提及【{sk.name}】并包含具体动作与结果/交付物: '{chosen_sent[:120]}'",
                            gap_explanation="当前材料包含实践上下文；属于材料支持，尚不等于外部核验",
                            actionable_advice="保留真实动作与交付物，准备说明个人负责范围及可核验来源；有可靠指标时再补充",
                        )
                    )
                else:
                    # A keyword or number alone is not evidence of practice.
                    scores.append(0.5)
                    gaps.append(
                        GapItem(
                            requirement_name=f"技能-{sk.name}",
                            category="skill",
                            importance=sk.importance,
                            state=GapState.INSUFFICIENT_EVIDENCE,
                            score=0.5,
                            candidate_evidence=f"简历中提及【{sk.name}】，但未识别到具体动作与结果/交付物",
                            gap_explanation="需要确认实践场景及个人贡献；缺少数字本身不构成能力缺口",
                            actionable_advice=f"请说明在哪项真实经历中使用 {sk.name}、本人做了什么、交付了什么，以及可核验来源；没有可靠数字时保留定性结果",
                        )
                    )
                continue

            # Check adjacent / synonymous skills
            adjacent_matches = []
            if sk_lower in self.ADJACENT_SKILLS:
                for adj in self.ADJACENT_SKILLS[sk_lower]:
                    if AliasRegistry.claim_matches(adj, cand_text):
                        adjacent_matches.append(adj)

            if adjacent_matches:
                # Expression gap
                scores.append(0.5)
                gaps.append(
                    GapItem(
                        requirement_name=f"技能-{sk.name}",
                        category="skill",
                        importance=sk.importance,
                        state=GapState.EXPRESSION_GAP,
                        score=0.5,
                        candidate_evidence=f"未直接提及【{sk.name}】，但具备强关联经验: 【{', '.join(adjacent_matches)}】",
                        gap_explanation=f"候选人具备相邻底层技术栈，但未针对性使用目标JD的标准行业术语",
                        actionable_advice=f"修改简历表述：将【{adjacent_matches[0]}】与【{sk.name}】联合叙述，明确说明技术迁移能力",
                    )
                )
                continue

            # Check if domain is somewhat touched
            is_possibly_covered = any(word in cand_text for word in ["算法", "模型", "深度学习", "训练", "推理"])

            if is_possibly_covered and sk.category in ["framework", "tool"]:
                # To be confirmed
                scores.append(0.5)
                gaps.append(
                    GapItem(
                        requirement_name=f"技能-{sk.name}",
                        category="skill",
                        importance=sk.importance,
                        state=GapState.TO_BE_CONFIRMED,
                        score=0.5,
                        candidate_evidence="简历有相近AI领域经验，但未明确该具体框架掌握深度",
                        gap_explanation="需要面试进一步确认候选人在该技术栈上的独立攻坚与调优深度",
                        actionable_advice=f"面试前突击梳理 {sk.name} 的核心底层设计与最佳实践，并准备1个技术对比分析回答",
                    )
                )
            else:
                # Real gap
                scores.append(0.0)
                gaps.append(
                    GapItem(
                        requirement_name=f"技能-{sk.name}",
                        category="skill",
                        importance=sk.importance,
                        state=GapState.REAL_GAP,
                        score=0.0,
                        candidate_evidence="简历未检索到该技能或任何相邻经验",
                        gap_explanation=f"存在真实技术栈缺失，可能成为技术复试的被动攻击点",
                        actionable_advice=f"制定速成补齐计划：在 GitHub 找 1 个基于 {sk.name} 的优质开源项目完整跑通一次并记录采坑日志",
                    )
                )

        return scores, gaps

    def _evaluate_single_responsibility(
        self, resp: CoreResponsibility, candidate: CandidateProfile
    ) -> Tuple[float, GapItem]:
        """Evaluate a single core responsibility against candidate profile."""
        cand_text = (
            candidate.raw_resume_text
            + " "
            + " ".join(candidate.project_descriptions)
        ).lower()

        keywords = [w for w in re.split(r"[^\w\+\#\-]+", resp.description) if len(w) >= 2]
        matched_kw = [kw for kw in keywords if kw.lower() in cand_text]

        match_ratio = len(matched_kw) / max(len(keywords), 1)

        if match_ratio >= 0.35:
            # Check if has quantifiable metrics
            if re.search(r"(\d+%\s*|\d+x\s*|\d+\s*(?:qps|ms|token|万|亿|gb|tb|卡))", cand_text):
                return 1.0, GapItem(
                    requirement_name=f"职责-{resp.title}",
                    category="responsibility",
                    importance="must_have",
                    state=GapState.MATCHED,
                    score=1.0,
                    candidate_evidence=f"命中核心职责关键词({len(matched_kw)}项): {', '.join(matched_kw[:5])}",
                    gap_explanation="与该职责对应的项目经历与业务场景契合度高",
                    actionable_advice="准备该经历的架构图与极端异常场景排查细节",
                )
            else:
                return 0.5, GapItem(
                    requirement_name=f"职责-{resp.title}",
                    category="responsibility",
                    importance="must_have",
                    state=GapState.INSUFFICIENT_EVIDENCE,
                    score=0.5,
                    candidate_evidence=f"包含相关方向表述，但缺乏可验证的度量指标",
                    gap_explanation="职责经历描述偏定性，缺少定量的数据支撑",
                    actionable_advice="在项目成果中加入对比基线、优化倍率和业务收益数字",
                )
        elif match_ratio >= 0.15:
            return 0.5, GapItem(
                requirement_name=f"职责-{resp.title}",
                category="responsibility",
                importance="must_have",
                state=GapState.EXPRESSION_GAP,
                score=0.5,
                candidate_evidence=f"部分匹配: {', '.join(matched_kw)}",
                gap_explanation="候选人有泛领域背景，但没有用目标JD的业务语言进行包装",
                actionable_advice="将原有项目的产出用该职责的业务词汇重新表述",
            )
        else:
            return 0.0, GapItem(
                requirement_name=f"职责-{resp.title}",
                category="responsibility",
                importance="must_have",
                state=GapState.REAL_GAP,
                score=0.0,
                candidate_evidence="无相近业务职责背景",
                gap_explanation="该核心职责在候选人过往履历中完全空缺",
                actionable_advice="坦承经验差异，但强调通用的系统设计抽象能力与极速学习迁移能力",
            )

    def _evaluate_hidden_signals(
        self, signals: List[ImplicitSignal], candidate: CandidateProfile
    ) -> Tuple[float, List[GapItem]]:
        """Evaluate candidate fit for implicit signals / big tech jargon."""
        if not signals:
            return 0.0, []

        scores: List[float] = []
        gaps: List[GapItem] = []
        cand_text = (
            candidate.raw_resume_text
            + " "
            + " ".join(candidate.project_descriptions)
        ).lower()

        for sig in signals:
            # Check candidate adaptability
            # If candidate shows ownership, startup, high throughput, zero-to-one
            has_fit = False
            if "0到1" in sig.original_text or "开拓" in sig.original_text:
                has_fit = any(k in cand_text for k in ["从0到1", "主导", "独立搭建", "架构设计", "初创", "从零"])
            elif "抗压" in sig.original_text or "压力" in sig.original_text:
                has_fit = any(k in cand_text for k in ["上线", "应急", "攻坚", "故障排查", "高并发", "保障"])
            elif "自驱" in sig.original_text:
                has_fit = any(k in cand_text for k in ["主动", "独立推进", "探索", "预研", "优化"])
            elif "商业化" in sig.original_text or "闭环" in sig.original_text:
                has_fit = any(k in cand_text for k in ["营收", "转化", "降本", "roi", "商业化", "日活", "dau"])
            else:
                # An unclassified signal is unknown, not proof of fit.
                has_fit = False

            if has_fit:
                scores.append(1.0)
                gaps.append(
                    GapItem(
                        requirement_name=f"隐性考核-{sig.original_text}",
                        category="signal",
                        importance="implicit",
                        state=GapState.MATCHED,
                        score=1.0,
                        candidate_evidence="过往经历体现出相应的自驱攻坚、业务闭环或抗压成果",
                        gap_explanation=f"能够较好适应【{sig.translated_meaning}】的工作节奏",
                        actionable_advice=sig.candidate_countermeasure,
                    )
                )
            else:
                scores.append(0.5)
                gaps.append(
                    GapItem(
                        requirement_name=f"隐性考核-{sig.original_text}",
                        category="signal",
                        importance="implicit",
                        state=GapState.TO_BE_CONFIRMED,
                        score=0.5,
                        candidate_evidence="履历偏向平稳规范研发，缺乏明显的极端攻坚或商业强背书印记",
                        gap_explanation=f"入职后可能面临【{sig.underlying_risk}】的潜在冲击",
                        actionable_advice=sig.candidate_countermeasure,
                    )
                )

        avg_score = sum(scores) / max(len(scores), 1)
        return round(avg_score, 4), gaps
