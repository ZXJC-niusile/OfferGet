"""
OfferGet Evidence Audit Report Schema Validator.
Ported and enhanced from ASu-resume-skills (Apache-2.0).
Validates JSON structure, ID referential integrity, and metric consistency.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from urllib.parse import urlparse

from core.evidence.metrics import MetricRecalculator
from core.evidence.models import (
    ALLOWED_CONFIDENCE,
    ALLOWED_RISKS,
    ALLOWED_STATUSES,
)


def validate_report_data(data: Dict[str, Any]) -> List[str]:
    """
    Validates report data against ASu report-schema.md.
    Returns list of error messages. If empty, the report data is valid.
    """
    errors: List[str] = []

    # 1. Metadata validation
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata 必须是对象")
        metadata = {}
    for key in ("title", "subject", "generated_at"):
        if not metadata.get(key):
            errors.append(f"metadata.{key} 缺失")

    # 2. Sources & Claims non-empty lists
    sources = data.get("sources")
    claims = data.get("claims")
    if not isinstance(sources, list) or not sources:
        errors.append("sources 必须是非空数组")
        sources = []
    if not isinstance(claims, list) or not claims:
        errors.append("claims 必须是非空数组")
        claims = []

    # 3. Source ID uniqueness and URLs
    source_ids = {s.get("id") for s in sources if isinstance(s, dict) and s.get("id")}
    if len(source_ids) != len(sources):
        errors.append("source id 缺失或重复")

    for source in sources:
        if not isinstance(source, dict):
            errors.append("source 条目必须是对象")
            continue
        sid = source.get("id", "<无编号>")
        url = source.get("url")
        if url:
            parsed = urlparse(str(url))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{sid} URL 必须使用 http 或 https：{url}")

    # 4. Claim ID uniqueness, required fields, and references
    claim_ids = {c.get("id") for c in claims if isinstance(c, dict) and c.get("id")}
    if len(claim_ids) != len(claims):
        errors.append("claim id 缺失或重复")

    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim 条目必须是对象")
            continue
        cid = claim.get("id", "<无编号>")
        for key in ("normalized_claim", "status", "risk", "confidence", "analysis"):
            if not claim.get(key):
                errors.append(f"{cid} 缺少 {key}")

        st = claim.get("status")
        if st and st not in ALLOWED_STATUSES:
            errors.append(f"{cid} status 非法：{st}")

        rk = claim.get("risk")
        if rk and rk not in ALLOWED_RISKS:
            errors.append(f"{cid} risk 非法：{rk}")

        cf = claim.get("confidence")
        if cf and cf not in ALLOWED_CONFIDENCE:
            errors.append(f"{cid} confidence 非法：{cf}")

        # Metric validation
        if "metric" in claim and claim["metric"] is not None:
            metric_errors = MetricRecalculator.validate_metric(claim["metric"], claim_id=cid)
            errors.extend(metric_errors)

        # Cross-reference sources
        ev_for = claim.get("evidence_for", [])
        ev_against = claim.get("evidence_against", [])
        if not isinstance(ev_for, list):
            errors.append(f"{cid} evidence_for 必须是列表")
            ev_for = []
        if not isinstance(ev_against, list):
            errors.append(f"{cid} evidence_against 必须是列表")
            ev_against = []

        for sid in ev_for + ev_against:
            if sid not in source_ids:
                errors.append(f"{cid} 引用了不存在的 source id：{sid}")

    # 5. Patterns cross-reference claim IDs
    for pattern in data.get("patterns", []):
        if not isinstance(pattern, dict):
            continue
        pname = pattern.get("name", "<未命名模式>")
        c_ids = pattern.get("claim_ids", [])
        if not isinstance(c_ids, list):
            errors.append(f"模式 {pname} claim_ids 必须是列表")
            continue
        for cid in c_ids:
            if cid not in claim_ids:
                errors.append(f"模式 {pname} 引用了不存在的 claim id：{cid}")

    # 6. Timeline cross-reference source IDs
    for item in data.get("timeline", []):
        if not isinstance(item, dict):
            continue
        title = item.get("title", "<未命名时间线>")
        s_ids = item.get("source_ids", [])
        if not isinstance(s_ids, list):
            errors.append(f"时间线 {title} source_ids 必须是列表")
            continue
        for sid in s_ids:
            if sid not in source_ids:
                errors.append(f"时间线 {title} 引用了不存在的 source id：{sid}")

    return errors
