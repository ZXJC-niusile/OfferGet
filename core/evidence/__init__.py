"""
OfferGet Evidence Package.
Absorbed and unified from ASu-resume-skills (Apache-2.0).
Provides typed atomic claims, source hierarchy, metric recalculation,
inflation pattern defenses, and audit report generation.
"""

from core.evidence.auditor import EvidenceAuditor
from core.evidence.extractor import ClaimExtractor
from core.evidence.metrics import MetricRecalculator, MetricValidationResult
from core.evidence.models import (
    ALLOWED_CONFIDENCE,
    ALLOWED_RISKS,
    ALLOWED_SOURCE_RELIABILITY,
    ALLOWED_STATUSES,
    AuditClaim,
    AuditPattern,
    AuditReport,
    AuditSource,
    AuditTimelineItem,
    MetricCheck,
)
from core.evidence.schema import validate_report_data

__all__ = [
    "ALLOWED_CONFIDENCE",
    "ALLOWED_RISKS",
    "ALLOWED_SOURCE_RELIABILITY",
    "ALLOWED_STATUSES",
    "AuditClaim",
    "AuditPattern",
    "AuditReport",
    "AuditSource",
    "AuditTimelineItem",
    "ClaimExtractor",
    "EvidenceAuditor",
    "MetricCheck",
    "MetricRecalculator",
    "MetricValidationResult",
    "validate_report_data",
]
