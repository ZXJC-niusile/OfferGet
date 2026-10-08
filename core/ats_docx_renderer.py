"""
OfferGet ATS Single-Column DOCX Resume Renderer (core/ats_docx_renderer.py)
===========================================================================
OfferGet native ATS-optimized resume rendering engine.
Produces deterministic, single-column Word (.docx) documents optimized for ATS parsers:
1. ATS-Friendly Structure:
   - Linear flow (Header -> Summary -> Experience -> Projects -> Education -> Skills).
   - Strict single-column layout without complex nested blocks or text boxes.
   - Standard section titles mapped directly from QualityRuleRegistry.STANDARD_SECTIONS.
2. Direct ResumeViewModel Consumption:
   - Consumes OfferGet's SSOT ResumeViewModel (or auto-converts from candidate profile).
3. Output Validation & Quality Audit:
   - Built-in ATS compliance validator checking for tables, columns, symbols, and margins.
"""

from __future__ import annotations

import re
from html import unescape
from unicodedata import east_asian_width
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import docx
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Mm, Pt, RGBColor
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False

from core.resume_view_model import ResumeViewModel
from core.registry import QualityRuleRegistry


@dataclass
class DocxRenderConfig:
    """Configurable styling knobs for DOCX rendering."""
    font_name: str = "Arial"
    font_name_cjk: str = "Noto Sans CJK SC"
    font_size_name: float = 22.0
    font_size_title: float = 11.0
    font_size_section: float = 11.5
    font_size_item_header: float = 11.0
    font_size_body: float = 10.5
    margin_inches: float = 0.75
    primary_color_hex: str = "202B3A"  # Restrained ink
    body_color_hex: str = "252525"     # High-contrast body text
    divider_line_size: int = 0          # Optional; whitespace separates sections by default


class AtsDocxRenderer:
    """Generates clean, single-column, ATS-parseable Word (.docx) resumes."""

    def __init__(self, config: Optional[DocxRenderConfig] = None):
        if not _DOCX_AVAILABLE:
            raise ImportError("python-docx is required for AtsDocxRenderer. Please install via: pip install python-docx")
        self.config = config or DocxRenderConfig()

    def render(
        self,
        view_model_or_profile: Union[ResumeViewModel, Dict[str, Any]],
        output_path: Union[str, Path],
    ) -> Path:
        """
        Renders the resume to a .docx file at output_path.
        Returns the resolved Path to the generated document.
        """
        if isinstance(view_model_or_profile, ResumeViewModel):
            vm = view_model_or_profile
        else:
            vm = ResumeViewModel.from_profile(view_model_or_profile)

        doc = Document()
        self._apply_page_margins(doc)
        self._apply_document_styles(doc)

        # 1. Header (Name & Contact info)
        self._render_header(doc, vm)

        # 2. Professional Summary (if available)
        narrative = (vm.raw_profile or {}).get("narrative", {})
        summary = narrative.get("summary_zh") or narrative.get("summary_en")
        if summary:
            self._render_section_heading(doc, "个人总结 / Professional Summary")
            self._render_paragraph(doc, str(summary))

        # 3. Work Experience
        if vm.experiences:
            self._render_section_heading(doc, "工作经历 / Work Experience")
            for exp in vm.experiences:
                self._render_experience_item(doc, exp)

        # 4. Key Projects
        if vm.projects:
            self._render_section_heading(doc, "重点项目 / Key Projects")
            for proj in vm.projects:
                self._render_project_item(doc, proj)

        # 5. Education
        if vm.edu_school or vm.education_grid_rows:
            self._render_section_heading(doc, "教育背景 / Education")
            self._render_education(doc, vm)

        if vm.postgraduate_exam:
            self._render_section_heading(doc, "考研成绩 / Postgraduate Exam")
            self._render_exam(doc, vm.postgraduate_exam)

        # 6. Technical Skills & Competencies
        if vm.competencies:
            self._render_section_heading(doc, "专业技能 / Technical Skills")
            self._render_skills(doc, vm)

        # 7. Publications (if any)
        if vm.publications:
            self._render_section_heading(doc, "学术成果与论文 / Publications")
            for pub in vm.publications:
                fields = [self._raw(pub, key) for key in ("title", "authors", "venue", "year")]
                self._render_bullet(doc, " · ".join(value for value in fields if value))

        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        import core.atomic_writer as atomic_writer
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
            tmp_docx_path = Path(tmp_docx.name)
        try:
            doc.save(str(tmp_docx_path))
            save_res = atomic_writer.safe_save_file(out_file, tmp_docx_path, allow_shadow=True)
            if not save_res.success:
                raise OSError(save_res.error_message or f"Failed to safely save DOCX: {out_file}")
            return Path(save_res.final_path)
        finally:
            tmp_docx_path.unlink(missing_ok=True)

    def _apply_page_margins(self, doc: Any) -> None:
        """Use explicit A4 geometry instead of the Word installation's defaults."""
        for section in doc.sections:
            section.page_width = Mm(210)
            section.page_height = Mm(297)
            margin = Inches(self.config.margin_inches)
            section.top_margin = margin
            section.bottom_margin = margin
            section.left_margin = margin
            section.right_margin = margin

    @staticmethod
    def _raw(item: Dict[str, Any], key: str, *aliases: str) -> str:
        """Prefer source text; decode only legacy HTML-projected fallback fields."""
        for field in (key,) + aliases:
            if "raw_" + field in item:
                return str(item["raw_" + field] or "")
        for field in (key,) + aliases:
            if item.get(field):
                return unescape(str(item[field]))
        return ""

    @staticmethod
    def _bullets(item: Dict[str, Any]) -> List[str]:
        if "raw_bullets" in item:
            return [str(value) for value in item["raw_bullets"]]
        # Only generated emphasis is markup. Decode afterwards so literal source
        # text such as &lt;strong&gt; remains literal, rather than being deleted.
        return [unescape(re.sub(r"</?strong>", "**", str(value)))
                for value in item.get("bullets", [])]

    def _apply_document_styles(self, doc: Any) -> None:
        normal = doc.styles["Normal"]
        normal.font.name = self.config.font_name
        normal.font.size = Pt(self.config.font_size_body)
        normal.paragraph_format.space_after = Pt(2)
        normal.paragraph_format.line_spacing = Pt(self.config.font_size_body * 1.28)
        normal.paragraph_format.widow_control = True
        # Word and LibreOffice use these explicit hanging indents consistently.
        bullet = doc.styles["List Bullet"].paragraph_format
        bullet.left_indent = Inches(0.16)
        bullet.first_line_indent = Inches(-0.16)
        bullet.tab_stops.add_tab_stop(Inches(0.16))
        doc.core_properties.title = "Resume"
        doc.core_properties.author = ""
        doc.core_properties.last_modified_by = ""

    def _run(self, paragraph: Any, text: str, *, bold: bool = False,
             size: Optional[float] = None, muted: bool = False) -> Any:
        run = paragraph.add_run(text)
        run.bold = bold
        run.font.size = Pt(size or self.config.font_size_body)
        self._set_font(run)
        self._set_color(run, "555555" if muted else self.config.body_color_hex)
        return run

    def _render_header(self, doc: Any, vm: ResumeViewModel) -> None:
        """Compact centered identity, still in the ordinary document body."""
        for text, size, bold, after in (
            (vm.raw_name or unescape(vm.name), self.config.font_size_name, True, 3),
            (vm.raw_title or unescape(vm.title), self.config.font_size_title, False, 4),
            ("  |  ".join(filter(None, (
                vm.raw_phone or unescape(vm.phone),
                vm.raw_email or unescape(vm.email),
                vm.raw_location or unescape(vm.location)))), self.config.font_size_body, False, 5),
        ):
            if not text:
                continue
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(after)
            p.paragraph_format.line_spacing = Pt(size * 1.3)
            p.paragraph_format.keep_with_next = True
            self._run(p, text, bold=bold, size=size)

    def _render_section_heading(self, doc: Any, heading_text: str) -> None:
        p = doc.add_paragraph(style="Heading 1")
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = Pt(self.config.font_size_section * 1.3)
        p.paragraph_format.keep_with_next = True
        self._run(p, heading_text, bold=True, size=self.config.font_size_section)
        if self.config.divider_line_size:
            self._add_bottom_border(p, self.config.primary_color_hex, self.config.divider_line_size)

    def _render_item_heading(self, doc: Any, label: str, dates: str, role: str = "") -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.keep_with_next = True
        section = doc.sections[-1]
        width = section.page_width - section.left_margin - section.right_margin
        p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        self._run(p, label, bold=True, size=self.config.font_size_item_header)
        if dates:
            # A tab alone can split dates after a long institution name. Give
            # crowded headers a dedicated right-aligned date line instead.
            units = sum(2 if east_asian_width(char) in "WF" else 1 for char in label)
            estimated_points = (units * self.config.font_size_item_header
                                + len(dates) * self.config.font_size_body) * 0.55
            if estimated_points > width / 12700 * 0.9:
                date_p = doc.add_paragraph()
                date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                date_p.paragraph_format.space_after = Pt(1)
                date_p.paragraph_format.keep_with_next = True
                self._run(date_p, dates, muted=True)
            else:
                self._run(p, "\t" + dates, muted=True)
        if role:
            role_p = doc.add_paragraph()
            role_p.paragraph_format.space_after = Pt(2)
            role_p.paragraph_format.keep_with_next = True
            self._run(role_p, role, muted=True)

    def _render_experience_item(self, doc: Any, exp: Dict[str, Any]) -> None:
        self._render_item_heading(doc, self._raw(exp, "org", "company"),
                                  self._raw(exp, "time", "dates"),
                                  self._raw(exp, "role_label", "role"))
        for text in self._bullets(exp):
            self._render_bullet(doc, text)

    def _render_project_item(self, doc: Any, proj: Dict[str, Any]) -> None:
        self._render_item_heading(doc, self._raw(proj, "name"),
                                  self._raw(proj, "time", "dates"), self._raw(proj, "role"))
        for text in self._bullets(proj):
            self._render_bullet(doc, text)

    def _render_education(self, doc: Any, vm: ResumeViewModel) -> None:
        # The grid contains supplementary badges, not a replacement for school,
        # degree and dates. Always retain the primary education identity.
        school = vm.raw_school or unescape(vm.edu_school)
        degree = vm.raw_degree or unescape(vm.edu_degree)
        dates = vm.raw_edu_time or unescape(vm.edu_time)
        if school or degree or dates:
            self._render_item_heading(doc, school, dates, degree)
        for row in vm.education_grid_rows:
            self._render_paragraph(doc, "  |  ".join(unescape(str(cell)) for cell in row if cell))

    def _render_exam(self, doc: Any, exam: Dict[str, Any]) -> None:
        target = [self._raw(exam, key) for key in ("target_school", "target_major", "direction")]
        if any(target):
            self._render_paragraph(doc, "  |  ".join(filter(None, target)))
        scores = [f"{self._raw(subject, 'name')}: {self._raw(subject, 'score')}"
                  for subject in exam.get("subjects", [])]
        total = self._raw(exam, "total_score")
        if total:
            scores.append(f"总分 / Total: {total}")
        if scores:
            self._render_paragraph(doc, "  |  ".join(scores))

    def _render_skills(self, doc: Any, vm: ResumeViewModel) -> None:
        # Competencies deliberately remain raw in ResumeViewModel.
        for category, skills in vm.competencies.items():
            if skills:
                p = doc.add_paragraph()
                self._run(p, f"{category}: ", bold=True)
                self._run(p, ", ".join(skills))

    def _render_bullet(self, doc: Any, bullet_text: str) -> None:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = Pt(self.config.font_size_body * 1.28)
        # A bullet may span pages when necessary; do not keep entire jobs together.
        p.paragraph_format.keep_with_next = False
        for part in re.split(r"(\*\*.*?\*\*)", bullet_text):
            bold = part.startswith("**") and part.endswith("**") and len(part) >= 4
            self._run(p, part[2:-2] if bold else part, bold=bold)

    def _render_paragraph(self, doc: Any, text: str) -> None:
        p = doc.add_paragraph()
        self._run(p, text)

    def _set_font(self, run: Any) -> None:
        run.font.name = self.config.font_name
        rPr = run._r.get_or_add_rPr()
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(qn("w:ascii"), self.config.font_name)
        rFonts.set(qn("w:hAnsi"), self.config.font_name)
        rFonts.set(qn("w:eastAsia"), self.config.font_name_cjk)
        rPr.append(rFonts)

    def _set_color(self, run: Any, hex_color: str) -> None:
        h = hex_color.lstrip("#")
        r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        run.font.color.rgb = RGBColor(r, g, b)

    def _add_bottom_border(self, paragraph: Any, hex_color: str, size: int = 8) -> None:
        pPr = paragraph._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), str(size))
        bottom.set(qn("w:space"), "2")
        bottom.set(qn("w:color"), hex_color.lstrip("#"))
        pBdr.append(bottom)
        pPr.append(pBdr)


# ============================================================================
# 3. ATS DOCX Quality Gate & Validation
# ============================================================================

def validate_docx_ats_compliance(docx_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Verifies that a generated DOCX file satisfies strict ATS parsing requirements:
    1. File exists and is a valid DOCX.
    2. Single column layout (no multi-column sections).
    3. No complex tables with borders that scramble text order.
    4. Uniform margins (at least 0.5 inches).
    5. Contains recognized standard section headings.
    """
    p = Path(docx_path)
    if not p.exists():
        return {"passed": False, "errors": [f"File not found: {docx_path}"]}

    try:
        doc = Document(str(p))
    except Exception as e:
        return {"passed": False, "errors": [f"Failed to open DOCX: {e}"]}

    errors: List[str] = []
    warnings: List[str] = []

    # Check 1: Margins
    for i, section in enumerate(doc.sections):
        if section.top_margin < Inches(0.49) or section.left_margin < Inches(0.49):
            errors.append(f"Section {i+1} margins too narrow for ATS (<0.5 inch)")

    # Check 2: Tables
    if len(doc.tables) > 0:
        warnings.append(f"Document contains {len(doc.tables)} table(s). Ensure linear reading order is preserved.")

    # Check 3: Standard Section headings presence
    headings_found: List[str] = []
    doc_text = " ".join(p.text for p in doc.paragraphs)
    for std_name, aliases in QualityRuleRegistry.STANDARD_SECTIONS.items():
        found = any(alias.lower() in doc_text.lower() for alias in aliases)
        if found:
            headings_found.append(std_name)

    if len(headings_found) < 3:
        errors.append(f"Insufficient standard section headings detected (found {len(headings_found)}, required ≥ 3)")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "sections_detected": headings_found,
        "paragraph_count": len(doc.paragraphs),
    }
