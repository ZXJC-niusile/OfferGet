"""
Career Review Application Service (services/review_service.py)
=============================================================
Domain service for orchestrating career reviews, targeted questions, and tailored resumes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union



class CareerReviewService:
    """Domain service for orchestrating career reviews, targeted questions, and tailored resumes."""

    def run_review(
        self,
        jd_text: Union[str, Path],
        profile_dict: Dict[str, Any],
        answers_dict: Optional[Dict[str, Any]] = None,
        listing_age_days: int = 15,
        build_resume: bool = False,
        resume_theme: str = "modern-navy",
        resume_output_dir: Optional[Union[str, Path]] = None,
        reserve_photo: bool = True,
        session_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Executes full career review pipeline with optional resume building."""
        if isinstance(jd_text, dict):
            raw_jd = str(jd_text.get("raw_text") or jd_text.get("clean_text") or "")
        elif isinstance(jd_text, Path):
            raw_jd = jd_text.read_text(encoding="utf-8")
        else:
            import core.services as facade

            raw_jd = facade.read_text(str(jd_text or ""))

        import core.services as facade

        return facade.run_career_review(
            jd_text=raw_jd,
            profile_dict=profile_dict,
            answers_dict=answers_dict,
            listing_age_days=listing_age_days,
            build_resume=build_resume,
            resume_theme=resume_theme,
            resume_output_dir=resume_output_dir,
            reserve_photo=reserve_photo,
            session_data=session_data,
            **kwargs,
        )

    def create_session(
        self,
        jd_text: Union[str, Path],
        profile_dict: Dict[str, Any],
        review_result: Dict[str, Any],
        base_session: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Creates a verifiable lightweight JSON session snapshot."""
        if isinstance(jd_text, dict):
            raw_jd = str(jd_text.get("raw_text") or jd_text.get("clean_text") or "")
        elif isinstance(jd_text, Path):
            raw_jd = jd_text.read_text(encoding="utf-8")
        else:
            import core.services as facade

            raw_jd = facade.read_text(str(jd_text or ""))
        import core.services as facade

        return facade.create_review_session(
            raw_jd, profile_dict, review_result, base_session=base_session, **kwargs
        )

    def validate_session(
        self,
        session: Dict[str, Any],
        incoming_answers: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """Validates incoming answers against the session's question snapshot."""
        import core.services as facade

        return facade.validate_session_answers(session, incoming_answers)

    def save_session(self, session: Dict[str, Any], output_path: Union[str, Path]) -> None:
        """Atomically saves review session JSON."""
        import core.services as facade

        facade.save_review_session(session, output_path)

    def load_session(self, session_path: Union[str, Path]) -> Dict[str, Any]:
        """Loads review session JSON."""
        import core.services as facade

        return facade.load_review_session(session_path)

    def score_rubrics(
        self,
        profile_data: Union[Dict[str, Any], Any],
        jd_input: Optional[Any] = None,
        matcher_result: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Evaluates Chinese recruitment rubrics (JD match, Credibility, HR Screen, Interview Readiness)."""
        from core.cn_rubrics import ComprehensiveRubricScorer
        from core.jd_compat import profile_to_canonical, to_canonical
        from modules.jd_analyst.models import CandidateProfile, DecodedJD
        from modules.jd_analyst.matcher import JDMatcher

        if isinstance(profile_data, CandidateProfile):
            candidate = profile_data
        else:
            candidate = profile_to_canonical(profile_data)

        decoded_jd: Optional[DecodedJD] = None
        if jd_input is not None:
            if isinstance(jd_input, DecodedJD):
                decoded_jd = jd_input
            else:
                decoded_jd = to_canonical(jd_input)

        if decoded_jd is not None and matcher_result is None:
            matcher_result = JDMatcher().match(decoded_jd, candidate)

        scorer = ComprehensiveRubricScorer()
        results: Dict[str, Any] = {
            "credibility": scorer.score_credibility(candidate),
            "hr_screen": scorer.score_hr_screen(candidate, decoded_jd),
            "interview_readiness": scorer.score_interview_readiness(candidate, matcher_result),
        }
        if decoded_jd is not None and matcher_result is not None:
            results["jd_match"] = scorer.score_jd_match(decoded_jd, candidate, matcher_result)

        return results

    def debrief_real_interview(
        self,
        transcript_text: str,
        target_role: str = "后端开发工程师",
        session_title: str = "真实面试复盘",
        profile_evidence_index: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Debriefs real-world interview transcript, diagnoses blindspots, and generates (N+1) checklist."""
        from core.interview_debrief import PostInterviewDebriefEngine

        return PostInterviewDebriefEngine.debrief(
            transcript_text=transcript_text,
            target_role=target_role,
            session_title=session_title,
            profile_evidence_index=profile_evidence_index,
        )
