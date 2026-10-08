"""Academic theme contracts; real browser geometry and PDFs are checked in CI."""

import copy
import re
from pathlib import Path

import pytest

from core.autofit import AutoFitEngine, TUNING_LADDER
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_modern_navy_layout import fixtures, synthetic_photo, text_content

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "themes/academic-postgraduate.html").read_text(encoding="utf-8")


def academic_profile(long=False):
    """Fabricated academic application, never a real student's biography."""
    profile = copy.deepcopy(fixtures()[0]["profile"])
    profile["intent"] = "计算机科学硕士 / MSc Computer Science"
    profile["postgraduate_exam"] = {
        "target_school": "示例大学 / Example University",
        "target_major": "计算机科学与技术 / Computer Science",
        "direction": "可信软件 / Reliable Software",
        "scores": {"思想政治理论": "72", "英语（一）": "78", "数学（一）": "125", "计算机学科基础": "120"},
        "total_score": "395",
    }
    if long:
        profile["postgraduate_exam"].update({
            "target_school": "InternationalInstituteOfAdvancedComputingAndInterdisciplinaryResearch" * 2,
            "direction": "分布式系统的形式化验证与可信软件研究 / Formal Verification of Distributed Systems",
            "scores": {"思想政治理论 / Political Theory": "72", "英语（一） / Academic English": "78",
                       "AdvancedMathematicsAndStatisticalMethods" * 2: "125",
                       "计算机学科专业基础综合 / Computer Science Foundations": "120"},
        })
    return profile


@pytest.mark.parametrize("long", [False, True])
@pytest.mark.parametrize("photo", ["none", "reserved", "embedded"])
def test_academic_content_survives_production_markup(long, photo):
    profile = academic_profile(long)
    original = copy.deepcopy(profile)
    vm = ResumeViewModel.from_profile(profile, reserve_photo=photo == "reserved")
    if photo == "embedded":
        vm.photo_data_uri = synthetic_photo()
    renderer = HtmlThemeRenderer()
    actual = renderer.render(vm, "academic-postgraduate", template_content=TEMPLATE)
    unstyled = renderer.render(vm, "academic-postgraduate", template_content=re.sub(
        r"<style>.*?</style>", "", TEMPLATE, flags=re.DOTALL))
    assert profile == original
    assert text_content(actual) == text_content(unstyled)
    assert "{{" not in actual
    assert "申请方向：" in actual
    assert "exam-score-table" in actual
    assert profile["postgraduate_exam"]["target_school"] in actual
    for name, score in profile["postgraduate_exam"]["scores"].items():
        assert name in actual
        assert f">{score}</td>" in actual
    assert ">395</td>" in actual
    assert ('class="photo-placeholder"' in actual) == (photo != "none")
    assert ('<img src="data:image/png;base64,' in actual) == (photo == "embedded")
    assert validate_output_security(actual, format_type="html") == []


@pytest.mark.parametrize("scores,total", [({}, "395"), ({"英语（一）": "78"}, "78"),
                                         ({"数学": "125", "专业课": "120"}, "245")])
def test_score_table_preserves_variable_subjects(scores, total):
    profile = academic_profile()
    profile["postgraduate_exam"].update(scores=scores, total_score=total)
    actual = HtmlThemeRenderer().render(ResumeViewModel.from_profile(profile),
                                       "academic-postgraduate", template_content=TEMPLATE)
    table = actual.split('<table class="exam-score-table"', 1)[1].split("</table>", 1)[0]
    assert len(re.findall(r"<th(?:\s|>)", table)) == len(scores) + 2
    assert f">{total}</td>" in table


@pytest.mark.parametrize("profile", TUNING_LADDER, ids=lambda p: p.name)
def test_academic_autofit_controls_and_repeated_print_gutters(profile):
    actual = AutoFitEngine(renderer=object()).apply_profile_to_html(TEMPLATE, profile)
    expected = {"--body-line-height": str(profile.line_height),
                "--page-padding-y": f"{profile.padding_y_mm}mm",
                "--page-padding-x": f"{profile.padding_x_mm}mm",
                "--body-font-size": f"{profile.font_size_px}px",
                "--item-gap": f"{profile.item_gap_px}px",
                "--section-gap": f"{profile.section_gap_px}px"}
    for name, value in expected.items():
        assert re.findall(re.escape(name) + r":\s*([^;]+);", actual) == [value]
    assert "margin: var(--page-padding-y) 0;" in actual
    assert "min-height: calc(297mm - 2 * var(--page-padding-y));" in actual


def test_academic_specific_markup_has_wrapping_and_plain_table_rules():
    assert "--font-serif:" in TEMPLATE
    assert "--color-accent:" in TEMPLATE
    for selector in (".header-top > *", ".contacts span", ".contacts a", ".edu-grid > div",
                     ".exam-target-bar > span", "#skills li > span"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", TEMPLATE)
        assert rule and "min-width: 0;" in rule.group(1), selector
        assert "overflow-wrap: anywhere;" in rule.group(1), selector
    assert "table-layout: fixed;" in TEMPLATE
    assert "background: transparent !important;" in TEMPLATE
    assert "li::marker" in TEMPLATE
    assert "li::before" not in TEMPLATE
    assert "text-overflow:" not in TEMPLATE
    assert "overflow: hidden" not in TEMPLATE
    assert "@import" not in TEMPLATE
    assert "url(" not in TEMPLATE
