# Native Typst resume

A conventional sans-serif A4 resume with 18 mm margins, readable 10.5 pt body type,
right-aligned dates, plain hanging bullets and compact section hierarchy. CJK text
uses Noto Sans CJK SC; Latin text uses Liberation Sans. Optional photo and reserved
photo layouts keep the contact block separate from the image. Sticky entry headers
and Typst's widow/orphan behavior preserve readable pagination.

Raw view-model fields are escaped for Typst exactly once. Angle brackets and slash
comments remain visible text rather than labels or comments. Long unbroken tokens
receive invisible optional line-break opportunities. Publication titles, authors,
venues and years, education badges, and exam subjects/scores are retained. Photo
filenames use quoted code strings, separate from content markup escaping.

## Reproduce verification

Install the repository dependencies, Noto CJK and Liberation fonts, the pinned
`typst==0.15.0` Python native compiler, and Playwright Chromium. Then run:

    python -m pytest tests/test_academic_typst_design.py -v
    python scripts/qa_academic_typst_layout.py --output artifacts/academic-typst

The harness renders the same fabricated profiles through real native Typst and the
existing academic HTML fallback separately. It also traces actual ResumeBuilder
returned PDFs in native and intentionally forced-fallback branches; the latter uses
BrowserRenderer's normal executable discovery. Every mode has independent source-fact,
A4 and margin checks, native CJK font checks, page PNGs, and a source hash manifest.
Review every actual page image before approving. No private resumes or paid services
are used. This change does not alter LaTeX or the previously verified HTML fallback.

Reference: [Typst block stickiness](https://typst.app/docs/reference/layout/block/),
[bullet list spacing](https://typst.app/docs/reference/model/list/), and the
[maintainer-published Python compiler](https://pypi.org/project/typst/0.15.0/).
