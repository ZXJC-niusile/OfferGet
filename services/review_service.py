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
        goal: str = "review",
        proposal_db: Optional[Union[str, Path]] = None,
        application_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Executes full career review pipeline with optional resume building."""
        import time
        from datetime import datetime
        from core.input_router import detect_and_route_input
        from core.run_context import RunContext, compute_fingerprint

        if goal == "interview" and not jd_text:
            jd_text = "简历面试"
        # Automatically route and parse inputs (handles filepaths, dicts, and raw strings)
        parsed_jd, parsed_profile, route_decision = detect_and_route_input(
            jd=jd_text,
            profile=profile_dict,
            fail_fast=False,
            goal=goal,
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
            goal=goal,
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

        if proposal_db:
            self.persist_proposal(result, proposal_db, application_id)

        # Attach telemetry, execution timestamp, and run context to result
        result["telemetry"] = run_ctx.to_dict()
        result["execution_timestamp"] = datetime.now().isoformat()
        result["run_context"] = run_ctx.to_dict()
        result["task_plan"] = {"goal": goal, "stages": route_decision.executable_stages,
                               "next_steps": route_decision.next_steps}

        return result

    def persist_proposal(
        self, result: Dict[str, Any], db_path: Union[str, Path],
        application_id: Optional[str] = None,
    ) -> None:
        """Persist once and derive client-independent state from the stored proposal."""
        from core.application_tracker import ApplicationStore
        from core.material_proposal import MaterialProposal
        from core.job_flow import build_review_summary

        data = dict(result["material_proposal"])
        data["application_id"] = application_id
        proposal = MaterialProposal.from_dict(data)
        proposal.proposal_hash = proposal.compute_hash()
        with ApplicationStore(str(db_path)) as store:
            if application_id and not store.get_application_detail(application_id):
                raise LookupError(f"Application not found for proposal link: {application_id}")
            previous = store.get_material_proposal(proposal.proposal_id)
            if previous and previous.status.value in {"accepted", "rejected"}:
                if previous.proposal_hash != proposal.proposal_hash:
                    raise ValueError("已有确认/拒绝记录，请基于更新后的材料生成新版本。")
                proposal = previous
            else:
                store.save_material_proposal(proposal)
            if application_id:
                store.attach_evidence_snapshot(application_id, result["evidence_snapshot"])
        result["material_proposal"] = proposal.to_dict()
        result["summary"] = build_review_summary(result)

    def refresh_resume(self, result, profile, theme, output_dir):
        """Refresh fixed output paths from user-updated source, never from an unapproved draft."""
        from services.resume_service import ResumeService
        from core.job_flow import build_review_summary

        service = ResumeService()
        if theme == "all":
            files = {name: {kind: str(path) for kind, path in paths.items()}
                     for name, paths in service.build_all(profile, output_dir=output_dir).items()}
            generated = {"files": files, **files.get("modern-navy", {})}
        else:
            generated = {kind: str(path) for kind, path in
                         service.build_resume(profile, theme=theme, output_dir=output_dir).items()}
        # Older review exports also expose a human-readable filename. Refresh an
        # existing same-candidate copy so it cannot silently retain stale content.
        import re
        from core.atomic_writer import safe_save_file
        candidate = profile.get("candidate", {}) if isinstance(profile, dict) else {}
        name = candidate.get("name") or profile.get("name") or "候选人"
        name = re.sub(r'[\\/:*?"<>|]', "_", str(name).strip()) or "个人"
        for kind in ("pdf", "html"):
            named = Path(output_dir) / f"{name}_个人简历.{kind}"
            if generated.get(kind) and named.is_file():
                saved = safe_save_file(named, Path(generated[kind]).read_bytes())
                if not saved.success:
                    raise OSError(saved.error_message)
                generated[f"named_{kind}"] = str(saved.final_path)
        result["generated_resumes"] = {**generated, "theme": theme, "output_dir": str(output_dir)}
        result["summary"] = build_review_summary(result)

    @staticmethod
    def _command_text(command):
        import shlex
        import sys
        if not command:
            return None
        return ("& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in command)
                if sys.platform == "win32" else shlex.join(command))

    def activate_accepted_profile(self, payload, source_profile, jd_text, db_path,
                                  workspace=None, session_path=None):
        """Bind an approved output to its matching review session, never by filename alone."""
        import hashlib
        import json
        import sys

        root = Path(workspace or Path(payload["profile_output"]).parent).resolve()
        session_file = Path(session_path or root / "session.json")
        if not session_file.is_file():
            if workspace or session_path:
                raise FileNotFoundError(
                    f"指定的会话文件不存在或不是文件：{session_file}。请恢复会话文件或修正 --session / --workspace 路径后重试原命令。"
                )
            return None
        try:
            session = self.load_session(session_file)
        except (ValueError, OSError):
            if workspace or session_path:
                raise
            return None
        workflow = session["workflow"]
        root = Path(workspace or workflow.get("workspace") or session_file.parent).resolve()
        source_hash = hashlib.sha256(json.dumps(source_profile, sort_keys=True).encode()).hexdigest()[:12]
        jd_hash = hashlib.sha256(jd_text.strip().encode()).hexdigest()[:12]
        if (not workflow.get("proposal_db") or Path(workflow["proposal_db"]).resolve() != Path(db_path).resolve()
                or session.get("jd_fingerprint") != jd_hash):
            return None
        output = Path(payload["profile_output"]).resolve()
        if hashlib.sha256(output.read_bytes()).hexdigest() != payload["artifact_hashes"]["profile"]:
            raise ValueError("已确认履历文件发生变化，请重新确认后继续。")
        current = json.loads(output.read_text(encoding="utf-8"))
        current_hash = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()[:12]
        if (workflow.get("accepted_proposal_id") == payload["proposal"]["proposal_id"]
                and session.get("profile_fingerprint") == current_hash
                and Path(workflow["inputs"].get("profile", "")).resolve() == output):
            return workflow
        if session.get("profile_fingerprint") != source_hash:
            # A retry after successful activation must preserve subsequent answers.
            if (session.get("profile_fingerprint") == current_hash
                    and Path(workflow["inputs"].get("profile", "")).resolve() == output):
                return workflow
            return None
        inputs = workflow["inputs"]
        workflow.setdefault("source_profile", inputs.get("profile"))
        workflow.setdefault("source_profile_fingerprint", source_hash)
        inputs["profile"] = str(output)
        workflow["accepted_proposal_id"] = payload["proposal"]["proposal_id"]
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "cli.py"),
                   "review", "--workspace", str(root)]
        if session_file.resolve() != root / "session.json":
            command += ["--session", str(session_file.resolve()), "--save-session", str(session_file.resolve())]
        workflow["next_command_args"] = command
        workflow["next_command"] = self._command_text(command)
        session.update({
            "session_id": f"SESSION-{jd_hash}-{current_hash}", "profile_fingerprint": current_hash,
            "questions_snapshot": [], "answers": [], "answer_feedback": [], "evidence_followup": {},
            "generated_questions_count": 0, "answered_questions_count": 0, "evaluated_questions_count": 0,
            "minimum_loop_completed": False, "all_questions_completed": False, "status": "source_updated",
            "question_strategy": "resume",
            "answer_context": None,
        })
        self.save_session(session, session_file)
        return workflow

    def prepare_workflow(
        self, result: Dict[str, Any], workspace: Union[str, Path],
        jd_path: Optional[Union[str, Path]], profile_path: Union[str, Path], *,
        session_path: Union[str, Path], proposal_db: Union[str, Path],
        application_id: Optional[str] = None,
        resume_theme: str = "modern-navy", resume_output_dir: Optional[Union[str, Path]] = None,
        source_profile: Optional[str] = None, source_profile_fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Link review artifacts and provide executable commands without applying a draft."""
        import hashlib
        import json
        import sys
        from core.artifacts import write_json_atomic

        root = Path(workspace).resolve()
        root.mkdir(parents=True, exist_ok=True)
        inputs = {"jd": str(Path(jd_path).resolve()) if jd_path else None, "profile": str(Path(profile_path).resolve())}
        output_dir = str(Path(resume_output_dir or root / "resume").resolve())
        answer_path = root / "answers.json"
        answered = {a["question_id"] for a in result.get("answers", []) if a.get("answer")}
        template = {"answer_context": result.get("answer_context"), "answers": [
            {"question_id": q["question_id"], "answer": ""}
            for q in result.get("interview_questions", []) if q["question_id"] not in answered
        ], **result.get("evidence_followup", {}).get("answer_template", {})}
        if result.get("practice_queue"):
            template["answers"] = [{"question_id": q["question_id"], "answer": ""}
                                   for q in result["practice_queue"]]
        def has_answers(data):
            if not isinstance(data, dict):
                return True
            for key in ("answers", "evidence_answers"):
                items = data.get(key, [])
                if not isinstance(items, list) or any(
                    not isinstance(a, dict) or a.get("answer") or a.get("status") == "no_experience"
                    for a in items
                ):
                    return True
            return False

        # Preserve written answers and provide a fresh template for the current round.
        def read_answers(path):
            if not path.exists():
                return {}
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise ValueError(
                    f"回答文件格式错误：{path}。原文件已保留；请修复 JSON，或将它改名备份后重新运行当前命令以生成模板。"
                ) from exc

        old = read_answers(answer_path)
        if has_answers(old):
            revision = hashlib.sha256(json.dumps({
                "answers": result.get("answers", []),
                "evidence": result.get("evidence_followup", {}).get("answers", []),
                "practice": result.get("practice_queue", []), "template": template,
                "questions": result.get("interview_questions", []),
                "profile": hashlib.sha256(Path(profile_path).read_bytes()).hexdigest(),
                "jd": hashlib.sha256(Path(jd_path).read_bytes()).hexdigest() if jd_path else None,
            }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
            answer_path = root / f"answers-{revision}.json"
        if not answer_path.exists() or not has_answers(read_answers(answer_path)):
            write_json_atomic(template, answer_path, allow_shadow=False)
        # Use the running interpreter and installed/source CLI file, even without a PATH entry.
        entrypoint = Path(__file__).resolve().parents[1] / "cli.py"
        prefix = [sys.executable, str(entrypoint)]
        command = prefix + ["review", "--workspace", str(root)]
        if Path(session_path).resolve() != root / "session.json":
            command += ["--session", str(Path(session_path).resolve()),
                        "--save-session", str(Path(session_path).resolve())]
        kind = result["summary"]["next_action"]["kind"]
        if kind in {"provide_evidence", "answer_question", "follow_up_question", "practice"}:
            command += ["--answers", str(answer_path)]
        elif kind in {"confirm_proposal", "resume_accepted_proposal"}:
            command = prefix + ["proposal", "accept", result["material_proposal"]["proposal_id"],
                       "--db", str(Path(proposal_db).resolve()), "--profile", inputs["profile"],
                       "--jd", inputs["jd"], "--output", str(root / "accepted_profile.json"),
                       "--build-resume", "--resume-theme", resume_theme, "--resume-output-dir", output_dir,
                       "--workspace", str(root), "--session", str(Path(session_path).resolve())]
        elif kind == "export":
            command += ["--build-resume", "--resume-output-dir", output_dir]
        elif kind in {"check_source", "check_threshold", "revise_source", "inspect_export", "provide_resume"}:
            command = []  # A human inspection is required before an executable next step.
        return {"workspace": str(root), "inputs": inputs,
                **({"source_profile": source_profile, "source_profile_fingerprint": source_profile_fingerprint}
                   if source_profile else {}),
                "resume_theme": resume_theme, "resume_output_dir": output_dir,
                "session_path": str(Path(session_path).resolve()),
                "proposal_db": str(Path(proposal_db).resolve()), "application_id": application_id, "answer_path": str(answer_path),
                "answer_template": template,
                "next_command_args": command,
                "next_command": self._command_text(command)}

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
