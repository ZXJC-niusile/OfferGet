"""Quality audits require evidence from a real PDF, including failure paths."""
from pathlib import Path

import pytest
from pypdf import PdfWriter

from core.browser_renderer import RenderResult
from core.resume_builder import audit_resume_quality


def write_pdf(path, pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with Path(path).open("wb") as output:
        writer.write(output)


class FaultRenderer:
    def __init__(self, fault=None, pages=1, reported_pages=None, shadow=False):
        self.fault = fault
        self.pages = pages
        self.reported_pages = pages if reported_pages is None else reported_pages
        self.shadow = shadow
        self.output = None

    def render_pdf(self, html_path, pdf_path):
        self.output = Path(pdf_path).with_name("shadow.pdf") if self.shadow else Path(pdf_path)
        if self.fault == "exception":
            raise RuntimeError("Simulated browser timeout")
        if self.fault not in ("missing", "failure"):
            if self.fault == "empty":
                self.output.touch()
            elif self.fault == "invalid":
                self.output.write_bytes(b"not a PDF")
            else:
                write_pdf(self.output, self.pages)
        return RenderResult(
            self.fault != "failure", self.reported_pages, "Simulated browser timeout" if self.fault == "failure" else "Rendered",
            final_path=self.output, error="browser_timeout" if self.fault == "failure" else "",
            diagnostics={"attempts": 3},
        )


@pytest.fixture
def clean_html(tmp_path):
    path = tmp_path / "resume.html"
    path.write_text("<!doctype html><html><body><h1>Synthetic Candidate</h1><p>Software engineer</p></body></html>")
    return path


@pytest.mark.parametrize("fault", ["failure", "exception", "missing", "empty", "invalid"])
def test_unverified_render_never_passes(clean_html, fault):
    renderer = FaultRenderer(fault=fault)
    report = audit_resume_quality(clean_html, renderer)
    assert report["passed"] is False
    assert report["health_score"] < 100
    assert report["page_count"] is None
    assert report["checks"]["page_overflow"]["status"] == "unverified"
    assert report["checks"]["page_overflow"]["passed"] is False
    assert any(item["category"] == "render" for item in report["findings"])
    assert "Fits within" not in str(report)
    assert not renderer.output.exists()


def test_renderer_failure_preserves_diagnostics(clean_html):
    report = audit_resume_quality(clean_html, FaultRenderer(fault="failure"))
    check = report["checks"]["page_overflow"]
    assert "Simulated browser timeout" in check["details"]
    assert check["render"]["error"] == "browser_timeout"
    assert check["render"]["diagnostics"] == {"attempts": 3}


@pytest.mark.parametrize("reported", [0, -1, None])
def test_invalid_reported_count_never_becomes_one_page(clean_html, reported):
    renderer = FaultRenderer()
    renderer.reported_pages = reported
    report = audit_resume_quality(clean_html, renderer)
    assert report["passed"] is False
    assert report["page_count"] is None


@pytest.mark.parametrize("pages", [1, 2, 3])
def test_actual_artifact_controls_budget(clean_html, pages):
    # A renderer's optimistic count must not conceal the final artifact's pages.
    renderer = FaultRenderer(pages=pages, reported_pages=1, shadow=True)
    report = audit_resume_quality(clean_html, renderer)
    assert report["page_count"] == pages
    assert report["passed"] is (pages == 1)
    assert report["checks"]["page_overflow"]["passed"] is (pages == 1)
    assert report["checks"]["page_overflow"]["status"] == ("passed" if pages == 1 else "failed")
    assert not renderer.output.exists()


def test_zero_page_pdf_is_not_a_measured_pass(clean_html):
    report = audit_resume_quality(clean_html, FaultRenderer(pages=0, reported_pages=1))
    assert report["page_count"] is None
    assert report["passed"] is False


def test_missing_html_has_unknown_page_count(tmp_path):
    report = audit_resume_quality(tmp_path / "missing.html", FaultRenderer())
    assert report["page_count"] is None
    assert report["checks"]["page_overflow"]["status"] == "unverified"


def test_pdf_parser_unavailability_is_explicit(clean_html, monkeypatch):
    import builtins
    original_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name in ("pypdf", "fitz"):
            raise ImportError("Parser unavailable")
        return original_import(name, *args, **kwargs)

    renderer = FaultRenderer()
    # Pre-write using the normal parser dependency, then simulate a render-only install.
    def render(html_path, pdf_path):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with Path(pdf_path).open("wb") as output:
            writer.write(output)
        monkeypatch.setattr(builtins, "__import__", unavailable)
        return True, 1, "Rendered"
    renderer.render_pdf = render
    result = audit_resume_quality(clean_html, renderer)
    assert result["passed"] is False
    assert result["page_count"] is None
    assert "Install pypdf or PyMuPDF" in result["checks"]["page_overflow"]["details"]


def test_corrupt_pdf_signature_is_not_evidence(clean_html):
    class CorruptRenderer:
        def render_pdf(self, html_path, pdf_path):
            Path(pdf_path).write_bytes(b"%PDF-1.4\n/Type /Page\n%%EOF\n")
            return True, 1, "Rendered"
    result = audit_resume_quality(clean_html, CorruptRenderer())
    assert result["passed"] is False
    assert result["page_count"] is None
