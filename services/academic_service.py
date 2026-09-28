"""
Academic, Communication, and Guard Services (services/academic_service.py)
========================================================================
Domain services for career communication, academic publication ingestion,
camp presentation planning, and multi-channel duplicate application guard.
"""

from __future__ import annotations

from typing import Any, Optional


class CommunicationService:
    """Domain service for career correspondence, cold outreach, and negotiation letters."""

    def cold_outreach(self, *args: Any, **kwargs: Any) -> Any:
        from core.communication_kit import CareerCommunicationKit
        return CareerCommunicationKit.cold_outreach(*args, **kwargs)

    def cover_letter(self, *args: Any, **kwargs: Any) -> Any:
        from core.communication_kit import CareerCommunicationKit
        return CareerCommunicationKit.cover_letter(*args, **kwargs)

    def reschedule(self, *args: Any, **kwargs: Any) -> Any:
        from core.communication_kit import CareerCommunicationKit
        return CareerCommunicationKit.reschedule(*args, **kwargs)

    def thank_you(self, *args: Any, **kwargs: Any) -> Any:
        from core.communication_kit import CareerCommunicationKit
        return CareerCommunicationKit.thank_you(*args, **kwargs)

    def follow_up(self, *args: Any, **kwargs: Any) -> Any:
        from core.communication_kit import CareerCommunicationKit
        return CareerCommunicationKit.follow_up(*args, **kwargs)

    def salary_negotiation(self, *args: Any, **kwargs: Any) -> Any:
        from core.communication_kit import CareerCommunicationKit
        return CareerCommunicationKit.salary_negotiation(*args, **kwargs)

    def decline_offer(self, *args: Any, **kwargs: Any) -> Any:
        from core.communication_kit import CareerCommunicationKit
        return CareerCommunicationKit.decline_offer(*args, **kwargs)


class AcademicService:
    """Domain service for academic publication ingestion and camp presentation planning."""

    def parse_bibtex(self, bib_content: str, candidate_name: Optional[str] = None) -> Any:
        from core.academic_sync import BibTexPublicationParser
        return BibTexPublicationParser.parse_string(bib_content, candidate_name=candidate_name)

    def plan_camp_presentation(self, *args: Any, **kwargs: Any) -> Any:
        from core.academic_sync import CampPresentationPlanner
        return CampPresentationPlanner.plan(*args, **kwargs)

    def audit_entry(self, entry: Any, *args: Any, **kwargs: Any) -> Any:
        """Audits academic resume entry for integrity and word-count."""
        from core.baoyan_auditor import audit_baoyan_entry
        return audit_baoyan_entry(entry, *args, **kwargs)

    def compress_entry(self, entry: Any, *args: Any, **kwargs: Any) -> Any:
        """Compresses academic entry to strict word count tier."""
        from core.baoyan_auditor import compress_baoyan_entry
        return compress_baoyan_entry(entry, *args, **kwargs)

    def match_advisor(
        self,
        advisor_data: Any,
        candidate_data: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Matches professor profile and generates tailored outreach email."""
        from core.advisor_matcher import match_advisor_and_draft_email
        return match_advisor_and_draft_email(
            advisor_data=advisor_data,
            candidate_data=candidate_data,
            *args,
            **kwargs,
        )

    def generate_checklist(self, profile: Any, *args: Any, **kwargs: Any) -> Any:
        """Generates summer camp / re-examination checklist."""
        from core.baoyan_pipeline import generate_camp_checklist
        return generate_camp_checklist(profile, *args, **kwargs)

    def validate_profile(self, profile: Any) -> Any:
        """Validates academic profile for completeness and red flags."""
        from core.baoyan_pipeline import validate_academic_profile
        return validate_academic_profile(profile)

    def simulate_defense(
        self,
        target_project_or_text: Any,
        candidate_profile: Optional[Any] = None,
        intensity: str = "开始挑刺",
    ) -> Any:
        """Simulates project defense interrogation."""
        from core.defense.simulator import simulate_project_defense
        return simulate_project_defense(
            target_project_or_text,
            candidate_profile=candidate_profile,
            intensity=intensity,
        )


class ApplicationGuardService:
    """Domain service for multi-channel duplicate application and recruiter collision guard."""

    def check_application(self, *args: Any, **kwargs: Any) -> Any:
        from core.duplicate_guard import DuplicateApplicationGuard
        return DuplicateApplicationGuard.check_application(*args, **kwargs)
