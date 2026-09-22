"""Legacy boundary adapter for JD decoding.

The canonical implementation is ``modules.jd_analyst.decoder.JDDecoder``
and the unified object schema is ``modules.jd_analyst.models.DecodedJD``.
This module acts as an ingress/egress boundary adapter preserving historical
``decode_jd``, ``to_canonical``, and ``classify_jd_role_taxonomy`` imports.
"""

from __future__ import annotations

from typing import Any, Dict

from core.jd_compat import (
    ROLE_TAXONOMIES,
    classify_role_taxonomy,
    decode_legacy,
    to_canonical,
)

# Kept for callers that imported the old taxonomy constant directly.
TECH_ROLE_TAXONOMY: Dict[str, Dict[str, Any]] = ROLE_TAXONOMIES


def classify_jd_role_taxonomy(jd_text: str) -> Dict[str, Any]:
    """Return the role taxonomy selected by the canonical compatibility layer."""
    return classify_role_taxonomy(jd_text)


def decode_jd(jd_text: str) -> Dict[str, Any]:
    """Decode a JD into a dictionary-compatible view for CLI/legacy presentation."""
    return decode_legacy(jd_text)


__all__ = [
    "TECH_ROLE_TAXONOMY",
    "classify_jd_role_taxonomy",
    "decode_jd",
    "to_canonical",
]
