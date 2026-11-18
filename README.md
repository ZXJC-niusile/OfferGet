# OfferGet

**English** | [简体中文](README.zh-CN.md)

An evidence-grounded resume-building Skill ([`SKILL.md`](SKILL.md)) and deterministic local Python CLI toolchain for organizing career materials, verifying facts and privacy boundaries, and rendering publication-grade resumes and academic CVs. All CLI operations run locally without uploading user materials or calling paid model APIs.

## Install

Requires Python 3.9+. PDF rendering also needs Chrome, Edge, or Chromium.

```bash
git clone https://github.com/ZXJC-niusile/OfferGet.git
cd OfferGet
pip install -e ".[render]"
python cli.py doctor
```

- For Word (`.docx`) export and input parsing, also install `.[docs]` (or `pip install -e ".[all]"` for full development and test dependencies).
- Native academic compilation uses `xelatex` (`academic-latex`) or the `typst` Python package / CLI (`academic-typst`), falling back to the shared academic HTML/browser renderer when native compilers are unavailable.
- Run commands from the repository root and quote paths containing spaces.

## Choose a workflow

| Workflow | Start with | Result |
| --- | --- | --- |
| [A. Organize materials](#a-organize-materials) | Notes, an old resume, BibTeX entries, or supporting docs | A reviewed, reusable JSON profile |
| [B. Build from existing materials](#b-build-from-existing-materials) | A prepared `.md`, `.txt`, `.docx`, `.html`, `.pdf`, or `.json` file | Rendered resume files (PDF / HTML / DOCX / TeX / Typst) |
| [C. Complete tailoring workflow](#c-complete-tailoring-workflow) | Your reviewed profile and a target JD (text or screenshot) | Confirmed edits, verified diff & fact report, and rendered resume |

Use only the route you need—formatting an existing resume does not require a job description, and standalone audit commands (`ats audit`, `fact verify`, `diff audit`, `resume audit`) can be run directly on demand. Commands below use synthetic examples; replace their paths with your own files.

## A. Organize materials

1. Collect education, work and project history, personal responsibilities, quantified outcomes, skills, and publications in a Markdown draft or structured JSON profile. For academic CVs, preserve exact author order, candidate-name highlighting, publication status (`published`, `accepted`, `under_review`, `submitted`), and paper links.
2. Parse existing `.md`, `.txt`, `.docx`, `.html`, `.pdf` (via `pypdf`/`PyMuPDF`), or `.bib` files into a separate JSON profile without modifying source files:

```bash
python cli.py profile parse examples/sample_resume.md --output output/profile.json
```

3. Inspect the recognized sections, warnings, and unclassified source lines. Correct the JSON against your sources, then record your review:

```bash
python cli.py profile parse output/profile.json --confirm-parsed --output output/reviewed-profile.json
```

4. Keep private project notes, design docs, or postmortems separate and query them as `reference-only` context when recalling details:

```bash
python cli.py profile refs --docs notes/ --query "distributed cache latency" --limit 5 --json
```

`--confirm-parsed` records your review of the parser output; it is not independent fact verification. Profile entries support visibility tags (`always`, `variant-specific`, `on-request`, and `reference-only`). Public exports require a disclosure-safe profile (`always` only) and reject unresolved visibility tags. See the [minimal profile example](examples/candidate_profile_minimal.json) and [full profile example](examples/candidate_profile.json).

## B. Build from existing materials

Use a prepared `.md`, `.txt`, `.docx`, `.html`, `.pdf`, or `.json` file. For imported text, verify that rule-based parsing preserved your facts before sharing the result.

```bash
# Default modern-navy theme (CLI defaults to --no-photo and --pages auto)
python cli.py resume build examples/sample_resume.md --output-dir output/resume

# A reviewed JSON profile with a specific theme and single-page budget
python cli.py resume build output/reviewed-profile.json --theme classic-tech --pages 1 --output-dir output/resume
```

Open the returned files and inspect text, links, page breaks, clipping, and photo placement. Without `--output-dir`, output defaults to the desktop folder named `个人简历`.

| Option | Purpose |
| --- | --- |
| `--pages auto` | Default page handling |
| `--pages 1` or `--pages 2` | Explicit PDF page budget; runs single-page AutoFit when applicable and fails if exceeded |
| `--no-photo` / `--photo-mode no-photo` | Default CLI behavior; excludes photos and reserved photo slots |
| `--photo-path "photo.jpg"` | Validate and embed a local raster photo (`PNG`, `JPEG`, `WebP`, `GIF`) |
| `--photo-mode placeholder` | Reserve a 3:4 portrait slot for layout preview only |
| `--theme ats-docx` | Export Word (`.docx`); requires `--pages auto` |
| `--theme all` | Build all 13 PDF themes for visual comparison; Word is exported separately |
| `--anonymize strict` | Produce an anonymized export (omits diff-ledger sidecars and real-name filename copies) |

## C. Complete tailoring workflow

1. **Review source & target JD**: Load your reviewed profile alongside the target JD text or screenshot (clarify any cut-off or ambiguous screenshot requirements first). Optionally inspect ATS readiness and keyword coverage:

```bash
python cli.py ats audit output/reviewed-profile.json --jd examples/sample_ai_jd.txt --json
python cli.py ats ledger output/reviewed-profile.json --jd examples/sample_ai_jd.txt --json
```

2. **Propose edits & confirm in conversation**: Present exact before/after wording and evidence gaps to the user first. Save approved edits only to a **separate derived file** (`output/tailored.json`), keeping the master profile untouched.
3. **Verify facts, diff, and disclosure before rendering**:

```bash
python cli.py fact verify output/tailored.json --profile output/reviewed-profile.json --json
python cli.py diff audit output/reviewed-profile.json output/tailored.json --output-dir output/diff
python cli.py resume build output/tailored.json --no-photo --baseline output/reviewed-profile.json --output-dir output/resume
```

Conversational confirmation replaces a stateful approval database, so keeping the unmodified master profile, running disclosure preflight, verifying metrics and arithmetic consistency via `fact verify` + `diff audit`, and visually inspecting final pages remain mandatory safeguards.

## Templates — under active refinement

**Templates are under active refinement.** Typography, spacing, pagination, and cross-theme consistency are continuously being tuned. Always inspect the rendered files before submitting an application.

There are 14 themes, selected with `--theme`:

| Theme | Format / style |
| --- | --- |
| `modern-navy` (default) | HTML/PDF, navy label-gutter layout |
| `classic-tech` | HTML/PDF, black-and-white date-rail layout |
| `asu-dense` | HTML/PDF, compact high-density layout |
| `modern-corporate` | HTML/PDF, restrained deep-teal corporate layout |
| `modern-career` | HTML/PDF, general career layout |
| `academic-postgraduate` | HTML/PDF, Chinese academic / postgraduate CV |
| `engineering-sb2nov` | HTML/PDF, single-column engineering CV |
| `executive-mckinsey` | HTML/PDF, consulting layout |
| `awesome-cv` | HTML/PDF, red-accent layout |
| `wall-street-classic` | HTML/PDF, compact serif finance layout |
| `ats-plain` | Markdown/HTML/PDF, single-column ATS plain layout |
| `academic-latex` | Native XeLaTeX (`.tex`) + standalone academic HTML + PDF |
| `academic-typst` | Native Typst (`.typ`) + PDF (with academic HTML fallback) |
| `ats-docx` | Native Word (`.docx`) |

See [theme & format QA](docs/RESUME_THEME_QA.md), [academic LaTeX QA](docs/ACADEMIC_LATEX_LAYOUT.md), [academic Typst QA](docs/ACADEMIC_TYPST_LAYOUT.md), [ATS plain QA](docs/ATS_PLAIN_DESIGN_QA.md), [ATS DOCX QA](docs/ATS_DOCX_LAYOUT.md), and [photo modes](docs/RESUME_PHOTO_MODES.md).

## Commands, QA harnesses, and development

Available CLI commands:
- `profile`: `parse`, `refs`
- `resume`: `build`, `render`, `autofit`, `audit`
- `ats`: `audit`, `ledger`, `filter`
- `fact`: `verify`
- `diff`: `audit`
- `anon`: `mask`, `unmask`
- `doctor`, `selftest`

Run `python cli.py <command> --help` for full options.

```bash
pip install -e ".[all]"

# Fast unit & contract test suite
python -m pytest tests -m "not browser and not package" --strict-markers

# Browser rendering & isolated wheel-packaging regression suite
python -m pytest tests -m "browser or package" --strict-markers

# Skill static contract validation & deterministic CLI smoke evaluation
python scripts/eval_offerget_skill.py validate
python scripts/eval_offerget_skill.py smoke

# Format-specific visual & geometry QA harnesses (require local compilers/Chromium)
python scripts/qa_academic_layout.py --format latex --output artifacts/academic-latex
python scripts/qa_academic_layout.py --format typst --output artifacts/academic-typst
python scripts/qa_ats_plain_layout.py --output-dir artifacts/ats-plain
python scripts/qa_ats_docx_layout.py --output artifacts/ats-docx
```

[Examples](examples/) · [Architecture](docs/ARCHITECTURE.md) · [Release Verification](docs/RELEASE_VERIFICATION.md) · [Skill Evaluation](docs/SKILL_EVALUATION.md) · [Agent Instructions](SKILL.md) · [License: CC BY-NC-SA 4.0](LICENSE)
