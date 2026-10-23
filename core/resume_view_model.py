"""
OfferGet Resume ViewModel & Decoupled Renderers (core/resume_view_model.py)
==========================================================================
OfferGet native strongly-typed resume view model and decoupled renderers:
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

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.paths import get_project_root, get_theme_path
from core.resume_themes import HTML_THEMES

PROJECT_ROOT = get_project_root()

from core.profile_adapter import extract_education_grid, normalize_candidate_profile, require_public_profile
from core.security_gate import (
    escape_html_attribute,
    escape_html_text,
    sanitize_url,
)


from core.resume_photo import image_to_base64_data_uri as _image_to_base64_data_uri, resolve_photo  # noqa: F401 - public photo helper


PUBLICATION_FIELDS = (
    "title", "authors", "venue", "conference", "year", "status",
    "author_role", "highlight", "summary", "individual_contribution",
)
PUBLICATION_LABELS = {
    "status": "状态：", "author_role": "作者角色：", "individual_contribution": "个人贡献：",
}


def _publication_text(value: Any) -> str:
    """Preserve source strings and ordered string-list fields without Python repr."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value if item is not None and str(item).strip())
    return str(value)


def publication_facts(publication: Dict[str, Any]) -> List[tuple[str, str]]:
    """Return supplied facts only, decoding legacy HTML projections exactly once."""
    from html import unescape
    facts = []
    for key in PUBLICATION_FIELDS:
        raw_key = f"raw_{key}"
        value = (_publication_text(publication[raw_key]) if raw_key in publication
                 else unescape(_publication_text(publication.get(key))))
        if value.strip():
            facts.append((key, value))
    return facts


def publication_text_parts(publication: Dict[str, Any]) -> List[str]:
    """Label supplied qualifications without inferring publication or author status."""
    return [PUBLICATION_LABELS.get(key, "") + value for key, value in publication_facts(publication)]


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
    photo_mode: Optional[str] = None

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
        photo_mode: Optional[str] = None,
    ) -> ResumeViewModel:
        """
        Factory method constructing a sanitized ResumeViewModel from raw or normalized profile.
        Ensures all HTML-rendered fields are pre-sanitized against XSS and markdown bold
        formatting (**bold**) is safely converted to <strong>bold</strong>.
        """
        require_public_profile(vars(profile) if isinstance(profile, ResumeViewModel) else profile)
        if isinstance(profile, ResumeViewModel):
            if reserve_photo and photo_mode is None and photo_path is None:
                return profile
            from dataclasses import replace
            selection = resolve_photo({}, photo_path=photo_path or profile.photo_path,
                                      reserve_photo=reserve_photo,
                                      photo_mode=photo_mode if photo_mode is not None else profile.photo_mode)
            return replace(profile, photo_path=selection.path, photo_data_uri=selection.data_uri,
                           reserve_photo=selection.mode != "no-photo", photo_mode=selection.mode)
        prof = normalize_candidate_profile(profile)
        raw_p = getattr(profile, "raw_profile", None) or (profile if isinstance(profile, dict) else None)
        fallback_edu = profile.get("education") if isinstance(profile, dict) else None
        return cls.from_normalized_profile(
            prof=prof,
            photo_path=photo_path,
            reserve_photo=reserve_photo,
            photo_mode=photo_mode,
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
        photo_mode: Optional[str] = None,
    ) -> ResumeViewModel:
        """
        Constructs a sanitized ResumeViewModel directly from an already normalized profile.
        Bypasses duplicate schema normalization when operating in an optimized pipeline.
        """
        require_public_profile(prof, raw_profile, fallback_education)
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
            if isinstance(pub, str):
                pub = {"title": pub}
            if not isinstance(pub, dict):
                continue
            publication = {}
            for key in PUBLICATION_FIELDS:
                raw_value = _publication_text(pub.get(key))
                publication[key] = escape_html_text(raw_value)
                publication[f"raw_{key}"] = raw_value
            publications.append(publication)

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

        selection = resolve_photo(cand, photo_path=photo_path,
                                  reserve_photo=reserve_photo, photo_mode=photo_mode)

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
            photo_data_uri=selection.data_uri,
            reserve_photo=selection.mode != "no-photo",
            photo_mode=selection.mode,
            raw_name=raw_name,
            raw_title=raw_title,
            raw_phone=raw_phone,
            raw_email=raw_email,
            raw_location=raw_loc,
            raw_school=raw_school,
            raw_degree=degree_raw,
            raw_edu_time=raw_edu_time,
            photo_path=selection.path,
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

        for pkg_name in ("themes", "offerget"):
            try:
                ref = pkg_resources.files(pkg_name).joinpath(f"{theme_normalized}.html")
                if ref.is_file():
                    return ref.read_text(encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass

    raise FileNotFoundError(
        f"Template not found for theme {theme_normalized} across {[str(c) for c in candidates]}"
    )


class HtmlThemeRenderer:
    """Renders HTML-based themes from ResumeViewModel."""

    THEMES = HTML_THEMES

    def render_header(self, vm: ResumeViewModel, theme_name: str = "modern-navy") -> str:
        """Renders header markup with optional photo placeholder."""
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

        title_value = f'<span data-field="identity.title">{vm.title}</span>' if theme_name in self.SEMANTIC_THEMES else vm.title
        title_html = (
            f'<span class="resume-title"{self._style(f"font-size:12px; font-weight:600; color:{title_color};", theme_name)}>{title_prefix}{title_value}</span>'
            if vm.title else ""
        )

        mailto_url = sanitize_url(f"mailto:{vm.raw_email or vm.email}") if (vm.raw_email or vm.email) else ""
        if mailto_url:
            email_link = f'<a href="{escape_html_attribute(mailto_url)}" style="color:inherit; text-decoration:none;">{vm.email}</a>'
        else:
            email_link = f'<span>{vm.email}</span>'

        contact_items = []
        if vm.phone:
            contact_items.append(f'<span data-field="identity.phone">{vm.phone}</span>')
        if vm.email:
            contact_items.append(f'<span data-field="identity.email">{email_link}</span>')
        if vm.location:
            contact_items.append(f'<span data-field="identity.location">{vm.location}</span>')
        contacts_html = '<span aria-hidden="true">•</span>'.join(contact_items)

        photo_html = ""
        if vm.photo_data_uri:
            src_attr = escape_html_attribute(vm.photo_data_uri)
            photo_html = f"""
      <div class="photo-placeholder" style="width:72px; height:96px; border:none !important; outline:none !important; box-shadow:none !important; background:transparent; border-radius:0; display:flex; align-items:center; justify-content:center; flex-shrink:0; overflow:hidden;" title="证件照">
        <img src="{src_attr}" alt="证件照" style="max-width:100%; max-height:100%; width:auto; height:auto; object-fit:contain; border:none !important; outline:none !important; box-shadow:none !important; display:block; image-rendering:-webkit-optimize-contrast;" />
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
    <header class="resume-header"{self._style(header_style, theme_name)}>
      <div class="resume-identity"{self._style(f"flex:1; padding-right:{12 if photo_html else 0}px;", theme_name)}>
        <div class="header-top"{self._style("display:flex; align-items:baseline; justify-content:space-between; border-bottom:none; margin-bottom:0; padding-bottom:0;", theme_name)}>
          <h1 class="resume-name" data-field="identity.name"{self._style(name_style, theme_name)}>{vm.name}</h1>
          {title_html}
        </div>
        <div class="contacts resume-contacts"{self._style("display:flex; gap:8px; font-size:11.2px; color:var(--color-muted, #64748B); margin-top:3px;", theme_name)}>
          {contacts_html}
        </div>
      </div>
      {photo_html}
    </header>
    """

    # Stylesheet-owned themes opt in after their templates have migrated. The
    # existing inline defaults stay intact for every other theme.
    SEMANTIC_THEMES = frozenset({"modern-navy", "classic-tech", "silicon-clean", "modern-career"})

    @classmethod
    def _style(cls, css: str, theme_name: str = "") -> str:
        return "" if theme_name in cls.SEMANTIC_THEMES else f' style="{css}"'

    @classmethod
    def _section(cls, section_id: str, heading: str, body: str, theme_name: str = "") -> str:
        if theme_name in cls.SEMANTIC_THEMES:
            body = f'<div class="resume-section-body">{body}</div>'
        return f"""
    <section id="{section_id}" aria-labelledby="{section_id}-heading">
      <div class="section-header">
        <h2 id="{section_id}-heading">{heading}</h2>
        <div class="rule" aria-hidden="true" style="flex:1; height:1px; background:var(--color-border, #E2E8F0);"></div>
      </div>
      {body}
    </section>
    """

    def _entry(self, entry_id: str, title: str, role: str, date: str,
               body: str, theme_name: str = "", education: bool = False,
               project: bool = False) -> str:
        """Keep each date, identity and ordered body together in the source DOM."""
        style = lambda css: self._style(css, theme_name)
        heading_class = "project-header" if project else "org-bar"
        identity_class = "entry-identity" if project else "org-left entry-identity"
        title_class = "entry-title" if project else "org-title entry-title"
        role_class = "entry-role" if project else "org-role entry-role"
        date_class = "entry-date" if project else "org-right entry-date"
        title_key = "name" if project else "school" if education else "org"
        role_key = "degree" if education else "role"
        # The logical field is the displayed department + role label for work.
        date_html = f'<div class="{date_class}" data-field="{entry_id}.time"{style("font-size:11.0px; color:var(--color-muted, #64748B);")}>{date}</div>'
        role_html = f'<span class="{role_class}" data-field="{entry_id}.{role_key}"{style("font-weight:600; font-size:11.8px; color:var(--color-accent, #0284C7);")}>{role}</span>' if role or not education else ""
        heading = f"""
        <div class="{heading_class} entry-header"{style(f'display:flex; justify-content:space-between; align-items:baseline; margin-top:{5 if education else 7}px; margin-bottom:3px;')}>
          <div class="{identity_class}"{style(f'display:flex; align-items:baseline; gap:{16 if education else 8}px;')}>
            <span class="{title_class}" data-field="{entry_id}.{title_key}"{style('font-weight:700; font-size:12.6px; color:var(--color-primary-dark, #0F172A);')}>{title}</span>
            {role_html}
          </div>
          {date_html if not (theme_name == "classic-tech" and theme_name in self.SEMANTIC_THEMES) else ""}
        </div>"""
        if theme_name not in self.SEMANTIC_THEMES:
            return heading + "\n" + body
        rail = date_html if theme_name == "classic-tech" else ""
        return f'<div class="resume-entry" data-entry="{entry_id}">{rail}<div class="entry-content">{heading}{body}</div></div>'

    def render_education(self, vm: ResumeViewModel, theme_name: str = "") -> str:
        """Render the existing education facts without changing their row order."""
        grid = vm.education_grid_rows
        max_cols = max((len(r) for r in grid), default=1)
        col_template = "38% 28% 1fr" if max_cols >= 3 else "45% 1fr" if max_cols == 2 else "1fr"
        cells = []
        for row_index, row in enumerate(grid):
            for index in range(max_cols):
                value = row[index] if index < len(row) else ""
                value = re.sub(r"\s*[｜|]\s*", " ", value).strip()
                cells.append(f'<div data-field="education.grid.{row_index}.{index}">{value}</div>')
        grid_style = f'display:grid; grid-template-columns:{col_template}; row-gap:3.5px; font-size:11.2px; color:var(--color-muted, #4B5563); line-height:1.54; margin-top:3.5px;'
        # Column count is content-derived; visual themes decide their own layout.
        grid_html = f'<div class="edu-grid" data-columns="{max_cols}"{self._style(grid_style, theme_name)}>{"".join(cells)}</div>'
        body = self._entry("education", vm.edu_school, vm.edu_degree, vm.edu_time,
                           grid_html, theme_name, education=True)
        return self._section("education", "教育背景", body, theme_name)

    def render_experience(self, vm: ResumeViewModel, theme_name: str = "") -> str:
        if not vm.experiences:
            return ""
        entries = []
        for index, exp in enumerate(vm.experiences):
            entry_id = f"experience.{index}"
            bullets = "".join(f'<li data-field="{entry_id}.bullets.{i}">{b}</li>'
                              for i, b in enumerate(exp.get("bullets", [])))
            entries.append(self._entry(entry_id, exp.get("org", ""),
                exp.get("role_label") or exp.get("role", ""), exp.get("time", ""),
                f'<ul class="entry-bullets">{bullets}</ul>', theme_name))
        return self._section("experience", "实习经历", "\n".join(entries), theme_name)

    def render_projects(self, vm: ResumeViewModel, theme_name: str = "") -> str:
        if not vm.projects:
            return ""
        entries = []
        for index, project in enumerate(vm.projects):
            entry_id = f"projects.{index}"
            bullets = "".join(f'<li data-field="{entry_id}.bullets.{i}">{b}</li>'
                              for i, b in enumerate(project.get("bullets", [])))
            entries.append(self._entry(entry_id, project.get("name", ""),
                project.get("role", ""), project.get("time", ""),
                f'<ul class="entry-bullets">{bullets}</ul>', theme_name, project=True))
        return self._section("projects", "校园与实践经历", "\n".join(entries), theme_name)

    def render_skills(self, vm: ResumeViewModel, theme_name: str = "") -> str:
        if not vm.competencies:
            return ""
        style = lambda css: self._style(css, theme_name)
        rows = []
        for index, (key, values) in enumerate(vm.competencies.items()):
            key_escaped = escape_html_text(str(key))
            value = ", ".join(str(x) for x in values) if isinstance(values, list) else str(values)
            value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape_html_text(value))
            label = f'<span data-field="skills.{index}.label">{key_escaped}</span>' if theme_name in self.SEMANTIC_THEMES else key_escaped
            rows.append(f"""
        <li class="skill-row" data-entry="skills.{index}"{style('display:flex; align-items:baseline; gap:6px; margin-bottom:4.5px; line-height:1.58; font-size:11.6px;')}>
          <span class="skill-label"{style('font-weight:700; white-space:nowrap; flex-shrink:0; color:var(--color-primary-dark, #0F172A);')}>{label}：</span>
          <span class="skill-value" data-field="skills.{index}.value"{style('color:var(--color-text, #1E293B);')}>{value}</span>
        </li>""")
        body = f'<ul class="skills-list"{style("list-style:none; padding-left:0; margin-top:4px;")}>{"".join(rows)}</ul>'
        return self._section("skills", "专业技能", body, theme_name)

    def render_publications(self, vm: ResumeViewModel, theme_name: str = "") -> str:
        """Expose only the publication facts already present in the view model."""
        if not vm.publications:
            return ""
        entries = []
        for index, publication in enumerate(vm.publications):
            fields = []
            for key, text in publication_facts(publication):
                value = f'<span class="publication-{key}" data-field="publications.{index}.{key}">{escape_html_text(text)}</span>'
                label = PUBLICATION_LABELS.get(key, "")
                fields.append(f'<span class="publication-fact">{label}{value}</span>')
            if fields:
                entries.append(f'<li class="publication-entry" data-entry="publications.{index}">{" · ".join(fields)}</li>')
        if not entries:
            return ""
        return self._section("publications", "学术成果", f'<ul class="publication-list">{"".join(entries)}</ul>', theme_name)

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

        fact = lambda key, value: f'<span data-field="postgraduate_exam.{key}">{value}</span>' if theme_name in self.SEMANTIC_THEMES else value
        target_items = []
        if school:
            target_items.append(f'<span><b>报考院校：</b>{fact("target_school", school)}</span>')
        if major:
            target_items.append(f'<span><b>报考专业：</b>{fact("target_major", major)}</span>')
        if direction:
            target_items.append(f'<span><b>研究方向：</b>{fact("direction", direction)}</span>')

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

            for index, sub in enumerate(subjects):
                th_cells.append(f'<th data-field="postgraduate_exam.subjects.{index}.name" style="border:1px solid #D8CFC4; padding:3.5px 5px; font-weight:600;">{sub["name"]}</th>')
                td_cells.append(f'<td data-field="postgraduate_exam.subjects.{index}.score" style="border:1px solid #D8CFC4; padding:3.5px 5px;">{sub["score"]}</td>')

            if total_score:
                th_cells.append(f'<th class="score-total-head" style="background:#F8ECE8; color:{color_primary}; font-weight:700; border:1px solid #D8CFC4; padding:3.5px 5px;">总分</th>')
                td_cells.append(f'<td class="score-total-val" data-field="postgraduate_exam.total_score" style="font-weight:700; color:{color_primary}; font-size:12px; background:#FCF6F4; border:1px solid #D8CFC4; padding:3.5px 5px;">{total_score}</td>')

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

        body = target_bar_html + "\n" + table_html
        if theme_name in self.SEMANTIC_THEMES:
            body = f'<div class="resume-section-body">{body}</div>'
        return f"""
    <section id="postgraduate-exam" aria-labelledby="postgraduate-exam-heading">
      <div class="section-header">
        <h2 id="postgraduate-exam-heading">报考信息</h2>
        <div class="rule" style="flex:1; height:1px; background:{color_rule};"></div>
      </div>
      {body}
    </section>
    """

    def render_sections(self, vm: ResumeViewModel, theme_name: str = "modern-navy") -> str:
        """Declare reading order in the DOM, never through visual CSS reordering."""
        sections = {
            "postgraduate-exam": self.render_postgraduate_exam(vm, theme_name),
            "education": self.render_education(vm, theme_name),
            "experience": self.render_experience(vm, theme_name),
            "projects": self.render_projects(vm, theme_name),
            "skills": self.render_skills(vm, theme_name),
            "publications": self.render_publications(vm, theme_name),
        }
        if theme_name == "silicon-clean" and theme_name in self.SEMANTIC_THEMES:
            opening = "\n".join(sections[key] for key in ("postgraduate-exam", "education") if sections[key])
            left = sections["experience"]
            right = "\n".join(sections[key] for key in ("projects", "publications") if sections[key])
            columns = []
            if left:
                columns.append(f'<div class="resume-column" data-column="left">{left}</div>')
            if right:
                columns.append(f'<div class="resume-column" data-column="right">{right}</div>')
            # Reserve a two-column body only when both editorial lanes have facts.
            body_class = "resume-columns" if left and right else "resume-single-column"
            body = f'<div class="{body_class}">{"".join(columns)}</div>' if columns else ""
            return f'<div class="resume-sections" data-layout="balanced-columns">{opening}{body}{sections["skills"]}</div>'
        content = "\n".join(section for section in sections.values() if section)
        if theme_name in self.SEMANTIC_THEMES:
            layout = "date-rail" if theme_name == "classic-tech" else "label-gutter"
            return f'<div class="resume-sections" data-layout="{layout}">{content}</div>'
        return content

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
        require_public_profile(vars(vm))
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
        require_public_profile(vars(vm))
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

        publications = [publication_text_parts(pub) for pub in vm.publications]
        publications = [parts for parts in publications if parts]
        if publications:
            md_lines.extend(["", "---", "", "## 学术成果"])
            md_lines.extend("- " + " · ".join(parts).replace("\n", "\n  ") for parts in publications)

        return "\n".join(md_lines)

    def render_html(self, vm: ResumeViewModel) -> str:
        """Render readable, linear HTML without changing the Markdown contract."""
        require_public_profile(vars(vm))
        photo_box = ""
        if vm.photo_data_uri:
            src_attr = escape_html_attribute(vm.photo_data_uri)
            photo_box = f"""
      <div class="photo" title="证件照">
        <img src="{src_attr}" alt="证件照" />
      </div>"""
        elif vm.reserve_photo:
            photo_box = """
      <div class="photo photo-reserved" title="预留证件照位置">
        <span>预留证件照<br>一寸 / 二寸</span>
      </div>"""

        # Education remains in source order, but no longer depends on columns
        # whose individual cells can collide or interleave in text extraction.
        education_rows = []
        for row in vm.education_grid_rows:
            cells = [re.sub(r"\s*[｜|]\s*", " ", cell).strip() for cell in row]
            education_rows.extend(f"<p>{cell}</p>" for cell in cells if cell)

        title_line = f'<p class="target-role">求职意向：{vm.title}</p>' if vm.title else ""
        contacts = []
        if vm.phone:
            contacts.append(f"<span>电话：{vm.phone}</span>")
        if vm.email:
            contacts.append(f"<span>邮箱：{vm.email}</span>")
        if vm.location:
            contacts.append(f"<span>{vm.location}</span>")
        contact_line = ' <span class="separator" aria-hidden="true">|</span> '.join(contacts)

        ats_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resume - ATS Plain ({vm.name})</title>
  <style>
    @page {{ size: A4 portrait; margin: 15mm 16mm; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Arial, Helvetica, "Noto Sans CJK SC", "Microsoft YaHei", "SimSun", sans-serif;
      font-size: 10.5pt;
      line-height: 1.48;
      color: #171717;
      background: #ffffff;
      overflow-wrap: anywhere;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .resume {{ max-width: 210mm; margin: 0 auto; padding: 15mm 16mm; }}
    .header {{ display: flex; flex-wrap: wrap; gap: 10pt 16pt; margin-bottom: 14pt; }}
    .identity {{ flex: 1 1 240px; min-width: 0; }}
    h1 {{ font-size: 23pt; line-height: 1.18; font-weight: 700; margin-bottom: 5pt; }}
    .target-role {{ font-size: 11pt; line-height: 1.4; margin-bottom: 5pt; }}
    .contact {{ font-size: 9.5pt; line-height: 1.5; }}
    .contact > span {{ overflow-wrap: anywhere; }}
    .separator {{ padding: 0 2pt; }}
    h2 {{
      font-size: 11.5pt; line-height: 1.35; font-weight: 700;
      margin: 13pt 0 6pt; padding-bottom: 3pt; border-bottom: 0.6pt solid #737373;
      break-after: avoid; page-break-after: avoid;
    }}
    .item-header {{
      font-size: 10.5pt; line-height: 1.45; font-weight: 700; margin-top: 7pt;
      break-after: avoid; page-break-after: avoid;
    }}
    .item-date {{
      font-size: 9.5pt; line-height: 1.45; margin: 1pt 0 3pt;
      break-after: avoid; page-break-after: avoid;
    }}
    .edu-grid, .exam-details {{ font-size: 10pt; line-height: 1.48; }}
    .edu-grid p, .exam-details p {{ margin-top: 2pt; }}
    ul {{ margin: 3pt 0 5pt; padding-left: 15pt; }}
    li {{ margin-bottom: 3pt; padding-left: 1pt; text-align: left; orphans: 2; widows: 2; }}
    p {{ orphans: 2; widows: 2; }}
    .photo {{
      width: 20mm; height: 26mm; flex: 0 0 20mm;
      display: flex; align-items: center; justify-content: center;
      font-size: 8pt; line-height: 1.35; text-align: center;
    }}
    .photo img {{ max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; }}
    .photo-reserved {{ border: 0.6pt dashed #737373; }}
    @media screen and (max-width: 600px) {{ .resume {{ padding: 24px 20px; }} }}
    @media print {{ .resume {{ max-width: none; margin: 0; padding: 0; }} }}
  </style>
</head>
<body>
  <main class="resume">
    <header class="header">
      <div class="identity">
        <h1>{vm.name}</h1>
        {title_line}
        <p class="contact">{contact_line}</p>
      </div>
      {photo_box}
    </header>
"""
        if vm.postgraduate_exam:
            pg = vm.postgraduate_exam
            details = []
            for key, label in (("target_school", "报考院校"), ("target_major", "报考专业"), ("direction", "研究方向")):
                if pg.get(key):
                    details.append(f"<p><b>{label}：</b>{pg[key]}</p>")
            subjects = pg.get("subjects", [])
            score_parts = [f"{subject['name']}：{subject['score']}" for subject in subjects]
            if pg.get("total_score"):
                score_parts.append(f"总分：{pg['total_score']}")
            if score_parts:
                details.append(f"<p>初试成绩：{' | '.join(score_parts)}</p>")
            ats_html += f"  <section><h2>报考信息</h2><div class='exam-details'>{''.join(details)}</div></section>\n"

        education_heading = " · ".join(value for value in (vm.edu_school, vm.edu_degree) if value)
        education_title = f'<h3 class="item-header">{education_heading}</h3>' if education_heading else ""
        education_date = f'<p class="item-date">{vm.edu_time}</p>' if vm.edu_time else ""
        ats_html += f"""
    <section>
      <h2>教育背景</h2>
      {education_title}
      {education_date}
      <div class="edu-grid">{''.join(education_rows)}</div>
    </section>
"""
        for title, entries, is_experience in (
            ("实习经历", vm.experiences, True),
            ("校园与实践经历", vm.projects, False),
        ):
            if not entries:
                continue
            ats_html += f"    <section><h2>{title}</h2>\n"
            for entry in entries:
                name = entry.get("org" if is_experience else "name", "")
                role = (entry.get("role_label") or entry.get("role", "")) if is_experience else entry.get("role", "")
                heading = " · ".join(value for value in (name, role) if value)
                date = f'<p class="item-date">{entry["time"]}</p>' if entry.get("time") else ""
                bullets = "".join(f"<li>{bullet}</li>" for bullet in entry.get("bullets", []))
                ats_html += f"      <h3 class='item-header'>{heading}</h3>{date}\n"
                if bullets:
                    ats_html += f"      <ul>{bullets}</ul>\n"
            ats_html += "    </section>\n"

        if vm.competencies:
            ats_html += "    <section><h2>专业技能</h2>\n      <ul>"
            for key, value in vm.competencies.items():
                key_html = escape_html_text(str(key))
                text = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
                ats_html += f"<li><b>{key_html}：</b>{escape_html_text(text)}</li>"
            ats_html += "</ul>\n    </section>\n"

        publications = [publication_text_parts(pub) for pub in vm.publications]
        publications = [parts for parts in publications if parts]
        if publications:
            ats_html += "    <section><h2>学术成果</h2>\n      <ul>"
            ats_html += "".join("<li>" + escape_html_text(" · ".join(parts)) + "</li>" for parts in publications)
            ats_html += "</ul>\n    </section>\n"

        ats_html += "  </main>\n</body>\n</html>"
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
