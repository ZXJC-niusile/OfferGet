"""Shared local artifact and path helpers for OfferGet.

This module keeps filesystem side effects at the boundary while preserving the
existing CLI helper behavior, atomic writes, and output paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.atomic_writer import safe_save_file

PathLike = Union[str, os.PathLike[str]]


def ensure_parent(path: PathLike) -> Path:
    """Create and return the parent directory for an output path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def write_text_atomic(content: str, path: PathLike) -> str:
    """Write UTF-8 text atomically and return the target path."""
    target = ensure_parent(path)
    res = safe_save_file(target, content.encode("utf-8") if isinstance(content, str) else content)
    if not res.success:
        raise OSError(res.error_message or f"Failed to atomically write {target}")
    return str(res.final_path)


def write_json_atomic(data: Any, path: PathLike) -> str:
    """Serialize JSON using the repository defaults and write it atomically."""
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    target = ensure_parent(path)
    res = safe_save_file(target, payload)
    if not res.success:
        raise OSError(res.error_message or f"Failed to atomically write {target}")
    return str(res.final_path)


def _atomic_write(target: Path, payload: bytes) -> Path:
    """Replace a target through atomic shadow write delegation."""
    res = safe_save_file(target, payload)
    if not res.success:
        raise OSError(res.error_message or f"Failed to atomically write {target}")
    return res.final_path


def require_file(path: PathLike, label: str = "File") -> Path:
    """Resolve an existing regular file or raise a stable FileNotFoundError."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return target.resolve()


def sha256_file(path: Union[str, Path]) -> str:
    """Computes SHA-256 hex digest of a file in 1MB chunks."""
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_artifacts(paths: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
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


@dataclass
class ArtifactManifest:
    """Standardized metadata manifest for generated artifacts (reports, resumes, exports)."""
    path: str
    format: str
    content_hash: str
    schema_version: str = "v1"
    page_count: Optional[int] = None
    status: str = "completed"
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    findings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


__all__ = [
    "PathLike",
    "ensure_parent",
    "write_text_atomic",
    "write_json_atomic",
    "require_file",
    "sha256_file",
    "inspect_artifacts",
    "ArtifactManifest",
]
