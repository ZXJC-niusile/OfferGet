import copy
import unittest

from core.interview_review_contract import (
    InterviewReviewContractError,
    SAFE_QUESTION,
    SAFE_SUMMARY,
    build_interview_review_snapshot,
    safe_empty_interview_review_proposal,
    validate_interview_review_proposal,
)


class TestInterviewReviewContract(unittest.TestCase):
    def setUp(self):
        self.note = {
            "company": "Example Co",
            "position": "Backend Engineer",
            "round": "Technical interview",
            "date": "2026-09-24",
            "questions": "How did you scale the API? I explained the cache layer.",
            "self_reflection": "I omitted the baseline and traffic volume.",
            "difficulty_points": "Capacity estimation",
            "mood": "nervous",
            "untrusted_extra": "must not enter snapshot",
        }
        self.snapshot = build_interview_review_snapshot(self.note)
        self.payload = {
            "summary": {
                "text": "回答提到了缓存层，但缺少流量基线。",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/self_reflection",
                    "excerpt": "omitted the baseline",
                }],
            },
            "observations": [{
                "id": "obs-1",
                "text": "复盘记录指出未提供基线。",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/self_reflection",
                    "excerpt": "the baseline",
                }],
            }],
            "clarifications": [{
                "id": "clarify-1",
                "question": "当时的请求量和基线是多少？",
                "evidence_refs": [{
                    "source": "interview_note",
                    "path": "/questions",
                    "excerpt": "How did you scale the API?",
                }],
            }],
            "practice_focuses": [],
            "next_questions": [],
        }

    def test_snapshot_whitelists_and_copies_note_text(self):
        snapshot = build_interview_review_snapshot(self.note)
        self.assertNotIn("untrusted_extra", snapshot["note"])
        self.note["questions"] = "changed after snapshot"
        self.assertEqual(snapshot["note"]["questions"], "How did you scale the API? I explained the cache layer.")

    def test_valid_grounded_payload_is_normalized(self):
        result = validate_interview_review_proposal(self.payload, self.snapshot)
        self.assertEqual(result["summary"]["text"], self.payload["summary"]["text"])
        self.assertEqual(result["observations"][0]["evidence_refs"][0]["path"], "/self_reflection")

    def test_rejects_forged_refs_duplicate_ids_and_extra_fields(self):
        forged = copy.deepcopy(self.payload)
        forged["summary"]["evidence_refs"][0]["excerpt"] = "not in the note"
        with self.assertRaisesRegex(InterviewReviewContractError, "does not match"):
            validate_interview_review_proposal(forged, self.snapshot)

        duplicate = copy.deepcopy(self.payload)
        duplicate["clarifications"][0]["id"] = "obs-1"
        with self.assertRaisesRegex(InterviewReviewContractError, "unique"):
            validate_interview_review_proposal(duplicate, self.snapshot)

        extra = copy.deepcopy(self.payload)
        extra["observations"][0]["score"] = 100
        with self.assertRaisesRegex(InterviewReviewContractError, "unexpected fields"):
            validate_interview_review_proposal(extra, self.snapshot)

    def test_rejects_unsupported_paths_and_unbounded_items(self):
        invalid_path = copy.deepcopy(self.payload)
        invalid_path["summary"]["evidence_refs"][0]["path"] = "/company"
        with self.assertRaisesRegex(InterviewReviewContractError, "outside the allowed"):
            validate_interview_review_proposal(invalid_path, self.snapshot)

        too_many = copy.deepcopy(self.payload)
        too_many["observations"] = [copy.deepcopy(self.payload["observations"][0]) for _ in range(11)]
        with self.assertRaisesRegex(InterviewReviewContractError, "at most 10"):
            validate_interview_review_proposal(too_many, self.snapshot)

    def test_safe_fallback_is_valid_only_for_empty_evidence(self):
        empty_snapshot = build_interview_review_snapshot({})
        safe = safe_empty_interview_review_proposal()
        self.assertEqual(validate_interview_review_proposal(safe, empty_snapshot), safe)
        unsafe = copy.deepcopy(safe)
        unsafe["summary"]["text"] = "根据复盘可以判断表现优秀。"
        with self.assertRaisesRegex(InterviewReviewContractError, "empty notes"):
            validate_interview_review_proposal(unsafe, empty_snapshot)

    def test_safe_phrases_are_exact_contract_values(self):
        safe = safe_empty_interview_review_proposal()
        self.assertEqual(safe["summary"]["text"], SAFE_SUMMARY)
        self.assertEqual(safe["clarifications"][0]["question"], SAFE_QUESTION)


if __name__ == "__main__":
    unittest.main()
