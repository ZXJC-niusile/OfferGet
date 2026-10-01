"""
OfferGet ATS Auditor Engine
Four-Dimension ATS Scorer, Three-State Skill Ledger, and Resume Visibility System.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.cli_helpers import load_json_or_text
from core.profile_adapter import (
    ProfileContext,
    ProfileEvidenceIndex,
    build_profile_evidence_index,
)
from core.lexicon import (
    STRONG_ACTION_VERBS_EN,
    STRONG_ACTION_VERBS_ZH,
    WEAK_ACTION_VERBS_EN,
    WEAK_ACTION_VERBS_ZH,
    QUANTIFIED_PATTERNS,
    AI_BUZZWORDS_LEXICON,
    STANDARD_SECTIONS,
    FORMATTING_RISKS,
    DEFENSE_GUIDE_TEMPLATES,
)


# ---------------------------------------------------------------------------
# Helper Extraction Functions
# ---------------------------------------------------------------------------

def extract_bullets_from_input(profile_or_text: Any) -> Tuple[List[str], Dict[str, Any]]:
    """
    Extracts bullet points and metadata from a candidate profile dict, ProfileContext,
    ProfileEvidenceIndex, or raw resume text.
    Returns: (bullets_list, meta_info)
    """
    bullets: List[str] = []
    meta: Dict[str, Any] = {
        "raw_text": "",
        "years_of_experience": 0,
        "is_dict": False,
        "parsed_profile": None,
        "evidence_index": None,
    }

    # 1. Handle ProfileEvidenceIndex directly
    if isinstance(profile_or_text, ProfileEvidenceIndex):
        index = profile_or_text
        cand = index.profile.get("candidate", {})
        yoe = cand.get("years_of_experience", 0)
        try:
            meta["years_of_experience"] = int(float(yoe)) if yoe is not None else 0
        except (ValueError, TypeError):
            meta["years_of_experience"] = 0

        meta["is_dict"] = True
        meta["parsed_profile"] = index.profile
        meta["evidence_index"] = index
        meta["raw_text"] = json.dumps(index.profile, ensure_ascii=False)
        bullets = list(index.bullets)
        return bullets, meta

    # 2. Handle ProfileContext directly
    if isinstance(profile_or_text, ProfileContext):
        index = profile_or_text.evidence_index
        cand = index.profile.get("candidate", {})
        yoe = cand.get("years_of_experience", 0)
        try:
            meta["years_of_experience"] = int(float(yoe)) if yoe is not None else 0
        except (ValueError, TypeError):
            meta["years_of_experience"] = 0

        meta["is_dict"] = True
        meta["parsed_profile"] = index.profile
        meta["evidence_index"] = index
        meta["raw_text"] = json.dumps(index.profile, ensure_ascii=False)
        bullets = list(index.bullets)
        return bullets, meta

    # 3. Handle raw dict
    if isinstance(profile_or_text, dict):
        index = build_profile_evidence_index(profile_or_text)
        cand = index.profile.get("candidate", {})
        yoe = cand.get("years_of_experience", 0)
        try:
            meta["years_of_experience"] = int(float(yoe)) if yoe is not None else 0
        except (ValueError, TypeError):
            meta["years_of_experience"] = 0

        meta["is_dict"] = True
        meta["parsed_profile"] = index.profile
        meta["evidence_index"] = index
        meta["raw_text"] = json.dumps(index.profile, ensure_ascii=False)
        bullets = list(index.bullets)
        return bullets, meta

    # 4. Handle string (text, filepath, or json string)
    text_content = str(profile_or_text).strip()
    loaded_json, content = load_json_or_text(text_content)
    if isinstance(loaded_json, (dict, list)):
        return extract_bullets_from_input(loaded_json)
    text_content = content

    # Treat as plain text / markdown / HTML
    meta["raw_text"] = text_content

    # Extract years of experience from text if present
    exp_match = re.search(r"(\d+)\+?\s*(?:years?|年)(?:研发|工作|经验|相关)", text_content, re.IGNORECASE)
    if exp_match:
        meta["years_of_experience"] = int(exp_match.group(1))

    # Split lines and identify bullets
    lines = text_content.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Check bullet prefixes
        if re.match(r"^[-*•·▪▫►✔✓]\s+", stripped) or re.match(r"^\d+[\.\)]\s+", stripped):
            clean_bullet = re.sub(r"^[-*•·▪▫►✔✓\d\.\)]+\s*", "", stripped).strip()
            if clean_bullet:
                bullets.append(clean_bullet)
        elif len(stripped) > 20 and not stripped.startswith("#") and not stripped.endswith(":"):
            bullets.append(stripped)

    return bullets, meta


def is_bullet_quantified(bullet: str) -> bool:
    """Checks whether a single bullet contains quantified metrics."""
    for pattern in QUANTIFIED_PATTERNS:
        if pattern.search(bullet):
            return True
    return False


def find_action_verbs(bullet: str) -> Tuple[List[str], List[str]]:
    """Finds strong action verbs and weak verbs in a bullet."""
    strong_found = []
    weak_found = []

    lower = bullet.lower()

    # English strong verbs
    for verb in STRONG_ACTION_VERBS_EN:
        if re.search(rf"\b{re.escape(verb)}\b", lower):
            strong_found.append(verb)

    # Chinese strong verbs
    for verb in STRONG_ACTION_VERBS_ZH:
        if verb in bullet:
            strong_found.append(verb)

    # English weak verbs
    for verb in WEAK_ACTION_VERBS_EN:
        if re.search(rf"\b{re.escape(verb)}\b", lower):
            weak_found.append(verb)

    # Chinese weak verbs
    for verb in WEAK_ACTION_VERBS_ZH:
        if verb in bullet:
            weak_found.append(verb)

    return strong_found, weak_found


# ---------------------------------------------------------------------------
# ATS Auditor Class (Four-Dimension Scorer)
# ---------------------------------------------------------------------------

class ATSAuditor:
    """
    Four-Dimension ATS Scorer & Verification Engine:
    - Dimension 1: Impact (Quantified bullet ratio, Action verb strength)
    - Dimension 2: ATS Readiness (Standard section headers, Formatting risk audit, Keyword stuffing)
    - Dimension 3: Clarity & Anti-AI (AI buzzword audit, 8-second skim test)
    - Dimension 4: Format & Alignment (Experience years vs page length alignment)
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        # Default dimension weights summing to 1.0 (translating 0-10 dimension scores to 0-100 total)
        self.weights = weights or {
            "impact": 0.30,
            "ats_readiness": 0.30,
            "clarity_anti_ai": 0.20,
            "format_alignment": 0.20
        }

    # -----------------------------------------------------------------------
    # Dimension 1: Impact (0 - 10)
    # -----------------------------------------------------------------------
    def audit_impact(self, bullets: List[str]) -> Dict[str, Any]:
        """
        Dimension 1: Impact (0-10).
        - Quantified bullet ratio (target >= 80%).
        - Action verbs (reward strong verbs, penalize weak verbs like 'Responsible for', '负责').
        """
        if not bullets:
            return {
                "score": 0.0,
                "quantified_ratio": 0.0,
                "quantified_count": 0,
                "total_bullets": 0,
                "aim_met": False,
                "strong_verbs_count": 0,
                "weak_verbs_count": 0,
                "strong_verbs_found": [],
                "weak_verbs_found": [],
                "feedback": ["No bullet points found in resume. Add impact-driven bullets with metrics."]
            }

        quantified_count = 0
        strong_verbs_found: Set[str] = set()
        weak_verbs_found: Set[str] = set()

        for b in bullets:
            if is_bullet_quantified(b):
                quantified_count += 1
            s_verbs, w_verbs = find_action_verbs(b)
            strong_verbs_found.update(s_verbs)
            weak_verbs_found.update(w_verbs)

        quantified_ratio = quantified_count / len(bullets)
        aim_met = quantified_ratio >= 0.80

        # Scoring: Quantified ratio contributes up to 6.0 points
        if quantified_ratio >= 0.80:
            ratio_score = 6.0
        else:
            ratio_score = (quantified_ratio / 0.80) * 6.0

        # Action verbs contribute up to 4.0 points
        # Base verb score starts at 2.0; strong verbs add, weak verbs subtract
        strong_boost = min(2.5, len(strong_verbs_found) * 0.6)
        weak_penalty = len(weak_verbs_found) * 1.0
        verb_score = max(0.0, min(4.0, 2.0 + strong_boost - weak_penalty))

        total_dim1 = min(10.0, max(0.0, ratio_score + verb_score))

        feedback = []
        if not aim_met:
            feedback.append(f"Quantified bullet ratio is {quantified_ratio:.1%} (target >= 80%). Add concrete numbers, percentages, or scale metrics.")
        if weak_verbs_found:
            feedback.append(f"Replace weak verbs {list(weak_verbs_found)} with high-impact action verbs like Built, Architected, Spearheaded, Shipped, Optimized, 主导.")
        if aim_met and not weak_verbs_found:
            feedback.append("Excellent impact metrics and strong action-oriented phrasing.")

        return {
            "score": round(total_dim1, 2),
            "quantified_ratio": round(quantified_ratio, 3),
            "quantified_count": quantified_count,
            "total_bullets": len(bullets),
            "aim_met": aim_met,
            "strong_verbs_count": len(strong_verbs_found),
            "weak_verbs_count": len(weak_verbs_found),
            "strong_verbs_found": sorted(list(strong_verbs_found)),
            "weak_verbs_found": sorted(list(weak_verbs_found)),
            "feedback": feedback
        }

    # -----------------------------------------------------------------------
    # Dimension 2: ATS Readiness (0 - 10)
    # -----------------------------------------------------------------------
    def audit_ats_readiness(self, profile_or_text: Any, raw_text: str) -> Dict[str, Any]:
        """
        Dimension 2: ATS Readiness (0-10).
        - Check standard section names (Experience, Education, Skills, Projects, Summary).
        - Check formatting risks (tables, multi-column text, complex nested blocks, non-standard symbols).
        - Check keyword frequency & detect keyword stuffing.
        """
        detected_sections = []
        missing_sections = []

        is_profile_dict = isinstance(profile_or_text, dict)

        # 1. Section audit
        for standard_sec, aliases in STANDARD_SECTIONS.items():
            found = False
            if is_profile_dict:
                # Check dict keys
                if standard_sec == "Experience" and ("experience" in profile_or_text or "work_experience" in profile_or_text):
                    found = True
                elif standard_sec == "Education" and ("education" in profile_or_text or "degree" in profile_or_text.get("candidate", {}) or "institution" in profile_or_text.get("candidate", {})):
                    found = True
                elif standard_sec == "Skills" and ("skills" in profile_or_text or "competencies" in profile_or_text):
                    found = True
                elif standard_sec == "Projects" and "projects" in profile_or_text:
                    found = True
                elif standard_sec == "Summary" and ("summary" in profile_or_text or "narrative" in profile_or_text):
                    found = True

            if not found:
                # Search raw text for section headers
                for alias in aliases:
                    if re.search(rf"(?:^|\n|#+|[\"'])\s*{re.escape(alias)}\b", raw_text, re.IGNORECASE):
                        found = True
                        break

            if found:
                detected_sections.append(standard_sec)
            else:
                missing_sections.append(standard_sec)

        # Standard sections score: up to 5.0 points
        # 1.0 point per detected section, deduct 0.5 per missing section
        found_count = len(detected_sections)
        missing_count = len(missing_sections)
        section_score = max(0.0, (found_count * 1.0) - (missing_count * 0.5))

        # 2. Formatting risks audit
        formatting_risks_detected = []
        for risk_name, pattern, reason in FORMATTING_RISKS:
            matches = pattern.findall(raw_text)
            if matches:
                formatting_risks_detected.append({
                    "risk": risk_name,
                    "count": len(matches),
                    "reason": reason
                })

        # Formatting penalty: 3.0 base, subtract for risks
        formatting_penalty = len(formatting_risks_detected) * 1.0
        formatting_score = max(0.0, 3.0 - formatting_penalty)

        # 3. Keyword stuffing audit
        # Tokenize words (>2 chars, excluding common stopwords)
        words = re.findall(r"[A-Za-z0-9_\-\+\#]{2,}|[\u4e00-\u9fa5]{2,}", raw_text.lower())
        stopwords = {
            "and", "the", "for", "with", "from", "that", "this", "are", "have", "been",
            "model", "system", "experience", "data", "负责", "基于", "实现", "通过", "进行", "具备"
        }
        filtered_words = [w for w in words if w not in stopwords]
        total_tokens = max(1, len(filtered_words))

        freq_dict: Dict[str, int] = {}
        for w in filtered_words:
            freq_dict[w] = freq_dict.get(w, 0) + 1

        top_keywords = sorted(freq_dict.items(), key=lambda x: x[1], reverse=True)[:10]

        stuffing_warnings = []
        # Flag if any non-stopword keyword density > 5% and frequency >= 6
        for kw, count in top_keywords:
            density = count / total_tokens
            if density > 0.05 and count >= 6:
                stuffing_warnings.append(f"Potential keyword stuffing: '{kw}' appears {count} times ({density:.1%} density).")

        # Check for hidden white-text / 0px font tricks
        if re.search(r"color\s*:\s*(?:white|#fff|#ffffff|rgba\(\s*255\s*,\s*255\s*,\s*255)|font-size\s*:\s*0(?:px)?|display\s*:\s*none", raw_text, re.IGNORECASE):
            stuffing_warnings.append("Critical formatting risk: Hidden text / zero-font styling detected.")

        keyword_stuffing_detected = len(stuffing_warnings) > 0
        keyword_score = 0.0 if keyword_stuffing_detected else 2.0

        total_dim2 = min(10.0, max(0.0, section_score + formatting_score + keyword_score))

        feedback = []
        if missing_sections:
            feedback.append(f"Missing standard ATS section headers: {missing_sections}. Standardize section names to ensure parsing.")
        if formatting_risks_detected:
            for r in formatting_risks_detected:
                feedback.append(f"Formatting risk [{r['risk']}]: {r['reason']}.")
        if keyword_stuffing_detected:
            feedback.extend(stuffing_warnings)
        if not missing_sections and not formatting_risks_detected and not keyword_stuffing_detected:
            feedback.append("ATS readiness is optimal: clean hierarchy, standard section names, and zero formatting risks.")

        return {
            "score": round(total_dim2, 2),
            "detected_sections": detected_sections,
            "missing_sections": missing_sections,
            "formatting_risks": formatting_risks_detected,
            "keyword_stuffing_detected": keyword_stuffing_detected,
            "stuffing_warnings": stuffing_warnings,
            "top_keywords": top_keywords,
            "feedback": feedback
        }

    # -----------------------------------------------------------------------
    # Dimension 3: Clarity & Anti-AI (0 - 10)
    # -----------------------------------------------------------------------
    def audit_clarity_anti_ai(self, bullets: List[str], raw_text: str) -> Dict[str, Any]:
        """
        Dimension 3: Clarity & Anti-AI (0-10).
        - AI buzzwords audit ('results-driven', 'dynamic', 'synergy', '具有深厚底蕴', '全面赋能', etc.).
        - 8-second skim test: bullet length <= 150 chars/2 lines.
        """
        # 1. Buzzword audit
        ai_buzzwords_detected = []
        for phrase in AI_BUZZWORDS_LEXICON:
            if ".*" in phrase:
                matches = re.findall(phrase, raw_text)
                if matches:
                    ai_buzzwords_detected.append(phrase)
            else:
                if phrase.lower() in raw_text.lower():
                    ai_buzzwords_detected.append(phrase)

        # Base AI score (5.0 max, deduct 1.5 per buzzword)
        ai_score = max(0.0, 5.0 - (len(ai_buzzwords_detected) * 1.5))

        # 2. 8-second skim test (bullet length <= 150 chars)
        long_bullets = []
        total_bullets = len(bullets)
        skim_pass_count = 0

        for b in bullets:
            length = len(b.strip())
            if length <= 150:
                skim_pass_count += 1
            else:
                long_bullets.append({
                    "snippet": b[:80] + ("..." if len(b) > 80 else ""),
                    "length": length,
                    "excess": length - 150
                })

        skim_pass_ratio = (skim_pass_count / total_bullets) if total_bullets > 0 else 1.0
        skim_score = skim_pass_ratio * 5.0

        total_dim3 = min(10.0, max(0.0, ai_score + skim_score))

        feedback = []
        if ai_buzzwords_detected:
            feedback.append(f"Detected {len(ai_buzzwords_detected)} AI buzzwords/cliches: {ai_buzzwords_detected}. Replace with specific technical CAR facts.")
        if long_bullets:
            feedback.append(f"{len(long_bullets)} bullet(s) exceeded the 150-char 8-second skim test threshold. Trim redundant phrasing.")
        if not ai_buzzwords_detected and not long_bullets:
            feedback.append("Passed Anti-AI and 8-second skim tests with crisp, punchy technical bullets.")

        return {
            "score": round(total_dim3, 2),
            "ai_buzzwords_detected": ai_buzzwords_detected,
            "buzzword_count": len(ai_buzzwords_detected),
            "skim_pass_ratio": round(skim_pass_ratio, 3),
            "skim_pass_count": skim_pass_count,
            "total_bullets": total_bullets,
            "long_bullets": long_bullets,
            "feedback": feedback
        }

    # -----------------------------------------------------------------------
    # Dimension 4: Format & Alignment (0 - 10)
    # -----------------------------------------------------------------------
    def audit_format_alignment(
        self,
        years_of_experience: int,
        bullets: List[str],
        raw_text: str,
        profile_obj: Any = None,
        explicit_page_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Dimension 4: Format & Alignment (0-10).
        - Experience years vs page length recommendation (<10 years 1 page, senior/exec 2 pages).
        - Contact info completeness & consistency.
        """
        # Recommendation rule: < 10 years -> 1 page, >= 10 years -> 2 pages
        recommended_pages = 1 if years_of_experience < 10 else 2

        # Estimate actual page count if not explicitly provided
        if explicit_page_count is not None:
            estimated_pages = explicit_page_count
        else:
            if isinstance(profile_obj, dict):
                total_exp = len(profile_obj.get("experience", []))
                total_proj = len(profile_obj.get("projects", []))
                total_hl = sum(len(e.get("highlights", [])) for e in profile_obj.get("experience", []))
                if total_exp <= 2 and total_hl <= 8 and total_proj <= 2:
                    estimated_pages = 1
                elif total_exp <= 4 and total_hl <= 16:
                    estimated_pages = 2
                else:
                    estimated_pages = 3
            else:
                char_count = len(raw_text.strip())
                if char_count <= 2500 and len(bullets) <= 10:
                    estimated_pages = 1
                elif char_count <= 5000 or len(bullets) <= 18:
                    estimated_pages = 2
                else:
                    estimated_pages = 3

        # Scoring page length alignment
        page_fit = True
        page_score = 7.0
        feedback = []

        if recommended_pages == 1:
            if estimated_pages == 1:
                page_score = 7.0
                feedback.append("Resume page length (1 page) perfectly aligns with <10 years experience.")
            elif estimated_pages == 2:
                page_score = 4.0
                page_fit = False
                feedback.append("Resume estimated at 2 pages for <10 years experience. Recommendation: condense to 1 punchy page.")
            else:
                page_score = 1.5
                page_fit = False
                feedback.append(f"Resume estimated at {estimated_pages} pages. Severe length inflation for <10 years experience.")
        else:
            # >= 10 years senior/executive
            if estimated_pages in (1, 2):
                page_score = 7.0
                feedback.append(f"Resume page length ({estimated_pages} pages) fits senior/exec profile recommendation (1-2 pages).")
            else:
                page_score = 3.5
                page_fit = False
                feedback.append(f"Resume estimated at {estimated_pages} pages (>2 pages). Trim older or low-impact positions.")

        # Check contact completeness (Email, Phone/Contact)
        has_email = bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text))
        has_phone = bool(re.search(r"\+?\d[\d\s-]{7,}\d", raw_text))

        contact_score = 3.0
        if not has_email:
            contact_score -= 1.5
            feedback.append("Missing candidate contact email.")
        if not has_phone:
            contact_score -= 1.5
            feedback.append("Missing candidate contact telephone number.")

        total_dim4 = min(10.0, max(0.0, page_score + contact_score))

        return {
            "score": round(total_dim4, 2),
            "experience_years": years_of_experience,
            "recommended_pages": recommended_pages,
            "estimated_pages": estimated_pages,
            "page_fit": page_fit,
            "has_email": has_email,
            "has_phone": has_phone,
            "feedback": feedback
        }

    # -----------------------------------------------------------------------
    # Comprehensive Audit
    # -----------------------------------------------------------------------
    def audit(
        self,
        profile_or_text: Any,
        jd_decoded_or_text: Any = None,
        target_tag: Optional[str] = None,
        page_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes four-dimension audit and calculates weighted score + verdict.
        """
        bullets, meta = extract_bullets_from_input(profile_or_text)
        active_input = meta["parsed_profile"] if meta["parsed_profile"] is not None else profile_or_text

        # If target_tag is specified and input is a profile dict, filter first
        # Note: Filtering produces an intentional materialized derived dict view with a fresh index
        if target_tag and isinstance(active_input, dict):
            active_input = filter_profile_by_visibility(active_input, target_tag)
            bullets, meta = extract_bullets_from_input(active_input)

        evidence_index = meta.get("evidence_index")
        raw_text = meta["raw_text"]
        years_exp = meta["years_of_experience"]

        # Run 4 Dimensions
        dim1 = self.audit_impact(bullets)
        dim2 = self.audit_ats_readiness(active_input, raw_text)
        dim3 = self.audit_clarity_anti_ai(bullets, raw_text)
        dim4 = self.audit_format_alignment(years_exp, bullets, raw_text, profile_obj=active_input, explicit_page_count=page_count)

        # Weighted calculation (0 - 100)
        w = self.weights
        overall_score = (
            dim1["score"] * w["impact"] +
            dim2["score"] * w["ats_readiness"] +
            dim3["score"] * w["clarity_anti_ai"] +
            dim4["score"] * w["format_alignment"]
        ) * 10.0
        overall_score = round(min(100.0, max(0.0, overall_score)), 1)

        # Critical Checks
        critical_issues = []
        # 1. Quantified bullet ratio critically low
        if dim1["total_bullets"] > 0 and dim1["quantified_ratio"] < 0.30:
            critical_issues.append("Critically low quantified bullet ratio (<30%). Immediate ATS rejection risk.")
        # 2. Critical sections missing
        critical_sections = {"Experience", "Education", "Skills"}
        missing_crit = critical_sections.intersection(set(dim2["missing_sections"]))
        if missing_crit:
            critical_issues.append(f"Missing core resume sections: {list(missing_crit)}.")
        # 3. Severe keyword stuffing
        if dim2["keyword_stuffing_detected"]:
            critical_issues.append("Keyword stuffing or hidden text detected.")
        # 4. Excessive AI buzzwords
        if dim3["buzzword_count"] >= 4:
            critical_issues.append(f"High AI slop concentration ({dim3['buzzword_count']} buzzwords).")
        # 5. Severe page mismatch (>2 pages for <10 years)
        if dim4["recommended_pages"] == 1 and dim4["estimated_pages"] >= 3:
            critical_issues.append(f"Resume page length ({dim4['estimated_pages']} pages) severely exceeds 1-page rule.")

        # Verdict logic
        if overall_score >= 75.0 and len(critical_issues) == 0:
            verdict = "READY_TO_SEND"
        else:
            verdict = "NEEDS_REVISION"

        # Three-State Skill Ledger (reusing evidence_index to avoid duplicate index construction)
        skill_ledger = generate_skill_ledger(active_input, jd_decoded_or_text, evidence_index=evidence_index)

        # Actionable recommendations
        recommendations = []
        recommendations.extend(dim1["feedback"])
        recommendations.extend(dim2["feedback"])
        recommendations.extend(dim3["feedback"])
        recommendations.extend(dim4["feedback"])
        for issue in critical_issues:
            recommendations.insert(0, f"[CRITICAL FIX] {issue}")

        return {
            "overall_score": overall_score,
            "verdict": verdict,
            "critical_issues": critical_issues,
            "dimensions": {
                "impact": dim1,
                "ats_readiness": dim2,
                "clarity_anti_ai": dim3,
                "format_alignment": dim4
            },
            "skill_ledger": skill_ledger,
            "recommendations": recommendations,
            "candidate_meta": {
                "years_of_experience": years_exp,
                "total_bullets_analyzed": len(bullets),
                "visibility_tag_applied": target_tag
            }
        }


# ---------------------------------------------------------------------------
# Three-State Skill Ledger
# ---------------------------------------------------------------------------

def extract_skills_from_jd(jd_decoded_or_text: Any) -> List[str]:
    """Extracts required and preferred skill keywords from a JD object or text."""
    if not jd_decoded_or_text:
        return []

    # If file path
    if isinstance(jd_decoded_or_text, str) and os.path.exists(jd_decoded_or_text):
        try:
            with open(jd_decoded_or_text, "r", encoding="utf-8") as f:
                jd_decoded_or_text = f.read()
        except Exception:
            pass

    skills: Set[str] = set()

    if isinstance(jd_decoded_or_text, dict):
        # Extract from requirements
        reqs = jd_decoded_or_text.get("requirements", {})
        for item in reqs.get("must_haves", []) + reqs.get("nice_haves", []):
            extracted = re.findall(r"[A-Za-z0-9_\-\+\#\.\/]{2,}|[\u4e00-\u9fa5]{2,6}", item)
            for token in extracted:
                if len(token) >= 2 and not re.match(r"^\d+$", token):
                    skills.add(token)

        # Extract from Layer 2
        l2 = jd_decoded_or_text.get("layers", {}).get("layer_2", {})
        for text in [l2.get("jd_text_zh", ""), l2.get("jd_text_en", "")]:
            tech_matches = re.findall(r"\b(?:Transformer|MoE|MLA|Megatron-LM|DeepSpeed|vLLM|Triton|CUDA|C\+\+|Python|PyTorch|GRPO|PPO|DPO|PagedAttention|FP8|MCP|LangGraph|GraphRAG|FlashAttention|Kubernetes|K8s|Docker|NCCL|Slurm)\b", text, re.IGNORECASE)
            skills.update(tech_matches)

    elif isinstance(jd_decoded_or_text, str):
        # Extract prominent technical entities
        tech_matches = re.findall(r"\b(?:Transformer|MoE|MLA|Megatron-LM|DeepSpeed|vLLM|Triton|CUDA|C\+\+|Python|PyTorch|GRPO|PPO|DPO|PagedAttention|FP8|MCP|LangGraph|GraphRAG|FlashAttention|Kubernetes|K8s|Docker|NCCL|Slurm|Go|Rust|Java|AWS|Ray|TensorRT-LLM)\b", jd_decoded_or_text, re.IGNORECASE)
        skills.update(tech_matches)

    return sorted(list(skills))


def extract_candidate_skills(
    profile_data: Any,
    evidence_index: Optional[ProfileEvidenceIndex] = None,
) -> Tuple[Set[str], List[str]]:
    """
    Extracts all candidate competencies and bullet texts for matching.
    Supports ProfileContext, ProfileEvidenceIndex, dict, or text, reusing evidence_index when provided.
    Returns: (competencies_set, verified_bullets)
    """
    competencies: Set[str] = set()
    verified_bullets: List[str] = []

    # 1. Reuse existing evidence_index if provided
    index: Optional[ProfileEvidenceIndex] = evidence_index

    # 2. Resolve index if not provided directly
    if index is None:
        if isinstance(profile_data, ProfileEvidenceIndex):
            index = profile_data
        elif isinstance(profile_data, ProfileContext):
            index = profile_data.evidence_index
        elif isinstance(profile_data, dict):
            index = build_profile_evidence_index(profile_data)
        elif isinstance(profile_data, (str, os.PathLike)):
            loaded, _ = load_json_or_text(str(profile_data))
            if isinstance(loaded, dict):
                index = build_profile_evidence_index(loaded)

    if index is not None:
        for item in index.skills:
            competencies.add(item.strip())
            sub_tokens = re.findall(r"\b[A-Za-z0-9_\-\+\#]{2,}\b", item)
            competencies.update(sub_tokens)

        # Bullets and project names for evidence matching
        verified_bullets.extend(index.bullets)
        for proj in index.profile.get("projects", []):
            if isinstance(proj, dict) and proj.get("name") and proj["name"] not in verified_bullets:
                verified_bullets.append(proj["name"])

    elif isinstance(profile_data, str):
        lines = profile_data.splitlines()
        for line in lines:
            if re.match(r"^[-*•·]\s+", line.strip()):
                verified_bullets.append(line.strip())

    return competencies, verified_bullets


def generate_skill_defense(skill: str) -> str:
    """Generates interview defense strategy for honest gap without fabrication."""
    skill_lower = skill.lower()
    for key, defense in DEFENSE_GUIDE_TEMPLATES.items():
        if key in skill_lower:
            return defense
    return DEFENSE_GUIDE_TEMPLATES["default"]


def generate_skill_ledger(
    profile_data: Any,
    jd_decoded_or_text: Any,
    skills_to_evaluate: Optional[List[str]] = None,
    evidence_index: Optional[ProfileEvidenceIndex] = None,
) -> Dict[str, Any]:
    """
    Categorizes skills against JD requirements into:
    - 'present': Skills possessed and backed by verified experience bullets.
    - 'missing': Skills possessed in competencies but not highlighted in bullets (suggest adding).
    - 'unsupported_gap': Skills required by JD but absent in candidate profile.
      CRITICAL: Strictly flag as honest gaps with interview defense advice, never fabricate or hallucinate!
    """
    competencies, verified_bullets = extract_candidate_skills(profile_data, evidence_index=evidence_index)

    # Determine skills to evaluate
    if skills_to_evaluate:
        eval_skills = skills_to_evaluate
    else:
        eval_skills = extract_skills_from_jd(jd_decoded_or_text)
        if not eval_skills and isinstance(profile_data, dict):
            # Fallback to key competencies of candidate if no JD provided
            eval_skills = list(competencies)[:15]

    present: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    unsupported_gap: List[Dict[str, Any]] = []

    # Pre-normalize competencies
    norm_competencies = {c.lower(): c for c in competencies}

    for skill in eval_skills:
        skill_clean = skill.strip()
        if not skill_clean:
            continue
        skill_lower = skill_clean.lower()

        # Check if candidate possesses skill
        possessed = False
        matched_comp_name = skill_clean

        if skill_lower in norm_competencies:
            possessed = True
            matched_comp_name = norm_competencies[skill_lower]
        else:
            # Substring match in competencies
            for c_lower, c_orig in norm_competencies.items():
                if skill_lower in c_lower or c_lower in skill_lower:
                    possessed = True
                    matched_comp_name = c_orig
                    break

        if possessed:
            # Check if backed by verified experience bullets
            backed = False
            evidence_bullets = []

            for b in verified_bullets:
                if re.search(rf"\b{re.escape(skill_lower)}\b", b.lower()) or skill_clean in b:
                    backed = True
                    evidence_bullets.append(b[:120] + ("..." if len(b) > 120 else ""))

            if backed:
                present.append({
                    "skill": skill_clean,
                    "status": "present",
                    "evidence_count": len(evidence_bullets),
                    "sample_evidence": evidence_bullets[:2],
                    "recommendation": "Verified by concrete project and experience bullet metrics."
                })
            else:
                missing.append({
                    "skill": skill_clean,
                    "status": "missing",
                    "competency_declaration": matched_comp_name,
                    "recommendation": f"Skill listed in competencies ('{matched_comp_name}') but lacks quantified evidence in experience bullets. Suggest adding a bullet demonstrating real-world impact with {skill_clean}."
                })
        else:
            # Skill required by JD but absent in candidate profile
            defense_advice = generate_skill_defense(skill_clean)
            unsupported_gap.append({
                "skill": skill_clean,
                "status": "unsupported_gap",
                "interview_defense": defense_advice,
                "anti_hallucination_rule": "CRITICAL: Strictly flag as honest gap. Never fabricate or hallucinate experience! Articulate foundational principles and fast ramp-up."
            })

    total = len(eval_skills)
    coverage = round((len(present) / total), 2) if total > 0 else 1.0

    return {
        "present": present,
        "missing": missing,
        "unsupported_gap": unsupported_gap,
        "summary": {
            "present_count": len(present),
            "missing_count": len(missing),
            "unsupported_gap_count": len(unsupported_gap),
            "total_evaluated": total,
            "coverage_ratio": coverage
        }
    }


# ---------------------------------------------------------------------------
# Visibility System
# ---------------------------------------------------------------------------

def filter_profile_by_visibility(
    profile: Dict[str, Any],
    target_tag: Optional[str] = None
) -> Dict[str, Any]:
    """
    Filters experiences and projects by visibility tag (e.g. 'always', 'ai_pretrain', 'cluster_infra', 'agentic_systems').
    Items with 'always' or matching the requested tag are preserved.
    """
    if not isinstance(profile, dict):
        return profile

    profile_copy = copy.deepcopy(profile)

    # If no target tag or wildcard, keep everything
    if not target_tag or target_tag.lower() in ("*", "all", "all_tags"):
        return profile_copy

    target_tag_lower = target_tag.lower()

    # 1. Filter experiences
    filtered_experience = []
    for exp in profile_copy.get("experience", []):
        exp_vis = exp.get("visibility", ["always"])
        if isinstance(exp_vis, str):
            exp_vis = [exp_vis]
        exp_vis_lower = [str(v).lower() for v in exp_vis]

        # Check if experience matches tag
        if "always" in exp_vis_lower or target_tag_lower in exp_vis_lower:
            # Filter individual highlights if they declare visibility
            if "highlights" in exp and isinstance(exp["highlights"], list):
                filtered_highlights = []
                for h in exp["highlights"]:
                    if isinstance(h, dict) and "visibility" in h:
                        h_vis = h.get("visibility", ["always"])
                        if isinstance(h_vis, str):
                            h_vis = [h_vis]
                        h_vis_lower = [str(v).lower() for v in h_vis]
                        if "always" in h_vis_lower or target_tag_lower in h_vis_lower:
                            filtered_highlights.append(h)
                    else:
                        filtered_highlights.append(h)
                exp["highlights"] = filtered_highlights
            filtered_experience.append(exp)

    profile_copy["experience"] = filtered_experience

    # 2. Filter projects
    filtered_projects = []
    for proj in profile_copy.get("projects", []):
        proj_vis = proj.get("visibility", ["always"])
        if isinstance(proj_vis, str):
            proj_vis = [proj_vis]
        proj_vis_lower = [str(v).lower() for v in proj_vis]

        if "always" in proj_vis_lower or target_tag_lower in proj_vis_lower:
            filtered_projects.append(proj)

    profile_copy["projects"] = filtered_projects

    return profile_copy


# ---------------------------------------------------------------------------
# Primary Entry Point
# ---------------------------------------------------------------------------

def audit_resume_ats(
    profile_or_text: Any,
    jd_decoded_or_text: Any = None,
    target_tag: Optional[str] = None,
    page_count: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Primary entry point for ATS audit in OfferGet.
    """
    auditor = ATSAuditor(weights=weights)
    return auditor.audit(
        profile_or_text=profile_or_text,
        jd_decoded_or_text=jd_decoded_or_text,
        target_tag=target_tag,
        page_count=page_count
    )
