# ATS Plain design and QA

## Scope

Only `AtsPlainRenderer.render_html` changes in the shared view-model module.
The view-model factory, other renderers, Markdown serializer, input aliases,
anonymization, fact guard, and builder dispatch remain unchanged. The design
retains every already-rendered source field and the existing photo choices.
No facts are added, rewritten, shortened, or selected by the theme.

The updated HTML uses a semantic `main`, header, section headings, and entry
headings. Black text, 10.5pt body type, a 1.48 line height, and restrained rules
replace cramped justified text. Education facts follow one linear sequence;
entry dates occupy a separate line. Natural wrapping covers contacts, dates,
organizations, education, exam fields, and skill labels. Print pages retain
15mm top/bottom and 16mm side margins; screen padding responds to narrow widths.
There are no decorative cards, sidebars, tables, gradients, or hidden keywords.

This is a presentation change, not a new ATS parsing guarantee. Existing
Markdown escaping and field support are preserved rather than silently changed.
In particular, this work does not expand ATS Plain's pre-existing publication
or narrative support. Baseline Markdown parity is not proof of factual accuracy.
The source-side checks below are an independent assertion for the supported
facts actually present in the synthetic fixtures.

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

## Local validation against main f01d6c1

- Dedicated design tests: 29 passed.
- Dedicated tests plus existing browser-independent view-model checks: 43 passed.
- Source-only before/after validation: 11 pairs, 335 source anchors preserved in
  HTML, Markdown bytes identical in every pair.
- All module bytes outside `AtsPlainRenderer.render_html`: identical to the base.
- Dedicated QA/test lint: passed.
- Full suite: 985 passed, 2 skipped, 15 failed. The same baseline run has 956
  passed, 2 skipped, and the exact same 15 failures; no new failures were found.
- CLI self-test: failed in the rendering subsystem at the existing real-browser
  AutoFit check. The earlier non-rendering checks ran; this is not a full pass.

The local Chromium processes terminate with `socket() failed: Operation not
permitted` in this execution environment. This prevents actual local PDF and
visual verification, including the existing ATS Plain production test. No
sandbox workaround is used. The draft must remain unapproved for visual
completion until the normal CI workflow produces inspectable PDFs/screenshots
and its exact-head artifacts are reviewed. A CI job that fails before running
steps provides no validation evidence and should be reported as a separate
workflow-start blocker, without guessing its cause.
