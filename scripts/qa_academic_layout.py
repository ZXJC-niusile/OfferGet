"""Check native and browser-rendered academic resumes using synthetic profiles."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.academic_exporter import AcademicExporter
from core.resume_builder import ResumeBuilder
from core.resume_view_model import ResumeViewModel
from scripts.qa_common import academic_docx_cases, build_source_manifest, expected_profile_text, squash


def fixture_view_model(case, photo=None):
    mode = {"none": "no-photo", "reserved": "placeholder", "embedded": "photo"}[case["photo"]]
    return ResumeViewModel.from_profile(case["profile"], photo_path=photo, photo_mode=mode)


def pdf_photo_metrics(pdf, photo):
    expected = int(photo == "embedded")
    actual = sum(len(page.get_image_info()) for page in pdf)
    return {"expected_images": expected, "actual_images": actual,
            "photo_errors": [] if actual == expected else [
                f"Expected {expected} portrait images, found {actual}"]}


def compile_native(fmt, folder, vm, photo):
    native = folder / "native"
    native.mkdir(exist_ok=True)
    log = native / "compiler.log"
    exporter = AcademicExporter()
    if fmt == "typst":
        import typst

        source = folder / "resume.typ"
        source.write_text(exporter.generate_typst(vm, photo_reference=photo.name if photo else None), encoding="utf-8")
        try:
            typst.compile(source, output=str(native / "resume.pdf"))
        except Exception as error:
            log.write_text(str(error), encoding="utf-8")
            raise
        log.write_text(f"Typst Python {version('typst')}: native compilation succeeded\n", encoding="utf-8")
        return 0

    compiler = shutil.which("xelatex")
    if not compiler:
        raise RuntimeError("XeLaTeX is required for native LaTeX QA")
    source = folder / "resume.tex"
    source.write_text(exporter.generate_latex(vm), encoding="utf-8")
    result = subprocess.run([compiler, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode",
                             "-output-directory=" + str(native), str(source)],
                            cwd=folder, capture_output=True, timeout=90)
    log.write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Compilation failed. See {log}")
    transcript = (native / "resume.log").read_text(errors="replace")
    if "Missing character:" in transcript:
        raise RuntimeError(f"Missing native glyphs. See {log}")
    return len(re.findall(r"Overfull \\hbox", transcript))


def render_fallback(browser, folder, vm):
    fallback = folder / "fallback"
    fallback.mkdir(exist_ok=True)
    html = folder / "resume.html"
    html.write_text(AcademicExporter().generate_academic_html_preview(vm), encoding="utf-8")
    page = browser.new_page(viewport={"width": 658, "height": 1000})
    try:
        page.emulate_media(media="print")
        page.goto(html.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.pdf(path=str(fallback / "resume.pdf"), format="A4", prefer_css_page_size=True, print_background=True)
        return page.evaluate("""() => [...document.querySelectorAll('.item-header')].filter(el => {
          const [a,b] = [...el.children].map(x=>x.getBoundingClientRect());
          return a.right > b.left + 1 && Math.min(a.bottom,b.bottom)>Math.max(a.top,b.top);
        }).map(el=>el.innerText)""")
    finally:
        page.close()


def inspect_pdf(fmt, case, mode, path, image_dir, *, overlaps=(), overfull_boxes=0, check_cjk_font=False):
    import fitz

    name = case["name"]
    max_pages = 3 if name == "dense-none" else 2
    if fmt == "latex" and name == "exam-publications":
        max_pages = 1
    with fitz.open(path) as pdf:
        if check_cjk_font:
            fonts = {font[3] for page in pdf for font in page.get_fonts()}
            if not any("notosanscjk" in font.lower().replace("-", "") for font in fonts):
                raise RuntimeError(f"Native CJK font missing in {path}: {fonts}")
        text = squash("".join(page.get_text() for page in pdf))
        missing = [value for value in expected_profile_text(case["profile"]) if squash(value) not in text]
        overflow = []
        for index, page in enumerate(pdf, start=1):
            width, height = page.rect.width, page.rect.height
            assert abs(width - 595.28) < 1 and abs(height - 841.89) < 1, path
            for word in page.get_text("words"):
                if word[0] < 47 or word[2] > width - 47 or word[1] < 45 or word[3] > height - 45:
                    overflow.append({"page": index, "text": word[4], "bbox": word[:4]})
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(image_dir / f"page-{index}.png")
        photos = pdf_photo_metrics(pdf, case["photo"]) if fmt == "latex" else {}
        return {"case": name, "mode": mode, "pages": len(pdf), "max_pages": max_pages, "missing": missing,
                "overflow": overflow, "overlaps": list(overlaps), "overfull_boxes": overfull_boxes, **photos}


def check_fixture(fmt, case, output, browser):
    folder = output / case["name"]
    folder.mkdir(exist_ok=True)
    photo = None
    if case["photo"] == "embedded":
        filename = "synthetic-photo.png"
        if fmt == "typst":
            filename = 'synthetic "photo" %.png' if os.name != "nt" else "synthetic photo %.png"
        photo = folder / filename
        photo.write_bytes(base64.b64decode(case["photo_data_uri"].split(",", 1)[1]))
    if case["name"] == "exam-publications":
        experience = case["profile"]["experience"][0]
        experience.update(company="Example & Research <Group>", role="R&D Engineer")
        if fmt == "typst":
            experience["bullets"][-1] = ("TYPST-RAW-FACT: **C++ & Python**; latency < 20 ms. "
                                         "Literal // comment remains visible. ~/.config --- literal.\n+ source item\n- source bullet")
    vm = fixture_view_model(case, photo)
    boxes = compile_native(fmt, folder, vm, photo)
    overlaps = render_fallback(browser, folder, vm)
    return [
        inspect_pdf(fmt, case, "native", folder / "native/resume.pdf", folder / "native",
                    overfull_boxes=boxes, check_cjk_font=fmt == "typst"),
        inspect_pdf(fmt, case, "fallback", folder / "fallback/resume.pdf", folder / "fallback", overlaps=overlaps),
    ]


def check_builder(fmt, case, output, mode):
    folder = output / ("production-" + mode)
    folder.mkdir(exist_ok=True)
    builder = ResumeBuilder(case["profile"])
    compile_name = f"compile_{fmt}"
    forced = mode == "forced-fallback"
    compiler = getattr(builder.academic_exporter, compile_name)
    trace = {"mode": mode, "compile": [], "browser": [], "browserPath": str(builder.renderer.browser_path)}

    def compile_pdf(source, target):
        success = False if forced else compiler(source, target)
        trace["compile"].append({"success": success, "forced_unavailable": forced})
        return success

    render = builder.renderer.render_pdf

    def render_pdf(*args, **kwargs):
        result = render(*args, **kwargs)
        trace["browser"].append({"ok": result[0], "pages": result[1], "message": result[2]})
        return result

    with patch.object(builder.academic_exporter, compile_name, compile_pdf), patch.object(builder.renderer, "render_pdf", render_pdf):
        build = getattr(builder, f"build_academic_{fmt}")
        result = build(folder, photo=False)
    trace["returned_pdf"] = str(result["pdf"])
    (folder / "builder-trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    assert trace["compile"] == [{"success": not forced, "forced_unavailable": forced}]
    assert len(trace["browser"]) == int(forced)
    assert ("html" in result) == (fmt == "latex" or forced)
    return inspect_pdf(fmt, dict(case, name="production-professional"), mode, result["pdf"], folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", required=True, choices=("latex", "typst"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sources = ["core/academic_exporter.py", "core/resume_view_model.py", "core/profile_adapter.py",
               "core/resume_photo.py", "core/resume_builder.py", "scripts/qa_academic_layout.py", "scripts/qa_common.py"]
    (output / "source-manifest.json").write_text(json.dumps(build_source_manifest(ROOT, sources), indent=2))
    report = []
    cases = academic_docx_cases()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for case in cases:
                report.extend(check_fixture(args.format, case, output, browser))
        finally:
            browser.close()
    production = next(case for case in cases if case["name"] == "professional-none")
    for mode in ("native", "forced-fallback"):
        report.append(check_builder(args.format, production, output, mode))
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    (output / "report.json").write_text(payload, encoding="utf-8")
    print(payload)
    if any(r["missing"] or r["overflow"] or r["overlaps"] or r["overfull_boxes"]
           or r.get("photo_errors") or r["pages"] > r["max_pages"] for r in report):
        raise SystemExit("Native/fallback layout or source checks failed; inspect report.json")


if __name__ == "__main__":
    main()
