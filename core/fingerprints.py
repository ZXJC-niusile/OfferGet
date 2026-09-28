"""Canonical content fingerprints used by OfferGet caches and artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a value deterministically without changing its semantic shape."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def content_fingerprint(value: Any, length: Optional[int] = None) -> str:
    """Return a SHA-256 fingerprint for structured data or text."""
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = canonical_json_bytes(value)
    digest = hashlib.sha256(payload).hexdigest()
    return digest if length is None else digest[:length]


def cache_key(stage: str, value: Any) -> str:
    """Build an explicit stage/content cache key."""
    return f"{stage}:{content_fingerprint(value)}"


def profile_fingerprint(profile_dict_or_ctx: Any, length: int = 16) -> str:
    """
    Computes deterministic SHA-256 fingerprint for a candidate profile.
    Maintains exact backwards compatibility with ApplicationRecord.evidence_snapshot.
    """
    from core.profile_adapter import ProfileContext

    if isinstance(profile_dict_or_ctx, ProfileContext):
        norm = profile_dict_or_ctx.normalized_profile
    elif isinstance(profile_dict_or_ctx, dict):
        ctx = ProfileContext.from_profile(profile_dict_or_ctx)
        norm = ctx.normalized_profile
    else:
        norm = getattr(profile_dict_or_ctx, "normalized_profile", {})

    prof_json = json.dumps(norm, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(prof_json.encode("utf-8")).hexdigest()
    return digest[:length] if length else digest


def jd_fingerprint(jd_text_or_canon: Any, length: int = 16) -> str:
    """Hash the canonical JD text for historical application snapshots.

    This is intentionally distinct from material_proposal.jd_fingerprint:
    proposal hashes strip whitespace and use a full digest. Do not interchange
    the two persistent contracts.
    """
    from core.jd_compat import to_canonical

    canon_jd = to_canonical(jd_text_or_canon)
    jd_text = canon_jd.raw_text or canon_jd.clean_text or canon_jd.job_title
    digest = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()
    return digest[:length] if length else digest


__all__ = [
    "canonical_json_bytes",
    "content_fingerprint",
    "cache_key",
    "profile_fingerprint",
    "jd_fingerprint",
]
