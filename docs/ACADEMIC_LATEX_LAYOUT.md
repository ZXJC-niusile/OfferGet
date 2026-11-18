# Academic LaTeX resume

The academic export uses a conventional serif A4 resume with 18 mm margins,
10.5 pt body type, aligned dates, hanging bullets, and section headings without
colored boxes or heavy rules. Long uninterrupted tokens receive safe line-break
opportunities; entries remain free to paginate rather than losing facts.

Native XeLaTeX uses TeX Gyre Termes (or Latin Modern Roman) and tries Noto Serif
CJK SC, Source Han Serif SC, SimSun, then the TeX Live Fandol family. The default
therefore does not depend on a proprietary Windows font being installed.

The standalone HTML/browser fallback uses the same source fields and a similar
serif hierarchy. It remains a separate rendering path. It now includes publication
authors, venue and year, and decodes HTML-projected education/exam values only once.
This shared academic fallback is also used when native Typst is unavailable;
the native Typst generator is unchanged in this PR.

## Validation

    python -m pytest tests/test_academic_latex_design.py -v
    python scripts/qa_academic_layout.py --format latex --output artifacts/academic-latex

Format-specific gates (in addition to [shared QA rules](RESUME_THEME_QA.md)): requires `xelatex` with `xeCJK`, Noto CJK fonts, `PyMuPDF`, and Playwright Chromium. Compiles six synthetic cases natively (`-no-shell-escape -halt-on-error`) and via HTML fallback separately, plus traced native and forced-fallback `ResumeBuilder` paths. Native missing glyphs, Overfull hboxes, or photo filenames with braces/percent signs/line breaks fail. Inspect both mode PDFs and page PNGs before approval.
