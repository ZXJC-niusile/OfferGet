"""
OfferGet Thin Application Services (core/services.py)
====================================================
Stateless domain application service layer inspired by offerPilot.
Orchestrates existing domain engines into cohesive, pythonic workflows
without terminal prints, CLI interactions, or side-effects.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

# Core engine imports
from core.jd_compat import (
    DecodedJDCompat,
    classify_role_taxonomy,
    decode_legacy,
    match_legacy,
    to_canonical,
    canonical_to_legacy,
)
from core.profile_adapter import (
    EvidenceClaim,
    ProfileEvidenceIndex,
    build_profile_evidence_index,
    iter_profile_claims,
    normalize_candidate_profile,
)
from core.job_flow import run_career_review
from core.resume_builder import ResumeBuilder, audit_resume_quality
from core.offer_negotiator import OfferNegotiator, evaluate_offer_package
from core.report_generator import generate_report
from core.security_gate import validate_output_security
from core.jd_decoder import decode_jd
from core.jd_matcher import match_profile_to_jd
from core.validator import validate_bilingual_html, validate_anti_ai_slop
from core.ats_checker import audit_resume_ats, generate_skill_ledger, filter_profile_by_visibility
from core.gap_roi import calculate_gap_roi
from core.anonymizer import PrivacyAnonymizer, anonymize_profile, deanonymize_text
from core.fact_guard import FactVerificationGuard, verify_resume_facts
from core.defense_simulator import DefenseSimulator, simulate_project_defense
from core.baoyan_auditor import BaoyanAuditor, audit_baoyan_entry, compress_baoyan_entry, count_baoyan_words
from core.baoyan_pipeline import BaoyanPipeline, BaoyanStatus, validate_academic_profile, generate_camp_checklist
from core.advisor_matcher import AdvisorMatcher, match_advisor_and_draft_email

from modules.jd_analyst.models import (
    CandidateProfile,
    DecodedJD,
    MatcherResult,
    PredictionResult,
    RedFlagReport,
)
from modules.jd_analyst.reporter import OfferStrategyReporter


class JDService:
    """Domain service for JD decoding, normalization, and taxonomy classification."""

    def decode_jd(self, jd_text_or_path: Union[str, Path]) -> DecodedJDCompat:
        """Decodes JD text or file path into a DecodedJDCompat dictionary view."""
        text = self._read_text_or_path(jd_text_or_path)
        return decode_legacy(text)

    def to_canonical(self, decoded: Any) -> DecodedJD:
        """Converts legacy or compat decoded JD to canonical DecodedJD dataclass."""
        return to_canonical(decoded)

    def classify_taxonomy(self, jd_text_or_path: Union[str, Path]) -> Dict[str, Any]:
        """Classifies role taxonomy keywords and dimensions."""
        text = self._read_text_or_path(jd_text_or_path)
        return classify_role_taxonomy(text)

    @staticmethod
    def _read_text_or_path(jd_text_or_path: Union[str, Path]) -> str:
        if isinstance(jd_text_or_path, Path) or (isinstance(jd_text_or_path, str) and os.path.isfile(jd_text_or_path)):
            with open(jd_text_or_path, "r", encoding="utf-8") as f:
                return f.read()
        return str(jd_text_or_path or "")


class ProfileService:
    """Domain service for candidate profile normalization, evidence indexing, and claims."""

    def normalize(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes candidate profile into standard SSOT schema."""
        return normalize_candidate_profile(profile_data)

    def get_evidence_index(self, profile_data: Dict[str, Any]) -> ProfileEvidenceIndex:
        """Extracts deterministic, auditable evidence index from candidate profile."""
        return build_profile_evidence_index(profile_data)

    def extract_claims(self, profile_data: Dict[str, Any]) -> List[EvidenceClaim]:
        """Extracts traceable evidence claims from profile."""
        normalized = self.normalize(profile_data)
        return iter_profile_claims(normalized)


class MatchService:
    """Domain service for matching candidate profiles against decoded JDs."""

    def match(self, jd_compat: Any, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Matches profile against decoded JD using canonical matcher and returns compatibility view."""
        return match_legacy(jd_compat, profile_data)


class CareerReviewService:
    """Domain service for orchestrating career reviews, targeted questions, and tailored resumes."""

    def run_review(
        self,
        jd_text: Union[str, Path],
        profile_dict: Dict[str, Any],
        answers_dict: Optional[Dict[str, Any]] = None,
        listing_age_days: int = 15,
        build_resume: bool = False,
        resume_theme: str = "modern-navy",
        resume_output_dir: Optional[Union[str, Path]] = None,
        reserve_photo: bool = True,
    ) -> Dict[str, Any]:
        """Executes full career review pipeline with optional resume building."""
        if isinstance(jd_text, Path) or (isinstance(jd_text, str) and os.path.isfile(jd_text)):
            with open(jd_text, "r", encoding="utf-8") as f:
                raw_jd = f.read()
        elif isinstance(jd_text, dict):
            raw_jd = str(jd_text.get("raw_text") or jd_text.get("clean_text") or "")
        else:
            raw_jd = str(jd_text or "")

        return run_career_review(
            jd_text=raw_jd,
            profile_dict=profile_dict,
            answers_dict=answers_dict,
            listing_age_days=listing_age_days,
            build_resume=build_resume,
            resume_theme=resume_theme,
            resume_output_dir=resume_output_dir,
            reserve_photo=reserve_photo,
        )


class ResumeService:
    """Domain service for generating multi-template resumes and auditing layout/XSS health."""

    @property
    def supported_themes(self) -> List[str]:
        return list(ResumeBuilder.THEMES)

    def build_resume(
        self,
        profile_or_path: Union[Dict[str, Any], str, Path],
        theme: str = "modern-navy",
        output_dir: Union[str, Path] = "dist/resume",
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Builds a single resume theme."""
        builder = ResumeBuilder(profile_or_path, photo_path=photo_path, anonymize=anonymize)
        return builder.build_theme(
            theme=theme,
            output_dir=output_dir,
            photo=photo,
            autofit=autofit,
            anonymize=anonymize,
        )

    def build_all(
        self,
        profile_or_path: Union[Dict[str, Any], str, Path],
        output_dir: Union[str, Path] = "dist/resume",
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Dict[str, Path]]:
        """Builds all supported resume variants."""
        builder = ResumeBuilder(profile_or_path, photo_path=photo_path, anonymize=anonymize)
        return builder.build_all(
            output_dir=output_dir,
            photo=photo,
            photo_path=photo_path,
            autofit=autofit,
            anonymize=anonymize,
        )

    def audit_resume(self, html_path: Union[str, Path]) -> Dict[str, Any]:
        """Audits generated resume HTML quality, layout health, and security."""
        return audit_resume_quality(html_path)


class OfferService:
    """Domain service for compensation valuation, trap detection, and tactical counter-offers."""

    def __init__(self, negotiator: Optional[OfferNegotiator] = None):
        self.negotiator = negotiator or OfferNegotiator()

    def evaluate_offer(
        self,
        offer_data: Dict[str, Any],
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluates total compensation package and audits for 6 contract traps."""
        return self.negotiator.evaluate_offer(offer_data, candidate_profile=candidate_profile)

    def generate_counter_offer(
        self,
        offer_data_or_eval: Dict[str, Any],
        target_base: Optional[float] = None,
        competing_offers: Optional[List[Dict[str, Any]]] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generates evidence-anchored counter-offer proposals."""
        if "total_compensation" not in offer_data_or_eval:
            eval_res = self.evaluate_offer(offer_data_or_eval, candidate_profile=candidate_profile)
        else:
            eval_res = offer_data_or_eval

        return self.negotiator.generate_counter_offer(
            evaluation_result=eval_res,
            target_base=target_base,
            competing_offers=competing_offers,
            candidate_profile=candidate_profile,
        )

    def generate_counter_offer_letter(
        self,
        offer_data_or_eval: Dict[str, Any],
        target_base: Optional[float] = None,
        competing_offers: Optional[List[Dict[str, Any]]] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
        lang: str = "zh",
    ) -> str:
        """Generates polite, professional counter-offer communication email/letter."""
        if "total_compensation" not in offer_data_or_eval:
            eval_res = self.evaluate_offer(offer_data_or_eval, candidate_profile=candidate_profile)
        else:
            eval_res = offer_data_or_eval

        return self.negotiator.generate_counter_offer_letter(
            evaluation_result=eval_res,
            target_base=target_base,
            competing_offers=competing_offers,
            candidate_profile=candidate_profile,
            lang=lang,
        )


class ReportService:
    """Domain service for generating and validating strategy reports across dual tracks."""

    def __init__(self, canonical_reporter: Optional[OfferStrategyReporter] = None):
        self.canonical_reporter = canonical_reporter or OfferStrategyReporter()

    def generate_offer_strategy_report(
        self,
        decoded_jd: Any,
        match_result: Dict[str, Any],
        output_path: Union[str, Path],
        template_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Generates the Offer Strategy HTML report using template replacement with XSS sanitization."""
        tpl = str(template_path) if template_path else "templates/offer_strategy.html"
        return generate_report(
            decoded_jd=decoded_jd,
            match_result=match_result,
            template_path=tpl,
            output_path=str(output_path),
        )

    def generate_canonical_report(
        self,
        jd: DecodedJD,
        candidate: CandidateProfile,
        matcher: MatcherResult,
        redflags: RedFlagReport,
        prediction: PredictionResult,
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
        if isinstance(report_path_or_content, Path) or (
            isinstance(report_path_or_content, str) and os.path.isfile(report_path_or_content)
        ):
            with open(report_path_or_content, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = str(report_path_or_content)

        unreplaced = re.findall(r"\{\{[A-Z0-9_]+\}\}", content)
        risks = []
        if unreplaced:
            for p in sorted(set(unreplaced)):
                risks.append(f"Unreplaced placeholder detected: {p}")
        return risks


__all__ = [
    "JDService",
    "ProfileService",
    "MatchService",
    "CareerReviewService",
    "ResumeService",
    "OfferService",
    "ReportService",
    "decode_jd",
    "match_profile_to_jd",
    "generate_report",
    "validate_bilingual_html",
    "validate_anti_ai_slop",
    "audit_resume_ats",
    "generate_skill_ledger",
    "filter_profile_by_visibility",
    "calculate_gap_roi",
    "evaluate_offer_package",
    "OfferNegotiator",
    "PrivacyAnonymizer",
    "anonymize_profile",
    "deanonymize_text",
    "FactVerificationGuard",
    "verify_resume_facts",
    "DefenseSimulator",
    "simulate_project_defense",
    "BaoyanAuditor",
    "audit_baoyan_entry",
    "compress_baoyan_entry",
    "count_baoyan_words",
    "BaoyanPipeline",
    "BaoyanStatus",
    "validate_academic_profile",
    "generate_camp_checklist",
    "AdvisorMatcher",
    "match_advisor_and_draft_email",
    "run_career_review",
    "ResumeBuilder",
]
