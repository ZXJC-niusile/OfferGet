"""
Match Application Service (services/match_service.py)
====================================================
Domain service for matching candidate profiles against decoded JDs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Sequence, Union

from core.profile_adapter import ProfileContext


class MatchService:
    """Domain service for matching candidate profiles against decoded JDs."""

    def match(
        self,
        jd_compat: Any,
        profile_data: Union[Dict[str, Any], ProfileContext],
        strict_gate: bool = False,
    ) -> Dict[str, Any]:
        """Matches profile or ProfileContext against decoded JD using canonical matcher and returns compatibility view."""
        import core.services as facade

        return facade.match_legacy(jd_compat, profile_data, strict_gate=strict_gate)

    def calculate_gap_roi(
        self,
        profile_data: Any,
        jd_files: Sequence[Union[str, Path]],
    ) -> Dict[str, Any]:
        """Calculates Skill Gap ROI for near-miss opportunities across target JDs."""
        from core.gap_roi import calculate_gap_roi

        return calculate_gap_roi(profile_data, list(jd_files))
