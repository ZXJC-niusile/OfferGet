"""
OfferGet Evidence Audit Report HTML Renderer.
Absorbed and modernized from ASu-resume-skills (Apache-2.0).
Renders high-fidelity, interactive, print-ready evidence audit reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.artifacts import write_text_atomic
from core.evidence.models import AuditReport

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_TEMPLATE_PATH = TEMPLATE_DIR / "audit_report.html"


def _safe_json_for_script(data: Dict[str, Any]) -> str:
    """Serializes data dictionary into JSON safe for embedding inside <script> tags."""
    raw_json = json.dumps(data, ensure_ascii=False)
    # Prevent </script> injection
    return raw_json.replace("</script>", "<\\/script>").replace("<!--", "<\\!--")


def render_audit_report_html(
    report: Union[AuditReport, Dict[str, Any]],
    template_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Renders an AuditReport object or dictionary into a standalone, styled HTML report.
    """
    if isinstance(report, AuditReport):
        report_dict = report.to_dict()
    elif isinstance(report, dict):
        report_dict = report
    else:
        raise TypeError(f"Expected AuditReport or dict, got {type(report).__name__}")

    tpl_path = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
    if not tpl_path.is_file():
        raise FileNotFoundError(f"Audit report template not found at: {tpl_path}")

    template_content = tpl_path.read_text(encoding="utf-8")
    json_payload = _safe_json_for_script(report_dict)

    if "__REPORT_JSON__" not in template_content:
        raise ValueError("Audit report template missing '__REPORT_JSON__' placeholder.")

    return template_content.replace("__REPORT_JSON__", json_payload)


def save_audit_report_html(
    report: Union[AuditReport, Dict[str, Any]],
    output_path: Union[str, Path],
    template_path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Renders and writes an AuditReport to the specified file path.
    """
    html_content = render_audit_report_html(report, template_path=template_path)
    target = write_text_atomic(html_content, output_path)
    return Path(target)
