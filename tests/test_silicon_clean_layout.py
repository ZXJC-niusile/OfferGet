"""Silicon Clean contracts; CI separately checks actual browser/PDF geometry."""

import copy
import re
from pathlib import Path

import pytest

from core.autofit import TUNING_LADDER, AutoFitEngine
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import fixtures, text_content

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/silicon-clean.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", fixtures("silicon-clean"), ids=lambda case: case["name"])
def test_synthetic_profiles_keep_all_facts_and_photo_choices(case):
    original = copy.deepcopy(case)
    vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=case["photo"] == "reserved")
    if case["photo"] == "embedded":
        vm.photo_data_uri = case["photo_data_uri"]
    renderer = HtmlThemeRenderer()
    html = renderer.render(vm, "silicon-clean", template_content=TEMPLATE)
    bare = renderer.render(vm, "silicon-clean", template_content=re.sub(
        r"<style>.*?</style>", "", TEMPLATE, flags=re.DOTALL))
    assert case == original
    assert text_content(html) == text_content(bare)
    assert case["profile"]["name"] in html
    assert case["profile"]["email"] in html
    assert "{{" not in html
    assert validate_output_security(html, format_type="html") == []
    assert ("photo-placeholder" in html) == (case["photo"] != "none")
    assert ('<img src="data:image/png;base64,' in html) == (case["photo"] == "embedded")


@pytest.mark.parametrize("profile", TUNING_LADDER, ids=lambda profile: profile.name)
def test_all_autofit_tokens_and_print_gutters_remain_compatible(profile):
    html = AutoFitEngine(renderer=object()).apply_profile_to_html(TEMPLATE, profile)
    expected = {
        "--body-line-height": str(profile.line_height),
        "--page-padding-y": f"{profile.padding_y_mm}mm",
        "--page-padding-x": f"{profile.padding_x_mm}mm",
        "--body-font-size": f"{profile.font_size_px}px",
        "--item-gap": f"{profile.item_gap_px}px",
        "--section-gap": f"{profile.section_gap_px}px",
    }
    for name, value in expected.items():
        assert re.findall(re.escape(name) + r":\s*([^;]+);", html) == [value]
    assert "margin: var(--page-padding-y) 0;" in html
    assert "min-height: calc(297mm - 2 * var(--page-padding-y));" in html
    assert "break-after: avoid;" in html


def rule(selector):
    match = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]+)\}", TEMPLATE)
    assert match, selector
    return match.group(1)


def test_centered_neutral_header_and_stacked_roles_are_distinct():
    assert "--color-primary: #202020;" in TEMPLATE
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);" in rule(".resume-columns")
    assert "align-items: start;" in rule(".resume-columns")
    assert ".entry-header { display: block; }" in TEMPLATE
    assert "font-size: 30px;" in rule(".resume-name") or "font-size: 30px;" in TEMPLATE
    assert TEMPLATE.count("!important") == 4  # Only scoped shared-solver compatibility rules


def test_generated_markup_has_wrap_safe_contacts_dates_and_skills():
    for selector in (".resume-identity", ".header-top > *", ".entry-identity", ".entry-date", ".edu-grid > div", ".resume-column"):
        assert "min-width: 0;" in rule(selector), selector
    assert "flex-wrap: wrap;" in rule(".resume-contacts")
    assert "overflow-wrap: anywhere;" in rule(".entry-date")
    assert "white-space: nowrap" not in TEMPLATE
    assert "column-gap: 24px;" in rule(".resume-columns")


def test_readable_default_type_and_plain_hanging_bullets():
    assert "--body-font-size: 13.333px;" in TEMPLATE
    assert "--page-padding-x: 14mm;" in TEMPLATE
    assert "font-size: 1.05em;" in rule("h2")
    assert "list-style: disc;" in rule("ul")
    assert "text-align: start;" in rule("li")
    for forbidden in ("li::before", "border-left:", "text-align: justify", "text-overflow: ellipsis", "overflow: hidden", "@import", "url(", "grid-auto-flow", "grid-row"):
        assert forbidden not in TEMPLATE
