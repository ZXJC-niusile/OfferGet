"""
OfferGet Evidence Audit Models.
Provides typed atomic claims, source hierarchy, metric checks, inflation patterns,
and audit report data models conforming to OfferGet evidence specifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Allowed string literals matching OfferGet report schema
ALLOWED_STATUSES: Set[str] = {
    "corroborated",
    "partially_corroborated",
    "contradicted",
    "unsupported",
    "unverifiable",
}

ALLOWED_RISKS: Set[str] = {
    "low",
    "medium",
    "high",
    "critical",
}

ALLOWED_CONFIDENCE: Set[str] = {
    "low",
    "medium",
    "high",
}

ALLOWED_SOURCE_RELIABILITY: Set[str] = {
    "A",  # 官方且同期的直接记录 (Official/contemporaneous direct record)
    "B",  # 可复现的公开一手记录 (Reproducible public first-party record)
    "C",  # 有署名的二手报道 (Attributed secondary reporting)
    "D",  # 未核验陈述 (Unverified statements / claims)
}

ALLOWED_CHANGE_TYPES: Set[str] = {
    "relative_percent",
    "percentage_points",
}


@dataclass
class MetricCheck:
    """
    Structured metric verification parameters.
    Supports either/both:
      - ratio consistency: numerator / denominator * 100 == displayed_percent
      - change consistency:
          relative_percent: (result - baseline) / baseline * 100 == displayed_change
          percentage_points: result - baseline == displayed_change
    """
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    displayed_percent: Optional[float] = None
    baseline: Optional[float] = None
    result: Optional[float] = None
    change_type: Optional[str] = None
    displayed_change: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if self.numerator is not None:
            data["numerator"] = self.numerator
        if self.denominator is not None:
            data["denominator"] = self.denominator
        if self.displayed_percent is not None:
            data["displayed_percent"] = self.displayed_percent
        if self.baseline is not None:
            data["baseline"] = self.baseline
        if self.result is not None:
            data["result"] = self.result
        if self.change_type is not None:
            data["change_type"] = self.change_type
        if self.displayed_change is not None:
            data["displayed_change"] = self.displayed_change
        return data

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional[MetricCheck]:
        if not d or not isinstance(d, dict):
            return None
        return cls(
            numerator=float(d["numerator"]) if "numerator" in d and d["numerator"] is not None else None,
            denominator=float(d["denominator"]) if "denominator" in d and d["denominator"] is not None else None,
            displayed_percent=float(d["displayed_percent"]) if "displayed_percent" in d and d["displayed_percent"] is not None else None,
            baseline=float(d["baseline"]) if "baseline" in d and d["baseline"] is not None else None,
            result=float(d["result"]) if "result" in d and d["result"] is not None else None,
            change_type=str(d["change_type"]) if "change_type" in d and d["change_type"] is not None else None,
            displayed_change=float(d["displayed_change"]) if "displayed_change" in d and d["displayed_change"] is not None else None,
        )


@dataclass
class AuditSource:
    """
    Represents an evidence source anchoring claims.
    Reliability tier: A (highest/official) to D (unverified claim).
    """
    id: str
    title: str = ""
    url: Optional[str] = None
    type: str = "official_record"
    publisher: str = ""
    accessed_at: str = ""
    reliability: str = "A"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "publisher": self.publisher,
            "accessed_at": self.accessed_at,
            "reliability": self.reliability,
            "notes": self.notes,
        }
        if self.url:
            d["url"] = self.url
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AuditSource:
        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", "")),
            url=str(d["url"]) if d.get("url") else None,
            type=str(d.get("type", "official_record")),
            publisher=str(d.get("publisher", "")),
            accessed_at=str(d.get("accessed_at", "")),
            reliability=str(d.get("reliability", "A")),
            notes=str(d.get("notes", "")),
        )


@dataclass
class AuditClaim:
    """
    Atomic proposition extracted from resume and audited against evidence sources.
    Note: Distinct from profile_adapter.EvidenceClaim (which is a ground-truth claim in the profile).
    """
    id: str
    category: str = "general"
    resume_text: str = ""
    normalized_claim: str = ""
    status: str = "unverifiable"
    risk: str = "medium"
    confidence: str = "medium"
    evidence_for: List[str] = field(default_factory=list)
    evidence_against: List[str] = field(default_factory=list)
    metric: Optional[MetricCheck] = None
    analysis: str = ""
    verification_steps: List[str] = field(default_factory=list)
    page_break_before: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "resume_text": self.resume_text,
            "normalized_claim": self.normalized_claim,
            "status": self.status,
            "risk": self.risk,
            "confidence": self.confidence,
            "evidence_for": list(self.evidence_for),
            "evidence_against": list(self.evidence_against),
            "analysis": self.analysis,
            "verification_steps": list(self.verification_steps),
            "page_break_before": self.page_break_before,
        }
        if self.metric is not None:
            d["metric"] = self.metric.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AuditClaim:
        return cls(
            id=str(d.get("id", "")),
            category=str(d.get("category", "general")),
            resume_text=str(d.get("resume_text", "")),
            normalized_claim=str(d.get("normalized_claim", "")),
            status=str(d.get("status", "unverifiable")),
            risk=str(d.get("risk", "medium")),
            confidence=str(d.get("confidence", "medium")),
            evidence_for=list(d.get("evidence_for", [])),
            evidence_against=list(d.get("evidence_against", [])),
            metric=MetricCheck.from_dict(d.get("metric")),
            analysis=str(d.get("analysis", "")),
            verification_steps=list(d.get("verification_steps", [])),
            page_break_before=bool(d.get("page_break_before", False)),
        )


@dataclass
class AuditPattern:
    """
    Pattern of inflation observed across claims (e.g. 角色升格, 全系统叙事, 伪精确).
    """
    name: str
    description: str = ""
    signals: List[str] = field(default_factory=list)
    claim_ids: List[str] = field(default_factory=list)
    counter_evidence: Optional[str] = None
    confidence: str = "medium"
    page_break_before: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "signals": list(self.signals),
            "claim_ids": list(self.claim_ids),
            "confidence": self.confidence,
            "page_break_before": self.page_break_before,
        }
        if self.counter_evidence is not None:
            d["counter_evidence"] = self.counter_evidence
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AuditPattern:
        return cls(
            name=str(d.get("name", "")),
            description=str(d.get("description", "")),
            signals=list(d.get("signals", [])),
            claim_ids=list(d.get("claim_ids", [])),
            counter_evidence=d.get("counter_evidence"),
            confidence=str(d.get("confidence", "medium")),
            page_break_before=bool(d.get("page_break_before", False)),
        )


@dataclass
class AuditTimelineItem:
    """
    Timeline item for contemporaneous event mapping.
    """
    date: str
    title: str
    detail: str = ""
    source_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "title": self.title,
            "detail": self.detail,
            "source_ids": list(self.source_ids),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AuditTimelineItem:
        return cls(
            date=str(d.get("date", "")),
            title=str(d.get("title", "")),
            detail=str(d.get("detail", "")),
            source_ids=list(d.get("source_ids", [])),
        )


@dataclass
class AuditReport:
    """
    Full audit report data model conforming to OfferGet report schema.
    """
    metadata: Dict[str, Any] = field(default_factory=lambda: {
        "title": "简历主张真实性审计",
        "subject": "候选人",
        "generated_at": "",
        "scope": "简历主张真实性审计",
        "analyst": "OfferGet Evidence Auditor",
        "disclaimer": "结论描述现有证据，不评价人格，也不构成法律认定。",
    })
    summary: Dict[str, Any] = field(default_factory=lambda: {
        "conclusion": "",
        "highest_risk": [],
        "limitations": [],
    })
    sources: List[AuditSource] = field(default_factory=list)
    claims: List[AuditClaim] = field(default_factory=list)
    patterns: List[AuditPattern] = field(default_factory=list)
    timeline: List[AuditTimelineItem] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": dict(self.metadata),
            "summary": dict(self.summary),
            "sources": [s.to_dict() for s in self.sources],
            "claims": [c.to_dict() for c in self.claims],
            "patterns": [p.to_dict() for p in self.patterns],
            "timeline": [t.to_dict() for t in self.timeline],
            "next_steps": list(self.next_steps),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AuditReport:
        return cls(
            metadata=dict(d.get("metadata", {})),
            summary=dict(d.get("summary", {})),
            sources=[AuditSource.from_dict(s) for s in d.get("sources", [])],
            claims=[AuditClaim.from_dict(c) for c in d.get("claims", [])],
            patterns=[AuditPattern.from_dict(p) for p in d.get("patterns", [])],
            timeline=[AuditTimelineItem.from_dict(t) for t in d.get("timeline", [])],
            next_steps=list(d.get("next_steps", [])),
        )
