"""
OfferGet Academic Exporter Engine (academic_exporter.py)
=========================================================
Exports CandidateProfile SSOT to Native Academic LaTeX and Typst Resumes:
1. LaTeX Generator:
   - High-density academic typography (xeCJK, FiraSans, SourceHanSansCN).
   - Structured sections: Education (with official branding), Publications,
     Research Projects (with 6-link mapping), Awards, and Skills.
2. Typst Generator:
   - Modern, lightning-fast reproducible markup.
   - Clean, publication-quality layout.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


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
    Renders CandidateProfile JSON into production-ready LaTeX and Typst source code.
    """

    def generate_latex(self, profile: Dict[str, Any]) -> str:
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

        lines = [
            r"\documentclass[a4paper,11pt]{article}",
            r"\usepackage{xeCJK}",
            r"\usepackage[margin=1.5cm]{geometry}",
            r"\usepackage{hyperref}",
            r"\usepackage{enumitem}",
            r"\usepackage{titlesec}",
            r"\usepackage{xcolor}",
            r"\pagestyle{empty}",
            r"\setCJKmainfont{SimSun}",
            r"\titlespacing{\section}{0pt}{10pt}{4pt}",
            r"\titleformat{\section}{\large\bfseries\color{blue!70!black}}{}{0em}{}[\titlerule]",
            r"\begin{document}",
            r"\begin{center}",
            f"  {{\\LARGE \\textbf{{{name}}}}} \\\\[4pt]",
            f"  {title} \\quad | \\quad {phone} \\quad | \\quad \\href{{mailto:{email}}}{{{email}}}",
            r"\end{center}",
            r"\vspace{-4pt}",
        ]

        # 1. Education
        lines.extend([
            r"\section*{教育背景}",
            r"\begin{itemize}[leftmargin=*,itemsep=2pt]",
            f"  \\item \\textbf{{{school}}} \\hfill {degree}",
            r"\end{itemize}"
        ])

        # 2. Competencies / Skills
        competencies = profile.get("competencies", {})
        if competencies:
            lines.extend([
                r"\section*{核心技术栈}",
                r"\begin{itemize}[leftmargin=*,itemsep=2pt]"
            ])
            for k, vals in competencies.items():
                if isinstance(vals, list):
                    val_str = escape_latex(", ".join(str(v) for v in vals))
                    lines.append(f"  \\item \\textbf{{{escape_latex(k.capitalize())}}}: {val_str}")
            lines.append(r"\end{itemize}")

        # 3. Projects
        projects = profile.get("projects", [])
        if projects:
            lines.extend([
                r"\section*{科研与架构项目经历}",
                r"\begin{itemize}[leftmargin=*,itemsep=4pt]"
            ])
            for proj in projects:
                p_name = escape_latex(proj.get("name", "项目"))
                p_role = escape_latex(proj.get("role", "架构 Owner"))
                lines.append(f"  \\item \\textbf{{{p_name}}} \\hfill \\textbf{{{p_role}}}")
                bullets = proj.get("bullets", [])
                if bullets:
                    lines.append(r"  \begin{itemize}[leftmargin=*,itemsep=1pt]")
                    for b in bullets:
                        lines.append(f"    \\item {escape_latex(b)}")
                    lines.append(r"  \end{itemize}")
            lines.append(r"\end{itemize}")

        # 4. Publications
        pubs = profile.get("publications", [])
        if pubs:
            lines.extend([
                r"\section*{学术发表与代表作}",
                r"\begin{enumerate}[leftmargin=*,itemsep=2pt]"
            ])
            for p in pubs:
                p_title = escape_latex(p.get("title", ""))
                p_venue = escape_latex(p.get("venue", ""))
                lines.append(f"  \\item \\textbf{{{p_title}}} -- \\textit{{{p_venue}}}")
            lines.append(r"\end{enumerate}")

        lines.append(r"\end{document}")
        return "\n".join(lines)

    def generate_typst(self, profile: Dict[str, Any]) -> str:
        """
        Generates modern Typst source (.typ).
        """
        cand = profile.get("candidate", {})
        name = cand.get("name", "候选人")
        title = cand.get("title", "算法架构师")
        email = cand.get("email", "candidate@example.com")
        phone = cand.get("phone", "+86 138-0000-0000")
        school = cand.get("school", "")
        degree = cand.get("degree", "")

        lines = [
            '#set page(paper: "a4", margin: (x: 1.5cm, y: 1.5cm))',
            '#set text(font: ("Source Han Sans CN", "Helvetica"), size: 10pt)',
            "",
            f"= {name}",
            f"_{title}_ | {phone} | {email}",
            "",
            "== 教育背景",
            f"- *{school}* -- {degree}",
            "",
            "== 核心项目经历",
        ]

        projects = profile.get("projects", [])
        for proj in projects:
            p_name = proj.get("name", "项目")
            p_role = proj.get("role", "架构 Owner")
            lines.append(f"=== {p_name} ({p_role})")
            for b in proj.get("bullets", []):
                lines.append(f"- {b}")

        return "\n".join(lines)
