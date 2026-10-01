#!/usr/bin/env python3
"""
OfferGet Master CLI - Job Description Decoding, Match Scoring, Report Generation & ApexResume Integration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from presentation.commands import (
    cmd_advisor_match,
    cmd_anon_mask,
    cmd_anon_profile,
    cmd_anon_unmask,
    cmd_application_add,
    cmd_application_list,
    cmd_application_show,
    cmd_application_snapshot,
    cmd_application_status,
    cmd_application_outcome,
    cmd_application_outcomes,
    cmd_application_insights,
    cmd_application_versions,
    cmd_application_version_diff,
    cmd_ats_audit,
    cmd_ats_filter,
    cmd_ats_ledger,
    cmd_baoyan_advisor,
    cmd_baoyan_audit,
    cmd_baoyan_checklist,
    cmd_baoyan_compress,
    cmd_career_review,
    cmd_defense_simulate,
    cmd_fact_verify,
    cmd_gap_roi,
    cmd_jd_decode,
    cmd_jd_match,
    cmd_jd_report,
    cmd_offer_counter,
    cmd_offer_eval,
    cmd_offer_evaluate,
    cmd_proposal_accept,
    cmd_proposal_list,
    cmd_proposal_reject,
    cmd_proposal_show,
    cmd_rendercv_export,
    cmd_rendercv_import,
    cmd_resume_build,
    cmd_resume_passthrough,
    cmd_selftest,
    cmd_doctor,
    cmd_diff_audit,
    cmd_profile_parse,
)



def build_parser() -> argparse.ArgumentParser:
    """Build and return the complete ArgumentParser for OfferGet CLI."""
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
  offerget review examples/sample_ai_jd.txt --profile examples/candidate_profile.json --proposal-db offers.db --application-id APP-001
  offerget proposal accept MP-AB12CD --profile examples/candidate_profile.json --jd examples/sample_ai_jd.txt --output tailored_profile.json
  offerget application add APP-001 --company "示例科技" --role "后端工程师"
  offerget application outcome APP-001 --stage interview --result rejected --tags system_design,communication
  offerget application insights --json
  offerget rendercv import rendercv.json --output profile.json
  offerget rendercv export profile.json --output rendercv.json
  offerget resume selftest
  offerget selftest
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # `offerget jd ...`
    jd_parser = subparsers.add_parser("jd", help="Job Description operations")
    jd_subparsers = jd_parser.add_subparsers(dest="jd_command", help="JD subcommands")

    decode_parser = jd_subparsers.add_parser("decode", help="Decode JD into 5 layers")
    decode_parser.add_argument("jd_file", help="Path to JD text file")
    decode_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    match_parser = jd_subparsers.add_parser("match", help="Match profile against JD")
    match_parser.add_argument("jd_file", help="Path to JD text file")
    match_parser.add_argument("--profile", required=True, help="Path to candidate_profile.json")
    match_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    report_parser = jd_subparsers.add_parser("report", help="Generate bilingual HTML report")
    report_parser.add_argument("jd_file", help="Path to JD text file")
    report_parser.add_argument("--profile", required=True, help="Path to candidate_profile.json")
    report_parser.add_argument("--output", default="report.html", help="Output HTML filepath")
    report_parser.add_argument("--template", help="Custom HTML template filepath")

    # `offerget ats ...`
    ats_parser = subparsers.add_parser("ats", help="ATS Auditor & verification operations")
    ats_subparsers = ats_parser.add_subparsers(dest="ats_command", help="ATS subcommands")

    ats_audit_parser = ats_subparsers.add_parser("audit", help="Audit candidate profile or resume against ATS standards")
    ats_audit_parser.add_argument("input_file", help="Path to candidate profile JSON or resume text")
    ats_audit_parser.add_argument("--jd", help="Path to target Job Description text file")
    ats_audit_parser.add_argument("--tag", help="Visibility tag to filter (e.g. ai_pretrain, always)")
    ats_audit_parser.add_argument("--json", action="store_true", help="Output raw JSON audit result")

    ats_ledger_parser = ats_subparsers.add_parser("ledger", help="Generate 3-state skill ledger (Verified vs Claimed vs Gap)")
    ats_ledger_parser.add_argument("profile", help="Path to candidate profile JSON")
    ats_ledger_parser.add_argument("--jd", required=True, help="Path to target Job Description text file")
    ats_ledger_parser.add_argument("--json", action="store_true", help="Output raw JSON ledger")

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

    # `offerget diff ...`
    diff_parser = subparsers.add_parser("diff", help="Diff Ledger & change traceability operations")
    diff_subparsers = diff_parser.add_subparsers(dest="diff_command", help="Diff subcommands")

    diff_audit_parser = diff_subparsers.add_parser("audit", help="Audit changes between baseline profile and tailored resume")
    diff_audit_parser.add_argument("baseline_file", help="Path to SSOT baseline candidate profile JSON")
    diff_audit_parser.add_argument("tailored_file", help="Path to tailored profile JSON, Markdown, or HTML file")
    diff_audit_parser.add_argument("--output-dir", default=None, help="Directory to save resume_diff_ledger.md and .json")
    diff_audit_parser.add_argument("--json", action="store_true", help="Output raw JSON Diff Ledger")

    # `offerget defense ...`
    defense_parser = subparsers.add_parser("defense", help="Project defense interrogation & red-team simulator")
    defense_subparsers = defense_parser.add_subparsers(dest="defense_command", help="Defense subcommands")

    defense_sim_parser = defense_subparsers.add_parser("simulate", help="Simulate project defense interrogation against claims")
    defense_sim_parser.add_argument("target", nargs="?", default=None, help="Project description text, claim list, or file path")
    defense_sim_parser.add_argument("--project", dest="project_opt", default=None, help="Project description text, claim list, or file path")
    defense_sim_parser.add_argument("--profile", help="Path to SSOT candidate_profile.json")
    defense_sim_parser.add_argument("--intensity", default="开始挑刺", choices=["先热个身", "开始挑刺", "严刑拷打", "warmup", "critical", "hell"], help="Interrogation intensity level")
    defense_sim_parser.add_argument("--scenario", default="技术 / 简历面试", help="Defense scenario")
    defense_sim_parser.add_argument("--output", help="Save full 7-section Markdown report to file")
    defense_sim_parser.add_argument("--json", action="store_true", help="Output raw JSON report")

    # `offerget baoyan ...`
    baoyan_parser = subparsers.add_parser("baoyan", help="Chinese Baoyan / Postgraduate Academic Application OS")
    baoyan_subparsers = baoyan_parser.add_subparsers(dest="baoyan_command", help="Baoyan subcommands")

    baoyan_audit_parser = baoyan_subparsers.add_parser("audit", help="Audit academic resume entry for integrity & word-count")
    baoyan_audit_parser.add_argument("entry", help="Resume text entry or file path")
    baoyan_audit_parser.add_argument("--role", help="Team role (项目负责人, 核心成员, 参赛队员, 辅助成员)")
    baoyan_audit_parser.add_argument("--tier", default="简历版", choices=["摘要版", "简历版", "陈述版"], help="Target length tier")
    baoyan_audit_parser.add_argument("--material", help="Source proof material text or file path for numerical tracing")
    baoyan_audit_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    baoyan_compress_parser = baoyan_subparsers.add_parser("compress", help="Compress academic entry to strict word count tier")
    baoyan_compress_parser.add_argument("entry", help="Text entry or file path to compress")
    baoyan_compress_parser.add_argument("--tier", default="简历版", choices=["摘要版", "简历版", "陈述版"], help="Target length tier")
    baoyan_compress_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    baoyan_adv_parser = baoyan_subparsers.add_parser("advisor", help="Match professor profile and generate high-EQ outreach email")
    baoyan_adv_parser.add_argument("advisor", help="Path to advisor JSON file")
    baoyan_adv_parser.add_argument("--profile", required=True, help="Path to academic_profile.json")
    baoyan_adv_parser.add_argument("--scenario", default="summer_camp", choices=["summer_camp", "pre_recommendation", "postgraduate_reexam", "phd_application"], help="Application scenario")
    baoyan_adv_parser.add_argument("--output", help="Path to save outreach email text")
    baoyan_adv_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    baoyan_check_parser = baoyan_subparsers.add_parser("checklist", help="Generate summer camp / re-examination checklist")
    baoyan_check_parser.add_argument("profile_pos", nargs="?", default=None, help="Path to academic_profile.json")
    baoyan_check_parser.add_argument("--profile", default=None, help="Path to academic_profile.json")
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
        choices=[
            "all",
            "modern-navy",
            "silicon-clean",
            "classic-tech",
            "asu-dense",
            "sidebar-clean",
            "academic-postgraduate",
            "engineering-sb2nov",
            "modern-corporate",
            "ats-plain",
            "academic-latex",
            "academic-typst",
        ],
        help="Theme for tailored resume (default: modern-navy)",
    )
    review_parser.add_argument("--resume-output-dir", default=None, help="Custom output directory for tailored resumes")
    review_parser.add_argument("--session", help="Optional path to load an existing review session JSON")
    review_parser.add_argument("--save-session", help="Optional path to save/update the review session JSON")
    review_parser.add_argument("--proposal-db", help="Optional SQLite path to persist the generated material proposal")
    review_parser.add_argument("--application-id", help="Optional application ID to attach to the generated proposal")

    proposal_parser = subparsers.add_parser("proposal", help="Human-confirmed material proposal operations")
    proposal_subparsers = proposal_parser.add_subparsers(dest="proposal_command")
    proposal_show = proposal_subparsers.add_parser("show", help="Show a persisted material proposal")
    proposal_show.add_argument("proposal_id")
    proposal_show.add_argument("--db", help="ApplicationStore SQLite path")
    proposal_show.add_argument("--json", action="store_true")
    proposal_list = proposal_subparsers.add_parser("list", help="List persisted material proposals")
    proposal_list.add_argument("--status", choices=["draft", "accepted", "rejected", "conflicted"])
    proposal_list.add_argument("--application-id")
    proposal_list.add_argument("--company")
    proposal_list.add_argument("--role")
    proposal_list.add_argument("--db", help="ApplicationStore SQLite path")
    proposal_list.add_argument("--json", action="store_true")
    proposal_accept = proposal_subparsers.add_parser("accept", help="Accept selected proposal patches into a new profile")
    proposal_accept.add_argument("proposal_id")
    proposal_accept.add_argument("--profile", required=True)
    proposal_accept.add_argument("--jd", required=True)
    proposal_accept.add_argument("--output", required=True)
    proposal_accept.add_argument("--patch-ids", help="Comma-separated patch indexes; default accepts all")
    proposal_accept.add_argument("--db", help="ApplicationStore SQLite path")
    proposal_accept.add_argument("--json", action="store_true")
    proposal_accept.add_argument("--build-resume", action="store_true")
    proposal_accept.add_argument(
        "--resume-theme",
        default="modern-navy",
        choices=[
            "modern-navy",
            "silicon-clean",
            "classic-tech",
            "asu-dense",
            "sidebar-clean",
            "academic-postgraduate",
            "engineering-sb2nov",
            "modern-corporate",
            "ats-plain",
            "academic-latex",
            "academic-typst",
            "ats-docx",
        ],
    )
    proposal_accept.add_argument("--resume-output-dir")
    proposal_reject = proposal_subparsers.add_parser("reject", help="Reject a persisted material proposal")
    proposal_reject.add_argument("proposal_id")
    proposal_reject.add_argument("--db", help="ApplicationStore SQLite path")
    proposal_reject.add_argument("--json", action="store_true")

    application_parser = subparsers.add_parser("application", help="Persistent application tracking operations")
    application_subparsers = application_parser.add_subparsers(dest="application_command")
    app_add = application_subparsers.add_parser("add", help="Create an application record")
    app_add.add_argument("application_id")
    app_add.add_argument("--company", required=True)
    app_add.add_argument("--role", required=True)
    app_add.add_argument("--status", default="pending")
    app_add.add_argument("--channel", default="官网")
    app_add.add_argument("--target-level")
    app_add.add_argument("--portal-url")
    app_add.add_argument("--recruiter-contact")
    app_add.add_argument("--notes")
    app_add.add_argument("--db")
    app_add.add_argument("--json", action="store_true")
    app_list = application_subparsers.add_parser("list", help="List application records")
    app_list.add_argument("--status")
    app_list.add_argument("--db")
    app_list.add_argument("--json", action="store_true")
    app_show = application_subparsers.add_parser("show", help="Show an application record")
    app_show.add_argument("application_id")
    app_show.add_argument("--db")
    app_show.add_argument("--json", action="store_true")
    app_status = application_subparsers.add_parser("status", help="Transition application status")
    app_status.add_argument("application_id")
    app_status.add_argument("status")
    app_status.add_argument("--note")
    app_status.add_argument("--db")
    app_status.add_argument("--json", action="store_true")
    app_snapshot = application_subparsers.add_parser("snapshot", help="Show the evidence snapshot")
    app_snapshot.add_argument("application_id")
    app_snapshot.add_argument("--db")
    app_snapshot.add_argument("--json", action="store_true")
    app_outcome = application_subparsers.add_parser("outcome", help="Record an application process outcome")
    app_outcome.add_argument("application_id")
    app_outcome.add_argument("--stage", required=True, help="applied|screening|written_test|interview|offer|closed")
    app_outcome.add_argument("--result", required=True, help="advanced|rejected|withdrawn|no_response|offer_received|other")
    app_outcome.add_argument("--feedback", default="")
    app_outcome.add_argument("--reflection", default="")
    app_outcome.add_argument("--next-action", default="")
    app_outcome.add_argument("--tags", default="", help="Comma-separated feedback tags")
    app_outcome.add_argument("--occurred-at", help="Timestamp (YYYY-MM-DD HH:MM), defaults to now")
    app_outcome.add_argument("--db")
    app_outcome.add_argument("--json", action="store_true")
    app_outcomes = application_subparsers.add_parser("outcomes", help="List recorded outcomes")
    app_outcomes.add_argument("application_id", nargs="?", help="Omit to list outcomes across applications")
    app_outcomes.add_argument("--db")
    app_outcomes.add_argument("--json", action="store_true")
    app_insights = application_subparsers.add_parser("insights", help="Aggregate outcome feedback across applications")
    app_insights.add_argument("--db")
    app_insights.add_argument("--json", action="store_true")
    app_versions = application_subparsers.add_parser("versions", help="List application-linked resume versions")
    app_versions.add_argument("application_id", nargs="?", help="Omit to list versions across applications")
    app_versions.add_argument("--db")
    app_versions.add_argument("--json", action="store_true")
    app_version_diff = application_subparsers.add_parser("version-diff", help="Compare two resume version metadata records")
    app_version_diff.add_argument("before_version_id")
    app_version_diff.add_argument("after_version_id")
    app_version_diff.add_argument("--db")
    app_version_diff.add_argument("--json", action="store_true")

    rendercv_parser = subparsers.add_parser("rendercv", help="Import/export RenderCV JSON data")
    rendercv_subparsers = rendercv_parser.add_subparsers(dest="rendercv_command")
    rendercv_import = rendercv_subparsers.add_parser("import", help="Import RenderCV JSON as an OfferGet profile")
    rendercv_import.add_argument("input", help="RenderCV JSON input; YAML must first be exported by RenderCV as JSON")
    rendercv_import.add_argument("--output", required=True)
    rendercv_import.add_argument("--json", action="store_true")
    rendercv_export = rendercv_subparsers.add_parser("export", help="Export an OfferGet profile to RenderCV JSON")
    rendercv_export.add_argument("profile")
    rendercv_export.add_argument("--output", required=True)
    rendercv_export.add_argument("--json", action="store_true")

    # `offerget profile ...`
    profile_parser = subparsers.add_parser("profile", help="Candidate profile operations and auto-ingestion")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")
    profile_parse = profile_subparsers.add_parser("parse", help="Parse Markdown or plain-text resume into OfferGet profile")
    profile_parse.add_argument("input_file", help="Path to resume file (.md, .txt, .json)")
    profile_parse.add_argument("--output", help="Path to save parsed profile JSON")
    profile_parse.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget resume ...`
    subparsers.add_parser("resume", help="Passthrough directly to ApexResume CLI")

    # `offerget selftest`
    subparsers.add_parser("selftest", help="Run comprehensive OfferGet & ApexResume tests")

    # `offerget doctor`
    subparsers.add_parser("doctor", help="Inspect Python runtime, headless browser, and optional toolkits")

    # Store subparser references for help fallback
    parser.subparsers = {
        "jd": jd_parser,
        "ats": ats_parser,
        "gap": gap_parser,
        "offer": offer_parser,
        "anon": anon_parser,
        "fact": fact_parser,
        "diff": diff_parser,
        "defense": defense_parser,
        "baoyan": baoyan_parser,
        "proposal": proposal_parser,
        "application": application_parser,
        "rendercv": rendercv_parser,
        "profile": profile_parser,
    }

    return parser



def main():
    """Main CLI entry point and command dispatcher."""
    # Special handling for `offerget resume ...`
    if len(sys.argv) > 1 and sys.argv[1] == "resume":
        if len(sys.argv) > 2 and sys.argv[2] == "build":
            cmd_resume_build(sys.argv[3:])
            return
        cmd_resume_passthrough(sys.argv[2:])
        return

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "review":
        cmd_career_review(args)
    elif args.command == "proposal":
        dispatch = {
            "show": cmd_proposal_show,
            "list": cmd_proposal_list,
            "accept": cmd_proposal_accept,
            "reject": cmd_proposal_reject,
        }
        handler = dispatch.get(args.proposal_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["proposal"].print_help()
    elif args.command == "application":
        dispatch = {
            "add": cmd_application_add,
            "list": cmd_application_list,
            "show": cmd_application_show,
            "status": cmd_application_status,
            "snapshot": cmd_application_snapshot,
            "outcome": cmd_application_outcome,
            "outcomes": cmd_application_outcomes,
            "insights": cmd_application_insights,
            "versions": cmd_application_versions,
            "version-diff": cmd_application_version_diff,
        }
        handler = dispatch.get(args.application_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["application"].print_help()
    elif args.command == "rendercv":
        dispatch = {"import": cmd_rendercv_import, "export": cmd_rendercv_export}
        handler = dispatch.get(args.rendercv_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["rendercv"].print_help()
    elif args.command == "jd":
        dispatch = {
            "decode": cmd_jd_decode,
            "match": cmd_jd_match,
            "report": cmd_jd_report,
        }
        handler = dispatch.get(args.jd_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["jd"].print_help()
    elif args.command == "ats":
        dispatch = {
            "audit": cmd_ats_audit,
            "ledger": cmd_ats_ledger,
            "filter": cmd_ats_filter,
        }
        handler = dispatch.get(args.ats_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["ats"].print_help()
    elif args.command == "gap":
        if args.gap_command == "roi":
            cmd_gap_roi(args)
        else:
            parser.subparsers["gap"].print_help()
    elif args.command == "offer":
        dispatch = {
            "evaluate": cmd_offer_evaluate,
            "counter": cmd_offer_counter,
        }
        handler = dispatch.get(args.offer_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["offer"].print_help()
    elif args.command == "anon":
        dispatch = {
            "mask": cmd_anon_mask,
            "unmask": cmd_anon_unmask,
        }
        handler = dispatch.get(args.anon_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["anon"].print_help()
    elif args.command == "fact":
        if args.fact_command == "verify":
            cmd_fact_verify(args)
        else:
            parser.subparsers["fact"].print_help()
    elif args.command == "diff":
        dispatch = {
            "audit": cmd_diff_audit,
        }
        handler = dispatch.get(args.diff_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["diff"].print_help()
    elif args.command == "defense":
        if args.defense_command == "simulate":
            cmd_defense_simulate(args)
        else:
            parser.subparsers["defense"].print_help()
    elif args.command == "baoyan":
        dispatch = {
            "audit": cmd_baoyan_audit,
            "compress": cmd_baoyan_compress,
            "advisor": cmd_baoyan_advisor,
            "checklist": cmd_baoyan_checklist,
        }
        handler = dispatch.get(args.baoyan_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["baoyan"].print_help()
    elif args.command == "profile":
        dispatch = {
            "parse": cmd_profile_parse,
        }
        handler = dispatch.get(args.profile_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["profile"].print_help()
    elif args.command == "selftest":
        cmd_selftest(args)
    elif args.command == "doctor":
        sys.exit(cmd_doctor(args))
    else:
        parser.print_help()



if __name__ == "__main__":
    main()
