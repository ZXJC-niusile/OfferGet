"""
OfferGet JD Decision Engine (core/jd_decision.py)
=================================================
OfferGet native JD decision and strategic application evaluation engine.
Provides:
1. DecodeBeforeMatchGate: Pipeline enforcement ensuring no un-decoded raw JD can bypass semantic decomposition.
2. ShouldIApplyEvaluator: 5-dimension Go/No-Go decision framework, ⭐ 1-5 rating, mandatory 3-pros/3-cons,
   channel-adjusted interview probability intervals, and 6-week structured action plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from core.jd_analyst.models import (
    CandidateProfile,
    ChannelProbability,
    ChannelType,
    DecodedJD,
    MatcherResult,
    ProbabilityForecast,
)
from core.jd_analyst.decoder import JDDecoder
from core.jd_analyst.predictor import InterviewProbabilityCalculator


class UnverifiedJDPipelineError(ValueError):
    """Raised when matching is attempted on an un-decoded raw JD string in strict gate mode."""
    pass


class DecisionVerdict(str, Enum):
    STRONG_GO = "STRONG_GO"              # ⭐ 5: 强烈推荐投递，罕见优质机会
    CONDITIONAL_GO = "CONDITIONAL_GO"    # ⭐ 4: 值得投递，但必须先定制简历或寻找内推
    REVISE_FIRST = "REVISE_FIRST"        # ⭐ 3: 投亦可不投亦可，建议补充关键证据后再投
    HESITATE = "HESITATE"                # ⭐ 2: 不建议优先投递，除非备选项不足
    NO_GO = "NO_GO"                      # ⭐ 1: 明确不建议投递（硬门槛否决或下行风险过大）


class NextAction(str, Enum):
    DIRECT_APPLY = "DIRECT_APPLY"            # 直接投递（材料高度对齐，裸投亦有较高胜率）
    TAILOR_FIRST = "TAILOR_FIRST"            # 先定制再投（过 ATS 仍有表达/证据缺口）
    REFERRAL_FIRST = "REFERRAL_FIRST"        # 先寻内推（目标公司竞争大，走内推乘数效应显著）
    BRIDGE_GAP_FIRST = "BRIDGE_GAP_FIRST"    # 先补缺口（核心技能存在真实缺口，需短期突击）
    SKIP = "SKIP"                            # 果断放弃（硬门槛一票否决或严重错位）


@dataclass(frozen=True)
class WeekPlan:
    week_range: str
    phase_name: str
    tasks: List[str]
    deliverables: str


@dataclass(frozen=True)
class SixWeekActionPlan:
    weeks: List[WeekPlan]
    focus_summary: str


@dataclass
class ShouldIApplyReport:
    """Comprehensive Go / No-Go decision report."""
    stars: int                                # 1 ~ 5
    composite_score: float                    # 0.0 ~ 1.0
    verdict: DecisionVerdict
    verdict_title: str
    verdict_description: str
    pros: List[str]                           # 必须提供 3 条具体正向理由
    cons: List[str]                           # 必须提供 3 条具体负面/风险理由（绝不粉饰）
    probability_range: Tuple[float, float]    # 拿面概率综合区间 (min%, max%)
    probability_breakdown: Dict[str, Tuple[float, float]] # 各渠道概率区间
    next_action: NextAction
    action_advice: str
    dimension_scores: Dict[str, float]        # match, trajectory, downside, comp, opp_cost
    six_week_plan: SixWeekActionPlan


# ============================================================================
# 1. Decode-Before-Match Gate
# ============================================================================

class DecodeBeforeMatchGate:
    """
    Pipeline gate enforcing that all downstream matching and evaluation
    operate strictly on semantically decoded and canonicalized JD DTOs.
    """

    @staticmethod
    def enforce(jd_input: Any, strict: bool = False) -> DecodedJD:
        """
        Validates that jd_input is a canonical DecodedJD or DecodedJDCompat.
        If strict=True and jd_input is a raw string, raises UnverifiedJDPipelineError.
        If strict=False and jd_input is a raw string, automatically decodes it.
        """
        # 1. Already canonical DecodedJD
        if isinstance(jd_input, DecodedJD):
            return jd_input

        # 2. DecodedJDCompat wrapper
        if hasattr(jd_input, "canonical") and isinstance(jd_input.canonical, DecodedJD):
            return jd_input.canonical

        # 3. Raw string / unverified input
        if isinstance(jd_input, str):
            if strict:
                raise UnverifiedJDPipelineError(
                    "Decode-Before-Match Gate Triggered: Attempted to run matching on a raw JD string. "
                    "All matching operations must consume a canonical DecodedJD produced by JDDecoder."
                )
            # Automatic canonicalization in non-strict mode
            return JDDecoder().decode(jd_input)

        raise TypeError(
            f"Unsupported JD input type for DecodeBeforeMatchGate: {type(jd_input).__name__}. "
            "Expected DecodedJD, DecodedJDCompat, or raw string."
        )


# ============================================================================
# 2. Should I Apply Evaluator
# ============================================================================

class ShouldIApplyEvaluator:
    """
    Evaluates candidate-to-JD alignment using OfferGet's 5-dimension Should I Apply
    decision framework.
    """

    # Weights
    WEIGHT_MATCH: float = 0.30
    WEIGHT_TRAJECTORY: float = 0.25
    WEIGHT_DOWNSIDE: float = 0.20
    WEIGHT_COMPENSATION: float = 0.15
    WEIGHT_OPPORTUNITY_COST: float = 0.10

    def evaluate(
        self,
        decoded_jd: DecodedJD,
        candidate: CandidateProfile,
        matcher_result: MatcherResult,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> ShouldIApplyReport:
        """
        Computes the 5-dimension Go/No-Go evaluation and generates the decision report.
        """
        user_constraints = constraints or {}

        # 1. Dimension 1: Match Quality (30%)
        match_score = matcher_result.final_match_score
        if matcher_result.is_hard_vetoed:
            dim_match = 0.0
        elif match_score >= 0.85:
            dim_match = 1.0
        elif match_score >= 0.70:
            dim_match = 0.8
        elif match_score >= 0.55:
            dim_match = 0.5
        elif match_score >= 0.40:
            dim_match = 0.3
        else:
            dim_match = 0.0

        # 2. Dimension 2: Career Trajectory Fit (25%)
        dim_trajectory = self._score_career_trajectory(decoded_jd, candidate, matcher_result)

        # 3. Dimension 3: Downside Risk (20%, higher is safer)
        dim_downside = self._score_downside_risk(decoded_jd, matcher_result)

        # 4. Dimension 4: Compensation / Hard Constraints (15%)
        dim_comp = float(user_constraints.get("compensation_fit", 0.7))

        # 5. Dimension 5: Opportunity Cost & Timing (10%)
        dim_opp = float(user_constraints.get("opportunity_cost_fit", 0.7))

        # Composite Score
        composite = (
            self.WEIGHT_MATCH * dim_match
            + self.WEIGHT_TRAJECTORY * dim_trajectory
            + self.WEIGHT_DOWNSIDE * dim_downside
            + self.WEIGHT_COMPENSATION * dim_comp
            + self.WEIGHT_OPPORTUNITY_COST * dim_opp
        )
        composite = round(min(max(composite, 0.0), 1.0), 3)

        # Map to Stars (1 ~ 5)
        if matcher_result.is_hard_vetoed or composite < 0.40:
            stars = 1
            verdict = DecisionVerdict.NO_GO
            title = "⭐☆☆☆☆ (1/5 · 不建议投递)"
            desc = "存在岗位硬门槛未满足或下行风险严重，投入产出比极低，建议放弃并将精力投入更匹配的岗位。"
        elif composite < 0.55:
            stars = 2
            verdict = DecisionVerdict.HESITATE
            title = "⭐⭐☆☆☆ (2/5 · 谨慎观望)"
            desc = "匹配度或发展路径存在较多缺口，不建议作为优先目标，除非手头缺乏其他机会。"
        elif composite < 0.70:
            stars = 3
            verdict = DecisionVerdict.REVISE_FIRST
            title = "⭐⭐⭐☆☆ (3/5 · 补充材料后再投)"
            desc = "基本具备竞争基础，但存在显著表达或证据缺口；投亦可不投亦可，建议针对性补强材料。"
        elif composite < 0.85:
            stars = 4
            verdict = DecisionVerdict.CONDITIONAL_GO
            title = "⭐⭐⭐⭐☆ (4/5 · 值得投递，建议先定制/内推)"
            desc = "核心技能与职责高度对齐，长期发展方向契合。强烈建议先定制针对性简历并通过内推渠道投递。"
        else:
            stars = 5
            verdict = DecisionVerdict.STRONG_GO
            title = "⭐⭐⭐⭐⭐ (5/5 · 强烈推荐，头号优先级)"
            desc = "罕见优质机会，核心要求深度匹配且几乎无下行风险。应作为当前求职周期的最高优先级重点攻坚。"

        # Generate 3 Pros
        pros = self._generate_pros(decoded_jd, candidate, matcher_result, stars)

        # Generate 3 Cons (Mandatory, never sugarcoat)
        cons = self._generate_cons(decoded_jd, candidate, matcher_result, stars)

        # Calculate Channel Probabilities
        prob_calc = InterviewProbabilityCalculator()
        prob_forecast = prob_calc.calculate(matcher_result)

        prob_range = (prob_forecast.base_min_prob, prob_forecast.base_max_prob)
        breakdown = {
            "cold_apply": (
                round(prob_forecast.base_min_prob * 0.4, 1),
                round(prob_forecast.base_max_prob * 0.4, 1),
            ),
            "tailored_apply": prob_range,
            "referral": (
                min(round(prob_forecast.base_min_prob * 1.8, 1), 95.0),
                min(round(prob_forecast.base_max_prob * 1.8, 1), 99.0),
            ),
        }

        # Next Action Recommendation
        next_action, action_advice = self._determine_next_action(verdict, matcher_result, breakdown)

        # 6-Week Action Plan
        six_week_plan = self._generate_six_week_plan(verdict, matcher_result, decoded_jd)

        return ShouldIApplyReport(
            stars=stars,
            composite_score=composite,
            verdict=verdict,
            verdict_title=title,
            verdict_description=desc,
            pros=pros,
            cons=cons,
            probability_range=prob_range,
            probability_breakdown=breakdown,
            next_action=next_action,
            action_advice=action_advice,
            dimension_scores={
                "match_quality": dim_match,
                "career_trajectory": dim_trajectory,
                "downside_risk": dim_downside,
                "compensation": dim_comp,
                "opportunity_cost": dim_opp,
            },
            six_week_plan=six_week_plan,
        )

    def _score_career_trajectory(
        self,
        jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
    ) -> float:
        """Evaluates whether the role represents positive progression."""
        # Check title level progression
        cand_years = candidate.years_of_experience
        if matcher.must_have_score >= 0.8:
            return 1.0
        if matcher.must_have_score >= 0.6:
            return 0.7
        if cand_years >= 3.0 and matcher.must_have_score >= 0.4:
            return 0.5
        return 0.3

    def _score_downside_risk(
        self,
        jd: DecodedJD,
        matcher: MatcherResult,
    ) -> float:
        """Evaluates downside risks such as hard gate vetoes and red flags."""
        if matcher.is_hard_vetoed:
            return 0.0
        # Check implicit signals / red flags
        red_flags_count = len(jd.implicit_signals)
        if red_flags_count == 0:
            return 1.0
        if red_flags_count <= 2:
            return 0.7
        if red_flags_count <= 4:
            return 0.4
        return 0.2

    def _generate_pros(
        self,
        jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
        stars: int,
    ) -> List[str]:
        """Generates exactly 3 concrete, verifiable pros."""
        pros = []

        # Pro 1: Must-Have match
        matched_skills = [
            g.requirement_name for g in matcher.gap_matrix
            if getattr(g, "state", None) and str(g.state).endswith("MATCHED")
        ]
        if matched_skills:
            sample_skills = "、".join(matched_skills[:3])
            pros.append(f"核心技能精准对齐：候选人在 {sample_skills} 等 Must-Have 关键项上具备明确证据支持。")
        else:
            pros.append(f"岗位领域契合：目标岗位 [{jd.job_title}] 与候选人当前技术方向具备基础交集。")

        # Pro 2: Business & Responsibility overlap
        if matcher.must_have_score >= 0.7:
            pros.append(f"胜任力得分充足：Must-Have 匹配度达 {round(matcher.must_have_score * 100)}%，满足用人方基准筛选线。")
        else:
            pros.append("发展空间适宜：岗位职责能为候选人提供下一阶段所需的核心架构或业务实践场景。")

        # Pro 3: Hidden signal or team alignment
        if matcher.hidden_signal_fit >= 0.6:
            pros.append("隐性诉求高度契合：候选人过往沉淀与用人部门当前的业务痛点及工程挑战吻合。")
        else:
            pros.append("求职杠杆价值：此岗位如果通过，能够有效为后续职业发展建立更扎实的项目背书。")

        return pros[:3]

    def _generate_cons(
        self,
        jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
        stars: int,
    ) -> List[str]:
        """Generates exactly 3 concrete, non-sugarcoated cons/risks (mandatory)."""
        cons = []

        # Con 1: Hard veto or real gaps
        if matcher.is_hard_vetoed:
            reasons = "；".join(matcher.hard_veto_reasons)
            cons.append(f"硬性门槛未满足：{reasons}。机筛阶段有极高被一票否决的风险。")
        else:
            real_gaps = [
                g.requirement_name for g in matcher.gap_matrix
                if str(getattr(g, "state", "")).endswith("REAL_GAP")
            ]
            if real_gaps:
                gap_str = "、".join(real_gaps[:2])
                cons.append(f"真实技术缺口：候选人底稿中暂无 {gap_str} 的生产实战证据，容易成为技术面重灾区。")
            else:
                cons.append("表达与量化缺口：部分核心经历缺乏完整的 Baseline 与生产级实效证据支撑。")

        # Con 2: Implicit signals / Red flags in JD
        if jd.implicit_signals:
            top_signal = jd.implicit_signals[0]
            meaning = getattr(top_signal, "translated_meaning", getattr(top_signal, "original_text", ""))
            risk = getattr(top_signal, "underlying_risk", "")
            cons.append(f"岗位潜在挑战：JD 暗示 '{top_signal.original_text}'（解读：{meaning}；风险：{risk}）。")
        else:
            cons.append("竞争烈度风险：目标岗位若处于热门赛道，裸投通过率低，简历极易淹没在海量候选人池中。")

        # Con 3: Opportunity cost or compensation/level misalignment
        if stars <= 2:
            cons.append("机会成本偏高：当前材料匹配偏低，强行投递将消耗内推额度并带来沉没试错成本。")
        else:
            cons.append("面评防守风险：面试官可能针对跨系统演进真实边界与个人独立贡献度发起连环追问。")

        # Ensure exactly 3 cons
        while len(cons) < 3:
            cons.append("盲区防范提示：建议在投递前通过校友或在职员工进一步核实团队近期业务稳定度与流动率。")

        return cons[:3]

    def _determine_next_action(
        self,
        verdict: DecisionVerdict,
        matcher: MatcherResult,
        breakdown: Dict[str, Tuple[float, float]],
    ) -> Tuple[NextAction, str]:
        """Determines the single most strategic next action."""
        if verdict == DecisionVerdict.NO_GO:
            return (
                NextAction.SKIP,
                "建议放弃本岗位。硬性门槛阻断或严重不匹配，投入时间回报率极低，应聚焦主航道目标。",
            )
        if verdict == DecisionVerdict.HESITATE:
            return (
                NextAction.BRIDGE_GAP_FIRST,
                "不建议立即投递。建议对照缺口清单集中突击补充 1~2 项核心技能证据，或暂作为兜底备选。",
            )
        if verdict == DecisionVerdict.REVISE_FIRST:
            return (
                NextAction.TAILOR_FIRST,
                "必须先定制简历再投递。修正简历中的表达缺口，补全量化指标基线，防范 ATS 自动过滤。",
            )
        # For CONDITIONAL_GO and STRONG_GO:
        referral_min, referral_max = breakdown.get("referral", (0.0, 0.0))
        if referral_max >= 70.0:
            return (
                NextAction.REFERRAL_FIRST,
                "强烈建议通过在职校友或前同事走内部推荐通道，内推可将拿面概率提升至最高区间。",
            )
        return (
            NextAction.DIRECT_APPLY,
            "材料准备充分，可直接投递；若有内推资源则优先内推，投递后 48 小时内准备答辩追问预案。",
        )

    def _generate_six_week_plan(
        self,
        verdict: DecisionVerdict,
        matcher: MatcherResult,
        jd: DecodedJD,
    ) -> SixWeekActionPlan:
        """Generates a structured 6-week milestone action plan."""
        real_gaps = [
            g.requirement_name for g in matcher.gap_matrix
            if str(getattr(g, "state", "")).endswith("REAL_GAP")
        ]
        gap_focus = real_gaps[0] if real_gaps else "核心项目指标与证据链"

        weeks = [
            WeekPlan(
                week_range="第 1~2 周",
                phase_name="缺口攻坚与证据梳理 (Evidence & Gap Bridging)",
                tasks=[
                    f"针对 [{gap_focus}] 进行技术复盘，梳理原型代码或验证 Demo",
                    "对过往项目补充准确的 Baseline 数据与指标计算公式（如 QPS, 延迟, 节省成本）",
                    "完成个人事实底稿 ProfileContext 的核对，消除未锚定指标",
                ],
                deliverables="形成可查证的技术证据卡与指标对账表",
            ),
            WeekPlan(
                week_range="第 3~4 周",
                phase_name="目标岗位精准适配 (Target Alignment & Artifacts)",
                tasks=[
                    f"根据 [{jd.job_title}] 核心职责重构 2 个重点项目的叙事结构（采用 Mini-RFC 格式）",
                    "编写针对目标业务场景的个人见解与架构思考文档",
                    "排查并消除简历中的 AI 套话、排他性最高级与虚高动词",
                ],
                deliverables="完成针对该岗位定制的高密度单页简历初稿",
            ),
            WeekPlan(
                week_range="第 5 周",
                phase_name="防守演练与内推外联 (Defense Drill & Outreach)",
                tasks=[
                    "运行答辩追问模拟器，完成 5 步稳妥应答框架演练",
                    "针对真实缺口准备 '透明承认 + 转守为攻' 的面试话术",
                    "联系目标团队校友或猎头，发送高情商自荐信寻求内推",
                ],
                deliverables="内推推荐信发出，答辩速查卡就绪",
            ),
            WeekPlan(
                week_range="第 6 周",
                phase_name="投递闭环与复盘推进 (Application & Follow-up)",
                tasks=[
                    "正式递交求职申请，记录投递渠道与时间节点",
                    "若 3 个工作日未获反馈，进行一次专业友好的礼貌跟进",
                    "收到面试通知后，复习该岗位专属 Top 20 面试预测题",
                ],
                deliverables="拿到首轮面试邀请并进入实战演练",
            ),
        ]

        return SixWeekActionPlan(
            weeks=weeks,
            focus_summary=f"重点攻坚 [{gap_focus}]，通过两周证据对账、两周定制重构与两周投递演练达成拿面目标。",
        )
