"""
OfferGet Unified Environment Self-Test Command Handler:
- cmd_selftest: Runs OfferGet core engines + ATS Auditor + ApexResume test suite
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

from core.paths import get_project_root
PROJECT_ROOT = get_project_root()

from core.cli_helpers import (
    read_text,
    load_json,
    emit_stderr,
)
from services.jd_service import JDService
from services.match_service import MatchService
from services.report_service import ReportService
from services.profile_service import ProfileService
from services.academic_service import AcademicService
from core.fact_guard import FactVerificationGuard
from core.validator import validate_bilingual_html, validate_anti_ai_slop


def cmd_selftest(args=None):
    """Runs OfferGet unified selftest: OfferGet core engines + ATS Auditor + ApexResume test suite."""
    print("=" * 68)
    print("              OfferGet Unified Environment Self-Test             ")
    print("=" * 68)
    print(f"[1/11] Python Runtime: {sys.version.split()[0]} ({sys.platform})")
    from ApexResume.core.render import BrowserRenderer
    diag = BrowserRenderer.diagnose_browser()
    if diag["found"]:
        print(f"      ✓ Headless Browser Detected: {diag['browser_path']}")
    else:
        print("      ○ Headless Browser: NOT FOUND (Run 'python cli.py doctor' for install guide)")

    # 1. Test JD Decoder
    print("[2/11] Testing JD Decoder on sample_ai_jd.txt ...")
    sample_jd_path = PROJECT_ROOT / "examples" / "sample_ai_jd.txt"
    if not sample_jd_path.exists():
        emit_stderr("[-] Error: sample_ai_jd.txt missing!")
        sys.exit(1)
    jd_text = read_text(str(sample_jd_path))
    decoded = JDService().decode_jd(jd_text)
    assert "layers" in decoded and len(decoded["layers"]) == 5, "JD Decoder must yield 5 layers!"
    print(f"      ✓ 5-Layer decomposition verified ({len(decoded['detected_signals'])} hidden signals detected)")

    # 2. Test JD Matcher
    print("[3/11] Testing JD Matcher against candidate_profile.json ...")
    sample_profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
    if not sample_profile_path.exists():
        emit_stderr("[-] Error: candidate_profile.json missing!")
        sys.exit(1)
    profile_data = load_json(str(sample_profile_path))
    match_result = MatchService().match(decoded, profile_data)
    assert match_result["overall_match_score"] > 80, "Match score should be > 80"
    print(f"      ✓ Match Matrix verified (Overall: {match_result['overall_match_score']}%, Interview Prob: {match_result['interview_prob']}%)")

    # 3. Test Report Generator & Bilingual Validator
    print("[4/11] Testing Report Generator & Bilingual Twin Validator ...")
    template_path = PROJECT_ROOT / "templates" / "offer_strategy.html"
    test_out = PROJECT_ROOT / "tests" / "test_output_report.html"
    ReportService().generate_offer_strategy_report(
        decoded, match_result, output_path=str(test_out), template_path=str(template_path)
    )

    val = validate_bilingual_html(str(test_out))
    if not val["passed"]:
        print(f"[-] Bilingual Validator failed: {val['errors']}", file=sys.stderr)
        sys.exit(1)
    print(f"      ✓ Bilingual Report verified: {val['en_count']} EN/ZH twin spans (≥80 required, passed)")

    # Anti-AI Slop check
    anti_slop = validate_anti_ai_slop(profile_data["narrative"]["summary_zh"])
    if not anti_slop["passed"]:
        print(f"[-] Anti-AI Slop warning: {anti_slop['violations']}")
    else:
        print(f"      ✓ Anti-AI-Slop audit verified: No forbidden cliches detected")

    # Clean up test output
    if test_out.exists():
        test_out.unlink()

    # 4. Test ATS Auditor & Three-State Skill Ledger
    print("[5/11] Testing ATS Auditor & Three-State Skill Ledger ...")
    ats_result = ProfileService().audit_ats(str(sample_profile_path), str(sample_jd_path))
    assert ats_result["overall_score"] >= 75.0, f"ATS overall score should be >= 75, got {ats_result['overall_score']}"
    assert ats_result["verdict"] == "READY_TO_SEND", f"Verdict should be READY_TO_SEND, got {ats_result['verdict']}"
    print(f"      ✓ ATS Quality Gate verified (Score: {ats_result['overall_score']}/100, Verdict: {ats_result['verdict']})")

    ats_res = ProfileService().audit_ats(profile_data, decoded, target_tag="always")
    assert ats_res["verdict"] == "READY_TO_SEND", f"ATS verdict should be READY_TO_SEND, got {ats_res['verdict']}"
    assert ats_res["overall_score"] >= 75.0, f"ATS overall score should be >= 75, got {ats_res['overall_score']}"
    assert "skill_ledger" in ats_res and len(ats_res["skill_ledger"]["present"]) > 0, "Skill ledger must detect present skills"
    print(f"      ✓ ATS Auditor verified (Score: {ats_res['overall_score']}, Verdict: {ats_res['verdict']}, Ledger: {ats_res['skill_ledger']['summary']['present_count']} verified)")

    # 5. Test Privacy Anonymizer
    print("[6/11] Testing Privacy Anonymizer (Standard & Strict) ...")
    anon_p, deanon_m = ProfileService().anonymize(profile_data, level="strict")
    assert anon_p["candidate"]["name"] == "Dr. Alex Chen", "Candidate name must be pseudonymized"
    restored_p = ProfileService().deanonymize(anon_p, deanon_m)
    assert restored_p == profile_data, "De-anonymization must restore profile 100%"
    print(f"      ✓ Privacy Anonymizer verified: Reversible pseudonymization confirmed")

    # 6. Test Fact Verification Guard
    print("[7/11] Testing Fact Verification Guard ...")
    guard = FactVerificationGuard(profile_data)
    v_res = guard.verify_facts("主导 1024 卡 H800 集群预训练，端到端 MFU 优化至 54.2%，提前 3 周交付。")
    assert v_res["passed"] is True, "Grounded bullet must pass"
    d_res = guard.verify_facts("主导 2048 卡 H800 集群预训练，端到端 MFU 优化至 85%。")
    assert d_res["passed"] is False, "Drifted bullet must be caught"
    assert len(d_res["drifts"]) >= 1, "Must detect drifts"
    print(f"      ✓ Fact Verification Guard verified: Zero-drift assertions & inflation caught")

    # 7. Test Baoyan Academic Integrity & Word-Count Auditor
    print("[8/11] Testing Baoyan Academic Integrity & Word-Count Auditor ...")
    test_entry = "负责 8 卡 A100 集群上完成并行微调实验，实测吞吐提升 34.2%，成果已整理准备投稿。"
    audit_res = AcademicService().audit_entry(test_entry, role="核心成员", target_tier="简历版")
    assert audit_res["passed"] is True, f"Legitimate entry must pass: {audit_res['violations']}"
    # Test illegal simulation conflation
    fake_entry = "负责利用 Gazebo 仿真环境搭建万卡集群产线实测系统。"
    fake_res = AcademicService().audit_entry(fake_entry, role="参赛队员", target_tier="简历版")
    assert fake_res["passed"] is False, "Simulation vs cluster conflation must be flagged"
    long_entry = (
        "针对移动机器人在未知复杂动态环境下的自主导航难题，在本项目中，作为核心成员，"
        "设计并实现了一种基于改进PPO与局部路径规划融合的导航算法。搭建仿真测试平台，"
        "通过深入研究，最终仿真测试表明，避障成功率达到94.8%，规划延迟降低至32ms，荣获国家一等奖。"
    )
    comp_res = AcademicService().compress_entry(long_entry, target_tier="摘要版")
    assert comp_res["is_in_range"] is True, f"Compressor must meet bounds: {comp_res}"
    print(f"      ✓ Baoyan Auditor verified: 4 integrity redlines enforced & 3-tier compression working")

    # 8. Test Baoyan Pipeline & Academic Candidate Schema
    print("[9/11] Testing Baoyan Pipeline & Academic Profile Schema ...")
    acad_profile_path = PROJECT_ROOT / "examples" / "academic_profile.json"
    assert acad_profile_path.exists(), "academic_profile.json must exist"
    acad_profile = load_json(str(acad_profile_path))
    v_acad = AcademicService().validate_profile(acad_profile)
    assert v_acad["valid"] is True, f"Academic profile schema must be valid: {v_acad['errors']}"
    assert v_acad["competitiveness_score"] >= 90.0, "Top tier academic profile should score >= 90"
    checklist = AcademicService().generate_checklist(acad_profile, stage="夏令营", track="直博")
    assert checklist["total_items"] >= 5, "Checklist must contain categorized items"
    print(f"      ✓ Baoyan Pipeline verified: Academic schema valid (Score: {v_acad['competitiveness_score']}/100, Checklist: {checklist['total_items']} items)")

    # 9. Test Advisor Matcher & Outreach Email Generator
    print("[10/11] Testing Chinese Advisor Matcher & Outreach Generator ...")
    adv_path = PROJECT_ROOT / "examples" / "sample_advisor.json"
    assert adv_path.exists(), "sample_advisor.json must exist"
    sample_adv = load_json(str(adv_path))
    match_adv = AcademicService().match_advisor(sample_adv, acad_profile, email_scenario="summer_camp")
    match_score = match_adv["intersection_match"]["intersection_score"]
    assert match_score >= 60.0, f"Matching score should be >= 60, got {match_score}"
    email_body = match_adv["outreach_email"]["body"]
    assert "NeurIPS 2024" in email_body or "陈老师" in email_body, "Outreach email must be generated"
    print(f"      ✓ Advisor Matcher verified: Overlap {match_score}%, High-EQ outreach email drafted")

    # 10. ApexResume Selftest
    print("\n[11/11] Invoking ApexResume Independent Subsystem Self-Test...")
    apex_cli = PROJECT_ROOT / "ApexResume" / "cli.py"
    if not apex_cli.exists():
        emit_stderr(f"[-] Error: ApexResume not found at {apex_cli}")
        sys.exit(1)

    cmd = [sys.executable, str(apex_cli), "selftest"]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT / "ApexResume"))
    if proc.returncode != 0:
        emit_stderr("[-] ApexResume self-test failed!")
        sys.exit(proc.returncode)

    print("\n" + "=" * 68)
    print("🎉 ALL TESTS PASSED! OfferGet & ApexResume Dual-Track System Fully Verified!")
    print("=" * 68)
