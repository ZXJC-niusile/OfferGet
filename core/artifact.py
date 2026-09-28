"""Backward-compatibility re-export for artifact inspection helpers.

Canonical implementation lives in `core.artifacts`.
"""

from __future__ import annotations

from core.artifacts import inspect_artifacts, sha256_file

__all__ = [
    "sha256_file",
    "inspect_artifacts",
]
