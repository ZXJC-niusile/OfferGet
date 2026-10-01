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

import copy
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from core.artifacts import write_text_atomic
from core.cli_helpers import load_json
from core.fingerprints import content_fingerprint
from core.paths import get_project_root, get_theme_dir

PROJECT_ROOT = get_project_root()

from core.profile_adapter import normalize_candidate_profile
from core.academic_exporter import AcademicExporter
from core.security_gate import validate_output_security

from core.browser_renderer import BrowserRenderer
from core.autofit import AutoFitEngine
from core.resume_auditor import ResumeAuditor


from core.resume_view_model import (
    ResumeViewModel,
    HtmlThemeRenderer,
    AtsPlainRenderer,
)


def _compute_profile_fingerprint(profile_data: Any) -> str:
    """Computes a deterministic SHA-256 fingerprint from profile data for caching."""
    payload = getattr(profile_data, "normalized_profile", profile_data)
    try:
        # This is a render-cache key, not the persistent evidence-snapshot hash.
        # Hash the supplied projection directly; rebuilding a ProfileContext here
        # would re-normalize and re-index it on every lookup, including hits.
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return content_fingerprint(serialized, length=16)
    except (TypeError, ValueError):
        return str(id(payload))


class ResumeBuilder:
    """Unified engine for building all 6 resume variants from candidate profile data."""

    HTML_THEMES = [
        "modern-navy",
        "silicon-clean",
        "classic-tech",
        "asu-dense",
        "sidebar-clean",
        "academic-postgraduate",
        "engineering-sb2nov",
        "modern-corporate",
    ]
    THEMES = HTML_THEMES + [
        "ats-plain",
        "academic-latex",
        "academic-typst",
        "ats-docx",
    ]
    PDF_THEMES = HTML_THEMES + [
        "ats-plain",
        "academic-latex",
        "academic-typst",
    ]
    DOCX_THEMES = [
        "ats-docx",
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
            if p_path.suffix.lower() == ".json":
                raw_data = load_json(p_path)
            else:
                from core.resume_parser import parse_resume_to_profile
                raw_data = parse_resume_to_profile(p_path)
        elif hasattr(profile_or_path, "raw_profile") and hasattr(profile_or_path, "normalized_profile"):
            raw_data = profile_or_path.raw_profile
        elif isinstance(profile_or_path, dict):
            raw_data = profile_or_path
        else:
            raise TypeError("profile_or_path must be a dictionary, ProfileContext, or file path")


        self.raw_profile = raw_data
        self.anonymize = anonymize
        self.photo_path = Path(photo_path).resolve() if photo_path else None
        self.deanon_map: Dict[str, str] = {}
        self._vm_cache: Dict[Tuple[str, Optional[str], bool], ResumeViewModel] = {}

        if hasattr(profile_or_path, "normalized_profile") and not anonymize:
            self.profile = copy.deepcopy(profile_or_path.normalized_profile)
        else:
            self.profile = self._resolve_profile(anonymize=self.anonymize)
        self.academic_exporter = AcademicExporter()

        self.template_dir = Path(template_dir).resolve() if template_dir else get_theme_dir()

        self.renderer = renderer or BrowserRenderer()
        self.autofit_engine = autofit_engine or AutoFitEngine(self.renderer)

        self.html_renderer = HtmlThemeRenderer()
        self.ats_renderer = AtsPlainRenderer()
        self.view_model: ResumeViewModel = self._get_view_model(
            self.profile,
            photo_path=self.photo_path,
            reserve_photo=True,
        )

    def _get_view_model(
        self,
        profile: Optional[Union[Dict[str, Any], Any]] = None,
        photo_path: Optional[Union[str, Path]] = None,
        reserve_photo: bool = True,
    ) -> ResumeViewModel:
        """Retrieves cached ResumeViewModel or constructs and caches a new one."""
        eff_photo_path = str(photo_path) if photo_path else (str(self.photo_path) if self.photo_path else None)

        # 1. If no profile passed or self.profile passed: it is ALREADY normalized by ResumeBuilder.__init__
        if profile is None or profile is self.profile:
            norm_profile = self.profile
            raw_p = getattr(self, "raw_profile", None)
        # 2. If ProfileContext passed: read Context's normalized profile directly
        elif hasattr(profile, "normalized_profile"):
            norm_profile = profile.normalized_profile
            raw_p = getattr(profile, "raw_profile", None)
        # 3. External plain dict or other profile: default to treating as raw profile, normalize via normalize_candidate_profile
        else:
            norm_profile = normalize_candidate_profile(profile)
            raw_p = profile if isinstance(profile, dict) else getattr(self, "raw_profile", None)

        profile_fp = _compute_profile_fingerprint(norm_profile)
        cache_key = (profile_fp, eff_photo_path, reserve_photo)
        if cache_key in self._vm_cache:
            return self._vm_cache[cache_key]

        vm = ResumeViewModel.from_normalized_profile(
            norm_profile,
            photo_path=eff_photo_path,
            reserve_photo=reserve_photo,
            raw_profile=raw_p,
        )
        self._vm_cache[cache_key] = vm
        return vm

    def _resolve_profile(self, anonymize: Optional[str] = None) -> Dict[str, Any]:
        """Resolves profile data, applying privacy anonymization if requested."""
        level = anonymize if anonymize is not None else self.anonymize
        if hasattr(self, "profile") and not level:
            return self.profile
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
        vm = self._get_view_model(profile=profile, photo_path=self.photo_path, reserve_photo=True)
        return self.html_renderer.render_sections(vm, theme_name=theme_name)

    def _render_header_html(
        self,
        theme_name: str,
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Builds header markup with optional photo placeholder."""
        vm = self._get_view_model(profile=profile, photo_path=photo_path, reserve_photo=photo)
        return self.html_renderer.render_header(vm, theme_name=theme_name)

    def build_html_theme(
        self,
        theme_name: str,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
        layout_config: Optional[Any] = None,
        adaptive_fill: bool = True,
        diff_ledger: bool = True,
        baseline_profile: Optional[Union[Dict[str, Any], Any]] = None,
        pages: str = "auto",
        **kwargs: Any,
    ) -> Dict[str, Path]:
        """Builds HTML + CSS based resume theme, optionally applying single-page AutoFit."""
        prof = self._resolve_profile(anonymize)
        eff_photo_path = photo_path or self.photo_path

        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        vm = self._get_view_model(profile=prof, photo_path=eff_photo_path, reserve_photo=photo)
        populated_html = self.html_renderer.render(
            vm=vm,
            theme_name=theme_name,
            template_dir=self.template_dir,
        )

        from core.layout_solver import LayoutConfig, solve_layout
        from core.diff_ledger import DiffLedger

        cfg = layout_config or LayoutConfig(page_mode=pages)
        if layout_config is not None and pages != "auto":
            cfg.page_mode = pages
        overflow_px = float(kwargs.get("overflow_px", 0.0))

        # Detect overflow / underflow via renderer if available and overflow_px not explicitly supplied
        if "overflow_px" not in kwargs and self.renderer:
            try:
                with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp_measure:
                    tmp_measure.write(populated_html)
                    tmp_measure_path = Path(tmp_measure.name)
                try:
                    measured_h, oflow = self.renderer.measure_overflow(tmp_measure_path, a4_target_height=cfg.a4_height_px)
                    if oflow != 0:
                        overflow_px = float(oflow)
                    elif measured_h < cfg.a4_height_px - 20:
                        overflow_px = float(measured_h - cfg.a4_height_px)
                finally:
                    tmp_measure_path.unlink(missing_ok=True)
            except Exception:
                overflow_px = 0.0

        if not adaptive_fill and overflow_px < 0:
            overflow_px = 0.0

        solve_res = solve_layout(populated_html, overflow_px=overflow_px, config=cfg)
        populated_html = solve_res.html

        clean_theme_name = theme_name.replace("-", "_")
        html_path = out_dir / f"resume_{clean_theme_name}.html"
        pdf_path = out_dir / f"resume_{clean_theme_name}.pdf"

        # If layout budget is solved for multi-page (> 1), skip single-page squashing
        is_multi_page = (solve_res.target_pages_solved > 1) or (pages == "2")

        if autofit and not is_multi_page:
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
                    write_text_atomic(populated_html, html_path)
                    self.renderer.render_pdf(html_path, pdf_path)
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass
        else:
            write_text_atomic(populated_html, html_path)
            self.renderer.render_pdf(html_path, pdf_path)

        result_paths: Dict[str, Path] = {"html": html_path, "pdf": pdf_path}

        if diff_ledger:
            effective_baseline = baseline_profile or self.raw_profile or prof
            cand_name = (
                prof.get("candidate", {}).get("name")
                or prof.get("name")
                or ""
            )
            layout_meta = {
                "solved": solve_res.solved,
                "target_pages": solve_res.target_pages_solved,
                "body_font_pt": solve_res.body_font_pt,
                "line_height": solve_res.line_height,
                "section_margin_pt": solve_res.section_margin_pt,
                "item_gap_pt": solve_res.item_gap_pt,
                "page_padding_y_mm": solve_res.page_padding_y_mm,
                "orphans_mitigated": solve_res.orphans_mitigated,
                "abbreviations_prevented": solve_res.abbreviations_prevented,
                "applied_compressions": solve_res.applied_compressions,
                "is_expanded_to_fill": solve_res.is_expanded_to_fill,
            }
            fact_guard_res = None
            try:
                from core.fact_guard import FactVerificationGuard
                guard = FactVerificationGuard(effective_baseline)
                fact_guard_res = guard.verify_facts(prof)
            except Exception:
                pass

            ledger = DiffLedger.from_fact_guard_result(
                guard_result=fact_guard_res,
                baseline_profile=effective_baseline,
                tailored_data=prof,
                candidate_name=cand_name,
                layout_metadata=layout_meta,
            )
            saved = ledger.save(out_dir, base_name="resume")
            result_paths["diff_ledger_md"] = saved["markdown"]
            result_paths["diff_ledger_json"] = saved["json"]

        return result_paths

    def solve_resume_layout(
        self,
        html_content: str,
        overflow_px: float = 0.0,
        config: Optional[Any] = None,
    ) -> Any:
        """DOM/AST adaptive layout solver and micro-typography integration."""
        from core.layout_solver import solve_layout
        return solve_layout(html_content, overflow_px=overflow_px, config=config)

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
        vm = self._get_view_model(profile=prof, photo_path=eff_photo_path, reserve_photo=photo)

        md_content = self.ats_renderer.render_markdown(vm)
        html_content = self.ats_renderer.render_html(vm)

        md_path = out_dir / "resume_ats_plain.md"
        write_text_atomic(md_content, md_path)

        html_path = out_dir / "resume_ats_plain.html"
        write_text_atomic(html_content, html_path)

        pdf_path = out_dir / "resume_ats_plain.pdf"
        self.renderer.render_pdf(html_path, pdf_path)

        return {"md": md_path, "html": html_path, "pdf": pdf_path}

    def build_academic_latex(
        self,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        anonymize: Optional[str] = None,
        photo_size: Optional[int] = None,
        photo_width: Optional[int] = None,
        photo_height: Optional[int] = None,
        lang: str = "zh",
        section_titles: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Path]:
        """Builds academic LaTeX resume, standalone HTML twin, and PDF."""
        prof = self._resolve_profile(anonymize)
        eff_photo_path = photo_path or self.photo_path
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        vm = self._get_view_model(profile=prof, photo_path=eff_photo_path, reserve_photo=photo)

        tex_src = self.academic_exporter.generate_latex(
            vm,
            reserve_photo=photo,
            photo_path=eff_photo_path,
            lang=lang,
            section_titles=section_titles,
        )
        tex_path = out_dir / "resume_academic_latex.tex"
        write_text_atomic(tex_src, tex_path)

        html_src = self.academic_exporter.generate_latex_html_preview(
            vm,
            reserve_photo=photo,
            photo_path=eff_photo_path,
            photo_size=photo_size,
            photo_width=photo_width,
            photo_height=photo_height,
            lang=lang,
            section_titles=section_titles,
        )
        html_path = out_dir / "resume_academic_latex.html"
        write_text_atomic(html_src, html_path)

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

        typ_photo = eff_photo_path
        if eff_photo_path and Path(eff_photo_path).is_file():
            import shutil
            try:
                dest_photo = out_dir / Path(eff_photo_path).name
                if dest_photo.resolve() != Path(eff_photo_path).resolve():
                    shutil.copy2(eff_photo_path, dest_photo)
                typ_photo = dest_photo.name
            except Exception:
                typ_photo = eff_photo_path

        vm = self._get_view_model(profile=prof, photo_path=eff_photo_path, reserve_photo=photo)
        typ_src = self.academic_exporter.generate_typst(vm, reserve_photo=photo, photo_path=typ_photo)
        typ_path = out_dir / "resume_academic_typst.typ"
        write_text_atomic(typ_src, typ_path)

        pdf_path = out_dir / "resume_academic_typst.pdf"
        compiled = self.academic_exporter.compile_typst(typ_path, pdf_path)
        if not compiled or not pdf_path.exists():
            html_src = self.academic_exporter.generate_latex_html_preview(
                vm,
                reserve_photo=photo,
                photo_path=eff_photo_path,
                lang="zh",
            )
            html_path = out_dir / "resume_academic_typst.html"
            write_text_atomic(html_src, html_path)
            self.renderer.render_pdf(html_path, pdf_path)

        return {"typ": typ_path, "pdf": pdf_path}

    def build_theme(
        self,
        theme: str,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
        adaptive_fill: bool = True,
        diff_ledger: bool = True,
        baseline_profile: Optional[Union[Dict[str, Any], Any]] = None,
        pages: str = "auto",
        **kwargs,
    ) -> Dict[str, Path]:
        """Builds a specific theme by name."""
        theme_normalized = theme.lower().replace("_", "-")
        eff_photo_path = photo_path or self.photo_path
        if theme_normalized in self.HTML_THEMES:
            return self.build_html_theme(
                theme_normalized,
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                autofit=autofit,
                anonymize=anonymize,
                adaptive_fill=adaptive_fill,
                diff_ledger=diff_ledger,
                baseline_profile=baseline_profile,
                pages=pages,
                **kwargs,
            )
        elif theme_normalized == "ats-plain":
            res = self.build_ats_plain(
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                anonymize=anonymize,
            )
        elif theme_normalized in ("academic-latex", "latex"):
            res = self.build_academic_latex(
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                anonymize=anonymize,
                **kwargs,
            )
        elif theme_normalized in ("academic-typst", "typst"):
            res = self.build_academic_typst(
                output_dir,
                photo=photo,
                photo_path=eff_photo_path,
                anonymize=anonymize,
            )
        elif theme_normalized in ("ats-docx", "docx"):
            res = self.build_ats_docx(
                output_dir,
                anonymize=anonymize,
            )
        else:
            raise ValueError(f"Unknown resume theme '{theme}'. Choices: {self.THEMES}")

        if diff_ledger and "diff_ledger_md" not in res:
            out_dir = Path(output_dir).resolve()
            effective_baseline = baseline_profile or self.raw_profile or self.profile
            cand_name = (
                self.profile.get("candidate", {}).get("name")
                or self.profile.get("name")
                or ""
            )
            fact_guard_res = None
            try:
                from core.fact_guard import FactVerificationGuard
                guard = FactVerificationGuard(effective_baseline)
                fact_guard_res = guard.verify_facts(self.profile)
            except Exception:
                pass
            from core.diff_ledger import DiffLedger
            ledger = DiffLedger.from_fact_guard_result(
                guard_result=fact_guard_res,
                baseline_profile=effective_baseline,
                tailored_data=self.profile,
                candidate_name=cand_name,
            )
            saved = ledger.save(out_dir, base_name="resume")
            res["diff_ledger_md"] = saved["markdown"]
            res["diff_ledger_json"] = saved["json"]

        return res

    def build_ats_docx(
        self,
        output_dir: Union[str, Path],
        anonymize: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Builds ATS-friendly single-column Word (.docx) resume."""
        from core.ats_docx_renderer import AtsDocxRenderer
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        prof = self._resolve_profile(anonymize)
        vm = self._get_view_model(profile=prof)
        docx_path = out_dir / "resume_ats.docx"
        AtsDocxRenderer().render(vm, docx_path)
        return {"docx": docx_path}

    def build_all(
        self,
        output_dir: Union[str, Path],
        photo: bool = True,
        photo_path: Optional[Union[str, Path]] = None,
        autofit: bool = True,
        anonymize: Optional[str] = None,
        include_docx: bool = False,
        adaptive_fill: bool = True,
        diff_ledger: bool = True,
        baseline_profile: Optional[Union[Dict[str, Any], Any]] = None,
        pages: str = "auto",
        **kwargs,
    ) -> Dict[str, Dict[str, Path]]:
        """Builds all 6 standard resume variants (or all 7 if include_docx=True)."""
        themes = self.THEMES if include_docx else self.PDF_THEMES
        results = {}
        for t in themes:
            results[t] = self.build_theme(
                t,
                output_dir,
                photo=photo,
                photo_path=photo_path,
                autofit=autofit,
                anonymize=anonymize,
                adaptive_fill=adaptive_fill,
                diff_ledger=diff_ledger,
                baseline_profile=baseline_profile,
                pages=pages,
                **kwargs,
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

    # 3. Check for dangerous tags (Security / XSS gate via validate_output_security)
    sec_violations = validate_output_security(content, format_type="html")
    dangerous_violations = []
    for viol in sec_violations:
        if "placeholder" in viol.lower():
            continue
        dangerous_violations.append(viol)
        extra_findings.append({
            "category": "security",
            "severity": "critical",
            "message": f"Dangerous security violation: {viol}",
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
