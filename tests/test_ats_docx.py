"""
Unit test suite for OfferGet ATS DOCX Resume Renderer (core.ats_docx_renderer):
- AtsDocxRenderer: deterministic single-column Word generation from ResumeViewModel
- Validation of ATS compliance (margins, single column, standard section headers)
- Integration with ResumeBuilder ("ats-docx" theme)
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.ats_docx_renderer import (
    AtsDocxRenderer,
    DocxRenderConfig,
    validate_docx_ats_compliance,
)
from core.resume_builder import ResumeBuilder
from core.resume_view_model import ResumeViewModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestAtsDocxRenderer(unittest.TestCase):

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_render_docx_from_profile(self):
        """Verify direct rendering of .docx from profile dict."""
        renderer = AtsDocxRenderer()
        docx_path = self.output_dir / "test_resume.docx"
        result_path = renderer.render(self.profile_data, docx_path)

        self.assertTrue(result_path.exists())
        self.assertGreater(result_path.stat().st_size, 1000)

        # Validate ATS compliance
        audit = validate_docx_ats_compliance(result_path)
        self.assertTrue(audit["passed"], f"ATS validation failed: {audit.get('errors')}")
        self.assertIn("Experience", audit["sections_detected"])
        self.assertIn("Skills", audit["sections_detected"])

    def test_02_render_docx_from_view_model(self):
        """Verify rendering from ResumeViewModel."""
        vm = ResumeViewModel.from_profile(self.profile_data)
        renderer = AtsDocxRenderer(DocxRenderConfig(margin_inches=0.75))
        docx_path = self.output_dir / "vm_resume.docx"
        result_path = renderer.render(vm, docx_path)

        self.assertTrue(result_path.exists())
        audit = validate_docx_ats_compliance(result_path)
        self.assertTrue(audit["passed"])

    def test_03_resume_builder_integration(self):
        """Verify ResumeBuilder supports 'ats-docx' theme."""
        builder = ResumeBuilder(self.profile_data)
        self.assertIn("ats-docx", builder.THEMES)

        res = builder.build_theme("ats-docx", self.output_dir)
        self.assertIn("docx", res)
        self.assertTrue(res["docx"].exists())

        audit = validate_docx_ats_compliance(res["docx"])
        self.assertTrue(audit["passed"])


if __name__ == "__main__":
    unittest.main()
