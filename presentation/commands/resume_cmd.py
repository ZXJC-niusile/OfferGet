"""
OfferGet Resume Command Handlers:
- cmd_resume_build: Build multi-template resumes from candidate profile
- cmd_resume_passthrough: Direct passthrough to ApexResume CLI
"""

from __future__ import annotations

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
        description="Build a resume (PDF & HTML) from candidate profile; use --theme all for every theme",
    )
    build_parser.add_argument("profile", help="Path to candidate profile JSON (minimal or standard)")
    build_parser.add_argument(
        "--theme",
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
            "ats-docx",
        ],
        help="Resume theme to build (default: modern-navy; use all for the previous batch output)",
    )
    build_parser.add_argument(
        "--output-dir",
        default="output/resumes",
        help="Output directory to save generated resumes (default: output/resumes)",
    )
    photo_group = build_parser.add_mutually_exclusive_group()
    photo_group.add_argument("--no-photo", action="store_true", help="Exclude all photos and photo slots, including photos in the profile")
    photo_group.add_argument("--photo-mode", choices=["photo", "no-photo", "placeholder"], default=None,
                             help="photo: require a real image; no-photo: no image or slot (default); placeholder: explicit layout preview only")
    build_parser.add_argument("--photo-path", default=None, help="Validated local PNG/JPEG/WebP/GIF still image; implies photo mode unless no-photo is selected")
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
        help="PDF page budget (DOCX requires auto; pagination is not verified): 'auto' (default: 1 page or auto-expand if needed), '1' (strict 1-page), '2' (balanced 2-page)",
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

    photo_mode = ("no-photo" if parsed.no_photo else
                  getattr(parsed, "photo_mode", None) or ("photo" if parsed.photo_path else "no-photo"))
    try:
        builder = ResumeBuilder(
            profile_path,
            photo_path=parsed.photo_path,
            anonymize=parsed.anonymize,
            photo_mode=photo_mode,
        )
        # Resolve before rendering: a missing or invalid real photo is an error,
        # never an implicit placeholder or a silently omitted portrait.
        builder.view_model
    except (ValueError, OSError) as exc:
        emit_stderr(f"[-] Error: {exc}")
        sys.exit(1)
    cand_name = builder.profile["candidate"].get("name", "候选人")
    target_role = builder.profile["candidate"].get("title", "")
    photo_status = {"no-photo": "No photo or reserved slot", "photo": "Validated image",
                    "placeholder": "Placeholder (layout preview only)"}[photo_mode]

    print("=" * 68)
    print("             OfferGet · Multi-Template Resume Builder            ")
    print("=" * 68)
    print(f"[*] Candidate:   {cand_name}")
    print(f"[*] Target Role: {target_role}")
    print(f"[*] Output Dir:  {out_dir}")
    print(f"[*] Photo Slot:  {photo_status}")
    page_status = "Not verified (DOCX)" if parsed.theme == "ats-docx" else parsed.pages
    print(f"[*] Page Budget: {page_status}")
    print(f"[*] Anonymize:   {parsed.anonymize or 'Disabled'}")
    print(f"[*] AutoFit:     {'Disabled' if parsed.no_autofit else 'Enabled'}")
    print(f"[*] Adaptive:    {'Enabled' if parsed.adaptive_fill else 'Disabled'}")
    print(f"[*] Diff Ledger: {'Enabled' if parsed.diff_ledger else 'Disabled'}")
    print("-" * 68)

    photo = photo_mode != "no-photo"
    autofit = not parsed.no_autofit
    adaptive_fill = bool(parsed.adaptive_fill)
    diff_ledger = bool(parsed.diff_ledger)
    pages = str(parsed.pages)

    failed_themes = []
    try:
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
                artifact = files.get("pdf") or files.get("docx")
                if artifact and not Path(artifact).exists():
                    failed_themes.append((theme_name, f"Target artifact missing: {artifact}"))
                    emit_stderr(f"  ✗ [{theme_name:<16}] -> FAILED (not found: {artifact.name})")
                else:
                    artifact_name = artifact.name if artifact else "generated"
                    print(f"  ✓ [{theme_name:<16}] -> {artifact_name}")
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
            artifact = files.get("pdf") or files.get("docx")
            if artifact and not Path(artifact).exists():
                failed_themes.append((parsed.theme, f"Target artifact missing: {artifact}"))
                emit_stderr(f"  ✗ [{parsed.theme:<16}] -> FAILED (not found: {artifact.name})")
            else:
                artifact_name = artifact.name if artifact else "generated"
                print(f"  ✓ [{parsed.theme:<16}] -> {artifact_name}")
    except (RuntimeError, ValueError, OSError) as exc:
        emit_stderr(f"[-] Error: Resume build failed: {exc}")
        sys.exit(1)

    if failed_themes:
        emit_stderr(f"[-] Error: {len(failed_themes)} theme variant(s) failed verification.")
        sys.exit(1)

    if diff_ledger:
        diff_md = out_dir / "resume_diff_ledger.md"
        diff_json = out_dir / "resume_diff_ledger.json"
        if diff_md.exists() and diff_json.exists():
            print(f"  ✓ [diff-ledger     ] -> {diff_md.name} & {diff_json.name}")

    print("=" * 68)
    print(f"🎉 Successfully built resume variant(s) in {out_dir}")
    print("=" * 68)


def cmd_resume_render(args_list):
    """Render HTML resume to A4 PDF."""
    parser = argparse.ArgumentParser(prog="offerget resume render", description="Render HTML resume to A4 PDF")
    parser.add_argument("input_html", help="Path to input HTML file")
    parser.add_argument("output_pdf", help="Path to output PDF file")
    parser.add_argument("--measure", action="store_true", help="Measure scrollHeight and overflow pixels")
    args = parser.parse_args(args_list)

    from core.browser_renderer import BrowserRenderer

    renderer = BrowserRenderer()
    print(f"[OfferGet] Detected Browser: {renderer.browser_path}")
    if args.measure:
        h, overflow = renderer.measure_overflow(args.input_html)
        print(f"[OfferGet] Document Height: {h}px (A4 Target: 1123px, Overflow: {overflow:+d}px)")

    success, pages, msg = renderer.render_pdf(args.input_html, args.output_pdf)
    if success:
        print(f"[OfferGet SUCCESS] {msg}")
        if pages > 1:
            print(f"[OfferGet WARNING] Page count is {pages} (>1). Run 'offerget resume autofit {args.input_html}' to compress into 1 page.")
            sys.exit(2)
        sys.exit(0)
    else:
        emit_stderr(f"[OfferGet ERROR] {msg}")
        sys.exit(1)


def cmd_resume_autofit(args_list):
    """Auto-fit HTML resume to single page."""
    parser = argparse.ArgumentParser(prog="offerget resume autofit", description="Auto-fit HTML resume to single page")
    parser.add_argument("input_html", help="Path to input HTML file")
    parser.add_argument("output_html", nargs="?", default=None, help="Path to output HTML file")
    parser.add_argument("--pdf", default=None, help="Optional output PDF path")
    args = parser.parse_args(args_list)

    from core.autofit import AutoFitEngine

    engine = AutoFitEngine()
    print("[OfferGet] Analyzing document geometry for single-page compaction...")
    success, msg, details = engine.fit_to_single_page(
        input_html_path=args.input_html,
        output_html_path=args.output_html,
        output_pdf_path=args.pdf,
    )
    print(f"\n[OfferGet AutoFit Result]\n{msg}")
    if success:
        if args.output_html:
            print(f"[OfferGet] Saved compacted HTML: {args.output_html}")
        if args.pdf:
            print(f"[OfferGet] Rendered single-page PDF: {args.pdf}")
        sys.exit(0)
    else:
        sys.exit(1)


def cmd_resume_audit(args_list):
    """Audit resume metrics, verbs, and anti-inflation."""
    parser = argparse.ArgumentParser(prog="offerget resume audit", description="Audit resume metrics, verbs, and anti-inflation")
    parser.add_argument("--claims", default=None, help="Path to atomic claims JSON")
    parser.add_argument("--html", default=None, help="Path to rendered resume HTML")
    parser.add_argument("--source", default=None, help="Path to raw source text draft for sandbox verification")
    args = parser.parse_args(args_list)

    from core.resume_auditor import ResumeAuditor

    auditor = ResumeAuditor()
    if not args.claims and not args.html:
        emit_stderr("[OfferGet ERROR] Must specify at least one of --claims or --html to audit.")
        sys.exit(1)

    if args.claims:
        print(f"[OfferGet] Auditing atomic claims in: {args.claims}")
        auditor.audit_claims_file(args.claims)

    if args.html:
        print(f"[OfferGet] Auditing static HTML quality in: {args.html}")
        auditor.audit_html_file(args.html)

    if args.source:
        if not args.html:
            emit_stderr("[OfferGet ERROR] --source requires --html to be specified for sandbox verification.")
            sys.exit(1)
        print(f"[OfferGet] Running source draft sandbox verification: {args.html} vs {args.source}")
        auditor.audit_source_sandbox(args.html, args.source)

    res = auditor.summary()
    print("\n========================================================")
    print("            OfferGet Resume Verification Summary        ")
    print("========================================================")
    status_str = "PASSED" if res["passed"] else "FAILED (REVISION REQUIRED)"
    print(f"Status:   {status_str}")
    print(f"Findings: Critical={res['critical_count']} | Warning={res['warning_count']} | Info={res['info_count']}")

    if any(res.get("depth_distribution", {}).values()) or any(res.get("result_distribution", {}).values()):
        depths = ", ".join(f"{k}:{v}" for k, v in res.get("depth_distribution", {}).items() if v > 0) or "None"
        results = ", ".join(f"{k}:{v}" for k, v in res.get("result_distribution", {}).items() if v > 0) or "None"
        print(f"Tiers:    DataDepth=[{depths}] | ResultEvidence=[{results}]")
    print()

    for idx, f in enumerate(res["findings"], 1):
        sev = f["severity"].upper()
        cat = f["category"].upper()
        prefix = "❌" if sev == "CRITICAL" else ("⚠️" if sev == "WARNING" else "ℹ️")
        print(f"{prefix} [{idx}] [{sev}] [{cat}] {f['message']}")

    sys.exit(0 if res["passed"] else 1)


def cmd_resume_dispatch(args_list):
    """Dispatches `offerget resume <subcommand>` to native handlers."""
    if not args_list:
        print("Usage: offerget resume <build|render|autofit|audit|selftest> [options]")
        sys.exit(1)

    subcmd = args_list[0]
    rest = args_list[1:]
    if subcmd == "build":
        cmd_resume_build(rest)
    elif subcmd == "render":
        cmd_resume_render(rest)
    elif subcmd == "autofit":
        cmd_resume_autofit(rest)
    elif subcmd == "audit":
        cmd_resume_audit(rest)
    elif subcmd == "selftest":
        from presentation.commands.selftest_cmd import cmd_selftest
        cmd_selftest()
    else:
        emit_stderr(f"[-] Unknown resume subcommand: {subcmd}")
        sys.exit(1)


cmd_resume_passthrough = cmd_resume_dispatch
