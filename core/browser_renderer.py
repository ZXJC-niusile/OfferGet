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
from pathlib import Path
from typing import Optional, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import core.atomic_writer as atomic_writer

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

    def render_pdf(
        self,
        html_path: str | Path,
        pdf_path: str | Path,
        timeout_seconds: int = 30,
    ) -> Tuple[bool, int, str]:
        """Renders an HTML file to an A4 PDF using headless browser CLI.

        Returns: (success: bool, pages: int, message: str)
        """
        html_file = Path(html_path).resolve()
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        if not html_file.exists():
            return False, 0, f"HTML file not found: {html_file}"

        temp_user_data = tempfile.mkdtemp(prefix="offerget_browser_")
        temp_rendered_pdf = Path(temp_user_data) / "rendered.pdf"
        file_url = html_file.as_uri()

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
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            if proc.returncode != 0 and not temp_rendered_pdf.exists():
                return False, 0, f"Browser returned code {proc.returncode}: {proc.stderr}"

            if not temp_rendered_pdf.exists() or temp_rendered_pdf.stat().st_size == 0:
                return False, 0, "PDF was not generated or generated empty."

            pages = self.count_pages(temp_rendered_pdf)

            res = atomic_writer.safe_save_file(pdf_file, temp_rendered_pdf, allow_shadow=True)
            if not res.success:
                return False, 0, f"Failed to save PDF to {pdf_file}: {res.error_message}"

            if res.is_shadow:
                msg = f"Successfully rendered {pages} page(s) (Saved to shadow copy: {res.final_path.name} due to lock)"
            else:
                msg = f"Successfully rendered {pages} page(s) ({res.final_path.stat().st_size} bytes)"

            return True, pages, msg
        except subprocess.TimeoutExpired:
            return False, 0, f"Rendering timed out after {timeout_seconds}s"
        except Exception as e:
            return False, 0, f"Render error: {str(e)}"
        finally:
            shutil.rmtree(temp_user_data, ignore_errors=True)

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
