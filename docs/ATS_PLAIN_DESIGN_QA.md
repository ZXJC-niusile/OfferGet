# ATS Plain design and QA

## Scope

`AtsPlainRenderer` provides the plain HTML/Markdown resume view. It uses the
shared view model, photo resolver, and output security checks. The theme formats
source facts; it must not invent, shorten, or rewrite achievements.

The updated HTML uses a semantic `main`, header, section headings, and entry
headings. Black text, 10.5pt body type, a 1.48 line height, and restrained rules
replace cramped justified text. Education facts follow one linear sequence;
entry dates occupy a separate line. Natural wrapping covers contacts, dates,
organizations, education, exam fields, and skill labels. Print pages retain
15mm top/bottom and 16mm side margins; screen padding responds to narrow widths.
There are no decorative cards, sidebars, tables, gradients, or hidden keywords.

The layout does not guarantee acceptance by every ATS. Check supported source
fields against the current renderer and inspect the exported text. Markdown
parity alone does not establish factual completeness.

## Reproducible checks

    python -m pytest tests/test_ats_plain_design.py -v
    python scripts/qa_ats_plain_layout.py \
      --baseline-root /absolute/path/to/exact-baseline \
      --output /absolute/path/to/new-output-directory

Format-specific gates (see [shared QA rules](RESUME_THEME_QA.md) and [photo modes](RESUME_PHOTO_MODES.md)): runs 11 baseline-vs-current pairs (335 source anchors) through `ResumeBuilder.build_ats_plain`, checking exact Markdown byte parity, desktop (`1000px`), mobile (`375px`), and print (`673px`) geometry, `14px` body font floor, and no inline photo `onerror` handlers. `--source-only` runs source/Markdown checks only (`visualVerified: false`).
