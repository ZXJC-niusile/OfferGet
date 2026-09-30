"""Canonical Ingress and compatibility gateway for Job Description processing.

The canonical typed models live in ``modules.jd_analyst.models``.
Legacy dictionary converters are isolated in ``adapters.jd_legacy`` and re-exported here
for 100% backwards compatibility.
"""

from __future__ import annotations

from typing import Any

from adapters.jd_legacy import (
    ROLE_TAXONOMIES,
    DecodedJDCompat,
    _legacy_to_canonical,
    canonical_to_legacy,
    classify_role_taxonomy,
    decode_legacy,
    match_legacy,
    profile_to_canonical,
)
from modules.jd_analyst.decoder import JDDecoder
from modules.jd_analyst.models import DecodedJD


def to_canonical(decoded: Any) -> DecodedJD:
    """Universal ingress gateway returning the SSOT canonical DecodedJD.

    Accepts DecodedJD, DecodedJDCompat, legacy dictionary, Path, or raw JD text.
    """
    if isinstance(decoded, DecodedJDCompat):
        return decoded.canonical
    if isinstance(decoded, DecodedJD):
        return decoded
    if isinstance(decoded, str):
        if not decoded.strip():
            return DecodedJD(
                raw_text=decoded,
                job_title="未指定职位",
                company_or_dept="未指定公司",
                clean_text=decoded.strip(),
            )
        return JDDecoder().decode(decoded)
    if hasattr(decoded, "read_text"):  # pathlib.Path
        text = decoded.read_text(encoding="utf-8")
        if not text.strip():
            return DecodedJD(
                raw_text=text,
                job_title="未指定职位",
                company_or_dept="未指定公司",
                clean_text=text.strip(),
            )
        return JDDecoder().decode(text)
    if isinstance(decoded, dict):
        if not decoded:
            return DecodedJD(
                raw_text="",
                job_title="未指定职位",
                company_or_dept="未指定公司",
                clean_text="",
            )
        return _legacy_to_canonical(decoded)
    raise TypeError(f"Unsupported decoded JD type: {type(decoded).__name__}")


match_profile_to_jd = match_legacy

__all__ = [
    "to_canonical",
    "DecodedJDCompat",
    "ROLE_TAXONOMIES",
    "classify_role_taxonomy",
    "canonical_to_legacy",
    "decode_legacy",
    "profile_to_canonical",
    "match_legacy",
    "match_profile_to_jd",
]
