"""Engineering theme contracts; actual browser layout remains a separate CI gate."""

import copy
import re
from pathlib import Path

from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from scripts.qa_modern_navy_layout import fixtures

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/engineering-sb2nov.html").read_text(encoding="utf-8")


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
