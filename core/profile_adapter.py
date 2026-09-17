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


__all__ = ["EvidenceClaim", "iter_profile_claims", "find_evidence", "claim_matches", "claim_ref", "canonical_terms"]
