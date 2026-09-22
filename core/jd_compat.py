"""Compatibility adapters for the canonical JD analyst implementation.

The typed implementation lives in ``modules.jd_analyst``.  This module keeps
OfferGet's historical dictionary-shaped API usable by the CLI and reports
without maintaining a second decoder or matcher.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from core.profile_adapter import (
    ProfileContext,
    build_profile_evidence_index,
    normalize_candidate_profile,
)
from modules.jd_analyst.decoder import JDDecoder
from modules.jd_analyst.matcher import JDMatcher
from modules.jd_analyst.models import (
    BusinessPainPoint,
    CandidateProfile,
    CoreResponsibility,
    CoreSkill,
    DecodedJD,
    HardThreshold,
    ImplicitSignal,
    MatcherResult,
    SkillImportance,
)
from modules.jd_analyst.predictor import InterviewProbabilityCalculator


from core.registry import TaxonomyRegistry

ROLE_TAXONOMIES: Dict[str, Dict[str, Any]] = TaxonomyRegistry.list_taxonomies()


class DecodedJDCompat(dict):
    """JSON-compatible legacy dict carrying the canonical typed object privately."""

    def __init__(self, payload: Dict[str, Any], canonical: DecodedJD):
        super().__init__(payload)
        self.canonical = canonical


def classify_role_taxonomy(jd_text: str) -> Dict[str, Any]:
    """Classify a JD for legacy metadata without changing canonical decoding."""
    return TaxonomyRegistry.classify_role(jd_text)



def _first_match(text: str, patterns: Iterable[str], default: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return default


def _extract_metadata(text: str) -> Dict[str, str]:
    return {
        "role": _first_match(text, [r"(?:【岗位名称】|岗位名称|职位名称|岗位|职位|Job\s*Title)[：:\s]*([^\n\r]+)"], "未指定职位"),
        "company": _first_match(text, [r"(?:【公司名称】|公司|雇主|Company)[：:\s]*([^\n\r]+)"], "未指定公司"),
        "department": _first_match(text, [r"(?:【所属部门】|部门|团队|Department|Team)[：:\s]*([^\n\r]+)"], "未指定部门"),
        "location": _first_match(text, [r"(?:【工作地点】|工作地点|地点|Location)[：:\s]*([^\n\r]+)"], "未提供"),
        "comp_band": _first_match(text, [r"(?:【薪资范围】|薪资范围|薪资|Salary|Compensation)[：:\s]*([^\n\r]+)"], "未提供"),
        "level": _first_match(text, [r"(?:【岗位级别】|岗位级别|职级|Level)[：:\s]*([^\n\r]+)"], "未提供"),
    }


def _layer(title: str, zh: str, en: str = "") -> Dict[str, str]:
    return {"title": title, "jd_text_zh": zh, "jd_text_en": en, "reality_zh": "仅基于当前 JD 原文，待候选人与招聘方进一步确认。", "reality_en": "Based on the supplied JD only; confirm with the hiring team."}


def canonical_to_legacy(canonical: DecodedJD) -> DecodedJDCompat:
    """Convert the canonical dataclass result to OfferGet's historical dict shape."""
    meta = _extract_metadata(canonical.raw_text)
    if canonical.job_title and canonical.job_title != "未指定职位":
        meta["role"] = canonical.job_title
    if canonical.company_or_dept and canonical.company_or_dept != "未指定公司":
        meta["company"] = canonical.company_or_dept
    taxonomy_info = classify_role_taxonomy(canonical.raw_text)

    responsibilities = [item.description for item in canonical.core_responsibilities]
    skills = [item.name for item in canonical.core_skills]
    domains = canonical.tech_domains or []
    pain_points = [item.description for item in canonical.business_pain_points]
    signals = [asdict(item) for item in canonical.implicit_signals]

    skill_text = "、".join(skills) if skills else "未识别明确技能"
    responsibility_text = "；".join(responsibilities) if responsibilities else "未识别明确职责"
    pain_text = "；".join(pain_points) if pain_points else "未从 JD 直接识别业务痛点"
    signal_text = "；".join(item.get("original_text", "") for item in signals) if signals else "未识别隐性信号"

    must_haves = [item.requirement for item in canonical.hard_thresholds if item.is_mandatory]
    must_haves.extend(item.name for item in canonical.core_skills if item.importance == SkillImportance.MUST_HAVE.value)
    nice_haves = [item.requirement for item in canonical.hard_thresholds if not item.is_mandatory]
    nice_haves.extend(item.name for item in canonical.core_skills if item.importance == SkillImportance.NICE_TO_HAVE.value)

    layers = {
        "layer_1": _layer("Organization & Mission", f"岗位：{meta['role']}；部门：{meta['department']}。"),
        "layer_2": _layer("Core Skills & Methods", f"识别到的技能与方法：{skill_text}。"),
        "layer_3": _layer("Responsibilities & Business Impact", f"核心职责：{responsibility_text}。"),
        "layer_4": _layer("Implicit Signals", f"原文隐性信号：{signal_text}。"),
        "layer_5": _layer("Risks & Evaluation Targets", f"业务痛点或评估线索：{pain_text}。"),
    }

    payload = {
        "metadata": {
            **meta,
            "role_category": taxonomy_info["taxonomy"]["title"],
            "role_key": taxonomy_info["role_key"],
            "dimensions": taxonomy_info["taxonomy"]["dimensions"],
            "tech_domains": domains,
        },
        "layers": layers,
        "requirements": {"must_haves": must_haves, "nice_haves": nice_haves},
        "detected_signals": signals,
        "raw_text_length": len(canonical.raw_text),
        "raw_text": canonical.raw_text,
        "clean_text": canonical.clean_text,
    }
    return DecodedJDCompat(payload, canonical)


def decode_legacy(jd_text: str) -> DecodedJDCompat:
    """Run the one canonical decoder and expose a backwards-compatible result."""
    text = jd_text or ""
    canonical = JDDecoder().decode(text)
    # The canonical module historically had an AI-specific fallback pain point.
    # Keep non-AI compatibility output neutral until role packs are introduced.
    if not re.search(r"大模型|机器学习|深度学习|Transformer|LLM|Agent|算法|模型|PyTorch|CUDA|vLLM", text, re.IGNORECASE):
        canonical.business_pain_points = []
    return canonical_to_legacy(canonical)


def _flatten_strings(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        result: List[str] = []
        for nested in value.values():
            result.extend(_flatten_strings(nested))
        return result
    return [str(value)] if value else []


def profile_to_canonical(profile_data: Union[Dict[str, Any], ProfileContext]) -> CandidateProfile:
    """Normalize the supported profile shapes without inventing defaults.

    Reuses core.profile_adapter.normalize_candidate_profile and unified evidence extraction.
    """
    if isinstance(profile_data, ProfileContext):
        norm_profile = profile_data.normalized_profile
        index = profile_data.evidence_index
    else:
        if not isinstance(profile_data, dict):
            profile_data = {}
        norm_profile = normalize_candidate_profile(profile_data)
        index = build_profile_evidence_index(norm_profile, _already_normalized=True)
    cand = norm_profile.get("candidate", {})

    degree = str(cand.get("degree") or cand.get("education_level") or "").strip()
    if "博士" in degree or "Ph.D" in degree or "PhD" in degree:
        education_level = "博士"
    elif "硕士" in degree or "Master" in degree:
        education_level = "硕士"
    elif "本科" in degree or "Bachelor" in degree:
        education_level = "本科"
    elif "大专" in degree or "专科" in degree:
        education_level = "大专"
    else:
        education_level = ""

    raw_years = cand.get("years_of_experience", cand.get("experience_years"))
    try:
        years = float(raw_years) if raw_years is not None else 0.0
    except (TypeError, ValueError):
        years = 0.0

    raw_text = json.dumps(norm_profile, ensure_ascii=False)
    return CandidateProfile(
        name=str(cand.get("name") or "候选人"),
        education_level=education_level,
        degree_school=str(cand.get("school") or cand.get("institution") or "").strip(),
        major=str(cand.get("major") or "").strip(),
        years_of_experience=years,
        skills=list(index.skills),
        project_descriptions=list(index.bullets),
        raw_resume_text=raw_text,
    )


def _legacy_to_canonical(decoded: Dict[str, Any]) -> DecodedJD:
    """Rehydrate a plain JSON legacy result when it did not come from decode_legacy."""
    raw_text = str(decoded.get("raw_text") or decoded.get("clean_text") or "")
    if raw_text and not any(k in decoded for k in ("job_title", "title", "required_skills", "core_skills", "requirements")):
        return JDDecoder().decode(raw_text)

    metadata = decoded.get("metadata", {}) if isinstance(decoded.get("metadata"), dict) else {}
    job_title = str(decoded.get("job_title") or decoded.get("title") or metadata.get("role") or "未指定职位")
    company_or_dept = str(
        decoded.get("company_or_dept")
        or decoded.get("company")
        or metadata.get("company")
        or metadata.get("department")
        or "未指定公司"
    )

    requirements = decoded.get("requirements", {}) if isinstance(decoded.get("requirements"), dict) else {}
    req_must_raw = decoded.get("required_skills") or requirements.get("must_haves") or []
    req_nice_raw = decoded.get("preferred_skills") or requirements.get("nice_haves") or []
    req_must = req_must_raw if isinstance(req_must_raw, (list, tuple)) else ([req_must_raw] if req_must_raw else [])
    req_nice = req_nice_raw if isinstance(req_nice_raw, (list, tuple)) else ([req_nice_raw] if req_nice_raw else [])

    hard_thresholds = [HardThreshold(category="other", requirement=str(item), is_mandatory=True) for item in req_must]
    nice_thresholds = [HardThreshold(category="other", requirement=str(item), is_mandatory=False) for item in req_nice]

    skills: List[CoreSkill] = []
    if "core_skills" in decoded and isinstance(decoded["core_skills"], (list, tuple)):
        for item in decoded["core_skills"]:
            if isinstance(item, CoreSkill):
                skills.append(item)
            elif isinstance(item, dict):
                skills.append(CoreSkill(name=str(item.get("name", "")), category=str(item.get("category", "other")), importance=str(item.get("importance", SkillImportance.MUST_HAVE.value)), domain=str(item.get("domain", "general"))))
            else:
                skills.append(CoreSkill(name=str(item), category="other", importance=SkillImportance.MUST_HAVE.value, domain="general"))
    else:
        skills.extend(CoreSkill(name=str(item), category="other", importance=SkillImportance.MUST_HAVE.value, domain="general") for item in req_must)
        skills.extend(CoreSkill(name=str(item), category="other", importance=SkillImportance.NICE_TO_HAVE.value, domain="general") for item in req_nice)

    responsibilities: List[CoreResponsibility] = []
    if "core_responsibilities" in decoded and isinstance(decoded["core_responsibilities"], (list, tuple)):
        for item in decoded["core_responsibilities"]:
            if isinstance(item, CoreResponsibility):
                responsibilities.append(item)
            elif isinstance(item, dict):
                responsibilities.append(CoreResponsibility(title=str(item.get("title", "")), description=str(item.get("description", "")), domain=str(item.get("domain", "general"))))
            else:
                responsibilities.append(CoreResponsibility(title=str(item)[:30], description=str(item), domain="general"))
    elif "responsibilities" in decoded and isinstance(decoded["responsibilities"], (list, tuple)):
        for item in decoded["responsibilities"]:
            responsibilities.append(CoreResponsibility(title=str(item)[:30], description=str(item), domain="general"))
    else:
        layers = decoded.get("layers", {}) if isinstance(decoded.get("layers"), dict) else {}
        for layer_key in ("layer_1", "layer_3"):
            text = layers.get(layer_key, {}).get("jd_text_zh", "")
            if text:
                responsibilities.append(CoreResponsibility(title=text[:30], description=text, domain="general"))

    signals = [ImplicitSignal(**item) for item in decoded.get("detected_signals", []) if isinstance(item, dict) and "original_text" in item]
    return DecodedJD(
        raw_text=raw_text,
        job_title=job_title,
        company_or_dept=company_or_dept,
        hard_thresholds=hard_thresholds + nice_thresholds,
        core_responsibilities=responsibilities,
        core_skills=skills,
        implicit_signals=signals,
        business_pain_points=[],
        clean_text=str(decoded.get("clean_text", raw_text)),
    )


def to_canonical(decoded: Any) -> DecodedJD:
    """Universal ingress gateway returning the SSOT canonical DecodedJD.

    Accepts DecodedJD, DecodedJDCompat, legacy dictionary, Path, or raw JD text.
    """
    if isinstance(decoded, DecodedJDCompat):
        return decoded.canonical
    if isinstance(decoded, DecodedJD):
        return decoded
    if isinstance(decoded, str):
        if not decoded.strip():
            return DecodedJD(
                raw_text=decoded,
                job_title="未指定职位",
                company_or_dept="未指定公司",
                clean_text=decoded.strip(),
            )
        return JDDecoder().decode(decoded)
    if hasattr(decoded, "read_text"):  # pathlib.Path
        text = decoded.read_text(encoding="utf-8")
        if not text.strip():
            return DecodedJD(
                raw_text=text,
                job_title="未指定职位",
                company_or_dept="未指定公司",
                clean_text=text.strip(),
            )
        return JDDecoder().decode(text)
    if isinstance(decoded, dict):
        if not decoded:
            return DecodedJD(
                raw_text="",
                job_title="未指定职位",
                company_or_dept="未指定公司",
                clean_text="",
            )
        return _legacy_to_canonical(decoded)
    raise TypeError(f"Unsupported decoded JD type: {type(decoded).__name__}")


def _gap_to_dict(gap: Any) -> Dict[str, Any]:
    state = gap.state.value if hasattr(gap.state, "value") else str(gap.state)
    priority = "high" if state == "REAL_GAP" or str(gap.importance).lower() in {"mandatory", "must_have"} else "medium"
    return {
        "requirement_name": gap.requirement_name,
        "category": gap.category,
        "importance": gap.importance,
        "state": state,
        "score": round(gap.score * 100),
        "title_zh": gap.requirement_name,
        "title_en": gap.requirement_name,
        "priority": priority,
        "evidence_zh": gap.candidate_evidence,
        "probe_zh": gap.gap_explanation,
        "fix_zh": gap.actionable_advice,
        "evidence_en": gap.candidate_evidence,
        "probe_en": gap.gap_explanation,
        "fix_en": gap.actionable_advice,
    }


def _json_safe(value: Any) -> Any:
    """Convert canonical dataclasses/enums into JSON-safe compatibility data."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def matcher_to_legacy(result: MatcherResult, candidate: CandidateProfile, decoded: DecodedJD) -> Dict[str, Any]:
    """Expose the old dict contract while retaining all canonical gap data."""
    probability = InterviewProbabilityCalculator().calculate(result)
    all_gaps = [_gap_to_dict(item) for item in result.gap_matrix]
    must_items = [item for item in all_gaps if item["importance"] in {"must_have", "MUST_HAVE", "mandatory"}]
    gaps = [item for item in all_gaps if item["state"] != "MATCHED"]
    score = round(result.final_match_score * 100)
    if result.is_hard_vetoed:
        verdict_title = "硬门槛未通过，需人工复核"
        verdict_desc = "候选人存在岗位硬性条件未满足或未确认的情况，不能由其他优势自动抵消。"
    elif score >= 75:
        verdict_title = "建议在证据复核后投递"
        verdict_desc = "当前材料与岗位要求存在较多对应关系，但请先复核每项证据和岗位硬门槛。"
    elif score >= 50:
        verdict_title = "补充材料后投递"
        verdict_desc = "当前存在可解释的表达缺口或证据缺口，建议补充材料后再决定。"
    else:
        verdict_title = "谨慎投递"
        verdict_desc = "当前材料与岗位要求的直接对应关系较少，建议先确认真实缺口。"

    from core.jd_decision import DecodeBeforeMatchGate, ShouldIApplyEvaluator

    should_i_apply = ShouldIApplyEvaluator().evaluate(decoded, candidate, result)
    should_i_apply_dict = {
        "stars": should_i_apply.stars,
        "composite_score": should_i_apply.composite_score,
        "verdict": should_i_apply.verdict.value,
        "verdict_title": should_i_apply.verdict_title,
        "verdict_description": should_i_apply.verdict_description,
        "pros": should_i_apply.pros,
        "cons": should_i_apply.cons,
        "probability_range": list(should_i_apply.probability_range),
        "probability_breakdown": {k: list(v) for k, v in should_i_apply.probability_breakdown.items()},
        "next_action": should_i_apply.next_action.value,
        "action_advice": should_i_apply.action_advice,
        "dimension_scores": should_i_apply.dimension_scores,
        "six_week_plan": {
            "focus_summary": should_i_apply.six_week_plan.focus_summary,
            "weeks": [
                {
                    "week_range": w.week_range,
                    "phase_name": w.phase_name,
                    "tasks": list(w.tasks),
                    "deliverables": w.deliverables,
                }
                for w in should_i_apply.six_week_plan.weeks
            ]
        }
    }

    return {
        "candidate_name": candidate.name,
        "overall_match_score": score,
        # Keep the historical scalar field as the conservative interval upper
        # bound for callers that cannot consume the richer range field.
        "interview_prob": round(probability.base_max_prob),
        "interview_probability_range": [probability.base_min_prob, probability.base_max_prob],
        "breakdown": {
            "must_have": round(result.must_have_score * 100),
            "nice_have": round(result.nice_to_have_score * 100),
            "hidden_fit": round(result.hidden_signal_fit * 100),
        },
        "verdict": {
            "title_zh": verdict_title,
            "title_en": "Review Before Applying" if not result.is_hard_vetoed else "Hard Gate Needs Review",
            "desc_zh": verdict_desc,
            "desc_en": "Review the evidence and hard requirements before making an application decision.",
        },
        "must_have_matches": must_items[:5],
        "all_must_have_matches": must_items,
        "gaps": gaps[:3],
        "all_gaps": all_gaps,
        "canonical_match": _json_safe(asdict(result)),
        "hard_vetoed": result.is_hard_vetoed,
        "hard_veto_reasons": result.hard_veto_reasons,
        "should_i_apply": should_i_apply_dict,
    }


def match_legacy(
    decoded: Any,
    profile_data: Union[Dict[str, Any], ProfileContext],
    strict_gate: bool = False,
) -> Dict[str, Any]:
    from core.jd_decision import DecodeBeforeMatchGate
    canonical_jd = DecodeBeforeMatchGate.enforce(decoded, strict=strict_gate)
    candidate = profile_to_canonical(profile_data)
    result = JDMatcher().match(canonical_jd, candidate)
    return matcher_to_legacy(result, candidate, canonical_jd)
