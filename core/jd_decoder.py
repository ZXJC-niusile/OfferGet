"""Backward-compatible JD decoder facade.

The canonical implementation is ``modules.jd_analyst.decoder.JDDecoder``.
This module preserves the historical ``decode_jd`` and
``classify_jd_role_taxonomy`` imports used by OfferGet callers.
"""

from __future__ import annotations

from typing import Any, Dict

from core.jd_compat import ROLE_TAXONOMIES, classify_role_taxonomy, decode_legacy

# Kept for callers that imported the old taxonomy constant directly.
TECH_ROLE_TAXONOMY: Dict[str, Dict[str, Any]] = ROLE_TAXONOMIES


def classify_jd_role_taxonomy(jd_text: str) -> Dict[str, Any]:
    """Return the role taxonomy selected by the canonical compatibility layer."""
    return classify_role_taxonomy(jd_text)


def decode_jd(jd_text: str) -> Dict[str, Any]:
    """Decode a JD through the canonical typed analyzer.

    The returned object is a dictionary-compatible view for existing CLI,
    report, and ATS consumers.  New code should use ``JDDecoder`` directly.
    """
    return decode_legacy(jd_text)


__all__ = ["TECH_ROLE_TAXONOMY", "classify_jd_role_taxonomy", "decode_jd"]
