"""
Tests for OfferGet Unified Resume Builder Engine (tests/test_resume_builder.py)
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.resume_builder import ResumeBuilder, audit_resume_quality


class TestResumeBuilder(unittest.TestCase):

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
        builder = ResumeBuilder(self.minimal_profile)
        for theme in ["modern-navy", "silicon-clean", "classic-tech"]:
            res = builder.build_html_theme(theme, self.test_dir, photo=True, autofit=True)
            self.assertTrue(res["html"].exists())
            self.assertTrue(res["pdf"].exists())
            html_text = res["html"].read_text(encoding="utf-8")
            self.assertIn("测试候选人", html_text)
            self.assertIn("预留证件照", html_text)
            # Ensure no dirty _raw.html left behind
            raw_path = self.test_dir / f"resume_{theme.replace('-', '_')}_raw.html"
            self.assertFalse(raw_path.exists())


    def test_build_all(self):
        builder = ResumeBuilder(self.minimal_profile)
        results = builder.build_all(self.test_dir, photo=True, autofit=True)
        self.assertEqual(len(results), 6)
        for theme_name, files in results.items():
            self.assertTrue(files["pdf"].exists(), f"{theme_name} PDF must exist")


    def test_default_photo_reservation_placeholder(self):
        """Test default behavior: perfectly preserves dashed photo reservation placeholder box."""
        builder = ResumeBuilder(self.minimal_profile)
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
        builder = ResumeBuilder(self.minimal_profile, photo_path=sample_img)
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
        builder = ResumeBuilder(self.minimal_profile, anonymize="strict")
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
        normal_builder = ResumeBuilder(self.minimal_profile)
        res_ats = normal_builder.build_ats_plain(self.test_dir, anonymize="strict")
        ats_content = res_ats["html"].read_text(encoding="utf-8")
        self.assertNotIn("测试候选人", ats_content)
        self.assertIn("Dr. Alex Chen", ats_content)
        self.assertNotIn("浙江大学", ats_content)

    def test_audit_resume_quality(self):
        """Test quality audit gate on valid generated resumes and defective HTML."""
        builder = ResumeBuilder(self.minimal_profile)
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
        mod_report = audit_resume_quality(res["html"])
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


if __name__ == "__main__":
    unittest.main()


