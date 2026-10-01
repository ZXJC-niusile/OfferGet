"""Human-confirmed MaterialProposal command handlers."""

from __future__ import annotations

import json
from pathlib import Path

from core.application_tracker import ApplicationStore, ResumeVersion
from core.artifacts import inspect_artifacts
from core.cli_helpers import emit_json, fail_cli, load_json, open_application_store, read_text, write_json
from core.material_proposal import apply_material_proposal, jd_fingerprint, profile_fingerprint
from services.resume_service import ResumeService


def _store(args) -> ApplicationStore:
    return open_application_store(args)


def cmd_proposal_show(args) -> None:
    with _store(args) as store:
        proposal = store.get_material_proposal(args.proposal_id)
    if proposal is None:
        fail_cli(args, "proposal_not_found", f"Proposal not found: {args.proposal_id}")
    payload = proposal.to_dict()
    emit_json(payload) if args.json else print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_proposal_list(args) -> None:
    with _store(args) as store:
        proposals = [p.to_dict() for p in store.list_material_proposals(
            args.status, args.application_id, args.company, args.role
        )]
    emit_json(proposals) if args.json else print(json.dumps(proposals, ensure_ascii=False, indent=2))


def cmd_proposal_reject(args) -> None:
    with _store(args) as store:
        proposal = store.get_material_proposal(args.proposal_id)
        if proposal is None:
            fail_cli(args, "proposal_not_found", f"Proposal not found: {args.proposal_id}")
        proposal.reject()
        store.save_material_proposal(proposal)
        payload = proposal.to_dict()
    emit_json(payload) if args.json else print(f"Proposal rejected: {args.proposal_id}")


def cmd_proposal_accept(args) -> None:
    profile_path = Path(args.profile)
    jd_path = Path(args.jd)
    if not profile_path.exists() or not jd_path.exists():
        fail_cli(args, "input_not_found", "Profile or JD file not found")
    profile = load_json(str(profile_path))
    jd_text = read_text(str(jd_path))
    patch_ids = None
    if args.patch_ids:
        try:
            patch_ids = [int(item) for item in args.patch_ids.split(",") if item.strip()]
        except ValueError:
            fail_cli(args, "invalid_patch_ids", "--patch-ids must be comma-separated integers")
    with _store(args) as store:
        proposal = store.get_material_proposal(args.proposal_id)
        if proposal is None:
            fail_cli(args, "proposal_not_found", f"Proposal not found: {args.proposal_id}")
        try:
            updated_profile = apply_material_proposal(proposal, profile, jd_text, patch_ids=patch_ids)
        except ValueError as exc:
            store.save_material_proposal(proposal)
            fail_cli(args, "proposal_accept_error", str(exc))
        store.save_material_proposal(proposal)

    actual_profile_path = write_json(updated_profile, args.output)
    proposal.applied_phase = "profile_written"
    with _store(args) as store:
        store.save_material_proposal(proposal)

    payload = {"proposal": proposal.to_dict(), "profile_output": str(actual_profile_path)}
    generated_resumes = {}
    if args.build_resume:
        output_dir = Path(args.resume_output_dir or Path(actual_profile_path).parent / "proposal_resume")
        built = ResumeService().build_resume(updated_profile, theme=args.resume_theme, output_dir=output_dir)
        generated_resumes = {key: str(value) for key, value in built.items()}
        payload["generated_resumes"] = generated_resumes
        proposal.applied_phase = "render_completed"
        with _store(args) as store:
            store.save_material_proposal(proposal)

    output_paths = {"profile": str(actual_profile_path), **generated_resumes}
    artifact_status, artifact_hashes = inspect_artifacts(output_paths)
    missing = [name for name, status in artifact_status.items() if status != "present"]
    if missing:
        fail_cli(args, "artifact_validation_failed", f"Generated artifacts unavailable: {', '.join(missing)}")
    proposal.applied_phase = "completed"
    with _store(args) as store:
        store.save_material_proposal(proposal)

    payload["accept_phase"] = proposal.applied_phase
    payload["artifact_status"] = artifact_status
    payload["artifact_hashes"] = artifact_hashes
    if proposal.application_id:
        version = ResumeVersion(
            application_id=proposal.application_id,
            proposal_id=proposal.proposal_id,
            profile_hash=profile_fingerprint(updated_profile),
            jd_hash=jd_fingerprint(jd_text),
            theme=args.resume_theme if args.build_resume else "profile-only",
            output_paths=output_paths,
            artifact_status=artifact_status,
            artifact_hashes=artifact_hashes,
            accept_phase=proposal.applied_phase,
            label=f"Proposal {proposal.proposal_id}",
        )
        with _store(args) as store:
            store.save_resume_version(version)
        payload["resume_version"] = version.to_dict()
    emit_json(payload) if args.json else print(f"Proposal accepted; new profile written to {actual_profile_path}")
