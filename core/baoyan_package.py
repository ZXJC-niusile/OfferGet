"""
OfferGet Baoyan Application Package Builder (core/baoyan_package.py)
===================================================================
Ported and evolved from baoyan-skills (baoyan-application-package,
baoyan-personal-statement, baoyan-taocixin-outreach).

Provides end-to-end tooling for Chinese postgraduate recommendation (保研/推免/夏令营):
1. Package Manifest & TOC Builder:
   - Aggregates multi-document PDFs into a standardized A4 application portfolio.
   - Computes physical page index (Page 1 = Cover, Page 2 = TOC, Page 3+ = Docs).
   - Grouping adjacent documents with identical `group` into page ranges.
2. Personal Statement Builder:
   - Structures 5-part academic personal statement from ProfileContext.
   - Validates compliance against academic rigor and anti-slop rules.
3. Taocixin Outreach Builder:
   - Generates personalized professor outreach email and follow-up ledger.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.profile_adapter import ProfileContext, build_profile_context
from core.registry import QualityRuleRegistry


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SchoolInfo:
    name: str
    english: str = ""
    logo_path: Optional[str] = None
    primary_color: str = "#003366"  # Hex color
    package_title: str = "夏令营申请材料"
    application_label: str = "申请学院"
    application_value: str = "计算机学院"


@dataclass
class ApplicantInfo:
    name: str
    undergraduate_school: str
    major: str
    english_name: str = ""
    date_label: str = "2026年6月"
    gpa: str = ""
    rank: str = ""
    email: str = ""
    phone: str = ""


@dataclass
class PackageDocument:
    path: str
    label: str
    group: str
    page_count: int = 1
    first_page: Optional[int] = None  # 1-based inclusive
    last_page: Optional[int] = None   # 1-based inclusive


@dataclass
class PackageSection:
    number: str  # "01", "02"
    title: str   # "个人材料", "学业与身份证明", "科研与知识产权"
    documents: List[PackageDocument] = field(default_factory=list)


@dataclass
class PackageConfig:
    school: SchoolInfo
    applicant: ApplicantInfo
    sections: List[PackageSection] = field(default_factory=list)
    output_path: Optional[str] = None
    preview_dir: Optional[str] = None


@dataclass
class TocEntry:
    section_number: str
    section_title: str
    group_label: str
    start_page: int
    end_page: int

    @property
    def page_range_display(self) -> str:
        if self.start_page == self.end_page:
            return f"{self.start_page:02d}"
        return f"{self.start_page:02d} - {self.end_page:02d}"


@dataclass
class PackageManifest:
    school: SchoolInfo
    applicant: ApplicantInfo
    total_pages: int
    toc_entries: List[TocEntry]
    sections: List[PackageSection]


@dataclass
class PersonalStatementDraft:
    applicant_name: str
    target_school: str
    target_major: str
    academic_background: str
    research_interests: List[str]
    practical_projects: List[str]
    academic_achievements: List[str]
    graduate_study_plan: str
    word_count: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class TaocixinLetterDraft:
    applicant_name: str
    professor_name: str
    target_school: str
    target_lab: str
    email_subject: str
    greeting: str
    body: str
    closing: str
    ledger_row: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# Package Builder
# =============================================================================

class BaoyanPackageBuilder:
    """Computes layout, validates config, and formats application portfolio TOC."""

    @staticmethod
    def validate_config(config_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validates configuration dictionary for required fields and logical consistency."""
        errors: List[str] = []
        if "school" not in config_dict or not config_dict["school"].get("name"):
            errors.append("缺少学校名称 (school.name)")
        if "applicant" not in config_dict or not config_dict["applicant"].get("name"):
            errors.append("缺少申请人姓名 (applicant.name)")
        if "sections" not in config_dict or not isinstance(config_dict["sections"], list):
            errors.append("缺少材料分类 (sections)")
        else:
            for i, sec in enumerate(config_dict["sections"]):
                if not sec.get("title"):
                    errors.append(f"分类 #{i+1} 缺少标题 (title)")
                for j, doc in enumerate(sec.get("documents", [])):
                    if not doc.get("label"):
                        errors.append(f"分类 #{i+1} 文档 #{j+1} 缺少识别名称 (label)")
        return len(errors) == 0, errors

    def build_manifest(self, config_dict: Dict[str, Any]) -> PackageManifest:
        """Computes physical page numbers and generates deterministic TOC manifest.
        Page 1: Cover
        Page 2: TOC
        Page 3+: Content pages
        """
        valid, errors = self.validate_config(config_dict)
        if not valid:
            raise ValueError(f"配置验证失败: {'; '.join(errors)}")

        school_data = config_dict["school"]
        school = SchoolInfo(
            name=school_data.get("name", ""),
            english=school_data.get("english", ""),
            logo_path=school_data.get("logo"),
            primary_color=school_data.get("primary_color", "#003366"),
            package_title=school_data.get("package_title", "夏令营申请材料"),
            application_label=school_data.get("application_label", "申请学院"),
            application_value=school_data.get("application_value", "计算机学院"),
        )

        app_data = config_dict["applicant"]
        applicant = ApplicantInfo(
            name=app_data.get("name", ""),
            undergraduate_school=app_data.get("undergraduate_school", ""),
            major=app_data.get("major", ""),
            english_name=app_data.get("english_name", ""),
            date_label=app_data.get("date_label", "2026年6月"),
            gpa=app_data.get("gpa", ""),
            rank=app_data.get("rank", ""),
            email=app_data.get("email", ""),
            phone=app_data.get("phone", ""),
        )

        # Page 1: Cover, Page 2: TOC. Body starts at Page 3.
        current_page = 3
        toc_entries: List[TocEntry] = []
        parsed_sections: List[PackageSection] = []

        for sec_dict in config_dict.get("sections", []):
            sec_num = str(sec_dict.get("number", f"{len(parsed_sections)+1:02d}"))
            sec_title = str(sec_dict.get("title", ""))
            sec_docs: List[PackageDocument] = []

            # Group contiguous documents by group name
            current_group: Optional[str] = None
            group_start_page: int = current_page

            for doc_dict in sec_dict.get("documents", []):
                doc_pages = int(doc_dict.get("page_count", 1))
                doc = PackageDocument(
                    path=str(doc_dict.get("path", "")),
                    label=str(doc_dict.get("label", "")),
                    group=str(doc_dict.get("group", doc_dict.get("label", ""))),
                    page_count=doc_pages,
                    first_page=doc_dict.get("first_page"),
                    last_page=doc_dict.get("last_page"),
                )
                sec_docs.append(doc)

                if current_group is None:
                    current_group = doc.group
                    group_start_page = current_page
                elif doc.group != current_group:
                    # Flush previous group to TOC
                    toc_entries.append(
                        TocEntry(
                            section_number=sec_num,
                            section_title=sec_title,
                            group_label=current_group,
                            start_page=group_start_page,
                            end_page=current_page - 1,
                        )
                    )
                    current_group = doc.group
                    group_start_page = current_page

                current_page += doc_pages

            if current_group is not None:
                toc_entries.append(
                    TocEntry(
                        section_number=sec_num,
                        section_title=sec_title,
                        group_label=current_group,
                        start_page=group_start_page,
                        end_page=current_page - 1,
                    )
                )

            parsed_sections.append(
                PackageSection(number=sec_num, title=sec_title, documents=sec_docs)
            )

        total_pages = current_page - 1

        return PackageManifest(
            school=school,
            applicant=applicant,
            total_pages=total_pages,
            toc_entries=toc_entries,
            sections=parsed_sections,
        )


# =============================================================================
# Personal Statement Builder
# =============================================================================

class PersonalStatementBuilder:
    """Builds and validates 5-part academic personal statements for Baoyan applications."""

    def build_statement(
        self,
        profile_data: Union[Dict[str, Any], ProfileContext],
        target_school: str,
        target_major: str,
        research_interests: Optional[List[str]] = None,
        future_plan: Optional[str] = None,
    ) -> PersonalStatementDraft:
        ctx = build_profile_context(profile_data)
        prof = ctx.profile
        raw = ctx.raw_profile

        cand = prof.get("candidate", {}) if isinstance(prof.get("candidate"), dict) else {}
        name = cand.get("name") or raw.get("name") or "申请人"
        raw_edu = raw.get("education", {}) if isinstance(raw.get("education"), dict) else {}
        edu = prof.get("education", {}) if isinstance(prof.get("education"), dict) else {}

        school = raw_edu.get("school") or edu.get("school") or cand.get("school") or raw.get("degree_school", "本科院校")
        major = raw_edu.get("major") or edu.get("major") or cand.get("major") or raw.get("major", "计算机科学与技术")
        gpa = raw_edu.get("gpa") or edu.get("gpa") or cand.get("gpa") or raw.get("gpa", "")
        rank = raw_edu.get("rank") or edu.get("rank") or cand.get("rank") or raw.get("rank", "")

        academic_bg = (
            f"本科就读于{school}{major}专业"
            + (f"，专业成绩排名为 {rank}" if rank else "")
            + (f"，GPA 为 {gpa}" if gpa else "")
            + "。在校期间系统学习了数据结构、操作系统、计算机网络、概率论与数理统计等核心课程，专业基础扎实。"
        )

        interests = research_interests or ["大模型推理优化", "分布式系统与异构计算"]

        # Extract real projects from claims or experience
        projects = []
        for claim in ctx.claims:
            if claim.metric_context:
                projects.append(f"{claim.text}（指标: {claim.metric_context}）")
            elif claim.kind in ("experience", "project", "bullet"):
                projects.append(claim.text)
            elif claim.text and len(claim.text) > 10:
                projects.append(claim.text)
        if not projects:
            projects = [
                "在校期间完成专业培养方案规定的各项实验与专业课程设计，具备扎实的代码实现能力。"
            ]

        # Academic achievements (papers, awards) - strict anti-hallucination, never fabricate scholarships
        raw_achievements = (
            prof.get("awards", [])
            or prof.get("honors", [])
            or raw.get("awards", [])
            or raw.get("honors", [])
            or raw.get("honors_awards", [])
            or []
        )
        achievements = [str(a) for a in raw_achievements]
        achievements_display = [f"- {a}" for a in achievements[:3]] if achievements else ["- （暂无已登记的校级或国家级奖项，建议在申请前补充）"]

        study_plan = future_plan or (
            f"若有幸进入{target_school}{target_major}攻读研究生，将在导师指导下深入开展课题研究，"
            "夯实理论基础，积极参与开源社区与学术前沿交流，努力产出具备学术价值与工程落地意义的高质量科研成果。"
        )

        full_text = (
            f"【个人陈述】\n"
            f"申请人：{name} | 目标院校：{target_school} | 目标方向：{target_major}\n\n"
            f"一、学术背景\n{academic_bg}\n\n"
            f"二、研究兴趣与学术志趣\n" + "；".join(interests) + "。\n\n"
            f"三、科研与工程实践\n" + "\n".join(f"- {p}" for p in projects[:4]) + "\n\n"
            f"四、荣誉与学术成果\n" + "\n".join(achievements_display) + "\n\n"
            f"五、研究生学业规划\n{study_plan}\n"
        )

        # Audit against quality rules
        warnings: List[str] = []
        for word in QualityRuleRegistry.SUPERLATIVES:
            if word in full_text:
                warnings.append(f"发现绝对化词汇【{word}】，建议改为限定语境或客观指标")
        for buzz in QualityRuleRegistry.FORBIDDEN_BUZZWORDS:
            if buzz in full_text:
                warnings.append(f"发现空洞套话【{buzz}】，建议删除或替换为具体科研动作")

        # Integrated Fact Verification Guard
        from core.fact_guard import FactVerificationGuard
        guard = FactVerificationGuard(ctx)
        for p_str in projects[:4]:
            verify_res = guard.verify_facts(p_str)
            if isinstance(verify_res, dict):
                if not verify_res.get("passed", True):
                    for drift in verify_res.get("drifts", []):
                        warnings.append(f"项目描述存在指标漂移：{drift}")
                    for unv in verify_res.get("unverified_claims", []):
                        warnings.append(f"项目描述存在未核验事实：{unv}")
            elif hasattr(verify_res, "passed") and not verify_res.passed:
                for issue in getattr(verify_res, "issues", []):
                    warnings.append(f"项目描述存在未核验事实：{issue}")

        return PersonalStatementDraft(
            applicant_name=name,
            target_school=target_school,
            target_major=target_major,
            academic_background=academic_bg,
            research_interests=interests,
            practical_projects=projects[:4],
            academic_achievements=achievements[:3] if achievements else [],
            graduate_study_plan=study_plan,
            word_count=len(full_text),
            warnings=warnings,
        )


# =============================================================================
# Taocixin Outreach Builder
# =============================================================================

class TaocixinOutreachBuilder:
    """Builds personalized advisor outreach emails and follow-up ledger entries."""

    def build_email(
        self,
        applicant_name: str,
        applicant_school: str,
        applicant_major: str,
        professor_name: str,
        target_school: str,
        target_lab: str,
        paper_title: str,
        applicant_strengths: List[str],
        gpa_rank: str = "",
    ) -> TaocixinLetterDraft:
        subject = f"【保研自荐】{applicant_school}{applicant_name}申请{target_school}{target_lab}研究生"
        greeting = f"尊敬的{professor_name}老师："
        body = (
            f"您好！我是{applicant_school}{applicant_major}的本科生{applicant_name}"
            + (f"（{gpa_rank}）" if gpa_rank else "")
            + f"。一直密切关注您在{target_school}{target_lab}的科研工作。\n\n"
            f"近期拜读了您发表的论文《{paper_title}》，对文中所提出的核心思路深受启发。"
            f"结合我过往在{'、'.join(applicant_strengths[:2])}方面的实践经验，"
            f"我非常希望能在您的指导下攻读硕士/博士学位。\n\n"
            f"随信附上我的个人简历与推免申请材料包，期盼能有机会向您汇报和请教！"
        )
        closing = f"祝好，\n{applicant_name}\n{applicant_school}"

        ledger_row = {
            "professor": professor_name,
            "school": target_school,
            "lab": target_lab,
            "status": "DRAFTED",
            "contact_date": "2026-06-01",
            "paper_referenced": paper_title,
        }

        return TaocixinLetterDraft(
            applicant_name=applicant_name,
            professor_name=professor_name,
            target_school=target_school,
            target_lab=target_lab,
            email_subject=subject,
            greeting=greeting,
            body=body,
            closing=closing,
            ledger_row=ledger_row,
        )
