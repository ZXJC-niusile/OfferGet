"""Unit tests for core/atomic_writer.py and WinError 32 shadow mitigation.
========================================================================
Validates atomic persistence, exclusive lock handling, transient retries,
shadow copy degradation, and pipeline resilience across BrowserRenderer
and AcademicExporter.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.atomic_writer import (
    SafeSaveResult,
    atomic_write,
    generate_shadow_path,
    is_file_locked,
    is_sharing_violation_error,
    safe_save_file,
)
from ApexResume.core.render import BrowserRenderer
from core.academic_exporter import AcademicExporter


@pytest.fixture
def tmp_path():
    """Isolated temporary directory fixture avoiding Windows pytest-of-* permissions."""
    with tempfile.TemporaryDirectory(prefix="atomic_test_") as tmp_dir:
        yield Path(tmp_dir)



# ---------------------------------------------------------------------------
# Helpers for Windows Exclusive Locking
# ---------------------------------------------------------------------------

def _acquire_windows_lock(file_path: Path):
    """Acquires a WPS/Adobe Acrobat-style sharing violation lock on Windows.

    Returns the open handle or None if not on Windows.
    """
    if sys.platform != "win32":
        return None

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3

    handle = ctypes.windll.kernel32.CreateFileW(
        str(file_path.resolve()),
        GENERIC_READ,
        FILE_SHARE_READ,  # No FILE_SHARE_WRITE and no FILE_SHARE_DELETE
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle in (-1, 0xFFFFFFFF, 4294967295):
        raise OSError(f"Failed to acquire test lock on {file_path}")
    return handle


def _release_windows_lock(handle):
    """Releases a lock handle acquired via CreateFileW."""
    if handle and sys.platform == "win32":
        ctypes.windll.kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# Test Suite 1: Normal Atomic Write & Fidelity
# ---------------------------------------------------------------------------

def test_atomic_write_bytes(tmp_path: Path):
    """Test raw binary atomic write."""
    dest = tmp_path / "sample.pdf"
    content = b"%PDF-1.4\n%Binary test payload \x00\x01\x02\xFF"

    res = atomic_write(dest, content)

    assert res.success is True
    assert res.is_shadow is False
    assert res.final_path == dest.resolve()
    assert res.original_path == dest.resolve()
    assert res.error_message is None
    assert dest.exists()
    assert dest.read_bytes() == content


def test_atomic_write_str(tmp_path: Path):
    """Test UTF-8 text atomic write."""
    dest = tmp_path / "resume.html"
    content = "<html><body><h1>候选人简历 - 算法工程师</h1></body></html>"

    res = atomic_write(dest, content)

    assert res.success is True
    assert res.is_shadow is False
    assert res.final_path == dest.resolve()
    assert dest.read_text(encoding="utf-8") == content


def test_safe_save_file_path_source(tmp_path: Path):
    """Test safe_save_file when content is a Path (file copy/move)."""
    src = tmp_path / "source.pdf"
    src.write_bytes(b"%PDF-source-data-12345")
    dest = tmp_path / "subfolder" / "dest.pdf"

    res = safe_save_file(dest, src)

    assert res.success is True
    assert res.is_shadow is False
    assert res.final_path == dest.resolve()
    assert dest.exists()
    assert dest.read_bytes() == b"%PDF-source-data-12345"
    # Source file should still exist
    assert src.exists()


def test_safe_save_file_nonexistent_source(tmp_path: Path):
    """Test safe_save_file fails gracefully when source path does not exist."""
    src = tmp_path / "does_not_exist.pdf"
    dest = tmp_path / "dest.pdf"

    res = safe_save_file(dest, src)

    assert res.success is False
    assert "does not exist" in str(res.error_message)


def test_safe_save_file_same_path(tmp_path: Path):
    """Test safe_save_file when source and destination are the exact same path."""
    dest = tmp_path / "same.pdf"
    dest.write_bytes(b"content")

    res = safe_save_file(dest, dest)

    assert res.success is True
    assert res.final_path == dest.resolve()
    assert dest.read_bytes() == b"content"


# ---------------------------------------------------------------------------
# Test Suite 2: File Lock Detection (`is_file_locked`)
# ---------------------------------------------------------------------------

def test_is_file_locked_nonexistent(tmp_path: Path):
    """Non-existent file should report not locked."""
    assert is_file_locked(tmp_path / "phantom.pdf") is False


def test_is_file_locked_normal_file(tmp_path: Path):
    """Standard unheld file should report not locked."""
    p = tmp_path / "normal.pdf"
    p.write_bytes(b"normal")
    assert is_file_locked(p) is False


def test_is_file_locked_windows_exclusive(tmp_path: Path):
    """On Windows, a file held with WPS/Adobe sharing restrictions reports locked."""
    if sys.platform != "win32":
        pytest.skip("Windows-specific ctypes lock test")

    target = tmp_path / "locked_target.pdf"
    target.write_bytes(b"initial")

    handle = _acquire_windows_lock(target)
    try:
        assert is_file_locked(target) is True
    finally:
        _release_windows_lock(handle)

    # Once unlocked, is_file_locked should immediately return False
    assert is_file_locked(target) is False


def test_is_sharing_violation_error():
    """Validates sharing violation classification across platforms and error types."""
    err32 = OSError()
    err32.winerror = 32
    assert is_sharing_violation_error(err32) is True

    err5 = OSError()
    err5.winerror = 5
    assert is_sharing_violation_error(err5) is True

    perm_err = PermissionError("[WinError 32] 另一个程序正在使用此文件，进程无法访问。")
    assert is_sharing_violation_error(perm_err) is True

    perm_generic = PermissionError("Permission denied")
    assert is_sharing_violation_error(perm_generic) is True

    val_err = ValueError("Invalid input")
    assert is_sharing_violation_error(val_err) is False


# ---------------------------------------------------------------------------
# Test Suite 3: Shadow Degradation on Windows Lock / Mock Lock
# ---------------------------------------------------------------------------

def test_safe_save_locked_windows_real(tmp_path: Path):
    """Real Windows test: when dest is held by external app, automatically falls back to shadow copy."""
    if sys.platform != "win32":
        pytest.skip("Windows-specific ctypes lock test")

    dest = tmp_path / "resume.pdf"
    dest.write_bytes(b"%PDF-original-unmodified")

    new_content = b"%PDF-new-version-rendered"

    # Acquire lock simulating WPS or Acrobat holding the PDF
    handle = _acquire_windows_lock(dest)
    try:
        res = safe_save_file(
            dest_path=dest,
            content=new_content,
            allow_shadow=True,
            max_retries=2,
            retry_delay=0.02,
        )

        assert res.success is True
        assert res.is_shadow is True
        assert res.original_path == dest.resolve()
        assert res.final_path != dest.resolve()
        assert res.final_path.exists() is True
        assert res.final_path.read_bytes() == new_content

        # Verify notice contains WinError 32 notification
        assert "[WinError 32]" in res.notice
        assert "影子副本" in res.notice
        assert res.final_path.name in res.notice

        # Verify original locked file was not corrupted
        assert dest.read_bytes() == b"%PDF-original-unmodified"
    finally:
        _release_windows_lock(handle)


def test_safe_save_locked_mocked_winerror_32(tmp_path: Path):
    """Simulates WinError 32 exception during os.replace to test shadow fallback logic."""
    dest = tmp_path / "output.pdf"
    dest.write_bytes(b"initial")

    real_replace = os.replace

    def mock_replace(src, dst):
        if Path(dst).resolve() == dest.resolve():
            err = PermissionError(13, "[WinError 32] 另一个程序正在使用此文件，进程无法访问。")
            err.winerror = 32
            raise err
        return real_replace(src, dst)

    with patch("os.replace", side_effect=mock_replace):
        res = safe_save_file(
            dest_path=dest,
            content=b"new-content-under-lock",
            allow_shadow=True,
            max_retries=2,
            retry_delay=0.01,
        )

    assert res.success is True
    assert res.is_shadow is True
    assert res.final_path != dest.resolve()
    assert "_shadow_" in res.final_path.name
    assert res.final_path.read_bytes() == b"new-content-under-lock"
    assert "[WinError 32]" in res.notice


def test_safe_save_locked_no_shadow_allowed(tmp_path: Path):
    """When allow_shadow=False and destination is locked, returns clean failure without crash."""
    dest = tmp_path / "rigid.pdf"
    dest.write_bytes(b"initial")

    def mock_replace(src, dst):
        err = PermissionError(13, "[WinError 32] 另一个程序正在使用此文件，进程无法访问。")
        err.winerror = 32
        raise err

    with patch("os.replace", side_effect=mock_replace):
        res = safe_save_file(
            dest_path=dest,
            content=b"new-content",
            allow_shadow=False,
            max_retries=2,
            retry_delay=0.01,
        )

    assert res.success is False
    assert res.is_shadow is False
    assert res.final_path == dest.resolve()
    assert "未允许影子副本" in res.notice
    assert res.error_message is not None


# ---------------------------------------------------------------------------
# Test Suite 4: Retry Mechanism for Transient Locks
# ---------------------------------------------------------------------------

def test_retry_mechanism_recovers_after_transient_lock(tmp_path: Path):
    """Test transient lock (e.g. anti-virus scan) unlocking after 1 failed attempt."""
    dest = tmp_path / "transient.pdf"
    dest.write_bytes(b"initial")

    real_replace = os.replace
    attempts = [0]

    def mock_replace(src, dst):
        if Path(dst).resolve() == dest.resolve():
            attempts[0] += 1
            if attempts[0] == 1:
                # First attempt fails with WinError 32
                err = PermissionError(13, "WinError 32: locked")
                err.winerror = 32
                raise err
        return real_replace(src, dst)

    with patch("os.replace", side_effect=mock_replace):
        res = safe_save_file(
            dest_path=dest,
            content=b"recovered-content",
            allow_shadow=True,
            max_retries=3,
            retry_delay=0.01,
        )

    assert res.success is True
    assert res.is_shadow is False
    assert res.final_path == dest.resolve()
    assert dest.read_bytes() == b"recovered-content"
    assert attempts[0] == 2


# ---------------------------------------------------------------------------
# Test Suite 5: Shadow Naming Rules & Formats
# ---------------------------------------------------------------------------

def test_generate_shadow_path_default_format(tmp_path: Path):
    """Default shadow format contains timestamp."""
    p = tmp_path / "resume.pdf"
    shadow = generate_shadow_path(p)

    assert shadow.parent.resolve() == p.parent.resolve()
    assert shadow.suffix == ".pdf"
    assert shadow.stem.startswith("resume_shadow_")


def test_generate_shadow_path_versioned_pattern(tmp_path: Path):
    """Custom format using {stem}_v{N}{ext}."""
    p = tmp_path / "resume.pdf"
    shadow1 = generate_shadow_path(p, pattern="{stem}_v{N}{ext}")
    assert shadow1.name == "resume_v1.pdf"

    # Pre-create resume_v1.pdf
    shadow1.write_bytes(b"v1")
    shadow2 = generate_shadow_path(p, pattern="{stem}_v{N}{ext}")
    assert shadow2.name == "resume_v2.pdf"


def test_generate_shadow_path_collision_avoidance(tmp_path: Path):
    """If default timestamp shadow already exists, appends counter suffix."""
    p = tmp_path / "sample.pdf"
    first = generate_shadow_path(p)
    first.write_bytes(b"first")

    # Generate again within same second
    second = generate_shadow_path(p)
    assert second != first
    assert second.exists() is False


# ---------------------------------------------------------------------------
# Test Suite 6: BrowserRenderer Resilience Under Lock
# ---------------------------------------------------------------------------

def test_browser_renderer_resilient_under_lock(tmp_path: Path):
    """Validates that BrowserRenderer saves to shadow copy and updates message when dest is locked."""
    renderer = BrowserRenderer(browser_path="mock_chrome")

    html_file = tmp_path / "input.html"
    html_file.write_text("<html><body>Resume</body></html>", encoding="utf-8")

    locked_pdf = tmp_path / "target.pdf"
    locked_pdf.write_bytes(b"existing-pdf")

    shadow_pdf = tmp_path / "target_shadow_20260930_999999.pdf"

    # Mock subprocess.run so Chrome writes rendered.pdf to the temp directory
    def fake_subprocess_run(cmd, **kwargs):
        # cmd: [... '--print-to-pdf=PATH', file_url]
        for arg in cmd:
            if arg.startswith("--print-to-pdf="):
                out_path = Path(arg.split("=", 1)[1])
                out_path.write_bytes(b"%PDF-1.4\n/Type /Page\n rendered bytes")
        return MagicMock(returncode=0, stderr="")

    mock_shadow_result = SafeSaveResult(
        success=True,
        final_path=shadow_pdf,
        is_shadow=True,
        original_path=locked_pdf,
        error_message=None,
        notice=f"Saved to shadow copy: {shadow_pdf.name}",
    )

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("core.atomic_writer.safe_save_file", return_value=mock_shadow_result):

        success, pages, msg = renderer.render_pdf(html_file, locked_pdf)

    assert success is True
    assert pages >= 1
    assert "Saved to shadow copy: target_shadow_20260930_999999.pdf due to lock" in msg


# ---------------------------------------------------------------------------
# Test Suite 7: AcademicExporter Resilience Under Lock
# ---------------------------------------------------------------------------

def test_academic_exporter_compile_typst_under_lock(tmp_path: Path):
    """Validates that AcademicExporter.compile_typst does not crash when output is locked."""
    exporter = AcademicExporter()

    typ_file = tmp_path / "resume.typ"
    typ_file.write_text("= Resume", encoding="utf-8")

    locked_pdf = tmp_path / "academic.pdf"
    locked_pdf.write_bytes(b"locked-content")

    # Mock typst.compile to simulate compiling to temp_pdf
    mock_typst = MagicMock()
    def fake_typst_compile(src, output):
        Path(output).write_bytes(b"%PDF-typst-compiled-data")

    mock_typst.compile = fake_typst_compile

    # Mock safe_save_file to return shadow result
    shadow_pdf = tmp_path / "academic_shadow_20260930_123456.pdf"
    mock_shadow_result = SafeSaveResult(
        success=True,
        final_path=shadow_pdf,
        is_shadow=True,
        original_path=locked_pdf,
        error_message=None,
        notice=f"Saved to shadow: {shadow_pdf.name}",
    )

    with patch.dict(sys.modules, {"typst": mock_typst}), \
         patch("core.atomic_writer.safe_save_file", return_value=mock_shadow_result):

        compiled = exporter.compile_typst(typ_file, locked_pdf)

    assert compiled is True


def test_academic_exporter_compile_latex_under_lock(tmp_path: Path):
    """Validates that AcademicExporter.compile_latex migrates output via safe_save_file."""
    exporter = AcademicExporter()

    tex_file = tmp_path / "resume.tex"
    tex_file.write_text(r"\documentclass{article}\begin{document}Hi\end{document}", encoding="utf-8")

    locked_pdf = tmp_path / "latex.pdf"
    locked_pdf.write_bytes(b"locked-latex")

    def fake_subprocess_run(cmd, **kwargs):
        # Find -output-directory
        for arg in cmd:
            if arg.startswith("-output-directory="):
                out_dir = Path(arg.split("=", 1)[1])
                (out_dir / f"{tex_file.stem}.pdf").write_bytes(b"%PDF-latex-compiled")
        return MagicMock(returncode=0)

    shadow_pdf = tmp_path / "latex_shadow_20260930_888888.pdf"
    mock_shadow_result = SafeSaveResult(
        success=True,
        final_path=shadow_pdf,
        is_shadow=True,
        original_path=locked_pdf,
        error_message=None,
        notice=f"Saved to shadow: {shadow_pdf.name}",
    )

    with patch("shutil.which", return_value="/usr/bin/xelatex"), \
         patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("core.atomic_writer.safe_save_file", return_value=mock_shadow_result):

        compiled = exporter.compile_latex(tex_file, locked_pdf)

    assert compiled is True
