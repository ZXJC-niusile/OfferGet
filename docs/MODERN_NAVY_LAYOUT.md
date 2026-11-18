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

Run the shared HTML QA runner (defaults to `--theme modern-navy`; see [shared QA rules](RESUME_THEME_QA.md)):

```bash
BASE_SHA="<full comparison commit SHA>"
BASE_DIR="$(mktemp -d)"
git archive "$BASE_SHA" | tar -x -C "$BASE_DIR"
printf '%s\n' "$BASE_SHA" > "$BASE_DIR/revision.txt"
python -m pytest tests/test_modern_navy_layout.py -q
python scripts/qa_modern_navy_layout.py \
  --baseline-root "$BASE_DIR" \
  --output-dir output/visual-regression
```

Theme-specific gates (`label-gutter` structural pilot, 26 cases): checks Modern Navy `13.333px` (`10pt`) body type with `14mm` side margins, `10.6px` AutoFit font floor, unwrapped skill-category overrides, plain stacked organization/role headings, and independent source-ledger field ordering.
