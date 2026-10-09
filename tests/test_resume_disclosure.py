"""Public export guards must run before metadata is flattened or serialized."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.academic_exporter import AcademicExporter
from core.ats_checker import filter_profile_by_visibility
from core.ats_docx_renderer import AtsDocxRenderer
from core.job_flow import run_career_review
from core.profile_adapter import build_profile_context, normalize_candidate_profile
from core.rendercv_adapter import export_rendercv, import_rendercv, write_rendercv_json
from core.resume_builder import ResumeBuilder
from core.resume_view_model import AtsPlainRenderer, HtmlThemeRenderer, ResumeViewModel
from services.resume_service import ResumeService

PRIVATE = {"text": "CONFIDENTIAL_SENTINEL", "visibility": "reference-only"}
PUBLIC = {"name": "Synthetic Public", "projects": [{"name": "Public Project", "bullets": ["Public result"]}]}


@pytest.mark.parametrize("visibility", [
    "reference-only", "on-request", "variant-specific", "unknown_tag", "all", "*",
    "", [], None, True, 1, {}, ["always", "reference-only"], ["always", "custom"],
    ["always", None], {"always": True},
])
def test_restricted_ambiguous_or_malformed_visibility_is_not_permission(visibility):
    source = {**copy.deepcopy(PUBLIC), "visibility": visibility}
    before = copy.deepcopy(source)
    with pytest.raises(ValueError, match="separate disclosure-safe profile"):
        ResumeViewModel.from_profile(source)
    assert source == before


@pytest.mark.parametrize("source", [
    {"candidate": {"visibility": "reference-only", "name": "Private"}},
    {"candidate": {"name": PRIVATE}},
    {"education": {"school": "Private School", "visibility": "on-request"}},
    {"education": {"education_badges": [PRIVATE]}},
    {"candidate": {"education_grid": [[PRIVATE]]}},
    {"internships": [{"company": "Private", "highlights": [PRIVATE]}]},
    {"experience": [{"org": PRIVATE}]},
    {"experience": [{"bullets": [PRIVATE]}]},
    {"campus_experience": [{"name": "Private", "visibility": "reference-only"}]},
    {"projects": [{"name": "Private", "visibility": "reference-only"}]},
    {"projects": [{"description_zh": PRIVATE}]},
    {"projects": [{"bullets": [PRIVATE]}]},
    {"projects": [{"raw_bullets": [PRIVATE]}]},
    {"papers": [{"title": "Private", "visibility": "on-request"}]},
    {"publications": [{"raw_title": PRIVATE}]},
    {"awards": [PRIVATE]},
    {"skills": {"Languages": [PRIVATE]}},
    {"narrative": {"summary_zh": PRIVATE}},
    {"exam_score": {"scores": [PRIVATE]}},
    {"postgraduate_exam": {"scores": {"Math": PRIVATE}}},
    {"candidate": {"photo": PRIVATE}},
])
def test_raw_nested_fields_and_aliases_are_checked_before_normalization(source):
    before = copy.deepcopy(source)
    context = build_profile_context(source)
    for profile in (source, context):
        with pytest.raises(ValueError, match="visibility") as error:
            ResumeViewModel.from_profile(profile, photo_mode="no-photo")
        assert "CONFIDENTIAL_SENTINEL" not in str(error.value)
        with pytest.raises(ValueError, match="visibility"):
            export_rendercv(profile)
    assert source == before
    assert context.raw_profile == before


@pytest.mark.parametrize("extra", ["normalized", "raw", "fallback"])
def test_normalized_factory_checks_all_inputs(extra):
    profile = normalize_candidate_profile(PUBLIC)
    kwargs = {}
    if extra == "normalized":
        profile["visibility"] = "reference-only"
    else:
        kwargs["raw_profile" if extra == "raw" else "fallback_education"] = PRIVATE
    before = copy.deepcopy((profile, kwargs))
    with pytest.raises(ValueError, match="visibility"):
        ResumeViewModel.from_normalized_profile(profile, **kwargs)
    assert (profile, kwargs) == before


def renderers(tmp_path):
    academic = AcademicExporter()
    return [
        *(lambda vm, theme=theme: HtmlThemeRenderer().render(vm, theme) for theme in HtmlThemeRenderer.THEMES),
        AtsPlainRenderer().render_markdown, AtsPlainRenderer().render_html,
        AtsPlainRenderer().render, academic.generate_latex, academic.generate_typst,
        academic.generate_latex_html_preview,
        lambda vm: AtsDocxRenderer().render(vm, tmp_path / "resume.docx"),
        ResumeViewModel.from_profile,
    ]


@pytest.mark.parametrize("field", ["raw_profile", "projects", "publications", "postgraduate_exam"])
def test_manual_or_mutated_view_models_cannot_bypass_guard(field, tmp_path):
    vm = ResumeViewModel.from_profile(PUBLIC, photo_mode="no-photo")
    setattr(vm, field, {"raw_alias": PRIVATE} if field in ("raw_profile", "postgraduate_exam") else [PRIVATE])
    before = copy.deepcopy(vars(vm))
    for render in renderers(tmp_path):
        with pytest.raises(ValueError, match="visibility"):
            render(vm)
    assert vars(vm) == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("visibility", ["always", ["always"], [" ALWAYS ", "always"]])
def test_public_and_untagged_profiles_render_without_fact_changes(visibility, tmp_path):
    source = copy.deepcopy(PUBLIC)
    source["projects"][0]["visibility"] = visibility
    before = copy.deepcopy(source)
    vm = ResumeViewModel.from_profile(source, photo_mode="no-photo")
    plain = ResumeViewModel.from_profile(PUBLIC, photo_mode="no-photo")
    for render in renderers(tmp_path)[:-2]:
        assert render(vm) == render(plain)
    assert export_rendercv(source) == export_rendercv(PUBLIC)
    assert AtsDocxRenderer().render(vm, tmp_path / "resume.docx").is_file()
    assert source == before


@pytest.mark.parametrize("anonymize", [None, "standard", "strict"])
def test_builders_and_services_reject_before_writing_or_anonymizing(anonymize, tmp_path):
    source = {**copy.deepcopy(PUBLIC), "visibility": "reference-only"}
    source_path = tmp_path / "master.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    original = source_path.read_bytes()
    for profile in (source, source_path, build_profile_context(source)):
        for build in (ResumeService().build_resume, ResumeService().build_all):
            with pytest.raises(ValueError, match="visibility"):
                build(profile, output_dir=tmp_path / "out", anonymize=anonymize)
    assert source_path.read_bytes() == original
    assert source == json.loads(original)
    assert not (tmp_path / "out").exists()


def test_cached_builder_cannot_hide_later_raw_restrictions(tmp_path):
    builder = ResumeBuilder(PUBLIC, photo_mode="no-photo")
    assert builder.view_model
    builder.raw_profile = {**copy.deepcopy(PUBLIC), "education": PRIVATE}
    with pytest.raises(ValueError, match="visibility"):
        builder.build_theme("ats-docx", tmp_path / "out")
    assert not list(tmp_path.rglob("*.docx"))


def test_wildcard_and_matching_filters_are_not_recursive_disclosure_approval(tmp_path):
    source = {"projects": [{"name": "Private", "visibility": ["always"], "bullets": [PRIVATE]}]}
    for tag in ("*", "all", "always"):
        filtered = filter_profile_by_visibility(source, tag)
        with pytest.raises(ValueError, match="visibility"):
            write_rendercv_json(filtered, tmp_path / "rendercv.json")
    assert not list(tmp_path.iterdir())


def test_private_evidence_and_review_remain_available_but_combined_export_rejects(tmp_path):
    source = {**copy.deepcopy(PUBLIC), "visibility": "reference-only"}
    source["projects"][0]["bullets"] = ["CONFIDENTIAL_SENTINEL Python project evidence"]
    before = copy.deepcopy(source)
    context = build_profile_context(source)
    assert any("CONFIDENTIAL_SENTINEL" in claim.text for claim in context.claims)
    assert run_career_review("Python developer", source)["tailored_profile"]
    with patch("core.resume_builder.ResumeBuilder") as builder:
        with pytest.raises(ValueError, match="visibility"):
            run_career_review("Python developer", context, build_resume=True, resume_output_dir=tmp_path)
        builder.assert_not_called()
    assert source == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("theme", ["all", "classic-tech", "ats-plain", "ats-docx", "academic-latex", "academic-typst"])
def test_cli_rejects_restricted_input_without_content_or_output(theme, tmp_path, capsys):
    from presentation.commands.resume_cmd import cmd_resume_build
    source_path = tmp_path / "master.json"
    source_path.write_text(json.dumps({"projects": [PRIVATE]}), encoding="utf-8")
    original = source_path.read_bytes()
    with pytest.raises(SystemExit) as error:
        cmd_resume_build([str(source_path), "--theme", theme, "--output-dir", str(tmp_path / "out")])
    assert error.value.code == 1
    stderr = capsys.readouterr().err
    assert "separate disclosure-safe profile" in stderr
    assert "CONFIDENTIAL_SENTINEL" not in stderr
    assert source_path.read_bytes() == original
    assert not list((tmp_path / "out").iterdir())


@pytest.mark.parametrize("source", [
    {**PUBLIC, "visibility": "on-request"},
    {**PUBLIC, "education": {"school": "Private School", "visibility": "reference-only"}},
    {"candidate": {"name": "Private", "education_grid": [[PRIVATE]]}},
    {**PUBLIC, "visibility": []},
])
def test_normalization_and_review_json_round_trips_preserve_export_restrictions(source):
    before = copy.deepcopy(source)
    normalized = normalize_candidate_profile(source)
    assert normalize_candidate_profile(normalized) == normalized
    reviewed = run_career_review("Python developer", source)["tailored_profile"]
    for derived in (normalized, build_profile_context(source).to_dict(), reviewed):
        restored = json.loads(json.dumps(derived))
        with pytest.raises(ValueError, match="visibility"):
            ResumeBuilder(restored)
    assert source == before


@pytest.mark.parametrize("root_tag", ["always", "reference-only", "on-request", None, []])
@pytest.mark.parametrize("root_first", [True, False])
def test_conflicting_root_and_nested_tags_are_stable(root_tag, root_first):
    root = {"visibility": root_tag}
    nested = {"education": {"school": "Private School", "visibility": "variant-specific"}}
    source = {**root, **nested} if root_first else {**nested, **root}
    before = copy.deepcopy(source)
    normalized = normalize_candidate_profile(source)
    assert normalized["visibility"] == ("variant-specific" if root_tag == "always" else root_tag)
    for _ in range(3):
        restored = json.loads(json.dumps(normalize_candidate_profile(normalized)))
        assert restored == normalized
        with pytest.raises(ValueError, match="visibility"):
            ResumeBuilder(restored)
    assert source == before


def test_proposal_json_retains_restrictions_without_blocking_private_accept(tmp_path):
    from core.material_proposal import create_material_proposal
    from services.offer_service import ProposalService

    source = {**copy.deepcopy(PUBLIC), "education": {"school": "Private", "visibility": "on-request"}}
    before = copy.deepcopy(source)
    proposal = create_material_proposal({}, source, "Python developer", "private-proposal")
    with ProposalService(tmp_path / "proposals.db") as service:
        service.save(proposal)
        result = service.accept(proposal.proposal_id, source, "Python developer", tmp_path / "private.json")
    restored = json.loads(Path(result["profile_output"]).read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="visibility"):
        ResumeBuilder(restored)
    assert source == before


def test_legacy_context_with_stripped_normalized_metadata_still_rejects():
    from core.profile_adapter import ProfileContext

    public = build_profile_context(PUBLIC)
    source = {**copy.deepcopy(PUBLIC), "visibility": "reference-only"}
    context = ProfileContext(source, public.normalized_profile, public.evidence_index,
                             public.claims, public.skills, public.bullets,
                             public.metric_anchors, public.input_quality)
    normalized = normalize_candidate_profile(context)
    assert normalized["visibility"] == "reference-only"
    with pytest.raises(ValueError, match="visibility"):
        ResumeBuilder(json.loads(json.dumps(normalized)))
    assert context.raw_profile == source
    assert context.normalized_profile == public.normalized_profile


@pytest.mark.parametrize("tagged", ["root", "section", "entry", "field"])
def test_rendercv_import_json_preserves_visibility_before_mapping(tagged):
    entry = {"name": "Private Project", "highlights": ["Private result"]}
    section = {"entries": [entry]}
    source = {"cv": {"name": "Synthetic", "sections": {"Projects": section}}}
    if tagged == "field":
        entry["highlights"] = [PRIVATE]
    else:
        {"root": source, "section": section, "entry": entry}[tagged]["visibility"] = "reference-only"
    before = copy.deepcopy(source)
    imported = import_rendercv(source).profile
    assert imported["visibility"] == "reference-only"
    with pytest.raises(ValueError, match="visibility"):
        ResumeBuilder(json.loads(json.dumps(imported)))
    assert source == before
