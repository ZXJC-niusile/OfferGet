#!/usr/bin/env python3
"""ApexResume Unified Command Line Interface (CLI).

Cross-platform toolkit for technical resume forging, verification, and printing.
Supports Windows, macOS, and Linux out-of-the-box.
"""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.render import BrowserRenderer
from core.audit import ResumeAuditor
from core.autofit import AutoFitEngine


def cmd_render(args: argparse.Namespace) -> int:
    """Renders an HTML file to an A4 PDF."""
    renderer = BrowserRenderer()
    print(f"[ApexResume] Detected Browser: {renderer.browser_path}")

    if args.measure:
        h, overflow = renderer.measure_overflow(args.input_html)
        print(f"[ApexResume] Document Height: {h}px (A4 Target: 1123px, Overflow: {overflow:+d}px)")

    success, pages, msg = renderer.render_pdf(args.input_html, args.output_pdf)
    if success:
        print(f"[ApexResume SUCCESS] {msg}")
        if pages > 1:
            print(f"[ApexResume WARNING] Page count is {pages} (>1). Run 'python cli.py autofit {args.input_html}' to compress into 1 page.")
            return 2
        return 0
    else:
        print(f"[ApexResume ERROR] {msg}")
        return 1


def cmd_autofit(args: argparse.Namespace) -> int:
    """Applies smart stepped compaction to ensure single-page delivery."""
    engine = AutoFitEngine()
    print(f"[ApexResume] Analyzing document geometry for single-page compaction...")

    success, msg, details = engine.fit_to_single_page(
        input_html_path=args.input_html,
        output_html_path=args.output_html,
        output_pdf_path=args.pdf,
    )

    print(f"\n[ApexResume AutoFit Result]")
    print(msg)

    if success:
        if args.output_html:
            print(f"[ApexResume] Saved compacted HTML: {args.output_html}")
        if args.pdf:
            print(f"[ApexResume] Rendered single-page PDF: {args.pdf}")
        return 0
    else:
        return 1


def cmd_audit(args: argparse.Namespace) -> int:
    """Runs deterministic mathematical, role, and HTML quality audits."""
    auditor = ResumeAuditor()

    if not args.claims and not args.html:
        print("[ApexResume ERROR] Must specify at least one of --claims or --html to audit.")
        return 1

    if args.claims:
        print(f"[ApexResume] Auditing atomic claims in: {args.claims}")
        auditor.audit_claims_file(args.claims)

    if args.html:
        print(f"[ApexResume] Auditing static HTML quality in: {args.html}")
        auditor.audit_html_file(args.html)

    if args.source:
        if not args.html:
            print("[ApexResume ERROR] --source requires --html to be specified for sandbox verification.")
            return 1
        print(f"[ApexResume] Running source draft sandbox verification: {args.html} vs {args.source}")
        auditor.audit_source_sandbox(args.html, args.source)

    res = auditor.summary()
    print("\n========================================================")
    print(f"            ApexResume Verification Summary             ")
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

    return 0 if res["passed"] else 1


def cmd_selftest(args: argparse.Namespace) -> int:
    """Runs the full test suite and verifies local environment health."""
    print("========================================================")
    print("           ApexResume Environment Self-Test             ")
    print("========================================================")

    # 1. Check Python
    print(f"[1/4] Python Runtime: {sys.version.split()[0]} ({sys.platform})")

    # 2. Check Browser
    try:
        browser = BrowserRenderer.find_browser()
        print(f"[2/4] Headless Browser Found: {browser}")
    except Exception as e:
        print(f"[2/4] Browser Detection FAILED: {e}")
        return 1

    # 3. Check Examples
    examples_dir = Path(__file__).parent / "examples"
    sample_html = examples_dir / "sample-resume.html"
    sample_claims = examples_dir / "claims.json"

    if sample_html.exists() and sample_claims.exists():
        print(f"[3/4] Sample Datasets Verified ({sample_html.name}, {sample_claims.name})")
    else:
        print(f"[3/4] Sample Datasets MISSING in {examples_dir}")

    # 4. Run Unit Tests
    print(f"[4/4] Running Unit Test Suite...")
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent / "tests"))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n🎉 ALL TESTS PASSED! ApexResume is fully functional and production-ready.")
        return 0
    else:
        print("\n❌ UNIT TESTS FAILED. Please inspect traceback above.")
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog="ApexResume",
        description="ApexResume: Industrial-Grade Technical Resume Forge & Verification Suite",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # render
    p_render = subparsers.add_parser("render", help="Render HTML to A4 PDF")
    p_render.add_argument("input_html", help="Path to input HTML file")
    p_render.add_argument("output_pdf", help="Path to output PDF file")
    p_render.add_argument("--measure", action="store_true", help="Measure scrollHeight overflow")

    # autofit
    p_autofit = subparsers.add_parser("autofit", help="Auto-compact resume to fit exactly 1 page")
    p_autofit.add_argument("input_html", help="Path to input HTML file")
    p_autofit.add_argument("output_html", nargs="?", help="Path to output compacted HTML")
    p_autofit.add_argument("--pdf", help="Also render compacted PDF directly")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit claims and HTML quality")
    p_audit.add_argument("--claims", help="Path to claims.json dataset")
    p_audit.add_argument("--html", help="Path to resume.html file")
    p_audit.add_argument("--source", help="Path to raw source text/draft file for anti-hallucination sandbox audit")

    # selftest
    subparsers.add_parser("selftest", help="Run comprehensive environment and test diagnostics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "render": cmd_render,
        "autofit": cmd_autofit,
        "audit": cmd_audit,
        "selftest": cmd_selftest,
    }

    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
