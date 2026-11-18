# OfferGet task workflows

Run commands from the repository root containing `cli.py`. Replace placeholder paths
with the user's paths and quote paths containing spaces. Each route is independent; do
not force unrelated stages.

## 1. Organize materials

Input: raw notes, old resumes (`.md`, `.txt`, `.docx`, `.html`, `.pdf`, `.json`),
BibTeX citations (`.bib`), or supporting design/postmortem notes. Keep source files unchanged.

```bash
python cli.py profile parse "/path/to/resume.md" --output "/path/to/output/profile.json"
# After reviewing parsed sections, warnings, and unclassified lines against sources:
python cli.py profile parse "/path/to/output/profile.json" --confirm-parsed --output "/path/to/output/reviewed-profile.json"
```

- `--confirm-parsed` records that you inspected the parse report; it is not external fact verification.
- Supporting project notes, postmortems, or private design docs can be searched locally without exposing them to public exports:

```bash
python cli.py profile refs --docs "/path/to/notes" --query "architecture QPS" --json
```

- Hits from `profile refs` carry `visibility: "reference-only"`. Use them to ask targeted follow-up questions or check claims; never copy unapproved `reference-only` text directly into a public resume.
- For academic CVs, keep exact author order, candidate-name highlighting, publication status (`published`, `accepted`, `under_review`, `submitted`), and supplied `url` links intact. `.bib` files can also be parsed via `profile parse`.

## 2. Format/export an existing resume

Input: a reviewed JSON profile or `.md`/`.txt`/`.docx`/`.html`/`.pdf` resume (PDF text extraction requires `pypdf` or `PyMuPDF`). No JD is required. Keep the source unchanged.

### Disclosure preflight before every export

Profile-based exports reject any visibility value other than `always` (a string or nonempty list). They cannot infer variant selection or disclosure approval. Before building, inspect the source and derived profile, including nested fields and aliases:

- `reference-only`: never put this evidence or its confidential text in the resume.
- `on-request`: exclude unless the user explicitly requests inclusion.
- `variant-specific`: include only for the matching variant; `always` is eligible.
- Conflicting/unclear tags or disclosure scope: ask before exporting those items.

If restricted items exist, prepare a **separate disclosure-safe profile** containing only eligible entries and their permitted facts. Preserve the master unchanged, list exclusions for the user, and inspect the derived profile before rendering. Do not use `ats filter --tag all` as a privacy check: wildcard tags keep all items, and even a specific tag filter is not a complete recursive disclosure validator. Anonymization (`anon mask`) does not authorize disclosure of restricted evidence. If a safe projection cannot be verified, stop and ask for an approved public profile.

For Markdown/text imports, inspect the parsed result for internal notes that lost their visibility context; pre-rendered HTML also needs manual review because it has no profile tags to check. `--no-photo` excludes profile photos and reserved photo slots.

```bash
python cli.py resume build "/path/to/public-profile.json" --no-photo --pages auto --output-dir "/path/to/output"
```

Omitting `--theme` builds `modern-navy`. Use `--theme all` only when comparing themes, `--theme ats-docx` for Word, or `academic-postgraduate` / `academic-latex` / `academic-typst` for academic CVs. Use `--pages 1` only for an explicit single-page requirement; if it cannot fit readably, report the failure rather than trimming achievements.

## 3. Full workflow: tailor to a job description

Input: a reviewed source profile and target JD (plain text or JD screenshot). If a screenshot is partially cut off or unreadable, ask the user to confirm the unclear requirements before tailoring.

1. **Analyze & identify gaps**: Read the JD directly to identify core requirements, hard gates, and genuine skill gaps. Optionally run `python cli.py ats audit "/path/to/profile.json" --jd "/path/to/jd.txt" --json` or `python cli.py ats ledger "/path/to/profile.json" --jd "/path/to/jd.txt" --json` for keyword coverage. Never treat an absent JD keyword as candidate experience.
2. **Present proposed edits & clarify missing facts**: Draft evidence-grounded suggestions using [sentence patterns](sentence-patterns.md), [anti-AI-slop](anti-ai-slop.md), [evidence rules](evidence-rules.md), and [inflation patterns](inflation-patterns.md). Show exact before/after changes and ask up to three targeted questions for missing scope or baselines.
3. **Wait for user confirmation**: **Trade-off note**: OfferGet uses conversational confirmation rather than a code-enforced proposal database, so never modify the master profile or overwrite the source file. Only after explicit user confirmation, save the revised content to a separate derived profile (e.g. `/path/to/output/tailored.json`).
4. **Verify facts, diff, and disclosure**: Before rendering, run deterministic checks and repeat the disclosure preflight above on the revised profile:

```bash
python cli.py fact verify "/path/to/output/tailored.json" --profile "/path/to/profile.json" --json
python cli.py diff audit "/path/to/profile.json" "/path/to/output/tailored.json" --output-dir "/path/to/output/diff"
python cli.py resume build "/path/to/output/tailored.json" --no-photo --baseline "/path/to/profile.json" --output-dir "/path/to/output/resume"
```

## Standalone checks & privacy helpers

For audit-only requests, run only the requested deterministic checks without rewriting content:

```bash
python cli.py ats audit "/path/to/profile.json" --json
python cli.py fact verify "Exact claim to inspect" --profile "/path/to/profile.json" --json
python cli.py resume audit --claims "/path/to/claims.json" --html "/path/to/resume.html" --source "/path/to/profile.json"
python cli.py anon mask "/path/to/profile.json" --level strict --map "/path/to/private/deanon.json" --output "/path/to/output/masked.json"
```

If the user explicitly requests interview practice after completing the resume, ask questions grounded directly in the projects, responsibilities, and outcomes in the final resume without fabricating experience.

## Failure and verification

- **Missing input**: ask for the missing file/facts needed for the active route; do not demand a JD for formatting or a photo when none is requested.
- **Missing renderer**: run `python cli.py doctor`; report the available HTML/source draft and the unchecked PDF stage honestly.
- **Layout check**: inspect rendered pages at normal reading size for clipping, overlaps, missing glyphs, long links, and page breaks.
- **Content check**: compare rendered text with the approved baseline; an audit score pass never replaces human review of factual truth.
