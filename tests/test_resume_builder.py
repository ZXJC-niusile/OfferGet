"""
Tests for OfferGet Unified Resume Builder Engine (tests/test_resume_builder.py)
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.resume_builder import ResumeBuilder


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


if __name__ == "__main__":
    unittest.main()

