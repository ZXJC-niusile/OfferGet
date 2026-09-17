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

import base64
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

try:
    from ApexResume.core.audit import ResumeAuditor
except ImportError:
    try:
        from core.audit import ResumeAuditor  # type: ignore
    except ImportError:
        ResumeAuditor = None  # type: ignore


def _image_to_base64_data_uri(image_path: Optional[Union[str, Path]]) -> Optional[str]:
    """Reads a local image file (jpg/png/webp) and returns a base64 data URI."""
    if not image_path:
        return None
    p = Path(image_path).resolve()
    if not p.is_file():
        return None
    suffix = p.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }
    mime_type = mime_types.get(suffix, "image/jpeg")
    try:
        data = p.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{b64}"
    except Exception:
        return None



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
        photo_path: Optional[Union[str, Path]] = None,
        anonymize: Optional[str] = None,
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

        self.raw_profile = raw_data
        self.anonymize = anonymize
        self.photo_path = Path(photo_path).resolve() if photo_path else None
        self.deanon_map: Dict[str, str] = {}

        self.profile = self._resolve_profile(anonymize=self.anonymize)
        self.academic_exporter = AcademicExporter()

        self.template_dir = Path(template_dir).resolve() if template_dir else (PROJECT_ROOT / "ApexResume" / "themes")

        self.renderer = renderer or BrowserRenderer()
        self.autofit_engine = autofit_engine or AutoFitEngine(self.renderer)

    def _resolve_profile(self, anonymize: Optional[str] = None) -> Dict[str, Any]:
        """Resolves profile data, applying privacy anonymization if requested."""
        level = anonymize if anonymize is not None else self.anonymize
        normalized = normalize_candidate_profile(self.raw_profile)
        if level:
            if level not in ("standard", "strict"):
                raise ValueError(f"Unknown sensitivity level: '{level}'. Supported levels: 'standard', 'strict'.")
            from core.anonymizer import anonymize_profile
            anon_data, deanon_map = anonymize_profile(normalized, level=level)
            self.deanon_map = deanon_map
            return normalize_candidate_profile(anon_data)
        return normalized

    def _render_sections_html(self, theme_name: str, profile: Optional[Dict[str, Any]] = None) -> str:
        """Renders standard HTML sections for HTML-based themes."""
        prof = profile or self.profile
        cand = prof.get("candidate", {})
        edu_badges = cand.get("education_badges", [])
        exp_list = prof.get("experience", [])
        proj_list = prof.get("projects", [])
        comps = prof.get("competencies", {})

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

    def _render_header_html(
        self,
        theme_name: str,
        photo: bool,
        photo_path: Optional[Union[str, Path]] = None,
        profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Builds header markup with optional photo placeholder."""
        prof = profile or self.profile
        cand = prof.get("candidate", {})
        name = cand.get("name", "")
        title = cand.get("title", "运营岗")
        phone = cand.get("phone", "")
        email = cand.get("email", "")
        location = cand.get("location", "")

        eff_photo_path = photo_path or self.photo_path
        photo_enabled = photo or (eff_photo_path is not None)

        photo_html = ""
        if photo_enabled:
            data_uri = _image_to_base64_data_uri(eff_photo_path)
            if data_uri:
                photo_html = f"""
      <div class="photo-placeholder" style="width:72px; height:96px; border:1.5px dashed var(--color-border, #CBD5E1); background:var(--color-bg-subtle, #F8FAFC); border-radius:3px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; flex-shrink:0; overflow:hidden; position:relative;" title="预留证件照位置">
        <img src="{data_uri}" alt="证件照" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
        <div style="display:none; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%;">
          <span style="font-size:8.5px; color:var(--color-muted, #64748B); line-height:1.2;">预留证件照<br>一寸 / 二寸</span>
        </div>
      </div>
                """
            else:
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
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Builds HTML + CSS based resume theme, optionally applying single-page AutoFit."""
        prof = self._resolve_profile(anonymize)
        eff_photo_path = photo_path or self.photo_path

        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        template_file = self.template_dir / f"{theme_name}.html"
        if not template_file.exists():
            # Fallback to ApexResume/themes
            template_file = PROJECT_ROOT / "ApexResume" / "themes" / f"{theme_name}.html"
        if not template_file.exists():
            raise FileNotFoundError(f"Template not found for theme {theme_name}")

        raw_template = template_file.read_text(encoding="utf-8")
        header_html = self._render_header_html(theme_name, photo, photo_path=eff_photo_path, profile=prof)
        sections_html = self._render_sections_html(theme_name, profile=prof)

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

    def build_ats_plain(
        self,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Builds ATS-friendly Markdown and single-column HTML with reserved photo slot."""
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        prof = self._resolve_profile(anonymize)
        eff_photo_path = photo_path or self.photo_path
        photo_enabled = photo or (eff_photo_path is not None)

        cand = prof.get("candidate", {})
        comps = prof.get("competencies", {})
        exp_list = prof.get("experience", [])
        proj_list = prof.get("projects", [])
        edu_badges = cand.get("education_badges", [])

        # 1. Markdown file
        photo_tag = f" | 照片：{eff_photo_path}" if (photo_enabled and eff_photo_path) else (" | 照片：预留证件照位置" if photo_enabled else "")
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
        if photo_enabled:
            data_uri = _image_to_base64_data_uri(eff_photo_path)
            if data_uri:
                photo_box = f"""
    <div style="width: 72px; height: 96px; border: 1.5px dashed #4b5563; background: #f9fafb; border-radius: 2px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; flex-shrink: 0; overflow: hidden; position: relative;" title="预留证件照位置">
      <img src="{data_uri}" alt="证件照" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
      <div style="display:none; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%;">
        <span style="font-size: 8pt; color: #4b5563; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
      </div>
    </div>
                """
            else:
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

    def build_academic_latex(
        self,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Builds academic LaTeX resume, standalone HTML twin, and PDF."""
        prof = self._resolve_profile(anonymize)
        eff_photo_path = photo_path or self.photo_path
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        tex_src = self.academic_exporter.generate_latex(prof, reserve_photo=photo, photo_path=eff_photo_path)
        tex_path = out_dir / "resume_academic_latex.tex"
        tex_path.write_text(tex_src, encoding="utf-8")

        html_src = self.academic_exporter.generate_latex_html_preview(prof, reserve_photo=photo, photo_path=eff_photo_path)
        html_path = out_dir / "resume_academic_latex.html"
        html_path.write_text(html_src, encoding="utf-8")

        pdf_path = out_dir / "resume_academic_latex.pdf"
        # Try native LaTeX compile first; if unavailable, render the LaTeX-style HTML
        if not self.academic_exporter.compile_latex(tex_path, pdf_path):
            self.renderer.render_pdf(html_path, pdf_path)

        return {"tex": tex_path, "html": html_path, "pdf": pdf_path}

    def build_academic_typst(
        self,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Builds modern academic Typst resume and compiles to PDF."""
        prof = self._resolve_profile(anonymize)
        eff_photo_path = photo_path or self.photo_path
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        typ_src = self.academic_exporter.generate_typst(prof, reserve_photo=photo, photo_path=eff_photo_path)
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
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Builds a specific theme by name."""
        theme_normalized = theme.lower().replace("_", "-")
        eff_photo_path = photo_path or self.photo_path
        if theme_normalized in ("modern-navy", "silicon-clean", "classic-tech"):
            return self.build_html_theme(
                theme_normalized,
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                autofit=autofit,
                anonymize=anonymize,
            )
        elif theme_normalized == "ats-plain":
            return self.build_ats_plain(
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                anonymize=anonymize,
            )
        elif theme_normalized in ("academic-latex", "latex"):
            return self.build_academic_latex(
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                anonymize=anonymize,
            )
        elif theme_normalized in ("academic-typst", "typst"):
            return self.build_academic_typst(
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                anonymize=anonymize,
            )
        else:
            raise ValueError(f"Unknown resume theme '{theme}'. Choices: {self.THEMES}")

    def build_all(
        self,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
    ) -> Dict[str, Dict[str, Path]]:
        """Builds all 6 resume variants."""
        results = {}
        for t in self.THEMES:
            results[t] = self.build_theme(
                t,
                output_dir,
                photo=photo,
                photo_path=photo_path,
                autofit=autofit,
                anonymize=anonymize,
            )
        return results

    def audit_resume_quality(self, html_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Audits generated resume HTML quality, layout health, security, and completeness."""
        target_path = html_path if html_path is not None else self
        renderer = getattr(self, "renderer", None) if not isinstance(self, (str, Path, type)) else None
        return audit_resume_quality(target_path, renderer=renderer)


def audit_resume_quality(
    html_path: Union[str, Path],
    renderer: Optional[BrowserRenderer] = None,
) -> Dict[str, Any]:
    """
    Audits generated resume HTML quality, layout health, security, and completeness.
    Reuses ResumeAuditor from ApexResume.core.audit.
    Checks:
      1. Unreplaced placeholders ({{...}}, .todo, [待定], NaN, undefined, etc.)
      2. Dangerous tags / XSS (<script>, <iframe>, <object>, <embed>, dangerous handlers)
      3. Height overflow / page budget (renders single A4 page verification)
    Returns layout health score (0-100), checklist items, and detailed findings.
    """
    path = Path(html_path).resolve()
    if not path.exists():
        return {
            "passed": False,
            "score": 0,
            "health_score": 0,
            "critical_count": 1,
            "warning_count": 0,
            "info_count": 0,
            "page_count": 0,
            "checks": {
                "placeholders": {"passed": False, "count": 0, "issues": ["File not found"]},
                "dangerous_tags": {"passed": False, "violations": []},
                "page_overflow": {"passed": False, "page_count": 0, "details": "File not found"},
                "formatting": {"passed": False},
            },
            "findings": [{"category": "io", "severity": "critical", "message": f"HTML file not found: {path}", "target": str(path)}],
            "summary": f"Audit FAILED: File not found: {path}",
        }

    content = path.read_text(encoding="utf-8")

    # 1. Base audit using ApexResume.core.audit.ResumeAuditor
    if ResumeAuditor is not None:
        auditor = ResumeAuditor()
        auditor.audit_html_file(path)
        base_summary = auditor.summary()
    else:
        base_summary = {"findings": []}

    extra_findings = []
    checks: Dict[str, Any] = {
        "placeholders": {"passed": True, "count": 0, "issues": []},
        "dangerous_tags": {"passed": True, "violations": []},
        "page_overflow": {"passed": True, "page_count": 1, "details": "Fits within single A4 page."},
        "formatting": {"passed": True, "warnings": []},
    }

    # Extract existing placeholder findings from base auditor
    placeholder_issues = [f["message"] for f in base_summary["findings"] if f.get("category") == "html" and "placeholder" in f.get("message", "").lower()]

    # 2. Check for additional unrendered placeholders
    custom_placeholder_patterns = [
        r"\{\{[^}]+\}\}",
        r"\[待定\]",
        r"\[TODO\]",
        r"\[待补充\]",
        r"\[TBD\]",
        r"\bundefined\b",
        r"\bNaN\b",
        r"FIXME:",
        r"XXX:",
    ]
    body_match = re.search(r"<body[^>]*>(.*?)</body>", content, re.DOTALL | re.IGNORECASE)
    body_content = body_match.group(1) if body_match else content
    clean_body = re.sub(r"<style[^>]*>.*?</style>", " ", body_content, flags=re.DOTALL | re.IGNORECASE)
    clean_body = re.sub(r"<!--.*?-->", " ", clean_body, flags=re.DOTALL)
    text_content = re.sub(r"<[^>]+>", " ", clean_body)

    for pat in custom_placeholder_patterns:
        matches = re.findall(pat, text_content, flags=re.IGNORECASE)
        if matches:
            issue_msg = f"Detected unreplaced placeholder match '{pat}': {matches[:3]}"
            if issue_msg not in placeholder_issues:
                placeholder_issues.append(issue_msg)
                extra_findings.append({
                    "category": "placeholder",
                    "severity": "critical",
                    "message": issue_msg,
                    "target": str(path),
                    "details": {"matches": matches[:5]},
                })

    if placeholder_issues:
        checks["placeholders"]["passed"] = False
        checks["placeholders"]["count"] = len(placeholder_issues)
        checks["placeholders"]["issues"] = placeholder_issues

    # 3. Check for dangerous tags (Security / XSS gate)
    dangerous_tag_patterns = [
        (r"<script\b", "Script tag (<script>)"),
        (r"<iframe\b", "Inline frame (<iframe>)"),
        (r"<object\b", "Embedded object (<object>)"),
        (r"<embed\b", "Plugin embed (<embed>)"),
        (r"<form\b", "Interactive form (<form>)"),
        (r"href\s*=\s*[\"']javascript:", "javascript: URI scheme in anchor"),
    ]
    dangerous_violations = []
    for pat, desc in dangerous_tag_patterns:
        if re.search(pat, content, re.IGNORECASE):
            dangerous_violations.append(desc)
            extra_findings.append({
                "category": "security",
                "severity": "critical",
                "message": f"Dangerous HTML pattern detected: {desc}",
                "target": str(path),
                "details": {"pattern": pat},
            })

    # Check for unauthorized event handlers (allow benign onerror fallback)
    for handler_match in re.finditer(r"\b(on\w+)\s*=\s*[\"'](.*?)[\"']", content, re.IGNORECASE):
        event_name = handler_match.group(1).lower()
        event_code = handler_match.group(2)
        if event_name == "onerror" and ("display" in event_code and "style" in event_code):
            # Benign image onerror fallback
            continue
        dangerous_violations.append(f"Inline event handler '{event_name}' with suspicious code: {event_code[:30]}")
        extra_findings.append({
            "category": "security",
            "severity": "critical",
            "message": f"Dangerous inline event handler '{event_name}' detected: {event_code[:40]}",
            "target": str(path),
        })

    if dangerous_violations:
        checks["dangerous_tags"]["passed"] = False
        checks["dangerous_tags"]["violations"] = dangerous_violations

    # 4. Check for height overflow (A4 budget)
    page_count = 1
    actual_renderer = renderer or BrowserRenderer()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        test_pdf = Path(tmp_pdf.name)

    try:
        ok, pages, _ = actual_renderer.render_pdf(path, test_pdf)
        if ok and pages is not None:
            page_count = pages
            if pages > 1:
                msg = f"Resume overflows single A4 page budget: rendered {pages} pages."
                checks["page_overflow"]["passed"] = False
                checks["page_overflow"]["page_count"] = pages
                checks["page_overflow"]["details"] = msg
                extra_findings.append({
                    "category": "overflow",
                    "severity": "critical" if pages > 2 else "warning",
                    "message": msg,
                    "target": str(path),
                    "details": {"pages": pages},
                })
            else:
                checks["page_overflow"]["page_count"] = 1
    except Exception:
        if len(text_content) > 3500:
            msg = f"Content text density ({len(text_content)} chars) exceeds standard single-page A4 capacity."
            checks["page_overflow"]["passed"] = False
            checks["page_overflow"]["details"] = msg
            extra_findings.append({
                "category": "overflow",
                "severity": "warning",
                "message": msg,
                "target": str(path),
            })
    finally:
        if test_pdf.exists():
            try:
                test_pdf.unlink()
            except Exception:
                pass

    # 5. Formatting warnings
    formatting_warnings = [f["message"] for f in base_summary["findings"] if f.get("category") in ("html", "inflation")]
    if formatting_warnings:
        checks["formatting"]["passed"] = False
        checks["formatting"]["warnings"] = formatting_warnings

    # 6. Compute layout health score
    all_findings = base_summary["findings"] + extra_findings
    crit_count = sum(1 for f in all_findings if f.get("severity") == "critical")
    warn_count = sum(1 for f in all_findings if f.get("severity") == "warning")
    info_count = sum(1 for f in all_findings if f.get("severity") == "info")

    score = 100 - (crit_count * 30) - (warn_count * 8) - (info_count * 2)
    score = max(0, min(100, score))
    passed = (crit_count == 0 and score >= 70)

    return {
        "passed": passed,
        "score": score,
        "health_score": score,
        "critical_count": crit_count,
        "warning_count": warn_count,
        "info_count": info_count,
        "page_count": page_count,
        "checks": checks,
        "findings": all_findings,
        "summary": f"Resume quality audit {'PASSED' if passed else 'FAILED'} with health score {score}/100 (critical: {crit_count}, warnings: {warn_count}).",
    }
