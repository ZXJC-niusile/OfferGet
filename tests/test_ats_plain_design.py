"""Narrow ATS plain design and source contracts; all fixtures are fabricated."""
import copy
import hashlib
from html.parser import HTMLParser

import pytest

from core.resume_view_model import AtsPlainRenderer, ResumeViewModel
from core.security_gate import validate_output_security
from scripts.qa_ats_plain_layout import cases, source_anchors, squash
from scripts.qa_modern_navy_layout import text_content

# Generated with the unchanged renderer at main f01d6c1. These protect the
# existing serialization contract, not a claim of baseline factual correctness.
MARKDOWN_SHA256 = {
    "short-none": "6a6ae08d29a340d317f857dcdd212d3d433d2747d8ac8546385575cec49550f7",
    "short-reserved": "4367873a83f29c5ce7e691e6d0e3b9a4ef8279d352bb440f5f6e6b34dc66bb2e",
    "long-none": "a9f3b528b8141a1c3550d5eb0465b4262f37e3b0478d6dfe05ca7f5f8636d482",
    "long-reserved": "3eecbb08e0b042aa12d675603a13920ae59dcebcc67427e185bd5a9ba46f65a0",
    "dense-none": "51958447589e4340539cc6f6efeeef0e0ecc7cb73915d72b06ab09658064cafd",
    "professional-none": "ea6ce5c872af233a7f3cc3088fb9477effeb99b38e776e1c4364f228cfce84de",
    "professional-reserved": "1aa8470e23fddaac56eb8b8df65119dd1ac1736b71de6c154ed5cd6a0958fe75",
    "professional-embedded": "9d97f46a3d3ecacdc66203c4c455989f757655c874b985c0e84a7e36e422f78c",
    "exam-long-none": "aa6cc7a9b408114f6b5385d54dd6961c3ae2e64cbeae94402d06150f2bbdad0d",
    "aliases-none": "2c6b9babe50970e23ae721c391c1b95a688d5dd12d0ac887ea2714b485ec47bd",
    "structured-none": "af72ed6eb2d2b264158abd3180f570c5a1bb07c6c2162af7b06955bf272c7e2f",
}


def render(case):
    vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=case["photo"] != "none")
    vm.photo_data_uri = case.get("photo_data_uri")
    return AtsPlainRenderer().render(vm)


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["name"])
def test_every_synthetic_source_fact_survives_in_html(case):
    original = copy.deepcopy(case)
    body = squash(text_content(render(case)["html"]))
    for anchor in source_anchors(case["profile"]):
        assert anchor in body, anchor
    assert case == original


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["name"])
def test_markdown_serialization_is_unchanged(case):
    assert hashlib.sha256(render(case)["md"].encode()).hexdigest() == MARKDOWN_SHA256[case["name"]]


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_semantic_single_column_and_readable_type():
    html = render(cases()[0])["html"]
    tags = Elements(html).tags
    assert [tag for tag, _ in tags].count("main") == 1
    assert [tag for tag, _ in tags].count("h1") == 1
    assert [tag for tag, _ in tags].count("h2") == 4
    assert [tag for tag, _ in tags].count("h3") == 3
    assert not any(tag in {"table", "aside", "svg", "canvas"} for tag, _ in tags)
    for prohibited in ("display:grid", "display: grid", "box-shadow", "linear-gradient", "text-align: justify",
                       "position: absolute", "white-space: nowrap", "column-count", "text-overflow: ellipsis"):
        assert prohibited not in html
    assert "font-size: 10.5pt" in html
    assert "overflow-wrap: anywhere" in html
    assert "margin: 15mm 16mm" in html
    assert "break-after: avoid" in html
    assert "@media print" in html and "padding: 0" in html
    assert 'name="viewport"' in html


def test_dates_follow_headings_and_education_cells_are_linear():
    case = next(case for case in cases() if case["name"] == "aliases-none")
    html = render(case)["html"]
    assert '<h3 class="item-header">Alias Institute · MSc</h3>' in html
    assert '<p class="item-date">2018 - 2020</p>' in html
    assert '<div class="edu-grid"><p>GPA 3.8/4.0</p><p>Synthetic Scholarship</p></div>' in html
    assert "<h3 class='item-header'>Alias Research · R&amp;D · Research Engineer</h3><p class=\"item-date\">2020 - 2024</p>" in html
    assert html.index("Alias Research") < html.index("2020 - 2024") < html.index("ATS-ALIAS-FACT")


@pytest.mark.parametrize("photo", ["none", "reserved", "embedded"])
def test_photo_choices_remain_opt_in_at_render_time(photo):
    case = next(case for case in cases() if case["name"] == f"professional-{photo}")
    html = render(case)["html"]
    tags = Elements(html).tags
    images = [attrs for tag, attrs in tags if tag == "img"]
    assert len(images) == (1 if photo == "embedded" else 0)
    if photo == "embedded":
        assert "onerror=" not in html
        assert "photo-fallback" not in html
        assert images[0]["alt"] == "证件照"
        assert images[0]["src"].startswith("data:image/png;base64,")
    assert ("预留证件照" in text_content(html)) == (photo == "reserved")


def test_escaping_and_source_supported_bold_are_preserved():
    case = next(case for case in cases() if case["name"] == "exam-long-none")
    case["profile"]["name"] = "Alex <script>alert('qa')</script> & 示例"
    html = render(case)["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<strong>C++ &amp; Python</strong>" in html
    assert "Systems &amp; Reliability &lt;Research&gt;" in html
    assert "latency < 20 ms." in text_content(html)
    assert validate_output_security(html, format_type="html") == []


def test_missing_contacts_do_not_create_empty_labels():
    html = AtsPlainRenderer().render_html(ResumeViewModel(name="Example", reserve_photo=False))
    body = text_content(html)
    assert "电话：" not in body and "邮箱：" not in body
    assert "求职意向：" not in body
    assert "<h3" not in html
