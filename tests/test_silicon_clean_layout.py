"""Silicon Clean contracts; CI separately checks actual browser/PDF geometry."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/silicon-clean.html").read_text(encoding="utf-8")


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
