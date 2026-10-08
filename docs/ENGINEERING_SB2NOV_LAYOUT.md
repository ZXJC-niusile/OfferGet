# Engineering sb2nov layout

A conventional single-column engineering resume with a LaTeX-like identity:
Times-style serif text, local CJK serif fallbacks, a centered name and contact
block, black section rules, bold organizations, italic roles/dates, and compact
hanging bullets. It uses no decorative cards, accent-color badges, or remote
fonts. Missing-fact warnings remain visible.

## Production behavior

The shared HTML renderer replaces the static header and supplies inline defaults
for many entries. Theme-local rules therefore override the generated header's
alignment, role/accent colors, font sizes, education grid, and long skill labels.
The optional photo, every supplied fact, section order, shared renderer, and six
AutoFit controls remain unchanged. Optional entrance-exam data stays visible in
monochrome cells rather than inheriting the academic theme's cell colors.

The default body is 10 pt with disciplined line spacing. Print gutters repeat
on every A4 page. Long contact links, organization/project names, dates, and
skill categories wrap without ellipsis or hidden overflow. Use automatic page
selection rather than removing content to force a one-page resume.

## Verification

```sh
python -m pytest tests/test_engineering_sb2nov_layout.py tests/test_resume_theme_qa.py -q
python -m pytest tests -q
python cli.py selftest
python scripts/qa_modern_navy_layout.py --theme engineering-sb2nov \
  --baseline-root /absolute/path/to/exact-baseline \
  --output-dir /absolute/path/to/empty-artifact-directory
```

The common sixteen-case matrix includes ordinary and stress CJK/English input,
no/reserved/embedded photos, long skill labels/values, raw and compact layouts,
dense solver layouts, and actual `ResumeBuilder` output with AutoFit and adaptive
fill enabled. Browser-independent markup contracts are not a PDF or visual pass.

Before merging, inspect all before/after PDF pages and actual production
screenshots for serif glyph coverage, centered-header/photo alignment, hanging
bullets, date placement, clipping, overlaps, and page breaks. Check selectable
text and exact head/base revisions. If local browser execution is restricted,
record that limitation and inspect the exact-head CI artifacts instead.
