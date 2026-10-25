"""Goal-oriented JD matching, evidence-backed material drafts and interview practice.

Source facts remain unchanged until the user accepts a material proposal.
Interview snapshots keep stable IDs across answer and follow-up rounds.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.artifacts import write_json_atomic
from core.interview_debrief import InterviewDebriefEngine
from core.jd_compat import profile_to_canonical
from core.fact_guard import FactVerificationGuard
from core.asu_modeler import AsuModeler
from core.validator import validate_anti_ai_slop
from core.profile_adapter import (
    EvidenceClaim,
    ProfileContext,
    build_profile_context,
    claim_ref,
    claim_matches,
    find_evidence,
    require_public_profile,
)
from core.evidence.graph import EvidenceGraph, EvidenceNodeState
from core.application_tracker import create_evidence_snapshot
from core.material_proposal import create_material_proposal
from core.jd_analyst.decoder import JDDecoder
from core.jd_analyst.matcher import JDMatcher
from core.jd_analyst.models import (
    CandidateProfile,
    DecodedJD,
    GapState,
    MatcherResult,
    QuestionCategory,
)
from core.jd_analyst.predictor import JDPredictor


def build_candidate_profile(profile_dict: Union[Dict[str, Any], ProfileContext]) -> CandidateProfile:
    """Use the shared profile adapter so missing facts remain unknown."""
    if isinstance(profile_dict, ProfileContext):
        return profile_dict.get_canonical_profile()
    return profile_to_canonical(profile_dict if isinstance(profile_dict, dict) else {})


STRONG_ROLE_PATTERN = re.compile(r"主导|统筹|牵头|Owner|owner|Lead|lead|架构师|从\s*0\s*(?:到|→|->)\s*1")
METRIC_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:%|倍|x|X|ms|s|分钟|小时|天|周|万元|亿元|卡|GPU|QPS|TPS)")
ATTRIBUTION_PATTERN = re.compile(r"个人|本人|独立|我负责|我实现|团队|协同|共同|归因|贡献边界")


def _claim_risk_flags(claim: EvidenceClaim) -> List[Dict[str, str]]:
    """Audit role, scope, metrics and attribution without inventing facts."""
    flags: List[Dict[str, str]] = []
    text = claim.text

    declared_role = "contributor"
    if claim.role_scope:
        role_lower = claim.role_scope.lower()
        if any(k in role_lower for k in ("architect", "架构", "lead", "负责人")):
            declared_role = "tech_lead"
        else:
            declared_role = "module_owner"

    for issue in AsuModeler().audit_bullet_inflation(
        text,
        verification=claim.verification,
        user_declared_role=declared_role,
    ):
        risk = issue.get("risk", "")
        flags.append({
            "code": str(issue.get("pattern", "claim_inflation")),
            "severity": risk.value if hasattr(risk, "value") else str(risk),
            "message": str(issue.get("detail", "")),
        })

    if STRONG_ROLE_PATTERN.search(text) and not claim.role_scope:
        flags.append({
            "code": "role_scope_unverified",
            "severity": "high",
            "message": "强角色表述缺少明确的负责模块或决策边界。",
        })
    if METRIC_PATTERN.search(text) and not claim.metric_context:
        flags.append({
            "code": "metric_context_missing",
            "severity": "medium",
            "message": "量化结果缺少结构化口径或已核验指标来源。",
        })
    if (STRONG_ROLE_PATTERN.search(text) or METRIC_PATTERN.search(text)) and not (
        claim.attribution or ATTRIBUTION_PATTERN.search(text)
    ):
        flags.append({
            "code": "personal_attribution_missing",
            "severity": "medium",
            "message": "未明确个人动作、团队成果和因果归因边界。",
        })

    slop = validate_anti_ai_slop(text)
    for violation in slop.get("violations", []):
        flags.append({
            "code": "anti_ai_slop",
            "severity": "medium",
            "message": str(violation.get("reason", "命中空洞或模板化表达")),
        })
    return flags


def _next_evidence_question(requirement: str, flags: List[Dict[str, str]], has_claim: bool) -> str:
    codes = {flag["code"] for flag in flags}
    if not has_claim:
        return f"你是否有与“{requirement}”直接相关的真实项目？请说明个人动作、使用场景、结果和可核验来源。"
    if "role_scope_unverified" in codes or "P1_SCOPE_INFLATION" in codes:
        return f"针对“{requirement}”，你本人独立负责的最小模块是什么？哪些决策和产物可证明该边界？"
    if "metric_context_missing" in codes:
        return f"针对“{requirement}”的数字，请补充 baseline、结果、单位、统计周期和数据来源。"
    if "personal_attribution_missing" in codes:
        return f"针对“{requirement}”，团队整体结果中哪些是你的个人动作，哪些由其他成员或基础设施贡献？"
    return f"针对“{requirement}”，请确认该证据是否仍准确，并准备说明选型、个人贡献和失败复盘。"


def _polish_grounded_bullet(text: str) -> str:
    """Remove presentation framing only; retain actions, scope and qualifications.

    This deterministic edit never supplies technologies, ownership or outcomes.
    Sentence and clause order stays intact so causal and attribution boundaries survive.
    """
    return re.sub(r"^(?:在该项目中[，,]|在此项目中[，,]|主要工作包括[：:])\s*", "", text.strip(), count=1)


def generate_resume_advice(
    jd: DecodedJD,
    matcher_result: MatcherResult,
    claims: List[EvidenceClaim],
    fact_guard: Optional[FactVerificationGuard] = None,
) -> List[Dict[str, Any]]:
    advice_list: List[Dict[str, Any]] = []

    for gap in matcher_result.gap_matrix:
        req_name = gap.requirement_name.replace("技能-", "").replace("职责-", "").replace("硬门槛-", "").replace("门槛要求-", "").replace("隐性考核-", "")
        matching_claims = find_evidence(req_name, claims)

        evidence_type = "direct" if matching_claims else "none"
        # A threshold must be supported by its corresponding candidate field;
        # an unrelated claim is not proof of education, major, or experience.
        if not matching_claims:
            if gap.category == "threshold":
                path_keys = set()
                if any(marker in req_name for marker in ("学历", "学位")):
                    path_keys.add("degree")
                if "专业" in req_name:
                    path_keys.add("major")
                if any(marker in req_name for marker in ("经验", "年")):
                    path_keys.add("years_of_experience")
                matching_claims.extend(
                    c for c in claims
                    if c.kind == "candidate" and any(key in c.source_path for key in path_keys)
                )
            else:
                # Try canonical-sized tokens, but mark the result as adjacent.
                tokens = [t for t in re.split(r"[/,、\s]+", req_name) if len(t) >= 2]
                for tok in tokens:
                    sub_match = find_evidence(tok, claims)
                    if sub_match:
                        matching_claims.extend(sub_match)
                if matching_claims:
                    evidence_type = "adjacent"

        # Deduplicate while preserving order
        seen_paths = set()
        unique_claims = []
        for c in matching_claims:
            if c.source_path not in seen_paths:
                seen_paths.add(c.source_path)
                unique_claims.append(c)
        matching_claims = unique_claims
        # Prefer actual practice over a keyword declaration or the first path.
        matching_claims.sort(key=lambda c: (
            claim_matches(req_name, c.text),
            c.kind in {"experience", "project", "bullet", "highlight"} or bool(re.search(r"experience\[|projects\[", c.source_path)),
            bool(c.role_scope or c.attribution),
            bool(re.search(r"开发|实现|交付|上线|负责|完成|采用|develop|deliver|implement", c.text)),
            c.direct,
        ), reverse=True)

        evidence_refs = [claim_ref(c) for c in matching_claims]
        risk_flags: List[Dict[str, str]] = []
        for claim in matching_claims:
            risk_flags.extend(_claim_risk_flags(claim))
        guard_report = {"passed": True, "verdict": "NOT_RUN"}

        if gap.state == GapState.MATCHED:
            state = "verified"
            action = "keep"
            safe_bullet = matching_claims[0].text if matching_claims else (gap.candidate_evidence if gap.candidate_evidence else "")
            grounding_note = f"在过往履历中已具备充分佐证 ({len(matching_claims)} 条依据)，保持并高亮。"
        elif gap.state == GapState.EXPRESSION_GAP:
            state = "claimed"
            action = "keep"
            safe_bullet = matching_claims[0].text if matching_claims else ""
            grounding_note = "保留相邻经验的真实技术名称，优先展示相关实践；不会将相邻技能改写成未使用过的目标技能。"
        elif gap.state == GapState.INSUFFICIENT_EVIDENCE:
            state = "needs_confirmation"
            action = "add_evidence"
            safe_bullet = matching_claims[0].text if matching_claims else ""
            grounding_note = f"请确认实际场景、个人贡献与交付物：{gap.actionable_advice}"
        elif gap.state == GapState.REAL_GAP:
            state = "unsupported"
            action = "ask_user"
            safe_bullet = ""
            grounding_note = "履历无此项事实支撑。严禁在简历中伪造经历；建议在面试中坦白并在开源破局中展示学习迁移能力。"
        else:
            state = "needs_confirmation"
            action = "ask_user"
            safe_bullet = matching_claims[0].text if matching_claims else ""
            grounding_note = gap.actionable_advice

        if safe_bullet and fact_guard is not None:
            guard_report = fact_guard.verify_facts(safe_bullet)
            if not guard_report.get("passed", False):
                risk_flags.append({
                    "code": "fact_guard_failed",
                    "severity": "high",
                    "message": "候选人原文中的数字或指标未通过事实底稿核验。",
                })
                state = "needs_confirmation"
                action = "ask_user"
                safe_bullet = ""
                grounding_note = "候选人原文包含未通过事实核验的数字或指标，补充来源后再改写。"

        blocking_codes = {
            "P1_SCOPE_INFLATION",
            "P2_UNBOUNDED_SUPERLATIVE",
            "P3_TEMPORAL_CONFUSION",
            "role_scope_unverified",
            "fact_guard_failed",
        }
        if safe_bullet and any(flag["code"] in blocking_codes for flag in risk_flags):
            state = "needs_confirmation"
            action = "ask_user"
            safe_bullet = ""
            grounding_note = "已有相关经历，但角色、范围、指标或个人归因尚未闭合；确认事实后再生成强表达。"

        coverage = {
            "direct": "direct",
            "adjacent": "adjacent",
            "none": "missing",
        }.get(evidence_type, "unknown")
        if coverage == "direct" and state == "needs_confirmation":
            coverage = "weak"

        original_bullet = safe_bullet
        if safe_bullet and action == "keep" and matching_claims:
            source = matching_claims[0]
            if re.search(r"(?:bullets|highlights)\[\d+\]", source.source_path):
                polished = _polish_grounded_bullet(safe_bullet)
                if polished and polished != safe_bullet:
                    safe_bullet = polished
                    action = "rewrite"
                    # A rewrite has one exact source; other supporting claims remain context.
                    evidence_refs = [claim_ref(source)]
                    grounding_note = "去除句首介绍性套语；保留原文动作、技术、结果和个人贡献边界，确认后应用。"
        next_question = _next_evidence_question(req_name, risk_flags, bool(matching_claims))
        advice_list.append({
            "requirement": req_name,
            "jd_requirement": {
                "text": req_name,
                "category": gap.category,
                "importance": gap.importance,
            },
            "category": gap.category,
            "state": state,
            "action": action,
            "coverage": coverage,
            "evidence_type": evidence_type,
            "evidence_refs": evidence_refs,
            "safe_bullet": safe_bullet,
            "original_bullet": original_bullet,
            "gap_explanation": gap.gap_explanation,
            "grounding_note": grounding_note,
            "guard_report": guard_report,
            "risk_flags": risk_flags,
            "next_question": next_question,
            "uncertainty": "needs_confirmation" if state == "needs_confirmation" else "none",
        })

    return advice_list


@dataclass
class ResumePatch:
    source_claim_id: str
    target_path: str
    before: str
    after: str
    approval_group: str = ""
    evidence_refs: List[Dict[str, Any]] = field(default_factory=list)
    validation_status: str = "applied"  # "applied", "rejected", "already_applied", "pending_user_confirmation"
    reason: str = ""
    unresolved_risks: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _rewrite_bullet_index(
    section: str, entry_index: int, bullets: list[str], evidence_refs: list[dict[str, Any]],
) -> int | None:
    """Resolve one evidenced source bullet without incidental substring matches."""
    prefix = f"{section}[{entry_index}]"
    refs = [ref for ref in evidence_refs
            if not ref.get("source_path") or str(ref["source_path"]).startswith(prefix + ".")]
    anchors = []
    for ref in refs:
        match = re.fullmatch(re.escape(prefix) + r"\.bullets\[(\d+)\]", str(ref.get("source_path", "")))
        if match:
            anchors.append((int(match.group(1)), ref.get("excerpt", "")))
    if anchors:
        indexes = {index for index, _ in anchors}
        if len(indexes) != 1:
            return None
        index = anchors[0][0]
        if index < len(bullets) and all(excerpt and excerpt in bullets[index] for _, excerpt in anchors):
            return index
        return None  # A stale explicit anchor must not redirect to another bullet.
    excerpts = {ref.get("excerpt") for ref in refs if ref.get("excerpt")}
    matches = [index for index, bullet in enumerate(bullets) if bullet in excerpts]
    return matches[0] if len(matches) == 1 else None


def generate_tailored_profile_from_review(
    review_result: Dict[str, Any],
    base_profile: Union[Dict[str, Any], ProfileContext],
    fact_guard: Optional[FactVerificationGuard] = None,
    evidence_graph: Optional[EvidenceGraph] = None,
) -> Dict[str, Any]:
    """Derive targeted tailored candidate profile from career review advice.

    Applies verified, un-inflated, fact-grounded recommendations to the candidate profile
    via structured ResumePatch audits. Preserves base_profile immutability and enforces:
    1. Idempotency (does not duplicate bullets on repeated execution)
    2. Zero unanchored fallback (never blindly injects into experience[0])
    3. Fact Guard verification on all incoming recommendations
    4. Unresolved risks and patch audit tracking
    """
    if isinstance(base_profile, ProfileContext):
        tailored = copy.deepcopy(base_profile.normalized_profile)
    else:
        tailored = copy.deepcopy(base_profile if isinstance(base_profile, dict) else {})

    # 1. Candidate metadata & photo slot
    if "candidate" in tailored and isinstance(tailored["candidate"], dict):
        cand = tailored["candidate"]
        if "school" not in cand and "institution" in cand:
            cand["school"] = cand["institution"]
        if "title" not in cand and "title_zh" in cand:
            cand["title"] = cand["title_zh"]
        cand["reserve_photo"] = True
    else:
        tailored["reserve_photo"] = True

    # 2. Normalize experiences
    experiences = tailored.get("experience")
    if experiences is None and "internships" in tailored:
        experiences = tailored["internships"]
        tailored["experience"] = experiences
    if not isinstance(experiences, list):
        experiences = []
        tailored["experience"] = experiences

    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        if "org" not in exp and "company" in exp:
            exp["org"] = exp["company"]
        if "company" not in exp and "org" in exp:
            exp["company"] = exp["org"]
        if "time" not in exp and "period" in exp:
            exp["time"] = exp["period"]
        if "period" not in exp and "time" in exp:
            exp["period"] = exp["time"]

        bullets = exp.get("bullets")
        if bullets is None:
            extracted = []
            for h in exp.get("highlights", []):
                if isinstance(h, dict):
                    txt = h.get("claim_zh") or h.get("claim_en") or h.get("text") or ""
                else:
                    txt = str(h)
                if txt and txt not in extracted:
                    extracted.append(txt)
            exp["bullets"] = extracted
        else:
            exp["bullets"] = list(bullets)

    # 3. Normalize projects
    projects = tailored.get("projects")
    if projects is None and "campus_experience" in tailored:
        projects = tailored["campus_experience"]
        tailored["projects"] = projects
    if isinstance(projects, list):
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            if "time" not in proj and "period" in proj:
                proj["time"] = proj["period"]
            p_bullets = proj.get("bullets")
            if p_bullets is None:
                extracted = []
                desc = proj.get("description_zh") or proj.get("description", "")
                if desc:
                    extracted.append(desc)
                proj["bullets"] = extracted
            else:
                proj["bullets"] = list(p_bullets)

    # 4. Extract and inject verified safe_bullet evidence via ResumePatch
    if isinstance(review_result, list):
        advice_list = review_result
    elif isinstance(review_result, dict):
        advice_list = review_result.get("resume_advice", [])
    else:
        advice_list = []

    guard = fact_guard
    if guard is None and base_profile:
        guard = FactVerificationGuard(base_profile)

    applied_patches: List[Dict[str, Any]] = []
    unresolved_risks: List[Dict[str, Any]] = []

    rewritten_sources = set()
    for advice in advice_list:
        if not isinstance(advice, dict):
            continue
        safe_bullet = advice.get("safe_bullet", "")
        if not isinstance(safe_bullet, str):
            continue
        safe_bullet = safe_bullet.strip()
        if not safe_bullet:
            if advice.get("risk_flags"):
                unresolved_risks.extend(advice["risk_flags"])
            continue

        # Clean diagnostic prefixes
        if safe_bullet.startswith("简历中明确提及") or safe_bullet.startswith("未直接提及") or safe_bullet.startswith("候选人专业"):
            m_quote = re.search(r"['‘\"](.+?)['’\"]", safe_bullet)
            if m_quote and len(m_quote.group(1).strip()) >= 5:
                safe_bullet = m_quote.group(1).strip()
            else:
                continue

        category = advice.get("category", "")
        action = advice.get("action", "")
        requirement = advice.get("requirement", "")
        evidence_refs = advice.get("evidence_refs", [])
        risk_flags = advice.get("risk_flags", [])
        source_paths = tuple(ref.get("source_path", "") for ref in evidence_refs)
        if any(path in rewritten_sources for path in source_paths):
            continue
        if action == "rewrite":
            rewritten_sources.update(source_paths)
        matched_claim_id = next(
            (
                str(ref.get("claim_id"))
                for ref in evidence_refs
                if isinstance(ref, dict) and ref.get("claim_id")
            ),
            "",
        )

        # Fact Guard Verification on safe_bullet
        if guard is not None and safe_bullet:
            guard_res = guard.verify_facts(safe_bullet)
            if not guard_res.get("passed", False):
                drift_items = guard_res.get("drifts", [])
                unv_items = guard_res.get("unverified_claims", [])
                reason_detail = []
                for d in drift_items:
                    reason_detail.append(f"指标虚标: {d.get('claimed_metric')} (底稿基线: {d.get('verified_baseline')})")
                for u in unv_items:
                    reason_detail.append(f"未核验指标: {u.get('claimed_metric')}")
                patch = ResumePatch(
                    source_claim_id=requirement,
                    target_path="unapplied",
                    before="",
                    after=safe_bullet,
                    evidence_refs=evidence_refs,
                    validation_status="rejected",
                    reason=f"fact_guard_rejected: {'; '.join(reason_detail)}",
                    unresolved_risks=risk_flags,
                )
                applied_patches.append(patch.to_dict())
                unresolved_risks.extend(risk_flags)
                continue

        # Filter candidate metadata
        is_candidate_meta = False
        for ref in evidence_refs:
            sp = ref.get("source_path", "")
            if any(marker in sp for marker in ("candidate.degree", "candidate.years_of_experience", "candidate.major", "candidate.school", "candidate.institution")):
                is_candidate_meta = True
                cand = tailored.get("candidate", {})
                if "degree" in sp and isinstance(cand, dict):
                    cand["degree"] = safe_bullet
                elif "years_of_experience" in sp and isinstance(cand, dict):
                    cand["years_of_experience"] = safe_bullet
                break
        if is_candidate_meta:
            continue
        if category == "threshold" and any(k in requirement for k in ("学历", "学位", "年限", "工作经验", "专业")):
            continue

        presentation_edit = (
            action == "rewrite" and len(evidence_refs) == 1
            and bool(evidence_refs[0].get("excerpt"))
            and safe_bullet != evidence_refs[0]["excerpt"]
            and safe_bullet == _polish_grounded_bullet(evidence_refs[0]["excerpt"])
        )
        if presentation_edit:
            source_match = re.match(r"(experience|projects)\[(\d+)\]", evidence_refs[0].get("source_path", ""))
            entries = tailored.get(source_match.group(1), []) if source_match else []
            index = int(source_match.group(2)) if source_match else -1
            presentation_edit = (
                0 <= index < len(entries) and isinstance(entries[index], dict)
                and _rewrite_bullet_index(source_match.group(1), index,
                    entries[index].get("bullets", []), evidence_refs) is not None
            )
        # Removing introductory framing changes no factual claim. Keep it as an
        # explicit approval draft even when the source itself is user-declared.
        if evidence_graph is not None and not presentation_edit:
                graph_claim_ids = [
                    str(ref.get("claim_id")) for ref in evidence_refs
                    if isinstance(ref, dict) and ref.get("claim_id")
                ]
                eligible_claim_id = next(
                    (
                        claim_id for claim_id in graph_claim_ids
                        if (node := evidence_graph.get_node(claim_id)) is not None
                        and node.state in {EvidenceNodeState.USED_IN_RESUME, EvidenceNodeState.INTERVIEW_DEFENDED}
                    ),
                    "",
                )
                if not eligible_claim_id:
                    patch = ResumePatch(
                        source_claim_id=matched_claim_id or requirement,
                    target_path="evidence_graph_blocked",
                    before="",
                    after=safe_bullet,
                    evidence_refs=evidence_refs,
                    validation_status="rejected",
                    reason="evidence_graph_blocked: claim is not verified, grounded, and selected for resume",
                    unresolved_risks=risk_flags,
                )
                    applied_patches.append(patch.to_dict())
                    unresolved_risks.extend(risk_flags)
                    continue
                matched_claim_id = eligible_claim_id

        target_exp_indices: List[int] = []
        target_proj_indices: List[int] = []
        excerpts: List[str] = []

        for ref in evidence_refs:
            sp = ref.get("source_path", "")
            cid = ref.get("claim_id", "")
            if cid and not matched_claim_id:
                matched_claim_id = cid
            if ref.get("excerpt"):
                excerpts.append(ref["excerpt"])

            m_exp = re.search(r"experience\[(\d+)\]", sp)
            if m_exp:
                idx = int(m_exp.group(1))
                if 0 <= idx < len(experiences):
                    target_exp_indices.append(idx)
            m_proj = re.search(r"projects\[(\d+)\]", sp)
            if m_proj:
                idx = int(m_proj.group(1))
                if projects and 0 <= idx < len(projects):
                    target_proj_indices.append(idx)

            if cid and experiences:
                for e_idx, exp in enumerate(experiences):
                    if not isinstance(exp, dict):
                        continue
                    for h in exp.get("highlights", []):
                        if isinstance(h, dict) and h.get("claim_id") == cid:
                            target_exp_indices.append(e_idx)

        # Content/excerpt matching fallback (strictly scoped, no blind index 0)
        if not target_exp_indices and not target_proj_indices:
            if excerpts and experiences:
                for e_idx, exp in enumerate(experiences):
                    if not isinstance(exp, dict):
                        continue
                    exp_text = " ".join(exp.get("bullets", [])).lower()
                    if any(ex.lower() in exp_text for ex in excerpts if len(ex) >= 4):
                        target_exp_indices.append(e_idx)
                        break

            if not target_exp_indices and excerpts and projects:
                for p_idx, proj in enumerate(projects):
                    if not isinstance(proj, dict):
                        continue
                    proj_text = f"{proj.get('name', '')} {' '.join(proj.get('bullets', []))}".lower()
                    if any(ex.lower() in proj_text for ex in excerpts if len(ex) >= 4):
                        target_proj_indices.append(p_idx)
                        break

        # Strictly reject if target location is unresolved (DO NOT fall back to experience[0])
        if not target_exp_indices and not target_proj_indices:
            patch = ResumePatch(
                source_claim_id=matched_claim_id or requirement,
                target_path="unresolved",
                before="",
                after=safe_bullet,
                evidence_refs=evidence_refs,
                validation_status="rejected",
                reason="target_location_unresolved: evidence cannot be anchored to a specific experience or project",
                unresolved_risks=risk_flags,
            )
            applied_patches.append(patch.to_dict())
            unresolved_risks.extend(risk_flags)
            continue

        # Inject / rewrite into matched experiences
        for e_idx in dict.fromkeys(target_exp_indices):
            if 0 <= e_idx < len(experiences):
                exp = experiences[e_idx]
                bullets = exp.setdefault("bullets", [])

                if safe_bullet in bullets:
                    patch = ResumePatch(
                        source_claim_id=matched_claim_id or requirement,
                        target_path=f"experience[{e_idx}].bullets[{bullets.index(safe_bullet)}]",
                        before=safe_bullet,
                        after=safe_bullet,
                        evidence_refs=evidence_refs,
                        validation_status="already_applied",
                        reason="idempotent: bullet already present in target",
                        unresolved_risks=risk_flags,
                    )
                    applied_patches.append(patch.to_dict())
                    continue

                replaced = False
                before_str = ""
                b_target_idx = -1
                if action == "rewrite":
                    b_idx = _rewrite_bullet_index("experience", e_idx, bullets, evidence_refs)
                    if b_idx is not None:
                        before_str = bullets[b_idx]
                        bullets[b_idx] = safe_bullet
                        replaced = True
                        b_target_idx = b_idx

                if not replaced:
                    bullets.append(safe_bullet)
                    b_target_idx = len(bullets) - 1

                # Check whether original had verified metrics (do not invent verified_metrics=True)
                has_orig_verified = False
                if "highlights" in exp and isinstance(exp["highlights"], list):
                    for h in exp["highlights"]:
                        if isinstance(h, dict) and (h.get("claim_id") == matched_claim_id or (before_str and before_str in (h.get("claim_zh") or ""))):
                            if h.get("verified_metrics"):
                                has_orig_verified = True
                                break

                    has_h = any(
                        (isinstance(h, dict) and (h.get("claim_zh") == safe_bullet or h.get("safe_bullet") == safe_bullet))
                        or h == safe_bullet
                        for h in exp["highlights"]
                    )
                    if not has_h:
                        exp["highlights"].append({
                            "claim_id": f"TAILORED-{len(exp['highlights'])+1}",
                            "claim_zh": safe_bullet,
                            "safe_bullet": safe_bullet,
                            "verified_metrics": has_orig_verified,
                            "tailored": True,
                        })

                patch = ResumePatch(
                    source_claim_id=matched_claim_id or requirement,
                    target_path=f"experience[{e_idx}].bullets[{b_target_idx}]",
                    before=before_str,
                    after=safe_bullet,
                    evidence_refs=evidence_refs,
                    validation_status="pending_user_confirmation" if presentation_edit else "applied",
                    reason="去除介绍性套语，保留原文事实与边界" if presentation_edit else "grounded rewrite" if replaced else "grounded supplement",
                    unresolved_risks=risk_flags,
                )
                applied_patches.append(patch.to_dict())

        # Inject into matched projects
        for p_idx in dict.fromkeys(target_proj_indices):
            if projects and 0 <= p_idx < len(projects):
                proj = projects[p_idx]
                p_bullets = proj.setdefault("bullets", [])
                if safe_bullet in p_bullets:
                    patch = ResumePatch(
                        source_claim_id=matched_claim_id or requirement,
                        target_path=f"projects[{p_idx}].bullets[{p_bullets.index(safe_bullet)}]",
                        before=safe_bullet,
                        after=safe_bullet,
                        evidence_refs=evidence_refs,
                        validation_status="already_applied",
                        reason="idempotent: bullet already present in project",
                        unresolved_risks=risk_flags,
                    )
                    applied_patches.append(patch.to_dict())
                    continue
                b_idx = (_rewrite_bullet_index("projects", p_idx, p_bullets, evidence_refs)
                         if action == "rewrite" else None)
                before_str = ""
                if b_idx is not None:
                    before_str = p_bullets[b_idx]
                    p_bullets[b_idx] = safe_bullet
                else:
                    b_idx = len(p_bullets)
                    p_bullets.append(safe_bullet)
                patch = ResumePatch(
                    source_claim_id=matched_claim_id or requirement,
                    target_path=f"projects[{p_idx}].bullets[{b_idx}]",
                    before=before_str,
                    after=safe_bullet,
                    evidence_refs=evidence_refs,
                    validation_status="pending_user_confirmation" if presentation_edit else "applied",
                    reason="去除介绍性套语，保留原文事实与边界" if presentation_edit else "grounded project rewrite" if before_str else "grounded project supplement",
                    unresolved_risks=risk_flags,
                )
                applied_patches.append(patch.to_dict())

    # Prioritize existing facts within each entry, preserving chronology, wording
    # and every bullet. The resulting permutation is an explicit approval diff.
    def relevance(text: str) -> int:
        score = 0
        for advice in advice_list:
            requirement = str(advice.get("requirement", ""))
            terms = [t for t in re.split(r"[/、,\s]+", requirement) if len(t) >= 2]
            if any(claim_matches(t, text) for t in terms):
                importance = advice.get("jd_requirement", {}).get("importance", "")
                score += 3 if importance == "must_have" else 1
        return score

    for section in ("experience", "projects"):
        for index, entry in enumerate(tailored.get(section, []) or []):
            if not isinstance(entry, dict):
                continue
            original = entry.get("bullets", [])
            if not isinstance(original, list) or not all(isinstance(b, str) for b in original):
                continue
            ordered = sorted(original, key=relevance, reverse=True)
            if ordered != original:
                # Reordering depends on earlier edits in this entry; approve the whole plan.
                for patch in applied_patches:
                    if str(patch.get("target_path", "")).startswith(f"{section}[{index}].bullets["):
                        patch["approval_group"] = f"reorder:{section}[{index}]"
            for slot, (before, after) in enumerate(zip(original, ordered)):
                if before == after:
                    continue
                applied_patches.append(ResumePatch(
                    source_claim_id="jd_relevance_order",
                    target_path=f"{section}[{index}].bullets[{slot}]",
                    before=before, after=after,
                    approval_group=f"reorder:{section}[{index}]",
                    validation_status="pending_user_confirmation",
                    evidence_refs=[{"source_path": f"{section}[{index}].bullets[{original.index(after)}]", "excerpt": after}],
                    reason="优先展示岗位相关原文；保留全部事实与措辞",
                ).to_dict())
            entry["bullets"] = ordered

    tailored["applied_patches"] = applied_patches
    tailored["unresolved_risks"] = unresolved_risks
    tailored["_audit"] = {
        "applied_patches": applied_patches,
        "unresolved_risks": unresolved_risks,
    }

    return tailored


def _interview_role_evidence(decoded_jd, claims):
    core_resp_text = ""
    req_id_q1 = "core_responsibility"
    if hasattr(decoded_jd, "core_responsibilities") and decoded_jd.core_responsibilities:
        responsibility = max(decoded_jd.core_responsibilities, key=lambda r: (
            getattr(r, "weight", 1.0),
            not bool(find_evidence(r.description, claims)),
        ))
        core_resp_text = responsibility.description
        req_id_q1 = getattr(responsibility, "responsibility_id", "core_resp_" + hashlib.sha256(core_resp_text.encode()).hexdigest()[:8])
    elif hasattr(decoded_jd, "core_skills") and decoded_jd.core_skills:
        skill = max(decoded_jd.core_skills, key=lambda sk: (
            sk.importance == "must_have", not bool(find_evidence(sk.name, claims)),
        ))
        core_resp_text = skill.name
        req_id_q1 = f"skill_{core_resp_text}"
    else:
        core_resp_text = "核心技术架构与系统设计"

    q1_claims = find_evidence(core_resp_text, claims) if core_resp_text else []
    # When full-text matching yields nothing, try keyword-split and tech_domains
    if not q1_claims and core_resp_text:
        _seen_q1: Set[str] = set()
        for kw in re.split(r"[/,、\s()（）]+", core_resp_text):
            if len(kw) >= 2:
                for c in find_evidence(kw, claims):
                    if c.claim_id not in _seen_q1:
                        q1_claims.append(c)
                        _seen_q1.add(c.claim_id)
    if not q1_claims and hasattr(decoded_jd, "tech_domains") and decoded_jd.tech_domains:
        _seen_q1 = {c.claim_id for c in q1_claims}
        for domain in decoded_jd.tech_domains[:5]:
            for c in find_evidence(domain, claims):
                if c.claim_id not in _seen_q1:
                    q1_claims.append(c)
                    _seen_q1.add(c.claim_id)
    q1_evidence_refs = [claim_ref(c) for c in q1_claims[:3]]
    q1_evidence_ids = [ref.get("claim_id") for ref in q1_evidence_refs if ref.get("claim_id")]

    return core_resp_text, req_id_q1, q1_evidence_refs, q1_evidence_ids


def _rank_interview_projects(decoded_jd, claims, q1_evidence_refs, q1_evidence_ids):
    substantive_claims = [
        c for c in claims
        if c.kind in ("experience", "project", "highlight", "bullet")
        and len(c.text.strip()) >= 10
        and not any(meta in c.source_path.lower() for meta in ("candidate.", "years_of_experience", "institution", "degree", "name", "phone", "email", "gender"))
        and not any(meta in c.claim_id.lower() for meta in ("candidate.", "degree", "institution", "name"))
    ]
    distinct_claims: List[EvidenceClaim] = []
    seen_claim_ids: Set[str] = set()
    for c in substantive_claims:
        if c.claim_id not in seen_claim_ids and re.search(r"[\u4e00-\u9fa5a-zA-Z]", c.text):
            distinct_claims.append(c)
            seen_claim_ids.add(c.claim_id)
    q1_used_texts = {ref.get("excerpt", "") for ref in q1_evidence_refs}
    q1_used_ids = set(q1_evidence_ids)

    def project_priority(claim):
        relevant = sum(3 if sk.importance == "must_have" else 1
                       for sk in getattr(decoded_jd, "core_skills", [])
                       if claim_matches(sk.name, claim.text))
        return (relevant, bool(claim.role_scope or claim.attribution), bool(claim.metric_context))

    anchor_claim = max(distinct_claims, key=lambda c: (
        project_priority(c), c.claim_id not in q1_used_ids and c.text not in q1_used_texts,
    )) if distinct_claims else None

    return sorted(distinct_claims, key=project_priority, reverse=True), anchor_claim


def _resume_interview_questions(ranked):
    if not ranked:
        return []
    unique = []
    seen_texts = set()
    for claim in ranked:
        text_key = re.sub(r"\s+", "", claim.text).casefold()
        if text_key not in seen_texts:
            unique.append(claim)
            seen_texts.add(text_key)

    def entry(claim):
        match = re.search(r"(?:experience|projects)\[\d+\]", claim.source_path)
        return match.group() if match else claim.source_path

    selected = [unique[0]]
    for _ in range(2):
        remaining = [claim for claim in unique if claim not in selected]
        used_entries = {entry(claim) for claim in selected}
        # Prefer another experience, then another statement in the same entry.
        selected.append(next((c for c in remaining if entry(c) not in used_entries),
                             remaining[0] if remaining else selected[0]))

    formatted_questions = []
    for slot, claim in enumerate(selected):
        excerpt = claim.text.strip()
        quoted = excerpt[:160] + ("…" if len(excerpt) > 160 else "")
        decision = "你为什么选择这种做法？遇到的最难问题是什么？比较过哪些替代方案，最后如何解决？"
        verification = "你如何验证交付结果？哪些结果来自团队，哪些是你的贡献？这项工作有哪些局限？"
        if re.search(r"实验|论文|训练|评测|\b(?:training|experiment|benchmark)\b", excerpt, re.I):
            decision = "你如何确定实验或评测方案？比较过哪些方法，如何控制影响结果的其他因素？"
            verification = "你如何检查结果能否复现？评测样本有哪些限制，哪些结论尚不能确定？"
        elif re.search(r"运营|活动|内容增长|用户增长|转化|拉新|留存|\b(?:campaign|conversion|retention)\b", excerpt, re.I):
            decision = "你如何选择目标用户和执行方案？根据什么反馈调整，哪些动作由你负责？"
            verification = "你如何判断效果来自这次行动，而非同期其他变化？统计范围和观察周期是什么？"
        elif re.search(r"接口|数据库|索引|服务|系统|部署|缓存|\b(?:api|sql|sqlite|backend|deployment)\b", excerpt, re.I):
            decision = "你如何拆分实现步骤并选择方案？遇到哪些故障或边界情况，如何定位和处理？"
            verification = "你用哪些测试或运行记录验证结果？哪些场景没有覆盖，发生异常时如何处理？"
        if slot == 0:
            question = f"简历中写到【{quoted}】。请说明这项工作的背景、你具体负责的部分、做法以及交付结果。"
            expected = ["工作背景", "个人动作", "交付结果及来源", "贡献边界与局限"]
        elif slot == 1:
            question = f"针对简历中的【{quoted}】，{decision}"
            expected = ["方案选择依据", "替代方案或约束", "个人处理过程", "结果与局限"]
        else:
            question = f"针对简历中的【{quoted}】，{verification}"
            if METRIC_PATTERN.search(excerpt):
                question += "请说明数字的基线、统计口径和数据来源。"
            expected = ["验证方法", "结果依据", "个人贡献边界", "未覆盖的情况"]
        formatted_questions.append({
            "question_id": slot + 1,
            "target_dimension": ("core_responsibility", "project_deep_dive", "gap_boundary")[slot],
            "dimension_name_cn": ("简历经历与个人贡献", "方案选择与问题解决", "结果依据与贡献边界")[slot],
            "requirement_id": f"resume_{claim.claim_id}", "requirement_name": excerpt,
            "question_zh": question,
            "question_en": f"Explain your work, evidence and contribution boundary for this resume statement: {quoted}",
            "jd_signal": excerpt, "category": "简历经历追问", "category_type": "DEEP_DIVE",
            "interviewer_intent": "根据简历中的真实经历核实个人动作、结果与贡献边界。",
            "expected_elements": expected,
            "prep_keypoints": "结合原文说明" + "、".join(expected) + "；没有测量数据时如实说明。",
            "evidence_refs": [claim_ref(claim)], "evidence_claim_ids": [claim.claim_id], "gap_refs": [],
        })
    return formatted_questions


def select_targeted_interview_questions(
    decoded_jd: Any,
    cand_profile: Dict[str, Any],
    claims: List[EvidenceClaim],
    matcher_result: Any,
    predictor: Any,
    resume_first: bool = False,
) -> List[Dict[str, Any]]:
    """Select resume-grounded questions, or the legacy JD-focused questions.

    Resume mode returns early without generating the legacy JD question set.

    Mainline 3 dimensions:
    Q1 (`core_responsibility`): 核心岗位能力与技术架构深度考查 - derived from JD core_responsibilities or must_have core skills.
    Q2 (`project_deep_dive`): 候选人真实项目经历与关键成果深入追问 - follows up on candidate's actual provided experience/project claims.
    Q3 (`gap_boundary`): 技术缺口/证据不足边界与真实性防守考查 - directly examines gaps in matcher_result.gap_matrix.
    """
    formatted_questions: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Q1: core_responsibility (核心岗位能力与技术架构深度考查)
    # -------------------------------------------------------------------------
    core_resp_text, req_id_q1, q1_evidence_refs, q1_evidence_ids = _interview_role_evidence(decoded_jd, claims)
    ranked, anchor_claim = _rank_interview_projects(decoded_jd, claims, q1_evidence_refs, q1_evidence_ids)
    if resume_first:
        return _resume_interview_questions(ranked)

    top20_qs = predictor.top20_pred.predict(decoded_jd, matcher_result) if hasattr(predictor, "top20_pred") else []
    arch_qs = [q for q in top20_qs if getattr(q, "category_type", None) == QuestionCategory.ARCHITECTURE]

    q1_obj = None
    best_score = -1.0
    if arch_qs:
        for aq in arch_qs:
            score = 0.0
            aq_text = (aq.question_cn + " " + aq.jd_signal).lower()
            if core_resp_text and any(claim_matches(t, aq_text) for t in re.split(r"[/,、\s]+", core_resp_text) if len(t) >= 2):
                score += 5.0
            if score > best_score:
                best_score = score
                q1_obj = aq

    combined_jd_text = f"{getattr(decoded_jd, 'job_title', '')} {getattr(decoded_jd, 'clean_text', '')} {core_resp_text}".lower()
    is_non_tech = any(k in combined_jd_text for k in [
        "运营", "市场", "产品经理", "ui/ux", "设计", "新媒体", "文案", "编辑",
        "社群", "增长", "商务", "销售", "hr", "人事", "招聘", "财务", "法务"
    ]) and not any(k in combined_jd_text for k in [
        "算法", "架构", "研发", "开发", "工程", "后端", "前端", "测试", "运维", "infra", "sre", "llm"
    ])

    if q1_obj is not None and best_score > 0 and not is_non_tech:
        q1_zh = q1_obj.question_cn
        q1_en = q1_obj.question_en
        q1_signal = q1_obj.jd_signal
        q1_intent = q1_obj.interviewer_intent
        q1_prep = q1_obj.prep_keypoints
        q1_category = "架构与系统设计"
        q1_category_type = "ARCHITECTURE"
        q1_expected = ["核心架构设计与模块划分", "关键技术选型与Trade-off", "高并发/吞吐/稳定性保障措施", "指标Baseline与量化收益"]
    elif is_non_tech:
        q1_zh = f"针对岗位核心职责【{core_resp_text}】，请结合具体业务场景，阐述你的核心策略、关键落地动作、跨部门协同过程以及量化业务成效？"
        q1_en = f"Regarding the core responsibility '{core_resp_text}', elaborate on your core strategy, execution actions, cross-functional collaboration, and quantified business outcomes."
        q1_signal = core_resp_text
        q1_intent = "考察候选人对岗位核心职责的理解深度、策略落地能力与量化业务成果闭环。"
        q1_prep = "1. 明确业务场景与核心目标；2. 阐明个人主导的关键动作与策略推演；3. 给出跨部门协同机制与量化业务收益。"
        q1_category = "业务职责与落地实践"
        q1_category_type = "BUSINESS_CORE"
        q1_expected = ["业务场景与目标定位", "关键动作与策略推演", "协同与执行把控", "核心指标Baseline与业务增长收益"]
    else:
        q1_zh = f"针对岗位核心职责【{core_resp_text}】，请结合具体业务场景，阐述你的端到端技术方案与架构设计，如何权衡关键选型及应对高并发/高可用挑战？"
        q1_en = f"Regarding the core responsibility '{core_resp_text}', elaborate on your end-to-end architecture design, key technical trade-offs, and how you tackle concurrency and stability challenges."
        q1_signal = core_resp_text
        q1_intent = "考察候选人对岗位核心技术职责的系统级掌控度、技术选型权衡及工程落地深度。"
        q1_prep = "1. 分层陈述整体架构与核心交互；2. 阐述关键技术选型与Trade-off；3. 给出高并发/稳定性保障措施与量化效果口径。"
        q1_category = "架构与系统设计"
        q1_category_type = "ARCHITECTURE"
        q1_expected = ["核心架构设计与模块划分", "关键技术选型与Trade-off", "高并发/吞吐/稳定性保障措施", "指标Baseline与量化收益"]

    formatted_questions.append({
        "question_id": 1,
        "target_dimension": "core_responsibility",
        "dimension_name_cn": "核心岗位能力与技术架构深度考查",
        "requirement_id": req_id_q1,
        "requirement_name": core_resp_text,
        "category": q1_category,
        "category_type": q1_category_type,
        "question_zh": q1_zh,
        "question_en": q1_en,
        "jd_signal": q1_signal,
        "interviewer_intent": q1_intent,
        "expected_elements": q1_expected,
        "prep_keypoints": q1_prep,
        "evidence_refs": q1_evidence_refs,
        "evidence_claim_ids": q1_evidence_ids,
        "gap_refs": [],
    })

    # -------------------------------------------------------------------------
    # Q2: project_deep_dive (候选人真实项目经历与关键成果深入追问)
    # -------------------------------------------------------------------------
    if anchor_claim is not None:
        c_text = anchor_claim.text.strip().rstrip("。")
        short_c = c_text[:45] + ("..." if len(c_text) > 45 else "")
        q2_zh = f"你在材料中提到【{short_c}】。请深入说明：1) 你在该工作中的个人独立贡献与核心动作；2) 面对的最关键技术瓶颈与方案权衡；3) 关键成果/指标的 Baseline 测算口径与数据来源；4) 若重新复盘，有何局限与改进空间？"
        q2_en = f"You mentioned in your profile: '{short_c}'. Please explain: 1) Your specific individual actions; 2) The key technical bottleneck and trade-offs; 3) The metric baseline methodology; 4) Limitations and lessons learned."
        q2_signal = short_c
        q2_intent = "深入核实候选人真实主导深度与技术品位，检验是否具备完整的技术攻坚、量化评估闭环与反思能力，防范挂名或夸大贡献。"
        q2_prep = "按背景、目标、个人独立动作、替代方案取舍、baseline与数据来源、团队协作边界与反省复盘结构化作答。"
        q2_evidence_refs = [claim_ref(anchor_claim)]
        q2_evidence_ids = [anchor_claim.claim_id]
        q2_req_id = f"project_deep_dive_{anchor_claim.claim_id}"
        q2_req_name = short_c
    else:
        q2_zh = "请选择你过往最具代表性的一个技术攻坚项目，深入阐述你独立负责的核心模块、遇到的最大技术瓶颈、选型对比、最终量化指标及复盘反思。"
        q2_en = "Please pick your most representative technical project, and explain your individual actions, biggest bottleneck, trade-offs, quantitative results, and retrospective reflection."
        q2_signal = "代表性技术项目"
        q2_intent = "考察候选人在无直接锚定证据时的项目自述完整度、工程攻坚能力与严谨度。"
        q2_prep = "选择最熟悉且有确凿数据支持的项目，按照STAR原则与反思闭环展开。"
        q2_evidence_refs = []
        q2_evidence_ids = []
        q2_req_id = "project_representative"
        q2_req_name = "代表性技术项目"

    formatted_questions.append({
        "question_id": 2,
        "target_dimension": "project_deep_dive",
        "dimension_name_cn": "候选人真实项目经历与关键成果深入追问",
        "requirement_id": q2_req_id,
        "requirement_name": q2_req_name,
        "category": "真实项目与成果追问",
        "category_type": "DEEP_DIVE",
        "question_zh": q2_zh,
        "question_en": q2_en,
        "jd_signal": q2_signal,
        "interviewer_intent": q2_intent,
        "expected_elements": ["个人负责动作", "方案与技术选型", "指标Baseline与数据来源", "边界限制与反思"],
        "prep_keypoints": q2_prep,
        "evidence_refs": q2_evidence_refs,
        "evidence_claim_ids": q2_evidence_ids,
        "gap_refs": [],
    })

    # -------------------------------------------------------------------------
    # Q3: gap_boundary (技术缺口/证据不足边界与真实性防守考查)
    # -------------------------------------------------------------------------
    actionable_gaps = []
    if hasattr(matcher_result, "gap_matrix") and matcher_result.gap_matrix:
        priority = {
            GapState.REAL_GAP: 0,
            GapState.INSUFFICIENT_EVIDENCE: 1,
            GapState.EXPRESSION_GAP: 2,
            GapState.TO_BE_CONFIRMED: 3,
        }
        actionable_gaps = [
            g for g in matcher_result.gap_matrix
            if getattr(g, "state", None) in priority
        ]
        actionable_gaps.sort(key=lambda g: (g.importance not in {"must_have", "mandatory"}, priority.get(g.state, 9)))

    if actionable_gaps:
        top_gap = actionable_gaps[0]
        req_clean = top_gap.requirement_name.replace("技能-", "").replace("职责-", "").replace("硬门槛-", "").replace("门槛要求-", "").replace("隐性考核-", "")
        if top_gap.state == GapState.REAL_GAP:
            q3_zh = f"目标岗位要求【{req_clean}】，但当前材料未直接提供充分证据。请诚实说明你在此领域的实际经验边界，并结合相邻真实经验说明底层可迁移能力。"
            q3_intent = "确认候选人是否能诚实守住真实能力边界，清晰辨析相邻可迁移能力，杜绝临场凭空捏造。"
            q3_prep = "先明确未做过的范围，再说明最接近的真实项目、底层共性、已经完成的学习验证和入职后的补齐步骤。"
        elif top_gap.state == GapState.INSUFFICIENT_EVIDENCE:
            q3_zh = f"你在材料中提到过【{req_clean}】，请选一个真实项目，说明背景、个人动作、方案取舍、结果口径以及证据来源。"
            q3_intent = "核实技能是否落到具体行动和结果，而不是只停留在技能清单。"
            q3_prep = "按背景、目标、个人动作、替代方案、baseline、结果、统计周期、团队边界和失败复盘组织回答。"
        else:
            q3_zh = f"当前材料只有与【{req_clean}】相邻的经验。两者哪些底层能力可迁移，哪些部分你尚未实际做过？"
            q3_intent = "检验候选人能否准确区分可迁移能力与真实经历，避免把相邻技术偷换成直接经验。"
            q3_prep = "分别列出共同原理、已做过的模块、未做过的模块和一个可验证的迁移计划。"

        q3_en = f"Explain the evidence and honest boundary for this job requirement: {req_clean}."
        q3_signal = req_clean
        q3_evidence_refs = [claim_ref(c) for c in find_evidence(req_clean, claims)[:2]]
        q3_evidence_ids = [ref.get("claim_id") for ref in q3_evidence_refs if ref.get("claim_id")]
        q3_gap_refs = [top_gap.requirement_name]
        q3_req_id = getattr(top_gap, "requirement_id", f"gap_{req_clean}")
        q3_req_name = top_gap.requirement_name
    else:
        q3_zh = "针对目标岗位的技术深度与可靠性要求，请分享一次你方案设计或上线中的失败/故障经历，你是如何定位真实根因并建立长期防范机制的？"
        q3_en = "Share a technical failure or outage experience: how did you locate the root cause and build long-term defense mechanisms?"
        q3_signal = "工程严谨性与故障复盘"
        q3_intent = "考察候选人在面临技术挫折与生产故障时的复盘深度、抗压能力与工程严谨性。"
        q3_prep = "真实陈述故障现象、排查定位过程、应急止血动作、根本原因剖析及后续预防规范。"
        q3_evidence_refs = []
        q3_evidence_ids = []
        q3_gap_refs = []
        q3_req_id = "gap_defense"
        q3_req_name = "工程严谨性与故障复盘"

    formatted_questions.append({
        "question_id": 3,
        "target_dimension": "gap_boundary",
        "dimension_name_cn": "技术缺口/证据不足边界与真实性防守考查",
        "requirement_id": q3_req_id,
        "requirement_name": q3_req_name,
        "category": "岗位缺口与事实防守",
        "category_type": "BQ",
        "question_zh": q3_zh,
        "question_en": q3_en,
        "jd_signal": q3_signal,
        "interviewer_intent": q3_intent,
        "expected_elements": ["明确未涉及的技术边界", "诚实说明知识储备或相邻经验", "说明底层原理迁移可能性", "提出可落地的补齐计划与验证途径"],
        "prep_keypoints": q3_prep,
        "evidence_refs": q3_evidence_refs,
        "evidence_claim_ids": q3_evidence_ids,
        "gap_refs": q3_gap_refs,
    })

    return formatted_questions


def prepare_evidence_followup(
    advice_list: List[Dict[str, Any]],
    tailored: Dict[str, Any], answers: Optional[Dict[str, Any]],
    session: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Collect source-bound facts as approval drafts, never as verified claims."""
    targets = [f"{section}[{i}]" for section in ("experience", "projects")
               for i, entry in enumerate(tailored.get(section, []) or []) if isinstance(entry, dict)]
    questions = []
    for advice in sorted(advice_list, key=lambda a: (
        a.get("jd_requirement", {}).get("importance") != "must_have",
        not bool(a.get("risk_flags")),
    )):
        if advice.get("category") == "threshold":
            # Education and seniority must be corrected in the source fields,
            # never appended to an unrelated project as a new bullet.
            continue
        if advice.get("state") not in {"needs_confirmation", "unsupported"} and not advice.get("risk_flags"):
            continue
        requirement = advice["requirement"]
        qid = "E-" + hashlib.sha256(requirement.encode("utf-8")).hexdigest()[:12]
        if any(q["question_id"] == qid for q in questions):
            continue
        anchored = []
        for ref in advice.get("evidence_refs", []):
            match = re.match(r"(experience|projects)\[\d+\]", ref.get("source_path", ""))
            if match and match.group() in targets and match.group() not in anchored:
                anchored.append(match.group())
        questions.append({"question_id": qid, "requirement": requirement,
                          "question": advice["next_question"],
                          "target_path": anchored[0] if len(anchored) == 1 else None,
                          "allowed_target_paths": targets,
                          "evidence_refs": advice.get("evidence_refs", [])})
    prior = (session or {}).get("evidence_followup", {})
    issued = {q["question_id"]: q for q in prior.get("questions_snapshot", [])}
    if not issued:
        issued = {q["question_id"]: q for q in questions[:3]}
    responses = {a["question_id"]: dict(a) for a in prior.get("answers", [])}
    incoming = (answers or {}).get("evidence_answers", [])
    if not isinstance(incoming, list):
        raise ValueError("evidence_answers must be a list")
    seen = set()
    for item in incoming:
        if (not isinstance(item, dict)
                or not isinstance(item.get("question_id"), (str, int))
                or isinstance(item.get("question_id"), bool)
                or item.get("question_id") not in issued):
            raise ValueError("补证回答必须关联当前会话已发出的问题 question_id")
        qid = item["question_id"]
        if qid in seen:
            raise ValueError(f"重复的补证回答: {qid}")
        seen.add(qid)
        text = item.get("answer", "")
        state = item.get("status", "provided")
        if state not in {"provided", "no_experience"}:
            raise ValueError("补证状态只能是 provided 或 no_experience")
        if not isinstance(text, str) or len(text) > 8000 or (state == "provided" and not text.strip()):
            raise ValueError("补证回答必须是非空文本，最长 8000 字符")
        target = item.get("target_path") or issued[qid].get("target_path")
        if state == "provided" and target not in targets:
            raise ValueError(f"请为 {qid} 指定真实经历 target_path，可选：{', '.join(targets)}")
        responses[qid] = {"question_id": qid, "answer": text.strip(), "target_path": target,
                          "status": state, "verification": "user_provided"}
    for qid, item in responses.items():
        if item["status"] == "no_experience":
            continue
        match = re.fullmatch(r"(experience|projects)\[(\d+)\]", item.get("target_path") or "")
        if not match or item["target_path"] not in targets:
            raise ValueError("补证关联的经历已不可用，请重新生成会话")
        section, index = match.group(1), int(match.group(2))
        bullets = tailored[section][index].get("bullets", [])
        if item["answer"] in bullets:
            continue
        planned = tailored.setdefault("applied_patches", [])
        prefix = item["target_path"] + ".bullets["
        additions = sum(p.get("before") == "" and str(p.get("target_path", "")).startswith(prefix)
                        and any(ref.get("source") == "user_answer" for ref in p.get("evidence_refs", []))
                        for p in planned)
        if any(p.get("after") == item["answer"] and str(p.get("target_path", "")).startswith(prefix) for p in planned):
            continue
        planned.append(ResumePatch(
            source_claim_id=qid, target_path=f"{prefix}{len(bullets) + additions}]",
            before="", after=item["answer"], validation_status="pending_user_confirmation",
            evidence_refs=[{"source": "user_answer", "question_id": qid, "excerpt": item["answer"],
                            "verification": "user_provided", "source_path": item["target_path"]}],
            reason="用户补充原文，尚未外部核验；确认后才写入新履历",
        ).to_dict())
    pending = [q for q in questions if q["question_id"] not in responses][:3]
    issued.update({q["question_id"]: q for q in pending})
    return {"questions": pending, "questions_snapshot": list(issued.values()),
            "answers": list(responses.values()), "pending_count": len(pending),
            "status": "awaiting_evidence" if pending else (
                "ready_for_confirmation" if any(p.get("before") != p.get("after")
                    and p.get("validation_status") in {"applied", "pending_user_confirmation"}
                    for p in tailored.get("applied_patches", [])) else "ready_for_export"),
            "answer_template": {"evidence_answers": [
                {"question_id": q["question_id"], "answer": "", "target_path": q["target_path"], "status": "provided"}
                for q in pending]}}


def build_review_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """One outcome-focused summary shared by CLI and structured clients."""
    goal = result["goal"]
    match = result["match_summary"]
    parse_report = result["input_quality"].get("profile_parse_report", {})
    parse_warnings = parse_report.get("warnings", []) if parse_report.get("status") != "reviewed" else []
    issues = [w["message"] for w in parse_warnings]
    issues.extend(match.get("hard_veto_reasons", []))
    gaps = sorted(match.get("gap_matrix", []), key=lambda g: (
        g.get("importance") != "must_have", g.get("state", "").upper() != "REAL_GAP",
    ))
    for gap in gaps:
        if match.get("hard_veto_reasons") and gap.get("category") == "threshold":
            continue
        if gap.get("state", "").lower() != "matched":
            issues.append(f"{gap['requirement_name']}：{gap.get('gap_explanation', '')}")
    patches = result["material_proposal"]["patches"]
    pending = result.get("evidence_followup", {}).get("questions", [])
    unanswered = [q for q in result["interview_questions"] if q["question_id"] not in {
        f["question_id"] for f in result["answer_feedback"] if f.get("status") == "evaluated"}]
    interview_active = goal == "interview" or (
        goal == "review" and result["material_proposal"].get("status") in {"accepted", "rejected"}
        and (unanswered or result.get("practice_queue"))
    )
    if interview_active:
        patches = [] if result["material_proposal"].get("status") in {"accepted", "rejected"} else patches
        followups = result.get("practice_queue", [])
        if followups:
            conclusion = "已根据回答生成追问。"
            action = {"kind": "follow_up_question", "message": followups[0]["question"], "question_id": followups[0]["question_id"]}
        elif unanswered:
            conclusion = f"已根据当前简历准备 {len(result['interview_questions'])} 道面试问题。"
            action = {"kind": "answer_question", "message": unanswered[0]["question_zh"], "question_id": unanswered[0]["question_id"]}
        elif not result["interview_questions"]:
            conclusion = "简历中还没有可用于模拟面试的具体经历。"
            action = {"kind": "provide_resume", "message": "补充真实项目或工作经历后，再生成面试问题。"}
        else:
            conclusion = "本轮面试回答已复盘。"
            action = {"kind": "practice", "message": "结合反馈练习简历中最需要补强的经历。"}
    elif result.get("generated_resumes"):
        conclusion = "简历已生成，请核对成品。"
        action = {"kind": "inspect_export", "message": "打开生成的简历，核对内容完整性和实际排版。"}
    elif result["material_proposal"].get("status") in {"accepted", "rejected"}:
        accepted = result["material_proposal"]["status"] == "accepted"
        patches = []
        conclusion = "该提案已确认，已保留原确认记录。" if accepted else "该提案已拒绝，已保留原拒绝记录。"
        action = {"kind": "resume_accepted_proposal" if accepted else "revise_source",
                  "message": "使用已确认提案继续生成履历和导出。" if accepted else "补充或修正底稿后，重新生成提案。"}
    elif parse_warnings:
        conclusion = "已完成分析，原始材料仍有识别疑点。"
        action = {"kind": "check_source", "message": "先核对解析摘要中的未归类原文和缺失字段，再继续修改。"}
    elif pending:
        conclusion = "已完成岗位对齐，关键事实仍需补充。"
        action = {"kind": "provide_evidence", "message": pending[0]["question"], "question_id": pending[0]["question_id"]}
    elif goal != "interview" and patches:
        conclusion = f"已生成 {len(patches)} 项待确认修改，原始履历未改动。"
        action = {"kind": "confirm_proposal", "message": "核对修改前后内容，确认选定提案后再导出简历。"}
    elif result.get("practice_queue"):
        followup = result["practice_queue"][0]
        conclusion = "本轮回答已复盘，优先补强尚未闭合的事实与解释。"
        action = {"kind": "follow_up_question", "message": followup["question"],
                  "question_id": followup["question_id"]}
    elif unanswered:
        conclusion = f"已准备 {len(result['interview_questions'])} 道岗位相关问题。"
        action = {"kind": "answer_question", "message": unanswered[0]["question_zh"], "question_id": unanswered[0]["question_id"]}
    else:
        conclusion = "当前没有需要确认的内容修改。"
        action = {"kind": "export", "message": "核对公开范围后，使用默认主题导出简历。"}
    if match.get("is_hard_vetoed") and not interview_active:
        conclusion += " 当前材料触发了岗位硬门槛，请人工复核原文与个人条件。"
        action = {"kind": "check_threshold", "message": "先核对岗位硬门槛与原始学历、专业、年限；底稿有误时修正底稿后重新分析，不通过补写项目绕过门槛。"}
    return {"conclusion": conclusion, "key_issues": list(dict.fromkeys(issues))[:3],
            "pending_change_count": len(patches),
            "pending_changes": [{"patch_id": index, **patch} for index, patch in enumerate(patches[:3])],
            "next_action": action}


def answer_context(profile_hash, jd_hash, questions, evidence_questions):
    """Bind submissions to the source version and the questions actually issued."""
    payload = {"profile": profile_hash, "jd": jd_hash,
               "questions": questions, "evidence_questions": evidence_questions}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _answer_context_errors(session, incoming):
    if not (incoming.get("answers") or incoming.get("evidence_answers")):
        return []
    if not session.get("answer_context"):
        return ["旧会话缺少回答版本，请先刷新会话并使用新的回答模板。"]
    if incoming.get("answer_context") != session["answer_context"]:
        return ["回答的材料或题目版本不匹配，请先刷新并填写当前回答模板。"]
    return []


def _pending_interview_feedback(q):
    return {
        "question_id": q["question_id"],
        "question_zh": q["question_zh"],
        "target_dimension": q.get("target_dimension", ""),
        "candidate_answer": "",
        "status": "awaiting_answer",
        "diagnosis": "not_submitted",
        "analysis": "等待候选人输入回答以开展事实核验与深度追问。",
        "coaching_advice": "建议结合具体项目经历，给出包含因果推导与指标基线的完整陈述。",
        "revised_answer": "",
        "refined_answer": "",
        "can_revise": False,
        "verification_status": "unverified",
        "key_takeaway": "请先提交针对该题的回答。",
        "evidence_refs": q.get("evidence_refs", []),
        "missing_elements": [],
        "follow_up_questions": [],
    }


def _review_interview_answers(formatted_questions, answers_dict, session_data, fact_guard, wants_interview):
    debrief_engine = InterviewDebriefEngine()
    feedback_items: List[Dict[str, Any]] = []
    invalid_answers: List[Dict[str, Any]] = []

    # Map of previous feedback and answers from session_data
    previous_feedback_map: Dict[int, Dict[str, Any]] = {}
    previous_answers_map: Dict[int, str] = {}
    if session_data and wants_interview:
        for f in session_data.get("answer_feedback", []):
            if isinstance(f, dict) and "question_id" in f:
                previous_feedback_map[f["question_id"]] = f
        for a in session_data.get("answers", []):
            if isinstance(a, dict) and "question_id" in a:
                previous_answers_map[a["question_id"]] = a.get("answer", "")

    new_answers_by_id: Dict[int, str] = {}
    if answers_dict and isinstance(answers_dict, dict) and answers_dict.get("answers"):
        provided_answers = answers_dict.get("answers", [])
        valid_ids = {q["question_id"] for q in formatted_questions}
        if not isinstance(provided_answers, list):
            invalid_answers.append({"reason": "answers_not_list"})
            provided_answers = []
        for item in provided_answers:
            if isinstance(item, dict):
                qid = item.get("question_id")
                if not isinstance(qid, (str, int)) or isinstance(qid, bool):
                    invalid_answers.append({"question_id": qid, "reason": "invalid_question_id"})
                    continue
                try:
                    normalized_qid = int(qid)
                except (TypeError, ValueError):
                    invalid_answers.append({"question_id": qid, "reason": "invalid_question_id"})
                    continue
                if normalized_qid in new_answers_by_id:
                    invalid_answers.append({"question_id": normalized_qid, "reason": "duplicate_question_id"})
                    continue
                if normalized_qid not in valid_ids:
                    invalid_answers.append({"question_id": normalized_qid, "reason": "unknown_question_id"})
                    continue
                txt = item.get("answer", "")
                if txt is None:
                    txt = ""
                if not isinstance(txt, str):
                    invalid_answers.append({"question_id": normalized_qid, "reason": "answer_not_string"})
                    continue
                if len(txt) > 8000:
                    invalid_answers.append({"question_id": normalized_qid, "reason": "answer_too_long", "max_length": 8000})
                    continue
                # Blank template fields do not erase a previously submitted answer.
                if txt.strip() or normalized_qid not in previous_answers_map:
                    new_answers_by_id[normalized_qid] = txt
            elif isinstance(item, str):
                next_id = len(new_answers_by_id) + 1
                if len(item) > 8000:
                    invalid_answers.append({"question_id": next_id, "reason": "answer_too_long", "max_length": 8000})
                elif next_id in valid_ids:
                    new_answers_by_id[next_id] = item
            else:
                invalid_answers.append({"reason": "answer_item_invalid"})

    # Combine answers: new answers override previous answers for that question_id
    combined_answers_map: Dict[int, str] = dict(previous_answers_map)
    combined_answers_map.update(new_answers_by_id)

    # Now evaluate each question
    for q in formatted_questions:
        qid = q["question_id"]
        # If freshly answered in this round: evaluate
        if qid in new_answers_by_id:
            user_ans = new_answers_by_id[qid]
            if user_ans.strip():
                debrief = debrief_engine.analyze_question(
                    q["question_zh"],
                    user_ans,
                    fact_guard=fact_guard,
                    claim_refs=q.get("evidence_refs", []),
                )
                feedback_items.append({
                    "question_id": qid,
                    "question_zh": q["question_zh"],
                    "target_dimension": q.get("target_dimension", ""),
                    "candidate_answer": user_ans,
                    "status": "evaluated",
                    "diagnosis": debrief.diagnosis.value if hasattr(debrief.diagnosis, "value") else str(debrief.diagnosis),
                    "analysis": debrief.analysis_zh,
                    "coaching_advice": debrief.coaching_advice,
                    "revised_answer": debrief.revised_answer,
                    "refined_answer": debrief.refined_answer,
                    "can_revise": debrief.can_revise,
                    "verification_status": debrief.verification_status,
                    "key_takeaway": debrief.key_takeaway,
                    "evidence_refs": debrief.claim_refs,
                    "missing_elements": debrief.missing_elements,
                    "follow_up_questions": debrief.follow_up_questions,
                })
            else:
                feedback_items.append(_pending_interview_feedback(q))
        # Else if previously evaluated in session_data: retain previous feedback!
        elif qid in previous_feedback_map:
            feedback_items.append(previous_feedback_map[qid])
        # Else: awaiting answer
        else:
            feedback_items.append(_pending_interview_feedback(q))

    practice_queue = [
        {"question_id": f["question_id"], "question": question,
         "diagnosis": f.get("diagnosis"), "evidence_refs": f.get("evidence_refs", [])}
        for f in sorted(feedback_items, key=lambda f: (
            f.get("verification_status") == "verified", not bool(f.get("missing_elements"))))
        if f.get("status") == "evaluated" and f.get("diagnosis") != "well_defended"
        for question in f.get("follow_up_questions", [])[:1]
    ]

    # Prepare combined answers list for result
    combined_answers_list = [
        {"question_id": qid, "answer": ans}
        for qid, ans in sorted(combined_answers_map.items())
    ]

    return feedback_items, invalid_answers, combined_answers_list, practice_queue


def _prepare_review_session(session_data, jd_hash, profile_hash, wants_interview, answers_dict):
    if session_data:
        session_data = validate_review_session(session_data)
        sess_jd_fp = session_data.get("jd_fingerprint")
        sess_prof_fp = session_data.get("profile_fingerprint")
        if sess_jd_fp and sess_jd_fp != jd_hash:
            raise ValueError(f"Session JD fingerprint mismatch: expected {sess_jd_fp}, got {jd_hash}")
        if sess_prof_fp and sess_prof_fp != profile_hash:
            raise ValueError(f"Session Profile fingerprint mismatch: expected {sess_prof_fp}, got {profile_hash}")
        if wants_interview and session_data.get("question_strategy") != "resume":
            session_data = {**session_data, "questions_snapshot": [], "answers": [], "answer_feedback": []}
            if (answers_dict or {}).get("answers"):
                raise ValueError("面试题已切换为当前简历，请先刷新题目，再填写回答。")
        if answers_dict:
            context_errors = _answer_context_errors(session_data, answers_dict)
            if context_errors:
                raise ValueError("; ".join(context_errors))
        formatted_questions = session_data.get("questions_snapshot", []) if wants_interview else []
    else:
        formatted_questions = []
    return session_data, formatted_questions


def run_career_review(
    jd_text: str,
    profile_dict: Union[Dict[str, Any], ProfileContext],
    answers_dict: Optional[Dict[str, Any]] = None,
    listing_age_days: int = 15,
    build_resume: bool = False,
    resume_theme: str = "modern-navy",
    resume_output_dir: Optional[Union[str, Path]] = None,
    reserve_photo: bool = True,
    session_data: Optional[Dict[str, Any]] = None,
    goal: str = "review",
) -> Dict[str, Any]:
    if goal not in {"tailor", "interview", "review"}:
        raise ValueError("review goal must be tailor, interview, or review")
    if answers_dict is not None and not isinstance(answers_dict, dict):
        raise ValueError("answers must be a JSON object")
    wants_interview = goal in {"interview", "review"}
    wants_materials = goal in {"tailor", "review"}
    if build_resume and not wants_materials:
        raise ValueError("面试准备不导出简历；请选择 tailor 目标并确认材料修改。")
    if not wants_interview and (answers_dict or {}).get("answers"):
        raise ValueError("面试回答需要 --goal interview 或 --goal review")
    if not wants_materials and (answers_dict or {}).get("evidence_answers"):
        raise ValueError("材料补证需要 --goal tailor 或 --goal review")
    if build_resume:
        require_public_profile(profile_dict)
    decoder = JDDecoder()
    decoded_jd = decoder.decode(jd_text)

    profile_ctx = build_profile_context(profile_dict if isinstance(profile_dict, (dict, ProfileContext)) else {})
    cand_profile = profile_ctx.get_canonical_profile()
    claims = list(profile_ctx.claims)

    matcher = JDMatcher()
    matcher_result = matcher.match(decoded_jd, cand_profile)

    predictor = JDPredictor() if wants_interview else None
    probability_forecast = predictor.prob_calc.calculate(matcher_result, listing_age_days=listing_age_days) if predictor else None

    jd_hash = hashlib.sha256(jd_text.strip().encode("utf-8")).hexdigest()[:12]
    raw_p = profile_dict.raw_profile if isinstance(profile_dict, ProfileContext) else profile_dict
    profile_hash = hashlib.sha256(json.dumps(raw_p, sort_keys=True).encode("utf-8")).hexdigest()[:12]

    session_data, formatted_questions = _prepare_review_session(
        session_data, jd_hash, profile_hash, wants_interview, answers_dict,
    )
    if wants_interview and not formatted_questions:
        formatted_questions = select_targeted_interview_questions(
            decoded_jd=decoded_jd,
            cand_profile=cand_profile,
            claims=claims,
            matcher_result=matcher_result,
            predictor=predictor,
            resume_first=True,
        )

    fact_guard = FactVerificationGuard(profile_ctx)
    resume_advices = generate_resume_advice(decoded_jd, matcher_result, claims, fact_guard=fact_guard) if wants_materials else []

    evidence_graph = EvidenceGraph.from_profile_context(profile_ctx)
    referenced_claim_ids: List[str] = []
    for advice in resume_advices:
        if not advice.get("safe_bullet"):
            continue
        for ref in advice.get("evidence_refs", []):
            if isinstance(ref, dict) and ref.get("claim_id"):
                referenced_claim_ids.append(str(ref["claim_id"]))
    selected_claim_ids, blocked_claims = evidence_graph.mark_used_for_resume(referenced_claim_ids)
    evidence_gate, evidence_blockers = evidence_graph.can_apply(selected_claim_ids)

    feedback_items, invalid_answers, combined_answers_list, practice_queue = _review_interview_answers(
        formatted_questions, answers_dict, session_data, fact_guard, wants_interview,
    )

    tailored_profile = generate_tailored_profile_from_review(
        {"resume_advice": resume_advices, "match_summary": matcher_result},
        profile_ctx,
        fact_guard=fact_guard,
        evidence_graph=evidence_graph,
    ) if wants_materials else copy.deepcopy(profile_ctx.normalized_profile)
    evidence_followup = prepare_evidence_followup(
        resume_advices, tailored_profile, answers_dict, session_data,
    ) if wants_materials else {}

    evidence_snapshot = create_evidence_snapshot(
        profile=profile_ctx,
        jd=decoded_jd,
        matcher_result=matcher_result,
        evidence_graph=evidence_graph,
        notes="career-review evidence snapshot",
    )
    material_proposal = create_material_proposal(
        {"tailored_profile": tailored_profile} if wants_materials else {},
        profile_ctx,
        jd_text,
        proposal_id=f"PROP-{profile_hash}-{jd_hash}",
    )
    # A new evidence round must not overwrite the approval of an older draft.
    patch_revision = hashlib.sha256(json.dumps(material_proposal.patches, ensure_ascii=False,
                                               sort_keys=True).encode("utf-8")).hexdigest()[:12]
    material_proposal.proposal_id += f"-{patch_revision}"
    material_proposal.proposal_hash = material_proposal.compute_hash()

    # Overall pipeline result dictionary strictly conforming to career-review.v1 schema
    result = {
        "schema_version": "career-review.v1",
        "answer_context": answer_context(profile_hash, jd_hash, formatted_questions,
                                         evidence_followup.get("questions_snapshot", [])),
        "goal": goal,
        "execution": {
            "executed_stages": ["jd_decode", "full_match"]
                + (["resume_advice", "material_proposal", "evidence_followup"] if wants_materials else [])
                + (["interview_questions", "answer_feedback"] if wants_interview else []),
            "skipped_stages": ([] if wants_materials else ["resume_advice", "material_proposal", "evidence_followup"])
                + ([] if wants_interview else ["interview_questions", "answer_feedback"]),
            "resumed": bool(session_data),
        },
        "jd_breakdown": {
            "job_title": decoded_jd.job_title,
            "company_or_dept": decoded_jd.company_or_dept,
            "core_skills": [s.name for s in decoded_jd.core_skills],
            "hard_thresholds": [
                {
                    "category": t.category,
                    "requirement": t.requirement,
                    "is_mandatory": t.is_mandatory,
                }
                for t in decoded_jd.hard_thresholds
            ],
            "implicit_signals": [
                {
                    "original_text": sig.original_text,
                    "translated_meaning": sig.translated_meaning,
                    "underlying_risk": sig.underlying_risk,
                }
                for sig in decoded_jd.implicit_signals
            ],
            "business_pain_points": [
                {
                    "aspect": p.aspect,
                    "description": p.description,
                    "evaluation_metric": p.evaluation_metric,
                }
                for p in decoded_jd.business_pain_points
            ],
        },
        "match_summary": {
            "raw_match_score": matcher_result.raw_match_score,
            "final_match_score": matcher_result.final_match_score,
            "must_have_score": matcher_result.must_have_score,
            "nice_to_have_score": matcher_result.nice_to_have_score,
            "hidden_signal_fit": matcher_result.hidden_signal_fit,
            "is_hard_vetoed": matcher_result.is_hard_vetoed,
            "hard_veto_reasons": matcher_result.hard_veto_reasons,
            "breakthrough_advice": matcher_result.breakthrough_advice,
            "prediction": asdict(probability_forecast) if probability_forecast else None,
            "prediction_note": "无经校准的招聘结果数据，暂不提供真实面试或录用概率。",
            "gap_matrix": [
                {
                    "requirement_name": g.requirement_name,
                    "category": g.category,
                    "importance": g.importance,
                    "state": g.state.value if hasattr(g.state, "value") else str(g.state),
                    "actionable_advice": g.actionable_advice,
                    "candidate_evidence": g.candidate_evidence,
                    "gap_explanation": g.gap_explanation,
                }
                for g in matcher_result.gap_matrix
            ],
        },
        "resume_advice": resume_advices,
        "evidence_followup": evidence_followup,
        "interview_questions": formatted_questions,
        "question_generation": {
            "strategy": "resume_grounded_simulation" if wants_interview else "not_requested",
            "dimensions": [
                {"dimension": q["target_dimension"], "name": q["dimension_name_cn"], "question_id": q["question_id"]}
                for q in formatted_questions
            ],
            "total_questions": len(formatted_questions),
        },
        "answers": combined_answers_list,
        "answer_feedback": feedback_items,
        "practice_queue": practice_queue,
        "input_quality": {
            "profile_parse_report": raw_p.get("_parse_report", {}) if isinstance(raw_p, dict) else {},
            "answers": combined_answers_list,
            "invalid_answers": invalid_answers,
            "evaluated_count": len([f for f in feedback_items if f.get("status") == "evaluated"]),
            "pending_count": len([f for f in feedback_items if f.get("status") == "awaiting_answer"]),
        },
        "polish_focus": {
            "focus_area": "interview_defense" if wants_interview else "resume_materials",
            "defense_checkpoints": [
                f"Q{q['question_id']}: {q.get('jd_signal', '')} ({q.get('category', q.get('dimension_name_cn', ''))})"
                for q in formatted_questions
            ],
        },
        "tailored_profile": tailored_profile,
        "evidence_graph": evidence_graph.audit_snapshot(claim_ids=selected_claim_ids),
        "evidence_gate": {
            "is_ready": evidence_gate,
            "selected_claim_ids": selected_claim_ids,
            "blocked_claims": blocked_claims,
            "blockers": evidence_blockers,
        },
        "evidence_snapshot": evidence_snapshot,
        "material_proposal": material_proposal.to_dict(),
        "resume_patches": [
            adv["patch"] for adv in resume_advices if adv.get("patch")
        ],
    }

    # A versioned template must also match when submitted without a saved session.
    if (not session_data and answers_dict and "answer_context" in answers_dict
            and answers_dict["answer_context"] != result["answer_context"]):
        raise ValueError("回答的材料或题目版本不匹配，请先刷新并填写当前回答模板。")

    # Optional resume generation using tailored_profile
    if build_resume:
        if material_proposal.patches:
            raise ValueError("存在待确认修改，请先保存提案并通过 proposal accept 确认，再导出简历。")
        from core.resume_builder import ResumeBuilder

        if resume_output_dir is None:
            from core.paths import get_default_resume_output_dir
            out_dir = get_default_resume_output_dir()
        else:
            out_dir = Path(resume_output_dir).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)

        builder = ResumeBuilder(tailored_profile)
        if resume_theme == "all":
            built_files = {name: {kind: str(path) for kind, path in paths.items()}
                           for name, paths in builder.build_all(out_dir, photo=reserve_photo).items()}
            primary_pdf = None
            if "modern-navy" in built_files and "pdf" in built_files["modern-navy"]:
                primary_pdf = built_files["modern-navy"]["pdf"]
            result["generated_resumes"] = {
                "theme": resume_theme,
                "pdf": primary_pdf,
                "files": built_files,
                "output_dir": str(out_dir),
            }
        else:
            built_files = {kind: str(path) for kind, path in
                           builder.build_theme(resume_theme, out_dir, photo=reserve_photo).items()}
            primary_pdf = built_files.get("pdf")
            result["generated_resumes"] = {
                **built_files,
                "theme": resume_theme,
                "pdf": primary_pdf,
                "html": built_files.get("html"),
                "output_dir": str(out_dir),
            }

        cand_name = tailored_profile.get("candidate", {}).get("name") or tailored_profile.get("name") or "候选人"
        try:
            import re
            import shutil
            clean_name = re.sub(r'[\/:*?"<>|]', '_', str(cand_name).strip()) or "个人"
            if primary_pdf and Path(primary_pdf).exists():
                named_pdf = out_dir / f"{clean_name}_个人简历.pdf"
                shutil.copy2(primary_pdf, named_pdf)
                result["generated_resumes"]["named_pdf"] = str(named_pdf)
            primary_html = result["generated_resumes"].get("html")
            if not primary_html and resume_theme == "all" and "modern-navy" in built_files:
                primary_html = built_files["modern-navy"].get("html")
            if primary_html and Path(primary_html).exists():
                named_html = out_dir / f"{clean_name}_个人简历.html"
                shutil.copy2(primary_html, named_html)
                result["generated_resumes"]["named_html"] = str(named_html)
        except Exception:
            pass

    result["summary"] = build_review_summary(result)
    return result


def create_review_session(
    jd_text: str,
    profile_dict: Union[Dict[str, Any], ProfileContext],
    review_result: Dict[str, Any],
    base_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Creates a verifiable lightweight JSON session snapshot."""
    jd_hash = hashlib.sha256(jd_text.strip().encode("utf-8")).hexdigest()[:12]
    raw_p = profile_dict.raw_profile if isinstance(profile_dict, ProfileContext) else profile_dict
    profile_hash = hashlib.sha256(json.dumps(raw_p, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    session_id = base_session.get("session_id") if (base_session and base_session.get("session_id")) else f"SESSION-{jd_hash}-{profile_hash}"

    questions_snapshot = copy.deepcopy(review_result.get("interview_questions", []))

    session_answers = review_result.get("answers", [])
    if not session_answers and isinstance(review_result.get("input_quality"), dict):
        session_answers = review_result["input_quality"].get("answers", [])

    feedbacks = review_result.get("answer_feedback", [])
    evaluated_count = len([f for f in feedbacks if f.get("status") == "evaluated" and f.get("diagnosis") != "not_submitted"])
    total_q = len(questions_snapshot)
    status = "completed" if (total_q > 0 and evaluated_count >= total_q) else "awaiting_answer"
    goal = review_result.get("goal", "review")
    if goal == "tailor":
        proposal_status = review_result.get("material_proposal", {}).get("status")
        if proposal_status in {"accepted", "rejected"}:
            status = "accepted" if proposal_status == "accepted" else "needs_source_revision"
        elif review_result.get("evidence_followup", {}).get("pending_count"):
            status = "awaiting_evidence"
        elif review_result.get("material_proposal", {}).get("patches"):
            status = "awaiting_confirmation"
        else:
            status = "ready_for_export"

    return {
        "session_id": session_id,
        "schema_version": "career-review-session.v1",
        "answer_context": review_result.get("answer_context"),
        "workflow": review_result.get("workflow", {}),
        "goal": goal,
        "question_strategy": "resume" if goal in {"interview", "review"} else "not_requested",
        "execution": review_result.get("execution", {}),
        "jd_fingerprint": jd_hash,
        "profile_fingerprint": profile_hash,
        "status": status,
        "generated_questions_count": total_q,
        "answered_questions_count": len(session_answers),
        "evaluated_questions_count": evaluated_count,
        "minimum_loop_completed": evaluated_count >= 1,
        "all_questions_completed": total_q > 0 and evaluated_count >= total_q,
        "questions_snapshot": questions_snapshot,
        "answers": session_answers,
        "answer_feedback": feedbacks,
        "evidence_followup": review_result.get("evidence_followup", {}),
    }


def validate_review_session(session: Any) -> Dict[str, Any]:
    """Validate stored JSON before workflow code dereferences nested fields."""
    if not isinstance(session, dict):
        raise ValueError("Session must be a JSON object")
    session = copy.deepcopy(session)
    for key in ("workflow", "evidence_followup"):
        if session.get(key) is None:
            session[key] = {}
        if not isinstance(session[key], dict):
            raise ValueError(f"Session {key} must be a JSON object")
    if session.get("goal") is not None and session["goal"] not in ("tailor", "interview", "review"):
        raise ValueError("Session goal must be tailor, interview or review")
    workflow = session["workflow"]
    if workflow.get("inputs") is None:
        workflow["inputs"] = {}
    if not isinstance(workflow["inputs"], dict):
        raise ValueError("Session workflow.inputs must be a JSON object")
    for key, value in workflow["inputs"].items():
        if key in {"jd", "profile"} and value is not None and not isinstance(value, str):
            raise ValueError(f"Session workflow.inputs.{key} must be a path string")
    for key in ("workspace", "proposal_db", "session_path", "resume_output_dir", "resume_theme", "application_id", "source_profile", "source_profile_fingerprint"):
        if workflow.get(key) is not None and not isinstance(workflow[key], str):
            raise ValueError(f"Session workflow.{key} must be a string")
    for container, keys in ((session, ("questions_snapshot", "answers", "answer_feedback")),
                            (session["evidence_followup"], ("questions", "questions_snapshot", "answers"))):
        for key in keys:
            values = container.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, dict) or "question_id" not in v for v in values):
                raise ValueError(f"Session {key} must be a list of objects with question_id")
            for value in values:
                if not isinstance(value["question_id"], (str, int)) or isinstance(value["question_id"], bool):
                    raise ValueError("Session question_id must be a string or integer")
                if "answer" in value and not isinstance(value["answer"], str):
                    raise ValueError("Session answer must be a string")
                if container is session and key == "questions_snapshot" and not isinstance(value.get("question_zh"), str):
                    raise ValueError("Session question must contain question_zh text")
                if key == "answer_feedback" and (
                    not isinstance(value.get("follow_up_questions", []), list)
                    or any(not isinstance(q, str) for q in value.get("follow_up_questions", []))
                ):
                    raise ValueError("Session follow_up_questions must be a list of strings")
                if container is session["evidence_followup"] and key == "answers":
                    if value.get("status") not in ("provided", "no_experience") or not isinstance(value.get("answer"), str):
                        raise ValueError("Session evidence answer requires status and answer text")
            container[key] = values
    return session


def save_review_session(session: Dict[str, Any], output_path: Union[str, Path]) -> None:
    """Atomically save review session JSON to disk using write_json_atomic."""
    write_json_atomic(session, output_path, allow_shadow=False)


def load_review_session(session_path: Union[str, Path]) -> Dict[str, Any]:
    """Load review session JSON from disk."""
    p = Path(session_path)
    if not p.exists():
        raise FileNotFoundError(f"Review session file not found: {session_path}")
    with open(p, "r", encoding="utf-8") as f:
        return validate_review_session(json.load(f))


def validate_session_answers(
    session: Dict[str, Any],
    incoming_answers: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validates that submitted answers correspond to the session's question snapshot."""
    errors = []
    if not isinstance(session, dict):
        return False, ["invalid_session_object"]
    if isinstance(incoming_answers, dict):
        errors.extend(_answer_context_errors(session, incoming_answers))
    valid_qids = {q.get("question_id") for q in session.get("questions_snapshot", [])}
    answers_list = incoming_answers.get("answers", []) if isinstance(incoming_answers, dict) else []
    if not isinstance(answers_list, list):
        return False, ["answers_field_must_be_list"]
    for ans in answers_list:
        if isinstance(ans, dict):
            qid = ans.get("question_id")
            if not isinstance(qid, (str, int)) or isinstance(qid, bool):
                errors.append("invalid_question_id_type")
            elif qid not in valid_qids:
                errors.append(f"question_id_{qid}_not_in_session_snapshot")
        elif isinstance(ans, str):
            pass
        else:
            errors.append("invalid_answer_entry_format")
    evidence_ids = {q.get("question_id") for q in session.get("evidence_followup", {}).get("questions_snapshot", [])}
    evidence_answers = incoming_answers.get("evidence_answers", []) if isinstance(incoming_answers, dict) else []
    if not isinstance(evidence_answers, list):
        errors.append("evidence_answers_field_must_be_list")
    else:
        for answer in evidence_answers:
            if (not isinstance(answer, dict)
                    or not isinstance(answer.get("question_id"), (str, int))
                    or isinstance(answer.get("question_id"), bool)
                    or answer.get("question_id") not in evidence_ids):
                errors.append("evidence_question_not_in_session_snapshot")
    return len(errors) == 0, errors


def generate_defense_followup_chain(
    context_text: str = "",
    chain_type: str = "project_boundary",
    role: str = "tech_interviewer",
    num_layers: int = 3,
) -> Dict[str, Any]:
    """
    Generates a 2-4 layer defense follow-up question chain using OfferGet's defense engine.
    """
    from core.defense.chain import DefenseQuestionChain, DefenseRole, QuestionChainType

    try:
        ct = QuestionChainType(chain_type)
    except ValueError:
        ct = QuestionChainType.PROJECT_BOUNDARY

    try:
        r = DefenseRole(role)
    except ValueError:
        r = DefenseRole.TECH_INTERVIEWER

    chain = DefenseQuestionChain.generate_chain(ct, context_text=context_text, role=r, num_layers=num_layers)
    return chain.to_dict()

