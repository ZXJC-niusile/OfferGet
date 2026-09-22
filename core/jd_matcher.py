"""Legacy boundary adapter for candidate-to-JD matching.

The canonical implementation is ``modules.jd_analyst.matcher.JDMatcher``
consuming ``modules.jd_analyst.models.DecodedJD`` and ``CandidateProfile``.
This module acts as a boundary adapter preserving the historical
dictionary-shaped ``match_profile_to_jd`` for legacy callers.
"""

from __future__ import annotations

from typing import Any, Dict

from core.jd_compat import match_legacy


def match_profile_to_jd(decoded_jd: Any, profile_data: Any) -> Dict[str, Any]:
    """Match a profile against a decoded JD using the canonical matcher."""
    return match_legacy(decoded_jd, profile_data)


__all__ = ["match_profile_to_jd"]
