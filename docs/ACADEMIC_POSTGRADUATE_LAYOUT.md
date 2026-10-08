# Academic postgraduate layout

The academic theme remains a Chinese postgraduate-application resume, with
Song-style serif headings, a centered name/application line, a restrained burgundy
accent, and a compact entrance-exam score table. It uses a single-column reading
order, plain education metadata, conventional hanging bullets, and right-aligned
dates. It does not add publication sections or change the shared content model.

## Production behavior

`HtmlThemeRenderer` replaces the static header and emits inline presentation
styles for most sections. Theme-local overrides therefore cover generated header,
organization, project, skills, education, and exam markup. They leave data,
section order, optional photos, and the shared renderer untouched.

All six AutoFit variables remain available. The default body is 10 pt; A4 print
margins repeat above and below every page. Long contact links, research-group
names, application targets, and exam subject names wrap rather than disappear.
Exam scores remain selectable text, without colored cells or decorative panels.
Missing-fact markers retain their visible warning treatment.

## Verification

Browser-independent checks:

```sh
python -m pytest tests/test_academic_postgraduate_layout.py tests/test_resume_view_model.py tests/test_resume_builder.py -q
python -m pytest tests -q
python cli.py selftest
```

The shared visual-regression runner accepts the academic theme:

```sh
python scripts/qa_modern_navy_layout.py --theme academic-postgraduate \
  --baseline-root /absolute/path/to/exact-baseline \
  --output-dir /absolute/path/to/empty-artifact-directory
```

Use synthetic ordinary-length and stress CJK/English profiles, including real
exam targets and score-table values; inspect all before/after PDF pages at normal
reading size. Verify the actual `ResumeBuilder` path with AutoFit and adaptive
fill enabled, alongside raw/compact/solver cases and no/reserved/embedded photos.
Record the exact baseline and head revisions, page count, text preservation,
clipping/overlap measurements, and screenshots/PDFs. A unit-test pass or static
HTML inspection is not a visual pass. If Chromium is unavailable, leave visual
acceptance pending and inspect the exact-head CI artifacts instead.
