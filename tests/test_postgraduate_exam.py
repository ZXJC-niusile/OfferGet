"""Tests for Postgraduate Entrance Exam Widget in ResumeViewModel and Themes.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from core.profile_adapter import normalize_candidate_profile
from core.resume_view_model import (
    ResumeViewModel,
    HtmlThemeRenderer,
    AtsPlainRenderer,
)
from core.academic_exporter import AcademicExporter


@pytest.fixture
def base_candidate_profile():
    return {
        "candidate": {
            "name": "张研",
            "title": "计算机科学与技术学术硕士",
            "phone": "13800000000",
            "email": "zhangyan@example.com",
            "location": "北京",
            "school": "北京航空航天大学",
            "degree": "工学学士",
            "edu_time": "2020.09 - 2024.06",
        },
        "experience": [
            {
                "org": "清华大学软件学院",
                "role": "科研助理",
                "time": "2023.07 - 2024.01",
                "bullets": ["参与分布式流处理系统的设计与性能优化。"],
            }
        ],
        "competencies": {
            "编程语言": ["C++", "Python", "Go"],
        },
    }


def test_resume_view_model_with_postgraduate_exam(base_candidate_profile):
    prof = dict(base_candidate_profile)
    prof["postgraduate_exam"] = {
        "target_school": "清华大学",
        "target_major": "计算机科学与技术",
        "direction": "智能系统与系统软件",
        "politics": 78,
        "foreign_language": 82,
        "math_or_business_one": 125,
        "major_subject": 130,
        "total_score": 415,
    }

    vm = ResumeViewModel.from_profile(prof)
    assert vm.postgraduate_exam is not None
    assert vm.postgraduate_exam["target_school"] == "清华大学"
    assert vm.postgraduate_exam["target_major"] == "计算机科学与技术"
    assert vm.postgraduate_exam["direction"] == "智能系统与系统软件"
    assert vm.postgraduate_exam["total_score"] == "415"

    subjects = {s["raw_name"]: s["raw_score"] for s in vm.postgraduate_exam["subjects"]}
    assert subjects["政治"] == "78"
    assert subjects["英语（一）"] == "82"
    assert subjects["数学（一）"] == "125"
    assert subjects["专业课"] == "130"


def test_resume_view_model_auto_computes_total_score(base_candidate_profile):
    prof = dict(base_candidate_profile)
    prof["postgraduate_exam"] = {
        "target_school": "浙江大学",
        "target_major": "软件工程",
        "politics": 75,
        "foreign_language": 80,
        "math_or_business_one": 120,
        "major_subject": 125,
        # total_score omitted
    }

    vm = ResumeViewModel.from_profile(prof)
    assert vm.postgraduate_exam is not None
    assert vm.postgraduate_exam["total_score"] == "400"


def test_resume_view_model_scores_dict_format(base_candidate_profile):
    prof = dict(base_candidate_profile)
    prof["postgraduate_exam"] = {
        "target_school": "中国科学院大学",
        "target_major": "计算科学",
        "scores": {
            "思想政治理论": 80,
            "英语（一）": 85,
            "数学（一）": 130,
            "408计算机专业基础": 135,
            "总分": 430,
        },
    }

    vm = ResumeViewModel.from_profile(prof)
    assert vm.postgraduate_exam is not None
    assert vm.postgraduate_exam["target_school"] == "中国科学院大学"
    assert vm.postgraduate_exam["total_score"] == "430"
    sub_names = [s["name"] for s in vm.postgraduate_exam["subjects"]]
    assert "408计算机专业基础" in sub_names


def test_resume_view_model_without_postgraduate_exam(base_candidate_profile):
    vm = ResumeViewModel.from_profile(base_candidate_profile)
    assert vm.postgraduate_exam is None

    renderer = HtmlThemeRenderer()
    html = renderer.render(vm, theme_name="academic-postgraduate")
    assert "报考信息" not in html
    assert "postgraduate-exam" not in html

    ats = AtsPlainRenderer()
    md = ats.render_markdown(vm)
    assert "报考信息" not in md


def test_html_theme_renderer_academic_postgraduate(base_candidate_profile):
    prof = dict(base_candidate_profile)
    prof["postgraduate_exam"] = {
        "target_school": "清华大学",
        "target_major": "计算机科学与技术",
        "politics": 78,
        "foreign_language": 82,
        "math_or_business_one": 125,
        "major_subject": 130,
        "total_score": 415,
    }

    vm = ResumeViewModel.from_profile(prof)
    renderer = HtmlThemeRenderer()
    html = renderer.render(vm, theme_name="academic-postgraduate")

    assert '<section id="postgraduate-exam">' in html
    assert "<h2>报考信息</h2>" in html
    assert "清华大学" in html
    assert "计算机科学与技术" in html
    assert "exam-score-table" in html
    assert "415" in html
    # Check that header adapted to academic theme
    assert "申请方向：" in html


def test_ats_plain_renderer_with_postgraduate_exam(base_candidate_profile):
    prof = dict(base_candidate_profile)
    prof["postgraduate_exam"] = {
        "target_school": "复旦大学",
        "target_major": "数据科学",
        "politics": 76,
        "foreign_language": 84,
        "math_or_business_one": 118,
        "major_subject": 122,
        "total_score": 400,
    }

    vm = ResumeViewModel.from_profile(prof)
    renderer = AtsPlainRenderer()

    # Markdown test
    md = renderer.render_markdown(vm)
    assert "## 报考信息" in md
    assert "报考院校：复旦大学" in md
    assert "总分：400" in md

    # HTML test
    html = renderer.render_html(vm)
    assert "<h2>报考信息</h2>" in html
    assert "复旦大学" in html
    assert "400" in html


def test_academic_exporter_with_postgraduate_exam(base_candidate_profile):
    prof = dict(base_candidate_profile)
    prof["postgraduate_exam"] = {
        "target_school": "上海交通大学",
        "target_major": "人工智能",
        "politics": 79,
        "foreign_language": 85,
        "math_or_business_one": 130,
        "major_subject": 132,
        "total_score": 426,
    }

    vm = ResumeViewModel.from_profile(prof)
    exporter = AcademicExporter()

    # LaTeX
    tex = exporter.generate_latex(vm)
    assert r"\section*{报考信息}" in tex
    assert "上海交通大学" in tex
    assert "tabularx" in tex
    assert "426" in tex

    # Typst
    typ = exporter.generate_typst(vm)
    assert "== 报考信息" in typ
    assert "上海交通大学" in typ
    assert "#table(" in typ
    assert "426" in typ

    # HTML preview
    prev = exporter.generate_latex_html_preview(vm)
    assert "<h2>报考信息</h2>" in prev
    assert "上海交通大学" in prev
    assert "426" in prev


def test_xss_protection_in_postgraduate_exam(base_candidate_profile):
    prof = dict(base_candidate_profile)
    prof["postgraduate_exam"] = {
        "target_school": "<script>alert('xss')</script>北京大学",
        "target_major": "软件工程<img src=x onerror=1>",
        "politics": "70<script>",
        "foreign_language": "80",
        "math_or_business_one": "100",
        "major_subject": "110",
        "total_score": "360",
    }

    vm = ResumeViewModel.from_profile(prof)
    renderer = HtmlThemeRenderer()
    html = renderer.render(vm, theme_name="academic-postgraduate")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html
    assert "&lt;img" in html
