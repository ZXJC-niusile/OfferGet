"""
Unit and integration tests for OfferGet Thin Application Services and Input Router.
(tests/test_services_and_router.py)
"""

import os
import sys
import tempfile
from pathlib import Path
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.input_router import InputMode, InputRouter, InvalidInputError
from core.services import (
    JDService,
    ProfileService,
    MatchService,
    CareerReviewService,
    ResumeService,
    OfferService,
    ReportService,
)
from core.jd_analyst.models import DecodedJD


class TestInputRouter(unittest.TestCase):
    def test_goal_controls_required_inputs_and_plan(self):
        profile = {"candidate": {"name": "Synthetic"}}
        route = InputRouter.route(jd=["JD1", "JD2"], profile=profile, goal="format")
        self.assertEqual(route.executable_stages, ["profile_audit", "resume_build"])
        self.assertEqual(route.missing_inputs, [])
        self.assertFalse(route.can_execute("career_review"))
        missing = InputRouter.route(profile=profile, goal="tailor")
        self.assertEqual(missing.missing_inputs, ["jd"])
        self.assertFalse(missing.is_valid)
        interview = InputRouter.route(jd="JD", profile=profile, goal="interview")
        self.assertTrue(interview.can_execute("interview_prediction"))
        self.assertFalse(interview.can_execute("resume_build"))
        with self.assertRaises(ValueError):
            InputRouter.route(profile=profile, goal="unsupported")

    """Tests for InputRouter covering 4 input states, decisions, blocked stages, and next steps."""

    def test_state_jd_only(self):
        jd_text = "职位：大模型算法专家\n要求：精通 PyTorch 与 vLLM。"
        decision = InputRouter.route(jd=jd_text, profile=None)

        self.assertEqual(decision.mode, InputMode.JD_ONLY.value)
        self.assertTrue(decision.is_valid)
        self.assertTrue(decision.can_execute("jd_decode"))
        self.assertTrue(decision.can_execute("pain_point_analysis"))
        self.assertTrue(decision.is_blocked("full_match"))
        self.assertTrue(decision.is_blocked("career_review"))
        self.assertIn("profile", decision.missing_inputs)
        self.assertNotIn("jd", decision.missing_inputs)
        self.assertTrue(len(decision.next_steps) > 0)

        # Verify raise_if_blocked
        with self.assertRaises(InvalidInputError):
            decision.raise_if_blocked("full_match")

    def test_state_profile_only(self):
        profile = {
            "candidate": {"name": "张三", "title_zh": "算法工程师"},
            "skills": ["PyTorch", "Python"],
        }
        decision = InputRouter.route(jd=None, profile=profile)

        self.assertEqual(decision.mode, InputMode.PROFILE_ONLY.value)
        self.assertTrue(decision.is_valid)
        self.assertTrue(decision.can_execute("profile_audit"))
        self.assertTrue(decision.can_execute("resume_build"))
        self.assertTrue(decision.is_blocked("jd_decode"))
        self.assertTrue(decision.is_blocked("full_match"))
        self.assertIn("jd", decision.missing_inputs)
        self.assertNotIn("profile", decision.missing_inputs)
        self.assertTrue(len(decision.next_steps) > 0)

    def test_state_jd_and_profile(self):
        jd_text = "职位：大模型算法专家\n要求：精通 PyTorch。"
        profile = {
            "candidate": {"name": "张三", "title_zh": "算法工程师"},
            "skills": ["PyTorch"],
        }
        decision = InputRouter.route(jd=jd_text, profile=profile)

        self.assertEqual(decision.mode, InputMode.JD_AND_PROFILE.value)
        self.assertTrue(decision.is_valid)
        self.assertTrue(decision.can_execute("jd_decode"))
        self.assertTrue(decision.can_execute("full_match"))
        self.assertTrue(decision.can_execute("career_review"))
        self.assertTrue(decision.can_execute("resume_build"))
        self.assertTrue(decision.can_execute("report_generation"))
        self.assertEqual(len(decision.blocked_stages), 0)
        self.assertEqual(len(decision.missing_inputs), 0)
        self.assertTrue(len(decision.next_steps) > 0)

    def test_state_multi_jd_and_profile(self):
        jds = [
            "职位：大模型预训练专家\n要求：精通 Megatron。",
            "职位：大模型推理专家\n要求：精通 vLLM 与 TensorRT-LLM。",
        ]
        profile = {
            "candidate": {"name": "李四", "title_zh": "大模型架构师"},
            "skills": ["Megatron", "vLLM"],
        }
        decision = InputRouter.route(jd=jds, profile=profile)

        self.assertEqual(decision.mode, InputMode.MULTI_JD_AND_PROFILE.value)
        self.assertTrue(decision.is_valid)
        for stage in ("multi_jd_decode", "batch_match", "cross_jd_gap_matrix", "career_review"):
            self.assertFalse(decision.can_execute(stage))
            self.assertTrue(decision.is_blocked(stage))
        self.assertTrue(decision.can_execute("profile_audit"))
        self.assertTrue(decision.can_execute("resume_build"))
        self.assertIn("unsupported", " ".join(decision.next_steps))
        self.assertEqual(len(decision.missing_inputs), 0)

    def test_state_invalid_and_fail_fast(self):
        # Without fail_fast: returns INVALID RouteDecision
        decision = InputRouter.route(jd=None, profile=None, fail_fast=False)
        self.assertEqual(decision.mode, InputMode.INVALID.value)
        self.assertFalse(decision.is_valid)
        self.assertIn("jd", decision.missing_inputs)
        self.assertIn("profile", decision.missing_inputs)
        self.assertTrue(len(decision.next_steps) > 0)

        # With fail_fast=True: raises InvalidInputError
        with self.assertRaises(InvalidInputError):
            InputRouter.route(jd="", profile={}, fail_fast=True)


class TestServices(unittest.TestCase):
    """Tests for thin domain application services."""

    def setUp(self):
        self.sample_jd = """
职位：大模型强化学习专家
公司：核心算法部
任职要求：
1. 计算机相关专业硕士及以上学历，3年以上工作经验。
2. 熟练掌握 PyTorch、vLLM、DPO 对齐算法。
3. 抗压能力强，能主导攻坚任务。
"""
        self.sample_profile = {
            "candidate": {
                "name": "王工",
                "degree": "硕士",
                "school": "清华大学",
                "years_of_experience": 4,
                "title_zh": "强化学习研究员",
                "email": "wang@example.com",
            },
            "competencies": {
                "框架与工具": ["PyTorch", "vLLM", "DPO"],
            },
            "experience": [
                {
                    "company": "前沿科技",
                    "role": "算法工程师",
                    "highlights": [
                        {
                            "claim_id": "exp1",
                            "claim_zh": "主导千亿大模型强化学习对齐，基于 DPO 优化模型胜率提升 25%",
                            "verified_metrics": "胜率提升 25%",
                            "role_scope": "强化学习算法研发",
                        }
                    ],
                }
            ],
        }

    def test_jd_service(self):
        service = JDService()

        # 1. Decode text
        decoded = service.decode_jd(self.sample_jd)
        self.assertIn("metadata", decoded)
        self.assertIn("layers", decoded)
        self.assertIn("requirements", decoded)
        self.assertEqual(decoded["metadata"]["role"], "大模型强化学习专家")

        # 2. To canonical
        canonical = service.to_canonical(decoded)
        self.assertIsInstance(canonical, DecodedJD)
        self.assertEqual(canonical.job_title, "大模型强化学习专家")

        # 3. Classify taxonomy
        taxonomy = service.classify_taxonomy(self.sample_jd)
        self.assertEqual(taxonomy["role_key"], "ai_algorithm")

        # 4. Decode from file path
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as f:
            f.write(self.sample_jd)
            tmp_path = f.name
        try:
            decoded_from_file = service.decode_jd(tmp_path)
            self.assertEqual(decoded_from_file["metadata"]["role"], "大模型强化学习专家")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_profile_service(self):
        service = ProfileService()

        # 1. Normalize
        norm = service.normalize(self.sample_profile)
        self.assertIn("candidate", norm)
        self.assertIn("education_grid", norm["candidate"])

        # 2. Evidence index
        index = service.get_evidence_index(self.sample_profile)
        self.assertTrue(len(index.claims) > 0)
        self.assertIn("PyTorch", index.skills)

        # 3. Claims
        claims = service.extract_claims(self.sample_profile)
        self.assertTrue(len(claims) > 0)

        # 4. ProfileContext & ProfileEvidenceIndex
        ctx = service.get_context(self.sample_profile)
        self.assertEqual(ctx.normalized_profile["candidate"]["name"], norm["candidate"]["name"])
        self.assertIs(ctx.evidence_index, service.get_evidence_index(ctx))
        self.assertIs(ctx.evidence_index, service.get_evidence_index(ctx.evidence_index))
        claims_from_ctx = service.extract_claims(ctx)
        self.assertEqual(len(claims_from_ctx), len(claims))
        claims_from_idx = service.extract_claims(ctx.evidence_index)
        self.assertEqual(len(claims_from_idx), len(claims))

    def test_match_service(self):
        jd_service = JDService()
        match_service = MatchService()
        profile_service = ProfileService()

        decoded = jd_service.decode_jd(self.sample_jd)
        match_res = match_service.match(decoded, self.sample_profile)

        self.assertIn("overall_match_score", match_res)
        self.assertIn("interview_prob", match_res)
        self.assertIn("verdict", match_res)
        self.assertIn("all_gaps", match_res)
        self.assertGreaterEqual(match_res["overall_match_score"], 50)

        # Direct ProfileContext acceptance
        ctx = profile_service.get_context(self.sample_profile)
        match_res_ctx = match_service.match(decoded, ctx)
        self.assertEqual(match_res_ctx["overall_match_score"], match_res["overall_match_score"])
        self.assertEqual(match_res_ctx["interview_prob"], match_res["interview_prob"])


    def test_resume_service(self):
        from unittest.mock import patch
        service = ResumeService()
        themes = service.supported_themes
        self.assertIn("modern-navy", themes)
        self.assertIn("ats-plain", themes)

        # Build controls are checked by test_resume_service_options; PDF output
        # and its audit are exercised by the accepted-proposal CLI integration.
        result = {"passed": True, "score": 100}
        with patch("core.resume_builder.audit_resume_quality", return_value=result) as audit:
            self.assertIs(service.audit_resume("synthetic.html"), result)
            audit.assert_called_once_with("synthetic.html")

    def test_offer_service(self):
        service = OfferService()
        offer_data = {
            "company": "未来人工智能科技",
            "role": "大模型高级算法工程师",
            "base_salary_monthly": 45000,
            "months_per_year": 16,
            "performance_split": {"fixed_ratio": 0.85, "floating_ratio": 0.15},
            "probation_months": 3,
            "probation_salary_ratio": 1.0,
            "non_compete_monthly_comp": 15000,
        }

        # Evaluate offer
        eval_res = service.evaluate_offer(offer_data, candidate_profile=self.sample_profile)
        self.assertIn("total_compensation", eval_res)
        self.assertIn("detected_traps", eval_res)
        self.assertEqual(eval_res["trap_count"], 0)

        # Generate counter offer
        counter_res = service.generate_counter_offer(
            offer_data,
            candidate_profile=self.sample_profile,
            target_base=50000.0,
        )
        self.assertIn("counter_offer_letter", counter_res)
        self.assertIn("tactical_leverage_points", counter_res)

        # Generate counter offer letter
        letter = service.generate_counter_offer_letter(
            offer_data,
            candidate_profile=self.sample_profile,
            target_base=50000.0,
        )
        self.assertIn("未来人工智能科技", letter)
        self.assertTrue(len(letter) > 100)

    def test_report_service(self):
        jd_service = JDService()
        match_service = MatchService()
        report_service = ReportService()

        decoded = jd_service.decode_jd(self.sample_jd)
        match_res = match_service.match(decoded, self.sample_profile)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "strategy_report.html")
            generated_path = report_service.generate_offer_strategy_report(
                decoded_jd=decoded,
                match_result=match_res,
                output_path=out_file,
            )
            self.assertTrue(os.path.exists(generated_path))

            # Security audit
            risks = report_service.validate_report_security(generated_path)
            self.assertEqual(risks, [], f"Security gate detected risks: {risks}")

            content = Path(generated_path).read_text(encoding="utf-8")
            self.assertIn("王工", content)
            self.assertIn("大模型强化学习专家", content)

            # Canonical report generation
            canon_file = os.path.join(tmp_dir, "canonical_report.html")
            from core.jd_analyst.decoder import JDDecoder
            from core.jd_analyst.matcher import JDMatcher
            from core.jd_analyst.models import CandidateProfile
            from core.jd_analyst.predictor import JDPredictor
            from core.jd_analyst.redflags import RedFlagDetector

            c_jd = JDDecoder().decode("职位：算法工程师\n要求：精通 Python 与 PyTorch。")
            c_cand = CandidateProfile(name="Alice", skills=["Python", "PyTorch"])
            c_match = JDMatcher().match(c_jd, c_cand)
            c_rf = RedFlagDetector().detect(c_jd)
            c_pred = JDPredictor().predict(jd=c_jd, matcher_result=c_match)
            canon_path = report_service.generate_canonical_report(
                jd=c_jd,
                candidate=c_cand,
                matcher=c_match,
                redflags=c_rf,
                prediction=c_pred,
                output_path=canon_file,
            )
            self.assertTrue(os.path.exists(canon_path))
            self.assertIn("Alice", Path(canon_path).read_text(encoding="utf-8"))

    def test_new_services_m10_m14(self):
        """Test newly converged services (OfferService.compare_offers, CareerReviewService.debrief_real_interview, CommunicationService, AcademicService, ApplicationGuardService, ResumeVersionService)."""
        from core.services import (
            OfferService,
            CareerReviewService,
            CommunicationService,
            AcademicService,
            ApplicationGuardService,
            ResumeVersionService,
        )

        # 1. OfferService.compare_offers
        offer_service = OfferService()
        rep = offer_service.compare_offers([
            {"offer_id": "o1", "company_name": "字节", "role_title": "后端", "base_salary_k": 30, "months": 15},
            {"offer_id": "o2", "company_name": "阿里", "role_title": "后端", "base_salary_k": 32, "months": 16},
        ])
        self.assertEqual(len(rep.evaluations), 2)
        self.assertIsNotNone(rep.winner_offer_id)

        # 2. CareerReviewService.debrief_real_interview
        cr_service = CareerReviewService()
        checklist = cr_service.debrief_real_interview(
            transcript_text="面试官：简单自我介绍\n候选人：我负责高并发中间件研发，主导限流组件落地。",
            target_role="后端架构师",
        )
        self.assertEqual(checklist.total_turns, 1)

        # 3. CommunicationService - test all generated correspondence types
        comm_service = CommunicationService()
        letter = comm_service.follow_up(
            candidate_name="李明",
            recruiter_name="HR Lucy",
            role_name="算法工程师",
            interview_date="2026-09-10",
            company_name="智谱AI",
        )
        self.assertIn("智谱AI", letter.body_text)

        cold = comm_service.cold_outreach(
            candidate_name="李明",
            recipient_name="张总",
            target_company="智谱AI",
            target_role="架构师",
            core_skills=["Python", "PyTorch"],
            key_achievements=["主导千卡训练集群容灾"],
        )
        self.assertIn("架构师", cold.subject)

        cover = comm_service.cover_letter(
            candidate_name="李明",
            company_name="智谱AI",
            role_name="架构师",
            company_mission_hook="大模型推理系统研发",
            matching_experiences=["主导千卡分布式训练与推理优化", "高并发网关中间件架构落地"],
            contact_info="email@example.com / 13800000000",
        )
        self.assertIn("智谱AI", cover.subject)

        resched = comm_service.reschedule(
            candidate_name="李明",
            interviewer_name="HR",
            role_name="架构师",
            original_datetime="周五下午3点",
            conflict_reason="突发线上技术答辩",
            available_slots=["下周一下午2点", "下周二上午10点"],
        )
        self.assertIn("改期", resched.subject)

        ty = comm_service.thank_you(
            candidate_name="李明",
            interviewer_name="李老师",
            role_name="架构师",
            round_name="技术终面",
            discussed_topic="分布式KV缓存淘汰策略",
            candidate_insight="结合W-TinyLFU可降低极端倾斜负载下的失效率",
        )
        self.assertIn("感谢", ty.subject)

        neg = comm_service.salary_negotiation(
            candidate_name="李明",
            recruiter_name="HR",
            company_name="智谱AI",
            role_name="架构师",
            current_offer_package="年薪 60 万",
            competing_offer_summary="手握另一家头部大厂头部评级 Offer",
            target_adjustment="底薪上浮 15%",
            professional_rationale="核心大模型算子优化经验",
        )
        self.assertIn("薪酬", neg.subject)

        dec = comm_service.decline_offer(
            candidate_name="李明",
            recruiter_name="HR",
            company_name="智谱AI",
            role_name="架构师",
            decline_reason="个人职业发展方向聚焦于大模型基础设施",
        )
        self.assertIn("录用沟通", dec.subject)

        boss = comm_service.boss_intro(
            candidate_name="李明",
            target_role="架构师",
            experience_summary="7年大模型基础设施研发经验",
            core_actions=["主导千卡训练集群调度", "算子深度优化"],
            verified_outcomes=["显存利用率达85%", "吞吐提升40%"],
        )
        self.assertIn("李明", boss.subject)

        hh = comm_service.headhunter_intro(
            candidate_name="李明",
            current_or_recent_title="资深后端架构师",
            years_of_experience="7年",
            core_focus_areas=["分布式存储", "高并发网关", "大模型推理"],
            representative_impact=["从0到1主导核心微服务重构", "千卡集群故障自动化恢复"],
            target_job_preferences="大厂技术专家或独角兽基础架构Leader",
        )
        self.assertIn("李明", hh.body_text)

        # 4. AcademicService - test bibtex and defense simulation
        acad_service = AcademicService()
        pubs = acad_service.parse_bibtex("@article{test2025, title={AI for Science}, author={Zhang, San}, journal={Nature}, year={2025}}")
        self.assertEqual(len(pubs), 1)

        sim_dict = acad_service.simulate_defense("分布式中间件系统研发", intensity="先热个身", output_format="dict")
        self.assertIsInstance(sim_dict, dict)
        self.assertIn("summary_stats", sim_dict)

        sim_raw = acad_service.simulate_defense("分布式中间件系统研发", intensity="先热个身", output_format="raw")
        self.assertTrue(hasattr(sim_raw, "to_markdown"))

        # 5. ApplicationGuardService
        guard_service = ApplicationGuardService()
        from core.duplicate_guard import ApplicationChannel
        res = guard_service.check_application(
            new_company="抖音",
            new_role="后端",
            new_channel=ApplicationChannel.DIRECT_CAREERS_SITE,
            applied_date="2026-09-20",
            history=[],
        )
        self.assertFalse(res.has_collision)

        # 6. ResumeVersionService
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_versions.db"
            with ResumeVersionService(db_path) as ver_service:
                from core.application_tracker import ApplicationRecord, AppStatus, ResumeVersion
                ver_service.store.save(ApplicationRecord(
                    id="app_123",
                    target_name="示例公司",
                    role_or_track="架构师",
                    status=AppStatus.APPLIED,
                ))
                r1 = ResumeVersion(
                    version_id="ver_001",
                    application_id="app_123",
                    proposal_id=None,
                    profile_hash="hash_abc",
                    theme="modern-navy",
                    label="v1",
                )
                r2 = ResumeVersion(
                    version_id="ver_002",
                    application_id="app_123",
                    proposal_id=None,
                    profile_hash="hash_def",
                    theme="classic-tech",
                    label="v2",
                )
                ver_service.store.save_resume_version(r1)
                ver_service.store.save_resume_version(r2)

                versions = ver_service.list("app_123")
                self.assertEqual(len(versions), 2)
                got_ver = ver_service.get("ver_001")
                self.assertIsNotNone(got_ver)
                self.assertEqual(got_ver.version_id, "ver_001")

                diff = ver_service.compare("ver_001", "ver_002")
                self.assertEqual(diff["before_version_id"], "ver_001")
                self.assertEqual(diff["after_version_id"], "ver_002")
                self.assertTrue(diff["profile_content_changed"])

    def test_lazy_services_compatibility_matrix(self):
        """Test PEP 562 lazy loading compatibility across core.services symbols and command handlers."""
        # 1. Test direct named imports from core.services
        from core.services import (
            ResumeBuilder,
            OfferNegotiator,
            generate_report,
            audit_resume_quality,
            FactVerificationGuard,
            BaoyanAuditor,
        )
        self.assertIsNotNone(ResumeBuilder)
        self.assertIsNotNone(OfferNegotiator)
        self.assertIsNotNone(generate_report)
        self.assertIsNotNone(audit_resume_quality)
        self.assertIsNotNone(FactVerificationGuard)
        self.assertIsNotNone(BaoyanAuditor)

        # 2. Test module-level getattr and __all__ completeness
        import core.services as s
        for sym in s.__all__:
            val = getattr(s, sym)
            self.assertIsNotNone(val, f"Failed to resolve {sym} via core.services")

        # 3. Test all presentation command handlers are intact and callable
        from presentation.commands import (
            cmd_jd_decode,
            cmd_jd_match,
            cmd_jd_report,
            cmd_resume_build,
            cmd_career_review,
            cmd_selftest,
        )
        for cmd in (cmd_jd_decode, cmd_jd_match, cmd_jd_report, cmd_resume_build, cmd_career_review, cmd_selftest):
            self.assertTrue(callable(cmd))

    def test_services_package_exports_and_facade_identity(self):
        """Verifies that all domain services are exported and match core.services."""
        import services as s
        import core.services as cs

        expected_services = [
            "JDService", "ProfileService", "MatchService", "CareerReviewService",
            "ResumeService", "ResumeVersionService", "OfferService", "ProposalService",
            "ApplicationOutcomeService", "ReportService", "CommunicationService",
            "AcademicService", "ApplicationGuardService",
        ]
        for name in expected_services:
            self.assertTrue(hasattr(s, name), f"services missing {name}")
            self.assertIs(getattr(cs, name), getattr(s, name))

    def test_parse_input_and_detect_and_route_input(self):
        """Tests parse_input and detect_and_route_input across filepaths, raw strings, and dicts."""
        from core.input_router import parse_input, detect_and_route_input, InputRouteResult

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf_json:
            tf_json.write('{"candidate": {"name": "张三"}, "skills": ["Python"]}')
            json_file = tf_json.name

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf_txt:
            tf_txt.write("职位：算法工程师\n要求：熟悉 Python")
            txt_file = tf_txt.name

        try:
            # 1. parse_input from filepaths
            p_json = parse_input(json_file)
            self.assertIsInstance(p_json, dict)
            self.assertEqual(p_json["candidate"]["name"], "张三")

            p_txt = parse_input(txt_file)
            self.assertIsInstance(p_txt, str)
            self.assertIn("算法工程师", p_txt)

            # 2. parse_input from raw strings and dicts
            p_raw_json = parse_input('{"name": "李四"}')
            self.assertIsInstance(p_raw_json, dict)
            self.assertEqual(p_raw_json["name"], "李四")

            d_in = {"a": 1}
            self.assertIs(parse_input(d_in), d_in)

            # 3. detect_and_route_input with filepaths
            route_res = detect_and_route_input(jd=txt_file, profile=json_file)
            self.assertIsInstance(route_res, InputRouteResult)
            self.assertTrue(route_res.can_execute("career_review"))
            self.assertTrue(route_res.can_execute("jd_decode"))

            # Unpack as tuple
            p_jd, p_prof, dec = route_res
            self.assertIn("算法工程师", p_jd)
            self.assertEqual(p_prof["candidate"]["name"], "张三")
            self.assertTrue(dec.is_valid)
        finally:
            if os.path.exists(json_file):
                os.remove(json_file)
            if os.path.exists(txt_file):
                os.remove(txt_file)

    def test_career_review_service_with_filepaths_and_run_context(self):
        """Tests that CareerReviewService.run_review automatically resolves filepaths and attaches RunContext telemetry."""
        service = CareerReviewService()

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf_json:
            import json
            json.dump(self.sample_profile, tf_json, ensure_ascii=False)
            prof_path = tf_json.name

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf_txt:
            tf_txt.write(self.sample_jd)
            jd_path = tf_txt.name

        try:
            result = service.run_review(
                jd_text=jd_path,
                profile_dict=prof_path,
                listing_age_days=5,
                build_resume=False,
            )

            self.assertEqual(result["schema_version"], "career-review.v1")
            self.assertIn("run_context", result)
            self.assertIn("telemetry", result)
            self.assertIn("execution_timestamp", result)

            telemetry = result["telemetry"]
            self.assertIn("run_id", telemetry)
            self.assertIn("fingerprint", telemetry)
            self.assertIn("traces", telemetry)
            self.assertTrue(len(telemetry["traces"]) > 0)
            self.assertEqual(telemetry["traces"][0]["stage_name"], "career_review")
            self.assertGreater(telemetry["total_elapsed_ms"], 0.0)
            from core.application_tracker import ApplicationStore
            from core.job_flow import create_review_session
            with tempfile.TemporaryDirectory() as directory:
                db = Path(directory) / "proposals.db"
                for terminal in ("accepted", "rejected"):
                    with self.subTest(status=terminal):
                        service.persist_proposal(result, db)
                        with ApplicationStore(str(db)) as store:
                            proposal = store.get_material_proposal(result["material_proposal"]["proposal_id"])
                            if terminal == "accepted":
                                proposal.accept(self.sample_profile, self.sample_jd)
                            else:
                                # A separate rejection record uses the same valid source/patch hash.
                                from core.material_proposal import MaterialProposal
                                data = dict(result["material_proposal"])
                                data["proposal_id"] += "-rejected"
                                data["status"] = "draft"
                                proposal = MaterialProposal.from_dict(data)
                                proposal.proposal_hash = proposal.compute_hash()
                                result["material_proposal"] = proposal.to_dict()
                                proposal.reject()
                            store.save_material_proposal(proposal)
                        service.persist_proposal(result, db)
                        self.assertEqual(result["material_proposal"]["status"], terminal)
                        self.assertEqual(result["summary"]["pending_change_count"], 0)
                        session = create_review_session(self.sample_jd, self.sample_profile, {**result, "goal": "tailor"})
                        self.assertEqual(session["status"], "accepted" if terminal == "accepted" else "needs_source_revision")
        finally:
            if os.path.exists(prof_path):
                os.remove(prof_path)
            if os.path.exists(jd_path):
                os.remove(jd_path)

    def test_career_review_service_with_interview_contract_validation(self):
        """Tests that CareerReviewService enforces interview_review_contract when note and proposal are passed."""
        service = CareerReviewService()

        note = {
            "company": "测试科技",
            "position": "强化学习研究员",
            "round": "一面",
            "date": "2026-09-30",
            "questions": "请谈谈千亿大模型强化学习对齐经验",
            "self_reflection": "说明了基于 DPO 优化模型胜率提升 25%",
            "difficulty_points": "分布式并行调试",
            "mood": "良好",
        }
        proposal = {
            "summary": {
                "text": "候选人说明了基于 DPO 优化模型胜率提升 25%",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/self_reflection",
                    "excerpt": "基于 DPO 优化模型胜率提升 25%",
                }],
            },
            "observations": [{
                "id": "obs-1",
                "text": "候选人提到了胜率提升 25%",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/self_reflection",
                    "excerpt": "胜率提升 25%",
                }],
            }],
            "clarifications": [],
            "practice_focuses": [],
            "next_questions": [],
        }

        result = service.run_review(
            jd_text=self.sample_jd,
            profile_dict=self.sample_profile,
            interview_note=note,
            interview_proposal=proposal,
            build_resume=False,
        )

        self.assertIn("validated_proposal", result)
        self.assertIn("interview_review_snapshot", result)
        self.assertEqual(result["validated_proposal"]["summary"]["text"], proposal["summary"]["text"])

    def test_scan_unsubmitted_placeholders(self):
        from core.input_router import scan_unsubmitted_placeholders
        raw_template = {
            "candidate": {
                "name": "{{CANDIDATE_NAME}}",
                "phone": "{{PHONE}}",
                "email": "",
            },
            "experience": [
                {
                    "company": "测试公司",
                    "role": "产品实习生",
                    "bullets": ["负责核心功能测试，达成提升指标 {{METRIC_RATE}}%"]
                }
            ]
        }
        res = scan_unsubmitted_placeholders(raw_template)
        self.assertTrue(res["has_placeholders"])
        self.assertIn("candidate.name", res["missing_fields"])
        self.assertIn("candidate.email", res["missing_fields"])
        self.assertIn("candidate.phone", res["missing_fields"])
        self.assertIn("CANDIDATE_NAME", [p["token"] for p in res["placeholders"]])
        self.assertIn("METRIC_RATE", [p["token"] for p in res["placeholders"]])
        self.assertIn("⚠️ 检测到未提交的关键信息与占位字段", res["proactive_inquiry"])

        # When profile is clean with real data
        clean_profile = {
            "candidate": {
                "name": "张三",
                "phone": "+86 138-0000-0000",
                "email": "zhangsan@example.com",
                "title": "产品经理",
            },
            "experience": []
        }
        clean_res = scan_unsubmitted_placeholders(clean_profile)
        self.assertFalse(clean_res["has_placeholders"])
        self.assertEqual(len(clean_res["missing_fields"]), 0)


if __name__ == "__main__":
    unittest.main()



def test_proposal_export_defaults_and_actual_paths(tmp_path, monkeypatch, capsys):
    import json

    from cli import build_parser
    from core.material_proposal import (
        MaterialProposal,
        jd_fingerprint,
        profile_fingerprint,
    )
    from presentation.commands.proposal_cmd import cmd_proposal_accept
    from services.offer_service import ProposalService

    profile = {"candidate": {"name": "Synthetic Candidate"},
               "experience": [{"bullets": ["Developed API"]}]}
    jd = "Backend engineer"
    source, job, db = tmp_path / "profile.json", tmp_path / "jd.txt", tmp_path / "proposals.db"
    source.write_text(json.dumps(profile))
    job.write_text(jd)
    artifact = tmp_path / "actual-shadow.docx"
    artifact.write_bytes(b"synthetic renderer result")
    def render(profile, *, theme, output_dir):
        assert theme == "modern-navy"
        return {"docx": artifact}
    monkeypatch.setattr(ResumeService, "build_resume", staticmethod(render))
    for mode in ("service", "text", "json", "legacy"):
        with ProposalService(db) as service:
            service.save(MaterialProposal(
                proposal_id=mode, source_profile_hash=profile_fingerprint(profile),
                source_jd_hash=jd_fingerprint(jd), patches=[{
                    "target_path": "experience[0].bullets[0]", "before": "Developed API",
                    "after": "Developed API and error handling", "validation_status": "applied"}]))
            output = tmp_path / f"{mode}.json"
            if mode == "service":
                result = service.accept(mode, profile, jd, output, build_resume=True)
                assert result["generated_resumes"]["docx"] == str(artifact)
                continue
        args = build_parser().parse_args([
            "proposal", "accept", mode, "--profile", str(source), "--jd", str(job),
            "--db", str(db), "--output", str(output), "--build-resume"]
            + (["--json"] if mode == "json" else []))
        if mode == "legacy":
            del args.resume_theme
        cmd_proposal_accept(args)
        stdout = capsys.readouterr().out
        if mode == "json":
            assert json.loads(stdout)["generated_resumes"]["docx"] == str(artifact)
        else:
            assert str(output) in stdout and f"docx: {artifact}" in stdout
