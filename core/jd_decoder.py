"""Legacy boundary aliases for JD decoding."""

from __future__ import annotations

from core.jd_compat import (
    ROLE_TAXONOMIES as TECH_ROLE_TAXONOMY,
    classify_role_taxonomy as classify_jd_role_taxonomy,
    decode_legacy as decode_jd,
    to_canonical,
)

__all__ = [
    "TECH_ROLE_TAXONOMY",
    "classify_jd_role_taxonomy",
    "decode_jd",
    "to_canonical",
]
