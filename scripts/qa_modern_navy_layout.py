"""Offline Chromium visual regression check using explicitly synthetic resumes.

Run with a git-archived baseline, never a user's resume. This script intentionally
requires real Playwright/Chromium and PyMuPDF; it does not replace a missing browser
with mocked screenshots or pass an unchecked layout. See docs/RESUME_THEME_QA.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import zlib
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
# -I plus an explicit root avoids importing the current tree for the baseline.
GENERATOR = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from core.resume_view_model import HtmlThemeRenderer, ResumeViewModel
from core.autofit import AutoFitEngine, TUNING_LADDER
from core.layout_solver import LayoutConfig, solve_layout
request = json.load(sys.stdin)
vm = ResumeViewModel.from_profile(request['profile'], reserve_photo=request['photo'] == 'reserved')
if request['photo'] == 'embedded':
    vm.photo_data_uri = request['photo_data_uri']
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
import json, sys
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
    builder = ResumeBuilder(request['profile'], template_dir=root / 'themes',
                            renderer=renderer, autofit_engine=MeasuredAutoFit(renderer))
    result = builder.build_html_theme(request.get('theme', 'modern-navy'), output,
        photo=request['photo'] == 'reserved', pages='auto', autofit=True,
        adaptive_fill=True, diff_ledger=False)
    print(json.dumps({'html': str(result['html']), 'pdf': str(result['pdf']), 'trace': trace}))
finally:
    (output / 'renderer-trace.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')
'''


# Geometry checks inspect actual rendered text ranges, rather than only scrollWidth
# (which misses overlapping flex siblings and text protruding out of inline boxes).
MEASURE = r'''() => {
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
    '.exam-target-bar', '.exam-score-table tr'];
  for (const selector of selectors) {
    for (const parent of document.querySelectorAll(selector)) {
      const children = [...parent.children].filter(el => el.getBoundingClientRect().width);
      for (let i=0;i<children.length;i++) for (let j=i+1;j<children.length;j++) {
        const a=children[i].getBoundingClientRect(), b=children[j].getBoundingClientRect();
        if (Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 &&
            Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1) {
          overlaps.push({selector, first:children[i].textContent.trim(),
                         second:children[j].textContent.trim()});
        }
      }
    }
  }
  const anchors = [...document.querySelectorAll(
    'h1, .header-top > span, .contacts > span, .org-title, .org-role, .org-right, '+
    '.project-header > div:first-child > span, .project-header > div:last-child, '+
    '.edu-grid > div, .exam-target-bar > span, .exam-score-table th, .exam-score-table td, li')].map(el=>el.textContent.trim()).filter(Boolean);
  return {pageWidth:box.width, contentWidth:right-left,
          bodyFontPx:parseFloat(getComputedStyle(document.body).fontSize),
          lineHeight:getComputedStyle(document.body).lineHeight,
          overflow:out, overlaps, anchors,
          bodyText:document.body.textContent,
          visibleText:document.body.innerText,
          images:[...document.images].map(img=>({complete:img.complete,width:img.naturalWidth})),
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


def squash(text):
    return re.sub(r"\s+", "", text)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def synthetic_photo():
    """A tiny labeled-by-fixture color swatch, never a person's photograph."""
    def chunk(kind, data):
        return (struct.pack("!I", len(data)) + kind + data
                + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    width, height = 72, 96
    pixels = b"".join(b"\0" + b"\x94\xa3\xb8" * width for _ in range(height))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


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
    if theme == "academic-postgraduate":
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
    for case in result:
        case["theme"] = theme
    return result


def render_html(root, case):
    if case["mode"] == "builder":
        raise ValueError("Production fixture requires render_production and a real browser")
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-X", "utf8", "-c", GENERATOR, str(root)],
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
            [sys.executable, "-I", "-B", "-X", "utf8", "-c", BUILDER_GENERATOR, str(root)],
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
    if not trace["measurements"] or not trace["renders"] or not trace["autofit"]:
        raise ValueError("Production fixture did not exercise measurement, PDF rendering and AutoFit")
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


def inspect_pdf(path, anchors):
    import fitz

    with fitz.open(path) as doc:
        text = "\n".join(page.get_text() for page in doc)
        compact = squash(text)
        pages = []
        for number, page in enumerate(doc, 1):
            blocks = [block for block in page.get_text("blocks") if block[4].strip()]
            pages.append({"number": number, "widthPt": page.rect.width, "heightPt": page.rect.height,
                          "textTopPt": min((b[1] for b in blocks), default=None),
                          "textBottomPt": max((b[3] for b in blocks), default=None)})
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(path.with_name(f"print-{number}.png"))
        return {"pages": len(doc), "pageBounds": pages, "textHash": digest(squash(text)),
                "missingAnchors": [anchor for anchor in anchors if squash(anchor) not in compact]}


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
    if metrics["blockedRequests"]:
        failures.append("attempted network resource request")
    if any(not img["complete"] or img["width"] == 0 for img in metrics["screen"]["images"]):
        failures.append("embedded image did not load")
    pdf = metrics["pdf"]
    if not 1 <= pdf["pages"] <= case["max_pages"]:
        failures.append(f"PDF page count {pdf['pages']} exceeds fixture budget {case['max_pages']}")
    if case["name"].startswith("dense") and pdf["pages"] < 2:
        failures.append("dense fixture did not exercise continuation pages")
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
                html, production = {}, {}
                for phase, root in (("before", baseline), ("after", ROOT)):
                    target = output / case["name"] / phase
                    target.mkdir(parents=True)
                    if case["mode"] == "builder":
                        html[phase], production[phase] = render_production(
                            root, case, target / "production")
                    else:
                        html[phase] = render_html(root, case)
                unchanged = text_content(html["before"]) == text_content(html["after"])
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
                               "htmlTextHash": digest(text_content(html[phase])), "blockedRequests": blocked}
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
                    metrics["pdf"] = inspect_pdf(target / "resume.pdf", metrics["screen"]["anchors"])
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
