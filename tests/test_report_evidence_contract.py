"""Reports must preserve supplied evidence and leave missing assessments unknown."""

import copy
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from core.jd_analyst.models import (
    BoilerplateFiltered,
    BusinessPainPoint,
    CoreResponsibility,
    CoreSkill,
    DecodedJD,
    GapState,
    HardThreshold,
    ImplicitSignal,
)
from core.jd_compat import (
    canonical_to_legacy,
    decode_legacy,
    match_legacy,
    to_canonical,
)
from core.report_generator import (
    _adapt_decoded_jd,
    _adapt_match_result,
    generate_report,
)
from core.security_gate import validate_output_security
from core.validator import validate_bilingual_html

ROOT = Path(__file__).resolve().parents[1]
ADMIN_JD = "职位：行政助理\n工作内容：安排会议，整理档案。"
PROFILE = {"name": "Synthetic Candidate", "skills": [], "education": {}}
FABRICATED = (
    "具备相关工程经验与高可用系统落地成果",
    "有项目经验但简历量化表达较少",
    "缺少大规模生产环境排障案例",
    "具备明确量化指标与项目实践",
    "P99 &lt; 200ms · 达标率 &gt; 99.5%",
)


def test_report_jd_uses_shared_ingress_for_object_json_and_file(tmp_path):
    decoded = decode_legacy(ADMIN_JD)
    path = tmp_path / "jd.txt"
    path.write_text(ADMIN_JD, encoding="utf-8")
    json_path = tmp_path / "decoded.json"
    json_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")
    inputs = [decoded, decoded.canonical, dict(decoded),
              json.loads(json_path.read_text(encoding="utf-8")), path, ADMIN_JD]
    for value in inputs:
        assert _adapt_decoded_jd(value) == to_canonical(value) == decoded.canonical
        assert _adapt_decoded_jd(value).implicit_signals == []
        assert _adapt_decoded_jd(value).business_pain_points == []


def test_canonical_json_preserves_every_supplied_jd_field():
    jd = DecodedJD(
        raw_text="Synthetic raw JD", job_title="Coordinator", company_or_dept="Sample team",
        hard_thresholds=[HardThreshold("degree", "Master degree", min_degree="硕士", min_years=2, required_majors=["CS"])],
        core_skills=[CoreSkill("Planning", "other", "MUST_HAVE", "operations", "Source context")],
        core_responsibilities=[CoreResponsibility("Schedule", "Arrange meetings", "operations", 0.4)],
        implicit_signals=[ImplicitSignal("On call", "Confirm schedule", "Unclear hours", "Ask recruiter")],
        business_pain_points=[BusinessPainPoint("Delays", "Reduce scheduling delays", "Source metric: 2 days")],
        filtered_boilerplates=[BoilerplateFiltered("Friendly team", "Promotional")],
        clean_text="Synthetic clean JD", tech_domains=["operations"],
    )
    for value in [json.loads(json.dumps(asdict(jd))),
                  json.loads(json.dumps(canonical_to_legacy(jd)))]:
        assert _adapt_decoded_jd(value) == jd


def test_legacy_without_canonical_payload_uses_shared_path():
    legacy = dict(decode_legacy(ADMIN_JD))
    legacy.pop("canonical_jd")
    actual = _adapt_decoded_jd(legacy)
    assert actual == to_canonical(legacy)
    assert actual.implicit_signals == actual.business_pain_points == []


@pytest.mark.parametrize("missing", [{}, {"overall_match_score": None},
                                     {"overall_match_score": "nan", "interview_prob": "inf"}])
def test_missing_match_has_no_positive_defaults_or_invented_evidence(tmp_path, missing):
    jd = decode_legacy(ADMIN_JD)
    candidate, matcher, _, prediction = _adapt_match_result(missing, jd.canonical)
    assert candidate.skills == []
    assert matcher.gap_matrix == []
    assert matcher.final_match_score == matcher.raw_match_score == 0
    assert matcher.must_have_score == matcher.nice_to_have_score == matcher.hidden_signal_fit == 0
    assert prediction.probability_forecast.base_max_prob == 0
    assert prediction.probability_forecast.channel_forecasts == {}
    output = Path(generate_report(jd, missing, output_path=tmp_path / "report.html"))
    html = output.read_text(encoding="utf-8")
    assert 'Not Assessed' in html
    assert '缺少可核对的渠道预测' in html
    assert 'All Mandatory Met' not in html
    assert 'Strong Fit' not in html
    for claim in FABRICATED:
        assert claim not in html
    assert validate_bilingual_html(html)["passed"]
    assert validate_output_security(html, "html") == []


def test_empty_gap_matrix_is_authoritative_and_partial_gaps_stay_unknown():
    jd = decode_legacy(ADMIN_JD).canonical
    _, empty, _, _ = _adapt_match_result({"gap_matrix": [], "gaps": [{"title_zh": "Stale gap"}]}, jd)
    assert empty.gap_matrix == []
    _, partial, _, _ = _adapt_match_result({"gaps": [{"title_zh": "Scheduling"}]}, jd)
    gap = partial.gap_matrix[0]
    assert gap.state == GapState.TO_BE_CONFIRMED
    assert gap.score == 0
    assert gap.candidate_evidence == gap.gap_explanation == gap.actionable_advice == ""
    assert partial.matched_count == 0


def test_real_evidence_scores_and_zero_probability_survive_without_mutation(tmp_path):
    jd = decode_legacy(ADMIN_JD)
    result = {
        "candidate_name": "Synthetic Candidate", "overall_match_score": 64,
        "interview_probability_range": [0, 0],
        "breakdown": {"must_have": 60, "nice_have": 70, "hidden_fit": 75},
        "gap_matrix": [{"requirement_name": "Scheduling", "state": "EXPRESSION_GAP", "score": 50,
                        "candidate_evidence": "Arranged 4 meetings <source>",
                        "gap_explanation": "No attendance figures supplied", "actionable_advice": "Confirm scope"}],
    }
    before = copy.deepcopy(result)
    _, matcher, _, prediction = _adapt_match_result(result, jd.canonical)
    assert matcher.final_match_score == 0.64
    assert matcher.must_have_score == 0.6
    assert matcher.gap_matrix[0].score == 0.5
    assert matcher.gap_matrix[0].candidate_evidence == "Arranged 4 meetings <source>"
    assert prediction.probability_forecast.base_min_prob == prediction.probability_forecast.base_max_prob == 0
    assert prediction.probability_forecast.channel_forecasts == {}
    html = Path(generate_report(jd, result, output_path=tmp_path / "report.html")).read_text(encoding="utf-8")
    assert 'Arranged 4 meetings &lt;source&gt;' in html
    assert result == before


def test_canonical_match_json_preserves_raw_score_and_full_gap_evidence():
    result = match_legacy(decode_legacy("职位：Python工程师\n要求：精通Python"), {"name": "Synthetic", "skills": ["Python"]})
    canonical = result["canonical_match"]
    _, matcher, _, _ = _adapt_match_result({"canonical_match": canonical}, to_canonical({}))
    assert matcher.raw_match_score == canonical["raw_match_score"]
    assert matcher.final_match_score == canonical["final_match_score"]
    assert len(matcher.gap_matrix) == len(canonical["gap_matrix"])
    for actual, expected in zip(matcher.gap_matrix, canonical["gap_matrix"]):
        assert asdict(actual) == expected


def test_real_jd_report_cli_keeps_empty_gap_matrix_empty(tmp_path):
    jd = tmp_path / "jd.txt"
    profile = tmp_path / "profile.json"
    output = tmp_path / "report.html"
    jd.write_text(ADMIN_JD, encoding="utf-8")
    profile.write_text(json.dumps(PROFILE), encoding="utf-8")
    assert match_legacy(decode_legacy(ADMIN_JD), PROFILE)["all_gaps"] == []
    result = subprocess.run([sys.executable, str(ROOT / "cli.py"), "jd", "report", str(jd),
                             "--profile", str(profile), "--output", str(output)],
                            cwd=ROOT, text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    html = output.read_text(encoding="utf-8")
    assert '<div class="item-box gap-item-row"' not in html
    for claim in FABRICATED:
        assert claim not in html
    assert "Synthetic Candidate" in html
    assert validate_bilingual_html(html)["passed"]
    assert validate_output_security(html, "html") == []


def test_custom_template_marks_missing_scores_unknown(tmp_path):
    template = tmp_path / "custom.html"
    template.write_text("<html><body>{{MATCH_SCORE_NUM}}|{{INTERVIEW_PROB_NUM}}|{{MUST_HAVE_SCORE}}</body></html>", encoding="utf-8")
    html = Path(generate_report({}, {}, template_path=template, output_path=tmp_path / "out.html")).read_text(encoding="utf-8")
    assert "N/A|N/A|N/A" in html


def test_missing_probability_is_not_generated_from_supplied_match_score():
    _, _, _, prediction = _adapt_match_result({"overall_match_score": 88}, to_canonical({}))
    assert prediction.probability_forecast.base_max_prob == 0
    assert prediction.probability_forecast.channel_forecasts == {}


def test_legacy_layer_evidence_survives_without_invented_ancillary_claims(tmp_path):
    legacy = {"metadata": {"role": "Planner"}, "layers": {
        "layer_2": {"jd_text_zh": "独有技能排期验证XYZ"},
        "layer_4": {"jd_text_zh": "独有轮班要求ABC", "reality_zh": "请确认轮班安排"},
        "layer_5": {"jd_text_zh": "独有成本挑战DEF", "reality_zh": "降低调度成本"},
    }}
    canonical = _adapt_decoded_jd(legacy)
    assert canonical.core_skills[0].name == "独有技能排期验证XYZ"
    assert canonical.implicit_signals[0].underlying_risk == ""
    assert canonical.implicit_signals[0].candidate_countermeasure == ""
    assert canonical.business_pain_points[0].evaluation_metric == ""
    html = Path(generate_report(legacy, {}, output_path=tmp_path / "report.html")).read_text(encoding="utf-8")
    for supplied in ["独有技能排期验证XYZ", "独有轮班要求ABC", "独有成本挑战DEF", "请确认轮班安排", "降低调度成本"]:
        assert supplied in html


def test_supplied_prediction_and_redflags_preserve_object_json_parity(tmp_path):
    from core.jd_analyst.models import (
        ChannelProbability,
        ChannelType,
        PredictionResult,
        ProbabilityForecast,
        RedFlagItem,
        RedFlagReport,
        RedFlagType,
    )

    prediction = PredictionResult(ProbabilityForecast(
        base_min_prob=12, base_max_prob=23, listing_age_days=19,
        age_decay_multiplier=0.7, is_ghost_job_risk=True,
        channel_forecasts={"INTERNAL_REFERRAL": ChannelProbability(
            "示例渠道", "Sample channel", ChannelType.INTERNAL_REFERRAL, 1, 12, 23,
        )}, strategic_summary="Supplied forecast",
    ))
    flags = RedFlagReport(flags=[RedFlagItem(
        RedFlagType.UNBOUNDED_OVERTIME, "源风险", "Source risk", "HIGH",
        "Source quote", "Supplied risk analysis", "Confirm schedule",
    )], overall_risk_level="HIGH", risk_score=71, summary="Supplied risk summary")
    jd = decode_legacy(ADMIN_JD)
    records = {"prediction_result": prediction, "redflag_report": flags}
    serialized = json.loads(json.dumps({key: asdict(value) for key, value in records.items()}))
    before = copy.deepcopy(records)
    html_results = []
    for index, data in enumerate([records, serialized]):
        _, _, actual_flags, actual_prediction = _adapt_match_result(data, jd.canonical)
        assert actual_flags == flags
        assert actual_prediction == prediction
        html_results.append(Path(generate_report(jd, data, output_path=tmp_path / f"report-{index}.html")).read_text(encoding="utf-8"))
    assert html_results[0] == html_results[1]
    assert records == before


@pytest.mark.parametrize("gate", ["false", "true", 0, 1, [], {}])
def test_invalid_gate_values_remain_unknown(tmp_path, gate):
    result = {"hard_vetoed": gate}
    _, matcher, _, _ = _adapt_match_result(result, to_canonical({}))
    assert not matcher.is_hard_vetoed
    html = Path(generate_report({}, result, output_path=tmp_path / "report.html")).read_text(encoding="utf-8")
    assert "All Mandatory Met" not in html
    assert "Veto Triggered" not in html


def test_empty_jd_does_not_claim_low_risk_or_known_posting_age(tmp_path):
    html = Path(generate_report({}, {"interview_prob": 0}, output_path=tmp_path / "report.html")).read_text(encoding="utf-8")
    assert "LOW Risk Level" not in html
    assert "岗位描述扎实，权责清晰" not in html
    assert "核心技术研发岗位" not in html
    assert "Listing Age Adjustment:</span></strong> N/A" in html
    assert "Estimated Probability:</span></strong> 0.0%" in html
    assert "8.3" not in html
    assert "96.0%" not in html
