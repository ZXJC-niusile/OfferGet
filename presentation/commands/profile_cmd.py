"""
OfferGet Profile Command Handlers (presentation/commands/profile_cmd.py)
========================================================================
CLI command handlers for candidate profile operations, including auto-ingestion
and conversion from Markdown or plain-text resumes into SSOT Profile JSON.
"""

from __future__ import annotations

import os
from typing import Any

from core.cli_helpers import (
    load_profile,
    write_json,
    emit_json,
    fail_cli,
)


def cmd_profile_parse(args: Any) -> None:
    """Handler for `offerget profile parse <resume_file> [--output <json_file>] [--json]`."""
    input_path = args.input_file
    if not os.path.exists(input_path):
        fail_cli(args, "input_not_found", f"Resume file not found: {input_path}")

    profile_data = load_profile(input_path)
    if getattr(args, "confirm_parsed", False) and profile_data.get("_parse_report"):
        profile_data["_parse_report"]["status"] = "reviewed"
        profile_data["_parse_report"]["next_action"] = "已记录人工核对，确认公开范围后可导出简历；原始解析提示保留供查阅。"

    if getattr(args, "output", None):
        out_path = write_json(profile_data, args.output)
        if getattr(args, "json", False):
            emit_json({"status": "success", "output": out_path, "profile": profile_data})
            return
        print(f"已保存解析结果：{out_path}")
    elif getattr(args, "json", False):
        emit_json(profile_data)
        return

    # User-friendly console display
    cand = profile_data.get("candidate", {})
    edu = profile_data.get("education", [])
    exp = profile_data.get("experience", [])
    proj = profile_data.get("projects", [])
    skills = profile_data.get("skills", [])
    comp = profile_data.get("competencies", {})

    print("=" * 68)
    print("      OfferGet · 简历解析结果核对    ")
    print("=" * 68)
    print(f"候选人：{cand.get('name', '候选人')}（{cand.get('title_zh') or '未指定职位'}）")
    report = profile_data.get("_parse_report", {})
    if report:
        counts = report["recognized_counts"]
        print(f"已识别：教育 {counts['education']} 段、工作 {counts['experience']} 段、项目 {counts['projects']} 个、技能 {counts['skills']} 项。")
        for warning in report.get("warnings", []):
            print(f"待核对：{warning['message']}（{warning['path']}）")
        for item in report.get("unclassified_lines", [])[:5]:
            print(f"  原文第 {item['line']} 行：{item['text']}")
        print(f"下一步：{report['next_action']}")
    contact = " | ".join(filter(None, [cand.get("email"), cand.get("phone"), cand.get("location")]))
    if contact:
        print(f"[*] Contact:        {contact}")
    if cand.get("github"):
        print(f"[*] GitHub:         {cand.get('github')}")
    if cand.get("years_of_experience"):
        print(f"[*] Experience:     {cand.get('years_of_experience')} 年研发/工作经验")

    if edu:
        print("-" * 68)
        print("【教育背景】")
        for e in edu:
            line = " · ".join(filter(None, [e.get("school"), e.get("degree"), e.get("major"), e.get("time")]))
            print(f"  • {line}")

    if comp:
        print("-" * 68)
        print("【技能矩阵 (已识别分类)】")
        for cat, items in comp.items():
            if items:
                print(f"  • {cat}: {', '.join(items[:8])}{'...' if len(items) > 8 else ''}")
    elif skills:
        print("-" * 68)
        print(f"【技能清单 ({len(skills)} 项)】")
        print(f"  • {', '.join(skills[:12])}...")

    if exp:
        print("-" * 68)
        print(f"【工作经历 ({len(exp)} 段)】")
        for idx, ex in enumerate(exp, 1):
            head = " · ".join(filter(None, [ex.get("company") or ex.get("org"), ex.get("role"), ex.get("time")]))
            print(f"  {idx}. {head}")
            bullets = ex.get("bullets", [])
            for b in bullets[:2]:
                print(f"     - {b[:70]}...")

    if proj:
        print("-" * 68)
        print(f"【项目经历 ({len(proj)} 个)】")
        for idx, pr in enumerate(proj, 1):
            head = " · ".join(filter(None, [pr.get("name"), pr.get("role"), pr.get("time")]))
            print(f"  {idx}. {head}")

    print("=" * 68)
    if not getattr(args, "output", None):
        print("[*] 提示: 加上 `--output my_profile.json` 可保存为标准化底稿文件供多处复用。")


def cmd_profile_refs(args: Any) -> None:
    """Handler for `offerget profile refs --docs <path...> --query <text> [--limit 5] [--json]`."""
    from core.reference_index import ReferenceKnowledgeIndex

    docs = getattr(args, "docs", None) or []
    query = (getattr(args, "query", None) or "").strip()
    raw_limit = getattr(args, "limit", None)
    limit = 5 if raw_limit is None else int(raw_limit)
    if not docs or not query:
        fail_cli(args, "invalid_input", "Both --docs and --query are required")
    if limit < 1:
        fail_cli(args, "invalid_input", "--limit must be >= 1")

    index = ReferenceKnowledgeIndex(docs)
    hits = index.search(query, limit=limit)
    payload = {
        "query": query,
        "visibility": "reference-only",
        "total_chunks": len(index.chunks),
        "hits": hits,
        "skipped_files": index.skipped_files,
    }
    if getattr(args, "json", False):
        emit_json(payload)
        return

    print(f"[Reference-Only Recall] query={query!r}, indexed_chunks={len(index.chunks)}, hits={len(hits)}")
    for i, hit in enumerate(hits, 1):
        print(f"{i}. [{hit['doc_title']} > {hit['section_path']}] (score={hit['score']})")
        print(f"   {hit['content'][:200]}{'...' if len(hit['content']) > 200 else ''}")
