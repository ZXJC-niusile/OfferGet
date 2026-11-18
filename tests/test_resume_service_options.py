"""CLI resume build controls preserve direct ResumeBuilder forwarding contracts."""

import inspect
import json
from unittest.mock import create_autospec

import pytest

from core.resume_builder import ResumeBuilder
from presentation.commands import resume_cmd


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


@pytest.mark.parametrize("theme,build_method,explicit", [
    (None, "build_theme", False),
    ("classic-tech", "build_theme", True),
    ("all", "build_all", False),
    ("all", "build_all", True),
])
def test_cli_options_forward_directly_to_resume_builder(builder_mock, tmp_path, theme, build_method, explicit):
    profile_path = tmp_path / "profile.json"
    baseline_path = tmp_path / "baseline.json"
    baseline = {"candidate": {"name": "Synthetic Baseline"}}
    profile_path.write_text('{"candidate": {"name": "Synthetic Candidate"}}', encoding="utf-8")
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    cli_options = [str(profile_path), "--output-dir", str(tmp_path)]
    if theme is not None:
        cli_options += ["--theme", theme]
    if explicit:
        cli_options += [
            "--pages", "2", "--no-adaptive-fill", "--no-diff-ledger",
            "--baseline", str(baseline_path), "--no-autofit",
            "--no-photo", "--anonymize", "strict",
        ]

    resume_cmd.cmd_resume_build(cli_options)

    called_method = getattr(builder_mock.return_value, build_method)
    called_method.assert_called_once()
    other_method = "build_all" if build_method == "build_theme" else "build_theme"
    getattr(builder_mock.return_value, other_method).assert_not_called()

    init_kwargs = builder_mock.call_args.kwargs
    forwarded = called_method.call_args.kwargs
    builder_sig = inspect.signature(getattr(ResumeBuilder, build_method)).parameters

    if build_method == "build_theme":
        assert called_method.call_args.args[0] == (theme or "modern-navy")
    else:
        assert forwarded.get("include_docx", builder_sig["include_docx"].default) is False

    if explicit:
        assert init_kwargs["anonymize"] == "strict"
        assert init_kwargs["photo_mode"] == "no-photo"
        assert forwarded["pages"] == "2"
        assert forwarded["adaptive_fill"] is False
        assert forwarded["diff_ledger"] is False
        assert forwarded["baseline_profile"] == baseline
        assert forwarded["autofit"] is False
        assert forwarded["photo"] is False
    else:
        assert init_kwargs["anonymize"] is None
        assert init_kwargs["photo_mode"] == "no-photo"
        assert forwarded["pages"] == builder_sig["pages"].default
        assert forwarded["adaptive_fill"] == builder_sig["adaptive_fill"].default
        assert forwarded["diff_ledger"] == builder_sig["diff_ledger"].default
        assert forwarded["baseline_profile"] is None
        assert forwarded["autofit"] is True
        assert forwarded["photo"] is False
