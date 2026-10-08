"""Classic Tech contracts; real Chromium/production-builder geometry is checked in CI."""

import copy
import re
from pathlib import Path

import pytest

from core.autofit import AutoFitEngine, TUNING_LADDER
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import fixtures, text_content

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/classic-tech.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", fixtures(), ids=lambda case: case["name"])
def test_all_synthetic_profiles_preserve_factual_text(case):
    original = copy.deepcopy(case)
    vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=case["photo"] == "reserved")
    if case["photo"] == "embedded":
        vm.photo_data_uri = case["photo_data_uri"]
    renderer = HtmlThemeRenderer()
    rendered = renderer.render(vm, "classic-tech", template_content=TEMPLATE)
    unstyled = renderer.render(vm, "classic-tech", template_content=re.sub(
        r"<style>.*?</style>", "", TEMPLATE, flags=re.DOTALL))
    assert case == original
    assert text_content(rendered) == text_content(unstyled)
    assert "{{" not in rendered
    assert case["profile"]["name"] in rendered
    assert case["profile"]["email"] in rendered
    assert validate_output_security(rendered, format_type="html") == []
    assert ("photo-placeholder" in rendered) == (case["photo"] != "none")
    assert ('<img src="data:image/png;base64,' in rendered) == (case["photo"] == "embedded")


@pytest.mark.parametrize("profile", TUNING_LADDER, ids=lambda profile: profile.name)
def test_autofit_tokens_and_repeatable_print_gutters(profile):
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
    assert "break-after: avoid;" in tuned


def test_generated_markup_receives_wrapping_and_unboxed_hierarchy():
    for selector in ("header > div:first-child", ".header-top > *", ".contacts span", ".contacts a",
                     ".org-left, .project-header > div:first-child", ".edu-grid > div",
                     "#skills li > span"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", TEMPLATE)
        assert rule, selector
        assert "min-width: 0;" in rule.group(1), selector
    for selector in (".header-top", ".contacts", ".org-bar, .project-header",
                     ".org-left, .project-header > div:first-child", "#skills li"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", TEMPLATE)
        assert "flex-wrap: wrap;" in rule.group(1), selector
    assert "background: transparent;" in TEMPLATE
    assert "text-align: justify" not in TEMPLATE
    assert "border-left:" not in TEMPLATE
    assert "text-overflow: ellipsis" not in TEMPLATE
    assert "overflow: hidden" not in TEMPLATE
    assert "@import" not in TEMPLATE
    assert "url(" not in TEMPLATE


def test_renderer_inline_styles_cannot_restore_colored_role_or_skill_chips():
    role = re.search(r"\.org-role, \.project-header > div:first-child > span \+ span\s*\{([^}]+)\}", TEMPLATE)
    assert "color: var(--color-text) !important;" in role.group(1)
    assert "font-weight: 400 !important;" in role.group(1)
    assert "white-space: normal !important;" in TEMPLATE
    assert "#skills li::before { content: none; }" in TEMPLATE
    assert "font-size: 25px !important;" in TEMPLATE


def test_heading_hierarchy_scales_with_production_body_type():
    assert "font-size: 1.08em;" in TEMPLATE
    assert "font-size: 1em !important;" in TEMPLATE
