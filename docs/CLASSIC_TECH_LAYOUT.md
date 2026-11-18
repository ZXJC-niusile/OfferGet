# Classic Tech resume layout

Classic Tech retains a restrained slate-blue, single-column technical identity.
The redesign uses 10pt default body type with 14mm side gutters, a clear
name/contact header, ruled section titles, unboxed
employer and project rows, right-aligned dates, and plain achievement bullets.
Body text and metrics share the same sans-serif family. Skills use ordinary
label/value lines. There are no colored role badges, code chips, quotation-style
side rules, or grey employer bands.

The hierarchy follows conventional resume examples, rather than their content:

- Harvard career services, [bullet resume template](https://cdn-careerservices.fas.harvard.edu/wp-content/uploads/sites/161/2024/07/resume-bullets.pdf)
- MIT CAPD, [resume samples](https://capd.mit.edu/resources/resumes/)

No candidate facts, renderer logic, shared AutoFit profiles, or other theme
files are changed. The six existing AutoFit variables remain available. Template-scoped
CSS overrides the shared renderer's inline header, role, and skills styles where
needed; editing only the placeholder header would not affect production output.

## Verification

```bash
python -m pytest tests/test_classic_tech_layout.py -q
python scripts/qa_modern_navy_layout.py --theme classic-tech \
  --baseline-root /absolute/path/to/exact-baseline \
  --output-dir /absolute/path/to/empty-artifact-directory
```

Theme-specific pilot (`date-rail` structural mode; see [shared QA rules](RESUME_THEME_QA.md)): checks unboxed organization/project rows, right-aligned dates, absence of colored role chips, and `17fr / 83fr` grid wrapping.
