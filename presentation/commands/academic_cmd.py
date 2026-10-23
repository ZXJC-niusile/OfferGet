"""
OfferGet Academic Command Handlers:
- cmd_baoyan_audit: Audit academic resume entry for integrity & word-count
- cmd_baoyan_compress: Compress academic entry to strict word count tier
- cmd_baoyan_advisor (cmd_advisor_match): Match professor profile and generate high-EQ outreach email
- cmd_baoyan_checklist: Generate summer camp / re-examination checklist
- cmd_defense_simulate: Project defense interrogation & red-team simulator
"""

from __future__ import annotations

import os
import sys

from core.cli_helpers import (
    read_text,
    load_json,
    load_profile,
    load_json_or_text,
    write_text,
    emit_json,
    emit_stderr,
)

from services.academic_service import AcademicService


def cmd_defense_simulate(args):
    """Handler for `offerget defense simulate [<target>] [--project <target>] [--profile <profile.json>] [--intensity <先热个身|开始挑刺|严刑拷打>]`."""
    target_input = args.target or getattr(args, "project_opt", None)
    if not target_input:
        emit_stderr("[-] Error: Project description text or file path is required.")
        sys.exit(1)

    json_data, text_data = load_json_or_text(target_input)
    target_data = json_data if json_data is not None else text_data

    profile_data = None
    if args.profile:
        if not os.path.exists(args.profile):
            emit_stderr(f"[-] Error: Profile file not found: {args.profile}")
            sys.exit(1)
        profile_data = load_profile(args.profile)

    service = AcademicService()
    result = service.simulate_defense(
        target_project_or_text=target_data,
        candidate_profile=profile_data,
        intensity=args.intensity or "开始挑刺",
        scenario=args.scenario or "技术 / 简历面试",
        output_format="raw",
    )

    if args.output:
        md_text = result.to_markdown()
        write_text(md_text, args.output)
        if args.json:
            emit_stderr(f"[+] Defense simulation report saved to: {args.output}")
        else:
            print(f"[+] Defense simulation report saved to: {args.output}")

    if args.json:
        emit_json(result.to_dict())
        return

    print("=" * 68)
    print("        OfferGet · Project Defense & Red-Team Simulator          ")
    print("=" * 68)
    print(f"[*] Project Name:   {result.project_name}")
    print(f"[*] Intensity:      {result.intensity}")
    print(f"[*] Scenario:       {result.scenario}")
    print(f"[*] Claims Audited: {result.summary_stats.get('total_claims', 0)} total "
          f"({result.summary_stats.get('supported_count', 0)} supported, "
          f"{result.summary_stats.get('implied_count', 0)} implied, "
          f"{result.summary_stats.get('missing_count', 0)} missing)")
    print(f"[*] Risk Profile:   {result.summary_stats.get('high_risk_count', 0)} High | "
          f"{result.summary_stats.get('medium_risk_count', 0)} Medium | "
          f"{result.summary_stats.get('low_risk_count', 0)} Low")
    print("-" * 68)
    print("【项目一句话定位】")
    print(f"  {result.one_sentence_positioning}")
    print("-" * 68)
    print(f"【高风险证据缺口 (Top {len(result.high_risk_gaps)})】")
    for idx, gap in enumerate(result.high_risk_gaps[:3], 1):
        print(f"  {idx}. [{gap.get('risk_level')}] {gap.get('category_zh')} - {gap.get('title')}")
        print(f"     • 缺口: {gap.get('gap')}")
        print(f"     • 状态: {gap.get('evidence_status')} ({gap.get('risk_basis')})")
    print("-" * 68)
    print("【连续追问链精选】")
    if result.follow_up_chains:
        chain = result.follow_up_chains[0]
        print(f"  • 追问目标: {chain.target_claim[:40]}...")
        for r in chain.rounds:
            print(f"    - {r.title}:")
            print(f"      “{r.question}”")
    print("-" * 68)
    print("【答辩速查卡 (摘要)】")
    if result.defense_cheat_sheet:
        for vuln in result.defense_cheat_sheet.top_vulnerabilities[:2]:
            print(f"  • 软肋: {vuln.get('vulnerability')}")
            print(f"    底线: {vuln.get('bottom_line')}")
    print("=" * 68)
    if not args.output:
        print("[*] 提示: 增加 `--output report.md` 可导出完整 7 章节答辩红蓝对抗报告。")


def cmd_baoyan_audit(args):
    """Handler for `offerget baoyan audit <entry_or_file> [--role <role>] [--tier <tier>] [--material <file>]`."""
    entry_text = read_text(args.entry)
    material_text = read_text(args.material) if args.material else None

    result = AcademicService().audit_entry(
        entry=entry_text,
        role=args.role,
        target_tier=args.tier or "简历版",
        material=material_text
    )

    if args.json:
        emit_json(result)
        return

    print("=" * 68)
    print("      OfferGet · Chinese Academic Integrity & Word-Count Auditor      ")
    print("=" * 68)
    badge = "✅ 审计通过 (PASSED)" if result["passed"] else "❌ 触发红线 (VIOLATIONS)"
    print(f"[*] 综合结论:        {badge}")
    print(f"[*] 目标规格:        {result['target_tier']}")
    print(f"[*] 当前字数:        {result['word_count']} 字")
    print("-" * 68)

    checks = result.get("checks", {})
    print("【4 大学术诚信审查】")
    sim = checks.get("simulation_vs_real_cluster", {})
    print(f"  1. 仿真 vs 实机集群隔离:   {'✅ 正常' if sim.get('passed') else '❌ 违规'}")
    if not sim.get("passed") and "message" in sim:
        print(f"     • {sim['message']}")

    exp = checks.get("expected_vs_acquired_outcomes", {})
    print(f"  2. 在投 vs 录用成果隔离:   {'✅ 正常' if exp.get('passed') else '❌ 违规'}")
    if not exp.get("passed") and "message" in exp:
        print(f"     • {exp['message']}")

    rv = checks.get("role_verb_hierarchy", {})
    print(f"  3. 团队位次与动词授权匹配: {'✅ 正常' if rv.get('passed') else '❌ 违规'}")
    if not rv.get("passed") and "message" in rv:
        print(f"     • {rv['message']}")

    bz = checks.get("academic_buzzwords_forbidden", {})
    print(f"  4. 空洞大词与学术吹捧审查: {'✅ 正常' if bz.get('passed') else '❌ 违规'}")
    if not bz.get("passed") and "found_buzzwords" in bz:
        print(f"     • 违规词: {bz['found_buzzwords']}")

    print("-" * 68)
    typo = checks.get("typography", {})
    print(f"【中文学术排版与标点】:     {'✅ 符合规范' if typo.get('passed') else '⚠️ 发现排版标点问题'}")
    if not typo.get("passed") and "issues" in typo:
        for issue in typo["issues"]:
            if isinstance(issue, dict):
                print(f"  • {issue.get('message')}")
            else:
                print(f"  • {issue}")

    if "numerical_provenance" in checks:
        prov = checks["numerical_provenance"]
        print("-" * 68)
        print(f"【数值原始出处追溯】:       {'✅ 数据全部属实' if prov.get('passed') else '⚠️ 存在未佐证指标'}")
        if prov.get("missing_numbers"):
            print(f"  • 未在证明材料中找到佐证的数值: {prov['missing_numbers']}")
    print("=" * 68)


def cmd_baoyan_compress(args):
    """Handler for `offerget baoyan compress <entry_or_file> --tier <摘要版|简历版|陈述版>`."""
    entry_text = read_text(args.entry)
    result = AcademicService().compress_entry(entry_text, target_tier=args.tier)

    if args.json:
        emit_json(result)
        return

    print("=" * 68)
    print(f"       OfferGet · Baoyan Word-Count Compressor ({args.tier})       ")
    print("=" * 68)
    print(f"[*] 原始字数:   {result['original_count']} 字")
    print(f"[*] 压缩后字数: {result['compressed_count']} 字 (目标区间: {result['tier_range'][0]}-{result['tier_range'][1]} 字)")
    print(f"[*] 达成状态:   {'✅ 成功达标' if result['is_in_range'] else '⚠️ 需微调'}")
    print(f"[*] 压缩率:     {result['compression_ratio']}")
    print("-" * 68)
    print("【压缩后推荐文本】")
    print(result["compressed_text"])
    print("=" * 68)


def cmd_baoyan_advisor(args):
    """Handler for `offerget baoyan advisor <advisor.json> --profile <profile.json> [--scenario <scenario>]`."""
    if not os.path.exists(args.advisor):
        emit_stderr(f"[-] Error: Advisor profile not found: {args.advisor}")
        sys.exit(1)
    if not os.path.exists(args.profile):
        emit_stderr(f"[-] Error: Candidate profile not found: {args.profile}")
        sys.exit(1)

    adv_data = load_json(args.advisor)
    prof_data = load_profile(args.profile)

    result = AcademicService().match_advisor(
        advisor_data=adv_data,
        candidate_data=prof_data,
        email_scenario=args.scenario or "summer_camp"
    )

    email = result.get("outreach_email", {})
    match_info = result.get("intersection_match", {})

    if args.output:
        write_text(email.get("body", ""), args.output)
        if args.json:
            emit_stderr(f"[+] Outreach email saved to: {args.output}")
        else:
            print(f"[+] Outreach email saved to: {args.output}")

    if args.json:
        emit_json(result)
        return

    print("=" * 68)
    print("         OfferGet · Chinese Advisor Matcher & Outreach Studio     ")
    print("=" * 68)
    print(f"[*] 目标导师:       {adv_data.get('name')} ({adv_data.get('title', '教授')} - {adv_data.get('institution', '')})")
    cand = prof_data.get("candidate", {})
    print(f"[*] 候选人:         {cand.get('name')} ({cand.get('university', '')} - {cand.get('major', '')})")
    print(f"[*] 学术匹配重合度: {match_info.get('intersection_score', 0)} %")
    print("-" * 68)
    print("【学术交集与核心重合点】")
    for topic in match_info.get("mutual_research_topics", []):
        print(f"  • 共同研究方向: {topic}")
    for overlap in match_info.get("technical_overlaps", [])[:3]:
        print(f"  • 技术重合: {overlap}")
    if match_info.get("strategic_attack_angle"):
        print(f"  • 进攻策略: {match_info['strategic_attack_angle']}")
    print("-" * 68)
    print("【生成的高情商导师学术自荐信】")
    print(f"主题: {email.get('subject', '')}")
    print("-" * 40)
    print(email.get("body", ""))
    print("-" * 68)
    anti_rep = result.get("anti_hallucination_report", {})
    print(f"【学术真实性审计】:   {anti_rep.get('audit_verdict', '正常')}")
    print("【防鸽与学术信誉红线提示】")
    print("  • 严禁群发相同套磁信；收到导师肯定性回复后须在 24-48 小时内确认")
    print("  • 若获得更好 offer，须在第一时间书面礼貌致歉并释放名额，切忌拖延至九推系统关闭")
    print("=" * 68)


cmd_advisor_match = cmd_baoyan_advisor


def cmd_baoyan_checklist(args):
    """Handler for `offerget baoyan checklist [--profile <profile.json>] [<profile.json>] [--stage <stage>] [--track <track>]`."""
    profile_path = args.profile or getattr(args, "profile_pos", None)
    if not profile_path or not os.path.exists(profile_path):
        emit_stderr(f"[-] Error: Profile file not found: {profile_path}")
        sys.exit(1)

    prof_data = load_profile(profile_path)


    stage = args.stage or "夏令营"
    track = args.track or "直博"
    checklist = AcademicService().generate_checklist(prof_data, stage=stage, track=track)

    if args.json:
        emit_json(checklist)
        return

    print("=" * 68)
    print(f"       OfferGet · Baoyan & Postgraduate Admission Checklist       ")
    print("=" * 68)
    print(f"[*] 候选人:     {checklist.get('candidate_name', '申请人')}")
    print(f"[*] 申请阶段:   {checklist['stage']}")
    print(f"[*] 报考通道:   {checklist['track']}")
    print(f"[*] 准备完成率: {checklist['readiness_percentage']}% ({checklist['ready_items']}/{checklist['total_items']} 项已就绪)")
    print("-" * 68)

    category_names = {
        "mandatory_materials": "基础必备证件与官方学业证明",
        "academic_proofs": "学术论文、在投证明与竞赛专利资产",
        "expert_recommendations": "专家推荐信 (正/副高职称亲笔签名)",
        "presentation_and_interview": "自我介绍PPT、中英文答辩与白板推导",
        "administrative_and_logistics": "报名系统状态跟踪与考务差旅行程"
    }

    for cat_key, items_list in checklist["categories"].items():
        cat_title = category_names.get(cat_key, cat_key)
        print(f"【{cat_title}】({len(items_list)} 项)")
        for item in items_list:
            crit = "⚠️ [关键必具]" if item.get("importance") == "CRITICAL" else "• [标准准备]"
            status_badge = "✅" if item.get("status") == "READY" else "⏳"
            print(f"  {status_badge} {crit} {item.get('name', item.get('item_id'))}")
            print(f"     说明: {item.get('requirement', '')}")
        print()
    print("=" * 68)
