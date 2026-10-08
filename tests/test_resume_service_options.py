"""Additive service controls preserve Builder and CLI forwarding contracts."""

import inspect
import json
from unittest.mock import create_autospec

import pytest

from core.resume_builder import ResumeBuilder
from presentation.commands import resume_cmd
from services.resume_service import ResumeService

CONTROLS = ("pages", "adaptive_fill", "diff_ledger", "baseline_profile")


@pytest.fixture
def builder_mock(monkeypatch):
    builder_class = create_autospec(ResumeBuilder)
    instance = builder_class.return_value
    instance.profile = {"candidate": {"name": "Synthetic Candidate"}}
    instance.view_model = object()
    instance.build_theme.return_value = {}
    instance.build_all.return_value = {"classic-tech": {}}
    monkeypatch.setattr("core.resume_builder.ResumeBuilder", builder_class)
    monkeypatch.setattr(resume_cmd, "ResumeBuilder", builder_class)
    return builder_class


@pytest.mark.parametrize("method,build_method", [("build_resume", "build_theme"), ("build_all", "build_all")])
@pytest.mark.parametrize("pages", ["auto", "1", "2"])
@pytest.mark.parametrize("enabled", [True, False])
def test_explicit_layout_and_evidence_options_are_forwarded(builder_mock, tmp_path, method, build_method, pages, enabled):
    profile = {"candidate": {"name": "Synthetic Candidate"}}
    baseline = {"candidate": {"name": "Synthetic Baseline"}}
    options = {"pages": pages, "adaptive_fill": enabled, "diff_ledger": enabled,
               "baseline_profile": baseline}
    result = getattr(ResumeService(), method)(profile, output_dir=tmp_path, **options)
    call = getattr(builder_mock.return_value, build_method)
    assert result is call.return_value
    for key, value in options.items():
        assert call.call_args.kwargs[key] is value
    assert call.call_args.kwargs["output_dir"] == tmp_path
    if method == "build_all":
        assert call.call_args.kwargs["include_docx"] is False


@pytest.mark.parametrize("include_docx", [True, False])
def test_build_all_preserves_docx_opt_in(builder_mock, include_docx):
    ResumeService().build_all({}, include_docx=include_docx)
    assert builder_mock.return_value.build_all.call_args.kwargs["include_docx"] is include_docx


@pytest.mark.parametrize("method,build_method", [("build_resume", "build_theme"), ("build_all", "build_all")])
@pytest.mark.parametrize("photo_mode", [None, "photo", "no-photo", "placeholder"])
@pytest.mark.parametrize("photo", [True, False])
def test_existing_photo_and_privacy_options_are_preserved(builder_mock, tmp_path, method, build_method, photo_mode, photo):
    profile = {"candidate": {"name": "Synthetic Candidate"}}
    photo_path = tmp_path / "synthetic-photo.png"
    getattr(ResumeService(), method)(profile, photo=photo, photo_path=photo_path,
                                    photo_mode=photo_mode, anonymize="strict", autofit=False,
                                    pages="2", diff_ledger=False)
    builder_mock.assert_called_once_with(profile, photo_path=photo_path,
                                         anonymize="strict", photo_mode=photo_mode)
    options = getattr(builder_mock.return_value, build_method).call_args.kwargs
    assert options["photo"] is photo
    assert options["autofit"] is False
    assert options["anonymize"] == "strict"
    if method == "build_all":
        assert options["photo_path"] == photo_path


@pytest.mark.parametrize("method,build_method", [("build_resume", "build_theme"), ("build_all", "build_all")])
def test_current_defaults_match_builder_without_resetting_service_defaults(builder_mock, method, build_method):
    service_method = getattr(ResumeService(), method)
    service_signature = inspect.signature(service_method)
    builder_signature = inspect.signature(getattr(ResumeBuilder, build_method))
    for key in CONTROLS + (("include_docx",) if method == "build_all" else ()):
        assert service_signature.parameters[key].default == builder_signature.parameters[key].default
        assert service_signature.parameters[key].kind is inspect.Parameter.KEYWORD_ONLY
    service_method({})
    forwarded = getattr(builder_mock.return_value, build_method).call_args.kwargs
    for key in CONTROLS:
        assert forwarded[key] == builder_signature.parameters[key].default
    assert forwarded["output_dir"] == "dist/resume"
    assert forwarded["photo"] is True
    assert forwarded["autofit"] is True
    assert forwarded["anonymize"] is None
    builder_mock.assert_called_once_with({}, photo_path=None, anonymize=None, photo_mode=None)
    if method == "build_resume":
        assert forwarded["theme"] == "modern-navy"


def test_existing_positional_arguments_still_bind(builder_mock, tmp_path):
    service = ResumeService()
    service.build_resume({}, "classic-tech", tmp_path, False, None, False, "standard", "no-photo")
    assert builder_mock.return_value.build_theme.call_args.kwargs["theme"] == "classic-tech"
    builder_mock.reset_mock()
    service.build_all({}, tmp_path, False, None, False, "standard", "no-photo")
    builder_mock.assert_called_once_with({}, photo_path=None, anonymize="standard", photo_mode="no-photo")
    assert builder_mock.return_value.build_all.call_args.kwargs["photo"] is False


@pytest.mark.parametrize("theme,method,build_method", [
    ("classic-tech", "build_resume", "build_theme"), ("all", "build_all", "build_all"),
])
@pytest.mark.parametrize("explicit", [False, True])
def test_shared_cli_options_have_service_parity(builder_mock, tmp_path, theme, method, build_method, explicit):
    profile_path = tmp_path / "profile.json"
    baseline_path = tmp_path / "baseline.json"
    baseline = {"candidate": {"name": "Synthetic Baseline"}}
    profile_path.write_text('{"candidate": {"name": "Synthetic Candidate"}}', encoding="utf-8")
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    cli_options = [str(profile_path), "--theme", theme, "--output-dir", str(tmp_path)]
    service_options = {}
    if explicit:
        cli_options += ["--pages", "2", "--no-adaptive-fill", "--no-diff-ledger",
                        "--baseline", str(baseline_path), "--no-autofit",
                        "--no-photo", "--anonymize", "strict"]
        service_options = {"pages": "2", "adaptive_fill": False, "diff_ledger": False,
                           "baseline_profile": baseline, "autofit": False,
                           "photo": False, "photo_mode": "no-photo", "anonymize": "strict"}
    if method == "build_resume":
        service_options["theme"] = theme
    resume_cmd.cmd_resume_build(cli_options)
    cli_call = getattr(builder_mock.return_value, build_method).call_args.kwargs
    builder_mock.reset_mock()
    getattr(ResumeService(), method)(profile_path, output_dir=tmp_path, **service_options)
    service_call = getattr(builder_mock.return_value, build_method).call_args.kwargs
    for key in CONTROLS + ("autofit",):
        assert service_call[key] == cli_call[key]
    if explicit:
        assert service_call["photo"] == cli_call["photo"]
        assert service_call["baseline_profile"] == baseline
    else:
        # Existing intentional interface difference: CLI selects no-photo;
        # service leaves photo-mode resolution to Builder/profile data.
        assert cli_call["photo"] is False
        assert service_call["photo"] is True
