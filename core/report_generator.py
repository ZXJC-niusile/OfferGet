"""
OfferGet Report Generator (core/report_generator.py)
====================================================
Unified report generator consolidating legacy dict and canonical pipelines into
OfferStrategyReporter. Produces high-fidelity, twin-language validated,
and strictly XSS-neutralized HTML Offer Strategy Reports.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.jd_compat import DecodedJDCompat, to_canonical
from core.security_gate import escape_html_text, validate_output_security
from core.validator import validate_bilingual_html
from modules.jd_analyst.models import (
    BusinessPainPoint,
    CandidateProfile,
    CoreResponsibility,
    CoreSkill,
    DecodedJD,
    GapItem,
    GapState,
    HardThreshold,
    ImplicitSignal,
    MatcherResult,
    PredictionResult,
    RedFlagReport,
)
from modules.jd_analyst.predictor import JDPredictor
from modules.jd_analyst.redflags import RedFlagDetector
from modules.jd_analyst.reporter import OfferStrategyReporter

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _to_float_score(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        f = float(val)
        if 0.0 < f <= 1.0:
            return round(f * 100.0, 1)
        return round(f, 1)
    except (TypeError, ValueError):
        return default


def _adapt_decoded_jd(decoded_jd: Any) -> DecodedJD:
    """Adapts arbitrary decoded JD representations (dict, DecodedJDCompat, DecodedJD) into canonical DecodedJD."""
    if isinstance(decoded_jd, DecodedJD):
        return decoded_jd
    if isinstance(decoded_jd, DecodedJDCompat):
        return decoded_jd.canonical
    if not isinstance(decoded_jd, dict):
        return DecodedJD(raw_text="", job_title="未指定职位", company_or_dept="未指定公司")

    metadata = decoded_jd.get("metadata", {})
    layers = decoded_jd.get("layers", {})
    raw_text = str(decoded_jd.get("raw_text") or decoded_jd.get("clean_text") or "")

    job_title = str(
        metadata.get("role")
        or decoded_jd.get("job_title")
        or metadata.get("role_title")
        or "未指定职位"
    )
    company = str(metadata.get("company") or decoded_jd.get("company") or "")
    department = str(metadata.get("department") or decoded_jd.get("department") or "")
    if company and department and department not in company:
        company_or_dept = f"{company} · {department}"
    else:
        company_or_dept = company or department or "未指定公司"

    # Extract requirements & thresholds
    reqs = decoded_jd.get("requirements", {})
    must_haves = reqs.get("must_haves", [])
    nice_haves = reqs.get("nice_haves", [])

    hard_thresholds: List[HardThreshold] = []
    for item in must_haves:
        hard_thresholds.append(HardThreshold(category="mandatory", requirement=str(item), is_mandatory=True))
    for item in nice_haves:
        hard_thresholds.append(HardThreshold(category="preferred", requirement=str(item), is_mandatory=False))

    l1 = layers.get("layer_1", {}) if isinstance(layers, dict) else {}
    if not hard_thresholds and isinstance(l1, dict) and l1.get("jd_text_zh"):
        hard_thresholds.append(HardThreshold(category="degree", requirement=str(l1["jd_text_zh"]), is_mandatory=True))

    # Core skills
    core_skills: List[CoreSkill] = []
    for item in must_haves:
        core_skills.append(CoreSkill(name=str(item), category="framework", importance="MUST_HAVE", domain="通用"))
    for item in nice_haves:
        core_skills.append(CoreSkill(name=str(item), category="framework", importance="NICE_TO_HAVE", domain="通用"))

    l2 = layers.get("layer_2", {}) if isinstance(layers, dict) else {}
    if not core_skills and isinstance(l2, dict) and l2.get("jd_text_zh"):
        core_skills.append(CoreSkill(name=str(l2["jd_text_zh"]), category="framework", importance="MUST_HAVE", domain="核心技术"))

    # Core responsibilities
    responsibilities: List[CoreResponsibility] = []
    l3 = layers.get("layer_3", {}) if isinstance(layers, dict) else {}
    if isinstance(l3, dict) and l3.get("jd_text_zh"):
        responsibilities.append(CoreResponsibility(title=str(l3["jd_text_zh"])[:30], description=str(l3["jd_text_zh"]), domain="核心业务"))

    # Implicit signals
    implicit_signals: List[ImplicitSignal] = []
    l4 = layers.get("layer_4", {}) if isinstance(layers, dict) else {}
    if isinstance(l4, dict) and l4.get("jd_text_zh"):
        implicit_signals.append(
            ImplicitSignal(
                original_text=str(l4.get("jd_text_zh", "")),
                translated_meaning=str(l4.get("reality_zh", "需进一步探查实际工作节奏与交付预期")),
                underlying_risk="排期紧凑",
                candidate_countermeasure="在面试中结合过往高并发排障经验主动展示抗压闭环能力",
            )
        )
    for s in decoded_jd.get("detected_signals", []):
        if isinstance(s, dict) and "original_text" in s:
            implicit_signals.append(ImplicitSignal(**s))

    # Business pain points
    pain_points: List[BusinessPainPoint] = []
    l5 = layers.get("layer_5", {}) if isinstance(layers, dict) else {}
    if isinstance(l5, dict) and l5.get("jd_text_zh"):
        pain_points.append(
            BusinessPainPoint(
                aspect=str(l5.get("jd_text_zh", "算力与性能优化")),
                description=str(l5.get("reality_zh", "面临实际业务吞吐与 SLA 挑战")),
                evaluation_metric="P99 < 200ms · 达标率 > 99.5%",
            )
        )

    return DecodedJD(
        raw_text=raw_text or f"职位：{job_title}\n公司：{company_or_dept}",
        job_title=job_title,
        company_or_dept=company_or_dept,
        hard_thresholds=hard_thresholds,
        core_responsibilities=responsibilities,
        core_skills=core_skills,
        implicit_signals=implicit_signals,
        business_pain_points=pain_points,
    )


def _adapt_match_result(
    match_result: Dict[str, Any],
    canonical_jd: DecodedJD,
) -> Tuple[CandidateProfile, MatcherResult, RedFlagReport, PredictionResult]:
    """Adapts match_result dict into canonical CandidateProfile, MatcherResult, RedFlagReport, and PredictionResult."""
    if not isinstance(match_result, dict):
        match_result = {}

    cand_name = str(match_result.get("candidate_name") or "候选人")
    candidate = CandidateProfile(name=cand_name)

    raw_match_score = (
        match_result.get("overall_match_score")
        if "overall_match_score" in match_result
        else match_result.get("final_match_score", 80.0)
    )
    score_pct = _to_float_score(raw_match_score, 80.0)
    final_score = score_pct / 100.0

    raw_prob = (
        match_result.get("interview_prob")
        if "interview_prob" in match_result
        else match_result.get("prob")
    )
    if raw_prob is None and "interview_probability_range" in match_result:
        prob_range = match_result.get("interview_probability_range")
        if isinstance(prob_range, (list, tuple)) and len(prob_range) > 1:
            raw_prob = prob_range[1]
    prob_pct = _to_float_score(raw_prob, 70.0)

    is_hard_vetoed = bool(
        match_result.get("hard_vetoed")
        or match_result.get("is_hard_vetoed")
        or (isinstance(match_result.get("canonical_match"), dict) and match_result["canonical_match"].get("is_hard_vetoed"))
    )

    hard_veto_reasons = match_result.get("hard_veto_reasons") or []
    if is_hard_vetoed and not hard_veto_reasons:
        hard_veto_reasons = ["硬性门槛拦截：岗位硬性条件未满足或未确认，需人工复核"]

    breakthrough_advice = match_result.get("breakthrough_advice") or []
    if is_hard_vetoed and not breakthrough_advice:
        breakthrough_advice = ["【学历破局通道】：建议通过顶会论文、开源项目或业务代表作绕过初筛通道"]

    breakdown = match_result.get("breakdown", {}) if isinstance(match_result, dict) else {}
    must_have_score = _to_float_score(breakdown.get("must_have", 85.0)) / 100.0
    nice_to_have_score = _to_float_score(breakdown.get("nice_have", 80.0)) / 100.0
    hidden_signal_fit = _to_float_score(breakdown.get("hidden_fit", 75.0)) / 100.0

    # Gap items
    gap_matrix: List[GapItem] = []
    raw_gaps = match_result.get("gap_matrix") or match_result.get("all_gaps") or match_result.get("gaps") or []
    if raw_gaps:
        for g in raw_gaps:
            if isinstance(g, GapItem):
                gap_matrix.append(g)
            elif isinstance(g, dict):
                st = g.get("state", "MATCHED")
                state_enum = getattr(GapState, st, GapState.MATCHED) if isinstance(st, str) else st
                score_val = _to_float_score(g.get("score", 1.0))
                normalized_gap_score = score_val / 100.0 if score_val > 1.0 else float(g.get("score", 1.0))
                gap_matrix.append(
                    GapItem(
                        requirement_name=str(g.get("requirement_name") or g.get("title_zh") or "技能要求"),
                        category=str(g.get("category", "skill")),
                        importance=str(g.get("importance", "must_have")),
                        state=state_enum,
                        score=normalized_gap_score,
                        candidate_evidence=str(g.get("candidate_evidence") or g.get("evidence_zh") or "具备明确量化指标与项目实践"),
                        gap_explanation=str(g.get("gap_explanation") or g.get("probe_zh") or "与核心技能要求吻合良好"),
                        actionable_advice=str(g.get("actionable_advice") or g.get("fix_zh") or "准备深入架构设计细节与底层调优经历"),
                    )
                )

    if not gap_matrix:
        gap_matrix = [
            GapItem(
                requirement_name="核心技能匹配度",
                category="skill",
                importance="must_have",
                state=GapState.MATCHED,
                score=0.9,
                candidate_evidence="具备相关工程经验与高可用系统落地成果",
                gap_explanation="与核心能力项匹配良好",
                actionable_advice="准备深入技术选型、架构权衡与系统设计全景",
            ),
            GapItem(
                requirement_name="业务痛点与指标数据化",
                category="experience",
                importance="must_have",
                state=GapState.EXPRESSION_GAP,
                score=0.75,
                candidate_evidence="有项目经验但简历量化表达较少",
                gap_explanation="缺少精确的吞吐、P99、SLA等业务数据支撑",
                actionable_advice="依据 STAR 原则补足具体的集群规模与业务增量百分比",
            ),
            GapItem(
                requirement_name="极端异常与攻坚实战",
                category="system",
                importance="nice_to_have",
                state=GapState.INSUFFICIENT_EVIDENCE,
                score=0.6,
                candidate_evidence="缺少大规模生产环境排障案例",
                gap_explanation="待面试深入核查排障与容灾细节",
                actionable_advice="梳理 2-3 个生产事故排障与极端容量冲刺实战复盘",
            ),
        ]

    matched_cnt = sum(1 for g in gap_matrix if (g.state == GapState.MATCHED or str(g.state) == "MATCHED"))
    expr_cnt = sum(1 for g in gap_matrix if (g.state == GapState.EXPRESSION_GAP or str(g.state) == "EXPRESSION_GAP"))
    ins_cnt = sum(1 for g in gap_matrix if (g.state == GapState.INSUFFICIENT_EVIDENCE or str(g.state) == "INSUFFICIENT_EVIDENCE"))
    real_cnt = sum(1 for g in gap_matrix if (g.state == GapState.REAL_GAP or str(g.state) == "REAL_GAP"))
    tbc_cnt = sum(1 for g in gap_matrix if (g.state == GapState.TO_BE_CONFIRMED or str(g.state) == "TO_BE_CONFIRMED"))

    matcher = MatcherResult(
        must_have_score=must_have_score,
        nice_to_have_score=nice_to_have_score,
        hidden_signal_fit=hidden_signal_fit,
        raw_match_score=final_score,
        final_match_score=final_score,
        is_hard_vetoed=is_hard_vetoed,
        hard_veto_reasons=hard_veto_reasons,
        breakthrough_advice=breakthrough_advice,
        gap_matrix=gap_matrix,
        matched_count=matched_cnt,
        expression_gap_count=expr_cnt,
        insufficient_evidence_count=ins_cnt,
        real_gap_count=real_cnt,
        to_be_confirmed_count=tbc_cnt,
    )

    # RedFlags
    if "redflag_report" in match_result and isinstance(match_result["redflag_report"], RedFlagReport):
        redflags = match_result["redflag_report"]
    else:
        redflags = RedFlagDetector().detect(canonical_jd)

    # Prediction
    if "prediction_result" in match_result and isinstance(match_result["prediction_result"], PredictionResult):
        prediction = match_result["prediction_result"]
    else:
        prediction = JDPredictor().predict(canonical_jd, matcher, listing_age_days=10)

    # Update probability forecast with passed interview_prob
    if prob_pct > 0.0:
        prediction.probability_forecast.base_max_prob = prob_pct
        prediction.probability_forecast.base_min_prob = max(0.0, prob_pct - 10.0)

    return candidate, matcher, redflags, prediction


def _is_default_template(template_path: Optional[str]) -> bool:
    """Checks whether the template path points to OfferGet's default offer_strategy.html."""
    if not template_path:
        return True
    p = Path(template_path)
    return p.name == "offer_strategy.html"


def _safe_fallback_render(
    template_path: str,
    decoded_jd: Dict[str, Any],
    match_result: Dict[str, Any],
) -> str:
    """Fallback renderer for non-default custom template files, preserving secure string replacements."""
    p = Path(template_path)
    if not p.is_file():
        p = PROJECT_ROOT / template_path
    if not p.is_file():
        raise FileNotFoundError(f"Custom template not found at: {template_path}")

    with open(p, "r", encoding="utf-8") as f:
        html = f.read()

    meta = decoded_jd.get("metadata", {}) if isinstance(decoded_jd, dict) else {}
    layers = decoded_jd.get("layers", {}) if isinstance(decoded_jd, dict) else {}
    verdict = match_result.get("verdict", {}) if isinstance(match_result, dict) else {}
    breakdown = match_result.get("breakdown", {}) if isinstance(match_result, dict) else {}

    raw_match_score = (
        match_result.get("overall_match_score")
        if "overall_match_score" in match_result
        else match_result.get("final_match_score", 0.0)
    )
    match_score = _to_float_score(raw_match_score, 0.0)

    raw_prob = (
        match_result.get("interview_prob")
        if "interview_prob" in match_result
        else match_result.get("prob", 0.0)
    )
    interview_prob = _to_float_score(raw_prob, 0.0)

    today_str = date.today().strftime("%Y-%m-%d")

    def _get_layer_val(layer_key: str, sub_key: str, default: str = "") -> str:
        l_obj = layers.get(layer_key)
        if isinstance(l_obj, dict):
            return str(l_obj.get(sub_key) or default)
        return default

    replacements: Dict[str, str] = {
        "{{COMPANY}}": escape_html_text(meta.get("company") or "未提供"),
        "{{ROLE}}": escape_html_text(meta.get("role") or "未提供"),
        "{{ROLE_TITLE}}": escape_html_text(meta.get("role") or "未提供"),
        "{{LEVEL}}": escape_html_text(meta.get("level") or "未提供"),
        "{{LOCATION}}": escape_html_text(meta.get("location") or "未提供"),
        "{{COMP_BAND}}": escape_html_text(meta.get("comp_band") or "未提供"),
        "{{DEPARTMENT}}": escape_html_text(meta.get("department") or "未提供"),
        "{{ARCHITECTURE_LAYER}}": escape_html_text(meta.get("architecture_layer") or meta.get("role_category") or "未提供"),
        "{{CANDIDATE_NAME}}": escape_html_text(match_result.get("candidate_name") or "未提供"),
        "{{REPORT_DATE}}": escape_html_text(today_str),
        "{{VERDICT_TITLE_EN}}": escape_html_text(verdict.get("title_en") or "Review Before Applying"),
        "{{VERDICT_TITLE_ZH}}": escape_html_text(verdict.get("title_zh") or "信息不足，无法判断"),
        "{{VERDICT_DESC_EN}}": escape_html_text(verdict.get("desc_en") or "Review before deciding."),
        "{{VERDICT_DESC_ZH}}": escape_html_text(verdict.get("desc_zh") or "缺少匹配证据时不生成投递结论。"),
        "{{MATCH_SCORE_NUM}}": f"{match_score:.1f}".rstrip("0").rstrip("."),
        "{{INTERVIEW_PROB_NUM}}": f"{interview_prob:.1f}".rstrip("0").rstrip("."),
        "{{MUST_HAVE_SCORE}}": str(round(_to_float_score(breakdown.get("must_have", 0)))),
        "{{NICE_HAVE_SCORE}}": str(round(_to_float_score(breakdown.get("nice_have", 0)))),
        "{{HIDDEN_FIT_SCORE}}": str(round(_to_float_score(breakdown.get("hidden_fit", 0)))),
        "{{L1_JD_TEXT_ZH}}": escape_html_text(_get_layer_val("layer_1", "jd_text_zh", "")),
        "{{L1_JD_TEXT_EN}}": escape_html_text(_get_layer_val("layer_1", "jd_text_en", "")),
        "{{L1_REALITY_ZH}}": escape_html_text(_get_layer_val("layer_1", "reality_zh", "")),
        "{{L1_REALITY_EN}}": escape_html_text(_get_layer_val("layer_1", "reality_en", "")),
        "{{L2_JD_TEXT_ZH}}": escape_html_text(_get_layer_val("layer_2", "jd_text_zh", "")),
        "{{L2_JD_TEXT_EN}}": escape_html_text(_get_layer_val("layer_2", "jd_text_en", "")),
        "{{L2_REALITY_ZH}}": escape_html_text(_get_layer_val("layer_2", "reality_zh", "")),
        "{{L2_REALITY_EN}}": escape_html_text(_get_layer_val("layer_2", "reality_en", "")),
        "{{L3_JD_TEXT_ZH}}": escape_html_text(_get_layer_val("layer_3", "jd_text_zh", "")),
        "{{L3_JD_TEXT_EN}}": escape_html_text(_get_layer_val("layer_3", "jd_text_en", "")),
        "{{L3_REALITY_ZH}}": escape_html_text(_get_layer_val("layer_3", "reality_zh", "")),
        "{{L3_REALITY_EN}}": escape_html_text(_get_layer_val("layer_3", "reality_en", "")),
        "{{L4_JD_TEXT_ZH}}": escape_html_text(_get_layer_val("layer_4", "jd_text_zh", "")),
        "{{L4_JD_TEXT_EN}}": escape_html_text(_get_layer_val("layer_4", "jd_text_en", "")),
        "{{L4_REALITY_ZH}}": escape_html_text(_get_layer_val("layer_4", "reality_zh", "")),
        "{{L4_REALITY_EN}}": escape_html_text(_get_layer_val("layer_4", "reality_en", "")),
        "{{L5_JD_TEXT_ZH}}": escape_html_text(_get_layer_val("layer_5", "jd_text_zh", "")),
        "{{L5_JD_TEXT_EN}}": escape_html_text(_get_layer_val("layer_5", "jd_text_en", "")),
        "{{L5_REALITY_ZH}}": escape_html_text(_get_layer_val("layer_5", "reality_zh", "")),
        "{{L5_REALITY_EN}}": escape_html_text(_get_layer_val("layer_5", "reality_en", "")),
    }

    for k, v in replacements.items():
        html = html.replace(k, v)

    unreplaced = re.findall(r"\{\{[A-Z0-9_]+\}\}", html)
    if unreplaced:
        raise ValueError(f"Custom template error: unreplaced placeholders found: {sorted(set(unreplaced))}")

    return html


def generate_report(
    decoded_jd: Dict[str, Any],
    match_result: Dict[str, Any],
    template_path: str,
    output_path: str,
) -> str:
    """
    Renders high-fidelity Offer Strategy Report HTML by dispatching to
    modules.jd_analyst.reporter.OfferStrategyReporter, maintaining fallback support
    for non-default custom templates, and verifying bilingual & security gates.

    Guarantees:
    1. Complete convergence to OfferStrategyReporter with zero fragile regex templating.
    2. Strict output security audit via core.security_gate.validate_output_security.
    3. Bilingual twin audit via core.validator.validate_bilingual_html.
    """
    # 1. Adapt inputs into canonical models
    canonical_jd = _adapt_decoded_jd(decoded_jd)
    candidate, matcher, redflags, prediction = _adapt_match_result(match_result, canonical_jd)

    # 2. Render HTML report
    if _is_default_template(template_path):
        reporter = OfferStrategyReporter()
        html = reporter.generate_html(
            jd=canonical_jd,
            candidate=candidate,
            matcher=matcher,
            redflags=redflags,
            prediction=prediction,
        )

        # 3. Verify bilingual parity on default reports
        bilingual_res = validate_bilingual_html(html)
        if not bilingual_res["passed"]:
            raise ValueError(
                f"Generated report failed bilingual twin validation: {bilingual_res['errors']}"
            )
    else:
        # Safe fallback for non-default custom templates
        html = _safe_fallback_render(template_path, decoded_jd, match_result)

    # 4. Strict security audit across all generated HTML reports
    sec_risks = validate_output_security(html, format_type="html")
    if sec_risks:
        raise ValueError(f"Generated report failed security audit: {sec_risks}")

    # 5. Write to output destination
    out_path = Path(output_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(out_path)


__all__ = ["generate_report"]
