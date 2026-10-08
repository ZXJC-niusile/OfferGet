# Photo and no-photo resume variants

The CLI now defaults to **no photo**. This is a deliberate change from the old
empty reserved-photo box. Use the same profile and theme for both versions; only
photo selection changes, never the candidate's facts.

```bash
# No image, empty box, or reserved portrait width, even if the profile has a photo.
python cli.py resume build profile.json --theme modern-navy \
  --photo-mode no-photo --output-dir output/modern-navy/no-photo

# A real local photo. Missing, invalid, or unsupported images fail clearly.
python cli.py resume build profile.json --theme modern-navy \
  --photo-mode photo --photo-path candidate.png --output-dir output/modern-navy/photo

# Explicit layout preview only; this is not a submission-ready resume.
python cli.py resume build profile.json --theme modern-navy \
  --photo-mode placeholder --output-dir output/modern-navy/placeholder-preview
```

`--no-photo` remains an alias for `--photo-mode no-photo`. `--photo-path` without a
mode selects `photo` for compatibility. `--no-photo --photo-path candidate.png`
still excludes the image and does not open it. Use separate output directories
for paired variants because existing artifact filenames are preserved.

## Input schema and precedence

Standard profiles can store `candidate.photo_path` (legacy alias
`candidate.photo`), `candidate.photo_mode`, and the legacy `candidate.reserve_photo`.
Minimal profiles accept the same fields at the top level. The mode values are
`photo`, `no-photo`, and `placeholder`. Profiles are copied, not edited in place.

- CLI selection wins over profile metadata. With no CLI photo options the default
  is `no-photo`, even if the source contains a photo. Use `--photo-mode photo` to
  deliberately load a profile's stored image path.
- API `photo=False` / `reserve_photo=False` always wins and excludes photo paths,
  data URIs, and the placeholder without reading the image.
- An explicit API `photo_mode` overrides the profile's `photo_mode`.
- `photo` requires an image. `placeholder` deliberately ignores any image path.
- Legacy Python callers with no mode retain their existing `photo=True` /
  `reserve_photo=True` placeholder behavior. New callers should pass a mode.
- Once a ViewModel is resolved as no-photo, supplying a new path alone does not
  re-enable it. Pass `photo_mode="photo"` explicitly. Mode overrides copy the VM.
- Native exporters preserve a supplied resolved VM by default. Their legacy
  explicit `reserve_photo=True` still reserves a slot for raw profiles without
  an image; use explicit modes for uniform new behavior.

## Formats and safety

Eight HTML themes, ATS HTML, LaTeX, Typst, and their HTML previews honor the same
selection. ATS Markdown cannot embed a portrait; in photo mode it records the
selected local photo path, and in no-photo mode it contains neither path nor
photo note. `ats-docx` currently supports **no-photo only**. An explicit photo or
placeholder request fails instead of silently discarding the selection; a DOCX
photo layout remains separate work.

A shared local helper checks the actual bytes with Pillow before embedding.
PNG, JPEG, WebP, and single-frame GIF are supported for HTML; extension and image
format must match. SVG, arbitrary files, truncated images, animation, files over
10 MiB, and images over 25 megapixels are rejected. LaTeX photo input is PNG or
JPEG only, so those are the portable choices for a multi-format build. Install
`.[render]` for photo-validation dependencies. No remote image fetch, face
creation, crop, or biographical change is performed.

Actual HTML photos no longer have an on-error handler that silently substitutes
an empty reservation box. Typst copies only the selected validated photo beside
its source and quotes its resource path safely. No-photo does not copy a source
photo. It does not delete artifacts left by an earlier build, so keep paired
outputs in separate directories.

## Verification

`python -m pytest tests/test_resume_photo_contract.py` checks same-profile pairs,
all eight HTML themes, native sources, ATS HTML/Markdown, DOCX exclusions, CLI
precedence, source immutability, and invalid-file rejection. The synthetic fixture
is a clearly illustrated head-and-shoulders portrait with registration markers,
not a real candidate or the user's photo.

These are source/IO contracts. Test renderer doubles do not establish visual
correctness or real PDF rendering. Actual browser/native-engine checks still need
to inspect portrait containment, header reflow, readable text, clipping, and page
breaks for each paired template on the final integrated commit.
