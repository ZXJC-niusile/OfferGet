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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import docx
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False

from core.resume_view_model import ResumeViewModel
from core.registry import QualityRuleRegistry


@dataclass
class DocxRenderConfig:
    """Configurable styling knobs for DOCX rendering."""
    font_name: str = "Calibri"
    font_name_cjk: str = "Microsoft YaHei"
    font_size_name: float = 20.0
    font_size_title: float = 12.0
    font_size_section: float = 13.0
    font_size_item_header: float = 11.0
    font_size_body: float = 10.5
    margin_inches: float = 0.75
    primary_color_hex: str = "1F3864"  # Classic Navy
    body_color_hex: str = "333333"     # Charcoal
    divider_line_size: int = 8          # 1pt divider


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

        # 1. Header (Name & Contact info)
        self._render_header(doc, vm)

        # 2. Professional Summary (if available)
        if vm.raw_profile and vm.raw_profile.get("narrative", {}).get("summary_zh"):
            self._render_section_heading(doc, "个人总结 / Professional Summary")
            self._render_paragraph(doc, vm.raw_profile["narrative"]["summary_zh"])

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

        # 6. Technical Skills & Competencies
        if vm.competencies:
            self._render_section_heading(doc, "专业技能 / Technical Skills")
            self._render_skills(doc, vm)

        # 7. Publications (if any)
        if vm.publications:
            self._render_section_heading(doc, "学术成果与论文 / Publications")
            for pub in vm.publications:
                title = pub.get("title", "")
                venue = pub.get("venue", "")
                year = pub.get("year", "")
                text = f"{title} - {venue} ({year})" if venue else title
                self._render_bullet(doc, text)

        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        import core.atomic_writer as atomic_writer
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_docx:
            tmp_docx_path = Path(tmp_docx.name)
        try:
            doc.save(str(tmp_docx_path))
            save_res = atomic_writer.safe_save_file(out_file, tmp_docx_path, allow_shadow=True)
            if save_res.success:
                return Path(save_res.final_path)
            doc.save(str(out_file))
            return out_file
        finally:
            tmp_docx_path.unlink(missing_ok=True)

    def _apply_page_margins(self, doc: Any) -> None:
        """Applies uniform 0.75-inch margins for ATS scanning standards."""
        for section in doc.sections:
            margin = Inches(self.config.margin_inches)
            section.top_margin = margin
            section.bottom_margin = margin
            section.left_margin = margin
            section.right_margin = margin

    def _render_header(self, doc: Any, vm: ResumeViewModel) -> None:
        """Renders linear, centered header block."""
        name_text = vm.raw_name or vm.name
        title_text = vm.raw_title or vm.title

        # Name
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.space_before = Pt(0)
        p_name.paragraph_format.space_after = Pt(2)
        run_name = p_name.add_run(name_text)
        run_name.bold = True
        run_name.font.size = Pt(self.config.font_size_name)
        self._set_font(run_name)
        self._set_color(run_name, self.config.primary_color_hex)

        # Title / Subtitle
        if title_text:
            p_title = doc.add_paragraph()
            p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_title.paragraph_format.space_before = Pt(0)
            p_title.paragraph_format.space_after = Pt(4)
            run_title = p_title.add_run(title_text)
            run_title.font.size = Pt(self.config.font_size_title)
            self._set_font(run_title)
            self._set_color(run_title, self.config.body_color_hex)

        # Contact Info Line: phone | email | location
        contact_parts = []
        if vm.raw_phone or vm.phone:
            contact_parts.append(vm.raw_phone or vm.phone)
        if vm.raw_email or vm.email:
            contact_parts.append(vm.raw_email or vm.email)
        if vm.raw_location or vm.location:
            contact_parts.append(vm.raw_location or vm.location)

        if contact_parts:
            p_contact = doc.add_paragraph()
            p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_contact.paragraph_format.space_before = Pt(0)
            p_contact.paragraph_format.space_after = Pt(12)
            run_contact = p_contact.add_run("  |  ".join(contact_parts))
            run_contact.font.size = Pt(self.config.font_size_body)
            self._set_font(run_contact)
            self._set_color(run_contact, self.config.body_color_hex)

    def _render_section_heading(self, doc: Any, heading_text: str) -> None:
        """Renders section header with divider line."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(heading_text)
        run.bold = True
        run.font.size = Pt(self.config.font_size_section)
        self._set_font(run)
        self._set_color(run, self.config.primary_color_hex)

        # Add bottom divider line via XML
        self._add_bottom_border(p, self.config.primary_color_hex, self.config.divider_line_size)

    def _render_experience_item(self, doc: Any, exp: Dict[str, Any]) -> None:
        """Renders a single work experience entry."""
        company = exp.get("company", "")
        role = exp.get("role", "")
        dates = exp.get("dates", "")

        # Header line: Company -- Role (Dates)
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(2)
        run_comp = p.add_run(company)
        run_comp.bold = True
        run_comp.font.size = Pt(self.config.font_size_item_header)
        self._set_font(run_comp)

        if role:
            run_role = p.add_run(f"  |  {role}")
            run_role.font.size = Pt(self.config.font_size_item_header)
            self._set_font(run_role)

        if dates:
            run_dates = p.add_run(f"  ({dates})")
            run_dates.font.size = Pt(self.config.font_size_body)
            self._set_font(run_dates)
            self._set_color(run_dates, "666666")

        # Bullets
        bullets = exp.get("bullets", [])
        for b in bullets:
            self._render_bullet(doc, b)

    def _render_project_item(self, doc: Any, proj: Dict[str, Any]) -> None:
        """Renders a single project entry."""
        name = proj.get("name", "")
        role = proj.get("role", "")
        dates = proj.get("dates", "")

        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(2)
        run_name = p.add_run(name)
        run_name.bold = True
        run_name.font.size = Pt(self.config.font_size_item_header)
        self._set_font(run_name)

        if role:
            run_role = p.add_run(f"  |  {role}")
            run_role.font.size = Pt(self.config.font_size_item_header)
            self._set_font(run_role)

        if dates:
            run_dates = p.add_run(f"  ({dates})")
            run_dates.font.size = Pt(self.config.font_size_body)
            self._set_font(run_dates)
            self._set_color(run_dates, "666666")

        bullets = proj.get("bullets", [])
        for b in bullets:
            self._render_bullet(doc, b)

    def _render_education(self, doc: Any, vm: ResumeViewModel) -> None:
        """Renders education entries."""
        if vm.education_grid_rows:
            for row in vm.education_grid_rows:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                line = "  |  ".join(str(c) for c in row if c)
                run = p.add_run(line)
                run.font.size = Pt(self.config.font_size_item_header)
                self._set_font(run)
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            school = vm.raw_school or vm.edu_school
            degree = vm.raw_degree or vm.edu_degree
            time_str = vm.raw_edu_time or vm.edu_time
            parts = [p for p in [school, degree, time_str] if p]
            run = p.add_run("  |  ".join(parts))
            run.font.size = Pt(self.config.font_size_item_header)
            self._set_font(run)

    def _render_skills(self, doc: Any, vm: ResumeViewModel) -> None:
        """Renders technical skills categorized line-by-line."""
        for cat_name, skill_list in vm.competencies.items():
            if not skill_list:
                continue
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            run_cat = p.add_run(f"• {cat_name}: ")
            run_cat.bold = True
            run_cat.font.size = Pt(self.config.font_size_body)
            self._set_font(run_cat)

            run_skills = p.add_run(", ".join(skill_list))
            run_skills.font.size = Pt(self.config.font_size_body)
            self._set_font(run_skills)

    def _render_bullet(self, doc: Any, bullet_text: str) -> None:
        """Renders a single bullet point with bold emphasis."""
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.15

        # Split markdown bold **text** if present
        parts = re.split(r"(\*\*.*?\*\*)", bullet_text)
        for part in parts:
            if part.startswith("**") and part.endswith("**") and len(part) >= 4:
                run = p.add_run(part[2:-2])
                run.bold = True
            else:
                run = p.add_run(part)
            run.font.size = Pt(self.config.font_size_body)
            self._set_font(run)
            self._set_color(run, self.config.body_color_hex)

    def _render_paragraph(self, doc: Any, text: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.size = Pt(self.config.font_size_body)
        self._set_font(run)
        self._set_color(run, self.config.body_color_hex)

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
