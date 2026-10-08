"""Render synthetic DOCX resumes through real LibreOffice and inspect actual PDFs.

Requires python-docx, PyMuPDF, and soffice. Writes all page PNGs for human review.
Never use private resumes here. Missing render dependencies are hard failures.
"""
from __future__ import annotations

import argparse
import copy
import json
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.ats_docx_renderer import AtsDocxRenderer
from core.resume_view_model import ResumeViewModel
from scripts.qa_modern_navy_layout import fixtures, synthetic_photo


def squash(value):
    return re.sub(r"\s+", "", str(value).replace("**", ""))


def cases():
    wanted = {"professional-none", "professional-reserved", "long-none", "dense-none"}
    result = [copy.deepcopy(case) for case in fixtures() if case["name"] in wanted]
    professional = next(case for case in result if case["name"] == "professional-none")
    academic = copy.deepcopy(professional)
    academic["name"] = "exam-publications"
    academic["profile"]["postgraduate_exam"] = {
        "target_school": "示例研究生院 / Example Graduate School", "target_major": "计算机 / Computing",
        "direction": "Systems & Reliability", "scores": {"政治 / Politics": 70, "英语 / English": 80,
                                                             "数学 / Mathematics": 130, "专业课 / Computing": 120},
        "total_score": 400,
    }
    academic["profile"]["publications"] = [{
        "title": "Reliability & Evidence <Review>", "authors": "Alex Lin & Sam Example",
        "venue": "Synthetic Systems Journal", "year": "2025",
    }]
    academic["profile"]["experience"][0]["bullets"].append("DOCX-RAW-FACT: **C++ & Python**; latency < 20 ms.")
    result.append(academic)
    embedded = copy.deepcopy(professional)
    embedded.update(name="professional-embedded", photo="embedded", photo_data_uri=synthetic_photo())
    result.append(embedded)
    return result


def expected_text(profile):
    """Source-side assertions, independent of the view model and DOCX writer."""
    anchors = [profile[k] for k in ("name", "intent", "phone", "email", "city") if profile.get(k)]
    education = profile.get("education", {})
    anchors.extend(str(value) for value in education.values() if value)
    for collection in ("experience", "campus_experience", "publications"):
        for item in profile.get(collection, []):
            for key, value in item.items():
                anchors.extend(value if key == "bullets" else [str(value)])
    for key, value in profile.get("skills", {}).items():
        anchors.append(key)
        anchors.extend(value if isinstance(value, list) else [value])
    exam = profile.get("postgraduate_exam", {})
    for key, value in exam.items():
        if key == "scores":
            anchors.extend(f"{subject}: {score}" for subject, score in value.items())
        else:
            anchors.append(str(value))
    return [squash(anchor) for anchor in anchors if anchor]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import fitz
    from docx import Document
    soffice = shutil.which("soffice")
    if not soffice:
        raise RuntimeError("Real LibreOffice is required; no mock rendering is accepted")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sources = ["core/ats_docx_renderer.py", "core/resume_view_model.py", "core/profile_adapter.py",
               "scripts/qa_ats_docx_layout.py", "scripts/qa_modern_navy_layout.py"]
    manifest = {}
    for source in sources:
        data = (ROOT / source).read_bytes()
        manifest[source] = {"sha256": hashlib.sha256(data).hexdigest(),
                            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = []
    for case in cases():
        folder = output / case["name"]
        folder.mkdir(exist_ok=True)
        vm = ResumeViewModel.from_profile(case["profile"], reserve_photo=case["photo"] == "reserved")
        vm.photo_data_uri = case.get("photo_data_uri")
        docx = AtsDocxRenderer().render(vm, folder / "resume.docx")
        profile_path = folder / "lo-profile"
        result = subprocess.run([soffice, "-env:UserInstallation=" + profile_path.as_uri(),
                                 "--headless", "--convert-to", "pdf", "--outdir", str(folder), str(docx)],
                                text=True, capture_output=True, timeout=90, check=True)
        (folder / "render.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        pdf = fitz.open(folder / "resume.pdf")
        text = squash("".join(page.get_text() for page in pdf))
        source = expected_text(case["profile"])
        missing = [anchor for anchor in source if anchor not in text]
        doc_text = squash("".join(p.text for p in Document(docx).paragraphs))
        missing_docx = [anchor for anchor in source if anchor not in doc_text]
        overflow = []
        for index, page in enumerate(pdf):
            assert abs(page.rect.width - 595.28) < 1 and abs(page.rect.height - 841.89) < 1
            for word in page.get_text("words"):
                if word[0] < 52 or word[2] > page.rect.width - 52 or word[1] < 48 or word[3] > page.rect.height - 48:
                    overflow.append({"page": index + 1, "word": word[4], "bbox": word[:4]})
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(folder / f"page-{index + 1}.png")
        entry = {"case": case["name"], "pages": len(pdf), "source_anchors": len(source),
                 "missing_pdf": missing, "missing_docx": missing_docx, "overflow": overflow,
                 "max_pages": 2 if case["name"] == "dense-none" else 1}
        report.append(entry)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(r["missing_pdf"] or r["missing_docx"] or r["overflow"] or r["pages"] > r["max_pages"] for r in report):
        raise SystemExit("DOCX visual/content checks failed; see report.json")


if __name__ == "__main__":
    main()
