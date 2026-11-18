"""Shared test fixtures, builders, and doubles independent of test_*.py modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from core.browser_renderer import BrowserRenderer


class FastBrowserRenderer(BrowserRenderer):
    """Lightweight headless browser double generating valid A4 PDFs instantly."""

    MINIMAL_PDF_BYTES = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n164\n%%EOF\n"
    )

    def __init__(self, browser_path: str = "fast-test-renderer"):
        self.browser_path = browser_path

    def render_pdf(self, html_path, pdf_path, timeout_seconds=30):
        pdf_file = Path(pdf_path).resolve()
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(self.MINIMAL_PDF_BYTES)
        return True, 1, f"Fast test render 1 page ({len(self.MINIMAL_PDF_BYTES)} bytes)"

    def count_pages(self, pdf_path):
        return 1

    def measure_overflow(self, html_path, a4_target_height=1122.5):
        return 1000, 0


def academic_design_fixture() -> Dict[str, Any]:
    """Synthetic bilingual/academic profile exercising LaTeX & Typst escaping."""
    return {
        "candidate": {
            "name": "示例 Alex & Lin",
            "title": "R&D Engineer",
            "email": "qa@example.invalid",
            "school": "Example & University",
            "degree": "MSc",
            "edu_time": "2018 - 2020",
            "education_rows": [["GPA > 3.8", "Award & Merit"]],
            "reserve_photo": False,
        },
        "experience": [
            {
                "org": "Research & Systems <Group>",
                "dept": "R&D",
                "role": "Engineer <Lead>",
                "time": "2020 - 2025",
                "bullets": [
                    "Used **C++ & SQL**; latency < 20 ms.",
                    "Literal &amp; and <strong>text</strong>.",
                ],
            }
        ],
        "projects": [
            {
                "name": "Project <One>",
                "role": "Owner & Maintainer",
                "time": "2022 - 2024",
                "bullets": [r"Printed \input{sample} literally; 95% complete."],
            }
        ],
        "publications": [
            {
                "title": "Evidence & Safety <Review>",
                "authors": "A. Lin & B. Example",
                "venue": "Synthetic Journal",
                "year": "2025",
            }
        ],
        "postgraduate_exam": {
            "target_school": "Graduate & School",
            "target_major": "Computing",
            "scores": {"Math <A>": 130, "English": 80},
            "total_score": 210,
        },
        "competencies": {"Tools & Languages": ["C++", "R&D"]},
    }


def docx_synthetic_profile() -> Dict[str, Any]:
    """Synthetic profile exercising Word XML escaping, badges, exam scores, and pubs."""
    return {
        "name": "林示例 Alex & Lin",
        "intent": "R&D Engineer",
        "email": "qa@example.invalid",
        "phone": "+00 000 000 0000",
        "city": "示例城市",
        "education": {
            "school": "Example & 示例大学",
            "degree": "MSc",
            "major": "Computing",
            "time": "2018 - 2020",
            "gpa": "3.8/4.0",
            "awards": "Test & Scholarship",
        },
        "experience": [
            {
                "company": "ACME & R&D",
                "dept": "Tools <Platform>",
                "role": "Engineer",
                "time": "2020 - 2024",
                "bullets": [
                    "Maintained **C++ & Python**; latency < 20 ms.",
                    "Literal &amp; and <strong>source</strong> remain source text.",
                ],
            }
        ],
        "campus_experience": [
            {
                "name": "Project <One>",
                "role": "Owner & Maintainer",
                "time": "2019 - 2020",
                "bullets": ["TEST-PROJECT-FACT"],
            }
        ],
        "skills": {"Tools & Languages": ["C++", "R&D"]},
        "publications": [
            {
                "title": "Safety & Systems",
                "authors": "A. Lin & B. Example",
                "venue": "Test <Journal>",
                "year": "2025",
            }
        ],
        "postgraduate_exam": {
            "target_school": "Example Graduate School",
            "target_major": "计算机",
            "direction": "Systems & Reliability",
            "scores": {"Math <A>": 130, "English": 80},
            "total_score": 210,
        },
        "narrative": {"summary_en": "Builds reproducible systems for synthetic QA."},
    }


def valid_layout_metrics() -> Dict[str, Any]:
    """Baseline passing visual-QA metrics dictionary for failure-gate tests."""
    return {
        "screen": {"overflow": [], "overlaps": [], "images": [], "bodyFontPx": 12},
        "print": {"overflow": [], "overlaps": [], "printPaddingMm": 8.8},
        "textUnchanged": True,
        "blockedRequests": [],
        "pdf": {
            "pages": 1,
            "missingAnchors": [],
            "pageBounds": [
                {"number": 1, "widthPt": 595.28, "heightPt": 841.89, "textTopPt": 26, "textBottomPt": 700}
            ],
        },
    }
