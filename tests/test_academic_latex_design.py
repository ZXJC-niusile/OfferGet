"""Source-text correctness for native LaTeX and its HTML fallback."""
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.academic_exporter import AcademicExporter
from core.resume_view_model import ResumeViewModel


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, value):
        self.parts.append(value)


def fixture():
    return {"candidate": {"name": "示例 Alex & Lin", "title": "R&D Engineer", "email": "qa@example.invalid",
                          "school": "Example & University", "degree": "MSc", "edu_time": "2018 - 2020",
                          "education_rows": [["GPA > 3.8", "Award & Merit"]], "reserve_photo": False},
            "experience": [{"org": "Research & Systems <Group>", "dept": "R&D", "role": "Engineer <Lead>",
                            "time": "2020 - 2025", "bullets": ["Used **C++ & SQL**; latency < 20 ms.",
                            "Literal &amp; and <strong>text</strong>."]}],
            "projects": [{"name": "Project <One>", "role": "Owner & Maintainer", "time": "2022 - 2024",
                          "bullets": [r"Printed \input{sample} literally; 95% complete."]}],
            "publications": [{"title": "Evidence & Safety <Review>", "authors": "A. Lin & B. Example",
                              "venue": "Synthetic Journal", "year": "2025"}],
            "postgraduate_exam": {"target_school": "Graduate & School", "target_major": "Computing",
                                  "scores": {"Math <A>": 130, "English": 80}, "total_score": 210},
            "competencies": {"Tools & Languages": ["C++", "R&D"]}}


def test_native_latex_uses_raw_fields_and_escapes_once():
    source = AcademicExporter().generate_latex(fixture())
    for expected in (r"Research \& Systems <Group>", r"R\&D · Engineer <Lead>", "2020 - 2025",
                     r"\textbf{C++ \& SQL}", "latency < 20 ms.", r"Literal \&amp; and <strong>text</strong>.",
                     r"GPA > 3.8", r"Award \& Merit", r"Project <One>", r"Owner \& Maintainer",
                     r"Evidence \& Safety <Review>", r"A. Lin \& B. Example", "Synthetic Journal", "2025",
                     r"Graduate \& School", "Math <A>: 130", "English: 80", "210",
                     r"\textbackslash{}input\{sample\}", r"95\%"):
        assert expected in source, expected
    assert r"\&amp; Systems" not in source
    assert r"\&lt;" not in source
    assert "margin=18mm" in source and "Noto Serif CJK SC" in source
    assert r"\Needspace" in source and r"\titlerule" not in source
    assert r"\input{sample}" not in source


def test_html_fallback_preserves_all_fields_and_literal_markup():
    source = AcademicExporter().generate_latex_html_preview(fixture(), reserve_photo=False)
    parser = Text(); parser.feed(source)
    text = " ".join(parser.parts).replace("\u00a0", " ")
    for expected in ("Research & Systems <Group>", "R&D · Engineer <Lead>", "Used ", "C++ & SQL",
                     "Literal &amp; and <strong>text</strong>.", "GPA > 3.8", "Award & Merit",
                     "Evidence & Safety <Review>", "A. Lin & B. Example", "Synthetic Journal", "2025",
                     "Graduate & School", "Math <A>: 130", "English: 80"):
        assert expected in text, expected
    assert "<strong>C++ &amp; SQL</strong>" in source
    assert "&amp;amp; Systems" not in source
    assert "grid-template-columns: minmax(0, 1fr) auto" in source


def test_custom_section_titles_are_data_in_both_formats():
    exporter = AcademicExporter()
    titles = {"education": r"Study <Notes> & \input{bad}"}
    tex = exporter.generate_latex(fixture(), section_titles=titles)
    html = exporter.generate_latex_html_preview(fixture(), section_titles=titles)
    assert r"Study <Notes> \& \textbackslash{}input\{bad\}" in tex
    assert "Study &lt;Notes&gt; &amp;" in html
    assert "<Notes>" not in html


def test_legacy_projected_view_model_decodes_generated_markup_once():
    vm = ResumeViewModel(name="Alex", experiences=[{"org": "A &amp; B", "role": "R&amp;D",
        "time": "2020 - 2025", "bullets": ["Used <strong>C++ &amp; SQL</strong>; x &lt; 2."]}])
    exporter = AcademicExporter()
    assert r"\textbf{C++ \& SQL}" in exporter.generate_latex(vm)
    assert "<strong>C++ &amp; SQL</strong>" in exporter.generate_latex_html_preview(vm)


def test_latex_compile_rejects_failed_partial_and_stale_pdf(tmp_path):
    source = tmp_path / "resume.tex"; source.write_text("invalid source")
    source.with_suffix(".pdf").write_bytes(b"%PDF-stale")
    target = tmp_path / "target.pdf"
    def fail(command, **kwargs):
        folder = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("-output-directory=")))
        (folder / "resume.pdf").write_bytes(b"%PDF-partial")
        assert "-halt-on-error" in command and "-no-shell-escape" in command
        return SimpleNamespace(returncode=1)
    with patch("shutil.which", return_value="xelatex"), patch("subprocess.run", side_effect=fail):
        assert not AcademicExporter().compile_latex(source, target)
    assert not target.exists()
    assert source.with_suffix(".pdf").read_bytes() == b"%PDF-stale"


def test_photo_percent_and_brace_filenames_fail_clearly(tmp_path):
    import pytest
    exporter = AcademicExporter()
    for name in ("photo%example.png", "photo{example}.png"):
        path = tmp_path / name; path.write_bytes(b"synthetic placeholder")
        with pytest.raises(ValueError, match="photo filenames"):
            exporter.generate_latex(fixture(), photo_path=path)
