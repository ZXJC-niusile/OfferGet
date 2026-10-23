"""
Predictor: Interview probability calculator & Top 20 interview questions predictor.
"""

import re
from typing import List
from .models import (
    DecodedJD,
    MatcherResult,
    ProbabilityForecast,
    QuestionCategory,
    InterviewQuestion,
    PredictionResult,
    GapState,
)


class InterviewProbabilityCalculator:
    """Do not infer outcome probabilities from a rule-based match score.

    A calibrated outcome dataset/model is not bundled with OfferGet. Keep the
    public forecast shape, but represent unknown values as null, never as 0%.
    """

    def calculate(self, matcher_result: MatcherResult, listing_age_days: int = 15) -> ProbabilityForecast:
        if isinstance(listing_age_days, bool) or not isinstance(listing_age_days, int) or listing_age_days < 0:
            raise ValueError("listing_age_days must be a non-negative integer")
        summary = "缺少经过校准的招聘结果数据，无法估计拿面概率或渠道胜率；匹配分仅表示材料对岗位要求的覆盖。"
        if matcher_result.is_hard_vetoed:
            summary += "存在未满足的硬门槛，请先向招聘方确认其是否为必要条件。"
        if listing_age_days > 60:
            summary += f"岗位发布已有 {listing_age_days} 天，请确认是否仍在招聘；发布时间本身不能证明是幽灵职位。"
        return ProbabilityForecast(
            base_min_prob=None,
            base_max_prob=None,
            listing_age_days=listing_age_days,
            age_decay_multiplier=None,
            is_ghost_job_risk=False,
            strategic_summary=summary,
            estimate_status="unavailable",
            estimate_basis="No calibrated recruitment outcome model or channel outcome data is available.",
        )


class InterviewTop20Predictor:
    """Build four sets of five questions from the JD and candidate evidence gaps."""

    def predict(self, jd: DecodedJD, matcher_result: MatcherResult) -> List[InterviewQuestion]:
        role = jd.job_title.strip() or "岗位名称待确认"
        def section_lines(headings):
            # Preserve explicit source requirements even when the domain decoder
            # has no taxonomy entry (for example, product research duties).
            selected, active = [], False
            for raw_line in (jd.clean_text or jd.raw_text).splitlines():
                line = raw_line.strip()
                heading = re.match(r"^(岗位职责|职责|工作内容|任职要求|要求|岗位要求|加分项|福利待遇|Responsibilities|Requirements)\s*[:：]\s*(.*)$", line, re.IGNORECASE)
                if heading:
                    active = heading.group(1).lower() in headings
                    line = heading.group(2).strip()
                if active and line:
                    selected.append(re.sub(r"^\s*\d+[.、)）]\s*", "", line))
            return list(dict.fromkeys(selected))

        responsibilities = [r.description or r.title for r in jd.core_responsibilities]
        responsibilities = responsibilities or section_lines({"岗位职责", "职责", "工作内容", "responsibilities"})
        skills = [s.name for s in jd.core_skills]
        skills = skills or section_lines({"任职要求", "要求", "岗位要求", "requirements"})
        gaps = sorted(getattr(matcher_result, "gap_matrix", []), key=lambda g: {
            GapState.REAL_GAP: 0, GapState.INSUFFICIENT_EVIDENCE: 1,
            GapState.EXPRESSION_GAP: 2, GapState.TO_BE_CONFIRMED: 3,
        }.get(g.state, 4))
        signals = [s.original_text for s in jd.implicit_signals]
        thresholds = [t.requirement for t in jd.hard_thresholds]

        def source(items, index, fallback):
            return items[index % len(items)] if items else fallback

        # The prompts ask for evidence; quoting a JD requirement never implies
        # that the candidate has performed it or has worked at any given scale.
        groups = [
            (QuestionCategory.ARCHITECTURE, "方案与任务设计", "Approach and task design", responsibilities or skills, [
                ("请拆解执行流程、输入输出和依赖，并解释关键选择。", "Break down the workflow, inputs, outputs and dependencies; explain the key choices."),
                ("有哪些可行方案？你会用哪些约束做取舍？", "Compare feasible approaches and explain the constraints behind your trade-offs."),
                ("如何定义验收标准，并验证方案是否解决实际问题？", "Define acceptance criteria and explain how you would validate the outcome."),
                ("如何识别失败情况、定位原因并设计恢复步骤？", "Identify failure cases, diagnose causes and outline recovery steps."),
                ("需求或资源发生变化时，如何调整方案并控制影响？", "Adapt the approach to changing requirements or resources and contain the impact."),
            ]),
            (QuestionCategory.PRINCIPLES, "关键能力与验证", "Required skills and verification", skills, [
                ("请解释核心原理，区分你实际用过和仅了解的部分。", "Explain the principles and distinguish hands-on experience from conceptual knowledge."),
                ("如何用最小案例验证你的理解，并说明局限？", "Use a minimal example to test your understanding and describe its limitations."),
                ("容易出现哪些错误判断？你会怎样排查？", "Explain common mistakes and how you would diagnose them."),
                ("在什么条件下你会选择替代方法，理由是什么？", "When would you choose an alternative, and why?"),
                ("如何设计可复核的测试或评价，避免只凭主观判断？", "Design reproducible tests or evaluations rather than relying on impressions."),
            ]),
            (QuestionCategory.BQ, "经历与证据边界", "Experience and evidence boundaries", [g.requirement_name for g in gaps] or responsibilities or skills, [
                ("请选择真实经历说明个人贡献；若没有直接经历，请明确指出。", "Use a real example to describe your contribution, or state the lack of direct experience."),
                ("你如何和协作者划分责任，哪些成果不能归为个人贡献？", "Explain responsibility boundaries and which outcomes cannot be attributed to you alone."),
                ("曾经有哪些失败或限制？如果没有实践经历，请说明验证计划。", "Describe failures or limitations; if you lack experience, explain a validation plan."),
                ("哪些结果有材料或日志可核验，哪些信息仍待确认？", "Which outcomes have supporting evidence, and what remains unverified?"),
                ("遇到不同意见或优先级冲突时，你会怎样沟通并记录决策？", "Explain how you communicate disagreements or priority conflicts and record decisions."),
            ]),
            (QuestionCategory.REVERSE, "向招聘方确认", "Questions for the hiring team", signals + thresholds + responsibilities, [
                ("请向招聘方确认这项要求对应的实际任务和优先级。", "Ask the hiring team which real tasks and priorities this requirement represents."),
                ("请确认评价标准、考核周期及可使用的资源。", "Clarify evaluation criteria, review periods and available resources."),
                ("请确认团队分工、协作接口及该岗位的职责边界。", "Clarify team responsibilities, collaboration interfaces and role boundaries."),
                ("请确认目前最主要的困难，以及此前尝试的方案。", "Ask about current challenges and approaches already tried."),
                ("请确认入职初期交付预期、支持方式及仍不明确的条件。", "Clarify early deliverables, support and any conditions that remain uncertain."),
            ]),
        ]
        questions = []
        for category, category_cn, category_en, anchors, prompts in groups:
            for index, (cn, en) in enumerate(prompts):
                anchor = source(anchors, index, role + "（该维度要求未明确，需确认）")
                questions.append(InterviewQuestion(
                    question_id=len(questions) + 1,
                    category_cn=category_cn, category_en=category_en, category_type=category,
                    question_cn=f"针对【{role}】的【{anchor}】，{cn}",
                    question_en=f"For the role '{role}', concerning '{anchor}': {en}",
                    jd_signal=anchor,
                    interviewer_intent="核对岗位要求、候选人的真实贡献与可验证证据，不预设候选人具备未提供的经历。",
                    prep_keypoints="引用原始岗位要求和真实底稿，说明个人动作、方案取舍、证据来源与能力边界；未知内容明确标记待确认。",
                ))
        return questions


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
