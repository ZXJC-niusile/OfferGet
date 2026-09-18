"""
Tests for OfferGet Academic Exporter Engine (tests/test_academic_exporter.py)
"""

import tempfile
import unittest
from pathlib import Path

from core.academic_exporter import AcademicExporter, escape_latex, escape_typst
from core.security_gate import validate_output_security


class TestAcademicExporter(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="offerget_test_academic_"))
        self.sample_profile = {
            "candidate": {
                "name": "张三",
                "title": "算法研究员",
                "email": "zhangsan@example.com",
                "phone": "+86 138-0000-0000",
                "school": "清华大学",
                "degree": "硕士 · 计算机科学",
                "location": "北京",
                "edu_time": "2021.09 - 2024.06",
                "reserve_photo": False,
                "education_rows": [
                    ["GPA 3.9/4.0", "国家奖学金", "CET-6 630"],
                    ["CCF 优秀大学生", "ACM-ICPC 区域金牌"],
                ],
            },
            "experience": [
                {
                    "org": "微软亚洲研究院",
                    "dept": "系统组",
                    "role": "研究实习生",
                    "time": "2023.03 - 2023.12",
                    "bullets": [
                        "设计分布式调度系统，吞吐提升 **40%**",
                        "发表系统顶会论文 1 篇",
                    ],
                }
            ],
            "projects": [
                {
                    "name": "高性能推理引擎",
                    "role": "核心研发",
                    "time": "2022.09 - 2023.02",
                    "bullets": [
                        "重构算子融合逻辑，延迟降低 **25%**",
                    ],
                }
            ],
            "publications": [
                {
                    "title": "Accelerating LLM Inference via Adaptive Kernel Fusion",
                    "venue": "OSDI 2024",
                }
            ],
            "competencies": {
                "编程语言": ["C++", "Python", "Rust"],
                "框架工具": ["PyTorch", "CUDA", "vLLM"],
            },
        }
        self.exporter = AcademicExporter()

    def test_generate_latex_structure_and_escaping(self):
        tex = self.exporter.generate_latex(self.sample_profile, reserve_photo=False)
        self.assertIn(r"\documentclass[a4paper,11pt]{article}", tex)
        self.assertIn("张三", tex)
        self.assertIn("算法研究员", tex)
        self.assertIn(r"\textbf{清华大学}", tex)
        self.assertIn("OSDI 2024", tex)
        self.assertIn(r"\textbf{40\%}", tex)
        self.assertIn(r"\textbf{25\%}", tex)
        self.assertIn(r"\end{document}", tex)

    def test_generate_latex_photo_reservation(self):
        # Default with photo
        tex_photo = self.exporter.generate_latex(self.sample_profile, reserve_photo=True)
        self.assertIn(r"\fbox", tex_photo)
        self.assertIn("预留证件照", tex_photo)

        # With mock image path
        dummy_img = self.test_dir / "avatar.jpg"
        dummy_img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 10)
        tex_with_img = self.exporter.generate_latex(self.sample_profile, reserve_photo=True, photo_path=dummy_img)
        self.assertIn(r"\includegraphics", tex_with_img)
        self.assertIn("avatar.jpg", tex_with_img)

    def test_generate_typst_structure_and_escaping(self):
        typ = self.exporter.generate_typst(self.sample_profile, reserve_photo=False)
        self.assertIn('#set page(paper: "a4"', typ)
        self.assertIn("张三", typ)
        self.assertIn("算法研究员", typ)
        self.assertIn("*清华大学*", typ)
        self.assertIn("== 学术发表与代表作", typ)
        self.assertIn("*Accelerating LLM Inference via Adaptive Kernel Fusion*", typ)
        self.assertIn("_OSDI 2024_", typ)
        self.assertIn("*40%*", typ)
        self.assertIn("*25%*", typ)

    def test_generate_typst_photo_reservation(self):
        typ_rect = self.exporter.generate_typst(self.sample_profile, reserve_photo=True)
        self.assertIn("#rect(", typ_rect)
        self.assertIn("预留证件照", typ_rect)

        dummy_img = self.test_dir / "photo.png"
        dummy_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
        typ_img = self.exporter.generate_typst(self.sample_profile, reserve_photo=True, photo_path=dummy_img)
        self.assertIn("#image(", typ_img)
        self.assertIn("photo.png", typ_img)

    def test_generate_latex_html_preview_security(self):
        html_src = self.exporter.generate_latex_html_preview(self.sample_profile, reserve_photo=True)
        self.assertIn("张三", html_src)
        self.assertIn("算法研究员", html_src)
        self.assertIn("清华大学", html_src)
        # Security audit
        risks = validate_output_security(html_src, format_type="html")
        self.assertEqual(risks, [])

    def test_special_chars_escaping(self):
        raw_text = r"Testing \ & % $ # _ { } ~ ^ in LaTeX and # [ ] * _ @ $ ` \ in Typst"
        tex_esc = escape_latex(raw_text)
        self.assertIn(r"\textbackslash{}", tex_esc)
        self.assertIn(r"\&", tex_esc)
        self.assertIn(r"\%", tex_esc)
        self.assertIn(r"\$", tex_esc)
        self.assertIn(r"\#", tex_esc)
        self.assertIn(r"\_", tex_esc)
        self.assertIn(r"\{", tex_esc)
        self.assertIn(r"\}", tex_esc)
        self.assertIn(r"\textasciitilde{}", tex_esc)
        self.assertIn(r"\textasciicircum{}", tex_esc)

        typ_esc = escape_typst(raw_text)
        self.assertIn(r"\#", typ_esc)
        self.assertIn(r"\[", typ_esc)
        self.assertIn(r"\]", typ_esc)
        self.assertIn(r"\*", typ_esc)
        self.assertIn(r"\_", typ_esc)
        self.assertIn(r"\@", typ_esc)
        self.assertIn(r"\$", typ_esc)
        self.assertIn(r"\`", typ_esc)
        self.assertIn(r"\\", typ_esc)


if __name__ == "__main__":
    unittest.main()
