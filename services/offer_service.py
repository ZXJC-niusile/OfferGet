"""
Offer and Application Services (services/offer_service.py)
=========================================================
Domain services for compensation valuation, trap detection, counter-offers,
material proposals, and application outcome insights.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from core.artifacts import write_json_atomic


class OfferService:
    """Domain service for compensation valuation, trap detection, and tactical counter-offers."""

    def __init__(self, negotiator: Optional[Any] = None):
        self._negotiator = negotiator

    @property
    def negotiator(self) -> Any:
        if self._negotiator is None:
            from core.offer_negotiator import OfferNegotiator

            self._negotiator = OfferNegotiator()
        return self._negotiator

    def evaluate_offer(
        self,
        offer_data: Dict[str, Any],
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluates total compensation package and audits for 6 contract traps."""
        return self.negotiator.evaluate_offer(offer_data, candidate_profile=candidate_profile)

    def generate_counter_offer(
        self,
        offer_data_or_eval: Dict[str, Any],
        target_base: Optional[float] = None,
        competing_offers: Optional[List[Dict[str, Any]]] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generates evidence-anchored counter-offer proposals."""
        if "total_compensation" not in offer_data_or_eval:
            eval_res = self.evaluate_offer(offer_data_or_eval, candidate_profile=candidate_profile)
        else:
            eval_res = offer_data_or_eval

        return self.negotiator.generate_counter_offer(
            evaluation_result=eval_res,
            target_base=target_base,
            competing_offers=competing_offers,
            candidate_profile=candidate_profile,
        )

    def generate_counter_offer_letter(
        self,
        offer_data_or_eval: Dict[str, Any],
        target_base: Optional[float] = None,
        competing_offers: Optional[List[Dict[str, Any]]] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
        lang: str = "zh",
    ) -> str:
        """Generates polite, professional counter-offer communication email/letter."""
        if "total_compensation" not in offer_data_or_eval:
            eval_res = self.evaluate_offer(offer_data_or_eval, candidate_profile=candidate_profile)
        else:
            eval_res = offer_data_or_eval

        return self.negotiator.generate_counter_offer_letter(
            evaluation_result=eval_res,
            target_base=target_base,
            competing_offers=competing_offers,
            candidate_profile=candidate_profile,
            lang=lang,
        )

    def compare_offers(
        self,
        offers: Sequence[Any],
        weights: Optional[Dict[str, float]] = None,
    ) -> Any:
        """Compares multiple offers across real hourly rate, compensation, and 6 dimensions."""
        from core.offer_comparator import MultiOfferComparator

        return MultiOfferComparator.compare_offers(list(offers), weights=weights)


class ProposalService:
    """Human-confirmed material proposal service backed by ApplicationStore."""

    def __init__(self, db_path: Union[str, Path] = "offerget_applications.db"):
        from core.application_tracker import ApplicationStore

        self.store = ApplicationStore(db_path)

    def __enter__(self) -> "ProposalService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        self.store.close()

    def save(self, proposal: Any) -> None:
        self.store.save_material_proposal(proposal)

    def get(self, proposal_id: str) -> Any:
        return self.store.get_material_proposal(proposal_id)

    def list(self, **filters: Any) -> List[Any]:
        return self.store.list_material_proposals(**filters)

    def reject(self, proposal_id: str) -> Any:
        proposal = self.get(proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        proposal.reject()
        self.save(proposal)
        return proposal

    def accept(
        self,
        proposal_id: str,
        profile: Dict[str, Any],
        jd_text: str,
        output_path: Union[str, Path],
        patch_ids: Optional[List[int]] = None,
        build_resume: bool = False,
        resume_theme: str = "classic-tech",
        resume_output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        from core.artifacts import inspect_artifacts, write_json_atomic
        from core.material_proposal import apply_material_proposal, jd_fingerprint, profile_fingerprint

        proposal = self.get(proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)

        try:
            updated = apply_material_proposal(proposal, profile, jd_text, patch_ids=patch_ids)
        except ValueError:
            self.save(proposal)
            raise

        actual_output_path = write_json_atomic(updated, output_path)
        proposal.applied_phase = "profile_written"
        self.save(proposal)

        generated_resumes: Dict[str, str] = {}
        if build_resume:
            from services.resume_service import ResumeService

            out_dir = Path(resume_output_dir or Path(actual_output_path).parent / "proposal_resume")
            built = ResumeService().build_resume(updated, theme=resume_theme, output_dir=out_dir)
            generated_resumes = {key: str(value) for key, value in built.items()}
            proposal.applied_phase = "render_completed"
            self.save(proposal)

        output_paths = {"profile": str(actual_output_path), **generated_resumes}
        artifact_status, artifact_hashes = inspect_artifacts(output_paths)
        missing = [name for name, status in artifact_status.items() if status != "present"]
        if missing:
            raise RuntimeError(f"Generated artifacts unavailable: {', '.join(missing)}")

        version_dict = None
        if proposal.application_id:
            from core.application_tracker import ResumeVersion

            version = ResumeVersion(
                application_id=proposal.application_id,
                proposal_id=proposal.proposal_id,
                profile_hash=profile_fingerprint(updated),
                jd_hash=jd_fingerprint(jd_text),
                theme=resume_theme if build_resume else "profile-only",
                output_paths=output_paths,
                artifact_status=artifact_status,
                artifact_hashes=artifact_hashes,
                accept_phase="completed",
                label=f"Proposal {proposal.proposal_id}",
            )
            self.store.save_resume_version(version)
            version_dict = version.to_dict()

        # Mark completed ONLY after artifacts inspection AND version registration succeed
        proposal.applied_phase = "completed"
        self.save(proposal)

        res_payload: Dict[str, Any] = {
            "proposal": proposal.to_dict(),
            "profile_output": str(actual_output_path),
            "accept_phase": proposal.applied_phase,
            "output_paths": output_paths,
            "artifact_status": artifact_status,
            "artifact_hashes": artifact_hashes,
        }
        if generated_resumes:
            res_payload["generated_resumes"] = generated_resumes
        if version_dict:
            res_payload["resume_version"] = version_dict

        return res_payload


class ApplicationOutcomeService:
    """Records and aggregates evidence-backed application outcome feedback."""

    def __init__(self, db_path: Union[str, Path] = "offerget_applications.db"):
        from core.application_tracker import ApplicationStore

        self.store = ApplicationStore(db_path)

    def __enter__(self) -> "ApplicationOutcomeService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        self.store.close()

    def record(self, outcome: Any) -> Dict[str, Any]:
        return self.store.record_outcome(outcome)

    def list(self, application_id: Optional[str] = None) -> List[Any]:
        return self.store.list_outcomes(application_id)

    def insights(self) -> Dict[str, Any]:
        return self.store.outcome_insights()
