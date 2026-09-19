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

import json
import re
from dataclasses import dataclass, field, asdict
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
    verification_status: str = "verified"

    def __post_init__(self):
        if not self.refined_answer:
            self.refined_answer = self.revised_answer or self.coaching_advice
        elif not self.revised_answer and self.can_revise:
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

    def _create_conservative_revision(
        self,
        answer: str,
        drifts: List[Dict[str, Any]],
        unverified: List[Dict[str, Any]],
    ) -> str:
        """Removes or qualifies ungrounded numbers from candidate answer while preserving supported statements."""
        revised = answer
        for u in unverified:
            claimed = u.get("claimed_metric", "")
            if claimed:
                pattern = re.compile(rf"(?:提升|降低|减少|提高|优化|下降)?\s*(?:了)?\s*{re.escape(claimed)}%?", re.IGNORECASE)
                revised = pattern.sub("进行结构化优化（具体提升幅度因缺乏基线压测数据不作主观量化）", revised)
        for d in drifts:
            claimed = d.get("claimed_metric", "")
            verified = d.get("verified_baseline", "")
            if claimed and verified:
                pattern = re.compile(re.escape(claimed), re.IGNORECASE)
                revised = pattern.sub(f"{verified}（已核验基线）", revised)
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

        if not any(marker in answer for marker in ("我", "本人", "个人", "负责", "参与", "协同", "团队", "主导", "牵头")):
            missing_elements.append("个人贡献与团队边界")
            follow_up_questions.append("你本人具体负责哪一段链路？团队其他成员分别负责什么？")
        if any(marker in a_lower or marker in answer for marker in ("%", "qps", "tps", "提升", "降低", "倍", "ms")):
            if "baseline" not in a_lower and "基线" not in answer:
                missing_elements.append("指标基线")
                follow_up_questions.append("该指标的 baseline、单位、统计周期和数据来源是什么？")
            if not any(marker in answer for marker in ("周期", "日志", "看板", "压测", "数据来源", "评测集")):
                missing_elements.append("指标来源与统计口径")
                follow_up_questions.append("这组数字来自哪份日志、看板或评测集，统计窗口多长？")
        if not any(marker in answer for marker in ("失败", "复盘", "取舍", "限制", "边界", "不足", "事故")):
            missing_elements.append("限制或失败复盘")
            follow_up_questions.append("该方案在哪些场景会失效？你经历过什么失败并如何修正？")

        # Check boundary indicators
        boundary_markers = ("没做过", "不了解", "不会", "未涉猎", "未主导过", "没有实际做过", "接触较少", "不太了解", "没有这方面经验", "未涉及")
        is_boundary = any(m in answer for m in boundary_markers)

        # Relevance heuristic
        stopwords = {"请问", "请谈", "谈谈", "介绍", "如何", "怎么", "什么", "以及", "通过", "进行", "针对", "基于", "可以", "说说"}
        q_tokens = [
            t.lower() for t in re.split(r"[^A-Za-z0-9+#.\-一-鿿]+", question)
            if len(t) >= 2 and t not in stopwords
        ]
        tech_indicators = (
            "架构", "性能", "优化", "集群", "模型", "训练", "推理", "通信", "接口", "数据库",
            "并发", "内存", "延迟", "吞吐", "代码", "算法", "系统", "开发", "测试", "项目",
            "模块", "方案", "实现", "设计", "sql", "redis", "vllm", "nccl", "python", "cuda"
        )
        is_relevant = (
            not q_tokens
            or any(t in a_lower for t in q_tokens)
            or any(k in a_lower for k in tech_indicators)
        )

        has_metrics = any(marker in a_lower or marker in answer for marker in ("%", "qps", "tps", "提升", "降低", "倍", "ms", "s", "min", "小时", "卡", "stars"))
        has_baseline = ("baseline" in a_lower or "基线" in answer or "从" in answer)

        can_revise = True
        verification_status = "verified"

        # Heuristics for diagnosis
        if not answer.strip():
            diagnosis = QuestionDiagnosis.FATAL_GAP
            analysis = "未提供回答。无法评估对该题目的掌握程度与实际经历。"
            coaching = "请结合真实项目或基础技术积累，按 STAR 框架组织作答。"
            refined = ""
            can_revise = False
            takeaway = "技术面试避免交白卷，可从基础原理切入。"
        elif is_boundary:
            diagnosis = QuestionDiagnosis.EXPERIENCE_BOUNDARY
            analysis = "诚实界定个人经验边界，明确未在实际项目中主导该技术。技术面试中坦陈边界优于编造经历；建议在此基础上说明底层相通机制与快速学习迁移能力。"
            coaching = "坦诚说明未在实际项目中主导过该技术，避免强行推测细节；可说明所掌握的相通底层原理（如有），并阐述面对未知技术时的调研路径与攻坚方法。"
            refined = ""
            can_revise = False
            takeaway = "诚实说明经验边界，重点展示基础功底与学习迁移路径。"
        elif len(answer.strip()) < 80 and not is_relevant:
            diagnosis = QuestionDiagnosis.UNCERTAIN
            analysis = "回答内容与题目考查的核心技术点缺乏语义关联，未正面作答。无法可靠判断技术深度与真实经历。"
            coaching = "请围绕题目关注的核心技术点（如架构选型、实现方案、指标基线与故障排查）进行正面阐述。"
            refined = ""
            can_revise = False
            takeaway = "正面回答题目考查要点，避免答非所问。"
        elif any(k in q_lower or k in question for k in ["源码", "推导", "底层", "公式", "nccl", "算子"]) and len(answer) < 35:
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

        # Fact Guard verification
        if fact_guard is not None and answer.strip() and not is_boundary:
            guard_result = fact_guard.verify_facts(answer)
            if not guard_result.get("passed", False):
                drifts = guard_result.get("drifts", [])
                unverified = guard_result.get("unverified_claims", [])
                diagnosis = QuestionDiagnosis.METRIC_DRIFT
                drift_notes = []
                for d in drifts:
                    drift_notes.append(f"声称 {d.get('claimed_metric')}，但底稿基线为 {d.get('verified_baseline')}")
                for u in unverified:
                    drift_notes.append(f"声称指标 {u.get('claimed_metric')} 缺少底稿依据")
                analysis = f"回答中的数字或指标未通过事实核验（{'; '.join(drift_notes)}），易被判定为指标虚标或口径不实。"
                coaching = "所有指标必须严格基于底稿真实基线、单位和统计周期；若缺乏严密压测或监控数据，应客观陈述方案本身，不建议主观推定具体提升幅度。"
                takeaway = "先核对事实底稿，再回答数字问题。"
                refined = self._create_conservative_revision(answer, drifts, unverified)
                can_revise = True

        # Incremental fact check on refined_answer
        if fact_guard is not None and refined and refined.strip():
            rev_guard = fact_guard.verify_facts(refined)
            if not rev_guard.get("passed", False):
                refined = ""
                can_revise = False
                verification_status = "revision_failed_fact_check"

        return DebriefQuestionItem(
            question=question,
            candidate_answer=answer,
            interviewer_follow_up=follow_up,
            diagnosis=diagnosis,
            analysis_zh=analysis,
            coaching_advice=coaching,
            revised_answer=refined,
            refined_answer=refined or coaching,
            key_takeaway=takeaway,
            claim_refs=claim_refs,
            missing_elements=list(dict.fromkeys(missing_elements)),
            follow_up_questions=list(dict.fromkeys(follow_up_questions)),
            can_revise=can_revise,
            verification_status=verification_status,
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
