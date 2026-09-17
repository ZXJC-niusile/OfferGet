"""Shared candidate-profile evidence extraction for career review flows.

The project historically had several small, incompatible profile readers. This
module stays deterministic and read-only: it produces ephemeral claim records
with source paths so recommendations can be grounded without inventing resume
content or persisting a second profile schema.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List


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


# Deterministic aliases are deliberately small. New aliases should be added
# deliberately and covered by a test; fuzzy matching is unsafe for fact gates.
ALIASES: Dict[str, set[str]] = {
    "pytorch": {"pytorch", "torch"},
    "python": {"python"},
    "c++": {"c++", "cpp"},
    "cuda": {"cuda"},
    "triton": {"triton"},
    "megatron-lm": {"megatron-lm", "megatron"},
    "deepspeed": {"deepspeed"},
    "vllm": {"vllm"},
    "tensorrt-llm": {"tensorrt-llm", "tensorrt llm"},
    "sglang": {"sglang"},
    "dpo": {"dpo"},
    "ppo": {"ppo"},
    "grpo": {"grpo"},
    "rlhf": {"rlhf"},
    "mcp": {"mcp", "model context protocol"},
    "graphrag": {"graphrag", "graph rag"},
    "flashattention": {"flashattention", "flashattention-2", "flashattention-3"},
    "pagedattention": {"pagedattention"},
    "awq": {"awq"},
    "gptq": {"gptq"},
    "rope": {"rope"},
    "mla": {"mla", "multi-head latent attention"},
}


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
    for canonical, forms in ALIASES.items():
        if normalized == canonical or normalized in forms:
            return {canonical, *forms}
    return {normalized}


def claim_matches(term: str, claim_text: str) -> bool:
    """Match a requirement without fuzzy substring guesses."""
    text = _text(claim_text).lower()
    if not text:
        return False
    for candidate in canonical_terms(term):
        if re.search(r"(?<![a-z0-9])" + re.escape(candidate) + r"(?![a-z0-9])", text):
            return True
        if re.search(r"[一-鿿]", candidate) and candidate in text:
            return True
    return False


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
    """
    if not isinstance(raw_profile, dict):
        raise TypeError(f"Expected dict for profile, got {type(raw_profile)}")

    # Case A: Profile is already structured with standard top-level 'candidate'
    if "candidate" in raw_profile and isinstance(raw_profile["candidate"], dict):
        cand = dict(raw_profile["candidate"])
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
        if "title" not in cand and "title_zh" in cand:
            cand["title"] = cand["title_zh"]
        if "reserve_photo" not in cand:
            cand["reserve_photo"] = True

        norm_exp = []
        for e in raw_profile.get("experience", []):
            if not isinstance(e, dict):
                continue
            e_copy = dict(e)
            org = e_copy.get("org") or e_copy.get("company", "")
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
            e_copy["time"] = time_str
            e_copy["period"] = time_str
            e_copy["bullets"] = bullets
            norm_exp.append(e_copy)

        norm_proj = []
        for p in raw_profile.get("projects", []):
            if not isinstance(p, dict):
                continue
            p_copy = dict(p)
            time_str = p_copy.get("time") or p_copy.get("period", "")
            bullets = list(p_copy.get("bullets", []))
            if not bullets:
                desc = p_copy.get("description_zh") or p_copy.get("description", "")
                if desc:
                    bullets.append(desc)
            p_copy["time"] = time_str
            p_copy["period"] = time_str
            p_copy["bullets"] = bullets
            norm_proj.append(p_copy)

        return {
            "candidate": cand,
            "competencies": raw_profile.get("competencies", {}),
            "experience": norm_exp,
            "projects": norm_proj,
            "publications": raw_profile.get("publications", []),
            "narrative": raw_profile.get("narrative", {}),
        }

    # Case B: Minimal / Flat profile format (Track 2 / Career Review input)
    cand_name = raw_profile.get("name") or raw_profile.get("candidate_name") or "候选人"
    title = raw_profile.get("intent") or raw_profile.get("target_role") or raw_profile.get("title") or "运营岗"
    phone = raw_profile.get("phone", "")
    email = raw_profile.get("email", "")
    location = raw_profile.get("city") or raw_profile.get("location", "")

    edu = raw_profile.get("education", {})
    school = edu.get("school", "")
    major = edu.get("major", "")
    degree = edu.get("degree", "")
    edu_time = edu.get("time", "")

    grid = extract_education_grid(edu)
    edu_badges = list(edu.get("education_badges", []))
    if not edu_badges:
        for r in grid:
            edu_badges.extend(r)

    # Experience normalization
    raw_exp = raw_profile.get("experience") or raw_profile.get("internships", [])
    norm_exp = []
    for e in raw_exp:
        org = e.get("company") or e.get("org") or e.get("organization", "")
        role = e.get("role") or e.get("title", "")
        time_str = e.get("time") or e.get("period", "")
        bullets = e.get("bullets", [])
        norm_exp.append({
            "org": org,
            "company": org,
            "role": role,
            "time": time_str,
            "bullets": bullets,
        })

    # Projects / Campus normalization
    raw_proj = raw_profile.get("projects") or raw_profile.get("campus_experience", [])
    norm_proj = []
    for p in raw_proj:
        p_name = p.get("name") or p.get("title") or "校园经历"
        p_role = p.get("role", "")
        p_time = p.get("time") or p.get("period", "")
        bullets = p.get("bullets", [])
        norm_proj.append({
            "name": p_name,
            "role": p_role,
            "time": p_time,
            "bullets": bullets,
        })

    # Competencies normalization
    competencies = raw_profile.get("competencies") or raw_profile.get("skills", {})

    clean_degree = f"{major}  {degree}" if major and degree else (degree or major)
    clean_degree = re.sub(r"\s*[｜|·]\s*", "  ", clean_degree).strip()

    return {
        "candidate": {
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
        },
        "competencies": competencies,
        "experience": norm_exp,
        "projects": norm_proj,
        "publications": raw_profile.get("publications", []),
        "narrative": raw_profile.get("narrative", {}),
    }


__all__ = [
    "EvidenceClaim",
    "iter_profile_claims",
    "find_evidence",
    "claim_matches",
    "claim_ref",
    "canonical_terms",
    "normalize_candidate_profile",
    "group_education_badges_into_rows",
    "extract_education_grid",
]

