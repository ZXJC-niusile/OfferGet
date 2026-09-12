"""
OfferGet Baoyan Pipeline & Academic Schema Engine.

Manages the postgraduate recommendation (保研) lifecycle, validates candidate
academic profiles against top-tier CS criteria, tracks the multi-stage application
state machine (COLLECTING_NOTICES -> CONTACTING_ADVISOR -> CAMP_APPLIED ->
CAMP_ACCEPTED -> PRE_RECOMMENDED -> FINAL_OFFER_LOCKED), and generates customized
summer camp / re-examination checklists.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class BaoyanStatus(str, Enum):
    """
    Canonical and branching states in the Baoyan (postgraduate recommendation) lifecycle.
    """
    # Canonical Golden Path
    COLLECTING_NOTICES = "COLLECTING_NOTICES"      # 通知收集与院校调研
    CONTACTING_ADVISOR = "CONTACTING_ADVISOR"      # 导师套磁与意向沟通
    CAMP_APPLIED = "CAMP_APPLIED"                  # 报名填报与材料投递
    CAMP_ACCEPTED = "CAMP_ACCEPTED"                # 入营资格审核通过 / 参营考核
    PRE_RECOMMENDED = "PRE_RECOMMENDED"            # 预推免通过 / 获优营拟录取
    FINAL_OFFER_LOCKED = "FINAL_OFFER_LOCKED"      # 国家推免系统最终确认锁定

    # Branching / Auxiliary States
    CAMP_WAITLISTED = "CAMP_WAITLISTED"            # 入营候补 (WL)
    CAMP_REJECTED = "CAMP_REJECTED"                # 入营初审未通过
    CAMP_ABANDONED = "CAMP_ABANDONED"              # 入营放弃 / 参营放弃
    OFFER_WAITLISTED = "OFFER_WAITLISTED"          # 考核候补 (优营/拟录取候补)
    OFFER_REJECTED = "OFFER_REJECTED"              # 考核未通过
    EXCELLENT_CAMP_ABANDONED = "EXCELLENT_CAMP_ABANDONED"  # 优营放弃 / 鸽了 (放弃录取)


# Ordered Golden Path sequence
GOLDEN_PATH: List[BaoyanStatus] = [
    BaoyanStatus.COLLECTING_NOTICES,
    BaoyanStatus.CONTACTING_ADVISOR,
    BaoyanStatus.CAMP_APPLIED,
    BaoyanStatus.CAMP_ACCEPTED,
    BaoyanStatus.PRE_RECOMMENDED,
    BaoyanStatus.FINAL_OFFER_LOCKED,
]

# Valid state machine transitions
ALLOWED_TRANSITIONS: Dict[BaoyanStatus, Set[BaoyanStatus]] = {
    BaoyanStatus.COLLECTING_NOTICES: {
        BaoyanStatus.CONTACTING_ADVISOR,
        BaoyanStatus.CAMP_APPLIED,
        BaoyanStatus.CAMP_ABANDONED,
    },
    BaoyanStatus.CONTACTING_ADVISOR: {
        BaoyanStatus.COLLECTING_NOTICES,
        BaoyanStatus.CAMP_APPLIED,
        BaoyanStatus.CAMP_ABANDONED,
    },
    BaoyanStatus.CAMP_APPLIED: {
        BaoyanStatus.CAMP_ACCEPTED,
        BaoyanStatus.CAMP_REJECTED,
        BaoyanStatus.CAMP_WAITLISTED,
        BaoyanStatus.CAMP_ABANDONED,
    },
    BaoyanStatus.CAMP_ACCEPTED: {
        BaoyanStatus.PRE_RECOMMENDED,
        BaoyanStatus.OFFER_REJECTED,
        BaoyanStatus.OFFER_WAITLISTED,
        BaoyanStatus.CAMP_ABANDONED,
        BaoyanStatus.EXCELLENT_CAMP_ABANDONED,
    },
    BaoyanStatus.CAMP_WAITLISTED: {
        BaoyanStatus.CAMP_ACCEPTED,
        BaoyanStatus.CAMP_REJECTED,
        BaoyanStatus.CAMP_ABANDONED,
    },
    BaoyanStatus.OFFER_WAITLISTED: {
        BaoyanStatus.PRE_RECOMMENDED,
        BaoyanStatus.OFFER_REJECTED,
        BaoyanStatus.EXCELLENT_CAMP_ABANDONED,
    },
    BaoyanStatus.PRE_RECOMMENDED: {
        BaoyanStatus.FINAL_OFFER_LOCKED,
        BaoyanStatus.EXCELLENT_CAMP_ABANDONED,
    },
    BaoyanStatus.CAMP_REJECTED: {
        BaoyanStatus.CAMP_APPLIED,         # 重新投递预推免/九推
        BaoyanStatus.COLLECTING_NOTICES,
    },
    BaoyanStatus.OFFER_REJECTED: {
        BaoyanStatus.CAMP_APPLIED,         # 投递下一轮 (预推免/九推)
        BaoyanStatus.COLLECTING_NOTICES,
    },
    BaoyanStatus.EXCELLENT_CAMP_ABANDONED: {
        BaoyanStatus.COLLECTING_NOTICES,
        BaoyanStatus.CAMP_APPLIED,
    },
    BaoyanStatus.CAMP_ABANDONED: {
        BaoyanStatus.COLLECTING_NOTICES,
    },
    BaoyanStatus.FINAL_OFFER_LOCKED: set(),  # Terminal state
}

# Supported Academic Stages and Tracks
SUPPORTED_STAGES = {"夏令营", "预推免", "九推", "统考复试"}
SUPPORTED_TRACKS = {"直博", "学硕", "专硕"}

VALID_CCF_RANKS = {"CCF-A", "CCF-B", "CCF-C", "Non-CCF", "Top-tier", "None"}
VALID_PUB_STATUSES = {"published", "accepted", "under_review", "in_preparation", "submitted"}
VALID_EXPERIMENT_TYPES = {"real_experiment", "simulation", "hybrid"}


def _load_profile(data: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
    """Helper to safely load profile dictionary from dict or file path."""
    if isinstance(data, dict):
        return data
    path = Path(data)
    if not path.exists():
        raise FileNotFoundError(f"Profile path not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_academic_profile(profile_data: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
    """
    Validates candidate academic profile structure against top-tier postgraduate standards.

    Checks:
    - Candidate basic info (name, university, major, email, phone)
    - Academic standing (GPA, Rank, CET-6 / English proficiency)
    - Publications schema (title, venue, CCF tier, author role, status, explicit 'under_review')
    - Graduation Thesis / Big Projects (team role, individual contribution, simulation vs real experiment)
    - Competitions (name, award/tier, year)
    - Honors & Scholarships (National Scholarship, university awards)
    - Target Schools & Advisors list
    """
    profile = _load_profile(profile_data)
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Candidate Info
    candidate = profile.get("candidate", {})
    if not candidate:
        errors.append("Missing required top-level object: 'candidate'.")
    else:
        for field in ["name", "university", "major", "email", "phone"]:
            if not candidate.get(field):
                errors.append(f"Candidate missing required field: '{field}'.")
        email = candidate.get("email", "")
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            warnings.append(f"Candidate email '{email}' does not look like a standard email format.")

    # 2. Academic Standing
    standing = profile.get("academic_standing", {})
    if not standing:
        errors.append("Missing required top-level object: 'academic_standing'.")
    else:
        gpa = standing.get("gpa")
        if gpa is None:
            errors.append("Academic standing missing 'gpa'.")
        elif not (isinstance(gpa, (int, float)) and 0.0 <= float(gpa) <= 5.0):
            errors.append(f"Invalid GPA value: {gpa}. Expected float between 0.0 and 5.0.")

        rank = standing.get("rank")
        if not rank:
            errors.append("Academic standing missing 'rank' (e.g. '2/150').")
        elif not re.search(r"\d+\s*/\s*\d+", str(rank)):
            warnings.append(f"Academic rank '{rank}' should follow 'rank/total' format (e.g. '2/150').")

        # English proficiency (CET-6, CET-4, TOEFL, IELTS)
        english = standing.get("english", {})
        cet6 = standing.get("cet6") or english.get("cet6")
        if cet6 is None and not english.get("toefl") and not english.get("ielts"):
            warnings.append("No CET-6, TOEFL, or IELTS score provided in academic standing.")
        elif cet6 is not None:
            try:
                cet6_val = int(cet6)
                if cet6_val < 425:
                    warnings.append(f"CET-6 score ({cet6_val}) is below 425 pass threshold.")
            except (ValueError, TypeError):
                errors.append(f"Invalid CET-6 score value: {cet6}.")

    # 3. Publications
    pubs = profile.get("publications", [])
    ccf_a_count = 0
    ccf_b_count = 0
    under_review_count = 0

    if not isinstance(pubs, list):
        errors.append("'publications' must be a list of publication entries.")
    else:
        for idx, pub in enumerate(pubs):
            prefix = f"Publication #{idx + 1} ('{pub.get('title', 'Unknown')}')"
            for f in ["title", "venue", "ccf_rank", "author_role", "status"]:
                if not pub.get(f):
                    errors.append(f"{prefix} missing required field: '{f}'.")

            ccf_rank = pub.get("ccf_rank")
            if ccf_rank and ccf_rank not in VALID_CCF_RANKS:
                errors.append(f"{prefix} has invalid CCF rank '{ccf_rank}'. Must be one of {sorted(VALID_CCF_RANKS)}.")

            if ccf_rank == "CCF-A":
                ccf_a_count += 1
            elif ccf_rank == "CCF-B":
                ccf_b_count += 1

            status = pub.get("status")
            if status and status not in VALID_PUB_STATUSES:
                errors.append(f"{prefix} has invalid publication status '{status}'. Must be one of {sorted(VALID_PUB_STATUSES)}.")

            if status == "under_review":
                under_review_count += 1

            # Check author role format
            role = pub.get("author_role", "")
            if role and role not in {"first_author", "co_first_author", "second_author", "corresponding_author", "other"}:
                warnings.append(f"{prefix} author_role '{role}' non-standard; prefer first_author/co_first_author.")

    # 4. Graduation Thesis / Projects
    projects = profile.get("projects", [])
    grad_thesis = profile.get("graduation_thesis")
    if not projects and not grad_thesis:
        warnings.append("Neither 'projects' nor 'graduation_thesis' found in profile.")

    all_projects = list(projects)
    if grad_thesis and isinstance(grad_thesis, dict):
        all_projects.append(grad_thesis)

    for idx, proj in enumerate(all_projects):
        p_name = proj.get("name") or proj.get("title") or f"Project #{idx + 1}"
        prefix = f"Project '{p_name}'"

        if not proj.get("role"):
            errors.append(f"{prefix} missing team 'role'.")
        if not proj.get("individual_contribution"):
            errors.append(f"{prefix} missing 'individual_contribution'.")

        # Check simulation vs real experiment tags
        exp_type = proj.get("experiment_type")
        tags = proj.get("tags", [])
        has_exp_tag = exp_type in VALID_EXPERIMENT_TYPES or any(
            t in ["real_experiment", "simulation", "hybrid"] for t in tags
        )
        if not has_exp_tag:
            errors.append(
                f"{prefix} missing simulation vs real experiment indicator. "
                "Must specify 'experiment_type' ('real_experiment'|'simulation'|'hybrid') or include in 'tags'."
            )

    # 5. Competitions
    competitions = profile.get("competitions", [])
    has_tier1_comp = False
    if isinstance(competitions, list):
        for comp in competitions:
            name = comp.get("name", "")
            award = comp.get("award", "")
            if any(k in name for k in ["MCM", "ICM", "电子设计", "NUEDC", "ACM", "ICPC", "CCPC"]):
                if any(w in award for w in ["Finalist", "Outstanding", "国家一等奖", "一等奖", "金奖", "银奖", "First Prize"]):
                    has_tier1_comp = True

    # 6. Honors & Scholarships
    honors = profile.get("honors", [])
    has_national_scholarship = False
    if isinstance(honors, list):
        for h in honors:
            name = h.get("name", "")
            if "国家奖学金" in name or "National Scholarship" in name:
                has_national_scholarship = True

    # 7. Target Schools & Advisors
    target_schools = profile.get("target_schools", [])
    if not target_schools:
        warnings.append("No 'target_schools' defined in candidate profile.")
    else:
        for idx, ts in enumerate(target_schools):
            s_name = ts.get("school_name", f"Target #{idx + 1}")
            if not ts.get("track"):
                warnings.append(f"Target '{s_name}' missing application track ('直博'|'学硕'|'专硕').")
            elif ts.get("track") not in SUPPORTED_TRACKS:
                warnings.append(f"Target '{s_name}' track '{ts.get('track')}' not in {SUPPORTED_TRACKS}.")

    # Calculate Competitiveness Score (0 - 100)
    score = 0.0

    # GPA & Rank (max 30 pts)
    try:
        gpa_val = float(standing.get("gpa", 0))
        max_gpa = float(standing.get("max_gpa", 4.0))
        gpa_ratio = min(gpa_val / max_gpa, 1.0)
        score += gpa_ratio * 15.0

        rank_pct_str = str(standing.get("rank_percent", ""))
        pct_match = re.search(r"(\d+(\.\d+)?)", rank_pct_str)
        if pct_match:
            pct = float(pct_match.group(1))
            if pct <= 2.0:
                score += 15.0
            elif pct <= 5.0:
                score += 12.0
            elif pct <= 10.0:
                score += 9.0
            else:
                score += 5.0
        else:
            score += 10.0
    except Exception:
        score += 15.0

    # Publications (max 35 pts)
    score += min(ccf_a_count * 20.0, 25.0)
    score += min(ccf_b_count * 10.0, 15.0)
    if under_review_count > 0 and (ccf_a_count + ccf_b_count) < 2:
        score += 5.0

    # Competitions (max 15 pts)
    if has_tier1_comp:
        score += 15.0
    elif len(competitions) > 0:
        score += 8.0

    # Honors (max 10 pts)
    if has_national_scholarship:
        score += 10.0
    elif len(honors) > 0:
        score += 5.0

    # English (max 10 pts)
    english = standing.get("english", {})
    cet6_score = standing.get("cet6") or english.get("cet6", 0)
    try:
        c6 = int(cet6_score)
        if c6 >= 600:
            score += 10.0
        elif c6 >= 550:
            score += 8.0
        elif c6 >= 500:
            score += 6.0
        elif c6 >= 425:
            score += 4.0
    except (ValueError, TypeError):
        if english.get("toefl", 0) >= 100 or english.get("ielts", 0) >= 7.5:
            score += 10.0

    score = min(round(score, 1), 100.0)

    # Rank & Percent extraction for summary
    rank_val = standing.get("rank", "")
    rank_pct_val = standing.get("rank_percent")
    if not rank_pct_val and "/" in str(rank_val):
        try:
            parts = str(rank_val).split("/")
            r_num = float(parts[0].strip())
            r_tot = float(parts[1].strip())
            rank_pct_val = f"Top {round((r_num / r_tot) * 100, 1)}%"
        except Exception:
            rank_pct_val = "N/A"

    return {
        "valid": len(errors) == 0,
        "competitiveness_score": score,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "candidate_name": candidate.get("name", "Unknown"),
            "university": candidate.get("university", "Unknown"),
            "major": candidate.get("major", "Unknown"),
            "gpa": standing.get("gpa"),
            "rank": rank_val,
            "rank_percent": rank_pct_val,
            "cet6": cet6,
            "ccf_a_count": ccf_a_count,
            "ccf_b_count": ccf_b_count,
            "under_review_count": under_review_count,
            "has_national_scholarship": has_national_scholarship,
            "has_tier1_competition": has_tier1_comp,
            "target_schools_count": len(target_schools),
        }
    }


def generate_camp_checklist(
    profile_data: Union[Dict[str, Any], str, Path],
    stage: str = "夏令营",
    track: str = "直博"
) -> Dict[str, Any]:
    """
    Generates customized Summer Camp / Postgraduate Re-examination material checklist.

    Categorized into:
    - mandatory_materials (基础必备证件与学业证明)
    - academic_proofs (学术论文、在投证明与专利)
    - expert_recommendations (专家推荐信)
    - presentation_and_interview (自我介绍PPT、中英文答辩、白板推导)
    - administrative_and_logistics (报名系统状态、导师沟通记录、考务行程)
    """
    if stage not in SUPPORTED_STAGES:
        raise ValueError(f"Unsupported stage '{stage}'. Supported stages: {sorted(SUPPORTED_STAGES)}")
    if track not in SUPPORTED_TRACKS:
        raise ValueError(f"Unsupported track '{track}'. Supported tracks: {sorted(SUPPORTED_TRACKS)}")

    profile = _load_profile(profile_data)
    candidate = profile.get("candidate", {})
    standing = profile.get("academic_standing", {})
    pubs = profile.get("publications", [])
    comps = profile.get("competitions", [])
    honors = profile.get("honors", [])
    thesis = profile.get("graduation_thesis")

    items: Dict[str, List[Dict[str, Any]]] = {
        "mandatory_materials": [],
        "academic_proofs": [],
        "expert_recommendations": [],
        "presentation_and_interview": [],
        "administrative_and_logistics": []
    }

    # 1. Mandatory Materials
    items["mandatory_materials"].append({
        "item_id": "MAND-01",
        "name": "二代身份证正反面扫描件 (PDF/高清图)",
        "requirement": "有效期内二代身份证，正反面合并在同一页A4纸，彩色扫描。",
        "status": "READY",
        "importance": "CRITICAL"
    })
    items["mandatory_materials"].append({
        "item_id": "MAND-02",
        "name": "教育部学籍在线验证报告及学生证注册页复印件",
        "requirement": "学信网下载教育部学籍在线验证报告（确保在验证有效期内）；学生证照片页与每学期注册盖章页扫描。",
        "status": "READY",
        "importance": "CRITICAL"
    })

    # Official Transcript
    gpa_display = standing.get("gpa_display") or f"{standing.get('gpa')}/{standing.get('max_gpa', 4.0)}"
    items["mandatory_materials"].append({
        "item_id": "MAND-03",
        "name": f"本科前五学期官方历年成绩单 (含教务处公章) [当前GPA: {gpa_display}]",
        "requirement": "由本科学校教务处或自助打印终端出具的原件扫描件，须加盖教务处红章。",
        "status": "READY" if standing.get("gpa") else "NEEDS_ATTENTION",
        "importance": "CRITICAL"
    })

    # Official Rank Proof
    rank_display = standing.get("rank", "待开具")
    rank_pct = standing.get("rank_percent", "")
    items["mandatory_materials"].append({
        "item_id": "MAND-04",
        "name": f"官方专业排名与综合素质证明 [当前排名: {rank_display} ({rank_pct})]",
        "requirement": "院系或教务处出具的专业人数与综合测评排名证明，必须包含公章，夏令营初审核心硬指标。",
        "status": "READY" if standing.get("rank") else "NEEDS_ATTENTION",
        "importance": "CRITICAL"
    })

    # English Proof
    english = standing.get("english", {})
    cet6_val = standing.get("cet6") or english.get("cet6")
    toefl_val = english.get("toefl")
    eng_status = "READY" if (cet6_val or toefl_val) else "NEEDS_ATTENTION"
    eng_desc = f"CET-6: {cet6_val}" if cet6_val else ""
    if toefl_val:
        eng_desc += f", TOEFL: {toefl_val}"
    items["mandatory_materials"].append({
        "item_id": "MAND-05",
        "name": f"国家大学英语六级 (CET-6) / 雅思 / 托福成绩单 [{eng_desc}]",
        "requirement": "大学英语六级成绩单扫描件 (原则上要求 >= 425 分，顶尖院校强com建议 >= 550 分)。",
        "status": eng_status,
        "importance": "CRITICAL"
    })

    # Customized Academic Resume
    items["mandatory_materials"].append({
        "item_id": "MAND-06",
        "name": f"针对{stage}定制的学术简历 (PDF, 单页/双页精致排版)",
        "requirement": "严格突出排名、CCF论文、国家奖学金及竞赛成果，文风客观严谨，杜绝AI空洞假大空修辞。",
        "status": "READY",
        "importance": "CRITICAL"
    })

    # Personal Statement
    items["mandatory_materials"].append({
        "item_id": "MAND-07",
        "name": f"保研个人陈述 (Personal Statement, 1500-2000字)",
        "requirement": "阐明本科科研经历、技术沉淀、攻读研究生阶段的科研兴趣、研究计划及为何选择该院系导师。",
        "status": "READY",
        "importance": "HIGH"
    })

    # 2. Academic Proofs
    if pubs:
        for idx, pub in enumerate(pubs):
            p_title = pub.get("title", f"Paper #{idx+1}")
            p_venue = pub.get("venue", "Unknown Venue")
            p_rank = pub.get("ccf_rank", "Non-CCF")
            p_status = pub.get("status", "published")

            if p_status == "under_review":
                items["academic_proofs"].append({
                    "item_id": f"ACAD-PUB-{idx+1:02d}",
                    "name": f"在投论文证明及抽印本: 《{p_title}》 ({p_venue}, {p_rank}) [在投/Under Review]",
                    "requirement": "提供投稿确认邮件截图或系统投稿页面截屏；提供隐去盲审敏感信息的论文初稿抽印本供导师审阅。",
                    "status": "READY",
                    "importance": "HIGH"
                })
            else:
                items["academic_proofs"].append({
                    "item_id": f"ACAD-PUB-{idx+1:02d}",
                    "name": f"已录用/发表顶会顶刊论文首页及录用函: 《{p_title}》 ({p_venue}, {p_rank})",
                    "requirement": "论文封面与首页完整复印件，包含作者列表、单位署名及录用邮件/DOI链接证明。",
                    "status": "READY",
                    "importance": "CRITICAL" if p_rank in ["CCF-A", "CCF-B"] else "HIGH"
                })

    if comps:
        comp_summary = "、".join([c.get("name", "") for c in comps[:2]])
        items["academic_proofs"].append({
            "item_id": "ACAD-COMP-01",
            "name": f"国家级/国际级高水平竞赛获奖证书复印件 ({comp_summary}等)",
            "requirement": "清晰彩色扫描件，重点呈现 MCM/ICM、电子设计竞赛、ACM/ICPC 等含金量顶格竞赛证书。",
            "status": "READY",
            "importance": "HIGH"
        })

    if honors:
        items["academic_proofs"].append({
            "item_id": "ACAD-HONOR-01",
            "name": "国家奖学金及校级顶级荣誉奖励证书",
            "requirement": "教育部印发国家奖学金证书原件扫描件，校级三好学生标兵等表彰文件复印件。",
            "status": "READY",
            "importance": "HIGH"
        })

    if thesis:
        items["academic_proofs"].append({
            "item_id": "ACAD-THESIS-01",
            "name": f"毕业设计/学术科研中期进展报告: 《{thesis.get('title', '')}》",
            "requirement": "阐明选题背景、算法机制、真实硬件集群评测数据与已取得的关键里程碑。",
            "status": "READY",
            "importance": "MEDIUM"
        })

    # 3. Expert Recommendations (Critical for 直博)
    rec_importance = "CRITICAL" if track == "直博" else "HIGH"
    items["expert_recommendations"].append({
        "item_id": "REC-01",
        "name": f"专家推荐信第 1 封 (正高级/副高级职称专家亲笔签名) [{'直博刚性必备' if track == '直博' else '院校选交'}]",
        "requirement": "通常由本校本科科研导师、班主任或专业学术委员会教授撰写，评价学生的科研自驱力、创新能力与学术诚信。",
        "status": "READY",
        "importance": rec_importance
    })
    items["expert_recommendations"].append({
        "item_id": "REC-02",
        "name": f"专家推荐信第 2 封 (正高级/副高级职称专家亲笔签名) [{'直博刚性必备' if track == '直博' else '院校选交'}]",
        "requirement": "由第二位专家独立出具；若目标院校采用线上推荐系统，需提前与专家确认邮箱并及时提醒完成网上提交。",
        "status": "READY",
        "importance": rec_importance
    })

    # 4. Presentation & Interview Preparation
    items["presentation_and_interview"].append({
        "item_id": "PRES-01",
        "name": f"{stage}综合面试自我介绍幻灯片 (PPT / PDF, 3-5分钟版 & 8分钟备用版)",
        "requirement": "控制页数在 8-12 页内：个人背景(1页) -> 核心科研与代表作(5-6页，着重系统设计与实验指标) -> 竞赛与综合素养(1-2页) -> 未来学术规划(1页)。",
        "status": "READY",
        "importance": "CRITICAL"
    })
    items["presentation_and_interview"].append({
        "item_id": "PRES-02",
        "name": "英文学术面试问答准备清单 (含2分钟英文自我介绍 & 项目英文答辩词)",
        "requirement": "梳理计算机专业高频英语词汇、所投论文的英文 Abstract 与创新点阐述，准备常见综合问答。",
        "status": "READY",
        "importance": "HIGH"
    })
    items["presentation_and_interview"].append({
        "item_id": "PRES-03",
        "name": "核心项目白板推导与代码架构复盘清单 (含真实实验与仿真对比要点)",
        "requirement": "针对已发表的 CCF 顶会论文与大作业系统，准备黑板/白板推导架构图、核心数学公式及实验极限瓶颈分析。",
        "status": "READY",
        "importance": "CRITICAL"
    })
    items["presentation_and_interview"].append({
        "item_id": "PRES-04",
        "name": "计算机专业核心基础课笔试/机试复习准备",
        "requirement": "复习数据结构与算法(刷 LeetCode/Codeforces 经典题)、操作系统、计算机网络、计算机体系结构核心原理。",
        "status": "READY",
        "importance": "HIGH"
    })

    # 5. Administrative & Logistics
    if stage == "夏令营":
        items["administrative_and_logistics"].append({
            "item_id": "LOG-01",
            "name": "目标院校夏令营网申系统填报确认与纸质材料寄送追踪",
            "requirement": "核验报名系统中所有附件上传完整；若需寄送纸质材料，选用顺丰速运并记录快递单号及签收状态。",
            "status": "READY",
            "importance": "CRITICAL"
        })
        items["administrative_and_logistics"].append({
            "item_id": "LOG-02",
            "name": "目标导师套磁邮件沟通记录与意向面谈预约",
            "requirement": "维护导师回复状态表（已发送/约面试/意向锁定），根据弱com/强com属性推进后续沟通。",
            "status": "READY",
            "importance": "HIGH"
        })
        items["administrative_and_logistics"].append({
            "item_id": "LOG-03",
            "name": "参营确认回执与线下差旅住宿安排",
            "requirement": "入营名单公布后在规定时间内回复确认参营回执；预订车票/机票与高校周边宾馆，备齐洗漱用品与正装。",
            "status": "READY",
            "importance": "HIGH"
        })
    elif stage == "预推免":
        items["administrative_and_logistics"].append({
            "item_id": "LOG-01",
            "name": "预推免网申系统材料提交及补充成果登记",
            "requirement": "将暑期最新获得的论文录用、实习或竞赛成果更新至预推免申请系统中。",
            "status": "READY",
            "importance": "CRITICAL"
        })
        items["administrative_and_logistics"].append({
            "item_id": "LOG-02",
            "name": "本校推免资格指标公示与推免生资格表确认",
            "requirement": "密切关注本科院校教务处推免名额分配细则与综合测评加分公示，确保顺利获得保研资格。",
            "status": "READY",
            "importance": "CRITICAL"
        })
    elif stage == "九推":
        items["administrative_and_logistics"].append({
            "item_id": "LOG-01",
            "name": "教育部全国推免服务系统 (yz.chsi.com.cn) 注册、信息核验与缴费",
            "requirement": "系统开放首日完成学籍核对与填报准备；开通志愿填报后第一时间填报已锁定意向院校。",
            "status": "READY",
            "importance": "CRITICAL"
        })
        items["administrative_and_logistics"].append({
            "item_id": "LOG-02",
            "name": "复试通知接受与待录取通知点击确认 (关键时间窗守候)",
            "requirement": "收到目标学校发送的‘待录取通知’后，务必在学校规定时间内（通常为 1-12 小时内）点击接受确认！",
            "status": "READY",
            "importance": "CRITICAL"
        })
    elif stage == "统考复试":
        items["administrative_and_logistics"].append({
            "item_id": "LOG-01",
            "name": "全国硕士研究生招生初试准考证与初试成绩单原件",
            "requirement": "研招网下载打印准考证，附带初试官方成绩单复印件。",
            "status": "READY",
            "importance": "CRITICAL"
        })
        items["administrative_and_logistics"].append({
            "item_id": "LOG-02",
            "name": "思想政治品德考核表 (政审表) 加盖院系党总支公章",
            "requirement": "由本科院系党总支填写学生日常思想道德与政治素养评语并加盖红章，密封或现场提交。",
            "status": "READY",
            "importance": "CRITICAL"
        })

    # Compute stats
    all_items_flat = []
    for cat_list in items.values():
        all_items_flat.extend(cat_list)

    total_count = len(all_items_flat)
    ready_count = sum(1 for it in all_items_flat if it.get("status") == "READY")
    attention_count = total_count - ready_count
    readiness_percentage = round((ready_count / total_count) * 100.0, 1) if total_count > 0 else 100.0

    return {
        "stage": stage,
        "track": track,
        "candidate_name": candidate.get("name", "Unknown"),
        "readiness_percentage": readiness_percentage,
        "total_items": total_count,
        "ready_items": ready_count,
        "attention_items": attention_count,
        "categories": items,
    }


class BaoyanPipeline:
    """
    Main pipeline engine orchestrating postgraduate recommendation applications,
    status transitions, profile validation, and task checklists.
    """

    def __init__(self, profile_data: Optional[Union[Dict[str, Any], str, Path]] = None):
        self.profile: Dict[str, Any] = {}
        self.applications: Dict[str, Dict[str, Any]] = {}
        self._timeline: Dict[str, List[Dict[str, Any]]] = {}

        if profile_data is not None:
            self.load_profile(profile_data)

    def load_profile(self, profile_data: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
        """Loads and initializes candidate profile and target school applications."""
        self.profile = _load_profile(profile_data)
        self.applications.clear()
        self._timeline.clear()

        # Populate target schools from profile
        target_schools = self.profile.get("target_schools", [])
        for idx, ts in enumerate(target_schools):
            target_id = ts.get("target_id") or f"TARGET-{idx+1:02d}"
            raw_stage = ts.get("current_stage", "COLLECTING_NOTICES")

            # Validate or fallback stage
            try:
                stage_status = BaoyanStatus(raw_stage)
            except ValueError:
                stage_status = BaoyanStatus.COLLECTING_NOTICES

            self.applications[target_id] = {
                "target_id": target_id,
                "school_name": ts.get("school_name", ""),
                "college": ts.get("college", ""),
                "major": ts.get("major", ""),
                "track": ts.get("track", "直博"),
                "target_advisor": ts.get("target_advisor", ""),
                "lab_name": ts.get("lab_name", ""),
                "research_direction": ts.get("research_direction", ""),
                "com_type": ts.get("com_type", "弱com"),
                "status": stage_status,
                "status_detail": ts.get("status_detail", ""),
                "updated_at": datetime.now().isoformat()
            }

            # Initialize timeline
            self._timeline[target_id] = [
                {
                    "status": stage_status.value,
                    "timestamp": datetime.now().isoformat(),
                    "note": ts.get("status_detail", "Initial application state loaded from profile")
                }
            ]

        return self.profile

    def validate(self, profile_data: Optional[Union[Dict[str, Any], str, Path]] = None) -> Dict[str, Any]:
        """Validates academic profile against schema and calculates competitiveness score."""
        target = profile_data if profile_data is not None else self.profile
        return validate_academic_profile(target)

    def add_target_application(
        self,
        school_name: str,
        college: str,
        major: str,
        track: str = "直博",
        target_advisor: str = "",
        lab_name: str = "",
        research_direction: str = "",
        com_type: str = "弱com",
        initial_status: Union[BaoyanStatus, str] = BaoyanStatus.COLLECTING_NOTICES,
        note: str = ""
    ) -> str:
        """Registers a new target university application."""
        if track not in SUPPORTED_TRACKS:
            raise ValueError(f"Unsupported track '{track}'. Must be one of {SUPPORTED_TRACKS}")

        status_enum = BaoyanStatus(initial_status)
        new_id = f"TARGET-{len(self.applications) + 1:02d}"

        self.applications[new_id] = {
            "target_id": new_id,
            "school_name": school_name,
            "college": college,
            "major": major,
            "track": track,
            "target_advisor": target_advisor,
            "lab_name": lab_name,
            "research_direction": research_direction,
            "com_type": com_type,
            "status": status_enum,
            "status_detail": note,
            "updated_at": datetime.now().isoformat()
        }

        self._timeline[new_id] = [
            {
                "status": status_enum.value,
                "timestamp": datetime.now().isoformat(),
                "note": note or "Target application created"
            }
        ]

        return new_id

    def can_transition(self, current_status: BaoyanStatus, next_status: BaoyanStatus) -> bool:
        """Checks whether a state machine transition is allowed."""
        if current_status == next_status:
            return True
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        return next_status in allowed

    def get_valid_next_states(self, target_id: str) -> List[str]:
        """Returns allowed next states for an application."""
        app = self.applications.get(target_id)
        if not app:
            raise KeyError(f"Application target ID '{target_id}' not found.")
        current: BaoyanStatus = app["status"]
        return [s.value for s in ALLOWED_TRANSITIONS.get(current, set())]

    def transition_application(
        self,
        target_id: str,
        new_status: Union[BaoyanStatus, str],
        note: str = ""
    ) -> Dict[str, Any]:
        """
        Transitions application to a new state, enforcing state machine rules.
        """
        app = self.applications.get(target_id)
        if not app:
            raise KeyError(f"Application target ID '{target_id}' not found.")

        target_status = BaoyanStatus(new_status)
        current_status: BaoyanStatus = app["status"]

        if not self.can_transition(current_status, target_status):
            raise ValueError(
                f"Invalid status transition for target '{target_id}': "
                f"{current_status.value} -> {target_status.value}. "
                f"Allowed next states: {[s.value for s in ALLOWED_TRANSITIONS.get(current_status, set())]}"
            )

        # Apply transition
        app["status"] = target_status
        if note:
            app["status_detail"] = note
        app["updated_at"] = datetime.now().isoformat()

        # Record timeline event
        self._timeline[target_id].append({
            "from_status": current_status.value,
            "to_status": target_status.value,
            "timestamp": datetime.now().isoformat(),
            "note": note
        })

        return {
            "target_id": target_id,
            "previous_status": current_status.value,
            "current_status": target_status.value,
            "updated_at": app["updated_at"],
            "note": note
        }

    def step_golden_path(self, target_id: str, note: str = "") -> Dict[str, Any]:
        """
        Advances the application to the next step along the canonical golden path:
        COLLECTING_NOTICES -> CONTACTING_ADVISOR -> CAMP_APPLIED -> CAMP_ACCEPTED -> PRE_RECOMMENDED -> FINAL_OFFER_LOCKED
        """
        app = self.applications.get(target_id)
        if not app:
            raise KeyError(f"Application target ID '{target_id}' not found.")

        current_status: BaoyanStatus = app["status"]
        if current_status not in GOLDEN_PATH:
            raise ValueError(
                f"Application '{target_id}' is currently at branching/terminal state '{current_status.value}', "
                f"cannot step automatically along canonical golden path."
            )

        current_idx = GOLDEN_PATH.index(current_status)
        if current_idx >= len(GOLDEN_PATH) - 1:
            raise ValueError(
                f"Application '{target_id}' has already reached the final golden path state '{current_status.value}'."
            )

        next_status = GOLDEN_PATH[current_idx + 1]
        step_note = note or f"Advanced along golden path to {next_status.value}"
        return self.transition_application(target_id, next_status, step_note)

    def get_application(self, target_id: str) -> Dict[str, Any]:
        """Returns details of a specific application."""
        if target_id not in self.applications:
            raise KeyError(f"Application target ID '{target_id}' not found.")
        app_copy = dict(self.applications[target_id])
        app_copy["status"] = app_copy["status"].value
        return app_copy

    def get_timeline(self, target_id: str) -> List[Dict[str, Any]]:
        """Returns chronological state audit timeline for an application."""
        if target_id not in self._timeline:
            raise KeyError(f"Application target ID '{target_id}' not found.")
        return list(self._timeline[target_id])

    def get_all_applications(self) -> List[Dict[str, Any]]:
        """Returns all tracked applications."""
        result = []
        for app in self.applications.values():
            entry = dict(app)
            entry["status"] = entry["status"].value
            result.append(entry)
        return result

    def get_funnel_summary(self) -> Dict[str, Any]:
        """
        Computes application status funnel statistics across all tracked targets.
        """
        counts = {status.value: 0 for status in BaoyanStatus}
        for app in self.applications.values():
            s_val = app["status"].value
            counts[s_val] = counts.get(s_val, 0) + 1

        total = len(self.applications)
        offers_locked = counts.get(BaoyanStatus.FINAL_OFFER_LOCKED.value, 0)
        pre_recommended = counts.get(BaoyanStatus.PRE_RECOMMENDED.value, 0)
        in_camp = counts.get(BaoyanStatus.CAMP_ACCEPTED.value, 0)

        return {
            "total_applications": total,
            "funnel_counts": counts,
            "locked_offers_count": offers_locked,
            "pre_recommended_count": pre_recommended,
            "camp_accepted_count": in_camp,
            "active_applications": total - counts.get(BaoyanStatus.CAMP_ABANDONED.value, 0) - counts.get(BaoyanStatus.CAMP_REJECTED.value, 0),
        }

    def generate_checklist(self, stage: str = "夏令营", track: str = "直博") -> Dict[str, Any]:
        """Generates dynamic checklist for the candidate profile."""
        return generate_camp_checklist(self.profile, stage=stage, track=track)
