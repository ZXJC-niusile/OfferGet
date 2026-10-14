"""Offline Chromium visual regression check using explicitly synthetic resumes.

Run with a git-archived baseline, never a user's resume. This script intentionally
requires real Playwright/Chromium and PyMuPDF; it does not replace a missing browser
with mocked screenshots or pass an unchecked layout. See docs/RESUME_THEME_QA.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
from collections import Counter
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.qa_common import squash
DEFAULT_THEME = "modern-navy"
THEMES = ("modern-navy", "modern-corporate", "classic-tech", "silicon-clean",
          "asu-dense", "sidebar-clean", "academic-postgraduate", "engineering-sb2nov")


def theme_path(theme=DEFAULT_THEME):
    if theme not in THEMES:
        raise ValueError(f"Unsupported HTML theme: {theme}")
    return Path("themes") / f"{theme}.html"


def changed_themes(paths):
    """Select actual edited themes; renderer changes must exercise every theme."""
    paths = set(paths)
    rendering_sources = {"core/resume_view_model.py", "core/resume_builder.py",
                         "core/browser_renderer.py", "core/autofit.py", "core/layout_solver.py"}
    if paths & rendering_sources:
        return list(THEMES)
    selected = {theme for theme in THEMES if theme_path(theme).as_posix() in paths}
    harness_sources = {"scripts/qa_modern_navy_layout.py", "tests/test_resume_theme_qa.py",
                       "tests/test_modern_navy_layout.py", ".github/workflows/resume-visual.yml"}
    if paths & harness_sources or not selected:
        selected.add(DEFAULT_THEME)
    return [theme for theme in THEMES if theme in selected]

# Run the same public rendering API in separate interpreters and source trees.
# Explicit root avoids importing the current tree for the baseline without stripping user site-packages.
GENERATOR = r'''
import base64, copy, inspect, json, sys, tempfile
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.autofit import AutoFitEngine, TUNING_LADDER
from core.layout_solver import LayoutConfig, solve_layout
request = json.load(sys.stdin)
profile = copy.deepcopy(request['profile'])
photo_workspace = tempfile.TemporaryDirectory(prefix='offerget-synthetic-photo-')
photo_path = None
if request['photo'] == 'embedded' or request.get('source_photo'):
    photo_path = Path(photo_workspace.name) / 'synthetic-portrait.png'
    photo_path.write_bytes(base64.b64decode(request['photo_data_uri'].split(',', 1)[1]))
if request.get('source_photo'):
    from core.profile_adapter import normalize_candidate_profile
    profile = normalize_candidate_profile(profile)
    profile['candidate']['photo_path'] = str(photo_path)
    profile['education'] = copy.deepcopy(request['profile'].get('education', {}))
kwargs = {'reserve_photo': request['photo'] != 'none'}
if request['photo'] == 'embedded':
    kwargs['photo_path'] = photo_path
if 'photo_mode' in inspect.signature(ResumeViewModel.from_profile).parameters:
    kwargs['photo_mode'] = {'none': 'no-photo', 'embedded': 'photo', 'reserved': 'placeholder'}[request['photo']]
vm = ResumeViewModel.from_profile(profile, **kwargs)
html = HtmlThemeRenderer().render(vm, request.get('theme', 'modern-navy'), template_dir=root / 'themes')
if request['mode'] == 'compact':
    # Token application is browser-independent; rendering is performed below.
    html = AutoFitEngine(renderer=object()).apply_profile_to_html(html, TUNING_LADDER[-1])
elif request['mode'] == 'solver':
    html = solve_layout(html, config=LayoutConfig(page_mode='auto')).html
sys.stdout.write(html)
'''

# Exercise the real production path as well as focused theme fixtures. Instrument
# the existing APIs without replacing browser measurements or generated PDFs.
BUILDER_GENERATOR = r'''
import base64, copy, inspect, json, sys, tempfile
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from core.resume_builder import ResumeBuilder
from core.browser_renderer import BrowserRenderer
from core.autofit import AutoFitEngine
request = json.load(sys.stdin)
trace = {'measurements': [], 'renders': [], 'autofit': []}
class MeasuredBrowser(BrowserRenderer):
    def measure_overflow(self, *args, **kwargs):
        result = super().measure_overflow(*args, **kwargs)
        trace['measurements'].append(list(result))
        return result
    def render_pdf(self, *args, **kwargs):
        result = super().render_pdf(*args, **kwargs)
        trace['renders'].append({'ok': result[0], 'pages': result[1], 'message': result[2]})
        return result
class MeasuredAutoFit(AutoFitEngine):
    def fit_to_single_page(self, *args, **kwargs):
        result = super().fit_to_single_page(*args, **kwargs)
        trace['autofit'].append({'success': result[0], 'details': result[2]})
        return result
output = Path(request['output_dir'])
output.mkdir(parents=True, exist_ok=True)
try:
    # Match the production CLI's browser discovery, including supported overrides.
    renderer = MeasuredBrowser()
    trace['browserPath'] = str(renderer.browser_path)
    profile = copy.deepcopy(request['profile'])
    photo_workspace = tempfile.TemporaryDirectory(prefix='offerget-synthetic-photo-')
    photo_path = None
    if request['photo'] == 'embedded' or request.get('source_photo'):
        photo_path = Path(photo_workspace.name) / 'synthetic-portrait.png'
        photo_path.write_bytes(base64.b64decode(request['photo_data_uri'].split(',', 1)[1]))
    if request.get('source_photo'):
        from core.profile_adapter import normalize_candidate_profile
        profile = normalize_candidate_profile(profile)
        profile['candidate']['photo_path'] = str(photo_path)
        profile['education'] = copy.deepcopy(request['profile'].get('education', {}))
    kwargs = {'photo_path': photo_path} if request['photo'] == 'embedded' else {}
    if 'photo_mode' in inspect.signature(ResumeBuilder).parameters:
        kwargs['photo_mode'] = {'none': 'no-photo', 'embedded': 'photo', 'reserved': 'placeholder'}[request['photo']]
    builder = ResumeBuilder(profile, template_dir=root / 'themes',
                            renderer=renderer, autofit_engine=MeasuredAutoFit(renderer), **kwargs)
    result = builder.build_html_theme(request.get('theme', 'modern-navy'), output,
        photo=request['photo'] != 'none', pages='auto', autofit=True,
        adaptive_fill=True, diff_ledger=False)
    print(json.dumps({'html': str(result['html']), 'pdf': str(result['pdf']), 'trace': trace}))
finally:
    (output / 'renderer-trace.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')
'''


# Geometry checks inspect actual rendered text ranges, rather than only scrollWidth
# (which misses overlapping flex siblings and text protruding out of inline boxes).
MEASURE = r'''() => {
  const isVisible = el => !!el.getClientRects().length && ![el,...function*(node){while(node.parentElement){node=node.parentElement;yield node;}}(el)]
    .some(node=>getComputedStyle(node).visibility==='hidden' || getComputedStyle(node).opacity==='0' || node.hidden);
  const page = document.querySelector('.page');
  const box = page.getBoundingClientRect();
  const style = getComputedStyle(page);
  const left = box.left + parseFloat(style.paddingLeft);
  const right = box.right - parseFloat(style.paddingRight);
  const out = [];
  const walker = document.createTreeWalker(page, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    for (const rect of range.getClientRects()) {
      if (rect.width && (rect.left < left - 1 || rect.right > right + 1)) {
        out.push({text:node.textContent.trim(), left:rect.left, right:rect.right,
                  overflow:Math.max(left-rect.left, rect.right-right)});
      }
    }
  }
  const overlaps = [];
  const selectors = ['header', '.header-top', '.contacts', '.org-bar', '.org-left',
    '.project-header', '.project-header > div:first-child', '.edu-grid', '#skills li',
    '.exam-target-bar', '.exam-score-table tr', '.resume-entry', '[data-layout]', '.resume-section-body'];
  for (const selector of selectors) {
    for (const parent of document.querySelectorAll(selector)) {
      const children = [...parent.children].filter(el => el.getBoundingClientRect().width);
      for (let i=0;i<children.length;i++) for (let j=i+1;j<children.length;j++) {
        // Inline spans can wrap into several disjoint line rectangles. Their
        // enclosing boxes may overlap even when the actual text does not.
        const rects = element => {
          if (selector !== '#skills li') return [element.getBoundingClientRect()];
          const range = document.createRange(); range.selectNodeContents(element);
          return [...range.getClientRects()].filter(rect=>rect.width && rect.height);
        };
        if (rects(children[i]).some(a=>rects(children[j]).some(b=>
            Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 &&
            Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1))) {
          overlaps.push({selector, first:children[i].textContent.trim(),
                         second:children[j].textContent.trim()});
        }
      }
    }
  }
  const anchors = [...document.querySelectorAll(
    '[data-field], h1, .header-top > span, .contacts > span, .org-title, .org-role, .org-right, '+
    '.project-header > div:first-child > span, .project-header > div:last-child, '+
    '.edu-grid > div, .exam-target-bar > span, .exam-score-table th, .exam-score-table td, li')].map(el=>el.textContent.trim()).filter(Boolean);
  return {pageWidth:box.width, contentWidth:right-left,
          bodyFontPx:parseFloat(getComputedStyle(document.body).fontSize),
          lineHeight:getComputedStyle(document.body).lineHeight,
          overflow:out, overlaps, anchors,
          bodyText:document.body.textContent,
          visibleText:document.body.innerText,
          images:[...document.images].map(img=>({complete:img.complete,width:img.naturalWidth,
            height:img.naturalHeight,displayWidth:img.getBoundingClientRect().width,
            displayHeight:img.getBoundingClientRect().height,objectFit:getComputedStyle(img).objectFit,
            visible:isVisible(img),contained:!img.closest('.photo-placeholder') || (()=>{
              const a=img.getBoundingClientRect(),b=img.closest('.photo-placeholder').getBoundingClientRect();
              return a.left>=b.left-1 && a.right<=b.right+1 && a.top>=b.top-1 && a.bottom<=b.bottom+1;
            })()})),
          photoSlots:document.querySelectorAll('.photo-placeholder').length,
          identityPaddingRight:parseFloat(getComputedStyle(document.querySelector('.resume-identity, header > div:first-child')).paddingRight),
          identityWidth:document.querySelector('.resume-identity, header > div:first-child').getBoundingClientRect().width,
          headerWidth:document.querySelector('header').getBoundingClientRect().width,
          fields:[...document.querySelectorAll('[data-field]')].map(el=>({
            id:el.dataset.field,text:el.textContent,
            visible:isVisible(el)})),
          columns:[...document.querySelectorAll('[data-column]')].map(el=>({
            name:el.dataset.column,left:el.getBoundingClientRect().left-box.left,
            right:el.getBoundingClientRect().right-box.left})),
          headerBottom:document.querySelector('header').getBoundingClientRect().bottom-box.top,
          printPaddingMm:parseFloat(getComputedStyle(document.documentElement)
            .getPropertyValue('--page-padding-y'))};
}'''


class BodyText(HTMLParser):
    """Extract text independent of line wrapping or incidental style whitespace."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            self.parts.append(data)


def text_content(html):
    parser = BodyText()
    parser.feed(html)
    return " ".join("".join(parser.parts).split())




def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def synthetic_portrait_png():
    """Byte-identical, code-drawn test portrait shared by photo-contract tests."""
    from PIL import Image, ImageDraw

    picture = Image.new("RGB", (120, 160), "#E6EDF2")
    draw = ImageDraw.Draw(picture)
    draw.ellipse((40, 22, 80, 70), fill="#D8A47F")
    draw.rectangle((52, 64, 68, 87), fill="#D8A47F")
    draw.rounded_rectangle((21, 83, 99, 164), radius=27, fill="#264C72")
    draw.ellipse((40, 20, 80, 36), fill="#29323B")
    draw.rectangle((3, 3, 116, 156), outline="#C25252", width=2)
    output = io.BytesIO()
    picture.save(output, format="PNG")
    return output.getvalue()


def synthetic_photo():
    """A synthetic head-and-shoulders illustration, never a person's photo."""
    return "data:image/png;base64," + base64.b64encode(synthetic_portrait_png()).decode("ascii")


# Explicit opt-in: legacy themes continue to require exact non-photo body order.
# A marker from an unknown theme cannot silently opt it into weaker comparisons.
STRUCTURAL_LAYOUTS = {"modern-navy": "label-gutter", "classic-tech": "date-rail",
                      "silicon-clean": "balanced-columns"}
PUBLICATION_FIELDS = ("title", "authors", "venue", "conference", "year", "status",
                      "author_role", "highlight", "summary", "individual_contribution")
SECTION_LABELS = {"education": "教育背景", "experience": "实习经历",
                  "projects": "校园与实践经历", "skills": "专业技能",
                  "publications": "学术成果", "postgraduate-exam": "报考信息"}


def plain_fact(value, bold=False):
    # Fixtures support the same documented **bold** presentation convention;
    # this oracle intentionally does not import a normalizer, VM, or renderer.
    value = str(value).strip()
    return re.sub(r"\*\*(.+?)\*\*", r"\1", value) if bold else value


def source_ledger(case):
    """Independent oracle for the deliberately bounded raw synthetic schema.

    Fail on unsupported fixture schemas instead of deriving expectations from
    the rendered DOM or production view model. Every expected field has a stable
    source path and one expected occurrence, even when its value is repeated.
    """
    profile = case["profile"]
    allowed = {"name", "intent", "phone", "email", "city", "education", "experience",
               "campus_experience", "skills", "publications", "postgraduate_exam"}
    unknown = set(profile) - allowed
    if unknown:
        raise ValueError(f"Add independent source-ledger support for fixture keys: {sorted(unknown)}")
    fields = {}
    def add(path, value):
        fields[path] = plain_fact(value, bold=".bullets." in path or path.startswith("skills.") and path.endswith(".value"))
    for target, key in (("name", "name"), ("title", "intent"), ("phone", "phone"),
                        ("email", "email"), ("location", "city")):
        value = profile.get(key, "")
        if value or target in ("name", "phone", "email"):
            add(f"identity.{target}", value)
    edu = profile.get("education", {})
    allowed_edu = {"school", "degree", "major", "time", "gpa", "awards", "certificates", "courses", "honors"}
    if set(edu) - allowed_edu:
        raise ValueError("Add independent ledger support for education fixture fields")
    add("education.school", edu.get("school", ""))
    degree = "  ".join(str(edu[key]) for key in ("major", "degree") if edu.get(key))
    if degree:
        add("education.degree", re.sub(r"\s*[｜|·]\s*", "  ", degree))
    add("education.time", edu.get("time", ""))
    badges = [edu[key] for key in ("gpa", "awards", "certificates", "courses", "honors") if edu.get(key)]
    rows = ([badges] if len(badges) <= 3 else [badges[:2], badges[2:]] if len(badges) == 4
            else [badges[:3], badges[3:]]) if badges else []
    columns = max((len(row) for row in rows), default=1)
    for row_index, row in enumerate(rows):
        for index in range(columns):
            add(f"education.grid.{row_index}.{index}",
                re.sub(r"\s*[｜|]\s*", " ", str(row[index])) if index < len(row) else "")
    for group, key, title_key in (("experience", "experience", "company"),
                                  ("projects", "campus_experience", "name")):
        for index, entry in enumerate(profile.get(key, [])):
            if set(entry) - {title_key, "role", "dept", "time", "bullets"}:
                raise ValueError(f"Add independent ledger support for {group} fixture fields")
            prefix = f"{group}.{index}"
            add(f"{prefix}.{'org' if group == 'experience' else 'name'}", entry.get(title_key, ""))
            role = entry.get("role", "")
            if group == "experience" and entry.get("dept"):
                role = f"{entry['dept']} · {role}"
            add(f"{prefix}.role", role)
            add(f"{prefix}.time", entry.get("time", ""))
            for bullet_index, bullet in enumerate(entry.get("bullets", [])):
                add(f"{prefix}.bullets.{bullet_index}", bullet)
    for index, (key, value) in enumerate(profile.get("skills", {}).items()):
        add(f"skills.{index}.label", key)
        values = value if isinstance(value, list) else re.split(r"[,，、]\s*", str(value))
        add(f"skills.{index}.value", ", ".join(str(item).strip() for item in values if str(item).strip()))
    for index, publication in enumerate(profile.get("publications", [])):
        if set(publication) - set(PUBLICATION_FIELDS):
            raise ValueError("Add independent ledger support for publication fixture fields")
        for key in PUBLICATION_FIELDS:
            if publication.get(key):
                add(f"publications.{index}.{key}", publication[key])
    exam = profile.get("postgraduate_exam", {})
    if set(exam) - {"target_school", "target_major", "direction", "scores", "total_score"}:
        raise ValueError("Add independent ledger support for exam fixture fields")
    for key in ("target_school", "target_major", "direction"):
        if exam.get(key):
            add(f"postgraduate_exam.{key}", exam[key])
    for index, (subject, score) in enumerate(exam.get("scores", {}).items()):
        add(f"postgraduate_exam.subjects.{index}.name", subject)
        add(f"postgraduate_exam.subjects.{index}.score", score)
    if exam.get("total_score"):
        add("postgraduate_exam.total_score", exam["total_score"])
    return fields


def field_section(path):
    return path.split(".", 1)[0].replace("postgraduate_exam", "postgraduate-exam")


def expected_sections(ledger, theme):
    order = ["postgraduate-exam", "education", "experience", "projects", "skills", "publications"]
    if theme == "silicon-clean":
        order = ["postgraduate-exam", "education", "experience", "projects", "publications", "skills"]
    return [section for section in order if any(field_section(key) == section for key in ledger)]


def expected_field_order(ledger, theme):
    sections = ["identity"] + expected_sections(ledger, theme)
    ordered = []
    for section in sections:
        keys = [key for key in ledger if field_section(key) == section]
        if section == "postgraduate-exam":
            keys = [key for key in keys if ".subjects." not in key and not key.endswith("total_score")] + [
                key for key in keys if key.endswith(".name")] + [
                key for key in keys if key.endswith(".score")] + [
                key for key in keys if key.endswith("total_score")]
        if theme == "classic-tech" and section in ("education", "experience", "projects"):
            result = []
            for key in keys:
                prefix = "education" if section == "education" else ".".join(key.split(".")[:2])
                date = prefix + ".time"
                if date in keys and date not in result:
                    result.append(date)
                if key not in result:
                    result.append(key)
            keys = result
        ordered.extend(keys)
    return ordered


def expected_presentation(case, ledger):
    parts = ["申请方向：" if case.get("theme") == "academic-postgraduate" else "求职意向："] if ledger.get("identity.title") else []
    parts.extend(["•", "•"] if ledger.get("identity.location") else ["•"])
    parts.extend(SECTION_LABELS[section] for section in expected_sections(ledger, case.get("theme")))
    parts.extend("：" for key in ledger if key.startswith("skills.") and key.endswith(".label"))
    for index in range(len(case["profile"].get("publications", []))):
        count = sum(key.startswith(f"publications.{index}.") for key in ledger)
        parts.extend("·" for _ in range(max(0, count - 1)))
        for key, label in (("status", "状态："), ("author_role", "作者角色："), ("individual_contribution", "个人贡献：")):
            if f"publications.{index}.{key}" in ledger:
                parts.append(label)
    if "postgraduate_exam.total_score" in ledger or any("postgraduate_exam.subjects." in key for key in ledger):
        parts.extend(["初试成绩", "得分"])
    for key, label in (("target_school", "报考院校："), ("target_major", "报考专业："), ("direction", "研究方向：")):
        if f"postgraduate_exam.{key}" in ledger:
            parts.append(label)
    if "postgraduate_exam.total_score" in ledger:
        parts.append("总分")
    if case["photo"] == "reserved":
        parts.append("预留证件照一寸 / 二寸")
    return "".join(parts)


class SemanticDocument(HTMLParser):
    """Read identity hooks; never use their values as expected fixture facts."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.stack, self.fields, self.sections, self.entries = [], [], [], []
        self.layout, self.body, self.non_photo_body, self.photo_body = [], [], [], []
        self.photos, self.images, self.image_sources = 0, 0, []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent = self.stack[-1] if self.stack else {}
        node = {"tag": tag, "body": tag == "body" or parent.get("body", False),
                "section": attrs.get("id") if tag == "section" else parent.get("section", "identity"),
                "column": attrs.get("data-column", parent.get("column")),
                "photo": "photo-placeholder" in attrs.get("class", "").split() or parent.get("photo", False),
                "field": None}
        if node["body"]:
            if "data-layout" in attrs:
                self.layout.append(attrs["data-layout"])
            if tag == "section":
                self.sections.append(attrs.get("id"))
            if "data-entry" in attrs:
                self.entries.append(attrs["data-entry"])
            if "data-field" in attrs:
                node["field"] = {"id": attrs["data-field"], "text": "", "section": node["section"], "column": node["column"]}
                self.fields.append(node["field"])
            self.photos += int("photo-placeholder" in attrs.get("class", "").split())
            self.images += int(tag == "img")
            if tag == "img":
                self.image_sources.append(attrs.get("src", ""))
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, value):
        if self.stack and self.stack[-1]["body"]:
            self.body.append(value)
            if not self.stack[-1]["photo"]:
                self.non_photo_body.append(value)
            else:
                self.photo_body.append(value)
            for node in self.stack:
                if node["field"] is not None:
                    node["field"]["text"] += value


def coverage_errors(actual, ledger, presentation, pdf=False):
    """Exact full-character coverage plus exact occurrence counts, never presence only."""
    expected = "".join(ledger.values()) + presentation
    normalize = lambda value: squash(re.sub("[•●◦▪]", "", value) if pdf else value)
    actual, expected = normalize(actual), normalize(expected)
    failures = []
    if Counter(actual) != Counter(expected):
        failures.append("full text coverage differs from independent source ledger")
    for value in set(ledger.values()):
        value = normalize(value)
        if value and actual.count(value) != expected.count(value):
            failures.append(f"field occurrence count differs: {value[:70]}")
    return failures


def audit_html(html, case):
    ledger, doc = source_ledger(case), SemanticDocument(html)
    expected = Counter((key, squash(value)) for key, value in ledger.items())
    actual = Counter((field["id"], squash(field["text"])) for field in doc.fields)
    errors = []
    if actual != expected:
        errors.append("source field IDs, exact values, or occurrence counts differ")
    theme = case.get("theme", DEFAULT_THEME)
    if [field["id"] for field in doc.fields] != expected_field_order(ledger, theme):
        errors.append("field/entry/bullet reading order differs")
    expected_entries = []
    for key in expected_field_order(ledger, theme):
        section = field_section(key)
        entry = "education" if section == "education" else ".".join(key.split(".")[:2])
        if section in ("education", "experience", "projects", "skills", "publications") and entry not in expected_entries:
            expected_entries.append(entry)
    if doc.entries != expected_entries:
        errors.append("entry wrappers, order, or multiplicity differ")
    if doc.sections != expected_sections(ledger, theme):
        errors.append("section order or multiplicity differs")
    for field in doc.fields:
        if field["section"] != field_section(field["id"]):
            errors.append(f"field moved to wrong section: {field['id']}")
        expected_column = None
        if theme == "silicon-clean":
            section = field_section(field["id"])
            expected_column = "left" if section == "experience" else "right" if section in ("projects", "publications") else None
        if field["column"] != expected_column:
            errors.append(f"field moved to wrong column: {field['id']}")
    if theme in STRUCTURAL_LAYOUTS and doc.layout != [STRUCTURAL_LAYOUTS[theme]]:
        errors.append("missing or incorrect declared layout")
    errors.extend(coverage_errors("".join(doc.body), ledger, expected_presentation(case, ledger)))
    if case["photo"] == "embedded" and doc.image_sources != [case["photo_data_uri"]]:
        errors.append("embedded portrait differs from the supplied synthetic source")
    expected_photos = int(case["photo"] != "none")
    expected_images = int(case["photo"] == "embedded")
    if case["photo"] == "none" and "data:image/" in html.lower():
        errors.append("no-photo output retains embedded image URI")
    if doc.photos != expected_photos or doc.images != expected_images:
        errors.append("photo/no-photo element contract differs")
    return {"fieldCount": len(doc.fields), "expectedFieldCount": len(ledger),
            "sourceLedgerHash": digest(json.dumps(ledger, ensure_ascii=False, sort_keys=True)),
            "errors": errors}


def unchanged_content(before, after, theme):
    if theme in STRUCTURAL_LAYOUTS:
        # Source-ledger checks replace equality only for this explicit migration.
        return True
    # Photo UI is deliberately changed by the independent photo-mode contract.
    # Keep exact body order/equality for every non-photo byte in legacy themes.
    before_doc, after_doc = SemanticDocument(before), SemanticDocument(after)
    def legacy_text(doc):
        # Only the known generated preview label may differ. Arbitrary content
        # put inside that wrapper remains significant, including hidden facts.
        photo_text = "".join(doc.photo_body)
        known = squash(photo_text) in ("", "预留证件照一寸/二寸")
        return (" ".join("".join(doc.non_photo_body).split()), "" if known else " ".join(photo_text.split()))
    return legacy_text(before_doc) == legacy_text(after_doc)


def fixtures(theme=DEFAULT_THEME):
    """All names, organizations, contacts and claims here are fabricated QA data."""
    short = {
        "name": "林示例 Alex Lin", "intent": "平台工程师 / Platform Engineer",
        "phone": "+00 000 000 0000", "email": "alex.qa@example.invalid", "city": "示例城市 / Remote",
        "education": {"school": "示例理工大学 / Example Institute", "degree": "计算机硕士 / MSc",
                      "major": "计算机科学 / Computer Science", "time": "2018.09 - 2020.06",
                      "gpa": "3.8/4.0", "awards": "示例奖学金 / Test Scholarship"},
        "experience": [{"company": "示例平台团队 / Example Platform Team", "role": "工程师 / Engineer",
                        "time": "2020.07 - 2024.12", "bullets": [
                            "QA-EXP-01：维护服务运行手册并记录发布结果。 Maintained service runbooks.",
                            "QA-EXP-02：整理故障复盘，验证修复步骤。 Documented repeatable recovery checks."]}],
        "campus_experience": [{"name": "示例开源项目 / Example Project", "role": "维护者 / Maintainer",
                               "time": "2019.01 - 2020.06", "bullets": [
                                   "QA-PROJ-01：补充使用说明与测试用例。 Added documentation and regression tests."]}],
        "skills": {"语言 / Languages": "Python, SQL", "工具 / Tools": "Git, Linux"},
    }
    long = json.loads(json.dumps(short))
    long.update({
        "name": "Alexandria Catherine Montgomery-Wellington 示例",
        "intent": "Principal Distributed Systems Architect and Research Engineering Lead / 平台架构",
        "email": "alexandria.montgomery.wellington." + "research" * 9 + "@engineering.example.invalid",
        "city": "示例城市 / Remote across several international research teams",
    })
    long["education"].update({
        "school": "International Institute of Advanced Computing and Reliability Research / 示例大学",
        "degree": "Master of Science in Distributed Systems / 计算机硕士",
        "awards": "PostgraduateResearchAndEngineeringExcellenceScholarship" * 2,
    })
    long["experience"][0].update({
        "company": "InternationalInfrastructureCompatibilityAndReliabilityResearchLaboratory" * 2,
        "role": "Principal Distributed Systems Architect and Engineering Lead / 负责人",
    })
    long["campus_experience"][0].update({
        "name": "OpenInfrastructureCompatibilityAndReliabilityResearchInitiative" * 2,
        "role": "Research Coordinator and Project Maintainer / 维护者",
    })
    dense = json.loads(json.dumps(short))
    dense["experience"] = [{
        "company": f"示例研究团队 {i + 1} / Example Research Team {i + 1}",
        "role": "平台工程师 / Platform Engineer", "time": f"{2010+i}.01 - {2011+i}.12",
        "bullets": [f"QA-DENSE-{i+1}-{j+1}：维护服务文档，与团队核对发布步骤和运行结果。 "
                    "Maintained operational documentation, reviewed release procedures with the team, "
                    "and recorded reproducible validation results for the shared infrastructure."
                    for j in range(4)],
    } for i in range(4)]
    result = []
    for label, profile, mode, max_pages in [
        ("short", short, "raw", 1), ("long", long, "raw", 2),
        ("dense", dense, "solver", 4), ("compact", long, "compact", 2),
    ]:
        for photo in ("none", "reserved"):
            result.append({"name": f"{label}-{photo}", "profile": profile, "photo": photo,
                           "mode": mode, "max_pages": max_pages})
    result.append({"name": "long-embedded", "profile": long, "photo": "embedded",
                   "photo_data_uri": synthetic_photo(), "mode": "raw", "max_pages": 2})
    result.append({"name": "production-reserved", "profile": short, "photo": "reserved",
                   "mode": "builder", "max_pages": 1})
    # Ordinary-length bilingual content complements pathological overflow tests.
    # All organizations, contacts, dates and achievements are fabricated QA data.
    professional = json.loads(json.dumps(short))
    professional["experience"] = [
        {"company": "示例云平台 / Example Cloud", "role": "后端工程师 / Backend Engineer",
         "time": "2022.07 - 2025.06", "bullets": [
             "维护订单服务的 Python 接口，补充输入校验与错误处理。 Maintained Python APIs for the order service and added request validation.",
             "为发布流程建立回归检查，记录验证步骤与回滚条件。 Added release regression checks with documented validation and rollback steps.",
             "与产品和支持团队复盘用户反馈，修复可重现的问题。 Worked with product and support teams to reproduce and resolve reported issues."]},
        {"company": "示例软件工作室 / Example Software", "role": "软件工程师 / Software Engineer",
         "time": "2020.07 - 2022.06", "bullets": [
             "开发内部数据查询工具，为运营同事提供统一的检索入口。 Built an internal data lookup tool for the operations team.",
             "整理 SQL 查询与数据字段说明，补充常见问题排查文档。 Documented SQL queries, data fields, and common troubleshooting steps.",
             "参与代码评审与单元测试维护，跟进缺陷直到验证完成。 Reviewed code, maintained unit tests, and verified defect fixes."]},
    ]
    professional["campus_experience"] = [
        {"name": "服务运行手册 / Service Runbooks", "role": "维护者 / Maintainer",
         "time": "2023.03 - 2024.12", "bullets": [
             "汇总值班流程与故障处理步骤，使用测试环境验证操作顺序。 Organized on-call procedures and verified recovery steps in a test environment.",
             "补充检索索引与更新记录，方便团队定位相关说明。 Added a search index and change log for shared operational documentation."]},
        {"name": "开源数据工具 / Open Data Tools", "role": "贡献者 / Contributor",
         "time": "2019.09 - 2020.06", "bullets": [
             "为 CSV 导入流程添加格式检查，并编写中英文使用示例。 Added CSV format checks and bilingual usage examples.",
             "整理社区报告的边界情况，补充对应回归测试。 Converted reported edge cases into repeatable regression tests."]},
    ]
    for photo in ("none", "reserved"):
        result.append({"name": f"professional-{photo}", "profile": professional,
                       "photo": photo, "mode": "builder", "max_pages": 2})
    skills_long = json.loads(json.dumps(short))
    skills_long["skills"] = {
        "分布式系统可靠性与故障排查 / Distributed Systems Reliability and Troubleshooting":
            "Python, SQL, Linux, reproducible validation and operational documentation",
        "CrossPlatformInfrastructureCompatibilityAndResearchEngineering" * 2:
            "LongUnbrokenTechnicalSkillValueForWrappingChecks" * 3,
    }
    for mode in ("raw", "builder"):
        for photo in ("none", "reserved"):
            result.append({"name": f"skills-long-{mode}-{photo}", "profile": skills_long,
                           "photo": photo, "mode": mode, "max_pages": 2,
                           "require_autofit": False})
    if theme in {"academic-postgraduate", "sidebar-clean"}:
        for long_exam in (False, True):
            academic = json.loads(json.dumps(short))
            academic["intent"] = "计算机科学硕士 / MSc Computer Science"
            academic["postgraduate_exam"] = {
                "target_school": "示例大学 / Example University",
                "target_major": "计算机科学与技术 / Computer Science",
                "direction": "可信软件 / Reliable Software",
                "scores": {"思想政治理论": "72", "英语（一）": "78", "数学（一）": "125", "计算机学科基础": "120"},
                "total_score": "395",
            }
            if long_exam:
                academic["postgraduate_exam"].update({
                    "target_school": "InternationalInstituteOfAdvancedComputingAndInterdisciplinaryResearch" * 2,
                    "direction": "分布式系统的形式化验证与可信软件研究 / Formal Verification of Distributed Systems",
                    "scores": {"思想政治理论 / Political Theory": "72", "英语（一） / Academic English": "78",
                               "AdvancedMathematicsAndStatisticalMethods" * 2: "125",
                               "计算机学科专业基础综合 / Computer Science Foundations": "120"},
                })
            for photo in ("none", "reserved"):
                label = "long" if long_exam else "normal"
                result.append({"name": f"exam-{label}-{photo}", "profile": academic,
                               "photo": photo, "mode": "builder", "max_pages": 2})
    # Preserve all original fixtures. Every existing no-photo shape also gets
    # the same real synthetic portrait through the identical rendering path.
    existing_names = {case["name"] for case in result}
    portrait = synthetic_photo()
    for case in list(result):
        if case["photo"] != "none":
            continue
        name = case["name"].removesuffix("-none") + "-embedded"
        if name not in existing_names:
            result.append(dict(case, name=name, photo="embedded", photo_data_uri=portrait))
    for mode in ("raw", "builder"):
        result.append({"name": f"source-photo-{mode}-none", "profile": short,
                       "photo": "none", "source_photo": True, "photo_data_uri": portrait,
                       "mode": mode, "max_pages": 1})
    if theme in STRUCTURAL_LAYOUTS:
        complete = json.loads(json.dumps(professional))
        complete["postgraduate_exam"] = {
            "target_school": "示例大学 / Example University",
            "target_major": "计算机科学 / Computer Science",
            "direction": "可信软件 / Reliable Software",
            "scores": {"政治 / Politics": "72", "英语 / English": "78", "数学 / Mathematics": "125"},
            "total_score": "275",
        }
        complete["publications"] = [
            {"title": "QA-PUB-01: Reproducible Reliability Checks", "authors": "Synthetic A, Synthetic B",
             "venue": "Example Systems Workshop", "conference": "Synthetic Reliability Meeting", "year": "2024",
             "status": "Submitted, not accepted", "author_role": "Co-author",
             "highlight": "QA-PUB-HIGHLIGHT-01: Checked 17 recorded cases.",
             "summary": "Synthetic validation study.", "individual_contribution": "Prepared reproducible fixtures."},
            {"title": "QA-PUB-02: Ordered Verification Notes", "authors": "Synthetic B, Synthetic A",
             "venue": "Example Testing Workshop", "conference": "Synthetic Methods Meeting", "year": "2025",
             "status": "Submitted, not accepted", "author_role": "Co-author",
             "highlight": "QA-PUB-HIGHLIGHT-02: Checked 23 recorded cases.",
             "summary": "Synthetic replication study.", "individual_contribution": "Reviewed recorded outputs."},
        ]
        for photo in ("none", "embedded"):
            result.append({"name": f"all-fields-{photo}", "profile": complete, "photo": photo,
                           "photo_data_uri": portrait, "mode": "raw", "max_pages": 3})
    for case in result:
        case["theme"] = theme
    return result


def render_html(root, case):
    if case["mode"] == "builder":
        raise ValueError("Production fixture requires render_production and a real browser")
    result = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-c", GENERATOR, str(root)],
        input=json.dumps(case, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
        cwd=root, timeout=30, check=True,
    )
    if "{{" in result.stdout or "<html" not in result.stdout:
        raise ValueError("Renderer did not produce fully populated HTML")
    return result.stdout


def save_child_logs(output, stdout, stderr):
    """Keep full child diagnostics in artifacts and return only a bounded summary."""
    def decode(value):
        return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
    stdout, stderr = decode(stdout), decode(stderr)
    output.mkdir(parents=True, exist_ok=True)
    (output / "child-stdout.txt").write_text(stdout, encoding="utf-8")
    (output / "child-stderr.txt").write_text(stderr, encoding="utf-8")
    return (stderr.strip() or stdout.strip() or "No child output was captured.")[-2000:]


def render_production(root, case, output):
    request = dict(case, output_dir=str(output))
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", "-c", BUILDER_GENERATOR, str(root)],
            input=json.dumps(request, ensure_ascii=False), capture_output=True, text=True,
            encoding="utf-8", cwd=root, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        detail = save_child_logs(output, exc.stdout, exc.stderr)
        raise RuntimeError(f"Production renderer timed out; logs: {output}\n{detail}") from None
    detail = save_child_logs(output, result.stdout, result.stderr)
    if result.returncode:
        raise RuntimeError(f"Production renderer exited {result.returncode}; logs: {output}\n{detail}")
    returned = json.loads(result.stdout)
    for kind in ("html", "pdf"):
        path = Path(returned[kind]).resolve()
        if output.resolve() not in path.parents or not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Invalid production {kind} output: {path}")
    trace = returned["trace"]
    if not trace["measurements"] or not trace["renders"]:
        raise ValueError("Production fixture did not exercise measurement and PDF rendering")
    # The builder deliberately skips single-page AutoFit after a multi-page
    # solve. Stress baselines can take that real branch; the original short and
    # professional cases still explicitly require the AutoFit coverage.
    if case.get("require_autofit", True) and not trace["autofit"]:
        raise ValueError("Production fixture did not exercise required AutoFit")
    return Path(returned["html"]).read_text(encoding="utf-8"), returned


def validate_paths(baseline, output, theme=DEFAULT_THEME):
    baseline, output = baseline.resolve(), output.resolve()
    if not (baseline / theme_path(theme)).is_file() or not (baseline / "core/resume_view_model.py").is_file():
        raise ValueError("--baseline-root must contain an isolated OfferGet source tree")
    if baseline == ROOT or ROOT in baseline.parents:
        raise ValueError("Baseline must be isolated outside the current source tree")
    for protected in (ROOT, baseline):
        if output == protected or output in protected.parents or protected == baseline and baseline in output.parents:
            raise ValueError("Output directory must not overwrite either source tree")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output directory must be empty; existing artifacts are never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    return baseline, output


def revision(root):
    # Git archives carry no .git; CI records its verified base SHA explicitly.
    archived_revision = root / "revision.txt"
    if archived_revision.is_file():
        value = archived_revision.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[a-f0-9]{40}", value):
            return value
    if not (root / ".git").exists():
        return None
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=10, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def ordered_field_errors(text, keys, ledger):
    """Check complete source fields in logical order, preserving every bullet."""
    text, cursor, errors = squash(text), 0, []
    for key in keys:
        value = squash(ledger[key])
        if not value:
            continue
        position = text.find(value, cursor)
        if position < 0:
            errors.append(f"missing or out-of-order field: {key}")
        else:
            cursor = position + len(value)
    return errors


def pdf_column_streams(lines, geometry):
    """Read actual PDF glyphs column-major, with full-width opening and ending.

    X bounds come from print DOM measurements; vertical transitions come from
    required section headings in the PDF itself, so page-break whitespace does
    not corrupt continuation-page coordinates. No source field is discarded.
    """
    columns = geometry.get("columns", [])
    if [column["name"] for column in columns] != ["left", "right"]:
        return {}, ["expected exactly the declared left and right print columns"]
    if columns[0]["right"] >= columns[1]["left"]:
        return {}, ["print column bounds overlap"]
    starts = [(line["page"], line["bbox"][1]) for line in lines
              if squash(line["text"]) in ("实习经历", "校园与实践经历")]
    endings = [(line["page"], line["bbox"][1]) for line in lines if squash(line["text"]) == "专业技能"]
    if not starts or len(endings) != 1:
        return {}, ["missing or repeated PDF column-boundary section headings"]
    start, end = min(starts), endings[0]
    if start >= end:
        return {}, ["full-width ending precedes column content"]
    streams = {"opening": [], "left": [], "right": [], "ending": []}
    errors = []
    for line in lines:
        scale = line["pageWidth"] / geometry["pageWidth"]
        position = (line["page"], line["bbox"][1])
        for char in line["chars"]:
            value, (x0, y0, x1, y1) = char["c"], char["bbox"]
            if not value.strip():
                continue
            if position < start:
                streams["opening"].append(value)
                continue
            if position >= end:
                streams["ending"].append(value)
                continue
            center = (x0 + x1) / 2
            hits = [column["name"] for column in columns
                    if column["left"] * scale - 1 <= center <= column["right"] * scale + 1]
            if len(hits) != 1:
                errors.append(f"unassigned or ambiguous PDF glyph on page {line['page']}: {value}")
            else:
                streams[hits[0]].append(value)
    return {key: "".join(values) for key, values in streams.items()}, errors


def pdf_line_overlaps(lines):
    """Flag separate PDF text lines whose boxes collide materially."""
    overlaps = []
    for index, first in enumerate(lines):
        for second in lines[index + 1:]:
            if first.get("page") != second.get("page"):
                continue
            a, b = first["bbox"], second["bbox"]
            x_overlap = min(a[2], b[2]) - max(a[0], b[0])
            y_overlap = min(a[3], b[3]) - max(a[1], b[1])
            # Font ascender/descender boxes can overlap slightly despite clear
            # ink. Require a collision across >40% of the shorter line height (the existing Sidebar gate).
            if x_overlap > 2 and y_overlap > max(2, min(a[3] - a[1], b[3] - b[1]) * .4):
                overlaps.append({"page": first.get("page"), "first": first["text"],
                                 "second": second["text"], "firstBox": list(a), "secondBox": list(b)})
    return overlaps


def inspect_pdf(path, anchors, check_text_overlap=False, *, case=None, geometry=None):
    import fitz

    with fitz.open(path) as doc:
        text = "\n".join(page.get_text() for page in doc)
        compact = squash(text)
        pages, lines = [], []
        for number, page in enumerate(doc, 1):
            blocks = [block for block in page.get_text("blocks") if block[4].strip()]
            pages.append({"number": number, "widthPt": page.rect.width, "heightPt": page.rect.height,
                          "textTopPt": min((b[1] for b in blocks), default=None),
                          "textBottomPt": max((b[3] for b in blocks), default=None)})
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    chars = [char for span in line["spans"] for char in span["chars"]]
                    lines.append({"page": number, "pageWidth": page.rect.width, "bbox": line["bbox"],
                                  "text": "".join(char["c"] for char in chars), "chars": chars})
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(path.with_name(f"print-{number}.png"))
        image_count = len({image[0] for page in doc for image in page.get_images(full=True)})
        result = {"imageCount": image_count, "pages": len(doc), "pageBounds": pages, "textHash": digest(compact),
                  "missingAnchors": [anchor for anchor in anchors if squash(anchor) not in compact],
                  "overlappingTextLines": pdf_line_overlaps(lines) if check_text_overlap or case and case.get("theme") in STRUCTURAL_LAYOUTS else []}
        if case and case.get("theme") in STRUCTURAL_LAYOUTS:
            ledger = source_ledger(case)
            result["sourceErrors"] = coverage_errors(text, ledger, expected_presentation(case, ledger), pdf=True)
            order = expected_field_order(ledger, case["theme"])
            if case["theme"] == "silicon-clean":
                streams, errors = pdf_column_streams(lines, geometry or {})
                result["columnErrors"] = errors
                for column, stream in streams.items():
                    keys = [key for key in order if (
                        "opening" if field_section(key) in ("identity", "postgraduate-exam", "education") else
                        "ending" if field_section(key) == "skills" else
                        "left" if field_section(key) == "experience" else "right") == column]
                    result["sourceErrors"].extend(ordered_field_errors(stream, keys, ledger))
                result["columnTextHashes"] = {key: digest(value) for key, value in streams.items()}
            else:
                result["sourceErrors"].extend(ordered_field_errors(text, order, ledger))
        return result


def final_failures(metrics, case):
    failures = []
    for media in ("screen", "print"):
        for key in ("overflow", "overlaps"):
            if metrics[media][key]:
                failures.append(f"{media}: {key} ({len(metrics[media][key])})")
    if metrics["screen"]["bodyFontPx"] < 10.6 - 0.01:
        failures.append("body font below the existing AutoFit floor")
    if not metrics["textUnchanged"]:
        failures.append("factual/body text changed")
    if case.get("theme") in STRUCTURAL_LAYOUTS:
        if "sourceAudit" not in metrics or "errors" not in metrics["sourceAudit"]:
            failures.append("source ledger audit was not run")
        if "sourceErrors" not in metrics["pdf"]:
            failures.append("PDF source ledger audit was not run")
    if metrics.get("sourceAudit", {}).get("errors"):
        failures.extend(f"source ledger: {error}" for error in metrics["sourceAudit"]["errors"])
    for media in ("screen", "print"):
        for field in metrics[media].get("fields", []):
            if field["text"].strip() and not field["visible"]:
                failures.append(f"{media}: hidden source field {field['id']}")
        if "photoSlots" in metrics[media] and "photo" in case:
            if metrics[media]["photoSlots"] != int(case["photo"] != "none"):
                failures.append(f"{media}: photo slot count differs")
            if len(metrics[media]["images"]) != int(case["photo"] == "embedded"):
                failures.append(f"{media}: photo image count differs")
            if case["photo"] == "none" and metrics[media].get("identityPaddingRight") not in (None, 0):
                failures.append(f"{media}: no-photo retained identity padding")
            if case["photo"] == "none" and metrics[media].get("identityWidth", float("inf")) < metrics[media].get("headerWidth", 0) - 1:
                failures.append(f"{media}: no-photo retained reserved geometry")
    if case.get("photo") == "none" and metrics.get("hasEmbeddedImageUri"):
        failures.append("no-photo output retains embedded image URI")
    if metrics["blockedRequests"]:
        failures.append("attempted network resource request")
    for media in ("screen", "print"):
        for img in metrics[media].get("images", []):
            if not img["complete"] or img["width"] == 0:
                failures.append(f"{media}: embedded image did not load")
            if case.get("photo") == "embedded":
                width, height = img.get("displayWidth", 0), img.get("displayHeight", 0)
                if not img.get("visible") or width <= 0 or height <= 0:
                    failures.append(f"{media}: embedded portrait is hidden or zero-sized")
                if not img.get("contained"):
                    failures.append(f"{media}: embedded portrait exceeds its frame")
                if img.get("height", 0) <= 0 or height <= 0:
                    failures.append(f"{media}: embedded portrait has invalid aspect geometry")
                elif abs(width / height - img["width"] / img["height"]) > .02 and img.get("objectFit") != "contain":
                    failures.append(f"{media}: embedded portrait is cropped or distorted")
    pdf = metrics["pdf"]
    if "imageCount" in pdf and "photo" in case and pdf["imageCount"] != int(case["photo"] == "embedded"):
        failures.append("PDF photo/no-photo image count differs")
    if not 1 <= pdf["pages"] <= case["max_pages"]:
        failures.append(f"PDF page count {pdf['pages']} exceeds fixture budget {case['max_pages']}")
    if case["name"].startswith("dense") and pdf["pages"] < 2:
        failures.append("dense fixture did not exercise continuation pages")
    failures.extend(f"PDF source ledger: {error}" for error in pdf.get("sourceErrors", []))
    if pdf.get("overlappingTextLines"):
        failures.append(f"PDF text lines overlap ({len(pdf['overlappingTextLines'])} pairs)")
    if pdf.get("overlaps"):
        failures.append(f"PDF text overlap ({len(pdf['overlaps'])})")
    if pdf.get("columnErrors"):
        failures.extend(f"PDF columns: {error}" for error in pdf["columnErrors"])
    if pdf["missingAnchors"]:
        failures.append(f"PDF lost selectable text ({len(pdf['missingAnchors'])} anchors)")
    gutter_pt = metrics["print"]["printPaddingMm"] * 72 / 25.4
    for page in pdf["pageBounds"]:
        if page["textTopPt"] is None:
            failures.append(f"blank PDF page {page['number']}")
        elif page["textTopPt"] < gutter_pt - 3 or page["textBottomPt"] > page["heightPt"] - gutter_pt + 3:
            failures.append(f"PDF page {page['number']} exceeds vertical gutter")
        if abs(page["widthPt"] - 595.28) > 1 or abs(page["heightPt"] - 841.89) > 1:
            failures.append(f"PDF page {page['number']} is not A4")
    return failures


def run(baseline, output, theme=DEFAULT_THEME):
    report = {"theme": theme, "syntheticDataOnly": True, "baselineRevision": os.environ.get("BASELINE_SHA") or revision(baseline),
              "currentRevision": os.environ.get("GITHUB_SHA") or revision(ROOT),
              "requestedHeadRevision": os.environ.get("QA_HEAD_SHA"),
              "baselineTemplateHash": digest((baseline / theme_path(theme)).read_text(encoding="utf-8")),
              "currentTemplateHash": digest((ROOT / theme_path(theme)).read_text(encoding="utf-8")),
              "verificationKind": "real-browser-and-actual-pdf",
              "fixtures": [], "failures": []}
    try:
        from importlib.metadata import version

        from playwright.sync_api import sync_playwright

        report["playwrightVersion"] = version("playwright")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            report["browserVersion"] = browser.version
            context = browser.new_context(viewport={"width": 1000, "height": 1200}, device_scale_factor=1)
            for case in fixtures(theme):
                pair = {"name": case["name"], "mode": case["mode"], "photo": case["photo"]}
                if theme in STRUCTURAL_LAYOUTS:
                    ledger = source_ledger(case)
                    (output / case["name"]).mkdir(parents=True, exist_ok=True)
                    (output / case["name"] / "source-ledger.json").write_text(json.dumps({
                        "origin": "raw synthetic fixture; independent of renderer and VM",
                        "fields": ledger, "expectedOccurrences": {key: 1 for key in ledger},
                        "fieldOrder": expected_field_order(ledger, theme),
                        "presentation": expected_presentation(case, ledger)}, ensure_ascii=False, indent=2), encoding="utf-8")
                html, production = {}, {}
                for phase, root in (("before", baseline), ("after", ROOT)):
                    target = output / case["name"] / phase
                    target.mkdir(parents=True)
                    if case["mode"] == "builder":
                        html[phase], production[phase] = render_production(
                            root, case, target / "production")
                    else:
                        html[phase] = render_html(root, case)
                unchanged = unchanged_content(html["before"], html["after"], theme)
                for phase in ("before", "after"):
                    target = output / case["name"] / phase
                    (target / "resume.html").write_text(html[phase], encoding="utf-8")
                    page = context.new_page()
                    blocked = []
                    def block_request(route, blocked=blocked):
                        blocked.append(route.request.url)
                        route.abort()
                    page.route("**/*", block_request)
                    page.set_content(html[phase], wait_until="load")
                    page.evaluate("document.fonts.ready")
                    page.emulate_media(media="screen")
                    metrics = {"screen": page.evaluate(MEASURE), "textUnchanged": unchanged,
                               "htmlTextHash": digest(text_content(html[phase])), "blockedRequests": blocked,
                               "hasEmbeddedImageUri": "data:image/" in html[phase].lower(),
                               "comparisonMode": "independent-source-ledger" if theme in STRUCTURAL_LAYOUTS else "legacy-exact-non-photo-body"}
                    if theme in STRUCTURAL_LAYOUTS:
                        metrics["sourceAudit"] = audit_html(html[phase], case)
                    page.screenshot(path=str(target / "screen.png"), full_page=True)
                    page.emulate_media(media="print")
                    metrics["print"] = page.evaluate(MEASURE)
                    if phase in production:
                        # Inspect the builder's actual returned PDF, not a second export.
                        (target / "resume.pdf").write_bytes(Path(production[phase]["pdf"]).read_bytes())
                        metrics["production"] = production[phase]
                    else:
                        page.pdf(path=str(target / "resume.pdf"), prefer_css_page_size=True, print_background=True,
                                 display_header_footer=False)
                    metrics["pdf"] = inspect_pdf(target / "resume.pdf", metrics["screen"]["anchors"],
                                                 check_text_overlap=theme == "sidebar-clean", case=case, geometry=metrics["print"])
                    metrics["failures"] = final_failures(metrics, case)
                    # Store text only once in HTML and keep the JSON compact and reviewable.
                    for media in ("screen", "print"):
                        metrics[media]["bodyTextHash"] = digest(" ".join(metrics[media].pop("bodyText").split()))
                        metrics[media].pop("visibleText")
                        metrics[media].pop("anchors")
                    (target / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
                    pair[phase] = metrics
                    page.close()
                report["fixtures"].append(pair)
                report["failures"].extend(f"{case['name']}: {failure}" for failure in pair["after"]["failures"])
                print(f"{case['name']}: before {len(pair['before']['failures'])} findings / "
                      f"{pair['before']['pdf']['pages']} pages; after {len(pair['after']['failures'])} findings / "
                      f"{pair['after']['pdf']['pages']} pages", flush=True)
            browser.close()
    except Exception as exc:  # noqa: BLE001 - preserve diagnostics for any failed browser stage
        report["failures"].append(f"QA execution failed: {type(exc).__name__}: {exc}")
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=THEMES, default=DEFAULT_THEME)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        baseline, output = validate_paths(args.baseline_root, args.output_dir, args.theme)
    except ValueError as exc:
        parser.error(str(exc))
    report = run(baseline, output, args.theme)
    if report["failures"]:
        print("\n".join(report["failures"]), file=sys.stderr)
        return 1
    print(f"PASS: {len(report['fixtures'])} fixture pairs; artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
