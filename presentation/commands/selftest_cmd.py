"""
OfferGet installed-runtime smoke checks using synthetic diagnostic fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from core.cli_helpers import emit_stderr
from core.fact_guard import FactVerificationGuard
from core.validator import validate_anti_ai_slop, validate_bilingual_html
from presentation.diagnostic_data import load_fixture, missing_resources, read_fixture
from services.academic_service import AcademicService
from services.jd_service import JDService
from services.match_service import MatchService
from services.profile_service import ProfileService
from services.report_service import ReportService


def cmd_selftest(args=None):
    """Run core smoke checks without requiring a source checkout or test suite."""
    missing = missing_resources()
    if missing:
        emit_stderr(f"[-] Missing installed diagnostic resources: {', '.join(missing)}. Reinstall OfferGet.")
        sys.exit(1)
    with TemporaryDirectory(prefix="offerget-selftest-") as temporary:
        _run_smoke_checks(Path(temporary))


def _run_smoke_checks(output_dir: Path):
    print("=" * 68)
    print("              OfferGet Installed-Runtime Smoke Checks             ")
    print("=" * 68)
    print(f"[1/11] Python Runtime: {sys.version.split()[0]} ({sys.platform})")
    from core.browser_renderer import BrowserRenderer
    diag = BrowserRenderer.diagnose_browser()
    if diag["found"]:
        print(f"      ✓ Headless Browser Detected: {diag['browser_path']}")
    else:
        print("      ○ Headless Browser: NOT FOUND (Run 'python cli.py doctor' for install guide)")

    # 1. Test JD Decoder
    print("[2/11] Testing JD Decoder on sample_ai_jd.txt ...")
    jd_text = read_fixture("sample_ai_jd.txt")
    decoded = JDService().decode_jd(jd_text)
    assert "layers" in decoded and len(decoded["layers"]) == 5, "JD Decoder must yield 5 layers!"
    print(f"      ✓ 5-Layer decomposition verified ({len(decoded['detected_signals'])} hidden signals detected)")

    # 2. Test JD Matcher
    print("[3/11] Testing JD Matcher against candidate_profile.json ...")
    profile_data = load_fixture("candidate_profile.json")
    match_result = MatchService().match(decoded, profile_data)
    assert 0 <= match_result["overall_match_score"] <= 100, "Match score must be bounded"
    print(f"      ✓ Match Matrix verified (Overall: {match_result['overall_match_score']}%, Interview Prob: {str(match_result['interview_prob']) + '%' if match_result['interview_prob'] is not None else 'N/A (no calibrated outcome data)'})")

    # 3. Test Report Generator & Bilingual Validator
    print("[4/11] Testing Report Generator & Bilingual Twin Validator ...")
    test_out = output_dir / "test_output_report.html"
    ReportService().generate_offer_strategy_report(
        decoded, match_result, output_path=str(test_out)
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
        print("      ✓ Anti-AI-Slop audit verified: No forbidden cliches detected")

    # Clean up test output
    if test_out.exists():
        test_out.unlink()

    # 4. Test ATS Auditor & Three-State Skill Ledger
    print("[5/11] Testing ATS Auditor & Three-State Skill Ledger ...")
    ats_res = ProfileService().audit_ats(profile_data, decoded, target_tag="always")
    assert ats_res["verdict"] == "NEEDS_REVISION", "Incomplete synthetic profile must need revision"
    assert 0 <= ats_res["overall_score"] <= 100, "ATS score must be bounded"
    assert "skill_ledger" in ats_res and len(ats_res["skill_ledger"]["present"]) > 0, "Skill ledger must detect present skills"
    print(f"      ✓ ATS Auditor verified (Score: {ats_res['overall_score']}, Verdict: {ats_res['verdict']}, Ledger: {ats_res['skill_ledger']['summary']['present_count']} verified)")

    # 5. Test Privacy Anonymizer
    print("[6/11] Testing Privacy Anonymizer (Strict) ...")
    anon_p, deanon_m = ProfileService().anonymize(profile_data, level="strict")
    assert anon_p["candidate"]["name"] == "Dr. Alex Chen", "Candidate name must be pseudonymized"
    restored_p = ProfileService().deanonymize(anon_p, deanon_m)
    assert restored_p == profile_data, "De-anonymization must restore profile 100%"
    print("      ✓ Privacy Anonymizer verified: Reversible pseudonymization confirmed")

    # 6. Test Fact Verification Guard
    print("[7/11] Testing Fact Verification Guard ...")
    guard = FactVerificationGuard(profile_data)
    v_res = guard.verify_facts("测试覆盖率达到 54.2%。")
    assert v_res["passed"] is True, "Grounded bullet must pass"
    d_res = guard.verify_facts("测试覆盖率达到 85%。")
    assert d_res["passed"] is False, "Drifted bullet must be caught"
    assert len(d_res["drifts"]) >= 1, "Must detect drifts"
    print("      ✓ Fact Verification Guard verified: Zero-drift assertions & inflation caught")

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
    print("      ✓ Baoyan Auditor smoke checks passed: entry validation and summary compression")

    # 8. Test Baoyan Pipeline & Academic Candidate Schema
    print("[9/11] Testing Baoyan Pipeline & Academic Profile Schema ...")
    acad_profile = load_fixture("academic_profile.json")
    v_acad = AcademicService().validate_profile(acad_profile)
    assert v_acad["valid"] is True, f"Academic profile schema must be valid: {v_acad['errors']}"
    assert 0 <= v_acad["competitiveness_score"] <= 100, "Academic score must be bounded"
    checklist = AcademicService().generate_checklist(acad_profile, stage="夏令营", track="直博")
    assert checklist["total_items"] >= 5, "Checklist must contain categorized items"
    print(f"      ✓ Baoyan Pipeline verified: Academic schema valid (Score: {v_acad['competitiveness_score']}/100, Checklist: {checklist['total_items']} items)")

    # 9. Test Advisor Matcher & Outreach Email Generator
    print("[10/11] Testing Chinese Advisor Matcher & Outreach Generator ...")
    sample_adv = load_fixture("sample_advisor.json")
    match_adv = AcademicService().match_advisor(sample_adv, acad_profile, email_scenario="summer_camp")
    match_score = match_adv["intersection_match"]["intersection_score"]
    assert 0 <= match_score <= 100, "Advisor match score must be bounded"
    email_body = match_adv["outreach_email"]["body"]
    assert "陈老师" in email_body and "Synthetic Student" in email_body, "Synthetic outreach must be generated"
    print(f"      ✓ Advisor Matcher verified: Overlap {match_score}%, High-EQ outreach email drafted")

    # Core-only checks do not depend on repository tests or optional renderers.
    print("[11/11] Testing Resume Audit & AutoFit CSS ...")
    from core.resume_auditor import ResumeAuditor
    from core.autofit import TUNING_LADDER, AutoFitEngine
    auditor = ResumeAuditor()
    auditor.check_metrics("synthetic", "4/5 (80%)", {
        "numerator": 4, "denominator": 5, "displayed_percent": 80,
    })
    assert auditor.summary()["passed"], "Valid synthetic ratio must pass"
    auditor.check_metrics("synthetic-invalid", "4/5 (90%)", {
        "numerator": 4, "denominator": 5, "displayed_percent": 90,
    })
    assert not auditor.summary()["passed"], "Invalid synthetic ratio must fail"
    html = "<html><head></head><body>synthetic</body></html>"
    tuned = AutoFitEngine(renderer=BrowserRenderer(browser_path="unused-css-only")).apply_profile_to_html(
        html, TUNING_LADDER[0]
    )
    assert 'id="autofit-override"' in tuned, "AutoFit CSS must be inserted"
    print("      ✓ Resume audit and AutoFit CSS smoke checks passed")
    print("      ○ PDF rendering: NOT RUN (browser discovery is not a render test)")

    print("\n" + "=" * 68)
    print("CORE SMOKE CHECKS PASSED. Optional rendering was not exercised.")
    print("Developer regression suite: run python -m pytest tests/ in a source checkout.")
    print("=" * 68)
