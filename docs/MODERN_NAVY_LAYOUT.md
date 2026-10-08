# Modern Navy layout regression checks

This theme-only change keeps the existing palette, factual content, A4 dimensions,
and six AutoFit CSS tokens. It lets long names, email addresses, organizations,
roles, project names, and education metadata wrap inside their available space.
Dates keep their own aligned column; bilingual bullets use natural start alignment.
Printed continuation pages repeat the vertical gutter, and entry headings stay
with their following content. Other themes and the shared renderer are unchanged.

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

The ten paired fixtures cover:

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
