"""
Negative and Edge-Case Tests for OfferGet Core Architecture:
1. ProfileContext: Non-hallucination of missing fields (grade, project name, honors).
2. AcademicExporter: Absence of hallucinated defaults (roles, emails, phones, titles) in LaTeX, Typst, and HTML.
"""

import tempfile
import unittest
from pathlib import Path

from core.academic_exporter import AcademicExporter
from core.profile_adapter import ProfileContext, build_profile_context, normalize_candidate_profile
from core.resume_view_model import ResumeViewModel


class TestArchitectureNegative(unittest.TestCase):

    def test_1_profile_no_hallucinated_defaults(self):
        """Verify that minimal profiles do not get populated with invented academic or career facts."""
        empty_profile = {}
        ctx = build_profile_context(empty_profile)
        self.assertIsInstance(ctx, ProfileContext)

        raw_proj = {"role": "志愿者", "bullets": ["负责接待"]}
        norm = normalize_candidate_profile({"projects": [raw_proj]})
        self.assertEqual(norm["projects"][0]["name"], "")
        self.assertNotEqual(norm["projects"][0]["name"], "校园经历")

        profile_with_honors = {
            "name": "李四",
            "honors": [{"name": "国家一等奖学金"}],
            "papers": [{"title": "Agent Research"}],
        }
        ctx2 = build_profile_context(profile_with_honors)
        norm2 = ctx2.to_dict()
        self.assertIn("国家一等奖学金", [h.get("name") if isinstance(h, dict) else h for h in norm2["honors_awards"]])
        self.assertEqual(len(norm2["publications"]), 1)

    def test_2_academic_exporter_no_hallucinations(self):
        """Verify that LaTeX, Typst, and HTML renderers do not inject placeholder strings."""
        exporter = AcademicExporter()
        minimal_profile = {
            "name": "王五",
            "projects": [
                {"name": "开源项目", "bullets": ["贡献代码"]}
            ]
        }
        vm = ResumeViewModel.from_profile(minimal_profile)

        latex_out = exporter.generate_latex(vm)
        self.assertNotIn("算法架构师", latex_out)
        self.assertNotIn("candidate@example.com", latex_out)
        self.assertNotIn("+86 138-0000-0000", latex_out)
        self.assertNotIn("架构 Owner", latex_out)
        self.assertIn("王五", latex_out)
        self.assertIn("开源项目", latex_out)

        typst_out = exporter.generate_typst(vm)
        self.assertNotIn("运营岗", typst_out)
        self.assertNotIn("candidate@example.com", typst_out)
        self.assertNotIn("+86 138-0000-0000", typst_out)
        self.assertNotIn("架构 Owner", typst_out)
        self.assertIn("王五", typst_out)

        html_out = exporter.generate_academic_html_preview(vm)
        self.assertNotIn("运营岗", html_out)
        self.assertNotIn("candidate@example.com", html_out)
        self.assertNotIn("+86 138-0000-0000", html_out)
        self.assertIn("王五", html_out)

        fake_tex = Path(tempfile.gettempdir()) / "non_existent_test.tex"
        fake_pdf = Path(tempfile.gettempdir()) / "non_existent_test.pdf"
        self.assertFalse(exporter.compile_latex(fake_tex, fake_pdf))
        self.assertFalse(exporter.compile_typst(fake_tex, fake_pdf))


if __name__ == "__main__":
    unittest.main()
