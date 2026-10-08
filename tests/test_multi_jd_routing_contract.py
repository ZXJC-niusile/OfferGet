"""Unsupported JD collections must stop before any single-JD pipeline work."""

import json
from unittest.mock import patch

import pytest

from core.input_router import (
    InputMode,
    InputRouter,
    InvalidInputError,
    RouteDecision,
    detect_and_route_input,
)
from services.review_service import CareerReviewService

JD = "职位：行政助理\n工作内容：安排会议，整理档案。"
PROFILE = {"name": "Synthetic Candidate", "skills": []}
STAGES = (
    "jd_decode", "multi_jd_decode", "full_match", "batch_match",
    "ats_matching_score", "gap_analysis", "cross_jd_gap_matrix",
    "comparative_analysis", "career_review", "tailored_resume",
    "interview_prediction", "report_generation",
)


@pytest.mark.parametrize("jds", [[JD, JD + "\n地点：上海"], (JD, JD), [JD], (JD,), [None, "", JD]])
def test_jd_collection_is_explicitly_unsupported_before_pipeline(jds, tmp_path):
    route = detect_and_route_input(jds, PROFILE)
    assert route.mode == InputMode.MULTI_JD_AND_PROFILE.value
    for stage in STAGES:
        assert not route.can_execute(stage)
        assert route.is_blocked(stage)
        with pytest.raises(InvalidInputError, match="unsupported"):
            route.raise_if_blocked(stage)
    assert route.can_execute("profile_audit")
    assert route.can_execute("resume_build")
    destination = tmp_path / "must-not-create"
    with patch("core.job_flow.run_career_review") as pipeline:
        with pytest.raises(InvalidInputError, match="Batch JD processing is unsupported") as error:
            CareerReviewService().run_review(jds, PROFILE, build_resume=True, resume_output_dir=destination)
        assert error.value.decision.mode == InputMode.MULTI_JD_AND_PROFILE.value
        pipeline.assert_not_called()
    assert not destination.exists()


def test_jd_collection_without_profile_does_not_advertise_single_decode():
    route = InputRouter.route([JD, JD], None)
    assert route.executable_stages == []
    assert route.is_blocked("jd_decode")
    assert not route.can_execute("jd_decode")
    assert "unsupported" in " ".join(route.next_steps)


@pytest.mark.parametrize("jds", [[], (), [None], ["", " "]])
def test_empty_jd_collections_cannot_reach_pipeline(jds):
    with patch("core.job_flow.run_career_review") as pipeline:
        with pytest.raises(InvalidInputError):
            CareerReviewService().run_review(jds, PROFILE)
        pipeline.assert_not_called()


def test_unadvertised_or_conflicting_stages_fail_closed():
    route = RouteDecision(mode=InputMode.JD_AND_PROFILE.value, executable_stages=["approved", "conflict"], blocked_stages=["conflict"])
    assert route.can_execute("approved")
    assert not route.is_blocked("approved")
    for stage in ["unknown_stage", "career_review", "conflict"]:
        assert not route.can_execute(stage)
        assert route.is_blocked(stage)
        with pytest.raises(InvalidInputError):
            route.raise_if_blocked(stage)


@pytest.mark.parametrize("kind", ["text", "path", "dict"])
def test_supported_single_jd_inputs_remain_unmodified(kind, tmp_path):
    value = JD
    if kind == "path":
        value = tmp_path / "jd.txt"
        value.write_text(JD, encoding="utf-8")
    elif kind == "dict":
        value = {"raw_text": JD}
    route = detect_and_route_input(value, PROFILE)
    assert route.mode == InputMode.JD_AND_PROFILE.value
    assert route.can_execute("career_review")
    assert not route.is_blocked("career_review")
    with patch("core.job_flow.run_career_review", return_value={"schema_version": "synthetic"}) as pipeline:
        result = CareerReviewService().run_review(value, PROFILE)
        assert pipeline.call_args.kwargs["jd_text"] == JD
        assert pipeline.call_args.kwargs["profile_dict"] == PROFILE
        assert result["schema_version"] == "synthetic"
        assert result["telemetry"]["traces"][0]["stage_name"] == "career_review"


def test_real_single_jd_review_still_succeeds():
    result = CareerReviewService().run_review(JD, PROFILE)
    assert result["schema_version"] == "career-review.v1"
    assert result["jd_breakdown"]["job_title"] == "行政助理"


@pytest.mark.parametrize("kind", ["json_text", "json_path", "json_path_string", "text_path"])
@pytest.mark.parametrize("items", [[JD, JD], [JD], []])
def test_serialized_jd_arrays_cannot_bypass_batch_rejection(kind, items, tmp_path):
    value = json.dumps(items, ensure_ascii=False)
    if kind != "json_text":
        path = tmp_path / ("batch.txt" if kind == "text_path" else "batch.json")
        path.write_text(value, encoding="utf-8")
        value = str(path) if kind == "json_path_string" else path
    route = detect_and_route_input(value, PROFILE)
    assert isinstance(route.jd, list)
    assert not route.can_execute("career_review")
    assert route.is_blocked("career_review")
    with patch("core.job_flow.run_career_review") as pipeline:
        with pytest.raises(InvalidInputError):
            CareerReviewService().run_review(value, PROFILE)
        pipeline.assert_not_called()
