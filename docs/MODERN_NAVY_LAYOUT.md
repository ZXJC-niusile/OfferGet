# Modern Navy layout regression checks

Modern Navy uses a conventional, single-column resume hierarchy: a stacked name
and target role, plain organization headings with subordinate role lines, aligned
dates, round hanging bullets, and thin rules below section labels. Navy is reserved
for the name and section labels; body text uses one familiar sans-serif family.
The default body size is 13.333px (10pt), with 14mm side margins. Shaded organization
bands, left rails, section pins, ornamental serif dates and project/code badges
have been removed. Safety warnings for unresolved facts remain visible.

The theme still preserves all factual content, A4 dimensions, six AutoFit tokens,
long-field wrapping, and repeatable print gutters. Existing AutoFit may select a
smaller profile for dense input; this change does not alter its ladder or the
shared renderer. Theme-scoped overrides are necessary for that renderer's inline
presentation defaults. Other themes are unchanged.

Design references: [MIT CAPD master's sample](https://cdn.uconnectlabs.com/wp-content/uploads/sites/123/2025/05/MITCAPD-MastersII.pdf)
and [Harvard's bullet resume template](https://cdn-careerservices.fas.harvard.edu/wp-content/uploads/sites/161/2024/07/resume-bullets.pdf).
These inform the typography-led hierarchy, plain entries, and hanging bullets;
this is not a reproduction or a claim of guaranteed ATS acceptance.

## Reproduce the visual comparison

Use an isolated archive of the exact comparison commit. Do not pass a user's
resume or contact data: the script owns its explicitly fabricated fixtures and
uses reserved `.invalid` addresses. The embedded-image fixture is a color swatch,
not a person's photo. No remote fonts, photos, or other network resources load.

```bash
BASE_SHA="<full comparison commit SHA>"
BASE_DIR="$(mktemp -d)"
git archive "$BASE_SHA" | tar -x -C "$BASE_DIR"
printf '%s\n' "$BASE_SHA" > "$BASE_DIR/revision.txt"
python -m pip install -e '.[all]' 'playwright==1.62.0'
python -m playwright install --with-deps chromium
# Install local CJK fonts if absent (CI uses fonts-noto-cjk).
python scripts/qa_modern_navy_layout.py \
  --baseline-root "$BASE_DIR" \
  --output-dir output/visual-regression
```

The output directory must be new or empty. The script never deletes old output,
rewrites either input tree, or fetches a baseline. Each baseline/current HTML is
created in a separate Python interpreter importing that tree's actual
`ResumeViewModel`, `HtmlThemeRenderer`, and applicable layout/AutoFit code.

The sixteen paired fixtures cover:

- Short bilingual resumes with and without a reserved photo slot
- Long names, unbroken email/organization/project strings and education metadata,
  with and without a reserved photo slot
- Dense bilingual multi-page resumes using the layout solver, with and without a
  reserved photo slot
- Long resumes using the existing most-compact AutoFit token profile, with and
  without a reserved photo slot
- A long resume with an actual embedded synthetic PNG
- A short resume through the real `ResumeBuilder.build_html_theme` production path,
  tracing the BrowserRenderer measurement API, the layout solver, and AutoFit; the returned
  HTML/PDF paths are checked and that actual PDF is inspected

- Two realistic, medium-density bilingual resumes through that same production
  builder, with and without a photo slot, each containing two work entries and
  two projects. These support aesthetic review alongside the extreme fixtures.

- Long bilingual and unbroken skill-category labels and values through both raw
  and production-builder rendering, with and without a photo slot. The theme
  explicitly overrides the shared label nowrap/shrink defaults.

This exercises the renderer, all six AutoFit variables, solver print CSS, and the
production builder pipeline. The builder measurement API can fall back to a PDF
page-count estimate; it is recorded separately from the actual Playwright DOM/text
geometry checks. CLI argument parsing and browser retry failures remain
covered by the existing builder and AutoFit suites.

## Artifacts and pass criteria

Every pair gets a populated HTML file, full-page screen PNG, selectable-text PDF,
PNG for every printed page, and `metrics.json`. The top-level `report.json`
records source revisions where available, template hashes, text hashes,
Playwright/Chromium versions, fixture names, page counts, and failures. The
production pair uses BrowserRenderer's normal browser discovery and records the
selected executable path in its trace. Full child stdout/stderr and renderer
traces are retained as artifacts; a bounded error excerpt appears in the report
if production rendering fails or times out.

The check fails on current-template text changes, horizontal text overflow,
intersecting flex/grid siblings, missing PDF text, unloaded embedded images,
network requests, empty/non-A4 pages, continuation text outside vertical gutters,
fixture page-budget violations, or body type below the existing 10.6px AutoFit
floor. Baseline failures are recorded but do not fail the run. Execution errors
also fail and leave available artifacts and diagnostics behind.

Normal pytest covers fixture safety, unchanged body text, token compatibility,
wrapping contracts, isolated output paths, and the failure conditions without
requiring Playwright. The dedicated GitHub visual workflow runs real Chromium
with local CJK fonts and uploads the artifacts even on failure.

Screenshots still need human review for typography, glyph quality, awkward
wrapping, and page-break aesthetics. Geometry checks alone are not visual approval.
