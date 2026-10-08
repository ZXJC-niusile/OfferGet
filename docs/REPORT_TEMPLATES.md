# Report rendering and legacy template compatibility

## Active default renderer

`generate_report()` and `ReportService.generate_offer_strategy_report()` use
`core.jd_analyst.reporter.OfferStrategyReporter` when `template_path` is omitted,
`None`, or an empty string. The renderer owns the active HTML and its evidence-aware
content. Its output is checked for bilingual parity and output security.

For compatibility, explicitly selecting the bundled `templates/offer_strategy.html`
path also selects this Python renderer. The bundled file is now a short migration
notice. It is not read when rendering the default report, so editing it does not
customize that report. The previous static mockup contained illustrative candidate
claims that were unrelated to input data and has been retired.

The path helpers `get_canonical_default_template_path()`, `resolve_report_template()`,
`is_default_template()` (and `_is_default_template`), and
`read_default_template_content()` retain their signatures and resource-resolution
behavior. The content-reading helper now returns the migration notice. This is an
intentional change for direct resource readers, not a change to generated reports.
The resource remains packaged; non-filesystem resource reads remain supported.

## Custom HTML files

Create a separate HTML file and select it explicitly:

```sh
python cli.py jd report jd.txt --profile profile.json --template custom.html --output report.html
```

A separate file named `offer_strategy.html` is also a custom template. Classification
uses the resolved path, not its basename. A symlink resolving to the bundled resource
retains the legacy default-renderer behavior. Missing explicit paths raise
`FileNotFoundError`; they do not silently fall back. Relative paths are checked against
the current directory first, then the project/package root.

Custom files support literal scalar placeholders, not Jinja syntax or dynamic loops.
Values are HTML-escaped. Missing metrics render as `N/A`; explicit zero stays zero.
Unsupported uppercase placeholders raise `ValueError`. All output receives the
security audit. The default renderer's bilingual gate is not applied to custom files;
the CLI separately reports bilingual validation results.

Supported placeholders:

- Metadata: `{{COMPANY}}`, `{{ROLE}}`, `{{ROLE_TITLE}}`, `{{LEVEL}}`, `{{LOCATION}}`,
  `{{COMP_BAND}}`, `{{DEPARTMENT}}`, `{{ARCHITECTURE_LAYER}}`
- Candidate and date: `{{CANDIDATE_NAME}}`, `{{REPORT_DATE}}`
- Supplied metrics: `{{MATCH_SCORE_NUM}}`, `{{INTERVIEW_PROB_NUM}}`,
  `{{MUST_HAVE_SCORE}}`, `{{NICE_HAVE_SCORE}}`, `{{HIDDEN_FIT_SCORE}}`
- Verdict: `{{VERDICT_TITLE_EN}}`, `{{VERDICT_TITLE_ZH}}`,
  `{{VERDICT_DESC_EN}}`, `{{VERDICT_DESC_ZH}}`
- For each layer `n` from 1 through 5: `{{Ln_JD_TEXT_EN}}`, `{{Ln_JD_TEXT_ZH}}`,
  `{{Ln_REALITY_EN}}`, `{{Ln_REALITY_ZH}}` (replace `n` with its digit)

Minimal example:

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Custom report</title></head>
<body><h1>{{COMPANY}} / {{ROLE}}</h1>
<p>Candidate: {{CANDIDATE_NAME}}</p><p>Supplied match score: {{MATCH_SCORE_NUM}}</p>
</body></html>
```

Keep static template text factual and neutral. Placeholder escaping and the security
audit do not establish that arbitrary claims written into a custom template are true.
