#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OfferGet Demo Resumes Generator - Fan Zengyu (fzy) Operations Edition
=====================================================================
Builds all 6 styles of resumes from candidate_profile.json (SSOT):
1. Silicon Clean (HTML -> Single-Page PDF, with photo slot)
2. Classic Tech (HTML -> Single-Page PDF, with photo slot)
3. Modern Navy (HTML -> Single-Page PDF, with photo slot)
4. ATS Plain (Markdown + Clean HTML -> PDF)
5. Academic Typst (Typst .typ -> Native PDF)
6. Academic LaTeX (LaTeX .tex + Academic Style PDF)
"""

import os
import re
import sys
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ApexResume.core.render import BrowserRenderer
from ApexResume.core.autofit import AutoFitEngine
import typst


def load_profile() -> dict:
    profile_path = Path(__file__).parent / "candidate_profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_header_with_photo_html(cand: dict) -> str:
    return f"""
    <header style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--color-primary, #2563EB); padding-bottom: 7px; margin-bottom: 5px;">
      <div style="flex: 1; padding-right: 16px;">
        <div style="display: flex; align-items: baseline; gap: 10px; margin-bottom: 4px;">
          <h1 style="font-size: 20px; font-weight: 700; color: var(--color-primary-dark, #0F172A); margin: 0; line-height: 1.1;">{cand['name']}</h1>
          <span style="font-size: 11px; font-weight: 600; color: var(--color-accent, #0284C7); background: #E0F2FE; padding: 2px 7px; border-radius: 3px;">求职意向：{cand.get('title', '运营岗')}</span>
        </div>
        <div style="font-size: 10.8px; color: var(--color-muted, #64748B); display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 3px;">
          <span>电话：{cand['phone']}</span>
          <span style="color: #CBD5E1;">|</span>
          <span>邮箱：<a href="mailto:{cand['email']}" style="color: inherit; text-decoration: none;">{cand['email']}</a></span>
          <span style="color: #CBD5E1;">|</span>
          <span>{cand['location']}</span>
        </div>
      </div>
      <div style="width: 76px; height: 100px; border: 1.5px dashed #94A3B8; border-radius: 4px; background: #F8FAFC; display: flex; flex-direction: column; align-items: center; justify-content: center; flex-shrink: 0; text-align: center; overflow: hidden;" title="预留证件照位置">
        <img src="avatar.jpg" alt="证件照" style="width: 100%; height: 100%; object-fit: cover; display: none;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" onload="this.style.display='block'; this.nextElementSibling.style.display='none';">
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%;">
          <svg style="width: 20px; height: 20px; fill: #94A3B8; margin-bottom: 2px;" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
          <span style="font-size: 9px; color: #64748B; line-height: 1.2;">预留证件照<br>一寸/二寸</span>
        </div>
      </div>
    </header>
    """


def build_sections_html(profile: dict) -> str:
    cand = profile["candidate"]
    exp_list = profile.get("experience", [])
    proj_list = profile.get("projects", [])
    comps = profile.get("competencies", {})
    edu_badges = cand.get("education_badges", [])

    sections = []

    # 1. Education
    badge_spans = "".join([
        f'<span style="font-size: 10.2px; color: #334155; background: #F1F5F9; border: 1px solid #E2E8F0; padding: 1px 6px; border-radius: 3px; font-weight: 500;">{b}</span>'
        for b in edu_badges
    ])

    edu_html = f"""
    <section id="education">
      <div class="section-header">
        <h2>教育背景</h2>
        <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
      </div>
      <div class="org-bar" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:3px; margin-bottom:3px;">
        <div class="org-left" style="display:flex; align-items:baseline; gap:8px;">
          <span class="org-title" style="font-weight:700; font-size:11.8px; color:var(--color-primary-dark, #0F172A);">{cand['school']}</span>
          <span class="org-role" style="font-weight:600; font-size:11.2px; color:var(--color-accent, #0284C7);">{cand['degree']}</span>
        </div>
        <div class="org-right" style="font-size:10.5px; color:var(--color-muted, #64748B);">{cand.get('edu_time', '2023.09 — 2027.06')}</div>
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
                <span class="org-title" style="font-weight:700; font-size:11.8px; color:var(--color-primary-dark, #0F172A);">{exp['org']}</span>
                <span class="org-role" style="font-weight:600; font-size:11.2px; color:var(--color-accent, #0284C7);">{exp['role']}</span>
              </div>
              <div class="org-right" style="font-size:10.5px; color:var(--color-muted, #64748B);">{exp['time']}</div>
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
                <span style="font-weight:700; font-size:11.8px; color:var(--color-primary-dark, #0F172A);">{proj['name']}</span>
                <span style="font-weight:600; font-size:11.2px; color:var(--color-accent, #0284C7);">{proj['role']}</span>
              </div>
              <div style="font-size:10.5px; color:var(--color-muted, #64748B);">{proj['time']}</div>
            </div>
            <ul>{bullets_li}</ul>
            """)
        proj_parts.append("</section>")
        sections.append("\n".join(proj_parts))

    # 4. Competencies (专业技能)
    if comps:
        skill_rows = []
        for k, v in comps.items():
            skill_rows.append(f"""
            <div style="display:flex; margin-bottom:2px; line-height:1.45;">
              <span style="width:76px; font-weight:700; color:var(--color-primary, #1E3A8A); flex-shrink:0;">{k}：</span>
              <span style="flex:1; color:#334155;">{v}</span>
            </div>
            """)
        skills_html = f"""
        <section id="skills">
          <div class="section-header">
            <h2>专业技能</h2>
            <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
          </div>
          <div style="background:var(--color-bg-bar, #F8FAFC); border:1px solid var(--color-border, #E2E8F0); border-radius:4px; padding:5px 8px; margin-top:3px;">
            {''.join(skill_rows)}
          </div>
        </section>
        """
        sections.append(skills_html)

    return "\n".join(sections)


def render_html_theme(theme_name: str, profile: dict, output_dir: Path, autofit: AutoFitEngine):
    theme_file = PROJECT_ROOT / "ApexResume" / "themes" / f"{theme_name}.html"
    raw_template = theme_file.read_text(encoding="utf-8")

    cand = profile["candidate"]
    header_html = build_header_with_photo_html(cand)
    sections_html = build_sections_html(profile)

    # Replace <header>...</header> with our photo-enabled header
    header_regex = re.compile(r"<header>.*?</header>", re.DOTALL)
    if header_regex.search(raw_template):
        populated_html = header_regex.sub(header_html, raw_template)
    else:
        populated_html = raw_template

    populated_html = populated_html.replace("{{SECTIONS_CONTENT}}", sections_html)

    raw_html_path = output_dir / f"resume_{theme_name.replace('-', '_')}_raw.html"
    raw_html_path.write_text(populated_html, encoding="utf-8")

    fit_html_path = output_dir / f"resume_{theme_name.replace('-', '_')}.html"
    pdf_path = output_dir / f"resume_{theme_name.replace('-', '_')}.pdf"

    print(f"[+] Processing {theme_name} via AutoFit...")
    success, msg, details = autofit.fit_to_single_page(
        input_html_path=raw_html_path,
        output_html_path=fit_html_path,
        output_pdf_path=pdf_path
    )
    print(f"    Result: {msg} (Details: {details})")
    return pdf_path


def build_ats_plain(profile: dict, output_dir: Path, renderer: BrowserRenderer):
    cand = profile["candidate"]
    comps = profile.get("competencies", {})
    exp_list = profile.get("experience", [])
    proj_list = profile.get("projects", [])
    edu_badges = cand.get("education_badges", [])

    md_lines = [
        f"# {cand['name']}",
        f"求职意向：{cand.get('title', '运营岗')}",
        f"电话：{cand['phone']} | 邮箱：{cand['email']} | {cand['location']} | 照片：预留证件照位置",
        "",
        "---",
        "",
        "## 教育背景",
        f"### {cand['school']} ｜ {cand['degree']} ｜ {cand.get('edu_time', '2023.09—2027.06')}",
    ]
    for b in edu_badges:
        md_lines.append(f"- {b}")

    md_lines.extend(["", "---", "", "## 实习经历"])
    for exp in exp_list:
        md_lines.extend([
            f"### {exp['org']} ｜ {exp['role']}",
            f"**任职时间**：{exp['time']}",
            "",
        ])
        for b in exp.get("bullets", []):
            md_lines.append(f"- {b}")
        md_lines.append("")

    md_lines.extend(["---", "", "## 校园与实践经历"])
    for proj in proj_list:
        md_lines.extend([
            f"### {proj['name']} ｜ {proj['role']}",
            f"**时间**：{proj['time']}",
            "",
        ])
        for b in proj.get("bullets", []):
            md_lines.append(f"- {b}")
        md_lines.append("")

    if comps:
        md_lines.extend(["---", "", "## 专业技能"])
        for k, v in comps.items():
            md_lines.append(f"- **{k}：**{v}")
        md_lines.append("")

    md_content = "\n".join(md_lines)
    md_path = output_dir / "resume_ats_plain.md"
    md_path.write_text(md_content, encoding="utf-8")

    # Render clean ATS single-column HTML with reserved photo slot
    ats_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{cand['name']} - 运营岗 ATS 简历</title>
  <style>
    @page {{ size: A4 portrait; margin: 10mm 14mm; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
      font-size: 11px;
      line-height: 1.5;
      color: #111827;
      background: #FFFFFF;
      margin: 0;
      padding: 0;
    }}
    h1 {{ font-size: 19px; margin: 0 0 3px 0; color: #000000; }}
    .contact {{ font-size: 10.5px; color: #4B5563; margin-bottom: 4px; }}
    hr {{ border: none; border-top: 1px solid #D1D5DB; margin: 6px 0; }}
    h2 {{ font-size: 12.5px; text-transform: uppercase; margin: 6px 0 3px 0; color: #111827; letter-spacing: 0.5px; }}
    h3 {{ font-size: 11.5px; margin: 4px 0 2px 0; color: #1F2937; }}
    ul {{ margin: 2px 0 4px 0; padding-left: 16px; }}
    li {{ margin-bottom: 2.5px; text-align: justify; }}
    b, strong {{ color: #000000; }}
  </style>
</head>
<body>
  <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 4px;">
    <div>
      <h1 style="margin-bottom: 3px;">{cand['name']}</h1>
      <div style="font-size: 11px; font-weight: 600; color: #1E40AF; margin-bottom: 4px;">求职意向：{cand.get('title', '运营岗')}</div>
      <div class="contact" style="margin-bottom: 0;">电话：{cand['phone']} &nbsp;|&nbsp; 邮箱：{cand['email']} &nbsp;|&nbsp; {cand['location']}</div>
    </div>
    <div style="width: 72px; height: 96px; border: 1.5px dashed #9CA3AF; border-radius: 3px; background: #F9FAFB; display: flex; flex-direction: column; align-items: center; justify-content: center; flex-shrink: 0; text-align: center; overflow: hidden;" title="预留证件照位置">
      <img src="avatar.jpg" alt="证件照" style="width: 100%; height: 100%; object-fit: cover; display: none;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" onload="this.style.display='block'; this.nextElementSibling.style.display='none';">
      <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%;">
        <svg style="width: 18px; height: 18px; fill: #9CA3AF; margin-bottom: 2px;" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
        <span style="font-size: 8.5px; color: #6B7280; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
      </div>
    </div>
  </div>
  <hr>
  <h2>教育背景</h2>
  <h3>{cand['school']} ｜ {cand['degree']} <span style="float:right;">{cand.get('edu_time', '2023.09—2027.06')}</span></h3>
  <ul>{"".join([f'<li>{b}</li>' for b in edu_badges])}</ul>
  <hr>
  <h2>实习经历</h2>
  {"".join([f"<h3>{exp['org']} ｜ {exp['role']} <span style='float:right;'>{exp['time']}</span></h3><ul>{''.join([f'<li>{b}</li>' for b in exp.get('bullets', [])])}</ul>" for exp in exp_list])}
  <hr>
  <h2>校园与实践经历</h2>
  {"".join([f"<h3>{p['name']} ｜ {p['role']} <span style='float:right;'>{p['time']}</span></h3><ul>{''.join([f'<li>{b}</li>' for b in p.get('bullets', [])])}</ul>" for p in proj_list])}
  <hr>
  <h2>专业技能</h2>
  <ul>{"".join([f"<li><b>{k}：</b>{v}</li>" for k, v in comps.items()])}</ul>
</body>
</html>"""
    html_path = output_dir / "resume_ats_plain.html"
    html_path.write_text(ats_html, encoding="utf-8")
    pdf_path = output_dir / "resume_ats_plain.pdf"

    print("[+] Rendering ATS Plain PDF...")
    renderer.render_pdf(html_path, pdf_path)
    return pdf_path


def build_academic_typst(profile: dict, output_dir: Path):
    cand = profile["candidate"]
    comps = profile.get("competencies", {})
    exp_list = profile.get("experience", [])
    proj_list = profile.get("projects", [])
    edu_badges = cand.get("education_badges", [])
    email_safe = cand['email'].replace("@", r"\@")

    typ_lines = [
        '#set page(paper: "a4", margin: (x: 1.5cm, y: 1.5cm))',
        '#set text(font: ("Microsoft YaHei", "SimSun", "Helvetica"), size: 10pt)',
        '#set par(justify: true, leading: 0.65em)',
        "",
        '#grid(',
        '  columns: (1fr, 72pt),',
        '  gutter: 15pt,',
        '  align: (left + horizon, right + horizon),',
        '  [',
        f'    #text(size: 17pt, weight: "bold")[{cand["name"]}] \\',
        f'    #text(size: 10.5pt, weight: "medium", fill: rgb("#0284C7"))[求职意向：{cand.get("title", "运营岗")}] \\',
        f'    #text(size: 9.5pt, fill: rgb("#4B5563"))[电话：{cand["phone"]} | 邮箱：{email_safe} | {cand["location"]}]',
        '  ],',
        '  rect(',
        '    width: 72pt,',
        '    height: 94pt,',
        '    stroke: (dash: "dashed", paint: luma(150), thickness: 1pt),',
        '    radius: 3pt,',
        '    fill: luma(248),',
        '    align(center + horizon)[',
        '      #text(size: 8.5pt, fill: luma(110))[',
        '        预留证件照\\',
        '        一寸 / 二寸',
        '      ]',
        '    ]',
        '  )',
        ')',
        "",
        "== 教育背景",
        f"- *{cand['school']}* -- {cand['degree']} #h(1fr) {cand.get('edu_time', '2023.09 — 2027.06')}",
    ]
    for b in edu_badges:
        typ_lines.append(f"  - {b}")

    typ_lines.extend(["", "== 实习经历"])
    for exp in exp_list:
        typ_lines.append(f"=== {exp['org']} ｜ {exp['role']} #h(1fr) _{exp['time']}_")
        for b in exp.get("bullets", []):
            typ_lines.append(f"- {b}")

    typ_lines.extend(["", "== 校园与实践经历"])
    for proj in proj_list:
        typ_lines.append(f"=== {proj['name']} ｜ {proj['role']} #h(1fr) _{proj['time']}_")
        for b in proj.get("bullets", []):
            typ_lines.append(f"- {b}")

    if comps:
        typ_lines.extend(["", "== 专业技能"])
        for k, v in comps.items():
            typ_lines.append(f"- *{k}*: {v}")

    typ_src = "\n".join(typ_lines)
    typ_path = output_dir / "resume_academic_typst.typ"
    typ_path.write_text(typ_src, encoding="utf-8")

    pdf_path = output_dir / "resume_academic_typst.pdf"
    print("[+] Compiling Academic Typst PDF via typst.compile...")
    typst.compile(typ_path, output=str(pdf_path))
    return pdf_path


def build_academic_latex(profile: dict, output_dir: Path, renderer: BrowserRenderer):
    cand = profile["candidate"]
    comps = profile.get("competencies", {})
    exp_list = profile.get("experience", [])
    proj_list = profile.get("projects", [])
    edu_badges = cand.get("education_badges", [])

    # Escape LaTeX
    def esc_l(text: str) -> str:
        rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}
        for k, v in rep.items():
            text = text.replace(k, v)
        return text

    tex_lines = [
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
        r"\noindent",
        r"\begin{minipage}[c]{0.78\textwidth}",
        f"  {{\\LARGE \\textbf{{{esc_l(cand['name'])}}}}} \\\\[4pt]",
        f"  \\textbf{{\\color{{blue!70!black}}求职意向：{esc_l(cand.get('title', '运营岗'))}}} \\\\[3pt]",
        f"  电话：{esc_l(cand['phone'])} \\quad | \\quad 邮箱：\\href{{mailto:{esc_l(cand['email'])}}}{{{esc_l(cand['email'])}}} \\quad | \\quad {esc_l(cand['location'])}",
        r"\end{minipage}%",
        r"\hfill",
        r"\begin{minipage}[c]{0.20\textwidth}",
        r"  \flushright",
        r"  \fbox{\parbox[c][75pt][c]{55pt}{\centering \small 预留证件照\\一寸/二寸}}",
        r"\end{minipage}",
        r"\vspace{6pt}",
        r"\section*{教育背景}",
        r"\begin{itemize}[leftmargin=*,itemsep=2pt]",
        f"  \\item \\textbf{{{esc_l(cand['school'])}}} \\hfill {esc_l(cand['degree'])} ({esc_l(cand.get('edu_time', ''))})",
    ]
    for b in edu_badges:
        tex_lines.append(f"  \\item {esc_l(b)}")
    tex_lines.append(r"\end{itemize}")

    tex_lines.append(r"\section*{实习经历}")
    for exp in exp_list:
        tex_lines.append(r"\begin{itemize}[leftmargin=*,itemsep=2pt]")
        tex_lines.append(f"  \\item \\textbf{{{esc_l(exp['org'])}}} \\hfill \\textbf{{{esc_l(exp['role'])}}} ({esc_l(exp['time'])})")
        tex_lines.append(r"  \begin{itemize}[leftmargin=*,itemsep=1pt]")
        for b in exp.get("bullets", []):
            tex_lines.append(f"    \\item {esc_l(b)}")
        tex_lines.append(r"  \end{itemize}")
        tex_lines.append(r"\end{itemize}")

    tex_lines.append(r"\section*{校园与实践经历}")
    for proj in proj_list:
        tex_lines.append(r"\begin{itemize}[leftmargin=*,itemsep=2pt]")
        tex_lines.append(f"  \\item \\textbf{{{esc_l(proj['name'])}}} \\hfill \\textbf{{{esc_l(proj['role'])}}} ({esc_l(proj['time'])})")
        tex_lines.append(r"  \begin{itemize}[leftmargin=*,itemsep=1pt]")
        for b in proj.get("bullets", []):
            tex_lines.append(f"    \\item {esc_l(b)}")
        tex_lines.append(r"  \end{itemize}")
        tex_lines.append(r"\end{itemize}")

    if comps:
        tex_lines.append(r"\section*{专业技能}")
        tex_lines.append(r"\begin{itemize}[leftmargin=*,itemsep=2pt]")
        for k, v in comps.items():
            tex_lines.append(f"  \\item \\textbf{{{esc_l(k)}}}：{esc_l(v)}")
        tex_lines.append(r"\end{itemize}")

    tex_lines.append(r"\end{document}")

    tex_path = output_dir / "resume_academic_latex.tex"
    tex_path.write_text("\n".join(tex_lines), encoding="utf-8")
    print(f"[+] Generated Academic LaTeX source: {tex_path}")

    # Build LaTeX-styled HTML with photo slot
    latex_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{cand['name']} - 运营岗 学术风简历</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 12mm 16mm;
    }}
    body {{
      font-family: "Times New Roman", "SimSun", "Songti SC", serif;
      font-size: 11pt;
      line-height: 1.48;
      color: #000000;
      background: #FFFFFF;
      margin: 0;
      padding: 0;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8pt;
      border-bottom: 1.5pt solid #1e3a8a;
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
      <h1>{cand['name']}</h1>
      <div style="font-size: 11pt; font-weight: bold; color: #1e3a8a; margin-bottom: 3pt;">求职意向：{cand.get('title', '运营岗')}</div>
      <div class="contact">
        电话：{cand['phone']} &nbsp;|&nbsp; 邮箱：{cand['email']} &nbsp;|&nbsp; {cand['location']}
      </div>
    </div>
    <div style="width: 72px; height: 96px; border: 1.5px dashed #1e3a8a; background: #fafafa; border-radius: 3px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; flex-shrink: 0;" title="预留证件照位置">
      <img src="avatar.jpg" alt="证件照" style="width: 100%; height: 100%; object-fit: cover; display: none;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" onload="this.style.display='block'; this.nextElementSibling.style.display='none';">
      <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%;">
        <span style="font-size: 8.5pt; color: #555; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
      </div>
    </div>
  </div>

  <h2>教育背景</h2>
  <div class="item-header">
    <span>{cand['school']} · {cand['degree']}</span>
    <span>{cand.get('edu_time', '2023.09 — 2027.06')}</span>
  </div>
  <ul>{"".join([f'<li>{b}</li>' for b in edu_badges])}</ul>

  <h2>实习经历</h2>
  {"".join([f"<div class='item-header'><span>{exp['org']} · {exp['role']}</span><span>{exp['time']}</span></div><ul>{''.join([f'<li>{b}</li>' for b in exp.get('bullets', [])])}</ul>" for exp in exp_list])}

  <h2>校园与实践经历</h2>
  {"".join([f"<div class='item-header'><span>{p['name']} · {p['role']}</span><span>{p['time']}</span></div><ul>{''.join([f'<li>{b}</li>' for b in p.get('bullets', [])])}</ul>" for p in proj_list])}

  <h2>专业技能</h2>
  <ul>{"".join([f"<li><b>{k}：</b>{v}</li>" for k, v in comps.items()])}</ul>
</body>
</html>"""

    academic_html_path = output_dir / "resume_academic_latex.html"
    academic_html_path.write_text(latex_html, encoding="utf-8")
    pdf_path = output_dir / "resume_academic_latex.pdf"
    print("[+] Rendering Academic LaTeX Style PDF...")
    renderer.render_pdf(academic_html_path, pdf_path)
    return pdf_path


def main():
    output_dir = Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print("OfferGet Resume Generation Pipeline (Fan Zengyu Edition)")
    print("==================================================")

    profile = load_profile()
    renderer = BrowserRenderer()
    autofit = AutoFitEngine(renderer)

    results = {}

    # 1. Silicon Clean
    results["Silicon Clean"] = render_html_theme("silicon-clean", profile, output_dir, autofit)

    # 2. Classic Tech
    results["Classic Tech"] = render_html_theme("classic-tech", profile, output_dir, autofit)

    # 3. Modern Navy
    results["Modern Navy"] = render_html_theme("modern-navy", profile, output_dir, autofit)

    # 4. ATS Plain
    results["ATS Plain"] = build_ats_plain(profile, output_dir, renderer)

    # 5. Academic Typst
    results["Academic Typst"] = build_academic_typst(profile, output_dir)

    # 6. Academic LaTeX
    results["Academic LaTeX"] = build_academic_latex(profile, output_dir, renderer)

    print("\n==================================================")
    print("All 6 Resumes for Fan Zengyu Generated Successfully!")
    print("==================================================")
    for name, path in results.items():
        size_kb = path.stat().st_size / 1024
        print(f"  • {name:16s} -> {path.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
