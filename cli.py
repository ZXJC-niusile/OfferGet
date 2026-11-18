#!/usr/bin/env python3
"""
OfferGet Skill CLI - Local Profile Ingestion, Resume Auditing, Diff Checking & Rendering.
"""

from __future__ import annotations

import argparse
import json
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

from core.cli_helpers import fail_cli
from presentation.commands import (
    cmd_anon_mask,
    cmd_anon_unmask,
    cmd_ats_audit,
    cmd_ats_filter,
    cmd_ats_ledger,
    cmd_diff_audit,
    cmd_doctor,
    cmd_fact_verify,
    cmd_profile_parse,
    cmd_profile_refs,
    cmd_resume_build,
    cmd_resume_dispatch,
    cmd_selftest,
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the ArgumentParser for OfferGet CLI."""
    parser = argparse.ArgumentParser(
        prog="offerget",
        description="OfferGet - Local Resume Skill Toolchain (Ingest, Audit, Diff, Anonymize & Render)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  offerget profile parse examples/sample_resume.md --output profile.json
  offerget profile refs --docs notes/ --query "distributed cache" --json
  offerget resume build profile.json --theme modern-navy --no-photo --output-dir output/resume
  offerget ats audit profile.json --jd examples/sample_ai_jd.txt
  offerget fact verify "Latency reduced from 240 ms to 180 ms" --profile profile.json --json
  offerget diff audit baseline.json tailored.json --output-dir output/diff
  offerget anon mask profile.json --level strict --map map.json --output masked.json
  offerget selftest
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # `offerget profile ...`
    profile_parser = subparsers.add_parser("profile", help="Candidate profile parsing and reference-only document search")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")
    profile_parse = profile_subparsers.add_parser(
        "parse",
        help="Parse Markdown, text, DOCX, HTML, PDF, or BibTeX file into OfferGet profile",
    )
    profile_parse.add_argument("input_file", help="Path to resume or BibTeX file (.md, .txt, .docx, .html, .pdf, .bib, .json)")
    profile_parse.add_argument("--output", help="Path to save parsed profile JSON")
    profile_parse.add_argument("--json", action="store_true", help="Output raw JSON")
    profile_parse.add_argument("--confirm-parsed", action="store_true", help="已人工核对解析结果及未归类原文，记录确认状态；不代表外部事实核验")

    profile_refs = profile_subparsers.add_parser("refs", help="Search local reference-only supporting docs (project notes, postmortems)")
    profile_refs.add_argument("--docs", nargs="+", required=True, help="Reference files or directories (.md, .txt, .docx, .html, .pdf)")
    profile_refs.add_argument("--query", required=True, help="Search query for recalling supporting details")
    profile_refs.add_argument("--limit", type=int, default=5, help="Max reference chunks to return (default: 5)")
    profile_refs.add_argument("--json", action="store_true", help="Output raw JSON")

    # `offerget resume ...`
    subparsers.add_parser(
        "resume",
        help="Build, render, autofit, and audit resumes (build|render|autofit|audit)",
    )

    # `offerget ats ...`
    ats_parser = subparsers.add_parser("ats", help="ATS structure, readability, keyword coverage, and visibility tools")
    ats_subparsers = ats_parser.add_subparsers(dest="ats_command", help="ATS subcommands")

    ats_audit_parser = ats_subparsers.add_parser("audit", help="Audit candidate profile or resume against ATS standards")
    ats_audit_parser.add_argument("input_file", help="Path to candidate profile JSON or resume text")
    ats_audit_parser.add_argument("--jd", help="Path to target Job Description text file")
    ats_audit_parser.add_argument("--tag", help="Visibility tag to filter (e.g. ai_pretrain, always)")
    ats_audit_parser.add_argument("--json", action="store_true", help="Output raw JSON audit result")

    ats_ledger_parser = ats_subparsers.add_parser("ledger", help="Check JD keyword coverage against profile evidence")
    ats_ledger_parser.add_argument("profile", help="Path to candidate profile JSON")
    ats_ledger_parser.add_argument("--jd", required=True, help="Path to target Job Description text file")
    ats_ledger_parser.add_argument("--json", action="store_true", help="Output raw JSON ledger")

    ats_filter_parser = ats_subparsers.add_parser("filter", help="Filter master profile by visibility tag")
    ats_filter_parser.add_argument("profile", help="Path to candidate profile JSON")
    ats_filter_parser.add_argument("--tag", required=True, help="Target visibility tag (e.g. ai_pretrain, agentic_systems)")
    ats_filter_parser.add_argument("--output", help="Output JSON filepath (default: stdout)")

    # `offerget fact ...`
    fact_parser = subparsers.add_parser("fact", help="Fact verification & anti-drift guard")
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

    # `offerget selftest` & `offerget doctor`
    subparsers.add_parser("selftest", help="Run installed-runtime core smoke checks (not the developer test suite)")
    subparsers.add_parser("doctor", help="Inspect Python runtime, headless browser, and optional toolkits")

    parser.subparsers = {
        "profile": profile_parser,
        "ats": ats_parser,
        "fact": fact_parser,
        "diff": diff_parser,
        "anon": anon_parser,
    }
    return parser


def main():
    """Main CLI entry point and command dispatcher."""
    if len(sys.argv) > 1 and sys.argv[1] == "resume":
        if len(sys.argv) > 2 and sys.argv[2] == "build":
            cmd_resume_build(sys.argv[3:])
            return
        cmd_resume_dispatch(sys.argv[2:])
        return

    parser = build_parser()
    args = parser.parse_args()
    try:
        _dispatch_command(args, parser)
    except FileNotFoundError as exc:
        fail_cli(args, "input_not_found", str(exc))
    except json.JSONDecodeError as exc:
        fail_cli(args, "invalid_json", str(exc))
    except OSError as exc:
        fail_cli(args, "io_error", f"文件操作失败：{exc}。请关闭占用文件的程序，并检查目录权限和可用空间后重试原命令。")
    except ValueError as exc:
        fail_cli(args, "invalid_input", str(exc))


def _dispatch_command(args, parser):
    if args.command == "profile":
        dispatch = {
            "parse": cmd_profile_parse,
            "refs": cmd_profile_refs,
        }
        handler = dispatch.get(args.profile_command)
        if handler:
            handler(args)
        else:
            parser.subparsers["profile"].print_help()
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
    elif args.command == "fact":
        if args.fact_command == "verify":
            cmd_fact_verify(args)
        else:
            parser.subparsers["fact"].print_help()
    elif args.command == "diff":
        if args.diff_command == "audit":
            cmd_diff_audit(args)
        else:
            parser.subparsers["diff"].print_help()
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
    elif args.command == "selftest":
        cmd_selftest(args)
    elif args.command == "doctor":
        sys.exit(cmd_doctor(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
