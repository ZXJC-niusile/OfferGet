"""
End-to-End (E2E) Integration Test Suite for OfferGet Core Skill Toolchain:
1. Profile Ingestion -> ATS Audit -> Anonymization -> Fact Guard -> Diff Ledger
2. Resume Rendering, Micro-typography Layout Solver, Safe I/O, and PDF Rendering
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.academic_exporter import AcademicExporter
from core.anonymizer import anonymize_profile, deanonymize_text
from core.atomic_writer import safe_save_file
from core.ats_checker import audit_resume_ats
from core.browser_renderer import BrowserRenderer
from core.cli_helpers import load_json, read_text
from core.diff_ledger import DiffCategory, DiffLedger, DiffSeverity
from core.fact_guard import FactVerificationGuard
from core.layout_solver import LayoutConfig, solve_layout
from core.resume_parser import parse_resume_to_profile


TEMP_DIRECTORY_OPTIONS = {"ignore_cleanup_errors": True} if sys.version_info >= (3, 10) else {}


class TestE2ECoreSkillPipeline(unittest.TestCase):
    """E2E Test 1: Profile parsing, ATS keyword check, anonymization, and fact verification."""

    def setUp(self):
        self.jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"

    def test_e2e_ingest_audit_and_guard(self):
        jd_text = read_text(str(self.jd_path))
        profile_data = load_json(str(self.profile_path))

        ats_result = audit_resume_ats(profile_data, jd_text)
        self.assertIn("overall_score", ats_result)
        self.assertIn("verdict", ats_result)
        self.assertIn("skill_ledger", ats_result)

        anon_profile, deanon_map = anonymize_profile(profile_data, level="strict")
        self.assertEqual(deanonymize_text(anon_profile, deanon_map), profile_data)

        parsed = parse_resume_to_profile(PROJECT_ROOT / "examples" / "sample_resume.md")
        self.assertIn("candidate", parsed)

        guard = FactVerificationGuard({
            "skills": ["Python", "PyTorch", "Redis"],
            "projects": [{"name": "高并发秒杀系统", "bullets": ["使用 Redis 缓存抗住 5万 QPS"]}],
        })
        self.assertTrue(guard.verify_bullet("我在项目中用 Redis 缓存承担高频查询")["passed"])
        fail = guard.verify_bullet("我用 Kafka 实现了万级消息队列削峰")
        self.assertFalse(fail["passed"])
        self.assertEqual(fail["verdict"], "FACT_DRIFT_DETECTED")


class TestE2EResumeRenderingAndAutofitPipeline(unittest.TestCase):
    """E2E Test 2: Full resume layout, micro-typography, HTML/PDF rendering, safe I/O, and Diff Ledger."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(**TEMP_DIRECTORY_OPTIONS)
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @pytest.mark.browser
    def test_e2e_resume_render_and_autofit(self):
        profile = {
            "candidate": {
                "name": "张明",
                "phone": "+86 138-0000-0000",
                "email": "candidate@example.com",
                "location": "杭州",
                "school": "华东理工大学",
                "degree": "工程管理 本科在读",
                "edu_time": "2023.09—2027.06",
                "education_badges": ["GPA 3.12", "前15%"],
                "courses": "概率论与数理统计、工程经济学、工程项目管理",
            },
            "experience": [
                {
                    "org": "交个朋友（杭州）",
                    "role": "直播运营",
                    "time": "2026.06—至今",
                    "bullets": [
                        "使用 Excel、飞书 建立场次数据台账，结合 巨量百应 跟踪 GMV、ROI、点击率及转化率，复盘流量下降节点与成交表现。",
                        "参与 150+ 场美妆直播，独立负责其中 90+ 场的选品筹备、货盘核对与现场执行。",
                    ],
                }
            ],
            "projects": [
                {
                    "name": "高校新媒体中心",
                    "role": "编辑部成员",
                    "time": "2023.09—2025.09",
                    "bullets": ["负责校官方公众号内容采编排版，累计输出 15+ 篇推文，建立标准化流程。"],
                }
            ],
        }

        exporter = AcademicExporter()
        html_content = exporter.generate_academic_html_preview(profile, lang="zh")
        self.assertIn("张明", html_content)
        self.assertIn("交个朋友", html_content)

        config = LayoutConfig(min_body_font_pt=9.5, target_body_font_pt=10.0)
        solve_res = solve_layout(html_content, overflow_px=-120, config=config)
        self.assertTrue(solve_res.solved)
        self.assertGreaterEqual(solve_res.body_font_pt, 9.5)
        self.assertTrue(solve_res.is_expanded_to_fill)
        self.assertIn("<style id=\"offerget-micro-typography\">", solve_res.html)

        target_html = self.work_dir / "resume_output.html"
        save_res = safe_save_file(target_html, solve_res.html, allow_shadow=True)
        self.assertTrue(save_res.success)
        self.assertTrue(target_html.exists())

        diag = BrowserRenderer.diagnose_browser()
        if diag["found"]:
            renderer = BrowserRenderer(browser_path=diag["browser_path"])
            target_pdf = self.work_dir / "resume_output.pdf"
            success, pages, msg = renderer.render_pdf(target_html, target_pdf)
            self.assertTrue(success, f"PDF rendering failed: {msg}")
            self.assertTrue(target_pdf.exists())
            self.assertGreater(target_pdf.stat().st_size, 1000)
            self.assertEqual(pages, 1, f"Expected 1 page, got {pages}")

        ledger = DiffLedger(candidate_name="张明", metadata={"target_role": "产品经理实习生"})
        ledger.add_entry(
            category=DiffCategory.ROLE_HIERARCHY,
            field="experience[0].role",
            baseline_zh="直播运营",
            tailored_en="Live Stream Operations Intern",
            severity=DiffSeverity.ALIGNED,
            explanation="Preserved authentic operational title without unverified inflation to Product Manager",
            action_taken="Maintained exact factual role boundary",
        )
        ledger.add_entry(
            category=DiffCategory.METRIC_SCOPE,
            field="experience[0].bullets[0]",
            baseline_zh="单场最高 GMV 超 80 万元",
            tailored_en="Peak single-session GMV exceeded RMB 800,000",
            severity=DiffSeverity.INFLATION_PREVENTED,
            explanation="Kept RMB denomination without arbitrary USD conversion",
            action_taken="Protected factual metric denomination",
        )

        saved_files = ledger.save(self.work_dir, base_name="test_ledger")
        self.assertTrue(saved_files["markdown"].exists())
        self.assertTrue(saved_files["json"].exists())
        md_text = saved_files["markdown"].read_text(encoding="utf-8")
        self.assertIn("张明", md_text)
        self.assertIn("Role Hierarchy", md_text)


if __name__ == "__main__":
    unittest.main()
