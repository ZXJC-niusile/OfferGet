"""Classic Tech contracts; real Chromium/production-builder geometry is checked in CI."""

import copy
import re
from pathlib import Path

import pytest

from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from scripts.qa_modern_navy_layout import fixtures, text_content

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/classic-tech.html").read_text(encoding="utf-8")


def test_generated_markup_receives_wrapping_and_unboxed_hierarchy():
    for selector in (".resume-identity", ".header-top > *", ".entry-identity", ".entry-date", ".edu-grid > div"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", TEMPLATE)
        assert rule and "min-width: 0;" in rule.group(1), selector
    assert "grid-template-columns: minmax(0, 17fr) minmax(0, 83fr);" in TEMPLATE
    assert ".resume-entry > .entry-date" in TEMPLATE
    for forbidden in ("text-align: justify", "border-left:", "text-overflow: ellipsis", "overflow: hidden", "@import", "url("):
        assert forbidden not in TEMPLATE


def test_renderer_inline_styles_cannot_restore_colored_role_or_skill_chips():
    html = HtmlThemeRenderer().render(ResumeViewModel.from_profile(fixtures()[0]["profile"], reserve_photo=False), "classic-tech")
    assert not re.search(r'class="(?:org-role entry-role|skill-row|skill-label)"[^>]*style=', html)
    assert TEMPLATE.count("!important") == 4  # Only scoped shared-solver compatibility rules
    assert "font-size: 28px;" in TEMPLATE
    assert "font-family: Georgia" in TEMPLATE


def test_heading_hierarchy_scales_with_production_body_type():
    assert "font-size: 1.05em;" in TEMPLATE
    assert "font-size: 1em;" in TEMPLATE


@pytest.mark.parametrize("label", [
    "ReliabilityAndInfrastructureEngineering" * 7,
    "跨区域分布式基础设施可靠性与研发协作能力" * 9,
])
def test_unbroken_skill_labels_and_long_dates_preserve_all_text(label):
    profile = copy.deepcopy(fixtures()[0]["profile"])
    profile["skills"] = {label: "Synthetic Python, SQL, Linux capability list"}
    long_date = "2020.07 – present / " + "SyntheticDateQualifier" * 5
    profile["experience"][0]["time"] = long_date
    rendered = HtmlThemeRenderer().render(ResumeViewModel.from_profile(profile), "classic-tech")
    assert label in text_content(rendered)
    assert long_date in text_content(rendered)
    date_rule = re.search(r"\.entry-date\s*\{([^}]+)\}", TEMPLATE)
    assert "overflow-wrap: anywhere;" in date_rule.group(1)
    assert "max-width: 100%;" in date_rule.group(1)
    assert "white-space: nowrap" not in TEMPLATE


def test_default_type_and_gutters_are_readable_before_autofit():
    assert "--body-font-size: 13.333px;" in TEMPLATE
    assert "--page-padding-x: 14mm;" in TEMPLATE
    assert "--page-padding-y: 12.7mm;" in TEMPLATE
