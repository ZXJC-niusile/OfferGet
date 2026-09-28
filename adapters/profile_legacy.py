"""Legacy compatibility adapters for candidate profile mapping and normalization.

Isolates historical field aliases and flat candidate dictionaries from core.profile_adapter.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.profile_adapter import (
    ProfileContext,
    normalize_candidate_profile,
)


def adapt_legacy_profile_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms historical flat or non-standard profile dictionaries into canonical raw profile shape
    before ProfileContext.from_profile() processes it.
    """
    if not isinstance(raw, dict):
        return {}

    adapted = dict(raw)

    # 1. Candidate metadata aliases
    candidate = dict(adapted.get("candidate", {})) if isinstance(adapted.get("candidate"), dict) else {}
    for legacy_key, target_key in [
        ("username", "name"),
        ("candidate_name", "name"),
        ("real_name", "name"),
        ("university", "school"),
        ("college", "school"),
        ("undergraduate_school", "school"),
        ("degree_school", "school"),
        ("telephone", "phone"),
        ("mobile", "phone"),
        ("mail", "email"),
        ("target_position", "title"),
        ("target_role", "title"),
        ("title_zh", "title"),
    ]:
        if legacy_key in adapted and target_key not in candidate:
            candidate[target_key] = adapted[legacy_key]

    if candidate:
        adapted["candidate"] = candidate

    # 2. Experiences / Internships / Projects aliases
    if "internships" in adapted and "experience" not in adapted:
        adapted["experience"] = adapted["internships"]
    elif "work_experience" in adapted and "experience" not in adapted:
        adapted["experience"] = adapted["work_experience"]
    elif "experiences" in adapted and "experience" not in adapted:
        adapted["experience"] = adapted["experiences"]

    if "project_experience" in adapted and "projects" not in adapted:
        adapted["projects"] = adapted["project_experience"]
    elif "project_list" in adapted and "projects" not in adapted:
        adapted["projects"] = adapted["project_list"]

    # 3. Awards / Honors aliases
    if "awards" in adapted and "honors_awards" not in adapted:
        adapted["honors_awards"] = adapted["awards"]
    elif "honors" in adapted and "honors_awards" not in adapted:
        adapted["honors_awards"] = adapted["honors"]

    # 4. Publications / Papers aliases
    if "papers" in adapted and "publications" not in adapted:
        adapted["publications"] = adapted["papers"]

    return adapted


def to_canonical_profile_context(profile_data: Union[Dict[str, Any], ProfileContext]) -> ProfileContext:
    """Universal ingress producing a canonical ProfileContext from any profile shape."""
    if isinstance(profile_data, ProfileContext):
        return profile_data
    adapted = adapt_legacy_profile_dict(profile_data if isinstance(profile_data, dict) else {})
    return ProfileContext.from_profile(adapted)


__all__ = [
    "adapt_legacy_profile_dict",
    "to_canonical_profile_context",
    "normalize_candidate_profile",
]
