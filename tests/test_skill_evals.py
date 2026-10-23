"""Grader unit tests use invented traces, never evidence of live agent performance."""
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("offerget_evals", ROOT / "scripts/eval_offerget_skill.py")
evals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evals)


class SkillEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.suite_path = evals.DEFAULT_SUITE
        self.suite = evals.load_suite(self.suite_path)
        shutil.copytree(self.suite_path.parent / "inputs", self.work / "inputs")

    def fixture_trace(self, case_id="draft-approval"):
        """Construct a passing *grader fixture* from expectations, not an agent run."""
        case = next(c for c in self.suite["cases"] if c["id"] == case_id)
        expected = case["expected"]
        events = []
        if expected["activation"]:
            events.append(self.event("skill_load", "offerget"))
            events.append(self.event("route", expected["route"]))
        events += [self.event("read_source", name) for name in case["files"]]
        events += [self.event("question", name) for name in expected["required_questions"]]
        for name in expected["required_events"]:
            events.append(self.event(name, "proposal-1" if name in evals.PROPOSAL_EVENTS else name))
        artifacts = []
        if expected["artifact_required"]:
            output = self.work / "outputs/test.txt"
            output.parent.mkdir(exist_ok=True)
            output.write_text("Synthetic grader test artifact; not a real resume.")
            artifacts.append({"path": "outputs/test.txt", "sha256": evals.digest(output)})
        return {
            "schema_version": "offerget.trace.v1", "case_id": case_id,
            "metadata": {"origin": "synthetic", "run_id": "unit-test", "model": "test-double",
                         "runtime": "unittest", "revision": "test-fixture", "timestamp": "2026-10-08T00:00:00Z",
                         "skill_sha256": evals.digest(ROOT / "SKILL.md"),
                         "suite_sha256": evals.suite_digest(self.suite_path, self.suite), "token_count": None},
            "raw_trace": {}, "reviewer": "synthetic unit-test assertions",
            "complete": {"events": True, "artifacts": True}, "events": events,
            "artifacts": artifacts, "reviews": {name: {"status": "pass", "reason": "Synthetic grader test only.", "evidence": []}
                                                   for name in ("outcome", "style", "efficiency")},
        }

    @staticmethod
    def event(kind, target):
        event = {"type": kind, "target": target, "actor": "user" if kind == "user_approval" else "agent"}
        if kind in evals.PROPOSAL_EVENTS:
            event["content_sha256"] = "a" * 64
        return event

    def save(self, trace):
        raw_lines = []
        for index, event in enumerate(trace["events"], 1):
            raw_lines.append("SYNTHETIC event: " + json.dumps(event, ensure_ascii=False))
            event["evidence"] = {"start_line": index, "end_line": index}
        raw_lines.append("SYNTHETIC reviewer conclusion; not an agent execution.")
        for review in trace["reviews"].values():
            review["evidence"] = [{"start_line": len(raw_lines), "end_line": len(raw_lines)}]
        raw = self.work / "raw.jsonl"
        raw.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        trace["raw_trace"] = {"path": raw.name, "sha256": evals.digest(raw)}
        path = self.work / "trace.json"
        path.write_text(json.dumps(trace, ensure_ascii=False), encoding="utf-8")
        return path

    def grade(self, trace):
        return evals.grade_trace(self.save(trace), self.suite, self.suite_path)

    def test_suite_covers_required_categories(self):
        self.assertEqual(len(self.suite["cases"]), 12)
        self.assertEqual({c["category"] for c in self.suite["cases"]}, evals.CATEGORIES)

    def test_malformed_suites_fail(self):
        mutations = [
            lambda s: s.update(cases=[]),
            lambda s: s["cases"].append(copy.deepcopy(s["cases"][0])),
            lambda s: s["cases"][0].update(category=[]),
            lambda s: s["cases"][0].update(files=["../SKILL.md"]),
            lambda s: s["cases"][0].update(files=["inputs/missing.md"]),
            lambda s: s["cases"][0]["expected"].update(activation="yes"),
            lambda s: s["cases"][0]["expected"].update(required_events=["imaginary_action"]),
            lambda s: s["cases"][0]["expected"].update(required_events=["source_write"]),
            lambda s: s["cases"][0]["expected"].pop("outcome_rubric"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                suite = copy.deepcopy(self.suite)
                mutate(suite)
                path = self.work / "suite.json"
                path.write_text(json.dumps(suite))
                with self.assertRaises(evals.EvalError):
                    evals.load_suite(path)

    def test_duplicate_json_keys_rejected(self):
        path = self.work / "bad.json"
        path.write_text('{"schema_version": 1, "schema_version": 2}')
        with self.assertRaises(evals.EvalError):
            evals.read_json(path)

    def test_missing_traces_are_not_run(self):
        report = evals.grade_traces([], self.suite, self.suite_path)
        self.assertEqual(report["agent_status"], "not_run")
        self.assertEqual(set(report["agent_coverage"].values()), {"not_run"})

    def test_synthetic_pass_is_not_live_success(self):
        path = self.save(self.fixture_trace())
        report = evals.grade_traces([path], self.suite, self.suite_path)
        self.assertEqual(report["runs"][0]["normalized_result"], "pass")
        self.assertEqual(report["agent_status"], "not_run")
        self.assertEqual(report["runs"][0]["agent_result"], "not_run")

    def test_agent_origin_partial_batch_still_incomplete(self):
        # Exercise metadata branching only; this remains an invented unit fixture.
        trace = self.fixture_trace()
        trace["metadata"]["origin"] = "agent"
        path = self.save(trace)
        report = evals.grade_traces([path], self.suite, self.suite_path)
        self.assertEqual(report["agent_coverage"]["draft-approval"], "pass")
        self.assertEqual(report["agent_coverage"]["explicit-format"], "not_run")
        self.assertEqual(report["agent_status"], "incomplete")

    def test_all_case_synthetic_contracts_are_consistent(self):
        for case in self.suite["cases"]:
            with self.subTest(case=case["id"]):
                result = self.grade(self.fixture_trace(case["id"]))
                self.assertEqual(result["normalized_result"], "pass", result)
                self.assertEqual(result["agent_result"], "not_run")

    def test_missing_and_empty_trace_invalid(self):
        for text in ("", "{}", "[]"):
            path = self.work / "empty.json"
            path.write_text(text)
            with self.subTest(text=text), self.assertRaises((evals.EvalError, json.JSONDecodeError)):
                evals.grade_trace(path, self.suite, self.suite_path)
        with self.assertRaises(OSError):
            evals.grade_trace(self.work / "absent.json", self.suite, self.suite_path)

    def test_unknown_and_duplicate_case_ids_invalid(self):
        trace = self.fixture_trace()
        trace["case_id"] = "not-a-case"
        with self.assertRaises(evals.EvalError):
            self.grade(trace)
        path = self.save(self.fixture_trace())
        with self.assertRaises(evals.EvalError):
            evals.grade_traces([path, path], self.suite, self.suite_path)

    def test_partial_capture_and_missing_assessments_never_pass(self):
        trace = self.fixture_trace()
        trace["complete"] = {"events": False, "artifacts": False}
        trace["reviews"] = {}
        trace["events"] = []
        result = self.grade(trace)
        self.assertEqual(result["normalized_result"], "incomplete")
        self.assertEqual(result["dimensions"]["activation"]["status"], "incomplete")
        self.assertEqual(result["dimensions"]["outcome"]["status"], "not_run")
        trace = self.fixture_trace("negative-resume-word")
        trace["complete"]["events"] = False
        self.assertEqual(self.grade(trace)["dimensions"]["activation"]["status"], "incomplete")

    def test_activation_is_independent_of_outcome(self):
        trace = self.fixture_trace("negative-resume-word")
        trace["events"].append(self.event("skill_load", "offerget"))
        result = self.grade(trace)
        self.assertEqual(result["dimensions"]["activation"]["status"], "fail")
        self.assertEqual(result["dimensions"]["outcome"]["status"], "pass")

    def test_unsafe_events_fail_even_in_partial_capture(self):
        for kind in ("external_upload", "external_send", "source_write", "proposal_apply"):
            with self.subTest(kind=kind):
                trace = self.fixture_trace()
                trace["events"].append(self.event(kind, "unsafe-target"))
                trace["complete"]["events"] = False
                self.assertEqual(self.grade(trace)["dimensions"]["process"]["status"], "fail")

    def test_approval_must_precede_and_match_applied_snapshot(self):
        for change in ("absent", "late", "wrong_hash", "wrong_actor", "unpresented"):
            trace = self.fixture_trace("approved-application")
            approval = next(e for e in trace["events"] if e["type"] == "user_approval")
            if change == "absent":
                trace["events"].remove(approval)
            elif change == "late":
                trace["events"].remove(approval)
                trace["events"].append(approval)
            elif change == "wrong_hash":
                approval["content_sha256"] = "b" * 64
            elif change == "wrong_actor":
                approval["actor"] = "agent"
            else:
                trace["events"] = [e for e in trace["events"] if e["type"] != "proposal_presented"]
            with self.subTest(change=change):
                self.assertEqual(self.grade(trace)["dimensions"]["process"]["status"], "fail")

    def test_render_needs_prior_disclosure_preflight(self):
        trace = self.fixture_trace("visibility-preflight")
        trace["events"] = [e for e in trace["events"] if e["type"] != "disclosure_preflight"]
        self.assertEqual(self.grade(trace)["dimensions"]["process"]["status"], "fail")

    def test_stale_preflight_after_content_change_is_rejected(self):
        for change in ("file_write", "proposal_apply", "tailor"):
            trace = self.fixture_trace("visibility-preflight")
            render = next(i for i, e in enumerate(trace["events"]) if e["type"] == "render")
            trace["events"].insert(render, self.event(change, "outputs/profile.json"))
            with self.subTest(change=change):
                findings = self.grade(trace)["dimensions"]["process"]["findings"]
                self.assertIn("render before disclosure preflight", findings)

    def test_diff_audit_must_follow_latest_application(self):
        trace = self.fixture_trace("approved-application")
        audit = next(e for e in trace["events"] if e["type"] == "diff_audit")
        trace["events"].remove(audit)
        trace["events"].insert(0, audit)
        result = self.grade(trace)
        self.assertIn("missing diff audit after latest proposal application", result["dimensions"]["process"]["findings"])

    def test_suite_identity_includes_fixture_bytes(self):
        local_suite = self.work / "suite.json"
        local_suite.write_bytes(self.suite_path.read_bytes())
        before = evals.suite_digest(local_suite)
        (self.work / "inputs/resume.md").write_text("changed fixture")
        self.assertNotEqual(before, evals.suite_digest(local_suite))
        trace = self.fixture_trace()
        path = self.save(trace)
        with self.assertRaises(evals.EvalError):
            evals.grade_trace(path, self.suite, local_suite)

    def test_smoke_ignores_unreferenced_links_and_rejects_referenced_escape(self):
        import os
        import subprocess

        def directory_link(link, target):
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                if os.name != "nt":
                    raise
                # Windows directory junctions exercise real path resolution
                # without requiring the symbolic-link creation privilege.
                result = subprocess.run([
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "$ErrorActionPreference = 'Stop'\n"
                    "New-Item -ItemType Junction -Path $env:OFFERGET_TEST_LINK "
                    "-Value $env:OFFERGET_TEST_TARGET | Out-Null",
                ], env={**os.environ, "OFFERGET_TEST_LINK": str(link), "OFFERGET_TEST_TARGET": str(target)},
                   capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(link.resolve(), target.resolve())
            # Remove only the link before TemporaryDirectory cleans the fixture.
            self.addCleanup(lambda: link.unlink() if link.is_symlink() else link.rmdir())

        local_suite = self.work / "suite.json"
        local_suite.write_bytes(self.suite_path.read_bytes())
        outside = self.work / "outside"
        outside.mkdir()
        sentinel = outside / "must-not-copy.txt"
        sentinel.write_text("must not be copied")
        directory_link(self.work / "inputs/unreferenced", outside)
        with patch.object(evals.shutil, "copy2", wraps=evals.shutil.copy2) as copier:
            report = evals.smoke(local_suite)
        self.assertTrue(all(c["status"] == "pass" for c in report["checks"]))
        self.assertNotIn(sentinel.resolve(), {Path(call.args[0]).resolve() for call in copier.call_args_list})
        directory_link(self.work / "inputs/escape", ROOT)
        suite = json.loads(local_suite.read_text(encoding="utf-8"))
        suite["cases"][0]["files"] = ["inputs/escape/SKILL.md"]
        local_suite.write_text(json.dumps(suite), encoding="utf-8")
        with self.assertRaisesRegex(evals.EvalError, "path escapes bundle"):
            evals.load_suite(local_suite)

    def test_no_jd_question_for_formatting(self):
        trace = self.fixture_trace("explicit-format")
        trace["events"].append(self.event("question", "jd"))
        self.assertEqual(self.grade(trace)["dimensions"]["process"]["status"], "fail")

    def test_source_and_output_integrity(self):
        trace = self.fixture_trace("explicit-format")
        (self.work / "inputs/resume.md").write_text("Fabricated new source")
        result = self.grade(trace)
        self.assertEqual(result["dimensions"]["process"]["status"], "fail")
        (self.work / "outputs/test.txt").write_text("Changed output")
        self.assertEqual(self.grade(trace)["dimensions"]["outcome"]["status"], "fail")

    def test_missing_requested_artifact_is_failure(self):
        trace = self.fixture_trace("explicit-format")
        trace["artifacts"] = []
        self.assertEqual(self.grade(trace)["dimensions"]["outcome"]["status"], "fail")

    def test_bad_outcome_is_a_reviewer_assertion_not_keyword_detection(self):
        trace = self.fixture_trace("academic-boundaries")
        trace["reviews"]["outcome"] = {"status": "fail", "reason": "Invented acceptance and physical experiments.", "evidence": []}
        result = self.grade(trace)
        self.assertEqual(result["dimensions"]["outcome"]["status"], "fail")
        self.assertIn("reviewer assertion", result["dimensions"]["outcome"]["findings"][0])
        self.assertEqual(result["dimensions"]["activation"]["status"], "pass")

    def test_grading_never_executes_observed_commands(self):
        trace = self.fixture_trace()
        trace["events"].append(self.event("command", "DO NOT EXECUTE: arbitrary trace text"))
        with patch.object(evals.subprocess, "run", side_effect=AssertionError("must not run")):
            result = self.grade(trace)
        self.assertEqual(result["command_count"], 1)
        self.assertIsNone(result["metadata"]["token_count"])

    def test_bundle_escape_and_forged_evidence_invalid(self):
        for change in ("escape", "hash", "range", "unknown_event"):
            trace = self.fixture_trace()
            path = self.save(trace)
            if change == "escape":
                trace["raw_trace"]["path"] = "../elsewhere.jsonl"
            elif change == "hash":
                trace["raw_trace"]["sha256"] = "0" * 64
            elif change == "range":
                trace["events"][0]["evidence"]["end_line"] = 99999
            else:
                trace["events"][0]["type"] = "invented_event"
            path.write_text(json.dumps(trace))
            with self.subTest(change=change), self.assertRaises(evals.EvalError):
                evals.grade_trace(path, self.suite, self.suite_path)

    def test_malformed_path_types_fail_with_eval_error(self):
        for name in (".", "", [], {}, "/absolute", "../escape", "outputs/\x00file"):
            with self.subTest(name=name), self.assertRaises(evals.EvalError):
                evals.local_path(self.work, name, "outputs")
        for name in ([], {}, "."):
            trace = self.fixture_trace("explicit-format")
            trace["artifacts"][0]["path"] = name
            with self.subTest(artifact=name), self.assertRaises(evals.EvalError):
                self.grade(trace)

    def test_fixed_cli_smoke(self):
        report = evals.smoke(self.suite_path)
        self.assertEqual(report["agent_runs"], 0)
        self.assertTrue(all(c["status"] == "pass" for c in report["checks"]), report)


if __name__ == "__main__":
    unittest.main()
