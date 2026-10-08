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

Install python-docx, PyMuPDF, LibreOffice Writer, Arial or Liberation Sans, and
Noto Sans CJK SC. From the repository root:

    python -m pytest tests/test_ats_docx_design.py tests/test_ats_checker.py tests/test_resume_builder.py -k 'docx or Docx' -v
    python scripts/qa_ats_docx_layout.py --output artifacts/ats-docx-layout

The QA command uses only fabricated bilingual profiles from the shared realistic
fixture set, plus fabricated exam/publication and markup-sentinel facts. It converts
actual DOCX files through LibreOffice, saves every page as PNG, and compares source
facts independently with both Word body/table text and selectable PDF text. Missing
renderers, missing facts, out-of-margin text, non-A4 output, and excessive pages fail.
The dedicated workflow uploads the DOCX/PDF/PNG/log/report artifacts for review.
A source hash manifest links each run to the exact renderer and fixture code.
Inspect every rendered page; programmatic geometry checks cannot prove aesthetics.

Expected page budgets: one page for the professional, photo-preference, and long-field
and extended exam/publication fixtures; two pages for dense experience.
The renderer never removes facts to meet a page target. Arbitrary larger user profiles
are allowed to run longer.

## Photo pair validation

`tests/test_docx_photo_contract.py` checks byte-backed media relationships, four
aspect ratios, raw text and reading order, no-photo exclusion, invalid data URIs,
image format conversion, EXIF orientation, and actual CLI pairing. The added
source tests do not substitute for visual inspection.

The October 8 local supported LibreOffice check rendered three clearly synthetic
photo/no-photo pairs: ordinary and long-header profiles at one page per version,
and dense experience at two pages per version. Every rendered page was inspected;
paired selectable text was identical and no text crossed the margin checks. The
illustrated test portrait appears once on the first page. These results cover
LibreOffice on the tested source; Microsoft Word-specific rendering is untested.
