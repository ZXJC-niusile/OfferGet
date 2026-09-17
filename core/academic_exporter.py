"""
OfferGet Academic Exporter Engine (academic_exporter.py)
=========================================================
Exports CandidateProfile SSOT to Native Academic LaTeX and Typst Resumes:
1. LaTeX Generator:
   - High-density academic typography (xeCJK, FiraSans, SourceHanSansCN).
   - Structured sections: Education (with badges), Experience, Projects,
     Publications, and Competencies.
   - Optional photo reservation via LaTeX \\fbox geometry.
2. Typst Generator:
   - Modern, reproducible markup with lightning-fast native compilation.
   - Optional photo reservation block.
3. Universal HTML Preview & PDF Compiler:
   - Instant HTML preview with LaTeX-like styling for browser rendering.
   - Typst & XeLaTeX compilation support.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def _image_to_base64_data_uri(image_path: Optional[Union[str, Path]]) -> Optional[str]:
    """Converts a local image file to a base64 data URI."""
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



def escape_latex(text: str) -> str:
    """Escapes special LaTeX characters."""
    if not text:
        return ""
    text = str(text)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, rep in replacements.items():
        text = text.replace(char, rep)
    return text


class AcademicExporter:
    """
    Renders CandidateProfile JSON into production-ready LaTeX and Typst source code,
    with photo reservation and compilation support.
    """

    def generate_latex(
        self,
        profile: Dict[str, Any],
        reserve_photo: bool = False,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Generates standard academic Chinese/English LaTeX source (.tex).
        """
        cand = profile.get("candidate", {})
        name = escape_latex(cand.get("name", "候选人"))
        title = escape_latex(cand.get("title", "算法架构师"))
        email = escape_latex(cand.get("email", "candidate@example.com"))
        phone = escape_latex(cand.get("phone", "+86 138-0000-0000"))
        degree = escape_latex(cand.get("degree", ""))
        school = escape_latex(cand.get("school", ""))
        location = escape_latex(cand.get("location", ""))
        edu_time = escape_latex(cand.get("edu_time", ""))
        photo_needed = reserve_photo or cand.get("reserve_photo", False) or (photo_path is not None)

        lines = [
            r"\documentclass[a4paper,11pt]{article}",
            r"\usepackage{xeCJK}",
            r"\usepackage[margin=1.5cm]{geometry}",
            r"\usepackage{hyperref}",
            r"\usepackage{enumitem}",
            r"\usepackage{titlesec}",
            r"\usepackage{xcolor}",
            r"\usepackage{graphicx}",
            r"\pagestyle{empty}",
            r"\setCJKmainfont{SimSun}",
            r"\titlespacing{\section}{0pt}{10pt}{4pt}",
            r"\titleformat{\section}{\large\bfseries\color{blue!70!black}}{}{0em}{}[\titlerule]",
            r"\begin{document}",
            r"\noindent",
        ]

        # Header block
        if photo_needed:
            loc_str = f" \\quad | \\quad {location}" if location else ""
            if photo_path and Path(photo_path).is_file():
                posix_path = Path(photo_path).resolve().as_posix()
                photo_box_tex = f"  \\fbox{{\\includegraphics[width=55pt,height=75pt,keepaspectratio=false]{{{posix_path}}}}}"
            else:
                photo_box_tex = r"  \fbox{\parbox[c][75pt][c]{55pt}{\centering \small 预留证件照\\一寸/二寸}}"

            lines.extend([
                r"\begin{minipage}[c]{0.78\textwidth}",
                f"  {{\\LARGE \\textbf{{{name}}}}} \\\\[4pt]",
                f"  \\textbf{{\\color{{blue!70!black}}求职意向：{title}}} \\\\[3pt]",
                f"  电话：{phone} \\quad | \\quad 邮箱：\\href{{mailto:{email}}}{{{email}}}{loc_str}",
                r"\end{minipage}%",
                r"\hfill",
                r"\begin{minipage}[c]{0.20\textwidth}",
                r"  \flushright",
                photo_box_tex,
                r"\end{minipage}",
                r"\vspace{6pt}",
            ])
        else:
            loc_str = f" \\quad | \\quad {location}" if location else ""
            lines.extend([
                r"\begin{center}",
                f"  {{\\LARGE \\textbf{{{name}}}}} \\\\[4pt]",
                f"  {title} \\quad | \\quad {phone} \\quad | \\quad \\href{{mailto:{email}}}{{{email}}}{loc_str}",
                r"\end{center}",
                r"\vspace{-4pt}",
            ])

        # 1. Education
        edu_rows = cand.get("education_rows", [])
        if not edu_rows and cand.get("education_badges"):
            from core.profile_adapter import group_education_badges_into_rows
            edu_rows = group_education_badges_into_rows(cand["education_badges"])

        lines.extend([
            r"\section*{教育背景}",
        ])
        time_part = f" \\hfill {escape_latex(edu_time)}" if edu_time else ""
        degree_disp = re.sub(r"\s*[｜|]\s*", r" \\quad | \\quad ", escape_latex(degree))
        degree_part = f" \\quad | \\quad {degree_disp}" if degree else ""
        lines.append(f"\\noindent \\textbf{{{escape_latex(school)}}}{degree_part}{time_part} \\\\[2pt]")
        for i, row in enumerate(edu_rows):
            escaped_row = re.sub(r"\s*[｜|]\s*", r" \\quad | \\quad ", escape_latex(row))
            trailing = r" \\[1pt]" if i < len(edu_rows) - 1 else r" \vspace{2pt}"
            lines.append(f"\\noindent {escaped_row}{trailing}")

        # 2. Work / Internship Experience
        experiences = profile.get("experience", [])
        if experiences:
            lines.extend([
                r"\section*{实习经历}",
            ])
            for exp in experiences:
                lines.append(r"\begin{itemize}[leftmargin=*,itemsep=2pt]")
                org = escape_latex(exp.get("org", ""))
                role = escape_latex(exp.get("role", ""))
                time_str = escape_latex(exp.get("time", ""))
                lines.append(f"  \\item \\textbf{{{org}}} \\hfill \\textbf{{{role}}} ({time_str})")
                bullets = exp.get("bullets", [])
                if bullets:
                    lines.append(r"  \begin{itemize}[leftmargin=*,itemsep=1pt]")
                    for b in bullets:
                        lines.append(f"    \\item {escape_latex(b)}")
                    lines.append(r"  \end{itemize}")
                lines.append(r"\end{itemize}")

        # 3. Projects & Practical Experience
        projects = profile.get("projects", [])
        if projects:
            p_title = "科研与架构项目经历" if profile.get("publications") else "校园与实践经历"
            lines.extend([
                f"\\section*{{{p_title}}}",
            ])
            for proj in projects:
                lines.append(r"\begin{itemize}[leftmargin=*,itemsep=2pt]")
                p_name = escape_latex(proj.get("name", "项目"))
                p_role = escape_latex(proj.get("role", "架构 Owner"))
                p_time = escape_latex(proj.get("time", ""))
                time_disp = f" ({p_time})" if p_time else ""
                lines.append(f"  \\item \\textbf{{{p_name}}} \\hfill \\textbf{{{p_role}}}{time_disp}")
                bullets = proj.get("bullets", [])
                if bullets:
                    lines.append(r"  \begin{itemize}[leftmargin=*,itemsep=1pt]")
                    for b in bullets:
                        lines.append(f"    \\item {escape_latex(b)}")
                    lines.append(r"  \end{itemize}")
                lines.append(r"\end{itemize}")

        # 4. Publications (if any)
        pubs = profile.get("publications", [])
        if pubs:
            lines.extend([
                r"\section*{学术发表与代表作}",
                r"\begin{enumerate}[leftmargin=*,itemsep=2pt]"
            ])
            for p in pubs:
                p_p_title = escape_latex(p.get("title", ""))
                p_venue = escape_latex(p.get("venue", ""))
                lines.append(f"  \\item \\textbf{{{p_p_title}}} -- \\textit{{{p_venue}}}")
            lines.append(r"\end{enumerate}")

        # 5. Competencies / Skills
        competencies = profile.get("competencies", {})
        if competencies:
            s_title = "核心技术栈" if profile.get("publications") else "专业技能"
            lines.extend([
                f"\\section*{{{s_title}}}",
                r"\begin{itemize}[leftmargin=*,itemsep=2pt]"
            ])
            for k, vals in competencies.items():
                if isinstance(vals, list):
                    val_str = escape_latex(", ".join(str(v) for v in vals))
                else:
                    val_str = escape_latex(str(vals))
                lines.append(f"  \\item \\textbf{{{escape_latex(str(k))}}}: {val_str}")
            lines.append(r"\end{itemize}")

        lines.append(r"\end{document}")
        return "\n".join(lines)

    def generate_typst(
        self,
        profile: Dict[str, Any],
        reserve_photo: bool = False,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Generates modern Typst source (.typ).
        """
        cand = profile.get("candidate", {})
        name = cand.get("name", "候选人")
        title = cand.get("title", "运营岗")
        email = cand.get("email", "candidate@example.com")
        phone = cand.get("phone", "+86 138-0000-0000")
        school = cand.get("school", "")
        degree = cand.get("degree", "")
        location = cand.get("location", "")
        edu_time = cand.get("edu_time", "")
        photo_needed = reserve_photo or cand.get("reserve_photo", False) or (photo_path is not None)

        lines = [
            '#set page(paper: "a4", margin: (x: 1.5cm, y: 1.5cm))',
            '#set text(font: ("Source Han Sans CN", "Helvetica"), size: 10pt)',
            "",
        ]

        email_typst = str(email).replace("@", "\\@")

        if photo_needed:
            loc_disp = f" | {location}" if location else ""
            if photo_path and Path(photo_path).is_file():
                posix_path = Path(photo_path).resolve().as_posix()
                rect_body = (
                    "    #rect(width: 2.1cm, height: 2.8cm, stroke: 1pt + rgb(\"#1e3a8a\"), radius: 2pt, inset: 0pt, clip: true)[\n"
                    f"      #image(\"{posix_path}\", width: 100%, height: 100%, fit: \"cover\")\n"
                    "    ]"
                )
            else:
                rect_body = (
                    "    #rect(width: 2.1cm, height: 2.8cm, stroke: 1pt + rgb(\"#1e3a8a\"), radius: 2pt, align(center + horizon)[\n"
                    "      #text(size: 8pt, fill: rgb(\"#555555\"))[预留证件照 \\ 一寸 / 二寸]\n"
                    "    ])"
                )

            lines.extend([
                "#grid(",
                "  columns: (1fr, auto),",
                "  gutter: 15pt,",
                "  align: (left + top, right + top),",
                "  [",
                f"    #text(size: 18pt, weight: \"bold\")[{name}] \\",
                f"    #v(2pt)#text(weight: \"bold\", fill: rgb(\"#1e3a8a\"))[求职意向：{title}] \\",
                f"    #v(2pt)#text(fill: rgb(\"#555555\"))[电话：{phone} | 邮箱：{email_typst}{loc_disp}]",
                "  ],",
                "  [",
                rect_body,
                "  ]",
                ")",
                "#v(6pt)",
            ])
        else:
            lines.extend([
                f"= {name}",
                f"_{title}_ | {phone} | {email_typst}",
                "",
            ])


        # Education
        edu_rows = cand.get("education_rows", [])
        if not edu_rows and cand.get("education_badges"):
            from core.profile_adapter import group_education_badges_into_rows
            edu_rows = group_education_badges_into_rows(cand["education_badges"])

        edu_meta = f" #h(1fr) {edu_time}" if edu_time else ""
        degree_meta = f" | {degree}" if degree else ""
        lines.extend([
            "== 教育背景",
            f"*{school}*{degree_meta}{edu_meta} \\",
        ])
        for i, row in enumerate(edu_rows):
            trailing = " \\" if i < len(edu_rows) - 1 else ""
            lines.append(f"{row}{trailing}")
        lines.append("")

        # Experience
        experiences = profile.get("experience", [])
        if experiences:
            lines.append("== 实习经历")
            for exp in experiences:
                lines.append(f"=== {exp.get('org', '')} ({exp.get('role', '')}) -- {exp.get('time', '')}")
                for b in exp.get("bullets", []):
                    lines.append(f"- {b}")
            lines.append("")

        # Projects
        projects = profile.get("projects", [])
        if projects:
            p_title = "科研与架构项目经历" if profile.get("publications") else "校园与实践经历"
            lines.append(f"== {p_title}")
            for proj in projects:
                p_name = proj.get("name", "项目")
                p_role = proj.get("role", "架构 Owner")
                p_time = proj.get("time", "")
                time_disp = f" -- {p_time}" if p_time else ""
                lines.append(f"=== {p_name} ({p_role}){time_disp}")
                for b in proj.get("bullets", []):
                    lines.append(f"- {b}")
            lines.append("")

        # Publications
        pubs = profile.get("publications", [])
        if pubs:
            lines.append("== 学术发表与代表作")
            for p in pubs:
                lines.append(f"- *{p.get('title', '')}* -- _{p.get('venue', '')}_")
            lines.append("")

        # Competencies
        comps = profile.get("competencies", {})
        if comps:
            s_title = "核心技术栈" if profile.get("publications") else "专业技能"
            lines.append(f"== {s_title}")
            for k, v in comps.items():
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                lines.append(f"- *{k}*: {val}")

        return "\n".join(lines)

    def generate_latex_html_preview(
        self,
        profile: Dict[str, Any],
        reserve_photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Generates single-page A4 HTML styled cleanly like LaTeX, with photo placeholder.
        Allows instant browser preview and headless PDF rendering without local LaTeX tools.
        """
        cand = profile.get("candidate", {})
        name = cand.get("name", "候选人")
        title = cand.get("title", "运营岗")
        email = cand.get("email", "candidate@example.com")
        phone = cand.get("phone", "+86 138-0000-0000")
        school = cand.get("school", "")
        degree = cand.get("degree", "")
        location = cand.get("location", "")
        edu_time = cand.get("edu_time", "")
        edu_badges = cand.get("education_badges", [])
        edu_rows = cand.get("education_rows", [])
        if not edu_rows and edu_badges:
            from core.profile_adapter import group_education_badges_into_rows
            edu_rows = group_education_badges_into_rows(edu_badges)
        edu_rows_html = "".join([f'<div style="margin-top:2pt;">{r}</div>' for r in edu_rows])
        exp_list = profile.get("experience", [])
        proj_list = profile.get("projects", [])
        comps = profile.get("competencies", {})
        photo_needed = reserve_photo or cand.get("reserve_photo", False) or (photo_path is not None)

        photo_html = ""
        if photo_needed:
            photo_data_uri = _image_to_base64_data_uri(photo_path)
            if photo_data_uri:
                photo_html = f"""
    <div style="width: 72px; height: 96px; border: 1.5px dashed #1e3a8a; background: #fafafa; border-radius: 3px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; flex-shrink: 0; overflow: hidden; position: relative;" title="预留证件照位置">
      <img src="{photo_data_uri}" alt="证件照" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
      <div style="display: none; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%;">
        <span style="font-size: 8.5pt; color: #555; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
      </div>
    </div>
                """
            else:
                photo_html = """
    <div style="width: 72px; height: 96px; border: 1.5px dashed #1e3a8a; background: #fafafa; border-radius: 3px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; flex-shrink: 0;" title="预留证件照位置">
      <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%;">
        <span style="font-size: 8.5pt; color: #555; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
      </div>
    </div>
                """

        loc_str = f" &nbsp;|&nbsp; {location}" if location else ""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Resume - Academic LaTeX Style ({name})</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 10mm 12mm;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: "SimSun", "Songti SC", "Times New Roman", serif;
      font-size: 10.2pt;
      line-height: 1.45;
      color: #111111;
      background: #FFFFFF;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8pt;
      border-bottom: 1.2pt solid #1e3a8a;
      padding-bottom: 6pt;
    }}
    h1 {{
      font-size: 19pt;
      font-weight: bold;
      margin: 0 0 3pt 0;
    }}
    .contact {{
      font-size: 10pt;
      color: #333333;
    }}
    h2 {{
      font-size: 11.5pt;
      font-weight: bold;
      color: #1e3a8a;
      border-bottom: 0.8pt solid #1e3a8a;
      padding-bottom: 2pt;
      margin-top: 8pt;
      margin-bottom: 3pt;
      text-transform: uppercase;
    }}
    .item-header {{
      display: flex;
      justify-content: space-between;
      font-size: 10.5pt;
      font-weight: bold;
      margin-top: 3pt;
    }}
    ul {{
      margin: 2pt 0 4pt 0;
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
      <h1>{name}</h1>
      <div style="font-size: 11pt; font-weight: bold; color: #1e3a8a; margin-bottom: 3pt;">求职意向：{title}</div>
      <div class="contact">
        电话：{phone} &nbsp;|&nbsp; 邮箱：{email}{loc_str}
      </div>
    </div>
    {photo_html}
  </div>

  <h2>教育背景</h2>
  <div class="item-header">
    <span>{school} ｜ {degree}</span>
    <span>{edu_time}</span>
  </div>
  <div class="edu-content" style="font-size: 10pt; color: #333333; line-height: 1.45; margin-top: 2pt; margin-bottom: 4pt;">
    {edu_rows_html}
  </div>
"""

        if exp_list:
            html += "  <h2>实习经历</h2>\n"
            for exp in exp_list:
                bullets = "".join([f"<li>{b}</li>" for b in exp.get("bullets", [])])
                html += f"""  <div class='item-header'><span>{exp.get('org', '')} · {exp.get('role', '')}</span><span>{exp.get('time', '')}</span></div>
  <ul>{bullets}</ul>
"""

        if proj_list:
            p_title = "科研与架构项目经历" if profile.get("publications") else "校园与实践经历"
            html += f"  <h2>{p_title}</h2>\n"
            for p in proj_list:
                bullets = "".join([f"<li>{b}</li>" for b in p.get("bullets", [])])
                html += f"""  <div class='item-header'><span>{p.get('name', '')} · {p.get('role', '')}</span><span>{p.get('time', '')}</span></div>
  <ul>{bullets}</ul>
"""

        if comps:
            s_title = "核心技术栈" if profile.get("publications") else "专业技能"
            html += f"  <h2>{s_title}</h2>\n  <ul>"
            for k, v in comps.items():
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                html += f"<li><b>{k}：</b>{val}</li>"
            html += "</ul>\n"

        html += "</body>\n</html>"
        return html

    def compile_typst(self, typ_path: str | Path, pdf_path: str | Path) -> bool:
        """Compiles Typst file to PDF using Python package or CLI."""
        typ_file = Path(typ_path).resolve()
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            import typst
            typst.compile(typ_file, output=str(pdf_file))
            return True
        except Exception:
            pass

        typst_cli = shutil.which("typst")
        if typst_cli:
            res = subprocess.run([typst_cli, "compile", str(typ_file), str(pdf_file)], capture_output=True)
            return res.returncode == 0

        return False

    def compile_latex(self, tex_path: str | Path, pdf_path: str | Path) -> bool:
        """Compiles LaTeX file to PDF using xelatex if available."""
        tex_file = Path(tex_path).resolve()
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        xelatex_cli = shutil.which("xelatex")
        if not xelatex_cli:
            return False

        res = subprocess.run(
            [xelatex_cli, "-interaction=nonstopmode", f"-output-directory={tex_file.parent}", str(tex_file)],
            capture_output=True,
            timeout=60
        )
        compiled_pdf = tex_file.with_suffix(".pdf")
        if compiled_pdf.exists() and compiled_pdf != pdf_file:
            shutil.move(str(compiled_pdf), str(pdf_file))
        return res.returncode == 0
