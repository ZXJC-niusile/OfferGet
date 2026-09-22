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
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union


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


class ProfileEvidenceIndex:
    """Immutable index of claims, skills, bullets, and evidence anchors."""

    def __init__(
        self,
        profile: Dict[str, Any],
        claims: Tuple[EvidenceClaim, ...],
        skills: Tuple[str, ...],
        bullets: Tuple[str, ...],
        metric_anchors: Tuple[Dict[str, Any], ...],
        claim_by_id: Dict[str, EvidenceClaim],
        source_paths: Tuple[str, ...],
        input_quality: Dict[str, Any],
    ):
        object.__setattr__(self, "_profile", copy.deepcopy(profile))
        object.__setattr__(self, "claims", tuple(claims))
        object.__setattr__(self, "skills", tuple(skills))
        object.__setattr__(self, "bullets", tuple(bullets))
        object.__setattr__(self, "_metric_anchors", tuple(copy.deepcopy(a) for a in metric_anchors))
        object.__setattr__(self, "_claim_by_id", {k: copy.deepcopy(v) for k, v in claim_by_id.items()})
        object.__setattr__(self, "source_paths", tuple(source_paths))
        object.__setattr__(self, "_input_quality", copy.deepcopy(input_quality))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"ProfileEvidenceIndex is immutable, cannot modify '{name}'")

    @property
    def profile(self) -> Dict[str, Any]:
        """Returns a defensive deep copy of the normalized profile."""
        return copy.deepcopy(self._profile)

    @property
    def metric_anchors(self) -> Tuple[Dict[str, Any], ...]:
        """Returns a defensive deep copy of metric anchors tuple with deepcopied dicts."""
        return tuple(copy.deepcopy(a) for a in self._metric_anchors)

    @property
    def claim_by_id(self) -> Dict[str, EvidenceClaim]:
        """Returns a copy of the claim_by_id dictionary with defensive claim copies."""
        return {k: copy.deepcopy(v) for k, v in self._claim_by_id.items()}

    @property
    def input_quality(self) -> Dict[str, Any]:
        """Returns a defensive deep copy of the input quality mapping."""
        return copy.deepcopy(self._input_quality)

    def profile_copy(self) -> Dict[str, Any]:
        """Explicit helper returning a defensive copy of the profile."""
        return copy.deepcopy(self._profile)

    def __repr__(self) -> str:
        return f"ProfileEvidenceIndex(skills={len(self.skills)}, bullets={len(self.bullets)}, claims={len(self.claims)})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ProfileEvidenceIndex):
            return False
        return (
            self._profile == other._profile
            and self.claims == other.claims
            and self.skills == other.skills
            and self.bullets == other.bullets
            and self._metric_anchors == other._metric_anchors
            and self.source_paths == other.source_paths
            and self._input_quality == other._input_quality
        )


class ProfileContext:
    """Unified candidate profile context holding SSOT normalized profile and evidence index.

    Eliminates redundant normalization, claim extraction, and index parsing across OfferGet pipelines.
    Enforces immutability by storing private deep copies and returning defensive copies through properties.
    """

    def __init__(
        self,
        raw_profile: Dict[str, Any],
        normalized_profile: Dict[str, Any],
        evidence_index: ProfileEvidenceIndex,
        claims: Tuple[EvidenceClaim, ...],
        skills: Tuple[str, ...],
        bullets: Tuple[str, ...],
        metric_anchors: Tuple[Dict[str, Any], ...],
        input_quality: Dict[str, Any],
        canonical_profile: Optional[Any] = None,
    ):
        object.__setattr__(self, "_raw_profile", copy.deepcopy(raw_profile))
        object.__setattr__(self, "_normalized_profile", copy.deepcopy(normalized_profile))
        object.__setattr__(self, "evidence_index", evidence_index)
        object.__setattr__(self, "claims", tuple(claims))
        object.__setattr__(self, "skills", tuple(skills))
        object.__setattr__(self, "bullets", tuple(bullets))
        object.__setattr__(self, "_metric_anchors", tuple(copy.deepcopy(a) for a in metric_anchors))
        object.__setattr__(self, "_input_quality", copy.deepcopy(input_quality))
        object.__setattr__(self, "_canonical_profile", canonical_profile)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"ProfileContext is immutable, cannot modify '{name}'")

    @classmethod
    def from_profile(cls, profile_or_context: Union[Dict[str, Any], ProfileContext]) -> ProfileContext:
        """Factory method to obtain or construct a ProfileContext."""
        if isinstance(profile_or_context, ProfileContext):
            return profile_or_context
        return build_profile_context(profile_or_context)

    @property
    def raw_profile(self) -> Dict[str, Any]:
        """Returns a defensive deep copy of the raw profile."""
        return copy.deepcopy(self._raw_profile)

    @property
    def normalized_profile(self) -> Dict[str, Any]:
        """Returns a defensive deep copy of the normalized profile."""
        return copy.deepcopy(self._normalized_profile)

    @property
    def profile(self) -> Dict[str, Any]:
        """Convenience alias returning a defensive copy of the normalized profile."""
        return copy.deepcopy(self._normalized_profile)

    @property
    def metric_anchors(self) -> Tuple[Dict[str, Any], ...]:
        """Returns a defensive deep copy of metric anchors tuple with deepcopied dicts."""
        return tuple(copy.deepcopy(a) for a in self._metric_anchors)

    @property
    def input_quality(self) -> Dict[str, Any]:
        """Returns a defensive deep copy of the input quality mapping."""
        return copy.deepcopy(self._input_quality)

    def profile_copy(self) -> Dict[str, Any]:
        """Returns a defensive copy of the normalized profile."""
        return copy.deepcopy(self._normalized_profile)

    def normalized_profile_copy(self) -> Dict[str, Any]:
        """Returns a defensive copy of the normalized profile."""
        return copy.deepcopy(self._normalized_profile)

    def raw_profile_copy(self) -> Dict[str, Any]:
        """Returns a defensive copy of the raw profile."""
        return copy.deepcopy(self._raw_profile)

    def get_canonical_profile(self) -> Any:
        """Lazily extracts and caches the canonical CandidateProfile representation, returning a defensive copy."""
        if self._canonical_profile is None:
            from core.jd_compat import profile_to_canonical

            canonical = profile_to_canonical(self)
            object.__setattr__(self, "_canonical_profile", canonical)
        return copy.deepcopy(self._canonical_profile)

    def canonical_profile_copy(self) -> Any:
        """Explicit helper returning a defensive copy of the canonical CandidateProfile."""
        return self.get_canonical_profile()

    def to_analyst_candidate(self) -> Any:
        """Project this ProfileContext into modules.jd_analyst.models.CandidateProfile."""
        return self.get_canonical_profile()

    def to_advisor_candidate(self) -> Any:
        """Project this ProfileContext into core.advisor_matcher.CandidateProfile."""
        from core.advisor_matcher import CandidateProfile as AdvisorCandidateProfile

        prof = self._normalized_profile
        raw = self._raw_profile
        cand = prof.get("candidate", {}) if isinstance(prof.get("candidate"), dict) else {}
        raw_cand = raw.get("candidate", {}) if isinstance(raw.get("candidate"), dict) else raw
        edu = prof.get("education", {}) if isinstance(prof.get("education"), dict) else {}
        raw_edu = raw.get("education", {}) if isinstance(raw.get("education"), dict) else {}
        standing = raw.get("academic_standing", {}) if isinstance(raw.get("academic_standing"), dict) else {}

        school = (
            raw_edu.get("school")
            or edu.get("school")
            or cand.get("school")
            or cand.get("institution")
            or raw_cand.get("undergraduate_school")
            or raw_cand.get("university")
            or raw.get("degree_school", "")
        )
        major = raw_edu.get("major") or edu.get("major") or cand.get("major") or raw_cand.get("major", "")
        gpa = str(standing.get("gpa_display") or standing.get("gpa") or raw_edu.get("gpa") or cand.get("gpa") or raw.get("gpa", ""))
        rank = str(standing.get("rank") or raw_edu.get("rank") or cand.get("rank") or raw.get("rank", ""))

        coursework = [c.get("course_name", "") for c in standing.get("core_courses", [])] if "core_courses" in standing else list(raw.get("coursework", raw.get("courses", [])))
        honors = [
            h.get("name", "") if isinstance(h, dict) else str(h)
            for h in (raw.get("honors") or raw.get("honors_awards") or raw.get("awards") or prof.get("honors_awards") or [])
        ]

        interests = list(raw.get("research_interests", raw.get("interests", [])))
        if not interests and "target_schools" in raw:
            for ts in raw["target_schools"]:
                if isinstance(ts, dict) and ts.get("research_direction") and ts["research_direction"] not in interests:
                    interests.append(ts["research_direction"])
        if not interests and "graduation_thesis" in raw and isinstance(raw["graduation_thesis"], dict):
            interests.extend(raw["graduation_thesis"].get("tags", []))

        grade = str(raw_cand.get("grade") or cand.get("grade") or raw.get("grade") or "")
        target_degree = str(raw.get("target_degree") or raw_cand.get("target_degree") or cand.get("target_degree") or "")

        return AdvisorCandidateProfile(
            name=str(cand.get("name") or raw_cand.get("name", "候选人")),
            undergraduate_school=str(school),
            major=str(major),
            grade=grade,
            target_degree=target_degree,
            gpa=gpa,
            rank=rank,
            rank_percentage=standing.get("rank_percentage") or raw.get("rank_percentage"),
            honors_awards=honors,
            publications=list(raw.get("publications", prof.get("publications", []))),
            projects=list(raw.get("projects", prof.get("projects", []))),
            coursework=coursework,
            skills=list(self.skills),
            research_interests=interests,
            read_advisor_papers=list(raw.get("read_advisor_papers", [])),
            email=str(cand.get("email") or raw_cand.get("email", "")),
            phone=str(cand.get("phone") or raw_cand.get("phone", "")),
            wechat=str(raw_cand.get("wechat", "")),
        )

    def to_view_model(
        self,
        photo_path: Optional[Union[str, Path]] = None,
        reserve_photo: bool = True,
    ) -> Any:
        """Constructs a sanitized ResumeViewModel from this ProfileContext SSOT."""
        from core.resume_view_model import ResumeViewModel

        return ResumeViewModel.from_profile(
            self,
            photo_path=photo_path,
            reserve_photo=reserve_photo,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Returns a defensive deep copy of the normalized profile dictionary."""
        return copy.deepcopy(self._normalized_profile)

    def __repr__(self) -> str:
        name = self._normalized_profile.get("candidate", {}).get("name", "unknown")
        return f"ProfileContext(candidate={name}, skills={len(self.skills)})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ProfileContext):
            return False
        return (
            self._raw_profile == other._raw_profile
            and self._normalized_profile == other._normalized_profile
            and self.claims == other.claims
            and self.skills == other.skills
            and self.bullets == other.bullets
            and self._metric_anchors == other._metric_anchors
            and self._input_quality == other._input_quality
        )


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
    if experiences is None and "internships" in profile:
        experiences = profile.get("internships")
    if isinstance(experiences, list):
        for exp_idx, experience in enumerate(experiences):
            if not isinstance(experience, dict):
                continue
            _append_claim(claims, f"experience[{exp_idx}].role", f"experience[{exp_idx}].role", experience.get("role"), "experience_metadata", True)
            highlights = experience.get("highlights", [])
            if isinstance(highlights, list):
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
            bullets = experience.get("bullets")
            if isinstance(bullets, list):
                for bullet_idx, bullet in enumerate(bullets):
                    if isinstance(bullet, dict):
                        bullet_text = bullet.get("text") or bullet.get("claim_zh") or bullet.get("claim_en")
                        b_ver = "verified" if bullet.get("verified_metrics") else "claimed"
                    else:
                        bullet_text = bullet
                        b_ver = "claimed"
                    _append_claim(
                        claims,
                        f"experience[{exp_idx}].bullets[{bullet_idx}]",
                        f"experience[{exp_idx}].bullets[{bullet_idx}]",
                        bullet_text,
                        "experience",
                        True,
                        verification=b_ver,
                        role_scope=_text(experience.get("role_scope") or experience.get("role")),
                    )

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
    """Return direct and declared evidence, with direct evidence first and zh before en."""
    matches = [claim for claim in claims if claim_matches(term, claim.text)]
    return sorted(matches, key=lambda claim: (not claim.direct, "claim_en" in claim.source_path, claim.source_path))


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


def _normalize_single_experience(e: Dict[str, Any], *, prefer_org_key: bool = True) -> Dict[str, Any]:
    """Normalizes a single experience entry into standard org, company, role, time, period, bullets schema."""
    e_copy = dict(e)
    if prefer_org_key:
        org = e_copy.get("org") or e_copy.get("company") or e_copy.get("organization", "")
    else:
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
    return e_copy


def _normalize_experiences(items: Iterable[Any], *, prefer_org_key: bool = True) -> List[Dict[str, Any]]:
    """Normalizes an iterable of experience entries, filtering out non-dict items."""
    norm_exp = []
    for item in items:
        if isinstance(item, dict):
            norm_exp.append(_normalize_single_experience(item, prefer_org_key=prefer_org_key))
    return norm_exp


def _normalize_single_project(p: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes a single project entry into standard name, role, time, period, bullets schema."""
    p_copy = dict(p)
    p_name = p_copy.get("name") or p_copy.get("title") or ""
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
    return p_copy


def _normalize_projects(items: Iterable[Any]) -> List[Dict[str, Any]]:
    """Normalizes an iterable of project entries, filtering out non-dict items."""
    norm_proj = []
    for item in items:
        if isinstance(item, dict):
            norm_proj.append(_normalize_single_project(item))
    return norm_proj


def normalize_candidate_profile(raw_profile: Union[Dict[str, Any], ProfileContext]) -> Dict[str, Any]:
    """Normalizes candidate profile into the standard SSOT schema.

    Supports both full standard profiles (Track 1) and minimal/flat profiles (Track 2).
    Guarantees idempotence, copy-protection, and non-hallucination of missing fields.
    """
    if isinstance(raw_profile, ProfileContext):
        return copy.deepcopy(raw_profile.normalized_profile)
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

        raw_awards = (
            raw_profile_copy.get("awards")
            or raw_profile_copy.get("honors")
            or raw_profile_copy.get("honors_awards")
            or cand.get("honors_awards")
            or cand.get("awards")
            or cand.get("honors")
            or []
        )
        if isinstance(raw_awards, list):
            awards_list = copy.deepcopy(raw_awards)
        else:
            awards_list = [raw_awards] if raw_awards else []

        raw_pubs = (
            raw_profile_copy.get("publications")
            or raw_profile_copy.get("papers")
            or cand.get("publications")
            or []
        )
        if isinstance(raw_pubs, list):
            pubs_list = copy.deepcopy(raw_pubs)
        else:
            pubs_list = [raw_pubs] if raw_pubs else []

        if awards_list and "honors_awards" not in cand:
            cand["honors_awards"] = awards_list

        norm_exp = _normalize_experiences(raw_profile_copy.get("experience", []), prefer_org_key=True)
        norm_proj = _normalize_projects(raw_profile_copy.get("projects", []))

        return {
            "candidate": cand,
            "competencies": raw_profile_copy.get("competencies", {}),
            "experience": norm_exp,
            "projects": norm_proj,
            "publications": pubs_list,
            "papers": pubs_list,
            "awards": awards_list,
            "honors": awards_list,
            "honors_awards": awards_list,
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
    norm_exp = _normalize_experiences(raw_exp, prefer_org_key=False)

    # Projects / Campus normalization
    raw_proj = raw_profile_copy.get("projects") or raw_profile_copy.get("campus_experience", [])
    norm_proj = _normalize_projects(raw_proj)

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

    raw_awards = (
        raw_profile_copy.get("awards")
        or raw_profile_copy.get("honors")
        or raw_profile_copy.get("honors_awards")
        or cand_dict.get("honors_awards")
        or cand_dict.get("awards")
        or []
    )
    if isinstance(raw_awards, list):
        awards_list = copy.deepcopy(raw_awards)
    else:
        awards_list = [raw_awards] if raw_awards else []

    raw_pubs = raw_profile_copy.get("publications") or raw_profile_copy.get("papers") or []
    if isinstance(raw_pubs, list):
        pubs_list = copy.deepcopy(raw_pubs)
    else:
        pubs_list = [raw_pubs] if raw_pubs else []

    if awards_list:
        cand_dict["honors_awards"] = awards_list
    if "grade" in raw_profile_copy:
        cand_dict["grade"] = raw_profile_copy["grade"]
    if "target_degree" in raw_profile_copy:
        cand_dict["target_degree"] = raw_profile_copy["target_degree"]

    return {
        "candidate": cand_dict,
        "competencies": competencies,
        "experience": norm_exp,
        "projects": norm_proj,
        "publications": pubs_list,
        "papers": pubs_list,
        "awards": awards_list,
        "honors": awards_list,
        "honors_awards": awards_list,
        "narrative": raw_profile_copy.get("narrative", {}),
    }


def build_profile_evidence_index(
    raw_profile: Union[Dict[str, Any], ProfileContext],
    *,
    _already_normalized: bool = False,
) -> ProfileEvidenceIndex:
    """Builds an immutable, single-source-of-truth evidence index from a candidate profile."""
    if isinstance(raw_profile, ProfileContext):
        return raw_profile.evidence_index
    if not isinstance(raw_profile, dict):
        raise TypeError(f"Expected dict or ProfileContext, got {type(raw_profile)}")

    # 1. Normalize profile (copy-protected and idempotent)
    if _already_normalized:
        profile = raw_profile
    else:
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


def build_profile_context(profile_or_context: Union[Dict[str, Any], ProfileContext]) -> ProfileContext:
    """Builds or returns an immutable ProfileContext, avoiding redundant normalization."""
    if isinstance(profile_or_context, ProfileContext):
        return profile_or_context
    if not isinstance(profile_or_context, dict):
        raise TypeError(f"Expected dict or ProfileContext, got {type(profile_or_context).__name__}")

    norm_profile = normalize_candidate_profile(profile_or_context)
    evidence_index = build_profile_evidence_index(norm_profile, _already_normalized=True)

    return ProfileContext(
        raw_profile=copy.deepcopy(profile_or_context),
        normalized_profile=norm_profile,
        evidence_index=evidence_index,
        claims=evidence_index.claims,
        skills=evidence_index.skills,
        bullets=evidence_index.bullets,
        metric_anchors=evidence_index.metric_anchors,
        input_quality=evidence_index.input_quality,
    )


__all__ = [
    "EvidenceClaim",
    "ProfileEvidenceIndex",
    "ProfileContext",
    "build_profile_evidence_index",
    "build_profile_context",
    "iter_profile_claims",
    "find_evidence",
    "claim_matches",
    "claim_ref",
    "canonical_terms",
    "normalize_candidate_profile",
    "group_education_badges_into_rows",
    "extract_education_grid",
]

