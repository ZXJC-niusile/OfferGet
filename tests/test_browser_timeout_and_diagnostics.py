"""
Tests for Headless Browser Timeout Hardening and Diagnostics (tests/test_browser_timeout_and_diagnostics.py)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.browser_renderer import (
    BrowserRenderer,
    RenderResult,
    _kill_process_tree,
    _safe_decode,
)


class TestBrowserTimeoutAndDiagnostics(unittest.TestCase):
    """Verifies timeout decoding, process-tree cleanup, finite retry, and diagnostic payloads."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_browser_timeout_"))
        self.html_file = self.test_dir / "resume.html"
        self.html_file.write_text("<html><body>Resume Content</body></html>", encoding="utf-8")
        self.pdf_file = self.test_dir / "resume.pdf"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_safe_decode_handles_all_types(self):
        """Verifies _safe_decode correctly transforms bytes, str, None, and corrupted encodings."""
        self.assertEqual(_safe_decode(None), "")
        self.assertEqual(_safe_decode("hello world"), "hello world")
        self.assertEqual(_safe_decode(b"binary hello"), "binary hello")
        self.assertEqual(_safe_decode(b"UTF-8: \xe6\xb5\x8b\xe8\xaf\x95"), "UTF-8: 测试")
        # Non-decodable bytes replaced without crash
        corrupted = b"\xff\xfe\x00\x88 invalid"
        decoded = _safe_decode(corrupted)
        self.assertIsInstance(decoded, str)
        self.assertTrue(len(decoded) > 0)

    def test_kill_process_tree_noop_on_invalid_pid(self):
        """Invalid PIDs (None, 0, -1) must return safely without error."""
        _kill_process_tree(None)
        _kill_process_tree(0)
        _kill_process_tree(-1)

    @patch("subprocess.run")
    def test_kill_process_tree_windows_targeted_pid(self, mock_run):
        """On Windows, kill_process_tree executes targeted taskkill with /F /T /PID."""
        with patch("sys.platform", "win32"):
            _kill_process_tree(9988)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertEqual(args, ["taskkill", "/F", "/T", "/PID", "9988"])

    def test_kill_process_tree_posix_process_group(self):
        """On POSIX systems, kill_process_tree signals the process group via os.killpg."""
        import signal
        mock_killpg = MagicMock()
        mock_sigkill = getattr(signal, "SIGKILL", 9)
        with patch("sys.platform", "linux"), \
             patch("os.killpg", mock_killpg, create=True):
            _kill_process_tree(5678)
            mock_killpg.assert_called_once_with(5678, mock_sigkill)

    def test_render_pdf_timeout_triggers_retry_and_succeeds(self):
        """Verifies that transient timeout on attempt 1 triggers retry with fresh user-data-dir and succeeds on attempt 2."""
        renderer = BrowserRenderer(browser_path="mock_browser")
        user_data_dirs = []
        call_count = 0

        def fake_run_subprocess(cmd, timeout_seconds):
            nonlocal call_count
            call_count += 1
            # Extract user-data-dir and output path
            for arg in cmd:
                if arg.startswith("--user-data-dir="):
                    user_data_dirs.append(arg.split("=", 1)[1])
                if arg.startswith("--print-to-pdf="):
                    pdf_out = Path(arg.split("=", 1)[1])

            if call_count == 1:
                # First attempt times out
                raise subprocess.TimeoutExpired(cmd, timeout_seconds, output=b"", stderr=b"hang")
            else:
                # Second attempt succeeds
                pdf_out.write_bytes(b"%PDF-1.4\n/Type /Page\nrendered bytes")
                return 0, "ok", "", 1.2

        with patch.object(BrowserRenderer, "_run_subprocess", side_effect=fake_run_subprocess):
            res = renderer.render_pdf(self.html_file, self.pdf_file, timeout_seconds=10, max_retries=1)

        self.assertTrue(res.ok)
        self.assertEqual(call_count, 2)
        self.assertEqual(len(user_data_dirs), 2)
        # Ensure fresh separate user-data-dirs were used across retry
        self.assertNotEqual(user_data_dirs[0], user_data_dirs[1])
        self.assertTrue("initial_render" in user_data_dirs[0])
        self.assertTrue("retry_render" in user_data_dirs[1])
        self.assertTrue(self.pdf_file.exists())
        self.assertTrue(res.recovered_after_retry)
        self.assertEqual(res.attempts, 2)
        self.assertEqual(len(res.diagnostics["attempts_history"]), 1)
        self.assertEqual(len(res.attempts_history), 1)
        self.assertIn("recovered on retry attempt 2/2", res.msg)
        self.assertGreater(res.total_elapsed_seconds, 0)

    def test_render_pdf_timeout_exhaustion_returns_structured_diagnostics(self):
        """When both attempt 1 and retry attempt 2 time out, returns structured diagnostics in RenderResult."""
        renderer = BrowserRenderer(browser_path="mock_timeout_browser")

        def fake_timeout(cmd, timeout_seconds):
            raise subprocess.TimeoutExpired(
                cmd,
                timeout_seconds,
                output=b"partial render stdout",
                stderr=b"rendering process timed out",
            )

        with patch.object(BrowserRenderer, "_run_subprocess", side_effect=fake_timeout):
            res = renderer.render_pdf(self.html_file, self.pdf_file, timeout_seconds=5, max_retries=1)

        self.assertFalse(res.ok)
        self.assertEqual(res.pages, 0)
        self.assertIn("Rendering timed out after 5s (attempt 2/2)", res.msg)

        diag = res.diagnostics
        self.assertIsInstance(diag, dict)
        self.assertEqual(diag["attempt"], 2)
        self.assertEqual(diag["attempts"], 2)
        self.assertEqual(diag["max_attempts"], 2)
        self.assertFalse(res.recovered_after_retry)
        self.assertEqual(res.attempts, 2)
        self.assertEqual(len(res.attempts_history), 2)
        self.assertEqual(len(diag["attempts_history"]), 2)
        self.assertGreater(res.total_elapsed_seconds, 0)
        self.assertEqual(diag["phase"], "retry_render")
        self.assertEqual(diag["timeout_budget"], 5)
        self.assertEqual(diag["browser_path"], "mock_timeout_browser")
        self.assertIn("rendering process timed out", diag["stderr"])
        self.assertEqual(diag["temp_pdf_exists"], False)
        self.assertEqual(diag["temp_pdf_size"], 0)

    def test_run_subprocess_timeout_output_draining_and_reaping(self):
        """Verifies that _run_subprocess kills process tree, drains output with bounded timeout, and waits for process."""
        mock_proc = MagicMock()
        mock_proc.pid = 4321
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["mock_browser"], timeout=10, output=None, stderr=None),
            (b"drained output stream", b"drained error stream"),
        ]
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("core.browser_renderer._kill_process_tree") as mock_kill_tree:
            with self.assertRaises(subprocess.TimeoutExpired) as ctx:
                BrowserRenderer._run_subprocess(["mock_browser", "--headless"], timeout_seconds=10)

            mock_kill_tree.assert_called_once_with(4321)
            mock_proc.kill.assert_called_once()
            self.assertEqual(mock_proc.communicate.call_count, 2)
            self.assertEqual(mock_proc.communicate.call_args_list[1][1], {"timeout": 5})
            mock_proc.wait.assert_called_once_with(timeout=2)
            self.assertEqual(ctx.exception.output, "drained output stream")
            self.assertEqual(ctx.exception.stderr, "drained error stream")

    def test_render_pdf_configurable_timeout_from_env(self):
        """Verifies that BROWSER_TIMEOUT_SECONDS environment variable configures timeout budget."""
        renderer = BrowserRenderer(browser_path="mock_env_browser")
        observed_timeouts = []

        def fake_run(cmd, timeout_seconds):
            observed_timeouts.append(timeout_seconds)
            for arg in cmd:
                if arg.startswith("--print-to-pdf="):
                    Path(arg.split("=", 1)[1]).write_bytes(b"%PDF-1.4\n/Type /Page\nbytes")
            return 0, "ok", "", 0.5

        with patch.dict(os.environ, {"BROWSER_TIMEOUT_SECONDS": "45"}), \
             patch.object(BrowserRenderer, "_run_subprocess", side_effect=fake_run):
            res = renderer.render_pdf(self.html_file, self.pdf_file)

        self.assertTrue(res.ok)
        self.assertEqual(observed_timeouts, [45])


if __name__ == "__main__":
    unittest.main()
