# HTML resume theme visual QA

The shared harness compares the same explicitly synthetic input against an
isolated exact baseline and the working tree. It supports all eight HTML themes:
`modern-navy`, `modern-corporate`, `classic-tech`, `silicon-clean`, `asu-dense`,
`sidebar-clean`, `academic-postgraduate`, and `engineering-sb2nov`.

```bash
BASE_SHA="<exact comparison commit>"
BASE_DIR="$(mktemp -d)"
git archive "$BASE_SHA" | tar -x -C "$BASE_DIR"
printf '%s\n' "$BASE_SHA" > "$BASE_DIR/revision.txt"
python -m pip install -e '.[all]' 'playwright==1.62.0'
python -m playwright install --with-deps chromium
# Install local CJK fonts (CI uses fonts-noto-cjk).
python scripts/qa_modern_navy_layout.py --theme modern-corporate \
  --baseline-root "$BASE_DIR" --output-dir output/corporate-comparison
```

The historical script filename and default `modern-navy` invocation remain
compatible. `--theme` explicitly selects both the baseline and current template,
including the three real `ResumeBuilder.build_html_theme` production fixtures.
Do not rewrite templates into another theme's filename, render mock HTML, or force
a test-only browser executable. The production path uses ordinary browser
discovery, records measurement/AutoFit/render calls, and inspects the PDF actually
returned by the builder. Each source tree is imported in a separate interpreter.

## Coverage and artifacts

The sixteen common fixtures cover short and pathological long bilingual input,
photo slots and embedded synthetic images, the most compact AutoFit profile,
dense two-page solver output, a short production build, and realistic bilingual
production builds with two work entries and two projects, with/without a photo.
All fixture facts are fabricated; contacts use reserved `.invalid` domains. The academic theme adds four production exam cases: normal/long target and
subject fields, each with and without a photo slot; every score cell is checked.
Do
not substitute a user's resume. No external resources or paid services load.

Each fixture has before/after HTML, full-page screen PNG, selectable-text PDF,
every printed page as a PNG, and geometry/text metrics. `report.json` identifies
the theme, exact baseline, requested PR head, CI merge revision, template hashes,
browser versions, all fixture page counts, and failures. Production child logs
and API traces remain available even when rendering fails.

Gates cover factual text, text overflow/overlap, missing PDF anchors, A4 page
bounds, repeated print gutters, loaded images, no external resource requests,
page budgets, and the existing AutoFit font floor. Baseline defects are recorded;
current defects fail. Existing outputs and either source tree are never
overwritten. Geometry passing is not aesthetic approval: inspect realistic
before/after pages, pathological wrapping, every continuation page, glyphs,
reading order, and photo choices before approving the exact candidate head.

## CI selection

The visual workflow selects actual changed `themes/*.html`, rather than always
rendering Navy. A shared harness/workflow change also exercises Navy for backward
compatibility; a shared rendering-engine change exercises all supported themes.
Artifacts are stored under `output/visual-regression/<theme>/` and uploaded even
on failure. Theme authors should limit their PR to their theme, independent
contract tests and documentation. The dedicated QA owner maintains this script
and workflow to avoid concurrent infrastructure edits.

## Long skill categories

Four common cases explicitly exercise long bilingual and unbroken skill labels
and values through both raw rendering and the actual production builder, with
and without a photo slot. This closes the earlier documented coverage gap.
Skill sibling overlap checks use actual text-range rectangles so harmless
multi-line inline-span bounding boxes are not mistaken for overlapping text.

## Modern Corporate design

Modern Corporate retains a restrained deep-teal identity and a compact inline
employer/role hierarchy. A left-aligned name and right-aligned target role form
its header; plain section labels and measured whitespace replace tinted blocks,
left rails, gradients and square pseudo-bullets. Dates use the body sans-serif
family, with standard round hanging bullets below each entry. The default body
size is 10pt with 14mm side gutters. Long fields wrap; print pages repeat their
vertical gutter. This is intentionally a different composition from Modern
Navy's stacked role headings and underlined sections.

The design uses the conventional hierarchy illustrated by the
[Harvard bullet resume](https://cdn-careerservices.fas.harvard.edu/wp-content/uploads/sites/161/2024/07/resume-bullets.pdf)
and [MIT CAPD master's sample](https://cdn.uconnectlabs.com/wp-content/uploads/sites/123/2025/05/MITCAPD-MastersII.pdf).
No facts are rewritten, no shared renderer changes, and no ATS acceptance claim
is made. Existing AutoFit compaction can still choose its smaller typography
profiles when needed; the theme does not silently change that global ladder.
