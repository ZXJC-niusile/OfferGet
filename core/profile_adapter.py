"""Shared candidate-profile evidence extraction for career review flows.

The project historically had several small, incompatible profile readers. This
module stays deterministic and read-only: it produces ephemeral claim records
with source paths so recommendations can be grounded without inventing resume
content or persisting a second profile schema.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Set, Tuple


@dataclass(frozen=True)
class EvidenceClaim:
    """One candidate fact with a traceable location in the source profile.

    The first five fields are the original compatibility contract.  The
    optional fields make the claim usable as an auditable evidence reference
    without guessing missing role, scope, metric, or attribution facts.
    """

    claim_id: str
    source_path: str
    text: str
    kind: str
    direct: bool = False
    source_kind: str = "profile"
    verification: str = "unknown"
    role_scope: str = ""
    metric_context: str = ""
    attribution: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProfileEvidenceIndex:
    profile: Dict[str, Any]
    claims: Tuple[EvidenceClaim, ...]
    skills: Tuple[str, ...]
    bullets: Tuple[str, ...]
    metric_anchors: Tuple[Dict[str, Any], ...]
    claim_by_id: Dict[str, EvidenceClaim]
    source_paths: Tuple[str, ...]
    input_quality: Dict[str, Any]


from core.registry import AliasRegistry

# Deterministic aliases are centrally governed in AliasRegistry.
# Maintained for backward compatibility.
ALIASES: Dict[str, set[str]] = AliasRegistry.all_aliases()



def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return ""


def _append_claim(
    claims: List[EvidenceClaim],
    claim_id: str,
    path: str,
    value: Any,
    kind: str,
    direct: bool,
    *,
    verification: str = "unknown",
    role_scope: str = "",
    metric_context: str = "",
    attribution: str = "",
) -> None:
    text = _text(value)
    if text:
        claims.append(EvidenceClaim(
            claim_id, path, text, kind, direct,
            verification=verification,
            role_scope=role_scope,
            metric_context=metric_context,
            attribution=attribution,
        ))


def iter_profile_claims(profile: Dict[str, Any]) -> List[EvidenceClaim]:
    """Extract supported profile facts without changing the input object."""
    if not isinstance(profile, dict):
        return []

    claims: List[EvidenceClaim] = []
    candidate = profile.get("candidate") if isinstance(profile.get("candidate"), dict) else {}
    for key in ("name", "degree", "institution", "major", "title_zh", "title_en", "years_of_experience"):
        if key in candidate:
            _append_claim(claims, f"candidate.{key}", f"candidate.{key}", candidate.get(key), "candidate", True)

    competencies = profile.get("competencies")
    if isinstance(competencies, dict):
        for group, values in competencies.items():
            if isinstance(values, list):
                for idx, value in enumerate(values):
                    _append_claim(claims, f"competencies.{group}[{idx}]", f"competencies.{group}[{idx}]", value, "competency", False)
            elif values:
                _append_claim(claims, f"competencies.{group}", f"competencies.{group}", values, "competency", False)

    skills = profile.get("skills")
    if isinstance(skills, list):
        for idx, value in enumerate(skills):
            _append_claim(claims, f"skills[{idx}]", f"skills[{idx}]", value, "competency", False)
    elif isinstance(skills, dict):
        for group, values in skills.items():
            if isinstance(values, list):
                for idx, value in enumerate(values):
                    _append_claim(claims, f"skills.{group}[{idx}]", f"skills.{group}[{idx}]", value, "competency", False)

    experiences = profile.get("experience")
    if isinstance(experiences, list):
        for exp_idx, experience in enumerate(experiences):
            if not isinstance(experience, dict):
                continue
            _append_claim(claims, f"experience[{exp_idx}].role", f"experience[{exp_idx}].role", experience.get("role"), "experience_metadata", True)
            highlights = experience.get("highlights", [])
            if not isinstance(highlights, list):
                continue
            for high_idx, highlight in enumerate(highlights):
                if isinstance(highlight, dict):
                    claim_id = str(highlight.get("claim_id") or f"experience[{exp_idx}].highlights[{high_idx}]")
                    verification = "verified" if highlight.get("verified_metrics") else "claimed"
                    role_scope = _text(highlight.get("role_scope") or experience.get("role_scope") or experience.get("role"))
                    metric_context = _text(highlight.get("verified_metrics"))
                    attribution = _text(highlight.get("attribution"))
                    for lang in ("claim_zh", "claim_en"):
                        if highlight.get(lang):
                            _append_claim(
                                claims,
                                claim_id,
                                f"experience[{exp_idx}].highlights[{high_idx}].{lang}",
                                highlight.get(lang),
                                "experience",
                                True,
                                verification=verification,
                                role_scope=role_scope,
                                metric_context=metric_context,
                                attribution=attribution,
                            )
                else:
                    _append_claim(claims, f"experience[{exp_idx}].highlights[{high_idx}]", f"experience[{exp_idx}].highlights[{high_idx}]", highlight, "experience", True, verification="claimed")

    projects = profile.get("projects")
    if isinstance(projects, list):
        for proj_idx, project in enumerate(projects):
            if not isinstance(project, dict):
                continue
            prefix = f"projects[{proj_idx}]"
            _append_claim(claims, f"{prefix}.name", f"{prefix}.name", project.get("name"), "project_metadata", True)
            project_verification = "verified" if project.get("verified") else "claimed"
            project_scope = _text(project.get("role_scope") or project.get("role"))
            for key in ("description", "description_zh", "description_en", "role"):
                if project.get(key):
                    _append_claim(
                        claims,
                        f"{prefix}.{key}",
                        f"{prefix}.{key}",
                        project.get(key),
                        "project",
                        True,
                        verification=project_verification,
                        role_scope=project_scope,
                    )
            bullets = project.get("bullets")
            if isinstance(bullets, list):
                for bullet_idx, bullet in enumerate(bullets):
                    if isinstance(bullet, dict):
                        bullet_text = bullet.get("text") or bullet.get("claim_zh") or bullet.get("claim_en")
                        bullet_verification = "verified" if bullet.get("verified_metrics") else project_verification
                    else:
                        bullet_text = bullet
                        bullet_verification = project_verification
                    _append_claim(
                        claims,
                        f"{prefix}.bullets[{bullet_idx}]",
                        f"{prefix}.bullets[{bullet_idx}]",
                        bullet_text,
                        "project",
                        True,
                        verification=bullet_verification,
                        role_scope=project_scope,
                    )

    publications = profile.get("publications")
    if isinstance(publications, list):
        for pub_idx, publication in enumerate(publications):
            if not isinstance(publication, dict):
                continue
            prefix = f"publications[{pub_idx}]"
            for key in ("title", "conference", "venue", "highlight"):
                if publication.get(key):
                    _append_claim(claims, f"{prefix}.{key}", f"{prefix}.{key}", publication.get(key), "publication", True)

    return claims


def canonical_terms(term: str) -> set[str]:
    """Return deterministic lower-case spellings for a requirement."""
    normalized = _text(term).lower()
    if not normalized:
        return set()
    return AliasRegistry.get_canonical_terms(normalized)


def claim_matches(term: str, claim_text: str) -> bool:
    """Match a requirement without fuzzy substring guesses."""
    return AliasRegistry.claim_matches(term, claim_text)



def find_evidence(term: str, claims: Iterable[EvidenceClaim]) -> List[EvidenceClaim]:
    """Return direct and declared evidence, with direct evidence first."""
    matches = [claim for claim in claims if claim_matches(term, claim.text)]
    return sorted(matches, key=lambda claim: (not claim.direct, claim.source_path))


def claim_ref(claim: EvidenceClaim) -> Dict[str, str]:
    return {
        "source": claim.source_kind,
        "claim_id": claim.claim_id,
        "source_path": claim.source_path,
        "excerpt": claim.text,
        "verification": claim.verification,
        "role_scope": claim.role_scope,
        "metric_context": claim.metric_context,
        "attribution": claim.attribution,
    }


def extract_education_grid(cand: Dict[str, Any]) -> List[List[str]]:
    """Extracts a normalized 2D grid of education items for column-aligned rendering without vertical pipes."""
    raw_grid = cand.get("education_grid") or cand.get("education_rows")
    if raw_grid and isinstance(raw_grid, list):
        rows: List[List[str]] = []
        for item in raw_grid:
            if isinstance(item, (list, tuple)):
                cells = [str(c).strip() for c in item if str(c).strip()]
                if cells:
                    rows.append(cells)
            elif isinstance(item, str):
                item_str = item.strip()
                if not item_str:
                    continue
                if "|" in item_str or "｜" in item_str:
                    cells = [s.strip() for s in re.split(r"\s*[｜|]\s*", item_str) if s.strip()]
                elif "\t" in item_str:
                    cells = [s.strip() for s in item_str.split("\t") if s.strip()]
                elif "  " in item_str:
                    cells = [s.strip() for s in re.split(r"\s{2,}", item_str) if s.strip()]
                else:
                    cells = [item_str]
                if cells:
                    rows.append(cells)
        if rows:
            return rows

    # Fallback to badges
    badges = [str(b).strip() for b in cand.get("education_badges", []) if str(b).strip()]
    if not badges:
        return []
    if len(badges) <= 3:
        return [badges]
    if len(badges) == 4:
        return [badges[:2], badges[2:]]
    return [badges[:3], badges[3:]]


def group_education_badges_into_rows(badges: Iterable[str]) -> List[str]:
    """Groups badge items into compact rows to conserve vertical resume space."""
    grid = extract_education_grid({"education_badges": list(badges)})
    return ["    ".join(r) for r in grid]


def normalize_candidate_profile(raw_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes candidate profile into the standard SSOT schema.

    Supports both full standard profiles (Track 1) and minimal/flat profiles (Track 2).
    Guarantees idempotence, copy-protection, and non-hallucination of missing fields.
    """
    if not isinstance(raw_profile, dict):
        raise TypeError(f"Expected dict for profile, got {type(raw_profile)}")

    # Deep copy ensures the caller's raw_profile dict is never mutated
    raw_profile_copy = copy.deepcopy(raw_profile)

    # Case A: Profile is already structured with standard top-level 'candidate'
    if "candidate" in raw_profile_copy and isinstance(raw_profile_copy["candidate"], dict):
        cand = dict(raw_profile_copy["candidate"])
        grid = extract_education_grid(cand)
        cand["education_grid"] = grid
        cand["education_rows"] = grid

        edu_badges = list(cand.get("education_badges", []))
        if not edu_badges:
            for r in grid:
                edu_badges.extend(r)
        cand["education_badges"] = edu_badges

        if "degree" in cand and isinstance(cand["degree"], str):
            cand["degree"] = re.sub(r"\s*[｜|·]\s*", "  ", cand["degree"]).strip()

        if "school" not in cand and "institution" in cand:
            cand["school"] = cand["institution"]
        if "title" not in cand:
            cand["title"] = cand.get("title_zh") or cand.get("title_en") or ""
        elif cand["title"] is None:
            cand["title"] = ""
        if "reserve_photo" not in cand:
            cand["reserve_photo"] = True

        norm_exp = []
        for e in raw_profile_copy.get("experience", []):
            if not isinstance(e, dict):
                continue
            e_copy = dict(e)
            org = e_copy.get("org") or e_copy.get("company") or e_copy.get("organization", "")
            role = e_copy.get("role") or e_copy.get("title", "")
            time_str = e_copy.get("time") or e_copy.get("period", "")
            bullets = list(e_copy.get("bullets", []))
            if not bullets and e_copy.get("highlights"):
                for h in e_copy["highlights"]:
                    if isinstance(h, dict):
                        txt = h.get("claim_zh") or h.get("claim_en") or h.get("text") or ""
                    else:
                        txt = str(h)
                    if txt and txt not in bullets:
                        bullets.append(txt)
            e_copy["org"] = org
            e_copy["company"] = org
            e_copy["role"] = role
            e_copy["time"] = time_str
            e_copy["period"] = time_str
            e_copy["bullets"] = bullets
            norm_exp.append(e_copy)

        norm_proj = []
        for p in raw_profile_copy.get("projects", []):
            if not isinstance(p, dict):
                continue
            p_copy = dict(p)
            p_name = p_copy.get("name") or p_copy.get("title") or "校园经历"
            p_role = p_copy.get("role", "")
            time_str = p_copy.get("time") or p_copy.get("period", "")
            bullets = list(p_copy.get("bullets", []))
            if not bullets:
                desc = p_copy.get("description_zh") or p_copy.get("description", "")
                if desc:
                    bullets.append(desc)
            p_copy["name"] = p_name
            p_copy["role"] = p_role
            p_copy["time"] = time_str
            p_copy["period"] = time_str
            p_copy["bullets"] = bullets
            norm_proj.append(p_copy)

        return {
            "candidate": cand,
            "competencies": raw_profile_copy.get("competencies", {}),
            "experience": norm_exp,
            "projects": norm_proj,
            "publications": raw_profile_copy.get("publications", []),
            "narrative": raw_profile_copy.get("narrative", {}),
        }

    # Case B: Minimal / Flat profile format (Track 2 / Career Review input)
    cand_name = raw_profile_copy.get("name") or raw_profile_copy.get("candidate_name") or "候选人"
    # Never hallucinate default title to "运营岗"; if not provided, default to ""
    title = raw_profile_copy.get("intent") or raw_profile_copy.get("target_role") or raw_profile_copy.get("title") or ""
    phone = raw_profile_copy.get("phone", "")
    email = raw_profile_copy.get("email", "")
    location = raw_profile_copy.get("city") or raw_profile_copy.get("location", "")

    edu = raw_profile_copy.get("education", {})
    if not isinstance(edu, dict):
        edu = {}
    school = edu.get("school") or edu.get("institution", "")
    major = edu.get("major", "")
    degree = edu.get("degree") or edu.get("education_level", "")
    edu_time = edu.get("time") or edu.get("period", "")

    grid = extract_education_grid(edu)
    edu_badges = list(edu.get("education_badges", []))
    if not edu_badges:
        for r in grid:
            edu_badges.extend(r)

    # Experience normalization
    raw_exp = raw_profile_copy.get("experience") or raw_profile_copy.get("internships", [])
    norm_exp = []
    for e in raw_exp:
        if not isinstance(e, dict):
            continue
        e_copy = dict(e)
        org = e_copy.get("company") or e_copy.get("org") or e_copy.get("organization", "")
        role = e_copy.get("role") or e_copy.get("title", "")
        time_str = e_copy.get("time") or e_copy.get("period", "")
        bullets = list(e_copy.get("bullets", []))
        if not bullets and e_copy.get("highlights"):
            for h in e_copy["highlights"]:
                if isinstance(h, dict):
                    txt = h.get("claim_zh") or h.get("claim_en") or h.get("text") or ""
                else:
                    txt = str(h)
                if txt and txt not in bullets:
                    bullets.append(txt)
        e_copy["org"] = org
        e_copy["company"] = org
        e_copy["role"] = role
        e_copy["time"] = time_str
        e_copy["period"] = time_str
        e_copy["bullets"] = bullets
        norm_exp.append(e_copy)

    # Projects / Campus normalization
    raw_proj = raw_profile_copy.get("projects") or raw_profile_copy.get("campus_experience", [])
    norm_proj = []
    for p in raw_proj:
        if not isinstance(p, dict):
            continue
        p_copy = dict(p)
        p_name = p_copy.get("name") or p_copy.get("title") or "校园经历"
        p_role = p_copy.get("role", "")
        time_str = p_copy.get("time") or p_copy.get("period", "")
        bullets = list(p_copy.get("bullets", []))
        if not bullets:
            desc = p_copy.get("description_zh") or p_copy.get("description", "")
            if desc:
                bullets.append(desc)
        p_copy["name"] = p_name
        p_copy["role"] = p_role
        p_copy["time"] = time_str
        p_copy["period"] = time_str
        p_copy["bullets"] = bullets
        norm_proj.append(p_copy)

    # Competencies normalization
    competencies = raw_profile_copy.get("competencies") or raw_profile_copy.get("skills", {})

    clean_degree = f"{major}  {degree}" if major and degree else (degree or major)
    clean_degree = re.sub(r"\s*[｜|·]\s*", "  ", clean_degree).strip()

    cand_dict: Dict[str, Any] = {
        "name": cand_name,
        "title": title,
        "phone": phone,
        "email": email,
        "location": location,
        "school": school,
        "major": major,
        "degree": clean_degree,
        "edu_time": edu_time,
        "education_badges": edu_badges,
        "education_rows": grid,
        "education_grid": grid,
        "reserve_photo": True,
    }
    yoe = raw_profile_copy.get("years_of_experience")
    if yoe is None:
        yoe = raw_profile_copy.get("experience_years")
    if yoe is not None:
        cand_dict["years_of_experience"] = yoe

    return {
        "candidate": cand_dict,
        "competencies": competencies,
        "experience": norm_exp,
        "projects": norm_proj,
        "publications": raw_profile_copy.get("publications", []),
        "narrative": raw_profile_copy.get("narrative", {}),
    }


def build_profile_evidence_index(raw_profile: Dict[str, Any]) -> ProfileEvidenceIndex:
    """Builds an immutable, single-source-of-truth evidence index from a candidate profile."""
    if not isinstance(raw_profile, dict):
        raise TypeError(f"Expected dict for profile, got {type(raw_profile)}")

    # 1. Normalize profile (copy-protected and idempotent)
    profile = normalize_candidate_profile(raw_profile)

    # 2. Extract claims via canonical iter_profile_claims
    extracted_claims = iter_profile_claims(profile)
    claims_tuple = tuple(extracted_claims)

    # 3. Build claim_by_id map and source_paths tuple
    claim_by_id: Dict[str, EvidenceClaim] = {}
    for c in claims_tuple:
        if c.claim_id not in claim_by_id:
            claim_by_id[c.claim_id] = c
    source_paths = tuple(c.source_path for c in claims_tuple)

    # 4. Extract skills (deduplicated, order-preserving)
    skills_list: List[str] = []
    seen_skills: Set[str] = set()

    def _add_skill(s: Any) -> None:
        if not s:
            return
        s_str = str(s).strip()
        if s_str and s_str not in seen_skills:
            seen_skills.add(s_str)
            skills_list.append(s_str)

    # From competencies
    comp = profile.get("competencies")
    if isinstance(comp, dict):
        for vals in comp.values():
            if isinstance(vals, list):
                for v in vals:
                    _add_skill(v)
            elif vals:
                _add_skill(vals)
    elif isinstance(comp, list):
        for v in comp:
            _add_skill(v)

    # From skills
    sk = profile.get("skills")
    if isinstance(sk, list):
        for v in sk:
            _add_skill(v)
    elif isinstance(sk, dict):
        for vals in sk.values():
            if isinstance(vals, list):
                for v in vals:
                    _add_skill(v)
            elif vals:
                _add_skill(vals)

    skills_tuple = tuple(skills_list)

    # 5. Extract bullets (narrative summaries, experience highlights/bullets, project descriptions/bullets)
    bullets_list: List[str] = []
    seen_bullets: Set[str] = set()

    def _add_bullet(b: Any) -> None:
        if not b:
            return
        b_str = str(b).strip()
        if b_str and b_str not in seen_bullets:
            seen_bullets.add(b_str)
            bullets_list.append(b_str)

    narrative = profile.get("narrative")
    if isinstance(narrative, dict):
        for k in ("summary_zh", "summary_en"):
            _add_bullet(narrative.get(k))

    for exp in profile.get("experience", []):
        if not isinstance(exp, dict):
            continue
        for b in exp.get("bullets", []):
            _add_bullet(b)
        for h in exp.get("highlights", []):
            if isinstance(h, dict):
                _add_bullet(h.get("claim_zh"))
                _add_bullet(h.get("claim_en"))
                _add_bullet(h.get("text"))
            else:
                _add_bullet(h)

    for proj in profile.get("projects", []):
        if not isinstance(proj, dict):
            continue
        for b in proj.get("bullets", []):
            _add_bullet(b)
        _add_bullet(proj.get("description_zh"))
        _add_bullet(proj.get("description_en"))
        _add_bullet(proj.get("description"))

    bullets_tuple = tuple(bullets_list)

    # 6. Extract metric anchors
    metric_anchors_list: List[Dict[str, Any]] = []

    # Candidate level (e.g. years_of_experience)
    cand = profile.get("candidate", {})
    if isinstance(cand, dict) and cand.get("years_of_experience") is not None:
        metric_anchors_list.append({
            "source_path": "candidate.years_of_experience",
            "claim_id": "candidate.years_of_experience",
            "name": "years_of_experience",
            "value": cand.get("years_of_experience"),
            "raw": str(cand.get("years_of_experience")),
        })

    # Experience highlights verified_metrics
    for exp_idx, exp in enumerate(profile.get("experience", [])):
        if not isinstance(exp, dict):
            continue
        for hl_idx, hl in enumerate(exp.get("highlights", [])):
            if isinstance(hl, dict):
                claim_id = str(hl.get("claim_id") or f"experience[{exp_idx}].highlights[{hl_idx}]")
                v_metrics = hl.get("verified_metrics")
                if isinstance(v_metrics, dict):
                    for k, v in v_metrics.items():
                        metric_anchors_list.append({
                            "source_path": f"experience[{exp_idx}].highlights[{hl_idx}].verified_metrics.{k}",
                            "claim_id": claim_id,
                            "name": k,
                            "value": v,
                            "raw": str(v),
                        })

    # Project verified_metrics / stars
    for proj_idx, proj in enumerate(profile.get("projects", [])):
        if not isinstance(proj, dict):
            continue
        proj_name = str(proj.get("name") or f"projects[{proj_idx}]")
        if proj.get("stars") is not None:
            metric_anchors_list.append({
                "source_path": f"projects[{proj_idx}].stars",
                "claim_id": f"{proj_name}:stars",
                "name": "stars",
                "value": proj.get("stars"),
                "raw": str(proj.get("stars")),
            })
        if isinstance(proj.get("verified_metrics"), dict):
            for k, v in proj["verified_metrics"].items():
                metric_anchors_list.append({
                    "source_path": f"projects[{proj_idx}].verified_metrics.{k}",
                    "claim_id": proj_name,
                    "name": k,
                    "value": v,
                    "raw": str(v),
                })
        for b_idx, b in enumerate(proj.get("bullets", [])):
            if isinstance(b, dict) and isinstance(b.get("verified_metrics"), dict):
                for k, v in b["verified_metrics"].items():
                    metric_anchors_list.append({
                        "source_path": f"projects[{proj_idx}].bullets[{b_idx}].verified_metrics.{k}",
                        "claim_id": str(b.get("claim_id") or f"projects[{proj_idx}].bullets[{b_idx}]"),
                        "name": k,
                        "value": v,
                        "raw": str(v),
                    })

    metric_anchors_tuple = tuple(metric_anchors_list)

    # 7. Input quality assessment
    cand_obj = profile.get("candidate", {}) if isinstance(profile.get("candidate"), dict) else {}
    unknown_experience = cand_obj.get("years_of_experience") is None
    degree_val = cand_obj.get("degree") or cand_obj.get("education_level") or ""
    unknown_education = not bool(str(degree_val).strip())
    major_val = cand_obj.get("major") or ""
    unknown_major = not bool(str(major_val).strip())
    title_val = cand_obj.get("title") or cand_obj.get("title_zh") or ""
    unknown_title = not bool(str(title_val).strip())

    unknown_fields: List[str] = []
    if unknown_education:
        unknown_fields.append("education")
    if unknown_experience:
        unknown_fields.append("years_of_experience")
    if unknown_major:
        unknown_fields.append("major")
    if unknown_title:
        unknown_fields.append("title")

    input_quality = {
        "evidence_claim_count": len(claims_tuple),
        "total_skills": len(skills_tuple),
        "total_bullets": len(bullets_tuple),
        "total_metric_anchors": len(metric_anchors_tuple),
        "unknown_experience": unknown_experience,
        "unknown_education": unknown_education,
        "unknown_major": unknown_major,
        "unknown_title": unknown_title,
        "unknown_fields": unknown_fields,
        "profile_fact_policy": "missing facts remain unknown",
    }

    return ProfileEvidenceIndex(
        profile=profile,
        claims=claims_tuple,
        skills=skills_tuple,
        bullets=bullets_tuple,
        metric_anchors=metric_anchors_tuple,
        claim_by_id=claim_by_id,
        source_paths=source_paths,
        input_quality=input_quality,
    )


__all__ = [
    "EvidenceClaim",
    "ProfileEvidenceIndex",
    "build_profile_evidence_index",
    "iter_profile_claims",
    "find_evidence",
    "claim_matches",
    "claim_ref",
    "canonical_terms",
    "normalize_candidate_profile",
    "group_education_badges_into_rows",
    "extract_education_grid",
]

