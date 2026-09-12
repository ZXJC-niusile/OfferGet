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
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


ROLE_TAXONOMIES: Dict[str, Dict[str, Any]] = {
    "ai_algorithm": {
        "title": "AI / 大模型与算法架构",
        "keywords": ["Transformer", "MoE", "Megatron", "vLLM", "PyTorch", "CUDA", "Triton", "RAG", "Agent"],
        "dimensions": [("算法与模型", 0.25), ("工程与性能", 0.25), ("业务落地", 0.20), ("数据与评测", 0.15), ("研究与生态", 0.15)],
    },
    "backend_distributed": {
        "title": "后端与分布式高并发架构",
        "keywords": ["Java", "Go", "gRPC", "Kafka", "MySQL", "Redis", "微服务", "分布式事务", "DDD"],
        "dimensions": [("系统设计", 0.30), ("存储与一致性", 0.25), ("稳定性", 0.20), ("业务建模", 0.15), ("性能与工程", 0.10)],
    },
    "frontend_fullstack": {
        "title": "前端与 Web 全栈工程",
        "keywords": ["React", "Vue", "TypeScript", "Next.js", "Web Vitals", "SSR", "Vite", "BFF"],
        "dimensions": [("交互架构", 0.25), ("性能治理", 0.25), ("组件工程", 0.20), ("跨端协同", 0.15), ("体验指标", 0.15)],
    },
    "client_mobile": {
        "title": "客户端与移动端工程",
        "keywords": ["iOS", "Android", "Flutter", "Swift", "Kotlin", "ANR", "SQLite", "QUIC"],
        "dimensions": [("端侧架构", 0.25), ("稳定性", 0.25), ("跨端工程", 0.20), ("弱网与存储", 0.15), ("业务交互", 0.15)],
    },
    "bigdata_infra": {
        "title": "大数据开发与实时湖仓",
        "keywords": ["Flink", "Spark", "Iceberg", "Hudi", "ClickHouse", "StarRocks", "Doris", "数据血缘"],
        "dimensions": [("计算引擎", 0.30), ("湖仓建模", 0.25), ("查询与存储", 0.20), ("质量与成本", 0.15), ("业务决策", 0.10)],
    },
    "cloudnative_sre": {
        "title": "系统底层 / 云原生 / SRE",
        "keywords": ["Kubernetes", "K8s", "eBPF", "Prometheus", "Docker", "Slurm", "RDMA", "FinOps"],
        "dimensions": [("平台与调度", 0.25), ("网络与硬件", 0.25), ("稳定性", 0.20), ("系统性能", 0.15), ("成本治理", 0.15)],
    },
    "product": {
        "title": "产品管理与产品策略",
        "keywords": ["产品经理", "产品", "用户研究", "需求分析", "路线图", "PRD", "A/B测试", "用户增长", "留存", "转化"],
        "dimensions": [("问题定义", 0.25), ("用户与需求", 0.25), ("决策与交付", 0.20), ("数据与实验", 0.15), ("业务结果", 0.15)],
    },
    "operations": {
        "title": "运营与业务增长",
        "keywords": ["运营", "增长", "活动", "内容", "用户运营", "产品运营", "流程优化", "转化", "留存", "SLA"],
        "dimensions": [("运营策略", 0.25), ("流程执行", 0.25), ("用户与供给", 0.20), ("数据指标", 0.15), ("协同交付", 0.15)],
    },
    "marketing_sales": {
        "title": "市场、销售与商务拓展",
        "keywords": ["市场", "营销", "销售", "商务", "渠道", "获客", "线索", "客户", "ROI", "CAC", "pipeline"],
        "dimensions": [("市场洞察", 0.25), ("渠道与获客", 0.25), ("客户经营", 0.20), ("转化与收入", 0.20), ("复盘与协同", 0.10)],
    },
    "project_management": {
        "title": "项目管理与交付",
        "keywords": ["项目管理", "项目经理", "PMO", "敏捷", "Scrum", "里程碑", "风险管理", "交付", "干系人"],
        "dimensions": [("目标与范围", 0.25), ("计划与交付", 0.25), ("风险与质量", 0.20), ("干系人协同", 0.20), ("复盘改进", 0.10)],
    },
    "general": {
        "title": "通用岗位能力",
        "keywords": [],
        "dimensions": [("职责匹配", 0.30), ("能力证据", 0.30), ("结果表达", 0.20), ("岗位约束", 0.20)],
    },
}


class DecodedJDCompat(dict):
    """JSON-compatible legacy dict carrying the canonical typed object privately."""

    def __init__(self, payload: Dict[str, Any], canonical: DecodedJD):
        super().__init__(payload)
        self.canonical = canonical


def classify_role_taxonomy(jd_text: str) -> Dict[str, Any]:
    """Classify a JD for legacy metadata without changing canonical decoding."""
    text = jd_text or ""
    scores = {
        key: sum(1 for keyword in info["keywords"] if keyword.lower() in text.lower())
        for key, info in ROLE_TAXONOMIES.items()
    }
    best_key = max(scores, key=scores.get) if scores and max(scores.values()) else "general"
    info = ROLE_TAXONOMIES[best_key]
    return {"role_key": best_key, "taxonomy": info}


def _first_match(text: str, patterns: Iterable[str], default: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return default


def _extract_metadata(text: str) -> Dict[str, str]:
    return {
        "role": _first_match(text, [r"(?:【岗位名称】|岗位名称|职位名称|岗位|职位|Job\s*Title)[：:\s]+([^\n\r]+)"], "未指定职位"),
        "company": _first_match(text, [r"(?:【公司名称】|公司|雇主|Company)[：:\s]+([^\n\r]+)"], "未指定公司"),
        "department": _first_match(text, [r"(?:【所属部门】|部门|团队|Department|Team)[：:\s]+([^\n\r]+)"], "未指定部门"),
        "location": _first_match(text, [r"(?:【工作地点】|工作地点|地点|Location)[：:\s]+([^\n\r]+)"], "未提供"),
        "comp_band": _first_match(text, [r"(?:【薪资范围】|薪资范围|薪资|Salary|Compensation)[：:\s]+([^\n\r]+)"], "未提供"),
        "level": _first_match(text, [r"(?:【岗位级别】|岗位级别|职级|Level)[：:\s]+([^\n\r]+)"], "未提供"),
    }


def _layer(title: str, zh: str, en: str = "") -> Dict[str, str]:
    return {"title": title, "jd_text_zh": zh, "jd_text_en": en, "reality_zh": "仅基于当前 JD 原文，待候选人与招聘方进一步确认。", "reality_en": "Based on the supplied JD only; confirm with the hiring team."}


def canonical_to_legacy(canonical: DecodedJD) -> DecodedJDCompat:
    """Convert the canonical dataclass result to OfferGet's historical dict shape."""
    meta = _extract_metadata(canonical.raw_text)
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


def profile_to_canonical(profile_data: Dict[str, Any]) -> CandidateProfile:
    """Normalize the supported profile shapes without inventing defaults."""
    profile = profile_data or {}
    candidate = profile.get("candidate", {}) if isinstance(profile.get("candidate", {}), dict) else {}
    degree = str(candidate.get("degree") or candidate.get("education_level") or "高中及以下")
    if "博士" in degree or "Ph.D" in degree or "PhD" in degree:
        education_level = "博士"
    elif "硕士" in degree or "Master" in degree:
        education_level = "硕士"
    elif "本科" in degree or "Bachelor" in degree:
        education_level = "本科"
    elif "大专" in degree or "专科" in degree:
        education_level = "大专"
    else:
        education_level = "高中及以下"

    raw_years = candidate.get("years_of_experience", candidate.get("experience_years", 0))
    try:
        years = float(raw_years or 0)
    except (TypeError, ValueError):
        years = 0.0

    skills: List[str] = []
    skills.extend(_flatten_strings(profile.get("skills", [])))
    skills.extend(_flatten_strings(profile.get("competencies", {})))

    descriptions: List[str] = []
    for experience in profile.get("experience", []) if isinstance(profile.get("experience", []), list) else []:
        if not isinstance(experience, dict):
            continue
        for highlight in experience.get("highlights", []):
            if isinstance(highlight, dict):
                descriptions.extend(_flatten_strings(highlight.get("claim_zh", "")))
                descriptions.extend(_flatten_strings(highlight.get("claim_en", "")))
            else:
                descriptions.extend(_flatten_strings(highlight))

    for project in profile.get("projects", []) if isinstance(profile.get("projects", []), list) else []:
        if isinstance(project, dict):
            descriptions.extend(_flatten_strings(project.get("description_zh", project.get("description", ""))))
            descriptions.extend(_flatten_strings(project.get("description_en", "")))

    raw_text = json.dumps(profile, ensure_ascii=False)
    return CandidateProfile(
        name=str(candidate.get("name") or "候选人"),
        education_level=education_level,
        degree_school=str(candidate.get("institution") or candidate.get("school") or ""),
        major=str(candidate.get("major") or ""),
        years_of_experience=years,
        skills=list(dict.fromkeys(item for item in skills if item)),
        project_descriptions=[item for item in descriptions if item],
        raw_resume_text=raw_text,
    )


def _legacy_to_canonical(decoded: Dict[str, Any]) -> DecodedJD:
    """Rehydrate a plain JSON legacy result when it did not come from decode_legacy."""
    raw_text = str(decoded.get("raw_text") or decoded.get("clean_text") or "")
    if raw_text:
        return JDDecoder().decode(raw_text)

    metadata = decoded.get("metadata", {})
    requirements = decoded.get("requirements", {})
    hard_thresholds = [HardThreshold(category="other", requirement=str(item), is_mandatory=True) for item in requirements.get("must_haves", [])]
    nice_thresholds = [HardThreshold(category="other", requirement=str(item), is_mandatory=False) for item in requirements.get("nice_haves", [])]
    skills = [CoreSkill(name=str(item), category="other", importance=SkillImportance.MUST_HAVE.value, domain="general") for item in requirements.get("must_haves", [])]
    skills.extend(CoreSkill(name=str(item), category="other", importance=SkillImportance.NICE_TO_HAVE.value, domain="general") for item in requirements.get("nice_haves", []))
    layers = decoded.get("layers", {})
    responsibilities = []
    for layer_key in ("layer_1", "layer_3"):
        text = layers.get(layer_key, {}).get("jd_text_zh", "")
        if text:
            responsibilities.append(CoreResponsibility(title=text[:30], description=text, domain="general"))
    signals = [ImplicitSignal(**item) for item in decoded.get("detected_signals", []) if isinstance(item, dict) and "original_text" in item]
    return DecodedJD(
        raw_text=raw_text,
        job_title=str(metadata.get("role", "未指定职位")),
        company_or_dept=str(metadata.get("company", metadata.get("department", "未指定公司"))),
        hard_thresholds=hard_thresholds + nice_thresholds,
        core_responsibilities=responsibilities,
        core_skills=skills,
        implicit_signals=signals,
        business_pain_points=[],
        clean_text=str(decoded.get("clean_text", raw_text)),
    )


def to_canonical(decoded: Any) -> DecodedJD:
    if isinstance(decoded, DecodedJDCompat):
        return decoded.canonical
    if isinstance(decoded, DecodedJD):
        return decoded
    if isinstance(decoded, dict):
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
    }


def match_legacy(decoded: Any, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    canonical_jd = to_canonical(decoded)
    candidate = profile_to_canonical(profile_data)
    result = JDMatcher().match(canonical_jd, candidate)
    return matcher_to_legacy(result, candidate, canonical_jd)
