"""
JD Application Service (services/jd_service.py)
==============================================
Domain service for JD decoding, normalization, and taxonomy classification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.jd_compat import DecodedJDCompat
from core.cli_helpers import read_text
from core.jd_analyst.models import DecodedJD


class JDService:
    """Domain service for JD decoding, normalization, and taxonomy classification."""

    def decode_jd(self, jd_text_or_path: Union[str, Path]) -> DecodedJDCompat:
        """Decodes JD text or file path into a DecodedJDCompat dictionary view."""
        text = self._read_text_or_path(jd_text_or_path)
        from core.jd_compat import decode_legacy

        return decode_legacy(text)

    def to_canonical(self, decoded: Any) -> DecodedJD:
        """Converts legacy or compat decoded JD to canonical DecodedJD dataclass."""
        from core.jd_compat import to_canonical

        return to_canonical(decoded)

    def classify_taxonomy(self, jd_text_or_path: Union[str, Path]) -> Dict[str, Any]:
        """Classifies role taxonomy keywords and dimensions."""
        text = self._read_text_or_path(jd_text_or_path)
        from core.jd_compat import classify_role_taxonomy

        return classify_role_taxonomy(text)

    def evaluate_should_i_apply(
        self,
        jd_input: Any,
        profile_data: Any,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluates Go/No-Go decision, rating, pros/cons, and 6-week action plan."""
        from core.jd_decision import DecodeBeforeMatchGate, ShouldIApplyEvaluator
        from core.jd_compat import profile_to_canonical
        from core.jd_analyst.matcher import JDMatcher

        canonical_jd = DecodeBeforeMatchGate.enforce(jd_input)
        candidate = profile_to_canonical(profile_data)
        matcher_result = JDMatcher().match(canonical_jd, candidate)
        report = ShouldIApplyEvaluator().evaluate(canonical_jd, candidate, matcher_result, constraints)
        return {
            "stars": report.stars,
            "composite_score": report.composite_score,
            "verdict": report.verdict.value,
            "verdict_title": report.verdict_title,
            "verdict_description": report.verdict_description,
            "pros": report.pros,
            "cons": report.cons,
            "probability_range": list(report.probability_range),
            "probability_breakdown": {k: list(v) for k, v in report.probability_breakdown.items()},
            "next_action": report.next_action.value,
            "action_advice": report.action_advice,
            "dimension_scores": report.dimension_scores,
            "six_week_plan": {
                "focus_summary": report.six_week_plan.focus_summary,
                "weeks": [
                    {
                        "week_range": w.week_range,
                        "phase_name": w.phase_name,
                        "tasks": list(w.tasks),
                        "deliverables": w.deliverables,
                    }
                    for w in report.six_week_plan.weeks
                ],
            },
        }

    @staticmethod
    def _read_text_or_path(jd_text_or_path: Union[str, Path]) -> str:
        if isinstance(jd_text_or_path, Path):
            return jd_text_or_path.read_text(encoding="utf-8")
        return read_text(str(jd_text_or_path or ""))
