"""
OfferGet JD Command Handlers:
- cmd_jd_decode: 5-layer JD parsing and hidden signal detection
- cmd_jd_match: Candidate alignment scoring against JD
- cmd_jd_report: Industrial-grade bilingual HTML report generation
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

from core.cli_helpers import (
    read_text,
    load_json,
    emit_json,
    emit_stderr,
)
from core.services import (
    decode_jd,
    match_profile_to_jd,
    generate_report,
    validate_bilingual_html,
)


def cmd_jd_decode(args):
    """Handler for `offerget jd decode <jd.txt>`."""
    jd_path = args.jd_file
    if not os.path.exists(jd_path):
        emit_stderr(f"[-] Error: JD file not found: {jd_path}")
        sys.exit(1)

    jd_text = read_text(jd_path)
    decoded = decode_jd(jd_text)

    if args.json:
        emit_json(decoded)
        return

    print("=" * 68)
    print("           OfferGet · 5-Layer Job Description Decoding           ")
    print("=" * 68)
    meta = decoded["metadata"]
    print(f"[*] Target Role:       {meta['role']}")
    print(f"[*] Company/Unit:      {meta['company']}")
    print(f"[*] Department:        {meta['department']}")
    print(f"[*] Level & Comp:      {meta['level']} | {meta['comp_band']}")
    print(f"[*] Work Location:     {meta['location']}")
    print("-" * 68)

    print("[1] Layer 1 - Organization & Mission:")
    print(f"    • JD Text:    {decoded['layers']['layer_1']['jd_text_zh']}")
    print(f"    • Reality:    {decoded['layers']['layer_1']['reality_zh']}")

    print("\n[2] Layer 2 - Hard Tech Architecture:")
    print(f"    • JD Text:    {decoded['layers']['layer_2']['jd_text_zh']}")
    print(f"    • Reality:    {decoded['layers']['layer_2']['reality_zh']}")

    print("\n[3] Layer 3 - Product Sense & Business Impact:")
    print(f"    • JD Text:    {decoded['layers']['layer_3']['jd_text_zh']}")
    print(f"    • Reality:    {decoded['layers']['layer_3']['reality_zh']}")

    print("\n[4] Layer 4 - Implicit Filters & Hidden Signals:")
    for sig in decoded.get("detected_signals", [])[:5]:
        pat = sig.get("pattern") or sig.get("original_text", "")
        meaning = sig.get("unspoken_reality") or sig.get("translated_meaning", "")
        print(f"    • [{pat}] -> {meaning}")

    print("\n[5] Layer 5 - Red Flags & KPI Reality:")
    print(f"    • Evaluation: {decoded['layers']['layer_5']['reality_zh']}")
    print("=" * 68)


def cmd_jd_match(args):
    """Handler for `offerget jd match <jd.txt> --profile <profile.json>`."""
    jd_path = args.jd_file
    profile_path = args.profile

    if not os.path.exists(jd_path):
        emit_stderr(f"[-] Error: JD file not found: {jd_path}")
        sys.exit(1)
    if not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)

    jd_text = read_text(jd_path)
    profile_data = load_json(profile_path)

    decoded = decode_jd(jd_text)
    match_result = match_profile_to_jd(decoded, profile_data)

    if args.json:
        emit_json(match_result)
        return

    print("=" * 68)
    print("           OfferGet · Candidate Alignment & Match Rubric         ")
    print("=" * 68)
    print(f"[*] Candidate:         {match_result['candidate_name']}")
    print(f"[*] Target Role:       {decoded['metadata']['role']}")
    print(f"[*] Overall Fit Score: {match_result['overall_match_score']}%")
    print(f"[*] Interview Prob:    {match_result['interview_prob']}%")
    bd = match_result['breakdown']
    print(f"[*] Score Breakdown:   Must-Have: {bd['must_have']}% | Nice-Have: {bd['nice_have']}% | Hidden: {bd['hidden_fit']}%")
    print("-" * 68)
    print(f"[>] Verdict: {match_result['verdict']['title_zh']}")
    print(f"    {match_result['verdict']['desc_zh']}")
    print("-" * 68)
    print("[*] Core Must-Have Credential Matches:")
    for idx, card in enumerate(match_result.get("must_have_matches", []), 1):
        req_title = card.get("title_zh") or card.get("req_zh") or card.get("requirement_name", "")
        evidence = card.get("evidence_zh") or card.get("evidence", "")
        print(f"    {idx}. [{card.get('score', 0)}%] {req_title}")
        if evidence:
            print(f"       Evidence: {evidence}")
    print("-" * 68)
    print("[!] Gaps Identified & 4-Week Fixes:")
    for gap in match_result.get("gaps", []):
        gap_p = gap.get("priority", "medium").upper()
        gap_t = gap.get("title_zh") or gap.get("title", "")
        gap_f = gap.get("fix_zh") or gap.get("fix", "")
        print(f"    • [{gap_p}] {gap_t}")
        if gap_f:
            print(f"      Fix: {gap_f}")
    print("=" * 68)


def cmd_jd_report(args):
    """Handler for `offerget jd report <jd.txt> --profile <profile.json> --output report.html`."""
    jd_path = args.jd_file
    profile_path = args.profile
    output_path = args.output or "report.html"
    template_arg = getattr(args, "template", None)

    if not os.path.exists(jd_path):
        emit_stderr(f"[-] Error: JD file not found: {jd_path}")
        sys.exit(1)
    if not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)

    print(f"[*] Decoding Job Description: {jd_path} ...")
    jd_text = read_text(jd_path)
    profile_data = load_json(profile_path)

    decoded = decode_jd(jd_text)

    print(f"[*] Computing Candidate Alignment Matrix with: {profile_path} ...")
    match_result = match_profile_to_jd(decoded, profile_data)

    print(f"[*] Generating Industrial-grade Bilingual HTML Report ...")
    try:
        out_file = generate_report(decoded, match_result, template_path=template_arg, output_path=output_path)
    except FileNotFoundError as e:
        emit_stderr(f"[-] Error: {e}")
        sys.exit(1)

    print(f"[*] Validating Bilingual Twin Integrity on {out_file} ...")
    val = validate_bilingual_html(out_file)
    if not val["passed"]:
        emit_stderr(f"[-] Validation Warning: {val['errors']}")
    else:
        print(f"[+] Bilingual Twin Validation Passed! (EN={val['en_count']}, ZH={val['zh_count']}, Root=<html lang='en'>)")

    print("=" * 68)
    print(f"🎉 Success! Offer Strategy Report successfully generated at:")
    normalized_out_file = os.path.abspath(out_file).replace(os.sep, "/")
    print(f"   file:///{normalized_out_file}")
    print("=" * 68)
