"""
Tests for OfferGet Unified Resume Builder Engine (tests/test_resume_builder.py)
"""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.resume_builder import ResumeBuilder, audit_resume_quality
from core.resume_view_model import ResumeViewModel

from core.browser_renderer import BrowserRenderer


class FastBrowserRenderer(BrowserRenderer):
    """A lightweight headless browser renderer for unit tests that generates valid A4 PDFs
    instantly without spawning heavy headless Chromium processes.
    """
    MINIMAL_PDF_BYTES = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n164\n%%EOF\n"
    )

    def __init__(self, browser_path: str = "fast-test-renderer"):
        self.browser_path = browser_path

    def render_pdf(self, html_path, pdf_path, timeout_seconds=30):
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(self.MINIMAL_PDF_BYTES)
        return True, 1, f"Fast test render 1 page ({len(self.MINIMAL_PDF_BYTES)} bytes)"

    def count_pages(self, pdf_path):
        return 1

    def measure_overflow(self, html_path, a4_target_height=1122.5):
        return 1000, 0


class TestResumeBuilder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fast_renderer = FastBrowserRenderer()

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="offerget_test_resumes_"))
        self.minimal_profile = {
            "name": "测试候选人",
            "phone": "+86 188-0000-0000",
            "email": "test@example.com",
            "city": "杭州",
            "intent": "运营主管",
            "education": {
                "school": "浙江大学",
                "major": "计算机科学与技术",
                "degree": "硕士",
                "time": "2023.09 - 2026.06",
                "gpa": "3.8/4.0",
                "awards": "一等奖学金",
                "certificates": "CET6 600",
            },
            "experience": [
                {
                    "company": "字节跳动",
                    "role": "产品运营",
                    "time": "2025.03 - 2025.09",
                    "bullets": ["提升活跃度 30%", "搭建数据看板"],
                }
            ],
            "campus_experience": [
                {
                    "name": "学生会",
                    "role": "主席",
                    "time": "2023.09 - 2024.06",
                    "bullets": ["统筹举办各类活动"],
                }
            ],
            "skills": {
                "办公软件": "Python, SQL, Excel",
                "语言能力": "CET-6",
            },
        }
        self.profile_json_path = self.test_dir / "profile.json"
        with open(self.profile_json_path, "w", encoding="utf-8") as f:
            json.dump(self.minimal_profile, f, ensure_ascii=False)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_with_minimal_profile_dict(self):
        builder = ResumeBuilder(self.minimal_profile)
        self.assertEqual(builder.profile["candidate"]["name"], "测试候选人")
        self.assertEqual(builder.profile["candidate"]["title"], "运营主管")
        self.assertEqual(builder.profile["candidate"]["school"], "浙江大学")
        self.assertEqual(len(builder.profile["experience"]), 1)

    def test_init_with_json_path(self):
        builder = ResumeBuilder(self.profile_json_path)
        self.assertEqual(builder.profile["candidate"]["name"], "测试候选人")
        self.assertIn("modern-navy", builder.THEMES)

    def test_build_ats_plain(self):
        builder = ResumeBuilder(self.minimal_profile)
        res = builder.build_ats_plain(self.test_dir, photo=True)
        self.assertTrue(res["md"].exists())
        self.assertTrue(res["html"].exists())
        self.assertTrue(res["pdf"].exists())
        md_text = res["md"].read_text(encoding="utf-8")
        self.assertIn("测试候选人", md_text)
        self.assertIn("预留证件照位置", md_text)

    def test_build_academic_latex(self):
        builder = ResumeBuilder(self.minimal_profile)
        res = builder.build_academic_latex(self.test_dir, photo=True)
        self.assertTrue(res["tex"].exists())
        self.assertTrue(res["html"].exists())
        self.assertTrue(res["pdf"].exists())
        tex_text = res["tex"].read_text(encoding="utf-8")
        self.assertIn("测试候选人", tex_text)
        self.assertIn("fbox", tex_text)

    def test_build_academic_typst(self):
        builder = ResumeBuilder(self.minimal_profile)
        res = builder.build_academic_typst(self.test_dir, photo=True)
        self.assertTrue(res["typ"].exists())
        self.assertTrue(res["pdf"].exists())
        typ_text = res["typ"].read_text(encoding="utf-8")
        self.assertIn("测试候选人", typ_text)

    def test_build_html_themes(self):
        # 1. Full end-to-end integration test with real AutoFitEngine and Chromium rasterization
        builder = ResumeBuilder(self.minimal_profile)
        res = builder.build_html_theme("modern-navy", self.test_dir, photo=True, autofit=True)
        self.assertTrue(res["html"].exists())
        self.assertTrue(res["pdf"].exists())
        html_text = res["html"].read_text(encoding="utf-8")
        self.assertIn("测试候选人", html_text)
        self.assertIn("预留证件照", html_text)
        raw_path = self.test_dir / "resume_modern_navy_raw.html"
        self.assertFalse(raw_path.exists())

        # 2. Test multi-theme template population & cleanup with fast renderer to avoid redundant Chromium launches
        fast_builder = ResumeBuilder(self.minimal_profile, renderer=self.fast_renderer)
        for theme in ["silicon-clean", "classic-tech"]:
            res = fast_builder.build_html_theme(theme, self.test_dir, photo=True, autofit=True)
            self.assertTrue(res["html"].exists())
            self.assertTrue(res["pdf"].exists())
            html_text = res["html"].read_text(encoding="utf-8")
            self.assertIn("测试候选人", html_text)
            self.assertIn("预留证件照", html_text)
            raw_path = self.test_dir / f"resume_{theme.replace('-', '_')}_raw.html"
            self.assertFalse(raw_path.exists())

    def test_build_all(self):
        # Uses FastBrowserRenderer to verify multi-theme dispatch across all 11 themes cleanly
        builder = ResumeBuilder(self.minimal_profile, renderer=self.fast_renderer)
        results = builder.build_all(self.test_dir, photo=True, autofit=True)
        self.assertEqual(len(results), len(builder.PDF_THEMES))
        for theme_name, files in results.items():
            self.assertTrue(files["pdf"].exists(), f"{theme_name} PDF must exist")

    def test_default_photo_reservation_placeholder(self):
        """Test default behavior: perfectly preserves dashed photo reservation placeholder box."""
        builder = ResumeBuilder(self.minimal_profile, renderer=self.fast_renderer)
        # 1. HTML theme
        res_html = builder.build_html_theme("modern-navy", self.test_dir, photo=True)
        html_content = res_html["html"].read_text(encoding="utf-8")
        self.assertIn("photo-placeholder", html_content)
        self.assertIn("预留证件照", html_content)
        self.assertIn("一寸 / 二寸", html_content)
        self.assertNotIn("src=\"data:image/", html_content)

        # 2. ATS plain
        res_ats = builder.build_ats_plain(self.test_dir, photo=True)
        ats_html = res_ats["html"].read_text(encoding="utf-8")
        self.assertIn("预留证件照", ats_html)
        self.assertIn("一寸 / 二寸", ats_html)
        self.assertNotIn("<img", ats_html)
        ats_md = res_ats["md"].read_text(encoding="utf-8")
        self.assertIn("预留证件照位置", ats_md)

        # 3. Academic LaTeX
        res_latex = builder.build_academic_latex(self.test_dir, photo=True)
        tex_content = res_latex["tex"].read_text(encoding="utf-8")
        self.assertIn(r"\fbox", tex_content)
        self.assertIn("预留证件照", tex_content)
        self.assertNotIn(r"\includegraphics", tex_content)

        # 4. Academic Typst
        res_typ = builder.build_academic_typst(self.test_dir, photo=True)
        typ_content = res_typ["typ"].read_text(encoding="utf-8")
        self.assertIn("#rect", typ_content)
        self.assertIn("预留证件照", typ_content)
        self.assertNotIn("#image(", typ_content)

    def test_photo_path_base64_embedded(self):
        """Test providing a valid local image embeds base64 data URI with onerror fallback."""
        # Create a valid minimal 1x1 PNG image
        dummy_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
            b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        sample_img = self.test_dir / "candidate_avatar.png"
        sample_img.write_bytes(dummy_png)

        # Test building HTML theme with photo_path
        builder = ResumeBuilder(self.minimal_profile, photo_path=sample_img, renderer=self.fast_renderer)
        res_html = builder.build_html_theme("modern-navy", self.test_dir)
        html_content = res_html["html"].read_text(encoding="utf-8")

        self.assertIn("photo-placeholder", html_content)
        self.assertIn("<img", html_content)
        self.assertIn("src=\"data:image/png;base64,", html_content)
        self.assertIn("onerror=", html_content)
        self.assertIn("预留证件照", html_content)  # Fallback exists

        # Test ATS plain with photo_path
        res_ats = builder.build_ats_plain(self.test_dir)
        ats_html = res_ats["html"].read_text(encoding="utf-8")
        self.assertIn("src=\"data:image/png;base64,", ats_html)
        self.assertIn("onerror=", ats_html)

        # Test Academic LaTeX with photo_path
        res_latex = builder.build_academic_latex(self.test_dir)
        tex_content = res_latex["tex"].read_text(encoding="utf-8")
        self.assertIn(r"\includegraphics", tex_content)
        self.assertIn("candidate_avatar.png", tex_content)

        # Test Academic Typst with photo_path
        res_typ = builder.build_academic_typst(self.test_dir)
        typ_content = res_typ["typ"].read_text(encoding="utf-8")
        self.assertIn("#image(", typ_content)
        self.assertIn("candidate_avatar.png", typ_content)

    def test_anonymize_strict_resume_generation(self):
        """Test --anonymize strict masks PII, institutions, companies, and projects."""
        # 1. Initialize with anonymize="strict"
        builder = ResumeBuilder(self.minimal_profile, anonymize="strict", renderer=self.fast_renderer)
        self.assertEqual(builder.profile["candidate"]["name"], "Dr. Alex Chen")
        self.assertIn("Top-Tier C9 Research University", builder.profile["candidate"]["school"])
        self.assertEqual(builder.profile["experience"][0]["company"], "Tech Conglomerate Beta")

        # Build theme
        res = builder.build_html_theme("modern-navy", self.test_dir)
        html_content = res["html"].read_text(encoding="utf-8")
        self.assertNotIn("测试候选人", html_content)
        self.assertIn("Dr. Alex Chen", html_content)
        self.assertNotIn("浙江大学", html_content)
        self.assertIn("Top-Tier C9 Research University", html_content)
        self.assertNotIn("字节跳动", html_content)
        self.assertIn("Tech Conglomerate Beta", html_content)
        self.assertNotIn("test@example.com", html_content)

        # 2. Test passing anonymize directly to build method on a normal builder
        normal_builder = ResumeBuilder(self.minimal_profile, renderer=self.fast_renderer)
        res_ats = normal_builder.build_ats_plain(self.test_dir, anonymize="strict")
        ats_content = res_ats["html"].read_text(encoding="utf-8")
        self.assertNotIn("测试候选人", ats_content)
        self.assertIn("Dr. Alex Chen", ats_content)
        self.assertNotIn("浙江大学", ats_content)

    def test_audit_resume_quality(self):
        """Test quality audit gate on valid generated resumes and defective HTML."""
        builder = ResumeBuilder(self.minimal_profile, renderer=self.fast_renderer)
        res = builder.build_html_theme("modern-navy", self.test_dir)

        # 1. Audit clean generated resume
        report = builder.audit_resume_quality(res["html"])
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(report["health_score"], 80)
        self.assertEqual(report["critical_count"], 0)
        self.assertIn("placeholders", report["checks"])
        self.assertIn("dangerous_tags", report["checks"])
        self.assertIn("page_overflow", report["checks"])
        self.assertTrue(report["checks"]["placeholders"]["passed"])
        self.assertTrue(report["checks"]["dangerous_tags"]["passed"])
        self.assertTrue(report["checks"]["page_overflow"]["passed"])

        # Also test standalone module-level function
        mod_report = audit_resume_quality(res["html"], renderer=self.fast_renderer)
        self.assertEqual(mod_report["passed"], report["passed"])
        self.assertEqual(mod_report["score"], report["score"])

        # 2. Audit defective HTML with unreplaced placeholders and dangerous tags
        dirty_html_path = self.test_dir / "defective_resume.html"
        dirty_html_path.write_text(
            "<!DOCTYPE html><html><body>"
            "<h1>Candidate Name</h1>"
            "<div>{{UNRENDERED_PLACEHOLDER}}</div>"
            "<span class=\"todo\">[待补充项目详情]</span>"
            "<script>window.location='http://attacker.com';</script>"
            "</body></html>",
            encoding="utf-8",
        )

        dirty_report = builder.audit_resume_quality(dirty_html_path)
        self.assertFalse(dirty_report["passed"])
        self.assertGreater(dirty_report["critical_count"], 0)
        self.assertFalse(dirty_report["checks"]["placeholders"]["passed"])
        self.assertFalse(dirty_report["checks"]["dangerous_tags"]["passed"])
        self.assertLess(dirty_report["health_score"], 70)

    def test_compact_education_formatting(self):
        """Test that education details are formatted into compact rows across all templates without vertical pipes."""
        profile = {
            "name": "张明",
            "candidate": {
                "name": "张明",
                "title": "运营岗",
                "school": "华东理工大学",
                "degree": "土木工程  本科在读",
                "edu_time": "2023.09—2027.06",
                "education_rows": [
                    [
                        "GPA 3.12，专业前15%",
                        "文体优秀奖学金",
                        "CET-4 506",
                    ],
                    [
                        "全国计算机二级（WPS Office）",
                        "普通话二级乙等",
                    ],
                ],
            },
            "experience": [],
        }
        builder = ResumeBuilder(profile, renderer=self.fast_renderer)

        # 1. HTML theme
        res_html = builder.build_html_theme("modern-navy", self.test_dir)
        html_text = res_html["html"].read_text(encoding="utf-8")
        self.assertIn("华东理工大学", html_text)
        self.assertIn("土木工程", html_text)
        self.assertIn("2023.09—2027.06", html_text)
        self.assertIn("edu-grid", html_text)
        self.assertIn("GPA 3.12，专业前15%", html_text)
        self.assertIn("文体优秀奖学金", html_text)
        self.assertIn("CET-4 506", html_text)
        self.assertIn("全国计算机二级（WPS Office）", html_text)
        self.assertIn("普通话二级乙等", html_text)
        # Ensure no vertical bar in education section header or grid
        edu_sec = html_text[html_text.find('<section id="education">'):html_text.find('</section>')]
        self.assertNotIn("｜", edu_sec)

        # 2. ATS plain
        res_ats = builder.build_ats_plain(self.test_dir)
        ats_md = res_ats["md"].read_text(encoding="utf-8")
        ats_html = res_ats["html"].read_text(encoding="utf-8")
        self.assertIn("华东理工大学", ats_md)
        self.assertIn("GPA 3.12，专业前15%", ats_md)
        self.assertIn("全国计算机二级（WPS Office）", ats_md)
        self.assertIn("edu-grid", ats_html)
        # Ensure ATS HTML education section has no vertical bars
        ats_edu_sec = ats_html[ats_html.find('<h2>教育背景</h2>'):ats_html.find('<h2>实习经历</h2>') if '<h2>实习经历</h2>' in ats_html else len(ats_html)]
        self.assertNotIn("｜", ats_edu_sec)

        # 3. Academic LaTeX
        res_latex = builder.build_academic_latex(self.test_dir)
        tex_text = res_latex["tex"].read_text(encoding="utf-8")
        self.assertIn(r"\textbf{华东理工大学}", tex_text)
        self.assertIn(r"2023.09—2027.06", tex_text)
        self.assertIn(r"\begin{tabular}", tex_text)
        self.assertIn(r"GPA 3.12，专业前15\%", tex_text)
        self.assertIn(r"全国计算机二级（WPS Office）", tex_text)

        # 4. Academic Typst
        res_typ = builder.build_academic_typst(self.test_dir)
        typ_text = res_typ["typ"].read_text(encoding="utf-8")
        self.assertIn("*华东理工大学*", typ_text)
        self.assertIn("2023.09—2027.06", typ_text)
        self.assertIn("#grid(", typ_text)
        self.assertIn("[GPA 3.12，专业前15%]", typ_text)
        self.assertIn("[全国计算机二级（WPS Office）]", typ_text)

    def test_resume_builder_view_model_caching(self):
        """Test ResumeBuilder caches ResumeViewModel across multiple theme renders."""
        builder = ResumeBuilder(self.minimal_profile)
        vm1 = builder._get_view_model()
        vm2 = builder._get_view_model()
        self.assertIs(vm1, vm2)

        # Header and sections reuse the same cached view model
        header_html = builder._render_header_html("modern-navy")
        self.assertIn("测试候选人", header_html)
        self.assertIs(builder._get_view_model(), vm1)

        # Passing identical content in a separate dict reuses cached VM due to SHA-256 fingerprint
        dup_profile = copy.deepcopy(self.minimal_profile)
        vm_dup = builder._get_view_model(profile=dup_profile)
        self.assertIs(vm1, vm_dup)

        # Modifying content invalidates cache key and creates a fresh ViewModel
        modified_profile = copy.deepcopy(builder.profile)
        modified_profile["candidate"]["name"] = "王五"
        vm_mod = builder._get_view_model(profile=modified_profile)
        self.assertIsNot(vm1, vm_mod)
        self.assertEqual(vm_mod.name, "王五")

    def test_resume_builder_anonymization_view_model_isolation(self):
        """Test that different anonymization levels produce distinct ViewModels."""
        builder = ResumeBuilder(self.minimal_profile)
        vm_raw = builder._get_view_model()

        prof_std = builder._resolve_profile(anonymize="standard")
        vm_std = builder._get_view_model(profile=prof_std)
        self.assertIsNot(vm_raw, vm_std)

        prof_strict = builder._resolve_profile(anonymize="strict")
        vm_strict = builder._get_view_model(profile=prof_strict)
        self.assertIsNot(vm_std, vm_strict)
        self.assertEqual(vm_strict.name, "Dr. Alex Chen")

    def test_resume_builder_with_profile_context(self):
        """Test ResumeBuilder seamlessly accepts ProfileContext."""
        from core.profile_adapter import build_profile_context

        ctx = build_profile_context(self.minimal_profile)
        builder = ResumeBuilder(ctx)
        self.assertEqual(builder.profile["candidate"]["name"], "测试候选人")
        self.assertIsInstance(builder.view_model, ResumeViewModel)
        self.assertEqual(builder.view_model.name, "测试候选人")


    def test_resume_builder_no_repeated_normalization_in_rendering(self):
        """Test that ResumeBuilder does not call normalize_candidate_profile during rendering."""
        from unittest.mock import patch

        builder = ResumeBuilder(self.minimal_profile)
        with patch("core.resume_builder.normalize_candidate_profile") as mock_norm:
            vm1 = builder._get_view_model()
            vm2 = builder._get_view_model(profile=builder.profile)
            header = builder._render_header_html("modern-navy")
            sections = builder._render_sections_html("modern-navy")
            self.assertEqual(mock_norm.call_count, 0)
            self.assertIs(vm1, vm2)

    def test_resume_builder_raw_track1_profile_normalized(self):
        """Test that passing a raw Track 1 dict with candidate/institution/title_zh is properly normalized."""
        raw_track1 = {
            "candidate": {
                "name": "李雷",
                "title_zh": "大模型预训练工程师",
                "institution": "清华大学 (Tsinghua University)",
                "degree": "计算机硕士",
            },
            "experience": [
                {
                    "company": "前沿AI实验室",
                    "role": "算法工程师",
                    "period": "2022.06 - 2024.06",
                    "highlights": [
                        {
                            "claim_id": "EXP-1",
                            "claim_zh": "主导万卡集群Megatron预训练优化，提升MFU达50%",
                        }
                    ],
                }
            ],
        }

        builder = ResumeBuilder(self.minimal_profile)

        # 1. Passing raw unnormalized dict to _get_view_model must trigger normalization
        vm = builder._get_view_model(raw_track1)
        self.assertEqual(vm.name, "李雷")
        self.assertEqual(vm.edu_school, "清华大学 (Tsinghua University)")
        self.assertEqual(vm.title, "大模型预训练工程师")
        self.assertEqual(len(vm.experiences), 1)
        self.assertEqual(vm.experiences[0]["time"], "2022.06 - 2024.06")
        self.assertTrue(any("提升MFU达50%" in b for b in vm.experiences[0]["bullets"]))

        # 2. Passing ProfileContext must also work smoothly
        from core.profile_adapter import build_profile_context

        ctx = build_profile_context(raw_track1)
        vm_ctx = builder._get_view_model(ctx)
        self.assertEqual(vm_ctx.edu_school, "清华大学 (Tsinghua University)")
        self.assertEqual(vm_ctx.title, "大模型预训练工程师")

    def test_build_html_theme_adaptive_fill_and_diff_ledger(self):
        """Tests that build_html_theme uses LayoutSolver underflow expansion and saves DiffLedger files."""
        builder = ResumeBuilder(self.minimal_profile, renderer=self.fast_renderer)
        out_files = builder.build_html_theme(
            theme_name="classic-tech",
            output_dir=self.test_dir,
            autofit=True,
            adaptive_fill=True,
            diff_ledger=True,
            overflow_px=-80.0,
        )

        self.assertIn("html", out_files)
        self.assertIn("pdf", out_files)
        self.assertIn("diff_ledger_md", out_files)
        self.assertIn("diff_ledger_json", out_files)

        self.assertTrue(out_files["diff_ledger_md"].exists())
        self.assertTrue(out_files["diff_ledger_json"].exists())

        md_text = out_files["diff_ledger_md"].read_text(encoding="utf-8")
        self.assertIn("改动溯源与口径对齐报告", md_text)
        self.assertIn("测试候选人", md_text)

        html_text = out_files["html"].read_text(encoding="utf-8")
        self.assertIn("offerget-micro-typography", html_text)

    def test_cmd_resume_build_cli_flags(self):
        """Tests cmd_resume_build CLI command with --diff-ledger and --adaptive-fill."""
        from presentation.commands.resume_cmd import cmd_resume_build

        out_sub = self.test_dir / "cli_out"
        cmd_resume_build([
            str(self.profile_json_path),
            "--theme", "classic-tech",
            "--output-dir", str(out_sub),
            "--diff-ledger",
            "--adaptive-fill",
        ])

        html_path = out_sub / "resume_classic_tech.html"
        pdf_path = out_sub / "resume_classic_tech.pdf"
        diff_md = out_sub / "resume_diff_ledger.md"
        diff_json = out_sub / "resume_diff_ledger.json"

        self.assertTrue(html_path.exists())
        self.assertTrue(pdf_path.exists())
        self.assertTrue(diff_md.exists())
        self.assertTrue(diff_json.exists())


if __name__ == "__main__":
    unittest.main()



