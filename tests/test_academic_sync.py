from __future__ import annotations

import pytest
from core.academic_sync import (
    AcademicPublication,
    BibTexPublicationParser,
    CampPresentationPlan,
    CampPresentationPlanner,
)


def test_bibtex_parser_conference_and_ccf():
    bib = """
@inproceedings{li2025fast,
  title = {{Fast distributed consensus via adaptive speculation}},
  author = {Li, Ming and Zhang, Wei and Wang, Gang},
  booktitle = {Proceedings of the 2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year = {2025},
  doi = {10.1109/CVPR.2025.0001},
  presentation = {Oral}
}
@article{zhang2024scaling,
  title = {Scaling large language models efficiently},
  author = {Wei Zhang and Ming Li},
  journal = {ACM Transactions on Computer Systems (TOCS)},
  year = {2024},
  doi = {10.1145/3600000}
}
"""
    pubs = BibTexPublicationParser.parse_string(bib, candidate_name="Ming Li")
    assert len(pubs) == 2

    p1 = pubs[0]
    assert p1.cite_key == "li2025fast"
    assert p1.title == "Fast distributed consensus via adaptive speculation"
    assert p1.entry_type == "inproceedings"
    assert p1.year == 2025
    assert p1.ccf_rank == "CCF-A"
    assert p1.presentation_type == "Oral"
    assert p1.is_first_or_corresponding is True
    assert p1.doi == "10.1109/CVPR.2025.0001"

    p2 = pubs[1]
    assert p2.cite_key == "zhang2024scaling"
    assert p2.entry_type == "article"
    assert p2.year == 2024
    assert p2.is_first_or_corresponding is False  # 候选人为二作


def test_camp_presentation_planner():
    pub = AcademicPublication(
        cite_key="li2025fast",
        entry_type="inproceedings",
        title="Adaptive Speculative Execution for Distributed Systems",
        authors=["Ming Li", "Wei Zhang"],
        venue="USENIX ATC",
        year=2025,
        ccf_rank="CCF-A",
    )

    plan = CampPresentationPlanner.plan(
        candidate_name="李明",
        target_lab_or_institution="清华大学计算机系网络技术研究所",
        target_direction="分布式系统与云原生底座",
        publications=[pub],
        key_projects=["高并发分布式KV引擎", "自研内核级旁路网关"],
    )

    assert isinstance(plan, CampPresentationPlan)
    assert plan.candidate_name == "李明"
    assert plan.target_lab_or_institution == "清华大学计算机系网络技术研究所"
    assert len(plan.slides) == 4

    # 验证单页结构与控时
    total_allocated = sum(s.allocated_seconds for s in plan.slides)
    assert total_allocated == 210  # 45 + 60 + 60 + 45

    s1, s2, s3, s4 = plan.slides
    assert "学术画像" in s1.slide_title
    assert "李明" in s1.script_preview

    assert "科研突破" in s2.slide_title
    assert "USENIX ATC" in s2.script_preview or "USENIX ATC" in s2.key_talking_points[1]

    assert "系统工程" in s3.slide_title
    assert "分布式KV引擎" in s3.script_preview or "高并发分布式KV引擎" in s3.key_talking_points[0]

    assert "学术志趣" in s4.slide_title
    assert "清华大学计算机系网络技术研究所" in s4.script_preview

    assert "# 🎓 李明 - 夏令营/保研面试 4 页自述 PPT 规范方案" in plan.markdown_outline
