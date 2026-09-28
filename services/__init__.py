"""
OfferGet Domain Application Services Package (services/)
=======================================================
Stateless domain application service layer inspired by offerPilot.
Orchestrates domain engines into cohesive, pythonic workflows without
CLI interactions or side-effects.
"""

from __future__ import annotations

from services.jd_service import JDService
from services.profile_service import ProfileService
from services.match_service import MatchService
from services.review_service import CareerReviewService
from services.resume_service import ResumeService, ResumeVersionService
from services.offer_service import (
    OfferService,
    ProposalService,
    ApplicationOutcomeService,
)
from services.report_service import ReportService
from services.academic_service import (
    CommunicationService,
    AcademicService,
    ApplicationGuardService,
)

__all__ = [
    "JDService",
    "ProfileService",
    "MatchService",
    "CareerReviewService",
    "ResumeService",
    "ResumeVersionService",
    "OfferService",
    "ProposalService",
    "ApplicationOutcomeService",
    "ReportService",
    "CommunicationService",
    "AcademicService",
    "ApplicationGuardService",
]
