"""
Comprehensive Unit Test Suite for OfferGet ATS Auditor Module.
Tests 4 Dimensions, Three-State Skill Ledger, Anti-AI Detector, Visibility Filter, and Edge Cases.
"""

import copy
import json
import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ats_checker import (
    ATSAuditor,
    audit_resume_ats,
    generate_skill_ledger,
    filter_profile_by_visibility,
    extract_bullets_from_input,
    is_bullet_quantified,
    find_action_verbs
)
from core.jd_compat import decode_jd


class TestATSAuditor(unittest.TestCase):

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        self.jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"

        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        with open(self.jd_path, "r", encoding="utf-8") as f:
            self.jd_text = f.read()

        self.decoded_jd = decode_jd(self.jd_text)
        self.auditor = ATSAuditor()

    # =======================================================================
    # 1. Dimension 1: Impact
    # =======================================================================

    def test_dim1_high_quantified_ratio_and_strong_verbs(self):
        bullets = [
            "Architected 1024-card H800 GPU cluster pre-training pipeline, improving MFU from 38.5% to 54.2%.",
            "Spearheaded automated straggler isolation system, slashing downtime from 2.4h to 8min with 99.4% uptime.",
            "Built custom vLLM inference engine with FP8 quantization, saving 38M RMB annually and cutting P99 latency by 45%.",
            "主导 230B MoE 基座大模型预训练，将单步训练耗时缩短 33%，提前 3 周完成训练交付。",
            "攻坚长文本注意力调度，首字延迟 (TTFT) 从 1.8s 下降至 320ms。"
        ]
        res = self.auditor.audit_impact(bullets)
        self.assertGreaterEqual(res["score"], 8.0)
        self.assertGreaterEqual(res["quantified_ratio"], 0.80)
        self.assertTrue(res["aim_met"])
        self.assertEqual(res["quantified_count"], 5)
        self.assertGreater(res["strong_verbs_count"], 0)
        self.assertEqual(res["weak_verbs_count"], 0)

    def test_dim1_low_quantified_ratio(self):
        bullets = [
            "Responsible for building deep learning models.",
            "Worked on data preprocessing and model evaluation.",
            "Assisted in daily code reviews and team meetings."
        ]
        res = self.auditor.audit_impact(bullets)
        self.assertFalse(res["aim_met"])
        self.assertEqual(res["quantified_count"], 0)
        self.assertEqual(res["quantified_ratio"], 0.0)
        self.assertLess(res["score"], 4.0)

    def test_dim1_weak_verbs_penalized(self):
        bullets_weak = [
            "Responsible for training 64B models with 50% speedup.",
            "Assisted in reducing P99 latency by 30% for 1000 users.",
            "负责优化分布式并行架构，提升 20% 吞吐量。",
            "参与模型量化调研，显存降低 40%。"
        ]
        res = self.auditor.audit_impact(bullets_weak)
        self.assertGreater(res["weak_verbs_count"], 0)
        self.assertIn("responsible for", [v.lower() for v in res["weak_verbs_found"]])
        self.assertIn("负责", res["weak_verbs_found"])
        self.assertTrue(any("Replace weak verbs" in f for f in res["feedback"]))

    def test_dim1_empty_bullets(self):
        res = self.auditor.audit_impact([])
        self.assertEqual(res["score"], 0.0)
        self.assertEqual(res["total_bullets"], 0)
        self.assertFalse(res["aim_met"])

    # =======================================================================
    # 2. Dimension 2: ATS Readiness
    # =======================================================================

    def test_dim2_standard_sections_detected(self):
        text = """
# Summary
Experienced AI Architect with 7 years track record.

# Experience
Senior Staff Architect at Frontier AI Lab.
- Built distributed training framework on 1024 GPUs.

# Education
Ph.D. in Computer Science, Tsinghua University.

# Skills
Python, CUDA, C++, PyTorch, Megatron-LM.

# Projects
Enterprise-Agent-OS: Open-source MCP multi-agent platform.
"""
        res = self.auditor.audit_ats_readiness(text, text)
        self.assertEqual(len(res["detected_sections"]), 5)
        self.assertEqual(len(res["missing_sections"]), 0)
        self.assertGreaterEqual(res["score"], 8.0)

    def test_dim2_missing_sections_detected(self):
        text = """
# Experience
Software Engineer at Acme Corp.

# Projects
Built an internal dashboard.
"""
        res = self.auditor.audit_ats_readiness(text, text)
        self.assertIn("Education", res["missing_sections"])
        self.assertIn("Skills", res["missing_sections"])
        self.assertIn("Summary", res["missing_sections"])
        self.assertLess(res["score"], 6.0)

    def test_dim2_formatting_risks_detected(self):
        # Text with table, multi-column CSS, and non-standard symbols
        risky_html = """
<div style="display: flex; column-count: 2;">
  <div class="two-column">
    <table><tr><td>Skills</td><td>★ Megatron-LM</td></tr></table>
  </div>
</div>
"""
        res = self.auditor.audit_ats_readiness(risky_html, risky_html)
        detected_risks = [r["risk"] for r in res["formatting_risks"]]
        self.assertIn("table", detected_risks)
        self.assertIn("multi_column", detected_risks)
        self.assertIn("non_standard_symbols", detected_risks)
        self.assertLess(res["score"], 6.0)

    def test_dim2_keyword_stuffing_detected(self):
        # Repetitive keyword abuse
        stuffed_text = """
Python Python Python Python Python Python Python Python Python Python
Deep learning engineer with Python Python Python Python Python.
"""
        res = self.auditor.audit_ats_readiness(stuffed_text, stuffed_text)
        self.assertTrue(res["keyword_stuffing_detected"])
        self.assertGreater(len(res["stuffing_warnings"]), 0)

    def test_dim2_hidden_text_detected(self):
        hidden_text = """
<div style="color: white; font-size: 0px; display: none;">
python pytorch cuda deep learning transformer
</div>
"""
        res = self.auditor.audit_ats_readiness(hidden_text, hidden_text)
        self.assertTrue(res["keyword_stuffing_detected"])
        self.assertTrue(any("Hidden text" in w for w in res["stuffing_warnings"]))

    # =======================================================================
    # 3. Dimension 3: Clarity & Anti-AI
    # =======================================================================

    def test_dim3_ai_buzzwords_detected(self):
        slop_text = "Results-driven tech leader with proven track record and dynamic synergy, 具有深厚底蕴，致力于全面赋能业务。"
        bullets = [slop_text]
        res = self.auditor.audit_clarity_anti_ai(bullets, slop_text)
        self.assertGreaterEqual(res["buzzword_count"], 4)
        self.assertIn("results-driven", res["ai_buzzwords_detected"])
        self.assertIn("dynamic", res["ai_buzzwords_detected"])
        self.assertIn("具有深厚底蕴", res["ai_buzzwords_detected"])
        self.assertIn("全面赋能", res["ai_buzzwords_detected"])
        self.assertLess(res["score"], 6.0)

    def test_dim3_8_second_skim_test_pass(self):
        short_bullets = [
            "Pioneered FP8 vLLM inference engine, reducing token cost by 62% and P99 latency by 45%.",
            "Authored 230B MoE pre-training with 54.2% MFU across 1,024 GPUs.",
            "主导万卡慢节点秒级自动剔除系统，训练可用率达 99.4%。"
        ]
        full_text = "\n".join(short_bullets)
        res = self.auditor.audit_clarity_anti_ai(short_bullets, full_text)
        self.assertEqual(res["skim_pass_ratio"], 1.0)
        self.assertEqual(len(res["long_bullets"]), 0)
        self.assertGreaterEqual(res["score"], 8.0)

    def test_dim3_8_second_skim_test_fail_overlong(self):
        long_bullet = (
            "This is an excessively long and verbose bullet point that stretches on across multiple lines without "
            "focus, packing in run-on clauses, descriptive narratives, historical backstories, multiple sub-projects, "
            "and unnecessary qualifications that recruiters and ATS systems cannot scan within 8 seconds threshold."
        )
        self.assertGreater(len(long_bullet), 150)
        bullets = [long_bullet]
        res = self.auditor.audit_clarity_anti_ai(bullets, long_bullet)
        self.assertEqual(res["skim_pass_ratio"], 0.0)
        self.assertEqual(len(res["long_bullets"]), 1)
        self.assertEqual(res["long_bullets"][0]["length"], len(long_bullet))

    # =======================================================================
    # 4. Dimension 4: Format & Alignment
    # =======================================================================

    def test_dim4_less_than_10_years_one_page_alignment(self):
        # 7 years experience on 1 page
        raw_text = "Name: Alex Zhang\nEmail: alex@example.com\nPhone: +86 186-0000-8899\nSummary: 7 years exp."
        bullets = ["Bullet 1", "Bullet 2"]
        res = self.auditor.audit_format_alignment(
            years_of_experience=7,
            bullets=bullets,
            raw_text=raw_text,
            explicit_page_count=1
        )
        self.assertEqual(res["recommended_pages"], 1)
        self.assertEqual(res["estimated_pages"], 1)
        self.assertTrue(res["page_fit"])
        self.assertTrue(res["has_email"])
        self.assertTrue(res["has_phone"])
        self.assertEqual(res["score"], 10.0)

    def test_dim4_less_than_10_years_multi_page_penalized(self):
        # 5 years experience on 3 pages
        raw_text = "Email: alex@example.com\nPhone: +86 186-0000-8899"
        res = self.auditor.audit_format_alignment(
            years_of_experience=5,
            bullets=["B"] * 25,
            raw_text=raw_text,
            explicit_page_count=3
        )
        self.assertEqual(res["recommended_pages"], 1)
        self.assertEqual(res["estimated_pages"], 3)
        self.assertFalse(res["page_fit"])
        self.assertLess(res["score"], 5.0)

    def test_dim4_senior_10_plus_years_two_pages(self):
        raw_text = "Email: exec@example.com\nPhone: +1 555-0199-000"
        res = self.auditor.audit_format_alignment(
            years_of_experience=12,
            bullets=["B"] * 14,
            raw_text=raw_text,
            explicit_page_count=2
        )
        self.assertEqual(res["recommended_pages"], 2)
        self.assertEqual(res["estimated_pages"], 2)
        self.assertTrue(res["page_fit"])
        self.assertEqual(res["score"], 10.0)

    def test_dim4_missing_contact_info(self):
        raw_text = "Candidate Name without email or phone numbers"
        res = self.auditor.audit_format_alignment(
            years_of_experience=4,
            bullets=["B1"],
            raw_text=raw_text,
            explicit_page_count=1
        )
        self.assertFalse(res["has_email"])
        self.assertFalse(res["has_phone"])
        self.assertLess(res["score"], 8.0)

    # =======================================================================
    # 5. Three-State Skill Ledger
    # =======================================================================

    def test_skill_ledger_three_states(self):
        # Profile contains:
        # - Megatron-LM (in competencies AND experience highlights) -> present
        # - RingAttention (in competencies BUT NOT in experience highlights) -> missing
        # - JD requires Kubernetes / Rust (NOT in competencies) -> unsupported_gap
        test_skills = ["Megatron-LM", "RingAttention", "Rust", "Kubernetes"]
        ledger = generate_skill_ledger(
            profile_data=self.profile_data,
            jd_decoded_or_text=None,
            skills_to_evaluate=test_skills
        )

        present_skills = [p["skill"] for p in ledger["present"]]
        missing_skills = [m["skill"] for m in ledger["missing"]]
        gap_skills = [g["skill"] for g in ledger["unsupported_gap"]]

        # Megatron-LM is backed by EXP-01 and Fast-Megatron-MLA
        self.assertIn("Megatron-LM", present_skills)

        # RingAttention is in competencies.algorithms but no highlight explicitly mentions it
        self.assertIn("RingAttention", missing_skills)

        # Rust and Kubernetes are not in candidate competencies
        self.assertIn("Rust", gap_skills)
        self.assertIn("Kubernetes", gap_skills)

        # Verify interview defense advice and anti-hallucination warning for gaps
        for gap in ledger["unsupported_gap"]:
            self.assertIn("interview_defense", gap)
            self.assertIn("anti_hallucination_rule", gap)
            self.assertTrue(len(gap["interview_defense"]) > 20)

        # Verify summary counts
        summary = ledger["summary"]
        self.assertEqual(summary["present_count"], len(present_skills))
        self.assertEqual(summary["missing_count"], len(missing_skills))
        self.assertEqual(summary["unsupported_gap_count"], len(gap_skills))
        self.assertEqual(summary["total_evaluated"], 4)

    # =======================================================================
    # 6. Visibility System
    # =======================================================================

    def test_visibility_filtering(self):
        # Profile has:
        # Exp 1: ["always", "ai_pretrain", "cluster_infra"]
        # Exp 2: ["always", "inference_serving"]
        # Proj 1: ["agentic_systems", "enterprise_rag"]
        # Proj 2: ["always", "ai_pretrain", "inference_serving"]

        # Tag: 'ai_pretrain' -> Proj 1 should be filtered out
        filtered_pretrain = filter_profile_by_visibility(self.profile_data, "ai_pretrain")
        exp_names_pretrain = [e["company"] for e in filtered_pretrain["experience"]]
        proj_names_pretrain = [p["name"] for p in filtered_pretrain["projects"]]

        self.assertEqual(len(exp_names_pretrain), 2)  # Both exps have 'always'
        self.assertEqual(len(proj_names_pretrain), 1)
        self.assertIn("Fast-Megatron-MLA", proj_names_pretrain[0])

        # Tag: 'agentic_systems' -> Proj 1 and Proj 2 both preserved
        filtered_agent = filter_profile_by_visibility(self.profile_data, "agentic_systems")
        proj_names_agent = [p["name"] for p in filtered_agent["projects"]]
        self.assertEqual(len(proj_names_agent), 2)

        # Tag: None or '*' -> all preserved
        filtered_all = filter_profile_by_visibility(self.profile_data, "*")
        self.assertEqual(len(filtered_all["projects"]), 2)

    def test_visibility_immutability(self):
        original_proj_count = len(self.profile_data["projects"])
        filtered = filter_profile_by_visibility(self.profile_data, "cluster_infra")
        # Ensure original profile was not modified in-place
        self.assertEqual(len(self.profile_data["projects"]), original_proj_count)
        self.assertIsNot(filtered, self.profile_data)

    # =======================================================================
    # 7. Overall Scorer & Verdict
    # =======================================================================

    def test_audit_resume_ats_candidate_profile_ready_to_send(self):
        # Run audit on standard candidate profile and JD
        result = audit_resume_ats(
            profile_or_text=self.profile_data,
            jd_decoded_or_text=self.decoded_jd,
            target_tag="always"
        )

        self.assertIn("overall_score", result)
        self.assertIn("verdict", result)
        self.assertIn("dimensions", result)
        self.assertIn("skill_ledger", result)
        self.assertIn("recommendations", result)

        # The gold standard candidate profile should easily achieve READY_TO_SEND
        self.assertGreaterEqual(result["overall_score"], 75.0)
        self.assertEqual(result["verdict"], "READY_TO_SEND")
        self.assertEqual(len(result["critical_issues"]), 0)

    def test_audit_resume_ats_needs_revision_when_critical_issues_exist(self):
        # Low quality profile with severe defects
        bad_profile = {
            "candidate": {
                "name": "Jane Doe",
                "years_of_experience": 2
            },
            "experience": [
                {
                    "company": "Company A",
                    "highlights": [
                        "Responsible for assisting in tasks.",
                        "Participated in team activities."
                    ]
                }
            ]
        }
        result = audit_resume_ats(
            profile_or_text=bad_profile,
            jd_decoded_or_text=self.decoded_jd
        )
        self.assertEqual(result["verdict"], "NEEDS_REVISION")
        self.assertGreater(len(result["critical_issues"]), 0)
        self.assertLess(result["overall_score"], 75.0)

    # =======================================================================
    # 8. Edge Cases & Formats
    # =======================================================================

    def test_audit_from_file_path(self):
        result = audit_resume_ats(
            profile_or_text=str(self.profile_path),
            jd_decoded_or_text=str(self.jd_path)
        )
        self.assertEqual(result["verdict"], "READY_TO_SEND")
        self.assertGreaterEqual(result["overall_score"], 75.0)

    def test_audit_from_plain_text(self):
        resume_text = """
John Doe
john.doe@example.com | +1 555-0123-4567

Summary
Senior Software Engineer with 6 years experience.

Experience
Acme Corporation - Senior Engineer (2021 - Present)
- Engineered high-throughput microservices handling 50,000 QPS with 99.99% availability.
- Shipped automated CI/CD pipeline, reducing deployment cycles by 65%.
- Optimized PostgreSQL indexing, slashing query latency by 40%.

Education
B.S. in Computer Science, State University

Skills
Python, Go, PostgreSQL, Docker, AWS, Distributed Systems

Projects
CloudMonitor: Real-time telemetry monitoring platform.
"""
        result = audit_resume_ats(
            profile_or_text=resume_text,
            jd_decoded_or_text="Looking for a Python and Go software engineer with distributed systems and PostgreSQL experience."
        )
        self.assertEqual(result["verdict"], "READY_TO_SEND")
        self.assertGreaterEqual(result["overall_score"], 75.0)

    # =======================================================================
    # 9. ProfileContext & ProfileEvidenceIndex Integration (M1-A)
    # =======================================================================

    def test_audit_profile_context_parity_and_zero_redundant_index(self):
        from unittest.mock import patch
        from core.profile_adapter import build_profile_context, build_profile_evidence_index, ProfileContext

        # 1. Build ProfileContext
        ctx = build_profile_context(self.profile_data)
        self.assertIsInstance(ctx, ProfileContext)

        # 2. Audit raw dict vs ProfileContext
        with patch("core.ats_checker.build_profile_evidence_index", wraps=build_profile_evidence_index) as mock_build_raw:
            res_dict = self.auditor.audit(self.profile_data, self.decoded_jd)
            # Raw dict should call build_profile_evidence_index exactly 1 time (in extract_bullets_from_input)
            self.assertEqual(mock_build_raw.call_count, 1)

        with patch("core.ats_checker.build_profile_evidence_index", wraps=build_profile_evidence_index) as mock_build_ctx:
            res_ctx = self.auditor.audit(ctx, self.decoded_jd)
            # Existing ProfileContext must NOT call build_profile_evidence_index at all (0 times)
            self.assertEqual(mock_build_ctx.call_count, 0)

        # 3. Parity assertions: overall_score, verdict, dimensions, skill_ledger counts
        self.assertEqual(res_dict["overall_score"], res_ctx["overall_score"])
        self.assertEqual(res_dict["verdict"], res_ctx["verdict"])
        self.assertEqual(res_dict["dimensions"]["impact"]["score"], res_ctx["dimensions"]["impact"]["score"])
        self.assertEqual(res_dict["dimensions"]["ats_readiness"]["score"], res_ctx["dimensions"]["ats_readiness"]["score"])
        self.assertEqual(res_dict["dimensions"]["clarity_anti_ai"]["score"], res_ctx["dimensions"]["clarity_anti_ai"]["score"])
        self.assertEqual(res_dict["dimensions"]["format_alignment"]["score"], res_ctx["dimensions"]["format_alignment"]["score"])
        self.assertEqual(len(res_dict["skill_ledger"]["present"]), len(res_ctx["skill_ledger"]["present"]))
        self.assertEqual(len(res_dict["skill_ledger"]["missing"]), len(res_ctx["skill_ledger"]["missing"]))
        self.assertEqual(len(res_dict["skill_ledger"]["unsupported_gap"]), len(res_ctx["skill_ledger"]["unsupported_gap"]))

        # 4. Assert ProfileContext was not converted to string representation
        bullets, meta = extract_bullets_from_input(ctx)
        self.assertFalse(meta["raw_text"].startswith("ProfileContext("))
        self.assertTrue(meta["is_dict"])
        self.assertIsNotNone(meta["evidence_index"])

    def test_audit_profile_evidence_index_directly(self):
        from unittest.mock import patch
        from core.profile_adapter import build_profile_evidence_index

        index = build_profile_evidence_index(self.profile_data)
        with patch("core.ats_checker.build_profile_evidence_index", wraps=build_profile_evidence_index) as mock_build:
            res_idx = self.auditor.audit(index, self.decoded_jd)
            self.assertEqual(mock_build.call_count, 0)
        self.assertEqual(res_idx["verdict"], "READY_TO_SEND")


class TestAtsDocxRenderer(unittest.TestCase):
    """Verify ATS DOCX single-column generation and compliance validation."""

    def setUp(self):
        import tempfile
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_render_docx_from_profile_and_view_model(self):
        from core.ats_docx_renderer import (
            AtsDocxRenderer,
            DocxRenderConfig,
            validate_docx_ats_compliance,
        )
        from core.resume_view_model import ResumeViewModel

        renderer = AtsDocxRenderer()
        docx_path = self.output_dir / "test_resume.docx"
        result_path = renderer.render(self.profile_data, docx_path)
        self.assertTrue(result_path.exists())
        self.assertGreater(result_path.stat().st_size, 1000)

        audit = validate_docx_ats_compliance(result_path)
        self.assertTrue(audit["passed"], f"ATS validation failed: {audit.get('errors')}")
        self.assertIn("Experience", audit["sections_detected"])
        self.assertIn("Skills", audit["sections_detected"])

        vm = ResumeViewModel.from_profile(self.profile_data)
        renderer_vm = AtsDocxRenderer(DocxRenderConfig(margin_inches=0.75))
        vm_path = self.output_dir / "vm_resume.docx"
        vm_res = renderer_vm.render(vm, vm_path)
        self.assertTrue(vm_res.exists())
        self.assertTrue(validate_docx_ats_compliance(vm_res)["passed"])

    def test_02_resume_builder_ats_docx_integration(self):
        from core.ats_docx_renderer import validate_docx_ats_compliance
        from core.resume_builder import ResumeBuilder

        builder = ResumeBuilder(self.profile_data)
        self.assertIn("ats-docx", builder.THEMES)

        res = builder.build_theme("ats-docx", self.output_dir)
        self.assertIn("docx", res)
        self.assertTrue(res["docx"].exists())
        audit = validate_docx_ats_compliance(res["docx"])
        self.assertTrue(audit["passed"])


if __name__ == "__main__":
    unittest.main()

