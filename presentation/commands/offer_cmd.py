"""
OfferGet Offer Command Handlers:
- cmd_offer_eval (cmd_offer_evaluate): Offer valuation and contract trap auditor
- cmd_offer_counter: High-EQ tactical counter-offer generator
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
    evaluate_offer_package,
    OfferNegotiator,
)


def cmd_offer_eval(args):
    """Handler for `offerget offer evaluate <offer.json> [--profile <profile.json>]`."""
    offer_path = args.offer_file
    if not os.path.exists(offer_path):
        emit_stderr(f"[-] Error: Offer file not found: {offer_path}")
        sys.exit(1)

    offer_data = load_json(offer_path)

    profile_data = None
    if args.profile:
        if not os.path.exists(args.profile):
            emit_stderr(f"[-] Error: Profile file not found: {args.profile}")
            sys.exit(1)
        profile_data = load_json(args.profile)

    result = evaluate_offer_package(offer_data, profile_data)

    if args.json:
        emit_json(result)
        return

    comp = result["total_compensation"]
    print("=" * 68)
    print("           OfferGet · Offer Valuation & Contract Trap Auditor    ")
    print("=" * 68)
    print(f"[*] Company:        {result['company']}")
    print(f"[*] Role:           {result['role']}")
    print(f"[*] Total Package:  {int(comp['total_annual_package']):,} RMB / 年")
    print(f"[*] Annual Cash:    {int(comp['total_annual_cash']):,} RMB / 年 (现金占比 {round(comp['cash_ratio']*100, 1)}%)")
    print(f"[*] Guaranteed Base:{int(comp['guaranteed_annual_cash']):,} RMB / 年")
    print(f"[*] Offer Health:   {result['overall_score']} / 100 (风险评级: {result['risk_level']})")
    print("-" * 68)
    if result["detected_traps"]:
        print(f"[!] 检测到 {len(result['detected_traps'])} 项合同陷阱与合规风险:")
        for idx, trap in enumerate(result["detected_traps"], 1):
            print(f"  {idx}. [{trap['severity']}] {trap['name']}")
            print(f"     • 隐患: {trap['issue_summary']}")
            print(f"     • 依据: {trap['legal_basis'][:60]}...")
            print(f"     • 对策: {trap['negotiation_countermeasure']}")
    else:
        print("[✓] 合同条款健全，未检出重大合同陷阱。")
    print("=" * 68)


cmd_offer_evaluate = cmd_offer_eval


def cmd_offer_counter(args):
    """Handler for `offerget offer counter <offer.json> [--target-base <int>] [--competing <json>]`."""
    offer_path = args.offer_file
    if not os.path.exists(offer_path):
        emit_stderr(f"[-] Error: Offer file not found: {offer_path}")
        sys.exit(1)

    offer_data = load_json(offer_path)

    profile_data = None
    if args.profile and os.path.exists(args.profile):
        profile_data = load_json(args.profile)

    competing = None
    if args.competing and os.path.exists(args.competing):
        competing = load_json(args.competing)

    negotiator = OfferNegotiator()
    eval_res = negotiator.evaluate_offer(offer_data, profile_data)
    counter_res = negotiator.generate_counter_offer(eval_res, target_base=args.target_base, competing_offers=competing)

    if args.json:
        emit_json(counter_res)
        return

    print("=" * 68)
    print("           OfferGet · High-EQ Tactical Counter-Offer Generator   ")
    print("=" * 68)
    print(f"[*] Target Monthly Base: {int(counter_res['target_base']):,} RMB (+{counter_res['base_increment_pct']}%)")
    print(f"[*] Strategy: {counter_res['negotiation_strategy_summary']}")
    print("-" * 68)
    print("[1] 电话/面谈高情商话术 (Verbal Negotiation Script):")
    script = counter_res["verbal_negotiation_script"]
    print(f"  • 开场致谢: {script['opening_and_anchor']}")
    print(f"  • 亮出筹码: {script['leverage_presentation']}")
    print(f"  • 明确要价: {script['the_ask_compensation']}")
    print(f"  • 条款修正: {script['trap_rectification_points']}")
    print(f"  • 促成收尾: {script['closing_and_commitment']}")
    print("-" * 68)
    print("[2] 书面 Counter-Offer 邮件草稿 (Written Letter Draft):")
    print(counter_res["counter_offer_letter"])
    print("=" * 68)
