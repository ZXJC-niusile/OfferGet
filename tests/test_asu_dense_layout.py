"""ASu Dense source contracts; real production geometry is checked in visual CI."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/asu-dense.html").read_text(encoding="utf-8")


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
