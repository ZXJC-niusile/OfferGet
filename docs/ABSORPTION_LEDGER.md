# OfferGet Knowledge & Repository Absorption Ledger

This ledger documents the absorption, integration, and retention status of all 26 external repositories located under `E:\github\简历\`.

---

## 1. Governance & Deletion Approval Criteria

Repositories under `E:\github\简历\` represent independent research assets, reference implementations, and specialized tooling. **OfferGet does not automatically delete or overwrite any external repository.**

> [!NOTE]
> **关于测试覆盖与 Parity 说明**：
> 表格中 `actual_tests` 记录的是 OfferGet 仓库内部覆盖已吸收规则的自动化测试用例路径，用以保证 OfferGet 自身功能稳定，**不代表**已完成对源仓库全部外部功能（如 Web UI、音频管线、插件系统、独立 Ontology 等）的 100% parity 验证。源仓库的独有资产与未吸收功能将继续独立保留。

To qualify for future archival or deletion, an external repository MUST satisfy all 6 strict gates:

1. **Rule & Logic Completeness**: Core domain algorithms, heuristic formulas, data models, and business boundaries are implemented in native Python within OfferGet.
2. **Asset Redundancy**: Unique prompt libraries, document templates, benchmark datasets, or design artifacts have either been absorbed or verified as obsolete.
3. **Zero Upstream Dependency**: The repository is not actively tracking upstream projects or maintaining live external integrations.
4. **Automated Test Parity**: Automated unit and integration test suites in OfferGet verify that behavior parity is achieved and regression-free without regressions.
5. **Formal User Authorization**: Explicit, written user confirmation has been obtained specifically approving the deletion of that specific repository.
6. **Archival Snapshot Confirmed**: An offline git bundle or compressed backup archive has been created and verified prior to any filesystem removal.

> [!IMPORTANT]
> **Current Deletion Verdict**: Under these strict criteria, **0 of the 26 repositories under `E:\github\简历\` are approved for immediate deletion**. All 26 repositories remain strictly intact on disk (`delete-approved = 0`).

---

## 2. Comprehensive 26-Repository Absorption Ledger

| source_repo | absorbed_capabilities | unabsorbed_capabilities | actual_tests | unique_assets | license_lineage | status | delete_gate_status |
|:---|:---|:---|:---|:---|:---|:---:|:---:|
| `academic-homepage-cv-sync` | Academic profile schema mapping, publication claim extraction | Static site generator, GitHub Pages workflow, Semantic Scholar live sync | `tests/test_profile_adapter.py`, `tests/test_baoyan_pipeline.py` | Hugo/Jekyll themes, GitHub Actions CI scripts, public API synchronization logic | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `Academic-Resume-Template` | Academic dual-column publication display rules, educational honors grouping | Custom XeLaTeX typography configurations, bespoke academic CV styles | `tests/test_academic_exporter.py`, `tests/test_resume_builder.py` | XeLaTeX cls/sty files, custom academic fonts, compiled PDF samples | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `academic-skills` | Academic statement structuring, advisor alignment criteria, research interest matching | Standalone Claude/Gemini CLI skill definitions, multi-step prompt chains | `tests/test_advisor_matcher.py` | Agent skill YAML definitions, prompt engineering templates | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `applyr` | CLI I/O patterns, file-vs-text routing, deterministic exit codes | Complete desktop GUI application, web automation backend, persistence layer | `tests/test_cli_helpers_and_smoke.py`, `tests/test_services_and_router.py` | Electron/PyQt desktop GUI, browser automation hooks | Apache-2.0 | `retained` | 0/6 gates approved (not approved for deletion) |
| `ASu-resume-skills` | Resume bullet structure audit, verb classification, impact metric enforcement | ASu skill YAML descriptors, historical reference datasets | `tests/test_asu_and_taxonomy.py`, `tests/test_fact_guard.py` | Reference benchmark datasets, legacy YAML descriptions | Apache-2.0 | `archive-candidate` | 0/6 gates approved (not approved for deletion) |
| `ats-optimized-resume-agent-skill` | Four-dimensional ATS audit, keyword density calculations, format hygiene checks | Standalone Skill prompt schemas and MCP tool definitions | `tests/test_ats_checker.py` | Standalone agent prompts, legacy MCP definitions | MIT | `archive-candidate` | 0/6 gates approved (not approved for deletion) |
| `baoyan-resume-writing` | 4 academic integrity redlines (simulation, submitted-as-accepted, role inflation, vacuous buzzwords), 3-tier length compression | Specific university-level application guidelines and Chinese Word (.docx) templates | `tests/test_baoyan_auditor.py` | Word (.docx) templates with tables, institutional submission instructions | CC-BY-NC-4.0 | `retained` | 0/6 gates approved (not approved for deletion) |
| `baoyan-skill` | Summer camp checklist rules, postgraduate status machine transitions | Raw skill prompts for external LLMs | `tests/test_baoyan_pipeline.py` | Raw prompt files for external models | MIT | `archive-candidate` | 0/6 gates approved (not approved for deletion) |
| `baoyan-skills` | High-EQ email drafting principles, multi-track candidate scoring (学硕 vs 专硕) | Standalone agent skills and prompt engineering templates | `tests/test_advisor_matcher.py`, `tests/test_baoyan_pipeline.py` | Standalone agent prompts and email templates | MIT | `archive-candidate` | 0/6 gates approved (not approved for deletion) |
| `Chinese-resume-template-postgraduate` | Single-page compact postgraduate grid layout, education badges grouping | Pure LaTeX template source code and PDF samples | `tests/test_academic_exporter.py`, `tests/test_profile_adapter.py` | LaTeX template source files, PDF reference outputs | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `defense-beating-simulator` | Project defense cross-examination simulator, claim-evidence cross-validation, 3 interrogation intensities | Standalone interactive terminal TUI and voice dialogue hooks | `tests/test_defense_simulator.py` | Terminal TUI scripts, voice dialogue hooks | MIT | `archive-candidate` | 0/6 gates approved (not approved for deletion) |
| `job-description-skill` | 5-layer JD decomposition, 32 corporate jargon decoder terms, hidden signal extraction | Independent Skill definitions and Claude slash commands | `tests/test_jd_decoder.py`, `tests/test_jd_matcher.py`, `tests/test_redflags.py` | Claude slash command configs, standalone YAML skills | MIT | `archive-candidate` | 0/6 gates approved (not approved for deletion) |
| `King-of-Pigeon` | 4-tier commitment matrix, defensive etiquette, polite decline letters, verbal offer confirmation templates | Comprehensive markdown guides on postgraduate admissions communication | `tests/test_advisor_matcher.py` | Markdown communication handbooks, reference email corpora | MIT | `partial-absorption` | 0/6 gates approved (not approved for deletion) |
| `latex-resume-template` | ATS-friendly LaTeX macro conversions, compact vertical spacing parameters | Standalone TeX fonts, custom cls/sty files, direct pdflatex build tooling | `tests/test_academic_exporter.py`, `tests/test_resume_builder.py` | Custom LaTeX packages, font files, styling definitions | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `offerPilot` | Compensation package valuation, 6 contract trap detection rules, tactical counter-offer generation | Web full-stack React frontend, database migration schemas, authentication modules | `tests/test_offer_negotiator.py`, `tests/test_services_and_router.py` | Full-stack React/Node.js web application, Prisma schemas, database migrations | GPL-3.0 | `retained` | 0/6 gates approved (not approved for deletion) |
| `PostInterviewAI` | Post-interview debrief diagnosis heuristics, gap vs evidence boundary demarcation | Audio recording transcription pipelines, speech-to-text models, audio ingestion UI | `tests/test_career_review.py` | Audio transcription scripts, Whisper integration models, speech processing modules | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `rendercv` | Strongly-typed View Model abstraction, photo embedding, layout separation | Complete multi-engine renderer (Typst, LaTeX, HTML, Markdown), CLI tooling | `tests/test_resume_view_model.py`, `tests/test_resume_builder.py` | Multi-engine rendering pipeline, CLI commands, Typst/LaTeX templates | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `rendercv-skill` | YAML-to-Resume translation mappings | Standalone prompt wrappers for RenderCV CLI | `tests/test_resume_view_model.py` | Agent skill definition files, RenderCV invocation prompts | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `resume-assistant-mcp` | Fact verification gate concepts, evidence anchoring rules | MCP (Model Context Protocol) server implementation, JSON-RPC handlers | `tests/test_fact_guard.py`, `tests/test_profile_adapter.py` | MCP server implementation, JSON-RPC protocol transport, tool schema registry | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `resume-jd-optimizer-cn` | Chinese terminology normalization, keyword alias mapping, matching formulas | Web UI application, standalone prompt files | `tests/test_registry.py`, `tests/test_jd_matcher.py` | Streamlit/Vue Web UI frontend, standalone optimizer prompts | MIT | `partial-absorption` | 0/6 gates approved (not approved for deletion) |
| `resume-tailor-plugin` | Resume patch audit trails, incremental bullet rewrite mechanisms | Obsidian / VSCode plugin wrappers and UI panels | `tests/test_career_review.py` | Obsidian/VSCode extension manifest, TypeScript plugin frontend | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `resume-toolkit` | Multi-format export utilities, text cleaning heuristics | Legacy format conversion scripts (Docx, RTF) | `tests/test_output_security.py`, `tests/test_cli_helpers_and_smoke.py` | RTF/Docx converters, standalone shell scripts | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `resume-typst` | Typst single-page grid and badge layout templates | Bespoke Typst packages, font configurations, standalone typst CLI tooling | `tests/test_academic_exporter.py`, `tests/test_resume_builder.py` | Typst custom packages, embedded font files, .typ source documents | MIT | `retained` | 0/6 gates approved (not approved for deletion) |
| `ResumeSkills` | Industry skill taxonomy trees, core competency categorization | Original skill ontology JSON files and standalone taxonomies not fully migrated | `tests/test_registry.py`, `tests/test_ats_checker.py` | Complete external skill ontology JSON datasets | MIT | `partial-absorption` | 0/6 gates approved (not approved for deletion) |
| `sigmacv` | Single-page budget constraints, autofit concept | Web-based visual canvas editor and drag-and-drop resume builder | `ApexResume/tests/test_autofit.py`, `ApexResume/tests/test_audit.py` | Web visual editor, canvas manipulation components, drag-and-drop UI | AGPL-3.0 | `retained` | 0/6 gates approved (not approved for deletion) |
| `vanceling-skills` | Career interview question taxonomy and intent prediction | Standalone prompt repository, audio, vision, Feishu integration, paper reading workflows | `tests/test_predictor.py`, `tests/test_career_review.py` | Multi-modal interview prompts, Feishu bot hooks, voice/vision scripts | MIT | `retained` | 0/6 gates approved (not approved for deletion) |

---

## 3. Status Category Summary

- **`retained` (17 repos)**: Repositories possessing standalone product capabilities, specialized runtime environments, or unique asset pipelines outside OfferGet's pure Python CLI scope (`academic-homepage-cv-sync`, `Academic-Resume-Template`, `academic-skills`, `applyr`, `baoyan-resume-writing`, `Chinese-resume-template-postgraduate`, `latex-resume-template`, `offerPilot`, `PostInterviewAI`, `rendercv`, `rendercv-skill`, `resume-assistant-mcp`, `resume-tailor-plugin`, `resume-toolkit`, `resume-typst`, `sigmacv`, `vanceling-skills`).
- **`partial-absorption` (3 repos)**: Repositories whose core scoring or normalization rules have entered OfferGet, but which retain standalone Web UIs, bespoke communication guides, or independent ontology datasets (`King-of-Pigeon`, `resume-jd-optimizer-cn`, `ResumeSkills`).
- **`archive-candidate` (6 repos)**: Repositories whose core scoring, decomposition, and audit heuristics have been fully absorbed into OfferGet test suites, eligible for archival when requested by user with formal backup (`ASu-resume-skills`, `ats-optimized-resume-agent-skill`, `baoyan-skill`, `baoyan-skills`, `defense-beating-simulator`, `job-description-skill`).
- **`delete-approved` (0 repos)**: Exactly 0 repositories are approved for deletion. All 26 repositories under `E:\github\简历\` remain strictly intact and preserved on disk.

---

## 4. Detailed Dossiers for Archive Candidates

Each of the 6 `archive-candidate` repositories is documented below with its source revision, absorbed capabilities, OfferGet counterpart implementation, internal regression test suite, unabsorbed assets that require preservation, and the exact backup/recovery protocol.

### 4.1 `ASu-resume-skills`
- **Source Revision**: Commit `f460582` (36 files)
- **Source Path**: `E:\github\简历\ASu-resume-skills`
- **License**: Apache-2.0
- **Absorbed Capabilities**:
  - Action verb classification and power-verb taxonomy.
  - Resume bullet structure audit (Action + Context + Metric / Impact).
  - Fact checking and hallucination guards against ungrounded metrics.
- **OfferGet Counterparts**:
  - `core/asu_modeler.py`: Action verb taxonomy and power scoring.
  - `core/fact_guard.py`: Fact verification and metric anchor checks.
  - `core/ats_checker.py`: Bullet structure audit rules.
- **OfferGet Internal Regression Tests**:
  - `tests/test_asu_and_taxonomy.py`
  - `tests/test_fact_guard.py`
- **Unabsorbed / Preserved Assets**:
  - Historical reference benchmark datasets (`examples/audit-report.example.json`, `examples/resume-data.example.json`).
  - Legacy YAML skill descriptors (`skills/asu-resume-audit-skill`, `skills/asu-resume-skill`).
  - Sample PDFs and visual assets (`assets/asu-resume-audit-example.pdf`, `assets/asu-circle.png`).
- **Archival / Recovery Protocol**:
  ```bash
  git -C "E:\github\简历\ASu-resume-skills" bundle create "ASu-resume-skills_f460582.bundle" --all
  ```

### 4.2 `ats-optimized-resume-agent-skill`
- **Source Revision**: Commit `153209b` (38 files)
- **Source Path**: `E:\github\简历\ats-optimized-resume-agent-skill`
- **License**: MIT
- **Absorbed Capabilities**:
  - 4-dimensional ATS scoring: Format Hygiene (25%), Keyword Density (30%), Experience Relevance (25%), Education & Hard Filters (20%).
  - Actionable improvement feedback generation.
- **OfferGet Counterparts**:
  - `core/ats_checker.py`: Native ATS evaluation engine and scoring rubrics.
  - `presentation/commands/ats_cmd.py`: CLI commands (`ats audit`, `ats ledger`, `ats filter`).
- **OfferGet Internal Regression Tests**:
  - `tests/test_ats_checker.py`
  - `tests/test_services_and_router.py`
- **Unabsorbed / Preserved Assets**:
  - Standalone Claude skill prompts (`skills/resume-skill`).
  - Claude plugin metadata (`.claude-plugin/plugin.json`, `marketplace.json`).
  - Shell and PowerShell automated installers (`install.ps1`, `install.sh`).
- **Archival / Recovery Protocol**:
  ```bash
  git -C "E:\github\简历\ats-optimized-resume-agent-skill" bundle create "ats-optimized-resume-agent-skill_153209b.bundle" --all
  ```

### 4.3 `baoyan-skill`
- **Source Revision**: Commit `95a331a` (48 files)
- **Source Path**: `E:\github\简历\baoyan-skill`
- **License**: MIT
- **Absorbed Capabilities**:
  - Summer camp application checklist generation and tracking.
  - Postgraduate application state-machine transitions (夏令营 -> 预推免 -> 九推 -> 统考复试).
  - Target track differentiation (直博, 学硕, 专硕).
- **OfferGet Counterparts**:
  - `core/baoyan_pipeline.py`: Postgraduate application lifecycle state-machine and checklist logic.
  - `core/advisor_matcher.py`: Advisor match rules.
  - `presentation/commands/academic_cmd.py`: CLI subcommands (`baoyan checklist`, `baoyan advisor`).
- **OfferGet Internal Regression Tests**:
  - `tests/test_baoyan_pipeline.py`
  - `tests/test_advisor_matcher.py`
- **Unabsorbed / Preserved Assets**:
  - Local Web GUI server and interactive frontend (`web/web_server.py`, `web/index.html`, `web/notices.html`).
  - Admissions notice crawler (`tools/notice_scraper.py`).
  - University and course knowledge base (`data/schools.yaml`, `data/hnu_courses.json`, `data/school_templates.json`).
  - Standalone LLM prompt markdown library (`prompts/advisor_email_cn.md`, `prompts/interview_questions_cn.md`, etc.).
- **Archival / Recovery Protocol**:
  ```bash
  git -C "E:\github\简历\baoyan-skill" bundle create "baoyan-skill_95a331a.bundle" --all
  ```

### 4.4 `baoyan-skills`
- **Source Revision**: Commit `1e88e5c` (41 files)
- **Source Path**: `E:\github\简历\baoyan-skills`
- **License**: MIT
- **Absorbed Capabilities**:
  - Academic outreach etiquette and high-EQ email drafting rules.
  - Academic profile scoring with multi-track weighting (research publications vs project engineering).
- **OfferGet Counterparts**:
  - `core/advisor_matcher.py`: High-EQ email drafting engine and tone validator.
  - `core/baoyan_pipeline.py`: Candidate-advisor profile alignment and score calculation.
- **OfferGet Internal Regression Tests**:
  - `tests/test_advisor_matcher.py`
  - `tests/test_baoyan_pipeline.py`
- **Unabsorbed / Preserved Assets**:
  - Standalone skill packages (`skills/application-package`, `skills/personal-statement`, `skills/taocixin-outreach`).
  - Automated privacy audit and skill validation scripts (`scripts/audit_privacy.py`, `scripts/validate_skills.py`).
  - Platform installation scripts (`install.ps1`, `install.sh`).
- **Archival / Recovery Protocol**:
  ```bash
  git -C "E:\github\简历\baoyan-skills" bundle create "baoyan-skills_1e88e5c.bundle" --all
  ```

### 4.5 `defense-beating-simulator`
- **Source Revision**: Commit `d1f4682` (41 files)
- **Source Path**: `E:\github\简历\defense-beating-simulator`
- **License**: MIT
- **Absorbed Capabilities**:
  - Project defense interrogation simulation.
  - 3-tier intensity levels: "先热个身" (warmup), "开始挑刺" (critical), "严刑拷打" (hell).
  - 7-section structured defense interrogation report.
- **OfferGet Counterparts**:
  - `core/defense_simulator.py`: Complete simulation engine and question generator.
  - `presentation/commands/fact_cmd.py`: CLI command (`defense simulate`).
- **OfferGet Internal Regression Tests**:
  - `tests/test_defense_simulator.py`
- **Unabsorbed / Preserved Assets**:
  - Interactive terminal dialogue scripts and voice simulation hooks.
  - Comprehensive multi-agent evaluation suites (`evals/expected_checks.yaml`, `evals/prompts.csv`).
  - Domain-specific rubrics (`references/domain-ai-projects.md`, `references/domain-engineering-simulation.md`, `references/question-patterns.md`).
- **Archival / Recovery Protocol**:
  ```bash
  git -C "E:\github\简历\defense-beating-simulator" bundle create "defense-beating-simulator_d1f4682.bundle" --all
  ```

### 4.6 `job-description-skill`
- **Source Revision**: Commit `ae4c050` (27 files)
- **Source Path**: `E:\github\简历\job-description-skill`
- **License**: MIT
- **Absorbed Capabilities**:
  - 5-layer Job Description structural decomposition (Mission, Competencies, Reality, Red Flags, Strategy).
  - 32 corporate jargon decoding rules and euphemism detection.
  - Hidden signals, unspoken requirements, and interview question prediction.
- **OfferGet Counterparts**:
  - `core/jd_decoder.py`: Native 5-layer decomposition engine.
  - `core/jd_matcher.py`: Match rubric and gap scoring.
  - `modules/jd_analyst/`: Complete JD analyst pipeline (decoder, matcher, predictor, redflags, reporter).
  - `presentation/commands/jd_cmd.py`: CLI commands (`jd decode`, `jd match`, `jd report`).
- **OfferGet Internal Regression Tests**:
  - `tests/test_jd_decoder.py`
  - `tests/test_jd_matcher.py`
  - `tests/test_redflags.py`
  - `tests/test_report_generator.py`
- **Unabsorbed / Preserved Assets**:
  - Claude slash command configuration files.
  - Standalone prompt files (`prompts/interview-predictor.md`, `prompts/jd-decoder.md`, `prompts/match-score.md`).
  - Reference JD bank (`jd-bank/`) and report preview images (`docs/report-preview-*.png`).
- **Archival / Recovery Protocol**:
  ```bash
  git -C "E:\github\简历\job-description-skill" bundle create "job-description-skill_ae4c050.bundle" --all
  ```

