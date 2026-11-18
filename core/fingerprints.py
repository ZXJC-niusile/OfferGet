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


__all__ = [
    "canonical_json_bytes",
    "content_fingerprint",
]
