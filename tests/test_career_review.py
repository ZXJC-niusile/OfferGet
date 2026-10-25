"""
Unit and Integration Tests for Career Review Pipeline (career-review.v1)
Testing:
1. End-to-end flow with sample profile and AI JD: schema version, exact 3 questions, valid structure.
2. Status is `awaiting_answer` when no answer is provided.
3. Structured feedback with `metric_drift` diagnosis when answer claims percentage gain without baseline.
4. Structured feedback with `well_defended` diagnosis when answer provides clear baseline and methodology.
5. Structured feedback with `fatal_gap` when candidate admits no experience / unfamiliarity.
6. Dynamic savings parsing in fact_guard without hardcoded 3800 bypass.
7. HTML escaping across reporter outputs to prevent XSS injection.
8. CLI `review` subcommand invocation with --json and --output flags.
"""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.job_flow import (
    run_career_review,
    generate_resume_advice,
    build_candidate_profile,
    generate_tailored_profile_from_review,
    create_review_session,
    validate_session_answers,
    save_review_session,
    load_review_session,
)
from core.fact_guard import FactVerificationGuard
from core.profile_adapter import iter_profile_claims
from core.jd_analyst.decoder import JDDecoder
from core.jd_analyst.matcher import JDMatcher
from core.jd_analyst.reporter import OfferStrategyReporter
from core.jd_analyst.predictor import JDPredictor


class TestCareerReviewPipeline(unittest.TestCase):

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        # Reviewed synthetic public facts for export tests; keep the restricted
        # master above unchanged for analysis and disclosure-negative coverage.
        self.public_profile_path = PROJECT_ROOT / "examples" / "candidate_profile_minimal.json"
        self.public_profile_data = json.loads(self.public_profile_path.read_text(encoding="utf-8"))

        self.jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"
        with open(self.jd_path, "r", encoding="utf-8") as f:
            self.jd_text = f.read()

    def test_01_e2e_career_review_schema(self):
        """Test top-level contract strictly conforms to career-review.v1."""
        res = run_career_review(self.jd_text, self.profile_data)

        self.assertEqual(res["schema_version"], "career-review.v1")
        self.assertIn("jd_breakdown", res)
        self.assertIn("match_summary", res)
        self.assertIn("resume_advice", res)
        self.assertIn("interview_questions", res)
        self.assertIn("answer_feedback", res)
        self.assertIn("polish_focus", res)

        # JD breakdown fields
        self.assertTrue(len(res["jd_breakdown"]["job_title"]) > 0)
        self.assertTrue(len(res["jd_breakdown"]["hard_thresholds"]) > 0)
        self.assertTrue(len(res["jd_breakdown"]["core_skills"]) > 0)

        # Exactly 3 targeted questions
        self.assertEqual(len(res["interview_questions"]), 3)
        for idx, q in enumerate(res["interview_questions"], 1):
            self.assertEqual(q["question_id"], idx)
            self.assertTrue(len(q["question_zh"]) > 0)
            self.assertTrue(len(q["interviewer_intent"]) > 0)
            self.assertTrue(len(q["prep_keypoints"]) > 0)

        # Polish focus
        self.assertEqual(res["polish_focus"]["focus_area"], "interview_defense")
        self.assertGreaterEqual(len(res["polish_focus"]["defense_checkpoints"]), 3)
        self.assertEqual(len(res["answer_feedback"]), 3)
        for feedback in res["answer_feedback"]:
            self.assertEqual(feedback["status"], "awaiting_answer")
            self.assertEqual(feedback["diagnosis"], "not_submitted")
            self.assertEqual(feedback["candidate_answer"], "")


    def test_03_answer_feedback_with_metric_drift(self):
        """Diagnose metric_drift when answer claims quantified gain without baseline."""
        answers = {
            "answers": [
                {"question_id": 1, "answer": "通过优化，我们将模型推理吞吐提升 50%，显存降低 30%。"},
                {"question_id": 2, "answer": "64B Dense 预训练 Baseline MFU 为 38%，我负责 Megatron-LM Sequence Parallel 通信重叠优化，从 38% 提升至 52%，测算口径为 H800 理论峰值。"}
            ]
        }
        # Keep feedback validation independent from ranking unrelated resume entries.
        profile = {"projects": [{"name": "Synthetic training evaluation", "bullets": [
            "64B Dense 预训练 Baseline MFU 为 38%，我负责 Megatron-LM Sequence Parallel 通信重叠优化，从 38% 提升至 52%，测算口径为 H800 理论峰值。"
        ]}]}
        res = run_career_review(self.jd_text, profile, answers_dict=answers)
        feedbacks = res["answer_feedback"]
        self.assertEqual(len(feedbacks), 3)

        # Question 1 mentions % gain without baseline -> metric_drift
        q1_fb = feedbacks[0]
        self.assertEqual(q1_fb["status"], "evaluated")
        self.assertEqual(q1_fb["diagnosis"], "metric_drift")
        self.assertIn("基线", q1_fb["analysis"])

        # Question 2 provides baseline and methodology -> well_defended
        q2_fb = feedbacks[1]
        self.assertEqual(q2_fb["status"], "evaluated")
        self.assertEqual(q2_fb["diagnosis"], "well_defended")

        # Question 3 was not answered -> awaiting_answer
        q3_fb = feedbacks[2]
        self.assertEqual(q3_fb["status"], "awaiting_answer")

    def test_04_answer_feedback_with_fatal_gap(self):
        """Diagnose experience_boundary when candidate admits not knowing or having no experience."""
        answers = {
            "answers": [
                {"question_id": 1, "answer": "这块技术我之前没做过，不太了解底层细节。"}
            ]
        }
        res = run_career_review(self.jd_text, self.profile_data, answers_dict=answers)
        q1_fb = res["answer_feedback"][0]
        self.assertEqual(q1_fb["status"], "evaluated")
        self.assertEqual(q1_fb["diagnosis"], "experience_boundary")
        self.assertEqual(q1_fb.get("refined_answer", ""), "")
        self.assertEqual(q1_fb.get("revised_answer", ""), "")
        self.assertFalse(q1_fb.get("can_revise", True))
        self.assertIn("未在实际项目中主导过", q1_fb.get("coaching_advice", ""))

    def test_05_resume_advice_grounding_and_no_hallucination(self):
        """Ensure resume advice adheres to verified vs unsupported actions without inventing facts."""
        res = run_career_review(self.jd_text, self.profile_data)
        advices = res["resume_advice"]
        self.assertGreater(len(advices), 0)

        for adv in advices:
            self.assertIn(adv["action"], ["keep", "rewrite", "add_evidence", "remove", "ask_user"])
            self.assertIn(adv["state"], ["verified", "claimed", "needs_confirmation", "unsupported"])
            if adv["state"] == "unsupported":
                # Must not hallucinate safe_bullet
                self.assertEqual(adv["safe_bullet"], "")
                self.assertIn("ask_user", adv["action"])

    def test_06_fact_guard_dynamic_savings_parsing(self):
        """Test fact_guard dynamically parses non-3800 values without hardcoded 3800 assumptions."""
        custom_profile = {
            "candidate": {"name": "Test User", "years_of_experience": 5},
            "experience": [
                {
                    "company": "Tech Corp",
                    "role": "Architect",
                    "highlights": [
                        {
                            "claim_id": "EXP-SAVINGS",
                            "claim_zh": "优化算力成本，年均节省云算力 1200 万元。",
                            "verified_metrics": {
                                "annual_savings": "1200 万元"
                            }
                        }
                    ]
                }
            ]
        }
        guard = FactVerificationGuard(custom_profile)
        # Verify 1200 is in verified set and 3800 is NOT in verified set
        self.assertIn(1200.0, guard.all_verified_numbers)
        self.assertNotIn(3800.0, guard.all_verified_numbers)

        # Bullet stating 1200 万元 passes
        pass_res = guard.verify_facts("优化算力成本，年均节省云算力 1200 万元。")
        self.assertTrue(pass_res["passed"])

        # Bullet inflating to 2000 万元 fails with drift
        drift_res = guard.verify_facts("优化算力成本，年均节省云算力 2000 万元。")
        self.assertFalse(drift_res["passed"])
        self.assertIn("1200", drift_res["drifts"][0]["verified_baseline"])

    def test_07_html_escaping_prevents_xss(self):
        """Test reporter safely escapes user input containing HTML/script tags."""
        malicious_jd_text = """
        【岗位名称】<script>alert('xss')</script>架构师
        【团队部门】<img src=x onerror=alert(1)>
        【核心技能】<svg onload=alert(2)>, Python, PyTorch
        """
        decoder = JDDecoder()
        decoded_jd = decoder.decode(malicious_jd_text)
        cand = build_candidate_profile(self.profile_data)
        matcher = JDMatcher()
        matcher_result = matcher.match(decoded_jd, cand)
        reporter = OfferStrategyReporter()
        pred = JDPredictor().predict(decoded_jd, matcher_result)
        from core.jd_analyst.models import RedFlagReport
        redflags = RedFlagReport()

        html_out = reporter.generate_html(decoded_jd, cand, matcher_result, redflags, pred)

        # Raw <script> should be escaped
        self.assertNotIn("<script>alert('xss')</script>", html_out)
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;", html_out)
        self.assertNotIn("<img src=x onerror=alert(1)>", html_out)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html_out)

    def test_08_missing_profile_facts_are_not_invented(self):
        """Missing education, major, and years stay unknown rather than defaults."""
        result = run_career_review("职位：算法工程师", {"candidate": {"name": "匿名"}})
        candidate = build_candidate_profile({"candidate": {"name": "匿名"}})
        self.assertEqual(candidate.education_level, "")
        self.assertEqual(candidate.major, "")
        self.assertEqual(candidate.years_of_experience, 0.0)
        self.assertNotIn("5年及以上算法研发经验（资深/专家岗推定）", str(result))

    def test_09_invalid_answers_are_reported(self):
        answers = {"answers": [
            {"question_id": "bad", "answer": "x"},
            *[{"question_id": bad_id, "answer": "x"} for bad_id in ([], {}, None, True, 1.0)],
            {"question_id": 1, "answer": None},
            {"question_id": 1, "answer": "duplicate"},
            {"question_id": 99, "answer": "unknown"},
        ]}
        result = run_career_review(self.jd_text, self.profile_data, answers_dict=answers)
        reasons = {item["reason"] for item in result["input_quality"]["invalid_answers"]}
        self.assertIn("invalid_question_id", reasons)
        self.assertIn("duplicate_question_id", reasons)
        self.assertIn("unknown_question_id", reasons)
        self.assertEqual(result["answer_feedback"][0]["status"], "awaiting_answer")

    def test_10_listing_age_does_not_create_uncalibrated_probability(self):
        result = run_career_review(self.jd_text, self.profile_data, listing_age_days=90)
        self.assertEqual(result["match_summary"]["prediction"]["listing_age_days"], 90)
        self.assertIsNone(result["match_summary"]["prediction"]["base_min_prob"])
        self.assertIsNone(result["match_summary"]["prediction"]["base_max_prob"])
        self.assertIn("暂不提供", result["match_summary"]["prediction_note"])

    def test_11_evidence_matrix_and_claim_risk_gate(self):
        profile = {
            "candidate": {"name": "匿名", "degree": "本科", "years_of_experience": 3},
            "skills": ["vLLM"],
            "experience": [{
                "role": "算法工程师",
                "highlights": [{
                    "claim_id": "RISK-01",
                    "claim_zh": "主导 vLLM 平台优化，P99 降低 40%。"
                }]
            }]
        }
        jd = "职位：推理工程师\n岗位职责：负责 vLLM 推理服务优化。\n任职要求：本科，3年经验，熟悉 vLLM。"
        result = run_career_review(jd, profile)
        vllm_items = [item for item in result["resume_advice"] if "vLLM" in item["requirement"]]
        self.assertTrue(vllm_items)
        item = vllm_items[0]
        self.assertIn(item["coverage"], {"direct", "weak"})
        self.assertTrue(item["evidence_refs"])
        self.assertTrue(item["risk_flags"])
        self.assertEqual(item["safe_bullet"], "")
        self.assertEqual(item["action"], "ask_user")
        self.assertTrue(item["next_question"])

    def test_12_project_bullets_are_indexed_as_evidence(self):
        profile = {
            "candidate": {"name": "匿名"},
            "projects": [{
                "name": "推理实验",
                "role": "核心参与者",
                "bullets": ["使用 SGLang 完成离线推理实验。"]
            }]
        }
        claims = iter_profile_claims(profile)
        paths = {claim.source_path for claim in claims}
        self.assertIn("projects[0].bullets[0]", paths)

    def test_13_answer_feedback_exposes_evidence_gaps(self):
        answers = {"answers": [{"question_id": 1, "answer": "我负责优化，吞吐提升 50%。"}]}
        result = run_career_review(self.jd_text, self.profile_data, answers_dict=answers)
        feedback = result["answer_feedback"][0]
        self.assertIn("missing_elements", feedback)
        self.assertIn("follow_up_questions", feedback)
        self.assertTrue(feedback["follow_up_questions"])
        self.assertEqual(result["practice_queue"][0]["question_id"], 1)
        self.assertIn(result["practice_queue"][0]["question"], feedback["follow_up_questions"])
        session = create_review_session(self.jd_text, self.profile_data, result)
        resumed = run_career_review(self.jd_text, self.profile_data, session_data=session)
        self.assertEqual(resumed["interview_questions"], result["interview_questions"])
        self.assertEqual(resumed["practice_queue"], result["practice_queue"])

    def test_14_too_long_answer_is_rejected(self):
        answers = {"answers": [{"question_id": 1, "answer": "x" * 8001}]}
        result = run_career_review(self.jd_text, self.profile_data, answers_dict=answers)
        reasons = {item["reason"] for item in result["input_quality"]["invalid_answers"]}
        self.assertIn("answer_too_long", reasons)
        self.assertEqual(result["answer_feedback"][0]["status"], "awaiting_answer")

    def test_15_cli_review_subcommand(self):
        """Test cli.py review execution via subprocess."""
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "cli.py"),
            "review",
            str(self.jd_path),
            "--profile",
            str(self.profile_path),
            "--json"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT))
        self.assertEqual(proc.returncode, 0, f"CLI error: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema_version"], "career-review.v1")
        self.assertEqual(data["goal"], "tailor")
        self.assertEqual(data["interview_questions"], [])
        self.assertLessEqual(len(data["summary"]["key_issues"]), 3)
        self.assertLessEqual(len(data["summary"]["pending_changes"]), 3)
        self.assertEqual(data["summary"]["next_action"]["kind"], "check_threshold" if data["match_summary"]["is_hard_vetoed"] else "provide_evidence")
        plain = subprocess.run(cmd[:-1], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT))
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertIn("下一步：", plain.stdout)
        self.assertNotIn("Final Match Score", plain.stdout)
        self.assertNotIn("Exactly 3", plain.stdout)

    def test_16_cli_output_and_json_keeps_stdout_machine_readable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "review.json"
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "cli.py"),
                "review",
                str(self.jd_path),
                "--profile",
                str(self.profile_path),
                "--output",
                str(output_path),
                "--json",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            parsed_stdout = json.loads(proc.stdout)
            self.assertEqual(parsed_stdout["schema_version"], "career-review.v1")
            self.assertTrue(output_path.exists())
            self.assertIn("written to", proc.stderr)

    def test_career_review_build_resume_wiring_and_default_theme(self):
        """API wiring and facts; real PDF acceptance is owned by the CLI workflow."""
        import tempfile
        from unittest.mock import patch
        from tests.test_resume_builder import FastBrowserRenderer
        with tempfile.TemporaryDirectory() as tmpdir, patch("core.resume_builder.BrowserRenderer", FastBrowserRenderer):
            out_dir = Path(tmpdir) / "resumes"
            res = run_career_review(
                self.jd_text,
                self.public_profile_data,
                build_resume=True,
                resume_output_dir=out_dir,
                reserve_photo=True,
            )
            # 1. Verify generated_resumes structure and PDF file
            self.assertIn("generated_resumes", res)
            self.assertIn("tailored_profile", res)

            gen = res["generated_resumes"]
            self.assertEqual(gen["theme"], "modern-navy")
            self.assertIn("pdf", gen)
            self.assertIn("html", gen)
            pdf_path = Path(gen["pdf"])
            self.assertTrue(pdf_path.exists())
            self.assertTrue(pdf_path.is_file())
            self.assertGreater(pdf_path.stat().st_size, 0)

            # 2. Verify rewritten experience contains safe_bullet evidence
            safe_bullets = [
                a["safe_bullet"] for a in res["resume_advice"]
                if a.get("safe_bullet") and a.get("category") != "threshold"
            ]
            self.assertTrue(len(safe_bullets) > 0)
            tailored_exp_bullets = [
                b for exp in res["tailored_profile"]["experience"]
                for b in exp.get("bullets", [])
            ]
            self.assertTrue(len(tailored_exp_bullets) > 0)
            has_safe_evidence = any(
                any(sb in b or b in sb for b in tailored_exp_bullets)
                for sb in safe_bullets
            )
            self.assertTrue(has_safe_evidence, "Rewritten experience must contain safe_bullet evidence")

            # 3. Verify photo placeholder slot ("预留证件照" / photo-placeholder)
            html_path = Path(gen["html"])
            self.assertTrue(html_path.exists())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertTrue("预留证件照" in html_text or "photo-placeholder" in html_text)
            self.assertTrue(res["tailored_profile"]["candidate"].get("reserve_photo", False))
            from services.review_service import CareerReviewService
            updated = copy.deepcopy(self.public_profile_data)
            updated["projects"] = [{"name": "UpdatedNamedResumeMarker", "bullets": ["使用 Python 开发新版报表工具。"]}]
            CareerReviewService().refresh_resume(res, updated, "modern-navy", out_dir)
            current = res["generated_resumes"]
            for kind in ("html", "pdf"):
                self.assertEqual(Path(current[f"named_{kind}"]), Path(gen[f"named_{kind}"]))
                self.assertEqual(Path(current[f"named_{kind}"]).read_bytes(), Path(current[kind]).read_bytes())
            self.assertIn("UpdatedNamedResumeMarker", Path(current["named_html"]).read_text(encoding="utf-8"))

    def test_18_generate_tailored_profile_from_review_unit(self):
        """Test unit behavior of generate_tailored_profile_from_review with ResumePatch gates."""
        base = {
            "candidate": {
                "name": "李四",
                "institution": "上海交通大学",
                "title_zh": "大模型算法工程师",
            },
            "experience": [
                {
                    "company": "科技公司A",
                    "role": "算法研究员",
                    "period": "2024.01 - 至今",
                    "bullets": [
                        "负责训练流水线优化，通信开销降低 20%。",
                    ],
                }
            ],
        }
        # Case A: Metric inflation (20% -> 35%) is rejected by FactVerificationGuard gate
        inflated_review = {
            "resume_advice": [
                {
                    "requirement": "Megatron-LM",
                    "category": "skill",
                    "state": "verified",
                    "action": "rewrite",
                    "safe_bullet": "基于 Megatron-LM 重构并行训练通信算子，通信开销降低 35%。",
                    "evidence_refs": [{"source_path": "experience[0].bullets[0]", "excerpt": "负责训练流水线优化"}],
                },
            ]
        }
        tailored_inflated = generate_tailored_profile_from_review(inflated_review, base)
        # Base profile should remain untouched (immutability)
        self.assertEqual(len(base["experience"][0]["bullets"]), 1)
        self.assertNotIn("Megatron-LM", base["experience"][0]["bullets"][0])
        # Tailored profile must NOT accept the inflated 35%
        bullets_inflated = tailored_inflated["experience"][0]["bullets"]
        self.assertFalse(any("35%" in b for b in bullets_inflated))
        # Patch must be recorded as rejected
        patches_inflated = tailored_inflated.get("applied_patches", [])
        self.assertEqual(len(patches_inflated), 1)
        self.assertEqual(patches_inflated[0]["validation_status"], "rejected")
        self.assertIn("fact_guard_rejected", patches_inflated[0]["reason"])

        # Case B1: 无新增依据的 Megatron-LM / 方法扩张必须被拒绝（rejected）
        unsupported_review = {
            "resume_advice": [
                {
                    "requirement": "Megatron-LM",
                    "category": "skill",
                    "state": "verified",
                    "action": "rewrite",
                    "safe_bullet": "基于 Megatron-LM 重构并行训练通信算子，通信开销降低 20%。",
                    "evidence_refs": [{"source_path": "experience[0].bullets[0]", "excerpt": "负责训练流水线优化"}],
                },
                {
                    "requirement": "幻觉技能",
                    "category": "skill",
                    "state": "needs_confirmation",
                    "action": "ask_user",
                    "safe_bullet": "",
                    "evidence_refs": [],
                },
            ]
        }
        tailored_b1 = generate_tailored_profile_from_review(unsupported_review, base)
        bullets_b1 = tailored_b1["experience"][0]["bullets"]
        self.assertFalse(any("Megatron-LM" in b for b in bullets_b1))
        self.assertFalse(any("通信算子重构" in b for b in bullets_b1))
        patches_b1 = tailored_b1.get("applied_patches", [])
        patch_b1 = next(p for p in patches_b1 if p["source_claim_id"] == "Megatron-LM")
        self.assertEqual(patch_b1["validation_status"], "rejected")
        self.assertIn("fact_guard_rejected", patch_b1["reason"])

        # Case B2: 真正不增加未经支持事实的改写（例如：“负责训练流水线与通信优化，通信开销降低 20%。”）被成功应用
        grounded_review = {
            "resume_advice": [
                {
                    "requirement": "训练流水线优化",
                    "category": "skill",
                    "state": "verified",
                    "action": "rewrite",
                    "safe_bullet": "负责训练流水线与通信优化，通信开销降低 20%。",
                    "evidence_refs": [{"source_path": "experience[0].bullets[0]", "excerpt": "负责训练流水线优化，通信开销降低 20%。"}],
                },
                {
                    "requirement": "幻觉技能",
                    "category": "skill",
                    "state": "needs_confirmation",
                    "action": "ask_user",
                    "safe_bullet": "",
                    "evidence_refs": [],
                },
            ]
        }
        tailored_grounded = generate_tailored_profile_from_review(grounded_review, base)
        bullets_grounded = tailored_grounded["experience"][0]["bullets"]
        self.assertTrue(any("负责训练流水线与通信优化" in b for b in bullets_grounded))
        self.assertTrue(any("20%" in b for b in bullets_grounded))
        self.assertNotIn("幻觉技能", " ".join(bullets_grounded))
        patches_grounded = tailored_grounded.get("applied_patches", [])
        applied_patch = next(p for p in patches_grounded if p["validation_status"] == "applied")
        self.assertEqual(applied_patch["target_path"], "experience[0].bullets[0]")

        # Case B3: 当底稿或新增确认材料确实包含 Megatron-LM 时，方可应用包含 Megatron-LM 的改写
        base_with_megatron = copy.deepcopy(base)
        base_with_megatron["competencies"] = {
            "frameworks": ["Megatron-LM", "通信算子重构", "并行训练"]
        }
        tailored_b3 = generate_tailored_profile_from_review(unsupported_review, base_with_megatron)
        bullets_b3 = tailored_b3["experience"][0]["bullets"]
        self.assertTrue(any("Megatron-LM" in b for b in bullets_b3))
        self.assertTrue(any("20%" in b for b in bullets_b3))
        patches_b3 = tailored_b3.get("applied_patches", [])
        applied_patch_b3 = next(p for p in patches_b3 if p["source_claim_id"] == "Megatron-LM")
        self.assertEqual(applied_patch_b3["validation_status"], "applied")

        # Case C: Re-application is idempotent (already_applied, no duplicate bullets)
        tailored_reapplied = generate_tailored_profile_from_review(unsupported_review, tailored_b3)
        self.assertEqual(len(tailored_reapplied["experience"][0]["bullets"]), 1)
        patches_reapplied = tailored_reapplied.get("applied_patches", [])
        reapplied_patch = next(p for p in patches_reapplied if p["source_claim_id"] == "Megatron-LM")
        self.assertEqual(reapplied_patch["validation_status"], "already_applied")

        # Photo reservation and bridged candidate fields
        self.assertTrue(tailored_grounded["candidate"]["reserve_photo"])
        self.assertEqual(tailored_grounded["candidate"]["school"], "上海交通大学")
        self.assertEqual(tailored_grounded["candidate"]["title"], "大模型算法工程师")

    def test_grounded_rewrites_use_the_evidenced_bullet_in_both_sections(self):
        from core.material_proposal import (
            apply_material_proposal,
            create_material_proposal,
        )

        source = ["Implemented parser. Then documented it.", "Implemented parser."]
        replacement = "Implemented a parser."
        for section in ("experience", "projects"):
            for path, excerpt, action, bullets, expected in (
                ("bullets[1]", source[1], "rewrite", source, [source[0], replacement]),
                ("bullets[0]", "not in source", "rewrite", source, source + [replacement]),
                ("highlights[0]", source[1], "rewrite", source, [source[0], replacement]),
                ("highlights[0]", source[1], "rewrite", [source[1], source[1]],
                 [source[1], source[1], replacement]),
                ("bullets[1]", source[1], "supplement", source, source + [replacement]),
            ):
                with self.subTest(section=section, path=path, action=action, bullets=bullets):
                    profile = {"candidate": {"name": "Synthetic"}, section: [
                        {"bullets": ["Unrelated project fact."]}, {"bullets": list(bullets)},
                    ]}
                    original = copy.deepcopy(profile)
                    advice = {"resume_advice": [{"action": action, "safe_bullet": replacement,
                              "evidence_refs": [{"source_path": f"{section}[1].{path}",
                                                 "excerpt": excerpt}]}]}
                    tailored = generate_tailored_profile_from_review(advice, profile)
                    self.assertEqual(tailored[section][1]["bullets"], expected)
                    self.assertEqual(tailored[section][0]["bullets"], ["Unrelated project fact."])
                    patch = tailored["applied_patches"][0]
                    self.assertEqual(patch["before"], source[1] if len(expected) == 2 else "")
                    proposal = create_material_proposal(
                        {"tailored_profile": tailored}, profile, "JD", "rewrite-target",
                    )
                    applied = apply_material_proposal(proposal, profile, "JD")
                    self.assertEqual(applied[section][1]["bullets"], expected)
                    repeated = generate_tailored_profile_from_review(advice, tailored)
                    self.assertEqual(repeated[section][1]["bullets"], expected)
                    self.assertEqual(repeated["applied_patches"][0]["validation_status"], "already_applied")
                    self.assertEqual(profile, original)

    def test_goal_skips_unrelated_work_and_retains_interview_evidence_on_resume(self):
        from unittest.mock import patch
        with patch("core.job_flow.select_targeted_interview_questions") as questions:
            tailored = run_career_review(self.jd_text, self.profile_data, goal="tailor")
            questions.assert_not_called()
        self.assertEqual(tailored["interview_questions"], [])
        self.assertEqual(tailored["question_generation"]["dimensions"], [])
        self.assertEqual(create_review_session(self.jd_text, self.profile_data, tailored)["status"], "awaiting_evidence")
        with patch("core.job_flow.generate_tailored_profile_from_review") as material, \
                patch("core.jd_analyst.predictor.InterviewTop20Predictor.predict") as legacy_questions:
            interview = run_career_review(self.jd_text, self.profile_data, goal="interview")
            material.assert_not_called()
            legacy_questions.assert_not_called()
        session = create_review_session(self.jd_text, self.profile_data, interview)
        self.assertEqual(session["questions_snapshot"][0]["evidence_refs"], interview["interview_questions"][0]["evidence_refs"])
        resumed = run_career_review(self.jd_text, self.profile_data, goal="interview", session_data=session)
        self.assertEqual(resumed["interview_questions"], interview["interview_questions"])
        self.assertEqual(resumed["material_proposal"]["patches"], [])
        for question in interview["interview_questions"]:
            self.assertTrue(question["evidence_refs"])
            self.assertIn(question["evidence_refs"][0]["excerpt"][:45], question["question_zh"])
        for status in ("accepted", "rejected"):
            from core.job_flow import build_review_summary
            interview["material_proposal"]["status"] = status
            self.assertEqual(build_review_summary(interview)["next_action"]["kind"], "answer_question")
        empty = run_career_review("简历面试", {"candidate": {"name": "Synthetic"}}, goal="interview")
        self.assertEqual(empty["interview_questions"], [])
        self.assertEqual(empty["summary"]["next_action"]["kind"], "provide_resume")

    def test_evidence_answers_resume_and_require_explicit_proposal_acceptance(self):
        from core.material_proposal import MaterialProposal, apply_material_proposal
        profile = {"candidate": {"name": "Synthetic"}, "projects": [{"name": "报表", "bullets": ["Python"]}]}
        jd = "后端工程师\n岗位要求：熟悉 Python，负责开发接口服务。"
        first = run_career_review(jd, profile)
        self.assertLessEqual(len(first["evidence_followup"]["questions"]), 3)
        question = first["evidence_followup"]["questions"][0]
        session = create_review_session(jd, profile, first)
        text = "负责使用 Python 开发报表工具，交付业务团队采用。"
        answers = {"answer_context": session["answer_context"], "evidence_answers": [{"question_id": question["question_id"], "target_path": "projects[0]", "answer": text}]}
        self.assertTrue(validate_session_answers(session, answers)[0])
        with self.assertRaisesRegex(ValueError, "question_id"):
            run_career_review(jd, profile, answers_dict={"evidence_answers": [{"question_id": [], "answer": text}]})
        result = run_career_review(jd, profile, answers_dict=answers, session_data=session)
        self.assertNotEqual(result["material_proposal"]["proposal_id"], first["material_proposal"]["proposal_id"])
        self.assertEqual(profile["projects"][0]["bullets"], ["Python"])
        self.assertNotIn(text, result["tailored_profile"]["projects"][0]["bullets"])
        proposal = MaterialProposal.from_dict(result["material_proposal"])
        applied = apply_material_proposal(proposal, profile, jd)
        self.assertIn(text, applied["projects"][0]["bullets"])
        resumed = run_career_review(jd, profile, session_data=create_review_session(jd, profile, result, session))
        self.assertEqual(resumed["evidence_followup"]["answers"], result["evidence_followup"]["answers"])
        self.assertEqual(len(resumed["material_proposal"]["patches"]), len(proposal.patches))
        self.assertEqual(resumed["material_proposal"]["proposal_id"], result["material_proposal"]["proposal_id"])
        with self.assertRaisesRegex(ValueError, "question_id"):
            run_career_review(jd, profile, answers_dict={"answer_context": session["answer_context"], "evidence_answers": [{"question_id": "foreign", "answer": text}]}, session_data=session)
        import tempfile
        from services.review_service import CareerReviewService
        from services.offer_service import ProposalService
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            jd_file = root / "jd.txt"
            source.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
            jd_file.write_text(jd, encoding="utf-8")
            db = root / "proposals.db"
            review_service = CareerReviewService()
            result["workflow"] = review_service.prepare_workflow(result, root, jd_file, source,
                session_path=root / "session.json", proposal_db=db)
            review_service.save_session(create_review_session(jd, profile, result), root / "session.json")
            # Corrupt templates must remain intact and name a concrete recovery step.
            answer_file = root / "answers.json"
            original_answers = answer_file.read_bytes()
            answer_file.write_text('{"answers":', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "answers.json.*JSON"):
                review_service.prepare_workflow(result, root, jd_file, source,
                    session_path=root / "session.json", proposal_db=db)
            self.assertEqual(answer_file.read_text(encoding="utf-8"), '{"answers":')
            answer_file.write_bytes(original_answers)
            original_source = source.read_bytes()
            with ProposalService(db) as service:
                service.save(MaterialProposal.from_dict(result["material_proposal"]))
                from unittest.mock import patch
                session_before = (root / "session.json").read_bytes()
                original_session = review_service.load_session(root / "session.json")
                proposal_before = service.get(result["material_proposal"]["proposal_id"]).to_dict()
                output_file = root / "approved-custom-name.json"
                output_file.write_bytes(b"existing output must survive rejection")
                output_before = output_file.read_bytes()
                for mismatch in ("database", "jd", "profile"):
                    with self.subTest(mismatch=mismatch):
                        wrong = copy.deepcopy(original_session)
                        if mismatch == "database":
                            wrong["workflow"]["proposal_db"] = str(root / "other.db")
                        else:
                            wrong[mismatch + "_fingerprint"] = "stale-version"
                        review_service.save_session(wrong, root / "session.json")
                        conflicting_bytes = (root / "session.json").read_bytes()
                        with patch("services.resume_service.ResumeService.build_resume") as render:
                            with self.assertRaisesRegex(ValueError, "指定会话.*不匹配"):
                                service.accept(result["material_proposal"]["proposal_id"], profile, jd,
                                               output_file, workspace=root, build_resume=True)
                            render.assert_not_called()
                        self.assertEqual(service.get(result["material_proposal"]["proposal_id"]).to_dict(), proposal_before)
                        self.assertEqual(output_file.read_bytes(), output_before)
                        self.assertEqual(source.read_bytes(), original_source)
                        self.assertEqual((root / "session.json").read_bytes(), conflicting_bytes)
                (root / "session.json").write_bytes(session_before)
                with patch.object(CareerReviewService, "save_session", side_effect=PermissionError("session locked")):
                    with self.assertRaises(PermissionError):
                        service.accept(result["material_proposal"]["proposal_id"], profile, jd,
                                       root / "approved-custom-name.json")
                self.assertEqual((root / "session.json").read_bytes(), session_before)
                self.assertNotEqual(service.get(result["material_proposal"]["proposal_id"]).applied_phase, "completed")
                for binding in ({"session_path": root / "missing-session.json"},
                                {"workspace": root / "missing-workspace"},
                                {"session_path": root}):
                    with self.subTest(binding=binding), self.assertRaisesRegex(FileNotFoundError, "会话文件"):
                        service.accept(result["material_proposal"]["proposal_id"],
                            json.loads((root / "approved-custom-name.json").read_text(encoding="utf-8")), jd,
                            root / "approved-custom-name.json", **binding)
                    self.assertNotEqual(service.get(result["material_proposal"]["proposal_id"]).applied_phase, "completed")
                    self.assertEqual((root / "session.json").read_bytes(), session_before)
                accepted = service.accept(result["material_proposal"]["proposal_id"],
                    json.loads((root / "approved-custom-name.json").read_text(encoding="utf-8")), jd,
                    root / "approved-custom-name.json")
            self.assertEqual(accepted["workflow"]["inputs"]["profile"], str((root / "approved-custom-name.json").resolve()))
            self.assertEqual(source.read_bytes(), original_source)
            activated = review_service.load_session(root / "session.json")
            activated["answers"] = [{"question_id": 1, "answer": "Preserve on retry"}]
            review_service.save_session(activated, root / "session.json")
            with ProposalService(db) as service:
                service.accept(result["material_proposal"]["proposal_id"],
                    json.loads((root / "approved-custom-name.json").read_text(encoding="utf-8")), jd,
                    root / "approved-custom-name.json")
            self.assertEqual(review_service.load_session(root / "session.json")["answers"], activated["answers"])
            activated["answers"] = []
            review_service.save_session(activated, root / "session.json")
            self.assertEqual(activated["answers"], [])
            self.assertFalse(any(activated["evidence_followup"].values()))
            self.assertNotIn("--answers", activated["workflow"]["next_command_args"])
            for goal in ("interview", "review"):
                resumed_cli = subprocess.run([sys.executable, str(PROJECT_ROOT / "cli.py"), "review", "--workspace", str(root),
                    "--goal", goal, "--json"], capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
                self.assertEqual(resumed_cli.returncode, 0, resumed_cli.stdout + resumed_cli.stderr)
                active = json.loads(resumed_cli.stdout)
                self.assertEqual(len(active["interview_questions"]), 3)
                self.assertTrue(all(text in q["question_zh"] for q in active["interview_questions"]))
                self.assertEqual(active["workflow"]["inputs"]["profile"], str((root / "approved-custom-name.json").resolve()))
                self.assertEqual(active["answers"], [])
            # Identical question IDs must not select a filled template from another material version.
            old_answers = json.dumps({"answers": [{"question_id": 1, "answer": "Previous material answer"}]})
            (root / "answers.json").write_text(old_answers, encoding="utf-8")
            approved_file = root / "approved-custom-name.json"
            previous_round = review_service.prepare_workflow(active, root, jd_file, approved_file,
                session_path=root / "session.json", proposal_db=db)
            Path(previous_round["answer_path"]).write_text(old_answers, encoding="utf-8")
            updated_profile = json.loads(approved_file.read_text(encoding="utf-8"))
            updated_profile["skills"] = ["Python", "SQL"]
            approved_file.write_text(json.dumps(updated_profile), encoding="utf-8")
            next_round = review_service.prepare_workflow(active, root, jd_file, approved_file,
                session_path=root / "session.json", proposal_db=db)
            self.assertNotEqual(previous_round["answer_path"], next_round["answer_path"])
            self.assertEqual(Path(previous_round["answer_path"]).read_text(encoding="utf-8"), old_answers)
            self.assertTrue(all(not answer["answer"] for answer in
                               json.loads(Path(next_round["answer_path"]).read_text(encoding="utf-8"))["answers"]))
            # Matching sessions still reject a changed artifact before activation.
            session_before_hash_error = (root / "session.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "已确认履历文件发生变化"):
                review_service.activate_accepted_profile(accepted, profile, jd, db, root)
            self.assertEqual((root / "session.json").read_bytes(), session_before_hash_error)
            unrelated = root / "unrelated"
            unrelated.mkdir()
            wrong_session = create_review_session(jd, profile, result)
            wrong_session["workflow"]["proposal_db"] = str(unrelated / "other.db")
            review_service.save_session(wrong_session, unrelated / "session.json")
            with self.assertRaisesRegex(ValueError, "指定会话.*不匹配"):
                review_service.activate_accepted_profile(accepted, profile, jd, db, unrelated)
            # An unrelated session discovered implicitly must not prevent standalone acceptance.
            implicit = {**accepted, "profile_output": str(unrelated / "approved.json")}
            self.assertIsNone(review_service.activate_accepted_profile(implicit, profile, jd, db))
            self.assertEqual(review_service.load_session(unrelated / "session.json")["workflow"]["inputs"]["profile"], str(source.resolve()))
            # Custom session and output locations are linked explicitly by the generated accept command.
            bound = root / "bound"
            custom_session = root / "custom-session.json"
            result["workflow"] = review_service.prepare_workflow(result, bound, jd_file, source,
                session_path=custom_session, proposal_db=db)
            review_service.save_session(create_review_session(jd, profile, result), custom_session)
            with ProposalService(db) as service:
                accepted = service.accept(result["material_proposal"]["proposal_id"], profile, jd,
                    root / "elsewhere" / "approved.json", workspace=bound, session_path=custom_session)
            command = accepted["workflow"]["next_command_args"]
            self.assertIn(str(custom_session.resolve()), command)
            resumed_cli = subprocess.run(command + ["--goal", "interview", "--json"],
                capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertEqual(resumed_cli.returncode, 0, resumed_cli.stdout + resumed_cli.stderr)
            self.assertEqual(json.loads(resumed_cli.stdout)["workflow"]["inputs"]["profile"],
                             str((root / "elsewhere" / "approved.json").resolve()))

    def test_relevance_order_requires_atomic_approval_and_preserves_source(self):
        from core.material_proposal import apply_material_proposal, create_material_proposal
        profile = {"candidate": {"name": "Synthetic"}, "projects": [{
            "bullets": ["维护内部文档。", "使用 Python 开发报表工具并交付业务采用。"],
        }]}
        original = copy.deepcopy(profile)
        advice = {"resume_advice": [{"requirement": "Python", "jd_requirement": {"importance": "must_have"}}]}
        tailored = generate_tailored_profile_from_review(advice, profile)
        proposal = create_material_proposal({"tailored_profile": tailored}, profile, "Python", "order")
        self.assertEqual(len(proposal.patches), 2)
        with self.assertRaisesRegex(ValueError, "整组"):
            proposal.accept(profile, "Python", [0])
        with self.assertRaisesRegex(ValueError, "整组"):
            apply_material_proposal(proposal, profile, "Python", [0])
        applied = apply_material_proposal(proposal, profile, "Python")
        self.assertEqual(applied["projects"][0]["bullets"], list(reversed(original["projects"][0]["bullets"])))
        self.assertEqual(profile, original)
        repeated = generate_tailored_profile_from_review(advice, applied)
        self.assertEqual(repeated["applied_patches"], [])

        for term, bullets, expected in (
            ("Go", ["Developed a Django service.", "Developed a Go service."], ["Developed a Go service.", "Developed a Django service."]),
            ("Go", ["Developed a Django service.", "Wrote documentation."], ["Developed a Django service.", "Wrote documentation."]),
            ("PyTorch", ["维护内部文档。", "使用 torch 开发模型。"], ["使用 torch 开发模型。", "维护内部文档。"]),
        ):
            with self.subTest(term=term, bullets=bullets):
                profile = {"projects": [{"bullets": bullets}]}
                ordered = generate_tailored_profile_from_review({"resume_advice": [
                    {"requirement": term, "jd_requirement": {"importance": "must_have"}}
                ]}, profile)
                self.assertEqual(ordered["projects"][0]["bullets"], expected)

    def test_grounded_polish_keeps_qualifications_and_combines_with_sorting(self):
        from core.job_flow import _polish_grounded_bullet
        from core.material_proposal import create_material_proposal, apply_material_proposal
        source = "在该项目中，协助团队使用 Python 开发报表工具，仅负责数据导出。"
        polished = "协助团队使用 Python 开发报表工具，仅负责数据导出。"
        self.assertEqual(_polish_grounded_bullet(source), polished)
        self.assertEqual(_polish_grounded_bullet("尚未独立主导，协助团队验证。"), "尚未独立主导，协助团队验证。")
        profile = {"candidate": {"name": "Synthetic"}, "projects": [{"bullets": ["维护内部文档。", source]}]}
        claims = iter_profile_claims(profile)
        decoded = JDDecoder().decode("后端工程师\n要求熟悉 Python，负责开发接口。")
        advice = generate_resume_advice(decoded, JDMatcher().match(decoded, build_candidate_profile(profile)), claims)
        rewritten = next(a for a in advice if a["action"] == "rewrite")
        self.assertEqual(rewritten["original_bullet"], source)
        self.assertEqual(rewritten["safe_bullet"], polished)
        self.assertEqual(rewritten["evidence_refs"][0]["excerpt"], source)
        tailored = generate_tailored_profile_from_review({"resume_advice": advice}, profile)
        proposal = create_material_proposal({"tailored_profile": tailored}, profile, "Python", "polish")
        self.assertTrue(proposal.patches)
        self.assertEqual({p["approval_group"] for p in proposal.patches}, {"reorder:projects[0]"})
        with self.assertRaisesRegex(ValueError, "整组"):
            apply_material_proposal(proposal, profile, "Python", [0])
        applied = apply_material_proposal(proposal, profile, "Python")
        self.assertEqual(applied["projects"][0]["bullets"], [polished, "维护内部文档。"])
        self.assertEqual(profile["projects"][0]["bullets"], ["维护内部文档。", source])
        full = run_career_review("后端工程师\n要求熟悉 Python，负责开发接口。", profile, goal="tailor")
        self.assertEqual(full["tailored_profile"]["projects"][0]["bullets"], [polished, "维护内部文档。"])
        self.assertTrue(all(p["validation_status"] == "pending_user_confirmation"
                            for p in full["material_proposal"]["patches"]))
        self.assertEqual(profile["projects"][0]["bullets"], ["维护内部文档。", source])

    def test_project_rewrite_still_rejects_unsupported_metrics(self):
        profile = {"candidate": {"name": "Synthetic"}, "projects": [
            {"bullets": ["Implemented parser."]},
        ]}
        advice = {"resume_advice": [{"action": "rewrite", "safe_bullet": "Reduced latency by 50%.",
                  "evidence_refs": [{"source_path": "projects[0].bullets[0]",
                                     "excerpt": "Implemented parser."}]}]}
        tailored = generate_tailored_profile_from_review(advice, profile)
        self.assertEqual(tailored["projects"][0]["bullets"], profile["projects"][0]["bullets"])
        self.assertEqual(tailored["applied_patches"][0]["validation_status"], "rejected")
        self.assertIn("fact_guard_rejected", tailored["applied_patches"][0]["reason"])


    def test_20_synthetic_sqlite_case_interview_and_resume(self):
        """
        Synthetic case required by acceptance criteria:
        JD: Python 后端实习生 (接口开发, SQL, 了解 Redis)
        Profile: 高校课程管理系统 (SQLite, 查询接口, 无 Redis, 无压测)
        Candidate Answer: "我负责查询接口，访问速度提升了 50%。"
        Expected:
        - 50% flagged as unverified (metric_drift diagnosis)
        - SQLite and query interface duties preserved
        - No hallucinated Redis or stress benchmarks injected
        - Conservative revision generated
        - Follow-up probe questions generated
        """
        jd = (
            "职位：Python 后端实习生\n"
            "职责：\n"
            "1. 负责核心业务 HTTP 查询接口开发与维护\n"
            "2. 编写高效 SQL 查询并配合 SQLite/MySQL 完成数据持久化\n"
            "3. 了解 Redis 缓存机制与常见应用场景\n"
        )
        profile = {
            "candidate": {
                "name": "张同学",
                "degree": "本科",
                "institution": "某大学",
                "major": "软件工程",
            },
            "skills": ["Python", "SQLite", "SQL"],
            "projects": [
                {
                    "name": "高校课程管理系统",
                    "role": "后端开发",
                    "bullets": [
                        "使用 Python 开发高校课程管理系统后端模块",
                        "使用 SQLite 设计并实现课程与选课数据表的 SQL 查询接口",
                    ],
                }
            ],
        }
        answers = {
            "answers": [
                {
                    "question_id": 1,
                    "answer": "我负责查询接口，访问速度提升了 50%。",
                }
            ]
        }
        res = run_career_review(jd, profile, answers_dict=answers)

        # 1. 3 targeted questions generated
        self.assertEqual(len(res["interview_questions"]), 3)

        # 2. Candidate answer diagnosed as metric_drift
        fb = res["answer_feedback"][0]
        self.assertEqual(fb["status"], "evaluated")
        self.assertEqual(fb["diagnosis"], "metric_drift")
        self.assertTrue(len(fb["follow_up_questions"]) > 0)
        self.assertIn("missing_elements", fb)

        # 3. Conservative revision generated, preserving interface duties without hallucinating Redis/benchmarks
        refined = fb["refined_answer"]
        self.assertNotIn("50%", refined)
        self.assertNotIn("Redis", refined)
        self.assertNotIn("QPS", refined)
        self.assertTrue("查询接口" in refined or "SQLite" in refined)
        self.assertTrue("缺乏基线" in refined or "不作主观量化" in refined)

        # 4. Resume advice grounded: Redis marked as unsupported / ask_user without safe_bullet
        redis_advice = next((a for a in res["resume_advice"] if "Redis" in a["requirement"]), None)
        if redis_advice:
            self.assertEqual(redis_advice["safe_bullet"], "")
            self.assertIn(redis_advice["action"], ["ask_user", "add_evidence"])

    def test_21_question_dimensions_grounding(self):
        """Verify the 3 questions correspond strictly to the 3 defined mainline dimensions."""
        res = run_career_review(self.jd_text, self.profile_data)
        qs = res["interview_questions"]
        self.assertEqual(len(qs), 3)

        # Q1: core_responsibility
        q1 = qs[0]
        self.assertEqual(q1["question_id"], 1)
        self.assertEqual(q1["target_dimension"], "core_responsibility")
        self.assertEqual(q1["dimension_name_cn"], "简历经历与个人贡献")
        self.assertEqual(q1["category_type"], "DEEP_DIVE")
        self.assertTrue(len(q1["requirement_name"]) > 0)
        self.assertGreaterEqual(len(q1["expected_elements"]), 4)

        # Q2: project_deep_dive
        q2 = qs[1]
        self.assertEqual(q2["question_id"], 2)
        self.assertEqual(q2["target_dimension"], "project_deep_dive")
        self.assertEqual(q2["dimension_name_cn"], "方案选择与问题解决")
        self.assertEqual(q2["category_type"], "DEEP_DIVE")
        self.assertTrue(len(q2["requirement_name"]) > 0)
        self.assertGreaterEqual(len(q2["expected_elements"]), 4)

        # Q3: gap_boundary
        q3 = qs[2]
        self.assertEqual(q3["question_id"], 3)
        self.assertEqual(q3["target_dimension"], "gap_boundary")
        self.assertEqual(q3["dimension_name_cn"], "结果依据与贡献边界")
        self.assertEqual(q3["category_type"], "DEEP_DIVE")
        self.assertTrue(len(q3["requirement_name"]) > 0)
        self.assertGreaterEqual(len(q3["expected_elements"]), 4)
        independent = run_career_review(self.jd_text, self.profile_data, goal="interview")
        self.assertEqual(qs, independent["interview_questions"])
        self.assertEqual(res["question_generation"]["strategy"], "resume_grounded_simulation")
        self.assertTrue(all(q["evidence_refs"] and not q["gap_refs"] for q in qs))
        from core.job_flow import _resume_interview_questions
        from core.profile_adapter import EvidenceClaim
        candidates = [
            EvidenceClaim("a", "projects[0].bullets[0]", "开发 API 接口并完成异常处理和上线验证", "project"),
            EvidenceClaim("duplicate", "projects[0].bullets[1]", "开发 API 接口并完成异常处理和上线验证", "project"),
            EvidenceClaim("same-entry", "projects[0].bullets[2]", "维护数据库索引并记录查询性能", "project"),
            EvidenceClaim("b", "projects[1].bullets[0]", "开展模型评测实验并记录不同方案的结果", "project"),
            EvidenceClaim("c", "experience[0].bullets[0]", "组织用户增长活动并记录转化率提升 20%", "experience"),
        ]
        diverse = _resume_interview_questions(candidates)
        self.assertEqual([q["evidence_claim_ids"] for q in diverse], [["a"], ["b"], ["c"]])
        self.assertIn("实验", diverse[1]["question_zh"])
        self.assertIn("观察周期", diverse[2]["question_zh"])
        self.assertIn("基线", diverse[2]["question_zh"])
        self.assertEqual(diverse, _resume_interview_questions(candidates))
        for claim, decision, verification in ((candidates[0], "故障", "运行记录"),
                                               (candidates[3], "实验", "复现"),
                                               (candidates[4], "目标用户", "观察周期")):
            with self.subTest(claim=claim.claim_id):
                single = _resume_interview_questions([claim])
                self.assertEqual(len(single), 3)
                self.assertEqual(len({q["question_zh"] for q in single}), 3)
                self.assertIn(decision, single[1]["question_zh"])
                self.assertIn(verification, single[2]["question_zh"])
                self.assertTrue(all(q["evidence_refs"][0]["excerpt"] == claim.text for q in single))
        self.assertEqual(_resume_interview_questions([]), [])
        legacy = create_review_session(self.jd_text, self.profile_data, res)
        legacy["question_strategy"] = "jd"
        legacy["answers"] = [{"question_id": 1, "answer": "Old answer must not be reused."}]
        migrated = run_career_review(self.jd_text, self.profile_data, goal="review", session_data=legacy)
        self.assertEqual(migrated["interview_questions"], qs)
        self.assertEqual(migrated["answers"], [])
        with self.assertRaisesRegex(ValueError, "刷新题目"):
            run_career_review(self.jd_text, self.profile_data, goal="review", session_data=legacy,
                              answers_dict={"answers": legacy["answers"]})

    def test_22_session_lifecycle_and_answer_validation(self):
        """Verify review session creation, atomic serialization, and answer validation."""
        import tempfile
        res = run_career_review(self.jd_text, self.profile_data)
        session = create_review_session(self.jd_text, self.profile_data, res)

        self.assertIn("session_id", session)
        self.assertEqual(session["schema_version"], "career-review-session.v1")
        self.assertEqual(session["status"], "awaiting_answer")
        self.assertEqual(len(session["questions_snapshot"]), 3)

        # Validate answers: valid question IDs pass
        valid_answers = {"answer_context": session["answer_context"], "answers": [{"question_id": 1, "answer": "回答内容"}]}
        is_valid, errors = validate_session_answers(session, valid_answers)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        for invalid_context in (None, "older-version"):
            with self.subTest(context=invalid_context):
                stale = {**valid_answers, "answer_context": invalid_context}
                self.assertFalse(validate_session_answers(session, stale)[0])
                with self.assertRaisesRegex(ValueError, "版本不匹配"):
                    run_career_review(self.jd_text, self.profile_data, answers_dict=stale, session_data=session)
                with self.assertRaisesRegex(ValueError, "版本不匹配"):
                    run_career_review(self.jd_text, self.profile_data, answers_dict=stale)
        legacy_session = {k: v for k, v in session.items() if k != "answer_context"}
        self.assertFalse(validate_session_answers(legacy_session, valid_answers)[0])
        refreshed = run_career_review(self.jd_text, self.profile_data, session_data=legacy_session)
        self.assertTrue(refreshed["answer_context"])

        # Nonexistent question ID fails validation
        invalid_answers = {"answers": [{"question_id": 99, "answer": "不存在的题目"}]}
        is_valid, errors = validate_session_answers(session, invalid_answers)
        self.assertFalse(is_valid)
        self.assertTrue(any("99" in e for e in errors))

        for field in ("answers", "evidence_answers"):
            for bad_id in ([], {}, None, True, 1.0):
                with self.subTest(field=field, bad_id=bad_id):
                    valid, errors = validate_session_answers(session, {
                        "answer_context": session["answer_context"],
                        field: [{"question_id": bad_id, "answer": "Invalid ID"}],
                    })
                    self.assertFalse(valid)
                    self.assertTrue(errors)

        # Save and load roundtrip
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "session.json"
            save_review_session(session, session_file)
            self.assertTrue(session_file.exists())

            loaded = load_review_session(session_file)
            self.assertEqual(loaded["session_id"], session["session_id"])
            self.assertEqual(len(loaded["questions_snapshot"]), 3)

    def test_23_cli_workspace_resumes_inputs_and_preserves_written_answers(self):
        """One directory manages the loop; explicit legacy session flags are covered below."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "review space"
            profile_path = Path(tmpdir) / "source.json"
            profile_path.write_text(json.dumps(self.profile_data, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, str(PROJECT_ROOT / "cli.py"), "review",
                       str(self.jd_path), "--profile", str(profile_path),
                       "--goal", "interview", "--workspace", str(workspace), "--json"]
            proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            first = json.loads(proc.stdout)
            self.assertTrue((workspace / "session.json").is_file())
            self.assertTrue((workspace / "proposals.db").is_file())
            self.assertEqual(json.loads((workspace / "review.json").read_text(encoding="utf-8")), first)
            answer_path = Path(first["workflow"]["answer_path"])
            answer = {**first["workflow"]["answer_template"], "answers": [{"question_id": 1, "answer": "我协助优化，吞吐提升 50%。"}]}
            answer_path.write_text(json.dumps(answer, ensure_ascii=False), encoding="utf-8")
            original = answer_path.read_bytes()
            command = [sys.executable, str(PROJECT_ROOT / "cli.py"), "review", "--workspace", str(workspace),
                       "--answers", str(answer_path), "--json"]
            proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            resumed = json.loads(proc.stdout)
            self.assertEqual(resumed["goal"], "interview")
            self.assertTrue(resumed["execution"]["resumed"])
            self.assertEqual(resumed["interview_questions"], first["interview_questions"])
            self.assertEqual(resumed["answers"], answer["answers"])
            self.assertEqual(answer_path.read_bytes(), original)
            self.assertNotEqual(resumed["workflow"]["answer_path"], str(answer_path))
            self.assertTrue(Path(resumed["workflow"]["answer_path"]).is_file())
            self.assertIn("--workspace", resumed["workflow"]["next_command"])
            self.assertIn("--answers", resumed["workflow"]["next_command"])
            session = json.loads((workspace / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(session["workflow"], resumed["workflow"])

            updated_profile = {"candidate": {"name": "Synthetic"}, "projects": [{"name": "Rust 工具", "bullets": [
                "使用 Rust 实现日志解析工具并交付团队使用。"]}]}
            profile_path.write_text(json.dumps(updated_profile, ensure_ascii=False), encoding="utf-8")
            refreshed = subprocess.run([sys.executable, str(PROJECT_ROOT / "cli.py"), "review", "--workspace", str(workspace), "--json"],
                                       capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertEqual(refreshed.returncode, 0, refreshed.stdout + refreshed.stderr)
            current = json.loads(refreshed.stdout)
            self.assertTrue(current["execution"]["sources_changed"])
            self.assertEqual(current["answers"], [])
            self.assertTrue(all("Rust" in q["question_zh"] for q in current["interview_questions"]))
            self.assertEqual(answer_path.read_bytes(), original)
            self.assertNotEqual(current["interview_questions"], first["interview_questions"])
            # Even after refresh, an explicitly selected old answer file must be rejected.
            before_reject = (workspace / "session.json").read_bytes()
            rejected = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("版本不匹配", json.loads(rejected.stdout)["message"])
            self.assertEqual((workspace / "session.json").read_bytes(), before_reject)
            current_answers = current["workflow"]["answer_template"]
            current_answers["answers"][0]["answer"] = "我实现了 Rust 日志解析工具。"
            Path(current["workflow"]["answer_path"]).write_text(json.dumps(current_answers), encoding="utf-8")
            accepted = subprocess.run(current["workflow"]["next_command_args"] + ["--json"],
                                      capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            # A JD is optional for resume-based simulation.
            resume_only = subprocess.run([sys.executable, str(PROJECT_ROOT / "cli.py"), "review", "--profile", str(profile_path),
                                          "--goal", "interview", "--json"], capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertEqual(resume_only.returncode, 0, resume_only.stdout + resume_only.stderr)
            self.assertEqual(len(json.loads(resume_only.stdout)["interview_questions"]), 3)
            session_path = workspace / "session.json"
            saved = json.loads(session_path.read_text(encoding="utf-8"))
            for malformed in ([], "invalid", {"inputs": []}, {"inputs": {"profile": 123}},
                              {"workspace": 123}, {"workspace": {}}, {"workspace": []}):
                with self.subTest(workflow=malformed):
                    session_path.write_text(json.dumps({**saved, "workflow": malformed}), encoding="utf-8")
                    failed = subprocess.run([sys.executable, str(PROJECT_ROOT / "cli.py"), "review", "--workspace", str(workspace), "--json"],
                                            capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertEqual(json.loads(failed.stdout)["error_type"], "invalid_input")
                    self.assertEqual(failed.stderr, "")
            session_path.write_text(json.dumps({**saved, "workflow": None}), encoding="utf-8")
            failed = subprocess.run([sys.executable, str(PROJECT_ROOT / "cli.py"), "review", "--workspace", str(workspace), "--json"],
                                    capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
            self.assertEqual(json.loads(failed.stdout)["error_type"], "invalid_input")
            self.assertNotIn("Traceback", failed.stderr)

    def test_24_session_multi_round_preserves_history(self):
        """Test that submitting Q1 in round 1 and Q2 in round 2 retains both answers and feedbacks."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Round 1: answer Q1
            ans1 = {"answers": [{"question_id": 1, "answer": "负责集群训练通信优化，从 40% 提升至 52%，测算口径为 H800 峰值。"}]}
            res1 = run_career_review(self.jd_text, self.profile_data, answers_dict=ans1)
            sess1 = create_review_session(self.jd_text, self.profile_data, res1)
            sess_path1 = Path(tmpdir) / "sess1.json"
            save_review_session(sess1, sess_path1)

            # Round 2: load sess1, answer Q2
            loaded_sess1 = load_review_session(sess_path1)
            ans2 = {"answer_context": loaded_sess1["answer_context"], "answers": [{"question_id": 2, "answer": "64B Dense 预训练 Baseline MFU 为 38%，负责 Megatron-LM Sequence Parallel，提升至 52%，测算口径为 H800 理论峰值。"}]}
            res2 = run_career_review(self.jd_text, self.profile_data, answers_dict=ans2, session_data=loaded_sess1)
            sess2 = create_review_session(self.jd_text, self.profile_data, res2, base_session=loaded_sess1)

            # Assertions
            # 1. Questions snapshot must be identical
            self.assertEqual(sess2["questions_snapshot"], sess1["questions_snapshot"])
            # 2. Both Q1 and Q2 answers must be present
            ans_map = {a["question_id"]: a["answer"] for a in sess2.get("answers", [])}
            self.assertIn(1, ans_map)
            self.assertIn(2, ans_map)
            # 3. Both Q1 and Q2 feedback must be evaluated
            fb_map = {f["question_id"]: f for f in sess2.get("answer_feedback", [])}
            self.assertEqual(fb_map[1]["status"], "evaluated")
            self.assertEqual(fb_map[2]["status"], "evaluated")
            # 4. Progress metrics
            self.assertTrue(sess2.get("minimum_loop_completed", False))
            self.assertGreaterEqual(sess2.get("evaluated_questions_count", 0), 2)
            blank_template = {"answer_context": sess2["answer_context"], "answers": [{"question_id": 1, "answer": ""}]}
            res3 = run_career_review(self.jd_text, self.profile_data, answers_dict=blank_template, session_data=sess2)
            self.assertEqual(res3["answers"], res2["answers"])
            self.assertEqual(res3["answer_feedback"], res2["answer_feedback"])

    def test_25_session_cli_validation_and_fingerprint_rejection(self):
        """CLI must exit non-zero and not overwrite session when answers are invalid or fingerprints mismatch."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sess_out = Path(tmpdir) / "session.json"
            cmd_init = [
                sys.executable, str(PROJECT_ROOT / "cli.py"), "review",
                str(self.jd_path), "--profile", str(self.profile_path),
                "--save-session", str(sess_out), "--json"
            ]
            subprocess.run(cmd_init, capture_output=True, check=True, cwd=str(PROJECT_ROOT))

            # Case A: invalid question_id (e.g. 999) must fail with non-zero exit code
            bad_ans_file = Path(tmpdir) / "bad_ans.json"
            with open(bad_ans_file, "w", encoding="utf-8") as f:
                json.dump({"answers": [{"question_id": 999, "answer": "invalid question answer"}]}, f)
            cmd_bad_ans = [
                sys.executable, str(PROJECT_ROOT / "cli.py"), "review",
                str(self.jd_path), "--profile", str(self.profile_path),
                "--session", str(sess_out), "--answers", str(bad_ans_file), "--json"
            ]
            proc_bad = subprocess.run(cmd_bad_ans, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT))
            self.assertNotEqual(proc_bad.returncode, 0, "CLI must reject unknown question_id with non-zero exit code")
            self.assertEqual(proc_bad.stderr, "")
            self.assertEqual(json.loads(proc_bad.stdout)["error_type"], "invalid_answers")
            self.assertIn("question_id_999_not_in_session_snapshot", json.loads(proc_bad.stdout)["message"])

            # Case B: mismatched JD with old session must fail
            other_jd_file = Path(tmpdir) / "other_jd.txt"
            other_jd_file.write_text("【岗位】新媒体运营专员\n职责：内容创作与用户运营", encoding="utf-8")
            cmd_mismatch = [
                sys.executable, str(PROJECT_ROOT / "cli.py"), "review",
                str(other_jd_file), "--profile", str(self.profile_path),
                "--session", str(sess_out), "--json"
            ]
            proc_mismatch = subprocess.run(cmd_mismatch, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT))
            self.assertNotEqual(proc_mismatch.returncode, 0, "CLI must reject mismatched JD fingerprint with non-zero exit code")
            self.assertEqual(proc_mismatch.stderr, "")
            self.assertEqual(json.loads(proc_mismatch.stdout)["error_type"], "session_conflict")

    def test_26_targeted_questions_role_adaptation_and_no_name_as_project(self):
        """Test Q1 adapts to non-engineering roles and Q2 does not quote candidate name/degree as project."""
        from core.jd_analyst.decoder import JDDecoder
        from core.jd_analyst.matcher import JDMatcher
        from core.jd_analyst.predictor import JDPredictor
        from core.profile_adapter import build_profile_context
        from core.job_flow import select_targeted_interview_questions

        # Scenario A: Operations role should not ask about architecture/high-concurrency/QPS
        ops_jd = "【岗位名称】新媒体运营专员\n【岗位职责】1. 负责微信公众号与小红书内容策划、撰写与排版；2. 负责粉丝社群日常运营与裂变增长。"
        ops_profile = {
            "candidate": {"name": "王小花", "degree": "本科", "institution": "中国传媒大学"},
            "experience": [
                {"title": "新媒体运营实习生", "company": "某互联网公司", "bullets": ["负责公众号推文策划，月均阅读量提升 30%。"]}
            ]
        }
        dec = JDDecoder().decode(ops_jd)
        ctx = build_profile_context(ops_profile)
        p_canon = ctx.get_canonical_profile()
        matcher_res = JDMatcher().match(dec, p_canon)
        pred = JDPredictor()
        qs = select_targeted_interview_questions(dec, p_canon, list(ctx.claims), matcher_res, pred)

        q1 = qs[0]
        self.assertNotIn("架构设计", q1["question_zh"], "Operations role Q1 should not mention architecture design")
        self.assertNotIn("高并发", q1["question_zh"], "Operations role Q1 should not mention high concurrency")

        from core.jd_analyst.models import CoreResponsibility, CoreSkill, GapItem, GapState
        dec.core_responsibilities = [CoreResponsibility("辅助", "整理周报", "general", 0.1),
                                    CoreResponsibility("核心", "内容增长策略", "general", 2.0)]
        matcher_res.gap_matrix = [
            GapItem("技能-辅助", "skill", "nice_to_have", GapState.REAL_GAP, 0, "", "", ""),
            GapItem("技能-内容增长", "skill", "must_have", GapState.INSUFFICIENT_EVIDENCE, 0, "", "", ""),
        ]
        ranked = select_targeted_interview_questions(dec, p_canon, list(ctx.claims), matcher_res, pred)
        self.assertEqual(ranked[0]["requirement_name"], "内容增长策略")
        self.assertEqual(ranked[2]["requirement_name"], "技能-内容增长")
        dec.core_responsibilities = []
        dec.core_skills = [CoreSkill("H100", "hardware", "nice_to_have", "general"),
                           CoreSkill("Python", "language", "must_have", "general")]
        ranked = select_targeted_interview_questions(dec, p_canon, list(ctx.claims), matcher_res, pred)
        self.assertEqual(ranked[0]["requirement_name"], "Python")

        # Scenario B: Profile with only candidate info (no experience/project) must NOT use name/degree in Q2
        empty_exp_profile = {
            "candidate": {"name": "张无忌", "degree": "硕士", "institution": "明教大学"}
        }
        ctx_empty = build_profile_context(empty_exp_profile)
        p_empty = ctx_empty.get_canonical_profile()
        m_empty = JDMatcher().match(dec, p_empty)
        qs_empty = select_targeted_interview_questions(dec, p_empty, list(ctx_empty.claims), m_empty, pred)

        q2 = qs_empty[1]
        self.assertNotIn("张无忌", q2["question_zh"], "Q2 must not quote candidate name as project anchor")
        self.assertNotIn("硕士", q2["question_zh"], "Q2 must not quote candidate degree as project anchor")
        self.assertNotIn("明教大学", q2["question_zh"], "Q2 must not quote candidate institution as project anchor")

        # Scenario C: Short real experience (15 chars) should be anchored, not ignored
        short_exp_profile = {
            "candidate": {"name": "赵敏"},
            "experience": [
                {"title": "助理", "bullets": ["搭建SQLite测试库与索引优化。"]}
            ]
        }
        ctx_short = build_profile_context(short_exp_profile)
        p_short = ctx_short.get_canonical_profile()
        m_short = JDMatcher().match(dec, p_short)
        qs_short = select_targeted_interview_questions(dec, p_short, list(ctx_short.claims), m_short, pred)
        q2_short = qs_short[1]
        self.assertIn("SQLite", q2_short["question_zh"], "Short real experience should be anchored in Q2")

    def test_27_evidence_graph_is_integrated_into_review_and_snapshot(self):
        result = run_career_review(self.jd_text, self.profile_data)

        self.assertIn("evidence_graph", result)
        self.assertIn("evidence_gate", result)
        self.assertIn("evidence_snapshot", result)
        self.assertTrue(result["evidence_gate"]["is_ready"])
        self.assertEqual(
            result["evidence_snapshot"]["evidence_graph"]["graph_hash"],
            result["evidence_graph"]["graph_hash"],
        )
        self.assertTrue(result["evidence_gate"]["selected_claim_ids"])
        self.assertTrue(
            all(
                patch.get("validation_status") != "applied"
                or patch.get("source_claim_id") in result["evidence_gate"]["selected_claim_ids"]
                for patch in result["tailored_profile"].get("applied_patches", [])
            )
        )


if __name__ == "__main__":
    unittest.main()


