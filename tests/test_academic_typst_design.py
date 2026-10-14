"""Literal facts, native markup and layout contracts for Typst."""
import json
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


def test_typst_photo_filename_is_a_quoted_code_string(tmp_path):
    from PIL import Image
    path = 'photo"name%[x].png'
    image = tmp_path / "photo_safe_name.png"
    Image.new("RGB", (30, 40), "gray").save(image)
    source = AcademicExporter().generate_typst(fixture(), photo_path=image,
                                               photo_mode="photo", photo_reference=path)
    assert '#image(' + json.dumps(path) + ',' in source
    # A quoted filename cannot escape into a Typst expression.
    assert 'photo\\"name%[x].png' in source


def test_typst_preserves_shorthands_and_multiline_list_markers():
    escaped = AcademicExporter._typst_text("~/.config --- literal\n- item\n+ numbered\n= heading")
    assert escaped == r"\~\/.config \-\-\- literal" + "\n" + r"\- item" + "\n" + r"\+ numbered" + "\n" + r"\= heading"


def test_multiline_source_remains_inside_its_original_bullet():
    profile = fixture()
    profile["experience"][0]["bullets"] = ["Start\n+ literal plus\n- literal dash"]
    source = AcademicExporter().generate_typst(profile)
    assert "- Start\n  " + r"\+ literal plus" + "\n  " + r"\- literal dash" in source


def test_typst_photo_reference_cannot_reenable_excluded_photo(tmp_path):
    from unittest.mock import patch
    exporter = AcademicExporter()
    profile = fixture()
    profile["candidate"]["photo_path"] = str(tmp_path / "must-not-read.png")
    with patch("core.resume_photo.image_to_base64_data_uri", side_effect=AssertionError("disabled photo must not be read")):
        for options in ({"reserve_photo": False, "photo_mode": "photo"}, {"photo_mode": "no-photo"},
                        {"photo_mode": "placeholder"}):
            source = exporter.generate_typst(profile, photo_reference="must-not-enable.png", **options)
            assert "#image(" not in source
            assert ("#rect(" in source) == (options.get("photo_mode") == "placeholder")
            assert r"Research & Systems \<Group\>" in source
