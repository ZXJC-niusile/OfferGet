"""Persistent application-tracker CLI commands."""

from __future__ import annotations

import json
from core.application_tracker import (
    ApplicationRecord,
    ApplicationStore,
    AppStatus,
    FEEDBACK_TAGS,
    OutcomeRecord,
)
from core.cli_helpers import emit_json, fail_cli, open_application_store


def _store(args) -> ApplicationStore:
    return open_application_store(args)


def cmd_application_add(args) -> None:
    record = ApplicationRecord(
        id=args.application_id,
        target_name=args.company,
        role_or_track=args.role,
        status=AppStatus.from_string(args.status),
        channel=args.channel,
        target_level=args.target_level or "",
        portal_url=args.portal_url or "",
        recruiter_contact=args.recruiter_contact or "",
        notes=args.notes or "",
    )
    with _store(args) as store:
        store.save(record)
    payload = record.to_dict()
    emit_json(payload) if args.json else print(f"Application saved: {record.id}")


def cmd_application_list(args) -> None:
    with _store(args) as store:
        records = [r.to_dict() for r in store.list_all()]
    if args.status:
        expected = AppStatus.from_string(args.status).value
        records = [r for r in records if r["status"] == expected]
    emit_json(records) if args.json else print(json.dumps(records, ensure_ascii=False, indent=2))


def cmd_application_show(args) -> None:
    with _store(args) as store:
        detail = store.get_application_detail(args.application_id)
    if detail is None:
        fail_cli(args, "application_not_found", f"Application not found: {args.application_id}")
    payload = detail
    emit_json(payload) if args.json else print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_application_status(args) -> None:
    with _store(args) as store:
        record = store.get(args.application_id)
        if record is None:
            fail_cli(args, "application_not_found", f"Application not found: {args.application_id}")
        record.transition_status(args.status, note=args.note or "CLI status update")
        store.save(record)
    emit_json(record.to_dict()) if args.json else print(f"Application {record.id}: {record.status.value}")


def cmd_application_snapshot(args) -> None:
    with _store(args) as store:
        record = store.get(args.application_id)
    if record is None:
        fail_cli(args, "application_not_found", f"Application not found: {args.application_id}")
    emit_json(record.evidence_snapshot) if args.json else print(json.dumps(record.evidence_snapshot, ensure_ascii=False, indent=2))


def _parse_feedback_tags(raw: str) -> list:
    tags = [item.strip().lower() for item in (raw or "").split(",") if item.strip()]
    unknown = sorted({t for t in tags if t not in FEEDBACK_TAGS})
    if unknown:
        raise ValueError(
            f"Unknown feedback tag(s): {', '.join(unknown)}; allowed: {', '.join(sorted(FEEDBACK_TAGS))}"
        )
    return tags


def cmd_application_outcome(args) -> None:
    """Records one process outcome with feedback, reflection and next action."""
    try:
        outcome = OutcomeRecord(
            application_id=args.application_id,
            stage=args.stage,
            result=args.result,
            feedback_text=args.feedback or "",
            reflection_text=args.reflection or "",
            next_action_text=args.next_action or "",
            feedback_tags=_parse_feedback_tags(args.tags or ""),
            occurred_at=args.occurred_at or None,
        )
    except ValueError as exc:
        fail_cli(args, "invalid_outcome", str(exc))
    with _store(args) as store:
        try:
            result = store.record_outcome(outcome)
        except ValueError as exc:
            fail_cli(args, "outcome_persistence_error", str(exc))
    payload = {"replayed": result["replayed"], "outcome": result["outcome"]}
    emit_json(payload) if args.json else print(
        f"Outcome recorded: {outcome.application_id} [{outcome.stage.value} -> {outcome.result.value}]"
        + (" (replayed)" if result["replayed"] else "")
    )


def cmd_application_outcomes(args) -> None:
    with _store(args) as store:
        records = store.list_outcomes(args.application_id)
    payload = [r.to_dict() for r in records]
    emit_json(payload) if args.json else print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_application_insights(args) -> None:
    with _store(args) as store:
        payload = store.outcome_insights()
    emit_json(payload) if args.json else print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_application_versions(args) -> None:
    from services.resume_service import ResumeVersionService

    with _store(args) as store:
        service = ResumeVersionService(store.db_path)
        records = [record.to_dict() for record in service.list(args.application_id)]
    emit_json(records) if args.json else print(json.dumps(records, ensure_ascii=False, indent=2))


def cmd_application_version_diff(args) -> None:
    from services.resume_service import ResumeVersionService

    with _store(args) as store:
        service = ResumeVersionService(store.db_path)
        try:
            payload = service.compare(args.before_version_id, args.after_version_id)
        except KeyError as exc:
            fail_cli(args, "resume_version_not_found", f"Resume version not found: {exc.args[0]}")
    emit_json(payload) if args.json else print(json.dumps(payload, ensure_ascii=False, indent=2))
