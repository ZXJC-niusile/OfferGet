"""
Negative and Edge-Case Tests for OfferGet Core Architecture Convergence:
1. ProfileContext: Non-hallucination of missing fields (grade, project name, honors).
2. JD Ingress: Robust handling of empty string, blank text, empty dict, and malformed inputs.
3. AcademicExporter: Absence of hallucinated defaults (roles, emails, phones, titles) in LaTeX, Typst, and HTML.
4. ApplicationStore & AppStatus: Schema migration tracking and canonical status coercion.
5. Unified Defense Engine Single Source of Truth via core.services.
"""

import tempfile
import unittest
from pathlib import Path

from core.academic_exporter import AcademicExporter
from core.advisor_matcher import CandidateProfile as AdvisorCandidateProfile
from core.application_tracker import (
    ApplicationRecord,
    ApplicationStore,
    AppStatus,
)
from core.defense import DefenseSimulator as UnifiedDefenseSimulator
from core.jd_compat import DecodedJD, to_canonical
from core.profile_adapter import ProfileContext, build_profile_context, normalize_candidate_profile
from core.resume_view_model import ResumeViewModel
import core.services as services


class TestArchitectureNegative(unittest.TestCase):

    def test_1_profile_no_hallucinated_defaults(self):
        """Verify that minimal profiles do not get populated with invented academic or career facts."""
        empty_profile = {}
        ctx = build_profile_context(empty_profile)
        self.assertIsInstance(ctx, ProfileContext)

        # 1. to_advisor_candidate must not hallucinate grade or degree
        advisor_cand = ctx.to_advisor_candidate()
        self.assertEqual(advisor_cand.grade, "")
        self.assertEqual(advisor_cand.target_degree, "")
        self.assertNotIn("2022级本科生", advisor_cand.grade)

        # 2. normalize_candidate_profile should not invent project name "校园经历"
        raw_proj = {"role": "志愿者", "bullets": ["负责接待"]}
        norm = normalize_candidate_profile({"projects": [raw_proj]})
        self.assertEqual(norm["projects"][0]["name"], "")
        self.assertNotEqual(norm["projects"][0]["name"], "校园经历")

        # 3. Aliases: awards, honors, honors_awards, publications, papers are normalized
        profile_with_honors = {
            "name": "李四",
            "honors": [{"name": "国家一等奖学金"}],
            "papers": [{"title": "Agent Research"}],
        }
        ctx2 = build_profile_context(profile_with_honors)
        adv2 = ctx2.to_advisor_candidate()
        self.assertEqual(adv2.honors_awards, ["国家一等奖学金"])
        self.assertEqual(len(adv2.publications), 1)
        self.assertEqual(adv2.publications[0]["title"], "Agent Research")

        norm2 = ctx2.to_dict()
        self.assertIn("国家一等奖学金", [h.get("name") if isinstance(h, dict) else h for h in norm2["honors_awards"]])
        self.assertEqual(len(norm2["publications"]), 1)

    def test_2_jd_to_canonical_negative_inputs(self):
        """Verify universal JD ingress handles empty and malformed inputs gracefully."""
        # 1. Empty string
        jd_empty = to_canonical("")
        self.assertIsInstance(jd_empty, DecodedJD)
        self.assertEqual(jd_empty.job_title, "未指定职位")
        self.assertEqual(jd_empty.raw_text, "")

        # 2. Blank whitespace string
        jd_blank = to_canonical("   \n\t  ")
        self.assertIsInstance(jd_blank, DecodedJD)
        self.assertEqual(jd_blank.job_title, "未指定职位")

        # 3. Empty dictionary
        jd_dict_empty = to_canonical({})
        self.assertIsInstance(jd_dict_empty, DecodedJD)
        self.assertEqual(jd_dict_empty.job_title, "未指定职位")
        self.assertEqual(jd_dict_empty.core_skills, [])

        # 4. Malformed dictionary (e.g. non-list skills, non-list requirements)
        malformed_dict = {
            "job_title": "测试工程师",
            "required_skills": "Python",  # string instead of list
            "requirements": None,
            "core_skills": "pytest",
            "responsibilities": None,
        }
        jd_malformed = to_canonical(malformed_dict)
        self.assertIsInstance(jd_malformed, DecodedJD)
        self.assertEqual(jd_malformed.job_title, "测试工程师")
        self.assertTrue(any(s.name == "Python" for s in jd_malformed.core_skills))

    def test_3_academic_exporter_no_hallucinations(self):
        """Verify that LaTeX, Typst, and HTML renderers do not inject placeholder strings."""
        exporter = AcademicExporter()
        minimal_profile = {
            "name": "王五",
            "projects": [
                {"name": "开源项目", "bullets": ["贡献代码"]}
            ]
        }
        vm = ResumeViewModel.from_profile(minimal_profile)

        # 1. LaTeX
        latex_out = exporter.generate_latex(vm)
        self.assertNotIn("算法架构师", latex_out)
        self.assertNotIn("candidate@example.com", latex_out)
        self.assertNotIn("+86 138-0000-0000", latex_out)
        self.assertNotIn("架构 Owner", latex_out)
        self.assertIn("王五", latex_out)
        self.assertIn("开源项目", latex_out)

        # 2. Typst
        typst_out = exporter.generate_typst(vm)
        self.assertNotIn("运营岗", typst_out)
        self.assertNotIn("candidate@example.com", typst_out)
        self.assertNotIn("+86 138-0000-0000", typst_out)
        self.assertNotIn("架构 Owner", typst_out)
        self.assertIn("王五", typst_out)

        # 3. HTML Preview
        html_out = exporter.generate_latex_html_preview(vm)
        self.assertNotIn("运营岗", html_out)
        self.assertNotIn("candidate@example.com", html_out)
        self.assertNotIn("+86 138-0000-0000", html_out)
        self.assertIn("王五", html_out)

        # 4. Compiler safety with non-existent CLI
        fake_tex = Path(tempfile.gettempdir()) / "non_existent_test.tex"
        fake_pdf = Path(tempfile.gettempdir()) / "non_existent_test.pdf"
        self.assertFalse(exporter.compile_latex(fake_tex, fake_pdf))
        self.assertFalse(exporter.compile_typst(fake_tex, fake_pdf))

    def test_4_application_store_migration_and_status(self):
        """Verify SQLite schema versioning, migration tracking, and AppStatus canonical coercion."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_mig.db"
            store = ApplicationStore(db_path)
            try:
                # Check user_version set to CURRENT_SCHEMA_VERSION (schema v2)
                with store._get_connection() as conn:
                    cur = conn.execute("PRAGMA user_version")
                    version = cur.fetchone()[0]
                    self.assertEqual(version, ApplicationStore.CURRENT_SCHEMA_VERSION)

                # Check save and retrieve
                rec = ApplicationRecord(
                    id="app-neg-01",
                    target_name="测试高校",
                    role_or_track="学术硕士",
                    status=AppStatus.INTERVIEW,
                )
                store.save(rec)
                loaded = store.get("app-neg-01")
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.status, AppStatus.INTERVIEW)
            finally:
                store.close()

        # Test AppStatus coercion
        self.assertEqual(AppStatus.from_string("面试中"), AppStatus.INTERVIEW)
        self.assertEqual(AppStatus.from_string("已获 Offer"), AppStatus.OFFER)
        self.assertEqual(AppStatus.from_string("笔试考核"), AppStatus.WRITTEN_TEST)
        self.assertEqual(AppStatus.from_string("已淘汰"), AppStatus.CLOSED)
        self.assertEqual(AppStatus.from_string("未知状态"), AppStatus.PENDING)

        # Test guard status mapping
        self.assertEqual(AppStatus.INTERVIEW.to_guard_status(), "interviewing")
        self.assertEqual(AppStatus.OFFER.to_guard_status(), "offered")
        self.assertEqual(AppStatus.CLOSED.to_guard_status(), "rejected")
        self.assertEqual(AppStatus.PENDING.to_guard_status(), "pending")

    def test_5_defense_simulator_single_source_of_truth(self):
        """Verify DefenseSimulator in core.services directly points to core.defense.simulator."""
        self.assertIs(services.DefenseSimulator, UnifiedDefenseSimulator)

    def test_6_future_application_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "future.db"
            store = ApplicationStore(db_path)
            store.close()
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA user_version = 999")
            conn.commit()
            conn.close()
            with self.assertRaises(RuntimeError):
                ApplicationStore(db_path)


if __name__ == "__main__":
    unittest.main()
