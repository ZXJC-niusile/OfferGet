"""DOCX content/layout contract using fabricated resume facts only."""
from pathlib import Path

import pytest

pytest.importorskip("docx")
from docx import Document
from docx.oxml.ns import qn

from core.ats_docx_renderer import AtsDocxRenderer
from core.resume_view_model import ResumeViewModel


def synthetic_profile():
    return {
        "name": "林示例 Alex & Lin", "intent": "R&D Engineer",
        "email": "qa@example.invalid", "phone": "+00 000 000 0000", "city": "示例城市",
        "education": {"school": "Example & 示例大学", "degree": "MSc", "major": "Computing",
                      "time": "2018 - 2020", "gpa": "3.8/4.0", "awards": "Test & Scholarship"},
        "experience": [{"company": "ACME & R&D", "dept": "Tools <Platform>", "role": "Engineer",
                        "time": "2020 - 2024", "bullets": [
                            "Maintained **C++ & Python**; latency < 20 ms.",
                            "Literal &amp; and <strong>source</strong> remain source text."]}],
        "campus_experience": [{"name": "Project <One>", "role": "Owner & Maintainer",
                               "time": "2019 - 2020", "bullets": ["TEST-PROJECT-FACT"]}],
        "skills": {"Tools & Languages": ["C++", "R&D"]},
        "publications": [{"title": "Safety & Systems", "authors": "A. Lin & B. Example",
                          "venue": "Test <Journal>", "year": "2025"}],
        "postgraduate_exam": {"target_school": "Example Graduate School", "target_major": "计算机",
                              "direction": "Systems & Reliability", "scores": {"Math <A>": 130, "English": 80},
                              "total_score": 210},
        "narrative": {"summary_en": "Builds reproducible systems for synthetic QA."},
    }


def render(tmp_path, profile=None):
    path = AtsDocxRenderer().render(profile or synthetic_profile(), tmp_path / "resume.docx")
    return Document(path)


def test_docx_preserves_raw_source_facts(tmp_path):
    doc = render(tmp_path)
    text = "\n".join(p.text for p in doc.paragraphs)
    for expected in (
        "ACME & R&D", "Tools <Platform>", "Engineer", "2020 - 2024", "C++ & Python",
        "latency < 20 ms.", "Literal &amp; and <strong>source</strong>",
        "Project <One>", "Owner & Maintainer", "2019 - 2020", "TEST-PROJECT-FACT",
        "Example & 示例大学", "MSc", "Computing", "2018 - 2020", "3.8/4.0", "Test & Scholarship",
        "Safety & Systems", "A. Lin & B. Example", "Test <Journal>", "2025",
        "Example Graduate School", "计算机", "Systems & Reliability", "Math <A>: 130", "English: 80", "210",
        "Tools & Languages: C++, R&D", "Builds reproducible systems",
    ):
        assert expected in text, expected
    assert "&lt;" not in text
    assert "<strong>C++" not in text
    assert "**C++" not in text
    assert any(r.bold and r.text == "C++ & Python" for p in doc.paragraphs for r in p.runs)


def test_legacy_html_projected_view_model_is_decoded_once(tmp_path):
    vm = ResumeViewModel(name="A &amp; B", experiences=[{
        "org": "ACME &amp; Co", "role": "R&amp;D", "time": "2020 &lt; 2025",
        "bullets": ["Used <strong>C++ &amp; SQL</strong> with &lt; 1 error."]}])
    doc = render(tmp_path, vm)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "ACME & Co" in text and "2020 < 2025" in text
    assert "Used C++ & SQL with < 1 error." in text
    assert any(r.bold and r.text == "C++ & SQL" for p in doc.paragraphs for r in p.runs)


def test_docx_uses_a4_linear_flow_and_safe_pagination(tmp_path):
    doc = render(tmp_path)
    section = doc.sections[0]
    assert section.page_width.mm == pytest.approx(210, abs=0.1)
    assert section.page_height.mm == pytest.approx(297, abs=0.1)
    assert section.left_margin.inches == pytest.approx(0.75)
    assert not doc.tables and not doc.inline_shapes
    assert not section.header.paragraphs[0].text
    assert not section.footer.paragraphs[0].text
    headings = [p for p in doc.paragraphs if p.style.name == "Heading 1"]
    assert headings and all(p.paragraph_format.keep_with_next for p in headings)
    dates = next(p for p in doc.paragraphs if "ACME & R&D" in p.text)
    assert dates.text == "ACME & R&D\t2020 - 2024"
    assert dates.paragraph_format.keep_with_next
    assert dates._p.xpath("./w:pPr/w:tabs/w:tab")[0].get(qn("w:val")) == "right"
    bullet = next(p for p in doc.paragraphs if "latency" in p.text)
    assert not bullet.paragraph_format.keep_with_next
    assert bullet.style.paragraph_format.first_line_indent < 0


def test_photo_preferences_do_not_introduce_ats_text_boxes(tmp_path):
    vm = ResumeViewModel.from_profile(synthetic_profile(), photo_mode="no-photo")
    vm.photo_data_uri = "data:image/png;base64,synthetic"
    doc = render(tmp_path, vm)
    assert not doc.inline_shapes and not doc.tables
    assert "ACME & R&D" in "\n".join(p.text for p in doc.paragraphs)


def test_long_item_labels_get_a_separate_unfragmented_date_line(tmp_path):
    profile = synthetic_profile()
    profile["experience"][0]["company"] = "LongInstitutionName" * 10
    doc = render(tmp_path, profile)
    paragraph = next(p for p in doc.paragraphs if p.text == "2020 - 2024")
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    assert paragraph.alignment == WD_ALIGN_PARAGRAPH.RIGHT
    assert paragraph.paragraph_format.keep_with_next
