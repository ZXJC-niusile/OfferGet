"""ATS plain source parity and real production PDF checks, synthetic inputs only.

The normal path calls ResumeBuilder.build_ats_plain with an unmodified
BrowserRenderer. --source-only is deliberately incomplete: it produces no PDFs
and marks visual validation as unverified. Missing browsers never become a pass.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.qa_modern_navy_layout import fixtures, synthetic_photo, text_content
from scripts.qa_common import squash


def source_anchors(profile):
    """Read every known synthetic source fact without calling the view model."""
    result = []
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("skills", "competencies", "scores"):
                    for label, content in item.items():
                        result.append(str(label))
                        visit(content)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif value is not None and str(value).strip():
            result.append(str(value))
    visit(profile)
    return [squash(value) for value in result]


def cases():
    wanted = {"short-none", "short-reserved", "professional-none", "professional-reserved",
              "long-none", "long-reserved", "dense-none"}
    result = [copy.deepcopy(case) for case in fixtures() if case["name"] in wanted]
    short = next(case for case in result if case["name"] == "short-none")
    professional = next(case for case in result if case["name"] == "professional-none")
    embedded = copy.deepcopy(professional)
    embedded.update(name="professional-embedded", photo="embedded", photo_data_uri=synthetic_photo())
    result.append(embedded)
    for case in result:
        if case["name"].startswith("long-"):
            case["profile"]["experience"][0]["time"] = "September 2020 - December 2024 / " + "LongUnbrokenDateLabel" * 6
            case["profile"]["skills"]["PlatformReliabilityAndOperationalTooling" * 5] = "Python, SQL / 可复现测试"
            case["max_pages"] = 3
    exam = copy.deepcopy(short)
    exam.update(name="exam-long-none", max_pages=2)
    exam["profile"]["postgraduate_exam"] = {
        "target_school": "InternationalGraduateSchoolOfReliableSystems" * 3,
        "target_major": "计算机科学 / Computer Science", "direction": "Systems & Reliability <Research>",
        "scores": {"PoliticalTheoryAndAcademicWriting" * 3: 70, "数学 / Mathematics": 130},
        "total_score": 200,
    }
    exam["profile"]["experience"][0]["bullets"].append("ATS-RAW-FACT: **C++ & Python**; latency < 20 ms.")
    result.append(exam)
    aliases = {
        "candidate_name": "示例 Alias Example", "target_role": "Software Engineer",
        "phone": "+00 000 000 0000", "email": "alias@example.invalid", "location": "Example City",
        "education": {"institution": "Alias Institute", "education_level": "MSc", "period": "2018 - 2020",
                      "education_rows": [["GPA 3.8/4.0", "Synthetic Scholarship"]]},
        "internships": [{"organization": "Alias Research", "title": "Research Engineer", "period": "2020 - 2024",
                         "dept": "R&D", "highlights": [{"claim_en": "ATS-ALIAS-FACT: Tested reproducible builds."}]}],
        "projects": [{"title": "Alias Project", "role": "Maintainer", "period": "2023 - 2024",
                      "description": "ATS-ALIAS-PROJECT: Maintained documentation."}],
        "competencies": {"Tools": ["C++", "SQL"]},
    }
    result.append({"name": "aliases-none", "profile": aliases, "photo": "none", "max_pages": 1})
    structured = {
        "candidate": {"name": "示例 Structured Example", "title_en": "Platform Engineer",
                      "phone": "+00 000 000 0000", "email": "structured@example.invalid", "location": "Example City",
                      "institution": "Structured Institute", "degree": "MSc", "edu_time": "2018 - 2020",
                      "education_grid": [["GPA 3.8/4.0", "Synthetic Scholarship"]]},
        "experience": aliases["internships"], "projects": aliases["projects"],
        "competencies": aliases["competencies"],
    }
    result.append({"name": "structured-none", "profile": structured, "photo": "none", "max_pages": 1})
    return result


GENERATOR = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from core.resume_view_model import ResumeViewModel, AtsPlainRenderer
request = json.load(sys.stdin)
output = Path(request['output']); output.mkdir(parents=True)
trace = {'production': not request['source_only'], 'renders': []}
try:
    if request['source_only']:
        vm = ResumeViewModel.from_profile(request['profile'], photo_path=request.get('photo_path'),
                                          reserve_photo=request['photo'] != 'none')
        result = {}
        for kind, text in AtsPlainRenderer().render(vm).items():
            result[kind] = output / ('resume.' + kind)
            result[kind].write_text(text, encoding='utf-8')
    else:
        from core.resume_builder import ResumeBuilder
        from core.browser_renderer import BrowserRenderer
        class TracedBrowser(BrowserRenderer):
            def render_pdf(self, *args, **kwargs):
                result = super().render_pdf(*args, **kwargs)
                trace['renders'].append({'ok': result[0], 'pages': result[1], 'message': result[2]})
                return result
        renderer = TracedBrowser()
        trace['browserPath'] = str(renderer.browser_path)
        result = ResumeBuilder(request['profile'], renderer=renderer).build_ats_plain(
            output, photo=request['photo'] != 'none', photo_path=request.get('photo_path'))
    result = {kind: str(path) for kind, path in result.items()}
    trace['returned'] = result
    print(json.dumps(result))
finally:
    (output / 'renderer-trace.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')
'''


MEASURE = r'''() => {
  const content = document.querySelector('main') || document.body;
  const rect = content.getBoundingClientRect(), style = getComputedStyle(content);
  const left = rect.left + parseFloat(style.paddingLeft), right = rect.right - parseFloat(style.paddingRight);
  const overflow = [];
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    for (const r of range.getClientRects()) {
      if (r.width && (r.left < left - 1 || r.right > right + 1))
        overflow.push({text: node.textContent.trim(), left: r.left, right: r.right});
    }
  }
  const overlaps = [];
  for (const el of document.querySelectorAll('.header, .item-header, .edu-grid, .exam-details')) {
    const children = [...el.children].filter(x => x.getBoundingClientRect().width);
    for (let i = 0; i < children.length; i++) for (let j = i + 1; j < children.length; j++) {
      const a = children[i].getBoundingClientRect(), b = children[j].getBoundingClientRect();
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&
          Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
        overlaps.push([children[i].innerText, children[j].innerText]);
    }
  }
  return {overflow, overlaps, bodyFontPx: parseFloat(getComputedStyle(document.body).fontSize),
          images: [...document.images].map(x => ({complete: x.complete, width: x.naturalWidth}))};
}'''


def render(root, request, target):
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", GENERATOR, str(root)],
                            input=json.dumps(dict(request, output=str(target))), text=True,
                            encoding="utf-8", capture_output=True, cwd=root, timeout=180, check=False)
    target.mkdir(parents=True, exist_ok=True)
    (target / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (target / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Production/source renderer failed at {target}; inspect stderr.txt")
    paths = {kind: Path(path).resolve() for kind, path in json.loads(result.stdout).items()}
    for kind in ("md", "html") + (() if request["source_only"] else ("pdf",)):
        path = paths[kind]
        if target.resolve() not in path.parents or not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"Invalid returned {kind} path: {path}")
    if not request["source_only"]:
        trace = json.loads((target / "renderer-trace.json").read_text())
        if len(trace["renders"]) != 1 or not trace["renders"][0]["ok"]:
            raise RuntimeError("The production BrowserRenderer did not produce the inspected PDF")
    return paths


def inspect_pdf(path, anchors, case):
    import fitz
    errors, bounds = [], []
    with fitz.open(path) as pdf:
        text = squash("".join(page.get_text() for page in pdf))
        missing = [anchor for anchor in anchors if anchor not in text]
        for number, page in enumerate(pdf, 1):
            if abs(page.rect.width - 595.28) > 1 or abs(page.rect.height - 841.89) > 1:
                errors.append(f"page {number}: not A4")
            words = page.get_text("words")
            if not words:
                errors.append(f"page {number}: blank")
            for word in words:
                # Small glyph overshoot tolerance; check every continuation page.
                if word[0] < 43 or word[2] > page.rect.width - 43 or word[1] < 39 or word[3] > page.rect.height - 39:
                    bounds.append({"page": number, "text": word[4], "bbox": word[:4]})
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(path.parent / f"page-{number}.png")
        pages = len(pdf)
        if not 1 <= pages <= case["max_pages"]:
            errors.append(f"{pages} pages exceeds fixture budget {case['max_pages']}")
        if case["name"].startswith("dense") and pages < 2:
            errors.append("dense fixture did not exercise continuation pages")
    return {"pages": pages, "missing": missing, "bounds": bounds, "errors": errors}


def validate_paths(baseline, output):
    baseline, output = baseline.resolve(), output.resolve()
    if baseline == ROOT or ROOT in baseline.parents or not (baseline / "core/resume_view_model.py").is_file():
        raise ValueError("Baseline must be an isolated OfferGet source tree")
    for protected in (ROOT, baseline):
        if output == protected or output in protected.parents or protected == baseline and baseline in output.parents:
            raise ValueError("Output must not overwrite either source tree")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be empty; existing artifacts are never overwritten")
    return baseline, output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    baseline, output = validate_paths(args.baseline_root, args.output)
    output.mkdir(parents=True, exist_ok=True)
    report = {"syntheticOnly": True, "visualVerified": False, "sourceOnly": args.source_only,
              "headRevision": os.environ.get("QA_HEAD_SHA"), "checkoutRevision": os.environ.get("GITHUB_SHA"),
              "baselineRevision": (baseline / "revision.txt").read_text().strip(), "fixtures": [], "failures": []}
    sources = ("core/resume_view_model.py", "core/resume_builder.py", "core/profile_adapter.py",
               "core/browser_renderer.py", "scripts/qa_ats_plain_layout.py", "scripts/qa_modern_navy_layout.py")
    report["sourceManifest"] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}
    try:
        for case in cases():
            folder = output / case["name"]; folder.mkdir()
            (folder / "synthetic-profile.json").write_text(json.dumps(case["profile"], indent=2, ensure_ascii=False), encoding="utf-8")
            request = dict(case, source_only=args.source_only)
            if case["photo"] == "embedded":
                photo = folder / "synthetic-photo.png"
                photo.write_bytes(base64.b64decode(case["photo_data_uri"].split(",", 1)[1]))
                request["photo_path"] = str(photo)
            pair = {"name": case["name"], "sourceAnchorCount": len(source_anchors(case["profile"]))}
            paths = {}
            for phase, root in (("before", baseline), ("after", ROOT)):
                paths[phase] = render(root, request, folder / phase)
                text = squash(text_content(paths[phase]["html"].read_text(encoding="utf-8")))
                missing = [anchor for anchor in source_anchors(case["profile"]) if anchor not in text]
                pair[phase] = {"missingHtml": missing}
                if not args.source_only:
                    pair[phase]["pdf"] = inspect_pdf(paths[phase]["pdf"], source_anchors(case["profile"]), case)
            pair["markdownUnchanged"] = paths["before"]["md"].read_bytes() == paths["after"]["md"].read_bytes()
            if not pair["markdownUnchanged"] or pair["after"]["missingHtml"]:
                report["failures"].append(f"{case['name']}: source/Markdown parity failed")
            if not args.source_only:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    report["inspectionBrowserVersion"] = browser.version
                    for phase in ("before", "after"):
                        page = browser.new_page(viewport={"width": 1000, "height": 1200})
                        blocked = []
                        def block(route, blocked=blocked):
                            blocked.append(route.request.url)
                            route.abort()
                        page.route("**/*", block)
                        page.set_content(paths[phase]["html"].read_text(encoding="utf-8"), wait_until="load")
                        page.evaluate("document.fonts.ready")
                        for media, width in (("screen", 1000), ("mobile", 375), ("print", 673)):
                            page.set_viewport_size({"width": width, "height": 1200})
                            page.emulate_media(media="print" if media == "print" else "screen")
                            pair[phase][media] = page.evaluate(MEASURE)
                            page.screenshot(path=str(paths[phase]["html"].parent / f"{media}.png"), full_page=True)
                        pair[phase]["blockedRequests"] = blocked
                        page.close()
                    browser.close()
                after = pair["after"]
                pdf = after["pdf"]
                if pdf["missing"] or pdf["bounds"] or pdf["errors"]:
                    report["failures"].append(f"{case['name']}: production PDF checks failed")
                for media in ("screen", "mobile", "print"):
                    metric = after[media]
                    if metric["overflow"] or metric["overlaps"] or metric["bodyFontPx"] < 14 - 0.01:
                        report["failures"].append(f"{case['name']}: {media} geometry/type checks failed")
                    if any(not image["complete"] or not image["width"] for image in metric["images"]):
                        report["failures"].append(f"{case['name']}: image did not load")
                if after["blockedRequests"]:
                    report["failures"].append(f"{case['name']}: attempted network request")
            report["fixtures"].append(pair)
            print(f"{case['name']}: source facts checked; Markdown unchanged={pair['markdownUnchanged']}", flush=True)
        report["visualVerified"] = not args.source_only and not report["failures"]
    except Exception as exc:  # noqa: BLE001 - preserve diagnostics for failed browser stages
        report["failures"].append(f"{type(exc).__name__}: {exc}")
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if report["failures"]:
        print("\n".join(report["failures"]), file=sys.stderr)
        return 1
    print("Source-only checks passed; PDF and visual checks remain UNVERIFIED." if args.source_only else "Production PDF and visual checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
