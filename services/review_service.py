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
        jd_text: Union[str, Path, Dict[str, Any]],
        profile_dict: Union[Dict[str, Any], str, Path],
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
        import time
        from datetime import datetime
        from core.input_router import detect_and_route_input, parse_input
        from core.run_context import RunContext, compute_fingerprint

        # Automatically route and parse inputs (handles filepaths, dicts, and raw strings)
        parsed_jd, parsed_profile, route_decision = detect_and_route_input(
            jd=jd_text,
            profile=profile_dict,
            fail_fast=False,
        )

        # Validate pipeline routing
        if not route_decision.is_valid:
            route_decision.raise_if_invalid()
        route_decision.raise_if_blocked("career_review")

        # Resolve raw JD string
        if isinstance(parsed_jd, dict):
            raw_jd = str(parsed_jd.get("raw_text") or parsed_jd.get("clean_text") or parsed_jd)
        else:
            raw_jd = str(parsed_jd or "")

        # Initialize RunContext for deterministic telemetry & tracing
        run_ctx = RunContext()
        run_ctx.fingerprint = compute_fingerprint({"jd": raw_jd, "profile": parsed_profile})
        start_time = time.perf_counter()

        from core.job_flow import run_career_review

        result = run_career_review(
            jd_text=raw_jd,
            profile_dict=parsed_profile,
            answers_dict=answers_dict,
            listing_age_days=listing_age_days,
            build_resume=build_resume,
            resume_theme=resume_theme,
            resume_output_dir=resume_output_dir,
            reserve_photo=reserve_photo,
            session_data=session_data,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        run_ctx.record_stage(
            stage_name="career_review",
            elapsed_ms=elapsed_ms,
            summary="Career review execution completed",
        )

        # Enforce contract from core/interview_review_contract.py if note / proposal provided
        interview_note = kwargs.get("interview_note") or kwargs.get("note")
        interview_proposal = kwargs.get("interview_proposal") or kwargs.get("proposal")
        if interview_note and interview_proposal:
            from core.interview_review_contract import (
                build_interview_review_snapshot,
                validate_interview_review_proposal,
            )
            snapshot = build_interview_review_snapshot(interview_note)
            validated_proposal = validate_interview_review_proposal(interview_proposal, snapshot)
            result["interview_review_snapshot"] = snapshot
            result["validated_proposal"] = validated_proposal

        # Attach telemetry, execution timestamp, and run context to result
        result["telemetry"] = run_ctx.to_dict()
        result["execution_timestamp"] = datetime.now().isoformat()
        result["run_context"] = run_ctx.to_dict()

        return result

    def create_session(
        self,
        jd_text: Union[str, Path, Dict[str, Any]],
        profile_dict: Union[Dict[str, Any], str, Path],
        review_result: Dict[str, Any],
        base_session: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Creates a verifiable lightweight JSON session snapshot."""
        from core.input_router import parse_input

        parsed_jd = parse_input(jd_text, expected_type="text")
        if isinstance(parsed_jd, dict):
            raw_jd = str(parsed_jd.get("raw_text") or parsed_jd.get("clean_text") or "")
        else:
            raw_jd = str(parsed_jd or "")
        parsed_profile = parse_input(profile_dict, expected_type="json")

        from core.job_flow import create_review_session

        return create_review_session(
            raw_jd, parsed_profile, review_result, base_session=base_session, **kwargs
        )

    def validate_session(
        self,
        session: Dict[str, Any],
        incoming_answers: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """Validates incoming answers against the session's question snapshot."""
        from core.job_flow import validate_session_answers

        return validate_session_answers(session, incoming_answers)

    def save_session(self, session: Dict[str, Any], output_path: Union[str, Path]) -> None:
        """Atomically saves review session JSON."""
        from core.job_flow import save_review_session

        save_review_session(session, output_path)

    def load_session(self, session_path: Union[str, Path]) -> Dict[str, Any]:
        """Loads review session JSON."""
        from core.job_flow import load_review_session

        return load_review_session(session_path)

    def score_rubrics(
        self,
        profile_data: Union[Dict[str, Any], Any],
        jd_input: Optional[Any] = None,
        matcher_result: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Evaluates Chinese recruitment rubrics (JD match, Credibility, HR Screen, Interview Readiness)."""
        from core.cn_rubrics import ComprehensiveRubricScorer
        from core.jd_compat import profile_to_canonical, to_canonical
        from core.jd_analyst.models import CandidateProfile, DecodedJD
        from core.jd_analyst.matcher import JDMatcher

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
