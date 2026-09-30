"""
Unit Tests for OfferGet Adaptive Layout Solver & Micro-typography Engine (tests/test_layout_solver.py)
======================================================================================================
Verifies:
1. Strict font size baseline: body_font_pt >= 9.5pt under any overflow conditions.
2. TeX springs & glue vertical budgeting priority: margins, gaps, line-height before font size.
3. Orphan & widow detection and &nbsp; / text-wrap mitigation.
4. Coursework adaptive multi-column flow grid and anti-abbreviation guarantee.
5. Micro-typography CSS generation and HTML injection across engines.
"""

import re
import unittest
from pathlib import Path
import tempfile

from core.layout_solver import (
    LayoutConfig,
    LayoutSolveResult,
    OrphanWidowMitigator,
    CourseworkGridAdapter,
    SpringsGlueBudgeter,
    solve_layout,
    generate_micro_typography_css,
    inject_micro_typography,
    MIN_BODY_FONT_PT_FLOOR,
)
from core.resume_builder import ResumeBuilder
from core.academic_exporter import AcademicExporter


class FastBrowserRenderer:
    """Lightweight mock renderer for testing layout builder integration."""
    MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n3 0 obj<< /Type /Page /Parent 2 0 R >>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<< /Size 4 /Root 1 0 R >>\nstartxref\n164\n%%EOF\n"

    def render_pdf(self, html_path, pdf_path, timeout_seconds=30):
        Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
        Path(pdf_path).write_bytes(self.MINIMAL_PDF)
        return True, 1, "Mock render"

    def count_pages(self, pdf_path):
        return 1

    def measure_overflow(self, html_path, a4_target_height=1122.5):
        return 1000, 0


class TestLayoutSolver(unittest.TestCase):

    def setUp(self):
        self.sample_html = """<!DOCTYPE html>
<html>
<head>
  <title>Resume</title>
</head>
<body>
  <h2>教育背景</h2>
  <div class="item-header"><span>浙江大学 · 计算机科学与技术</span><span>2020 - 2024</span></div>
  <div><b>核心课程：</b>Math Stats, Civil Eng., Econ, Engineering Project Management</div>

  <h2>实习经历</h2>
  <div class="item-header"><span>字节跳动 · 基础架构平台</span><span>2023.03 - 2023.09</span></div>
  <ul>
    <li>负责分布式缓存网关的设计与实现，支持跨机房双活与高可用容灾优化</li>
    <li>Led the architecture for High Availability and Software Engineering</li>
  </ul>

  <h2>项目经历</h2>
  <div class="item-header"><span>自适应微排版引擎</span><span>2024.01 - 2024.05</span></div>
  <ul>
    <li>Implemented micro-typography with Machine Learning and Probability and Mathematical Statistics</li>
  </ul>

  <h2>专业技能</h2>
  <ul>
    <li>核心技术：Python, Go, C++, Linux, Docker, Kubernetes</li>
  </ul>
</body>
</html>"""

    # =========================================================================
    # 1. 验证正文字号底线（>=9.5pt，拒绝低于底线）
    # =========================================================================

    def test_strictly_rejects_sub_9_5pt_configuration(self):
        """Rejects any config attempting to set min_body_font_pt lower than 9.5pt."""
        with self.assertRaises(ValueError) as ctx:
            LayoutConfig(min_body_font_pt=8.0)
        self.assertIn("cannot be less than strict floor 9.5pt", str(ctx.exception))

        with self.assertRaises(ValueError):
            LayoutConfig(min_body_font_pt=9.49)

        # 9.5pt is allowed as the strict floor
        cfg = LayoutConfig(min_body_font_pt=9.5)
        self.assertEqual(cfg.min_body_font_pt, 9.5)

    def test_font_size_never_drops_below_9_5pt_under_extreme_overflow(self):
        """Under mild, severe, or absurd overflow (e.g. 1500px), font size never drops below 9.5pt."""
        cfg = LayoutConfig(min_body_font_pt=9.5, target_body_font_pt=10.0)

        test_overflows = [0.0, 30.0, 80.0, 150.0, 300.0, 800.0, 2500.0]
        for ovf in test_overflows:
            res = solve_layout(self.sample_html, overflow_px=ovf, config=cfg)
            self.assertGreaterEqual(
                res.body_font_pt,
                9.5,
                f"Body font size {res.body_font_pt}pt dropped below 9.5pt at overflow={ovf}px!",
            )

    def test_extreme_overflow_reports_unsolved_rather_than_violating_floor(self):
        """When overflow exceeds total capacity, font clamps at 9.5pt and solved=False."""
        cfg = LayoutConfig(min_body_font_pt=9.5, target_body_font_pt=10.0)
        res = solve_layout(self.sample_html, overflow_px=1000.0, config=cfg)
        self.assertEqual(res.body_font_pt, 9.5)
        self.assertFalse(res.solved)
        self.assertGreater(res.overflow_px_remaining, 0.0)

    # =========================================================================
    # 2. 验证孤字孤词检测与 &nbsp; / text-wrap 消除
    # =========================================================================

    def test_orphan_risk_detection(self):
        """Detects orphan risk for trailing lone words and fragile technical terms."""
        # Trailing English word
        self.assertTrue(OrphanWidowMitigator.detect_orphan_risk("Distributed Systems and Software Engineering"))
        # Trailing vulnerable phrase
        self.assertTrue(OrphanWidowMitigator.detect_orphan_risk("Enrolled in Civil Engineering"))
        # Clean text without orphan risk
        self.assertFalse(OrphanWidowMitigator.detect_orphan_risk(""))

    def test_bind_fragile_phrases(self):
        """Binds fragile academic and engineering noun phrases with &nbsp;."""
        raw = "Studied Civil Engineering and Probability and Mathematical Statistics with Machine Learning."
        bound, count = OrphanWidowMitigator.bind_fragile_phrases(raw)
        self.assertIn("Civil&nbsp;Engineering", bound)
        self.assertIn("Probability&nbsp;and&nbsp;Mathematical&nbsp;Statistics", bound)
        self.assertIn("Machine&nbsp;Learning", bound)
        self.assertGreaterEqual(count, 3)

    def test_bind_trailing_orphan(self):
        """Replaces the last whitespace before a trailing word with &nbsp;."""
        text = "Led architecture for Distributed Systems"
        bound, n = OrphanWidowMitigator.bind_trailing_orphan(text)
        self.assertEqual(n, 1)
        self.assertTrue(bound.endswith("Distributed&nbsp;Systems"))

    def test_mitigate_html_text_content_preserves_markup(self):
        """Mitigates orphans in HTML blocks without altering HTML tags or attributes."""
        html = '<li>Led development of <strong>Civil Engineering</strong> infrastructure in Go</li>'
        mitigated, count = OrphanWidowMitigator.mitigate_html_text_content(html)
        self.assertIn("<strong>Civil&nbsp;Engineering</strong>", mitigated)
        self.assertIn("infrastructure in&nbsp;Go</li>", mitigated)
        self.assertIn("<li>", mitigated)
        self.assertIn("</li>", mitigated)

    def test_css_includes_text_wrap_and_widow_orphan_rules(self):
        """Generated CSS must include text-wrap: pretty, balance, and orphans/widows controls."""
        cfg = LayoutConfig()
        css = generate_micro_typography_css(cfg)
        self.assertIn("text-wrap: pretty;", css)
        self.assertIn("text-wrap: balance;", css)
        self.assertIn("orphans: 2;", css)
        self.assertIn("widows: 2;", css)
        self.assertIn("-webkit-font-smoothing: antialiased;", css)

    # =========================================================================
    # 3. 验证弹簧与胶水纵向高度预算分配（优先压缩 margins/gap 而非 font size）
    # =========================================================================

    def test_springs_and_glue_progressive_absorption(self):
        """Verifies priority ladder: section margins -> item gaps -> padding -> line height -> font size."""
        cfg = LayoutConfig(
            target_body_font_pt=10.0,
            min_body_font_pt=9.5,
            target_section_margin_pt=14.0,
            min_section_margin_pt=10.0,
            target_item_gap_pt=6.0,
            min_item_gap_pt=4.0,
            target_line_height=1.45,
            min_line_height=1.35,
        )

        # 1. Zero overflow: all target
        b0 = SpringsGlueBudgeter.solve_budget(0.0, cfg)
        self.assertEqual(b0["body_font_pt"], 10.0)
        self.assertEqual(b0["section_margin_pt"], 14.0)
        self.assertEqual(b0["item_gap_pt"], 6.0)
        self.assertEqual(b0["line_height"], 1.45)

        # 2. Minor overflow (15px): absorbed entirely by section margins
        b1 = SpringsGlueBudgeter.solve_budget(15.0, cfg)
        self.assertEqual(b1["body_font_pt"], 10.0)      # Font size UNTOUCHED
        self.assertEqual(b1["line_height"], 1.45)       # Line height UNTOUCHED
        self.assertEqual(b1["item_gap_pt"], 6.0)        # Item gap UNTOUCHED
        self.assertLess(b1["section_margin_pt"], 14.0)  # Margins absorbed it
        self.assertTrue(b1["solved"])

        # 3. Moderate overflow (45px): absorbed by section margins & item gaps
        b2 = SpringsGlueBudgeter.solve_budget(45.0, cfg)
        self.assertEqual(b2["body_font_pt"], 10.0)      # Font size UNTOUCHED
        self.assertEqual(b2["line_height"], 1.45)       # Line height UNTOUCHED
        self.assertEqual(b2["section_margin_pt"], 10.0) # Margins reached min
        self.assertLess(b2["item_gap_pt"], 6.0)         # Item gaps absorbed remainder
        self.assertTrue(b2["solved"])

        # 4. Large overflow (110px): absorbed by margins, gaps, padding, and line height
        b3 = SpringsGlueBudgeter.solve_budget(110.0, cfg)
        self.assertEqual(b3["body_font_pt"], 10.0)      # Font size STILL 10.0pt!
        self.assertLess(b3["line_height"], 1.45)        # Line height absorbed it
        self.assertTrue(b3["solved"])

        # 5. Heavy overflow (180px): font size finally participates, but stays >= 9.5pt
        b4 = SpringsGlueBudgeter.solve_budget(180.0, cfg)
        self.assertLess(b4["body_font_pt"], 10.0)
        self.assertGreaterEqual(b4["body_font_pt"], 9.5)

    # =========================================================================
    # 4. 验证课程名完整保留且多列/换行自适应
    # =========================================================================

    def test_term_abbreviations_strictly_restored(self):
        """Restores destructive abbreviations like 'Math Stats' and 'Civil Eng.' back to full academic titles."""
        input_text = "Courses include Math Stats, Civil Eng., and Econ."
        restored, prevented = CourseworkGridAdapter.restore_abbreviations(input_text)
        self.assertIn("Probability and Mathematical Statistics", restored)
        self.assertIn("Civil Engineering", restored)
        self.assertIn("Economics", restored)
        self.assertNotIn("Math Stats", restored)
        self.assertNotIn("Civil Eng.", restored)
        self.assertEqual(len(prevented), 3)

    def test_adaptive_coursework_grid_generates_2_column_flow_for_long_titles(self):
        """Long course titles automatically get a 2-column grid allowing natural multi-line wrapping."""
        long_courses = [
            "Probability and Mathematical Statistics",
            "Engineering Project Management",
            "Distributed Systems Architecture",
            "Object-Oriented Programming and Design Patterns",
        ]
        grid_html = CourseworkGridAdapter.format_adaptive_coursework_grid(long_courses)
        self.assertIn("repeat(2, 1fr)", grid_html)
        self.assertIn("adaptive-coursework-container", grid_html)
        self.assertIn("white-space:normal", grid_html)
        self.assertIn("Probability&nbsp;and&nbsp;Mathematical&nbsp;Statistics", grid_html)

    def test_adaptive_coursework_grid_for_short_titles(self):
        """Short course titles can use a 3-column compact grid."""
        short_courses = ["Calculus", "Physics", "Linear Algebra", "Algorithms"]
        grid_html = CourseworkGridAdapter.format_adaptive_coursework_grid(short_courses)
        self.assertIn("repeat(3, 1fr)", grid_html)

    def test_coursework_adaptation_in_html(self):
        """HTML coursework block is dynamically transformed into adaptive flow grid with restored terms."""
        cfg = LayoutConfig(allow_term_abbreviation=False)
        html = '<div><b>核心课程：</b>Math Stats, Civil Eng., Econ</div>'
        adapted, prevented = CourseworkGridAdapter.adapt_coursework_in_html(html, cfg)
        self.assertIn("adaptive-coursework-container", adapted)
        self.assertIn("Probability&nbsp;and&nbsp;Mathematical&nbsp;Statistics", adapted)
        self.assertIn("Civil&nbsp;Engineering", adapted)
        self.assertGreaterEqual(len(prevented), 3)

    # =========================================================================
    # 5. 验证 HTML 注入与 CSS 规则生成
    # =========================================================================

    def test_inject_micro_typography_into_head(self):
        """Injects style block right before </head> when head tag is present."""
        html = "<html><head><title>Test</title></head><body><p>Hello World</p></body></html>"
        injected = inject_micro_typography(html)
        self.assertIn('<style id="offerget-micro-typography">', injected)
        self.assertIn("</style>\n</head>", injected)

    def test_inject_micro_typography_into_headless_html(self):
        """Prepends style block when HTML lacks <head>."""
        html = "<p>Fragment text with Civil Engineering</p>"
        injected = inject_micro_typography(html)
        self.assertTrue(injected.startswith('<style id="offerget-micro-typography">'))
        self.assertIn("Civil&nbsp;Engineering", injected)

    def test_solve_layout_e2e_full_flow(self):
        """End-to-end execution of solve_layout verifying result attributes."""
        res: LayoutSolveResult = solve_layout(self.sample_html, overflow_px=50.0)
        self.assertTrue(res.solved)
        self.assertEqual(res.body_font_pt, 10.0)  # Preserved at 10pt!
        self.assertGreaterEqual(res.orphans_mitigated, 1)
        self.assertGreaterEqual(len(res.abbreviations_prevented), 2)
        self.assertIn("adaptive-coursework-container", res.html)
        self.assertIn("Civil&nbsp;Engineering", res.html)
        self.assertIn('<style id="offerget-micro-typography">', res.html)

    # =========================================================================
    # 6. 集成测试：ResumeBuilder 与 AcademicExporter
    # =========================================================================

    def test_integration_with_resume_builder(self):
        """ResumeBuilder solve_resume_layout and build_html_theme seamlessly apply micro-typography."""
        mock_renderer = FastBrowserRenderer()
        minimal_profile = {
            "name": "张测试",
            "phone": "13800000000",
            "email": "zhang@example.com",
            "city": "杭州",
            "intent": "软件架构师",
            "education": {
                "school": "浙江大学",
                "major": "计算机科学与技术",
                "degree": "硕士",
                "time": "2020 - 2023",
                "courses": "Probability and Mathematical Statistics, Civil Engineering",
            },
            "experience": [
                {
                    "company": "字节跳动",
                    "role": "研发工程师",
                    "time": "2022 - 2023",
                    "bullets": ["负责分布式系统微服务架构优化与高可用容灾"],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = ResumeBuilder(
                profile_or_path=minimal_profile,
                renderer=mock_renderer,
            )

            # Test solve_resume_layout interface
            solve_res = builder.solve_resume_layout(self.sample_html, overflow_px=25.0)
            self.assertTrue(solve_res.solved)
            self.assertEqual(solve_res.body_font_pt, 10.0)

            # Test build_html_theme injects micro-typography
            out_files = builder.build_html_theme(
                theme_name="modern-navy",
                output_dir=tmp_dir,
                autofit=False,
            )
            html_content = Path(out_files["html"]).read_text(encoding="utf-8")
            self.assertIn("offerget-micro-typography", html_content)
            self.assertIn("text-wrap: pretty;", html_content)

    def test_integration_with_academic_exporter(self):
        """AcademicExporter.generate_latex_html_preview automatically injects micro-typography rules."""
        profile = {
            "name": "李学者",
            "title": "清华大学计算机系",
            "email": "li@tsinghua.edu.cn",
            "school": "清华大学",
            "degree": "博士研究生",
            "edu_time": "2021.09 - 2026.06",
            "education": {
                "school": "清华大学",
                "degree": "博士",
                "courses": "Probability and Mathematical Statistics, Advanced Data Structures",
            },
            "experience": [
                {
                    "org": "微软亚洲研究院",
                    "role": "研究实习生",
                    "time": "2023 - 2024",
                    "bullets": ["研发大规模图神经网络加速引擎与分布式计算优化"],
                }
            ],
        }
        exporter = AcademicExporter()
        preview_html = exporter.generate_latex_html_preview(profile)
        self.assertIn("offerget-micro-typography", preview_html)
        self.assertIn("text-wrap: pretty;", preview_html)
        self.assertIn("text-wrap: balance;", preview_html)
        self.assertIn("Probability&nbsp;and&nbsp;Mathematical&nbsp;Statistics", preview_html)

    def test_underflow_springs_expansion(self):
        """Underflow (negative overflow: content underfills page) triggers elastic expansion to fill the page."""
        cfg = LayoutConfig(
            target_body_font_pt=10.0,
            target_line_height=1.45,
            target_section_margin_pt=14.0,
            max_section_margin_pt=20.0,
            target_item_gap_pt=6.0,
            max_item_gap_pt=10.0,
        )
        res = solve_layout("<p>Short resume content</p>", overflow_px=-80.0, config=cfg)
        self.assertTrue(res.solved)
        self.assertTrue(res.is_expanded_to_fill)
        self.assertGreater(res.section_margin_pt, 14.0)
        self.assertGreater(res.item_gap_pt, 6.0)
        self.assertGreater(res.line_height, 1.45)
        self.assertFalse(res.requires_page_expansion_prompt)

    def test_unsolvable_overflow_triggers_page_expansion_prompt(self):
        """Massive overflow exceeding single-page compression capacity triggers user multi-page prompt."""
        cfg = LayoutConfig(
            min_body_font_pt=9.5,
            target_body_font_pt=10.0,
            min_section_margin_pt=10.0,
            min_item_gap_pt=4.0,
            min_line_height=1.35,
        )
        # 1000px overflow cannot be safely compressed into 1 page at 9.5pt floor
        res = solve_layout("<p>Massive 5-page resume content</p>", overflow_px=1000.0, config=cfg)
        self.assertFalse(res.solved)
        self.assertTrue(res.requires_page_expansion_prompt)
        self.assertIsNotNone(res.page_expansion_prompt_message)
        self.assertIn("双页排版", res.page_expansion_prompt_message)
        self.assertIn("9.5pt", res.page_expansion_prompt_message)


if __name__ == "__main__":
    unittest.main()

