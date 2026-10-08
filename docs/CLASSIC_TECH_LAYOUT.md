# Classic Tech resume layout

Classic Tech retains a restrained slate-blue, single-column technical identity.
The redesign uses a clear name/contact header, ruled section titles, unboxed
employer and project rows, right-aligned dates, and plain achievement bullets.
Body text and metrics share the same sans-serif family. Skills use ordinary
label/value lines. There are no colored role badges, code chips, quotation-style
side rules, or grey employer bands.

The hierarchy follows conventional resume examples, rather than their content:

- Harvard career services, [bullet resume template](https://cdn-careerservices.fas.harvard.edu/wp-content/uploads/sites/161/2024/07/resume-bullets.pdf)
- MIT CAPD, [resume samples](https://capd.mit.edu/resources/resumes/)

No candidate facts, renderer logic, AutoFit settings, or other theme files are
changed. The six existing AutoFit variables remain available. Template-scoped
CSS overrides the shared renderer's inline header, role, and skills styles where
needed; editing only the placeholder header would not affect production output.

## Verification

Run browser-independent contracts with:

```bash
python -m pytest tests/test_classic_tech_layout.py -q
```

Use the repository's shared visual QA against an isolated archive of the exact
comparison revision, selecting `classic-tech`. It renders synthetic, reserved
`.invalid` fixtures only. Coverage must include ordinary and long bilingual text,
long unbroken contacts and employer names, optional/embedded photo, dense pages,
compact AutoFit, and the real production-builder path with AutoFit and adaptive
fill enabled. Inspect both before/after PNGs and every page of the actual PDFs.

Acceptance requires unchanged factual text, valid A4 PDFs, readable type,
non-overlapping contacts and dates, safe long-string wrapping, correct embedded
images, no network resources, and repeated continuation-page gutters. Geometry
checks do not replace visual review of typography, hierarchy, and page breaks.
