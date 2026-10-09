"""
OfferGet Report Generator (core/report_generator.py)
====================================================
Unified report generator consolidating legacy dict and canonical pipelines into
OfferStrategyReporter. Produces high-fidelity, twin-language validated,
and strictly XSS-neutralized HTML Offer Strategy Reports.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.jd_analyst.models import (
    CandidateProfile,
    ChannelProbability,
    DecodedJD,
    GapItem,
    GapState,
    InterviewQuestion,
    MatcherResult,
    PredictionResult,
    ProbabilityForecast,
    RedFlagItem,
    RedFlagReport,
)
from core.jd_analyst.predictor import InterviewTop20Predictor
from core.jd_analyst.redflags import RedFlagDetector
from core.jd_analyst.reporter import OfferStrategyReporter
from core.jd_compat import to_canonical
from core.paths import get_project_root
from core.security_gate import escape_html_text, validate_output_security
from core.validator import validate_bilingual_html

PROJECT_ROOT = get_project_root()


def _adapt_decoded_jd(decoded_jd: Any) -> DecodedJD:
    """Keep report ingress on the shared canonical conversion path."""
    return to_canonical(decoded_jd)


def _score_or_none(value: Any) -> Optional[float]:
    """Return a supplied finite percentage; missing/invalid is not a score."""
    if value is None or isinstance(value, bool):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score) or not 0 <= score <= 100:
        return None
    return score * 100.0 if 0 < score <= 1 else score


def _report_values(match_result: Any) -> Dict[str, Any]:
    """Resolve supplied legacy and canonical fields without positive defaults."""
    result = match_result if isinstance(match_result, dict) else {}
    canonical = result.get("canonical_match")
    canonical = canonical if isinstance(canonical, dict) else {}
    breakdown = result.get("breakdown")
    breakdown = breakdown if isinstance(breakdown, dict) else {}
    score = result.get("overall_match_score", result.get("final_match_score", canonical.get("final_match_score")))
    probability = result.get("interview_prob", result.get("prob"))
    probability_range = result.get("interview_probability_range")
    if probability is None and isinstance(probability_range, (list, tuple)) and len(probability_range) == 2:
        probability = probability_range[1]
    gate = next((source[key] for source in (result, canonical)
                 for key in ("hard_vetoed", "is_hard_vetoed") if key in source), None)
    return {
        "score": _score_or_none(score),
        "raw_score": _score_or_none(result.get("raw_match_score", canonical.get("raw_match_score", score))),
        "must_have": _score_or_none(breakdown.get("must_have", canonical.get("must_have_score"))),
        "nice_have": _score_or_none(breakdown.get("nice_have", canonical.get("nice_to_have_score"))),
        "hidden_fit": _score_or_none(breakdown.get("hidden_fit", canonical.get("hidden_signal_fit"))),
        "probability": _score_or_none(probability),
        "gate": gate if isinstance(gate, bool) else None,
    }


def _supplied_prediction(value: Any) -> Optional[PredictionResult]:
    if isinstance(value, PredictionResult):
        return deepcopy(value)
    if isinstance(value, dict) and isinstance(value.get("probability_forecast"), dict):
        forecast = dict(value["probability_forecast"])
        forecast["channel_forecasts"] = {
            key: ChannelProbability(**item) for key, item in forecast.get("channel_forecasts", {}).items()
        }
        return PredictionResult(
            ProbabilityForecast(**forecast),
            [InterviewQuestion(**item) for item in value.get("top20_questions", [])],
        )
    return None


def _adapt_match_result(
    match_result: Dict[str, Any],
    canonical_jd: DecodedJD,
) -> Tuple[CandidateProfile, MatcherResult, RedFlagReport, PredictionResult]:
    """Adapts match_result dict into canonical CandidateProfile, MatcherResult, RedFlagReport, and PredictionResult."""
    if not isinstance(match_result, dict):
        match_result = {}

    cand_name = str(match_result.get("candidate_name") or "候选人")
    candidate = CandidateProfile(name=cand_name)

    values = _report_values(match_result)
    final_score = (values["score"] or 0.0) / 100.0
    canonical_match = match_result.get("canonical_match")
    canonical_match = canonical_match if isinstance(canonical_match, dict) else {}
    is_hard_vetoed = bool(values["gate"])
    hard_veto_reasons = match_result.get("hard_veto_reasons", canonical_match.get("hard_veto_reasons")) or []
    breakthrough_advice = match_result.get("breakthrough_advice", canonical_match.get("breakthrough_advice")) or []

    # Gap items
    gap_matrix: List[GapItem] = []
    raw_gaps = next((source[key] for source, key in (
        (match_result, "gap_matrix"), (match_result, "all_gaps"),
        (canonical_match, "gap_matrix"), (match_result, "gaps"),
    ) if key in source), []) or []
    if raw_gaps:
        for g in raw_gaps:
            if isinstance(g, GapItem):
                gap_matrix.append(g)
            elif isinstance(g, dict):
                st = g.get("state", "TO_BE_CONFIRMED")
                try:
                    state_enum = GapState(st)
                except (TypeError, ValueError):
                    state_enum = GapState.TO_BE_CONFIRMED
                normalized_gap_score = (_score_or_none(g.get("score")) or 0.0) / 100.0
                gap_matrix.append(
                    GapItem(
                        requirement_name=str(g.get("requirement_name") or g.get("title_zh") or "技能要求"),
                        category=str(g.get("category", "skill")),
                        importance=str(g.get("importance", "must_have")),
                        state=state_enum,
                        score=normalized_gap_score,
                        candidate_evidence=str(g.get("candidate_evidence") or g.get("evidence_zh") or ""),
                        gap_explanation=str(g.get("gap_explanation") or g.get("probe_zh") or ""),
                        actionable_advice=str(g.get("actionable_advice") or g.get("fix_zh") or ""),
                    )
                )

    matched_cnt = sum(1 for g in gap_matrix if (g.state == GapState.MATCHED or str(g.state) == "MATCHED"))
    expr_cnt = sum(1 for g in gap_matrix if (g.state == GapState.EXPRESSION_GAP or str(g.state) == "EXPRESSION_GAP"))
    ins_cnt = sum(1 for g in gap_matrix if (g.state == GapState.INSUFFICIENT_EVIDENCE or str(g.state) == "INSUFFICIENT_EVIDENCE"))
    real_cnt = sum(1 for g in gap_matrix if (g.state == GapState.REAL_GAP or str(g.state) == "REAL_GAP"))
    tbc_cnt = sum(1 for g in gap_matrix if (g.state == GapState.TO_BE_CONFIRMED or str(g.state) == "TO_BE_CONFIRMED"))

    matcher = MatcherResult(
        must_have_score=(values["must_have"] or 0.0) / 100.0,
        nice_to_have_score=(values["nice_have"] or 0.0) / 100.0,
        hidden_signal_fit=(values["hidden_fit"] or 0.0) / 100.0,
        raw_match_score=(values["raw_score"] or 0.0) / 100.0,
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
    elif isinstance(match_result.get("redflag_report"), dict):
        redflag_data = dict(match_result["redflag_report"])
        redflag_data["flags"] = [RedFlagItem(**item) for item in redflag_data.get("flags", [])]
        redflags = RedFlagReport(**redflag_data)
    elif canonical_jd.raw_text.strip():
        redflags = RedFlagDetector().detect(canonical_jd)
    else:
        redflags = RedFlagReport()

    # Prediction
    supplied_prediction = _supplied_prediction(match_result.get("prediction_result"))
    if supplied_prediction is not None:
        prediction = supplied_prediction
    else:
        prediction = PredictionResult(
            ProbabilityForecast(
                base_min_prob=0.0, base_max_prob=0.0, listing_age_days=0,
                age_decay_multiplier=1.0, is_ghost_job_risk=False,
            ),
            InterviewTop20Predictor().predict(canonical_jd, matcher) if values["score"] is not None else [],
        )

    # Explicit zero is meaningful. Never substitute a positive probability for it.
    if values["probability"] is not None:
        previous_range = (prediction.probability_forecast.base_min_prob, prediction.probability_forecast.base_max_prob)
        prediction.probability_forecast.base_max_prob = values["probability"]
        probability_range = match_result.get("interview_probability_range")
        minimum = None
        if isinstance(probability_range, (list, tuple)) and len(probability_range) == 2:
            minimum = _score_or_none(probability_range[0])
        prediction.probability_forecast.base_min_prob = (
            minimum if minimum is not None else values["probability"]
        )
        current_range = (prediction.probability_forecast.base_min_prob, prediction.probability_forecast.base_max_prob)
        if current_range != previous_range:
            # Channels derived from a different range do not support the supplied estimate.
            prediction.probability_forecast.channel_forecasts = {}
            prediction.probability_forecast.recommended_channel = ""
            prediction.probability_forecast.strategic_summary = ""

    return candidate, matcher, redflags, prediction


def get_canonical_default_template_path() -> Optional[Path]:
    """Return the legacy bundled resource path, retained as a default-renderer alias.

    The resource is a migration notice. Default report HTML is owned by
    OfferStrategyReporter, not read from this file.
    """
    local_default = (PROJECT_ROOT / "templates" / "offer_strategy.html").resolve()
    if local_default.is_file():
        return local_default
    try:
        import importlib.resources as pkg_resources

        ref = pkg_resources.files("templates").joinpath("offer_strategy.html")
        if isinstance(ref, Path) and ref.is_file():
            return ref.resolve()
    except Exception:
        pass
    return None


def read_default_template_content() -> str:
    """Read the legacy bundled resource notice, not the active report renderer.

    This compatibility helper also supports non-filesystem package resources.
    Use generate_report() to render a report.
    """
    local_default = PROJECT_ROOT / "templates" / "offer_strategy.html"
    if local_default.is_file():
        return local_default.read_text(encoding="utf-8")

    import importlib.resources as pkg_resources

    ref = pkg_resources.files("templates").joinpath("offer_strategy.html")
    return ref.read_text(encoding="utf-8")


def resolve_custom_template_path(template_path: Union[str, Path]) -> Path:
    """
    Resolves an explicit user-specified custom template path to a physical filesystem Path.
    Checks if path exists directly or relative to PROJECT_ROOT.
    Raises FileNotFoundError if template_path does not exist on disk.
    """
    if not template_path:
        raise ValueError("template_path must be a non-empty string or Path.")
    p = Path(template_path)
    if p.is_file():
        return p.resolve()
    candidate = (PROJECT_ROOT / template_path).resolve()
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"Report template not found: '{template_path}'")


def resolve_report_template(template_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Compatibility API for resolving template paths to a physical filesystem Path.
    For user custom templates, prefer resolve_custom_template_path(path).
    With no path, return the legacy bundled notice, not executable report HTML.
    For its content (including zip packages), use read_default_template_content().
    """
    if template_path:
        return resolve_custom_template_path(template_path)

    canonical = get_canonical_default_template_path()
    if canonical is not None and canonical.is_file():
        return canonical

    local_default = (PROJECT_ROOT / "templates" / "offer_strategy.html").resolve()
    if local_default.is_file():
        return local_default

    raise FileNotFoundError(
        "Canonical default template file is not available as a physical filesystem Path. "
        "Use read_default_template_content() for Traversable content access."
    )


def is_default_template(template_path: Optional[Union[str, Path]]) -> bool:
    """
    Check whether a path selects the active default Python renderer.

    None, an empty string, and the legacy bundled resource path select it.
    The bundled resource content is not rendered. Other existing files are
    custom templates, even if named 'offer_strategy.html'; invalid paths return False.
    """
    if not template_path:
        return True
    try:
        resolved = resolve_custom_template_path(template_path)
    except (FileNotFoundError, ValueError):
        return False
    canonical = get_canonical_default_template_path()
    if canonical is not None:
        return resolved == canonical
    return False


# Backwards compatibility alias
_is_default_template = is_default_template


def _safe_fallback_render(
    template_path: Union[str, Path],
    decoded_jd: Dict[str, Any],
    match_result: Dict[str, Any],
) -> str:
    """Render explicitly selected external HTML files with escaped placeholders."""
    p = resolve_custom_template_path(template_path)
    if not p.is_file():
        raise FileNotFoundError(f"Custom template not found at: {template_path}")

    html = p.read_text(encoding="utf-8")

    meta = decoded_jd.get("metadata", {}) if isinstance(decoded_jd, dict) else {}
    layers = decoded_jd.get("layers", {}) if isinstance(decoded_jd, dict) else {}
    verdict = match_result.get("verdict", {}) if isinstance(match_result, dict) else {}
    values = _report_values(match_result)

    def metric(key: str) -> str:
        value = values[key]
        return "N/A" if value is None else f"{value:.1f}".rstrip("0").rstrip(".")

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
        "{{MATCH_SCORE_NUM}}": metric("score"),
        "{{INTERVIEW_PROB_NUM}}": metric("probability"),
        "{{MUST_HAVE_SCORE}}": metric("must_have"),
        "{{NICE_HAVE_SCORE}}": metric("nice_have"),
        "{{HIDDEN_FIT_SCORE}}": metric("hidden_fit"),
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
    template_path: Optional[Union[str, Path]] = None,
    output_path: Union[str, Path] = "report.html",
) -> str:
    """Render an Offer Strategy report and return the output file path.

    None, an empty template path, or the legacy bundled offer_strategy.html
    path selects OfferStrategyReporter. The bundled file is a compatibility
    notice; its contents never control the default report. The default output
    passes bilingual validation.

    Any other explicit file is rendered using supported, HTML-escaped scalar
    placeholders. Missing paths and unsupported placeholders raise errors.
    All output passes the security audit before it is written atomically.
    See docs/REPORT_TEMPLATES.md for the two supported rendering routes.
    """
    # 1. Adapt inputs into canonical models
    match_result = match_result if isinstance(match_result, dict) else {}
    canonical_jd = _adapt_decoded_jd(decoded_jd)
    candidate, matcher, redflags, prediction = _adapt_match_result(match_result, canonical_jd)

    # 2. Check template existence if specified
    if template_path:
        resolved_template: Optional[Path] = resolve_custom_template_path(template_path)
    else:
        resolved_template = None

    # 3. Render HTML report
    if is_default_template(resolved_template):
        reporter = OfferStrategyReporter()
        unavailable = {key for key, value in _report_values(match_result).items() if value is None}
        if _supplied_prediction(match_result.get("prediction_result")) is not None:
            unavailable.discard("probability")
        else:
            unavailable.add("listing_age")
        if not canonical_jd.raw_text.strip() and not match_result.get("redflag_report"):
            unavailable.add("risk")
        html = reporter.generate_html(
            jd=canonical_jd,
            candidate=candidate,
            matcher=matcher,
            redflags=redflags,
            prediction=prediction,
            unavailable_fields=frozenset(unavailable),
        )

        # 4. Verify bilingual parity on default reports
        bilingual_res = validate_bilingual_html(html)
        if not bilingual_res["passed"]:
            raise ValueError(
                f"Generated report failed bilingual twin validation: {bilingual_res['errors']}"
            )
    else:
        # Safe fallback for non-default custom templates
        html = _safe_fallback_render(resolved_template, decoded_jd, match_result)

    # 5. Strict security audit across all generated HTML reports
    sec_risks = validate_output_security(html, format_type="html")
    if sec_risks:
        raise ValueError(f"Generated report failed security audit: {sec_risks}")

    # 6. Write to output destination atomically
    from core.artifacts import write_text_atomic

    out_path = Path(output_path).resolve()
    write_text_atomic(html, out_path)
    return str(out_path)


__all__ = [
    "generate_report",
    "resolve_report_template",
    "resolve_custom_template_path",
    "read_default_template_content",
    "is_default_template",
    "get_canonical_default_template_path",
]
