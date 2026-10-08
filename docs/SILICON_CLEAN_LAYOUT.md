# Silicon Clean resume layout

Silicon Clean uses neutral sans-serif type throughout, a centered name, target
role and contact block, and centered section labels separated by white space.
Employer/project names sit above their roles, with dates aligned to the right.
This composition is intentionally distinct from Classic Tech's left-aligned
blue header, ruled sections and inline employer/role rows.

The theme removes code chips, dotted link rules, tiny square pseudo-bullets and
justified text. Standard round hanging bullets and ordinary skill label/value
lines give wrapped content a clear reading edge. Default body type is 10pt with
14mm side gutters. The existing six AutoFit variables remain editable.

The hierarchy draws on conventional [Harvard bullet resume examples](https://cdn-careerservices.fas.harvard.edu/wp-content/uploads/sites/161/2024/07/resume-bullets.pdf)
and [MIT CAPD resume samples](https://capd.mit.edu/resources/resumes/), without
copying any candidate content. No factual content, shared renderer, AutoFit
profiles, solver, other theme or gallery path is changed. Theme-scoped CSS
addresses the shared renderer's actual inline header/entry/skills markup.

## Verification

```bash
python -m pytest tests/test_silicon_clean_layout.py -q
python scripts/qa_modern_navy_layout.py --theme silicon-clean \
  --baseline-root "$EXACT_ISOLATED_BASELINE" --output-dir output/silicon-comparison
```

Use an isolated archive of the exact baseline commit and a new output directory.
The shared harness owns sixteen fabricated before/after fixtures; contacts use
reserved `.invalid` domains. It covers long English/CJK names, contacts,
employers, roles and skill labels/values; reserved and embedded photos; compact
AutoFit; dense continuation pages; and actual production-builder output with
AutoFit and adaptive fill enabled.

Inspect the actual PDFs and every printed-page PNG in addition to passing the
geometry/text gates. Verify neutral typography, centered hierarchy, date
alignment, natural wrapping, readable type, unchanged selectable facts, loaded
images, no external resources, and repeated A4 continuation gutters. Real
production renders are required; editing the placeholder header alone would
not establish production behavior. No guaranteed ATS acceptance is claimed.
