"""Offline fixture checks and evidence-linked trace grading; never runs an agent."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = ROOT / "evals/offerget/suite.json"
EVENTS = {
    "skill_load", "route", "read_source", "question", "command", "file_write",
    "disclosure_preflight", "render", "inspect_render", "tailor", "academic_audit",
    "proposal_presented", "user_approval", "proposal_apply", "diff_audit",
    "source_write", "external_upload", "external_send",
}
PROPOSAL_EVENTS = {"proposal_presented", "user_approval", "proposal_apply"}
DIMENSIONS = ("activation", "process", "outcome", "style", "efficiency")
CATEGORIES = {"explicit", "implicit", "contextual", "incomplete", "negative", "edge"}
ROUTES = {"format", "tailor", "clarify", "academic", "none"}


class EvalError(ValueError):
    """Malformed fixture or evidence bundle, distinct from a failed evaluation."""


def require(condition, message):
    if not condition:
        raise EvalError(message)


def keys(value, required, optional=()):
    require(isinstance(value, dict), "expected an object")
    require(set(required) <= value.keys(), f"missing fields: {set(required) - value.keys()}")
    require(value.keys() <= set(required) | set(optional), "unknown fields")


def strings(value):
    require(isinstance(value, list), "expected a list")
    require(all(isinstance(s, str) and s.strip() for s in value), "expected nonempty strings")
    require(len(set(value)) == len(value), "duplicate entries")


def enum(value, choices, message):
    require(isinstance(value, str) and value in choices, message)


def nonempty(value):
    require(isinstance(value, str) and bool(value.strip()), "expected nonempty text")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "invalid SHA-256")


def local_path(base, name, prefix=None):
    nonempty(name)
    require("\x00" not in name, "path contains NUL")
    path = Path(name)
    require(bool(path.parts), "path must identify a file")
    require(not path.is_absolute() and ".." not in path.parts, "path must stay inside bundle")
    require(prefix is None or path.parts[0] == prefix, f"path must be under {prefix}/")
    resolved = (base / path).resolve()
    require(resolved.is_relative_to(base.resolve()), "path escapes bundle (possibly via symlink)")
    return resolved


def read_json(path):
    # Reject duplicate keys, which ordinary json.load silently overwrites.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def load_suite(path=DEFAULT_SUITE):
    path = Path(path)
    suite = read_json(path)
    keys(suite, {"schema_version", "cases"})
    require(suite["schema_version"] == "offerget.suite.v1", "unsupported suite version")
    require(isinstance(suite["cases"], list) and suite["cases"], "empty cases")
    ids = set()
    for case in suite["cases"]:
        keys(case, {"id", "category", "prompt", "files", "expected"}, {"follow_up"})
        nonempty(case["id"])
        require(case["id"] not in ids, "duplicate case ID")
        ids.add(case["id"])
        enum(case["category"], CATEGORIES, "unknown category")
        nonempty(case["prompt"])
        if "follow_up" in case:
            nonempty(case["follow_up"])
        strings(case["files"])
        for name in case["files"]:
            require(local_path(path.parent, name, "inputs").is_file(), f"missing fixture: {name}")
        expected = case["expected"]
        keys(expected, {
            "activation", "route", "required_events", "forbidden_events",
            "required_questions", "forbidden_questions", "artifact_required",
            "outcome_rubric", "style_rubric", "efficiency_rubric",
        })
        for field in ("activation", "artifact_required"):
            require(type(expected[field]) is bool, f"{field} must be boolean")
        enum(expected["route"], ROUTES, "unknown route")
        for field in ("required_events", "forbidden_events", "required_questions", "forbidden_questions"):
            strings(expected[field])
        for field in ("required_events", "forbidden_events"):
            require(set(expected[field]) <= EVENTS, "unknown event type")
        for first, second in (("required_events", "forbidden_events"), ("required_questions", "forbidden_questions")):
            require(not set(expected[first]) & set(expected[second]), "contradictory expectations")
        for dimension in ("outcome", "style", "efficiency"):
            nonempty(expected[dimension + "_rubric"])
    return suite


def suite_digest(path, suite=None):
    """Bind the suite plus every referenced fixture path and its exact bytes."""
    path = Path(path)
    suite = load_suite(path) if suite is None else suite
    names = sorted({name for case in suite["cases"] for name in case["files"]})
    manifest = {"suite_json": digest(path), "inputs": {
        name: digest(local_path(path.parent, name, "inputs")) for name in names}}
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


def score(errors=(), complete=True):
    return {"status": "fail" if errors else ("pass" if complete else "incomplete"), "findings": list(errors)}


def grade_trace(path, suite, suite_path):
    """Check normalized observations; evidence meaning remains a reviewer assertion."""
    path = Path(path)
    trace = read_json(path)
    keys(trace, {"schema_version", "case_id", "metadata", "raw_trace", "reviewer", "complete", "events", "artifacts", "reviews"})
    require(trace["schema_version"] == "offerget.trace.v1", "unsupported trace version")
    cases = {c["id"]: c for c in suite["cases"]}
    enum(trace["case_id"], cases, "unknown case ID")
    case = cases[trace["case_id"]]
    expected = case["expected"]
    meta = trace["metadata"]
    keys(meta, {"origin", "run_id", "model", "runtime", "revision", "skill_sha256", "suite_sha256", "timestamp", "token_count"})
    enum(meta["origin"], {"agent", "synthetic"}, "unknown trace origin")
    for field in ("run_id", "model", "runtime", "revision", "timestamp"):
        nonempty(meta[field])
    for field in ("skill_sha256", "suite_sha256"):
        sha(meta[field])
    require(meta["suite_sha256"] == suite_digest(suite_path, suite), "trace refers to a different suite")
    require(meta["token_count"] is None or (type(meta["token_count"]) is int and meta["token_count"] >= 0), "invalid token count")
    nonempty(trace["reviewer"])
    keys(trace["complete"], {"events", "artifacts"})
    require(all(type(v) is bool for v in trace["complete"].values()), "completeness must be boolean")
    keys(trace["raw_trace"], {"path", "sha256"})
    raw = local_path(path.parent, trace["raw_trace"]["path"])
    sha(trace["raw_trace"]["sha256"])
    require(raw.is_file() and digest(raw) == trace["raw_trace"]["sha256"], "raw trace missing or hash mismatch")
    lines = raw.read_text(encoding="utf-8").splitlines()
    require(lines and any(line.strip() for line in lines), "raw trace is empty")

    def evidence(ref):
        keys(ref, {"start_line", "end_line"})
        start, end = ref["start_line"], ref["end_line"]
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), "invalid evidence range")

    events = trace["events"]
    require(isinstance(events, list), "events must be a list")
    for event in events:
        keys(event, {"type", "target", "actor", "evidence"}, {"content_sha256"})
        enum(event["type"], EVENTS, "unknown event type")
        enum(event["actor"], {"agent", "user", "tool"}, "unknown actor")
        nonempty(event["target"])
        evidence(event["evidence"])
        if event["type"] in PROPOSAL_EVENTS:
            sha(event.get("content_sha256"))
        else:
            require("content_sha256" not in event, "proposal hash on unrelated event")
    require(all(a["evidence"]["start_line"] <= b["evidence"]["start_line"] for a, b in zip(events, events[1:])), "events are not chronological")
    observed = {e["type"] for e in events}
    loaded = any(e["type"] == "skill_load" and e["target"] == "offerget" for e in events)
    complete = trace["complete"]["events"]
    activation_errors = []
    if loaded and not expected["activation"]:
        activation_errors.append("OfferGet loaded for a negative case")
    if complete and expected["activation"] and not loaded:
        activation_errors.append("OfferGet was not loaded")
    results = {"activation": score(activation_errors, complete)}

    errors = [f"forbidden event: {name}" for name in sorted(observed & set(expected["forbidden_events"]))]
    if complete:
        errors += [f"missing event: {name}" for name in sorted(set(expected["required_events"]) - observed)]
        routes = [e["target"] for e in events if e["type"] == "route"]
        if expected["route"] != "none" and routes != [expected["route"]]:
            errors.append("missing or unexpected workflow route")
        if expected["route"] == "none" and routes:
            errors.append("unexpected career workflow")
        if expected["route"] in {"format", "tailor", "academic"}:
            reads = {e["target"] for e in events if e["type"] == "read_source"}
            errors += [f"source not read: {name}" for name in case["files"] if name not in reads]
    questions = {e["target"] for e in events if e["type"] == "question"}
    errors += [f"unnecessary question: {q}" for q in sorted(questions & set(expected["forbidden_questions"]))]
    if complete:
        errors += [f"missing question: {q}" for q in sorted(set(expected["required_questions"]) - questions)]
    presented, approvals = set(), set()
    preflight = False
    last_apply, last_diff = -1, -1
    for index, event in enumerate(events):
        kind = event["type"]
        if kind in {"proposal_apply", "source_write", "file_write", "tailor"}:
            preflight = False
        if kind == "proposal_apply":
            last_apply = index
        elif kind == "diff_audit":
            last_diff = index
        binding = (event["target"], event.get("content_sha256"))
        if kind == "proposal_presented":
            presented.add(binding)
        elif kind == "user_approval":
            if event["actor"] != "user" or binding not in presented:
                errors.append("approval lacks an earlier matching proposal or user actor")
            else:
                approvals.add(binding)
        elif kind == "proposal_apply" and binding not in approvals:
            errors.append("proposal applied without earlier matching user approval")
        elif kind == "disclosure_preflight":
            preflight = True
        elif kind == "render" and not preflight:
            errors.append("render before disclosure preflight")
        elif kind == "file_write":
            try:
                local_path(path.parent, event["target"], "outputs")
            except EvalError:
                errors.append("write outside outputs/: " + event["target"])
    if complete and last_apply >= 0 and last_diff <= last_apply:
        errors.append("missing diff audit after latest proposal application")
    artifact_errors = []
    require(isinstance(trace["artifacts"], list), "artifacts must be a list")
    artifact_names = set()
    for artifact in trace["artifacts"]:
        keys(artifact, {"path", "sha256"})
        sha(artifact["sha256"])
        nonempty(artifact["path"])
        require(artifact["path"] not in artifact_names, "duplicate artifact path")
        artifact_names.add(artifact["path"])
        artifact_path = local_path(path.parent, artifact["path"], "outputs")
        if not artifact_path.is_file() or digest(artifact_path) != artifact["sha256"]:
            artifact_errors.append("artifact missing or changed: " + artifact["path"])
    artifacts_complete = trace["complete"]["artifacts"]
    if artifacts_complete and expected["artifact_required"] and not artifact_names:
        artifact_errors.append("requested artifact absent")
    for name in case["files"]:
        after = local_path(path.parent, name, "inputs")
        if after.is_file():
            if digest(after) != digest(local_path(Path(suite_path).parent, name, "inputs")):
                errors.append("source changed: " + name)
        elif artifacts_complete:
            errors.append("missing post-run source snapshot: " + name)
    results["process"] = score(errors, complete and artifacts_complete)
    require(isinstance(trace["reviews"], dict), "reviews must be an object")
    require(set(trace["reviews"]) <= {"outcome", "style", "efficiency"}, "unknown review dimension")
    for dimension in ("outcome", "style", "efficiency"):
        review = trace["reviews"].get(dimension)
        if review is None:
            results[dimension] = {"status": "not_run", "findings": ["independent assessment absent"]}
        else:
            keys(review, {"status", "reason", "evidence"})
            enum(review["status"], {"pass", "fail", "incomplete"}, "unknown assessment status")
            nonempty(review["reason"])
            require(isinstance(review["evidence"], list) and review["evidence"], "assessment evidence missing")
            for ref in review["evidence"]:
                evidence(ref)
            results[dimension] = {"status": review["status"], "findings": ["reviewer assertion: " + review["reason"]]}
    if artifact_errors:
        results["outcome"]["status"] = "fail"
        results["outcome"]["findings"].extend(artifact_errors)
    elif not artifacts_complete and results["outcome"]["status"] == "pass":
        results["outcome"]["status"] = "incomplete"
    statuses = {r["status"] for r in results.values()}
    overall = "fail" if "fail" in statuses else ("pass" if statuses == {"pass"} else "incomplete")
    return {"case_id": case["id"], "metadata": meta, "reviewer": trace["reviewer"],
            "dimensions": results, "normalized_result": overall,
            "agent_result": overall if meta["origin"] == "agent" else "not_run",
            "command_count": sum(e["type"] == "command" for e in events),
            "command_count_complete": complete}


def grade_traces(paths, suite, suite_path):
    runs = [grade_trace(Path(p), suite, suite_path) for p in paths]
    ids = [r["case_id"] for r in runs]
    require(len(ids) == len(set(ids)), "duplicate case IDs in trace batch; use separate batches for repeats")
    by_id = {r["case_id"]: r for r in runs}
    coverage = {c["id"]: by_id[c["id"]]["agent_result"] if c["id"] in by_id else "not_run" for c in suite["cases"]}
    states = set(coverage.values())
    status = "fail" if "fail" in states else ("pass" if states == {"pass"} else ("not_run" if states == {"not_run"} else "incomplete"))
    return {"mode": "trace_grading", "runs": runs, "agent_status": status,
            "agent_coverage": coverage,
            "note": "No agent was executed. Human/adapter annotations are assertions, not automatically proven facts."}


def smoke(suite_path=DEFAULT_SUITE):
    """Fixed local CLI calls only. Never execute commands from suites or traces."""
    suite_path = Path(suite_path)
    suite = load_suite(suite_path)
    fixture_names = sorted({name for case in suite["cases"] for name in case["files"]})
    checks = []
    with tempfile.TemporaryDirectory(prefix="offerget-skill-eval-") as temp:
        work = Path(temp)
        before = {}
        for name in fixture_names:
            source = local_path(suite_path.parent, name, "inputs")
            destination = work / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            before[destination] = digest(destination)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        commands = [
            ("parse", ["profile", "parse", "inputs/resume.md", "--output", "profile.json", "--json"]),
            ("draft_review", ["review", "inputs/target_jd.txt", "--profile", "inputs/profile.json", "--output", "review.json", "--json"]),
            ("academic_guard", ["baoyan", "audit", "Gazebo 仿真冒充产线实测，论文在投却写为已录用。", "--role", "辅助成员", "--tier", "简历版", "--json"]),
        ]
        for name, args in commands:
            try:
                run = subprocess.run([sys.executable, str(ROOT / "cli.py"), *args], cwd=work,
                                     env=env, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
                data = json.loads(run.stdout)
                ok = run.returncode == 0
                if name == "parse":
                    ok = ok and data.get("profile", {}).get("candidate", {}).get("name") == "Alex Example" and (work / "profile.json").is_file()
                elif name == "draft_review":
                    ok = ok and data.get("material_proposal", {}).get("status") == "draft" and not data.get("generated_resumes") and (work / "review.json").is_file()
                else:
                    ok = ok and data.get("checks", {}).get("simulation_vs_real_cluster", {}).get("passed") is False and data.get("checks", {}).get("expected_vs_acquired_outcomes", {}).get("passed") is False
                checks.append({"name": name, "status": "pass" if ok else "fail", "returncode": run.returncode})
            except (OSError, UnicodeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                checks.append({"name": name, "status": "fail", "error": str(exc)})
        unchanged = all(p.is_file() and digest(p) == value for p, value in before.items())
        checks.append({"name": "sources_unchanged", "status": "pass" if unchanged else "fail"})
    return {"mode": "cli_smoke", "checks": checks, "agent_runs": 0,
            "note": "Deterministic CLI contracts only; no activation, factual-quality, or rendering evaluation."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate fixture structure and local input paths")
    commands.add_parser("smoke", help="Run three fixed CLI calls in a temporary workspace")
    grade = commands.add_parser("grade", help="Grade normalized traces; no traces means all cases not run")
    grade.add_argument("traces", nargs="*", type=Path)
    args = parser.parse_args(argv)
    try:
        suite = load_suite(args.suite)
        if args.command == "validate":
            report = {"mode": "static_validation", "status": "pass", "cases": len(suite["cases"]), "suite_sha256": suite_digest(args.suite, suite), "agent_runs": 0}
        elif args.command == "smoke":
            report = smoke(args.suite)
        else:
            report = grade_traces(args.traces, suite, args.suite)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.command == "smoke":
            return 0 if all(c["status"] == "pass" for c in report["checks"]) else 1
        if args.command == "grade":
            return 0 if report["agent_status"] == "pass" else 1
        return 0
    except (EvalError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
