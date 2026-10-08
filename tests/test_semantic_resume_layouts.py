"""Runtime contracts for the first three structural layouts (no browser claims)."""

import copy
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel

PILOTS = ("modern-navy", "classic-tech", "silicon-clean")
LEGACY = (
    "modern-corporate",
    "asu-dense",
    "sidebar-clean",
    "academic-postgraduate",
    "engineering-sb2nov",
)
PROFILE = {
    "name": "Synthetic 候选人",
    "intent": "Platform Engineer",
    "phone": "+00 5550100",
    "email": "synthetic@resume.invalid",
    "city": "测试城市",
    "education": {
        "school": "Synthetic University",
        "degree": "BSc Computer Science",
        "time": "2020–2024",
        "gpa": "GPA 3.5/4.0",
    },
    "experience": [
        {
            "company": "Synthetic Org A",
            "dept": "Platform",
            "role": "Engineer A",
            "time": "2024–2025",
            "bullets": ["First **12ms** evidence", "Second 原始事实"],
        },
        {
            "company": "Synthetic Org B",
            "role": "Engineer B",
            "time": "2023–2024",
            "bullets": ["Third ordered evidence"],
        },
    ],
    "campus_experience": [
        {
            "name": "Synthetic Project",
            "role": "Contributor",
            "time": "2022–2023",
            "bullets": ["Project fact one", "Project fact two"],
        }
    ],
    "skills": {"Languages": ["Python", "SQL"], "能力": ["系统设计", "Testing"]},
    "publications": [
        {
            "title": "Synthetic <Paper>",
            "authors": "Fictional Author",
            "venue": "Draft, not accepted",
            "year": "2025",
        }
    ],
}


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = {
            "tag": tag,
            "attrs": dict(attrs),
            "parent": self.stack[-1] if self.stack else None,
            "text": "",
        }
        self.nodes.append(node)
        if tag not in {"meta", "img", "br", "link", "input", "hr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        for node in self.stack:
            node["text"] += text

    def matching(self, attr, value=None):
        return [
            node
            for node in self.nodes
            if attr in node["attrs"] and (value is None or node["attrs"][attr] == value)
        ]

    def fields(self):
        return [
            (node["attrs"]["data-field"], " ".join(node["text"].split()))
            for node in self.matching("data-field")
        ]

    def classes(self, value):
        return [
            node
            for node in self.nodes
            if value in node["attrs"].get("class", "").split()
        ]


def render(theme, profile=None, reserve=False):
    return HtmlThemeRenderer().render(
        ResumeViewModel.from_profile(profile or PROFILE, reserve_photo=reserve), theme
    )


@pytest.mark.parametrize("theme", PILOTS)
def test_stylesheet_owned_structure_has_no_inline_layout_override(theme):
    doc = Document(render(theme))
    for classname in (
        "resume-header",
        "resume-identity",
        "resume-name",
        "resume-title",
        "resume-contacts",
        "entry-header",
        "entry-identity",
        "entry-title",
        "entry-role",
        "entry-date",
        "skill-row",
        "skill-label",
    ):
        assert doc.classes(classname), classname
        assert all("style" not in node["attrs"] for node in doc.classes(classname)), (
            classname
        )
    assert len(doc.classes("resume-section-body")) == 5
    assert not doc.classes("photo-placeholder")
    assert len(doc.matching("data-layout")) == 1


@pytest.mark.parametrize("theme", PILOTS)
def test_all_entries_bullets_and_publication_facts_are_exact_and_ordered(theme):
    original = copy.deepcopy(PROFILE)
    doc = Document(render(theme))
    assert PROFILE == original
    fields = doc.fields()
    assert len(fields) == len(dict(fields)), "Every field must appear exactly once"
    assert dict(fields)["experience.0.role"] == "Platform · Engineer A"
    assert [(key, value) for key, value in fields if ".bullets." in key] == [
        ("experience.0.bullets.0", "First 12ms evidence"),
        ("experience.0.bullets.1", "Second 原始事实"),
        ("experience.1.bullets.0", "Third ordered evidence"),
        ("projects.0.bullets.0", "Project fact one"),
        ("projects.0.bullets.1", "Project fact two"),
    ]
    assert [
        (key, value) for key, value in fields if key.startswith("publications.")
    ] == [
        ("publications.0.title", "Synthetic <Paper>"),
        ("publications.0.authors", "Fictional Author"),
        ("publications.0.venue", "Draft, not accepted"),
        ("publications.0.year", "2025"),
    ]
    assert not any(node["tag"] == "paper" for node in doc.nodes)
    assert [n["attrs"]["data-entry"] for n in doc.classes("resume-entry")] == [
        "education",
        "experience.0",
        "experience.1",
        "projects.0",
    ]


@pytest.mark.parametrize("theme", PILOTS)
def test_photo_space_does_not_change_factual_fields_or_reading_order(theme):
    assert (
        Document(render(theme)).fields()
        == Document(render(theme, reserve=True)).fields()
    )
    assert len(Document(render(theme, reserve=True)).classes("photo-placeholder")) == 1
    assert "padding-right" not in Document(render(theme)).classes("resume-identity")[0][
        "attrs"
    ].get("style", "")


def test_date_rail_is_source_order_and_keeps_date_inside_its_entry():
    doc = Document(render("classic-tech"))
    for entry in doc.classes("resume-entry"):
        children = [node for node in doc.nodes if node["parent"] is entry]
        assert (
            children[0]["attrs"]["data-field"] == entry["attrs"]["data-entry"] + ".time"
        )
        assert children[1]["attrs"]["class"] == "entry-content"


def test_silicon_sections_have_explicit_column_and_full_width_ownership():
    doc = Document(render("silicon-clean"))
    sections = [node for node in doc.nodes if node["tag"] == "section"]
    assert [node["attrs"]["id"] for node in sections] == [
        "education",
        "experience",
        "projects",
        "publications",
        "skills",
    ]
    owners = {
        node["attrs"]["id"]: node["parent"]["attrs"].get("data-column", "full")
        for node in sections
    }
    assert owners == {
        "education": "full",
        "experience": "left",
        "projects": "right",
        "publications": "right",
        "skills": "full",
    }
    assert len(doc.classes("resume-columns")) == 1


@pytest.mark.parametrize("missing", ["experience", "campus_experience"])
def test_silicon_does_not_reserve_an_empty_editorial_column(missing):
    profile = copy.deepcopy(PROFILE)
    profile[missing] = []
    profile["publications"] = []
    doc = Document(render("silicon-clean", profile))
    assert not doc.classes("resume-columns")
    assert len(doc.classes("resume-single-column")) == 1


@pytest.mark.parametrize("theme", LEGACY)
def test_unmigrated_themes_keep_legacy_structure_and_include_publications(theme):
    doc = Document(render(theme))
    assert not doc.matching("data-layout")
    assert not doc.classes("resume-entry")
    assert not doc.classes("resume-section-body")
    assert len(doc.matching("id", "publications")) == 1


# Canonical legacy section signatures from verified f01d6c1. The header photo
# contract is tested separately because it intentionally changes. Ignore only
# inert semantic annotations/classes, not elements, text, legacy classes or styles.
NEW_CLASSES = {
    "resume-header",
    "resume-identity",
    "resume-name",
    "resume-title",
    "resume-contacts",
    "entry-header",
    "entry-identity",
    "entry-title",
    "entry-role",
    "entry-date",
    "entry-bullets",
    "skill-row",
    "skill-label",
    "skill-value",
    "skills-list",
}


class LegacyShape(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.in_body = True
        if not self.in_body:
            return
        clean = []
        for key, value in attrs:
            if key.startswith(("data-", "aria-")) or (tag == "h2" and key == "id"):
                continue
            if key == "class":
                value = " ".join(
                    part for part in value.split() if part not in NEW_CLASSES
                )
                if not value:
                    continue
            clean.append((key, value))
        self.parts.append(("start", tag, sorted(clean)))

    def handle_endtag(self, tag):
        if self.in_body:
            self.parts.append(("end", tag))
        if tag == "section":
            self.in_body = False

    def handle_data(self, value):
        if self.in_body and value.strip():
            self.parts.append(("text", " ".join(value.split())))


def legacy_signature(html):
    parser = LegacyShape()
    parser.feed(html)
    return hashlib.sha256(
        json.dumps(parser.parts, ensure_ascii=False).encode()
    ).hexdigest()


@pytest.mark.parametrize("theme", LEGACY)
def test_legacy_section_elements_text_and_inline_styles_match_archived_baseline(theme):
    expected = json.loads(
        (Path(__file__).parent / "fixtures/legacy_resume_signatures.json").read_text()
    )
    # Publications were missing in the archive. Preserve every other section's
    # elements, text, and styles; verify the added section independently.
    import re
    html = render(theme)
    without_publications = re.sub(r'<section id="publications".*?</section>', '', html, flags=re.S)
    assert legacy_signature(without_publications) == expected[theme]


@pytest.mark.parametrize("theme", PILOTS)
def test_production_solver_and_autofit_cannot_restore_legacy_date_or_heading_rules(
    theme,
):
    import re

    from core.autofit import TUNING_LADDER, AutoFitEngine
    from core.layout_solver import LayoutConfig, solve_layout

    profile = copy.deepcopy(PROFILE)
    long_date = "2020–present / " + "SyntheticUnbrokenDateQualifier" * 12
    profile["experience"][0]["time"] = long_date
    raw = render(theme, profile)
    solved = solve_layout(raw, config=LayoutConfig(page_mode="auto")).html
    compact = AutoFitEngine(renderer=object()).apply_profile_to_html(
        solved, TUNING_LADDER[-1]
    )
    assert ".org-right, .time, .date" in solved  # Real production CSS injection ran.
    for html in (raw, solved, compact):
        assert dict(Document(html).fields())["experience.0.time"] == long_date
        # A two-class selector outranks the solver's later one-class !important.
        rule = re.search(r"\.resume-sections \.entry-date\s*\{([^}]+)\}", html)
        assert rule and "white-space: normal !important;" in rule.group(1)
        assert (
            ".resume-sections .section-header, .resume-sections h2 { margin-top: 0 !important; }"
            in html
        )
        assert (
            ".resume-sections .entry-bullets, .resume-sections .publication-list, .resume-sections .skills-list"
            in html
        )
        assert "break-inside: auto !important;" in html
        assert "page-break-inside: auto !important;" in html


@pytest.mark.parametrize("theme", PILOTS)
def test_optional_publication_facts_preserve_status_contribution_and_duplicates(theme):
    profile = copy.deepcopy(PROFILE)
    publication = {
        "title": "Synthetic <unpublished draft>",
        "authors": "Synthetic Author",
        "venue": "Synthetic Venue",
        "conference": "Synthetic Conference",
        "year": "2026",
        "status": "under_review",
        "author_role": "second_author",
        "highlight": "Explicit highlight & evidence",
        "summary": "Original summary 原文",
        "individual_contribution": 'Exact contribution <script>alert("x")</script>',
    }
    profile["publications"] = [publication, copy.deepcopy(publication)]
    doc = Document(render(theme, profile))
    fields = [
        (key, value) for key, value in doc.fields() if key.startswith("publications.")
    ]
    assert fields == [
        (f"publications.{index}.{key}", value)
        for index in range(2)
        for key, value in publication.items()
    ]
    assert not [node for node in doc.nodes if node["tag"] == "script"]
    assert "accepted" not in render(theme, profile)
    assert profile["publications"] == [publication, publication]


@pytest.mark.parametrize("theme", PILOTS)
def test_missing_publication_metadata_is_not_invented(theme):
    profile = copy.deepcopy(PROFILE)
    profile["publications"] = [{"title": "Synthetic title only"}]
    doc = Document(render(theme, profile))
    assert [
        (key, value) for key, value in doc.fields() if key.startswith("publications.")
    ] == [("publications.0.title", "Synthetic title only")]
    assert "作者角色：" not in render(theme, profile)
    assert "状态：" not in render(theme, profile)
