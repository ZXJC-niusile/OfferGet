# ATS DOCX resume layout

The editable Word export uses a conventional, single-column A4 resume:

- 19.05 mm margins, an understated centered identity, and 10.5 pt body type
- Arial with Noto Sans CJK SC for Chinese text (install these or a compatible fallback)
- Right-aligned dates, hanging bullets, and whitespace-led section hierarchy
- Headings stay with the next paragraph; long entries can continue naturally across pages
- Long employer and institution names get a separate date line, rather than splitting dates
- Ordinary body paragraphs only: no tables, text boxes, header/footer contact data, or photos

Photo preferences intentionally do not add images to this ATS-oriented format.
Use a visual HTML theme when a photo layout is needed.

## Content contract

The non-HTML export prefers the view model's `raw_*` fields. Markdown emphasis
becomes Word run formatting, while source ampersands and angle brackets remain
literal text. Legacy HTML-projected view models are decoded once. Organization,
department/role, dates, primary education fields, supplementary education badges,
exam subjects/scores, and publication authors are retained.

## Reproduce visual checks

Install python-docx, PyMuPDF, LibreOffice Writer, Arial or Liberation Sans, and
Noto Sans CJK SC. From the repository root:

    python -m pytest tests/test_ats_docx_design.py tests/test_ats_checker.py tests/test_resume_builder.py -k 'docx or Docx' -v
    python scripts/qa_ats_docx_layout.py --output artifacts/ats-docx-layout

The QA command uses only fabricated bilingual profiles from the shared realistic
fixture set, plus fabricated exam/publication and markup-sentinel facts. It converts
actual DOCX files through LibreOffice, saves every page as PNG, and compares source
facts independently with both Word paragraphs and selectable PDF text. Missing
renderers, missing facts, out-of-margin text, non-A4 output, and excessive pages fail.
The dedicated workflow uploads the DOCX/PDF/PNG/log/report artifacts for review.
Inspect every rendered page; programmatic geometry checks cannot prove aesthetics.

Expected page budgets: one page for the professional, photo-preference, and long-field
fixtures; two pages for dense experience and the extended exam/publication fixture.
The renderer never removes facts to meet a page target. Arbitrary larger user profiles
are allowed to run longer.
