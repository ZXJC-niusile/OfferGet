"""
OfferGet Doctor Environment Diagnostic Command Handler.
Performs pre-flight checks on Python runtime, headless browser, optional PDF toolkits,
and installed diagnostic resources with actionable cross-platform repair guidance.
"""

from __future__ import annotations

import sys
from typing import Any

from core.browser_renderer import BrowserRenderer
from presentation.diagnostic_data import missing_resources


def check_python_environment() -> dict[str, Any]:
    version_tuple = sys.version_info
    valid = version_tuple >= (3, 9)
    return {
        "name": "Python Runtime",
        "valid": valid,
        "detail": f"{version_tuple.major}.{version_tuple.minor}.{version_tuple.micro} ({sys.platform})",
        "guidance": "OfferGet requires Python 3.9+. Please upgrade your Python runtime." if not valid else "",
    }


def check_headless_browser() -> dict[str, Any]:
    diag = BrowserRenderer.diagnose_browser()
    return {
        "name": "Headless Browser (optional PDF rendering)",
        "valid": diag["found"],
        "detail": diag["browser_path"] if diag["found"] else "Not Found",
        "guidance": diag["installation_guide"] if not diag["found"] else "",
        "candidates": diag["checked_candidates"],
    }


def check_optional_toolkits() -> dict[str, Any]:
    tools = []
    
    # Check PyMuPDF (fitz)
    try:
        import fitz  # type: ignore
        tools.append(("PyMuPDF (fitz)", True, f"Installed (v{fitz.__version__})"))
    except ImportError:
        tools.append(("PyMuPDF (fitz)", False, "Optional — pip install pymupdf (enables high-speed PDF inspection)"))

    # Check pypdf
    try:
        import pypdf  # type: ignore
        tools.append(("pypdf", True, f"Installed (v{pypdf.__version__})"))
    except ImportError:
        tools.append(("pypdf", False, "Optional — pip install pypdf (enables PDF fallback page counting)"))

    # Check python-docx
    try:
        import docx  # type: ignore  # noqa: F401
        tools.append(("python-docx", True, "Installed"))
    except ImportError:
        tools.append(("python-docx", False, "Optional — pip install python-docx (enables ATS docx output)"))

    return {
        "name": "Optional PDF & Document Toolkits",
        "valid": True,
        "tools": tools,
    }


def check_sample_assets() -> dict[str, Any]:
    missing = missing_resources()
    valid = not missing
    return {
        "name": "Installed Diagnostic Resources",
        "valid": valid,
        "detail": "Verified (synthetic fixtures and report template)" if valid else f"Missing: {', '.join(missing)}",
        "guidance": "Reinstall OfferGet; its installed diagnostic resources are incomplete." if not valid else "",
    }


def cmd_doctor(args=None) -> int:
    """Executes full environment diagnostic and prints actionable guidance."""
    print("=" * 68)
    print("                 OfferGet Environment Doctor                     ")
    print("=" * 68)

    checks = [
        check_python_environment(),
        check_headless_browser(),
        check_sample_assets(),
    ]

    all_passed = True

    for i, c in enumerate(checks, 1):
        status_symbol = "✓" if c["valid"] else "✗"
        print(f"[{i}/{len(checks) + 1}] {c['name']} ... {status_symbol} {c['detail']}")
        if not c["valid"]:
            all_passed = False
            if c.get("guidance"):
                print(c["guidance"])

    # Optional dependencies
    opt = check_optional_toolkits()
    print(f"[{len(checks) + 1}/{len(checks) + 1}] {opt['name']}:")
    for name, installed, msg in opt["tools"]:
        symbol = "✓" if installed else "○"
        print(f"      {symbol} {name}: {msg}")

    print("-" * 68)
    if all_passed:
        print("Core resources and browser executable found. Rendering has not been tested.")
        return 0
    else:
        print("ENVIRONMENT INCOMPLETE: Review the missing components above. A missing optional browser affects PDF rendering, not core smoke checks.")
        return 1
