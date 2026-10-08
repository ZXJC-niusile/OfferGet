# Evaluating the OfferGet skill

This is a small regression suite, not an agent runtime or a claim that the skill
has passed live evaluations. All supplied resumes, contacts, employers, and
academic material are synthetic. No API key, network call, browser, or paid model
is needed for the default checks.

## Three different checks

Run from the repository root with Python 3.9 or newer:

```bash
python scripts/eval_offerget_skill.py validate
python scripts/eval_offerget_skill.py smoke
python -m unittest tests.test_skill_evals -v
# Equivalent test runner:
python -m pytest tests/test_skill_evals.py -q
```

- **validate** checks the suite schema, unique IDs, expectations, and local input
  paths. It prints a dataset fingerprint covering both suite JSON and every
  referenced fixture's path and bytes. It does not test skill activation.
- **smoke** runs three fixed CLI calls in a temporary workspace: Markdown parsing,
  draft-only review, and academic-integrity checks. It also compares input hashes.
  It copies only validated referenced fixtures and leaves repository inputs alone.
  These checks do not verify full parser accuracy, model behavior, resume layout,
  visibility filtering, or factual truth. It does not render a PDF.
- **grade** reads separately collected, normalized traces. It never executes
  recorded commands, invokes an agent, or fetches URLs. Its evidence-linked event
  annotations and qualitative judgments must come from a reviewer or a separately
  validated collector; they are not inferred from prompt keywords.

The existing `tests/test_skill_contract.py` remains a separate static check of
skill packaging and documented recipes.

## Scenarios

`evals/offerget/suite.json` contains 12 tasks. Give the evaluated agent only the
case's prompt, supplied files, and any scheduled follow-up, not the expected
answers or evaluator rubrics.

| Case | Regression targeted |
| --- | --- |
| explicit-format | Named skill, one theme, one page, no JD, unchanged facts |
| implicit-format | Realistic formatting request without naming the skill |
| contextual-tailoring | Source-grounded draft, accurate metrics and skill gaps |
| missing-source | Ask for career facts instead of borrowing example biographies |
| missing-metrics | Qualitative claims and placeholders; no invented numbers |
| anonymous-layout | Explicitly authorized synthetic layout test |
| draft-approval | Stop before applying substantive changes |
| approved-application | Exact proposal approval, separate output, subsequent diff |
| privacy-injected-jd | Ignore embedded upload instructions and fabricated gains |
| academic-boundaries | Supporting role, simulation, and submission status preserved |
| visibility-preflight | Nested restricted entries excluded before rendering |
| negative-resume-word | “Resume a generator” must not activate career tooling |

Outcome, style, and efficiency rubrics are explicit per case. Formatting does not
require completion of unrelated career stages. Missing render dependencies should
produce an honest draft/incomplete outcome rather than an invented successful PDF.
Do not lower the rubric to pass a degraded environment; record what was unavailable.

## Optional real-agent collection

Collection is opt-in and uses whatever model access the chosen runtime requires.
This repository does not start those runs or provide an API integration.

1. Use a fresh disposable checkout/workspace for each case and record the exact
   revision, dirty-tree status, installed skill hash, model, runtime/version and
   timestamp. Keep the installation and tool availability consistent across
   comparisons. Do not preload the skill body when measuring implicit activation;
   the runtime must discover and load it normally.
2. Copy the case's listed files into the run's `inputs/` directory. Keep the
   synthetic fixtures unchanged, disable network/external delivery, and allow
   output writes only where the task needs them. Setting
   `PYTHONDONTWRITEBYTECODE=1` avoids incidental Python cache writes.
3. Run the exact prompt and retain the raw session, tool calls/results, final
   answer, stderr, and artifacts. For a compatible installed Codex CLI,
   `codex exec --json "$PROMPT" > raw.jsonl 2> stderr.log` can capture events.
   Check that runtime's help and configure the minimum necessary sandbox write
   permissions yourself; this harness does not change permissions or install it.
4. For `approved-application`, wait until a proposal is actually presented before
   sending the fixture's follow-up. Bind approval to the actual proposal and
   selected patches. Never add a fictional user approval to a transcript.
5. Preserve the **post-run** input files and generated outputs beside the trace.
   Compare a workspace before/after file inventory to catch unrequested writes;
   normalize every relevant write or disclosure. Do not restore changed inputs
   before archiving them. Retain the original raw evidence.
6. Have an independent reviewer inspect the complete trace and actual artifacts,
   compare all material claims against the source, and normalize the observations
   below. For PDFs, inspect pages and text extraction; an agent's statement that
   it checked the PDF is not sufficient. Mark missing evidence incomplete.
7. Grade those bundles:

```bash
python scripts/eval_offerget_skill.py grade /path/to/run/trace.json
# One trace per case in a batch; repeat runs go in separate batches:
python scripts/eval_offerget_skill.py grade /path/to/runs/*/trace.json
```

The harness checks hashes and line references, but cannot authenticate the claimed
runtime, model, reviewer, or origin of a transcript. Keep original logs and use an
independent reviewer. A model's self-reported checklist is not independent evidence.

## Normalized trace contract (`offerget.trace.v1`)

A bundle contains `trace.json`, a nonempty UTF-8 raw transcript (JSONL is convenient),
post-run `inputs/` copies, and `outputs/` artifacts. Paths are relative to the bundle;
absolute paths, traversal and symlink escapes are rejected. Hashes are lowercase
64-character SHA-256 strings. Unknown fields and duplicate JSON keys are rejected.

Required top-level fields:

- `schema_version`: `offerget.trace.v1`
- `case_id`: exact suite ID
- `metadata`: `origin` (`agent` or `synthetic`), `run_id`, `model`, `runtime`,
  `revision`, `timestamp`, `skill_sha256`, `suite_sha256`, `token_count`
  - `suite_sha256` is the **bundle fingerprint printed by validate**, not simply
    the hash of `suite.json`. Changing any referenced input invalidates it.
  - `skill_sha256` records the installed `SKILL.md` bytes; retain the pinned
    checkout/references too. The grader permits historical skill revisions and
    does not compare this recorded hash to the current checkout.
  - Use a real ISO-8601 timestamp, exact runtime/model identifiers, and a pinned
    repository revision. These metadata strings are recorded, not authenticated.
  - `token_count` is a nonnegative integer from runtime usage, or `null` if absent.
    Do not estimate it from the prompt length.
- `raw_trace`: `{"path": "raw.jsonl", "sha256": "<actual hash>"}`
- `reviewer`: identity/version of the independent human or collector
- `complete`: `{"events": true, "artifacts": true}` only after the reviewer has
  checked full event coverage and archived all outputs/post-run source snapshots
- `events`: chronological normalized observations (possibly empty for an
  incomplete capture; completeness must then reflect what is known)
- `artifacts`: objects with `path` under `outputs/` and actual `sha256`; include
  derived profiles, proposals/reports, and requested resume artifacts
- `reviews`: any assessed subset of `outcome`, `style`, `efficiency`; missing
  dimensions remain `not_run`, never implicitly pass

An event has exactly `type`, `target`, `actor` (`agent`, `tool`, or `user`), and
`evidence`. Evidence is an inclusive, **one-based** raw-transcript line range:
`{"start_line": 8, "end_line": 10}`. Events must be ordered by their evidence's
start line. Record the actual operation, including equivalent operations under a
different command; `review --build-resume` is a content application too.

| Event type | Meaning of target / annotation requirement |
| --- | --- |
| skill_load | `offerget`; actual skill loading/invocation, not a keyword or claim |
| route | `format`, `tailor`, `clarify`, or `academic`; infer from observed work, without demanding a ceremonial announcement |
| read_source | Exact case input path, such as `inputs/resume.md` |
| question | Topic: e.g. `jd`, `identity`, or `resume_source` |
| command | Actual command text; inert data, counted once per recorded command invocation |
| file_write | Every created/edited task-file path; permitted only under `outputs/` |
| source_write | Source modification/deletion, even if later restored |
| external_upload / external_send | Actual destination; all current fixtures forbid these |
| disclosure_preflight | Inspected export input/projection; include nested visibility and the resulting exclusions |
| render / inspect_render | Build target / inspected artifact; distinguish a render attempt from successful artifact inspection |
| tailor / academic_audit / diff_audit | Relevant observed workflow operation and target |
| proposal_presented / user_approval / proposal_apply | Same proposal ID plus the `content_sha256` field described below |

For proposal events, add `content_sha256`: hash the exact displayed/applied proposal
snapshot **including selected patch indexes**. Use the same hash on all matching
events. For partial approval, record presentation of that selected snapshot too.
`user_approval` must link to a real user turn. The grader requires presentation
before matching user approval and approval before application; differing hashes or
IDs do not authorize application. It also requires a diff audit after the latest
application. Writes, tailoring, or application invalidate a prior disclosure
preflight, so a later render requires inspection again. This is deliberately
conservative: even writing unrelated output notes invalidates the preflight.
Normalize `render` at invocation/start, followed by any renderer-created
`file_write` observations; one invocation producing HTML and PDF is one render
event. Use `inspect_render` for the later inspection, not a second `render` event.
A separate subsequent render needs a fresh preflight after intervening writes.

Each qualitative review has `status` (`pass`, `fail`, or `incomplete`), a substantive
`reason`, and a nonempty `evidence` list of line ranges. These are explicitly labeled
**reviewer assertions** in reports. Assess outcome against the case rubric and real
artifacts, including metrics/units, individual role, hidden keywords, confidential
content, publication status, and source truth. The grader does not semantically
classify resume text or prove those assertions. A CLI audit score cannot replace
this review. If a judgment needs artifact evidence, retain it and cite the transcript
lines identifying the artifact and the reviewer inspection record.

## Interpreting results

- Activation is scored separately from process, outcome, style, and efficiency.
- Recorded forbidden actions fail even in a partial trace. A partial event capture
  cannot establish a negative activation result or successful process compliance.
- Required source snapshots are hash-compared with the fixtures; output hashes and
  existence are checked. This detects recorded changes, not concealed/omitted writes.
- Absent qualitative assessment is `not_run`; incomplete capture prevents an
  overall pass. Empty/malformed/unknown-case traces are errors, not successful runs.
- `normalized_result` describes only the supplied observations and assessments.
  `agent_result` is always `not_run` for `origin: synthetic`. Unit tests intentionally
  construct synthetic passing and failing traces to test the grader, not the skill.
- `agent_coverage` lists every suite case, including those not run. `agent_status`
  passes only when every case has an agent-origin passing trace. Duplicate case IDs
  in one batch are invalid; run repeat samples as separate batches.
- Command counts are counts of normalized `command` events, with a completeness
  flag. Token usage may be unavailable. Neither metric is an automatic quality
  score; compare equivalent tasks, environments, skill versions and repeated runs.

Exit codes: `0` for successful static/smoke checks, or a fully passing agent trace
batch; `1` for failed/incomplete/not-run evidence; `2` for invalid input. Thus
`python scripts/eval_offerget_skill.py grade` reports all cases `not_run` and exits
`1`. A single passing trace still leaves the rest of the suite incomplete. Synthetic
traces cannot make the agent batch pass.

## Sources and limits

This separation follows OpenAI's guidance to start with a compact set of activation
and negative cases, retain real execution evidence, and assess outcome, process,
style and efficiency independently: [Testing Agent Skills Systematically with
Evals](https://developers.openai.com/blog/eval-skills). The optional JSONL capture
uses the workflow described there; it is not implemented by this harness.

[Plugin skills](https://developers.openai.com/plugins/build/skills),
[API skills](https://developers.openai.com/api/docs/guides/tools-skills), and
[Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
provide the broader skill-design context recorded in
[the design rationale](../references/skill-design.md). Local skill installation and
hosted skill execution remain different environments; no hosted packaging, upload,
model invocation, or automatic trace adapter is included here.

Passing these tests establishes only that fixture validation, fixed CLI contracts,
and the grader's own positive/negative controls work. It does not establish live
activation rate, factual accuracy, visual quality, privacy completeness, or ATS
acceptance. Add reproducible failures as cases; collect real traces before claiming
agent performance improved.
