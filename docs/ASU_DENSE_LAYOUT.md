# ASu Dense: compact professional resume

ASu Dense retains a compact single-column technical layout. White paper, a dark
slate heading color, fine section rules and ordinary bullets replace the ivory
background, tinted organization cards, terracotta squares and boxed code tokens.
Organization, role and date form a clear text hierarchy. The name and target role
are stacked so a long title cannot squeeze the candidate's name.

The theme changes presentation only. It retains the shared renderer's factual
content, section sequence, real/reserved/no-photo options, local font fallbacks,
A4 dimensions, and all six AutoFit tokens. Dates use tabular figures and align to
the right when room permits. Long bilingual labels, identifiers, contacts and
education metadata can wrap without hiding or shortening text.

## Production-aware implementation

`HtmlThemeRenderer` replaces the header and supplies inline styles throughout the
resume. Every necessary override is scoped to `body.resume-dense`, including the
stacked header, normal-flow skills labels, plain organization rows and compact
spacing. The shared renderer, layout solver and AutoFit engine are untouched.
Print margins repeat the vertical gutter on continuation pages. Entry headings
stay with the following content; long lists may continue on another page rather
than forcing an entire entry into one unbreakable block.

## Validation

```bash
python -m pytest tests/test_asu_dense_layout.py -q
python scripts/qa_modern_navy_layout.py --theme asu-dense \
  --baseline-root /absolute/path/to/exact-baseline \
  --output-dir /absolute/path/to/empty-artifact-directory
```

Runs the shared HTML visual harness (see [shared QA rules](RESUME_THEME_QA.md)), checking `body.resume-dense` overrides, tabular right-aligned dates, and long-entry continuation breaks.
