"""
Report Application Service (services/report_service.py)
======================================================
Domain service for generating and validating strategy reports across dual tracks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.cli_helpers import read_text


class ReportService:
    """Domain service for generating and validating strategy reports across dual tracks."""

    def __init__(self, canonical_reporter: Optional[Any] = None):
        self._canonical_reporter = canonical_reporter

    @property
    def canonical_reporter(self) -> Any:
        if self._canonical_reporter is None:
            from modules.jd_analyst.reporter import OfferStrategyReporter

            self._canonical_reporter = OfferStrategyReporter()
        return self._canonical_reporter

    def generate_offer_strategy_report(
        self,
        decoded_jd: Any,
        match_result: Dict[str, Any],
        output_path: Union[str, Path],
        template_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Generates the Offer Strategy HTML report using template replacement with XSS sanitization."""
        from core.report_generator import generate_report

        return generate_report(
            decoded_jd=decoded_jd,
            match_result=match_result,
            template_path=template_path,
            output_path=output_path,
        )

    def generate_canonical_report(
        self,
        jd: Any,
        candidate: Any,
        matcher: Any,
        redflags: Any,
        prediction: Any,
        output_path: Union[str, Path],
    ) -> str:
        """Generates canonical interactive standalone HTML report."""
        return self.canonical_reporter.save_report(
            str(output_path),
            jd=jd,
            candidate=candidate,
            matcher=matcher,
            redflags=redflags,
            prediction=prediction,
        )

    def validate_report_security(self, report_path_or_content: Union[str, Path]) -> List[str]:
        """Audits report HTML for residual unreplaced placeholders and dangerous patterns."""
        if isinstance(report_path_or_content, Path):
            content = report_path_or_content.read_text(encoding="utf-8")
        else:
            content = read_text(str(report_path_or_content))

        unreplaced = re.findall(r"\{\{[A-Z0-9_]+\}\}", content)
        risks = []
        if unreplaced:
            for p in sorted(set(unreplaced)):
                risks.append(f"Unreplaced placeholder detected: {p}")
        return risks
