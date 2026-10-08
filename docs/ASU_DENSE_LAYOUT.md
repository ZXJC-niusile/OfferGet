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

Run the theme contracts with:

```bash
python -m pytest tests/test_asu_dense_layout.py -q
```

The contracts use the shared, explicitly synthetic multilingual fixtures and
check unchanged body text, security validation, each photo mode, scoped overrides,
and all five existing AutoFit profiles. They are not visual approval.

The shared visual workflow must render this theme against the exact PR base with
its real Chromium production builder, AutoFit and layout solver. Review the
paired HTML, full-page screen PNG, every printed-page PNG, selectable-text PDF,
renderer trace and `report.json`. Include both realistic medium-length production
resumes and the long-string/multipage stress cases. Check clipping, overlaps,
readable glyphs, dates, section breaks, repeated gutters and retained factual text.
The local container cannot launch Chromium because its socket operation is
restricted, so local source checks do not establish a successful PDF export.
Final visual and exact-head CI results are recorded in the pull request.
