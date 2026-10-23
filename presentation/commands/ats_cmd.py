"""
OfferGet ATS Command Handlers:
- cmd_ats_audit: Audit candidate profile or resume against ATS standards
- cmd_ats_ledger: Generate 3-state skill ledger (Verified vs Claimed vs Gap)
- cmd_ats_filter: Filter master profile by visibility tag
"""

from __future__ import annotations

import os
import sys

from core.cli_helpers import (
    read_text,
    load_profile,
    write_json,
    emit_json,
    emit_stderr,
)

from services.profile_service import ProfileService


def cmd_ats_audit(args):
    """Handler for `offerget ats audit <input_file>`."""
    input_path = args.input_file
    if not os.path.exists(input_path):
        emit_stderr(f"[-] Error: Input file not found: {input_path}")
        sys.exit(1)

    jd_path = args.jd
    if jd_path and not os.path.exists(jd_path):
        emit_stderr(f"[-] Error: JD file not found: {jd_path}")
        sys.exit(1)

    result = ProfileService().audit_ats(
        profile_or_text=input_path,
        jd_decoded_or_text=jd_path,
        target_tag=args.tag
    )

    if args.json:
        emit_json(result)
        return

    print("=" * 68)
    print("           OfferGet · ATS Auditor & Three-State Skill Ledger     ")
    print("=" * 68)
    print(f"[*] Overall ATS Score:  {result['overall_score']} / 100")
    print(f"[*] Verdict:            {result['verdict']}")
    dims = result['dimensions']
    print(f"[*] 4-Dimension Breakdown (0-10):")
    print(f"    • Impact & Metrics:      {dims['impact']['score']} / 10 (Quantified: {dims['impact']['quantified_ratio']:.0%})")
    print(f"    • ATS Readiness:         {dims['ats_readiness']['score']} / 10")
    print(f"    • Anti-AI & Clarity:     {dims['clarity_anti_ai']['score']} / 10")
    print(f"    • Format Alignment:      {dims['format_alignment']['score']} / 10")
    print("-" * 68)
    if result['critical_issues']:
        print("[!] Critical Issues:")
        for ci in result['critical_issues']:
            print(f"    ❌ {ci}")
        print("-" * 68)
    ledger = result['skill_ledger']
    print(f"[*] Three-State Skill Ledger (Coverage: {ledger['summary']['coverage_ratio']:.0%}):")
    if ledger['present']:
        print(f"    • [VERIFIED]   ({len(ledger['present'])}): {', '.join([s['skill'] for s in ledger['present'][:6]])}...")
    if ledger['missing']:
        print(f"    • [CLAIMED]    ({len(ledger['missing'])}): {', '.join([s['skill'] for s in ledger['missing'][:4]])}")
    if ledger['unsupported_gap']:
        print(f"    • [GAP/HONEST] ({len(ledger['unsupported_gap'])}): {', '.join([s['skill'] for s in ledger['unsupported_gap'][:4]])}")
    print("-" * 68)
    print(f"[>] Actionable Recommendations:")
    for rec in result['recommendations'][:3]:
        print(f"    • {rec}")
    print("=" * 68)


def cmd_ats_ledger(args):
    """Handler for `offerget ats ledger <profile.json> --jd <jd.txt>`."""
    profile_path = args.profile
    jd_path = args.jd
    if not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)
    if not os.path.exists(jd_path):
        emit_stderr(f"[-] Error: JD file not found: {jd_path}")
        sys.exit(1)

    profile_data = load_profile(profile_path)
    jd_text = read_text(jd_path)

    ledger = ProfileService().generate_skill_ledger(profile_data, jd_text)

    if args.json:
        emit_json(ledger)
        return

    print("=" * 68)
    print("           OfferGet · Three-State Skill Ledger Analysis         ")
    print("=" * 68)
    summary = ledger["summary"]
    print(f"[*] Total Evaluated Skills: {summary['total_evaluated']}")
    print(f"[*] Verified Coverage:      {summary['coverage_ratio']:.0%}")
    print(f"[*] Distribution:           {summary['present_count']} Verified | {summary['missing_count']} Claimed | {summary['unsupported_gap_count']} Gaps")
    print("-" * 68)

    print("[1] VERIFIED SKILLS (Supported by concrete experience bullets):")
    for item in ledger["present"][:8]:
        print(f"    ✓ {item['skill']} ({item['evidence_count']} evidence bullets)")
    if len(ledger["present"]) > 8:
        print(f"    ... and {len(ledger['present']) - 8} more verified skills.")

    print("\n[2] CLAIMED SKILLS (Listed in competencies but needs bullet proof):")
    for item in ledger["missing"][:6]:
        print(f"    ? {item['skill']}")
        print(f"      Action: {item['recommendation']}")

    print("\n[3] UNSUPPORTED GAPS (Required by JD but candidate lacks; DO NOT FAKE):")
    for item in ledger["unsupported_gap"][:5]:
        print(f"    ! {item['skill']}")
        print(f"      Defense Strategy: {item['interview_defense']}")
    print("=" * 68)


def cmd_ats_filter(args):
    """Handler for `offerget ats filter <profile.json> --tag <tag> [--output <file>]`."""
    profile_path = args.profile
    tag = args.tag
    if not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)

    profile_data = load_profile(profile_path)
    tailored = ProfileService().filter_by_visibility(profile_data, tag)

    if args.output:
        write_json(tailored, args.output)
        print(f"[+] Tailored profile for tag '{tag}' saved to {args.output}")
    else:
        emit_json(tailored)
