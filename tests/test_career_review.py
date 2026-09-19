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

import html
import json
import os
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
)
from core.fact_guard import FactVerificationGuard
from core.profile_adapter import iter_profile_claims
from modules.jd_analyst.decoder import JDDecoder
from modules.jd_analyst.matcher import JDMatcher
from modules.jd_analyst.reporter import OfferStrategyReporter
from modules.jd_analyst.predictor import JDPredictor


class TestCareerReviewPipeline(unittest.TestCase):

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

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

    def test_02_awaiting_answer_status_when_no_answers(self):
        """When no answers_dict is passed, all 3 questions report awaiting_answer."""
        res = run_career_review(self.jd_text, self.profile_data)
        self.assertEqual(len(res["answer_feedback"]), 3)
        for fb in res["answer_feedback"]:
            self.assertEqual(fb["status"], "awaiting_answer")
            self.assertEqual(fb["diagnosis"], "not_submitted")
            self.assertEqual(fb["candidate_answer"], "")

    def test_03_answer_feedback_with_metric_drift(self):
        """Diagnose metric_drift when answer claims quantified gain without baseline."""
        answers = {
            "answers": [
                {"question_id": 1, "answer": "通过优化，我们将模型推理吞吐提升 50%，显存降低 30%。"},
                {"question_id": 2, "answer": "基线是 2.4h，我们基于 NCCL 心跳探针压减到 8min。"}
            ]
        }
        res = run_career_review(self.jd_text, self.profile_data, answers_dict=answers)
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
        self.assertNotIn("但我深入实践过与之底层相通的架构", q1_fb.get("refined_answer", ""))
        self.assertIn("未在实际项目中主导过", q1_fb.get("refined_answer", ""))

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
        from modules.jd_analyst.models import RedFlagReport
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

    def test_10_listing_age_is_exposed_as_heuristic(self):
        result = run_career_review(self.jd_text, self.profile_data, listing_age_days=90)
        self.assertEqual(result["match_summary"]["prediction"]["listing_age_days"], 90)
        self.assertIn("启发式", result["match_summary"]["prediction_note"])

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
        self.assertEqual(len(data["interview_questions"]), 3)

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

    def test_17_career_review_build_resume_e2e(self):
        """Test run_career_review with build_resume=True end-to-end closed loop."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "resumes"
            res = run_career_review(
                self.jd_text,
                self.profile_data,
                build_resume=True,
                resume_output_dir=out_dir,
                resume_theme="modern-navy",
                reserve_photo=True,
            )
            # 1. Verify generated_resumes structure and PDF file
            self.assertIn("generated_resumes", res)
            self.assertIn("tailored_profile", res)

            gen = res["generated_resumes"]
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

        # Case B: Grounded metric (preserving 20%) succeeds and is applied
        grounded_review = {
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
        tailored_grounded = generate_tailored_profile_from_review(grounded_review, base)
        bullets_grounded = tailored_grounded["experience"][0]["bullets"]
        self.assertTrue(any("Megatron-LM" in b for b in bullets_grounded))
        self.assertTrue(any("20%" in b for b in bullets_grounded))
        self.assertNotIn("幻觉技能", " ".join(bullets_grounded))
        patches_grounded = tailored_grounded.get("applied_patches", [])
        applied_patch = next(p for p in patches_grounded if p["validation_status"] == "applied")
        self.assertEqual(applied_patch["target_path"], "experience[0].bullets[0]")

        # Case C: Re-application is idempotent (already_applied, no duplicate bullets)
        tailored_reapplied = generate_tailored_profile_from_review(grounded_review, tailored_grounded)
        self.assertEqual(len(tailored_reapplied["experience"][0]["bullets"]), 1)
        patches_reapplied = tailored_reapplied.get("applied_patches", [])
        reapplied_patch = next(p for p in patches_reapplied if p["source_claim_id"] == "Megatron-LM")
        self.assertEqual(reapplied_patch["validation_status"], "already_applied")

        # Photo reservation and bridged candidate fields
        self.assertTrue(tailored_grounded["candidate"]["reserve_photo"])
        self.assertEqual(tailored_grounded["candidate"]["school"], "上海交通大学")
        self.assertEqual(tailored_grounded["candidate"]["title"], "大模型算法工程师")

    def test_19_career_review_default_build_resume(self):
        """Test run_career_review with default build_resume=True parameters."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "default_resumes"
            res = run_career_review(self.jd_text, self.profile_data, build_resume=True, resume_output_dir=out_dir)
            self.assertIn("generated_resumes", res)
            pdf_path = Path(res["generated_resumes"]["pdf"])
            self.assertTrue(pdf_path.exists())
            self.assertTrue(pdf_path.stat().st_size > 0)
            self.assertEqual(res["generated_resumes"]["theme"], "modern-navy")

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


if __name__ == "__main__":
    unittest.main()

