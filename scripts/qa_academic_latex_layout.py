"""Real native XeLaTeX and independent Chromium fallback QA, synthetic facts only."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.academic_exporter import AcademicExporter
from core.resume_view_model import ResumeViewModel
from scripts.qa_ats_docx_layout import cases, expected_text


def squash(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).replace("**", "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    import fitz
    from playwright.sync_api import sync_playwright
    compiler = shutil.which("xelatex")
    if not compiler:
        raise RuntimeError("Real XeLaTeX is required for native QA")
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    sources = ["core/academic_exporter.py", "core/resume_view_model.py", "core/profile_adapter.py",
               "scripts/qa_academic_latex_layout.py", "scripts/qa_ats_docx_layout.py", "scripts/qa_modern_navy_layout.py"]
    manifest = {}
    for source in sources:
        data = (ROOT / source).read_bytes()
        manifest[source] = {"sha256": hashlib.sha256(data).hexdigest(),
                            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2))
    report = []
    exporter = AcademicExporter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for case in cases():
                folder = output / case["name"]; folder.mkdir(exist_ok=True)
                photo = None
                if case["photo"] == "embedded":
                    photo = folder / "synthetic-photo.png"
                    photo.write_bytes(base64.b64decode(case["photo_data_uri"].split(",", 1)[1]))
                profile = case["profile"]
                # Cover entities in organization/role as well as bullets/publications.
                if case["name"] == "exam-publications":
                    profile["experience"][0]["company"] = "Example & Research <Group>"
                    profile["experience"][0]["role"] = "R&D Engineer"
                vm = ResumeViewModel.from_profile(profile, photo_path=photo, reserve_photo=case["photo"] == "reserved")
                tex = folder / "resume.tex"
                tex.write_text(exporter.generate_latex(vm), encoding="utf-8")
                html = folder / "resume.html"
                html.write_text(exporter.generate_latex_html_preview(vm, reserve_photo=case["photo"] == "reserved"), encoding="utf-8")
                native = folder / "native"; native.mkdir(exist_ok=True)
                compile_result = subprocess.run([compiler, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode",
                                                  "-output-directory=" + str(native), str(tex)],
                                                 cwd=folder, text=True, capture_output=True, timeout=90)
                (native / "compiler.log").write_text(compile_result.stdout + compile_result.stderr, encoding="utf-8")
                if compile_result.returncode != 0:
                    raise RuntimeError(f"Native compile failed for {case['name']}; inspect compiler.log")
                log = (native / "resume.log").read_text(errors="replace")
                if "Missing character:" in log:
                    raise RuntimeError(f"Missing native glyphs for {case['name']}")
                fallback = folder / "fallback"; fallback.mkdir(exist_ok=True)
                page = browser.new_page(viewport={"width": 658, "height": 1000})
                page.emulate_media(media="print")
                page.goto(html.as_uri(), wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                page.pdf(path=str(fallback / "resume.pdf"), format="A4", prefer_css_page_size=True, print_background=True)
                overlaps = page.evaluate('''() => [...document.querySelectorAll('.item-header')].filter(el => {
                  const [a,b] = [...el.children].map(x=>x.getBoundingClientRect());
                  return a.right > b.left + 1 && Math.min(a.bottom,b.bottom)>Math.max(a.top,b.top);
                }).map(el=>el.innerText)''')
                page.close()
                for mode in ("native", "fallback"):
                    pdf = fitz.open(folder / mode / "resume.pdf")
                    text = squash("".join(page.get_text() for page in pdf))
                    missing = [anchor for anchor in expected_text(profile) if squash(anchor) not in text]
                    overflow = []
                    for index, pdf_page in enumerate(pdf):
                        assert abs(pdf_page.rect.width - 595.28) < 1 and abs(pdf_page.rect.height - 841.89) < 1
                        for word in pdf_page.get_text("words"):
                            if word[0] < 47 or word[2] > pdf_page.rect.width - 47 or word[1] < 45 or word[3] > pdf_page.rect.height - 45:
                                overflow.append({"page": index + 1, "text": word[4], "bbox": word[:4]})
                        pdf_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(folder / mode / f"page-{index + 1}.png")
                    report.append({"case": case["name"], "mode": mode, "pages": len(pdf), "missing": missing,
                                   "overflow": overflow, "overlaps": overlaps if mode == "fallback" else [],
                                   "overfull_boxes": len(re.findall(r"Overfull \\hbox", log)) if mode == "native" else 0,
                                   "max_pages": 3 if case["name"] == "dense-none" else 2})
            # Verify the actual builder return path in both modes, not only the
            # generator. The native result must not silently be a browser PDF.
            from core.resume_builder import ResumeBuilder
            from core.browser_renderer import BrowserRenderer
            production = next(case for case in cases() if case["name"] == "professional-none")
            for mode in ("native", "forced-fallback"):
                trace = {"mode": mode, "compile": [], "browser": []}
                class TracedExporter(AcademicExporter):
                    def compile_latex(self, source, target):
                        success = False if mode == "forced-fallback" else super().compile_latex(source, target)
                        trace["compile"].append({"success": success, "forced_unavailable": mode == "forced-fallback"})
                        return success
                class TracedBrowser(BrowserRenderer):
                    def render_pdf(self, *values, **kwargs):
                        result = super().render_pdf(*values, **kwargs)
                        trace["browser"].append({"ok": result[0], "pages": result[1], "message": result[2]})
                        return result
                folder = output / ("production-" + mode); folder.mkdir(exist_ok=True)
                builder = ResumeBuilder(production["profile"], renderer=TracedBrowser(browser_path=playwright.chromium.executable_path))
                builder.academic_exporter = TracedExporter()
                result = builder.build_academic_latex(folder, photo=False)
                trace["returned_pdf"] = str(result["pdf"])
                (folder / "builder-trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
                assert len(trace["compile"]) == 1
                assert trace["compile"][0]["success"] == (mode == "native")
                assert len(trace["browser"]) == (0 if mode == "native" else 1)
                pdf = fitz.open(result["pdf"])
                text = squash("".join(page.get_text() for page in pdf))
                missing = [anchor for anchor in expected_text(production["profile"]) if squash(anchor) not in text]
                overflow = []
                for index, pdf_page in enumerate(pdf):
                    assert abs(pdf_page.rect.width - 595.28) < 1 and abs(pdf_page.rect.height - 841.89) < 1
                    for word in pdf_page.get_text("words"):
                        if word[0] < 47 or word[2] > pdf_page.rect.width - 47 or word[1] < 45 or word[3] > pdf_page.rect.height - 45:
                            overflow.append({"page": index + 1, "text": word[4], "bbox": word[:4]})
                    pdf_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(folder / f"page-{index + 1}.png")
                report.append({"case": "production-professional", "mode": mode, "pages": len(pdf), "missing": missing,
                               "overflow": overflow, "overlaps": [], "overfull_boxes": 0, "max_pages": 2})
        finally:
            browser.close()
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if any(r["missing"] or r["overflow"] or r["overlaps"] or r["overfull_boxes"] or r["pages"] > r["max_pages"] for r in report):
        raise SystemExit("Native/fallback layout or source checks failed; inspect report.json")


if __name__ == "__main__":
    main()
