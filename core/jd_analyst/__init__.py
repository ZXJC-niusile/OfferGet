"""
JD Analyst Subsystem (jd_analyst)
=================================
Core modules for deep semantic JD decoding, weighted candidate matching,
red flags detection, interview prediction, and bilingual HTML report generation.
"""

from typing import Optional, Dict, Any

from .models import (
    ThresholdType,
    HardThreshold,
    SkillImportance,
    TechDomain,
    CoreSkill,
    CoreResponsibility,
    ImplicitSignal,
    BusinessPainPoint,
    BoilerplateFiltered,
    DecodedJD,
    GapState,
    GapItem,
    CandidateProfile,
    MatcherResult,
    RedFlagType,
    RedFlagItem,
    RedFlagReport,
    ChannelType,
    ChannelProbability,
    ProbabilityForecast,
    QuestionCategory,
    InterviewQuestion,
    PredictionResult,
)

from .decoder import JDDecoder
from .matcher import JDMatcher
from .redflags import RedFlagDetector
from .predictor import (
    InterviewProbabilityCalculator,
    InterviewTop20Predictor,
    JDPredictor,
)
from .reporter import OfferStrategyReporter


def analyze_jd(
    jd_text: str,
    candidate: Optional[CandidateProfile] = None,
    listing_age_days: int = 15,
    report_output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    All-in-one pipeline: Decodes JD, evaluates candidate match, detects red flags,
    forecasts interview probabilities, predicts top 20 questions, and optionally
    renders/saves a standalone bilingual HTML strategy report.
    """
    decoder = JDDecoder()
    matcher = JDMatcher()
    redflags_detector = RedFlagDetector()
    predictor = JDPredictor()
    reporter = OfferStrategyReporter()

    if candidate is None:
        candidate = CandidateProfile()

    decoded_jd = decoder.decode(jd_text)
    matcher_result = matcher.match(decoded_jd, candidate)
    redflag_report = redflags_detector.detect(decoded_jd)
    prediction_result = predictor.predict(decoded_jd, matcher_result, listing_age_days=listing_age_days)

    html_report = ""
    saved_path = None
    if report_output_path:
        saved_path = reporter.save_report(
            report_output_path,
            decoded_jd,
            candidate,
            matcher_result,
            redflag_report,
            prediction_result,
        )
    else:
        html_report = reporter.generate_html(
            decoded_jd,
            candidate,
            matcher_result,
            redflag_report,
            prediction_result,
        )

    return {
        "decoded_jd": decoded_jd,
        "matcher_result": matcher_result,
        "redflag_report": redflag_report,
        "prediction_result": prediction_result,
        "html_report": html_report,
        "saved_report_path": saved_path,
    }


__all__ = [
    "ThresholdType",
    "HardThreshold",
    "SkillImportance",
    "TechDomain",
    "CoreSkill",
    "CoreResponsibility",
    "ImplicitSignal",
    "BusinessPainPoint",
    "BoilerplateFiltered",
    "DecodedJD",
    "GapState",
    "GapItem",
    "CandidateProfile",
    "MatcherResult",
    "RedFlagType",
    "RedFlagItem",
    "RedFlagReport",
    "ChannelType",
    "ChannelProbability",
    "ProbabilityForecast",
    "QuestionCategory",
    "InterviewQuestion",
    "PredictionResult",
    "JDDecoder",
    "JDMatcher",
    "RedFlagDetector",
    "InterviewProbabilityCalculator",
    "InterviewTop20Predictor",
    "JDPredictor",
    "OfferStrategyReporter",
    "analyze_jd",
]
