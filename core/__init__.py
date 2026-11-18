"""OfferGet Core Engine - Deterministic Resume Ingestion, Auditing, and Rendering.

Implements PEP 562 module-level __getattr__ for lazy-loading core modules while
keeping core CLI helpers and registries eager.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Tuple

__version__ = "1.0.0"

# 1. Eager Core Infrastructure Imports
from core import cli_helpers
from core import registry

# 2. PEP 562 Lazy Loading Registry for Core Resume Modules
_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    # core.resume_view_model
    "ResumeViewModel": ("core.resume_view_model", "ResumeViewModel"),
    "HtmlThemeRenderer": ("core.resume_view_model", "HtmlThemeRenderer"),
    "AtsPlainRenderer": ("core.resume_view_model", "AtsPlainRenderer"),

    # core.resume_builder
    "ResumeBuilder": ("core.resume_builder", "ResumeBuilder"),
    "audit_resume_quality": ("core.resume_builder", "audit_resume_quality"),

    # core.browser_renderer
    "BrowserRenderer": ("core.browser_renderer", "BrowserRenderer"),
    "BrowserNotFoundError": ("core.browser_renderer", "BrowserNotFoundError"),

    # core.autofit
    "AutoFitEngine": ("core.autofit", "AutoFitEngine"),
    "TUNING_LADDER": ("core.autofit", "TUNING_LADDER"),
    "TuneProfile": ("core.autofit", "TuneProfile"),

    # core.resume_auditor
    "ResumeAuditor": ("core.resume_auditor", "ResumeAuditor"),
    "Finding": ("core.resume_auditor", "Finding"),

    # core.layout_solver
    "LayoutConfig": ("core.layout_solver", "LayoutConfig"),
    "LayoutSolveResult": ("core.layout_solver", "LayoutSolveResult"),
    "solve_layout": ("core.layout_solver", "solve_layout"),
    "generate_micro_typography_css": ("core.layout_solver", "generate_micro_typography_css"),
    "inject_micro_typography": ("core.layout_solver", "inject_micro_typography"),

    # core.validator
    "validate_anti_ai_slop": ("core.validator", "validate_anti_ai_slop"),

    # core.ats_checker
    "audit_resume_ats": ("core.ats_checker", "audit_resume_ats"),
    "generate_skill_ledger": ("core.ats_checker", "generate_skill_ledger"),
    "filter_profile_by_visibility": ("core.ats_checker", "filter_profile_by_visibility"),
    "ATSAuditor": ("core.ats_checker", "ATSAuditor"),

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

    # core.academic_sync
    "AcademicPublication": ("core.academic_sync", "AcademicPublication"),
    "BibTexPublicationParser": ("core.academic_sync", "BibTexPublicationParser"),

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
    "FORBIDDEN_BUZZWORDS": ("core.lexicon", "FORBIDDEN_BUZZWORDS"),
    "AI_BUZZWORDS_LEXICON": ("core.lexicon", "AI_BUZZWORDS_LEXICON"),

    # core.atomic_writer
    "SafeSaveResult": ("core.atomic_writer", "SafeSaveResult"),
    "safe_save_file": ("core.atomic_writer", "safe_save_file"),
    "atomic_write": ("core.atomic_writer", "atomic_write"),
    "is_file_locked": ("core.atomic_writer", "is_file_locked"),

    # core.resume_parser
    "ResumeTextParser": ("core.resume_parser", "ResumeTextParser"),
    "parse_resume_to_profile": ("core.resume_parser", "parse_resume_to_profile"),

    # core.reference_index
    "ReferenceKnowledgeIndex": ("core.reference_index", "ReferenceKnowledgeIndex"),
    "chunk_markdown_document": ("core.reference_index", "chunk_markdown_document"),
}

_SUBMODULES: set[str] = {
    "academic_exporter",
    "academic_sync",
    "anonymizer",
    "artifacts",
    "atomic_writer",
    "ats_checker",
    "ats_docx_renderer",
    "autofit",
    "browser_renderer",
    "cli_helpers",
    "diff_ledger",
    "fact_guard",
    "fingerprints",
    "layout_solver",
    "lexicon",
    "paths",
    "profile_adapter",
    "reference_index",
    "registry",
    "resume_auditor",
    "resume_builder",
    "resume_parser",
    "resume_photo",
    "resume_themes",
    "resume_view_model",
    "security_gate",
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
    "cli_helpers",
    "registry",
    "ResumeViewModel",
    "HtmlThemeRenderer",
    "AtsPlainRenderer",
    "ResumeBuilder",
    "audit_resume_quality",
    "validate_anti_ai_slop",
    "audit_resume_ats",
    "generate_skill_ledger",
    "filter_profile_by_visibility",
    "ATSAuditor",
    "PrivacyAnonymizer",
    "anonymize_profile",
    "deanonymize_text",
    "FactVerificationGuard",
    "verify_resume_facts",
    "DiffLedger",
    "DiffEntry",
    "DiffCategory",
    "DiffSeverity",
    "AcademicPublication",
    "BibTexPublicationParser",
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
    "ResumeTextParser",
    "parse_resume_to_profile",
    "ReferenceKnowledgeIndex",
    "chunk_markdown_document",
    "__version__",
]
