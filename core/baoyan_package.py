"""
OfferGet Baoyan Application Package Builder (core/baoyan_package.py)
===================================================================
Compatibility re-export layer.

All core models and builders (BaoyanPackageBuilder, PersonalStatementBuilder,
TaocixinOutreachBuilder) have been consolidated into `core.baoyan_pipeline`
to unify the academic postgraduate recommendation workflow into a single SSOT.
"""

from __future__ import annotations

from core.baoyan_pipeline import (
    ApplicantInfo,
    BaoyanPackageBuilder,
    PackageConfig,
    PackageDocument,
    PackageManifest,
    PackageSection,
    PersonalStatementBuilder,
    PersonalStatementDraft,
    SchoolInfo,
    TaocixinLetterDraft,
    TaocixinOutreachBuilder,
    TocEntry,
)

# Compatibility aliases
PackageTOCEntry = TocEntry
TaocixinOutreachEmail = TaocixinLetterDraft

__all__ = [
    "ApplicantInfo",
    "BaoyanPackageBuilder",
    "PackageConfig",
    "PackageDocument",
    "PackageManifest",
    "PackageSection",
    "PackageTOCEntry",
    "PersonalStatementBuilder",
    "PersonalStatementDraft",
    "SchoolInfo",
    "TaocixinLetterDraft",
    "TaocixinOutreachBuilder",
    "TaocixinOutreachEmail",
    "TocEntry",
]
