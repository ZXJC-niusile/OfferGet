"""
Profile Application Service (services/profile_service.py)
========================================================
Domain service for candidate profile normalization, evidence indexing, and claims.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.profile_adapter import EvidenceClaim, ProfileContext, ProfileEvidenceIndex


class ProfileService:
    """Domain service for candidate profile normalization, evidence indexing, and claims."""

    def normalize(self, profile_data: Union[Dict[str, Any], ProfileContext]) -> Dict[str, Any]:
        """Normalizes candidate profile into standard SSOT schema."""
        import core.services as facade

        return facade.normalize_candidate_profile(profile_data)

    def get_context(self, profile_data: Union[Dict[str, Any], ProfileContext]) -> ProfileContext:
        """Constructs or returns a unified, immutable ProfileContext from candidate profile without cross-call caching."""
        import core.services as facade

        return facade.build_profile_context(profile_data)

    def get_evidence_index(
        self, profile_data: Union[Dict[str, Any], ProfileContext, ProfileEvidenceIndex]
    ) -> ProfileEvidenceIndex:
        """Extracts deterministic, auditable evidence index from candidate profile or returns existing index."""
        if isinstance(profile_data, ProfileEvidenceIndex):
            return profile_data
        if isinstance(profile_data, ProfileContext):
            return profile_data.evidence_index
        import core.services as facade

        return facade.build_profile_evidence_index(profile_data)

    def extract_claims(
        self, profile_data: Union[Dict[str, Any], ProfileContext, ProfileEvidenceIndex]
    ) -> List[EvidenceClaim]:
        """Extracts traceable evidence claims from profile or returns claims from existing context/index."""
        if isinstance(profile_data, ProfileEvidenceIndex):
            return list(profile_data.claims)
        if isinstance(profile_data, ProfileContext):
            return list(profile_data.claims)
        normalized = self.normalize(profile_data)
        import core.services as facade

        return facade.iter_profile_claims(normalized)

    def audit_ats(
        self,
        profile_or_text: Union[Dict[str, Any], str, Path],
        jd_decoded_or_text: Optional[Union[Dict[str, Any], str, Path]] = None,
        target_tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Audits candidate profile or resume text against ATS rules."""
        from core.ats_checker import audit_resume_ats

        return audit_resume_ats(
            profile_or_text=profile_or_text,
            jd_decoded_or_text=jd_decoded_or_text,
            target_tag=target_tag,
        )

    def generate_skill_ledger(
        self,
        profile_data: Any,
        jd_data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generates 3-state skill ledger (Verified vs Claimed vs Gap)."""
        from core.ats_checker import generate_skill_ledger

        return generate_skill_ledger(profile_data, jd_data=jd_data)

    def filter_by_visibility(
        self,
        profile_data: Any,
        target_tag: str,
    ) -> Dict[str, Any]:
        """Filters master profile by visibility tag."""
        from core.ats_checker import filter_profile_by_visibility

        return filter_profile_by_visibility(profile_data, target_tag=target_tag)

    def anonymize(
        self,
        data: Union[dict, str],
        level: str = "strict",
    ) -> Tuple[Union[dict, str], dict]:
        """Performs privacy anonymization on profile or resume text."""
        from core.anonymizer import anonymize_profile

        return anonymize_profile(data, level=level)

    def deanonymize(
        self,
        text_or_data: Union[str, dict],
        deanon_map: dict,
    ) -> Union[str, dict]:
        """Restores anonymized text or profile using reverse mapping."""
        from core.anonymizer import deanonymize_text

        return deanonymize_text(text_or_data, deanon_map)

    def verify_facts(
        self,
        profile_data: Any,
        text_or_claims: Any,
    ) -> Dict[str, Any]:
        """Verifies text or claims against candidate profile evidence."""
        from core.fact_guard import verify_resume_facts

        return verify_resume_facts(profile_data, text_or_claims)
