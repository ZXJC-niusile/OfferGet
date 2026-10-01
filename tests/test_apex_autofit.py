#!/usr/bin/env python3
"""Unit tests for ApexResume Smart Auto-Fit Compaction Engine."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from core.autofit import AutoFitEngine, TUNING_LADDER, TuneProfile
from core.browser_renderer import BrowserRenderer, RenderResult


class FakeAutofitRenderer(BrowserRenderer):
    """Deterministic, fast renderer mock for unit testing AutoFit layout algorithms."""

    def __init__(
        self,
        pages_schedule: list[int] | None = None,
        shadow_pdf: Path | None = None,
        empty_file: bool = False,
        fail_initial: bool = False,
    ):
        self.browser_path = "mock-autofit-browser"
        self.pages_schedule = pages_schedule or [1]
        self.shadow_pdf = shadow_pdf
        self.empty_file = empty_file
        self.fail_initial = fail_initial
        self.call_count = 0
        self.rendered_inputs: list[Path] = []

    def render_pdf(self, html_path, pdf_path, timeout_seconds=30):
        self.rendered_inputs.append(Path(html_path))
        if self.fail_initial and self.call_count == 0:
            self.call_count += 1
            return RenderResult(False, 0, "Simulated render failure", error="Simulated render failure")

        idx = min(self.call_count, len(self.pages_schedule) - 1)
        pages = self.pages_schedule[idx]
        self.call_count += 1

        target = Path(pdf_path)
        if self.shadow_pdf:
            self.shadow_pdf.parent.mkdir(parents=True, exist_ok=True)
            self.shadow_pdf.write_bytes(b"%PDF-1.4 shadow content from fake renderer")
            return RenderResult(
                True,
                pages,
                f"Saved to shadow copy: {self.shadow_pdf.name} due to lock",
                final_path=self.shadow_pdf,
                is_shadow=True,
            )

        if not self.empty_file:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"%PDF-1.4 valid dummy pdf bytes for autofit test")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")

        return RenderResult(True, pages, f"Rendered {pages} page(s)", final_path=target, is_shadow=False)


class TestAutoFitEngine(unittest.TestCase):
    """Test suite for AutoFitEngine layout tuning and single-page fitting."""

    def setUp(self):
        self.fake_renderer = FakeAutofitRenderer(pages_schedule=[1])
        self.engine = AutoFitEngine(renderer=self.fake_renderer)

    def test_apply_profile_with_css_variables(self):
        """Replaces CSS variables when :root contains layout custom properties."""
        html_with_vars = """
<!DOCTYPE html>
<html>
<head>
  <style>
    :root {
      --body-line-height: 1.6;
      --page-padding-y: 9mm;
      --page-padding-x: 10.6mm;
      --body-font-size: 11.5px;
      --item-gap: 4px;
      --section-gap: 10px;
    }
  </style>
</head>
<body><p>Content</p></body>
</html>
"""
        profile = TUNING_LADDER[2]  # Step 2
        tuned = self.engine.apply_profile_to_html(html_with_vars, profile)

        self.assertIn(f"--body-line-height: {profile.line_height};", tuned)
        self.assertIn(f"--page-padding-y: {profile.padding_y_mm}mm;", tuned)
        self.assertIn(f"--body-font-size: {profile.font_size_px}px;", tuned)

    def test_apply_profile_without_css_variables_fallback(self):
        """Injects override style block when HTML lacks CSS variables."""
        plain_html = "<html><head></head><body><p>Simple HTML</p></body></html>"
        profile = TUNING_LADDER[1]
        tuned = self.engine.apply_profile_to_html(plain_html, profile)

        self.assertIn('id="autofit-override"', tuned)
        self.assertIn(f"line-height: {profile.line_height} !important;", tuned)

    def test_fit_to_single_page_already_fitting(self):
        """Short HTML that already fits in 1 page returns step 0 without modifications."""
        short_html = "<html><body><h1>Short</h1><p>Fits 1 page</p></body></html>"
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
            tf.write(short_html)
            in_path = tf.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pf:
            out_pdf = pf.name

        try:
            success, msg, details = self.engine.fit_to_single_page(in_path, output_pdf_path=out_pdf)
            self.assertTrue(success, f"msg={msg}; details={details}")
            self.assertEqual(details["pages"], 1)
            self.assertEqual(details["step"], 0)
            final_out_pdf = details.get("final_pdf_path", out_pdf)
            self.assertTrue(Path(final_out_pdf).exists())
            self.assertGreater(Path(final_out_pdf).stat().st_size, 0)
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_pdf).unlink(missing_ok=True)

    def test_fit_to_single_page_stepped_compression(self):
        """Content overflowing to 2 pages steps down ladder until fitting 1 page at step 1."""
        stepped_renderer = FakeAutofitRenderer(pages_schedule=[2, 1])
        engine = AutoFitEngine(renderer=stepped_renderer)

        html_doc = "<html><body>Long Content</body></html>"
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
            tf.write(html_doc)
            in_path = tf.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pf:
            out_pdf = pf.name

        try:
            success, msg, details = engine.fit_to_single_page(in_path, output_pdf_path=out_pdf)
            self.assertTrue(success, f"msg={msg}; details={details}")
            self.assertEqual(details["step"], 0)  # TUNING_LADDER[0] was step 1 attempt
            self.assertEqual(details["pages"], 1)
            self.assertIn("Compressed from 2 pages down to 1 page", msg)
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_pdf).unlink(missing_ok=True)

    def test_fit_to_single_page_shadow_propagation_step_0(self):
        """Verifies that if renderer redirects temporary PDF to a shadow file at step 0,
        AutoFit publishes the shadow file rather than the initial 0-byte test_pdf."""
        with tempfile.TemporaryDirectory(prefix="autofit_shadow_test_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            shadow_pdf = tmp_path / "temp_shadow_12345.pdf"
            shadow_renderer = FakeAutofitRenderer(pages_schedule=[1], shadow_pdf=shadow_pdf)
            engine = AutoFitEngine(renderer=shadow_renderer)

            in_html = tmp_path / "input.html"
            in_html.write_text("<html><body>Test</body></html>", encoding="utf-8")
            out_pdf = tmp_path / "published.pdf"

            success, msg, details = engine.fit_to_single_page(in_html, output_pdf_path=out_pdf)
            self.assertTrue(success, f"msg={msg}; details={details}")
            self.assertTrue(out_pdf.exists())
            self.assertEqual(out_pdf.read_bytes(), b"%PDF-1.4 shadow content from fake renderer")
            # Shadow file in temp dir should be unlinked by finally block
            self.assertFalse(shadow_pdf.exists())

    def test_fit_to_single_page_shadow_propagation_step_n(self):
        """Verifies that if renderer redirects temporary PDF to a shadow file during tuning,
        AutoFit publishes the shadow file at the matching step."""
        with tempfile.TemporaryDirectory(prefix="autofit_shadow_step_n_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            shadow_pdf = tmp_path / "step_shadow_67890.pdf"

            class StepShadowRenderer(BrowserRenderer):
                def __init__(self):
                    self.browser_path = "mock-browser"
                    self.step = 0

                def render_pdf(self, html_path, pdf_path, timeout_seconds=30):
                    if self.step == 0:
                        self.step += 1
                        Path(pdf_path).write_bytes(b"%PDF-1.4 step 0 (2 pages)")
                        return RenderResult(True, 2, "2 pages", final_path=Path(pdf_path), is_shadow=False)
                    else:
                        self.step += 1
                        shadow_pdf.write_bytes(b"%PDF-1.4 step 1 compacted shadow content")
                        return RenderResult(True, 1, "1 page shadow", final_path=shadow_pdf, is_shadow=True)

            engine = AutoFitEngine(renderer=StepShadowRenderer())
            in_html = tmp_path / "input.html"
            in_html.write_text("<html><body>Test Overflow</body></html>", encoding="utf-8")
            out_pdf = tmp_path / "final.pdf"

            success, msg, details = engine.fit_to_single_page(in_html, output_pdf_path=out_pdf)
            self.assertTrue(success, f"msg={msg}; details={details}")
            self.assertTrue(out_pdf.exists())
            self.assertEqual(out_pdf.read_bytes(), b"%PDF-1.4 step 1 compacted shadow content")
            self.assertFalse(shadow_pdf.exists())

    def test_fit_to_single_page_rejects_empty_rendered_pdf(self):
        """Verifies that AutoFit rejects an empty (0-byte) rendered PDF and returns error details."""
        empty_renderer = FakeAutofitRenderer(pages_schedule=[1], empty_file=True)
        engine = AutoFitEngine(renderer=empty_renderer)

        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
            tf.write("<html><body>Empty PDF Test</body></html>")
            in_path = tf.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pf:
            out_pdf = pf.name

        try:
            success, msg, details = engine.fit_to_single_page(in_path, output_pdf_path=out_pdf)
            self.assertFalse(success)
            self.assertIn("missing or empty", msg)
            self.assertIn("error", details)
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_pdf).unlink(missing_ok=True)


class TestAutoFitRealBrowserIntegration(unittest.TestCase):
    """Integration test suite executing against real Chrome/Edge browser when available."""

    def test_fit_to_single_page_real_browser(self):
        diag = BrowserRenderer.diagnose_browser()
        if not diag["found"]:
            self.skipTest("No compatible browser found for real integration test")

        engine = AutoFitEngine(renderer=BrowserRenderer(browser_path=diag["browser_path"]))
        short_html = """
<!DOCTYPE html>
<html>
<head>
  <style>
    @page { size: A4 portrait; margin: 0; }
    :root {
      --body-line-height: 1.6;
      --page-padding-y: 9mm;
      --page-padding-x: 10.6mm;
      --body-font-size: 11.5px;
      --item-gap: 4px;
      --section-gap: 10px;
    }
    body { font-family: sans-serif; padding: 20px; }
  </style>
</head>
<body>
  <h1>Real Browser Short Resume</h1>
  <p>Single page test content.</p>
</body>
</html>
"""
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
            tf.write(short_html)
            in_path = tf.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pf:
            out_pdf = pf.name

        try:
            success, msg, details = engine.fit_to_single_page(in_path, output_pdf_path=out_pdf)
            self.assertTrue(success, f"msg={msg}; details={details}")
            self.assertEqual(details["pages"], 1)
            self.assertEqual(details["step"], 0)
            final_out_pdf = details.get("final_pdf_path", out_pdf)
            self.assertTrue(Path(final_out_pdf).exists())
            self.assertGreater(Path(final_out_pdf).stat().st_size, 0)
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_pdf).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
