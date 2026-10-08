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
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union


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

    def __init__(self) -> None:
        self.last_compile_result: Any = None

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

    @staticmethod
    def _raw_field(item: Dict[str, Any], key: str) -> str:
        """Non-HTML renderers consume source fields, with legacy decode fallback."""
        from html import unescape
        if "raw_" + key in item:
            return str(item["raw_" + key] or "")
        return unescape(str(item.get(key, "") or ""))

    @staticmethod
    def _raw_bullets(item: Dict[str, Any]) -> list[str]:
        from html import unescape
        if "raw_bullets" in item:
            return [str(value) for value in item["raw_bullets"]]
        return [unescape(re.sub(r"</?strong>", "**", str(value)))
                for value in item.get("bullets", [])]

    @staticmethod
    def _latex_text(value: str) -> str:
        """Escape data, adding safe break opportunities only to long tokens."""
        chunks = re.split(r"(\S{40,})", str(value))
        return "".join(
            r"\allowbreak{}".join(escape_latex(chunk[i:i + 12])
                                  for i in range(0, len(chunk), 12))
            if index % 2 else escape_latex(chunk)
            for index, chunk in enumerate(chunks)
        )

    def generate_latex(
        self,
        profile: Union[Any, Dict[str, Any]],
        reserve_photo: bool = False,
        photo_path: Optional[Union[str, Path]] = None,
        lang: str = "zh",
        section_titles: Optional[Dict[str, str]] = None,
    ) -> str:
        """Generate a conventional A4 academic resume with literal source facts."""
        from html import unescape
        vm = self._resolve_view_model(profile, reserve_photo=reserve_photo, photo_path=photo_path)
        is_en = str(lang).lower().startswith("en")
        titles = section_titles or {}
        esc = self._latex_text
        raw = self._raw_field
        photo = photo_path or vm.photo_path
        photo_needed = reserve_photo or vm.reserve_photo or bool(photo)
        lines = [
            r"\documentclass[a4paper,11pt]{article}",
            r"\usepackage{xeCJK}",
            r"\usepackage[margin=18mm]{geometry}",
            r"\usepackage{tabularx,enumitem,titlesec,xcolor,graphicx,needspace}",
            r"\usepackage[hidelinks]{hyperref}",
            r"\IfFontExistsTF{TeX Gyre Termes}{\setmainfont{TeX Gyre Termes}}{\setmainfont{Latin Modern Roman}}",
            r"\IfFontExistsTF{Noto Serif CJK SC}{\setCJKmainfont{Noto Serif CJK SC}}{\IfFontExistsTF{Source Han Serif SC}{\setCJKmainfont{Source Han Serif SC}}{\IfFontExistsTF{SimSun}{\setCJKmainfont{SimSun}}{\setCJKmainfont{FandolSong-Regular}[BoldFont=FandolSong-Bold]}}}",
            r"\pagestyle{empty}",
            r"\setlength{\parindent}{0pt}",
            r"\setlength{\parskip}{1pt}",
            r"\clubpenalty=10000\widowpenalty=10000",
            r"\setlength{\emergencystretch}{3em}",
            r"\raggedright",
            r"\setlist[itemize]{leftmargin=1.2em,label=\textbullet,itemsep=1pt,topsep=2pt,parsep=0pt,partopsep=0pt}",
            r"\titlespacing*{\section}{0pt}{6pt}{3pt}",
            r"\titleformat{\section}{\fontsize{11.5}{14}\selectfont\bfseries}{}{0em}{}",
            r"\newcommand{\resumeentry}[3]{\Needspace{3\baselineskip}\begin{tabularx}{\linewidth}{@{}Xr@{}}\textbf{#1}&{\small #2}\end{tabularx}\par\nopagebreak[4]\if\relax\detokenize{#3}\relax\else{\color{black!75}#3}\par\nopagebreak[4]\fi}",
            r"\begin{document}",
            r"\fontsize{10.5}{13.5}\selectfont",
        ]
        name = esc(vm.raw_name or unescape(vm.name) or ("Candidate" if is_en else "候选人"))
        title = esc(vm.raw_title or unescape(vm.title))
        contacts = [vm.raw_phone or unescape(vm.phone), vm.raw_email or unescape(vm.email),
                    vm.raw_location or unescape(vm.location)]
        contact = r" \enspace | \enspace ".join(esc(value) for value in contacts if value)
        if photo_needed:
            lines += [r"\noindent\begin{minipage}[c]{\dimexpr\textwidth-72pt\relax}"]
        else:
            lines += [r"{\centering"]
        lines.append(r"{\fontsize{22}{27}\selectfont\bfseries " + name + r"}\par")
        if title:
            lines.append(title + r"\par")
        if contact:
            lines.append(r"{\small " + contact + r"}\par")
        if photo_needed:
            lines += [r"\end{minipage}\hfill\begin{minipage}[c]{60pt}\raggedleft"]
            if photo and Path(photo).is_file():
                # \detokenize keeps spaces and underscores in ordinary filenames literal.
                path = Path(photo).resolve().as_posix()
                if any(char in path for char in "{}%\n\r"):
                    raise ValueError("LaTeX photo filenames cannot contain braces, percent signs or line breaks")
                lines.append(r"\includegraphics[width=54pt,height=72pt,keepaspectratio]{\detokenize{" + path + "}}")
            else:
                label = r"Photo\\(3:4)" if is_en else r"预留证件照\\一寸 / 二寸"
                lines.append(r"\fbox{\parbox[c][68pt][c]{50pt}{\centering\small " + label + "}}")
            lines += [r"\end{minipage}\par"]
        else:
            lines += [r"\par}"]

        def section(key: str, en: str, zh: str) -> None:
            lines.append(r"\section*{" + esc(titles.get(key, en if is_en else zh)) + "}")

        def entry(label: str, time: str, role: str = "") -> None:
            # Bold markup remains explicit for simple source inspection and tools.
            lines.append(r"\resumeentry{" + esc(label) + "}{" + esc(time) + "}{" + esc(role) + "}")

        def bullet(text: str) -> str:
            return "".join(r"\textbf{" + esc(part) + "}" if i % 2 else esc(part)
                           for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)))

        if vm.edu_school or vm.raw_school or vm.education_grid_rows:
            section("education", "EDUCATION", "教育背景")
            school = vm.raw_school or unescape(vm.edu_school)
            degree = vm.raw_degree or unescape(vm.edu_degree)
            time = vm.raw_edu_time or unescape(vm.edu_time)
            # A simple explicit heading preserves the public source-format contract.
            lines += [r"\Needspace{3\baselineskip}",
                      r"\begin{tabularx}{\linewidth}{@{}Xr@{}}\textbf{" + esc(school) + "}&" + esc(time) + r"\end{tabularx}\par\nopagebreak[4]"]
            if degree:
                lines.append(esc(degree) + r"\par")
            if vm.education_grid_rows:
                lines.append(r"\begin{tabular}{@{}p{\linewidth}@{}}")
                for row in vm.education_grid_rows:
                    lines.append(r" \enspace \enspace ".join(esc(unescape(str(cell))) for cell in row if cell) + r" \\")
                lines.append(r"\end{tabular}\par")
            metadata = (vm.raw_profile or {}).get("candidate", {})
            courses = metadata.get("courses") or metadata.get("core_courses")
            if courses:
                lines.append(esc(("Key Coursework: " if is_en else "核心课程：") + str(courses)) + r"\par")

        if vm.postgraduate_exam:
            section("postgraduate_exam", "POSTGRADUATE EXAM", "报考信息")
            pg = vm.postgraduate_exam
            target = [raw(pg, key) for key in ("target_school", "target_major", "direction")]
            lines.append(r" \enspace | \enspace ".join(esc(value) for value in target if value) + r"\par")
            scores = [raw(subject, "name") + ": " + raw(subject, "score") for subject in pg.get("subjects", [])]
            if raw(pg, "total_score"):
                scores.append(("Total: " if is_en else "总分：") + raw(pg, "total_score"))
            lines.append(r" \enspace | \enspace ".join(esc(value) for value in scores) + r"\par")

        for key, records, en, zh in (
            ("experience", vm.experiences, "WORK EXPERIENCE", "实习经历"),
            ("projects", vm.projects, "PROJECTS", "科研与架构项目经历" if vm.publications else "校园与实践经历"),
        ):
            if not records:
                continue
            section(key, en, zh)
            for item in records:
                label = raw(item, "org" if key == "experience" else "name")
                role = raw(item, "role_label") or raw(item, "role")
                entry(label, raw(item, "time"), role)
                bullets = self._raw_bullets(item)
                if bullets:
                    lines.append(r"\begin{itemize}")
                    lines.extend(r"\item " + bullet(text) for text in bullets)
                    lines.append(r"\end{itemize}")

        if vm.publications:
            section("publications", "PUBLICATIONS", "学术发表与代表作")
            lines.append(r"\begin{itemize}")
            for publication in vm.publications:
                parts = [raw(publication, key) for key in ("title", "authors", "venue", "year")]
                lines.append(r"\item " + " · ".join(esc(part) for part in parts if part))
            lines.append(r"\end{itemize}")
        if vm.competencies:
            section("skills", "SKILLS", "专业技能")
            competencies = vm.competencies if isinstance(vm.competencies, dict) else {"专业技能": vm.competencies}
            for category, values in competencies.items():
                value = ", ".join(str(v) for v in values) if isinstance(values, list) else str(values)
                lines.append(r"\textbf{" + esc(category) + "}: " + esc(value) + r"\par")
        lines.append(r"\end{document}")
        return "\n".join(lines)

    @staticmethod
    def _typst_text(value: str) -> str:
        """Escape markup/labels/comments, with invisible breaks in long tokens."""
        def literal(text: str) -> str:
            escaped = escape_typst(text).replace("<", r"\<").replace(">", r"\>").replace("/", r"\/").replace("~", r"\~")
            escaped = re.sub(r"-{2,}", lambda match: r"\-" * len(match[0]), escaped)
            return re.sub(r"(?m)^(\s*)(=+|[-+])(?=\s)",
                          lambda match: match[1] + "".join("\\" + char for char in match[2]), escaped)
        chunks = re.split(r"(\S{40,})", str(value))
        return "".join(
            r"\u{200b}".join(literal(chunk[i:i + 12]) for i in range(0, len(chunk), 12))
            if index % 2 else literal(chunk)
            for index, chunk in enumerate(chunks)
        )

    def generate_typst(
        self,
        profile: Union[Any, Dict[str, Any]],
        reserve_photo: bool = False,
        photo_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Generate a restrained, single-column native Typst resume."""
        import json
        from html import unescape
        vm = self._resolve_view_model(profile, reserve_photo=reserve_photo, photo_path=photo_path)
        raw = self._raw_field
        esc = self._typst_text
        photo = photo_path or vm.photo_path
        photo_needed = reserve_photo or vm.reserve_photo or bool(photo)
        lines = [
            '#set page(paper: "a4", margin: (x: 18mm, y: 18mm))',
            '#set text(font: ("Liberation Sans", "Noto Sans CJK SC"), size: 10.5pt, fill: rgb("#252525"), lang: "zh", hyphenate: false)',
            '#set par(justify: false, leading: 3pt, spacing: 2pt)',
            '#set smartquote(enabled: false)',
            '#set list(indent: 0pt, body-indent: 12pt, spacing: 1.5pt)',
            '#show heading.where(level: 2): set text(size: 11.5pt, weight: "bold")',
            '#show heading.where(level: 2): set block(above: 7pt, below: 3pt)',
            '',
        ]
        name = esc(vm.raw_name or unescape(vm.name) or "候选人")
        title = esc(vm.raw_title or unescape(vm.title))
        contacts = " | ".join(esc(value) for value in (
            vm.raw_phone or unescape(vm.phone), vm.raw_email or unescape(vm.email),
            vm.raw_location or unescape(vm.location)) if value)
        identity = [f'#block(above: 0pt, below: 3pt)[#text(size: 22pt, weight: "bold")[{name}]]']
        if title:
            identity.append(f'#block(above: 0pt, below: 3pt)[{title}]')
        if contacts:
            identity.append(f'#block(above: 0pt, below: 0pt)[#text(size: 9.5pt)[{contacts}]]')
        if photo_needed:
            if photo:
                from pathlib import PureWindowsPath
                path = PureWindowsPath(str(photo)).name if ":" in str(photo) else Path(photo).as_posix()
                # File paths are code strings, not content markup. JSON quoting
                # safely preserves quotes/backslashes and cannot emit Typst code.
                picture = f'#image({json.dumps(path, ensure_ascii=False)}, width: 54pt, height: 72pt, fit: "contain")'
            else:
                picture = '#rect(width: 54pt, height: 72pt, stroke: 0.5pt + rgb("#888888"))[#align(center + horizon)[#text(size: 8pt)[预留证件照 \\ 一寸 / 二寸]]]'
            lines += ['#grid(', '  columns: (1fr, auto), column-gutter: 18pt, align: (left + horizon, right + horizon),',
                      '  [\n' + '\n'.join(identity) + '\n],', '  [' + picture + ']', ')']
        else:
            lines += ['#align(center)[', '\n'.join(identity), ']']
        lines.append('')

        def entry(label: str, date: str, role: str = "") -> None:
            lines.append('#block(width: 100%, sticky: true, above: 3pt, below: 1pt)[')
            lines.append('#grid(columns: (1fr, auto), column-gutter: 10pt, align: (left, right), '
                         + '[*' + esc(label) + '*], [#text(size: 9.5pt)[' + esc(date) + ']])')
            if role:
                lines.append('#text(fill: rgb("#555555"))[' + esc(role) + ']')
            lines.append(']')

        def bullet(value: str) -> str:
            return "".join("*" + esc(part) + "*" if index % 2 else esc(part)
                           for index, part in enumerate(re.split(r"\*\*(.+?)\*\*", value)))

        if vm.edu_school or vm.raw_school or vm.education_grid_rows:
            lines.append('== 教育背景')
            entry(vm.raw_school or unescape(vm.edu_school), vm.raw_edu_time or unescape(vm.edu_time),
                  vm.raw_degree or unescape(vm.edu_degree))
            for row in vm.education_grid_rows:
                cells = ['[' + esc(unescape(str(cell))) + ']' for cell in row if cell]
                if cells:
                    lines.append('#grid(columns: (' + ', '.join(['1fr'] * len(cells)) + ',), column-gutter: 12pt, row-gutter: 2pt, '
                                 + ', '.join(cells) + ')')
            lines.append('')
        if vm.postgraduate_exam:
            lines.append('== 报考信息')
            pg = vm.postgraduate_exam
            target = [raw(pg, key) for key in ("target_school", "target_major", "direction")]
            lines.append(' | '.join(esc(value) for value in target if value))
            lines.append('')
            scores = [raw(subject, "name") + ': ' + raw(subject, "score") for subject in pg.get("subjects", [])]
            if raw(pg, "total_score"):
                scores.append('总分：' + raw(pg, "total_score"))
            lines += [' | '.join(esc(value) for value in scores), '']

        for key, records, heading in (
            ("experience", vm.experiences, "工作经历"),
            ("projects", vm.projects, "项目经历"),
        ):
            if records:
                lines.append('== ' + heading)
                for item in records:
                    entry(raw(item, "org" if key == "experience" else "name"), raw(item, "time"),
                          raw(item, "role_label") or raw(item, "role"))
                    lines.extend('- ' + bullet(value).replace('\n', '\n  ') for value in self._raw_bullets(item))
                    lines.append('')
        if vm.publications:
            lines.append('== 学术发表与代表作')
            for publication in vm.publications:
                parts = []
                title = raw(publication, "title")
                authors = raw(publication, "authors")
                venue = raw(publication, "venue")
                year = raw(publication, "year")
                if title:
                    parts.append('*' + esc(title) + '*')
                if authors:
                    parts.append(esc(authors))
                if venue:
                    parts.append('_' + esc(venue) + '_')
                if year:
                    parts.append(esc(year))
                lines.append('- ' + ' · '.join(parts))
            lines.append('')
        if vm.competencies:
            lines.append('== 专业技能')
            competencies = vm.competencies if isinstance(vm.competencies, dict) else {"专业技能": vm.competencies}
            for category, values in competencies.items():
                value = ', '.join(str(item) for item in values) if isinstance(values, list) else str(values)
                lines += ['*' + esc(category) + '*: ' + esc(value), '']
        return '\n'.join(lines)

    def generate_latex_html_preview(
        self,
        profile: Union[Any, Dict[str, Any]],
        reserve_photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        photo_size: Optional[int] = None,
        photo_width: Optional[int] = None,
        photo_height: Optional[int] = None,
        lang: str = "zh",
        section_titles: Optional[Dict[str, str]] = None,
        layout_config: Optional[Any] = None,
    ) -> str:
        """Semantic HTML fallback with the same source facts and academic hierarchy."""
        from html import unescape
        vm = self._resolve_view_model(profile, reserve_photo=reserve_photo, photo_path=photo_path)
        en = str(lang).lower().startswith("en")
        titles = section_titles or {}
        esc = escape_html_text
        raw = self._raw_field
        name = esc(vm.raw_name or unescape(vm.name) or ("Candidate" if en else "候选人"))
        title = esc(vm.raw_title or unescape(vm.title))
        photo = photo_path or vm.photo_path
        need_photo = reserve_photo or vm.reserve_photo or bool(photo)
        image = ""
        if need_photo:
            data = _image_to_base64_data_uri(photo) or vm.photo_data_uri
            data = sanitize_url(data, allow_data_image=True) if data else ""
            width = max(24, min(180, int(photo_width or photo_size or 72)))
            height = max(24, min(240, int(photo_height or photo_size or 96)))
            if data:
                image = f'<img class="photo" src="{escape_html_attribute(data)}" alt="Photo" style="width:{width}px;height:{height}px">'
            else:
                label = "Photo<br>(3:4)" if en else "预留证件照<br>一寸 / 二寸"
                image = f'<div class="photo-placeholder">{label}</div>'
        contact = " | ".join(esc(value) for value in (
            vm.raw_phone or unescape(vm.phone), vm.raw_email or unescape(vm.email),
            vm.raw_location or unescape(vm.location)) if value)
        parts = [f'''<!DOCTYPE html>
<html lang="{'en' if en else 'zh-CN'}"><head><meta charset="UTF-8">
<title>Resume - {name}</title>
<style>
@page {{ size: A4; margin: 18mm; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: "Times New Roman", "Noto Serif CJK SC", "Songti SC", "SimSun", serif;
  font-size: 10.5pt; line-height: 1.30; color: #202020; background: white; }}
.page {{ width: 100%; }}
.header {{ display: flex; align-items: center; gap: 18pt; margin-bottom: 8pt; }}
.identity {{ flex: 1; min-width: 0; overflow-wrap: anywhere; }}
.header.no-photo {{ display: block; text-align: center; }}
h1 {{ font-size: 22pt; line-height: 1.2; margin: 0 0 3pt; }}
.title {{ margin: 0 0 3pt; }}
.contact {{ font-size: 9.5pt; }}
.photo, .photo-placeholder {{ flex: none; object-fit: contain; }}
.photo-placeholder {{ width: 72px; height: 96px; border: 1px solid #888;
  display: flex; align-items: center; justify-content: center; text-align: center; font-size: 8pt; color: #555; }}
h2 {{ font-size: 11.5pt; margin: 6pt 0 3pt; line-height: 1.25; break-after: avoid; }}
.item-header {{ display: grid; grid-template-columns: minmax(0, 1fr) auto;
  gap: 10pt; margin-top: 4pt; break-after: avoid; }}
.item-header strong {{ min-width: 0; overflow-wrap: anywhere; }}
.date {{ font-size: 9.5pt; text-align: right; max-width: 48mm; overflow-wrap: anywhere; }}
.role {{ color: #444; margin-top: 1pt; break-after: avoid; }}
p {{ margin: 1pt 0; overflow-wrap: anywhere; }}
ul {{ margin: 2pt 0 5pt; padding-left: 1.2em; }}
li {{ margin: 0 0 1.5pt; overflow-wrap: anywhere; orphans: 2; widows: 2; }}
strong {{ font-weight: 700; }}
@media screen {{ body {{ max-width: 210mm; padding: 18mm; margin: auto; }} }}
</style></head><body><main class="page">
<header class="header{' no-photo' if not image else ''}"><div class="identity"><h1>{name}</h1>
{('<div class="title">' + title + '</div>') if title else ''}<div class="contact">{contact}</div></div>{image}</header>''']

        def section(key: str, english: str, chinese: str) -> None:
            parts.append("<h2>" + esc(titles.get(key, english if en else chinese)) + "</h2>")

        def entry(label: str, date: str, role: str = "") -> None:
            parts.append('<div class="item-header"><strong>' + esc(label) + '</strong><span class="date">' + esc(date) + '</span></div>')
            if role:
                parts.append('<p class="role">' + esc(role) + '</p>')

        def bullet(value: str) -> str:
            return "".join("<strong>" + esc(part) + "</strong>" if index % 2 else esc(part)
                           for index, part in enumerate(re.split(r"\*\*(.+?)\*\*", value)))

        if vm.edu_school or vm.raw_school or vm.education_grid_rows:
            section("education", "EDUCATION", "教育背景")
            entry(vm.raw_school or unescape(vm.edu_school), vm.raw_edu_time or unescape(vm.edu_time),
                  vm.raw_degree or unescape(vm.edu_degree))
            for row in vm.education_grid_rows:
                parts.append("<p>" + " | ".join(esc(unescape(str(cell))) for cell in row if cell) + "</p>")
            metadata = (vm.raw_profile or {}).get("candidate", {})
            courses = metadata.get("courses") or metadata.get("core_courses")
            if courses:
                parts.append("<p>" + esc(("Key Coursework: " if en else "核心课程：") + str(courses)) + "</p>")
        if vm.postgraduate_exam:
            section("postgraduate_exam", "POSTGRADUATE EXAM", "报考信息")
            pg = vm.postgraduate_exam
            target = [raw(pg, key) for key in ("target_school", "target_major", "direction")]
            parts.append("<p>" + " | ".join(esc(value) for value in target if value) + "</p>")
            scores = [raw(subject, "name") + ": " + raw(subject, "score") for subject in pg.get("subjects", [])]
            if raw(pg, "total_score"):
                scores.append(("Total: " if en else "总分：") + raw(pg, "total_score"))
            parts.append("<p>" + " | ".join(esc(value) for value in scores) + "</p>")
        for key, records, english, chinese in (
            ("experience", vm.experiences, "WORK EXPERIENCE", "实习经历"),
            ("projects", vm.projects, "PROJECTS", "科研与架构项目经历" if vm.publications else "校园与实践经历"),
        ):
            if records:
                section(key, english, chinese)
                for item in records:
                    entry(raw(item, "org" if key == "experience" else "name"), raw(item, "time"),
                          raw(item, "role_label") or raw(item, "role"))
                    parts.append("<ul>" + "".join("<li>" + bullet(text) + "</li>" for text in self._raw_bullets(item)) + "</ul>")
        if vm.publications:
            section("publications", "PUBLICATIONS", "学术发表与代表作")
            parts.append("<ul>")
            for publication in vm.publications:
                fields = [raw(publication, key) for key in ("title", "authors", "venue", "year")]
                parts.append("<li>" + " · ".join(esc(value) for value in fields if value) + "</li>")
            parts.append("</ul>")
        if vm.competencies:
            section("skills", "SKILLS", "专业技能")
            competencies = vm.competencies if isinstance(vm.competencies, dict) else {"专业技能": vm.competencies}
            for category, values in competencies.items():
                value = ", ".join(str(v) for v in values) if isinstance(values, list) else str(values)
                parts.append("<p><strong>" + esc(category) + ": </strong>" + esc(value) + "</p>")
        parts.append("</main></body></html>")
        html = "\n".join(parts)
        from core.layout_solver import LayoutConfig, inject_micro_typography
        config = layout_config or LayoutConfig(
            target_body_font_pt=10.5, min_line_height=1.30, target_line_height=1.30,
            min_section_margin_pt=6, target_section_margin_pt=6,
            min_item_gap_pt=1.5, target_item_gap_pt=1.5,
            target_page_padding_y_mm=18, max_page_padding_y_mm=18,
            target_letter_spacing_em=0, page_mode="auto",
        )
        html = inject_micro_typography(html, config=config)
        # Keep the academic page geometry and free-flowing long lists after the
        # shared micro-typography rules (which otherwise zero horizontal margins).
        vertical_margin = config.target_page_padding_y_mm
        overrides = f"""<style id="academic-print-flow">
@page {{ margin: {vertical_margin}mm 18mm; }}
@media print {{ .page {{ min-height: 0 !important; }}
ul {{ break-inside: auto !important; page-break-inside: auto !important; }} }}
</style>"""
        return html.replace("</head>", overrides + "</head>")

    def compile_typst(self, typ_path: str | Path, pdf_path: str | Path) -> bool:
        """Compiles Typst file to PDF using Python package or CLI."""
        typ_file = Path(typ_path).resolve()
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        from core.atomic_writer import safe_save_file

        with tempfile.TemporaryDirectory(prefix="typst_out_") as tmp_dir:
            temp_pdf = Path(tmp_dir) / "output.pdf"
            compiled = False

            try:
                import typst
                typst.compile(typ_file, output=str(temp_pdf))
                compiled = temp_pdf.exists() and temp_pdf.stat().st_size > 0
            except Exception:
                pass

            if not compiled:
                typst_cli = shutil.which("typst")
                if typst_cli:
                    try:
                        res = subprocess.run([typst_cli, "compile", str(typ_file), str(temp_pdf)], capture_output=True)
                        compiled = res.returncode == 0 and temp_pdf.exists() and temp_pdf.stat().st_size > 0
                    except Exception:
                        pass

            if compiled:
                save_res = safe_save_file(dest_path=pdf_file, content=temp_pdf, allow_shadow=True)
                self.last_compile_result = save_res
                return save_res.success

            self.last_compile_result = None
            return False

    def compile_latex(self, tex_path: str | Path, pdf_path: str | Path) -> bool:
        """Compiles LaTeX file to PDF using xelatex if available."""
        tex_file = Path(tex_path).resolve()
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)

        xelatex_cli = shutil.which("xelatex")
        if not xelatex_cli:
            self.last_compile_result = None
            return False

        from core.atomic_writer import safe_save_file

        with tempfile.TemporaryDirectory(prefix="latex_out_") as tmp_dir:
            try:
                res = subprocess.run(
                    [xelatex_cli, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode", f"-output-directory={tmp_dir}", str(tex_file)],
                    cwd=str(tex_file.parent),
                    capture_output=True,
                    timeout=60,
                )
                compiled_pdf = Path(tmp_dir) / f"{tex_file.stem}.pdf"
                if res.returncode == 0 and compiled_pdf.exists() and compiled_pdf.stat().st_size > 0:
                    save_res = safe_save_file(dest_path=pdf_file, content=compiled_pdf, allow_shadow=True)
                    self.last_compile_result = save_res
                    return save_res.success
                self.last_compile_result = None
                return False
            except Exception:
                self.last_compile_result = None
                return False

