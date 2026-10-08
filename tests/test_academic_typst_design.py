"""Literal facts, native markup and layout contracts for Typst."""
import json
import re
from pathlib import Path

from core.academic_exporter import AcademicExporter
from core.resume_view_model import ResumeViewModel
from tests.test_academic_latex_design import fixture


def test_typst_preserves_raw_facts_and_neutralizes_label_markup():
    source = AcademicExporter().generate_typst(fixture())
    for expected in (r"Research & Systems \<Group\>", r"R&D · Engineer \<Lead\>", "2020 - 2025",
                     "*C++ & SQL*", r"latency \< 20 ms.", r"Literal &amp; and \<strong\>text\<\/strong\>.",
                     r"GPA \> 3.8", "Award & Merit", r"Project \<One\>", "Owner & Maintainer",
                     r"Evidence & Safety \<Review\>", "A. Lin & B. Example", "_Synthetic Journal_", "2025",
                     "Graduate & School", r"Math \<A\>: 130", "English: 80", "210"):
        assert expected in source, expected
    assert "&amp; Systems" not in source and "&lt;" not in source
    assert 'size: 10.5pt' in source and '18mm' in source
    assert 'sticky: true' in source and 'body-indent: 12pt' in source


def test_typst_escapes_comments_and_long_tokens_without_html_entities():
    exporter = AcademicExporter()
    assert exporter._typst_text("literal // comment") == r"literal \/\/ comment"
    assert exporter._typst_text("x < 2 and <label>") == r"x \< 2 and \<label\>"
    token = "ExtremelyLongUnbrokenResearchInstitutionName" * 3
    escaped = exporter._typst_text(token)
    assert r"\u{200b}" in escaped
    assert escaped.replace(r"\u{200b}", "") == token


def test_typst_legacy_view_model_decodes_once():
    vm = ResumeViewModel(name="Alex", experiences=[{"org": "A &amp; B", "role": "R&amp;D",
        "time": "2020 - 2025", "bullets": ["Used <strong>C++ &amp; SQL</strong>; x &lt; 2."]}])
    source = AcademicExporter().generate_typst(vm)
    assert "A & B" in source and "*C++ & SQL*" in source and r"x \< 2." in source


def test_typst_photo_filename_is_a_quoted_code_string():
    path = 'photo"name%[x].png'
    source = AcademicExporter().generate_typst(fixture(), photo_path=path)
    assert '#image(' + json.dumps(path) + ',' in source
    # A quoted filename cannot escape into a Typst expression.
    assert 'photo\\"name%[x].png' in source
