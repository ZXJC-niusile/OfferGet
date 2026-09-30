"""
OfferGet Defense Package.
OfferGet native interview defense and adversarial questioning system.
Provides defense rubrics, 9 weakness dimensions, 2-4 layer follow-up chains,
100-point answer scoring, 5-step safe answer reframing, and project defense simulation.
"""

from __future__ import annotations

from typing import Any

from .chain import (
    DefenseQuestion,
    DefenseQuestionChain,
    DefenseRole,
    FollowUpChain,
    QuestionChainType,
)
from .evaluator import (
    NEGATION_MARKERS,
    OVERCLAIMING_PATTERNS,
    DefenseEvaluator,
)
from .rubrics import (
    AnswerScoreResult,
    AnswerScoringRubric,
    DefenseWeaknessDimension,
    EvidenceStatus,
    RiskBasis,
)

_SIMULATOR_EXPORTS = {
    "ARCHITECTURE_KEYWORDS",
    "CONTRIBUTION_KEYWORDS",
    "ClaimItem",
    "DEFAULT_SCENARIO",
    "DefenseCheatSheet",
    "DefenseSimulationResult",
    "DefenseSimulator",
    "EvidenceStatus",
    "FollowUpRound",
    "INTENSITY_ALIASES",
    "IntensityLevel",
    "METRIC_PATTERNS",
    "NOVELTY_KEYWORDS",
    "OVERCLAIM_PATTERNS",
    "PROHIBITED_TO_SAFE_REPLACEMENTS",
    "ProjectInterrogationChain",
    "RiskBasis",
    "RiskLevel",
    "SCENARIO_ROLES",
    "simulate_project_defense",
}


def __getattr__(name: str) -> Any:
    if name in _SIMULATOR_EXPORTS:
        from . import simulator
        return getattr(simulator, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AnswerScoreResult",
    "AnswerScoringRubric",
    "DefenseEvaluator",
    "DefenseQuestion",
    "DefenseQuestionChain",
    "DefenseRole",
    "DefenseWeaknessDimension",
    "EvidenceStatus",
    "FollowUpChain",
    "NEGATION_MARKERS",
    "OVERCLAIMING_PATTERNS",
    "QuestionChainType",
    "RiskBasis",
    *_SIMULATOR_EXPORTS,
]
