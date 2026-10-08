# Sidebar Clean: a restrained two-column resume

Sidebar Clean keeps education and skills in a narrow left column, with experience
and projects in the wider main column. White paper, dark teal headings, fine
section rules and ordinary bullets replace tinted rounded cards, triangle bullets,
dashed entry rules and saturated blue accents. Names and target roles stack above
both columns. Main-column organizations and roles have separate levels, with dates
in a small right-hand column; sidebar education reads naturally from top to bottom.

The layout changes only this theme. The shared renderer, AutoFit engine and layout
solver stay unchanged. Theme-scoped overrides handle their actual generated inline
styles, including nowrap skill labels, flex headers and education grids. Long
multilingual content wraps without clipping or shortening it. All six AutoFit
controls, A4 dimensions and photo modes remain available. Print gutters repeat on
continuation pages.

## Column and reading order

The source remains header, optional exam section, education, experience, projects
and skills, without
cloning facts or visually hiding text. Explicit grid tracks keep skills directly
below education and projects after experience; they avoid the original automatic
row stretching and dense grid placement. If experience is absent, projects start
at the top of the main column. Very long sidebar content may push later main-column
content down. This is checked using the stress fixtures rather than fixed heights
or absolute positioning that could overlap or lose content. The optional exam
section has its own full-width row above the columns, including a fixed-layout
score table with wrapping subject labels. Printed output uses ordinary grid rows
without experience row-spans: Chromium can overlap later content when a spanning
item fragments. This retains two columns but places printed skills alongside the
projects row. Screen layout keeps skills directly below education.

A two-column visual presentation needs an explicit PDF reading-order review. Do
not claim generic ATS compatibility from a clean screenshot. Inspect the actual
production PDF's selectable text for intact heading/organization/role/date/bullet
groups and factual order, including across every continuation page.

## Verification

```bash
python -m pytest tests/test_sidebar_clean_layout.py -q
python scripts/qa_modern_navy_layout.py --theme sidebar-clean \
  --baseline-root /path/to/exact-isolated-base \
  --output-dir output/sidebar-clean-comparison
```

The shared 20-pair Sidebar matrix includes realistic production resumes, short/long raw
resumes, extreme unbroken identifiers, long bilingual skill labels and values,
compact AutoFit settings, multi-page dense content, four normal/long exam-table
production cases and all photo modes. Inputs
are fabricated QA data with `.invalid` contacts; no private resumes or paid API
calls are used. Before/after HTML, screen PNG, every printed-page PNG, selectable
PDF, renderer traces and `report.json` must be retained and inspected.

Source tests check all fixture facts, unchanged semantic DOM order, optional
sections, scoped renderer overrides and every AutoFit profile. Local Chromium
cannot start because its socket operation is restricted, so local tests alone do
not establish a valid PDF. Exact-head CI, production pixels, reading order and
remaining limitations are recorded in the pull request before approval. Sidebar QA
also compares actual PDF text-line bounding boxes, catching substantial overlaps
that a non-fragmented print-media DOM can miss. It ignores tiny font overhangs;
manual page and reading-order inspection remains required.
