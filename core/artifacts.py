"""Shared local artifact and path helpers for OfferGet.

This module keeps filesystem side effects at the boundary while preserving the
existing CLI helper behavior, atomic writes, and output paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Union

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
        raise OSError(f"Failed to atomically write {target}: {res.error_message or 'unknown error'}")
    return str(res.final_path)


def write_json_atomic(data: Any, path: PathLike, *, allow_shadow: bool = True) -> str:
    """Serialize JSON using the repository defaults and write it atomically."""
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    target = ensure_parent(path)
    res = safe_save_file(target, payload, allow_shadow=allow_shadow)
    if not res.success:
        raise OSError(f"Failed to atomically write {target}: {res.error_message or 'unknown error'}")
    return str(res.final_path)


def require_file(path: PathLike, label: str = "File") -> Path:
    """Resolve an existing regular file or raise a stable FileNotFoundError."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return target.resolve()


__all__ = [
    "PathLike",
    "ensure_parent",
    "write_text_atomic",
    "write_json_atomic",
    "require_file",
]
