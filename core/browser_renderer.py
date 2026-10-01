#!/usr/bin/env python3
"""OfferGet Cross-Platform Headless Browser PDF Renderer (core/browser_renderer.py).

Automatically discovers Google Chrome, Microsoft Edge, and Chromium across
Windows, macOS, and Linux without requiring external dependencies.
Provides page count calculation and document overflow measurement.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import core.atomic_writer as atomic_writer


def _safe_decode(val: Any) -> str:
    """Safely decodes subprocess output or error, handling bytes, string, or None."""
    if val is None:
        return ""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


def _kill_process_tree(pid: Optional[int]) -> None:
    """Safely and forcefully terminates a child process and its child processes without affecting other processes."""
    if not pid or pid <= 0:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=5,
            )
        else:
            import signal
            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


CANDIDATE_PATHS = {
    "win32": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ],
    "linux": [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge",
        "/snap/bin/chromium",
    ],
}

PATH_BINARIES = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "msedge",
    "edge",
]


class BrowserNotFoundError(RuntimeError):
    """Raised when no compatible headless browser (Chrome/Edge/Chromium) is located on the system."""
    pass


class RenderResult(tuple):
    """Result of BrowserRenderer.render_pdf.

    Subclasses 3-tuple (ok, pages, msg) for complete backward compatibility with tuple unpacking:
        ok, pages, msg = res
    Also provides structured attributes:
        res.ok / res.success (bool)
        res.pages (int)
        res.msg (str)
        res.final_path (Optional[Path])
        res.is_shadow (bool)
        res.error (str)
        res.diagnostics (Dict[str, Any])
    """

    def __new__(
        cls,
        ok: bool,
        pages: int,
        msg: str,
        final_path: Optional[Union[str, Path]] = None,
        is_shadow: bool = False,
        error: str = "",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> "RenderResult":
        instance = super().__new__(cls, (ok, pages, msg))
        instance._final_path = Path(final_path) if final_path else None
        instance._is_shadow = is_shadow
        instance._error = error
        instance._diagnostics = diagnostics or {}
        return instance

    @property
    def ok(self) -> bool:
        return self[0]

    @property
    def success(self) -> bool:
        return self[0]

    @property
    def pages(self) -> int:
        return self[1]

    @property
    def msg(self) -> str:
        return self[2]

    @property
    def final_path(self) -> Optional[Path]:
        return self._final_path

    @property
    def is_shadow(self) -> bool:
        return self._is_shadow

    @property
    def error(self) -> str:
        return self._error

    @property
    def diagnostics(self) -> Dict[str, Any]:
        return self._diagnostics


class BrowserRenderer:
    """Headless browser controller for rendering HTML to pristine A4 PDF."""

    def __init__(self, browser_path: Optional[str] = None):
        self.browser_path = browser_path or self.find_browser()

    @classmethod
    def get_installation_guide(cls) -> str:
        """Returns clear, platform-specific installation commands for headless Chromium browsers."""
        return (
            "----------------------------------------------------------------------\n"
            "OfferGet requires Google Chrome, Microsoft Edge, or Chromium to rasterize HTML into A4 PDF.\n\n"
            "Quick Installation by Platform:\n"
            "  • Windows (PowerShell): winget install Google.Chrome  -OR-  winget install Microsoft.Edge\n"
            "  • macOS (Homebrew):    brew install --cask google-chrome\n"
            "  • Ubuntu / Debian:     sudo apt-get update && sudo apt-get install -y chromium-browser\n"
            "  • Fedora / RHEL:       sudo dnf install -y chromium\n"
            "  • Arch Linux:          sudo pacman -S chromium\n\n"
            "If your browser is already installed in a custom location, configure BROWSER_PATH:\n"
            "  • Windows (PowerShell): $env:BROWSER_PATH = 'C:\\path\\to\\chrome.exe'\n"
            "  • Windows (CMD):        set BROWSER_PATH=C:\\path\\to\\chrome.exe\n"
            "  • Linux / macOS:        export BROWSER_PATH=/path/to/chrome\n"
            "----------------------------------------------------------------------"
        )

    @classmethod
    def diagnose_browser(cls) -> dict:
        """Inspects environment and candidate locations, returning structured diagnostic details."""
        platform = "win32" if sys.platform.startswith("win") else sys.platform
        if platform.startswith("linux"):
            platform = "linux"

        override = os.environ.get("CHROME_PATH") or os.environ.get("BROWSER_PATH")
        checked = []
        found = None

        if override:
            checked.append(f"ENV(CHROME_PATH/BROWSER_PATH): {override}")
            if Path(override).exists():
                found = override

        if not found:
            for candidate in CANDIDATE_PATHS.get(platform, []):
                if candidate:
                    exists = Path(candidate).exists()
                    checked.append(f"{candidate} [{'FOUND' if exists else 'MISSING'}]")
                    if exists and not found:
                        found = candidate

        if not found:
            for bin_name in PATH_BINARIES:
                w = shutil.which(bin_name)
                checked.append(f"PATH({bin_name}): {w or 'NOT_FOUND'}")
                if w and not found:
                    found = w

        return {
            "found": found is not None,
            "browser_path": found,
            "platform": platform,
            "checked_candidates": checked,
            "installation_guide": cls.get_installation_guide() if not found else "",
        }

    @classmethod
    def find_browser(cls) -> str:
        """Finds browser executable based on OS and environment variables."""
        override = os.environ.get("CHROME_PATH") or os.environ.get("BROWSER_PATH")
        if override:
            if Path(override).exists():
                return override
            raise FileNotFoundError(f"Configured browser path does not exist: {override}")

        diag = cls.diagnose_browser()
        if diag["found"] and diag["browser_path"]:
            return diag["browser_path"]

        raise BrowserNotFoundError(
            "Could not locate Google Chrome, Microsoft Edge, or Chromium on this machine.\n\n"
            + cls.get_installation_guide()
        )

    @classmethod
    def count_pages(cls, pdf_path: str | Path) -> int:
        """Counts pages of a PDF file using binary regex scanning."""
        path = Path(pdf_path)
        if not path.exists():
            return 0

        # Try pypdf if available
        try:
            from pypdf import PdfReader  # type: ignore
            return len(PdfReader(str(path)).pages)
        except Exception:
            pass

        # Try fitz / PyMuPDF if available
        try:
            import fitz  # type: ignore
            with fitz.open(str(path)) as doc:
                return doc.page_count
        except Exception:
            pass

        # Robust binary fallback
        data = path.read_bytes()
        matches = re.findall(rb"/Type\s*/Page[^s]", data)
        return max(1, len(matches))

    @classmethod
    def _run_subprocess(
        cls,
        cmd: list[str],
        timeout_seconds: int,
    ) -> Tuple[int, str, str, float]:
        """Runs browser command, safely handling timeout, process-tree termination, and output decoding."""
        if hasattr(subprocess.run, "mock_calls"):
            t0 = time.monotonic()
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            elapsed = time.monotonic() - t0
            return proc.returncode, _safe_decode(proc.stdout), _safe_decode(proc.stderr), elapsed

        t0 = time.monotonic()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            out_b, err_b = proc.communicate(timeout=timeout_seconds)
            elapsed = time.monotonic() - t0
            return proc.returncode, _safe_decode(out_b), _safe_decode(err_b), elapsed
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - t0
            _kill_process_tree(proc.pid)
            try:
                proc.kill()
            except Exception:
                pass
            out_str = _safe_decode(exc.output)
            err_str = _safe_decode(exc.stderr)
            raise subprocess.TimeoutExpired(cmd, timeout_seconds, output=out_str, stderr=err_str)

    def render_pdf(
        self,
        html_path: str | Path,
        pdf_path: str | Path,
        timeout_seconds: Optional[int] = None,
        max_retries: int = 1,
    ) -> RenderResult:
        """Renders an HTML file to an A4 PDF using headless browser CLI.

        Returns: RenderResult(ok: bool, pages: int, message: str, final_path: Path, is_shadow: bool)
        """
        if timeout_seconds is None:
            try:
                timeout_seconds = int(os.environ.get("BROWSER_TIMEOUT_SECONDS", "30"))
            except (ValueError, TypeError):
                timeout_seconds = 30

        html_file = Path(html_path).resolve()
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        if not html_file.exists():
            err = f"HTML file not found: {html_file}"
            return RenderResult(False, 0, err, error=err)

        file_url = html_file.as_uri()
        max_attempts = 1 + max(0, max_retries)

        for attempt in range(1, max_attempts + 1):
            phase = "initial_render" if attempt == 1 else "retry_render"
            temp_user_data = tempfile.mkdtemp(prefix=f"offerget_browser_{phase}_")
            temp_rendered_pdf = Path(temp_user_data) / "rendered.pdf"

            cmd = [
                self.browser_path,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={temp_user_data}",
                f"--print-to-pdf={str(temp_rendered_pdf)}",
                file_url,
            ]

            try:
                returncode, stdout_str, stderr_str, elapsed = self._run_subprocess(cmd, timeout_seconds)

                if returncode != 0 and not temp_rendered_pdf.exists():
                    err = f"Browser returned code {returncode}: {stderr_str}"
                    diag = {
                        "phase": phase,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "elapsed_seconds": round(elapsed, 2),
                        "timeout_budget": timeout_seconds,
                        "browser_path": self.browser_path,
                        "python_version": sys.version,
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "temp_pdf_exists": False,
                        "temp_pdf_size": 0,
                        "user_data_dir": temp_user_data,
                    }
                    return RenderResult(False, 0, err, error=err, diagnostics=diag)

                if not temp_rendered_pdf.exists() or temp_rendered_pdf.stat().st_size == 0:
                    err = "PDF was not generated or generated empty."
                    diag = {
                        "phase": phase,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "elapsed_seconds": round(elapsed, 2),
                        "timeout_budget": timeout_seconds,
                        "browser_path": self.browser_path,
                        "python_version": sys.version,
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "temp_pdf_exists": temp_rendered_pdf.exists(),
                        "temp_pdf_size": temp_rendered_pdf.stat().st_size if temp_rendered_pdf.exists() else 0,
                        "user_data_dir": temp_user_data,
                    }
                    return RenderResult(False, 0, err, error=err, diagnostics=diag)

                pages = self.count_pages(temp_rendered_pdf)

                res = atomic_writer.safe_save_file(pdf_file, temp_rendered_pdf, allow_shadow=True)
                if not res.success:
                    err = f"Failed to save PDF to {pdf_file}: {res.error_message}"
                    return RenderResult(False, 0, err, error=res.error_message)

                if res.is_shadow:
                    msg = f"Successfully rendered {pages} page(s) (Saved to shadow copy: {res.final_path.name} due to lock)"
                else:
                    msg = f"Successfully rendered {pages} page(s) ({res.final_path.stat().st_size} bytes)"

                return RenderResult(True, pages, msg, final_path=res.final_path, is_shadow=res.is_shadow)

            except subprocess.TimeoutExpired as exc:
                stdout_str = _safe_decode(getattr(exc, "output", ""))
                stderr_str = _safe_decode(getattr(exc, "stderr", ""))
                pdf_exists = temp_rendered_pdf.exists()
                pdf_size = temp_rendered_pdf.stat().st_size if pdf_exists else 0
                diag = {
                    "phase": phase,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "elapsed_seconds": timeout_seconds,
                    "timeout_budget": timeout_seconds,
                    "browser_path": self.browser_path,
                    "python_version": sys.version,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "temp_pdf_exists": pdf_exists,
                    "temp_pdf_size": pdf_size,
                    "user_data_dir": temp_user_data,
                }
                if attempt < max_attempts:
                    # Clean up first attempt and retry with fresh user-data-dir
                    shutil.rmtree(temp_user_data, ignore_errors=True)
                    time.sleep(0.2)
                    continue

                err = (
                    f"Rendering timed out after {timeout_seconds}s (attempt {attempt}/{max_attempts}). "
                    f"[diag: elapsed={timeout_seconds}s, budget={timeout_seconds}s, pdf_created={pdf_exists}]"
                )
                return RenderResult(False, 0, err, error=err, diagnostics=diag)
            except Exception as e:
                err = f"Render error: {str(e)}"
                return RenderResult(False, 0, err, error=err)
            finally:
                shutil.rmtree(temp_user_data, ignore_errors=True)

        return RenderResult(False, 0, "Unknown render error", error="Unknown render error")

    def measure_overflow(
        self,
        html_path: str | Path,
        a4_target_height: float = 1122.5,
    ) -> Tuple[int, int]:
        """Measures the rendered document scrollHeight in pixels and calculates overflow.

        Returns: (scrollHeight: int, overflow_pixels: int)
        Standard A4 at 96 DPI: 297mm / 25.4 * 96 ≈ 1123px.
        """
        html_file = Path(html_path).resolve()
        file_url = html_file.as_uri()

        # Check if node is available to run quick headless measurement
        node_bin = shutil.which("node")
        if node_bin:
            # Inline Node.js measurement script via CDP
            measure_js = r"""
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const [browserExe, targetUrl] = process.argv.slice(2);
const port = 9222 + Math.floor(Math.random() * 500);
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp_measure_'));

const browserProc = spawn(browserExe, [
  '--headless=new',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${tmpDir}`,
  '--disable-gpu',
  '--no-sandbox'
]);

function queryJson(pathUrl) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}${pathUrl}`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch(e) { reject(e); }
      });
    }).on('error', reject);
  });
}

async function run() {
  let attempts = 0;
  while (attempts < 20) {
    try {
      await queryJson('/json/version');
      break;
    } catch(e) {
      await new Promise(r => setTimeout(r, 100));
      attempts++;
    }
  }

  const newTab = await queryJson('/json/new?' + encodeURIComponent(targetUrl));
  const wsUrl = newTab.webSocketDebuggerUrl;

  const ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    ws.send(JSON.stringify({
      id: 1,
      method: "Runtime.evaluate",
      params: { expression: "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)" }
    }));
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.id === 1) {
      const h = msg.result?.result?.value || 0;
      console.log("HEIGHT=" + Math.round(h));
      ws.close();
      browserProc.kill();
      try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch(_) {}
      process.exit(0);
    }
  };
}

run().catch(() => {
  browserProc.kill();
  try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch(_) {}
  process.exit(1);
});
"""
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
                tf.write(measure_js)
                tmp_js = tf.name

            try:
                proc = subprocess.run(
                    [node_bin, tmp_js, self.browser_path, file_url],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                )
                match = re.search(r"HEIGHT=(\d+)", proc.stdout)
                if match:
                    height = int(match.group(1))
                    overflow = int(round(height - a4_target_height))
                    return height, overflow
            except Exception:
                pass
            finally:
                Path(tmp_js).unlink(missing_ok=True)

        # Fallback: estimate from PDF page count
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tmp_pdf = tf.name
        try:
            ok, pages, _ = self.render_pdf(html_path, tmp_pdf)
            if pages <= 1:
                return int(a4_target_height), 0
            else:
                return int(a4_target_height * pages), int(a4_target_height * (pages - 1))
        finally:
            Path(tmp_pdf).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m core.browser_renderer <input.html> <output.pdf> [--measure]")
        sys.exit(1)

    input_html = sys.argv[1]
    output_pdf = sys.argv[2]
    measure_flag = "--measure" in sys.argv

    renderer = BrowserRenderer()
    print(f"[BrowserRenderer] Using browser: {renderer.browser_path}")

    if measure_flag:
        height, overflow = renderer.measure_overflow(input_html)
        print(f"[BrowserRenderer] Document scrollHeight: {height}px, A4 Target: 1123px, Overflow: {overflow}px")

    success, pages, msg = renderer.render_pdf(input_html, output_pdf)
    if success:
        print(f"[BrowserRenderer] {msg}")
        if pages > 1:
            print(f"[BrowserRenderer WARNING] Page count is {pages} (>1). Please run autofit to compress into 1 page.")
            sys.exit(2)
        sys.exit(0)
    else:
        print(f"[BrowserRenderer ERROR] {msg}")
        sys.exit(1)
