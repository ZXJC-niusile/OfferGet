"""Engineering theme contracts; actual browser layout remains a separate CI gate."""

import copy
import re
from pathlib import Path

import pytest

from core.autofit import AutoFitEngine, TUNING_LADDER
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import fixtures, text_content

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/engineering-sb2nov.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", fixtures("engineering-sb2nov"), ids=lambda case: case["name"])
def test_engineering_markup_preserves_every_fixture_and_photo_state(case):
    original = copy.deepcopy(case)
    vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=case["photo"] == "reserved")
    if case["photo"] == "embedded":
        vm.photo_data_uri = case["photo_data_uri"]
    renderer = HtmlThemeRenderer()
    actual = renderer.render(vm, "engineering-sb2nov", template_content=TEMPLATE)
    unstyled = renderer.render(vm, "engineering-sb2nov", template_content=re.sub(
        r"<style>.*?</style>", "", TEMPLATE, flags=re.DOTALL))
    assert case == original
    assert text_content(actual) == text_content(unstyled)
    assert case["profile"]["name"] in actual
    assert case["profile"]["email"] in actual
    assert "{{" not in actual
    assert ('class="photo-placeholder"' in actual) == (case["photo"] != "none")
    assert ('<img src="data:image/png;base64,' in actual) == (case["photo"] == "embedded")
    assert validate_output_security(actual, format_type="html") == []


@pytest.mark.parametrize("profile", TUNING_LADDER, ids=lambda p: p.name)
def test_engineering_autofit_tokens_and_continuation_gutters(profile):
    actual = AutoFitEngine(renderer=object()).apply_profile_to_html(TEMPLATE, profile)
    expected = {"--body-line-height": str(profile.line_height),
                "--page-padding-y": f"{profile.padding_y_mm}mm",
                "--page-padding-x": f"{profile.padding_x_mm}mm",
                "--body-font-size": f"{profile.font_size_px}px",
                "--item-gap": f"{profile.item_gap_px}px",
                "--section-gap": f"{profile.section_gap_px}px"}
    for name, value in expected.items():
        assert re.findall(re.escape(name) + r":\s*([^;]+);", actual) == [value]
    assert "margin: var(--page-padding-y) 0;" in actual
    assert "min-height: calc(297mm - 2 * var(--page-padding-y));" in actual


def test_generated_header_is_centered_and_roles_do_not_use_fallback_cyan():
    header = re.search(r"\.header-top\s*\{([^}]+)\}", TEMPLATE).group(1)
    assert "flex-direction: column;" in header
    assert "align-items: center !important;" in header
    assert "--color-accent: #333333;" in TEMPLATE
    assert "--color-primary-dark: #111111;" in TEMPLATE
    assert "font-family: var(--font-serif);" in TEMPLATE
    assert "Noto Serif CJK SC" in TEMPLATE
    assert "font-style: italic;" in TEMPLATE


def test_engineering_long_content_wraps_without_clipping_or_remote_assets():
    for selector in (".header-top > *", ".contacts span", ".contacts a", ".edu-grid > div",
                     "#skills li > span", ".exam-target-bar > span"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", TEMPLATE)
        assert rule and "min-width: 0;" in rule.group(1), selector
        assert "overflow-wrap: anywhere;" in rule.group(1), selector
    assert "white-space: normal !important;" in TEMPLATE
    assert "flex-shrink: 1 !important;" in TEMPLATE
    assert "li::marker" in TEMPLATE
    assert "li::before" not in TEMPLATE
    for forbidden in ("text-overflow:", "overflow: hidden", "@import", "url("):
        assert forbidden not in TEMPLATE


def test_optional_exam_content_is_retained_in_monochrome_theme():
    profile = copy.deepcopy(fixtures("engineering-sb2nov")[0]["profile"])
    profile["postgraduate_exam"] = {
        "target_school": "示例大学 / Example University",
        "direction": "可靠系统 / Reliable Systems",
        "scores": {"数学 / Mathematics": "125", "专业课 / Engineering": "120"},
        "total_score": "245",
    }
    actual = HtmlThemeRenderer().render(ResumeViewModel.from_profile(profile),
                                       "engineering-sb2nov", template_content=TEMPLATE)
    assert "示例大学 / Example University" in actual
    assert "可靠系统 / Reliable Systems" in actual
    assert ">125</td>" in actual and ">120</td>" in actual and ">245</td>" in actual
    assert "background: transparent !important;" in TEMPLATE
