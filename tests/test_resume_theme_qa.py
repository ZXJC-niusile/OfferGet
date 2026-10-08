"""Theme routing contracts for the shared, real-browser visual harness."""

import copy
import re

import pytest

from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from scripts.qa_modern_navy_layout import (
    BUILDER_GENERATOR, DEFAULT_THEME, ROOT, THEMES, STRUCTURAL_LAYOUTS, changed_themes, fixtures,
    render_html, text_content, theme_path, validate_paths,
)


@pytest.mark.parametrize("theme", THEMES)
def test_explicit_theme_uses_its_actual_template_and_preserves_facts(theme):
    case = fixtures(theme)[0]
    original = copy.deepcopy(case)
    html = render_html(ROOT, case)
    template = (ROOT / theme_path(theme)).read_text(encoding="utf-8")
    assert case == original
    assert re.search(r"<title>(.*?)</title>", template).group(1) in html
    assert case["profile"]["name"] in html
    assert case["profile"]["email"] in html
    vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=False)
    bare = HtmlThemeRenderer().render(vm, theme, template_content=re.sub(
        r"<style>.*?</style>", "", template, flags=re.DOTALL))
    assert text_content(html) == text_content(bare)


def test_default_fixture_matrix_remains_compatible_with_modern_navy():
    assert all(case["theme"] == DEFAULT_THEME for case in fixtures())
    assert len(fixtures()) == 26
    assert "request.get('theme', 'modern-navy')" in BUILDER_GENERATOR


def test_changed_themes_selects_changed_files_and_shared_regression_coverage():
    assert changed_themes(["themes/classic-tech.html"]) == ["classic-tech"]
    assert changed_themes(["themes/modern-corporate.html", "themes/sidebar-clean.html"]) == [
        "modern-corporate", "sidebar-clean"]
    assert changed_themes(["themes/modern-corporate.html", "scripts/qa_modern_navy_layout.py"]) == [
        "modern-navy", "modern-corporate"]
    assert changed_themes(["core/resume_view_model.py"]) == list(THEMES)
    assert changed_themes([]) == [DEFAULT_THEME]
    assert changed_themes(["themes/not-a-theme.html"]) == [DEFAULT_THEME]


def test_theme_selection_rejects_arbitrary_paths_and_requires_matching_baseline(tmp_path):
    for theme in ("../secrets", "ats-plain", "unknown"):
        with pytest.raises(ValueError, match="Unsupported HTML theme"):
            theme_path(theme)
    baseline = tmp_path / "baseline"
    (baseline / "themes").mkdir(parents=True)
    (baseline / "core").mkdir()
    (baseline / "themes/modern-navy.html").write_text("synthetic")
    (baseline / "core/resume_view_model.py").write_text("")
    with pytest.raises(ValueError, match="isolated OfferGet source tree"):
        validate_paths(baseline, tmp_path / "output", "modern-corporate")


def test_corporate_presentation_has_plain_entries_and_keeps_wrapping_contracts():
    template = (ROOT / theme_path("modern-corporate")).read_text(encoding="utf-8")
    assert "--color-primary: #0F5156;" in template
    assert "border-left:" not in template
    assert "linear-gradient" not in template
    assert "li::before" not in template
    assert "list-style: disc;" in template
    assert "background: transparent;" in template
    assert "margin: var(--page-padding-y) 0;" in template
    assert "min-height: calc(297mm - 2 * var(--page-padding-y));" in template
    for selector in (".header-top", ".contacts", ".org-bar", ".org-left", ".project-header"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", template)
        assert "flex-wrap: wrap;" in rule.group(1), selector
    assert "text-overflow: ellipsis" not in template
    assert "overflow: hidden" not in template


@pytest.mark.parametrize("theme", ["academic-postgraduate", "sidebar-clean"])
def test_academic_exam_fixtures_cover_every_field_and_long_subjects(theme):
    cases = [case for case in fixtures(theme) if case["name"].startswith("exam-")]
    assert len(fixtures(theme)) == 30
    assert len(cases) == 6
    assert {case["photo"] for case in cases} == {"none", "reserved", "embedded"}
    assert all(case["mode"] == "builder" for case in cases)
    for case in cases:
        exam = case["profile"]["postgraduate_exam"]
        assert set(exam) == {"target_school", "target_major", "direction", "scores", "total_score"}
        assert sum(int(score) for score in exam["scores"].values()) == int(exam["total_score"])
    assert max(len(label) for case in cases for label in case["profile"]["postgraduate_exam"]["scores"]) > 70


def test_long_skills_are_checked_for_every_theme_through_raw_and_builder_paths():
    for theme in THEMES:
        cases = [case for case in fixtures(theme) if case["name"].startswith("skills-long-")]
        assert len(cases) == 6
        assert {case["mode"] for case in cases} == {"raw", "builder"}
        assert {case["photo"] for case in cases} == {"none", "reserved", "embedded"}
        assert all(max(len(label) for label in case["profile"]["skills"]) > 100 for case in cases)


def test_navy_long_skill_category_wraps_with_stylesheet_owned_fields():
    template = (ROOT / theme_path("modern-navy")).read_text(encoding="utf-8")
    rule = re.search(r"\.skill-value, \.skill-label\s*\{([^}]+)\}", template)
    assert "min-width: 0;" in rule.group(1)
    assert "overflow-wrap: anywhere;" in rule.group(1)
    case = next(case for case in fixtures() if case["name"] == "skills-long-raw-none")
    html = render_html(ROOT, case)
    assert not re.search(r'class="skill-label"[^>]*white-space:nowrap', html)


def test_git_paths_are_matched_portably_on_windows(monkeypatch):
    from pathlib import PureWindowsPath
    monkeypatch.setattr("scripts.qa_modern_navy_layout.theme_path",
                        lambda theme: PureWindowsPath("themes") / f"{theme}.html")
    assert changed_themes(["themes/classic-tech.html"]) == ["classic-tech"]
    assert changed_themes(["themes/modern-corporate.html"]) == ["modern-corporate"]


@pytest.mark.parametrize("require_autofit", [False, True])
def test_stress_builder_can_report_real_multi_page_branch_without_single_page_autofit(
        tmp_path, monkeypatch, require_autofit):
    import json
    from types import SimpleNamespace
    from scripts.qa_modern_navy_layout import render_production
    output = tmp_path / "production"

    def child(*args, **kwargs):
        output.mkdir()
        html, pdf = output / "resume.html", output / "resume.pdf"
        html.write_text("<html><body>synthetic multi-page baseline</body></html>")
        pdf.write_bytes(b"%PDF-unit-test")
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({
            "html": str(html), "pdf": str(pdf), "trace": {
                "measurements": [[4400, 3300]], "renders": [{"ok": True, "pages": 4}],
                "autofit": [],
            },
        }))

    monkeypatch.setattr("scripts.qa_modern_navy_layout.subprocess.run", child)
    case = {"mode": "builder", "require_autofit": require_autofit}
    if require_autofit:
        with pytest.raises(ValueError, match="required AutoFit"):
            render_production(ROOT, case, output)
    else:
        _, result = render_production(ROOT, case, output)
        assert result["trace"]["renders"][0]["pages"] == 4
        assert result["trace"]["autofit"] == []


def test_sidebar_exam_coverage_does_not_expand_unrelated_themes():
    for theme in THEMES:
        cases = fixtures(theme)
        has_exam = theme in {"academic-postgraduate", "sidebar-clean"}
        assert len(cases) == (30 if has_exam else 26 if theme in STRUCTURAL_LAYOUTS else 24)
        assert any(case["name"].startswith("exam-") for case in cases) == has_exam

