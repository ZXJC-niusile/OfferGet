"""
Tests for Baoyan Application Package Builder (core/baoyan_package.py)
=====================================================================
Validates:
1. BaoyanPackageBuilder: config validation, manifest computation, TOC grouping.
2. PersonalStatementBuilder: 5-part structure, ProfileContext integration, audit warnings.
3. TaocixinOutreachBuilder: personalized email draft, ledger row formatting.
"""

import pytest
from core.baoyan_package import (
    ApplicantInfo,
    BaoyanPackageBuilder,
    PackageConfig,
    PackageDocument,
    PackageManifest,
    PackageSection,
    PersonalStatementBuilder,
    SchoolInfo,
    TaocixinOutreachBuilder,
    TocEntry,
)
from core.profile_adapter import build_profile_context


class TestBaoyanPackageBuilder:

    def test_validate_config_missing_fields(self):
        builder = BaoyanPackageBuilder()
        valid, errors = builder.validate_config({})
        assert not valid
        assert any("school.name" in e for e in errors)
        assert any("applicant.name" in e for e in errors)
        assert any("sections" in e for e in errors)

    def test_build_manifest_happy_path(self):
        builder = BaoyanPackageBuilder()
        config = {
            "school": {
                "name": "清华大学",
                "english": "Tsinghua University",
                "primary_color": "#660874",
                "package_title": "2026年优秀大学生夏令营申请材料",
                "application_label": "申请学院",
                "application_value": "计算机科学与技术系",
            },
            "applicant": {
                "name": "李华",
                "undergraduate_school": "北京航空航天大学",
                "major": "软件工程",
                "date_label": "2026年6月",
                "gpa": "3.92/4.0",
                "rank": "1/120",
            },
            "sections": [
                {
                    "number": "01",
                    "title": "个人材料",
                    "documents": [
                        {"label": "中英文简历", "group": "个人简历", "page_count": 2},
                        {"label": "个人陈述", "group": "个人陈述", "page_count": 2},
                    ],
                },
                {
                    "number": "02",
                    "title": "学业证明",
                    "documents": [
                        {"label": "本科成绩单", "group": "学业成绩", "page_count": 1},
                        {"label": "专业排名证明", "group": "学业成绩", "page_count": 1},
                        {"label": "四六级成绩单", "group": "英语水平", "page_count": 1},
                    ],
                },
            ],
        }

        manifest = builder.build_manifest(config)
        assert isinstance(manifest, PackageManifest)
        assert manifest.school.name == "清华大学"
        assert manifest.applicant.name == "李华"

        # Page 1: Cover, Page 2: TOC.
        # Section 01:
        # - 个人简历: 2 pages -> Page 3, 4 (03 - 04)
        # - 个人陈述: 2 pages -> Page 5, 6 (05 - 06)
        # Section 02:
        # - 学业成绩 (2 contiguous docs): 1 + 1 pages -> Page 7, 8 (07 - 08)
        # - 英语水平: 1 page -> Page 9 (09)
        # Total pages = 9
        assert manifest.total_pages == 9

        toc = manifest.toc_entries
        assert len(toc) == 4

        assert toc[0].group_label == "个人简历"
        assert toc[0].start_page == 3
        assert toc[0].end_page == 4
        assert toc[0].page_range_display == "03 - 04"

        assert toc[1].group_label == "个人陈述"
        assert toc[1].start_page == 5
        assert toc[1].end_page == 6
        assert toc[1].page_range_display == "05 - 06"

        assert toc[2].group_label == "学业成绩"
        assert toc[2].start_page == 7
        assert toc[2].end_page == 8
        assert toc[2].page_range_display == "07 - 08"

        assert toc[3].group_label == "英语水平"
        assert toc[3].start_page == 9
        assert toc[3].end_page == 9
        assert toc[3].page_range_display == "09"


class TestPersonalStatementBuilder:

    def test_build_statement_from_profile(self):
        builder = PersonalStatementBuilder()
        profile_data = {
            "name": "王五",
            "degree_school": "浙江大学",
            "major": "计算机科学与技术",
            "education": {
                "school": "浙江大学",
                "major": "计算机科学与技术",
                "gpa": "3.88",
                "rank": "3/150",
            },
            "experience": [
                {
                    "title": "大模型分布式微调平台",
                    "bullets": [
                        "主导开发分布式微调流水线，吞吐量提升 40%",
                        "实现低延迟 KV Cache 管理机制",
                    ],
                }
            ],
            "awards": ["国家奖学金", "全国大学生数学建模竞赛一等奖"],
        }

        draft = builder.build_statement(
            profile_data=profile_data,
            target_school="上海交通大学",
            target_major="计算机科学与技术",
            research_interests=["高效机器学习", "异构加速"],
        )

        assert draft.applicant_name == "王五"
        assert draft.target_school == "上海交通大学"
        assert "浙江大学" in draft.academic_background
        assert "3/150" in draft.academic_background
        assert len(draft.research_interests) == 2
        assert len(draft.practical_projects) > 0
        assert draft.word_count > 200
        assert not draft.warnings


class TestTaocixinOutreachBuilder:

    def test_build_email(self):
        builder = TaocixinOutreachBuilder()
        letter = builder.build_email(
            applicant_name="赵六",
            applicant_school="华中科技大学",
            applicant_major="软件工程",
            professor_name="张",
            target_school="北京大学",
            target_lab="系统软件实验室",
            paper_title="Fast Distributed Graph Neural Network Training",
            applicant_strengths=["图计算优化", "C++ 高性能并发"],
            gpa_rank="前 2%",
        )

        assert "【保研自荐】" in letter.email_subject
        assert "华中科技大学赵六" in letter.email_subject
        assert "张老师" in letter.greeting
        assert "Fast Distributed Graph Neural Network Training" in letter.body
        assert "图计算优化" in letter.body
        assert letter.ledger_row["professor"] == "张"
        assert letter.ledger_row["status"] == "DRAFTED"
