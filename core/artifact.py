"""Small deterministic helpers for generated-file provenance."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable


def sha256_file(path: str | Path) -> str:
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_artifacts(paths: Dict[str, str]) -> tuple[Dict[str, str], Dict[str, str]]:
    """Return per-artifact status and hash without hiding missing files."""
    statuses: Dict[str, str] = {}
    hashes: Dict[str, str] = {}
    for name, raw_path in paths.items():
        path = Path(raw_path)
        if not path.is_file():
            statuses[name] = "missing"
            continue
        try:
            hashes[name] = sha256_file(path)
            statuses[name] = "present"
        except OSError:
            statuses[name] = "unreadable"
    return statuses, hashes
