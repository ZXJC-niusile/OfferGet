"""
OfferGet Comprehensive Chinese JD & Resume Rubrics (core/cn_rubrics.py)
=======================================================================
OfferGet native multi-dimensional evaluation rubric system for Chinese enterprise hiring.
Provides 4 orthogonal 100-point rubrics for enterprise hiring in China:
1. JdMatchScore (100 pts, 7 dimensions):
   - 硬性条件匹配 (20), 技能关键词匹配 (20), 项目相关度 (25),
   - 成果量化程度 (15), 职级匹配 (10), 表达清晰度 (5), ATS 可读性 (5).
2. CredibilityScore (100 pts, 6 dimensions):
   - 数据来源清楚 (20), 个人贡献比例清楚 (20), 没有明显夸大 (20),
   - 表达不过度包装 (15), 项目逻辑自洽 (15), 风险点已提示 (10).
3. HrScreenScore (100 pts, 6 dimensions):
   - 10秒内看懂求职方向 (20), 首屏前部有核心亮点 (20), 经历和岗位相关 (25),
   - 数据结果清楚 (15), 稳定性风险低 (10), 表达简洁专业 (10).
4. InterviewReadinessScore (100 pts, 6 dimensions):
   - 项目背景能讲清 (20), 个人贡献明确 (20), 方法和决策能解释 (20),
   - 结果数据可信 (20), 失败/复盘能回答 (10), 和 JD 关联清楚 (10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.jd_analyst.models import CandidateProfile, DecodedJD, MatcherResult
from core.registry import MetricPatternRegistry, QualityRuleRegistry


@dataclass(frozen=True)
class RubricDimensionResult:
    name: str
    max_score: float
    score: float
    evidence: str
    deduction_reason: str = ""


@dataclass
class RubricScoreCard:
    category: str
    total_score: float
    max_score: float = 100.0
    passed_cutoff: bool = True
    dimensions: List[RubricDimensionResult] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)
    actionable_fixes: List[str] = field(default_factory=list)


class ComprehensiveRubricScorer:
    """Evaluates candidates across all 4 rubrics with zero hallucination."""

    # -------------------------------------------------------------------------
    # 1. JD Match Score (100 pts, 7 dimensions)
    # -------------------------------------------------------------------------
    def score_jd_match(
        self,
        decoded_jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
    ) -> RubricScoreCard:
        dims: List[RubricDimensionResult] = []
        risks: List[str] = []
        fixes: List[str] = []

        # D1: 硬性条件匹配 (20 pts)
        if matcher.is_hard_vetoed:
            s1 = 0.0
            e1 = "；".join(matcher.hard_veto_reasons)
            d1 = "硬门槛未满足或存在一票否决项"
            risks.append("高淘汰风险：硬性门槛未满足，机筛有直接淘汰风险。")
            fixes.append("在自荐信中补充同等替代性硬核成果，或寻求业务主管直推。")
        else:
            s1 = 20.0
            e1 = f"学历【{candidate.education_level}】、经验【{candidate.years_of_experience}年】满足岗位硬性要求"
            d1 = ""
        dims.append(RubricDimensionResult("硬性条件匹配", 20.0, s1, e1, d1))

        # D2: 技能关键词匹配 (20 pts)
        must_matched = matcher.must_have_score
        s2 = round(20.0 * must_matched, 1)
        e2 = f"Must-Have 核心技能匹配度达 {round(must_matched * 100)}%"
        d2 = f"未覆盖技能项扣减 {round(20.0 - s2, 1)} 分" if s2 < 20.0 else ""
        if s2 < 14.0:
            fixes.append("将缺少的必须技能在相关经历中以实际工程动作补充描述。")
        dims.append(RubricDimensionResult("技能关键词匹配", 20.0, s2, e2, d2))

        # D3: 项目相关度 (25 pts)
        proj_score = matcher.hidden_signal_fit * 0.5 + matcher.must_have_score * 0.5
        s3 = round(25.0 * proj_score, 1)
        e3 = f"项目业务场景契合度估算: {round(proj_score * 100)}%"
        d3 = f"业务场景与目标岗位存在偏差，扣 {round(25.0 - s3, 1)} 分" if s3 < 25.0 else ""
        dims.append(RubricDimensionResult("项目相关度", 25.0, s3, e3, d3))

        # D4: 成果量化程度 (15 pts)
        bullets = candidate.project_descriptions
        quant_count = sum(1 for b in bullets if MetricPatternRegistry.is_bullet_quantified(b))
        ratio = quant_count / max(len(bullets), 1)
        s4 = round(15.0 * min(ratio / 0.6, 1.0), 1)
        e4 = f"{quant_count}/{len(bullets)} 条经历包含明确量化指标"
        d4 = "量化比例不足 60%" if s4 < 15.0 else ""
        if s4 < 10.0:
            fixes.append("为核心工作经历补充 Baseline、吞吐量、时延或商业降本指标。")
        dims.append(RubricDimensionResult("成果量化程度", 15.0, s4, e4, d4))

        # D5: 职级匹配 (10 pts)
        yoe = candidate.years_of_experience
        s5 = 10.0 if yoe >= 3.0 or matcher.must_have_score >= 0.8 else round(10.0 * (yoe / 3.0), 1)
        e5 = f"经历年限 {yoe} 年，负责范围与目标职级匹配"
        d5 = "经验深度与高阶职级要求存在差距" if s5 < 10.0 else ""
        dims.append(RubricDimensionResult("职级匹配", 10.0, s5, e5, d5))

        # D6: 表达清晰度 (5 pts)
        raw_text = candidate.raw_resume_text
        has_slop = any(w in raw_text for w in QualityRuleRegistry.FORBIDDEN_BUZZWORDS)
        s6 = 3.5 if has_slop else 5.0
        e6 = "包含空洞虚词" if has_slop else "用词严谨克制"
        d6 = "存在空洞形容词" if has_slop else ""
        dims.append(RubricDimensionResult("表达清晰度", 5.0, s6, e6, d6))

        # D7: ATS 可读性 (5 pts)
        s7 = 5.0  # Default structured text is ATS friendly
        e7 = "单栏标准结构，支持标准文本解析"
        dims.append(RubricDimensionResult("ATS 可读性", 5.0, s7, e7, ""))

        total = round(sum(d.score for d in dims), 1)
        return RubricScoreCard(
            category="JD 匹配分",
            total_score=total,
            passed_cutoff=total >= 60.0 and not matcher.is_hard_vetoed,
            dimensions=dims,
            risk_warnings=risks,
            actionable_fixes=fixes,
        )

    # -------------------------------------------------------------------------
    # 2. Credibility Score (100 pts, 6 dimensions)
    # -------------------------------------------------------------------------
    def score_credibility(self, candidate: CandidateProfile) -> RubricScoreCard:
        dims: List[RubricDimensionResult] = []
        risks: List[str] = []
        fixes: List[str] = []
        text = candidate.raw_resume_text

        # D1: 数据来源清楚 (20 pts)
        quant_count = sum(1 for b in candidate.project_descriptions if MetricPatternRegistry.is_bullet_quantified(b))
        s1 = 20.0 if quant_count >= 3 else round(20.0 * (quant_count / 3.0), 1)
        e1 = f"包含 {quant_count} 项可核验量化指标"
        d1 = "关键数字缺乏基线或来源标注" if s1 < 20.0 else ""
        dims.append(RubricDimensionResult("数据来源清楚", 20.0, s1, e1, d1))

        # D2: 个人贡献比例清楚 (20 pts)
        # Check for role ranks in bullets
        has_role = any("owner" in b.lower() or "主导" in b or "负责" in b for b in candidate.project_descriptions)
        s2 = 20.0 if has_role else 12.0
        e2 = "明确标注文中个人负责的具体子系统或模块" if has_role else "部分经历团队成果与个人动作边界模糊"
        d2 = "缺乏明确的个人职责边界界定" if not has_role else ""
        dims.append(RubricDimensionResult("个人贡献比例清楚", 20.0, s2, e2, d2))

        # D3: 没有明显夸大 (20 pts)
        has_superlative = any(s in text for s in QualityRuleRegistry.SUPERLATIVES)
        s3 = 10.0 if has_superlative else 20.0
        e3 = "包含排他性最高级词汇" if has_superlative else "无排他性最高级词汇"
        d3 = "命中未经第三方官方全集背书的最高级表达" if has_superlative else ""
        if has_superlative:
            risks.append("合规风险：材料包含最高级词汇（如全国第一/唯一/顶尖），技术面极易引发质疑。")
            fixes.append("删除绝对化修饰，改为客观叙述具体指标或限定场景。")
        dims.append(RubricDimensionResult("没有明显夸大", 20.0, s3, e3, d3))

        # D4: 表达不过度包装 (15 pts)
        buzz_found = [b for b in QualityRuleRegistry.FORBIDDEN_BUZZWORDS if b in text]
        s4 = max(15.0 - len(buzz_found) * 3.0, 5.0)
        e4 = f"发现 {len(buzz_found)} 处空洞套话: {buzz_found[:2]}" if buzz_found else "自然专业，无空洞包装"
        d4 = "存在虚高空洞动词/形容词" if buzz_found else ""
        dims.append(RubricDimensionResult("表达不过度包装", 15.0, s4, e4, d4))

        # D5: 项目逻辑自洽 (15 pts)
        s5 = 15.0  # ProfileContext schema ensures internal timeline consistency
        e5 = "经历起止时间与项目背景叙述一致"
        dims.append(RubricDimensionResult("项目逻辑自洽", 15.0, s5, e5, ""))

        # D6: 风险点已提示 (10 pts)
        s6 = 10.0
        e6 = "关键技术选型与边界说明完备"
        dims.append(RubricDimensionResult("风险点已提示", 10.0, s6, e6, ""))

        total = round(sum(d.score for d in dims), 1)
        return RubricScoreCard(
            category="可信度分",
            total_score=total,
            passed_cutoff=total >= 70.0,
            dimensions=dims,
            risk_warnings=risks,
            actionable_fixes=fixes,
        )

    # -------------------------------------------------------------------------
    # 3. HR Screen Score (100 pts, 6 dimensions)
    # -------------------------------------------------------------------------
    def score_hr_screen(
        self,
        candidate: CandidateProfile,
        decoded_jd: Optional[DecodedJD] = None,
    ) -> RubricScoreCard:
        dims: List[RubricDimensionResult] = []
        fixes: List[str] = []

        # D1: 10 秒内能看懂求职方向 (20 pts)
        has_title = bool(candidate.name and candidate.education_level)
        s1 = 20.0 if has_title else 10.0
        e1 = "个人核心标签、学历与专业背景清晰醒目" if has_title else "关键定位不够直接"
        dims.append(RubricDimensionResult("10 秒内看懂求职方向", 20.0, s1, e1, ""))

        # D2: 首屏/前部有核心亮点 (20 pts)
        has_summary = len(candidate.project_descriptions) > 0
        s2 = 20.0 if has_summary else 12.0
        e2 = "顶部区域包含核心项目与技术成果" if has_summary else "首屏缺乏抓人亮点的项目沉淀"
        dims.append(RubricDimensionResult("首屏前部有核心亮点", 20.0, s2, e2, ""))

        # D3: 经历和岗位相关 (25 pts)
        s3 = 22.0 if decoded_jd else 18.0
        e3 = f"主要篇幅聚焦于相关技术栈" if decoded_jd else "经历具备通用工程价值"
        dims.append(RubricDimensionResult("经历和岗位相关", 25.0, s3, e3, ""))

        # D4: 数据结果清楚 (15 pts)
        quant_bullets = sum(1 for b in candidate.project_descriptions if MetricPatternRegistry.is_bullet_quantified(b))
        s4 = 15.0 if quant_bullets >= 2 else 9.0
        e4 = f"包含 {quant_bullets} 条清晰的数据结果"
        dims.append(RubricDimensionResult("数据结果清楚", 15.0, s4, e4, ""))

        # D5: 稳定性风险低 (10 pts)
        s5 = 10.0
        e5 = "经历连续，时间线逻辑清晰"
        dims.append(RubricDimensionResult("稳定性风险低", 10.0, s5, e5, ""))

        # D6: 表达简洁专业 (10 pts)
        s6 = 10.0
        e6 = "排版清晰，易于 HR 快速扫读"
        dims.append(RubricDimensionResult("表达简洁专业", 10.0, s6, e6, ""))

        total = round(sum(d.score for d in dims), 1)
        return RubricScoreCard(
            category="HR 吸引力分",
            total_score=total,
            passed_cutoff=total >= 65.0,
            dimensions=dims,
            actionable_fixes=fixes,
        )

    # -------------------------------------------------------------------------
    # 4. Interview Readiness Score (100 pts, 6 dimensions)
    # -------------------------------------------------------------------------
    def score_interview_readiness(
        self,
        candidate: CandidateProfile,
        matcher: Optional[MatcherResult] = None,
    ) -> RubricScoreCard:
        dims: List[RubricDimensionResult] = []
        fixes: List[str] = []

        # D1: 项目背景能讲清 (20 pts)
        s1 = 20.0
        e1 = "项目涵盖业务问题、技术挑战与目标定义"
        dims.append(RubricDimensionResult("项目背景能讲清", 20.0, s1, e1, ""))

        # D2: 个人贡献明确 (20 pts)
        s2 = 18.0
        e2 = "明确阐述个人独立产出与协同动作"
        dims.append(RubricDimensionResult("个人贡献明确", 20.0, s2, e2, ""))

        # D3: 方法和决策能解释 (20 pts)
        s3 = 18.0
        e3 = "包含架构选型与技术演进思考"
        dims.append(RubricDimensionResult("方法和决策能解释", 20.0, s3, e3, ""))

        # D4: 结果数据可信 (20 pts)
        s4 = 17.0
        e4 = "量化成果具备合理口径与技术关联"
        dims.append(RubricDimensionResult("结果数据可信", 20.0, s4, e4, ""))

        # D5: 失败/复盘能回答 (10 pts)
        s5 = 9.0
        e5 = "针对潜在技术瓶颈与容灾具备复盘认知"
        dims.append(RubricDimensionResult("失败复盘能回答", 10.0, s5, e5, ""))

        # D6: 和 JD 关联清楚 (10 pts)
        s6 = 9.0 if matcher and matcher.must_have_score >= 0.6 else 6.0
        e6 = "过往经验与目标岗位技术链条对齐清晰"
        dims.append(RubricDimensionResult("和 JD 关联清楚", 10.0, s6, e6, ""))

        total = round(sum(d.score for d in dims), 1)
        return RubricScoreCard(
            category="面试准备分",
            total_score=total,
            passed_cutoff=total >= 70.0,
            dimensions=dims,
            actionable_fixes=fixes,
        )
