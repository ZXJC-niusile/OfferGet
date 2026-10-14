"""Synthetic schema coverage, CLI round trips, and strict export privacy."""
import copy
from contextlib import nullcontext
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from core.anonymizer import PrivacyAnonymizer, PrivacyCoverageWarning
from core.resume_builder import ResumeBuilder


@pytest.mark.parametrize("identity_key", [None, "candidate", "basics"])
@pytest.mark.parametrize("school_key", ["school", "institution", "university", "undergraduate_school", "degree_school"])
def test_unfamiliar_identities_across_supported_schemas(identity_key, school_key):
    identities = {"name": "Synthetic Zorabel Person", school_key: "Fictional Qerlon College"}
    profile = {identity_key: identities} if identity_key else identities.copy()
    profile.update({"education": [{"school": "Fictional Wistaria Academy"}],
                    "internships": [{"organization": "Imaginary Fernworks"}],
                    "experience": [{"org": "Synthetic Kestrel Company"}],
                    "campus_experience": [{"title": "Fictional Opal Project"}],
                    "summary": "Synthetic Zorabel Person studied at Fictional Qerlon College."})
    original = copy.deepcopy(profile)
    anonymizer = PrivacyAnonymizer()
    masked, reverse = anonymizer.anonymize(profile, "strict")
    rendered = json.dumps(masked)
    for value in [*identities.values(), "Fictional Wistaria Academy", "Imaginary Fernworks", "Synthetic Kestrel Company", "Fictional Opal Project"]:
        assert value not in rendered
    assert profile == original
    assert masked.keys() == profile.keys()
    assert anonymizer.deanonymize(masked, reverse) == profile


@pytest.mark.parametrize("key", ["company", "company_en", "org", "organization", "employer"])
def test_company_aliases_and_standard_level_boundaries(key):
    profile = {"candidate": {"name": "Synthetic Alias Person", "school": "Invented Institute"},
               "experience": [{key: "Invented Organization"}]}
    anonymizer = PrivacyAnonymizer()
    standard, reverse = anonymizer.anonymize(profile, "standard")
    assert standard["candidate"]["name"] != profile["candidate"]["name"]
    assert standard["candidate"]["school"] == "Invented Institute"
    assert standard["experience"] == profile["experience"]
    assert anonymizer.deanonymize(standard, reverse) == profile
    strict, reverse = anonymizer.anonymize(profile, "strict")
    assert "Invented" not in json.dumps(strict)
    assert anonymizer.deanonymize(strict, reverse) == profile


def test_flat_cli_preserves_schema_and_roundtrips(tmp_path):
    profile = {"candidate_name": "Imaginary Neris Person", "education": {"school": "Fictional Amber College"},
               "experience": [{"org": "Synthetic Violet Company"}], "counter": 7}
    source, output, mapping = (tmp_path / name for name in ("source.json", "masked.json", "map.json"))
    source.write_text(json.dumps(profile), encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(root / "cli.py"), "anon"]
    result = subprocess.run(command + ["mask", str(source), "--level", "strict", "--map", str(mapping), "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    masked = json.loads(output.read_text(encoding="utf-8"))
    assert masked.keys() == profile.keys()
    for original in (profile["candidate_name"], profile["education"]["school"], profile["experience"][0]["org"]):
        assert original not in output.read_text(encoding="utf-8")
    restored = subprocess.run(command + ["unmask", str(output), "--map", str(mapping)], capture_output=True, text=True)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout) == profile


def test_unknown_privacy_fields_warn_without_echoing_sensitive_values():
    with pytest.warns(PrivacyCoverageWarning, match="candidate.passport") as caught:
        masked, _ = PrivacyAnonymizer().anonymize({"candidate": {"name": "Synthetic User", "passport": "SYNTHETIC-UNSUPPORTED"}})
    assert all("SYNTHETIC-UNSUPPORTED" not in str(w.message) for w in caught)
    assert masked["candidate"]["passport"] == "SYNTHETIC-UNSUPPORTED"


def test_unsupported_identity_type_fails_before_cli_output(tmp_path):
    source = tmp_path / "invalid.json"
    output = tmp_path / "out.json"
    mapping = tmp_path / "map.json"
    source.write_text(json.dumps({"name": {"private": "Synthetic Nested Name"}}))
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "cli.py"), "anon", "mask", str(source), "--output", str(output), "--map", str(mapping)], capture_output=True, text=True)
    assert result.returncode != 0
    assert not output.exists() and not mapping.exists()
    assert "Unsupported privacy field type" in result.stderr


def test_text_only_discovery_reports_limitations():
    with pytest.warns(PrivacyCoverageWarning, match="manual review"):
        PrivacyAnonymizer().anonymize("Unfamiliar synthetic name in unstructured prose")


@pytest.mark.parametrize("shape", ["flat", "candidate"])
def test_strict_export_source_scan_for_original_identities(shape, tmp_path):
    name, school, company = "Synthetic Belora Person", "Fictional Eider University", "Imaginary Falcon Works"
    profile = ({"name": name, "education": {"school": school}} if shape == "flat"
               else {"candidate": {"name": name, "school": school}})
    profile["experience"] = [{"org": company, "bullets": [f"{name} worked at {company} after {school}."]}]
    builder = ResumeBuilder(profile, anonymize="strict", photo_mode="no-photo")
    vm = builder.view_model
    outputs = [builder.ats_renderer.render_markdown(vm), builder.ats_renderer.render_html(vm),
               builder.html_renderer.render(vm, "classic-tech", builder.template_dir)]
    docx = builder.build_ats_docx(tmp_path)["docx"]
    with zipfile.ZipFile(docx) as archive:
        outputs.extend(archive.read(path).decode() for path in archive.namelist() if path.endswith(".xml"))
    for output in outputs:
        for original in (name, school, company):
            assert original not in output


@pytest.mark.parametrize("constructor_strict", [True, False])
@pytest.mark.parametrize("photo_source", ["profile", "constructor", "method"])
def test_strict_excludes_photos_before_reading_even_explicit_mode(tmp_path, constructor_strict, photo_source):
    missing = tmp_path / "SYNTHETIC_PRIVATE_PHOTO.png"
    profile = {"candidate": {"name": "Synthetic Photo Person", "photo_mode": "photo"}}
    kwargs = {"photo_mode": "photo"}
    if photo_source == "profile":
        profile["candidate"]["photo_path"] = str(missing)
    elif photo_source == "constructor":
        kwargs["photo_path"] = missing
    if constructor_strict:
        kwargs["anonymize"] = "strict"
    with pytest.warns(PrivacyCoverageWarning) if photo_source == "profile" else nullcontext():
        builder = ResumeBuilder(profile, **kwargs)
        strict = builder._resolve_profile("strict")
    with pytest.warns(PrivacyCoverageWarning, match="omits requested/profile photos"):
        vm = builder._get_view_model(strict, photo_path=missing if photo_source == "method" else None)
    assert vm.photo_mode == "no-photo" and vm.photo_data_uri is None
    html = builder.ats_renderer.render_html(vm)
    assert str(missing) not in html and "data:image" not in html
    docx = builder.build_ats_docx(tmp_path / "docx", anonymize="strict", photo=True, photo_path=missing)["docx"]
    with zipfile.ZipFile(docx) as archive:
        assert not any(name.startswith("word/media/") for name in archive.namelist())


@pytest.mark.parametrize("method", ["build_html_theme", "build_ats_plain", "build_academic_latex", "build_academic_typst"])
def test_actual_export_entrypoints_exclude_requested_photo_sources(method, tmp_path, monkeypatch):
    # This exercises generated source artifacts, not browser/native PDF layout.
    from tests.test_resume_builder import FastBrowserRenderer
    from core.academic_exporter import AcademicExporter

    monkeypatch.setattr(AcademicExporter, "compile_latex", lambda *args, **kwargs: False)
    monkeypatch.setattr(AcademicExporter, "compile_typst", lambda *args, **kwargs: False)
    missing = tmp_path / "SYNTHETIC_PRIVATE_PHOTO.png"
    profile = {"candidate": {"name": "Synthetic Zorabel", "school": "Fictional Qerlon"}}
    builder = ResumeBuilder(profile, renderer=FastBrowserRenderer(), photo_mode="photo")
    kwargs = {"output_dir": tmp_path / method, "anonymize": "strict", "photo": True, "photo_path": missing}
    if method == "build_html_theme":
        kwargs.update(theme_name="classic-tech", autofit=False, adaptive_fill=False, diff_ledger=False)
    with pytest.warns(PrivacyCoverageWarning, match="omits requested/profile photos"):
        outputs = getattr(builder, method)(**kwargs)
    for artifact in outputs.values():
        if isinstance(artifact, Path) and artifact.suffix in {".html", ".md", ".tex", ".typ"}:
            text = artifact.read_text(encoding="utf-8")
            for original in ("Synthetic Zorabel", "Fictional Qerlon", str(missing), "data:image"):
                assert original not in text
    assert not list((tmp_path / method).glob("*.png"))


@pytest.mark.parametrize("name", ["Alex", "Chen", "Candidate"])
def test_generated_name_alias_does_not_repeat_original_identity(name):
    profile = {"candidate": {"name": name}}
    anonymizer = PrivacyAnonymizer()
    masked, reverse = anonymizer.anonymize(profile, "strict")
    assert name not in masked["candidate"]["name"]
    assert anonymizer.deanonymize(masked, reverse) == profile


@pytest.mark.parametrize("level", ["standard", "strict"])
def test_masked_raw_fallback_preserves_facts_without_identity_leaks(level, tmp_path):
    profile = {"name": "Synthetic Repeat Person", "education": {
        "school": "Invented College", "gpa": "3.85/4.0", "courses": ["Synthetic Statistics"],
        "honors": "Synthetic Repeat Person Medal",
    }}
    builder = ResumeBuilder(profile, anonymize=level, photo_mode="no-photo")
    outputs = [builder.ats_renderer.render_html(builder.view_model),
               builder.ats_renderer.render_markdown(builder.view_model)]
    docx = builder.build_ats_docx(tmp_path)["docx"]
    with zipfile.ZipFile(docx) as archive:
        outputs.append(archive.read("word/document.xml").decode())
    for output in outputs:
        assert "3.85/4.0" in output
        assert "Synthetic Statistics" in output
        assert "Medal" in output
        assert "Synthetic Repeat Person" not in output
        if level == "strict":
            assert "Invented College" not in output


@pytest.mark.parametrize("key", ["projects", "campus_experience"])
def test_project_base_codename_mentions_are_masked_and_reversible(key):
    profile = {key: [{"name": "SyntheticCodename (Internal System)",
                     "description": "Maintained SyntheticCodename reliability"}]}
    anonymizer = PrivacyAnonymizer()
    masked, reverse = anonymizer.anonymize(profile, "strict")
    assert "SyntheticCodename" not in json.dumps(masked)
    assert anonymizer.deanonymize(masked, reverse) == profile


@pytest.mark.parametrize("level", ["standard", "strict"])
@pytest.mark.parametrize("constructor_level", [True, False])
@pytest.mark.parametrize("theme", ["ats-docx", "classic-tech"])
def test_default_export_does_not_write_reverse_identity_sidecars(tmp_path, level, constructor_level, theme):
    from tests.test_resume_builder import FastBrowserRenderer
    profile = {"candidate": {"name": "Synthetic Sidecar Person", "school": "Imaginary Academy"},
               "experience": [{"company": "Invented Employer"}]}
    baseline = {"candidate": {"name": "Synthetic Baseline Person", "school": "Fictional Baseline Academy"}}
    builder = ResumeBuilder(profile, renderer=FastBrowserRenderer(), photo_mode="no-photo",
                            anonymize=level if constructor_level else None)
    kwargs = {"anonymize": None if constructor_level else level, "baseline_profile": baseline,
              "autofit": False, "adaptive_fill": False}
    with pytest.warns(PrivacyCoverageWarning, match="omits the diff ledger"):
        outputs = builder.build_theme(theme, tmp_path, **kwargs)
    assert not any("diff_ledger" in key for key in outputs)
    assert not list(tmp_path.glob("*diff_ledger*"))
    if theme == "classic-tech":
        assert "Synthetic Sidecar Person" not in outputs["html"].read_text(encoding="utf-8")


@pytest.mark.parametrize("direct", [True, False])
def test_anonymized_export_refuses_stale_identity_sidecars(tmp_path, direct):
    stale = tmp_path / "resume_diff_ledger.json"
    stale.write_text('{"candidate_name":"Synthetic Old Identity"}', encoding="utf-8")
    builder = ResumeBuilder({"name": "Synthetic New Identity"}, anonymize="strict")
    with pytest.raises(ValueError, match="clean output directory"):
        if direct:
            builder.build_ats_docx(tmp_path)
        else:
            builder.build_theme("ats-docx", tmp_path)
    assert stale.read_text(encoding="utf-8") == '{"candidate_name":"Synthetic Old Identity"}'
    assert not (tmp_path / "resume_ats.docx").exists()


@pytest.mark.parametrize("profile", [
    {"candidate": {"name": "Synthetic Person", "en_name": "Chen"}},
    {"candidate": {"name": "OFFERGET", "en_name": "a"}, "projects": [{"name": "1"}]},
])
def test_aliases_cannot_reintroduce_other_discovered_identities(profile):
    anonymizer = PrivacyAnonymizer()
    discovered = anonymizer._extract_entities_from_profile_dict(profile, "strict")
    masked, reverse = anonymizer.anonymize(profile)
    for alias in reverse:
        assert not any(real in alias for real in discovered)
    assert anonymizer.deanonymize(masked, reverse) == profile
    assert anonymizer.anonymize(profile) == (masked, reverse)


def test_stale_original_output_is_preserved_with_explicit_scope_warning(tmp_path):
    stale = tmp_path / "older_resume.html"
    stale.write_text("Synthetic Original Identity", encoding="utf-8")
    builder = ResumeBuilder({"name": "Synthetic Current Identity"}, anonymize="strict", photo_mode="no-photo")
    with pytest.warns(PrivacyCoverageWarning, match="Existing output-directory files are not anonymized"):
        outputs = builder.build_ats_docx(tmp_path)
    assert stale.read_text(encoding="utf-8") == "Synthetic Original Identity"
    assert stale not in outputs.values()
    with zipfile.ZipFile(outputs["docx"]) as archive:
        assert "Synthetic Current Identity" not in archive.read("word/document.xml").decode()
