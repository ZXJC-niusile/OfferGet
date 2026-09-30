"""
Tests for Comprehensive Chinese JD & Resume Rubrics (core/cn_rubrics.py)
========================================================================
Validates all 4 orthogonal rubrics:
1. JD Match Score (100 pts, 7 dimensions, hard-veto behavior)
2. Credibility Score (100 pts, 6 dimensions, superlatives and buzzwords deduction)
3. HR Screen Score (100 pts, 6 dimensions)
4. Interview Readiness Score (100 pts, 6 dimensions)
5. Service integration via CareerReviewService.score_rubrics
"""

import pytest
from core.cn_rubrics import ComprehensiveRubricScorer, RubricScoreCard
from core.services import CareerReviewService
from core.jd_analyst.models import (
    CandidateProfile,
    CoreSkill,
    DecodedJD,
    HardThreshold,
    ImplicitSignal,
    MatcherResult,
)


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        name="张三",
        education_level="硕士",
        years_of_experience=4.0,
        skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
        project_descriptions=[
            "主导电商高并发结算系统重构，QPS 从 1200 提升至 8500，P99 延迟降低 45%",
            "负责分布式任务调度组件设计与落地，日常支撑 5000 万次调用，故障率降低 60%",
            "优化 PostgreSQL 慢查询与连接池，慢 SQL 数量下降 80%，节省服务器成本 30%",
        ],
        raw_resume_text="张三，硕士学历，4年后端开发经验。主导电商结算系统重构，QPS提升至8500，负责调度组件设计，优化数据库性能。",
    )


@pytest.fixture
def sample_jd() -> DecodedJD:
    return DecodedJD(
        raw_text="高级后端工程师，本科及以上，3年经验",
        job_title="高级后端工程师",
        company_or_dept="某科技公司",
        hard_thresholds=[
            HardThreshold(category="education", requirement="本科及以上", min_degree="本科"),
            HardThreshold(category="experience_years", requirement="3年经验", min_years=3.0),
        ],
        core_skills=[
            CoreSkill(name="Python", category="language", importance="must_have", domain="后端开发"),
            CoreSkill(name="Docker", category="tool", importance="must_have", domain="部署"),
            CoreSkill(name="Kubernetes", category="tool", importance="nice_to_have", domain="容器编排"),
        ],
        implicit_signals=[
            ImplicitSignal(
                original_text="能承受高强度业务压力",
                translated_meaning="需要较强抗压能力与交付节奏",
                underlying_risk="加班较多",
                candidate_countermeasure="在过往经历中展示高效交付与项目稳定性",
            ),
        ],
    )


@pytest.fixture
def sample_matcher() -> MatcherResult:
    return MatcherResult(
        must_have_score=1.0,
        nice_to_have_score=0.0,
        hidden_signal_fit=0.85,
        raw_match_score=0.92,
        final_match_score=0.92,
        is_hard_vetoed=False,
        hard_veto_reasons=[],
        breakthrough_advice=[],
        gap_matrix=[],
    )


class TestComprehensiveRubrics:

    def test_score_jd_match_happy_path(
        self,
        sample_jd: DecodedJD,
        sample_candidate: CandidateProfile,
        sample_matcher: MatcherResult,
    ):
        scorer = ComprehensiveRubricScorer()
        card = scorer.score_jd_match(sample_jd, sample_candidate, sample_matcher)

        assert isinstance(card, RubricScoreCard)
        assert card.category == "JD 匹配分"
        assert card.total_score >= 80.0
        assert card.passed_cutoff is True
        assert len(card.dimensions) == 7
        assert not card.risk_warnings

    def test_score_jd_match_hard_veto(
        self,
        sample_jd: DecodedJD,
        sample_candidate: CandidateProfile,
    ):
        vetoed_matcher = MatcherResult(
            must_have_score=0.5,
            nice_to_have_score=0.0,
            hidden_signal_fit=0.5,
            raw_match_score=0.4,
            final_match_score=0.3,
            is_hard_vetoed=True,
            hard_veto_reasons=["学历要求硕士，当前为本科"],
            breakthrough_advice=[],
            gap_matrix=[],
        )
        scorer = ComprehensiveRubricScorer()
        card = scorer.score_jd_match(sample_jd, sample_candidate, vetoed_matcher)

        assert card.passed_cutoff is False
        assert card.dimensions[0].score == 0.0
        assert any("高淘汰风险" in r for r in card.risk_warnings)
        assert len(card.actionable_fixes) > 0

    def test_score_credibility_clean(self, sample_candidate: CandidateProfile):
        scorer = ComprehensiveRubricScorer()
        card = scorer.score_credibility(sample_candidate)

        assert card.category == "可信度分"
        assert card.total_score >= 80.0
        assert card.passed_cutoff is True
        assert len(card.dimensions) == 6
        assert not card.risk_warnings

    def test_score_credibility_superlatives_and_buzzwords(self):
        sloppy_candidate = CandidateProfile(
            name="李四",
            education_level="本科",
            years_of_experience=2.0,
            skills=["Java"],
            project_descriptions=[
                "深度赋能团队，打造行业顶尖且全国唯一的微服务架构，全面打通底层闭环",
            ],
            raw_resume_text="深度赋能团队，打造行业顶尖且全国唯一的微服务架构，首创并颠覆现有方案，全面打通底层闭环，实现降本增效抓手",
        )
        scorer = ComprehensiveRubricScorer()
        card = scorer.score_credibility(sloppy_candidate)

        assert any("合规风险" in r for r in card.risk_warnings)
        # D3 should be penalized for superlatives
        d3 = next(d for d in card.dimensions if d.name == "没有明显夸大")
        assert d3.score < 20.0
        # D4 should be penalized for forbidden buzzwords
        d4 = next(d for d in card.dimensions if d.name == "表达不过度包装")
        assert d4.score < 15.0

    def test_score_hr_screen(self, sample_candidate: CandidateProfile, sample_jd: DecodedJD):
        scorer = ComprehensiveRubricScorer()
        card = scorer.score_hr_screen(sample_candidate, sample_jd)

        assert card.category == "HR 吸引力分"
        assert card.total_score >= 70.0
        assert card.passed_cutoff is True
        assert len(card.dimensions) == 6

    def test_score_interview_readiness(
        self,
        sample_candidate: CandidateProfile,
        sample_matcher: MatcherResult,
    ):
        scorer = ComprehensiveRubricScorer()
        card = scorer.score_interview_readiness(sample_candidate, sample_matcher)

        assert card.category == "面试准备分"
        assert card.total_score >= 75.0
        assert card.passed_cutoff is True
        assert len(card.dimensions) == 6


class TestCareerReviewServiceRubricIntegration:

    def test_service_score_rubrics_full(
        self,
        sample_candidate: CandidateProfile,
        sample_jd: DecodedJD,
    ):
        svc = CareerReviewService()
        results = svc.score_rubrics(sample_candidate, jd_input=sample_jd)

        assert "jd_match" in results
        assert "credibility" in results
        assert "hr_screen" in results
        assert "interview_readiness" in results

        assert results["jd_match"].passed_cutoff is True
        assert results["credibility"].passed_cutoff is True
        assert results["hr_screen"].passed_cutoff is True
        assert results["interview_readiness"].passed_cutoff is True

    def test_service_score_rubrics_profile_only(self, sample_candidate: CandidateProfile):
        svc = CareerReviewService()
        results = svc.score_rubrics(sample_candidate)

        assert "jd_match" not in results
        assert "credibility" in results
        assert "hr_screen" in results
        assert "interview_readiness" in results
