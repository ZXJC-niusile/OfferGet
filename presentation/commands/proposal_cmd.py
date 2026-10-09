"""Human-confirmed MaterialProposal command handlers."""

from __future__ import annotations

import json
from pathlib import Path

from core.application_tracker import ApplicationStore
from core.cli_helpers import emit_json, fail_cli, load_json, open_application_store, read_text
from services.offer_service import ProposalService


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
    db_path = getattr(args, "db", None) or "offerget_applications.db"
    svc = ProposalService(db_path=db_path)
    try:
        proposal = svc.reject(args.proposal_id)
        payload = proposal.to_dict()
    except KeyError:
        fail_cli(args, "proposal_not_found", f"Proposal not found: {args.proposal_id}")
    finally:
        svc.close()
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

    db_path = getattr(args, "db", None) or "offerget_applications.db"
    svc = ProposalService(db_path=db_path)
    try:
        payload = svc.accept(
            proposal_id=args.proposal_id,
            profile=profile,
            jd_text=jd_text,
            output_path=args.output,
            patch_ids=patch_ids,
            build_resume=getattr(args, "build_resume", False),
            resume_theme=getattr(args, "resume_theme", "modern-navy"),
            resume_output_dir=getattr(args, "resume_output_dir", None),
        )
    except KeyError:
        fail_cli(args, "proposal_not_found", f"Proposal not found: {args.proposal_id}")
    except ValueError as exc:
        fail_cli(args, "proposal_accept_error", str(exc))
    except RuntimeError as exc:
        fail_cli(args, "artifact_validation_failed", str(exc))
    finally:
        svc.close()

    actual_profile_path = payload["profile_output"]
    if args.json:
        emit_json(payload)
    else:
        print(f"Proposal accepted; new profile written to {actual_profile_path}")
        for kind, path in payload.get("generated_resumes", {}).items():
            print(f"  {kind}: {path}")
