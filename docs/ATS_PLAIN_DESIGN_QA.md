# ATS Plain design and QA

## Scope

`AtsPlainRenderer` provides the plain HTML/Markdown resume view. It uses the
shared view model, photo resolver, and output security checks. The theme formats
source facts; it must not invent, shorten, or rewrite achievements.

The updated HTML uses a semantic `main`, header, section headings, and entry
headings. Black text, 10.5pt body type, a 1.48 line height, and restrained rules
replace cramped justified text. Education facts follow one linear sequence;
entry dates occupy a separate line. Natural wrapping covers contacts, dates,
organizations, education, exam fields, and skill labels. Print pages retain
15mm top/bottom and 16mm side margins; screen padding responds to narrow widths.
There are no decorative cards, sidebars, tables, gradients, or hidden keywords.

The layout does not guarantee acceptance by every ATS. Check supported source
fields against the current renderer and inspect the exported text. Markdown
parity alone does not establish factual completeness.

## Reproducible checks

The dedicated harness uses only fabricated bilingual profiles and reserved
`.invalid` contact addresses. Eleven before/after fixture pairs cover ordinary
and professional resumes, reserved/embedded/no photos, dense continuation
pages, pathological contacts, dates, skill labels, long exam fields, HTML
escaping, flat input aliases, and structured input aliases. It reads 335 source
anchors directly from those profiles, independently of the view model.

```bash
python -m pytest tests/test_ats_plain_design.py -v
python scripts/qa_ats_plain_layout.py \
  --baseline-root /absolute/path/to/exact-baseline \
  --output /absolute/path/to/new-output-directory
```

The baseline must be an isolated checkout/archive with a `revision.txt` containing
its verified commit SHA. Both source trees run in separate Python interpreters.
The normal harness calls the actual `ResumeBuilder.build_ats_plain` using ordinary
`BrowserRenderer` discovery, preserves its returned Markdown/HTML/PDF paths and
render trace, and inspects that exact PDF. It does not substitute a second PDF
export, alter browser launch flags, or replace the renderer with a mock.

Validation checks all source anchors in HTML and selectable PDF text, exact
Markdown bytes against the baseline, A4 size, every page's text gutters, blank
pages, fixture page budgets, and real continuation pages for the dense profile.
Desktop/narrow/print geometry checks cover text overflow and sibling overlap,
the body font floor, image loading, and unexpected network requests. Artifacts
include source profiles, before/after Markdown and HTML, actual production PDFs,
every PDF page PNG, screen screenshots, renderer traces, diagnostics, source
hashes, baseline/head/checkout revision identifiers, and `report.json`.

A machine pass still requires visual inspection of ordinary, dense, long,
exam, and photo layouts before design approval. If a stage fails, inspect the
retained diagnostics; missing browser dependencies do not become a pass.

`--source-only` runs the source/Markdown checks without a browser. Its report
explicitly marks `sourceOnly: true` and `visualVerified: false`. It cannot
establish PDF pagination, glyph quality, clipping, or aesthetic approval.

The isolated `ats-plain-layout.yml` workflow does not replace or disable the
repository's existing matrix, HTML theme, DOCX, LaTeX, or Typst checks. A shared
view-model edit continues to trigger the existing checks according to their
path filters.

## Photo behavior

Actual-photo markup has no inline `onerror` handler. No-photo mode excludes the
image and reserved slot; placeholders remain an explicit preview choice.
Embedded-image QA enables photo selection explicitly. See
[photo modes](RESUME_PHOTO_MODES.md) for the input contract.

## Recording results

Run the checks above for the revision being reviewed. Report source checks,
real-browser results, and visual inspection separately. Earlier development-run
counts and environment failures do not describe the current checkout.

Follow [release verification](RELEASE_VERIFICATION.md) to record the environment,
failures, skips, and retained artifacts. A local pytest pass does not prove that
remote CI ran or that every rendered page was visually approved.
