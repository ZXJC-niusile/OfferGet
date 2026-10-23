"""Regressions for the concrete failures found during the project audit."""
import json
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch

import pytest

from core.browser_renderer import BrowserRenderer, RenderResult
from core.jd_analyst.matcher import JDMatcher
from core.jd_analyst.models import (
    CandidateProfile, CoreSkill, DecodedJD, GapItem, GapState, MatcherResult,
    QuestionCategory,
)
from core.jd_analyst.predictor import InterviewProbabilityCalculator, InterviewTop20Predictor
from core.jd_compat import match_legacy, to_canonical
from core.report_generator import generate_report
from core.security_gate import validate_output_security


@pytest.mark.parametrize("handler", [
    'onerror="this.style.display=1;nextElementSibling;alert(1)"',
    'ONERROR="this.style.display=1;nextElementSibling;fetch(\'https://example.test\')"',
    'onerror="if (1 > 0) alert(1)"',
    'onerror="&#97;lert(1)"',
    'onerror=alert(1)',
    'onerror="" onerror="alert(1)"',
])
def test_photo_fallback_cannot_whitelist_script(handler):
    assert validate_output_security(f'<img src="invalid" {handler}>')
    assert not validate_output_security('&lt;img onerror="alert(1)"&gt;')


@pytest.mark.parametrize("result", [
    RenderResult(False, 0, "browser failed"),
    RenderResult(True, 0, "invalid count"),
    RenderResult(True, True, "boolean count"),
])
def test_overflow_measurement_does_not_turn_failure_into_zero_overflow(tmp_path, result):
    renderer = BrowserRenderer(browser_path="mock-browser")
    with patch("core.browser_renderer.shutil.which", return_value=None), \
         patch.object(renderer, "render_pdf", return_value=result):
        with pytest.raises(RuntimeError, match="Cannot measure document overflow"):
            renderer.measure_overflow(tmp_path / "source.html")


def test_sparse_jd_does_not_award_or_deduct_missing_dimensions():
    required = CoreSkill("Python", "language", "MUST_HAVE", "software")
    optional = CoreSkill("SQL", "language", "NICE_TO_HAVE", "software")
    profile = CandidateProfile(skills=["Python", "SQL"],
                               project_descriptions=["Implemented Python query endpoint measured 120 QPS; implemented SQL query measured 20 ms"])
    sparse = JDMatcher().match(DecodedJD("Python", "Backend", "", core_skills=[required]), profile)
    explicit = JDMatcher().match(DecodedJD("Python SQL", "Backend", "", core_skills=[required, optional]), profile)
    assert sparse.final_match_score == explicit.final_match_score == 1
    assert sparse.dimension_weights == {"must_have": 1}
    assert set(sparse.unavailable_dimensions) == {"nice_have", "hidden_fit"}
    assert sparse.hidden_signal_fit == 0
    missing = JDMatcher().match(DecodedJD("Python", "Backend", "", core_skills=[required]), CandidateProfile())
    assert missing.final_match_score == 0
    empty = JDMatcher().match(DecodedJD("", "", ""), profile)
    assert empty.final_match_score == 0 and empty.dimension_weights == {}


def test_questions_follow_role_requirements_and_candidate_gaps():
    backend = to_canonical("职位：Python 后端实习生\n任职要求：熟悉 Python、SQLite 和 HTTP 接口开发")
    product = to_canonical("职位：产品经理\n岗位职责：用户调研、需求分析和产品验收")
    predictor = InterviewTop20Predictor()
    result = MatcherResult(1, 0, 0, 1, 1, False)
    backend_questions = predictor.predict(backend, result)
    product_questions = predictor.predict(product, result)
    assert len({q.question_cn for q in product_questions}) == 20
    assert [q.question_cn for q in backend_questions] != [q.question_cn for q in product_questions]
    assert "Python" in " ".join(q.question_cn for q in backend_questions)
    assert not any(token in " ".join(q.question_cn for q in product_questions)
                   for token in ("千亿", "万卡", "vLLM", "PagedAttention"))
    result.gap_matrix = [GapItem("SQLite", "skill", "must_have", GapState.REAL_GAP,
                                0, "", "No evidence", "Confirm actual experience")]
    questions = predictor.predict(backend, result)
    behavioral = [q for q in questions if q.category_type == QuestionCategory.BQ]
    assert "SQLite" in behavioral[0].question_cn
    assert "没有直接经历" in behavioral[0].question_cn


def test_unknown_probabilities_remain_unknown_through_json_and_report(tmp_path):
    matched = match_legacy(to_canonical("职位：Python 开发\n要求：熟悉 Python"), {"skills": ["Python"]})
    serialized = json.loads(json.dumps(matched, ensure_ascii=False))
    assert serialized["interview_prob"] is None
    assert serialized["interview_probability_range"] is None
    assert serialized["should_i_apply"]["probability_range"] is None
    assert serialized["should_i_apply"]["probability_breakdown"] == {}
    forecast = asdict(InterviewProbabilityCalculator().calculate(
        MatcherResult(1, 0, 0, 1, 1, False)))
    assert forecast["estimate_status"] == "unavailable"
    assert forecast["base_max_prob"] is None
    assert forecast["channel_forecasts"] == {}
    html = generate_report(to_canonical("职位：Python 开发\n要求：熟悉 Python"), matched,
                           output_path=tmp_path / "report.html")
    text = Path(html).read_text(encoding="utf-8")
    assert "8 倍" not in text and "95.0%-96.0%" not in text
    assert "Insufficient information" in text or "No calibrated recruitment" in text


@pytest.mark.parametrize("age", [-1, True, 1.5])
def test_invalid_posting_age_is_not_used_as_outcome_evidence(age):
    result = MatcherResult(1, 1, 1, 1, 1, False)
    with pytest.raises(ValueError):
        InterviewProbabilityCalculator().calculate(result, age)


def test_posting_age_and_match_score_do_not_imply_success_odds():
    for score in (0, 0.5, 1):
        result = MatcherResult(score, score, score, score, score, False)
        forecast = InterviewProbabilityCalculator().calculate(result, 90)
        assert asdict(forecast)["base_min_prob"] is None
        assert forecast.channel_forecasts == {}
        assert not forecast.is_ghost_job_risk


def test_empty_contact_fields_do_not_render_stray_separators():
    from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
    vm = ResumeViewModel.from_profile({"name": "Synthetic"}, photo_mode="no-photo")
    header = HtmlThemeRenderer().render_header(vm, "modern-career")
    assert "•" not in header
    assert 'data-field="identity.email"' not in header
    vm = ResumeViewModel.from_profile({"name": "Synthetic", "email": "test@example.test"}, photo_mode="no-photo")
    header = HtmlThemeRenderer().render_header(vm, "modern-career")
    assert "•" not in header
    assert 'data-field="identity.email"' in header


def test_unknown_taxonomy_still_uses_explicit_source_duties():
    predictor = InterviewTop20Predictor()
    result = MatcherResult(0, 0, 0, 0, 0, False)
    jd = DecodedJD("职位：产品经理\n职责：用户调研、需求分析和产品验收\n要求：跨团队协作", "产品经理", "")
    questions = predictor.predict(jd, result)
    assert "用户调研" in questions[0].question_cn
    assert any("跨团队协作" in q.question_cn for q in questions)
    assert not any("PyTorch" in q.question_cn or "千亿" in q.question_cn for q in questions)
