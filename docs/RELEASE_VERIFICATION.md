# Release verification

This is a procedure, not a current release certification. Earlier revisions of
this file contained an undated RC report with no pinned commit. Its test counts,
package sizes, pass-rate claims and Windows timings are historical notes, not
proof for the current tree. The former `ApexResume/tests` path is no longer a
separate test suite; current regression tests live in `tests/`.

## Source and installed-package checks

From a clean checkout, record the commit (`git rev-parse HEAD`), date, operating
system, Python version and installed dependencies alongside the commands and
logs. Provision the build tools before running the wheel-install regression:

```sh
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[all]"
python cli.py doctor
python -m pytest tests/ -ra
```

- `doctor` checks the environment and installed resources. A missing optional
  browser can produce exit code 1; browser discovery does not prove rendering.
- `python cli.py selftest` is an optional quick smoke check, already exercised
  by the pytest suite. It does not run the developer suite or produce a real
  PDF, and explicitly reports rendering as `NOT RUN`.
- `pytest` is the developer regression suite. Report passes, failures, skips and
  deselections separately. A constrained or filtered run is not a full pass.

The suite already includes direct smoke checks and
[`tests/test_packaged_diagnostics.py`](../tests/test_packaged_diagnostics.py).
For focused packaging verification, run:

```sh
python -m pytest tests/test_packaged_diagnostics.py -ra
```

That test builds and installs a wheel with package indexes disabled, removes its
build checkout, and runs diagnostics outside the source tree while forbidding
network access and installed-resource writes. It verifies packaged fixtures and
the report template; it does not validate an sdist or rendered resume output.
For an installed package, `python -m cli doctor` and `python -m cli selftest`
work outside the checkout. Do not infer package contents from old artifact names
or sizes.

## Rendering and release evidence

Use the commands and dependency setup in the applicable workflows:
[HTML themes](../.github/workflows/resume-visual.yml),
[ATS Plain](../.github/workflows/ats-plain-layout.yml),
[DOCX](../.github/workflows/ats-docx-layout.yml),
[LaTeX](../.github/workflows/academic-latex-layout.yml) and
[Typst](../.github/workflows/academic-typst-layout.yml).
Keep the actual PDFs, page images and measurements for the exact revision, and
inspect layout, clipping, text and photo treatment. Check native compiler output
separately from any browser fallback.

Source-level, mocked-renderer and smoke checks do not establish visual
acceptance. If browser sandbox/socket restrictions or missing compiler packages
block rendering, record the exact blocker and untested formats. Do not report
those paths as passed. Benchmark timings likewise need a pinned revision,
inputs, environment and fresh measurements before supporting performance claims.
