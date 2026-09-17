"""
OfferGet Job Flow Orchestration Engine (core/job_flow.py)
=========================================================
Implements the competition track 2 closed-loop job-seeking pipeline:
1. canonical JD breakdown (`jd_breakdown`) via modules.jd_analyst.decoder
2. candidate matching & fact-grounded resume recommendations (`resume_advice`) via profile_adapter
3. exactly 3 targeted interview questions (`interview_questions`) via predictor.predict_targeted_questions
4. one round of structured answer feedback (`answer_feedback`) via InterviewDebriefEngine
5. deep polish focus (`polish_focus`: "interview_defense")
6. schema version: "career-review.v1"
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.interview_debrief import InterviewDebriefEngine
from core.jd_compat import profile_to_canonical
from core.fact_guard import FactVerificationGuard
from core.asu_modeler import AsuModeler
from core.validator import validate_anti_ai_slop
from core.profile_adapter import EvidenceClaim, claim_ref, find_evidence, iter_profile_claims
from modules.jd_analyst.decoder import JDDecoder
from modules.jd_analyst.matcher import JDMatcher
from modules.jd_analyst.models import CandidateProfile, DecodedJD, GapState, MatcherResult
from modules.jd_analyst.predictor import JDPredictor


def build_candidate_profile(profile_dict: Dict[str, Any]) -> CandidateProfile:
    """Use the shared profile adapter so missing facts remain unknown."""
    return profile_to_canonical(profile_dict if isinstance(profile_dict, dict) else {})


STRONG_ROLE_PATTERN = re.compile(r"主导|统筹|牵头|Owner|owner|Lead|lead|架构师|从\s*0\s*(?:到|→|->)\s*1")
METRIC_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:%|倍|x|X|ms|s|分钟|小时|天|周|万元|亿元|卡|GPU|QPS|TPS)")
ATTRIBUTION_PATTERN = re.compile(r"个人|本人|独立|我负责|我实现|团队|协同|共同|归因|贡献边界")


def _claim_risk_flags(claim: EvidenceClaim) -> List[Dict[str, str]]:
    """Audit role, scope, metrics and attribution without inventing facts."""
    flags: List[Dict[str, str]] = []
    text = claim.text

    for issue in AsuModeler().audit_bullet_inflation(
        text,
        verification=claim.verification,
        user_declared_role="contributor" if not claim.role_scope else "module_owner",
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
            action = "rewrite"
            safe_bullet = matching_claims[0].text if matching_claims else ""
            grounding_note = f"候选人具备底层相通经验，建议将术语转换为 JD 要求的关键词：{gap.actionable_advice}"
        elif gap.state == GapState.INSUFFICIENT_EVIDENCE:
            state = "needs_confirmation"
            action = "add_evidence"
            safe_bullet = matching_claims[0].text if matching_claims else ""
            grounding_note = f"仅有泛化表述，请候选人依据事实补充具体基线与度量：{gap.actionable_advice}"
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
                evidence_type = "none"
                grounding_note = "候选人原文包含未通过事实核验的数字或指标，补充来源后再改写。"

        blocking_codes = {
            "P1_SCOPE_INFLATION",
            "P2_UNBOUNDED_SUPERLATIVE",
            "P3_TEMPORAL_CONFUSION",
            "role_scope_unverified",
            "metric_context_missing",
            "personal_attribution_missing",
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
            "gap_explanation": gap.gap_explanation,
            "grounding_note": grounding_note,
            "guard_report": guard_report,
            "risk_flags": risk_flags,
            "next_question": next_question,
            "uncertainty": "needs_confirmation" if state == "needs_confirmation" else "none",
        })

    return advice_list


def generate_tailored_profile_from_review(
    review_result: Dict[str, Any],
    base_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """Derive targeted tailored candidate profile from career review advice.

    Extracts safe_bullet recommendations (verified, un-inflated, fact-grounded)
    and injects or supplements them into corresponding experiences or projects
    in base_profile, generating a highly tailored profile for the target JD.
    """
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

    # 4. Extract and inject verified safe_bullet evidence
    if isinstance(review_result, list):
        advice_list = review_result
    elif isinstance(review_result, dict):
        advice_list = review_result.get("resume_advice", [])
    else:
        advice_list = []

    for advice in advice_list:
        if not isinstance(advice, dict):
            continue
        safe_bullet = advice.get("safe_bullet", "")
        if not isinstance(safe_bullet, str):
            continue
        safe_bullet = safe_bullet.strip()
        if not safe_bullet:
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

        target_exp_indices: List[int] = []
        target_proj_indices: List[int] = []
        excerpts: List[str] = []

        for ref in evidence_refs:
            sp = ref.get("source_path", "")
            cid = ref.get("claim_id", "")
            if ref.get("excerpt"):
                excerpts.append(ref["excerpt"])

            m_exp = re.search(r"experience\[(\d+)\]", sp)
            if m_exp:
                target_exp_indices.append(int(m_exp.group(1)))
            m_proj = re.search(r"projects\[(\d+)\]", sp)
            if m_proj:
                target_proj_indices.append(int(m_proj.group(1)))

            if cid and experiences:
                for e_idx, exp in enumerate(experiences):
                    if not isinstance(exp, dict):
                        continue
                    for h in exp.get("highlights", []):
                        if isinstance(h, dict) and h.get("claim_id") == cid:
                            target_exp_indices.append(e_idx)

        # Keyword matching fallback
        if not target_exp_indices and not target_proj_indices and experiences:
            best_idx = -1
            best_score = 0
            for e_idx, exp in enumerate(experiences):
                if not isinstance(exp, dict):
                    continue
                exp_text = f"{exp.get('company', '')} {exp.get('role', '')} {' '.join(exp.get('bullets', []))}".lower()
                score = 0
                if requirement and requirement.lower() in exp_text:
                    score += 5
                for token in re.split(r"[/,、\s\-]+", safe_bullet):
                    if len(token) >= 2 and token.lower() in exp_text:
                        score += 1
                if score > best_score:
                    best_score = score
                    best_idx = e_idx
            if best_idx >= 0 and best_score >= 1:
                target_exp_indices.append(best_idx)
            elif category in ("responsibility", "experience") or action == "rewrite":
                target_exp_indices.append(0)

        # Inject / rewrite into matched experiences
        for e_idx in dict.fromkeys(target_exp_indices):
            if 0 <= e_idx < len(experiences):
                exp = experiences[e_idx]
                bullets = exp.setdefault("bullets", [])

                if safe_bullet in bullets:
                    continue

                replaced = False
                if action == "rewrite":
                    for b_idx, existing_b in enumerate(bullets):
                        if any(ex and ex in existing_b for ex in excerpts):
                            bullets[b_idx] = safe_bullet
                            replaced = True
                            break

                if not replaced:
                    bullets.append(safe_bullet)

                if "highlights" in exp and isinstance(exp["highlights"], list):
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
                            "verified_metrics": True,
                            "tailored": True,
                        })

        # Inject into matched projects
        for p_idx in dict.fromkeys(target_proj_indices):
            if projects and 0 <= p_idx < len(projects):
                proj = projects[p_idx]
                p_bullets = proj.setdefault("bullets", [])
                if safe_bullet not in p_bullets:
                    p_bullets.append(safe_bullet)

    return tailored


def run_career_review(
    jd_text: str,
    profile_dict: Dict[str, Any],
    answers_dict: Optional[Dict[str, Any]] = None,
    listing_age_days: int = 15,
    build_resume: bool = False,
    resume_theme: str = "modern-navy",
    resume_output_dir: Optional[Union[str, Path]] = None,
    reserve_photo: bool = True,
) -> Dict[str, Any]:
    decoder = JDDecoder()
    decoded_jd = decoder.decode(jd_text)

    cand_profile = build_candidate_profile(profile_dict)
    claims = iter_profile_claims(profile_dict)

    matcher = JDMatcher()
    matcher_result = matcher.match(decoded_jd, cand_profile)

    predictor = JDPredictor()
    probability_forecast = predictor.prob_calc.calculate(matcher_result, listing_age_days=listing_age_days)
    questions = predictor.predict_targeted_questions(decoded_jd, matcher_result, count=3)

    formatted_questions: List[Dict[str, Any]] = []
    for q in questions:
        q_keywords = [w for w in re.split(r"[/,、\s]+", q.question_cn + " " + q.jd_signal) if len(w) >= 2]
        related_claims = []
        for kw in q_keywords[:5]:
            matched = find_evidence(kw, claims)
            if matched:
                related_claims.extend(matched)

        evidence_refs = [claim_ref(c) for c in related_claims[:3]]

        formatted_questions.append({
            "question_id": q.question_id,
            "category": q.category_cn,
            "category_type": q.category_type.value if hasattr(q.category_type, "value") else str(q.category_type),
            "question_zh": q.question_cn,
            "question_en": q.question_en,
            "jd_signal": q.jd_signal,
            "interviewer_intent": q.interviewer_intent,
            "prep_keypoints": q.prep_keypoints,
            "evidence_refs": evidence_refs,
            "gap_refs": [gap.requirement_name for gap in matcher_result.gap_matrix if any(
                token and token.lower() in (q.question_cn + " " + q.jd_signal).lower()
                for token in re.split(r"[/,、\s\-]+", gap.requirement_name.replace("技能-", "").replace("职责-", ""))
                if len(token) >= 2
            )][:3],
        })

    fact_guard = FactVerificationGuard(profile_dict if isinstance(profile_dict, dict) else {})
    resume_advices = generate_resume_advice(decoded_jd, matcher_result, claims, fact_guard=fact_guard)

    debrief_engine = InterviewDebriefEngine()
    feedback_items: List[Dict[str, Any]] = []
    invalid_answers: List[Dict[str, Any]] = []

    if answers_dict and isinstance(answers_dict, dict) and answers_dict.get("answers"):
        provided_answers = answers_dict.get("answers", [])
        ans_by_id: Dict[int, str] = {}
        valid_ids = {q["question_id"] for q in formatted_questions}
        if not isinstance(provided_answers, list):
            invalid_answers.append({"reason": "answers_not_list"})
            provided_answers = []
        for item in provided_answers:
            if isinstance(item, dict):
                qid = item.get("question_id")
                try:
                    normalized_qid = int(qid)
                except (TypeError, ValueError):
                    invalid_answers.append({"question_id": qid, "reason": "invalid_question_id"})
                    continue
                if normalized_qid in ans_by_id:
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
                ans_by_id[normalized_qid] = txt
            elif isinstance(item, str):
                next_id = len(ans_by_id) + 1
                if len(item) > 8000:
                    invalid_answers.append({"question_id": next_id, "reason": "answer_too_long", "max_length": 8000})
                elif next_id in valid_ids:
                    ans_by_id[next_id] = item
            else:
                invalid_answers.append({"reason": "answer_item_invalid"})

        for q in formatted_questions:
            qid = q["question_id"]
            user_ans = ans_by_id.get(qid, "")
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
                    "candidate_answer": user_ans,
                    "status": "evaluated",
                    "diagnosis": debrief.diagnosis.value if hasattr(debrief.diagnosis, "value") else str(debrief.diagnosis),
                    "analysis": debrief.analysis_zh,
                    "refined_answer": debrief.refined_answer,
                    "key_takeaway": debrief.key_takeaway,
                    "evidence_refs": debrief.claim_refs,
                    "missing_elements": debrief.missing_elements,
                    "follow_up_questions": debrief.follow_up_questions,
                })
            else:
                feedback_items.append({
                    "question_id": qid,
                    "question_zh": q["question_zh"],
                    "candidate_answer": "",
                    "status": "awaiting_answer",
                    "diagnosis": "not_submitted",
                    "analysis": "未提供回答。请针对该问题提交您的作答以获得针对性攻防诊断。",
                    "refined_answer": q["prep_keypoints"],
                    "key_takeaway": "参考题目的考查意图与备考要点构思 STAR 框架回答。",
                })
    else:
        for q in formatted_questions:
            feedback_items.append({
                "question_id": q["question_id"],
                "question_zh": q["question_zh"],
                "candidate_answer": "",
                "status": "awaiting_answer",
                "diagnosis": "not_submitted",
                "analysis": "候选人尚未提交该题的一轮回答。请提交回答以触发基于指标与证据的诊断。",
                "refined_answer": q["prep_keypoints"],
                "key_takeaway": "明确指标口径、数据来源和个人贡献边界。",
            })

    polish_focus = {
        "focus_area": "interview_defense",
        "description": "针对真实证据、指标口径与个人贡献边界的防守训练",
        "defense_checkpoints": [
            "确保所有量化指标自带 baseline、结果、单位和数据来源，避免被追问时判定为 metric_drift",
            "在被问及未涉猎领域时诚实划定边界并提出可迁移能力，避免白板硬猜触发 fatal_gap",
            "对主导、搭建、优化等强动词准备个人动作、替代方案、失败复盘和团队边界"
        ],
        "total_claims_indexed": len(claims),
        "verified_metrics_protected": bool(fact_guard.master_profile),
        "fact_guard_verdict": "available" if fact_guard.master_profile else "profile_missing",
        "invalid_answers": invalid_answers,
    }

    result = {
        "schema_version": "career-review.v1",
        "jd_breakdown": {
            "job_title": getattr(decoded_jd, "job_title", ""),
            "company_or_dept": getattr(decoded_jd, "company_or_dept", ""),
            "target_level": getattr(decoded_jd, "target_level", ""),
            "compensation_band": getattr(decoded_jd, "compensation_band", ""),
            "location": getattr(decoded_jd, "location", ""),
            "tech_domains": getattr(decoded_jd, "tech_domains", []),
            "hard_thresholds": [asdict(t) for t in getattr(decoded_jd, "hard_thresholds", [])],
            "core_responsibilities": [asdict(r) for r in getattr(decoded_jd, "core_responsibilities", [])],
            "core_skills": [asdict(s) for s in getattr(decoded_jd, "core_skills", [])],
            "implicit_signals": [asdict(sig) for sig in getattr(decoded_jd, "implicit_signals", [])],
            "business_pain_points": [asdict(p) for p in getattr(decoded_jd, "business_pain_points", [])],
            "filtered_boilerplates": [asdict(b) if hasattr(b, "__dataclass_fields__") else str(b) for b in getattr(decoded_jd, "filtered_boilerplates", [])],
            "source_note": "岗位拆解仅使用提供的 JD 原文；隐性信号和业务解释属于启发式推断。",
        },
        "match_summary": {
            "final_match_score": matcher_result.final_match_score,
            "raw_match_score": matcher_result.raw_match_score,
            "must_have_score": matcher_result.must_have_score,
            "nice_to_have_score": matcher_result.nice_to_have_score,
            "hidden_signal_fit": matcher_result.hidden_signal_fit,
            "is_hard_vetoed": matcher_result.is_hard_vetoed,
            "hard_veto_reasons": matcher_result.hard_veto_reasons,
            "breakthrough_advice": matcher_result.breakthrough_advice,
            "prediction": asdict(probability_forecast),
            "prediction_note": "基于规则和当前材料的启发式区间，不代表真实录用概率。",
        },
        "resume_advice": resume_advices,
        "interview_questions": formatted_questions,
        "question_generation": {
            "status": "complete" if len(formatted_questions) >= 3 else "insufficient_jd_signals",
            "requested_count": 3,
            "generated_count": len(formatted_questions),
            "method": "deterministic JD/gap ranking over the compatibility question bank",
        },
        "answer_feedback": feedback_items,
        "input_quality": {
            "route": "complete_review" if jd_text.strip() and claims else "insufficient_input",
            "jd_available": bool(jd_text.strip()),
            "profile_evidence_available": bool(claims),
            "invalid_answers": invalid_answers,
            "evidence_claim_count": len(claims),
            "profile_fact_policy": "missing facts remain unknown",
        },
        "polish_focus": polish_focus,
    }

    tailored_profile = generate_tailored_profile_from_review(
        {"resume_advice": resume_advices, "match_summary": matcher_result},
        profile_dict,
    )
    result["tailored_profile"] = tailored_profile

    if build_resume:
        from core.resume_builder import ResumeBuilder

        if resume_output_dir is None:
            out_dir = PROJECT_ROOT / "output" / "resumes"
        else:
            out_dir = Path(resume_output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        builder = ResumeBuilder(tailored_profile)
        if resume_theme == "all":
            built_files = builder.build_all(out_dir, photo=reserve_photo)
            primary_pdf = None
            if "modern-navy" in built_files and "pdf" in built_files["modern-navy"]:
                primary_pdf = built_files["modern-navy"]["pdf"]
            elif built_files:
                first_theme = next(iter(built_files.values()))
                primary_pdf = first_theme.get("pdf")
            result["generated_resumes"] = {
                "theme": resume_theme,
                "pdf": primary_pdf,
                "files": built_files,
                "output_dir": out_dir,
            }
        else:
            built_files = builder.build_theme(resume_theme, out_dir, photo=reserve_photo)
            result["generated_resumes"] = {
                **built_files,
                "theme": resume_theme,
                "pdf": built_files.get("pdf"),
                "html": built_files.get("html"),
                "output_dir": out_dir,
            }

    return result

