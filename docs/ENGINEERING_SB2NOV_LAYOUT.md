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
python scripts/qa_modern_navy_layout.py --theme engineering-sb2nov \
  --baseline-root /absolute/path/to/exact-baseline \
  --output-dir /absolute/path/to/empty-artifact-directory
```

Checks serif fallback (`Noto Serif CJK SC`), centered header alignment, italic roles/dates, and monochrome exam score cells via the [shared QA harness](RESUME_THEME_QA.md).
