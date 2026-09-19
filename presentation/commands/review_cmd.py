"""
OfferGet Career Review Command Handler:
- cmd_career_review: Full-lifecycle career review pipeline (Track 2 closed-loop)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.cli_helpers import (
    read_text,
    load_json,
    write_json,
    emit_json,
    emit_stderr,
)
from core.services import (
    run_career_review,
    create_review_session,
    save_review_session,
    load_review_session,
    validate_session_answers,
)


def cmd_career_review(args):
    """Handler for `offerget review <jd.txt> --profile <profile.json> [--answers <answers.json>] [--session <session.json>] [--save-session <out.json>]`."""
    jd_path = args.jd_file
    profile_path = args.profile
    answers_path = args.answers
    session_path = getattr(args, "session", None)
    save_session_path = getattr(args, "save_session", None)

    if not os.path.exists(jd_path):
        emit_stderr(f"[-] Error: JD file not found: {jd_path}")
        sys.exit(1)
    if not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)

    session_data = None
    if session_path:
        if not os.path.exists(session_path):
            emit_stderr(f"[-] Error: Session file not found: {session_path}")
            sys.exit(1)
        session_data = load_review_session(session_path)

    answers_data = None
    if answers_path:
        if not os.path.exists(answers_path):
            emit_stderr(f"[-] Error: Answers file not found: {answers_path}")
            sys.exit(1)
        answers_data = load_json(answers_path)
        if session_data:
            valid, errors = validate_session_answers(session_data, answers_data)
            if not valid:
                emit_stderr(f"[-] Warning: Answers do not match session snapshot: {'; '.join(errors)}")

    jd_text = read_text(jd_path)
    profile_data = load_json(profile_path)

    review_result = run_career_review(
        jd_text=jd_text,
        profile_dict=profile_data,
        answers_dict=answers_data,
        build_resume=getattr(args, "build_resume", False),
        resume_theme=getattr(args, "resume_theme", "modern-navy"),
        resume_output_dir=getattr(args, "resume_output_dir", None),
    )

    if save_session_path:
        session = create_review_session(jd_text, profile_data, review_result)
        save_review_session(session, save_session_path)
        if args.json:
            emit_stderr(f"[+] Review session saved to {save_session_path}")
        else:
            print(f"[+] Review session saved to {save_session_path}")

    if args.output:
        write_json(review_result, args.output)
        if args.json:
            emit_stderr(f"[+] Full career review written to {args.output}")
        else:
            print(f"[+] Full career review written to {args.output}")

    if args.json:
        emit_json(review_result)
        return

    # Formatted terminal output
    print("=" * 72)
    print("        OfferGet · Full-Lifecycle Career Review (career-review.v1)       ")
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

    print("\n[2] Exactly 3 Targeted Interview Defense Questions:")
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
