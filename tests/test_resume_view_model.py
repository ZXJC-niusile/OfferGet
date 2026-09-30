"""
Tests for OfferGet Resume ViewModel & Decoupled Renderers (tests/test_resume_view_model.py)
==========================================================================================
Comprehensive tests for:
1. ResumeViewModel.from_profile field extraction and HTML/XSS sanitization.
2. HtmlThemeRenderer rendering of all 3 HTML themes (modern-navy, silicon-clean, classic-tech).
3. AtsPlainRenderer rendering of structured Markdown and single-column HTML.
4. Photo reservation placeholder vs. embedded base64 photo logic.
5. AutoFit single-page compaction engine integration with HtmlThemeRenderer.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.resume_view_model import (
    ResumeViewModel,
    HtmlThemeRenderer,
    AtsPlainRenderer,
    _image_to_base64_data_uri,
)
from core.security_gate import validate_output_security
from core.academic_exporter import AcademicExporter, escape_latex, escape_typst

try:
    from ApexResume.core.render import BrowserRenderer
    from ApexResume.core.autofit import AutoFitEngine
except ImportError:
    from core.render import BrowserRenderer  # type: ignore
    from core.autofit import AutoFitEngine    # type: ignore


class TestResumeViewModel(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="offerget_test_vm_"))
        self.sample_profile = {
            "name": "张三",
            "phone": "+86 138-0000-0000",
            "email": "zhangsan@example.com",
            "city": "杭州",
            "intent": "高级后端架构师",
            "education": {
                "school": "浙江大学",
                "major": "计算机科学与技术",
                "degree": "硕士 · 工学硕士",
                "time": "2023.09 - 2026.06",
                "gpa": "3.9/4.0",
                "awards": "国家奖学金",
                "certificates": "CET6 620",
            },
            "experience": [
                {
                    "company": "阿里巴巴",
                    "dept": "云原生团队",
                    "role": "研发专家",
                    "time": "2024.03 - 2025.09",
                    "bullets": [
                        "负责**分布式缓存集群**优化，提升吞吐量 **45%**",
                        "主导单元化架构演进，P99 延迟降低至 **12ms**",
                    ],
                }
            ],
            "campus_experience": [
                {
                    "name": "开源社区",
                    "role": "核心贡献者",
                    "time": "2023.09 - 2024.06",
                    "bullets": [
                        "维护高并发网络库，累计 **1.2k+ GitHub Stars**",
                    ],
                }
            ],
            "skills": {
                "核心语言": "Go, Python, C++, Rust",
                "中间件": ["Kafka", "Redis", "Etcd"],
            },
            "publications": [
                {
                    "title": "A Distributed Storage Engine",
                    "authors": "San Zhang, et al.",
                    "venue": "VLDB 2025",
                    "year": "2025",
                }
            ],
        }

        # Malicious profile for injection testing
        self.malicious_profile = {
            "name": "<script>alert('pwn_name')</script>",
            "phone": "+86 138-0000-0000",
            "email": "hacker@example.com",
            "city": "北京<script>",
            "intent": "安全研究员<iframe src='x'>",
            "education": {
                "school": "清华大学<script>",
                "degree": "博士 ｜ 计算机",
                "time": "2021.09 - 2025.06",
                "awards": "一等奖<img src=x onerror=alert(1)>",
            },
            "experience": [
                {
                    "company": "安全实验室<script>",
                    "dept": "RedTeam",
                    "role": "队长<img src=x onerror=alert('role')>",
                    "time": "2023.01 - 2024.01",
                    "bullets": [
                        "发现 **0-day** 漏洞：<script>alert('exploit')</script>",
                        "构造 payload: <iframe src='http://evil.com'>",
                    ],
                }
            ],
            "campus_experience": [
                {
                    "name": "CTF 战队<script>",
                    "role": "Leader",
                    "time": "2022 - 2023",
                    "bullets": ["带领团队荣获 **DefCon** 战队特等奖<script>"],
                }
            ],
            "skills": {
                "安全攻防<script>": "渗透测试<script>, 逆向工程",
            },
        }

        # 1x1 valid PNG image
        self.dummy_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
            b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self.sample_photo_path = self.test_dir / "candidate_photo.png"
        self.sample_photo_path.write_bytes(self.dummy_png)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_from_profile_field_construction(self):
        """Test ResumeViewModel.from_profile accurately parses and populates all fields."""
        vm = ResumeViewModel.from_profile(self.sample_profile)

        self.assertEqual(vm.name, "张三")
        self.assertEqual(vm.title, "高级后端架构师")
        self.assertEqual(vm.phone, "+86 138-0000-0000")
        self.assertEqual(vm.email, "zhangsan@example.com")
        self.assertEqual(vm.location, "杭州")
        self.assertEqual(vm.edu_school, "浙江大学")
        self.assertIn("硕士", vm.edu_degree)
        self.assertEqual(vm.edu_time, "2023.09 - 2026.06")

        # Verify education grid rows
        self.assertTrue(len(vm.education_grid_rows) >= 1)
        for row in vm.education_grid_rows:
            for cell in row:
                self.assertNotIn("｜", cell)
                self.assertNotIn("|", cell)

        # Verify experiences
        self.assertEqual(len(vm.experiences), 1)
        exp0 = vm.experiences[0]
        self.assertEqual(exp0["org"], "阿里巴巴")
        self.assertEqual(exp0["dept"], "云原生团队")
        self.assertEqual(exp0["role"], "研发专家")
        self.assertIn("云原生团队 · 研发专家", exp0["role_label"])
        self.assertIn("<strong>分布式缓存集群</strong>", exp0["bullets"][0])
        self.assertIn("<strong>45%</strong>", exp0["bullets"][0])

        # Verify projects
        self.assertEqual(len(vm.projects), 1)
        proj0 = vm.projects[0]
        self.assertEqual(proj0["name"], "开源社区")
        self.assertEqual(proj0["role"], "核心贡献者")
        self.assertIn("<strong>1.2k+ GitHub Stars</strong>", proj0["bullets"][0])

        # Verify competencies
        self.assertIn("核心语言", vm.competencies)
        self.assertEqual(vm.competencies["核心语言"], ["Go", "Python", "C++", "Rust"])
        self.assertIn("中间件", vm.competencies)
        self.assertEqual(vm.competencies["中间件"], ["Kafka", "Redis", "Etcd"])

        # Verify publications
        self.assertEqual(len(vm.publications), 1)
        self.assertEqual(vm.publications[0]["title"], "A Distributed Storage Engine")
        self.assertEqual(vm.publications[0]["venue"], "VLDB 2025")

        # Default photo reservation
        self.assertTrue(vm.reserve_photo)
        self.assertIsNone(vm.photo_data_uri)

    def test_from_profile_security_and_escaping(self):
        """Test ResumeViewModel.from_profile performs comprehensive HTML escaping and neutralizes XSS."""
        vm = ResumeViewModel.from_profile(self.malicious_profile)

        # Basic identity escaped
        self.assertNotIn("<script>", vm.name)
        self.assertIn("&lt;script&gt;alert(&#x27;pwn_name&#x27;)&lt;/script&gt;", vm.name)
        self.assertNotIn("<script>", vm.location)
        self.assertIn("&lt;script&gt;", vm.location)
        self.assertNotIn("<iframe", vm.title)
        self.assertIn("&lt;iframe", vm.title)

        # Education escaped
        self.assertNotIn("<script>", vm.edu_school)
        self.assertIn("&lt;script&gt;", vm.edu_school)
        for row in vm.education_grid_rows:
            for cell in row:
                self.assertNotIn("<img", cell)
                self.assertNotIn("<script>", cell)

        # Experiences escaped and markdown bold safe
        exp0 = vm.experiences[0]
        self.assertNotIn("<script>", exp0["org"])
        self.assertNotIn("<img", exp0["role"])
        self.assertNotIn("<script>", exp0["bullets"][0])
        self.assertNotIn("<iframe", exp0["bullets"][1])
        self.assertIn("<strong>0-day</strong>", exp0["bullets"][0])
        self.assertIn("&lt;script&gt;alert(&#x27;exploit&#x27;)&lt;/script&gt;", exp0["bullets"][0])
        self.assertIn("&lt;iframe src=&#x27;http://evil.com&#x27;&gt;", exp0["bullets"][1])

        # Projects escaped
        proj0 = vm.projects[0]
        self.assertNotIn("<script>", proj0["name"])
        self.assertNotIn("<script>", proj0["bullets"][0])
        self.assertIn("<strong>DefCon</strong>", proj0["bullets"][0])

    def test_html_theme_renderer_three_themes(self):
        """Test HtmlThemeRenderer successfully renders modern-navy, silicon-clean, and classic-tech."""
        renderer = HtmlThemeRenderer()
        vm = ResumeViewModel.from_profile(self.sample_profile)

        for theme in ["modern-navy", "silicon-clean", "classic-tech"]:
            html_content = renderer.render(vm, theme_name=theme)
            self.assertIsInstance(html_content, str)
            self.assertIn("张三", html_content)
            self.assertIn("高级后端架构师", html_content)
            self.assertIn("浙江大学", html_content)
            self.assertIn("阿里巴巴", html_content)
            self.assertIn("开源社区", html_content)
            self.assertIn("核心语言", html_content)
            self.assertIn("分布式缓存集群", html_content)

            # Ensure all template placeholders were resolved
            self.assertNotIn("{{NAME}}", html_content)
            self.assertNotIn("{{SECTIONS_CONTENT}}", html_content)
            self.assertNotIn("{{PHONE}}", html_content)
            self.assertNotIn("{{EMAIL}}", html_content)

            # Security gate verification
            risks = validate_output_security(html_content, format_type="html")
            self.assertEqual(risks, [], f"Security gate found risks in theme {theme}: {risks}")

    def test_html_theme_renderer_security_on_malicious_vm(self):
        """Test HtmlThemeRenderer with malicious ViewModel yields zero security violations."""
        renderer = HtmlThemeRenderer()
        vm = ResumeViewModel.from_profile(self.malicious_profile)

        for theme in ["modern-navy", "silicon-clean", "classic-tech"]:
            html_content = renderer.render(vm, theme_name=theme)
            self.assertNotIn("<script>", html_content)
            self.assertNotIn("<script>alert", html_content)
            self.assertNotIn("<iframe", html_content)
            self.assertNotIn("<img src=x", html_content)
            self.assertIn("&lt;img src=x onerror=alert(&#x27;role&#x27;)&gt;", html_content)

            risks = validate_output_security(html_content, format_type="html")
            self.assertEqual(risks, [], f"Risks detected in {theme}: {risks}")

    def test_ats_plain_renderer(self):
        """Test AtsPlainRenderer generates both structured Markdown and clean single-column HTML."""
        renderer = AtsPlainRenderer()
        vm = ResumeViewModel.from_profile(self.sample_profile)

        # 1. Markdown
        md_text = renderer.render_markdown(vm)
        self.assertIn("# 张三", md_text)
        self.assertIn("求职意向：高级后端架构师", md_text)
        self.assertIn("电话：+86 138-0000-0000 | 邮箱：zhangsan@example.com | 杭州", md_text)
        self.assertIn("## 教育背景", md_text)
        self.assertIn("### 浙江大学", md_text)
        self.assertIn("## 实习经历", md_text)
        self.assertIn("### 阿里巴巴 ｜ 云原生团队 ｜ 研发专家", md_text)
        self.assertIn("## 校园与实践经历", md_text)
        self.assertIn("### 开源社区 ｜ 核心贡献者", md_text)
        self.assertIn("## 专业技能", md_text)
        self.assertIn("- **核心语言：**Go, Python, C++, Rust", md_text)
        self.assertIn("预留证件照位置", md_text)

        # 2. HTML
        html_text = renderer.render_html(vm)
        self.assertIn("<h1>张三</h1>", html_text)
        self.assertIn("求职意向：高级后端架构师", html_text)
        self.assertIn("<h2>教育背景</h2>", html_text)
        self.assertIn("浙江大学", html_text)
        self.assertIn("<h2>实习经历</h2>", html_text)
        self.assertIn("阿里巴巴", html_text)
        self.assertIn("云原生团队 · 研发专家", html_text)
        self.assertIn("<h2>校园与实践经历</h2>", html_text)
        self.assertIn("开源社区", html_text)
        self.assertIn("<h2>专业技能</h2>", html_text)
        self.assertIn("edu-grid", html_text)
        self.assertIn("预留证件照", html_text)

        # Security check on ATS HTML
        risks = validate_output_security(html_text, format_type="html")
        self.assertEqual(risks, [])

        # 3. Convenience render dict
        bundle = renderer.render(vm)
        self.assertEqual(bundle["md"], md_text)
        self.assertEqual(bundle["html"], html_text)

    def test_photo_reservation_and_placeholder_logic(self):
        """Test photo slot variations: dashed placeholder, embedded base64, and disabled."""
        renderer_html = HtmlThemeRenderer()
        renderer_ats = AtsPlainRenderer()

        # Scenario 1: Default reserve_photo=True, no photo path
        vm_default = ResumeViewModel.from_profile(self.sample_profile, reserve_photo=True)
        self.assertTrue(vm_default.reserve_photo)
        self.assertIsNone(vm_default.photo_data_uri)

        html_1 = renderer_html.render(vm_default, "modern-navy")
        self.assertIn("photo-placeholder", html_1)
        self.assertIn("预留证件照", html_1)
        self.assertNotIn("src=\"data:image/", html_1)

        ats_html_1 = renderer_ats.render_html(vm_default)
        self.assertIn("预留证件照", ats_html_1)
        self.assertNotIn("<img", ats_html_1)

        ats_md_1 = renderer_ats.render_markdown(vm_default)
        self.assertIn("照片：预留证件照位置", ats_md_1)

        # Scenario 2: Valid local photo provided
        vm_photo = ResumeViewModel.from_profile(self.sample_profile, photo_path=self.sample_photo_path)
        self.assertTrue(vm_photo.reserve_photo)
        self.assertIsNotNone(vm_photo.photo_data_uri)
        self.assertTrue(vm_photo.photo_data_uri.startswith("data:image/png;base64,"))

        html_2 = renderer_html.render(vm_photo, "modern-navy")
        self.assertIn("photo-placeholder", html_2)
        self.assertIn("<img src=\"data:image/png;base64,", html_2)
        self.assertIn("onerror=", html_2)
        self.assertIn("预留证件照", html_2)  # Fallback div present

        ats_html_2 = renderer_ats.render_html(vm_photo)
        self.assertIn("<img src=\"data:image/png;base64,", ats_html_2)
        self.assertIn("onerror=", ats_html_2)

        ats_md_2 = renderer_ats.render_markdown(vm_photo)
        self.assertIn(str(self.sample_photo_path), ats_md_2)

        # Scenario 3: reserve_photo=False explicitly
        vm_no_photo = ResumeViewModel.from_profile(self.sample_profile, reserve_photo=False)
        self.assertFalse(vm_no_photo.reserve_photo)
        self.assertIsNone(vm_no_photo.photo_data_uri)

        html_3 = renderer_html.render(vm_no_photo, "modern-navy")
        self.assertNotIn("photo-placeholder", html_3)
        self.assertNotIn("预留证件照", html_3)

        ats_html_3 = renderer_ats.render_html(vm_no_photo)
        self.assertNotIn("预留证件照", ats_html_3)

        ats_md_3 = renderer_ats.render_markdown(vm_no_photo)
        self.assertNotIn("照片：", ats_md_3)

    def test_autofit_compatibility(self):
        """Verify that HTML generated by HtmlThemeRenderer integrates seamlessly with AutoFitEngine."""
        vm = ResumeViewModel.from_profile(self.sample_profile)
        renderer = HtmlThemeRenderer()
        html_src = renderer.render(vm, "silicon-clean")

        input_html = self.test_dir / "test_autofit_input.html"
        input_html.write_text(html_src, encoding="utf-8")

        output_html = self.test_dir / "test_autofit_output.html"
        output_pdf = self.test_dir / "test_autofit_output.pdf"

        browser_renderer = BrowserRenderer()
        autofit_engine = AutoFitEngine(browser_renderer)

        success, msg, details = autofit_engine.fit_to_single_page(
            input_html_path=input_html,
            output_html_path=output_html,
            output_pdf_path=output_pdf,
        )

        self.assertTrue(success, f"AutoFit failed: {msg}")
        self.assertTrue(output_html.exists())
        self.assertTrue(output_pdf.exists())
        fitted_content = output_html.read_text(encoding="utf-8")
        self.assertIn("张三", fitted_content)
        self.assertIn("高级后端架构师", fitted_content)

    def test_from_normalized_profile_and_section_projections(self):
        """Test from_normalized_profile factory and section_projections property."""
        from core.profile_adapter import normalize_candidate_profile

        norm = normalize_candidate_profile(self.sample_profile)
        vm = ResumeViewModel.from_normalized_profile(norm)
        self.assertEqual(vm.name, "张三")
        self.assertEqual(vm.title, "高级后端架构师")

        proj = vm.section_projections
        self.assertIn("identity", proj)
        self.assertIn("education", proj)
        self.assertIn("experiences", proj)
        self.assertIn("projects", proj)
        self.assertIn("competencies", proj)
        self.assertIn("has_photo", proj)
        self.assertEqual(proj["identity"]["name"], "张三")
        self.assertGreater(len(proj["experiences"]), 0)


class TestPostgraduateExamWidget(unittest.TestCase):
    """Tests for Postgraduate Entrance Exam Widget in ResumeViewModel and Renderers."""

    def setUp(self):
        self.profile = {
            "candidate": {
                "name": "张研",
                "title": "计算机科学与技术硕士",
                "phone": "13800000000",
                "email": "zhangyan@example.com",
                "school": "北京航空航天大学",
                "degree": "工学学士",
            },
            "experience": [{"org": "清华大学软件学院", "role": "科研助理", "bullets": ["参与分布式流处理系统设计。"]}],
            "competencies": {"编程语言": ["C++", "Python", "Go"]},
            "postgraduate_exam": {
                "target_school": "清华大学",
                "target_major": "计算机科学与技术",
                "direction": "智能系统",
                "politics": 78,
                "foreign_language": 82,
                "math_or_business_one": 125,
                "major_subject": 130,
                "total_score": 415,
            },
        }

    def test_postgraduate_exam_view_model_and_renderers(self):
        vm = ResumeViewModel.from_profile(self.profile)
        self.assertIsNotNone(vm.postgraduate_exam)
        self.assertEqual(vm.postgraduate_exam["total_score"], "415")
        self.assertEqual(vm.postgraduate_exam["target_school"], "清华大学")

        # HTML Theme Renderer
        html_rend = HtmlThemeRenderer()
        html = html_rend.render(vm, "modern-navy")
        self.assertIn("415", html)
        self.assertIn("清华大学", html)

        # ATS Plain Renderer
        ats_rend = AtsPlainRenderer()
        md = ats_rend.render_markdown(vm)
        self.assertIn("415", md)
        self.assertIn("清华大学", md)

        # Academic Exporter
        from core.academic_exporter import AcademicExporter
        exporter = AcademicExporter()
        latex = exporter.generate_latex(vm)
        self.assertIn("415", latex)
        typst = exporter.generate_typst(vm)
        self.assertIn("415", typst)


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
        tex_photo = self.exporter.generate_latex(self.sample_profile, reserve_photo=True)
        self.assertIn(r"\fbox", tex_photo)
        self.assertIn("预留证件照", tex_photo)

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

