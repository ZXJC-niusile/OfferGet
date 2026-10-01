"""OfferGet Core Engine - Strategic Job Description Decoding & Offer Strategy OS.

Implements PEP 562 module-level __getattr__ for lightweight lazy-loading of heavy
vertical business domains while keeping eager imports for core infrastructure.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Tuple

__version__ = "1.0.0"

# Extend core namespace path to seamlessly absorb ApexResume core modules
from pathlib import Path
_apex_core_dir = Path(__file__).resolve().parent.parent / "ApexResume" / "core"
if _apex_core_dir.is_dir() and str(_apex_core_dir) not in __path__:
    __path__.append(str(_apex_core_dir))

# 1. Eager Core Infrastructure Imports
from core import cli_helpers
from core import registry

# 2. PEP 562 Lazy Loading Registry for Heavy Vertical Domains
_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    # core.run_context
    "StageTrace": ("core.run_context", "StageTrace"),
    "RunContext": ("core.run_context", "RunContext"),
    "compute_fingerprint": ("core.run_context", "compute_fingerprint"),
    "sanitize_trace_payload": ("core.run_context", "sanitize_trace_payload"),
    "DeterministicCache": ("core.run_context", "DeterministicCache"),

    # core.resume_view_model
    "ResumeViewModel": ("core.resume_view_model", "ResumeViewModel"),
    "HtmlThemeRenderer": ("core.resume_view_model", "HtmlThemeRenderer"),
    "AtsPlainRenderer": ("core.resume_view_model", "AtsPlainRenderer"),

    # core.resume_builder
    "ResumeBuilder": ("core.resume_builder", "ResumeBuilder"),
    "audit_resume_quality": ("core.resume_builder", "audit_resume_quality"),

    # core.layout_solver
    "LayoutConfig": ("core.layout_solver", "LayoutConfig"),
    "LayoutSolveResult": ("core.layout_solver", "LayoutSolveResult"),
    "solve_layout": ("core.layout_solver", "solve_layout"),
    "generate_micro_typography_css": ("core.layout_solver", "generate_micro_typography_css"),
    "inject_micro_typography": ("core.layout_solver", "inject_micro_typography"),

    # core.jd_compat
    "decode_jd": ("core.jd_compat", "decode_jd"),

    # core.jd_compat
    "match_profile_to_jd": ("core.jd_compat", "match_profile_to_jd"),

    # core.report_generator
    "generate_report": ("core.report_generator", "generate_report"),

    # core.validator
    "validate_bilingual_html": ("core.validator", "validate_bilingual_html"),
    "validate_anti_ai_slop": ("core.validator", "validate_anti_ai_slop"),

    # core.ats_checker
    "audit_resume_ats": ("core.ats_checker", "audit_resume_ats"),
    "generate_skill_ledger": ("core.ats_checker", "generate_skill_ledger"),
    "filter_profile_by_visibility": ("core.ats_checker", "filter_profile_by_visibility"),
    "ATSAuditor": ("core.ats_checker", "ATSAuditor"),

    # core.gap_roi
    "SkillGapROIEngine": ("core.gap_roi", "SkillGapROIEngine"),
    "calculate_gap_roi": ("core.gap_roi", "calculate_gap_roi"),

    # core.offer_negotiator
    "OfferNegotiator": ("core.offer_negotiator", "OfferNegotiator"),
    "evaluate_offer_package": ("core.offer_negotiator", "evaluate_offer_package"),

    # core.anonymizer
    "PrivacyAnonymizer": ("core.anonymizer", "PrivacyAnonymizer"),
    "anonymize_profile": ("core.anonymizer", "anonymize_profile"),
    "deanonymize_text": ("core.anonymizer", "deanonymize_text"),

    # core.fact_guard
    "FactVerificationGuard": ("core.fact_guard", "FactVerificationGuard"),
    "verify_resume_facts": ("core.fact_guard", "verify_resume_facts"),

    # core.diff_ledger
    "DiffLedger": ("core.diff_ledger", "DiffLedger"),
    "DiffEntry": ("core.diff_ledger", "DiffEntry"),
    "DiffCategory": ("core.diff_ledger", "DiffCategory"),
    "DiffSeverity": ("core.diff_ledger", "DiffSeverity"),

    # core.baoyan_auditor
    "BaoyanAuditor": ("core.baoyan_auditor", "BaoyanAuditor"),
    "audit_baoyan_entry": ("core.baoyan_auditor", "audit_baoyan_entry"),
    "compress_baoyan_entry": ("core.baoyan_auditor", "compress_baoyan_entry"),
    "count_baoyan_words": ("core.baoyan_auditor", "count_baoyan_words"),

    # core.baoyan_pipeline
    "BaoyanPipeline": ("core.baoyan_pipeline", "BaoyanPipeline"),
    "BaoyanStatus": ("core.baoyan_pipeline", "BaoyanStatus"),
    "validate_academic_profile": ("core.baoyan_pipeline", "validate_academic_profile"),
    "generate_camp_checklist": ("core.baoyan_pipeline", "generate_camp_checklist"),

    # core.advisor_matcher
    "AdvisorMatcher": ("core.advisor_matcher", "AdvisorMatcher"),
    "AdvisorProfile": ("core.advisor_matcher", "AdvisorProfile"),
    "CandidateProfile": ("core.advisor_matcher", "CandidateProfile"),
    "Publication": ("core.advisor_matcher", "Publication"),
    "match_advisor_and_draft_email": ("core.advisor_matcher", "match_advisor_and_draft_email"),

    # core.defense
    "DefenseSimulator": ("core.defense", "DefenseSimulator"),
    "simulate_project_defense": ("core.defense", "simulate_project_defense"),

    # core.lexicon
    "VERB_HIERARCHY": ("core.lexicon", "VERB_HIERARCHY"),
    "STRONG_ACTION_VERBS_ZH": ("core.lexicon", "STRONG_ACTION_VERBS_ZH"),
    "STRONG_ACTION_VERBS_EN": ("core.lexicon", "STRONG_ACTION_VERBS_EN"),
    "WEAK_ACTION_VERBS_ZH": ("core.lexicon", "WEAK_ACTION_VERBS_ZH"),
    "WEAK_ACTION_VERBS_EN": ("core.lexicon", "WEAK_ACTION_VERBS_EN"),
    "ROLE_RANKS": ("core.lexicon", "ROLE_RANKS"),
    "QUANTIFIED_PATTERNS": ("core.lexicon", "QUANTIFIED_PATTERNS"),
    "NON_METRIC_TECH_PATTERNS": ("core.lexicon", "NON_METRIC_TECH_PATTERNS"),
    "INFLATION_PATTERNS": ("core.lexicon", "INFLATION_PATTERNS"),
    # core.atomic_writer
    "SafeSaveResult": ("core.atomic_writer", "SafeSaveResult"),
    "safe_save_file": ("core.atomic_writer", "safe_save_file"),
    "atomic_write": ("core.atomic_writer", "atomic_write"),
    "is_file_locked": ("core.atomic_writer", "is_file_locked"),
    # core.resume_parser
    "ResumeTextParser": ("core.resume_parser", "ResumeTextParser"),
    "parse_resume_to_profile": ("core.resume_parser", "parse_resume_to_profile"),
}

_SUBMODULES: set[str] = {
    "academic_exporter",
    "atomic_writer",
    "advisor_matcher",
    "anonymizer",
    "application_tracker",
    "asu_modeler",
    "ats_checker",
    "baoyan_auditor",
    "baoyan_pipeline",
    "resume_parser",

    "cli_helpers",
    "defense_simulator",
    "fact_guard",
    "gap_roi",
    "input_router",
    "interview_debrief",
    "interview_review_contract",
    "jd_compat",
    "jd_decoder",
    "jd_matcher",
    "job_flow",
    "lexicon",
    "material_proposal",
    "offer_negotiator",
    "profile_adapter",
    "registry",
    "report_generator",
    "rendercv_adapter",
    "resume_version_diff",
    "resume_builder",
    "resume_view_model",
    "run_context",
    "security_gate",
    "services",
    "validator",
}


def __getattr__(name: str) -> Any:
    """PEP 562 dynamic attribute resolution with module-level globals caching."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        val = getattr(module, attr_name)
        globals()[name] = val
        return val

    if name in _SUBMODULES:
        module = importlib.import_module(f"core.{name}")
        globals()[name] = module
        return module

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> List[str]:
    """Expose all eager, lazy symbols and submodules for inspection and auto-completion."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()) + list(_SUBMODULES))


__all__ = [
    "StageTrace",
    "RunContext",
    "compute_fingerprint",
    "sanitize_trace_payload",
    "DeterministicCache",
    "cli_helpers",
    "services",
    "registry",
    "ResumeViewModel",
    "HtmlThemeRenderer",
    "AtsPlainRenderer",
    "ResumeBuilder",
    "audit_resume_quality",
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
    "DiffLedger",
    "DiffEntry",
    "DiffCategory",
    "DiffSeverity",
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
    "VERB_HIERARCHY",
    "STRONG_ACTION_VERBS_ZH",
    "STRONG_ACTION_VERBS_EN",
    "WEAK_ACTION_VERBS_ZH",
    "WEAK_ACTION_VERBS_EN",
    "ROLE_RANKS",
    "QUANTIFIED_PATTERNS",
    "NON_METRIC_TECH_PATTERNS",
    "INFLATION_PATTERNS",
    "FORBIDDEN_BUZZWORDS",
    "AI_BUZZWORDS_LEXICON",
    "SafeSaveResult",
    "safe_save_file",
    "atomic_write",
    "is_file_locked",
    "__version__",
]
