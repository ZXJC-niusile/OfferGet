"""
OfferGet Career Review Command Handler:
- cmd_career_review: Goal-oriented review workflow with resumable local sessions
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from core.cli_helpers import (
    read_text,
    load_profile,
    write_json,
    emit_json,
    emit_stderr,
    fail_cli,
)
from services.review_service import CareerReviewService


def print_review_summary(result, show_all=False):
    summary = result["summary"]
    print(summary["conclusion"])
    if summary["key_issues"]:
        print("\n优先处理：")
        for index, issue in enumerate(summary["key_issues"], 1):
            print(f"  {index}. {issue}")
    if summary["pending_changes"]:
        qualifier = "全部展示" if show_all else "预览前 3 项"
        print(f"\n待确认修改（共 {summary['pending_change_count']} 项，{qualifier}）：")
        changes = ([{"patch_id": index, **patch} for index, patch in enumerate(result["material_proposal"]["patches"])]
                   if show_all else summary["pending_changes"])
        for change in changes:
            print(f"  [{change['patch_id']}] {change['reason']}")
            print(f"    原文：{change['before'] or '（新增条目）'}")
            print(f"    建议：{change['after']}")
            if change.get("approval_group"):
                print(f"    需整组确认：{change['approval_group']}")
        if not show_all and summary["pending_change_count"] > 3:
            print("  完整修改可使用 --verbose 或 --json 查看。")
    generated = result.get("generated_resumes", {})
    if generated.get("pdf"):
        print(f"\n简历文件：{generated.get('named_pdf') or generated['pdf']}")
    print(f"\n下一步：{summary['next_action']['message']}")
    workflow = result.get("workflow", {})
    if workflow.get("next_command"):
        print(f"  执行：{workflow['next_command']}")
    if workflow.get("answer_path"):
        print(f"  回答模板：{workflow['answer_path']}")
    question_id = summary["next_action"].get("question_id")
    if question_id is not None:
        print(f"  回答关联：{question_id}")


def cmd_career_review(args):
    """Handler for `offerget review <jd.txt> --profile <profile.json> [--answers <answers.json>] [--session <session.json>] [--save-session <out.json>]`."""
    workspace = Path(args.workspace).resolve() if getattr(args, "workspace", None) else None
    saved_inputs = {}
    saved_workflow = {}
    saved_goal = None
    if workspace:
        existing_session = workspace / "session.json"
        if not getattr(args, "session", None) and existing_session.is_file():
            args.session = str(existing_session)
        if getattr(args, "session", None):
            saved = CareerReviewService().load_session(args.session)
            saved_goal = saved.get("goal")
            saved_workflow = saved.get("workflow", {})
            saved_inputs = saved_workflow.get("inputs", {})
        args.save_session = getattr(args, "save_session", None) or str(existing_session)
        args.proposal_db = getattr(args, "proposal_db", None) or saved_workflow.get("proposal_db") or str(workspace / "proposals.db")
        args.application_id = getattr(args, "application_id", None) or saved_workflow.get("application_id")
        args.output = args.output or str(workspace / "review.json")
    jd_path = args.jd_file or saved_inputs.get("jd")
    profile_path = args.profile or saved_inputs.get("profile")
    # Follow a newly edited original source instead of a stale approved derivative.
    original = saved_workflow.get("source_profile")
    if not args.profile and original and Path(original).is_file():
        original_data = load_profile(original)
        original_hash = hashlib.sha256(json.dumps(original_data, sort_keys=True).encode()).hexdigest()[:12]
        if original_hash != saved_workflow.get("source_profile_fingerprint"):
            profile_path = original
    if profile_path != saved_inputs.get("profile"):
        saved_workflow.pop("source_profile", None)
        saved_workflow.pop("source_profile_fingerprint", None)
    goal_hint = getattr(args, "goal", None) or saved_goal
    if not profile_path or (not jd_path and goal_hint != "interview"):
        fail_cli(args, "invalid_input", "请提供 --profile；定制简历还需要 JD，面试模拟可使用 --goal interview。")
    answers_path = args.answers
    session_path = getattr(args, "session", None)
    save_session_path = getattr(args, "save_session", None)

    if jd_path and not os.path.exists(jd_path):
        fail_cli(args, "input_not_found", f"JD file not found: {jd_path}")
    if not os.path.exists(profile_path):
        fail_cli(args, "input_not_found", f"Profile file not found: {profile_path}")

    jd_text = read_text(jd_path) if jd_path else "简历面试"
    profile_data = load_profile(profile_path)
    if not isinstance(profile_data, dict):
        fail_cli(args, "invalid_input", "Profile must be a JSON object")

    review_service = CareerReviewService()

    session_data = None
    sources_changed = False
    if session_path:
        if not os.path.exists(session_path):
            fail_cli(args, "input_not_found", f"Session file not found: {session_path}")
        session_data = review_service.load_session(session_path)
        if not isinstance(session_data, dict):
            fail_cli(args, "invalid_input", "Session must be a JSON object")

        jd_hash = hashlib.sha256(jd_text.strip().encode("utf-8")).hexdigest()[:12]
        profile_hash = hashlib.sha256(json.dumps(profile_data, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        sess_jd_fp = session_data.get("jd_fingerprint")
        sess_prof_fp = session_data.get("profile_fingerprint")
        sources_changed = bool(session_data.get("status") == "source_updated" or
                               (sess_jd_fp and sess_jd_fp != jd_hash) or
                               (sess_prof_fp and sess_prof_fp != profile_hash))
        if sources_changed:
            if not workspace:
                fail_cli(args, "session_conflict", "Session source changed; use --workspace to refresh the current version")
            if answers_path:
                fail_cli(args, "invalid_answers", "材料已更新，旧回答不能用于新简历。请先刷新会话，再填写新的回答模板。")
            saved_goal = session_data.get("goal")
            session_data = None

    answers_data = None
    if answers_path:
        if not os.path.exists(answers_path):
            fail_cli(args, "input_not_found", f"Answers file not found: {answers_path}")
        try:
            answers_data = json.loads(Path(answers_path).read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            fail_cli(args, "invalid_json",
                     f"回答文件格式错误：{answers_path}。请修复 JSON 后重试；需要新模板时先备份该文件，再不带 --answers 运行当前工作区。{exc}")
        if not isinstance(answers_data, dict):
            fail_cli(args, "invalid_input", "Answers must be a JSON object")
        if session_data:
            valid, errors = review_service.validate_session(session_data, answers_data)
            if not valid:
                fail_cli(args, "invalid_answers", f"Answers do not match session snapshot: {'; '.join(errors)}")

    goal = getattr(args, "goal", None) or (session_data or {}).get("goal") or saved_goal
    if not goal:
        has_interview_answers = bool((answers_data or {}).get("answers"))
        has_evidence_answers = bool((answers_data or {}).get("evidence_answers"))
        goal = "review" if has_interview_answers and has_evidence_answers else "interview" if has_interview_answers else "tailor"

    resume_theme = getattr(args, "resume_theme", None) or saved_workflow.get("resume_theme") or "modern-navy"
    resume_dir = getattr(args, "resume_output_dir", None) or saved_workflow.get("resume_output_dir")
    if workspace and not resume_dir:
        resume_dir = str(workspace / "resume")
    try:
        review_result = review_service.run_review(
            jd_text=jd_text,
            profile_dict=profile_data,
            answers_dict=answers_data,
            build_resume=getattr(args, "build_resume", False),
            resume_theme=resume_theme,
            resume_output_dir=resume_dir,
            session_data=session_data,
            goal=goal,
        )
    except ValueError as e:
        fail_cli(args, "invalid_input", str(e))

    review_result["execution"]["sources_changed"] = sources_changed
    if sources_changed and resume_dir and Path(resume_dir).is_dir() and any(
        path.suffix.lower() in {".pdf", ".html", ".docx"} for path in Path(resume_dir).iterdir()
    ):
        review_service.refresh_resume(review_result, profile_data, resume_theme, resume_dir)

    proposal_db = getattr(args, "proposal_db", None)
    if proposal_db:
        if workspace:
            workspace.mkdir(parents=True, exist_ok=True)
        try:
            review_service.persist_proposal(review_result, proposal_db, getattr(args, "application_id", None))
        except LookupError as e:
            fail_cli(args, "application_not_found", str(e))
        except ValueError as e:
            fail_cli(args, "proposal_conflict", str(e))
        emit_stderr(f"[+] Material proposal saved to {proposal_db}: {review_result['material_proposal']['proposal_id']}")

    if workspace:
        workflow = review_service.prepare_workflow(
            review_result, workspace, jd_path, profile_path,
            session_path=save_session_path, proposal_db=proposal_db,
            application_id=getattr(args, "application_id", None),
            resume_theme=resume_theme, resume_output_dir=resume_dir,
            source_profile=saved_workflow.get("source_profile"),
            source_profile_fingerprint=saved_workflow.get("source_profile_fingerprint"),
        )
        review_result["workflow"] = workflow
    if save_session_path:
        session = review_service.create_session(jd_text, profile_data, review_result, base_session=session_data)
        review_service.save_session(session, save_session_path)
        emit_stderr(f"[+] Review session saved to {save_session_path}")

    if args.output:
        actual_output = write_json(review_result, args.output)
        if args.json:
            emit_stderr(f"[+] Full career review written to {actual_output}")
        else:
            print(f"[+] Full career review written to {actual_output}")

    if args.json:
        emit_json(review_result)
        return

    print_review_summary(review_result, show_all=getattr(args, "verbose", False))
    if not getattr(args, "verbose", False):
        return

    # Formatted terminal output
    print("=" * 72)
    print("        OfferGet · 详细分析       ")
    print("=" * 72)
    jdb = review_result["jd_breakdown"]
    ms = review_result["match_summary"]
    print(f"[*] Target Position:    {jdb.get('job_title', 'AI Engineer')} ({jdb.get('company_or_dept', 'Frontier Team')})")
    print(f"[*] Final Match Score:  {round(ms.get('final_match_score', 0.0) * 100, 1)}% (Raw: {round(ms.get('raw_match_score', 0.0) * 100, 1)}%)")
    if ms.get("is_hard_vetoed"):
        print(f"[!] Hard Veto Triggered: {'; '.join(ms.get('hard_veto_reasons', []))}")
    print("-" * 72)

    print("\n[1] Fact-Grounded Resume Advice (No Hallucination):")
    for idx, adv in enumerate(review_result.get("resume_advice", [])[:5], 1):
        print(f"    {idx}. [{adv['state'].upper()}] -> Action: {adv['action']}")
        print(f"       Requirement: {adv['requirement']}")
        print(f"       Grounding:   {adv['grounding_note']}")
        if adv.get("safe_bullet"):
            print(f"       Safe Bullet: {adv['safe_bullet'][:70]}...")

    print(f"\n[2] 根据当前简历模拟的面试问题（{len(review_result.get('interview_questions', []))} 道）：")
    for q in review_result.get("interview_questions", []):
        print(f"    • [Q{q['question_id']}] [{q['category']}]: {q['question_zh']}")
        print(f"      Intent:  {q['interviewer_intent']}")
        print(f"      Prep:    {q['prep_keypoints'][:65]}...")

    print("\n[3] Structured Interview Answer Debrief & Feedback:")
    for fb in review_result.get("answer_feedback", []):
        print(f"    • [Q{fb['question_id']}] Status: {fb['status']} | Diagnosis: {fb['diagnosis']}")
        print(f"      Analysis:  {fb['analysis']}")
        if fb.get("candidate_answer"):
            print(f"      Answer:    {fb['candidate_answer'][:50]}...")
        print(f"      Takeaway:  {fb['key_takeaway']}")

    print("\n[4] Focus Polish: Interview Defense:")
    pf = review_result.get("polish_focus", {})
    print(f"    • Focus Area: {pf.get('focus_area')}")
    print(f"    • Description: {pf.get('description')}")
    for cp in pf.get("defense_checkpoints", []):
        print(f"      - {cp}")

    if review_result.get("generated_resumes"):
        print("\n[5] Directly Generated Tailored Resumes:")
        gen = review_result["generated_resumes"]
        if "files" in gen:
            for theme_name, fmap in gen["files"].items():
                p = fmap.get("pdf", "")
                print(f"    ✓ [{theme_name:<16}] -> {p}")
        else:
            p = gen.get("pdf", "")
            t = gen.get("theme", "modern-navy")
            print(f"    ✓ [{t:<16}] -> {p}")
    print("=" * 72)
