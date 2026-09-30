"""Deterministic contract for evidence-grounded interview review proposals.

This module validates structured review payloads at the boundary where model or
external output enters OfferGet. It does not generate reviews or mutate source
notes. Evidence excerpts must match the immutable snapshot supplied by caller.
"""

from __future__ import annotations

from typing import Any, Dict, List


MAX_REVIEW_ITEMS = 10
MAX_EVIDENCE_REFS = 5
NOTE_FIELDS = (
    "company",
    "position",
    "round",
    "date",
    "questions",
    "self_reflection",
    "difficulty_points",
    "mood",
)
EVIDENCE_NOTE_FIELDS = frozenset(NOTE_FIELDS[4:])
TOP_LEVEL_FIELDS = frozenset(
    {"summary", "observations", "clarifications", "practice_focuses", "next_questions"}
)
SAFE_SUMMARY = "现有复盘记录不足以支持结论，请补充具体面试问题与作答。"
SAFE_QUESTION = "请补充一段具体的面试问题、你的回答和复盘感受。"


class InterviewReviewContractError(ValueError):
    """Raised when an interview-review proposal violates its evidence contract."""


def build_interview_review_snapshot(note: Dict[str, Any]) -> Dict[str, Any]:
    """Freeze the whitelisted interview-note fields used for grounding."""
    if not isinstance(note, dict):
        raise TypeError("interview note must be a dictionary")
    frozen: Dict[str, str] = {}
    for field in NOTE_FIELDS:
        value = note.get(field, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise TypeError(f"interview note field {field!r} must be text")
        frozen[field] = value
    return {"note": frozen}


def safe_empty_interview_review_proposal() -> Dict[str, Any]:
    return {
        "summary": {"text": SAFE_SUMMARY, "evidence_refs": []},
        "observations": [],
        "clarifications": [
            {"id": "clarification-1", "question": SAFE_QUESTION, "evidence_refs": []}
        ],
        "practice_focuses": [],
        "next_questions": [],
    }


def validate_interview_review_proposal(
    payload: Dict[str, Any], snapshot: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate exact shape, bounded collections, unique IDs and source quotes."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("note"), dict):
        raise InterviewReviewContractError("snapshot must contain a note object")
    note = snapshot["note"]
    if set(note) != set(NOTE_FIELDS) or any(not isinstance(note.get(k), str) for k in NOTE_FIELDS):
        raise InterviewReviewContractError("snapshot note does not match the canonical shape")
    if not isinstance(payload, dict) or set(payload) != TOP_LEVEL_FIELDS:
        raise InterviewReviewContractError("proposal contains missing or unexpected top-level fields")

    summary = payload["summary"]
    if not isinstance(summary, dict) or set(summary) != {"text", "evidence_refs"}:
        raise InterviewReviewContractError("summary must contain exactly text and evidence_refs")
    summary_text, summary_refs = _validate_item_text_refs(summary["text"], summary["evidence_refs"], note)
    note_has_evidence = any(note[field].strip() for field in EVIDENCE_NOTE_FIELDS)
    if not note_has_evidence and summary_text != SAFE_SUMMARY:
        raise InterviewReviewContractError("empty notes cannot support review observations")
    if not summary_refs and summary_text != SAFE_SUMMARY:
        raise InterviewReviewContractError("summary requires at least one grounded evidence reference")

    result: Dict[str, Any] = {
        "summary": {"text": summary_text, "evidence_refs": summary_refs},
        "observations": [],
        "clarifications": [],
        "practice_focuses": [],
        "next_questions": [],
    }
    seen_ids = set()
    for key in ("observations", "clarifications", "practice_focuses", "next_questions"):
        items = payload[key]
        if not isinstance(items, list) or len(items) > MAX_REVIEW_ITEMS:
            raise InterviewReviewContractError(f"{key} must be a list of at most {MAX_REVIEW_ITEMS} items")
        question_items = key in {"clarifications", "next_questions"}
        expected = {"id", "question", "evidence_refs"} if question_items else {"id", "text", "evidence_refs"}
        text_key = "question" if question_items else "text"
        for item in items:
            if not isinstance(item, dict) or set(item) != expected:
                raise InterviewReviewContractError(f"{key} item contains missing or unexpected fields")
            item_id = item["id"]
            if not isinstance(item_id, str) or not item_id.strip() or item_id in seen_ids:
                raise InterviewReviewContractError("item IDs must be unique, non-empty strings")
            seen_ids.add(item_id)
            text, refs = _validate_item_text_refs(item[text_key], item["evidence_refs"], note)
            if not refs and text != SAFE_QUESTION:
                raise InterviewReviewContractError(f"{key} item requires grounded evidence")
            result[key].append({"id": item_id, text_key: text, "evidence_refs": refs})

    if not note_has_evidence:
        safe = safe_empty_interview_review_proposal()
        if result != safe:
            raise InterviewReviewContractError("empty notes cannot support review observations")
    return result


def _validate_item_text_refs(
    text: Any, raw_refs: Any, note: Dict[str, str]
) -> tuple[str, List[Dict[str, str]]]:
    if not isinstance(text, str) or not text.strip():
        raise InterviewReviewContractError("proposal text must be a non-empty string")
    if not isinstance(raw_refs, list) or len(raw_refs) > MAX_EVIDENCE_REFS:
        raise InterviewReviewContractError(f"evidence_refs must contain at most {MAX_EVIDENCE_REFS} items")
    refs: List[Dict[str, str]] = []
    for ref in raw_refs:
        if not isinstance(ref, dict) or set(ref) != {"source", "path", "excerpt"}:
            raise InterviewReviewContractError("evidence reference must contain source, path and excerpt")
        source, path, excerpt = ref["source"], ref["path"], ref["excerpt"]
        if source != "interview_note" or not isinstance(path, str) or not path.startswith("/"):
            raise InterviewReviewContractError("evidence reference has an unsupported source or path")
        field = path[1:]
        if field not in EVIDENCE_NOTE_FIELDS or not isinstance(excerpt, str) or not excerpt.strip():
            raise InterviewReviewContractError("evidence reference is outside the allowed note fields")
        if excerpt not in note[field]:
            raise InterviewReviewContractError("evidence excerpt does not match the frozen interview note")
        refs.append({"source": source, "path": path, "excerpt": excerpt})
    return text.strip(), refs
