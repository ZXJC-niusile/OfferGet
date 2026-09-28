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
from core.evidence.graph import (
    EvidenceGraph,
    EvidenceNode,
    EvidenceNodeState,
)
from core.evidence.open_source import (
    OpenSourceAuditor,
    OpenSourceContributionLevel,
)
from core.evidence.report_renderer import (
    render_audit_report_html,
    save_audit_report_html,
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
    "EvidenceGraph",
    "EvidenceNode",
    "EvidenceNodeState",
    "MetricCheck",
    "MetricRecalculator",
    "MetricValidationResult",
    "OpenSourceAuditor",
    "OpenSourceContributionLevel",
    "render_audit_report_html",
    "save_audit_report_html",
    "validate_report_data",
]
