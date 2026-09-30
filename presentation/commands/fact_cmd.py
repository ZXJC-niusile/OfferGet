"""
OfferGet Fact & Privacy Command Handlers:
- cmd_fact_verify: Fact verification & anti-drift guard against SSOT profile
- cmd_anon_mask (cmd_anon_profile): Anonymize profile JSON or resume text
- cmd_anon_unmask: Restore anonymized profile or text using mapping
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.cli_helpers import (
    load_json,
    load_json_or_text,
    write_json,
    write_text,
    emit_json,
    emit_stderr,
)
from core.anonymizer import PrivacyAnonymizer
from core.fact_guard import FactVerificationGuard


def cmd_anon_mask(args):
    """Handler for `offerget anon mask <file>`."""
    input_path = args.input_file
    if not os.path.exists(input_path):
        emit_stderr(f"[-] Error: Input file not found: {input_path}")
        sys.exit(1)

    json_data, content = load_json_or_text(input_path)
    is_json = json_data is not None
    data = json_data if is_json else content

    anonymizer = PrivacyAnonymizer()
    anon_data, deanon_map = anonymizer.anonymize(data, level=args.level)

    if args.map:
        anonymizer.save_map(deanon_map, args.map)

    if args.output:
        if is_json:
            write_json(anon_data, args.output)
        else:
            write_text(anon_data, args.output)
        if args.json:
            emit_stderr(f"[✓] Anonymized data saved to: {args.output}")
            if args.map:
                emit_stderr(f"[✓] De-anonymization map saved to: {args.map}")
        else:
            print(f"[✓] Anonymized data saved to: {args.output}")
            if args.map:
                print(f"[✓] De-anonymization map saved to: {args.map}")
    else:
        if args.json or is_json:
            emit_json(anon_data)
        else:
            print(anon_data)


cmd_anon_profile = cmd_anon_mask


def cmd_anon_unmask(args):
    """Handler for `offerget anon unmask <file> --map <map_file>`."""
    input_path = args.input_file
    map_path = args.map
    if not os.path.exists(input_path):
        emit_stderr(f"[-] Error: Input file not found: {input_path}")
        sys.exit(1)
    if not os.path.exists(map_path):
        emit_stderr(f"[-] Error: De-anonymization map not found: {map_path}")
        sys.exit(1)

    json_data, content = load_json_or_text(input_path)
    is_json = json_data is not None
    data = json_data if is_json else content

    anonymizer = PrivacyAnonymizer()
    deanon_map = anonymizer.load_map(map_path)
    restored_data = anonymizer.deanonymize(data, deanon_map)

    if args.output:
        if is_json:
            write_json(restored_data, args.output)
        else:
            write_text(restored_data, args.output)
        if args.json:
            emit_stderr(f"[✓] Restored data saved to: {args.output}")
        else:
            print(f"[✓] Restored data saved to: {args.output}")
    else:
        if args.json or is_json:
            emit_json(restored_data)
        else:
            print(restored_data)


def cmd_fact_verify(args):
    """Handler for `offerget fact verify <file_or_text> --profile <profile.json>`."""
    profile_path = args.profile
    if not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Master profile file not found: {profile_path}")
        sys.exit(1)

    master_profile = load_json(profile_path)

    json_data, text_data = load_json_or_text(args.target)
    target_data = json_data if json_data is not None else text_data

    guard = FactVerificationGuard(master_profile)
    result = guard.verify_facts(target_data)

    if args.json:
        emit_json(result)
        return

    print("=" * 68)
    print("           OfferGet · Fact Verification & Anti-Drift Guard       ")
    print("=" * 68)
    verdict_badge = "✅ PASSED" if result["passed"] else "❌ DRIFT DETECTED"
    print(f"[*] Verdict:        {result['verdict']} ({verdict_badge})")
    print(f"[*] Fact Score:     {result['score']} / 100")
    print(f"[*] Total Checked:  {result['summary']['total_bullets_checked']} bullets")
    print(f"[*] Verified:       {result['summary']['verified_bullets_count']} bullets")
    print("-" * 68)

    if result["drifts"]:
        print(f"[!] 发现 {len(result['drifts'])} 处指标虚标与数据漂移 (Metric Inflation Drift):")
        for idx, d in enumerate(result["drifts"], 1):
            print(f"  {idx}. [DRIFT] Claimed: {d['claimed_metric']}  ->  Verified SSOT: {d['verified_baseline']}")
            print(f"     • Bullet: {d['bullet'][:80]}...")

    if result["unverified_claims"]:
        print(f"\n[!] 发现 {len(result['unverified_claims'])} 处无事实锚点指标 (Unverified Numerical Claims):")
        for idx, u in enumerate(result["unverified_claims"], 1):
            print(f"  {idx}. [UNVERIFIED] Claimed: {u['claimed_metric']}")
            print(f"     • Bullet: {u['bullet'][:80]}...")

    if result["passed"]:
        print("[✓] 100% 事实锚定通过：所有技术指标均严格与 SSOT 单事实源吻合，未检出任何虚标或幻觉！")
    print("=" * 68)
