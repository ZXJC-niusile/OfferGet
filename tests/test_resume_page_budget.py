"""Enforce explicit budgets using the final PDF, including AutoFit fallbacks."""
import json
from pathlib import Path

import pytest
from pypdf import PdfWriter

from core.browser_renderer import RenderResult
from core.layout_solver import LayoutConfig
from core.resume_builder import ResumeBuilder


def write_pdf(path, pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with Path(path).open("wb") as output:
        writer.write(output)


class FinalRenderer:
    def __init__(self, pages=1, fault=None, shadow=False, reported=1):
        self.pages, self.fault, self.shadow, self.reported = pages, fault, shadow, reported

    def measure_overflow(self, *args, **kwargs):
        raise RuntimeError("Measurement unavailable")

    def render_pdf(self, html_path, pdf_path):
        target = Path(pdf_path).with_name("final-shadow.pdf") if self.shadow else Path(pdf_path)
        if self.fault == "exception":
            raise RuntimeError("Render exploded")
        if self.fault == "empty":
            target.touch()
        elif self.fault == "invalid":
            target.write_bytes(b"invalid PDF")
        elif self.fault not in ("failure", "missing"):
            write_pdf(target, self.pages)
        return RenderResult(self.fault != "failure", self.reported, "Synthetic result", target, error="failure reason", diagnostics={"attempts": 2})


class FailedAutoFit:
    def fit_to_single_page(self, **kwargs):
        return False, "Still overflows", {"pages": 2, "last_message": "No remaining compression"}


class MisleadingAutoFit:
    def __init__(self, pages, fault=None):
        self.pages, self.fault = pages, fault

    def fit_to_single_page(self, **kwargs):
        html_path = Path(kwargs["output_html_path"]).with_name("autofit-shadow.html")
        pdf_path = Path(kwargs["output_pdf_path"]).with_name("autofit-shadow.pdf")
        html_path.write_text(Path(kwargs["input_html_path"]).read_text())
        if self.fault != "missing":
            write_pdf(pdf_path, self.pages)
        return True, "Claims one page", {"pages": 1, "final_html_path": str(html_path), "final_pdf_path": str(pdf_path)}


def build(tmp_path, renderer, **kwargs):
    engine = kwargs.pop("engine", FailedAutoFit())
    builder = ResumeBuilder({"candidate": {"name": "Synthetic Candidate"}}, renderer=renderer, autofit_engine=engine)
    return builder.build_html_theme("classic-tech", tmp_path, photo=False, **kwargs)


def report(tmp_path):
    return json.loads((tmp_path / "resume_classic_tech_layout.json").read_text())


@pytest.mark.parametrize("autofit", [False, True])
def test_strict_one_page_rejects_two_page_final_pdf(tmp_path, autofit):
    with pytest.raises(RuntimeError, match="2 pages.*1-page budget"):
        build(tmp_path, FinalRenderer(pages=2, shadow=True), pages="1", autofit=autofit, overflow_px=10000)
    data = report(tmp_path)
    assert data["actual_page_count"] == 2
    assert data["page_budget_passed"] is False
    assert data["status"] == "failed"
    assert data["solver_solved"] is False
    assert data["pdf_path"].endswith("final-shadow.pdf")
    if autofit:
        assert data["autofit"]["success"] is False
        assert data["autofit"]["details"]["last_message"] == "No remaining compression"


@pytest.mark.parametrize("pages", [1, 2])
def test_two_page_budget_accepts_one_or_two_actual_pages(tmp_path, pages):
    output = build(tmp_path, FinalRenderer(pages=pages), pages="2")
    assert output["pdf"].exists()
    assert report(tmp_path)["actual_page_count"] == pages
    assert report(tmp_path)["page_budget_passed"] is True


def test_two_page_budget_rejects_three_pages(tmp_path):
    with pytest.raises(RuntimeError, match="3 pages.*2-page budget"):
        build(tmp_path, FinalRenderer(pages=3), pages="2")


def test_layout_config_budget_applies_when_pages_argument_is_auto(tmp_path):
    with pytest.raises(RuntimeError, match="1-page budget"):
        build(tmp_path, FinalRenderer(pages=2), layout_config=LayoutConfig(page_mode="1"))


def test_explicit_page_argument_overrides_layout_config(tmp_path):
    output = build(tmp_path, FinalRenderer(pages=2), pages="2", layout_config=LayoutConfig(page_mode="1"))
    assert output["pdf"].exists()
    assert report(tmp_path)["requested_page_mode"] == "2"


def test_auto_expansion_is_reported_without_a_diff_ledger(tmp_path):
    with pytest.warns(UserWarning, match="3 pages in auto mode"):
        output = build(tmp_path, FinalRenderer(pages=3), pages="auto", diff_ledger=False)
    data = json.loads(output["layout_report_json"].read_text())
    assert data["actual_page_count"] == 3
    assert data["page_budget_passed"] is True
    assert data["autofit"]["success"] is False
    assert data["measurement"] == {"status": "unverified", "error": "Measurement unavailable"}
    assert "diff_ledger_json" not in output


def test_final_ledger_records_actual_count_and_preserves_solver_status(tmp_path):
    output = build(tmp_path, FinalRenderer(pages=1), pages="1", overflow_px=10000)
    ledger = json.loads(output["diff_ledger_json"].read_text())
    metadata = ledger["metadata"]["layout_metadata"]
    assert metadata["actual_page_count"] == 1
    assert metadata["solved"] is True
    assert metadata["solver_solved"] is False


@pytest.mark.parametrize("fault", ["failure", "exception", "missing", "empty", "invalid"])
def test_failed_render_returns_no_success_paths_and_saves_diagnostics(tmp_path, fault):
    with pytest.raises(RuntimeError, match="Resume build failed"):
        build(tmp_path, FinalRenderer(fault=fault), pages="1", autofit=False)
    data = report(tmp_path)
    assert data["actual_page_count"] is None
    assert data["page_budget_passed"] is False
    assert data["status"] == "unverified"
    if fault == "failure":
        assert data["render"]["diagnostics"] == {"attempts": 2}
        assert data["render"]["error"] == "failure reason"


@pytest.mark.parametrize("reported", [0, None])
def test_zero_or_missing_reported_count_is_not_success(tmp_path, reported):
    with pytest.raises(RuntimeError, match="Resume build failed"):
        build(tmp_path, FinalRenderer(reported=reported), pages="1", autofit=False)
    assert report(tmp_path)["page_budget_passed"] is False


@pytest.mark.parametrize("pages", [0, 2])
def test_autofit_success_cannot_override_actual_pdf(tmp_path, pages):
    with pytest.raises(RuntimeError, match="Resume build failed"):
        build(tmp_path, FinalRenderer(), pages="1", engine=MisleadingAutoFit(pages))
    assert report(tmp_path)["page_budget_passed"] is False


def test_autofit_success_with_missing_pdf_fails(tmp_path):
    with pytest.raises(RuntimeError, match="missing or empty"):
        build(tmp_path, FinalRenderer(), pages="1", engine=MisleadingAutoFit(1, fault="missing"))


def test_autofit_success_honors_final_shadow_paths(tmp_path):
    output = build(tmp_path, FinalRenderer(), pages="1", engine=MisleadingAutoFit(1))
    assert output["pdf"].name == "autofit-shadow.pdf"
    assert output["html"].name == "autofit-shadow.html"
    assert report(tmp_path)["actual_page_count"] == 1


@pytest.mark.parametrize("theme,method", [
    ("ats-plain", "build_ats_plain"),
    ("academic-latex", "build_academic_latex"),
    ("latex", "build_academic_latex"),
    ("academic-typst", "build_academic_typst"),
    ("typst", "build_academic_typst"),
])
def test_native_or_fallback_dispatch_obeys_explicit_budget(tmp_path, monkeypatch, theme, method):
    builder = ResumeBuilder({"name": "Synthetic Candidate"}, renderer=FinalRenderer())
    final_pdf = tmp_path / "native-or-fallback-shadow.pdf"
    write_pdf(final_pdf, 2)
    monkeypatch.setattr(builder, method, lambda *args, **kwargs: {"pdf": final_pdf})
    with pytest.raises(RuntimeError, match="2 pages.*1-page budget"):
        builder.build_theme(theme, tmp_path, pages="1", diff_ledger=False)
    data = json.loads((tmp_path / f"resume_{theme.replace('-', '_')}_layout.json").read_text())
    assert data["actual_page_count"] == 2
    assert data["page_budget_passed"] is False
    assert data["pdf_path"] == str(final_pdf)
    with pytest.warns(UserWarning, match="2 pages in auto mode"):
        output = builder.build_theme(theme, tmp_path, pages="auto", diff_ledger=False)
    assert output["pdf"] == final_pdf
    assert json.loads(output["layout_report_json"].read_text())["actual_page_count"] == 2


@pytest.mark.parametrize("theme", ["ats-plain", "academic-latex", "academic-typst"])
def test_real_fallback_dispatch_obeys_budget(tmp_path, monkeypatch, theme):
    renderer = FinalRenderer(pages=2)
    builder = ResumeBuilder({"name": "Synthetic Candidate"}, renderer=renderer)
    monkeypatch.setattr(builder.academic_exporter, "compile_latex", lambda *args: False)
    monkeypatch.setattr(builder.academic_exporter, "compile_typst", lambda *args: False)
    with pytest.raises(RuntimeError, match="2 pages.*1-page budget"):
        builder.build_theme(theme, tmp_path, pages="1")
    output = builder.build_theme(theme, tmp_path, pages="2")
    assert json.loads(output["layout_report_json"].read_text())["page_budget_passed"] is True


def test_non_html_dispatch_rejects_missing_final_pdf(tmp_path, monkeypatch):
    builder = ResumeBuilder({"name": "Synthetic Candidate"}, renderer=FinalRenderer())
    monkeypatch.setattr(builder, "build_academic_typst", lambda *args, **kwargs: {"pdf": tmp_path / "missing.pdf"})
    with pytest.raises(RuntimeError, match="missing or empty"):
        builder.build_theme("academic-typst", tmp_path, pages="1")


@pytest.mark.parametrize("pages", ["1", "2"])
def test_docx_explicit_budget_rejected_before_export(tmp_path, monkeypatch, pages):
    from services.resume_service import ResumeService
    builder = ResumeBuilder({"name": "Synthetic Candidate"}, renderer=FinalRenderer())
    def unexpected_export(*args, **kwargs):
        pytest.fail("Unsupported DOCX budget must fail before exporting")
    monkeypatch.setattr(builder, "build_ats_docx", unexpected_export)
    for theme in ("ats-docx", "docx"):
        with pytest.raises(ValueError, match="Explicit page budgets require PDF"):
            builder.build_theme(theme, tmp_path, pages=pages)
    monkeypatch.setattr(builder, "build_theme", unexpected_export)
    with pytest.raises(ValueError, match="omit include_docx"):
        builder.build_all(tmp_path, include_docx=True, pages=pages)
    with pytest.raises(ValueError, match="Explicit page budgets require PDF"):
        ResumeService().build_resume({"name": "Synthetic Candidate"}, theme="ats-docx",
                                     output_dir=tmp_path, pages=pages)
