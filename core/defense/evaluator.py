"""
OfferGet Defense Answer Evaluator and Safe Answer Framer.
Absorbed and formalized from defense-beating-simulator (MIT).
Evaluates candidate answers against the 100-point rubric and generates
conservative 5-step safe answers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.defense.rubrics import (
    AnswerScoreResult,
    AnswerScoringRubric,
    DefenseWeaknessDimension,
)


OVERCLAIMING_PATTERNS = [
    "完全实现了",
    "真实部署了",
    "效果大幅领先",
    "最优控制",
    "高精度预测",
    "全部由我完成",
    "完美解决",
    "毫无瑕疵",
    "彻底消除",
    "绝对领先",
    "100%自主研发",
]

NEGATION_MARKERS = ("不", "未", "没有", "不能", "不要", "尚未", "避免", "并非", "不得", "不代表")

BOUNDARY_ACKNOWLEDGMENT_MARKERS = (
    "当前版本主要",
    "主要实现",
    "局限在于",
    "目前尚未",
    "基于典型",
    "面向课程",
    "原型阶段",
    "主要用于",
    "后续可以接入",
    "后续改进",
    "暂未覆盖",
    "没有做到",
    "不足之处",
)

PERSONAL_CONTRIBUTION_MARKERS = (
    "我主要负责",
    "本人独立",
    "我负责",
    "我的工作主要",
    "团队其他成员",
    "基于开源",
    "二次开发",
    "本人重点实现了",
)


class DefenseEvaluator:
    """
    Evaluates candidate responses using the 100-point defense rubric.
    """

    @classmethod
    def evaluate(
        cls,
        question: str,
        answer: str,
        context_facts: Optional[str] = None,
    ) -> AnswerScoreResult:
        """
        Evaluates a defense answer against the 100-point rubric.
        """
        ans_clean = answer.strip()
        q_clean = question.strip()

        scores: Dict[str, float] = {}
        deductions: Dict[str, str] = {}
        main_problems: List[str] = []
        suggestions: List[str] = []

        # 1. 正面回答问题 (20 pts)
        direct_score = 20.0
        if len(ans_clean) < 10:
            direct_score = 5.0
            deductions["direct_response"] = "作答字数过短，未实质性回应提问。"
            main_problems.append("回答过于简略，缺乏实质内容。")
        elif not cls._check_relevance(q_clean, ans_clean):
            direct_score = 8.0
            deductions["direct_response"] = "回答未紧扣提问的核心考点，存在顾左右而言他倾向。"
            main_problems.append("答非所问或脱离题目核心。")
        scores["direct_response"] = direct_score

        # 2. 有技术或材料细节 (20 pts)
        tech_score = 20.0
        tech_count = cls._count_concrete_details(ans_clean)
        if len(ans_clean) < 10 or tech_count == 0:
            tech_score = 0.0 if len(ans_clean) < 10 else 6.0
            deductions["technical_details"] = "缺乏具体的算法、数据、参数或组件细节，表述泛泛。"
            main_problems.append("技术细节空洞，只有高层定性描述。")
            suggestions.append("补充具体的机制逻辑、调优参数或实际代码落地点。")
        elif tech_count < 2:
            tech_score = 14.0
            deductions["technical_details"] = "细节支撑偏弱，建议增加参数或机制说明。"
            suggestions.append("补充更多具体的工程细节或指标口径。")
        scores["technical_details"] = tech_score

        # 3. 承认项目边界 (15 pts)
        boundary_score = 15.0
        has_boundary = any(m in ans_clean for m in BOUNDARY_ACKNOWLEDGMENT_MARKERS)
        if len(ans_clean) < 10 or not has_boundary:
            boundary_score = 0.0 if len(ans_clean) < 10 else 7.0
            deductions["acknowledges_boundary"] = "未主动声明当前版本的适用工况、假设条件或局限性。"
            main_problems.append("未承认项目边界，容易引发评委连续追问。")
            suggestions.append("主动说明当前做到了什么、没做到什么以及适用边界。")
        scores["acknowledges_boundary"] = boundary_score

        # 4. 突出个人贡献 (15 pts)
        contrib_score = 15.0
        has_contrib = any(m in ans_clean for m in PERSONAL_CONTRIBUTION_MARKERS)
        if len(ans_clean) < 10 or not has_contrib:
            contrib_score = 0.0 if len(ans_clean) < 10 else 8.0
            deductions["highlights_personal_contribution"] = "未明确本人工作与团队协作、开源复用或既有模板的划分边界。"
            suggestions.append("使用“我主要负责...，团队其他成员负责...”清晰切分贡献。")
        scores["highlights_personal_contribution"] = contrib_score

        # 5. 避免夸大 (15 pts)
        overclaim_score = 15.0
        detected_overclaims = cls._detect_unqualified_overclaims(ans_clean)
        if detected_overclaims:
            overclaim_score = max(0.0, 15.0 - len(detected_overclaims) * 7.5)
            deductions["avoids_overclaiming"] = f"使用了绝对化或无保留的高调措辞：{', '.join(detected_overclaims)}。"
            main_problems.append(f"存在夸大或过度断言：{', '.join(detected_overclaims)}。")
            suggestions.append("将绝对化表述替换为客观稳妥的阶段性结论。")
        scores["avoids_overclaiming"] = overclaim_score

        # 6. 表达清晰 (15 pts)
        clarity_score = 15.0
        if len(ans_clean) < 10:
            clarity_score = 5.0
            deductions["clarity"] = "作答字数过少，无法呈现清晰论证。"
        elif len(ans_clean) > 400:
            clarity_score = 10.0
            deductions["clarity"] = "单轮答辩作答偏冗长，核心要点不够突出。"
            suggestions.append("控制作答篇幅在 150-250 字以内，条理分明。")
        scores["clarity"] = clarity_score

        total = sum(scores.values())

        # Generate 5-step safe answer
        safe_ans = cls.generate_safe_answer(question, ans_clean)

        return AnswerScoreResult(
            total_score=total,
            dimension_scores=scores,
            deductions=deductions,
            main_problems=main_problems,
            suggestions=suggestions,
            safe_answer=safe_ans,
        )

    @classmethod
    def _detect_unqualified_overclaims(cls, text: str) -> List[str]:
        """
        Detects unqualified overclaiming assertions unless preceded by negation.
        """
        overclaims: List[str] = []
        for phrase in OVERCLAIMING_PATTERNS:
            idx = 0
            while True:
                pos = text.find(phrase, idx)
                if pos == -1:
                    break
                prefix = text[max(0, pos - 12) : pos]
                if not any(neg in prefix for neg in NEGATION_MARKERS):
                    overclaims.append(phrase)
                    break
                idx = pos + len(phrase)
        return overclaims

    @classmethod
    def _check_relevance(cls, question: str, answer: str) -> bool:
        """Checks relevance between question and answer via keyword and 2-gram overlap."""
        if not question.strip() or not answer.strip():
            return False

        # 1. English/Alphanumeric words
        q_en = {w.lower() for w in re.findall(r"[a-zA-Z0-9_+-]{2,}", question)}
        a_en = {w.lower() for w in re.findall(r"[a-zA-Z0-9_+-]{2,}", answer)}
        if q_en and (q_en & a_en):
            return True

        # 2. Chinese 2-grams (excluding stop characters)
        stopwords = {
            "请问", "请说", "说明", "如何", "怎么", "什么", "以及", "通过", "进行",
            "哪些", "是否", "这是", "对于", "关于", "你的", "你们", "请详", "详细", "介绍"
        }
        zh_chars = re.sub(r"[^\u4e00-\u9fa5]", "", question)
        q_bigrams = set()
        for i in range(len(zh_chars) - 1):
            bg = zh_chars[i : i + 2]
            if bg not in stopwords:
                q_bigrams.add(bg)

        if not q_bigrams:
            return True

        return any(bg in answer for bg in q_bigrams)


    @classmethod
    def _count_concrete_details(cls, text: str) -> int:
        """Counts presence of concrete numbers, units, framework names, or mechanisms."""
        count = 0
        # Check numbers and quantified metrics
        nums = re.findall(r"\d+(?:\.\d+)?\s*(?:%|ms|s|卡|台|qps|tps|mb|gb|tb|万|亿)", text, re.I)
        if nums:
            count += len(nums)
        elif re.search(r"\d+", text):
            count += 1
        # Check technical/framework terms
        from core.fact_guard import KNOWN_TECH_TERMS
        text_l = text.lower()
        if any(t.lower() in text_l for t in KNOWN_TECH_TERMS if len(t) >= 2):
            count += 1
        return count

    @classmethod
    def generate_safe_answer(cls, question: str, raw_answer: str) -> str:
        """
        Generates conservative 5-step reference answer based on raw answer:
          1. 正面回应问题
          2. 当前版本实际做到了什么
          3. 承认当前没有做到什么
          4. 解释为什么这样处理（环境/原型/资源限制）
          5. 给出后续改进方向（先改哪一步）
        """
        # Clean out obvious overclaiming phrases
        cleaned = raw_answer
        for oc in OVERCLAIMING_PATTERNS:
            cleaned = cleaned.replace(oc, "重点优化了")

        step1 = "正面回应：在当前阶段，该模块主要定位在原型验证与核心链路打通。"
        step2 = f"实际实现：当前版本主要实现了核心数据流与调度逻辑，确保了基准功能的稳定运行。"
        step3 = "边界与局限：由于测试环境与时间所限，目前尚未接入全量生产级真实数据，极端并发与偶发异常处理仍在完善中。"
        step4 = "原因说明：基于当前的迭代周期与原型验证需求，我们优先保证了核心机制的可解释性与正确性。"
        step5 = "改进规划：后续改进中，第一步我们将接入更严格的真实压测数据，补充边界异常降级策略。"

        return f"{step1}\n{step2}\n{step3}\n{step4}\n{step5}"
