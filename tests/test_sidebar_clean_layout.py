"""Sidebar source contracts; production PDF geometry and order require visual CI."""

import copy
import re
from pathlib import Path

import pytest

from core.autofit import TUNING_LADDER, AutoFitEngine
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import fixtures, synthetic_photo, text_content

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/sidebar-clean.html").read_text(encoding="utf-8")


def rendered(case, template=TEMPLATE):
    vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=case["photo"] == "reserved")
    if case["photo"] == "embedded":
        vm.photo_data_uri = synthetic_photo()
    return HtmlThemeRenderer().render(vm, "sidebar-clean", template_content=template)


@pytest.mark.parametrize("case", fixtures("sidebar-clean"), ids=lambda case: case["name"])
def test_synthetic_facts_photo_modes_and_dom_order_are_preserved(case):
    original = copy.deepcopy(case)
    html = rendered(case)
    bare = re.sub(r"<style>.*?</style>", "", TEMPLATE, flags=re.DOTALL)
    assert case == original
    assert text_content(html) == text_content(rendered(case, bare))
    expected_sections = ["education", "experience", "projects", "skills"]
    if case["profile"].get("postgraduate_exam"):
        expected_sections.insert(0, "postgraduate-exam")
    assert re.findall(r'<section id="([^"]+)"', html) == expected_sections
    assert case["profile"]["name"] in html
    assert case["profile"]["email"] in html
    assert "{{" not in html
    assert validate_output_security(html, format_type="html") == []
    assert ("photo-placeholder" in html) == (case["photo"] != "none")
    assert ('<img src="data:image/png;base64,' in html) == (case["photo"] == "embedded")
    assert '<body class="resume-sidebar">' in html


@pytest.mark.parametrize("profile", TUNING_LADDER, ids=lambda profile: profile.name)
def test_all_six_autofit_tokens_remain_effective(profile):
    tuned = AutoFitEngine(renderer=object()).apply_profile_to_html(TEMPLATE, profile)
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


def test_sidebar_is_a_genuine_two_column_flow_without_fixed_content_heights():
    assert "grid-template-columns: minmax(0, 28%) minmax(0, 1fr);" in TEMPLATE
    assert "grid-template-rows: auto auto min-content auto auto;" in TEMPLATE
    assert "align-content: start;" in TEMPLATE
    for section in ("education", "skills"):
        rule = re.search(r"\.resume-sidebar #" + section + r"\s*\{([^}]+)\}", TEMPLATE)
        assert "grid-column: 1;" in rule.group(1)
    for section in ("experience", "projects"):
        rule = re.search(r"\.resume-sidebar #" + section + r"\s*\{([^}]+)\}", TEMPLATE)
        assert "grid-column: 2;" in rule.group(1)
    assert ".page:not(:has(#experience)) #projects" in TEMPLATE
    assert "grid-auto-flow: dense" not in TEMPLATE
    assert "position: absolute" not in TEMPLATE
    assert not re.search(r"(?:^|[;{])\s*order\s*:", TEMPLATE)


def test_generated_inline_markup_is_overridden_within_this_theme():
    assert ".resume-sidebar .header-top {\n      display: block !important;" in TEMPLATE
    assert ".resume-sidebar #skills li {\n      display: block !important;" in TEMPLATE
    assert ".resume-sidebar #education .org-bar {\n      display: block !important;" in TEMPLATE
    rule = re.search(r"\.resume-sidebar #skills li > span\s*\{([^}]+)\}", TEMPLATE)
    assert "display: block;" in rule.group(1)
    assert "white-space: normal !important;" in rule.group(1)
    assert "overflow-wrap: anywhere;" in rule.group(1)
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, max-content);" in TEMPLATE
    assert "font-variant-numeric: tabular-nums;" in TEMPLATE
    assert "list-style: disc;" in TEMPLATE
    for unwanted in ("linear-gradient", "box-shadow", "text-overflow: ellipsis",
                     "overflow: hidden", "@import", "url(", "content: \"▸\"",
                     "border-radius:", "--color-sidebar-bg"):
        assert unwanted not in TEMPLATE


@pytest.mark.parametrize("omitted", ["experience", "campus_experience", "skills"])
def test_optional_sections_do_not_introduce_placeholders_or_duplicate_facts(omitted):
    case = copy.deepcopy(fixtures("sidebar-clean")[0])
    case["profile"].pop(omitted)
    html = rendered(case)
    assert "{{" not in html
    assert html.count(case["profile"]["name"]) == 1
    expected_id = "projects" if omitted == "campus_experience" else omitted
    assert f'<section id="{expected_id}">' not in html


@pytest.mark.parametrize("long", [False, True])
def test_optional_exam_keeps_facts_and_uses_a_full_width_row(long):
    cases = [case for case in fixtures("academic-postgraduate") if case["name"].startswith(
        "exam-long-" if long else "exam-normal-")]
    for case in cases:
        html = rendered(case)
        exam = case["profile"]["postgraduate_exam"]
        assert re.findall(r'<section id="([^"]+)"', html)[0] == "postgraduate-exam"
        assert exam["target_school"] in html
        assert exam["direction"] in html
        for subject, score in exam["scores"].items():
            assert subject in html
            assert f">{score}</td>" in html
    rule = re.search(r"\.resume-sidebar #postgraduate-exam\s*\{([^}]+)\}", TEMPLATE)
    assert "grid-column: 1 / -1;" in rule.group(1)
    assert "grid-row: 2;" in rule.group(1)
    assert "table-layout: fixed;" in TEMPLATE
