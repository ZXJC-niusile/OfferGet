"""
Tests for OfferGet 6 Core Architecture Optimizations:
1. Unified Profile Context SSOT & Boundary Projection Adapters
2. Unified Defense Engine & Backwards-Compatible Facade
3. Canonical JD Processing Gateway (to_canonical)
4. Unified Resume Rendering Pipeline (ProfileContext -> ResumeViewModel -> Renderers)
5. Persistent Application Tracking Store (SQLite, Timeline, Collisions, Multi-Offer Comparison)
6. Factual Boundary Protection for Baoyan Package & Advisor Outreach
"""

import os
import tempfile
import unittest
from pathlib import Path

# Step 1 imports
from core.profile_adapter import ProfileContext, build_profile_context
from core.advisor_matcher import AdvisorMatcher, CandidateProfile as AdvisorCandidateProfile
from core.jd_analyst.models import CandidateProfile as AnalystCandidateProfile
from core.resume_view_model import ResumeViewModel

# Step 2 imports
from core.defense import (
    DefenseSimulator as UnifiedDefenseSimulator,
    EvidenceStatus,
    RiskBasis,
)
import core.defense as defense_pkg

# Step 3 imports
from core.jd_compat import DecodedJD, to_canonical, DecodedJDCompat

# Step 4 imports
from core.academic_exporter import AcademicExporter
from core.resume_builder import ResumeBuilder

# Step 5 imports
from core.application_tracker import (
    ApplicationTracker,
    ApplicationStore,
    ApplicationRecord,
    AppStatus,
)

# Step 6 imports
from core.baoyan_pipeline import PersonalStatementBuilder


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
                    "venue": "ACL 2025",
                    "is_first_author": False,
                    "author_rank": 3,
                }
            ],
            "awards": ["国家励志奖学金"],
        }

    # ------------------------------------------------------------------------
    # Optimization 1: Unified Profile Model
    # ------------------------------------------------------------------------
    def test_1_unified_profile_model(self):
        ctx = build_profile_context(self.sample_profile_dict)
        self.assertIsInstance(ctx, ProfileContext)

        # 1. Projection to jd_analyst CandidateProfile
        analyst_cand = ctx.to_analyst_candidate()
        self.assertIsInstance(analyst_cand, AnalystCandidateProfile)
        self.assertEqual(analyst_cand.name, "张三")
        self.assertIn("Python", analyst_cand.skills)

        # 2. Projection to advisor_matcher CandidateProfile
        advisor_cand = ctx.to_advisor_candidate()
        self.assertIsInstance(advisor_cand, AdvisorCandidateProfile)
        self.assertEqual(advisor_cand.name, "张三")
        self.assertEqual(advisor_cand.undergraduate_school, "浙江大学")

        # 3. Projection to ResumeViewModel
        vm = ctx.to_view_model()
        self.assertIsInstance(vm, ResumeViewModel)
        self.assertEqual(vm.name, "张三")

        # 4. AdvisorMatcher natively handles ProfileContext
        matcher = AdvisorMatcher()
        ensured = matcher._ensure_candidate_profile(ctx)
        self.assertIsInstance(ensured, AdvisorCandidateProfile)
        self.assertEqual(ensured.name, "张三")

    # ------------------------------------------------------------------------
    # Optimization 2: Consolidated Defense Simulator Engine
    # ------------------------------------------------------------------------
    def test_2_consolidated_defense_engine(self):
        # 1. New engine directly imported
        sim_new = UnifiedDefenseSimulator()
        self.assertIsNotNone(sim_new)

        # 2. Package facade points to the unified engine
        self.assertIs(defense_pkg.EvidenceStatus, EvidenceStatus)
        self.assertIs(defense_pkg.RiskBasis, RiskBasis)
        self.assertIs(defense_pkg.DefenseSimulator, UnifiedDefenseSimulator)

        # 3. Run defense simulation via package
        profile = {
            "projects": [
                {"name": "分布式架构", "bullets": ["设计高并发架构，QPS 提升 10 倍"]}
            ]
        }
        sim = defense_pkg.DefenseSimulator()
        res = sim.simulate(profile)
        self.assertIsNotNone(res)
        self.assertEqual(res.project_name, "分布式架构")
        self.assertIn("total_claims", res.summary_stats)

    # ------------------------------------------------------------------------
    # Optimization 3: Converged JD Pipeline Gateway (to_canonical)
    # ------------------------------------------------------------------------
    def test_3_converged_jd_pipeline(self):
        raw_text = """
        职位名称：大模型算法工程师
        岗位职责：负责 LLM 推理加速与模型量化部署。
        任职要求：
        1. 熟练掌握 PyTorch 与 CUDA；
        2. 具备 3 年以上分布式训练经验。
        """
        # From raw text
        cjd1 = to_canonical(raw_text)
        self.assertIsInstance(cjd1, DecodedJD)
        cjd1_skills = [s.name.lower() for s in cjd1.core_skills]
        self.assertTrue(any("pytorch" in s for s in cjd1_skills))

        # From dict
        raw_dict = {
            "title": "后端开发工程师",
            "required_skills": ["Go", "MySQL"],
            "responsibilities": ["负责支付核心链路开发"],
        }
        cjd2 = to_canonical(raw_dict)
        self.assertIsInstance(cjd2, DecodedJD)
        self.assertEqual(cjd2.job_title, "后端开发工程师")
        cjd2_skills = [s.name.lower() for s in cjd2.core_skills]
        self.assertTrue(any("go" in s for s in cjd2_skills))

        # From legacy DecodedJDCompat
        from core.jd_compat import canonical_to_legacy
        legacy_obj = canonical_to_legacy(cjd2)
        self.assertIsInstance(legacy_obj, DecodedJDCompat)
        cjd3 = to_canonical(legacy_obj)
        self.assertIsInstance(cjd3, DecodedJD)
        self.assertEqual(cjd3.job_title, "后端开发工程师")

        # Idempotent on canonical
        cjd4 = to_canonical(cjd3)
        self.assertIs(cjd4, cjd3)

    # ------------------------------------------------------------------------
    # Optimization 4: Unified Resume Rendering Pipeline
    # ------------------------------------------------------------------------
    def test_4_unified_resume_rendering(self):
        ctx = build_profile_context(self.sample_profile_dict)
        vm = ctx.to_view_model()

        # 1. AcademicExporter directly consumes ResumeViewModel
        exporter = AcademicExporter()
        latex = exporter.generate_latex(vm)
        self.assertIn("张三", latex)
        self.assertIn("浙江大学", latex)
        self.assertIn("未来科技", latex)

        typst = exporter.generate_typst(vm)
        self.assertIn("张三", typst)
        self.assertIn("浙江大学", typst)
        self.assertIn("未来科技", typst)

        # 2. HTML preview directly consumes ResumeViewModel
        html = exporter.generate_latex_html_preview(vm)
        self.assertIn("张三", html)
        self.assertIn("未来科技", html)

        # 3. ResumeBuilder integrates cleanly with ProfileContext
        builder = ResumeBuilder(ctx)
        self.assertIsNotNone(builder)
        self.assertEqual(builder.view_model.name, "张三")

    # ------------------------------------------------------------------------
    # Optimization 5: Persistent Application Tracker Store & Offer Compare
    # ------------------------------------------------------------------------
    def test_5_application_store_and_offer_compare(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_applications.db"
            store = ApplicationStore(db_path=db_path)
            try:
                record = ApplicationRecord(
                    id="APP-001",
                    target_name="未来科技",
                    role_or_track="算法工程师",
                    channel="boss直聘",
                    status=AppStatus.APPLIED,
                    evidence_snapshot={"profile_version": "v1.0", "skills": ["PyTorch"]},
                )
                store.save(record)

                # Retrieve and verify persistence
                loaded = store.get("APP-001")
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.target_name, "未来科技")
                self.assertEqual(len(loaded.status_history), 1)

                # Update status via transition_status and verify timeline
                loaded.transition_status(AppStatus.INTERVIEW, note="通过一面")
                store.save(loaded)
                updated = store.get("APP-001")
                self.assertEqual(updated.status, AppStatus.INTERVIEW)
                self.assertEqual(len(updated.status_history), 2)
                self.assertEqual(updated.status_history[-1]["note"], "通过一面")

                # Multi-channel collision check
                tracker = ApplicationTracker(store=store)
                duplicate_rec = ApplicationRecord(
                    id="APP-002",
                    target_name="未来科技",
                    role_or_track="算法工程师",
                    channel="猎聘",
                    status=AppStatus.APPLIED,
                )
                tracker.add_record(duplicate_rec, check_collision=True)
                self.assertIsNotNone(duplicate_rec.collision_risk)

                # Multi-offer comparison
                offer_rec_a = ApplicationRecord(
                    id="APP-OFFER-1",
                    target_name="未来科技",
                    role_or_track="大模型算法",
                    status=AppStatus.OFFER,
                    offer_details={
                        "base_monthly": 25000,
                        "months": 16,
                        "annual_stock": 50000,
                        "annual_bonus": 30000,
                        "weekly_hours": 45,
                    },
                )
                offer_rec_b = ApplicationRecord(
                    id="APP-OFFER-2",
                    target_name="另一巨头",
                    role_or_track="后端架构",
                    status=AppStatus.OFFER,
                    offer_details={
                        "base_monthly": 32000,
                        "months": 15,
                        "annual_stock": 0,
                        "annual_bonus": 0,
                        "weekly_hours": 55,
                    },
                )
                tracker.add_record(offer_rec_a, check_collision=False)
                tracker.add_record(offer_rec_b, check_collision=False)

                comparison = tracker.compare_offers()
                self.assertEqual(comparison["total_offers"], 2)
                self.assertIsNotNone(comparison["best_hourly_offer"])
                self.assertIsNotNone(comparison["best_total_offer"])
                self.assertIn("折算等效时薪最高", comparison["summary"])

                incomplete = ApplicationRecord(
                    id="APP-OFFER-INCOMPLETE",
                    target_name="待补充公司",
                    role_or_track="算法工程师",
                    status=AppStatus.OFFER,
                    offer_details={"weekly_hours": 45},
                )
                tracker.add_record(incomplete, check_collision=False)
                incomplete_result = tracker.compare_offers()
                self.assertEqual(incomplete_result["total_offers"], 3)
                self.assertEqual(incomplete_result["incomplete"][0]["record_id"], "APP-OFFER-INCOMPLETE")
                self.assertNotIn("待补充公司", [item["company"] for item in incomplete_result["comparison"]])
            finally:
                store.close()

    # ------------------------------------------------------------------------
    # Optimization 6: Strict Fact Boundaries for Baoyan & Advisor Matcher
    # ------------------------------------------------------------------------
    def test_6_factual_boundaries_baoyan_and_advisor(self):
        # 1. Baoyan Statement: no unverified scholarships or claims
        statement_builder = PersonalStatementBuilder()
        draft = statement_builder.build_statement(
            profile_data=self.sample_profile_dict,
            target_school="上海交通大学",
            target_major="计算机科学与技术",
        )
        # Should not claim "多次获得校级一等奖学金"
        for ach in draft.academic_achievements:
            self.assertNotIn("多次获得校级一等奖学金", ach)
        self.assertTrue(any("国家励志奖学金" in a for a in draft.academic_achievements))

        # 2. Advisor outreach email: non-first author & non-lead project phrasing
        matcher = AdvisorMatcher()
        advisor_data = {
            "name": "王教授",
            "title": "博导",
            "institution": "上海交通大学",
            "department": "计算机系",
            "recent_publications": [
                {
                    "title": "A High-Performance Distributed Computing Framework",
                    "year": 2024,
                    "venue": "OSDI 2024",
                }
            ],
        }
        email_data = matcher.generate_outreach_email(
            advisor=advisor_data,
            candidate=self.sample_profile_dict,
        )

        hook = email_data["profile_hook"]
        # Candidate is author rank 3, not first author: must not say "曾以第一作者"
        self.assertNotIn("曾以第一作者", hook)
        self.assertIn("曾参与", hook)

        # Candidate project role is "算法复现成员", not lead: must not say "曾主导完成"
        cand_no_pub = dict(self.sample_profile_dict)
        cand_no_pub["publications"] = []
        email_no_pub = matcher.generate_outreach_email(
            advisor=advisor_data,
            candidate=cand_no_pub,
        )
        hook_no_pub = email_no_pub["profile_hook"]
        self.assertNotIn("曾主导完成", hook_no_pub)
        self.assertIn("曾参与完成【分布式推理框架】", hook_no_pub)

        # 3. When GPA and Rank are missing: must not claim "专业成绩名列前茅"
        cand_no_creds = dict(self.sample_profile_dict)
        cand_no_creds["education"] = {"school": "浙江大学", "major": "计算机"}
        cand_no_creds["awards"] = []
        email_no_creds = matcher.generate_outreach_email(
            advisor=advisor_data,
            candidate=cand_no_creds,
        )
        hook_no_creds = email_no_creds["profile_hook"]
        self.assertNotIn("专业成绩名列前茅", hook_no_creds)
        self.assertIn("系统修读了专业核心课程", hook_no_creds)


if __name__ == "__main__":
    unittest.main()
