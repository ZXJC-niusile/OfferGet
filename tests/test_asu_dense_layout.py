"""ASu Dense source contracts; real production geometry is checked in visual CI."""

import copy
import re
from pathlib import Path

import pytest

from core.autofit import TUNING_LADDER, AutoFitEngine
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import fixtures, synthetic_photo, text_content

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/asu-dense.html").read_text(encoding="utf-8")


def rendered(case, template=TEMPLATE):
    vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=case["photo"] == "reserved")
    if case["photo"] == "embedded":
        vm.photo_data_uri = synthetic_photo()
    return HtmlThemeRenderer().render(vm, "asu-dense", template_content=template)


@pytest.mark.parametrize("case", fixtures(), ids=lambda case: case["name"])
def test_all_synthetic_facts_and_photo_modes_survive(case):
    original = copy.deepcopy(case)
    result = rendered(case)
    unstyled = re.sub(r"<style>.*?</style>", "", TEMPLATE, flags=re.DOTALL)
    assert case == original
    assert text_content(result) == text_content(rendered(case, unstyled))
    assert case["profile"]["name"] in result
    assert case["profile"]["email"] in result
    assert "{{" not in result
    assert validate_output_security(result, format_type="html") == []
    assert ("photo-placeholder" in result) == (case["photo"] != "none")
    assert ('<img src="data:image/png;base64,' in result) == (case["photo"] == "embedded")
    assert '<body class="resume-dense">' in result


@pytest.mark.parametrize("profile", TUNING_LADDER, ids=lambda profile: profile.name)
def test_all_six_autofit_tokens_remain_effective(profile):
    tuned = AutoFitEngine(renderer=object()).apply_profile_to_html(TEMPLATE, profile)
    values = {
        "--body-line-height": str(profile.line_height),
        "--page-padding-y": f"{profile.padding_y_mm}mm",
        "--page-padding-x": f"{profile.padding_x_mm}mm",
        "--body-font-size": f"{profile.font_size_px}px",
        "--item-gap": f"{profile.item_gap_px}px",
        "--section-gap": f"{profile.section_gap_px}px",
    }
    for name, value in values.items():
        assert re.findall(re.escape(name) + r":\s*([^;]+);", tuned) == [value]
    assert "margin: var(--page-padding-y) 0;" in tuned
    assert "min-height: calc(297mm - 2 * var(--page-padding-y));" in tuned


def test_generated_inline_markup_has_scoped_layout_overrides():
    # Shared rendering replaces <header> and injects inline flex/nowrap styles.
    assert ".resume-dense .header-top {\n      display: block !important;" in TEMPLATE
    assert ".resume-dense #skills li {\n      display: block !important;" in TEMPLATE
    skills_rule = re.search(r"\.resume-dense #skills li > span\s*\{([^}]+)\}", TEMPLATE)
    assert "white-space: normal !important;" in skills_rule.group(1)
    for selector in ("header > div:first-child", ".header-top > *", ".contacts a",
                     ".project-header > div:first-child", ".edu-grid > div"):
        rule = re.search(re.escape(".resume-dense " + selector) + r"\s*\{([^}]+)\}", TEMPLATE)
        assert rule, selector
        assert "min-width: 0;" in rule.group(1), selector
    assert "flex-wrap: wrap;" in TEMPLATE
    assert "font-variant-numeric: tabular-nums;" in TEMPLATE
    assert "margin: 0 !important;" in TEMPLATE  # No doubled solver heading margin.


def test_dense_theme_uses_print_safe_plain_resume_hierarchy():
    assert "list-style: disc;" in TEMPLATE
    assert "break-inside: auto !important;" in TEMPLATE  # Long entries can continue.
    assert "text-align: start;" in TEMPLATE
    for unwanted in ("linear-gradient", "box-shadow", "text-overflow: ellipsis",
                     "overflow: hidden", "@import", "url(", "content: \"▪\"",
                     "border-left:", "border-radius:"):
        assert unwanted not in TEMPLATE
