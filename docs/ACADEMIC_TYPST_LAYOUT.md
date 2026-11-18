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

Install the repository dependencies, Noto CJK and Liberation fonts, `typst==0.15.0`, and Playwright Chromium, then run:

    python -m pytest tests/test_academic_typst_design.py -v
    python scripts/qa_academic_layout.py --format typst --output artifacts/academic-typst

Format-specific gates (see [shared QA rules](RESUME_THEME_QA.md)): checks Typst CJK font embedding (`Noto Sans CJK`), traced native vs forced-fallback `ResumeBuilder` paths, and `photo_reference` relocation constraints without enabling excluded `--no-photo` images.
