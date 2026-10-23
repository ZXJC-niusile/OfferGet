"""Browser-independent contracts for modern-navy; real geometry lives in CI QA."""

import base64
import copy
import json
import re
import subprocess
from types import SimpleNamespace

import pytest

from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import (
    BUILDER_GENERATOR,
    ROOT,
    SemanticDocument,
    final_failures,
    fixtures,
    render_html,
    render_production,
    revision,
    synthetic_photo,
    text_content,
    validate_paths,
)

TEMPLATE = (ROOT / "themes/modern-navy.html").read_text(encoding="utf-8")


# One specimen per real generator branch, plus long fields, embedded photos,
# source-photo opt-out and complete source facts. Full geometry combinations
# remain in the real-browser QA fixture matrix.
@pytest.mark.parametrize("case", [case for case in fixtures() if case["name"] in {
    "short-none", "long-embedded", "compact-reserved", "dense-embedded",
    "skills-long-raw-none", "source-photo-raw-none", "all-fields-embedded",
}], ids=lambda case: case["name"])
def test_synthetic_fixtures_render_without_changing_facts(case):
    original = copy.deepcopy(case)
    actual = render_html(ROOT, case)
    assert case == original
    assert "{{" not in actual
    assert case["profile"]["name"] in actual
    assert case["profile"]["email"] in actual
    assert validate_output_security(actual, format_type="html") == []
    assert (SemanticDocument(actual).photos == 1) == (case["photo"] != "none")
    assert SemanticDocument(actual).images == int(case["photo"] == "embedded")


def test_layout_rules_cover_generated_flex_and_grid_markup():
    for selector in (".resume-identity", ".header-top > *", ".entry-identity",
                     ".entry-date", ".edu-grid > div"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", TEMPLATE)
        assert rule, selector
        assert "min-width: 0;" in rule.group(1), selector
    assert "flex-wrap: wrap;" in TEMPLATE
    for forbidden in ("text-overflow: ellipsis", "overflow: hidden", "@import", "url("):
        assert forbidden not in TEMPLATE
    assert TEMPLATE.count("!important") == 4  # Only shared-solver compatibility rules


def test_fixture_matrix_includes_page_and_photo_variants():
    cases = fixtures()
    assert len({case["name"] for case in cases}) == len(cases)
    assert {case["mode"] for case in cases} == {"raw", "compact", "solver", "builder"}
    assert {case["photo"] for case in cases} == {"none", "reserved", "embedded"}
    assert all(case["profile"]["email"].endswith(".invalid") for case in cases)
    assert max(len(case["profile"]["email"]) for case in cases) > 100
    assert base64.b64decode(synthetic_photo().split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")


def valid_metrics():
    return {
        "screen": {"overflow": [], "overlaps": [], "images": [], "bodyFontPx": 12},
        "print": {"overflow": [], "overlaps": [], "printPaddingMm": 8.8},
        "textUnchanged": True, "blockedRequests": [],
        "pdf": {"pages": 1, "missingAnchors": [], "pageBounds": [
            {"number": 1, "widthPt": 595.28, "heightPt": 841.89, "textTopPt": 26, "textBottomPt": 700}
        ]},
    }


def test_qa_accepts_clean_real_measurements():
    assert final_failures(valid_metrics(), {"name": "short-none", "max_pages": 1}) == []


@pytest.mark.parametrize("failure", ["overflow", "overlap", "text", "network", "image", "pages",
                                     "missing", "blank", "gutter", "paper", "dense"])
def test_qa_fails_closed_on_layout_or_content_regression(failure):
    metrics = valid_metrics()
    case = {"name": "short-none", "max_pages": 1}
    if failure == "overflow":
        metrics["screen"]["overflow"] = [{"overflow": 22}]
    elif failure == "overlap":
        metrics["print"]["overlaps"] = [{"selector": ".contacts"}]
    elif failure == "text":
        metrics["textUnchanged"] = False
    elif failure == "network":
        metrics["blockedRequests"] = ["https://example.invalid/font.woff"]
    elif failure == "image":
        metrics["screen"]["images"] = [{"complete": True, "width": 0}]
    elif failure == "pages":
        metrics["pdf"]["pages"] = 2
    elif failure == "missing":
        metrics["pdf"]["missingAnchors"] = ["lost contact"]
    elif failure == "blank":
        metrics["pdf"]["pageBounds"][0]["textTopPt"] = None
    elif failure == "gutter":
        metrics["pdf"]["pageBounds"][0]["textTopPt"] = 0
    elif failure == "paper":
        metrics["pdf"]["pageBounds"][0]["widthPt"] = 612
    else:
        case["name"] = "dense-none"
    assert final_failures(metrics, case)


def make_baseline(tmp_path):
    root = tmp_path / "baseline"
    (root / "themes").mkdir(parents=True)
    (root / "core").mkdir()
    (root / "themes/modern-navy.html").write_text(TEMPLATE, encoding="utf-8")
    (root / "core/resume_view_model.py").write_text("", encoding="utf-8")
    return root


def test_qa_does_not_overwrite_inputs_or_existing_artifacts(tmp_path):
    baseline = make_baseline(tmp_path)
    for output in (baseline, baseline / "rendered", tmp_path, ROOT):
        with pytest.raises(ValueError):
            validate_paths(baseline, output)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_paths(baseline, existing)
    assert (existing / "keep.txt").read_text() == "keep"
    with pytest.raises(ValueError):
        validate_paths(ROOT, tmp_path / "new")
    assert validate_paths(baseline, tmp_path / "new") == (baseline, tmp_path / "new")


def test_archive_revision_is_explicitly_recorded(tmp_path):
    sha = "f5d1af30e7baeb3b41085c3be54553b1488d77f4"
    (tmp_path / "revision.txt").write_text(sha + "\n", encoding="utf-8")
    assert revision(tmp_path) == sha


def test_text_comparison_preserves_tokens_and_normalizes_whitespace():
    assert text_content("<html><style>different</style><body>A <b>B</b>&nbsp;C</body></html>") == "A B C"
    assert text_content("<body>A 12ms</body>") != text_content("<body>A 21ms</body>")


def test_production_fixture_cannot_silently_use_the_raw_renderer():
    case = next(case for case in fixtures() if case["mode"] == "builder")
    with pytest.raises(ValueError, match="real browser"):
        render_html(ROOT, case)


@pytest.mark.parametrize("timeout", [False, True])
def test_production_failure_preserves_full_child_diagnostics(tmp_path, monkeypatch, timeout):
    output = tmp_path / "production"
    stdout = "builder output 示例\n"
    stderr = "x" * 5000 + "\nExact browser startup failure 示例"

    def failed_child(*args, **kwargs):
        assert kwargs["check"] is False
        if timeout:
            raise subprocess.TimeoutExpired(args[0], 180, output=stdout.encode(), stderr=stderr.encode())
        return SimpleNamespace(returncode=7, stdout=stdout, stderr=stderr)

    monkeypatch.setattr("scripts.qa_modern_navy_layout.subprocess.run", failed_child)
    with pytest.raises(RuntimeError) as raised:
        render_production(ROOT, {"mode": "builder"}, output)
    assert "Exact browser startup failure 示例" in str(raised.value)
    assert len(str(raised.value)) < 2500
    assert (output / "child-stdout.txt").read_text(encoding="utf-8") == stdout
    assert (output / "child-stderr.txt").read_text(encoding="utf-8") == stderr


def test_production_uses_default_browser_selection_and_records_its_path(tmp_path, monkeypatch):
    assert "renderer = MeasuredBrowser()" in BUILDER_GENERATOR
    assert "trace['browserPath'] = str(renderer.browser_path)" in BUILDER_GENERATOR
    output = tmp_path / "production"

    def successful_child(*args, **kwargs):
        request = json.loads(kwargs["input"])
        assert "browser_path" not in request
        output.mkdir()
        html_path, pdf_path = output / "resume.html", output / "resume.pdf"
        html_path.write_text("<html><body>synthetic</body></html>", encoding="utf-8")
        pdf_path.write_bytes(b"%PDF-unit-test-output")
        returned = {"html": str(html_path), "pdf": str(pdf_path), "trace": {
            "browserPath": "/test/default-browser", "measurements": [[800, 0]],
            "renders": [{"ok": True, "pages": 1}], "autofit": [{"success": True}],
        }}
        return SimpleNamespace(returncode=0, stdout=json.dumps(returned), stderr="")

    monkeypatch.setattr("scripts.qa_modern_navy_layout.subprocess.run", successful_child)
    html, returned = render_production(ROOT, {"mode": "builder"}, output)
    assert "synthetic" in html
    assert returned["trace"]["browserPath"] == "/test/default-browser"
    assert (output / "child-stdout.txt").is_file()


def test_conventional_resume_presentation_replaces_decorative_blocks():
    assert "h2::before" not in TEMPLATE
    assert "li::before" not in TEMPLATE
    assert "linear-gradient" not in TEMPLATE
    assert "border-left:" not in TEMPLATE
    assert "list-style: disc;" in TEMPLATE
    assert "grid-template-columns: minmax(0, 18fr) minmax(0, 82fr);" in TEMPLATE
    assert ".resume-sections > section > .resume-section-body" in TEMPLATE
    assert "--body-font-size: 13.333px;" in TEMPLATE


def test_fixture_matrix_has_realistic_production_resumes():
    cases = [case for case in fixtures() if case["name"].startswith("professional-")]
    assert {case["photo"] for case in cases} == {"none", "reserved", "embedded"}
    for case in cases:
        assert case["mode"] == "builder"
        assert len(case["profile"]["experience"]) == 2
        assert len(case["profile"]["campus_experience"]) == 2
