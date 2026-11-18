"""
Tests for OfferGet Core Architecture Integration:
1. Unified Profile Context SSOT & ResumeViewModel projection
2. Unified Resume Rendering Pipeline (ProfileContext -> ResumeViewModel -> Renderers)
3. BibTeX literature parsing & Academic CV publication rendering
"""

import unittest

from core.academic_exporter import AcademicExporter
from core.academic_sync import BibTexPublicationParser
from core.profile_adapter import ProfileContext, build_profile_context
from core.resume_builder import ResumeBuilder
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel


class TestArchitectureConvergence(unittest.TestCase):

    def setUp(self):
        self.sample_profile_dict = {
            "name": "张三",
            "education": {
                "school": "浙江大学",
                "major": "计算机科学与技术",
                "degree": "本科",
                "gpa": "3.85/4.0",
                "rank": "5/120",
            },
            "skills": ["Python", "PyTorch", "Linux", "C++"],
            "experience": [
                {
                    "company": "未来科技",
                    "role": "算法实习生",
                    "highlights": [
                        {"claim_zh": "优化大模型推理流水线，提升吞吐量 35%"}
                    ],
                }
            ],
            "projects": [
                {
                    "name": "分布式推理框架",
                    "role": "算法复现成员",
                    "description": "基于 PyTorch 实现 KV Cache 优化",
                }
            ],
            "publications": [
                {
                    "title": "A Novel KV Cache Acceleration Method",
                    "authors": ["李四", "张三", "王五"],
                    "venue": "ACL 2025",
                    "status": "under_review",
                    "url": "https://example.invalid/paper",
                }
            ],
            "awards": ["国家励志奖学金"],
        }

    def test_1_unified_profile_model(self):
        ctx = build_profile_context(self.sample_profile_dict)
        self.assertIsInstance(ctx, ProfileContext)
        vm = ctx.to_view_model()
        self.assertIsInstance(vm, ResumeViewModel)
        self.assertEqual(vm.name, "张三")

    def test_2_unified_resume_rendering(self):
        ctx = build_profile_context(self.sample_profile_dict)
        vm = ctx.to_view_model()

        exporter = AcademicExporter()
        latex = exporter.generate_latex(vm)
        self.assertIn("张三", latex)
        self.assertIn("浙江大学", latex)
        self.assertIn("未来科技", latex)
        self.assertIn(r"\textbf{张三}", latex)
        self.assertIn(r"\href{https://example.invalid/paper}", latex)

        typst = exporter.generate_typst(vm)
        self.assertIn("张三", typst)
        self.assertIn("浙江大学", typst)
        self.assertIn("未来科技", typst)
        self.assertIn("*张三*", typst)
        self.assertIn('#link("https://example.invalid/paper")', typst)

        html = exporter.generate_academic_html_preview(vm)
        self.assertIn("张三", html)
        self.assertIn("未来科技", html)
        self.assertIn("<strong>张三</strong>", html)
        self.assertIn('<a href="https://example.invalid/paper"', html)

        themed = HtmlThemeRenderer().render(vm, "academic-postgraduate")
        self.assertIn("<strong>张三</strong>", themed)
        self.assertIn('<a href="https://example.invalid/paper"', themed)
        self.assertLess(themed.index("李四"), themed.index("<strong>张三</strong>"))
        self.assertLess(themed.index("<strong>张三</strong>"), themed.index("王五"))

        builder = ResumeBuilder(ctx)
        self.assertIsNotNone(builder)
        self.assertEqual(builder.view_model.name, "张三")

    def test_3_bibtex_publication_parsing(self):
        bib = """
        @inproceedings{zhang2025kv,
          title={A Novel KV Cache Method},
          author={Si Li and San Zhang and Wu Wang},
          booktitle={ACL 2025},
          year={2025},
          url={https://example.invalid/kv}
        }
        """
        entries = BibTexPublicationParser.parse_string(bib, candidate_name="San Zhang")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].authors, ["Si Li", "San Zhang", "Wu Wang"])
        self.assertEqual(entries[0].ccf_rank, "CCF-A")
        self.assertEqual(entries[0].url, "https://example.invalid/kv")


if __name__ == "__main__":
    unittest.main()
