"""
Unit tests for the modular `services/` package.
(tests/test_services_package.py)
"""

import unittest
from pathlib import Path


class TestServicesPackage(unittest.TestCase):
    """Verifies that all domain service classes can be imported from services/ directly."""

    def test_services_init_exports(self):
        from services import (
            JDService,
            ProfileService,
            MatchService,
            CareerReviewService,
            ResumeService,
            ResumeVersionService,
            OfferService,
            ProposalService,
            ApplicationOutcomeService,
            ReportService,
            CommunicationService,
            AcademicService,
            ApplicationGuardService,
        )

        self.assertIsNotNone(JDService)
        self.assertIsNotNone(ProfileService)
        self.assertIsNotNone(MatchService)
        self.assertIsNotNone(CareerReviewService)
        self.assertIsNotNone(ResumeService)
        self.assertIsNotNone(ResumeVersionService)
        self.assertIsNotNone(OfferService)
        self.assertIsNotNone(ProposalService)
        self.assertIsNotNone(ApplicationOutcomeService)
        self.assertIsNotNone(ReportService)
        self.assertIsNotNone(CommunicationService)
        self.assertIsNotNone(AcademicService)
        self.assertIsNotNone(ApplicationGuardService)

    def test_individual_service_modules(self):
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

        jd_s = JDService()
        self.assertTrue(hasattr(jd_s, "decode_jd"))
        self.assertTrue(hasattr(jd_s, "to_canonical"))

        prof_s = ProfileService()
        self.assertTrue(hasattr(prof_s, "normalize"))
        self.assertTrue(hasattr(prof_s, "get_context"))
        self.assertTrue(hasattr(prof_s, "audit_ats"))
        self.assertTrue(hasattr(prof_s, "generate_skill_ledger"))
        self.assertTrue(hasattr(prof_s, "filter_by_visibility"))
        self.assertTrue(hasattr(prof_s, "anonymize"))
        self.assertTrue(hasattr(prof_s, "deanonymize"))
        self.assertTrue(hasattr(prof_s, "verify_facts"))

        match_s = MatchService()
        self.assertTrue(hasattr(match_s, "match"))
        self.assertTrue(hasattr(match_s, "calculate_gap_roi"))

        review_s = CareerReviewService()
        self.assertTrue(hasattr(review_s, "run_review"))
        self.assertTrue(hasattr(review_s, "create_session"))
        self.assertTrue(hasattr(review_s, "save_session"))
        self.assertTrue(hasattr(review_s, "load_session"))
        self.assertTrue(hasattr(review_s, "validate_session"))

        resume_s = ResumeService()
        self.assertTrue(hasattr(resume_s, "build_resume"))
        self.assertTrue(hasattr(resume_s, "build_all"))
        self.assertTrue(hasattr(resume_s, "supported_themes"))

        offer_s = OfferService()
        self.assertTrue(hasattr(offer_s, "evaluate_offer"))
        self.assertTrue(hasattr(offer_s, "generate_counter_offer"))
        self.assertTrue(hasattr(offer_s, "compare_offers"))

        report_s = ReportService()
        self.assertTrue(hasattr(report_s, "generate_offer_strategy_report"))
        self.assertTrue(hasattr(report_s, "validate_report_security"))

        acad_s = AcademicService()
        self.assertTrue(hasattr(acad_s, "audit_entry"))
        self.assertTrue(hasattr(acad_s, "compress_entry"))
        self.assertTrue(hasattr(acad_s, "match_advisor"))
        self.assertTrue(hasattr(acad_s, "generate_checklist"))
        self.assertTrue(hasattr(acad_s, "validate_profile"))
        self.assertTrue(hasattr(acad_s, "simulate_defense"))

    def test_core_services_facade_identity(self):
        """Verifies that core.services exports the exact same classes as services/."""
        import core.services as cs
        import services as s

        self.assertIs(cs.JDService, s.JDService)
        self.assertIs(cs.ProfileService, s.ProfileService)
        self.assertIs(cs.MatchService, s.MatchService)
        self.assertIs(cs.CareerReviewService, s.CareerReviewService)
        self.assertIs(cs.ResumeService, s.ResumeService)
        self.assertIs(cs.ResumeVersionService, s.ResumeVersionService)
        self.assertIs(cs.OfferService, s.OfferService)
        self.assertIs(cs.ProposalService, s.ProposalService)
        self.assertIs(cs.ApplicationOutcomeService, s.ApplicationOutcomeService)
        self.assertIs(cs.ReportService, s.ReportService)
        self.assertIs(cs.CommunicationService, s.CommunicationService)
        self.assertIs(cs.AcademicService, s.AcademicService)
        self.assertIs(cs.ApplicationGuardService, s.ApplicationGuardService)


if __name__ == "__main__":
    unittest.main()
