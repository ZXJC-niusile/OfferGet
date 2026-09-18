"""
OfferGet Run Context & Desensitized Trace Subsystem (core/run_context.py)
========================================================================
Implements deterministic execution fingerprinting, stage tracing, data sanitization,
and in-memory deterministic intermediate caching for OfferGet pipelines.
Inspired by robust production pipeline architectures.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union


@dataclass
class StageTrace:
    """Represents the execution telemetry of a single pipeline stage."""

    stage_name: str
    elapsed_ms: float
    cache_hit: bool = False
    error_code: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to a serializable dictionary."""
        return {
            "stage_name": self.stage_name,
            "elapsed_ms": round(float(self.elapsed_ms), 2),
            "cache_hit": self.cache_hit,
            "error_code": self.error_code,
            "summary": self.summary,
        }


@dataclass
class RunContext:
    """Execution context carrying run metadata, input fingerprint, and stage traces."""

    run_id: str = field(default_factory=lambda: secrets.token_hex(4))  # 8-character hex ID
    fingerprint: str = ""  # Deterministic SHA-256 fingerprint
    engine_version: str = "2.0.0"
    traces: List[StageTrace] = field(default_factory=list)

    def record_stage(
        self,
        stage_name: str,
        elapsed_ms: float,
        cache_hit: bool = False,
        error_code: str = "",
        summary: str = "",
    ) -> StageTrace:
        """Records telemetry for a pipeline execution stage."""
        trace = StageTrace(
            stage_name=stage_name,
            elapsed_ms=round(float(elapsed_ms), 2),
            cache_hit=cache_hit,
            error_code=error_code,
            summary=summary,
        )
        self.traces.append(trace)
        return trace

    def get_total_elapsed_ms(self) -> float:
        """Compute the sum of elapsed milliseconds across all recorded stages."""
        return round(sum(t.elapsed_ms for t in self.traces), 2)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize run context to dictionary."""
        return {
            "run_id": self.run_id,
            "fingerprint": self.fingerprint,
            "engine_version": self.engine_version,
            "traces": [t.to_dict() for t in self.traces],
            "total_elapsed_ms": self.get_total_elapsed_ms(),
        }


def _normalize_for_fingerprint(val: Any) -> Any:
    """Recursively converts data to a canonical, sortable representation."""
    if val is None or isinstance(val, (int, float, bool, str)):
        return val
    if isinstance(val, Enum):
        return val.value
    if is_dataclass(val) and not isinstance(val, type):
        return _normalize_for_fingerprint(asdict(val))
    if hasattr(val, "to_dict") and callable(val.to_dict):
        return _normalize_for_fingerprint(val.to_dict())
    if hasattr(val, "dict") and callable(val.dict):
        return _normalize_for_fingerprint(val.dict())
    if isinstance(val, dict):
        return {
            str(k): _normalize_for_fingerprint(v)
            for k, v in sorted(val.items(), key=lambda item: str(item[0]))
        }
    if isinstance(val, (list, tuple)):
        return [_normalize_for_fingerprint(x) for x in val]
    if isinstance(val, (set, frozenset)):
        items = [_normalize_for_fingerprint(x) for x in val]
        return sorted(
            items,
            key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False, default=str),
        )
    return str(val)


def compute_fingerprint(data: Any) -> str:
    """
    Pure function computing a deterministic SHA-256 fingerprint for arbitrary data.
    Ensures that identical structures with different dictionary key orderings
    produce identical 64-character hexadecimal SHA-256 hashes.
    """
    normalized = _normalize_for_fingerprint(data)
    serialized = json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# Desensitization regex patterns
_PHONE_PATTERN = re.compile(
    r"(?:\+?86[- ]?)?(?:1[3-9]\d{9}|1[3-9]\d{1}[- ]\d{4}[- ]\d{4})"
)
_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)
_ID_CARD_PATTERN = re.compile(
    r"\b[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
)

_SENSITIVE_NAME_KEYS = {
    "name",
    "candidate_name",
    "user_name",
    "username",
    "real_name",
    "applicant_name",
    "candidate",
}

_SENSITIVE_PHONE_KEYS = {
    "phone",
    "mobile",
    "tel",
    "telephone",
    "phone_number",
    "contact_phone",
}

_SENSITIVE_EMAIL_KEYS = {
    "email",
    "mail",
    "email_address",
    "contact_email",
}


def _mask_phone_match(match: Union[re.Match[str], Any]) -> str:
    if not match:
        return "[PHONE_MASKED]"
    raw = match.group(0) if hasattr(match, "group") else str(match)
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 11:
        # standard 11-digit Chinese phone: keep 3 prefix, 4 suffix
        clean_11 = digits[-11:]
        return f"{clean_11[:3]}****{clean_11[-4:]}"
    if len(digits) >= 7:
        return f"{digits[:2]}****{digits[-2:]}"
    return "****"


def _mask_email_match(match: Union[re.Match[str], Any]) -> str:
    if not match:
        return "[EMAIL_MASKED]"
    raw = match.group(0) if hasattr(match, "group") else str(match)
    parts = raw.split("@")
    if len(parts) == 2:
        user, domain = parts
        if len(user) <= 1:
            masked_user = "*..."
        elif len(user) <= 3:
            masked_user = f"{user[0]}***"
        else:
            masked_user = f"{user[0]}***{user[-1]}"
        return f"{masked_user}@{domain}"
    return "[EMAIL_MASKED]"


def _mask_name_string(name_str: str) -> str:
    s = name_str.strip()
    if not s:
        return s
    # Check if Chinese name
    if re.match(r"^[\u4e00-\u9fa5]{2,4}$", s):
        if len(s) == 2:
            return f"{s[0]}*"
        elif len(s) == 3:
            return f"{s[0]}*{s[-1]}"
        elif len(s) == 4:
            return f"{s[0]}**{s[-1]}"
    # English or western name with spaces
    tokens = s.split()
    if len(tokens) > 1:
        return " ".join(f"{t[0]}***" if len(t) > 1 else "*" for t in tokens)
    # General word
    if len(s) <= 2:
        return f"{s[0]}*"
    return f"{s[0]}***{s[-1]}"


def _mask_free_text(text: str) -> str:
    """Mask phones, emails, and id cards in general text."""
    res = _PHONE_PATTERN.sub(_mask_phone_match, text)
    res = _EMAIL_PATTERN.sub(_mask_email_match, res)
    res = _ID_CARD_PATTERN.sub(lambda m: f"{m.group(0)[:6]}********{m.group(0)[-4:]}", res)
    return res


def sanitize_trace_payload(data: Any) -> Any:
    """
    Desensitizes sensitive personal data (phone numbers, email addresses, names, ID cards)
    from payloads before writing them into trace logs or public state.
    Recursively processes dictionaries, lists, tuples, and strings, returning a sanitized copy.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return _mask_free_text(data)

    if isinstance(data, (int, float, bool)):
        return data

    if isinstance(data, Enum):
        return data.value

    if is_dataclass(data) and not isinstance(data, type):
        return sanitize_trace_payload(asdict(data))

    if hasattr(data, "to_dict") and callable(data.to_dict):
        return sanitize_trace_payload(data.to_dict())

    if isinstance(data, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if k_lower in _SENSITIVE_PHONE_KEYS and isinstance(v, str):
                m = _PHONE_PATTERN.search(v)
                sanitized[k] = _mask_phone_match(m) if m else _mask_phone_match(re.search(r"\d+", v))
            elif k_lower in _SENSITIVE_EMAIL_KEYS and isinstance(v, str):
                match = _EMAIL_PATTERN.search(v)
                sanitized[k] = _mask_email_match(match) if match else "[EMAIL_MASKED]"
            elif k_lower in _SENSITIVE_NAME_KEYS and isinstance(v, str):
                sanitized[k] = _mask_name_string(v)
            else:
                sanitized[k] = sanitize_trace_payload(v)
        return sanitized

    if isinstance(data, list):
        return [sanitize_trace_payload(item) for item in data]

    if isinstance(data, tuple):
        return tuple(sanitize_trace_payload(item) for item in data)

    if isinstance(data, set):
        return {sanitize_trace_payload(item) for item in data}

    return _mask_free_text(str(data))


class DeterministicCache:
    """
    In-memory deterministic cache keyed by f"{stage}:{fingerprint}".
    Provides read/write intermediate stage caching for pipeline stages.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    def _make_key(self, stage: str, fingerprint: str) -> str:
        return f"{stage}:{fingerprint}"

    def get(self, stage: str, fingerprint: str) -> Optional[Any]:
        """Retrieve a cached value, or None if not found."""
        return self._cache.get(self._make_key(stage, fingerprint))

    def set(self, stage: str, fingerprint: str, value: Any) -> None:
        """Store an intermediate stage value in the cache."""
        self._cache[self._make_key(stage, fingerprint)] = value

    def has(self, stage: str, fingerprint: str) -> bool:
        """Check whether a cached entry exists for the given stage and fingerprint."""
        return self._make_key(stage, fingerprint) in self._cache

    def delete(self, stage: str, fingerprint: str) -> bool:
        """Remove a cached entry if present."""
        return self._cache.pop(self._make_key(stage, fingerprint), None) is not None

    def clear(self) -> None:
        """Clear all entries in the cache."""
        self._cache.clear()

    def size(self) -> int:
        """Return the total number of cached entries."""
        return len(self._cache)

    def __contains__(self, item: Tuple[str, str]) -> bool:
        if isinstance(item, tuple) and len(item) == 2:
            return self.has(item[0], item[1])
        return False


__all__ = [
    "StageTrace",
    "RunContext",
    "compute_fingerprint",
    "sanitize_trace_payload",
    "DeterministicCache",
]
