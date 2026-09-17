#!/usr/bin/env python3
"""
OfferGet Master CLI - Job Description Decoding, Match Scoring, Report Generation & ApexResume Integration.
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add current directory to sys.path so core is importable
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from core.jd_decoder import decode_jd
from core.jd_matcher import match_profile_to_jd
from core.report_generator import generate_report
from core.validator import validate_bilingual_html, validate_anti_ai_slop
from core.ats_checker import audit_resume_ats, generate_skill_ledger, filter_profile_by_visibility
from core.gap_roi import calculate_gap_roi, SkillGapROIEngine
from core.offer_negotiator import evaluate_offer_package, OfferNegotiator
from core.anonymizer import PrivacyAnonymizer, anonymize_profile, deanonymize_text
from core.fact_guard import FactVerificationGuard, verify_resume_facts
from core.defense_simulator import DefenseSimulator, simulate_project_defense
from core.baoyan_auditor import BaoyanAuditor, audit_baoyan_entry, compress_baoyan_entry, count_baoyan_words
from core.baoyan_pipeline import BaoyanPipeline, BaoyanStatus, validate_academic_profile, generate_camp_checklist
from core.advisor_matcher import AdvisorMatcher, match_advisor_and_draft_email
from core.job_flow import run_career_review


def cmd_jd_decode(args):
    """Handler for `offerget jd decode <jd.txt>`."""
    jd_path = args.jd_file
    if not os.path.exists(jd_path):
        print(f"[-] Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    decoded = decode_jd(jd_text)

    if args.json:
        print(json.dumps(decoded, ensure_ascii=False, indent=2))
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
    for sig in decoded["detected_signals"][:5]:
        print(f"    • [{sig['pattern']}] -> {sig['unspoken_reality']}")

    print("\n[5] Layer 5 - Red Flags & KPI Reality:")
    print(f"    • Evaluation: {decoded['layers']['layer_5']['reality_zh']}")
    print("=" * 68)


def cmd_jd_match(args):
    """Handler for `offerget jd match <jd.txt> --profile <profile.json>`."""
    jd_path = args.jd_file
    profile_path = args.profile

    if not os.path.exists(jd_path):
        print(f"[-] Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(profile_path):
        print(f"[-] Error: Profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    decoded = decode_jd(jd_text)
    match_result = match_profile_to_jd(decoded, profile_data)

    if args.json:
        print(json.dumps(match_result, ensure_ascii=False, indent=2))
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
    for idx, card in enumerate(match_result["must_have_matches"], 1):
        print(f"    {idx}. [{card['score']}%] {card['req_zh']}")
        print(f"       Evidence: {card['evidence_zh']}")
    print("-" * 68)
    print("[!] Gaps Identified & 4-Week Fixes:")
    for gap in match_result["gaps"]:
        print(f"    • [{gap['priority'].upper()}] {gap['title_zh']}")
        print(f"      Fix: {gap['fix_zh']}")
    print("=" * 68)


def cmd_jd_report(args):
    """Handler for `offerget jd report <jd.txt> --profile <profile.json> --output report.html`."""
    jd_path = args.jd_file
    profile_path = args.profile
    output_path = args.output or "report.html"
    template_path = args.template or str(CURRENT_DIR / "templates" / "offer_strategy.html")

    if not os.path.exists(jd_path):
        print(f"[-] Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(profile_path):
        print(f"[-] Error: Profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(template_path):
        print(f"[-] Error: Template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Decoding Job Description: {jd_path} ...")
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    decoded = decode_jd(jd_text)

    print(f"[*] Computing Candidate Alignment Matrix with: {profile_path} ...")
    match_result = match_profile_to_jd(decoded, profile_data)

    print(f"[*] Generating Industrial-grade Bilingual HTML Report ...")
    out_file = generate_report(decoded, match_result, template_path, output_path)

    print(f"[*] Validating Bilingual Twin Integrity on {out_file} ...")
    val = validate_bilingual_html(out_file)
    if not val["passed"]:
        print(f"[-] Validation Warning: {val['errors']}", file=sys.stderr)
    else:
        print(f"[+] Bilingual Twin Validation Passed! (EN={val['en_count']}, ZH={val['zh_count']}, Root=<html lang='en'>)")

    print("=" * 68)
    print(f"🎉 Success! Offer Strategy Report successfully generated at:")
    normalized_out_file = os.path.abspath(out_file).replace(os.sep, "/")
    print(f"   file:///{normalized_out_file}")
    print("=" * 68)


def cmd_career_review(args):
    """Handler for `offerget review <jd.txt> --profile <profile.json> [--answers <answers.json>]`."""
    jd_path = args.jd_file
    profile_path = args.profile
    answers_path = args.answers

    if not os.path.exists(jd_path):
        print(f"[-] Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(profile_path):
        print(f"[-] Error: Profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    answers_data = None
    if answers_path:
        if not os.path.exists(answers_path):
            print(f"[-] Error: Answers file not found: {answers_path}", file=sys.stderr)
            sys.exit(1)
        with open(answers_path, "r", encoding="utf-8") as f:
            answers_data = json.load(f)

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    review_result = run_career_review(
        jd_text=jd_text,
        profile_dict=profile_data,
        answers_dict=answers_data,
        build_resume=getattr(args, "build_resume", False),
        resume_theme=getattr(args, "resume_theme", "modern-navy"),
        resume_output_dir=getattr(args, "resume_output_dir", None),
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(review_result, f, ensure_ascii=False, indent=2)
        print(f"[+] Full career review written to {out_path}", file=sys.stderr if args.json else sys.stdout)

    if args.json:
        print(json.dumps(review_result, ensure_ascii=False, indent=2))
        return

    # Formatted terminal output
    print("=" * 72)
    print("        OfferGet · Full-Lifecycle Career Review (career-review.v1)       ")
    print("=" * 72)
    jdb = review_result["jd_breakdown"]
    ms = review_result["match_summary"]
    print(f"[*] Target Position:    {jdb.get('job_title', 'AI Engineer')} ({jdb.get('company_or_dept', 'Frontier Team')})")
    print(f"[*] Final Match Score:  {round(ms.get('final_match_score', 0.0) * 100, 1)}% (Raw: {round(ms.get('raw_match_score', 0.0) * 100, 1)}%)")
    if ms.get("is_hard_vetoed"):
        print(f"[!] Hard Veto Triggered: {'; '.join(ms.get('hard_veto_reasons', []))}")
    print("-" * 72)

    print("\n[1] Fact-Grounded Resume Advice (No Hallucination):")
    for idx, adv in enumerate(review_result.get("resume_advice", [])[:5], 1):
        print(f"    {idx}. [{adv['state'].upper()}] -> Action: {adv['action']}")
        print(f"       Requirement: {adv['requirement']}")
        print(f"       Grounding:   {adv['grounding_note']}")
        if adv.get("safe_bullet"):
            print(f"       Safe Bullet: {adv['safe_bullet'][:70]}...")

    print("\n[2] Exactly 3 Targeted Interview Defense Questions:")
    for q in review_result.get("interview_questions", []):
        print(f"    • [Q{q['question_id']}] [{q['category']}]: {q['question_zh']}")
        print(f"      Intent:  {q['interviewer_intent']}")
        print(f"      Prep:    {q['prep_keypoints'][:65]}...")

    print("\n[3] Structured Interview Answer Debrief & Feedback:")
    for fb in review_result.get("answer_feedback", []):
        print(f"    • [Q{fb['question_id']}] Status: {fb['status']} | Diagnosis: {fb['diagnosis']}")
        print(f"      Analysis:  {fb['analysis']}")
        if fb.get("candidate_answer"):
            print(f"      Answer:    {fb['candidate_answer'][:50]}...")
        print(f"      Takeaway:  {fb['key_takeaway']}")

    print("\n[4] Focus Polish: Interview Defense:")
    pf = review_result.get("polish_focus", {})
    print(f"    • Focus Area: {pf.get('focus_area')}")
    print(f"    • Description: {pf.get('description')}")
    for cp in pf.get("defense_checkpoints", []):
        print(f"      - {cp}")

    if review_result.get("generated_resumes"):
        print("\n[5] Directly Generated Tailored Resumes:")
        gen = review_result["generated_resumes"]
        if "files" in gen:
            for theme_name, fmap in gen["files"].items():
                p = fmap.get("pdf", "")
                print(f"    ✓ [{theme_name:<16}] -> {p}")
        else:
            p = gen.get("pdf", "")
            t = gen.get("theme", "modern-navy")
            print(f"    ✓ [{t:<16}] -> {p}")
    print("=" * 72)




def cmd_ats_audit(args):
    """Handler for `offerget ats audit <input_file>`."""
    input_path = args.input_file
    if not os.path.exists(input_path):
        print(f"[-] Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    jd_path = args.jd
    if jd_path and not os.path.exists(jd_path):
        print(f"[-] Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)

    result = audit_resume_ats(
        profile_or_text=input_path,
        jd_decoded_or_text=jd_path,
        target_tag=args.tag
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
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
        print(f"[-] Error: Profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(jd_path):
        print(f"[-] Error: JD file not found: {jd_path}", file=sys.stderr)
        sys.exit(1)

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    ledger = generate_skill_ledger(profile_data, jd_text)

    if args.json:
        print(json.dumps(ledger, ensure_ascii=False, indent=2))
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
        print(f"[-] Error: Profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    tailored = filter_profile_by_visibility(profile_data, tag)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(tailored, f, ensure_ascii=False, indent=2)
        print(f"[+] Tailored profile for tag '{tag}' saved to {args.output}")
    else:
        print(json.dumps(tailored, ensure_ascii=False, indent=2))


def cmd_gap_roi(args):
    """Handler for `offerget gap roi <jd_files...> --profile <profile.json>`."""
    profile_path = args.profile
    if not os.path.exists(profile_path):
        print(f"[-] Error: Profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    jd_files = args.jd_files
    for p in jd_files:
        if not os.path.exists(p):
            print(f"[-] Error: JD file not found: {p}", file=sys.stderr)
            sys.exit(1)

    result = calculate_gap_roi(profile_data, jd_files)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
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


def cmd_offer_evaluate(args):
    """Handler for `offerget offer evaluate <offer.json> [--profile <profile.json>]`."""
    offer_path = args.offer_file
    if not os.path.exists(offer_path):
        print(f"[-] Error: Offer file not found: {offer_path}", file=sys.stderr)
        sys.exit(1)

    with open(offer_path, "r", encoding="utf-8") as f:
        offer_data = json.load(f)

    profile_data = None
    if args.profile:
        if not os.path.exists(args.profile):
            print(f"[-] Error: Profile file not found: {args.profile}", file=sys.stderr)
            sys.exit(1)
        with open(args.profile, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

    result = evaluate_offer_package(offer_data, profile_data)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
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


def cmd_offer_counter(args):
    """Handler for `offerget offer counter <offer.json> [--target-base <int>] [--competing <json>]`."""
    offer_path = args.offer_file
    if not os.path.exists(offer_path):
        print(f"[-] Error: Offer file not found: {offer_path}", file=sys.stderr)
        sys.exit(1)

    with open(offer_path, "r", encoding="utf-8") as f:
        offer_data = json.load(f)

    profile_data = None
    if args.profile and os.path.exists(args.profile):
        with open(args.profile, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

    competing = None
    if args.competing and os.path.exists(args.competing):
        with open(args.competing, "r", encoding="utf-8") as f:
            competing = json.load(f)

    negotiator = OfferNegotiator()
    eval_res = negotiator.evaluate_offer(offer_data, profile_data)
    counter_res = negotiator.generate_counter_offer(eval_res, target_base=args.target_base, competing_offers=competing)

    if args.json:
        print(json.dumps(counter_res, ensure_ascii=False, indent=2))
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


def cmd_anon_mask(args):
    """Handler for `offerget anon mask <file>`."""
    input_path = args.input_file
    if not os.path.exists(input_path):
        print(f"[-] Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    is_json = False
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()
    if input_path.endswith(".json") or content.strip().startswith("{"):
        try:
            data = json.loads(content)
            is_json = True
        except Exception:
            data = content
    else:
        data = content

    anonymizer = PrivacyAnonymizer()
    anon_data, deanon_map = anonymizer.anonymize(data, level=args.level)

    if args.map:
        anonymizer.save_map(deanon_map, args.map)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            if is_json:
                json.dump(anon_data, f, ensure_ascii=False, indent=2)
            else:
                f.write(anon_data)
        print(f"[✓] Anonymized data saved to: {args.output}")
        if args.map:
            print(f"[✓] De-anonymization map saved to: {args.map}")
    else:
        if args.json or is_json:
            print(json.dumps(anon_data, ensure_ascii=False, indent=2))
        else:
            print(anon_data)


def cmd_anon_unmask(args):
    """Handler for `offerget anon unmask <file> --map <map_file>`."""
    input_path = args.input_file
    map_path = args.map
    if not os.path.exists(input_path):
        print(f"[-] Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(map_path):
        print(f"[-] Error: De-anonymization map not found: {map_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    is_json = False
    if input_path.endswith(".json") or content.strip().startswith("{"):
        try:
            data = json.loads(content)
            is_json = True
        except Exception:
            data = content
    else:
        data = content

    anonymizer = PrivacyAnonymizer()
    deanon_map = anonymizer.load_map(map_path)
    restored_data = anonymizer.deanonymize(data, deanon_map)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            if is_json:
                json.dump(restored_data, f, ensure_ascii=False, indent=2)
            else:
                f.write(restored_data)
        print(f"[✓] Restored data saved to: {args.output}")
    else:
        if args.json or is_json:
            print(json.dumps(restored_data, ensure_ascii=False, indent=2))
        else:
            print(restored_data)


def cmd_fact_verify(args):
    """Handler for `offerget fact verify <file_or_text> --profile <profile.json>`."""
    profile_path = args.profile
    if not os.path.exists(profile_path):
        print(f"[-] Error: Master profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    with open(profile_path, "r", encoding="utf-8") as f:
        master_profile = json.load(f)

    target_input = args.target
    if os.path.exists(target_input):
        with open(target_input, "r", encoding="utf-8") as f:
            content = f.read()
        if target_input.endswith(".json") or content.strip().startswith("{"):
            try:
                target_data = json.loads(content)
            except Exception:
                target_data = content
        else:
            target_data = content
    else:
        target_data = target_input

    guard = FactVerificationGuard(master_profile)
    result = guard.verify_facts(target_data)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
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


def cmd_defense_simulate(args):
    """Handler for `offerget defense simulate <target> [--profile <profile.json>] [--intensity <先热个身|开始挑刺|严刑拷打>]`."""
    target_input = args.target
    if os.path.exists(target_input):
        with open(target_input, "r", encoding="utf-8") as f:
            content = f.read()
        if target_input.endswith(".json") or content.strip().startswith("{") or content.strip().startswith("["):
            try:
                target_data = json.loads(content)
            except Exception:
                target_data = content
        else:
            target_data = content
    else:
        target_data = target_input

    profile_data = None
    if args.profile:
        if not os.path.exists(args.profile):
            print(f"[-] Error: Profile file not found: {args.profile}", file=sys.stderr)
            sys.exit(1)
        with open(args.profile, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

    simulator = DefenseSimulator(profile_context=profile_data)
    result = simulator.simulate(
        project_input=target_data,
        intensity=args.intensity or "开始挑刺",
        scenario=args.scenario or "技术 / 简历面试"
    )

    if args.output:
        md_text = result.to_markdown()
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md_text)
        print(f"[+] Defense simulation report saved to: {args.output}")

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print("=" * 68)
    print("        OfferGet · Project Defense & Red-Team Simulator          ")
    print("=" * 68)
    print(f"[*] Project Name:   {result.project_name}")
    print(f"[*] Intensity:      {result.intensity}")
    print(f"[*] Scenario:       {result.scenario}")
    print(f"[*] Claims Audited: {result.summary_stats.get('total_claims', 0)} total "
          f"({result.summary_stats.get('supported_count', 0)} supported, "
          f"{result.summary_stats.get('implied_count', 0)} implied, "
          f"{result.summary_stats.get('missing_count', 0)} missing)")
    print(f"[*] Risk Profile:   {result.summary_stats.get('high_risk_count', 0)} High | "
          f"{result.summary_stats.get('medium_risk_count', 0)} Medium | "
          f"{result.summary_stats.get('low_risk_count', 0)} Low")
    print("-" * 68)
    print("【项目一句话定位】")
    print(f"  {result.one_sentence_positioning}")
    print("-" * 68)
    print(f"【高风险证据缺口 (Top {len(result.high_risk_gaps)})】")
    for idx, gap in enumerate(result.high_risk_gaps[:3], 1):
        print(f"  {idx}. [{gap.get('risk_level')}] {gap.get('category_zh')} - {gap.get('title')}")
        print(f"     • 缺口: {gap.get('gap')}")
        print(f"     • 状态: {gap.get('evidence_status')} ({gap.get('risk_basis')})")
    print("-" * 68)
    print("【连续追问链精选】")
    if result.follow_up_chains:
        chain = result.follow_up_chains[0]
        print(f"  • 追问目标: {chain.target_claim[:40]}...")
        for r in chain.rounds:
            print(f"    - {r.title}:")
            print(f"      “{r.question}”")
    print("-" * 68)
    print("【答辩速查卡 (摘要)】")
    if result.defense_cheat_sheet:
        for vuln in result.defense_cheat_sheet.top_vulnerabilities[:2]:
            print(f"  • 软肋: {vuln.get('vulnerability')}")
            print(f"    底线: {vuln.get('bottom_line')}")
    print("=" * 68)
    if not args.output:
        print("[*] 提示: 增加 `--output report.md` 可导出完整 7 章节答辩红蓝对抗报告。")


def cmd_baoyan_audit(args):
    """Handler for `offerget baoyan audit <entry_or_file> [--role <role>] [--tier <tier>] [--material <file>]`."""
    target_input = args.entry
    material_text = None
    if os.path.exists(target_input):
        with open(target_input, "r", encoding="utf-8") as f:
            entry_text = f.read()
    else:
        entry_text = target_input

    if args.material:
        if os.path.exists(args.material):
            with open(args.material, "r", encoding="utf-8") as f:
                material_text = f.read()
        else:
            material_text = args.material

    result = audit_baoyan_entry(
        entry=entry_text,
        role=args.role,
        target_tier=args.tier or "简历版",
        material=material_text
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 68)
    print("      OfferGet · Chinese Academic Integrity & Word-Count Auditor      ")
    print("=" * 68)
    badge = "✅ 审计通过 (PASSED)" if result["passed"] else "❌ 触发红线 (VIOLATIONS)"
    print(f"[*] 综合结论:        {badge}")
    print(f"[*] 目标规格:        {result['target_tier']}")
    print(f"[*] 当前字数:        {result['word_count']} 字")
    print("-" * 68)

    checks = result.get("checks", {})
    print("【4 大学术诚信审查】")
    sim = checks.get("simulation_vs_real_cluster", {})
    print(f"  1. 仿真 vs 实机集群隔离:   {'✅ 正常' if sim.get('passed') else '❌ 违规'}")
    if not sim.get("passed") and "message" in sim:
        print(f"     • {sim['message']}")

    exp = checks.get("expected_vs_acquired_outcomes", {})
    print(f"  2. 在投 vs 录用成果隔离:   {'✅ 正常' if exp.get('passed') else '❌ 违规'}")
    if not exp.get("passed") and "message" in exp:
        print(f"     • {exp['message']}")

    rv = checks.get("role_verb_hierarchy", {})
    print(f"  3. 团队位次与动词授权匹配: {'✅ 正常' if rv.get('passed') else '❌ 违规'}")
    if not rv.get("passed") and "message" in rv:
        print(f"     • {rv['message']}")

    bz = checks.get("academic_buzzwords_forbidden", {})
    print(f"  4. 空洞大词与学术吹捧审查: {'✅ 正常' if bz.get('passed') else '❌ 违规'}")
    if not bz.get("passed") and "found_buzzwords" in bz:
        print(f"     • 违规词: {bz['found_buzzwords']}")

    print("-" * 68)
    typo = checks.get("typography", {})
    print(f"【中文学术排版与标点】:     {'✅ 符合规范' if typo.get('passed') else '⚠️ 发现排版标点问题'}")
    if not typo.get("passed") and "issues" in typo:
        for issue in typo["issues"]:
            if isinstance(issue, dict):
                print(f"  • {issue.get('message')}")
            else:
                print(f"  • {issue}")

    if "numerical_provenance" in checks:
        prov = checks["numerical_provenance"]
        print("-" * 68)
        print(f"【数值原始出处追溯】:       {'✅ 数据全部属实' if prov.get('passed') else '⚠️ 存在未佐证指标'}")
        if prov.get("missing_numbers"):
            print(f"  • 未在证明材料中找到佐证的数值: {prov['missing_numbers']}")
    print("=" * 68)


def cmd_baoyan_compress(args):
    """Handler for `offerget baoyan compress <entry_or_file> --tier <摘要版|简历版|陈述版>`."""
    target_input = args.entry
    if os.path.exists(target_input):
        with open(target_input, "r", encoding="utf-8") as f:
            entry_text = f.read()
    else:
        entry_text = target_input

    result = compress_baoyan_entry(entry_text, target_tier=args.tier)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 68)
    print(f"       OfferGet · Baoyan Word-Count Compressor ({args.tier})       ")
    print("=" * 68)
    print(f"[*] 原始字数:   {result['original_count']} 字")
    print(f"[*] 压缩后字数: {result['compressed_count']} 字 (目标区间: {result['tier_range'][0]}-{result['tier_range'][1]} 字)")
    print(f"[*] 达成状态:   {'✅ 成功达标' if result['is_in_range'] else '⚠️ 需微调'}")
    print(f"[*] 压缩率:     {result['compression_ratio']}")
    print("-" * 68)
    print("【压缩后推荐文本】")
    print(result["compressed_text"])
    print("=" * 68)


def cmd_baoyan_advisor(args):
    """Handler for `offerget baoyan advisor <advisor.json> --profile <profile.json> [--scenario <scenario>]`."""
    if not os.path.exists(args.advisor):
        print(f"[-] Error: Advisor profile not found: {args.advisor}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.profile):
        print(f"[-] Error: Candidate profile not found: {args.profile}", file=sys.stderr)
        sys.exit(1)

    with open(args.advisor, "r", encoding="utf-8") as f:
        adv_data = json.load(f)
    with open(args.profile, "r", encoding="utf-8") as f:
        prof_data = json.load(f)

    result = match_advisor_and_draft_email(
        advisor_data=adv_data,
        candidate_data=prof_data,
        email_scenario=args.scenario or "summer_camp"
    )

    email = result.get("outreach_email", {})
    match_info = result.get("intersection_match", {})

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(email.get("body", ""))
        print(f"[+] Outreach email saved to: {args.output}")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 68)
    print("         OfferGet · Chinese Advisor Matcher & Outreach Studio     ")
    print("=" * 68)
    print(f"[*] 目标导师:       {adv_data.get('name')} ({adv_data.get('title', '教授')} - {adv_data.get('institution', '')})")
    cand = prof_data.get("candidate", {})
    print(f"[*] 候选人:         {cand.get('name')} ({cand.get('university', '')} - {cand.get('major', '')})")
    print(f"[*] 学术匹配重合度: {match_info.get('intersection_score', 0)} %")
    print("-" * 68)
    print("【学术交集与核心重合点】")
    for topic in match_info.get("mutual_research_topics", []):
        print(f"  • 共同研究方向: {topic}")
    for overlap in match_info.get("technical_overlaps", [])[:3]:
        print(f"  • 技术重合: {overlap}")
    if match_info.get("strategic_attack_angle"):
        print(f"  • 进攻策略: {match_info['strategic_attack_angle']}")
    print("-" * 68)
    print("【生成的高情商导师学术自荐信】")
    print(f"主题: {email.get('subject', '')}")
    print("-" * 40)
    print(email.get("body", ""))
    print("-" * 68)
    anti_rep = result.get("anti_hallucination_report", {})
    print(f"【学术真实性审计】:   {anti_rep.get('audit_verdict', '正常')}")
    print("【防鸽与学术信誉红线提示】")
    print("  • 严禁群发相同套磁信；收到导师肯定性回复后须在 24-48 小时内确认")
    print("  • 若获得更好 offer，须在第一时间书面礼貌致歉并释放名额，切忌拖延至九推系统关闭")
    print("=" * 68)


def cmd_baoyan_checklist(args):
    """Handler for `offerget baoyan checklist --profile <profile.json> [--stage <stage>] [--track <track>]`."""
    if not os.path.exists(args.profile):
        print(f"[-] Error: Profile file not found: {args.profile}", file=sys.stderr)
        sys.exit(1)

    with open(args.profile, "r", encoding="utf-8") as f:
        prof_data = json.load(f)

    stage = args.stage or "夏令营"
    track = args.track or "直博"
    checklist = generate_camp_checklist(prof_data, stage=stage, track=track)

    if args.json:
        print(json.dumps(checklist, ensure_ascii=False, indent=2))
        return

    print("=" * 68)
    print(f"       OfferGet · Baoyan & Postgraduate Admission Checklist       ")
    print("=" * 68)
    print(f"[*] 候选人:     {checklist.get('candidate_name', '申请人')}")
    print(f"[*] 申请阶段:   {checklist['stage']}")
    print(f"[*] 报考通道:   {checklist['track']}")
    print(f"[*] 准备完成率: {checklist['readiness_percentage']}% ({checklist['ready_items']}/{checklist['total_items']} 项已就绪)")
    print("-" * 68)

    category_names = {
        "mandatory_materials": "基础必备证件与官方学业证明",
        "academic_proofs": "学术论文、在投证明与竞赛专利资产",
        "expert_recommendations": "专家推荐信 (正/副高职称亲笔签名)",
        "presentation_and_interview": "自我介绍PPT、中英文答辩与白板推导",
        "administrative_and_logistics": "报名系统状态跟踪与考务差旅行程"
    }

    for cat_key, items_list in checklist["categories"].items():
        cat_title = category_names.get(cat_key, cat_key)
        print(f"【{cat_title}】({len(items_list)} 项)")
        for item in items_list:
            crit = "⚠️ [关键必具]" if item.get("importance") == "CRITICAL" else "• [标准准备]"
            status_badge = "✅" if item.get("status") == "READY" else "⏳"
            print(f"  {status_badge} {crit} {item.get('name', item.get('item_id'))}")
            print(f"     说明: {item.get('requirement', '')}")
        print()
    print("=" * 68)


def cmd_resume_build(args_list):
    """Build multi-template resumes from candidate profile."""
    from core.resume_builder import ResumeBuilder

    build_parser = argparse.ArgumentParser(
        prog="offerget resume build",
        description="Build multi-template resumes (PDF & HTML) from candidate profile",
    )
    build_parser.add_argument("profile", help="Path to candidate profile JSON (minimal or standard)")
    build_parser.add_argument(
        "--theme",
        default="all",
        choices=["all", "modern-navy", "silicon-clean", "classic-tech", "ats-plain", "academic-latex", "academic-typst"],
        help="Resume theme to build (default: all)",
    )
    build_parser.add_argument(
        "--output-dir",
        default="output/resumes",
        help="Output directory to save generated resumes (default: output/resumes)",
    )
    build_parser.add_argument("--no-photo", action="store_true", help="Do not reserve photo slot")
    build_parser.add_argument("--photo-path", default=None, help="Path to candidate photo image (jpg/png/webp)")
    build_parser.add_argument(
        "--anonymize",
        default=None,
        choices=["standard", "strict"],
        help="Privacy anonymization level ('standard' or 'strict')",
    )
    build_parser.add_argument("--no-autofit", action="store_true", help="Disable single-page AutoFit compaction")

    parsed = build_parser.parse_args(args_list)

    profile_path = Path(parsed.profile)
    if not profile_path.exists():
        print(f"[-] Error: Profile file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(parsed.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    builder = ResumeBuilder(
        profile_path,
        photo_path=parsed.photo_path,
        anonymize=parsed.anonymize,
    )
    cand_name = builder.profile["candidate"].get("name", "候选人")
    target_role = builder.profile["candidate"].get("title", "运营岗")

    photo_status = 'Disabled' if parsed.no_photo else ('Custom image' if parsed.photo_path else 'Reserved placeholder')

    print("=" * 68)
    print("             OfferGet · Multi-Template Resume Builder            ")
    print("=" * 68)
    print(f"[*] Candidate:   {cand_name}")
    print(f"[*] Target Role: {target_role}")
    print(f"[*] Output Dir:  {out_dir}")
    print(f"[*] Photo Slot:  {photo_status}")
    print(f"[*] Anonymize:   {parsed.anonymize or 'Disabled'}")
    print(f"[*] AutoFit:     {'Disabled' if parsed.no_autofit else 'Enabled'}")
    print("-" * 68)

    photo = not parsed.no_photo
    autofit = not parsed.no_autofit

    if parsed.theme == "all":
        results = builder.build_all(out_dir, photo=photo, autofit=autofit)
        for theme_name, files in results.items():
            pdf_name = files.get("pdf", Path("")).name
            print(f"  ✓ [{theme_name:<16}] -> {pdf_name}")
    else:
        files = builder.build_theme(parsed.theme, out_dir, photo=photo, autofit=autofit)
        pdf_name = files.get("pdf", Path("")).name
        print(f"  ✓ [{parsed.theme:<16}] -> {pdf_name}")

    print("=" * 68)
    print(f"🎉 Successfully built resume variant(s) in {out_dir}")
    print("=" * 68)


def cmd_resume_passthrough(unknown_args):
    """Passes through any `offerget resume ...` command directly to ApexResume/cli.py."""
    apex_cli = CURRENT_DIR / "ApexResume" / "cli.py"
    if not apex_cli.exists():
        print(f"[-] Error: ApexResume submodule not found at {apex_cli}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(apex_cli)] + unknown_args
    proc = subprocess.run(cmd, cwd=str(CURRENT_DIR / "ApexResume"))
    sys.exit(proc.returncode)


def cmd_selftest(args):

    """Runs OfferGet unified selftest: OfferGet core engines + ATS Auditor + ApexResume test suite."""
    print("=" * 68)
    print("              OfferGet Unified Environment Self-Test             ")
    print("=" * 68)
    print(f"[1/6] Python Runtime: {sys.version.split()[0]} ({sys.platform})")

    # 1. Test JD Decoder
    print("[2/6] Testing JD Decoder on sample_ai_jd.txt ...")
    sample_jd_path = CURRENT_DIR / "examples" / "sample_ai_jd.txt"
    if not sample_jd_path.exists():
        print("[-] Error: sample_ai_jd.txt missing!", file=sys.stderr)
        sys.exit(1)
    with open(sample_jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    decoded = decode_jd(jd_text)
    assert "layers" in decoded and len(decoded["layers"]) == 5, "JD Decoder must yield 5 layers!"
    print(f"      ✓ 5-Layer decomposition verified ({len(decoded['detected_signals'])} hidden signals detected)")

    # 2. Test JD Matcher
    print("[3/6] Testing JD Matcher against candidate_profile.json ...")
    sample_profile_path = CURRENT_DIR / "examples" / "candidate_profile.json"
    if not sample_profile_path.exists():
        print("[-] Error: candidate_profile.json missing!", file=sys.stderr)
        sys.exit(1)
    with open(sample_profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    match_result = match_profile_to_jd(decoded, profile_data)
    assert match_result["overall_match_score"] > 80, "Match score should be > 80"
    print(f"      ✓ Match Matrix verified (Overall: {match_result['overall_match_score']}%, Interview Prob: {match_result['interview_prob']}%)")

    # 3. Test Report Generator & Bilingual Validator
    print("[4/6] Testing Report Generator & Bilingual Twin Validator ...")
    template_path = CURRENT_DIR / "templates" / "offer_strategy.html"
    test_out = CURRENT_DIR / "tests" / "test_output_report.html"
    generate_report(decoded, match_result, str(template_path), str(test_out))

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
    print("[5/6] Testing ATS Auditor & Three-State Skill Ledger ...")
    ats_result = audit_resume_ats(str(sample_profile_path), str(sample_jd_path))
    assert ats_result["overall_score"] >= 75.0, f"ATS overall score should be >= 75, got {ats_result['overall_score']}"
    assert ats_result["verdict"] == "READY_TO_SEND", f"Verdict should be READY_TO_SEND, got {ats_result['verdict']}"
    print(f"      ✓ ATS Quality Gate verified (Score: {ats_result['overall_score']}/100, Verdict: {ats_result['verdict']})")

    ats_res = audit_resume_ats(profile_data, decoded, target_tag="always")
    assert ats_res["verdict"] == "READY_TO_SEND", f"ATS verdict should be READY_TO_SEND, got {ats_res['verdict']}"
    assert ats_res["overall_score"] >= 75.0, f"ATS overall score should be >= 75, got {ats_res['overall_score']}"
    assert "skill_ledger" in ats_res and len(ats_res["skill_ledger"]["present"]) > 0, "Skill ledger must detect present skills"
    print(f"      ✓ ATS Auditor verified (Score: {ats_res['overall_score']}, Verdict: {ats_res['verdict']}, Ledger: {ats_res['skill_ledger']['summary']['present_count']} verified)")

    # 5. Test Privacy Anonymizer
    print("[6/8] Testing Privacy Anonymizer (Standard & Strict) ...")
    anon_p, deanon_m = anonymize_profile(profile_data, level="strict")
    assert anon_p["candidate"]["name"] == "Dr. Alex Chen", "Candidate name must be pseudonymized"
    restored_p = deanonymize_text(anon_p, deanon_m)
    assert restored_p == profile_data, "De-anonymization must restore profile 100%"
    print(f"      ✓ Privacy Anonymizer verified: Reversible pseudonymization confirmed")

    # 6. Test Fact Verification Guard
    print("[7/8] Testing Fact Verification Guard ...")
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
    audit_res = audit_baoyan_entry(test_entry, role="核心成员", target_tier="简历版")
    assert audit_res["passed"] is True, f"Legitimate entry must pass: {audit_res['violations']}"
    # Test illegal simulation conflation
    fake_entry = "负责利用 Gazebo 仿真环境搭建万卡集群产线实测系统。"
    fake_res = audit_baoyan_entry(fake_entry, role="参赛队员", target_tier="简历版")
    assert fake_res["passed"] is False, "Simulation vs cluster conflation must be flagged"
    long_entry = (
        "针对移动机器人在未知复杂动态环境下的自主导航难题，在本项目中，作为核心成员，"
        "设计并实现了一种基于改进PPO与局部路径规划融合的导航算法。搭建仿真测试平台，"
        "通过深入研究，最终仿真测试表明，避障成功率达到94.8%，规划延迟降低至32ms，荣获国家一等奖。"
    )
    comp_res = compress_baoyan_entry(long_entry, target_tier="摘要版")
    assert comp_res["is_in_range"] is True, f"Compressor must meet bounds: {comp_res}"
    print(f"      ✓ Baoyan Auditor verified: 4 integrity redlines enforced & 3-tier compression working")

    # 8. Test Baoyan Pipeline & Academic Candidate Schema
    print("[9/11] Testing Baoyan Pipeline & Academic Profile Schema ...")
    acad_profile_path = CURRENT_DIR / "examples" / "academic_profile.json"
    assert acad_profile_path.exists(), "academic_profile.json must exist"
    with open(acad_profile_path, "r", encoding="utf-8") as f:
        acad_profile = json.load(f)
    v_acad = validate_academic_profile(acad_profile)
    assert v_acad["valid"] is True, f"Academic profile schema must be valid: {v_acad['errors']}"
    assert v_acad["competitiveness_score"] >= 90.0, "Top tier academic profile should score >= 90"
    checklist = generate_camp_checklist(acad_profile, stage="夏令营", track="直博")
    assert checklist["total_items"] >= 5, "Checklist must contain categorized items"
    print(f"      ✓ Baoyan Pipeline verified: Academic schema valid (Score: {v_acad['competitiveness_score']}/100, Checklist: {checklist['total_items']} items)")

    # 9. Test Advisor Matcher & Outreach Email Generator
    print("[10/11] Testing Chinese Advisor Matcher & Outreach Generator ...")
    adv_path = CURRENT_DIR / "examples" / "sample_advisor.json"
    assert adv_path.exists(), "sample_advisor.json must exist"
    with open(adv_path, "r", encoding="utf-8") as f:
        sample_adv = json.load(f)
    match_adv = match_advisor_and_draft_email(sample_adv, acad_profile, email_scenario="summer_camp")
    match_score = match_adv["intersection_match"]["intersection_score"]
    assert match_score >= 60.0, f"Matching score should be >= 60, got {match_score}"
    email_body = match_adv["outreach_email"]["body"]
    assert "NeurIPS 2024" in email_body or "陈老师" in email_body, "Outreach email must be generated"
    print(f"      ✓ Advisor Matcher verified: Overlap {match_score}%, High-EQ outreach email drafted")

    # 10. ApexResume Selftest
    print("\n[11/11] Invoking ApexResume Independent Subsystem Self-Test...")
    apex_cli = CURRENT_DIR / "ApexResume" / "cli.py"
    if not apex_cli.exists():
        print(f"[-] Error: ApexResume not found at {apex_cli}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(apex_cli), "selftest"]
    proc = subprocess.run(cmd, cwd=str(CURRENT_DIR / "ApexResume"))
    if proc.returncode != 0:
        print("[-] ApexResume self-test failed!", file=sys.stderr)
        sys.exit(proc.returncode)

    print("\n" + "=" * 68)
    print("🎉 ALL TESTS PASSED! OfferGet & ApexResume Dual-Track System Fully Verified!")
    print("=" * 68)


def main():
    parser = argparse.ArgumentParser(
        prog="offerget",
        description="OfferGet - Strategic Job Description Decoding, Match Scoring & Offer Strategy OS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  offerget jd decode examples/sample_ai_jd.txt
  offerget jd match examples/sample_ai_jd.txt --profile examples/candidate_profile.json
  offerget jd report examples/sample_ai_jd.txt --profile examples/candidate_profile.json --output report.html
  offerget ats audit examples/candidate_profile.json --jd examples/sample_ai_jd.txt
  offerget resume selftest
  offerget selftest
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # `offerget jd ...`
    jd_parser = subparsers.add_parser("jd", help="Job Description operations")
    jd_subparsers = jd_parser.add_subparsers(dest="jd_command", help="JD subcommands")

    # `offerget jd decode`
    decode_parser = jd_subparsers.add_parser("decode", help="Decode JD into 5 layers")
    decode_parser.add_argument("jd_file", help="Path to JD text file")
    decode_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget jd match`
    match_parser = jd_subparsers.add_parser("match", help="Match profile against JD")
    match_parser.add_argument("jd_file", help="Path to JD text file")
    match_parser.add_argument("--profile", required=True, help="Path to candidate_profile.json")
    match_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget jd report`
    report_parser = jd_subparsers.add_parser("report", help="Generate bilingual HTML report")
    report_parser.add_argument("jd_file", help="Path to JD text file")
    report_parser.add_argument("--profile", required=True, help="Path to candidate_profile.json")
    report_parser.add_argument("--output", default="report.html", help="Output HTML filepath")
    report_parser.add_argument("--template", help="Custom HTML template filepath")

    # `offerget ats ...`
    ats_parser = subparsers.add_parser("ats", help="ATS Auditor & verification operations")
    ats_subparsers = ats_parser.add_subparsers(dest="ats_command", help="ATS subcommands")

    # `offerget ats audit`
    ats_audit_parser = ats_subparsers.add_parser("audit", help="Audit candidate profile or resume against ATS standards")
    ats_audit_parser.add_argument("input_file", help="Path to candidate profile JSON or resume text")
    ats_audit_parser.add_argument("--jd", help="Path to target Job Description text file")
    ats_audit_parser.add_argument("--tag", help="Visibility tag to filter (e.g. ai_pretrain, always)")
    ats_audit_parser.add_argument("--json", action="store_true", help="Output raw JSON audit result")

    # `offerget ats ledger`
    ats_ledger_parser = ats_subparsers.add_parser("ledger", help="Generate 3-state skill ledger (Verified vs Claimed vs Gap)")
    ats_ledger_parser.add_argument("profile", help="Path to candidate profile JSON")
    ats_ledger_parser.add_argument("--jd", required=True, help="Path to target Job Description text file")
    ats_ledger_parser.add_argument("--json", action="store_true", help="Output raw JSON ledger")

    # `offerget ats filter`
    ats_filter_parser = ats_subparsers.add_parser("filter", help="Filter master profile by visibility tag")
    ats_filter_parser.add_argument("profile", help="Path to candidate profile JSON")
    ats_filter_parser.add_argument("--tag", required=True, help="Target visibility tag (e.g. ai_pretrain, agentic_systems)")
    ats_filter_parser.add_argument("--output", help="Output JSON filepath (default: stdout)")

    # `offerget gap ...`
    gap_parser = subparsers.add_parser("gap", help="Skill Gap ROI and Near-Miss analysis")
    gap_subparsers = gap_parser.add_subparsers(dest="gap_command", help="Gap subcommands")
    gap_roi_parser = gap_subparsers.add_parser("roi", help="Calculate Skill Gap ROI for near-miss opportunities")
    gap_roi_parser.add_argument("jd_files", nargs="+", help="Path(s) to JD text file(s)")
    gap_roi_parser.add_argument("--profile", required=True, help="Path to candidate_profile.json")
    gap_roi_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget offer ...`
    offer_parser = subparsers.add_parser("offer", help="Offer evaluation, contract trap detection & counter-offer")
    offer_subparsers = offer_parser.add_subparsers(dest="offer_command", help="Offer subcommands")
    
    offer_eval_parser = offer_subparsers.add_parser("evaluate", help="Evaluate offer package & detect 6 contract traps")
    offer_eval_parser.add_argument("offer_file", help="Path to offer JSON file")
    offer_eval_parser.add_argument("--profile", help="Path to candidate profile JSON")
    offer_eval_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    offer_counter_parser = offer_subparsers.add_parser("counter", help="Generate high-EQ tactical counter-offer letter & script")
    offer_counter_parser.add_argument("offer_file", help="Path to offer JSON file")
    offer_counter_parser.add_argument("--profile", help="Path to candidate profile JSON")
    offer_counter_parser.add_argument("--target-base", type=float, help="Desired monthly base salary (RMB)")
    offer_counter_parser.add_argument("--competing", help="Path to competing offers JSON file")
    offer_counter_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget anon ...`
    anon_parser = subparsers.add_parser("anon", help="Privacy anonymizer and reversible tokenization")
    anon_subparsers = anon_parser.add_subparsers(dest="anon_command", help="Anon subcommands")

    anon_mask_parser = anon_subparsers.add_parser("mask", help="Anonymize profile JSON or resume text")
    anon_mask_parser.add_argument("input_file", help="Path to input JSON profile or text file")
    anon_mask_parser.add_argument("--level", choices=["standard", "strict"], default="strict", help="Sensitivity level")
    anon_mask_parser.add_argument("--map", help="Path to save de-anonymization mapping JSON")
    anon_mask_parser.add_argument("--output", help="Path to save anonymized output file")
    anon_mask_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    anon_unmask_parser = anon_subparsers.add_parser("unmask", help="Restore anonymized profile or text using mapping")
    anon_unmask_parser.add_argument("input_file", help="Path to anonymized file")
    anon_unmask_parser.add_argument("--map", required=True, help="Path to de-anonymization mapping JSON file")
    anon_unmask_parser.add_argument("--output", help="Path to save restored output file")
    anon_unmask_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget fact ...`
    fact_parser = subparsers.add_parser("fact", help="Fact verification & anti-hallucination guard")
    fact_subparsers = fact_parser.add_subparsers(dest="fact_command", help="Fact subcommands")

    fact_verify_parser = fact_subparsers.add_parser("verify", help="Verify tailored resume bullets against SSOT profile")
    fact_verify_parser.add_argument("target", help="Tailored resume text, bullet, or file path")
    fact_verify_parser.add_argument("--profile", required=True, help="Path to SSOT candidate_profile.json")
    fact_verify_parser.add_argument("--json", action="store_true", help="Output raw JSON report")

    # `offerget defense ...`
    defense_parser = subparsers.add_parser("defense", help="Project defense interrogation & red-team simulator")
    defense_subparsers = defense_parser.add_subparsers(dest="defense_command", help="Defense subcommands")

    defense_sim_parser = defense_subparsers.add_parser("simulate", help="Simulate project defense interrogation against claims")
    defense_sim_parser.add_argument("target", help="Project description text, claim list, or file path")
    defense_sim_parser.add_argument("--profile", help="Path to SSOT candidate_profile.json")
    defense_sim_parser.add_argument("--intensity", default="开始挑刺", choices=["先热个身", "开始挑刺", "严刑拷打", "warmup", "critical", "hell"], help="Interrogation intensity level")
    defense_sim_parser.add_argument("--scenario", default="技术 / 简历面试", help="Defense scenario")
    defense_sim_parser.add_argument("--output", help="Save full 7-section Markdown report to file")
    defense_sim_parser.add_argument("--json", action="store_true", help="Output raw JSON report")

    # `offerget baoyan ...`
    baoyan_parser = subparsers.add_parser("baoyan", help="Chinese Baoyan / Postgraduate Academic Application OS")
    baoyan_subparsers = baoyan_parser.add_subparsers(dest="baoyan_command", help="Baoyan subcommands")

    # `offerget baoyan audit`
    baoyan_audit_parser = baoyan_subparsers.add_parser("audit", help="Audit academic resume entry for integrity & word-count")
    baoyan_audit_parser.add_argument("entry", help="Resume text entry or file path")
    baoyan_audit_parser.add_argument("--role", help="Team role (项目负责人, 核心成员, 参赛队员, 辅助成员)")
    baoyan_audit_parser.add_argument("--tier", default="简历版", choices=["摘要版", "简历版", "陈述版"], help="Target length tier")
    baoyan_audit_parser.add_argument("--material", help="Source proof material text or file path for numerical tracing")
    baoyan_audit_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget baoyan compress`
    baoyan_compress_parser = baoyan_subparsers.add_parser("compress", help="Compress academic entry to strict word count tier")
    baoyan_compress_parser.add_argument("entry", help="Text entry or file path to compress")
    baoyan_compress_parser.add_argument("--tier", default="简历版", choices=["摘要版", "简历版", "陈述版"], help="Target length tier")
    baoyan_compress_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget baoyan advisor`
    baoyan_adv_parser = baoyan_subparsers.add_parser("advisor", help="Match professor profile and generate high-EQ outreach email")
    baoyan_adv_parser.add_argument("advisor", help="Path to advisor JSON file")
    baoyan_adv_parser.add_argument("--profile", required=True, help="Path to academic_profile.json")
    baoyan_adv_parser.add_argument("--scenario", default="summer_camp", choices=["summer_camp", "pre_recommendation", "postgraduate_reexam", "phd_application"], help="Application scenario")
    baoyan_adv_parser.add_argument("--output", help="Path to save outreach email text")
    baoyan_adv_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget baoyan checklist`
    baoyan_check_parser = baoyan_subparsers.add_parser("checklist", help="Generate summer camp / re-examination checklist")
    baoyan_check_parser.add_argument("--profile", required=True, help="Path to academic_profile.json")
    baoyan_check_parser.add_argument("--stage", default="夏令营", choices=["夏令营", "预推免", "九推", "统考复试"], help="Application stage")
    baoyan_check_parser.add_argument("--track", default="直博", choices=["直博", "学硕", "专硕"], help="Target track")
    baoyan_check_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget review ...`
    review_parser = subparsers.add_parser("review", help="Full-lifecycle career review pipeline (Track 2 closed-loop)")
    review_parser.add_argument("jd_file", help="Path to JD text file")
    review_parser.add_argument("--profile", required=True, help="Path to candidate_profile.json")
    review_parser.add_argument("--answers", help="Optional path to interview answers JSON")
    review_parser.add_argument("--output", help="Optional output JSON file path")
    review_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    review_parser.add_argument("--build-resume", action="store_true", help="Directly build tailored resume PDF using review safe bullets")
    review_parser.add_argument(
        "--resume-theme",
        default="modern-navy",
        choices=["all", "modern-navy", "silicon-clean", "classic-tech", "ats-plain", "academic-latex", "academic-typst"],
        help="Theme for tailored resume (default: modern-navy)",
    )
    review_parser.add_argument("--resume-output-dir", default=None, help="Custom output directory for tailored resumes")


    # `offerget resume ...`
    resume_parser = subparsers.add_parser("resume", help="Passthrough directly to ApexResume CLI")

    # `offerget selftest`
    selftest_parser = subparsers.add_parser("selftest", help="Run comprehensive OfferGet & ApexResume tests")

    # Special handling for `offerget resume ...`
    if len(sys.argv) > 1 and sys.argv[1] == "resume":
        if len(sys.argv) > 2 and sys.argv[2] == "build":
            cmd_resume_build(sys.argv[3:])
            return
        cmd_resume_passthrough(sys.argv[2:])
        return


    args = parser.parse_args()

    if args.command == "review":
        cmd_career_review(args)
    elif args.command == "jd":
        if args.jd_command == "decode":
            cmd_jd_decode(args)
        elif args.jd_command == "match":
            cmd_jd_match(args)
        elif args.jd_command == "report":
            cmd_jd_report(args)
        else:
            jd_parser.print_help()
    elif args.command == "ats":
        if args.ats_command == "audit":
            cmd_ats_audit(args)
        elif args.ats_command == "ledger":
            cmd_ats_ledger(args)
        elif args.ats_command == "filter":
            cmd_ats_filter(args)
        else:
            ats_parser.print_help()
    elif args.command == "gap":
        if args.gap_command == "roi":
            cmd_gap_roi(args)
        else:
            gap_parser.print_help()
    elif args.command == "offer":
        if args.offer_command == "evaluate":
            cmd_offer_evaluate(args)
        elif args.offer_command == "counter":
            cmd_offer_counter(args)
        else:
            offer_parser.print_help()
    elif args.command == "anon":
        if args.anon_command == "mask":
            cmd_anon_mask(args)
        elif args.anon_command == "unmask":
            cmd_anon_unmask(args)
        else:
            anon_parser.print_help()
    elif args.command == "fact":
        if args.fact_command == "verify":
            cmd_fact_verify(args)
        else:
            fact_parser.print_help()
    elif args.command == "defense":
        if args.defense_command == "simulate":
            cmd_defense_simulate(args)
        else:
            defense_parser.print_help()
    elif args.command == "baoyan":
        if args.baoyan_command == "audit":
            cmd_baoyan_audit(args)
        elif args.baoyan_command == "compress":
            cmd_baoyan_compress(args)
        elif args.baoyan_command == "advisor":
            cmd_baoyan_advisor(args)
        elif args.baoyan_command == "checklist":
            cmd_baoyan_checklist(args)
        else:
            baoyan_parser.print_help()
    elif args.command == "selftest":
        cmd_selftest(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
