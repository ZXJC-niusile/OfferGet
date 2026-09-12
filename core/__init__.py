"""OfferGet Core Engine - Strategic Job Description Decoding & Offer Strategy OS."""

__version__ = "1.0.0"

from core.jd_decoder import decode_jd
from core.jd_matcher import match_profile_to_jd
from core.report_generator import generate_report
from core.validator import validate_bilingual_html, validate_anti_ai_slop
from core.ats_checker import (
    audit_resume_ats,
    generate_skill_ledger,
    filter_profile_by_visibility,
    ATSAuditor
)

from core.gap_roi import SkillGapROIEngine, calculate_gap_roi
from core.offer_negotiator import OfferNegotiator, evaluate_offer_package
from core.anonymizer import (
    PrivacyAnonymizer,
    anonymize_profile,
    deanonymize_text
)
from core.fact_guard import (
    FactVerificationGuard,
    verify_resume_facts
)
from core.baoyan_auditor import (
    BaoyanAuditor,
    audit_baoyan_entry,
    compress_baoyan_entry,
    count_baoyan_words
)
from core.baoyan_pipeline import (
    BaoyanPipeline,
    BaoyanStatus,
    validate_academic_profile,
    generate_camp_checklist
)
from core.advisor_matcher import (
    AdvisorMatcher,
    AdvisorProfile,
    CandidateProfile,
    Publication,
    match_advisor_and_draft_email
)
from core.defense_simulator import (
    DefenseSimulator,
    simulate_project_defense
)

__all__ = [
    "decode_jd",
    "match_profile_to_jd",
    "generate_report",
    "validate_bilingual_html",
    "validate_anti_ai_slop",
    "audit_resume_ats",
    "generate_skill_ledger",
    "filter_profile_by_visibility",
    "ATSAuditor",
    "SkillGapROIEngine",
    "calculate_gap_roi",
    "OfferNegotiator",
    "evaluate_offer_package",
    "PrivacyAnonymizer",
    "anonymize_profile",
    "deanonymize_text",
    "FactVerificationGuard",
    "verify_resume_facts",
    "BaoyanAuditor",
    "audit_baoyan_entry",
    "compress_baoyan_entry",
    "count_baoyan_words",
    "BaoyanPipeline",
    "BaoyanStatus",
    "validate_academic_profile",
    "generate_camp_checklist",
    "AdvisorMatcher",
    "AdvisorProfile",
    "CandidateProfile",
    "Publication",
    "match_advisor_and_draft_email",
    "DefenseSimulator",
    "simulate_project_defense",
    "__version__"
]

