# OfferGet

**English** | [简体中文](README.zh-CN.md)

A local toolkit for organizing career materials, building resumes, tailoring them to a job description, and practicing interviews. The core CLI uses local rules and does not require uploading your materials or calling a paid model API.

## Install

Requires Python 3.9+. PDF rendering also needs Chrome, Edge, or Chromium.

```bash
git clone https://github.com/ZXJC-niusile/OfferGet.git
cd OfferGet
pip install -e ".[render]"
python cli.py doctor
```

For Word export, also install `.[docs]`. Native LaTeX and Typst output requires the corresponding compiler. Run commands from the repository root and quote paths containing spaces.

## Choose a workflow

| Workflow | Start with | Result |
| --- | --- | --- |
| [A. Organize materials](#a-organize-materials) | Notes, an old resume, project records, or publication details | A reviewed, reusable profile |
| [B. Build from existing materials](#b-build-from-existing-materials) | A prepared Markdown, text, or JSON resume | Rendered resume files |
| [C. Complete workflow](#c-complete-workflow) | Your materials and a target job description | Reviewed changes, an exported resume, and interview practice |

Use the route you need. Formatting an existing resume does not require a job description or an interview session. Commands below use synthetic examples; replace their paths with your own files.

## A. Organize materials

1. Collect education, work and project history, personal responsibilities, results, skills, and publications in a Markdown draft. Keep each experience together with its outcomes and supporting links. For research, explain the problem, method, your contribution, and reported results; retain author order and publication status.
2. Add evidence where available: project repositories, merged PRs, papers, reports, or measurement records. Resolve conflicting dates and metrics before using them. The CLI parses supplied files; it does **not** automatically research GitHub or fill missing facts. Research and substantive rewriting require a separate review of the sources.
3. Parse the draft into a separate JSON profile:

```bash
python cli.py profile parse examples/sample_resume.md --output output/profile.json
```

Inspect the recognized sections, warnings, and unclassified source lines. Correct the JSON against your materials, then record your review:

```bash
python cli.py profile parse output/profile.json --confirm-parsed --output output/reviewed-profile.json
```

`--confirm-parsed` records your review of the parsing; it is not independent fact verification. Keep private evidence and unresolved notes in your master materials, and use a separate profile containing only approved public content for export. See the [profile example](examples/candidate_profile_minimal.json).

**Next:** use the reviewed profile in Workflow B or C. No rendering is required just to organize your materials.

## B. Build from existing materials

Use a prepared `.md`, `.txt`, or `.json` file. For imported text, check that parsing preserves your facts before sharing the result.

```bash
# One resume, using the default modern-navy theme
python cli.py resume build examples/sample_resume.md --output-dir output/resume

# A reviewed JSON profile with a different theme
python cli.py resume build output/reviewed-profile.json --theme classic-tech --output-dir output/resume
```

Open the returned files and check text, links, page breaks, clipping, and photo placement. Without `--output-dir`, output goes to the desktop folder named `个人简历`.

Useful options:

| Option | Purpose |
| --- | --- |
| `--pages auto` | Default page handling |
| `--pages 1` or `--pages 2` | Explicit PDF page budget; fails if the final PDF exceeds it |
| `--photo-path "photo.jpg"` | Include a local photo |
| `--no-photo` | Exclude photos and reserved photo slots |
| `--theme ats-docx` | Export Word; use the default `--pages auto` |
| `--theme all` | Build all 13 PDF themes for comparison; Word is separate |
| `--anonymize strict` | Produce an anonymized export; inspect it before sharing |

This route formats supplied content. It does not invent achievements or verify claims against external sources.

## C. Complete workflow

### 1. Prepare your source and target

Use the reviewed profile from Workflow A, or an existing profile you have already checked. Save the target job description as a text file.

```bash
python cli.py review examples/sample_ai_jd.txt --profile output/reviewed-profile.json --goal review --workspace output/job-review
```

The workspace links the source paths, session, answer templates, proposals, and output files. Use `--goal tailor` instead if you only want resume tailoring.

### 2. Supply missing evidence

Read the issues and proposed changes. If more information is needed, fill the answer file printed by the command and run the suggested next command. On the first round, it may look like this:

```bash
python cli.py review --workspace output/job-review --answers output/job-review/answers.json
```

Keep the template's version identifier. Later rounds may use different filenames, so use the **actual path printed for that round**. If the source profile or JD changes, first refresh without submitting old answers:

```bash
python cli.py review --workspace output/job-review
```

Unchanged JD decoding and matching are reused when continuing a session.

### 3. Review, approve, and export

Inspect the before/after edits, then run the exact `proposal accept` command printed by OfferGet when you approve them. It includes the proposal ID, source/JD paths, database, workspace, and export options. If there are no pending edits, follow the printed export command instead.

Content changes require approval. Current automatic edits include relevance ordering and removing introductory filler; new facts must come from your supplied evidence. The accepted profile becomes the input for subsequent interview work. Source updates refresh existing resume outputs in the configured directory; keep a separate copy if you need historical rendered versions.

### 4. Practice from the current resume

Continue the same workspace in interview mode:

```bash
python cli.py review --workspace output/job-review --goal interview
```

For interview practice without tailoring or a JD:

```bash
python cli.py review --profile examples/candidate_profile_minimal.json --goal interview --workspace output/interview
```

Questions cover your contribution, design choices, and evidence for results, grounded in the current resume. Fill the printed answer template and follow the next command for feedback and follow-up questions. Interview-only runs do not create material proposals or export resumes.

Use `--verbose` for details and `--json` for structured output. Match scores describe coverage of job requirements, not interview or hiring probabilities.

## Templates — still being refined

**Templates are under active refinement.** Typography, spacing, pagination, and consistency across themes are still being optimized. Inspect the rendered files before using them for an application.

There are 14 themes, selected with `--theme`:

| Theme | Format / style |
| --- | --- |
| `modern-navy` (default) | HTML/PDF, navy |
| `classic-tech` | HTML/PDF, black and white |
| `asu-dense` | HTML/PDF, compact two-column |
| `modern-corporate` | HTML/PDF, corporate |
| `modern-career` | HTML/PDF, general career |
| `academic-postgraduate` | HTML/PDF, Chinese academic |
| `engineering-sb2nov` | HTML/PDF, single-column engineering |
| `academic-latex` | LaTeX/PDF |
| `academic-typst` | Typst/PDF |
| `ats-plain` | Text/HTML/PDF |
| `executive-mckinsey` | HTML/PDF, consulting style |
| `awesome-cv` | HTML/PDF, red accents |
| `wall-street-classic` | HTML/PDF, compact serif |
| `ats-docx` | Word/DOCX |

Batch exports save separate difference and layout reports for each theme. See [template QA](docs/RESUME_THEME_QA.md) and [photo options](docs/RESUME_PHOTO_MODES.md).

## Resume after an error

Fix unreadable paths, permissions, or file locks, then retry. If answer JSON is invalid, repair it or rename it as a backup before regenerating a template. Restore a missing session or correct its path. After an interrupted approval/export, retry the original command: recovery checks preserve the accepted version and already-connected answers.

## More commands and development

Use `python cli.py --help` or a command's `--help` for JD analysis (`jd`), resume checks (`ats`), fact/difference checks (`fact`, `diff`), academic applications (`baoyan`), offers (`offer`), and application tracking (`application`).

```bash
pip install -e ".[all]"
python -m pytest tests -m "not browser and not package"
# Full suite, including real browser and isolated package checks
python -m pytest tests
```

Daily CI uses Linux/Python 3.9, Linux/Python 3.13, and Windows/Python 3.13, with separate browser/package jobs. Run CI manually with `full-matrix` enabled for both platforms across Python 3.9–3.13. Check the actual run results for validation status.

[Examples](examples/) · [Architecture](docs/ARCHITECTURE.md) · [Agent instructions](SKILL.md) · [License: CC BY-NC-SA 4.0](LICENSE)
