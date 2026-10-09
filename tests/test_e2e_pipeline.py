"""
End-to-End (E2E) Integration Test Suite for OfferGet.
Verifies complete user workflows from raw input files to final outputs:
1. E2E Industry Career Lifecycle (JD Decode -> Match -> ATS Audit -> Proposal -> App Track -> Offer Matrix)
2. E2E Resume Rendering & Layout Pipeline (Profile -> Layout Solver -> HTML -> PDF -> Atomic Safe Write -> Diff Ledger)
3. E2E Academic Baoyan Lifecycle (Academic Profile -> Integrity Audit -> 3-Tier Compression -> Advisor Match -> Package)
4. E2E Interview Debrief & Defense Pipeline (Claims -> Fact Guard -> Defense Simulator -> Multi-turn Debrief -> Session Persistence)
5. ATS Audit CLI Command Smoke Check
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Core imports
from core.paths import get_project_root
from core.cli_helpers import read_text, load_json
from services.jd_service import JDService
from services.match_service import MatchService
from services.report_service import ReportService
from services.review_service import CareerReviewService
from services.profile_service import ProfileService
from services.academic_service import AcademicService
from services.offer_service import OfferService
from core.fact_guard import FactVerificationGuard
from core.layout_solver import solve_layout, LayoutConfig, LayoutSolveResult
from core.diff_ledger import DiffLedger, DiffCategory, DiffSeverity
from core.atomic_writer import safe_save_file
from core.academic_exporter import AcademicExporter
from core.material_proposal import create_material_proposal, apply_material_proposal, MaterialProposalStatus
from core.application_tracker import ApplicationStore, ApplicationRecord, AppStatus
from core.interview_debrief import (
    InterviewDebriefEngine,
    InterviewSessionDebrief,
    DebriefQuestionItem,
    QuestionDiagnosis,
)
from core.defense.simulator import DefenseSimulator
from core.baoyan_auditor import audit_baoyan_entry, compress_baoyan_entry
from core.baoyan_pipeline import validate_academic_profile, generate_camp_checklist, BaoyanPipeline
from core.advisor_matcher import AdvisorMatcher
from core.browser_renderer import BrowserRenderer


class TestE2EIndustryCareerPipeline(unittest.TestCase):
    """E2E Test 1: Full industry career workflow from JD decoding to multi-offer matrix."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.work_dir = Path(self.temp_dir.name)
        self.jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_e2e_industry_full_lifecycle(self):
        # 1. Decode raw JD
        jd_text = read_text(str(self.jd_path))
        jd_service = JDService()
        decoded_jd = jd_service.decode_jd(jd_text)
        self.assertIn("layers", decoded_jd)
        self.assertEqual(len(decoded_jd["layers"]), 5)
        self.assertTrue(len(decoded_jd.get("detected_signals", [])) >= 0)

        # 2. Match Candidate Profile against Decoded JD
        profile_data = load_json(str(self.profile_path))
        match_service = MatchService()
        match_result = match_service.match(decoded_jd, profile_data)
        self.assertIn("overall_match_score", match_result)
        self.assertGreater(match_result["overall_match_score"], 70)
        self.assertIn("must_have_matches", match_result)

        # 3. ATS Audit with 3-State Skill Ledger
        profile_service = ProfileService()
        ats_result = profile_service.audit_ats(profile_data, decoded_jd)
        self.assertIn("overall_score", ats_result)
        self.assertIn("verdict", ats_result)
        self.assertIn("skill_ledger", ats_result)
        self.assertGreater(len(ats_result["skill_ledger"]), 0)

        # 4. Review & Material Proposal Flow
        review_service = CareerReviewService()
        review_output = review_service.run_review(jd_text, profile_data)
        self.assertIn("interview_questions", review_output)

        # 5. Proposal Generation, Acceptance & Application Store Integration
        proposal = create_material_proposal(review_output, profile_data, jd_text, proposal_id="prop_e2e_001")
        self.assertEqual(proposal.status, MaterialProposalStatus.DRAFT)

        # Apply accepted proposal to profile
        tailored_profile = apply_material_proposal(proposal, profile_data, jd_text)
        self.assertEqual(proposal.status, MaterialProposalStatus.ACCEPTED)
        self.assertIsInstance(tailored_profile, dict)

        # Store in ApplicationStore
        app_rec = ApplicationRecord(
            id="app_deepmind_001",
            target_name="DeepMind Technologies",
            role_or_track="Senior AI Architect",
            status=AppStatus.APPLIED,
            channel="内推",
            notes="Applied through referral",
        )
        with ApplicationStore(db_path=self.work_dir / "applications.db") as app_store:
            app_store.save(app_rec)
            app_store.save_material_proposal(proposal)
            saved_prop = app_store.get_material_proposal(proposal.proposal_id)
            self.assertIsNotNone(saved_prop)
            self.assertEqual(saved_prop.status, MaterialProposalStatus.ACCEPTED)

            # 6. Application Tracker Lifecycle Transitions
            # Advance state: applied -> interview -> offer
            app_rec.transition_status(AppStatus.INTERVIEW, note="Invited to onsite interview")
            app_store.save(app_rec)
            app_rec.transition_status(AppStatus.OFFER, note="Received formal offer package")
            app_store.save(app_rec)
            final_app = app_store.get(app_rec.id)
            self.assertEqual(final_app.status, AppStatus.OFFER)
            self.assertEqual(len(final_app.status_history), 3)

        # 7. Multi-Offer Comparison & Contract Trap Evaluation
        offer_service = OfferService()
        offer_a = {
            "company": "DeepMind",
            "base_salary": 600000,
            "bonus": 100000,
            "bonus_haircut": 0.8,
            "housing_fund": 50000,
            "weekly_hours": 45,
            "commute_daily_mins": 30,
            "commute_rent_delta": 0,
            "probation_months": 3,
            "probation_pay_ratio": 1.0,
            "non_compete_scope": "none",
        }
        eval_result = offer_service.evaluate_offer(offer_a)
        self.assertIn("total_compensation", eval_result)
        self.assertGreater(eval_result["total_compensation"]["total_annual_package"], 0)
        self.assertIn("detected_traps", eval_result)


class TestE2EResumeRenderingAndAutofitPipeline(unittest.TestCase):
    """E2E Test 2: Full resume layout, micro-typography, HTML/PDF rendering, safe I/O, and Diff Ledger."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

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

        # 1. Generate HTML preview with AcademicExporter
        exporter = AcademicExporter()
        html_content = exporter.generate_latex_html_preview(profile, lang="zh")
        self.assertIn("张明", html_content)
        self.assertIn("交个朋友", html_content)

        # 2. Layout Solver Integration (Underflow expansion + Anti-orphan)
        config = LayoutConfig(min_body_font_pt=9.5, target_body_font_pt=10.0)
        solve_res = solve_layout(html_content, overflow_px=-120, config=config)  # Underflow by 120px
        self.assertTrue(solve_res.solved)
        self.assertGreaterEqual(solve_res.body_font_pt, 9.5)
        self.assertTrue(solve_res.is_expanded_to_fill)
        self.assertIn("<style id=\"offerget-micro-typography\">", solve_res.html)

        # 3. Atomic Safe File Write
        target_html = self.work_dir / "resume_output.html"
        save_res = safe_save_file(target_html, solve_res.html, allow_shadow=True)
        self.assertTrue(save_res.success)
        self.assertTrue(target_html.exists())

        # 4. Browser Rendering (if headless browser is present)
        diag = BrowserRenderer.diagnose_browser()
        if diag["found"]:
            renderer = BrowserRenderer(browser_path=diag["browser_path"])
            target_pdf = self.work_dir / "resume_output.pdf"
            success, pages, msg = renderer.render_pdf(target_html, target_pdf)
            self.assertTrue(success, f"PDF rendering failed: {msg}")
            self.assertTrue(target_pdf.exists())
            self.assertGreater(target_pdf.stat().st_size, 1000)
            self.assertEqual(pages, 1, f"Expected 1 page, got {pages}")

        # 5. Diff Ledger Traceability
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


class TestE2EAcademicBaoyanPipeline(unittest.TestCase):
    """E2E Test 3: Full academic baoyan track from integrity audit to cold outreach."""

    def test_e2e_academic_baoyan_lifecycle(self):
        academic_profile = {
            "candidate": {
                "name": "赵同学",
                "university": "浙江大学",
                "major": "计算机科学与技术",
                "email": "zhao@zju.edu.cn",
                "phone": "+86 13800000000",
            },
            "academic_standing": {
                "gpa": 3.88,
                "max_gpa": 4.0,
                "rank": "3/150",
                "rank_percent": "2.0%",
                "cet6": 620,
            },
            "honors": [
                {"name": "国家奖学金", "level": "national"},
                {"name": "美国大学生数学建模竞赛一等奖 (M奖)", "level": "international"},
            ],
            "publications": [
                {
                    "title": "Efficient Distributed LLM Serving via Speculative Decoding",
                    "venue": "ACL 2025",
                    "ccf_rank": "CCF-A",
                    "author_role": "first_author",
                    "status": "under_review",
                    "authors": ["赵同学", "李教授"],
                    "is_first_author": True,
                }
            ],
            "projects": [
                {
                    "name": "vLLM推理加速与显存池化管理",
                    "role": "核心骨干",
                    "individual_contribution": "负责vLLM推理加速核心算子优化与显存池化",
                    "experiment_type": "real_experiment",
                    "tags": ["real_experiment"],
                }
            ],
            "target_schools": [
                {"school_name": "清华大学", "track": "直博"}
            ],
            "statement": "自进入大学以来，我始终专注于系统级分布式优化与大模型推理加速..." * 20,
        }

        # 1. Baoyan Academic Profile Validation & Integrity Audit
        valid_res = validate_academic_profile(academic_profile)
        self.assertTrue(valid_res["valid"])
        self.assertIn("competitiveness_score", valid_res)
        self.assertGreater(valid_res["competitiveness_score"], 60)
        self.assertIn("metrics", valid_res)

        sample_entry = "在国家重点研发计划项目中作为技术骨干，负责 vLLM 推理加速与分布式显存池化管理。"
        entry_audit = audit_baoyan_entry(sample_entry)
        self.assertIn("word_count", entry_audit)
        self.assertIn("checks", entry_audit)

        # 2. Multi-tier Personal Statement Compression
        original_text = academic_profile["statement"]
        comp_res = compress_baoyan_entry(original_text, target_tier="精炼版")
        self.assertIn("compressed_text", comp_res)
        self.assertLessEqual(len(comp_res["compressed_text"]), len(original_text))

        # 3. Summer Camp Checklist Generation
        checklist = generate_camp_checklist(academic_profile, stage="夏令营", track="直博")
        self.assertIn("categories", checklist)
        self.assertGreater(len(checklist["categories"]), 0)

        # 4. Faculty Advisor Matcher & High-EQ Outreach Generation
        advisor_matcher = AdvisorMatcher()
        advisor = {
            "name": "陈院士",
            "institution": "清华大学",
            "department": "计算机系",
            "research_topics": ["分布式系统", "大模型系统架构", "异构计算"],
        }
        candidate_summary = {
            "name": "赵同学",
            "university": "浙江大学",
            "major": "计算机科学与技术",
            "gpa": "3.88/4.0",
            "research_interests": ["分布式系统", "大模型推理加速"],
        }
        match_output = advisor_matcher.match_candidate_to_advisor(advisor, candidate_summary)
        self.assertIn("intersection_score", match_output)
        self.assertIn("mutual_research_topics", match_output)

        outreach_email = advisor_matcher.generate_outreach_email(advisor, candidate_summary)
        self.assertIn("email_body", outreach_email)
        self.assertIn("陈老师", outreach_email["email_body"])
        self.assertIn("赵同学", outreach_email["email_body"])


class TestE2EInterviewDebriefAndDefensePipeline(unittest.TestCase):
    """E2E Test 4: Interview debrief, fact guard grilling, and multi-turn session persistence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_e2e_interview_debrief_and_defense(self):
        # 1. Fact Verification Guard
        baseline_profile = {
            "skills": ["Python", "PyTorch", "Redis"],
            "projects": [
                {"name": "高并发秒杀系统", "bullets": ["使用 Redis 缓存抗住 5万 QPS"]}
            ],
        }
        guard = FactVerificationGuard(baseline_profile)

        # Verifying truthful claim
        truthful_claim = "我在项目中用 Redis 缓存承担高频查询"
        check_ok = guard.verify_bullet(truthful_claim)
        self.assertTrue(check_ok["passed"])

        # Catching invented technology
        hallucinated_claim = "我用 Kafka 实现了万级消息队列削峰"
        check_fail = guard.verify_bullet(hallucinated_claim)
        self.assertFalse(check_fail["passed"])
        self.assertEqual(check_fail["verdict"], "FACT_DRIFT_DETECTED")

        # 2. Defense Simulator Grilling Question Generation
        simulator = DefenseSimulator()
        sim_res = simulator.simulate(baseline_profile["projects"][0])
        self.assertGreater(len(sim_res.intensity_questions), 0)
        self.assertGreater(len(sim_res.follow_up_chains), 0)

        # 3. Interview Debrief Analysis
        engine = InterviewDebriefEngine()
        q1 = "请问你在高并发秒杀项目中是如何解决缓存雪崩与穿透的？"
        a1 = "我们在高并发项目中基于 Redis 集群做了冷热数据分离，单机压测达 50,000 QPS，依靠指标监控看板验证。"
        item1 = engine.analyze_question(q1, a1, fact_guard=guard)
        self.assertIsInstance(item1, DebriefQuestionItem)

        q2 = "请问你有用过 Kafka 做分布式消息队列吗？"
        a2 = "我以前没有做过 Kafka，主要是用本地通道，在这方面接触较少。"
        item2 = engine.analyze_question(q2, a2, fact_guard=guard)
        self.assertEqual(item2.diagnosis, QuestionDiagnosis.EXPERIENCE_BOUNDARY)

        # 4. Generate Session Debrief and Persist
        session_debrief = engine.generate_session_debrief(
            company="DeepMind",
            role="AI Architect",
            round_name="技术终面",
            qa_pairs=[
                {"question": q1, "answer": a1},
                {"question": q2, "answer": a2},
            ],
        )
        self.assertIsInstance(session_debrief, InterviewSessionDebrief)
        self.assertEqual(len(session_debrief.questions), 2)

        # 5. Serialize and Reload
        from dataclasses import asdict
        session_file = self.work_dir / "interview_session_debrief.json"
        session_data = asdict(session_debrief)
        session_file.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(session_file.exists())

        reloaded_data = json.loads(session_file.read_text(encoding="utf-8"))
        self.assertEqual(reloaded_data["session_id"], session_debrief.session_id)
        self.assertEqual(len(reloaded_data["questions"]), 2)
        self.assertEqual(reloaded_data["questions"][1]["diagnosis"], QuestionDiagnosis.EXPERIENCE_BOUNDARY.value)


class TestE2ECLIWorkflow(unittest.TestCase):
    """ATS command smoke coverage; JD CLI and diagnostics have dedicated suites."""

    def test_cli_ats_audit(self):
        from presentation.commands.ats_cmd import cmd_ats_audit
        import argparse

        jd_path = str(PROJECT_ROOT / "examples" / "sample_ai_jd.txt")
        prof_path = str(PROJECT_ROOT / "examples" / "candidate_profile.json")
        args_ats = argparse.Namespace(input_file=prof_path, jd=jd_path, tag=None, json=True)
        cmd_ats_audit(args_ats)


if __name__ == "__main__":
    unittest.main()
