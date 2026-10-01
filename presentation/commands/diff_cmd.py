"""
OfferGet Diff Ledger Command Handlers (presentation/commands/diff_cmd.py)
==========================================================================
Audits modifications from SSOT baseline to tailored resume, tracking role hierarchy,
metric scope, credential fidelity, and adaptive layout actions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from core.cli_helpers import (
    load_json,
    load_profile,
    load_json_or_text,
    emit_json,
    emit_stderr,
)
from core.fact_guard import FactVerificationGuard
from core.diff_ledger import DiffLedger


def cmd_diff_audit(args: Any) -> None:
    """Handler for `offerget diff audit <baseline_file> <tailored_file>`."""
    baseline_path = Path(args.baseline_file)
    if not baseline_path.exists():
        emit_stderr(f"[-] Error: Baseline profile file not found: {baseline_path}")
        sys.exit(1)

    tailored_path = Path(args.tailored_file)
    if not tailored_path.exists():
        emit_stderr(f"[-] Error: Tailored resume file not found: {tailored_path}")
        sys.exit(1)

    baseline_data = load_profile(str(baseline_path))

    json_data, text_data = load_json_or_text(str(tailored_path))
    tailored_data = json_data if json_data is not None else text_data

    # Execute FactVerificationGuard audit against baseline
    guard = FactVerificationGuard(baseline_data)
    guard_result = guard.verify_facts(tailored_data)

    # Build DiffLedger
    ledger = DiffLedger.from_fact_guard_result(
        guard_result=guard_result,
        baseline_profile=baseline_data,
        tailored_data=tailored_data,
    )

    output_dir = getattr(args, "output_dir", None)
    saved_files = None
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        saved_files = ledger.save(out_path, base_name="resume")

    if getattr(args, "json", False):
        emit_json(ledger.to_dict())
    else:
        # Emit formatted markdown report to terminal
        print(ledger.generate_markdown())
        if saved_files:
            print(f"\n[✓] Diff Ledger report saved to {output_dir}: {saved_files['markdown'].name}, {saved_files['json'].name}")


__all__ = ["cmd_diff_audit"]
