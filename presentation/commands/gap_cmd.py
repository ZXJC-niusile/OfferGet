"""
OfferGet Gap Command Handlers:
- cmd_gap_roi: Calculate Skill Gap ROI for near-miss opportunities
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.cli_helpers import (
    load_json,
    emit_json,
    emit_stderr,
)
from core.services import (
    calculate_gap_roi,
)


def cmd_gap_roi(args):
    """Handler for `offerget gap roi <jd_files...> --profile <profile.json>`."""
    profile_path = args.profile
    if not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)

    profile_data = load_json(profile_path)

    jd_files = args.jd_files
    for p in jd_files:
        if not os.path.exists(p):
            emit_stderr(f"[-] Error: JD file not found: {p}")
            sys.exit(1)

    result = calculate_gap_roi(profile_data, jd_files)

    if args.json:
        emit_json(result)
        return

    print("=" * 68)
    print("           OfferGet · Skill Gap ROI & Opportunity Engine         ")
    print("=" * 68)
    print(f"[*] Near-Miss Jobs Scanned (50-80% Fit): {result['total_near_miss_jobs']}")
    print("-" * 68)
    print("[*] Top 5 High-Leverage Skills to Acquire (Ranked by ROI):")
    for idx, item in enumerate(result["top_recommendations"], 1):
        print(f"  {idx}. [{item['skill']}] (ROI Score: {item['roi_score']})")
        print(f"     • 难易度: {item['difficulty']} | 预期上手: {item['rampup_estimate']}")
        print(f"     • 出现频次: {item['frequency_in_near_miss']} 岗位 | 预计直接解锁: {item['jobs_unlocked_estimate']} 岗位")
        print(f"     • 行动方案: {item['actionable_plan']}")
    print("-" * 68)
    print("[*] 战略突破建议 (Strategic Narrative):")
    print(result["strategic_summary"])
    print("=" * 68)
