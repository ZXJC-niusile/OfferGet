# ATS DOCX resume layout

The editable Word export uses a conventional, single-column A4 resume:

- 19.05 mm margins, an understated centered identity, and 10.5 pt body type
- Arial with Noto Sans CJK SC for Chinese text (install these or a compatible fallback)
- Right-aligned dates, hanging bullets, and whitespace-led section hierarchy
- Headings stay with the next paragraph; long entries can continue naturally across pages
- Long employer and institution names get a separate date line, rather than splitting dates
- Ordinary body paragraphs, with no text boxes or header/footer contact data
- Optional upper-right portrait in one borderless 1x2 masthead table; no-photo keeps the centered full-width identity and has no table or image

Use `--photo-mode photo --photo-path candidate.png` for the photo version and
`--photo-mode no-photo` for the no-photo version. Store the pair in separate
output directories. Validated image bytes are embedded as PNG, with EXIF
orientation normalized, original aspect ratio preserved, and a 54 x 72 pt maximum
portrait footprint. Identity text precedes the image in the masthead's reading
order. The body remains editable and linear. The ATS checker still reports the
masthead table as a warning; use no-photo where strictly table-free parsing is
required. `placeholder` is a labeled layout preview, not a finished photo resume.

## Content contract

The non-HTML export prefers the view model's `raw_*` fields. Markdown emphasis
becomes Word run formatting, while source ampersands and angle brackets remain
literal text. Legacy HTML-projected view models are decoded once. Organization,
department/role, dates, primary education fields, supplementary education badges,
exam subjects/scores, and publication authors are retained.

## Reproduce visual checks

Install `python-docx`, `PyMuPDF`, LibreOffice Writer (`soffice`), Arial or Liberation Sans, and Noto Sans CJK SC:

    python -m pytest tests/test_ats_docx_design.py tests/test_docx_photo_contract.py -v
    python scripts/qa_ats_docx_layout.py --output artifacts/ats-docx-layout

Format-specific gates (see [shared QA rules](RESUME_THEME_QA.md)): verifies Word body/table text and LibreOffice-converted PDF text/margins; expected page budgets are 1 page for professional/long-field fixtures and 2 pages for dense/exam fixtures (never truncating facts). Photo pairs require `1` first-page portrait in photo mode and `0` tables/images in no-photo mode; Word-specific desktop rendering beyond LibreOffice remains unverified.
