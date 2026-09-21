"""
Tests for OfferGet Defense Rubrics and Weakness Dimensions.
Verifies enum definitions, 9 weakness dimensions, and 100-point rubric data structures.
"""

import pytest

from core.defense.rubrics import (
    AnswerScoreResult,
    AnswerScoringRubric,
    DefenseWeaknessDimension,
    EvidenceStatus,
    RiskBasis,
)


def test_evidence_status_and_risk_basis_enums():
    assert EvidenceStatus.MATERIAL_SUPPORTED.value == "Material-supported"
    assert EvidenceStatus.MATERIAL_IMPLIED.value == "Material-implied"
    assert EvidenceStatus.MATERIAL_MISSING.value == "Material-missing"

    assert RiskBasis.MATERIAL_DERIVED.value == "Material-derived"
    assert RiskBasis.RISK_INFERRED.value == "Risk-inferred"
    assert RiskBasis.COMBINED.value == "Material-derived + Risk-inferred"


def test_defense_weakness_dimensions_count():
    dims = list(DefenseWeaknessDimension)
    assert len(dims) == 9
    dim_values = {d.value for d in dims}
    assert "项目定位" in dim_values
    assert "技术深度" in dim_values
    assert "数据支撑" in dim_values
    assert "结果展示" in dim_values
    assert "个人贡献" in dim_values
    assert "创新表达" in dim_values
    assert "可复现性" in dim_values
    assert "风险表述" in dim_values
    assert "答辩安全性" in dim_values


def test_answer_scoring_rubric_max_points():
    total = sum(AnswerScoringRubric.MAX_SCORES.values())
    assert total == 100.0
    assert len(AnswerScoringRubric.MAX_SCORES) == 6
    assert AnswerScoringRubric.MAX_SCORES["direct_response"] == 20.0
    assert AnswerScoringRubric.MAX_SCORES["technical_details"] == 20.0
    assert AnswerScoringRubric.MAX_SCORES["acknowledges_boundary"] == 15.0
    assert AnswerScoringRubric.MAX_SCORES["highlights_personal_contribution"] == 15.0
    assert AnswerScoringRubric.MAX_SCORES["avoids_overclaiming"] == 15.0
    assert AnswerScoringRubric.MAX_SCORES["clarity"] == 15.0


def test_answer_score_result_serialization():
    res = AnswerScoreResult(
        total_score=85.5,
        dimension_scores={
            "direct_response": 20.0,
            "technical_details": 18.0,
            "acknowledges_boundary": 15.0,
            "highlights_personal_contribution": 15.0,
            "avoids_overclaiming": 7.5,
            "clarity": 10.0,
        },
        deductions={"avoids_overclaiming": "存在轻度夸大表述。"},
        main_problems=["存在高调措辞"],
        suggestions=["使用客观稳妥词替换"],
        safe_answer="稳妥应答",
    )
    d = res.to_dict()
    assert d["total_score"] == 85.5
    assert d["dimension_scores"]["direct_response"] == 20.0
    assert len(d["main_problems"]) == 1
    assert d["safe_answer"] == "稳妥应答"
