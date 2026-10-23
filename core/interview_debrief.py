"""
OfferGet Interview Debrief Engine (interview_debrief.py)
=========================================================
Implements Post-Interview Structured Reflection and Dynamic Knowledge-Base Feedback Loop:
1. Question & Answer Diagnosis:
   - Evaluates whether questions were answered with high clarity, partial defense, or fatal gap.
   - Diagnoses root causes: "Depth deficiency", "Metric unverified", "Expression deformation", "Scope mismatch".
2. Dynamic Defense Cheat Sheet Update:
   - Extracts newly encountered edge cases and pushes them directly into candidate defense cards.
3. Debrief Ledger:
   - Stores session notes, interviewer attitude signals, and next-round preparation points.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class QuestionDiagnosis(str, Enum):
    WELL_DEFENDED = "well_defended"            # 严密防守，依据充分且切题
    EXPERIENCE_BOUNDARY = "experience_boundary" # 诚实界定经验边界（明确说明没做过/不了解）
    EXPRESSION_GAP = "expression_gap"          # 实际做过但表达变形，缺少结构或量化来源
    DEPTH_DEFICIENT = "depth_deficient"        # 底层源码/数学推导缺乏储备
    METRIC_DRIFT = "metric_drift"              # 指标缺基线、数据来源或被事实门禁拦截
    FATAL_GAP = "fatal_gap"                    # 空回答或严重失实
    UNCERTAIN = "uncertain"                    # 答非所问或无法可靠核验


@dataclass
class DebriefQuestionItem:
    question: str
    candidate_answer: str
    interviewer_follow_up: str = ""
    diagnosis: QuestionDiagnosis = QuestionDiagnosis.WELL_DEFENDED
    analysis_zh: str = ""
    coaching_advice: str = ""
    revised_answer: str = ""
    refined_answer: str = ""
    key_takeaway: str = ""
    claim_refs: List[Dict[str, Any]] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    can_revise: bool = True
    verification_status: str = "unverified"
    defense_score: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.can_revise:
            self.revised_answer = ""
            self.refined_answer = ""
        else:
            if not self.refined_answer and self.revised_answer:
                self.refined_answer = self.revised_answer
            elif not self.revised_answer and self.refined_answer:
                self.revised_answer = self.refined_answer


@dataclass
class InterviewSessionDebrief:
    session_id: str
    target_company: str
    target_role: str
    interview_round: str  # e.g., "技术一面", "技术终面", "夏令营考核", "复试答辩"
    interview_date: str
    overall_confidence: int  # 1 to 5
    questions: List[DebriefQuestionItem] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    defense_updates: List[Dict[str, str]] = field(default_factory=list)


class InterviewDebriefEngine:
    """
    Analyzes interview questions/answers and generates actionable feedback loops.
    """

    @staticmethod
    def _is_tech_in_negative_context(text: str, tech_term: str) -> bool:
        """
        Checks whether all occurrences of a technology term in the text appear in
        negative/boundary contexts (e.g., '没用过 Redis', '未主导过 Redis', '对 Redis 不太了解').
        Returns True if the term is ONLY mentioned negatively (or not found),
        Returns False if there is at least one affirmative usage of the term (e.g. '用 Redis 实现').
        """
        if not text or not tech_term:
            return False

        if re.search(r"[\u4e00-\u9fa5]", tech_term):
            term_pattern = re.compile(re.escape(tech_term), re.IGNORECASE)
        else:
            term_pattern = re.compile(r"(?<![a-z0-9_])" + re.escape(tech_term) + r"(?![a-z0-9_])", re.IGNORECASE)

        matches = list(term_pattern.finditer(text))
        if not matches:
            return True

        delims = r"[，。；！？,.;!?\n]"
        for m in matches:
            start, end = m.start(), m.end()
            prev_text = text[:start]
            next_text = text[end:]

            last_delim = -1
            for dm in re.finditer(delims, prev_text):
                last_delim = dm.end()
            clause_start = last_delim if last_delim != -1 else 0

            next_m = re.search(delims, next_text)
            clause_end = end + next_m.start() if next_m else len(text)

            clause = text[clause_start:clause_end]
            term_start_in_clause = start - clause_start
            term_end_in_clause = end - clause_start

            pre_term = clause[:term_start_in_clause].strip()
            post_term = clause[term_end_in_clause:].strip()

            pre_neg_pattern = re.compile(
                r"(?:没(?:有)?(?:实际)?(?:怎么)?|未(?:曾)?(?:实际)?|不(?:太)?|从未|并未|无|缺少|缺乏)\s*"
                r"(?:在[^，。；;\n]{1,15}?(?:中|环境|里))?\s*"
                r"(?:用过|使用|接触(?:过)?|做过|主导(?:过)?|了解|涉及|涉猎|熟悉|学过|掌握|落地|配置|搭建|开发|维护)?\s*"
                r"(?:比如|例如|像)?\s*$",
                re.IGNORECASE,
            )
            post_neg_pattern = re.compile(
                r"^(?:这块|方面|相关|技术|本身)?\s*(?:在[^，。；;\n]{1,15}?(?:中|环境|里))?\s*(?:我)?\s*(?:之前|平时|暂时)?\s*"
                r"(?:没做过|未做过|没用过|未使用|没有用过|不了解|不太了解|不太熟悉|不熟悉|接触较少|没有实际做过|未涉猎|未主导过|未涉及|没有经验)",
                re.IGNORECASE,
            )
            en_neg_pattern = re.compile(
                r"\b(?:never|not|haven't|hasn't|hadn't|didn't|don't|without|no)\s+"
                r"(?:used?|have\s+used|experienced?|familiar\s+with|worked\s+with)?\s*$",
                re.IGNORECASE,
            )

            is_neg = bool(
                pre_neg_pattern.search(pre_term)
                or post_neg_pattern.search(post_term)
                or en_neg_pattern.search(pre_term)
                or ("对" in pre_term and any(nk in post_term for nk in ("不了解", "不太了解", "不熟悉", "不太熟悉")))
            )

            if not is_neg:
                return False

        return True

    def _create_conservative_revision(
        self,
        answer: str,
        drifts: List[Dict[str, Any]],
        unverified: List[Dict[str, Any]],
        fact_guard: Optional[Any] = None,
    ) -> str:
        """Removes or qualifies ungrounded numbers from candidate answer while preserving supported statements."""
        revised = answer
        for u in unverified:
            # Skip non-numeric tech/method unverified claims — replacing a tech term
            # with a numeric qualifier message is semantically nonsensical.
            if u.get("claim_type") == "tech_method":
                continue
            claimed = u.get("claimed_metric", "")
            if claimed:
                pattern = re.compile(
                    rf"(?:(?:从而|进而|导致|使得|进而导致|从而使得|带来|进而带来)\s*)*"
                    rf"((?:[^\s，。；;\n]{{0,10}}?\s*)?)"
                    rf"(?:大幅|显著|极大)?\s*(?:提升|降低|减少|提高|优化|下降)?\s*(?:了)?\s*"
                    rf"{re.escape(str(claimed))}%?",
                    re.IGNORECASE,
                )
                def _replace_unverified(match):
                    noun = match.group(1).strip() if match.group(1) else ""
                    qualifier = "（具体幅度因未提供基线数据不作主观量化）"
                    if noun in {"我", "我们", "团队", "本人", "大家"}:
                        noun = f"{noun}相关指标"
                    if noun:
                        return f"{noun}{qualifier}"
                    return qualifier
                revised = pattern.sub(_replace_unverified, revised)
        for d in drifts:
            claimed = d.get("claimed_metric", "")
            verified = d.get("verified_baseline", "")
            if claimed and verified:
                pattern = re.compile(re.escape(str(claimed)), re.IGNORECASE)
                revised = pattern.sub(f"{verified}（已核验基线）", revised)

        # R4-03: Moderate unsupported lead actions (unless verified in profile)
        profile_has_lead = False
        if fact_guard is not None:
            profile_has_lead = "主导" in getattr(fact_guard, "profile_all_text", "")
        if not profile_has_lead:
            revised = re.sub(r"由我主导", "由我负责", revised)
            revised = re.sub(r"我主导了", "我负责了", revised)
            revised = re.sub(r"我主导", "我负责", revised)
            revised = re.sub(r"(?<!未)(?<!没)主导了", "负责了", revised)
            revised = re.sub(r"(?<!未)(?<!没)主导", "负责", revised)

        return revised

    def analyze_question(
        self,
        question: str,
        answer: str,
        follow_up: str = "",
        fact_guard: Optional[Any] = None,
        claim_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> DebriefQuestionItem:
        """
        Classifies interview Q&A performance and generates diagnosis.
        """
        answer = answer if isinstance(answer, str) else ""
        claim_refs = claim_refs or []
        q_lower = question.lower()
        a_lower = answer.lower()
        missing_elements: List[str] = []
        follow_up_questions: List[str] = []

        # Unit regex matching for metrics (ISSUE-08: strict word boundary, no single 's')
        unit_metric_pattern = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:s|ms|min|h)\b|\b(?:ms|min|h)\b|\b[sS]\b",
            re.IGNORECASE,
        )
        has_metrics = (
            any(marker in a_lower or marker in answer for marker in ("%", "qps", "tps", "提升", "降低", "提高", "减少", "优化了", "倍", "小时", "卡", "stars"))
            or bool(unit_metric_pattern.search(answer))
        )

        # Strict baseline pattern matching (ISSUE-08: strict baseline regex, no isolated '从')
        baseline_pattern = re.compile(
            r"(?:baseline|基线|基准)"
            r"|(?:从|由)\s*[^，。；;\n]{1,30}?\s*(?:到|至|压减到|压减至|降至|降到|提升至|提升到|提高至|提高到)"
            r"|(?:对比|相比|相较于?)\s*[^，。；;\n]{1,20}?(?:原|旧|之前|历史|过去|baseline|基线)",
            re.IGNORECASE,
        )
        has_baseline = bool(baseline_pattern.search(answer))

        if not any(marker in answer for marker in ("我", "本人", "个人", "负责", "参与", "协同", "团队", "主导", "牵头")):
            missing_elements.append("个人贡献与团队边界")
            follow_up_questions.append("你本人具体负责哪一段链路？团队其他成员分别负责什么？")
        if has_metrics:
            if not has_baseline:
                missing_elements.append("指标基线")
                follow_up_questions.append("该指标的 baseline、单位、统计周期和数据来源是什么？")
            if not any(marker in answer for marker in ("周期", "日志", "看板", "压测", "数据来源", "评测集")):
                missing_elements.append("指标来源与统计口径")
                follow_up_questions.append("这组数字来自哪份日志、看板或评测集，统计窗口多长？")
        if not any(marker in answer for marker in ("失败", "复盘", "取舍", "限制", "边界", "不足", "事故")):
            missing_elements.append("限制或失败复盘")
            follow_up_questions.append("该方案在哪些场景会失效？你经历过什么失败并如何修正？")

        # Check boundary indicators (ISSUE-05: distinguish pure boundary from multi-claim with metrics)
        boundary_markers = (
            "没做过", "未做过", "没用过", "未使用", "没有用过", "没有做过",
            "未接触", "没接触过", "从未用过", "从未接触", "未曾使用", "并未用过",
            "不了解", "不太了解", "并不了解", "不熟悉", "不太熟悉",
            "不会", "未涉猎", "未主导过", "未主导", "没有实际做过", "接触较少",
            "没怎么用过", "没有这方面经验", "未涉及", "未深入", "没有深入",
        )
        is_boundary = any(m in answer for m in boundary_markers)
        is_pure_boundary = is_boundary and not has_metrics

        # Relevance heuristic (ISSUE-06: core examination terms of the question)
        q_stopwords = {
            "请问", "请谈", "谈谈", "介绍", "如何", "怎么", "什么", "以及", "通过", "进行",
            "针对", "基于", "可以", "说说", "简述", "描述", "阐述", "分析", "解释", "为什么",
            "哪些", "哪种", "是否", "有没有", "掌握", "熟悉", "了解", "具体", "这是", "对于",
            "关于", "你的", "你们", "项目中", "实际", "工作中", "遇到", "解决", "处理", "情况",
            "怎么做", "考查", "意图", "重点", "问题", "回答", "一下", "怎样"
        }
        tech_vocab = {
            "架构", "性能", "优化", "调优", "加速", "耗时", "集群", "模型", "训练", "推理", "通信", "接口", "数据库",
            "并发", "内存", "显存", "延迟", "吞吐", "吞吐量", "算法", "系统",
            "模块", "方案", "实现", "设计", "sql", "redis", "vllm", "nccl", "python", "cuda",
            "sqlite", "mysql", "postgresql", "kafka", "mq", "rpc", "grpc", "http", "tcp", "udp",
            "缓存", "索引", "分库", "分表", "锁", "事务", "死锁", "协程", "线程", "进程",
            "算子", "梯度", "反向传播", "微调", "量化", "剪枝", "蒸馏", "lora", "sft", "deepspeed", "megatron",
            "kv", "cache", "attention", "transformer", "p99", "qps", "tps", "显存占用",
            "流水线", "调度", "负载均衡", "容灾", "高可用", "故障", "排查", "压测", "基线", "监控",
            "网关", "路由", "微服务", "服务治理", "降级", "熔断", "限流", "幂等", "一致性", "分布式",
            "击穿", "雪崩", "穿透", "分片", "分词", "召回", "排序", "重排", "精排", "向量", "嵌入"
        }
        q_tech_terms = {k for k in tech_vocab if k in q_lower or k in question}
        q_en_terms = {
            w for w in re.findall(r"[a-z0-9+#.\-]+", q_lower)
            if len(w) >= 2 and w not in q_stopwords
        }
        q_zh_candidates = set()
        for chunk in re.split(r"[^一-鿿]+", question):
            chunk = chunk.strip()
            if len(chunk) >= 2 and chunk not in q_stopwords:
                q_zh_candidates.add(chunk)
                if len(chunk) > 2:
                    for i in range(len(chunk) - 1):
                        sub = chunk[i:i+2]
                        if sub not in q_stopwords:
                            q_zh_candidates.add(sub)

        # Domain concept expansion for question core terms
        perf_keywords = {"性能", "优化", "调优", "加速", "耗时", "延迟", "吞吐", "吞吐量"}
        if any(pk in q_lower or pk in question for pk in perf_keywords):
            q_tech_terms.update({"性能", "优化", "调优", "加速", "耗时", "延迟", "吞吐", "吞吐量", "显存", "qps", "tps", "p99", "压测", "基线"})

        db_keywords = {"数据库", "sql", "查询", "sqlite", "mysql", "postgresql"}
        if any(dk in q_lower or dk in question for dk in db_keywords):
            q_tech_terms.update({"数据库", "sql", "查询", "sqlite", "mysql", "postgresql", "索引", "事务", "表"})

        q_core_terms = q_tech_terms | q_en_terms | q_zh_candidates

        # Gap/transfer questions: interviewer asks candidate to honestly state gap and present adjacent/transferable experience
        is_gap_transfer_question = any(gk in question for gk in ("相邻经验", "可迁移能力", "可迁移", "迁移能力", "底层能力可迁移", "缺口"))

        # Check relevance (ISSUE-06: must relate to question's core terms, not arbitrary irrelevant tech words)
        matches_q_core = any(term in a_lower or term in answer for term in q_core_terms) if q_core_terms else True
        if matches_q_core:
            is_relevant = True
        elif is_gap_transfer_question:
            # For gap/transfer questions, candidate provides adjacent technical experience
            has_substantive_tech = any(k in a_lower for k in ("nccl", "vllm", "cuda", "redis", "sql", "模型", "架构", "接口", "探针", "心跳", "分布式", "训练", "推理"))
            is_relevant = (has_substantive_tech and (has_baseline or has_metrics)) or is_pure_boundary
        else:
            is_relevant = False

        can_revise = True
        verification_status = "unverified"

        # Heuristics for diagnosis
        if not answer.strip():
            diagnosis = QuestionDiagnosis.FATAL_GAP
            analysis = "未提供回答。无法评估对该题目的掌握程度与实际经历。"
            coaching = "请结合真实项目或基础技术积累，按 STAR 框架组织作答。"
            refined = ""
            can_revise = False
            takeaway = "技术面试避免交白卷，可从基础原理切入。"
        elif is_pure_boundary:
            # ISSUE-05: Pure boundary without other quantified claims is classified as EXPERIENCE_BOUNDARY
            diagnosis = QuestionDiagnosis.EXPERIENCE_BOUNDARY
            analysis = "诚实界定个人经验边界，明确未在实际项目中主导该技术。技术面试中坦陈边界优于编造经历；建议在此基础上说明底层相通机制与快速学习迁移能力。"
            coaching = "坦诚说明未在实际项目中主导过该技术，避免强行推测细节；可说明所掌握的相通底层原理（如有），并阐述面对未知技术时的调研路径与攻坚方法。"
            refined = ""
            can_revise = False
            takeaway = "诚实说明经验边界，重点展示基础功底与学习迁移路径。"
        elif not is_relevant:
            # ISSUE-07: Removed len < 80 bypass. Any irrelevant answer is UNCERTAIN.
            diagnosis = QuestionDiagnosis.UNCERTAIN
            analysis = "回答内容与题目考查的核心技术点缺乏语义关联，未正面作答。无法可靠判断技术深度与真实经历。"
            coaching = "请围绕题目关注的核心技术点（如架构选型、实现方案、指标基线与故障排查）进行正面阐述。"
            refined = ""
            can_revise = False
            takeaway = "正面回答题目考查要点，避免答非所问。"
        elif any(k in q_lower or k in question for k in ["源码", "推导", "公式", "底层原理", "算子内核", "原语实现"]) and len(answer) < 35:
            diagnosis = QuestionDiagnosis.DEPTH_DEFICIENT
            analysis = "面试官直击底层实现与推导细节，但回答偏向宏观 API 描述，深度明显不足。"
            coaching = "建议深入到底层通信原语、内存/显存数据结构、算子实现细节或数学推导，展示硬核功底。"
            refined = answer
            takeaway = "面试前务必提前推导核心算子与底层机制。"
        elif has_metrics and not has_baseline:
            diagnosis = QuestionDiagnosis.METRIC_DRIFT
            analysis = "提及量化收益但未同步提供基线（Baseline），缺少对比基准与统计口径，易触发追问。"
            coaching = "在回答指标时，严格遵循：'基线口径 -> 优化手段 -> 结果提升 -> 统计周期与数据来源'。"
            refined = answer
            takeaway = "所有数字必须自带 Baseline，杜绝伪精确。"
        else:
            diagnosis = QuestionDiagnosis.WELL_DEFENDED
            analysis = "回答逻辑连贯，表述切题且具备因果推导。"
            coaching = "保持严谨客观的表达节奏，准备好应对面试官关于边界条件和极限场景的深挖追问。"
            refined = answer
            takeaway = "表现稳定，注意保持数据与口径一致性。"

        # Fact Guard verification (ISSUE-05: do not skip when boundary statement exists alongside other claims)
        if fact_guard is not None and answer.strip():
            guard_result = fact_guard.verify_facts(answer)
            drifts = guard_result.get("drifts", [])
            raw_unverified = guard_result.get("unverified_claims", [])

            # R4-02: Filter out tech_method claims in negative / boundary contexts
            unverified: List[Dict[str, Any]] = []
            for u in raw_unverified:
                if u.get("claim_type") == "tech_method":
                    term = u.get("claimed_metric", "") or u.get("claimed_fact", "")
                    if self._is_tech_in_negative_context(answer, term):
                        continue
                unverified.append(u)

            has_fact_issues = bool(drifts) or bool(unverified)
            if has_fact_issues:
                diagnosis = QuestionDiagnosis.METRIC_DRIFT
                drift_notes = []
                for d in drifts:
                    drift_notes.append(f"声称 {d.get('claimed_metric')}，但底稿基线为 {d.get('verified_baseline')}")
                for u in unverified:
                    if u.get("claim_type") == "tech_method":
                        drift_notes.append(f"声称技术/方法 {u.get('claimed_metric')} 缺少底稿依据")
                    else:
                        drift_notes.append(f"声称指标 {u.get('claimed_metric')} 缺少底稿依据")
                analysis = f"回答中的技术栈或指标未通过事实核验（{'; '.join(drift_notes)}），易被判定为经历存疑或口径不实。"
                coaching = "回答涉及的技术与指标必须严格基于底稿真实基线与经历；未在底稿中核验的技术栈不建议主观声称具备实际落地经验；若未在底稿中提供严密基线或监控数据，应客观陈述方案本身，不建议主观推定具体提升幅度。"
                takeaway = "先核对事实底稿，再回答数字与技术经历问题。"
                refined = self._create_conservative_revision(answer, drifts, unverified, fact_guard=fact_guard)
                can_revise = True
            else:
                if not is_pure_boundary and is_relevant:
                    verification_status = "verified"

        # Incremental fact check on refined_answer
        if fact_guard is not None and refined and refined.strip():
            rev_guard = fact_guard.verify_facts(refined)
            if not rev_guard.get("passed", False):
                rev_drifts = rev_guard.get("drifts", [])
                raw_rev_unverified = rev_guard.get("unverified_claims", [])

                rev_unverified: List[Dict[str, Any]] = []
                for u in raw_rev_unverified:
                    if u.get("claim_type") == "tech_method":
                        term = u.get("claimed_metric", "") or u.get("claimed_fact", "")
                        if self._is_tech_in_negative_context(refined, term):
                            continue
                    rev_unverified.append(u)

                has_numeric_issues = bool(rev_drifts) or any(
                    u.get("claim_type") != "tech_method" for u in rev_unverified
                )
                has_affirmative_tech = any(
                    u.get("claim_type") == "tech_method" for u in rev_unverified
                )

                if has_numeric_issues:
                    refined = ""
                    can_revise = False
                    verification_status = "revision_failed_fact_check"
                elif has_affirmative_tech:
                    # R4-02: Affirmative unverified tech must NOT be exempted or marked as verified
                    verification_status = "tech_unverified"
                else:
                    # Only negative tech context remained, which is benign
                    verification_status = "verified"
            else:
                verification_status = "verified"

        # ISSUE-04: refined_answer and revised_answer must be empty if cannot revise, never use coaching_advice
        final_revised = refined if can_revise else ""

        # M3: Evaluate against 100-point defense rubric
        from core.defense.evaluator import DefenseEvaluator
        defense_eval = DefenseEvaluator.evaluate(question, answer)
        defense_score_dict = defense_eval.to_dict()
        for p in defense_eval.main_problems:
            if p not in missing_elements:
                missing_elements.append(p)

        return DebriefQuestionItem(
            question=question,
            candidate_answer=answer,
            interviewer_follow_up=follow_up,
            diagnosis=diagnosis,
            analysis_zh=analysis,
            coaching_advice=coaching,
            revised_answer=final_revised,
            refined_answer=final_revised,
            key_takeaway=takeaway,
            claim_refs=claim_refs,
            missing_elements=list(dict.fromkeys(missing_elements)),
            follow_up_questions=list(dict.fromkeys(follow_up_questions)),
            can_revise=can_revise,
            verification_status=verification_status,
            defense_score=defense_score_dict,
        )

    def generate_session_debrief(
        self,
        company: str,
        role: str,
        round_name: str,
        qa_pairs: List[Dict[str, str]],
        confidence: int = 4
    ) -> InterviewSessionDebrief:
        """
        Processes full session and generates dynamic defense updates.
        """
        now_str = datetime.now().strftime("%Y-%m-%d")
        session_id = f"DEBRIEF-{company}-{round_name}-{now_str}"

        analyzed_questions = []
        action_items = []
        defense_updates = []

        for pair in qa_pairs:
            q = pair.get("question", "")
            a = pair.get("answer", "")
            fu = pair.get("follow_up", "")
            item = self.analyze_question(q, a, fu)
            analyzed_questions.append(item)

            if item.diagnosis in [QuestionDiagnosis.DEPTH_DEFICIENT, QuestionDiagnosis.METRIC_DRIFT, QuestionDiagnosis.EXPRESSION_GAP]:
                action_items.append(f"针对 [{item.question[:20]}...]：{item.key_takeaway}")
                defense_updates.append({
                    "trigger_question": item.question,
                    "defense_strategy": item.refined_answer,
                    "risk_warning": item.analysis_zh
                })

        return InterviewSessionDebrief(
            session_id=session_id,
            target_company=company,
            target_role=role,
            interview_round=round_name,
            interview_date=now_str,
            overall_confidence=confidence,
            questions=analyzed_questions,
            action_items=action_items,
            defense_updates=defense_updates
        )


# ============================================================================
# Real-world Long Transcript Parsing & Post-Interview Debrief Engine
# ============================================================================

from core.defense.evaluator import DefenseEvaluator


@dataclass
class InterviewDialogueTurn:
    """代表面试实录中的一轮对话"""
    turn_id: int
    interviewer_question: str
    candidate_answer: str
    interviewer_challenge: str = ""
    intent_category: str = "通用技术考察"
    blindspots: List[str] = field(default_factory=list)
    metric_anomalies: List[str] = field(default_factory=list)
    omitted_key_mechanisms: List[str] = field(default_factory=list)
    turn_score: float = 80.0
    safe_response_guidance: str = ""
    verdict: str = "pass"  # "pass", "warning", "gap"


@dataclass
class NextRoundChecklist:
    """(N+1) 面针对性备战清单与综合诊断"""
    session_title: str
    target_role: str
    total_turns: int
    weak_turns_count: int
    next_round_readiness_score: float
    blindspot_summary: List[str] = field(default_factory=list)
    high_frequency_follow_ups: List[str] = field(default_factory=list)
    mandatory_metrics_to_memorize: List[str] = field(default_factory=list)
    failure_contingency_scripts: List[Dict[str, str]] = field(default_factory=list)
    dialogue_turns: List[InterviewDialogueTurn] = field(default_factory=list)
    markdown_report: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TranscriptParser:
    """面试实录长文本切分器"""

    INTERVIEWER_PREFIXES = [
        r"^(?:面试官|提问|考官|主管|Leader|Interviewer|Q\d*|问)(?:[:：\s]|\b)",
    ]
    CANDIDATE_PREFIXES = [
        r"^(?:候选人|我|应聘者|答辩人|Candidate|A\d*|答)(?:[:：\s]|\b)",
    ]

    @classmethod
    def parse(cls, transcript_text: str) -> List[InterviewDialogueTurn]:
        """将非结构化面试录音/文本整理为标准轮次列表"""
        lines = [line.strip() for line in transcript_text.strip().splitlines() if line.strip()]
        if not lines:
            return []

        turns: List[InterviewDialogueTurn] = []
        curr_turn_id = 1
        curr_q = ""
        curr_a = ""
        curr_speaker = None

        interviewer_pattern = re.compile("|".join(cls.INTERVIEWER_PREFIXES), re.IGNORECASE)
        candidate_pattern = re.compile("|".join(cls.CANDIDATE_PREFIXES), re.IGNORECASE)

        for line in lines:
            m_interviewer = interviewer_pattern.match(line)
            m_candidate = candidate_pattern.match(line)

            if m_interviewer:
                if curr_q and curr_a:
                    turns.append(
                        InterviewDialogueTurn(
                            turn_id=curr_turn_id,
                            interviewer_question=curr_q.strip(),
                            candidate_answer=curr_a.strip(),
                        )
                    )
                    curr_turn_id += 1
                    curr_q = ""
                    curr_a = ""
                cleaned_line = interviewer_pattern.sub("", line).strip()
                curr_q = cleaned_line
                curr_speaker = "interviewer"
            elif m_candidate:
                cleaned_line = candidate_pattern.sub("", line).strip()
                curr_a = cleaned_line
                curr_speaker = "candidate"
            else:
                if curr_speaker == "candidate":
                    curr_a = f"{curr_a}\n{line}" if curr_a else line
                elif curr_speaker == "interviewer":
                    curr_q = f"{curr_q}\n{line}" if curr_q else line
                else:
                    curr_q = line
                    curr_speaker = "interviewer"

        if curr_q:
            turns.append(
                InterviewDialogueTurn(
                    turn_id=curr_turn_id,
                    interviewer_question=curr_q.strip(),
                    candidate_answer=curr_a.strip(),
                )
            )

        return turns


class PostInterviewDebriefEngine:
    """真实面试长文本复盘与 (N+1) 面备战清单引擎"""

    INTENT_KEYWORDS = {
        "高并发与分布式架构": ["高并发", "qps", "分布式", "微服务", "分库分表", "kafka", "mq", "熔断", "降级"],
        "数据库与存储性能": ["mysql", "redis", "索引", "事务", "锁", "缓存", "一致性", "b+树", "持久化"],
        "系统底层与网络": ["tcp", "http", "三次握手", "epoll", "io多路复用", "内存泄漏", "gc", "goroutine"],
        "业务设计与架构权衡": ["架构设计", "业务重构", "选型", "成本", "trade-off", "演进", "可用性"],
        "团队协作与工程质量": ["上线", "排障", "监控", "故障", "ci/cd", "测试", "代码规范"],
    }

    @classmethod
    def _detect_intent(cls, question: str) -> str:
        q_lower = question.lower()
        for category, kws in cls.INTENT_KEYWORDS.items():
            if any(kw in q_lower for kw in kws):
                return category
        return "专业深度与综合能力"

    @classmethod
    def debrief(
        cls,
        transcript_text: str,
        target_role: str = "后端开发工程师",
        session_title: str = "真实面试复盘",
        profile_evidence_index: Optional[Dict[str, Any]] = None,
    ) -> NextRoundChecklist:
        """执行长文本面试复盘，生成针对下一轮的备战清单"""
        turns = TranscriptParser.parse(transcript_text)
        if not turns:
            return NextRoundChecklist(
                session_title=session_title,
                target_role=target_role,
                total_turns=0,
                weak_turns_count=0,
                next_round_readiness_score=0.0,
                markdown_report="# 面试复盘报告\n未解析到有效的面试对话轮次，请检查文本格式。",
            )

        weak_turns_count = 0
        all_blindspots: List[str] = []
        follow_ups: List[str] = []
        metrics_to_memorize: List[str] = []
        contingency_scripts: List[Dict[str, str]] = []
        turn_scores: List[float] = []

        for turn in turns:
            turn.intent_category = cls._detect_intent(turn.interviewer_question)

            eval_res = DefenseEvaluator.evaluate(
                question=turn.interviewer_question,
                answer=turn.candidate_answer,
            )
            turn.turn_score = eval_res.total_score
            turn.safe_response_guidance = eval_res.safe_answer
            turn_scores.append(eval_res.total_score)

            if eval_res.total_score < 70.0:
                turn.verdict = "gap"
                weak_turns_count += 1
            elif eval_res.total_score < 85.0:
                turn.verdict = "warning"
            else:
                turn.verdict = "pass"

            for prob in eval_res.main_problems:
                turn.blindspots.append(prob)
                all_blindspots.append(f"[第{turn.turn_id}轮] {prob}")

            numbers_found = re.findall(r"\d+(?:\.\d+)?(?:%|％|w|k|ms|s|qps|tps|mb|gb)?", turn.candidate_answer, re.IGNORECASE)
            for num in numbers_found:
                num = num.strip()
                if not num or (num.isdigit() and len(num) == 4 and (1990 <= int(num) <= 2030)):
                    continue
                if any(c.isdigit() for c in num):
                    metrics_to_memorize.append(f"参数口径核实: {num}（原问题: {turn.interviewer_question[:25]}...）")

            if profile_evidence_index:
                for word in ["架构重构", "全链路压测", "自研内核", "百亿级", "零故障"]:
                    if word in turn.candidate_answer and word not in profile_evidence_index.get("keywords", []):
                        turn.metric_anomalies.append(f"词汇「{word}」在底层经历底稿中缺乏硬性支撑")

            if turn.verdict in ("gap", "warning"):
                follow_up_q = f"针对【{turn.intent_category}】：请详细阐明「{turn.interviewer_question[:30]}」在极端高压场景下的熔断兜底策略与量化基线？"
                follow_ups.append(follow_up_q)
                contingency_scripts.append({
                    "turn_id": str(turn.turn_id),
                    "original_question": turn.interviewer_question,
                    "safe_script": turn.safe_response_guidance,
                })

        avg_score = sum(turn_scores) / len(turn_scores) if turn_scores else 0.0

        unique_blindspots = list(dict.fromkeys(all_blindspots))
        unique_follow_ups = list(dict.fromkeys(follow_ups))
        unique_metrics = list(dict.fromkeys(metrics_to_memorize))

        md_lines = [
            f"# 🎯 面试全复盘战报与 (N+1) 面备战清单",
            f"- **复盘主题**: {session_title}",
            f"- **目标岗位**: {target_role}",
            f"- **总对话轮次**: {len(turns)} 轮",
            f"- **薄弱/待加固轮次**: {weak_turns_count} 轮",
            f"- **下一轮面试就绪度预估分**: {avg_score:.1f} / 100",
            "",
            "## 1. 核心技术盲区梳理",
        ]
        if unique_blindspots:
            for bp in unique_blindspots[:5]:
                md_lines.append(f"- ⚠️ {bp}")
        else:
            md_lines.append("- ✅ 全场防守严密，未暴露明显事实与表达漏洞。")

        md_lines.extend([
            "",
            "## 2. (N+1) 面预计高频追问预测",
        ])
        if unique_follow_ups:
            for fu in unique_follow_ups[:4]:
                md_lines.append(f"- ❓ {fu}")
        else:
            md_lines.append("- 💡 下一轮面试官预计将侧重业务大局观与系统演化落地。")

        md_lines.extend([
            "",
            "## 3. 必背量化参数与指标口径核验",
        ])
        if unique_metrics:
            for met in unique_metrics[:5]:
                md_lines.append(f"- 📊 {met}")
        else:
            md_lines.append("- ℹ️ 建议在后续作答中主动引入基线数字（如优化前 vs 优化后对比）。")

        md_lines.extend([
            "",
            "## 4. 薄弱环节 5 步安全答题预案",
        ])
        for script_info in contingency_scripts[:3]:
            md_lines.extend([
                f"### [第{script_info['turn_id']}轮] {script_info['original_question']}",
                f"```text\n{script_info['safe_script']}\n```",
                "",
            ])

        markdown_report = "\n".join(md_lines).strip()

        return NextRoundChecklist(
            session_title=session_title,
            target_role=target_role,
            total_turns=len(turns),
            weak_turns_count=weak_turns_count,
            next_round_readiness_score=round(avg_score, 1),
            blindspot_summary=unique_blindspots,
            high_frequency_follow_ups=unique_follow_ups,
            mandatory_metrics_to_memorize=unique_metrics,
            failure_contingency_scripts=contingency_scripts,
            dialogue_turns=turns,
            markdown_report=markdown_report,
        )


__all__ = [
    "QuestionDiagnosis",
    "DebriefQuestionItem",
    "InterviewSessionDebrief",
    "InterviewDebriefEngine",
    "InterviewDialogueTurn",
    "NextRoundChecklist",
    "TranscriptParser",
    "PostInterviewDebriefEngine",
]
