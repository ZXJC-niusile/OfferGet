"""Photo/no-photo source contracts. These do not claim browser or PDF visual QA."""
import copy
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from core.academic_exporter import AcademicExporter
from core.profile_adapter import normalize_candidate_profile
from core.resume_builder import ResumeBuilder
from core.resume_photo import image_to_base64_data_uri, resolve_photo
from core.resume_view_model import AtsPlainRenderer, HtmlThemeRenderer, ResumeViewModel
from presentation.commands.resume_cmd import cmd_resume_build
from scripts.qa_modern_navy_layout import text_content


@pytest.fixture
def portrait(tmp_path):
    """Clearly synthetic head-and-shoulders test illustration, never a real person."""
    path = tmp_path / "synthetic-portrait.png"
    image = Image.new("RGB", (120, 160), "#E6EDF2")
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 22, 80, 70), fill="#D8A47F")
    draw.rectangle((52, 64, 68, 87), fill="#D8A47F")
    draw.rounded_rectangle((21, 83, 99, 164), radius=27, fill="#264C72")
    draw.ellipse((40, 20, 80, 36), fill="#29323B")
    # Visible registration markers help later visual QA identify containment.
    draw.rectangle((3, 3, 116, 156), outline="#C25252", width=2)
    image.save(path)
    return path


@pytest.fixture
def profile(portrait):
    return {"candidate": {"name": "Synthetic Test Candidate", "title": "Engineer / 研究员",
                           "email": "fixture@example.test", "phone": "TEST-0000",
                           "school": "Synthetic University", "degree": "MSc", "edu_time": "2020–2022",
                           "photo_path": str(portrait)},
            "experience": [{"company": "Synthetic Lab", "role": "Engineer", "time": "2023–2025",
                            "bullets": ["Preserved source fact: 17 verified test cases."]}],
            "competencies": {"Languages": ["Python", "中文"]}}


@pytest.mark.parametrize("source", ["candidate_path", "candidate_photo", "flat_path", "explicit"])
def test_no_photo_never_reads_source_image_or_mutates_input(profile, portrait, source):
    if source == "candidate_photo":
        profile["candidate"]["photo"] = profile["candidate"].pop("photo_path")
    elif source == "flat_path":
        profile = {"name": "Synthetic", "photo_path": str(portrait)}
    original = copy.deepcopy(profile)
    kwargs = {"photo_path": portrait} if source == "explicit" else {}
    with patch("core.resume_photo.image_to_base64_data_uri", side_effect=AssertionError("must not read")):
        for selection in ({"reserve_photo": False}, {"photo_mode": "no-photo"}):
            vm = ResumeViewModel.from_profile(profile, **kwargs, **selection)
            assert vm.photo_path is None and vm.photo_data_uri is None and vm.reserve_photo is False
            assert not vm.section_projections["has_photo"]
    assert profile == original


@pytest.mark.parametrize("theme", ResumeBuilder.HTML_THEMES)
def test_same_source_produces_photo_and_no_photo_without_changing_facts(profile, theme):
    original = copy.deepcopy(profile)
    photo = ResumeViewModel.from_profile(profile, photo_mode="photo")
    no_photo = ResumeViewModel.from_profile(profile, photo_mode="no-photo")
    renderer = HtmlThemeRenderer()
    with_photo = renderer.render(photo, theme)
    without = renderer.render(no_photo, theme)
    assert '<img src="data:image/png;base64,' in with_photo
    assert "onerror=" not in with_photo and "预留证件照" not in with_photo
    assert "<img " not in without and "photo-placeholder" not in without and "预留证件照" not in without
    assert "padding-right:0px" in without
    assert text_content(with_photo) == text_content(without)
    assert "17 verified test cases" in without and "Synthetic Test Candidate" in without
    assert profile == original


def test_ats_html_and_markdown_respect_mode(profile):
    renderer = AtsPlainRenderer()
    for mode in ("photo", "no-photo", "placeholder"):
        vm = ResumeViewModel.from_profile(profile, photo_mode=mode)
        html, md = renderer.render_html(vm), renderer.render_markdown(vm)
        assert ('<img src="data:image/png;base64,' in html) == (mode == "photo")
        assert ("预留证件照" in html) == (mode == "placeholder")
        assert ("照片：" in md) == (mode != "no-photo")
        assert ("synthetic-portrait.png" in md) == (mode == "photo")
        assert "17 verified test cases" in html and "17 verified test cases" in md


@pytest.mark.parametrize("method,image_marker,placeholder_marker", [
    ("generate_latex", r"\includegraphics", r"\fbox"),
    ("generate_typst", "#image(", "#rect("),
    ("generate_latex_html_preview", "<img ", '<div class="photo-placeholder">'),
])
def test_native_sources_and_preview_do_not_reenable_disabled_photo(profile, portrait, method, image_marker, placeholder_marker):
    exporter = AcademicExporter()
    render = getattr(exporter, method)
    photo_vm = ResumeViewModel.from_profile(profile, photo_mode="photo")
    for source in (profile, photo_vm):
        with patch("core.resume_photo.image_to_base64_data_uri", side_effect=AssertionError("must not read")):
            source_text = render(source, reserve_photo=False, photo_path=portrait)
        assert image_marker not in source_text and placeholder_marker not in source_text
        assert "synthetic-portrait.png" not in source_text
        assert "17 verified test cases" in source_text.replace("&nbsp;", " ")
    assert image_marker in render(photo_vm)
    assert placeholder_marker in render(profile, photo_mode="placeholder")


@pytest.mark.parametrize("mode", ["photo", "no-photo", "placeholder"])
def test_existing_vm_honors_explicit_overrides_without_mutation(profile, mode):
    old = ResumeViewModel.from_profile(profile, photo_mode="photo")
    snapshot = copy.deepcopy(old)
    new = ResumeViewModel.from_profile(old, photo_mode=mode)
    assert new.photo_mode == mode
    assert (new.photo_path is not None) == (mode == "photo")
    assert old == snapshot
    with pytest.raises(ValueError, match="Unknown photo mode"):
        ResumeViewModel.from_profile(old, photo_mode="unexpected")


def test_placeholder_requires_explicit_new_mode_and_does_not_read(profile):
    with patch("core.resume_photo.image_to_base64_data_uri", side_effect=AssertionError("must not read")):
        vm = ResumeViewModel.from_profile(profile, photo_mode="placeholder")
    assert vm.reserve_photo and vm.photo_data_uri is None and vm.photo_path is None
    # Legacy API placeholder behavior remains available to existing callers.
    assert ResumeViewModel.from_profile({"name": "Synthetic"}, reserve_photo=True).reserve_photo
    with pytest.raises(ValueError, match="requires an actual image"):
        ResumeViewModel.from_profile({"name": "Synthetic"}, photo_mode="photo")


@pytest.mark.parametrize("filename,payload", [
    ("private.txt", b"NOT AN IMAGE: private text must never become a data URI"),
    ("fake.png", b"not a png"),
    ("fake.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 10),
    ("active.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'),
])
def test_non_images_are_rejected_not_mislabeled(tmp_path, filename, payload):
    file = tmp_path / filename
    file.write_bytes(payload)
    with pytest.raises(ValueError):
        image_to_base64_data_uri(file)
    with pytest.raises(ValueError):
        ResumeViewModel.from_profile({"candidate": {"photo_path": str(file)}}, photo_mode="photo")
    # Disabled invalid inputs do not block text exports.
    assert resolve_photo({"photo_path": str(file)}, photo_mode="no-photo").path is None


def test_missing_truncated_mismatched_animated_and_oversized_images_fail(tmp_path, portrait, monkeypatch):
    with pytest.raises(ValueError, match="not found"):
        image_to_base64_data_uri(tmp_path / "missing.png")
    file = tmp_path / "truncated.png"; file.write_bytes(portrait.read_bytes()[:-20])
    with pytest.raises(ValueError):
        image_to_base64_data_uri(file)
    mismatch = tmp_path / "wrong.jpg"; mismatch.write_bytes(portrait.read_bytes())
    with pytest.raises(ValueError, match="extension"):
        image_to_base64_data_uri(mismatch)
    animated = tmp_path / "animated.gif"
    Image.new("RGB", (10, 10), "red").save(animated, save_all=True,
                                          append_images=[Image.new("RGB", (10, 10), "blue")], duration=100)
    with pytest.raises(ValueError, match="single-frame"):
        image_to_base64_data_uri(animated)
    monkeypatch.setattr("core.resume_photo.MAX_PHOTO_BYTES", 2)
    with pytest.raises(ValueError, match="limit"):
        image_to_base64_data_uri(portrait)


def test_shared_helper_identity_and_flat_schema(portrait):
    from core.academic_exporter import _image_to_base64_data_uri as native_helper
    from core.resume_view_model import _image_to_base64_data_uri as vm_helper
    assert native_helper is vm_helper is image_to_base64_data_uri
    normalized = normalize_candidate_profile({"name": "Synthetic", "photo_path": str(portrait),
                                              "photo_mode": "no-photo", "reserve_photo": False})
    assert normalized["candidate"]["photo_mode"] == "no-photo"
    assert normalized["candidate"]["photo_path"] == str(portrait)
    assert normalized["candidate"]["reserve_photo"] is False


class SourceOnlyRenderer:
    """Test double for source/IO assertions; never usable as visual evidence."""
    def render_pdf(self, html_path, pdf_path):
        Path(pdf_path).write_bytes(b"source-contract-test-double")
        return True, 1, "source contract only"


def test_builder_does_not_read_or_copy_disabled_photo(profile, portrait, tmp_path):
    with patch("core.resume_photo.image_to_base64_data_uri", side_effect=AssertionError("must not read")):
        builder = ResumeBuilder(profile, photo_path=portrait, photo_mode="photo", renderer=SourceOnlyRenderer())
        with patch.object(builder.academic_exporter, "compile_typst", return_value=False):
            result = builder.build_academic_typst(tmp_path / "typst", photo=False)
        assert "#image(" not in result["typ"].read_text()
        assert not list((tmp_path / "typst").glob("*.png"))
        with patch.object(builder.academic_exporter, "compile_latex", return_value=False):
            result = builder.build_academic_latex(tmp_path / "latex", photo=False)
        assert r"\includegraphics" not in result["tex"].read_text()
        result = builder.build_theme("ats-docx", tmp_path / "docx", photo=False, diff_ledger=False)
    with zipfile.ZipFile(result["docx"]) as doc:
        assert not any(name.startswith("word/media/") for name in doc.namelist())
        assert "Synthetic Test Candidate" in doc.read("word/document.xml").decode()


def test_typst_copies_only_validated_selected_image(profile, tmp_path):
    builder = ResumeBuilder(profile, photo_mode="photo", renderer=SourceOnlyRenderer())
    with patch.object(builder.academic_exporter, "compile_typst", return_value=False):
        result = builder.build_academic_typst(tmp_path / "typst")
    assert '#image("synthetic-portrait.png"' in result["typ"].read_text()
    assert (tmp_path / "typst/synthetic-portrait.png").read_bytes() == Path(profile["candidate"]["photo_path"]).read_bytes()


@pytest.mark.parametrize("mode", ["photo", "placeholder"])
def test_docx_honors_explicit_photo_request(profile, tmp_path, mode):
    builder = ResumeBuilder(profile, photo_mode=mode)
    result = builder.build_theme("ats-docx", tmp_path, diff_ledger=False)
    from docx import Document
    assert len(Document(result["docx"]).inline_shapes) == (1 if mode == "photo" else 0)


@pytest.mark.parametrize("flags", [[], ["--no-photo"], ["--photo-mode", "no-photo"]])
def test_cli_default_and_alias_are_no_photo(profile, portrait, tmp_path, capsys, flags):
    source = tmp_path / "profile.json"; source.write_text(json.dumps(profile))
    with patch("core.resume_photo.image_to_base64_data_uri", side_effect=AssertionError("must not read")):
        cmd_resume_build([str(source), "--theme", "ats-docx", "--output-dir", str(tmp_path / "out"),
                          "--no-diff-ledger", *flags])
    assert "No photo or reserved slot" in capsys.readouterr().out
    assert source.read_text() == json.dumps(profile)


def test_cli_no_photo_overrides_explicit_invalid_path(tmp_path, capsys):
    source = tmp_path / "profile.json"; source.write_text('{"name":"Synthetic"}')
    cmd_resume_build([str(source), "--theme", "ats-docx", "--output-dir", str(tmp_path / "out"),
                      "--no-diff-ledger", "--no-photo", "--photo-path", str(tmp_path / "missing.png")])
    assert "No photo or reserved slot" in capsys.readouterr().out


def test_cli_photo_requires_valid_image_before_renderer(tmp_path, capsys):
    source = tmp_path / "profile.json"; source.write_text('{"name":"Synthetic"}')
    with pytest.raises(SystemExit) as error:
        cmd_resume_build([str(source), "--theme", "modern-navy", "--photo-mode", "photo",
                          "--output-dir", str(tmp_path / "out")])
    assert error.value.code == 1
    assert "requires an actual image" in capsys.readouterr().err


@pytest.mark.parametrize("method", ["generate_latex", "generate_typst", "generate_latex_html_preview"])
@pytest.mark.parametrize("context", [False, True])
def test_native_exports_honor_profile_mode_without_implicit_downgrade(method, context):
    from core.profile_adapter import ProfileContext
    exporter = AcademicExporter()
    for mode in ("photo", "placeholder", "no-photo"):
        source = {"candidate": {"name": "Synthetic", "photo_mode": mode}}
        if context:
            source = ProfileContext.from_profile(source)
        render = getattr(exporter, method)
        if mode == "photo":
            with pytest.raises(ValueError, match="requires an actual image"):
                render(source)
        else:
            text = render(source)
            assert ("预留证件照" in text) == (mode == "placeholder")


def test_explicit_mode_overrides_profile_and_boolean_false_wins(profile):
    profile["candidate"]["photo_mode"] = "no-photo"
    assert ResumeViewModel.from_profile(profile, photo_mode="photo").photo_data_uri
    assert ResumeViewModel.from_profile(profile, reserve_photo=False, photo_mode="photo").photo_data_uri is None
    profile["candidate"]["photo_mode"] = "photo"
    assert ResumeViewModel.from_profile(profile, photo_mode="no-photo").photo_path is None


def test_cli_photo_path_implies_photo_and_explicit_placeholder_is_preview(profile, portrait, tmp_path, capsys):
    source = tmp_path / "profile.json"; source.write_text(json.dumps(profile))
    # Stub only output rendering; real CLI, builder and photo selection still run.
    def build_source(builder, theme, output_dir, **kwargs):
        vm = builder._get_view_model(reserve_photo=kwargs["photo"])
        html = HtmlThemeRenderer().render(vm, theme)
        output = Path(output_dir) / "source.html"; output.write_text(html)
        return {"html": output}
    with patch.object(ResumeBuilder, "build_theme", build_source):
        cmd_resume_build([str(source), "--theme", "modern-navy", "--photo-path", str(portrait),
                          "--output-dir", str(tmp_path / "photo"), "--no-diff-ledger"])
        assert '<img src="data:image/png;base64,' in (tmp_path / "photo/source.html").read_text()
        assert "Validated image" in capsys.readouterr().out
        cmd_resume_build([str(source), "--theme", "modern-navy", "--photo-mode", "placeholder",
                          "--output-dir", str(tmp_path / "preview"), "--no-diff-ledger"])
        preview = (tmp_path / "preview/source.html").read_text()
        assert "预留证件照" in preview and "<img " not in preview
        assert "layout preview only" in capsys.readouterr().out


def test_resolved_no_photo_vm_requires_explicit_mode_to_reenable(profile, portrait):
    vm = ResumeViewModel.from_profile(profile, photo_mode="no-photo")
    assert ResumeViewModel.from_profile(vm, photo_path=portrait).photo_data_uri is None
    assert ResumeViewModel.from_profile(vm, photo_path=portrait, photo_mode="photo").photo_data_uri
    for method, marker in (("generate_latex", r"\includegraphics"), ("generate_typst", "#image("),
                           ("generate_latex_html_preview", "<img ")):
        render = getattr(AcademicExporter(), method)
        assert marker not in render(vm, photo_path=portrait)
        assert marker in render(vm, photo_path=portrait, photo_mode="photo")


@pytest.mark.parametrize("method", ["generate_latex", "generate_typst"])
def test_removed_selected_image_never_downgrades_to_placeholder(profile, portrait, method):
    vm = ResumeViewModel.from_profile(profile, photo_mode="photo")
    portrait.unlink()
    with pytest.raises(ValueError, match="not found"):
        getattr(AcademicExporter(), method)(vm)


def test_docx_profile_selected_photo_mode_is_not_silently_dropped(profile, tmp_path):
    profile["candidate"]["photo_mode"] = "photo"
    builder = ResumeBuilder(profile)
    from docx import Document
    result = builder.build_theme("ats-docx", tmp_path, diff_ledger=False)
    assert len(Document(result["docx"]).inline_shapes) == 1
    assert builder.build_theme("ats-docx", tmp_path, photo=False, diff_ledger=False)["docx"].exists()
