"""OfferGet QA Common Utilities.

Shared helpers for layout QA suites across PDF, DOCX, LaTeX, Typst and Markdown themes.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List


def squash(text: Any) -> str:
    """Normalize and strip whitespace, markdown bold formatting, and invisible characters for robust text assertions."""
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    return re.sub(r"\s+", "", normalized).replace("**", "").replace("\u200b", "")


def build_source_manifest(root: Path, sources: List[str]) -> Dict[str, Dict[str, str]]:
    """Generate SHA256 and Git blob SHA1 signatures for test-reproducibility manifests."""
    manifest = {}
    for source in sources:
        data = (root / source).read_bytes()
        manifest[source] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
        }
    return manifest
