"""
OfferGet Thin Application Services (core/services.py)
====================================================
Backward-compatible Facade re-exporting domain services from `services/`
and lazy loading core subsystem functions and classes.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Keep former module-level dependency names importable. These names are public
# compatibility symbols and common monkeypatch targets.
from core.cli_helpers import read_text
from core.jd_compat import (
    DecodedJDCompat,
    canonical_to_legacy,
    classify_role_taxonomy,
    decode_legacy,
    match_legacy,
    to_canonical,
)
from core.profile_adapter import (
    EvidenceClaim,
    ProfileContext,
    ProfileEvidenceIndex,
    build_profile_context,
    build_profile_evidence_index,
    iter_profile_claims,
    normalize_candidate_profile,
)
from core.job_flow import (
    create_review_session,
    load_review_session,
    run_career_review,
    save_review_session,
    validate_session_answers,
)

# Re-export domain services
from services.jd_service import JDService
from services.profile_service import ProfileService
from services.match_service import MatchService
from services.review_service import CareerReviewService
from services.resume_service import ResumeService, ResumeVersionService
from services.offer_service import (
    OfferService,
    ProposalService,
    ApplicationOutcomeService,
)
from services.report_service import ReportService
from services.academic_service import (
    CommunicationService,
    AcademicService,
    ApplicationGuardService,
)

_LAZY_EXPORTS: Dict[str, Tuple[str, str]] = {
    "ResumeBuilder": ("core.resume_builder", "ResumeBuilder"),
    "audit_resume_quality": ("core.resume_builder", "audit_resume_quality"),
    "OfferNegotiator": ("core.offer_negotiator", "OfferNegotiator"),
    "evaluate_offer_package": ("core.offer_negotiator", "evaluate_offer_package"),
    "generate_report": ("core.report_generator", "generate_report"),
    "resolve_report_template": ("core.report_generator", "resolve_report_template"),
    "validate_output_security": ("core.security_gate", "validate_output_security"),
    "decode_jd": ("core.jd_decoder", "decode_jd"),
    "match_profile_to_jd": ("core.jd_compat", "match_profile_to_jd"),
    "validate_bilingual_html": ("core.validator", "validate_bilingual_html"),
    "validate_anti_ai_slop": ("core.validator", "validate_anti_ai_slop"),
    "audit_resume_ats": ("core.ats_checker", "audit_resume_ats"),
    "generate_skill_ledger": ("core.ats_checker", "generate_skill_ledger"),
    "filter_profile_by_visibility": ("core.ats_checker", "filter_profile_by_visibility"),
    "calculate_gap_roi": ("core.gap_roi", "calculate_gap_roi"),
    "PrivacyAnonymizer": ("core.anonymizer", "PrivacyAnonymizer"),
    "anonymize_profile": ("core.anonymizer", "anonymize_profile"),
    "deanonymize_text": ("core.anonymizer", "deanonymize_text"),
    "FactVerificationGuard": ("core.fact_guard", "FactVerificationGuard"),
    "verify_resume_facts": ("core.fact_guard", "verify_resume_facts"),
    "DefenseSimulator": ("core.defense.simulator", "DefenseSimulator"),
    "simulate_project_defense": ("core.defense.simulator", "simulate_project_defense"),
    "BaoyanAuditor": ("core.baoyan_auditor", "BaoyanAuditor"),
    "audit_baoyan_entry": ("core.baoyan_auditor", "audit_baoyan_entry"),
    "compress_baoyan_entry": ("core.baoyan_auditor", "compress_baoyan_entry"),
    "count_baoyan_words": ("core.baoyan_auditor", "count_baoyan_words"),
    "BaoyanPipeline": ("core.baoyan_pipeline", "BaoyanPipeline"),
    "BaoyanStatus": ("core.baoyan_pipeline", "BaoyanStatus"),
    "validate_academic_profile": ("core.baoyan_pipeline", "validate_academic_profile"),
    "generate_camp_checklist": ("core.baoyan_pipeline", "generate_camp_checklist"),
    "BaoyanPackageBuilder": ("core.baoyan_package", "BaoyanPackageBuilder"),
    "PersonalStatementBuilder": ("core.baoyan_package", "PersonalStatementBuilder"),
    "TaocixinOutreachBuilder": ("core.baoyan_package", "TaocixinOutreachBuilder"),
    "AdvisorMatcher": ("core.advisor_matcher", "AdvisorMatcher"),
    "match_advisor_and_draft_email": ("core.advisor_matcher", "match_advisor_and_draft_email"),
    "CandidateProfile": ("modules.jd_analyst.models", "CandidateProfile"),
    "DecodedJD": ("modules.jd_analyst.models", "DecodedJD"),
    "MatcherResult": ("modules.jd_analyst.models", "MatcherResult"),
    "PredictionResult": ("modules.jd_analyst.models", "PredictionResult"),
    "RedFlagReport": ("modules.jd_analyst.models", "RedFlagReport"),
    "OfferStrategyReporter": ("modules.jd_analyst.reporter", "OfferStrategyReporter"),
    "MultiOfferComparator": ("core.offer_comparator", "MultiOfferComparator"),
    "CareerCommunicationKit": ("core.communication_kit", "CareerCommunicationKit"),
    "PostInterviewDebriefEngine": ("core.interview_debrief", "PostInterviewDebriefEngine"),
    "DuplicateApplicationGuard": ("core.duplicate_guard", "DuplicateApplicationGuard"),
    "BibTexPublicationParser": ("core.academic_sync", "BibTexPublicationParser"),
    "CampPresentationPlanner": ("core.academic_sync", "CampPresentationPlanner"),
    "run_career_review": ("core.job_flow", "run_career_review"),
    "create_review_session": ("core.job_flow", "create_review_session"),
    "save_review_session": ("core.job_flow", "save_review_session"),
    "load_review_session": ("core.job_flow", "load_review_session"),
    "validate_session_answers": ("core.job_flow", "validate_session_answers"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        mod_name, attr_name = _LAZY_EXPORTS[name]
        mod = importlib.import_module(mod_name)
        val = getattr(mod, attr_name)
        globals()[name] = val
        return val
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> List[str]:
    return sorted(set(globals().keys()) | set(_LAZY_EXPORTS.keys()))


__all__ = [
    "JDService",
    "ProfileService",
    "MatchService",
    "CareerReviewService",
    "ResumeService",
    "OfferService",
    "CommunicationService",
    "AcademicService",
    "ApplicationGuardService",
    "ProposalService",
    "ApplicationOutcomeService",
    "ResumeVersionService",
    "ReportService",
    "decode_jd",
    "match_profile_to_jd",
    "generate_report",
    "resolve_report_template",
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
    "create_review_session",
    "save_review_session",
    "load_review_session",
    "validate_session_answers",
    "ResumeBuilder",
    "MultiOfferComparator",
    "CareerCommunicationKit",
    "PostInterviewDebriefEngine",
    "DuplicateApplicationGuard",
    "BibTexPublicationParser",
    "CampPresentationPlanner",
]
