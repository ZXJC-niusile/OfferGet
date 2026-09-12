"""Backward-compatible JD matcher facade.

Matching is implemented once in ``modules.jd_analyst.matcher.JDMatcher``.
The historical dictionary-shaped function remains available for CLI/report
callers and is implemented by ``core.jd_compat``.
"""

from __future__ import annotations

from typing import Any, Dict

from core.jd_compat import match_legacy


def match_profile_to_jd(decoded_jd: Any, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Match a profile against a decoded JD using the canonical matcher."""
    return match_legacy(decoded_jd, profile_data)


__all__ = ["match_profile_to_jd"]
