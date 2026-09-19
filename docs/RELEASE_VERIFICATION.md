# OfferGet Release Candidate (RC) Verification Report

This document records the comprehensive release qualification, test baselines, packaging verification, and performance profiling for OfferGet.

---

## 1. Environment Baseline

- **Operating System**: Windows 11 (win32)
- **Python Runtime**: Python 3.13.11 (`D:\Program Files\Developer Tools\miniconda3\python.exe`)
- **Core Test Frameworks**:
  - `pytest`: 9.1.0
  - `pluggy`: 1.5.0
  - `anyio`: 4.14.1
  - `fast-array-utils`: 1.4.1
- **Headless Browser Runtime**:
  - `Chrome Path`: `C:\Program Files\Google\Chrome\Application\chrome.exe` (detected via `BrowserRenderer._find_chrome()`)
- **Package Build Tooling**: `setuptools` >= 68 (PEP 517 / PEP 621 compliant via `setuptools.build_meta`)

---

## 2. Test Suite Execution Baselines

OfferGet maintains a three-tier test verification regimen:

| Test Target | Suite Command | Collected Items | Result | Duration | Notes |
|:---|:---|:---:|:---:|:---:|:---|
| OfferGet Core Tests | `pytest tests -q` | 352 items | **352 passed** | ~14s | Full coverage of profile adapter, jd analyst, ats checker, baoyan, fact guard, router |
| ApexResume Integration | `pytest ApexResume/tests --rootdir=ApexResume -q` | 34 items | **34 passed** | ~0.6s | Verifies audit heuristics, single-page budget compaction, font scaling, DOM fitting |
| Self-Test Diagnostics | `python cli.py selftest` | 11 checks | **11/11 passed** | ~4s | End-to-end integration check covering imports, CLI parsing, report generation, and exports |

---

## 3. Dual Packaging & Isolated Out-of-Source Verification

OfferGet builds both source distribution (`sdist`) and binary wheel (`wheel`) artifacts containing all submodules, runtime assets, and theme templates:

### 3.1 Package Build Artifacts
- **Source Distribution (`sdist`)**: `offerget-1.0.0.tar.gz` (350,143 bytes)
- **Binary Wheel (`wheel`)**: `offerget-1.0.0-py3-none-any.whl` (373,715 bytes)
- **Included Resources**:
  - `core/`, `modules/`, `presentation/`
  - `ApexResume/` (full engine, `themes/` including `ats-plain.md`, `classic-tech.html`, `modern-navy.html`, `silicon-clean.html`)
  - `templates/` (`offer_strategy.html`, `__init__.py`)
  - `LICENSE`, `README.md`, `SKILL.md`

### 3.2 Out-of-Source CLI Verification Matrix
Verification executed inside an isolated virtual environment (`$env:TEMP/offerget_pkg_test_*`) located outside the project repository, with zero local source dependencies:

| Command | Invocation Arguments | Exit Code | Verified Output |
|:---|:---|:---:|:---|
| `offerget jd decode` | `jd decode sample_jd.txt --json` | `0` | Correct 5-layer decomposition output in valid JSON |
| `offerget jd report` | `jd report sample_jd.txt --profile sample_profile.json --output report.html` | `0` | Bilingual twin validation passed (EN=276, ZH=276, 96,113 bytes generated) |
| `offerget resume build` | `resume build sample_profile.json --theme ats-plain --output-dir resumes` | `0` | Generated `resume_ats_plain.html`, `resume_ats_plain.md`, `resume_ats_plain.pdf` |
| `offerget review` | `review sample_jd.txt --profile sample_profile.json --output review.json --json` | `0` | Generated complete closed-loop `career-review.v1` JSON structure |
| **Missing Template Test** | `jd report ... --template missing-template.html` | `1` | Clean failure: `[-] Error: Report template not found: 'missing-template.html'` |
| **Custom Template Test** | `jd report ... --template custom_template.html --output custom.html` | `0` | Injected custom HTML markers and variable placeholders successfully |
| **Wheel Installation** | `pip uninstall -y offerget && pip install *.whl` | `0` | Clean wheel install; CLI commands fully operational |

---

## 4. Sub-Stage Performance Profiling Breakdown

Benchmark measurements conducted using `examples/synthetic_intern_profile.json` evaluating the 6 supported resume themes:

```json
{
  "modern-navy": {
    "html_gen_ms": 0.47,
    "render_autofit_pdf_ms": 2280.29,
    "total_theme_ms": 2280.76
  },
  "silicon-clean": {
    "html_gen_ms": 0.46,
    "render_autofit_pdf_ms": 2020.63,
    "total_theme_ms": 2021.09
  },
  "classic-tech": {
    "html_gen_ms": 0.58,
    "render_autofit_pdf_ms": 2095.19,
    "total_theme_ms": 2095.77
  },
  "ats-plain": {
    "html_gen_ms": 0.02,
    "render_autofit_pdf_ms": 741.73,
    "total_theme_ms": 741.75
  },
  "academic-latex": {
    "html_gen_ms": 0.07,
    "render_autofit_pdf_ms": 772.19,
    "total_theme_ms": 772.27
  },
  "academic-typst": {
    "html_gen_ms": 0.06,
    "render_autofit_pdf_ms": 84.93,
    "total_theme_ms": 84.99
  },
  "metrics": {
    "profile_context_setup_ms": 0.37,
    "shared_view_model_init_ms": 0.02,
    "total_normalize_calls": 0,
    "total_view_model_instantiations": 1
  }
}
```

### Key Performance Findings:
1. **Zero Redundant Normalizations**: `ProfileContext` and `ResumeBuilder` cache normalized data using content fingerprinting. Across all 6 themes, `normalize_candidate_profile` was called **0 times**, and `ResumeViewModel` was instantiated **exactly 1 time**.
2. **Template Generation Overhead**: HTML, Markdown, LaTeX, and Typst source generation takes `< 0.6 ms` per theme (`~0.02 - 0.58 ms`).
3. **Primary Runtime Bottleneck**: Headless Chromium initialization, AutoFit multi-pass CSS compaction, and PDF rasterization account for **> 99.9%** of the total runtime (~2.0 - 2.3s per HTML theme).
4. **Architectural Verification**: Confirms that adding complex caching layers around profile normalization or template rendering would yield negligible gains, and that optimizing Chrome process lifecycle or pre-warming browser instances would be the appropriate direction for future render acceleration.

---

## 5. Repository Governance & Zero-Deletion Audit

- **Scope**: 26 external repositories under `E:\github\简历\`.
- **Governing Document**: `docs/ABSORPTION_LEDGER.md`.
- **Status Classification**:
  - `retained`: 17 repositories (containing independent Web UIs, audio pipelines, or desktop apps).
  - `partial-absorption`: 3 repositories (`King-of-Pigeon`, `resume-jd-optimizer-cn`, `ResumeSkills`).
  - `archive-candidate`: 6 repositories (`ASu-resume-skills`, `ats-optimized-resume-agent-skill`, `baoyan-skill`, `baoyan-skills`, `defense-beating-simulator`, `job-description-skill`).
  - `delete-approved`: **0 repositories**.
- **Audit Verification**:
  - All 26 source repositories remain completely untouched on disk.
  - Zero `git commit`, `git push`, `git reset`, or `git clean` operations performed.
  - Offline git bundle recovery commands documented for all 6 archive candidates.
