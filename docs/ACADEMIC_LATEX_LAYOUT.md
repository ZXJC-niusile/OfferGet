# Academic LaTeX resume

The academic export uses a conventional serif A4 resume with 18 mm margins,
10.5 pt body type, aligned dates, hanging bullets, and section headings without
colored boxes or heavy rules. Long uninterrupted tokens receive safe line-break
opportunities; entries remain free to paginate rather than losing facts.

Native XeLaTeX uses TeX Gyre Termes (or Latin Modern Roman) and tries Noto Serif
CJK SC, Source Han Serif SC, SimSun, then the TeX Live Fandol family. The default
therefore does not depend on a proprietary Windows font being installed.

The standalone HTML/browser fallback uses the same source fields and a similar
serif hierarchy. It remains a separate rendering path. It now includes publication
authors, venue and year, and decodes HTML-projected education/exam values only once.
This shared academic fallback is also used when native Typst is unavailable;
the native Typst generator is unchanged in this PR.

## Validation

    python -m pytest tests/test_academic_latex_design.py -v
    python scripts/qa_academic_latex_layout.py --output artifacts/academic-latex

The second command requires working XeLaTeX with xeCJK/standard LaTeX packages,
Noto CJK fonts, PyMuPDF and Playwright Chromium. It compiles real native PDFs and
renders the HTML fallback independently for six entirely fabricated bilingual,
long-field, dense, photo-preference, exam/publication fixtures. Each mode gets
separate PDFs, page PNGs and source-fact/margin checks. Two additional traced production
builds inspect ResumeBuilder's returned PDF: real native compilation and an intentionally
forced fallback using the real BrowserRenderer. Native missing glyphs,
compiler errors and overfull horizontal boxes fail. A source hash manifest ties
artifacts to the exact exporter and fixture revisions. Inspect all page images
before approval; the checks alone do not establish visual quality.

Each fixture resolves an explicit photo, no-photo or placeholder mode once for
both LaTeX and HTML sources. Both native and fallback PDFs must contain exactly
one embedded image for the portrait case and none for the other modes, including
the production no-photo builds. Missing or duplicate portraits fail the gate.
Source-mode and PDF-inspection unit tests do not replace actual renderer runs.

Compilation failures are not treated as native success merely because a partial
or stale PDF exists. XeLaTeX runs with shell escape disabled and halts on errors.
Photo filenames containing braces, percent signs or line breaks produce a clear error
rather than ambiguous TeX.
