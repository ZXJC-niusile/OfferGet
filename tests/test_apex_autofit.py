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
from core.render import BrowserRenderer


class TestAutoFitEngine(unittest.TestCase):
    """Test suite for AutoFitEngine layout tuning and single-page fitting."""

    def setUp(self):
        self.engine = AutoFitEngine()

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
  <h1>Short Resume Test</h1>
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
            success, msg, details = self.engine.fit_to_single_page(in_path, output_pdf_path=out_pdf)
            self.assertTrue(success)
            self.assertEqual(details["pages"], 1)
            self.assertEqual(details["step"], 0)
            self.assertTrue(Path(out_pdf).exists())
            self.assertGreater(Path(out_pdf).stat().st_size, 0)
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_pdf).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
