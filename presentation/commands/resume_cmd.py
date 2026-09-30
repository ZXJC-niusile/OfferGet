"""
OfferGet Resume Command Handlers:
- cmd_resume_build: Build multi-template resumes from candidate profile
- cmd_resume_passthrough: Direct passthrough to ApexResume CLI
"""

from __future__ import annotations

import os
import sys
import argparse
import subprocess
from pathlib import Path

from core.paths import get_project_root
PROJECT_ROOT = get_project_root()

from core.cli_helpers import (
    emit_stderr,
)
from core.resume_builder import ResumeBuilder


def cmd_resume_build(args_list=None):
    """Build multi-template resumes from candidate profile."""
    build_parser = argparse.ArgumentParser(
        prog="offerget resume build",
        description="Build multi-template resumes (PDF & HTML) from candidate profile",
    )
    build_parser.add_argument("profile", help="Path to candidate profile JSON (minimal or standard)")
    build_parser.add_argument(
        "--theme",
        default="all",
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
    build_parser.add_argument(
        "--diff-ledger",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Produce change traceability report (Diff Ledger) (default: True)",
    )
    build_parser.add_argument(
        "--adaptive-fill",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Adaptively expand vertical margins/typography on non-full pages (default: True)",
    )
    build_parser.add_argument(
        "--pages",
        default="auto",
        choices=["auto", "1", "2"],
        help="Target page budget: 'auto' (default: 1 page or auto-expand if needed), '1' (strict 1-page), '2' (balanced 2-page)",
    )
    build_parser.add_argument(
        "--baseline",
        default=None,
        help="Path to baseline candidate profile JSON for diff audit",
    )

    if isinstance(args_list, argparse.Namespace):
        parsed = args_list
    else:
        parsed = build_parser.parse_args(args_list if args_list is not None else sys.argv[3:])

    profile_path = Path(parsed.profile)
    if not profile_path.exists():
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)

    out_dir = Path(parsed.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_data = None
    if parsed.baseline:
        b_path = Path(parsed.baseline)
        if not b_path.exists():
            emit_stderr(f"[-] Error: Baseline profile file not found: {b_path}")
            sys.exit(1)
        from core.cli_helpers import load_json
        baseline_data = load_json(str(b_path))

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
    print(f"[*] Page Budget: {parsed.pages}")
    print(f"[*] Anonymize:   {parsed.anonymize or 'Disabled'}")
    print(f"[*] AutoFit:     {'Disabled' if parsed.no_autofit else 'Enabled'}")
    print(f"[*] Adaptive:    {'Enabled' if parsed.adaptive_fill else 'Disabled'}")
    print(f"[*] Diff Ledger: {'Enabled' if parsed.diff_ledger else 'Disabled'}")
    print("-" * 68)

    photo = not parsed.no_photo
    autofit = not parsed.no_autofit
    adaptive_fill = bool(parsed.adaptive_fill)
    diff_ledger = bool(parsed.diff_ledger)
    pages = str(parsed.pages)

    if parsed.theme == "all":
        results = builder.build_all(
            out_dir,
            photo=photo,
            autofit=autofit,
            adaptive_fill=adaptive_fill,
            diff_ledger=diff_ledger,
            baseline_profile=baseline_data,
            pages=pages,
        )
        for theme_name, files in results.items():
            pdf_name = files.get("pdf", Path("")).name
            print(f"  ✓ [{theme_name:<16}] -> {pdf_name}")
    else:
        files = builder.build_theme(
            parsed.theme,
            out_dir,
            photo=photo,
            autofit=autofit,
            adaptive_fill=adaptive_fill,
            diff_ledger=diff_ledger,
            baseline_profile=baseline_data,
            pages=pages,
        )
        pdf_name = files.get("pdf", Path("")).name
        print(f"  ✓ [{parsed.theme:<16}] -> {pdf_name}")

    if diff_ledger:
        diff_md = out_dir / "resume_diff_ledger.md"
        diff_json = out_dir / "resume_diff_ledger.json"
        if diff_md.exists() and diff_json.exists():
            print(f"  ✓ [diff-ledger     ] -> {diff_md.name} & {diff_json.name}")

    print("=" * 68)
    print(f"🎉 Successfully built resume variant(s) in {out_dir}")
    print("=" * 68)


def cmd_resume_passthrough(unknown_args):
    """Passes through any `offerget resume ...` command directly to ApexResume/cli.py."""
    apex_cli = PROJECT_ROOT / "ApexResume" / "cli.py"
    if not apex_cli.exists():
        emit_stderr(f"[-] Error: ApexResume submodule not found at {apex_cli}")
        sys.exit(1)

    cmd = [sys.executable, str(apex_cli)] + unknown_args
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT / "ApexResume"))
    sys.exit(proc.returncode)
