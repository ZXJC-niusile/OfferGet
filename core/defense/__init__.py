"""
OfferGet Defense Package.
Absorbed and formalized from defense-beating-simulator (MIT).
Provides defense rubrics, 9 weakness dimensions, 2-4 layer follow-up chains,
100-point answer scoring, and 5-step safe answer reframing.
"""

from core.defense.chain import (
    DefenseQuestion,
    DefenseQuestionChain,
    DefenseRole,
    FollowUpChain,
    QuestionChainType,
)
from core.defense.evaluator import (
    NEGATION_MARKERS,
    OVERCLAIMING_PATTERNS,
    DefenseEvaluator,
)
from core.defense.rubrics import (
    AnswerScoreResult,
    AnswerScoringRubric,
    DefenseWeaknessDimension,
    EvidenceStatus,
    RiskBasis,
)

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
]
