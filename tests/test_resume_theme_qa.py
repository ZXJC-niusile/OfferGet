"""Theme routing contracts for the shared, real-browser visual harness."""

import base64
import copy
import re

import pytest

from core.autofit import TUNING_LADDER, AutoFitEngine
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import (
    BUILDER_GENERATOR,
    DEFAULT_THEME,
    ROOT,
    STRUCTURAL_LAYOUTS,
    THEMES,
    changed_themes,
    fixtures,
    render_html,
    text_content,
    theme_path,
    validate_paths,
)

# This test renders templates directly; mode=builder/solver/compact does not
# execute those pipelines here. Their full fixture matrix belongs to browser QA.
SOURCE_CASES = [(theme, case) for theme in THEMES for case in fixtures(theme)
                if case["name"] == "professional-none"]
# Every template's photo/no-photo facts are compared in test_resume_photo_contract.
# Reserved slots exercise the semantic header and both legacy header variants.
SOURCE_CASES += [(theme, next(case for case in fixtures(theme) if case["name"] == "professional-reserved"))
                 for theme in ("modern-navy", "sidebar-clean", "engineering-sb2nov")]
# Distinct shared-model branches not exercised by professional profiles: a
# single string skill value and exam markup in a stylesheet-owned theme.
SOURCE_CASES += [
    ("modern-navy", next(case for case in fixtures() if case["name"] == "skills-long-raw-none")),
    ("modern-navy", next(case for case in fixtures("sidebar-clean") if case["name"] == "exam-long-none")),
]


@pytest.mark.parametrize("theme,case", SOURCE_CASES,
                         ids=[f"{theme}-{case['name']}" for theme, case in SOURCE_CASES])
def test_theme_source_preserves_facts_styles_and_photo_modes(theme, case, tmp_path):
    original = copy.deepcopy(case)
    template = (ROOT / theme_path(theme)).read_text(encoding="utf-8")
    mode = {"none": "no-photo", "reserved": "placeholder", "embedded": "photo"}[case["photo"]]
    photo_path = tmp_path / "portrait.png" if mode == "photo" else None
    if photo_path:
        photo_path.write_bytes(base64.b64decode(case["photo_data_uri"].split(",", 1)[1]))
    vm = ResumeViewModel.from_profile(case["profile"], photo_mode=mode, photo_path=photo_path)
    renderer = HtmlThemeRenderer()
    html = renderer.render(vm, theme, template_content=template)
    bare = renderer.render(vm, theme, template_content=re.sub(
        r"<style>.*?</style>", "", template, flags=re.DOTALL))
    assert case == original
    assert re.search(r"<title>(.*?)</title>", template).group(1) in html
    assert text_content(html) == text_content(bare)
    assert case["profile"]["name"] in html
    assert case["profile"]["email"] in html
    assert "{{" not in html
    assert validate_output_security(html, format_type="html") == []
    marker = 'class="photo-placeholder"' if theme == "engineering-sb2nov" else "photo-placeholder"
    assert (marker in html) == (case["photo"] != "none")
    assert ('<img src="data:image/png;base64,' in html) == (case["photo"] == "embedded")
    if theme == "asu-dense":
        assert '<body class="resume-dense">' in html


@pytest.mark.parametrize("theme", THEMES)
def test_theme_autofit_tokens_and_repeatable_print_gutters(theme):
    # Intermediate tuning steps and the search ladder are covered by test_autofit.
    profile = TUNING_LADDER[-1]
    template = (ROOT / theme_path(theme)).read_text(encoding="utf-8")
    tuned = AutoFitEngine(renderer=object()).apply_profile_to_html(template, profile)
    expected = {
        "--body-line-height": str(profile.line_height),
        "--page-padding-y": f"{profile.padding_y_mm}mm",
        "--page-padding-x": f"{profile.padding_x_mm}mm",
        "--body-font-size": f"{profile.font_size_px}px",
        "--item-gap": f"{profile.item_gap_px}px",
        "--section-gap": f"{profile.section_gap_px}px",
    }
    for name, value in expected.items():
        assert re.findall(re.escape(name) + r":\s*([^;]+);", tuned) == [value]
    assert "margin: var(--page-padding-y) 0;" in tuned
    assert "min-height: calc(297mm - 2 * var(--page-padding-y));" in tuned
    if theme in {"classic-tech", "silicon-clean"}:
        assert "break-after: avoid;" in tuned


def test_default_fixture_matrix_remains_compatible_with_modern_navy():
    assert all(case["theme"] == DEFAULT_THEME for case in fixtures())
    assert len(fixtures()) == 26
    assert "request.get('theme', 'modern-navy')" in BUILDER_GENERATOR


def test_changed_themes_selects_changed_files_and_shared_regression_coverage():
    assert changed_themes(["themes/classic-tech.html"]) == ["classic-tech"]
    assert changed_themes(["themes/modern-corporate.html", "themes/sidebar-clean.html"]) == [
        "sidebar-clean", "modern-corporate"]
    assert changed_themes(["themes/modern-corporate.html", "scripts/qa_modern_navy_layout.py"]) == [
        "modern-navy", "modern-corporate"]
    workflow = (ROOT / ".github/workflows/resume-visual.yml").read_text(encoding="utf-8")
    for source in ("core/resume_view_model.py", "core/profile_adapter.py", "core/resume_photo.py",
                   "core/security_gate.py", "core/atomic_writer.py", "core/artifacts.py", "pyproject.toml"):
        assert changed_themes([source]) == list(THEMES)
        assert workflow.count("      - '" + source + "'") == 2  # Both push and PR triggers.
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

