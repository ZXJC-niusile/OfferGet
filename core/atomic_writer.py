"""OfferGet Atomic Shadow Writer (atomic_writer.py)
===================================================
Robust atomic file persistence designed to gracefully eliminate Windows
`PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问`
exceptions caused by PDF viewers (WPS Office, Adobe Acrobat, Edge/Chrome)
or system indexers/antivirus scanners holding exclusive file locks.

Architecture:
1. Atomic staged write: content is written to a same-directory temporary file
   (`.tmp_atomic_*`) to ensure single-volume atomic `os.replace`.
2. Micro-backoff retries: handles transient locks from background indexers.
3. Resilient shadow degradation: if destination remains locked by an external
   viewer, automatically downgrades and persists to a timestamped or
   versioned shadow copy (`{stem}_shadow_{timestamp}.pdf`) without crashing.
"""

from __future__ import annotations

import errno
import logging
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SafeSaveResult:
    """Encapsulates the outcome of a safe file save operation."""

    success: bool
    final_path: Path
    is_shadow: bool
    original_path: Path
    error_message: Optional[str] = None
    notice: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.final_path, Path):
            self.final_path = Path(self.final_path)
        if not isinstance(self.original_path, Path):
            self.original_path = Path(self.original_path)


def is_sharing_violation_error(exc: Optional[BaseException]) -> bool:
    """Determines whether an exception represents a Windows sharing violation or file lock."""
    if exc is None:
        return False
    if not isinstance(exc, (PermissionError, OSError)):
        return False

    winerror = getattr(exc, "winerror", None)
    # 32: ERROR_SHARING_VIOLATION
    # 33: ERROR_LOCK_VIOLATION
    # 5:  ERROR_ACCESS_DENIED (frequently reported by MoveFileEx/os.replace when destination is open)
    if winerror in (32, 33, 5):
        return True

    err_no = getattr(exc, "errno", None)
    if err_no in (errno.EACCES, errno.EBUSY):
        return True

    msg = str(exc)
    if any(
        kw in msg
        for kw in (
            "WinError 32",
            "WinError 33",
            "WinError 5",
            "ERROR_SHARING_VIOLATION",
            "另一个程序正在使用此文件",
            "Sharing violation",
            "locked by another process",
        )
    ):
        return True

    return isinstance(exc, PermissionError)


def is_file_locked(path: Path | str) -> bool:
    """Checks whether a target file exists and is locked by an external application."""
    p = Path(path)
    if not p.exists():
        return False

    if sys.platform == "win32":
        try:
            import ctypes

            GENERIC_WRITE = 0x40000000
            OPEN_EXISTING = 3
            # Attempt to open with exclusive write access (dwShareMode = 0)
            handle = ctypes.windll.kernel32.CreateFileW(
                str(p.resolve()),
                GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None,
            )
            # INVALID_HANDLE_VALUE is -1 or 0xFFFFFFFF (or 4294967295 unsigned)
            if handle in (-1, 0xFFFFFFFF, 4294967295):
                err = ctypes.GetLastError()
                if err in (32, 33, 5):
                    return True
                return True
            ctypes.windll.kernel32.CloseHandle(handle)
            return False
        except Exception:
            pass

    # Cross-platform / fallback check
    try:
        with open(p, "a+b"):
            pass
        return False
    except (PermissionError, OSError):
        return True


def generate_shadow_path(dest_path: Path | str, pattern: Optional[str] = None) -> Path:
    """Generates an available, uncolliding shadow copy path."""
    p = Path(dest_path).resolve()
    parent = p.parent
    stem = p.stem
    ext = p.suffix

    if pattern:
        if "{N}" in pattern or "{n}" in pattern:
            counter = 1
            while True:
                name = (
                    pattern.replace("{stem}", stem)
                    .replace("{N}", str(counter))
                    .replace("{n}", str(counter))
                    .replace("{ext}", ext)
                )
                candidate = parent / name
                if not candidate.exists() and not is_file_locked(candidate):
                    return candidate
                counter += 1
        elif "{timestamp}" in pattern:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            candidate = parent / pattern.replace("{stem}", stem).replace("{timestamp}", timestamp).replace("{ext}", ext)
            if not candidate.exists() and not is_file_locked(candidate):
                return candidate
            counter = 1
            while True:
                candidate = parent / f"{candidate.stem}_{counter}{ext}"
                if not candidate.exists() and not is_file_locked(candidate):
                    return candidate
                counter += 1

    # Standard default pattern: {stem}_shadow_{timestamp}{ext}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = parent / f"{stem}_shadow_{timestamp}{ext}"
    if not candidate.exists() and not is_file_locked(candidate):
        return candidate

    counter = 1
    while True:
        candidate = parent / f"{stem}_shadow_{timestamp}_{counter}{ext}"
        if not candidate.exists() and not is_file_locked(candidate):
            return candidate
        counter += 1


def safe_save_file(
    dest_path: Path | str,
    content: bytes | str | Path,
    allow_shadow: bool = True,
    max_retries: int = 3,
    retry_delay: float = 0.1,
    shadow_pattern: Optional[str] = None,
) -> SafeSaveResult:
    """Atomically saves content or copies/moves a source file to destination.

    Parameters:
        dest_path: Target destination path.
        content: Path (source file to copy/move) or bytes/str (payload to write).
        allow_shadow: If True, falls back to a timestamped shadow copy if locked.
        max_retries: Number of short micro-backoff retries before shadow fallback.
        retry_delay: Base delay in seconds between retries.
        shadow_pattern: Optional naming template, e.g. '{stem}_v{N}{ext}'.

    Returns:
        SafeSaveResult with success status, final path, shadow flag, and notice.
    """
    target = Path(dest_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Prepare atomic temporary staging file in the target directory (same volume)
    temp_atomic = target.parent / f".tmp_atomic_{uuid.uuid4().hex[:12]}_{target.name}"

    try:
        # 1. Populate staging file
        if isinstance(content, Path):
            src = content.resolve()
            if not src.exists():
                return SafeSaveResult(
                    success=False,
                    final_path=target,
                    is_shadow=False,
                    original_path=target,
                    error_message=f"Source path does not exist: {src}",
                    notice=f"Source file not found: {src}",
                )
            if src == target:
                return SafeSaveResult(
                    success=True,
                    final_path=target,
                    is_shadow=False,
                    original_path=target,
                    error_message=None,
                    notice=f"Source and destination are identical: {target.name}",
                )
            shutil.copy2(src, temp_atomic)
        elif isinstance(content, (bytes, bytearray)):
            temp_atomic.write_bytes(content)
        elif isinstance(content, str):
            temp_atomic.write_text(content, encoding="utf-8")
        else:
            temp_atomic.write_bytes(bytes(content))

        # 2. Attempt atomic replacement with micro-backoff retries
        last_error: Optional[BaseException] = None
        replaced = False

        for attempt in range(max(1, max_retries)):
            try:
                os.replace(temp_atomic, target)
                replaced = True
                break
            except (PermissionError, OSError) as e:
                last_error = e
                if is_sharing_violation_error(e):
                    if attempt < max_retries - 1 and retry_delay > 0:
                        time.sleep(retry_delay * (1.5 ** attempt))
                else:
                    break

        if replaced:
            return SafeSaveResult(
                success=True,
                final_path=target,
                is_shadow=False,
                original_path=target,
                error_message=None,
                notice=f"File saved successfully to {target.name}",
            )

        # 3. Handle lock / sharing violation: fallback to shadow copy
        if allow_shadow and is_sharing_violation_error(last_error):
            shadow_saved = False
            chosen_shadow_path = target
            for _ in range(5):
                chosen_shadow_path = generate_shadow_path(target, pattern=shadow_pattern)
                try:
                    os.replace(temp_atomic, chosen_shadow_path)
                    shadow_saved = True
                    break
                except (PermissionError, OSError):
                    time.sleep(0.05)

            if shadow_saved:
                notice = (
                    f"[WinError 32] 目标文件被外部程序（WPS/Adobe）独占占用，已自动降级保存至影子副本: {chosen_shadow_path.name}"
                )
                logger.warning(notice)
                return SafeSaveResult(
                    success=True,
                    final_path=chosen_shadow_path,
                    is_shadow=True,
                    original_path=target,
                    error_message=str(last_error) if last_error else None,
                    notice=notice,
                )

        # 4. If shadow not allowed or replacement completely failed
        notice = (
            f"[WinError 32] 目标文件被外部程序独占占用，保存失败（未允许影子副本）: {target.name}"
            if is_sharing_violation_error(last_error)
            else f"Save failed for {target.name}: {last_error}"
        )
        return SafeSaveResult(
            success=False,
            final_path=target,
            is_shadow=False,
            original_path=target,
            error_message=str(last_error) if last_error else "Unknown error during save",
            notice=notice,
        )

    finally:
        if temp_atomic.exists():
            try:
                temp_atomic.unlink(missing_ok=True)
            except Exception:
                pass


def atomic_write(
    dest_path: Path | str,
    data: bytes | str,
    allow_shadow: bool = True,
    **kwargs: Any,
) -> SafeSaveResult:
    """Convenience helper for atomic writing bytes or string data."""
    return safe_save_file(
        dest_path=dest_path,
        content=data,
        allow_shadow=allow_shadow,
        **kwargs,
    )


__all__ = [
    "SafeSaveResult",
    "is_file_locked",
    "is_sharing_violation_error",
    "generate_shadow_path",
    "safe_save_file",
    "atomic_write",
]
