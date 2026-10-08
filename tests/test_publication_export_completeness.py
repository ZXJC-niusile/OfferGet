"""Independent raw-source publication coverage; no browser/compiler claims."""

import copy
from html import escape
from html.parser import HTMLParser
from xml.etree import ElementTree
import zipfile

import pytest

from core.academic_exporter import AcademicExporter
from core.ats_docx_renderer import AtsDocxRenderer
from core.resume_builder import ResumeBuilder
from core.resume_view_model import AtsPlainRenderer, HtmlThemeRenderer, ResumeViewModel


# Deliberately independent of the production field tuple and VM projections.
SOURCE_FACTS = {
    "title": "PubTitleQ7",
    "authors": "PubAuthorsR8",
    "venue": "PubVenueS9",
    "conference": "PubConferenceC2",
    "year": "2097",
    "status": "submitted, not accepted StatusT0",
    "author_role": "supporting author RoleU1",
    "highlight": "PubHighlightW3",
    "summary": "PubSummaryX4",
    "individual_contribution": "only validation ContributionV2",
}
THEMES = (
    "modern-navy", "silicon-clean", "classic-tech", "asu-dense", "sidebar-clean",
    "academic-postgraduate", "engineering-sb2nov", "modern-corporate",
)
FORMATS = THEMES + ("ats-markdown", "ats-html", "docx", "latex", "typst", "academic-html")
HTML_FORMATS = THEMES + ("ats-html", "academic-html")


class TextContent(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_data(self, data):
        self.parts.append(data)


def render(format_name, profile_or_vm, tmp_path):
    vm = (profile_or_vm if isinstance(profile_or_vm, ResumeViewModel)
          else ResumeViewModel.from_profile(profile_or_vm, photo_mode="no-photo"))
    if format_name in THEMES:
        return HtmlThemeRenderer().render(vm, format_name)
    if format_name == "ats-markdown":
        return AtsPlainRenderer().render_markdown(vm)
    if format_name == "ats-html":
        return AtsPlainRenderer().render_html(vm)
    if format_name == "docx":
        path = AtsDocxRenderer().render(vm, tmp_path / "publications.docx")
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join("".join(p.itertext()) for p in root.findall(".//w:p", ns))
    exporter = AcademicExporter()
    if format_name == "latex":
        return exporter.generate_latex(vm, reserve_photo=False)
    if format_name == "typst":
        return exporter.generate_typst(vm, reserve_photo=False)
    return exporter.generate_latex_html_preview(vm, reserve_photo=False)


def text_content(format_name, output):
    if format_name in HTML_FORMATS:
        return "".join(TextContent(output).parts).replace("\xa0", " ")
    # Long-token break controls are layout instructions, not source content.
    return output.replace(r"\allowbreak{}", "").replace(r"\u{200b}", "")


def test_matrix_includes_every_supported_html_theme():
    assert set(THEMES) == set(ResumeBuilder.HTML_THEMES)


@pytest.mark.parametrize("format_name", FORMATS)
def test_every_recognized_field_survives_from_independent_raw_source(format_name, tmp_path):
    profile = {"candidate": {"name": "Synthetic Author"}, "publications": [copy.deepcopy(SOURCE_FACTS)]}
    before = copy.deepcopy(profile)
    output = text_content(format_name, render(format_name, profile, tmp_path))
    assert profile == before
    positions = []
    for key, sentinel in SOURCE_FACTS.items():
        assert sentinel in output, (format_name, key)
        assert output.count(sentinel) == 1, (format_name, key)
        positions.append(output.index(sentinel))
    assert positions == sorted(positions)
    assert "状态：submitted, not accepted StatusT0" in output
    assert "作者角色：supporting author RoleU1" in output
    assert "个人贡献：only validation ContributionV2" in output


@pytest.mark.parametrize("format_name", FORMATS)
@pytest.mark.parametrize("publication", [
    {"title": "OnlyTitleY6"},
    {"status": "accepted, not published StatusA5"},
    {"author_role": "supporting author RoleB6"},
    {"individual_contribution": "validation only ContributionC7"},
])
def test_partial_records_do_not_require_title_or_infer_missing_qualifications(format_name, publication, tmp_path):
    output = text_content(format_name, render(format_name, {"publications": [publication]}, tmp_path))
    for value in publication.values():
        assert value in output
    for key, label in (("status", "状态："), ("author_role", "作者角色："), ("individual_contribution", "个人贡献：")):
        assert (label in output) == (key in publication)
    if "status" not in publication:
        assert "accepted" not in output
        assert "published" not in output


@pytest.mark.parametrize("format_name", FORMATS)
@pytest.mark.parametrize("publications", [None, [], [{}], [{"title": "", "status": None, "authors": []}],
                                           [{"title": "  ", "summary": [None, ""]}], [None, 42]])
def test_missing_and_empty_records_do_not_emit_publication_sections(format_name, publications, tmp_path):
    profile = {} if publications is None else {"publications": publications}
    output = render(format_name, profile, tmp_path)
    for heading in ("学术成果", "学术发表", "PUBLICATIONS", "/ Publications"):
        assert heading not in output
    assert 'id="publications"' not in output
    assert "状态：" not in output


@pytest.mark.parametrize("format_name", FORMATS)
def test_ordered_string_lists_and_plain_publication_strings_are_preserved(format_name, tmp_path):
    profile = {"publications": [
        "CitationOneZ1",
        {"title": "CitationTwoZ2", "authors": ["AuthorOneZ3", "AuthorTwoZ4"],
         "highlight": ["HighlightOneZ5", "HighlightTwoZ6"],
         "summary": ["SummaryOneZ7", "SummaryTwoZ8"],
         "individual_contribution": ["ContributionOneZ9", "ContributionTwoZ0"]},
        "CitationThreeN1",
    ]}
    output = text_content(format_name, render(format_name, profile, tmp_path))
    expected = ["CitationOneZ1", "CitationTwoZ2", "AuthorOneZ3; AuthorTwoZ4",
                "HighlightOneZ5; HighlightTwoZ6", "SummaryOneZ7; SummaryTwoZ8",
                "ContributionOneZ9; ContributionTwoZ0", "CitationThreeN1"]
    positions = [output.index(value) for value in expected]
    assert positions == sorted(positions)
    assert "['" not in output


@pytest.mark.parametrize("format_name", FORMATS)
def test_legacy_escaped_vm_and_raw_precedence_do_not_double_decode(format_name, tmp_path):
    vm = ResumeViewModel(name="Synthetic Author", reserve_photo=False, publications=[
        {key: escape(value) for key, value in SOURCE_FACTS.items()},
        {"title": "StaleTitle", "raw_title": "Literal &amp; Entity",
         "status": "StaleAccepted", "raw_status": ""},
    ])
    output = text_content(format_name, render(format_name, vm, tmp_path))
    for value in SOURCE_FACTS.values():
        assert value in output
    assert "StaleTitle" not in output
    assert "StaleAccepted" not in output
    expected = r"Literal \&amp; Entity" if format_name == "latex" else "Literal &amp; Entity"
    assert expected in output


@pytest.mark.parametrize("format_name", FORMATS)
def test_markup_qualifiers_are_literal_and_format_escaped(format_name, tmp_path):
    # Every newly exposed optional field is independently checked for escaping.
    value = '<script>x</script> & 50% #tag {x} **own**'
    profile = {"publications": [{key: value for key in SOURCE_FACTS}]}
    output = render(format_name, profile, tmp_path)
    if format_name in HTML_FORMATS:
        parser = TextContent(output)
        assert "script" not in parser.tags
        assert " ".join(parser.parts).count(value) == len(SOURCE_FACTS)
        assert '&lt;script&gt;x&lt;/script&gt; &amp; 50%' in output
    elif format_name == "latex":
        assert output.count(r'<script>x</script> \& 50\% \#tag \{x\} **own**') == len(SOURCE_FACTS)
        assert r"\input" not in output
    elif format_name == "typst":
        expected = r'\<script\>x\<\/script\> & 50% \#tag {x} \*\*own\*\*'
        assert output.count(expected) == len(SOURCE_FACTS)
    else:
        # ATS Markdown is the existing plain-text source contract; DOCX stores literal text.
        assert output.count(value) == len(SOURCE_FACTS)


@pytest.mark.parametrize("format_name", FORMATS)
def test_unknown_metadata_is_not_serialized_as_publication_content(format_name, tmp_path):
    profile = {"publications": [{"title": "PublicTitleP2", "internal_note": "PrivateNoteK9"}]}
    output = text_content(format_name, render(format_name, profile, tmp_path))
    assert "PublicTitleP2" in output
    assert "PrivateNoteK9" not in output


def test_typst_multiline_qualifiers_stay_in_the_original_bullet(tmp_path):
    profile = {"publications": [{"title": "MultilineQ2", "summary": "Start\n- literal\n= heading"}]}
    output = render("typst", profile, tmp_path)
    assert "Start\n  " + r"\- literal" + "\n  " + r"\= heading" in output
