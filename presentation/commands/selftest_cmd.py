"""
OfferGet installed-runtime smoke checks using synthetic diagnostic fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from core.anonymizer import anonymize_profile, deanonymize_text
from core.ats_checker import audit_resume_ats
from core.autofit import TUNING_LADDER, AutoFitEngine
from core.browser_renderer import BrowserRenderer
from core.cli_helpers import emit_stderr
from core.fact_guard import FactVerificationGuard
from core.resume_auditor import ResumeAuditor
from core.resume_parser import parse_resume_to_profile
from core.validator import validate_anti_ai_slop
from presentation.diagnostic_data import load_fixture, missing_resources, read_fixture


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
    print(f"[1/7] Python Runtime: {sys.version.split()[0]} ({sys.platform})")
    diag = BrowserRenderer.diagnose_browser()
    if diag["found"]:
        print(f"      ✓ Headless Browser Detected: {diag['browser_path']}")
    else:
        print("      ○ Headless Browser: NOT FOUND (Run 'python cli.py doctor' for install guide)")

    # 1. Resume Parser & Anti-AI Slop
    print("[2/7] Testing Resume Parser & Anti-AI-Slop ...")
    parsed = parse_resume_to_profile("# Alex Example\n\n## Experience\n- Example Corp | Engineer | 2024-2025\n  - Reduced latency by 25%.\n")
    assert parsed.get("candidate", {}).get("name") == "Alex Example", "Parser must preserve candidate name"
    profile_data = load_fixture("candidate_profile.json")
    anti_slop = validate_anti_ai_slop(profile_data["narrative"]["summary_zh"])
    if not anti_slop["passed"]:
        print(f"[-] Anti-AI Slop warning: {anti_slop['violations']}")
    else:
        print("      ✓ Resume Parser & Anti-AI-Slop verified")

    # 2. ATS Auditor & Keyword Coverage
    print("[3/7] Testing ATS Auditor & Skill Ledger ...")
    jd_text = read_fixture("sample_ai_jd.txt")
    ats_res = audit_resume_ats(profile_data, jd_text, target_tag="always")
    assert ats_res["verdict"] == "NEEDS_REVISION", "Incomplete synthetic profile must need revision"
    assert 0 <= ats_res["overall_score"] <= 100, "ATS score must be bounded"
    assert "skill_ledger" in ats_res and len(ats_res["skill_ledger"]["present"]) > 0, "Skill ledger must detect present skills"
    print(f"      ✓ ATS Auditor verified (Score: {ats_res['overall_score']}, Verdict: {ats_res['verdict']})")

    # 3. Privacy Anonymizer
    print("[4/7] Testing Privacy Anonymizer (Strict) ...")
    anon_p, deanon_m = anonymize_profile(profile_data, level="strict")
    assert anon_p["candidate"]["name"] == "Dr. Alex Chen", "Candidate name must be pseudonymized"
    restored_p = deanonymize_text(anon_p, deanon_m)
    assert restored_p == profile_data, "De-anonymization must restore profile 100%"
    print("      ✓ Privacy Anonymizer verified: Reversible pseudonymization confirmed")

    # 4. Fact Verification Guard
    print("[5/7] Testing Fact Verification Guard ...")
    guard = FactVerificationGuard(profile_data)
    v_res = guard.verify_facts("测试覆盖率达到 54.2%。")
    assert v_res["passed"] is True, "Grounded bullet must pass"
    d_res = guard.verify_facts("测试覆盖率达到 85%。")
    assert d_res["passed"] is False, "Drifted bullet must be caught"
    assert len(d_res["drifts"]) >= 1, "Must detect drifts"
    print("      ✓ Fact Verification Guard verified: Zero-drift assertions & inflation caught")

    # 5. Resume Audit & AutoFit CSS
    print("[6/7] Testing Resume Audit & AutoFit CSS ...")
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

    # 6. Academic Publication Exporter
    print("[7/7] Testing Academic Exporter & HTML Rendering ...")
    from core.academic_exporter import AcademicExporter
    from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
    vm = ResumeViewModel.from_profile({
        "candidate": {"name": "Alex Lin"},
        "publications": [{"title": "Paper A", "authors": ["Alex Lin", "B. Coauthor"], "status": "submitted"}],
    }, photo_mode="no-photo")
    rendered = HtmlThemeRenderer().render(vm, "modern-navy")
    assert "<strong>Alex Lin</strong>" in rendered and "Paper A" in rendered
    tex = AcademicExporter().generate_latex(vm)
    assert r"\textbf{Alex Lin}" in tex and "Paper A" in tex
    print("      ✓ Academic CV & HTML rendering checks passed")
    print("      ○ PDF rendering: NOT RUN (browser discovery is not a render test)")

    print("\n" + "=" * 68)
    print("CORE SMOKE CHECKS PASSED. Optional rendering was not exercised.")
    print("Developer regression suite: run python -m pytest tests/ in a source checkout.")
    print("=" * 68)
