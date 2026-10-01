#!/usr/bin/env python3
"""OfferGet Smart Auto-Fit Compaction Engine (core/autofit.py).

Automatically calculates overflow pixels and dynamically fine-tunes CSS tokens
(line-height, margins, padding, font-size) along a safe ladder of adjustments
until the resume cleanly fits onto exactly 1 single A4 page.
"""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import core.atomic_writer as atomic_writer
from core.artifacts import write_text_atomic
from core.browser_renderer import BrowserRenderer


@dataclass
class TuneProfile:
    name: str
    line_height: float
    padding_y_mm: float
    padding_x_mm: float
    font_size_px: float
    item_gap_px: float
    section_gap_px: float


# Safe step-down adjustment ladder
TUNING_LADDER = [
    TuneProfile(name="Step 0 (Standard)", line_height=1.62, padding_y_mm=8.8, padding_x_mm=10.6, font_size_px=12.0, item_gap_px=4.8, section_gap_px=11.0),
    TuneProfile(name="Step 1 (Slight Line-Height)", line_height=1.58, padding_y_mm=8.2, padding_x_mm=10.2, font_size_px=11.8, item_gap_px=4.2, section_gap_px=10.0),
    TuneProfile(name="Step 2 (Moderate Compact)", line_height=1.54, padding_y_mm=7.8, padding_x_mm=9.8, font_size_px=11.4, item_gap_px=3.6, section_gap_px=9.0),
    TuneProfile(name="Step 3 (Deep Compact)", line_height=1.50, padding_y_mm=7.2, padding_x_mm=9.5, font_size_px=11.0, item_gap_px=3.0, section_gap_px=8.0),
    TuneProfile(name="Step 4 (Ultra Compact Max)", line_height=1.45, padding_y_mm=6.5, padding_x_mm=9.0, font_size_px=10.6, item_gap_px=2.5, section_gap_px=6.5),
]


class AutoFitEngine:
    """Intelligent page compressor for HTML resumes."""

    def __init__(self, renderer: Optional[BrowserRenderer] = None):
        self.renderer = renderer or BrowserRenderer()

    def apply_profile_to_html(self, html_content: str, profile: TuneProfile) -> str:
        """Applies layout tuning variables to HTML content."""
        has_css_vars = ":root" in html_content and "--body-line-height" in html_content

        if has_css_vars:
            replacements = {
                r"--body-line-height:\s*[^;]+;": f"--body-line-height: {profile.line_height};",
                r"--page-padding-y:\s*[^;]+;": f"--page-padding-y: {profile.padding_y_mm}mm;",
                r"--page-padding-x:\s*[^;]+;": f"--page-padding-x: {profile.padding_x_mm}mm;",
                r"--body-font-size:\s*[^;]+;": f"--body-font-size: {profile.font_size_px}px;",
                r"--item-gap:\s*[^;]+;": f"--item-gap: {profile.item_gap_px}px;",
                r"--section-gap:\s*[^;]+;": f"--section-gap: {profile.section_gap_px}px;",
            }
            res = html_content
            for pat, val in replacements.items():
                res = re.sub(pat, val, res)
            return res

        override_style = f"""
<style id="autofit-override">
  :root {{
    --body-line-height: {profile.line_height};
    --page-padding-y: {profile.padding_y_mm}mm;
    --page-padding-x: {profile.padding_x_mm}mm;
    --body-font-size: {profile.font_size_px}px;
    --item-gap: {profile.item_gap_px}px;
    --section-gap: {profile.section_gap_px}px;
  }}
  .page {{
    padding-top: {profile.padding_y_mm}mm !important;
    padding-bottom: {profile.padding_y_mm}mm !important;
    padding-left: {profile.padding_x_mm}mm !important;
    padding-right: {profile.padding_x_mm}mm !important;
  }}
  body, p, li {{
    font-size: {profile.font_size_px}px !important;
    line-height: {profile.line_height} !important;
  }}
  li {{
    margin-bottom: {profile.item_gap_px}px !important;
  }}
  h2, .section-header {{
    margin-top: {profile.section_gap_px}px !important;
  }}
</style>
"""
        if "</head>" in html_content:
            return html_content.replace("</head>", f"{override_style}\n</head>")
        else:
            return f"{override_style}\n{html_content}"

    def fit_to_single_page(
        self,
        input_html_path: str | Path,
        output_html_path: Optional[str | Path] = None,
        output_pdf_path: Optional[str | Path] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Automatically compresses HTML resume until it fits exactly 1 page.

        Returns: (success: bool, report_message: str, details: dict)
        """
        in_path = Path(input_html_path).resolve()
        raw_html = in_path.read_text(encoding="utf-8")

        temp_files_to_clean: set[Path] = set()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            test_pdf = Path(tmp_pdf.name)
            temp_files_to_clean.add(test_pdf)

        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp_html:
            test_html = Path(tmp_html.name)
            temp_files_to_clean.add(test_html)

        actual_pdf_path: Optional[Path] = None

        try:
            # First check step 0
            test_html.write_text(raw_html, encoding="utf-8")
            render_res = self.renderer.render_pdf(test_html, test_pdf)
            ok, initial_pages, initial_msg = render_res[0], render_res[1], render_res[2]
            source_pdf = Path(getattr(render_res, "final_path", None) or test_pdf)
            temp_files_to_clean.add(source_pdf)

            if not ok:
                return False, f"Initial render failed: {initial_msg}", {"step": 0, "error": initial_msg}

            if not source_pdf.is_file() or source_pdf.stat().st_size == 0:
                err = "Initial render failed: Rendered PDF is missing or empty"
                return False, err, {"step": 0, "error": err}

            if initial_pages == 1:
                # Already fits perfectly
                actual_html_path = None
                if output_html_path:
                    actual_html_path = write_text_atomic(raw_html, output_html_path)
                is_shadow = False
                if output_pdf_path:
                    save_res = atomic_writer.safe_save_file(output_pdf_path, source_pdf, allow_shadow=True)
                    if not save_res.success:
                        return False, f"Failed to save output PDF: {save_res.error_message}", {
                            "step": 0, "pages": 1, "error": save_res.error_message
                        }
                    actual_pdf_path = save_res.final_path
                    is_shadow = save_res.is_shadow
                details: Dict[str, Any] = {
                    "step": 0,
                    "pages": 1,
                    "profile": TUNING_LADDER[0].name,
                }
                if actual_pdf_path:
                    details["final_pdf_path"] = str(actual_pdf_path)
                    details["is_shadow"] = is_shadow
                if actual_html_path:
                    details["final_html_path"] = str(actual_html_path)
                return True, "Resume already fits onto 1 page cleanly without modifications.", details

            # If pages > 1, start stepped tuning
            last_pages = initial_pages
            last_msg = initial_msg
            for step_idx, profile in enumerate(TUNING_LADDER):
                tuned_html = self.apply_profile_to_html(raw_html, profile)
                test_html.write_text(tuned_html, encoding="utf-8")

                render_res = self.renderer.render_pdf(test_html, test_pdf)
                ok, pages, step_msg = render_res[0], render_res[1], render_res[2]
                step_source_pdf = Path(getattr(render_res, "final_path", None) or test_pdf)
                temp_files_to_clean.add(step_source_pdf)
                last_pages = pages
                last_msg = step_msg

                if ok and pages == 1:
                    if not step_source_pdf.is_file() or step_source_pdf.stat().st_size == 0:
                        err = f"Rendered PDF for step {step_idx} is missing or empty"
                        return False, err, {"step": step_idx, "pages": 1, "error": err}

                    # Success!
                    actual_html_path = None
                    if output_html_path:
                        actual_html_path = write_text_atomic(tuned_html, output_html_path)
                    is_shadow = False
                    if output_pdf_path:
                        save_res = atomic_writer.safe_save_file(output_pdf_path, step_source_pdf, allow_shadow=True)
                        if not save_res.success:
                            return False, f"Failed to save output PDF: {save_res.error_message}", {
                                "step": step_idx, "pages": 1, "error": save_res.error_message
                            }
                        actual_pdf_path = save_res.final_path
                        is_shadow = save_res.is_shadow

                    msg = (
                        f"AutoFit Success: Compressed from {initial_pages} pages down to 1 page "
                        f"using [{profile.name}] (line-height: {profile.line_height}, "
                        f"padding: {profile.padding_y_mm}mm, font-size: {profile.font_size_px}px)."
                    )
                    details = {
                        "step": step_idx,
                        "initial_pages": initial_pages,
                        "pages": 1,
                        "profile": profile.name,
                        "line_height": profile.line_height,
                        "padding_y_mm": profile.padding_y_mm,
                    }
                    if actual_pdf_path:
                        details["final_pdf_path"] = str(actual_pdf_path)
                        details["is_shadow"] = is_shadow
                    if actual_html_path:
                        details["final_html_path"] = str(actual_html_path)
                    return True, msg, details

            # If still overflows after step 4
            return False, (
                f"AutoFit Warning: Content exceeds 1-page capacity even after Ultra Compact tuning "
                f"(remains {last_pages} pages). It is strongly advised to prune 1-2 bullet points or remove "
                f"the weakest project to maintain readability and avoid visual overcrowding."
            ), {
                "step": len(TUNING_LADDER) - 1,
                "initial_pages": initial_pages,
                "pages": last_pages,
                "last_message": last_msg,
            }

        finally:
            for p in temp_files_to_clean:
                try:
                    p_obj = Path(p)
                    if actual_pdf_path and p_obj.resolve() == Path(actual_pdf_path).resolve():
                        continue
                    if p_obj.exists():
                        p_obj.unlink(missing_ok=True)
                except Exception:
                    pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core.autofit <input.html> [output.html] [--pdf output.pdf]")
        sys.exit(1)

    in_html = sys.argv[1]
    out_html = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    out_pdf = None

    if "--pdf" in sys.argv:
        p_idx = sys.argv.index("--pdf")
        if p_idx + 1 < len(sys.argv):
            out_pdf = sys.argv[p_idx + 1]

    engine = AutoFitEngine()
    success, message, details = engine.fit_to_single_page(in_html, out_html, out_pdf)
    print(f"\n[AutoFit Report]")
    print(message)
    sys.exit(0 if success else 1)
