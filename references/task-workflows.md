# OfferGet task workflows

Run from the repository root containing `cli.py`. Replace example paths with the
user's supplied paths; all shell paths below are quoted. A route is a bounded task,
not a mandatory stage in a larger funnel.

## Format/export an existing resume

Input: a JSON profile or Markdown/text resume. Optional: theme, output format,
page count, photo, language. Keep the source unchanged.

### Disclosure preflight before every export

Profile-based exports reject any visibility value other than `always` (a string or
nonempty list). They cannot infer variant selection or disclosure approval. Before
building, inspect the source and derived profile, including nested fields and aliases:

- `reference-only`: never put this evidence or its confidential text in the resume.
- `on-request`: exclude unless the user explicitly requests inclusion.
- `variant-specific`: include only for the matching variant; `always` is eligible.
- Conflicting/unclear tags or disclosure scope: ask before exporting those items.

If restricted items exist, prepare a **separate disclosure-safe profile** containing
only eligible entries and their permitted facts. Preserve the master unchanged,
list exclusions for the user, and inspect the derived profile before rendering.
Normalization keeps an unresolved source tag at the derived profile's root, so
private analysis/proposal JSON stays restricted. Only after reviewing eligibility
and excluding restricted facts, mark approved facts `always` or leave them untagged.
Do not erase visibility metadata and then render the original content. Do not use
`ats filter --tag all` as a privacy check: wildcard tags keep all items, and even a
specific tag filter is not a complete recursive disclosure validator. Anonymization
does not authorize disclosure of restricted evidence. If a safe projection cannot
be verified, stop and ask for an approved public profile.

For Markdown/text imports, inspect the parsed result for internal notes that lost
their visibility context; pre-rendered HTML also needs manual review because it has
no profile tags to check. `--no-photo` excludes profile photos and reserved photo
slots. The build input below means the inspected, disclosure-safe resume profile.

```bash
python cli.py resume build "/path/to/public-profile.json" --theme classic-tech --no-photo --pages auto --output-dir "/path/to/output"
```

The same build command accepts `.md` and `.txt`. Inspect parsed facts before a
submission-ready export: parsing is heuristic and may miss headings or dates.
If a reusable JSON profile is needed, create a separate file:

```bash
python cli.py profile parse "/path/to/resume.md" --output "/path/to/output/profile.json"
```

Use `modern-navy` for the navy-accented layout, `ats-plain` for a plain-text companion,
`ats-docx` for Word, or the academic formats on request. `--theme all` is deliberately
opt-in at the skill level because the CLI's default builds every format. Use
`--pages 1` only for an explicit single-page requirement. If it cannot fit readably,
report the failure rather than trimming achievements or claiming success.

Output: the requested HTML/PDF, Markdown, or DOCX files and a brief check summary.
No JD or content-rewrite approval is needed for faithful formatting. Existing
claims remain the user's claims; formatting does not verify their truth.

## Create a first resume

Input: the user's real contact/education/experience/skills information, even if
incomplete. First distinguish an actual application resume from a synthetic layout
test. Ask for missing required identity or source facts; omit optional sections
rather than inventing content. Lack of numerical impact is not itself a blocker.

Prepare a source draft for review. Use specific, honest qualitative descriptions
when a result was not measured. Ask the user to approve substantive proposed wording
before applying it. Parse a reviewed Markdown draft or use the existing JSON schema;
then follow the format/export route. Do not silently copy achievements, employers,
or contact information from `examples/`.

Output: a reviewed source draft, separate rendered files, and any unresolved facts.
A draft with placeholders must be labeled as a draft, never submission-ready.

## Tailor to a job description

Input: an existing source profile and target JD. For a Markdown/text source, first
parse into a separate JSON file and inspect it; `proposal accept` currently expects
JSON. Keep the same inspected JSON and JD through review and acceptance.

```bash
python cli.py review "/path/to/jd.txt" --profile "/path/to/profile.json" --proposal-db "/path/to/output/proposals.db" --output "/path/to/output/review.json" --json
python cli.py proposal list --status draft --db "/path/to/output/proposals.db" --json
python cli.py proposal show "MP-RETURNED-ID" --db "/path/to/output/proposals.db" --json
```

Show the proposed changes and their source evidence to the user. Ask for approval
of the proposal or selected patch indexes. The command below is an **approval
boundary**, not the next automatic step:

```bash
python cli.py proposal accept "MP-RETURNED-ID" --db "/path/to/output/proposals.db" --profile "/path/to/profile.json" --jd "/path/to/jd.txt" --output "/path/to/output/tailored.json" --patch-ids "0,2" --json
```

Use the actual ID and approved indexes; omit `--patch-ids` only if all patches are
approved. If the source/JD fingerprint conflicts, generate and review a fresh
proposal rather than bypassing the conflict. Use the returned profile output path
for the following commands, including any shadow/fallback path. Before rendering,
repeat the disclosure preflight above on the tailored profile; an approved content
patch does not authorize publishing reference-only evidence. The build command below
assumes the tailored file is already verified disclosure-safe:

```bash
python cli.py diff audit "/path/to/profile.json" "/path/to/output/tailored.json" --output-dir "/path/to/output/diff"
python cli.py resume build "/path/to/output/tailored.json" --theme classic-tech --no-photo --output-dir "/path/to/output/resume"
```

Output: draft review, approved derived profile, diff ledger, requested render files.
Never treat a skill gap as a verified skill or promote a role without source evidence.

## Audit without rewriting

Run only the requested audit. These rule-based checks flag problems; they do not
prove real-world truth or guarantee a particular employer's ATS result.

```bash
python cli.py ats audit "/path/to/profile.json" --json
python cli.py fact verify "Exact claim to inspect" --profile "/path/to/profile.json" --json
python cli.py resume audit --claims "/path/to/claims.json" --html "/path/to/resume.html"
```

Add `--jd "/path/to/jd.txt"` to ATS audit only if a target JD was supplied. Return
findings with evidence paths and uncertainty. Do not apply edits without approval.

## Other supported tasks

These are optional destinations, never prerequisites for resume formatting:

- Interview preparation: `python cli.py defense simulate --help`, or `review` with
  supplied answers. Ask the user for their own answers; do not fabricate experience.
- Academic materials: `python cli.py baoyan --help`. Preserve simulation vs. physical
  experiments, submitted vs. accepted papers, and personal contribution boundaries.
- Offer analysis: `python cli.py offer --help`. Explain assumptions and uncertainty;
  provide preparation support, not legal advice or automatic negotiation outreach.
- Reversible anonymization: `python cli.py anon --help`. Inspect the masked artifact;
  keep the reverse map private and never claim masking alone authorizes publication.

## Failure and verification

- Missing input: ask for the exact file/facts needed for this route; do not demand a
  JD for formatting or a photo when the user wants none.
- Missing renderer: run `python cli.py doctor`; report the available HTML/source and
  the unchecked PDF stage. Do not call a failed build a finished PDF.
- Layout: inspect rendered pages at normal reading size, including first/last lines,
  long contact links, section breaks, and multilingual text. Use a representative
  long fixture when changing theme code.
- Content: compare source/approved output and retain all factual anchors. An audit
  pass does not replace human review of source truth.
- Editing the project itself: run relevant pytest cases and the aggregate checks
  described in README. Report actual counts/results, not historical badge counts.
