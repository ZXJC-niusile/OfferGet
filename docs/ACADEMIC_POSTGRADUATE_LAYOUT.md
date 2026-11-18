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

```sh
python -m pytest tests/test_academic_postgraduate_layout.py -q
python scripts/qa_modern_navy_layout.py --theme academic-postgraduate \
  --baseline-root /absolute/path/to/exact-baseline \
  --output-dir /absolute/path/to/empty-artifact-directory
```

Theme-specific checks (see [shared QA rules](RESUME_THEME_QA.md)): expands the shared matrix with exam target/score fixtures (`30` total cases), verifying Song serif headings, single-column exam tables, and selectable score cells across real `ResumeBuilder` and raw paths.
