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



from core.security_gate import (
    escape_latex,
    escape_typst,
    escape_html_text,
    escape_html_attribute,
    sanitize_url,
)


class AcademicExporter:
    """
    Renders CandidateProfile JSON into production-ready LaTeX and Typst source code,
    with photo reservation and compilation support.
    """

    def _resolve_view_model(
        self,
        profile_or_vm: Union[Any, Dict[str, Any]],
        reserve_photo: bool = False,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> Any:
        from core.resume_view_model import ResumeViewModel
        from core.profile_adapter import ProfileContext

        if isinstance(profile_or_vm, ResumeViewModel):
            return profile_or_vm
        if isinstance(profile_or_vm, ProfileContext):
            return profile_or_vm.to_view_model(photo_path=photo_path, reserve_photo=reserve_photo)
        if isinstance(profile_or_vm, dict):
            return ResumeViewModel.from_profile(profile_or_vm, photo_path=photo_path, reserve_photo=reserve_photo)
        return ResumeViewModel.from_profile({}, photo_path=photo_path, reserve_photo=reserve_photo)

    def generate_latex(
        self,
        profile: Union[Any, Dict[str, Any]],
        reserve_photo: bool = False,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Generates standard academic Chinese/English LaTeX source (.tex).
        Accepts ResumeViewModel, ProfileContext, or candidate profile dictionary.
        """
        vm = self._resolve_view_model(profile, reserve_photo=reserve_photo, photo_path=photo_path)

        name = escape_latex(vm.raw_name or "候选人")
        title = escape_latex(vm.raw_title or "")
        email = escape_latex(vm.raw_email or "")
        phone = escape_latex(vm.raw_phone or "")
        degree_raw = re.sub(r"\s*[｜|·]\s*", "  ", str(vm.raw_degree or "")).strip()
        degree = escape_latex(degree_raw)
        school = escape_latex(vm.raw_school or "")
        location = escape_latex(vm.raw_location or "")
        edu_time = escape_latex(vm.raw_edu_time or "")
        eff_photo_path = photo_path or vm.photo_path
        photo_needed = reserve_photo or vm.reserve_photo or (eff_photo_path is not None)

        lines = [
            r"\documentclass[a4paper,11pt]{article}",
            r"\usepackage{xeCJK}",
            r"\usepackage[margin=1.5cm]{geometry}",
            r"\usepackage{hyperref}",
            r"\usepackage{tabularx}",
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
        contact_parts = []
        if phone:
            contact_parts.append(f"电话：{phone}")
        if email:
            contact_parts.append(f"邮箱：\\href{{mailto:{email}}}{{{email}}}")
        if location:
            contact_parts.append(location)
        contact_tex = " \\quad | \\quad ".join(contact_parts)

        if photo_needed:
            if eff_photo_path and Path(eff_photo_path).is_file():
                posix_path = Path(eff_photo_path).resolve().as_posix()
                photo_box_tex = f"  \\includegraphics[width=55pt,height=75pt,keepaspectratio=true]{{{posix_path}}}"
            else:
                photo_box_tex = r"  \fbox{\parbox[c][75pt][c]{55pt}{\centering \small 预留证件照\\一寸/二寸}}"

            lines.extend([
                r"\begin{minipage}[c]{0.78\textwidth}",
                f"  {{\\LARGE \\textbf{{{name}}}}} \\\\[4pt]",
            ])
            if title:
                lines.append(f"  \\textbf{{\\color{{blue!70!black}}求职意向：{title}}} \\\\[3pt]")
            if contact_tex:
                lines.append(f"  {contact_tex}")
            lines.extend([
                r"\end{minipage}%",
                r"\hfill",
                r"\begin{minipage}[c]{0.20\textwidth}",
                r"  \flushright",
                photo_box_tex,
                r"\end{minipage}",
                r"\vspace{6pt}",
            ])
        else:
            title_part = f"{title} \\quad | \\quad " if title else ""
            second_line = f"  {title_part}{contact_tex}" if (title_part or contact_tex) else ""
            lines.extend([
                r"\begin{center}",
                f"  {{\\LARGE \\textbf{{{name}}}}} \\\\[4pt]",
            ])
            if second_line:
                lines.append(second_line)
            lines.extend([
                r"\end{center}",
                r"\vspace{-4pt}",
            ])

        # Postgraduate Exam
        if vm.postgraduate_exam:
            pg = vm.postgraduate_exam
            pg_school = escape_latex(pg.get("raw_target_school", pg.get("target_school", "")))
            pg_major = escape_latex(pg.get("raw_target_major", pg.get("target_major", "")))
            pg_dir = escape_latex(pg.get("raw_direction", pg.get("direction", "")))
            target_items = []
            if pg_school:
                target_items.append(f"\\textbf{{报考院校：}}{pg_school}")
            if pg_major:
                target_items.append(f"\\textbf{{报考专业：}}{pg_major}")
            if pg_dir:
                target_items.append(f"\\textbf{{研究方向：}}{pg_dir}")

            lines.extend([
                r"\section*{报考信息}",
            ])
            if target_items:
                target_str = " \\quad \\quad ".join(target_items)
                lines.append(f"\\noindent {target_str} \\\\[3pt]")

            subjects = pg.get("subjects", [])
            total_score = escape_latex(pg.get("raw_total_score", pg.get("total_score", "")))
            if subjects or total_score:
                num_cols = 1 + len(subjects) + (1 if total_score else 0)
                col_spec = "|" + "X|" * num_cols
                lines.append(f"\\noindent \\begin{{tabularx}}{{\\textwidth}}{{{col_spec}}}")
                lines.append(r"\hline")
                head_row = [r"\textbf{初试成绩}"] + [escape_latex(s.get("raw_name", s.get("name", ""))) for s in subjects]
                if total_score:
                    head_row.append(r"\textbf{总分}")
                lines.append(" & ".join(head_row) + r" \\")
                lines.append(r"\hline")
                score_row = ["得分"] + [escape_latex(s.get("raw_score", s.get("score", ""))) for s in subjects]
                if total_score:
                    score_row.append(f"\\textbf{{{total_score}}}")
                lines.append(" & ".join(score_row) + r" \\")
                lines.append(r"\hline")
                lines.append(r"\end{tabularx}")
                lines.append(r"\vspace{3pt}")

        # 1. Education
        grid = vm.education_grid_rows
        max_cols = max((len(r) for r in grid), default=1)

        degree_part = f" \\quad \\quad {degree}" if degree else ""
        time_part = f" \\hfill {edu_time}" if edu_time else ""

        lines.extend([
            r"\section*{教育背景}",
            f"\\noindent \\textbf{{{school}}}{degree_part}{time_part} \\\\[3pt]",
        ])

        if grid:
            if max_cols >= 3:
                tabular_spec = "@{}p{0.38\\textwidth}p{0.28\\textwidth}p{0.30\\textwidth}@{}"
            elif max_cols == 2:
                tabular_spec = "@{}p{0.48\\textwidth}p{0.48\\textwidth}@{}"
            else:
                tabular_spec = "@{}p{0.96\\textwidth}@{}"

            lines.append(f"\\noindent \\begin{{tabular}}{{{tabular_spec}}}")
            for r in grid:
                row_cells = []
                for i in range(max_cols):
                    cell_clean = re.sub(r"\s*[｜|]\s*", " ", r[i]).strip() if i < len(r) else ""
                    cell = escape_latex(cell_clean)
                    row_cells.append(cell)
                lines.append(" & ".join(row_cells) + r" \\")
            lines.append(r"\end{tabular}")
            lines.append(r"\vspace{2pt}")

        # 2. Work / Internship Experience
        def format_latex_bullet(text: str) -> str:
            clean = re.sub(r"<strong>(.*?)</strong>", r"**\1**", str(text), flags=re.IGNORECASE)
            parts = re.split(r"\*\*(.+?)\*\*", clean)
            res = []
            for idx, part in enumerate(parts):
                if idx % 2 == 1:
                    res.append(r"\textbf{" + escape_latex(part) + "}")
                else:
                    res.append(escape_latex(part))
            return "".join(res)

        experiences = vm.experiences
        if experiences:
            lines.extend([
                r"\section*{实习经历}",
            ])
            for exp in experiences:
                lines.append(r"\begin{itemize}[leftmargin=*,itemsep=2pt]")
                org = escape_latex(exp.get("org", ""))
                dept_str = exp.get("dept", "")
                role_str = exp.get("role", "")
                role_combined = f"{dept_str} · {role_str}" if dept_str else role_str
                role = escape_latex(role_combined)
                time_str = escape_latex(exp.get("time", ""))
                lines.append(f"  \\item \\textbf{{{org}}} \\hfill \\textbf{{{role}}} ({time_str})")
                bullets = exp.get("bullets", [])
                if bullets:
                    lines.append(r"  \begin{itemize}[leftmargin=*,itemsep=1pt]")
                    for b in bullets:
                        lines.append(f"    \\item {format_latex_bullet(b)}")
                    lines.append(r"  \end{itemize}")
                lines.append(r"\end{itemize}")

        # 3. Projects & Practical Experience
        projects = vm.projects
        pubs = vm.publications
        if projects:
            p_title = "科研与架构项目经历" if pubs else "校园与实践经历"
            lines.extend([
                f"\\section*{{{p_title}}}",
            ])
            for proj in projects:
                lines.append(r"\begin{itemize}[leftmargin=*,itemsep=2pt]")
                p_name = escape_latex(proj.get("name", "项目"))
                p_role = escape_latex(proj.get("role", ""))
                p_time = escape_latex(proj.get("time", ""))
                time_disp = f" ({p_time})" if p_time else ""
                role_disp = f" \\hfill \\textbf{{{p_role}}}" if p_role else ""
                lines.append(f"  \\item \\textbf{{{p_name}}}{role_disp}{time_disp}")
                bullets = proj.get("bullets", [])
                if bullets:
                    lines.append(r"  \begin{itemize}[leftmargin=*,itemsep=1pt]")
                    for b in bullets:
                        lines.append(f"    \\item {format_latex_bullet(b)}")
                    lines.append(r"  \end{itemize}")
                lines.append(r"\end{itemize}")

        # 4. Publications (if any)
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
        competencies = vm.competencies
        if competencies:
            if isinstance(competencies, list):
                competencies = {"专业技能": competencies}
            s_title = "核心技术栈" if pubs else "专业技能"
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
        profile: Union[Any, Dict[str, Any]],
        reserve_photo: bool = False,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Generates modern Typst source (.typ).
        Accepts ResumeViewModel, ProfileContext, or candidate profile dictionary.
        """
        vm = self._resolve_view_model(profile, reserve_photo=reserve_photo, photo_path=photo_path)

        name = escape_typst(vm.raw_name or "候选人")
        title = escape_typst(vm.raw_title or "")
        email = escape_typst(vm.raw_email or "")
        phone = escape_typst(vm.raw_phone or "")
        school = escape_typst(vm.raw_school or "")
        degree = escape_typst(vm.raw_degree or "")
        location = escape_typst(vm.raw_location or "")
        edu_time = escape_typst(vm.raw_edu_time or "")
        eff_photo_path = photo_path or vm.photo_path
        photo_needed = reserve_photo or vm.reserve_photo or (eff_photo_path is not None)

        lines = [
            '#set page(paper: "a4", margin: (x: 1.5cm, y: 1.5cm))',
            '#set text(font: ("Source Han Sans CN", "Helvetica"), size: 10pt)',
            "",
        ]

        email_typst = email
        contact_parts = []
        if phone:
            contact_parts.append(f"电话：{phone}")
        if email:
            contact_parts.append(f"邮箱：{email_typst}")
        if location:
            contact_parts.append(location)
        contact_line = " | ".join(contact_parts)

        if photo_needed:
            if eff_photo_path:
                p_str = Path(eff_photo_path).name if ":" in str(eff_photo_path) else Path(eff_photo_path).as_posix()
                rect_body = (
                    "    #box(width: 2.1cm, height: 2.8cm, clip: false)[\n"
                    f'      #image("{p_str}", width: 100%, height: 100%, fit: "contain")\n'
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
            ])
            if title:
                lines.append(f"    #v(2pt)#text(weight: \"bold\", fill: rgb(\"#1e3a8a\"))[求职意向：{title}] \\")
            if contact_line:
                lines.append(f"    #v(2pt)#text(fill: rgb(\"#555555\"))[{contact_line}]")
            lines.extend([
                "  ],",
                "  [",
                rect_body,
                "  ]",
                ")",
                "#v(6pt)",
            ])
        else:
            title_part = f"_{title}_ | " if title else ""
            lines.extend([
                f"= {name}",
            ])
            second_line = f"{title_part}{contact_line}" if (title_part or contact_line) else ""
            if second_line:
                lines.append(second_line)
            lines.append("")

        def format_typst_bullet(text: str) -> str:
            clean = re.sub(r"<strong>(.*?)</strong>", r"**\1**", str(text), flags=re.IGNORECASE)
            parts = re.split(r"\*\*(.+?)\*\*", clean)
            res = []
            for idx, part in enumerate(parts):
                if idx % 2 == 1:
                    res.append(f"*{escape_typst(part)}*")
                else:
                    res.append(escape_typst(part))
            return "".join(res)

        # Postgraduate Exam
        if vm.postgraduate_exam:
            pg = vm.postgraduate_exam
            pg_school = escape_typst(pg.get("raw_target_school", pg.get("target_school", "")))
            pg_major = escape_typst(pg.get("raw_target_major", pg.get("target_major", "")))
            pg_dir = escape_typst(pg.get("raw_direction", pg.get("direction", "")))

            lines.append("== 报考信息")
            target_items = []
            if pg_school:
                target_items.append(f"[*报考院校：* {pg_school}]")
            if pg_major:
                target_items.append(f"[*报考专业：* {pg_major}]")
            if pg_dir:
                target_items.append(f"[*研究方向：* {pg_dir}]")

            if target_items:
                lines.extend([
                    "#grid(",
                    f"  columns: ({', '.join(['1fr'] * len(target_items))}),",
                    f"  {', '.join(target_items)}",
                    ")",
                ])

            subjects = pg.get("subjects", [])
            total_score = escape_typst(pg.get("raw_total_score", pg.get("total_score", "")))
            if subjects or total_score:
                num_cols = 1 + len(subjects) + (1 if total_score else 0)
                col_spec = f"({', '.join(['1fr'] * num_cols)})"
                lines.extend([
                    "#table(",
                    f"  columns: {col_spec},",
                    "  align: center + horizon,",
                    '  stroke: 0.5pt + rgb("#D1D5DB"),',
                    "  [*初试成绩*],",
                ])
                for s in subjects:
                    s_name = escape_typst(s.get("raw_name", s.get("name", "")))
                    lines.append(f"  [*{s_name}*],")
                if total_score:
                    lines.append("  [*总分*],")

                lines.append("  [得分],")
                for s in subjects:
                    s_score = escape_typst(s.get("raw_score", s.get("score", "")))
                    lines.append(f"  [{s_score}],")
                if total_score:
                    lines.append(f"  [*{total_score}*],")
                lines.append(")")
            lines.append("")

        # Education
        grid = vm.education_grid_rows
        max_cols = max((len(r) for r in grid), default=1)

        degree_raw = re.sub(r"\s*[｜|·]\s*", "  ", str(vm.raw_degree or "")).strip()
        degree_clean = escape_typst(degree_raw)
        degree_meta = f" #h(1.5em) {degree_clean}" if degree_clean else ""
        edu_meta = f" #h(1fr) {edu_time}" if edu_time else ""

        lines.extend([
            "== 教育背景",
            f"*{school}*{degree_meta}{edu_meta}",
        ])

        if grid:
            if max_cols >= 3:
                cols_str = "(38%, 28%, 1fr)"
            elif max_cols == 2:
                cols_str = "(48%, 1fr)"
            else:
                cols_str = "(1fr,)"

            cell_tokens = []
            for r in grid:
                for i in range(max_cols):
                    cell = r[i] if i < len(r) else ""
                    cell_clean = re.sub(r"\s*[｜|]\s*", " ", cell).strip()
                    cell_tokens.append(f"[{escape_typst(cell_clean)}]")

            lines.append(f"#grid(\n  columns: {cols_str},\n  row-gutter: 3pt,\n  " + ", ".join(cell_tokens) + ",\n)")
        lines.append("")

        # Experience
        experiences = vm.experiences
        if experiences:
            lines.append("== 实习经历")
            for exp in experiences:
                dept_str = str(exp.get("dept", ""))
                role_str = str(exp.get("role", ""))
                role_label_raw = f"{dept_str} · {role_str}" if dept_str else role_str
                role_label = escape_typst(role_label_raw)
                exp_org = escape_typst(exp.get('org', ''))
                exp_time = escape_typst(exp.get('time', ''))
                lines.append(f"=== {exp_org} ({role_label}) -- {exp_time}")
                for b in exp.get("bullets", []):
                    lines.append(f"- {format_typst_bullet(b)}")
            lines.append("")

        # Projects
        projects = vm.projects
        pubs = vm.publications
        if projects:
            p_title = "科研与架构项目经历" if pubs else "校园与实践经历"
            lines.append(f"== {p_title}")
            for proj in projects:
                p_name = escape_typst(proj.get("name", "项目"))
                p_role = escape_typst(proj.get("role", ""))
                p_time = escape_typst(proj.get("time", ""))
                time_disp = f" -- {p_time}" if p_time else ""
                role_disp = f" ({p_role})" if p_role else ""
                lines.append(f"=== {p_name}{role_disp}{time_disp}")
                for b in proj.get("bullets", []):
                    lines.append(f"- {format_typst_bullet(b)}")
            lines.append("")

        # Publications
        if pubs:
            lines.append("== 学术发表与代表作")
            for p in pubs:
                p_title_str = escape_typst(p.get('title', ''))
                p_venue_str = escape_typst(p.get('venue', ''))
                lines.append(f"- *{p_title_str}* -- _{p_venue_str}_")
            lines.append("")

        # Competencies
        comps = vm.competencies
        if comps:
            if isinstance(comps, list):
                comps = {"专业技能": comps}
            s_title = "核心技术栈" if pubs else "专业技能"
            lines.append(f"== {s_title}")
            for k, v in comps.items():
                k_esc = escape_typst(str(k))
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                val_esc = escape_typst(val)
                lines.append(f"- *{k_esc}*: {val_esc}")

        return "\n".join(lines)

    def generate_latex_html_preview(
        self,
        profile: Union[Any, Dict[str, Any]],
        reserve_photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Generates single-page A4 HTML styled cleanly like LaTeX, with photo placeholder.
        Allows instant browser preview and headless PDF rendering without local LaTeX tools.
        Accepts ResumeViewModel, ProfileContext, or candidate profile dictionary.
        """
        vm = self._resolve_view_model(profile, reserve_photo=reserve_photo, photo_path=photo_path)

        name = escape_html_text(vm.raw_name or "候选人")
        title = escape_html_text(vm.raw_title or "")
        email_raw = str(vm.raw_email or "")
        email = escape_html_text(email_raw)
        phone = escape_html_text(vm.raw_phone or "")
        school = escape_html_text(vm.raw_school or "")
        location = escape_html_text(vm.raw_location or "")
        edu_time = escape_html_text(vm.raw_edu_time or "")

        grid = vm.education_grid_rows
        max_cols = max((len(r) for r in grid), default=1)
        if max_cols >= 3:
            col_template = "38% 28% 1fr"
        elif max_cols == 2:
            col_template = "45% 1fr"
        else:
            col_template = "1fr"

        grid_cells_html = []
        for r in grid:
            for i in range(max_cols):
                cell_text = r[i] if i < len(r) else ""
                cell_clean = re.sub(r"\s*[｜|]\s*", " ", cell_text).strip()
                grid_cells_html.append(f'<div>{escape_html_text(cell_clean)}</div>')

        degree = vm.raw_degree or ""
        degree_clean = escape_html_text(re.sub(r"\s*[｜|·]\s*", "  ", str(degree)).strip())
        exp_list = vm.experiences
        proj_list = vm.projects
        pubs = vm.publications
        comps = vm.competencies
        eff_photo_path = photo_path or vm.photo_path
        photo_needed = reserve_photo or vm.reserve_photo or (eff_photo_path is not None)

        photo_html = ""
        if photo_needed:
            photo_data_uri = _image_to_base64_data_uri(eff_photo_path)
            safe_data_uri = sanitize_url(photo_data_uri, allow_data_image=True) if photo_data_uri else ""
            if safe_data_uri:
                src_attr = escape_html_attribute(safe_data_uri)
                photo_html = f"""
    <div style="width: 72px; height: 96px; border: none !important; outline: none !important; box-shadow: none !important; background: transparent; border-radius: 0; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden;" title="证件照">
      <img src="{src_attr}" alt="证件照" style="max-width:100%; max-height:100%; width:auto; height:auto; object-fit:contain; border:none !important; outline:none !important; box-shadow:none !important; display:block; image-rendering:-webkit-optimize-contrast;" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
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

        mailto_url = sanitize_url(f"mailto:{email_raw}")
        if mailto_url and email:
            email_link = f'<a href="{escape_html_attribute(mailto_url)}" style="color:inherit; text-decoration:none;">{email}</a>'
        else:
            email_link = f'<span>{email}</span>' if email else ''

        contact_parts = []
        if phone:
            contact_parts.append(f"电话：{phone}")
        if email_link:
            contact_parts.append(f"邮箱：{email_link}")
        if location:
            contact_parts.append(location)
        contact_html = " &nbsp;|&nbsp; ".join(contact_parts)

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
      {'<div style="font-size: 11pt; font-weight: bold; color: #1e3a8a; margin-bottom: 3pt;">求职意向：' + title + '</div>' if title else ''}
      <div class="contact">
        {contact_html}
      </div>
    </div>
    {photo_html}
  </div>
"""

        if vm.postgraduate_exam:
            pg = vm.postgraduate_exam
            pg_school = escape_html_text(pg.get("target_school", ""))
            pg_major = escape_html_text(pg.get("target_major", ""))
            pg_dir = escape_html_text(pg.get("direction", ""))
            target_items = []
            if pg_school:
                target_items.append(f"<span><b>报考院校：</b>{pg_school}</span>")
            if pg_major:
                target_items.append(f"<span><b>报考专业：</b>{pg_major}</span>")
            if pg_dir:
                target_items.append(f"<span><b>研究方向：</b>{pg_dir}</span>")

            target_bar = f"<div class='item-header' style='display:flex; justify-content:space-between; margin-bottom:3pt;'>{' '.join(target_items)}</div>\n" if target_items else ""

            subjects = pg.get("subjects", [])
            total_score = escape_html_text(pg.get("total_score", ""))
            table_html = ""
            if subjects or total_score:
                th_cells = ['<th style="background:#F5EFEB; font-weight:bold; border:1px solid #D8CFC4; padding:3pt 5pt; width:16%;">初试成绩</th>']
                td_cells = ['<td style="background:#FDFBF7; font-weight:bold; color:#555; border:1px solid #D8CFC4; padding:3pt 5pt;">得分</td>']
                for s in subjects:
                    th_cells.append(f'<th style="border:1px solid #D8CFC4; padding:3pt 5pt;">{s["name"]}</th>')
                    td_cells.append(f'<td style="border:1px solid #D8CFC4; padding:3pt 5pt;">{s["score"]}</td>')
                if total_score:
                    th_cells.append('<th style="background:#F8ECE8; color:#1e3a8a; font-weight:bold; border:1px solid #D8CFC4; padding:3pt 5pt;">总分</th>')
                    td_cells.append(f'<td style="font-weight:bold; color:#1e3a8a; background:#FCF6F4; border:1px solid #D8CFC4; padding:3pt 5pt;">{total_score}</td>')

                table_html = f"""<table style="width:100%; border-collapse:collapse; margin-top:3pt; margin-bottom:5pt; text-align:center; font-size:10pt; border:1px solid #1e3a8a;">
  <thead><tr style="background:#FDFBF7; border-bottom:1.5px solid #1e3a8a;">{''.join(th_cells)}</tr></thead>
  <tbody><tr>{''.join(td_cells)}</tr></tbody>
</table>
"""

            html += f"""  <h2>报考信息</h2>
  {target_bar}
  {table_html}
"""

        html += f"""
  <h2>教育背景</h2>
  <div class="item-header">
    <span>{school} &nbsp;&nbsp;&nbsp;&nbsp; {degree_clean}</span>
    <span>{edu_time}</span>
  </div>
  <div class="edu-grid" style="display:grid; grid-template-columns:{col_template}; row-gap:3pt; font-size:10pt; color:#333333; line-height:1.45; margin-top:3pt; margin-bottom:5pt;">
    {"".join(grid_cells_html)}
  </div>
"""

        if exp_list:
            html += "  <h2>实习经历</h2>\n"
            for exp in exp_list:
                dept_str = str(exp.get("dept", ""))
                role_str = str(exp.get("role", ""))
                role_label_raw = f"{dept_str} · {role_str}" if dept_str else role_str
                role_label = escape_html_text(role_label_raw)
                exp_org_esc = escape_html_text(exp.get('org', ''))
                exp_time_esc = escape_html_text(exp.get('time', ''))
                bullets = "".join([
                    f"<li>{re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escape_html_text(str(b)))}</li>"
                    for b in exp.get("bullets", [])
                ])
                html += f"""  <div class='item-header'><span>{exp_org_esc} · {role_label}</span><span>{exp_time_esc}</span></div>
  <ul>{bullets}</ul>
"""

        if proj_list:
            p_title = "科研与架构项目经历" if pubs else "校园与实践经历"
            html += f"  <h2>{p_title}</h2>\n"
            for p in proj_list:
                p_name_esc = escape_html_text(p.get('name', ''))
                p_role_esc = escape_html_text(p.get('role', ''))
                p_time_esc = escape_html_text(p.get('time', ''))
                role_disp = f" · {p_role_esc}" if p_role_esc else ""
                bullets = "".join([
                    f"<li>{re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escape_html_text(str(b)))}</li>"
                    for b in p.get("bullets", [])
                ])
                html += f"""  <div class='item-header'><span>{p_name_esc}{role_disp}</span><span>{p_time_esc}</span></div>
  <ul>{bullets}</ul>
"""

        if comps:
            if isinstance(comps, list):
                comps = {"专业技能": comps}
            s_title = "核心技术栈" if pubs else "专业技能"
            html += f"  <h2>{s_title}</h2>\n  <ul>"
            for k, v in comps.items():
                k_esc = escape_html_text(str(k))
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                val_esc = escape_html_text(val)
                html += f"<li><b>{k_esc}：</b>{val_esc}</li>"
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
            try:
                res = subprocess.run([typst_cli, "compile", str(typ_file), str(pdf_file)], capture_output=True)
                return res.returncode == 0
            except Exception:
                return False

        return False

    def compile_latex(self, tex_path: str | Path, pdf_path: str | Path) -> bool:
        """Compiles LaTeX file to PDF using xelatex if available."""
        tex_file = Path(tex_path).resolve()
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        xelatex_cli = shutil.which("xelatex")
        if not xelatex_cli:
            return False

        try:
            res = subprocess.run(
                [xelatex_cli, "-interaction=nonstopmode", f"-output-directory={tex_file.parent}", str(tex_file)],
                capture_output=True,
                timeout=60
            )
            compiled_pdf = tex_file.with_suffix(".pdf")
            if compiled_pdf.exists() and compiled_pdf != pdf_file:
                shutil.move(str(compiled_pdf), str(pdf_file))
            return res.returncode == 0
        except Exception:
            return False
