"""Theme routing contracts for the shared, real-browser visual harness."""

import copy
import re

import pytest

from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from scripts.qa_modern_navy_layout import (
    BUILDER_GENERATOR, DEFAULT_THEME, ROOT, THEMES, changed_themes, fixtures,
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
    assert len(fixtures()) == 12
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


def test_academic_exam_fixtures_cover_every_field_and_long_subjects():
    cases = [case for case in fixtures("academic-postgraduate") if case["name"].startswith("exam-")]
    assert len(cases) == 4
    assert {case["photo"] for case in cases} == {"none", "reserved"}
    assert all(case["mode"] == "builder" for case in cases)
    for case in cases:
        exam = case["profile"]["postgraduate_exam"]
        assert set(exam) == {"target_school", "target_major", "direction", "scores", "total_score"}
        assert sum(int(score) for score in exam["scores"].values()) == int(exam["total_score"])
    assert max(len(label) for case in cases for label in case["profile"]["postgraduate_exam"]["scores"]) > 70


def test_git_paths_are_matched_portably_on_windows(monkeypatch):
    from pathlib import PureWindowsPath
    monkeypatch.setattr("scripts.qa_modern_navy_layout.theme_path",
                        lambda theme: PureWindowsPath("themes") / f"{theme}.html")
    assert changed_themes(["themes/classic-tech.html"]) == ["classic-tech"]
    assert changed_themes(["themes/modern-corporate.html"]) == ["modern-corporate"]
