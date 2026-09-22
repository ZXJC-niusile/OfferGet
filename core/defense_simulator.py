"""Backward-compatible defense simulator facade.

OfferGet's defense engine has converged into ``core.defense``.
This module preserves legacy imports from ``core.defense_simulator`` for backward compatibility.
"""

from __future__ import annotations

from core.defense import simulator as _sim

ARCHITECTURE_KEYWORDS = _sim.ARCHITECTURE_KEYWORDS
CONTRIBUTION_KEYWORDS = _sim.CONTRIBUTION_KEYWORDS
ClaimItem = _sim.ClaimItem
DEFAULT_SCENARIO = _sim.DEFAULT_SCENARIO
DefenseCheatSheet = _sim.DefenseCheatSheet
DefenseSimulationResult = _sim.DefenseSimulationResult
DefenseSimulator = _sim.DefenseSimulator
EvidenceStatus = _sim.EvidenceStatus
FollowUpChain = _sim.FollowUpChain
FollowUpRound = _sim.FollowUpRound
INTENSITY_ALIASES = _sim.INTENSITY_ALIASES
IntensityLevel = _sim.IntensityLevel
METRIC_PATTERNS = _sim.METRIC_PATTERNS
NOVELTY_KEYWORDS = _sim.NOVELTY_KEYWORDS
OVERCLAIM_PATTERNS = _sim.OVERCLAIM_PATTERNS
PROHIBITED_TO_SAFE_REPLACEMENTS = _sim.PROHIBITED_TO_SAFE_REPLACEMENTS
ProjectInterrogationChain = _sim.ProjectInterrogationChain
RiskBasis = _sim.RiskBasis
RiskLevel = _sim.RiskLevel
SCENARIO_ROLES = _sim.SCENARIO_ROLES
simulate_project_defense = _sim.simulate_project_defense

__all__ = [
    "ARCHITECTURE_KEYWORDS",
    "CONTRIBUTION_KEYWORDS",
    "ClaimItem",
    "DEFAULT_SCENARIO",
    "DefenseCheatSheet",
    "DefenseSimulationResult",
    "DefenseSimulator",
    "EvidenceStatus",
    "FollowUpChain",
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
]
