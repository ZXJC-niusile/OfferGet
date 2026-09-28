"""
OfferGet Resume ViewModel & Decoupled Renderers (core/resume_view_model.py)
==========================================================================
Absorbs architectural patterns from ASu & RenderCV:
1. ResumeViewModel:
   - Decoupled, strongly-typed view model representation of resume data.
   - Pre-escaped strings and safe markdown bold conversions (preventing runtime XSS).
   - Clean factory `from_profile` supporting both Track 1 (SSOT) and Track 2 (minimal) profiles.
2. HtmlThemeRenderer:
   - Modular assembly of HTML resume themes (modern-navy, silicon-clean, classic-tech).
   - Independent section renderers (header, education, experience, projects, skills).
3. AtsPlainRenderer:
   - Decoupled single-column clean HTML and plain text Markdown renderer for ATS parsing.
"""

from __future__ import annotations

import base64
import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure OfferGet and ApexResume are in sys.path
from core.paths import get_project_root, get_theme_path

PROJECT_ROOT = get_project_root()

from core.profile_adapter import extract_education_grid, normalize_candidate_profile
from core.security_gate import (
    escape_html_attribute,
    escape_html_text,
    sanitize_url,
)


def _image_to_base64_data_uri(image_path: Optional[Union[str, Path]]) -> Optional[str]:
    """Reads a local image file (jpg/png/webp/gif/svg) and returns a base64 data URI."""
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


@dataclass
class ResumeViewModel:
    """Unified, pre-escaped View Model for cross-template resume rendering."""

    name: str = ""
    title: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    edu_school: str = ""
    edu_degree: str = ""
    edu_time: str = ""
    education_grid_rows: List[List[str]] = field(default_factory=list)
    experiences: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    competencies: Dict[str, List[str]] = field(default_factory=dict)
    publications: List[Dict[str, Any]] = field(default_factory=list)
    postgraduate_exam: Optional[Dict[str, Any]] = None
    photo_data_uri: Optional[str] = None
    reserve_photo: bool = True

    # Raw metadata preserved for Markdown and non-HTML formatters
    raw_name: str = ""
    raw_title: str = ""
    raw_phone: str = ""
    raw_email: str = ""
    raw_location: str = ""
    raw_school: str = ""
    raw_degree: str = ""
    raw_edu_time: str = ""
    photo_path: Optional[str] = None
    raw_profile: Optional[Dict[str, Any]] = None

    @property
    def section_projections(self) -> Dict[str, Any]:
        """Structured dictionary of section projections for theme rendering and ATS serialization."""
        return {
            "identity": {
                "name": self.name,
                "title": self.title,
                "phone": self.phone,
                "email": self.email,
                "location": self.location,
            },
            "education": {
                "school": self.edu_school,
                "degree": self.edu_degree,
                "time": self.edu_time,
                "grid_rows": self.education_grid_rows,
            },
            "postgraduate_exam": self.postgraduate_exam,
            "experiences": self.experiences,
            "projects": self.projects,
            "competencies": self.competencies,
            "publications": self.publications,
            "has_photo": bool(self.photo_data_uri or self.reserve_photo),
        }

    @classmethod
    def from_profile(
        cls,
        profile: Union[Dict[str, Any], Any],
        photo_path: Optional[Union[str, Path]] = None,
        reserve_photo: bool = True,
    ) -> ResumeViewModel:
        """
        Factory method constructing a sanitized ResumeViewModel from raw or normalized profile.
        Ensures all HTML-rendered fields are pre-sanitized against XSS and markdown bold
        formatting (**bold**) is safely converted to <strong>bold</strong>.
        """
        if isinstance(profile, ResumeViewModel):
            return profile
        prof = normalize_candidate_profile(profile)
        raw_p = getattr(profile, "raw_profile", None) or (profile if isinstance(profile, dict) else None)
        fallback_edu = profile.get("education") if isinstance(profile, dict) else None
        return cls.from_normalized_profile(
            prof=prof,
            photo_path=photo_path,
            reserve_photo=reserve_photo,
            raw_profile=raw_p,
            fallback_education=fallback_edu,
        )

    @classmethod
    def from_normalized_profile(
        cls,
        prof: Dict[str, Any],
        photo_path: Optional[Union[str, Path]] = None,
        reserve_photo: bool = True,
        raw_profile: Optional[Dict[str, Any]] = None,
        fallback_education: Optional[Dict[str, Any]] = None,
    ) -> ResumeViewModel:
        """
        Constructs a sanitized ResumeViewModel directly from an already normalized profile.
        Bypasses duplicate schema normalization when operating in an optimized pipeline.
        """
        cand = prof.get("candidate", {})

        # Basic identity
        raw_name = str(cand.get("name", "")).strip()
        raw_title = str(cand.get("title", "")).strip()
        raw_phone = str(cand.get("phone", "")).strip()
        raw_email = str(cand.get("email", "")).strip()
        raw_loc = str(cand.get("location", "")).strip()

        name = escape_html_text(raw_name)
        title = escape_html_text(raw_title)
        phone = escape_html_text(raw_phone)
        email = escape_html_text(raw_email)
        location = escape_html_text(raw_loc)

        # Education
        raw_school = str(cand.get("school", "")).strip()
        degree_raw = re.sub(r"\s*[｜|·]\s*", "  ", str(cand.get("degree", ""))).strip()
        raw_edu_time = str(cand.get("edu_time", "")).strip()

        edu_school = escape_html_text(raw_school)
        edu_degree = escape_html_text(degree_raw)
        edu_time = escape_html_text(raw_edu_time)

        # Education Grid Rows
        raw_grid = extract_education_grid(cand)
        if not raw_grid:
            edu = fallback_education or (raw_profile.get("education") if isinstance(raw_profile, dict) else {})
            fallback_badges = []
            for k in ["gpa", "awards", "certificates", "courses", "honors"]:
                val = cand.get(k) or (edu.get(k) if isinstance(edu, dict) else None)
                if val:
                    fallback_badges.append(str(val).strip())
            if fallback_badges:
                raw_grid = extract_education_grid({"education_badges": fallback_badges})

        education_grid_rows: List[List[str]] = []
        for row in raw_grid:
            clean_row: List[str] = []
            for cell in row:
                c_clean = re.sub(r"\s*[｜|]\s*", " ", str(cell)).strip()
                clean_row.append(escape_html_text(c_clean))
            if clean_row:
                education_grid_rows.append(clean_row)

        # Experiences
        experiences: List[Dict[str, Any]] = []
        for exp in prof.get("experience", []):
            if not isinstance(exp, dict):
                continue
            dept_raw = str(exp.get("dept", "")).strip()
            role_raw = str(exp.get("role", "")).strip()
            org_raw = str(exp.get("org", "") or exp.get("company", "")).strip()
            time_raw = str(exp.get("time", "")).strip()
            bullets_raw = [str(b).strip() for b in exp.get("bullets", []) if str(b).strip()]

            role_label_raw = f"{dept_raw} · {role_raw}" if dept_raw else role_raw

            formatted_bullets = [
                re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape_html_text(b))
                for b in bullets_raw
            ]

            experiences.append({
                "org": escape_html_text(org_raw),
                "dept": escape_html_text(dept_raw),
                "role": escape_html_text(role_raw),
                "role_label": escape_html_text(role_label_raw),
                "time": escape_html_text(time_raw),
                "bullets": formatted_bullets,
                "raw_org": org_raw,
                "raw_dept": dept_raw,
                "raw_role": role_raw,
                "raw_role_label": role_label_raw,
                "raw_time": time_raw,
                "raw_bullets": bullets_raw,
            })

        # Projects
        projects: List[Dict[str, Any]] = []
        for proj in prof.get("projects", []):
            if not isinstance(proj, dict):
                continue
            p_name_raw = str(proj.get("name", "")).strip()
            p_role_raw = str(proj.get("role", "")).strip()
            p_time_raw = str(proj.get("time", "")).strip()
            bullets_raw = [str(b).strip() for b in proj.get("bullets", []) if str(b).strip()]

            formatted_bullets = [
                re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape_html_text(b))
                for b in bullets_raw
            ]

            projects.append({
                "name": escape_html_text(p_name_raw),
                "role": escape_html_text(p_role_raw),
                "time": escape_html_text(p_time_raw),
                "bullets": formatted_bullets,
                "raw_name": p_name_raw,
                "raw_role": p_role_raw,
                "raw_time": p_time_raw,
                "raw_bullets": bullets_raw,
            })

        # Competencies
        raw_comps = prof.get("competencies", {})
        competencies: Dict[str, List[str]] = {}
        if isinstance(raw_comps, dict):
            for k, v in raw_comps.items():
                k_clean = str(k).strip()
                if isinstance(v, list):
                    items = [str(x).strip() for x in v if str(x).strip()]
                elif isinstance(v, str):
                    if "," in v or "，" in v or "、" in v:
                        items = [s.strip() for s in re.split(r"[,，、]\s*", v) if s.strip()]
                    else:
                        items = [v.strip()] if v.strip() else []
                else:
                    items = [str(v).strip()] if str(v).strip() else []
                competencies[k_clean] = items

        # Publications
        publications: List[Dict[str, Any]] = []
        for pub in prof.get("publications", []):
            if not isinstance(pub, dict):
                continue
            publications.append({
                "title": escape_html_text(str(pub.get("title", ""))),
                "authors": escape_html_text(str(pub.get("authors", ""))),
                "venue": escape_html_text(str(pub.get("venue", ""))),
                "year": escape_html_text(str(pub.get("year", ""))),
                "raw_title": str(pub.get("title", "")),
                "raw_authors": str(pub.get("authors", "")),
                "raw_venue": str(pub.get("venue", "")),
                "raw_year": str(pub.get("year", "")),
            })

        # Postgraduate Exam resolution
        raw_pg = (
            prof.get("postgraduate_exam")
            or cand.get("postgraduate_exam")
            or (raw_profile.get("postgraduate_exam") if isinstance(raw_profile, dict) else None)
            or (raw_profile.get("candidate", {}).get("postgraduate_exam") if isinstance(raw_profile, dict) else None)
        )
        postgraduate_exam: Optional[Dict[str, Any]] = None
        if isinstance(raw_pg, dict) and raw_pg:
            target_school = str(raw_pg.get("target_school") or raw_pg.get("school") or raw_pg.get("target_institution") or "").strip()
            target_major = str(raw_pg.get("target_major") or raw_pg.get("major") or raw_pg.get("target_discipline") or "").strip()
            direction = str(raw_pg.get("direction") or raw_pg.get("research_direction") or "").strip()

            scores_data = raw_pg.get("scores")
            subjects: List[Dict[str, str]] = []
            total_val = str(raw_pg.get("total_score") or raw_pg.get("total") or raw_pg.get("总分") or "").strip()

            if isinstance(scores_data, list):
                for item in scores_data:
                    if isinstance(item, dict):
                        sub_name = str(item.get("name") or item.get("subject") or "").strip()
                        sub_score = str(item.get("score") or item.get("grade") or "").strip()
                        if sub_name and sub_score:
                            if sub_name == "总分" or sub_name.lower() == "total":
                                if not total_val:
                                    total_val = sub_score
                            else:
                                subjects.append({
                                    "name": escape_html_text(sub_name),
                                    "score": escape_html_text(sub_score),
                                    "raw_name": sub_name,
                                    "raw_score": sub_score,
                                })
            elif isinstance(scores_data, dict):
                for k, v in scores_data.items():
                    k_str = str(k).strip()
                    v_str = str(v).strip()
                    if k_str == "总分" or k_str.lower() == "total":
                        if not total_val:
                            total_val = v_str
                    else:
                        subjects.append({
                            "name": escape_html_text(k_str),
                            "score": escape_html_text(v_str),
                            "raw_name": k_str,
                            "raw_score": v_str,
                        })
            else:
                pol = raw_pg.get("politics") or raw_pg.get("political_theory") or raw_pg.get("思想政治理论") or raw_pg.get("政治")
                if pol is not None:
                    pol_name = str(raw_pg.get("politics_name") or "政治").strip()
                    subjects.append({"name": escape_html_text(pol_name), "score": escape_html_text(str(pol).strip()), "raw_name": pol_name, "raw_score": str(pol).strip()})

                fl = raw_pg.get("foreign_language") or raw_pg.get("english") or raw_pg.get("外语") or raw_pg.get("英语") or raw_pg.get("英语（一）") or raw_pg.get("英语（二）")
                if fl is not None:
                    fl_name = str(raw_pg.get("foreign_language_name") or raw_pg.get("english_name") or "英语（一）").strip()
                    subjects.append({"name": escape_html_text(fl_name), "score": escape_html_text(str(fl).strip()), "raw_name": fl_name, "raw_score": str(fl).strip()})

                math_val = raw_pg.get("math_or_business_one") or raw_pg.get("math") or raw_pg.get("业务课一") or raw_pg.get("数学") or raw_pg.get("数学（一）") or raw_pg.get("数学（二）") or raw_pg.get("数学（三）")
                if math_val is not None:
                    math_name = str(raw_pg.get("math_name") or raw_pg.get("business_one_name") or "数学（一）").strip()
                    subjects.append({"name": escape_html_text(math_name), "score": escape_html_text(str(math_val).strip()), "raw_name": math_name, "raw_score": str(math_val).strip()})

                major_val = raw_pg.get("major_subject") or raw_pg.get("professional") or raw_pg.get("业务课二") or raw_pg.get("专业课")
                if major_val is not None:
                    maj_name = str(raw_pg.get("major_subject_name") or raw_pg.get("business_two_name") or "专业课").strip()
                    subjects.append({"name": escape_html_text(maj_name), "score": escape_html_text(str(major_val).strip()), "raw_name": maj_name, "raw_score": str(major_val).strip()})

            if not total_val and subjects:
                try:
                    num_scores = [float(s["raw_score"]) for s in subjects]
                    if len(num_scores) == len(subjects):
                        sum_val = sum(num_scores)
                        total_val = f"{int(sum_val)}" if sum_val.is_integer() else f"{sum_val:.1f}"
                except (ValueError, TypeError):
                    pass

            if target_school or target_major or direction or subjects or total_val:
                postgraduate_exam = {
                    "target_school": escape_html_text(target_school),
                    "target_major": escape_html_text(target_major),
                    "direction": escape_html_text(direction),
                    "subjects": subjects,
                    "total_score": escape_html_text(total_val),
                    "raw_target_school": target_school,
                    "raw_target_major": target_major,
                    "raw_direction": direction,
                    "raw_total_score": total_val,
                }

        # Photo resolution
        eff_photo_path = photo_path or cand.get("photo_path") or cand.get("photo")
        data_uri = _image_to_base64_data_uri(eff_photo_path) if eff_photo_path else None
        safe_data_uri = sanitize_url(data_uri, allow_data_image=True) if data_uri else None
        photo_data_uri = safe_data_uri if safe_data_uri else None

        # Determine effective reserve_photo preference
        if not reserve_photo:
            eff_reserve_photo = bool(photo_data_uri or eff_photo_path)
        else:
            cand_pref = cand.get("reserve_photo", None)
            if cand_pref is False:
                eff_reserve_photo = bool(photo_data_uri or eff_photo_path)
            else:
                eff_reserve_photo = True

        return cls(
            name=name,
            title=title,
            phone=phone,
            email=email,
            location=location,
            edu_school=edu_school,
            edu_degree=edu_degree,
            edu_time=edu_time,
            education_grid_rows=education_grid_rows,
            experiences=experiences,
            projects=projects,
            competencies=competencies,
            publications=publications,
            postgraduate_exam=postgraduate_exam,
            photo_data_uri=photo_data_uri,
            reserve_photo=eff_reserve_photo,
            raw_name=raw_name,
            raw_title=raw_title,
            raw_phone=raw_phone,
            raw_email=raw_email,
            raw_location=raw_loc,
            raw_school=raw_school,
            raw_degree=degree_raw,
            raw_edu_time=raw_edu_time,
            photo_path=str(eff_photo_path) if eff_photo_path else None,
            raw_profile=prof,
        )


def resolve_theme_template(
    theme_normalized: str,
    template_dir: Optional[Union[str, Path]] = None,
) -> str:
    """Resolves and loads theme HTML template from local filesystem or installed package resources."""
    candidates = []
    if template_dir:
        candidates.append(Path(template_dir).resolve() / f"{theme_normalized}.html")
    candidates.append(get_theme_path(theme_normalized))

    for p in candidates:
        if p.is_file():
            return p.read_text(encoding="utf-8")

    try:
        import importlib.resources as pkg_resources

        ref = pkg_resources.files("ApexResume").joinpath("themes", f"{theme_normalized}.html")
        if ref.is_file():
            return ref.read_text(encoding="utf-8")
    except Exception:
        pass

    raise FileNotFoundError(
        f"Template not found for theme {theme_normalized} across {[str(c) for c in candidates]}"
    )


class HtmlThemeRenderer:
    """Renders HTML-based themes from ResumeViewModel."""

    THEMES = (
        "modern-navy",
        "silicon-clean",
        "classic-tech",
        "asu-dense",
        "sidebar-clean",
        "academic-postgraduate",
        "engineering-sb2nov",
        "modern-corporate",
    )

    def render_header(self, vm: ResumeViewModel, theme_name: str = "modern-navy") -> str:
        """Renders header markup with optional photo placeholder."""
        loc_str = f"<span>•</span><span>{vm.location}</span>" if vm.location else ""
        if theme_name == "academic-postgraduate":
            title_prefix = "申请方向："
            title_color = "var(--color-primary, #8B1E1E)"
            header_style = "display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--color-primary, #8B1E1E); border-bottom:2.5px solid var(--color-primary, #8B1E1E); padding:6px 0; margin-bottom:var(--section-gap, 10px);"
            name_style = "font-size:24px; font-weight:700; color:var(--color-primary, #8B1E1E); font-family:var(--font-serif, serif); letter-spacing:2px; margin-bottom:2px;"
        else:
            title_prefix = "求职意向："
            title_color = "var(--color-accent, #0284C7)"
            header_style = "display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom:1.5px solid var(--color-primary, #0F172A); padding-bottom:5px;"
            name_style = "font-size:22px; font-weight:700; margin-bottom:2px;"

        title_html = (
            f'<span style="font-size:12px; font-weight:600; color:{title_color};">{title_prefix}{vm.title}</span>'
            if vm.title else ""
        )

        mailto_url = sanitize_url(f"mailto:{vm.raw_email or vm.email}") if (vm.raw_email or vm.email) else ""
        if mailto_url:
            email_link = f'<a href="{escape_html_attribute(mailto_url)}" style="color:inherit; text-decoration:none;">{vm.email}</a>'
        else:
            email_link = f'<span>{vm.email}</span>'

        photo_html = ""
        if vm.photo_data_uri:
            src_attr = escape_html_attribute(vm.photo_data_uri)
            photo_html = f"""
      <div class="photo-placeholder" style="width:72px; height:96px; border:none !important; outline:none !important; box-shadow:none !important; background:transparent; border-radius:0; display:flex; align-items:center; justify-content:center; flex-shrink:0; overflow:hidden;" title="证件照">
        <img src="{src_attr}" alt="证件照" style="max-width:100%; max-height:100%; width:auto; height:auto; object-fit:contain; border:none !important; outline:none !important; box-shadow:none !important; display:block; image-rendering:-webkit-optimize-contrast;" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
        <div style="display:none; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%;">
          <span style="font-size:8.5px; color:var(--color-muted, #64748B); line-height:1.2;">预留证件照<br>一寸 / 二寸</span>
        </div>
      </div>
            """
        elif vm.reserve_photo:
            photo_html = """
      <div class="photo-placeholder" style="width:72px; height:96px; border:1.5px dashed var(--color-border, #CBD5E1); background:var(--color-bg-subtle, #F8FAFC); border-radius:3px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; flex-shrink:0;" title="预留证件照位置">
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%;">
          <span style="font-size:8.5px; color:var(--color-muted, #64748B); line-height:1.2;">预留证件照<br>一寸 / 二寸</span>
        </div>
      </div>
            """

        return f"""
    <header style="{header_style}">
      <div style="flex:1; padding-right:12px;">
        <div class="header-top" style="display:flex; align-items:baseline; justify-content:space-between; border-bottom:none; margin-bottom:0; padding-bottom:0;">
          <h1 style="{name_style}">{vm.name}</h1>
          {title_html}
        </div>
        <div class="contacts" style="display:flex; gap:8px; font-size:11.2px; color:var(--color-muted, #64748B); margin-top:3px;">
          <span>{vm.phone}</span>
          <span>•</span>
          <span>{email_link}</span>
          {loc_str}
        </div>
      </div>
      {photo_html}
    </header>
    """

    def render_education(self, vm: ResumeViewModel) -> str:
        """Renders education background with clean multi-column grid."""
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
                grid_cells_html.append(f'<div>{cell_clean}</div>')

        edu_grid_html = f"""
      <div class="edu-grid" style="display:grid; grid-template-columns:{col_template}; row-gap:3.5px; font-size:11.2px; color:var(--color-muted, #4B5563); line-height:1.54; margin-top:3.5px;">
        {"".join(grid_cells_html)}
      </div>"""

        role_span = (
            f'<span class="org-role" style="font-weight:600; font-size:11.8px; color:var(--color-accent, #0284C7);">{vm.edu_degree}</span>'
            if vm.edu_degree else ""
        )

        return f"""
    <section id="education">
      <div class="section-header">
        <h2>教育背景</h2>
        <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
      </div>
      <div class="org-bar" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:5px; margin-bottom:3px;">
        <div class="org-left" style="display:flex; align-items:baseline; gap:16px;">
          <span class="org-title" style="font-weight:700; font-size:12.6px; color:var(--color-primary-dark, #0F172A);">{vm.edu_school}</span>
          {role_span}
        </div>
        <div class="org-right" style="font-size:11.0px; color:var(--color-muted, #64748B);">{vm.edu_time}</div>
      </div>
      {edu_grid_html}
    </section>
    """

    def render_experience(self, vm: ResumeViewModel) -> str:
        """Renders work / internship experience section."""
        if not vm.experiences:
            return ""

        exp_parts = ["""
    <section id="experience">
      <div class="section-header">
        <h2>实习经历</h2>
        <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
      </div>
    """]
        for exp in vm.experiences:
            org_str = exp.get("org", "")
            role_label = exp.get("role_label") or exp.get("role", "")
            time_str = exp.get("time", "")
            bullets_li = "".join([f"<li>{b}</li>" for b in exp.get("bullets", [])])
            exp_parts.append(f"""
        <div class="org-bar" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:7px; margin-bottom:3px;">
          <div class="org-left" style="display:flex; align-items:baseline; gap:8px;">
            <span class="org-title" style="font-weight:700; font-size:12.6px; color:var(--color-primary-dark, #0F172A);">{org_str}</span>
            <span class="org-role" style="font-weight:600; font-size:11.8px; color:var(--color-accent, #0284C7);">{role_label}</span>
          </div>
          <div class="org-right" style="font-size:11.0px; color:var(--color-muted, #64748B);">{time_str}</div>
        </div>
        <ul>{bullets_li}</ul>
        """)
        exp_parts.append("</section>")
        return "\n".join(exp_parts)

    def render_projects(self, vm: ResumeViewModel) -> str:
        """Renders campus and practical project experiences."""
        if not vm.projects:
            return ""

        proj_parts = ["""
    <section id="projects">
      <div class="section-header">
        <h2>校园与实践经历</h2>
        <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
      </div>
    """]
        for proj in vm.projects:
            p_name = proj.get("name", "")
            p_role = proj.get("role", "")
            p_time = proj.get("time", "")
            bullets_li = "".join([f"<li>{b}</li>" for b in proj.get("bullets", [])])
            proj_parts.append(f"""
        <div class="project-header" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:7px; margin-bottom:3px;">
          <div style="display:flex; align-items:baseline; gap:8px;">
            <span style="font-weight:700; font-size:12.6px; color:var(--color-primary-dark, #0F172A);">{p_name}</span>
            <span style="font-weight:600; font-size:11.8px; color:var(--color-accent, #0284C7);">{p_role}</span>
          </div>
          <div style="font-size:11.0px; color:var(--color-muted, #64748B);">{p_time}</div>
        </div>
        <ul>{bullets_li}</ul>
        """)
        proj_parts.append("</section>")
        return "\n".join(proj_parts)

    def render_skills(self, vm: ResumeViewModel) -> str:
        """Renders professional competencies and skills."""
        if not vm.competencies:
            return ""

        skill_rows = []
        for k, v in vm.competencies.items():
            k_esc = escape_html_text(str(k))
            val_raw = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
            val_esc = escape_html_text(val_raw)
            val_formatted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", val_esc)
            skill_rows.append(f"""
        <li style="display:flex; align-items:baseline; gap:6px; margin-bottom:4.5px; line-height:1.58; font-size:11.6px;">
          <span style="font-weight:700; white-space:nowrap; flex-shrink:0; color:var(--color-primary-dark, #0F172A);">{k_esc}：</span>
          <span style="color:var(--color-text, #1E293B);">{val_formatted}</span>
        </li>
        """)

        return f"""
    <section id="skills">
      <div class="section-header">
        <h2>专业技能</h2>
        <div class="rule" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
      </div>
      <ul style="list-style:none; padding-left:0; margin-top:4px;">
        {"".join(skill_rows)}
      </ul>
    </section>
    """

    def render_postgraduate_exam(self, vm: ResumeViewModel, theme_name: str = "academic-postgraduate") -> str:
        """Renders postgraduate entrance exam and target institution section."""
        if not vm.postgraduate_exam:
            return ""

        pg = vm.postgraduate_exam
        school = pg.get("target_school", "")
        major = pg.get("target_major", "")
        direction = pg.get("direction", "")
        subjects = pg.get("subjects", [])
        total_score = pg.get("total_score", "")

        is_academic = (theme_name == "academic-postgraduate")
        color_primary = "var(--color-primary, #8B1E1E)" if is_academic else "var(--color-primary, #0F172A)"
        color_rule = "var(--color-primary, #8B1E1E)" if is_academic else "var(--color-border, #E2E8F0)"

        target_items = []
        if school:
            target_items.append(f'<span><b>报考院校：</b>{school}</span>')
        if major:
            target_items.append(f'<span><b>报考专业：</b>{major}</span>')
        if direction:
            target_items.append(f'<span><b>研究方向：</b>{direction}</span>')

        target_bar_html = ""
        if target_items:
            target_bar_html = f"""
      <div class="exam-target-bar" style="display:flex; justify-content:space-between; align-items:baseline; margin-top:4px; margin-bottom:5px; font-size:11.8px;">
        {"".join(target_items)}
      </div>"""

        table_html = ""
        if subjects or total_score:
            th_cells = [f'<th class="score-label" style="background:#F5EFEB; font-weight:700; width:16%; border:1px solid #D8CFC4; padding:3.5px 5px; color:{color_primary};">初试成绩</th>']
            td_cells = ['<td class="score-sublabel" style="background:var(--color-bg-subtle, #FDFBF7); font-weight:600; color:var(--color-muted, #555555); border:1px solid #D8CFC4; padding:3.5px 5px;">得分</td>']

            for sub in subjects:
                th_cells.append(f'<th style="border:1px solid #D8CFC4; padding:3.5px 5px; font-weight:600;">{sub["name"]}</th>')
                td_cells.append(f'<td style="border:1px solid #D8CFC4; padding:3.5px 5px;">{sub["score"]}</td>')

            if total_score:
                th_cells.append(f'<th class="score-total-head" style="background:#F8ECE8; color:{color_primary}; font-weight:700; border:1px solid #D8CFC4; padding:3.5px 5px;">总分</th>')
                td_cells.append(f'<td class="score-total-val" style="font-weight:700; color:{color_primary}; font-size:12px; background:#FCF6F4; border:1px solid #D8CFC4; padding:3.5px 5px;">{total_score}</td>')

            table_html = f"""
      <table class="exam-score-table" style="width:100%; border-collapse:collapse; margin-top:4px; margin-bottom:6px; text-align:center; font-size:11.2px; border:1.2px solid {color_primary};">
        <thead>
          <tr style="background:var(--color-bg-subtle, #FDFBF7); border-bottom:1.5px solid {color_primary};">
            {"".join(th_cells)}
          </tr>
        </thead>
        <tbody>
          <tr>
            {"".join(td_cells)}
          </tr>
        </tbody>
      </table>"""

        return f"""
    <section id="postgraduate-exam">
      <div class="section-header">
        <h2>报考信息</h2>
        <div class="rule" style="flex:1; height:1px; background:{color_rule};"></div>
      </div>
      {target_bar_html}
      {table_html}
    </section>
    """

    def render_sections(self, vm: ResumeViewModel, theme_name: str = "modern-navy") -> str:
        """Assembles all standard content sections into a unified markup string."""
        sections = []
        pg = self.render_postgraduate_exam(vm, theme_name=theme_name)
        if pg:
            sections.append(pg)
        edu = self.render_education(vm)
        if edu:
            sections.append(edu)
        exp = self.render_experience(vm)
        if exp:
            sections.append(exp)
        proj = self.render_projects(vm)
        if proj:
            sections.append(proj)
        skills = self.render_skills(vm)
        if skills:
            sections.append(skills)
        return "\n".join(sections)

    def render(
        self,
        vm: ResumeViewModel,
        theme_name: str = "modern-navy",
        template_dir: Optional[Union[str, Path]] = None,
        template_content: Optional[str] = None,
    ) -> str:
        """
        Renders complete HTML document by combining template boilerplate, header, and sections.
        """
        theme_normalized = theme_name.lower().replace("_", "-")
        if template_content is None:
            raw_template = resolve_theme_template(theme_normalized, template_dir=template_dir)
        else:
            raw_template = template_content

        header_html = self.render_header(vm, theme_name=theme_normalized)
        sections_html = self.render_sections(vm, theme_name=theme_normalized)

        header_regex = re.compile(r"<header>.*?</header>", re.DOTALL)
        if header_regex.search(raw_template):
            populated_html = header_regex.sub(header_html, raw_template)
        else:
            populated_html = raw_template

        populated_html = populated_html.replace("{{SECTIONS_CONTENT}}", sections_html)
        return populated_html


class AtsPlainRenderer:
    """Renders plain text ATS formats: Single-column Clean HTML and Plain Text Markdown."""

    def render_markdown(self, vm: ResumeViewModel) -> str:
        """Renders ATS-optimized structured Markdown."""
        photo_tag = ""
        if vm.photo_path:
            photo_tag = f" | 照片：{vm.photo_path}"
        elif vm.photo_data_uri:
            photo_tag = " | 照片：已嵌入证件照"
        elif vm.reserve_photo:
            photo_tag = " | 照片：预留证件照位置"

        ats_title = vm.raw_title or vm.title
        raw_name = vm.raw_name or vm.name
        raw_phone = vm.raw_phone or vm.phone
        raw_email = vm.raw_email or vm.email
        raw_loc = vm.raw_location or vm.location

        md_lines = [
            f"# {raw_name}",
        ]
        if ats_title:
            md_lines.append(f"求职意向：{ats_title}")

        md_lines.extend([
            f"电话：{raw_phone} | 邮箱：{raw_email} | {raw_loc}{photo_tag}",
        ])

        if vm.postgraduate_exam:
            pg = vm.postgraduate_exam
            md_lines.extend(["", "---", "", "## 报考信息"])
            school = pg.get("raw_target_school", pg.get("target_school", ""))
            major = pg.get("raw_target_major", pg.get("target_major", ""))
            direction = pg.get("raw_direction", pg.get("direction", ""))
            target_parts = []
            if school:
                target_parts.append(f"报考院校：{school}")
            if major:
                target_parts.append(f"报考专业：{major}")
            if direction:
                target_parts.append(f"研究方向：{direction}")
            if target_parts:
                md_lines.append(" | ".join(target_parts))

            subjects = pg.get("subjects", [])
            total_score = pg.get("raw_total_score", pg.get("total_score", ""))
            if subjects or total_score:
                sub_parts = [f"{s.get('raw_name', s.get('name', ''))}：{s.get('raw_score', s.get('score', ''))}" for s in subjects]
                if total_score:
                    sub_parts.append(f"总分：{total_score}")
                md_lines.append(f"初试成绩：{' | '.join(sub_parts)}")

        md_lines.extend([
            "",
            "---",
            "",
            "## 教育背景",
        ])

        raw_school = vm.raw_school or vm.edu_school
        raw_degree = vm.raw_degree or vm.edu_degree
        raw_edu_time = vm.raw_edu_time or vm.edu_time

        head_edu = f"{raw_school}    {raw_degree}" if raw_degree else raw_school
        head_edu_full = f"{head_edu}    {raw_edu_time}" if raw_edu_time else head_edu
        md_lines.append(f"### {head_edu_full}")

        grid = vm.education_grid_rows
        for r in grid:
            c1 = r[0] if len(r) > 0 else ""
            c2 = r[1] if len(r) > 1 else ""
            c3 = r[2] if len(r) > 2 else ""
            c1_clean = re.sub(r"\s*[｜|]\s*", " ", c1).strip()
            c2_clean = re.sub(r"\s*[｜|]\s*", " ", c2).strip()
            c3_clean = re.sub(r"\s*[｜|]\s*", " ", c3).strip()
            w1 = sum(2 if ord(ch) > 127 else 1 for ch in c1_clean)
            pad1 = max(4, 32 - w1)
            w2 = sum(2 if ord(ch) > 127 else 1 for ch in c2_clean)
            pad2 = max(4, 20 - w2)
            line = f"{c1_clean}{' ' * pad1}{c2_clean}{' ' * pad2}{c3_clean}".rstrip()
            md_lines.append(f"{line}  ")

        if vm.experiences:
            md_lines.extend(["", "---", "", "## 实习经历"])
            for exp in vm.experiences:
                dept_str = exp.get("raw_dept", exp.get("dept", ""))
                role_str = exp.get("raw_role", exp.get("role", ""))
                role_label = f"{dept_str} ｜ {role_str}" if dept_str else role_str
                org_str = exp.get("raw_org", exp.get("org", ""))
                time_str = exp.get("raw_time", exp.get("time", ""))
                md_lines.extend([
                    f"### {org_str} ｜ {role_label}",
                    f"**任职时间**：{time_str}",
                    "",
                ])
                for b in exp.get("raw_bullets", exp.get("bullets", [])):
                    md_lines.append(f"- {b}")
                md_lines.append("")

        if vm.projects:
            md_lines.extend(["---", "", "## 校园与实践经历"])
            for proj in vm.projects:
                p_name = proj.get("raw_name", proj.get("name", ""))
                p_role = proj.get("raw_role", proj.get("role", ""))
                p_time = proj.get("raw_time", proj.get("time", ""))
                md_lines.extend([
                    f"### {p_name} ｜ {p_role}",
                    f"**时间**：{p_time}",
                    "",
                ])
                for b in proj.get("raw_bullets", proj.get("bullets", [])):
                    md_lines.append(f"- {b}")
                md_lines.append("")

        if vm.competencies:
            md_lines.extend(["---", "", "## 专业技能"])
            for k, v in vm.competencies.items():
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                md_lines.append(f"- **{k}：**{val}")
            md_lines.append("")

        return "\n".join(md_lines)

    def render_html(self, vm: ResumeViewModel) -> str:
        """Renders single-column ATS clean HTML."""
        photo_box = ""
        if vm.photo_data_uri:
            src_attr = escape_html_attribute(vm.photo_data_uri)
            photo_box = f"""
    <div style="width: 72px; height: 96px; border: none !important; outline: none !important; box-shadow: none !important; background: transparent; border-radius: 0; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden;" title="证件照">
      <img src="{src_attr}" alt="证件照" style="max-width:100%; max-height:100%; width:auto; height:auto; object-fit:contain; border:none !important; outline:none !important; box-shadow:none !important; display:block; image-rendering:-webkit-optimize-contrast;" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';" />
      <div style="display:none; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%;">
        <span style="font-size: 8pt; color: #4b5563; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
      </div>
    </div>
            """
        elif vm.reserve_photo:
            photo_box = """
    <div style="width: 72px; height: 96px; border: 1.5px dashed #4b5563; background: #f9fafb; border-radius: 2px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; flex-shrink: 0;" title="预留证件照位置">
      <span style="font-size: 8pt; color: #4b5563; line-height: 1.2;">预留证件照<br>一寸 / 二寸</span>
    </div>
            """

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
                grid_cells_html.append(f'<div>{cell_clean}</div>')

        title_div = (
            f'<div style="font-size: 11pt; font-weight: bold; margin-bottom: 3pt;">求职意向：{vm.title}</div>'
            if vm.title else ""
        )

        ats_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Resume - ATS Plain ({vm.name})</title>
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
      font-family: Arial, Helvetica, "SimSun", sans-serif;
      font-size: 9.8pt;
      line-height: 1.46;
      color: #000000;
      background: #FFFFFF;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 7pt;
      border-bottom: 1pt solid #000000;
      padding-bottom: 4pt;
    }}
    h1 {{
      font-size: 18.5pt;
      font-weight: bold;
      margin: 0 0 2pt 0;
    }}
    .contact {{
      font-size: 9.8pt;
      color: #222222;
    }}
    h2 {{
      font-size: 11.2pt;
      font-weight: bold;
      border-bottom: 0.8pt solid #333333;
      padding-bottom: 1.5pt;
      margin-top: 7pt;
      margin-bottom: 3.5pt;
      text-transform: uppercase;
    }}
    .item-header {{
      display: flex;
      justify-content: space-between;
      font-size: 10.2pt;
      font-weight: bold;
      margin-top: 4.5pt;
    }}
    ul {{
      margin: 2pt 0 4pt 0;
      padding-left: 16pt;
    }}
    li {{
      font-size: 9.8pt;
      margin-bottom: 2.2pt;
      text-align: justify;
      line-height: 1.44;
    }}
  </style>
</head>
<body>
  <div class="header">
      <div>
        <h1>{vm.name}</h1>
        {title_div}
        <div class="contact">
          电话：{vm.phone} &nbsp;|&nbsp; 邮箱：{vm.email} &nbsp;|&nbsp; {vm.location}
        </div>
      </div>
    {photo_box}
  </div>
"""
        if vm.postgraduate_exam:
            pg = vm.postgraduate_exam
            school = pg.get("target_school", "")
            major = pg.get("target_major", "")
            direction = pg.get("direction", "")
            subjects = pg.get("subjects", [])
            total_score = pg.get("total_score", "")

            target_items = []
            if school:
                target_items.append(f"<span><b>报考院校：</b>{school}</span>")
            if major:
                target_items.append(f"<span><b>报考专业：</b>{major}</span>")
            if direction:
                target_items.append(f"<span><b>研究方向：</b>{direction}</span>")

            target_bar = f"  <div class='item-header' style='margin-bottom:3pt;'>{' &nbsp;&nbsp;&nbsp;&nbsp; '.join(target_items)}</div>\n" if target_items else ""

            sub_items = []
            for s in subjects:
                sub_items.append(f"<span>{s['name']}：<b>{s['score']}</b></span>")
            if total_score:
                sub_items.append(f"<span>总分：<b>{total_score}</b></span>")

            scores_bar = f"  <div style='font-size:9.5pt; line-height:1.4; margin-top:2pt; margin-bottom:3pt;'>初试成绩：{' &nbsp;|&nbsp; '.join(sub_items)}</div>\n" if sub_items else ""

            ats_html += f"""  <h2>报考信息</h2>
{target_bar}{scores_bar}"""

        ats_html += f"""
  <h2>教育背景</h2>
  <div class="item-header">
    <span>{vm.edu_school} &nbsp;&nbsp;&nbsp;&nbsp; {vm.edu_degree}</span>
    <span>{vm.edu_time}</span>
  </div>
  <div class="edu-grid" style="display:grid; grid-template-columns:{col_template}; row-gap:2pt; font-size:9.5pt; line-height:1.4; margin-top:2pt; margin-bottom:3pt;">
    {"".join(grid_cells_html)}
  </div>
"""
        if vm.experiences:
            ats_html += "  <h2>实习经历</h2>\n"
            for exp in vm.experiences:
                exp_org = exp.get("org", "")
                role_label = exp.get("role_label") or exp.get("role", "")
                exp_time = exp.get("time", "")
                bullets = "".join([f"<li>{b}</li>" for b in exp.get("bullets", [])])
                ats_html += f"""  <div class='item-header'><span>{exp_org} · {role_label}</span><span>{exp_time}</span></div>
  <ul>{bullets}</ul>
"""

        if vm.projects:
            ats_html += "  <h2>校园与实践经历</h2>\n"
            for p in vm.projects:
                p_name = p.get("name", "")
                p_role = p.get("role", "")
                p_time = p.get("time", "")
                bullets = "".join([f"<li>{b}</li>" for b in p.get("bullets", [])])
                ats_html += f"""  <div class='item-header'><span>{p_name} · {p_role}</span><span>{p_time}</span></div>
  <ul>{bullets}</ul>
"""

        if vm.competencies:
            ats_html += "  <h2>专业技能</h2>\n  <ul>"
            for k, v in vm.competencies.items():
                k_esc = escape_html_text(str(k))
                val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                val_esc = escape_html_text(val)
                ats_html += f"<li><b>{k_esc}：</b>{val_esc}</li>"
            ats_html += "</ul>\n"

        ats_html += "</body>\n</html>"
        return ats_html

    def render(self, vm: ResumeViewModel) -> Dict[str, str]:
        """Convenience method returning both Markdown and single-column HTML strings."""
        return {
            "md": self.render_markdown(vm),
            "html": self.render_html(vm),
        }


__all__ = [
    "ResumeViewModel",
    "HtmlThemeRenderer",
    "AtsPlainRenderer",
    "resolve_theme_template",
]
