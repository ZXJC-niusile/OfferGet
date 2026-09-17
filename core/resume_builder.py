"""
OfferGet Unified Resume Builder Engine (core/resume_builder.py)
===============================================================
Central orchestrator for multi-template resume generation, compiling, and compaction:
1. Universal Profile Ingestion:
   - Uses `core.profile_adapter.normalize_candidate_profile` to accept both
     standard and minimal candidate profiles (Track 1 / Track 2 SSOT).
2. Deep Reuse of ApexResume Engines:
   - Reuses `ApexResume.core.render.BrowserRenderer` for cross-platform headless
     PDF rendering without external PDF tools.
   - Reuses `ApexResume.core.autofit.AutoFitEngine` for single-page A4 stepped
     compaction (CSS variables auto-tuning).
3. Universal Multi-Template Formats:
   - Modern Navy (`modern-navy`)
   - Silicon Clean (`silicon-clean`)
   - Classic Tech (`classic-tech`)
   - ATS Plain (`ats-plain`, Markdown & single-column HTML)
   - Academic LaTeX (`academic-latex`, .tex + HTML twin + PDF)
   - Academic Typst (`academic-typst`, .typ + native compile)
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure OfferGet and ApexResume are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "ApexResume") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "ApexResume"))

from core.profile_adapter import normalize_candidate_profile
from core.academic_exporter import AcademicExporter

try:
    from ApexResume.core.render import BrowserRenderer
    from ApexResume.core.autofit import AutoFitEngine
except ImportError:
    from core.render import BrowserRenderer  # type: ignore
    from core.autofit import AutoFitEngine    # type: ignore



class ResumeBuilder:
    """Unified engine for building all 6 resume variants from candidate profile data."""

    THEMES = [
        "modern-navy",
        "silicon-clean",
        "classic-tech",
        "ats-plain",
        "academic-latex",
        "academic-typst",
    ]

    def __init__(
        self,
        profile_or_path: Union[Dict[str, Any], str, Path],
        template_dir: Optional[Union[str, Path]] = None,
        renderer: Optional[BrowserRenderer] = None,
        autofit_engine: Optional[AutoFitEngine] = None,
    ):
        if isinstance(profile_or_path, (str, Path)):
            p_path = Path(profile_or_path).resolve()
            if not p_path.exists():
                raise FileNotFoundError(f"Candidate profile not found at {p_path}")
            with open(p_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        elif isinstance(profile_or_path, dict):
            raw_data = profile_or_path
        else:
            raise TypeError("profile_or_path must be a dictionary or file path")

        self.profile = normalize_candidate_profile(raw_data)
        self.academic_exporter = AcademicExporter()

        self.template_dir = Path(template_dir).resolve() if template_dir else (PROJECT_ROOT / "ApexResume" / "themes")


        self.renderer = renderer or BrowserRenderer()
        self.autofit_engine = autofit_engine or AutoFitEngine(self.renderer)

    def _render_sections_html(self, theme_name: str) -> str:
        """Renders standard HTML sections for HTML-based themes."""
        cand = self.profile.get("candidate", {})
        edu_badges = cand.get("education_badges", [])
        exp_list = self.profile.get("experience", [])
        proj_list = self.profile.get("projects", [])
        comps = self.profile.get("competencies", {})

        badge_spans = "".join([
            f'<span style="font-size:10.5px; color:var(--color-muted, #4B5563); background:var(--color-bg-bar, #F3F4F6); padding:1px 6px; border-radius:2px; border:1px solid var(--color-bar-border, #E5E7EB);">{b}</span>'
            for b in edu_badges
        ])

        sections = []

        # 1. Education
        edu_html = f"""
    <section id="education">
      <div class="section-header">
        <h2>教育背景</h2>
        <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
      </div>
      <div class="org-bar" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:3px; margin-bottom:3px;">
        <div class="org-left" style="display:flex; align-items:baseline; gap:8px;">
          <span class="org-title" style="font-weight:700; font-size:11.8px; color:var(--color-primary-dark, #0F172A);">{cand.get('school', '')}</span>
          <span class="org-role" style="font-weight:600; font-size:11.2px; color:var(--color-accent, #0284C7);">{cand.get('degree', '')}</span>
        </div>
        <div class="org-right" style="font-size:10.5px; color:var(--color-muted, #64748B);">{cand.get('edu_time', '')}</div>
      </div>
      <div style="display:flex; flex-wrap:wrap; gap:5px; margin-top:2px; margin-bottom:2px;">
        {badge_spans}
      </div>
    </section>
    """
        sections.append(edu_html)

        # 2. Experience
        if exp_list:
            exp_parts = ["""
        <section id="experience">
          <div class="section-header">
            <h2>实习经历</h2>
            <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
          </div>
        """]
            for exp in exp_list:
                bullets_li = "".join([f"<li>{b}</li>" for b in exp.get("bullets", [])])
                exp_parts.append(f"""
            <div class="org-bar" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:4px; margin-bottom:2px;">
              <div class="org-left" style="display:flex; align-items:baseline; gap:8px;">
                <span class="org-title" style="font-weight:700; font-size:11.8px; color:var(--color-primary-dark, #0F172A);">{exp.get('org', '')}</span>
                <span class="org-role" style="font-weight:600; font-size:11.2px; color:var(--color-accent, #0284C7);">{exp.get('role', '')}</span>
              </div>
              <div class="org-right" style="font-size:10.5px; color:var(--color-muted, #64748B);">{exp.get('time', '')}</div>
            </div>
            <ul>{bullets_li}</ul>
            """)
            exp_parts.append("</section>")
            sections.append("\n".join(exp_parts))

        # 3. Projects & Campus
        if proj_list:
            proj_parts = ["""
        <section id="projects">
          <div class="section-header">
            <h2>校园与实践经历</h2>
            <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
          </div>
        """]
            for proj in proj_list:
                bullets_li = "".join([f"<li>{b}</li>" for b in proj.get("bullets", [])])
                proj_parts.append(f"""
            <div class="project-header" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:4px; margin-bottom:2px;">
              <div style="display:flex; align-items:baseline; gap:8px;">
                <span style="font-weight:700; font-size:11.8px; color:var(--color-primary-dark, #0F172A);">{proj.get('name', '')}</span>
                <span style="font-weight:600; font-size:11.2px; color:var(--color-accent, #0284C7);">{proj.get('role', '')}</span>
              </div>
              <div style="font-size:10.5px; color:var(--color-muted, #64748B);">{proj.get('time', '')}</div>
            </div>
            <ul>{bullets_li}</ul>
            """)
            proj_parts.append("</section>")
            sections.append("\n".join(proj_parts))

        # 4. Competencies
        if comps:
            skill_rows = []
            for k, v in comps.items():
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                skill_rows.append(f"""
            <li style="display:flex; align-items:baseline; gap:6px; margin-bottom:2px;">
              <span style="font-weight:700; min-width:85px; color:var(--color-primary-dark, #0F172A);">{k}：</span>
              <span style="color:var(--color-text, #1E293B);">{val}</span>
            </li>
            """)
            skills_html = f"""
        <section id="skills">
          <div class="section-header">
            <h2>专业技能</h2>
            <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
          </div>
          <ul style="list-style:none; padding-left:0; margin-top:3px;">
            {"".join(skill_rows)}
          </ul>
        </section>
        """
            sections.append(skills_html)

        return "\n".join(sections)

    def _render_header_html(self, theme_name: str, photo: bool) -> str:
        """Builds header markup with optional photo placeholder."""
        cand = self.profile.get("candidate", {})
        name = cand.get("name", "")
        title = cand.get("title", "运营岗")
        phone = cand.get("phone", "")
        email = cand.get("email", "")
        location = cand.get("location", "")

        photo_html = ""
        if photo:
            photo_html = """
      <div class="photo-placeholder" style="width:72px; height:96px; border:1.5px dashed var(--color-border, #CBD5E1); background:var(--color-bg-subtle, #F8FAFC); border-radius:3px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; flex-shrink:0;" title="预留证件照位置">
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%;">
          <span style="font-size:8.5px; color:var(--color-muted, #64748B); line-height:1.2;">预留证件照<br>一寸 / 二寸</span>
        </div>
      </div>
            """

        loc_str = f"<span>•</span><span>{location}</span>" if location else ""

        return f"""
    <header style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom:1.5px solid var(--color-primary, #0F172A); padding-bottom:5px;">
      <div style="flex:1; padding-right:12px;">
        <div class="header-top" style="display:flex; align-items:baseline; justify-content:space-between; border-bottom:none; margin-bottom:0; padding-bottom:0;">
          <h1 style="font-size:22px; font-weight:700; margin-bottom:2px;">{name}</h1>
          <span style="font-size:12px; font-weight:600; color:var(--color-accent, #0284C7);">求职意向：{title}</span>
        </div>
        <div class="contacts" style="display:flex; gap:8px; font-size:11px; color:var(--color-muted, #64748B); margin-top:2px;">
          <span>{phone}</span>
          <span>•</span>
          <span><a href="mailto:{email}" style="color:inherit; text-decoration:none;">{email}</a></span>
          {loc_str}
        </div>
      </div>
      {photo_html}
    </header>
    """

    def build_html_theme(
        self,
        theme_name: str,
        output_dir: Union[str, Path],
        photo: bool = True,
        autofit: bool = True,
    ) -> Dict[str, Path]:
        """Builds HTML + CSS based resume theme, optionally applying single-page AutoFit."""
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        template_file = self.template_dir / f"{theme_name}.html"
        if not template_file.exists():
            # Fallback to ApexResume/themes
            template_file = PROJECT_ROOT / "ApexResume" / "themes" / f"{theme_name}.html"
        if not template_file.exists():
            raise FileNotFoundError(f"Template not found for theme {theme_name}")

        raw_template = template_file.read_text(encoding="utf-8")
        header_html = self._render_header_html(theme_name, photo)
        sections_html = self._render_sections_html(theme_name)

        header_regex = re.compile(r"<header>.*?</header>", re.DOTALL)
        if header_regex.search(raw_template):
            populated_html = header_regex.sub(header_html, raw_template)
        else:
            populated_html = raw_template

        populated_html = populated_html.replace("{{SECTIONS_CONTENT}}", sections_html)

        clean_theme_name = theme_name.replace("-", "_")
        html_path = out_dir / f"resume_{clean_theme_name}.html"
        pdf_path = out_dir / f"resume_{clean_theme_name}.pdf"

        if autofit:
            # Write to a temporary file for AutoFit engine
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
                tmp.write(populated_html)
                tmp_path = Path(tmp.name)

            try:
                success, msg, details = self.autofit_engine.fit_to_single_page(
                    input_html_path=tmp_path,
                    output_html_path=html_path,
                    output_pdf_path=pdf_path,
                )
                if not success:
                    # Fallback write and render
                    html_path.write_text(populated_html, encoding="utf-8")
                    self.renderer.render_pdf(html_path, pdf_path)
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass
        else:
            html_path.write_text(populated_html, encoding="utf-8")
            self.renderer.render_pdf(html_path, pdf_path)

        return {"html": html_path, "pdf": pdf_path}

    def build_ats_plain(self, output_dir: Union[str, Path], photo: bool = True) -> Dict[str, Path]:
        """Builds ATS-friendly Markdown and single-column HTML with reserved photo slot."""
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        cand = self.profile.get("candidate", {})
        comps = self.profile.get("competencies", {})
        exp_list = self.profile.get("experience", [])
        proj_list = self.profile.get("projects", [])
        edu_badges = cand.get("education_badges", [])

        # 1. Markdown file
        photo_tag = " | 照片：预留证件照位置" if photo else ""
        md_lines = [
            f"# {cand.get('name', '')}",
            f"求职意向：{cand.get('title', '运营岗')}",
            f"电话：{cand.get('phone', '')} | 邮箱：{cand.get('email', '')} | {cand.get('location', '')}{photo_tag}",
            "",
            "---",
            "",
            "## 教育背景",
            f"### {cand.get('school', '')} ｜ {cand.get('degree', '')} ｜ {cand.get('edu_time', '')}",
        ]
        for b in edu_badges:
            md_lines.append(f"- {b}")

        if exp_list:
            md_lines.extend(["", "---", "", "## 实习经历"])
            for exp in exp_list:
                md_lines.extend([
                    f"### {exp.get('org', '')} ｜ {exp.get('role', '')}",
                    f"**任职时间**：{exp.get('time', '')}",
                    "",
                ])
                for b in exp.get("bullets", []):
                    md_lines.append(f"- {b}")
                md_lines.append("")

        if proj_list:
            md_lines.extend(["---", "", "## 校园与实践经历"])
            for proj in proj_list:
                md_lines.extend([
                    f"### {proj.get('name', '')} ｜ {proj.get('role', '')}",
                    f"**时间**：{proj.get('time', '')}",
                    "",
                ])
                for b in proj.get("bullets", []):
                    md_lines.append(f"- {b}")
                md_lines.append("")

        if comps:
            md_lines.extend(["---", "", "## 专业技能"])
            for k, v in comps.items():
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                md_lines.append(f"- **{k}：**{val}")
            md_lines.append("")

        md_path = out_dir / "resume_ats_plain.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        # 2. ATS Single-Column Clean HTML
        photo_box = ""
        if photo:
            photo_box = """
    <div style="width: 72px; height: 96px; border: 1.5px dashed #4b5563; background: #f9fafb; border-radius: 2px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; flex-shrink: 0;" title="预留证件照位置">
      <span style="font-size: 8pt; color: #4b5563; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
    </div>
            """

        ats_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Resume - ATS Plain ({cand.get('name', '')})</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 12mm 15mm;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: Arial, Helvetica, "SimSun", sans-serif;
      font-size: 10.5pt;
      line-height: 1.5;
      color: #000000;
      background: #FFFFFF;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10pt;
      border-bottom: 1pt solid #000000;
      padding-bottom: 6pt;
    }}
    h1 {{
      font-size: 20pt;
      font-weight: bold;
      margin: 0 0 3pt 0;
    }}
    .contact {{
      font-size: 10pt;
      color: #222222;
    }}
    h2 {{
      font-size: 12pt;
      font-weight: bold;
      border-bottom: 0.8pt solid #333333;
      padding-bottom: 2pt;
      margin-top: 10pt;
      margin-bottom: 4pt;
      text-transform: uppercase;
    }}
    .item-header {{
      display: flex;
      justify-content: space-between;
      font-size: 10.5pt;
      font-weight: bold;
      margin-top: 4pt;
    }}
    ul {{
      margin: 2pt 0 6pt 0;
      padding-left: 18pt;
    }}
    li {{
      font-size: 10pt;
      margin-bottom: 2pt;
      text-align: justify;
    }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>{cand.get('name', '')}</h1>
      <div style="font-size: 11pt; font-weight: bold; margin-bottom: 3pt;">求职意向：{cand.get('title', '运营岗')}</div>
      <div class="contact">
        电话：{cand.get('phone', '')} &nbsp;|&nbsp; 邮箱：{cand.get('email', '')} &nbsp;|&nbsp; {cand.get('location', '')}
      </div>
    </div>
    {photo_box}
  </div>

  <h2>教育背景</h2>
  <div class="item-header">
    <span>{cand.get('school', '')} · {cand.get('degree', '')}</span>
    <span>{cand.get('edu_time', '')}</span>
  </div>
  <ul>{"".join([f'<li>{b}</li>' for b in edu_badges])}</ul>
"""
        if exp_list:
            ats_html += "  <h2>实习经历</h2>\n"
            for exp in exp_list:
                bullets = "".join([f"<li>{b}</li>" for b in exp.get("bullets", [])])
                ats_html += f"""  <div class='item-header'><span>{exp.get('org', '')} · {exp.get('role', '')}</span><span>{exp.get('time', '')}</span></div>
  <ul>{bullets}</ul>
"""

        if proj_list:
            ats_html += "  <h2>校园与实践经历</h2>\n"
            for p in proj_list:
                bullets = "".join([f"<li>{b}</li>" for b in p.get("bullets", [])])
                ats_html += f"""  <div class='item-header'><span>{p.get('name', '')} · {p.get('role', '')}</span><span>{p.get('time', '')}</span></div>
  <ul>{bullets}</ul>
"""

        if comps:
            ats_html += "  <h2>专业技能</h2>\n  <ul>"
            for k, v in comps.items():
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                ats_html += f"<li><b>{k}：</b>{val}</li>"
            ats_html += "</ul>\n"

        ats_html += "</body>\n</html>"

        html_path = out_dir / "resume_ats_plain.html"
        html_path.write_text(ats_html, encoding="utf-8")

        pdf_path = out_dir / "resume_ats_plain.pdf"
        self.renderer.render_pdf(html_path, pdf_path)

        return {"md": md_path, "html": html_path, "pdf": pdf_path}

    def build_academic_latex(self, output_dir: Union[str, Path], photo: bool = True) -> Dict[str, Path]:
        """Builds academic LaTeX resume, standalone HTML twin, and PDF."""
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        tex_src = self.academic_exporter.generate_latex(self.profile, reserve_photo=photo)
        tex_path = out_dir / "resume_academic_latex.tex"
        tex_path.write_text(tex_src, encoding="utf-8")

        html_src = self.academic_exporter.generate_latex_html_preview(self.profile, reserve_photo=photo)
        html_path = out_dir / "resume_academic_latex.html"
        html_path.write_text(html_src, encoding="utf-8")

        pdf_path = out_dir / "resume_academic_latex.pdf"
        # Try native LaTeX compile first; if unavailable, render the LaTeX-style HTML
        if not self.academic_exporter.compile_latex(tex_path, pdf_path):
            self.renderer.render_pdf(html_path, pdf_path)

        return {"tex": tex_path, "html": html_path, "pdf": pdf_path}

    def build_academic_typst(self, output_dir: Union[str, Path], photo: bool = True) -> Dict[str, Path]:
        """Builds modern academic Typst resume and compiles to PDF."""
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        typ_src = self.academic_exporter.generate_typst(self.profile, reserve_photo=photo)
        typ_path = out_dir / "resume_academic_typst.typ"
        typ_path.write_text(typ_src, encoding="utf-8")

        pdf_path = out_dir / "resume_academic_typst.pdf"
        self.academic_exporter.compile_typst(typ_path, pdf_path)

        return {"typ": typ_path, "pdf": pdf_path}

    def build_theme(
        self,
        theme: str,
        output_dir: Union[str, Path],
        photo: bool = True,
        autofit: bool = True,
    ) -> Dict[str, Path]:
        """Builds a specific theme by name."""
        theme_normalized = theme.lower().replace("_", "-")
        if theme_normalized in ("modern-navy", "silicon-clean", "classic-tech"):
            return self.build_html_theme(theme_normalized, output_dir, photo=photo, autofit=autofit)
        elif theme_normalized == "ats-plain":
            return self.build_ats_plain(output_dir, photo=photo)
        elif theme_normalized in ("academic-latex", "latex"):
            return self.build_academic_latex(output_dir, photo=photo)
        elif theme_normalized in ("academic-typst", "typst"):
            return self.build_academic_typst(output_dir, photo=photo)
        else:
            raise ValueError(f"Unknown resume theme '{theme}'. Choices: {self.THEMES}")

    def build_all(
        self,
        output_dir: Union[str, Path],
        photo: bool = True,
        autofit: bool = True,
    ) -> Dict[str, Dict[str, Path]]:
        """Builds all 6 resume variants."""
        results = {}
        for t in self.THEMES:
            results[t] = self.build_theme(t, output_dir, photo=photo, autofit=autofit)
        return results
