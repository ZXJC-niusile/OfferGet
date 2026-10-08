# Anonymization boundaries

OfferGet provides reversible text pseudonymization, not a guarantee that a resume
cannot be identified. Keep the reverse map private and separate from shared
outputs; it contains original identity values.

## Structured profiles

`anon mask profile.json --level strict --map /private/map.json --output masked.json`
preserves the original JSON structure and types. It discovers candidate identities
in flat, `candidate`, and `basics` profiles; education can be a dictionary or list.
Supported institution keys include `school`, `institution`, `university`,
`undergraduate_school`, and `degree_school`. Employer discovery includes `company`,
`company_en`, `org`, `organization`, and `employer`, including internships.
Project names/titles are discovered in `projects` and `campus_experience`.

Standard mode masks declared names, contact fields and profile/project links.
Strict mode additionally masks declared schools, companies, and project identities,
plus known hardware patterns. Discovered identities are replaced throughout text
values, including repeated mentions in descriptions; keys and non-string data are
preserved. Unknown privacy-bearing fields produce warnings. Unsupported types in
known identity fields fail rather than pretending they were masked.

Arbitrary new field names, unstructured descriptions, publication titles, indirect
clues, and identifiers not declared in supported fields may remain identifying.
Review the output before sharing. Raw text input uses limited patterns and emits a
coverage warning, since it cannot discover every unfamiliar name or institution.
Warnings identify field paths, without echoing field values.

## Strict resume exports exclude photos

`resume build ... --anonymize strict` excludes real photos in every export format,
including HTML, ATS Markdown, LaTeX, Typst, and DOCX. Strict privacy takes precedence
over explicit photo modes and constructor, profile, or per-build photo paths. A
warning explains when a requested/profile photo was omitted. Excluded files are
not opened, so even nonexistent or invalid photo paths cannot leak bytes or block
a strict export. Standard mode retains the ordinary photo contract.

Standalone `anon mask` works on text fields and does not alter image files or
remove photo references; photo fields produce a coverage warning. Image omission
in resume exports is not reversible image anonymization. Restore text only with
`anon unmask masked.json --map /private/map.json`.

## Audit sidecars

Anonymized exports omit diff-ledger sidecars with a warning, even if a baseline
profile or diff-ledger option was supplied. These audit files can contain original
identity values and belong in a separate private audit workflow. An anonymized
export refuses an output directory containing earlier `resume_diff_ledger.md` or
`.json` sidecars; choose a clean output directory rather than sharing stale files.

Privacy masking applies to the newly returned artifacts, not every file already
in an output directory. Existing HTML/PDF files, originals left by a shadow-path
write, and unrelated files are not scrubbed or deleted. A nonempty destination
produces a scope warning. Share only returned files; use a new empty destination
when the entire directory will be shared.

## Reversible aliases

Mappings use deterministic distinct aliases and a single-pass replacement in each
direction. Existing alias-like text and reverse-map metadata names are protected.
Ambiguous readable aliases fall back to reserved opaque tokens. Each result is
checked for an exact public-API round trip before being returned. Different inputs
can therefore use different aliases when their collision context differs.
