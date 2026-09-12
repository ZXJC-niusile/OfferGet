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
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class QuestionDiagnosis(str, Enum):
    WELL_DEFENDED = "well_defended"      # 严密防守，依据充分
    EXPRESSION_GAP = "expression_gap"    # 实际做过但表达变形，谦逊或术语不准
    DEPTH_DEFICIENT = "depth_deficient"  # 底层源码/数学推导缺乏储备
    METRIC_DRIFT = "metric_drift"        # 指标被现场追问细节时露怯
    FATAL_GAP = "fatal_gap"              # 确实盲区，严禁死扛


@dataclass
class DebriefQuestionItem:
    question: str
    candidate_answer: str
    interviewer_follow_up: str = ""
    diagnosis: QuestionDiagnosis = QuestionDiagnosis.WELL_DEFENDED
    analysis_zh: str = ""
    refined_answer: str = ""
    key_takeaway: str = ""


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

    def analyze_question(
        self,
        question: str,
        answer: str,
        follow_up: str = ""
    ) -> DebriefQuestionItem:
        """
        Classifies interview Q&A performance and generates diagnosis.
        """
        q_lower = question.lower()
        a_lower = answer.lower()

        # Heuristics for diagnosis
        if not answer.strip() or "没做过" in answer or "不了解" in answer or "不会" in answer:
            diagnosis = QuestionDiagnosis.FATAL_GAP
            analysis = "属于未涉猎的绝对盲区。面试建议：诚实坦白认知边界，并给出高相关可迁移能力论证。"
            refined = "该方向此前未在生产环境主导过，但我深入实践过与之底层相通的架构，有信心在短期内迁移攻坚。"
            takeaway = "补足基础概念定义，切忌白板硬猜。"
        elif any(k in q_lower or k in question for k in ["源码", "推导", "底层", "公式", "nccl", "算子"]) and len(answer) < 30:
            diagnosis = QuestionDiagnosis.DEPTH_DEFICIENT
            analysis = "面试官直击底层实现，但回答停留在宏观 API 级别，深度明显不足。"
            refined = "正面给出底层通信原语、显存切分公式与关键数据结构。"
            takeaway = "面试前务必提前白板手撕核心算子与推导式。"
        elif any(k in q_lower or k in question for k in ["基线", "baseline", "提升", "%", "指标", "qps"]):
            if "baseline" not in a_lower and "基线" not in answer:
                diagnosis = QuestionDiagnosis.METRIC_DRIFT
                analysis = "提及量化收益但未同步提供基线（Baseline），触发面试官追问警觉。"
                refined = "在回答指标时，严格遵循：'基线口径 -> 调优手段 -> 结果提升 -> 统计周期'。"
                takeaway = "所有数字必须自带 Baseline，杜绝伪精确。"
            else:
                diagnosis = QuestionDiagnosis.WELL_DEFENDED
                analysis = "数字严密，基线与手段交代清晰，防守成功。"
                refined = answer
                takeaway = "保持该严谨回答节奏。"
        else:
            diagnosis = QuestionDiagnosis.WELL_DEFENDED
            analysis = "逻辑结构清晰，因果关系连贯。"
            refined = answer
            takeaway = "表现稳定。"

        return DebriefQuestionItem(
            question=question,
            candidate_answer=answer,
            interviewer_follow_up=follow_up,
            diagnosis=diagnosis,
            analysis_zh=analysis,
            refined_answer=refined,
            key_takeaway=takeaway
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
