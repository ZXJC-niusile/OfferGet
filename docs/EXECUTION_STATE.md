# OfferGet Execution State & Handover Ledger

## 1. Product Objective & Active Milestone
- **Core Product Objective**:
  JD 拆解 → 用户事实整理 → 基于事实的简历建议 → 至少三道针对性问题 → 用户真实作答 → 一轮具体反馈。
  重点打磨：基于真实经历、岗位要求和证据边界的面试训练。
- **Active Milestone**:
  - `M1`: 把“全档案查词”收敛为有范围的事实判断（经历级作用域、否定/计划句式识别、移除出口豁免）。
  - `M2`: 将会话辅助函数接成真正可恢复的流程（多轮历史保留、严格指纹与答案校验、原子保存）。
  - `M3`: 问题与反馈贴合岗位（运营/业务岗位自适应、禁止姓名/学历作项目追问、短经历支持）。
   - `M4`: 独立验收与质量集对齐。
   - `M15`: 外部简历生态吸收后的公共契约收敛，优先统一画像、JD、答辩、渲染和投递跟踪边界；删除/归档工作暂停。

## 1.1 Current Architecture Convergence Snapshot (2026-09-22)
- **Profile SSOT**: `ProfileContext` now exposes explicit boundary projections for JD analyst, advisor matching, and resume rendering. Existing domain dataclasses remain compatibility projections, not independent facts. Factual defaults (grade, target_degree, 校园经历) completely removed to guarantee zero hallucination. Field aliases (`awards`, `honors`, `honors_awards`, `publications`, `papers`) normalized across tracks.
- **Defense SSOT**: `core.defense.simulator` is the sole unified engine; `core.defense_simulator` is a 100% backward-compatible facade; `core.services` directly routes to the canonical simulator; `FollowUpChain`, `EvidenceStatus`, and `RiskBasis` are cleanly shared.
- **JD Ingress**: `core.jd_compat.to_canonical()` is the universal ingress gateway for raw text, `Path`, dictionaries, legacy views, and canonical `DecodedJD`. Hardened against empty strings, blank whitespace, empty dicts, and non-list skill/requirement containers.
- **Resume Rendering**: Academic LaTeX, Typst, and HTML preview consume `ResumeViewModel` SSOT directly; hallucinated defaults ("算法架构师", "运营岗", "candidate@example.com", "+86 138-0000-0000", "架构 Owner") completely eliminated; compilation callers wrapped with fail-safe error handling.
- **Application Tracking**: `ApplicationStore` persists lifecycle history, evidence snapshots, offer details, and collision risk with SQLite `PRAGMA user_version` migrations (v1 schema). `AppStatus` provides canonical coercion (`from_string`) and bidirectional mapping with collision guard.
- **Academic Truth Boundary**: Personal statements and advisor outreach strictly avoid fabricated awards, rank claims, first-author claims, and project ownership claims; generated factual text passes through `FactVerificationGuard`.
- **Verification at this snapshot**: `tests/` 493/493 passed (100%); `ApexResume/tests/` 34/34 passed (100%); `tests/test_architecture_convergence.py` 6/6 passed; `tests/test_architecture_negative.py` 5/5 passed; `python cli.py selftest` 11/11 passed; `git diff --check` clean (0 errors).
- **Known next work**: Proceed to Stage 2: absorb applyr core assets (Evidence Graph state machine, immutable historical scoring snapshots, unified application schema).

## 2. Baseline & Code Snapshot
- **Repository Root**: `E:/github/OfferGet`
- **Baseline HEAD**: `c9a9a2cd0812544f0244280b85c67e7b219d9108` (PR #4 head, merged at `377814fde14c98900472feea60a77abeb59092a4`)
- **Python Runtime**: 3.13.11 (win32)
- **Chrome Path**: `C:\Program Files\Google\Chrome\Application\chrome.exe`

## 3. Issue Ledger

| issue_id | priority | code_location | user_impact | evidence_grade | owner | status | acceptance_test | log_or_artifact |
|:---|:---:|:---|:---|:---:|:---:|:---:|:---|:---|
| `ISSUE-01` | P0 | `core/fact_guard.py`, `core/job_flow.py`, `tests/test_career_review.py:371` | 简历改写在数值保持 20% 时，无依据注入 `Megatron-LM` 与通信算子重构被误判为 verified 并应用 | CODE_CONFIRMED | Subagent A / Primary | RESOLVED | `tests/test_career_review.py:test_18`, `tests/test_fact_guard.py:test_11-13` | `core/fact_guard.py` |
| `ISSUE-02` | P0 | `core/interview_debrief.py:88` | 候选人答案中去除未核验数字后，系统自动补造“进行结构化优化”伪造动作 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_02` | `core/interview_debrief.py` |
| `ISSUE-03` | P1 | `core/interview_debrief.py:49,154` | `verification_status` 默认为 `"verified"`，未经充分核验即被标为已核验 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_03` | `core/interview_debrief.py` |
| `ISSUE-04` | P1 | `core/interview_debrief.py:53,231` | `refined_answer` 为空时用 `coaching_advice` 充当回答，混淆指导建议与口头回答 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_04` | `core/interview_debrief.py` |
| `ISSUE-05` | P1 | `core/interview_debrief.py:198` | 包含“没做过”等边界词时整段跳过事实检查，导致“没做过A但做了B提升50%”中的B逃避核验 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_05` | `core/interview_debrief.py` |
| `ISSUE-06` | P1 | `core/interview_debrief.py:147` | 任意技术词即可命中相关性，导致答非所问被误判为切题 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_06` | `core/interview_debrief.py` |
| `ISSUE-07` | P1 | `core/interview_debrief.py:171` | 回答字数超过 80 字即可绕过不相关检查，直接被判定为 WELL_DEFENDED | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_07` | `core/interview_debrief.py` |
| `ISSUE-08` | P1 | `core/interview_debrief.py:150,151` | 单个字母 `'s'` 或中文 `'从'` 误触发指标和基线判断 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_08` | `core/interview_debrief.py` |
| `ISSUE-09` | P1 | `core/job_flow.py` | 面试题目按 idx 机械分配标签，缺乏题目意图与统一岗位要求-证据映射 | CODE_CONFIRMED | Subagent B / Primary | RESOLVED | `tests/test_career_review.py:test_21` | `core/job_flow.py` |
| `ISSUE-10` | P1 | `core/job_flow.py` | 会话管理未接入真实 CLI 入口，缺乏可恢复的最小本地会话状态机 | CODE_CONFIRMED | Subagent B / Primary | RESOLVED | `tests/test_career_review.py:test_22,test_23` | `core/job_flow.py`, `core/services.py`, `presentation/commands/review_cmd.py`, `cli.py` |
| `R4-01` | P0 | `core/fact_guard.py` | 全档案查词导致技能清单/项目A的技术被借用到项目B，或将否定/计划误当成已完成经历 | CODE_CONFIRMED | Subagent A (`a560e526`) | RESOLVED | `tests/test_fact_guard.py:test_14-16` | `core/fact_guard.py` |
| `R4-02` | P0 | `core/interview_debrief.py` | 修订结果只剩 tech_method 时被 verified_with_tech_context 豁免，放行肯定陈述中新增的技术 | CODE_CONFIRMED | Subagent B (`f7633838`) | RESOLVED | `tests/test_interview_debrief.py:test_r4_02_*` | `core/interview_debrief.py` |
| `R4-03` | P1 | `core/interview_debrief.py` | 保守修订武断断定“没有基线压测数据”并保留未核验的主导动词与因果归因 | CODE_CONFIRMED | Subagent B (`f7633838`) | RESOLVED | `tests/test_interview_debrief.py:test_r4_03_*` | `core/interview_debrief.py` |
| `R4-04` | P0 | `core/job_flow.py`, `presentation/commands/review_cmd.py` | `--session` 加载后未传入恢复路径导致重出题、旧答案/反馈丢失，校验失败未非零退出 | CODE_CONFIRMED | Primary Agent | RESOLVED | `tests/test_career_review.py:test_24,test_25` | `core/job_flow.py`, `presentation/commands/review_cmd.py` |
| `R4-05` | P1 | `core/job_flow.py` | Q1 对非技术岗位机械要求架构/高并发；Q2 无实体经历时回退到 claims[0] 引用姓名/学位 | CODE_CONFIRMED | Primary Agent | RESOLVED | `tests/test_career_review.py:test_26` | `core/job_flow.py` |

## 4. Subagent Delegation Ledger

| task_id | native_agent_id | role | target_files (whitelist) | dependencies | status | deliverables |
|:---|:---|:---|:---|:---|:---:|:---|
| `TASK-A01` | subagent-fact-consistency | Subagent A: Fact & Data Consistency | `core/fact_guard.py`, `core/profile_adapter.py`, `tests/test_fact_guard.py`, `tests/test_career_review.py` | None | VERIFIED | Non-metric hallucination detection, ResumePatch validation, grounding tests |
| `TASK-B01` | subagent-interview-quality | Subagent B: Interview Quality | `core/interview_debrief.py`, `tests/test_interview_debrief.py` | None | VERIFIED | Remove fabricated actions, separate coaching from answer, fix boundary/relevance/metric regex |
| `TASK-B02` | primary-agent | Primary Agent: Question Grounding & Session Loop | `core/job_flow.py`, `core/services.py`, `presentation/commands/review_cmd.py`, `cli.py`, `tests/test_career_review.py` | TASK-A01, TASK-B01 | VERIFIED | 3 fixed dimension questions, session save/load/validate, CLI flags --session/--save-session |
| `TASK-A02` | `a560e526-5230-4a4e-bd73-6d8e4e136782` | Fact & Scope Grounding Auditor | `core/fact_guard.py`, `tests/test_fact_guard.py` | None | VERIFIED | 经历级作用域索引、否定与规划句式排除、verify_bullet(target_scope=...) |
| `TASK-B03` | `f7633838-e53d-4e47-a736-6d11cf1ca7e1` | Interview Feedback & Revision Auditor | `core/interview_debrief.py`, `tests/test_interview_debrief.py` | None | VERIFIED | 移除出口豁免、否定语境保护、主导动词与因果归因降级、客观未提供基线口径 |
| `TASK-R01` | `3fcba67f-63b4-482a-b611-a096f49e456b` | Independent Verification & Anti-example Auditor | Read-only across workspace | TASK-A02, TASK-B03 | VERIFIED | 独立反例验证全通、发现并推动修复 job_flow 变量作用域回归与负向语境介词增强 |

## 5. Verification Results & Layered Snapshots
- **M0 Baseline Snapshot**: `patches/uncommitted_pr4_fixes.patch` (114,152 bytes, 105,087 chars, SHA-256 `57cd1272b6f75795cd0fa04f117f1d4c94ba85a2ae68d3c1a44ca759aac82133`).
  - Covers 7 PR4 business & test files: `core/fact_guard.py`, `core/interview_debrief.py`, `core/job_flow.py`, `presentation/commands/review_cmd.py`, `tests/test_career_review.py`, `tests/test_fact_guard.py`, `tests/test_interview_debrief.py` (+ `docs/EXECUTION_STATE.md`).
- **M1 Incremental Snapshot**: `patches/m1_incremental.patch` (23,629 bytes, 23,072 chars, SHA-256 `313a83e89a530b6e5f84211a6e5b38d7e66a95a6a12df75d762961f2665397c0`).
  - Covers 6 M1 files: `core/ats_checker.py`, `core/services.py`, `tests/test_ats_checker.py`, `tests/test_services_and_router.py`, `tests/test_jd_compat.py`, `tests/test_registry.py`.
- **M2 Incremental Snapshot**: `patches/m2_asu_absorption.patch` (125,497 bytes, SHA-256 `8bb355d6f3067257666a1a8b8e5f0539140cc9ca242a8aebe8f2fc88d321c1b1`).
  - Covers M2 files: `core/evidence/` (models.py, metrics.py, extractor.py, auditor.py, schema.py, __init__.py), `core/fact_guard.py`, `tests/test_evidence_models.py`, `tests/test_evidence_metrics.py`, `tests/test_evidence_auditor.py`.
- **M3 Incremental Snapshot**: `patches/m3_defense_absorption.patch` (79,161 bytes, SHA-256 `43103210dd9eb13ff18588d48e1e01e39cbf98551828ad404c371bd1dbc910ff`).
  - Covers M3 files: `core/defense/` (models, rubrics.py, chain.py, evaluator.py, __init__.py), `core/interview_debrief.py`, `core/job_flow.py`, `tests/test_defense_rubrics.py`, `tests/test_defense_chain.py`, `tests/test_defense_evaluator.py`.
- **M4 Incremental Snapshot**: `patches/m4_registry_unification.patch` (41,905 bytes, SHA-256 `6b5184a5aa7562ab6507842bad42909e66d4bd201b3348bf3cf4a3398c496dee`).
  - Covers M4 files: `core/registry.py` (QualityRuleRegistry SSOT unification), `core/lexicon.py` (complete re-export parity), `ApexResume/core/audit.py` (dynamic SSOT import), `core/validator.py`, `core/ats_checker.py`, `core/baoyan_auditor.py`, `tests/test_registry.py`.
- **M5 Incremental Snapshot**: `patches/m5_jd_decision_absorption.patch` (7,900 bytes, SHA-256 `1a546e214f28c0ac9ae83c3acac33c41d5242c18cb14c81fd4431966006ae348`).
  - Covers M5 files: `core/jd_decision.py`, `core/jd_compat.py`, `core/services.py`, `tests/test_jd_decision.py`.
- **M6 Incremental Snapshot**: `patches/m6_ats_docx_absorption.patch` (1,451 bytes, SHA-256 `2ddd508c9de29ccc4031e270a0baddd61b4cd5fb41597c68ba0e94986808d08b`).
  - Covers M6 files: `core/ats_docx_renderer.py`, `core/resume_builder.py`, `tests/test_ats_docx.py`.
- **M7 Incremental Snapshot**: `patches/m7_cn_rubrics_absorption.patch` (2,089 bytes, SHA-256 `bba6ab46744c2b4206376b4a78735c3999b6e7490bbf1ff42187fb27eb0edbc2`).
  - Covers M7 files: `core/cn_rubrics.py`, `core/services.py`, `tests/test_cn_rubrics.py`.
- **M8 Incremental Snapshot**: `patches/m8_baoyan_package.patch` (916 bytes, SHA-256 `ce53361cda7b380e4d57b5ec170df07659ca78b485f54b154c98d74f9788959d`).
  - Covers M8 files: `core/baoyan_package.py`, `core/services.py`, `tests/test_baoyan_package.py`.
- **M10-M14 Incremental Snapshot**: `patches/m10_m14_convergence.patch` (104,422 bytes, SHA-256 `7d2bcde081a59133605f69fcf38d6a08c0ad1356ab201448645c8aa192021465`).
  - Covers M10-M14 files: `core/offer_comparator.py`, `core/communication_kit.py`, `core/post_interview.py`, `core/duplicate_guard.py`, `core/academic_sync.py`, `core/services.py`, `core/resume_builder.py`, `tests/test_offer_comparator.py`, `tests/test_communication_kit.py`, `tests/test_post_interview.py`, `tests/test_duplicate_guard.py`, `tests/test_academic_sync.py`, `tests/test_services_and_router.py`.
- **M0-M14 Governance Artifacts (Untracked)**: `patches/` (10 patches), `docs/repos_inspection.json`.
- **Current Verified Test Counts (2026-09-21 Session)**:
  - `tests/test_offer_comparator.py`: 3/3 passed
  - `tests/test_communication_kit.py`: 7/7 passed
  - `tests/test_post_interview.py`: 4/4 passed
  - `tests/test_duplicate_guard.py`: 5/5 passed
  - `tests/test_academic_sync.py`: 2/2 passed
  - `tests/test_services_and_router.py`: 14/14 passed
  - `tests/test_defense_rubrics.py`: 4/4 passed
  - `tests/test_defense_chain.py`: 6/6 passed
  - `tests/test_defense_evaluator.py`: 6/6 passed
  - `tests/test_evidence_models.py`: 5/5 passed
  - `tests/test_evidence_metrics.py`: 18/18 passed
  - `tests/test_evidence_auditor.py`: 9/9 passed
  - `tests/test_fact_guard.py`: 16/16 passed
  - `tests/test_interview_debrief.py`: 16/16 passed
  - `tests/test_career_review.py`: 26/26 passed
  - `tests/test_ats_checker.py`: 25/25 passed
  - `tests/test_ats_docx.py`: 3/3 passed
  - `tests/test_jd_compat.py`: 10/10 passed
  - `tests/test_jd_decision.py`: 8/8 passed
  - `tests/test_cn_rubrics.py`: 8/8 passed
  - `tests/test_baoyan_package.py`: 4/4 passed
  - `tests/test_architecture_convergence.py`: 6/6 passed
   - `tests/test_architecture_negative.py`: 6/6 passed
   - `tests/test_applyr_absorption.py`: 13/13 passed
   - `tests/` (full OfferGet suite): **507/507 passed** (0 failed, exit code 0)
  - `ApexResume/tests/`: **34/34 passed** (0 failed, exit code 0)
  - `python cli.py selftest`: **11/11 passed** (0 failed, exit code 0)
  - `git diff --check`: **0 errors** (clean whitespace & line formatting)
- External repos in `E:\github\简历`: 26 repositories untouched, 0 files deleted/modified.

## 1.2 Stage 2 Applyr Asset Absorption Snapshot (2026-09-22)
- **Evidence Graph State Machine**: Absorbed ADR-011 finite state machine from `applyr` into `core.evidence.graph` (`EvidenceNodeState`: DRAFT -> VERIFIED -> GROUNDED -> USED_IN_RESUME -> INTERVIEW_DEFENDED / INVALIDATED). Linear monotonic progression enforced; audit snapshot generation with content hash; `can_apply()` gate ensures zero ungrounded/invalidated claims reach the application phase.
- **Immutable Evidence & Scoring Snapshot**: `create_evidence_snapshot()` in `core/application_tracker.py` captures exact profile & JD SHA-256 fingerprints, ATS score, match score, gap matrix, and evidence graph audit trails for zero-drift auditability.
- **Persistent Application Schema v2**: `ApplicationStore` upgraded to `PRAGMA user_version = 2` with idempotent forward migration adding `target_level`, `portal_url`, `recruiter_contact`. `ApplicationRecord` models unified application targets across enterprise and academic tracks.
- **Verification before post-audit hardening**: `tests/test_applyr_absorption.py` (9/9 passed), full `tests/` (502/502 passed, 100%), `ApexResume/tests/` (34/34 passed), `python cli.py selftest` (11/11 passed), `git diff --check` (0 errors).
- **Post-audit hardening**: EvidenceGraph now rejects empty/duplicate claims, exposes defensive node copies, blocks verified-but-ungrounded application claims, prevents failed defense mutations, normalizes canonical/legacy matcher score units, and closes SQLite connections when future schema versions are rejected.
- **Post-audit verification**: `tests/test_applyr_absorption.py` 13/13, `tests/test_architecture_negative.py` 6/6, full `tests/` 507/507, `ApexResume/tests/` 34/34, and `python cli.py selftest` 11/11 passed; `git diff --check` clean.

## 1.3 Stage 3 Evidence-Graph Mainline Integration (2026-09-23)
- **Profile projection**: `EvidenceGraph.from_profile_context()` converts the shared `ProfileContext.claims` index into a scoped graph. Claims with verified metrics become `VERIFIED`; claims with an explicit experience/project role scope become `GROUNDED`.
- **Career Review integration**: `run_career_review()` now emits `evidence_graph`, `evidence_gate`, and `evidence_snapshot`. Resume advice references are promoted only when the corresponding graph claim is verified, grounded, and selected for the resume.
- **ResumePatch gate**: `generate_tailored_profile_from_review()` accepts an optional `EvidenceGraph` and rejects patches without a selected `USED_IN_RESUME`/`INTERVIEW_DEFENDED` claim, while preserving the legacy standalone API when no graph is supplied.
- **Application persistence**: `ApplicationStore.attach_evidence_snapshot()` persists the career-review snapshot into the application record for later audit/export.
- **Verification at this snapshot**: `tests/test_career_review.py` 27/27, `tests/test_applyr_absorption.py` 13/13, `tests/test_architecture_negative.py` 6/6, full `tests/` 508/508, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Known next work**: expose an explicit CLI command to attach a review snapshot to an application ID; add proposal/HITL semantics before accepting any generated material mutation; do not treat `evidence_gate` as a replacement for user confirmation.

## 1.4 Stage 4 Material Proposal / HITL Boundary (2026-09-23)
- **Proposal contract**: `core/material_proposal.py` adds `MaterialProposal` with `DRAFT`, `ACCEPTED`, `REJECTED`, and `CONFLICTED` states, deterministic source fingerprints, proposal hash, partial patch acceptance, and source drift detection.
- **Career Review output**: `run_career_review()` now emits a draft `material_proposal`; rejected or evidence-blocked patches are excluded from the proposal.
- **Confirmed application**: `apply_material_proposal()` validates source fingerprints and the previous target text, then returns a new profile copy without modifying the original profile.
- **Verification**: `tests/test_material_proposal.py` 4/4 passed; full `tests/` 512/512 passed; `git diff --check` clean.
- **Known next work**: expose proposal accept/reject through a CLI/service command and persist proposal records with idempotency before connecting them to automatic resume rendering.

## 1.5 Stage 5 Proposal Persistence and CLI HITL (2026-09-23)
- **Persistent proposals**: `ApplicationStore` schema v3 adds `material_proposals`; proposal records retain source fingerprints, patch payloads, status, accepted patch indexes, and conflict reason.
- **CLI**: added `offerget proposal show|accept|reject`. `review --proposal-db <db>` persists a generated draft. `proposal accept` requires current `--profile` and `--jd`, checks drift, and writes a new profile via `--output`.
- **Safety**: accepting a proposal never overwrites the source profile; rejected/conflicted proposals cannot be silently applied; partial patch acceptance is supported.
- **Verification**: full `tests/` 514/514, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Known next work**: add an application-id relation and proposal listing/filtering, then add service-level API support before any automatic resume rendering integration.

## 1.6 Stage 6 Proposal Tracking and Confirmed Rendering (2026-09-23)
- **Application relation**: Proposal persistence upgraded to Schema v4 with optional `application_id`; proposals can be filtered by application and status.
- **CLI**: added `offerget proposal list`; `review --application-id` attaches a proposal to an application; `proposal accept` can optionally run `--build-resume --resume-theme ...` after writing the new profile.
- **Safety**: rendering occurs only after explicit proposal acceptance and uses the newly generated profile copy; source profile remains untouched.
- **Verification**: full `tests/` suite and proposal persistence tests pass; CLI parser exposes `show/list/accept/reject`.
- **Known next work**: add a higher-level application command to create/link records and service-layer proposal APIs for non-CLI callers.

## 1.7 Stage 7 Persistent Application Workbench CLI (2026-09-23)
- **Application CLI**: added `offerget application add|list|show|status|snapshot`, backed by `ApplicationStore`, with lifecycle history and evidence snapshot output.
- **Workflow**: Proposal `application_id` can now point to a record created by the application CLI, completing the local flow from application intake to material confirmation.
- **Verification**: added `tests/test_application_cli.py`; full `tests/` suite passes, CLI help and a real temporary SQLite lifecycle were exercised successfully.
- **Known next work**: add service-level APIs for the same operations and enforce proposal/application existence checks when attaching an ID.

## 1.8 Stage 8 Strong Proposal/Application Association (2026-09-23)
- **Association validation**: persisting a Proposal with an `application_id` now fails if the application record does not exist.
- **Filtering**: `proposal list` supports `--status`, `--application-id`, `--company`, and `--role` filters.
- **Service layer**: added `ProposalService` for non-CLI callers to save, list, accept, reject, and persist new profile output.
- **Verification**: full `tests/` 515/515, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Known next work**: add application-linked proposal summaries to the application detail output and build a small end-to-end smoke fixture for proposal accept plus resume rendering.

## 1.9 Stage 9 End-to-End Application Review Smoke (2026-09-23)
- **Application detail**: `application show` now includes linked Proposal summaries (`get_application_detail`).
- **Review flow**: `review` validates `--application-id` and writes the evidence snapshot to the linked application.
- **End-to-end smoke**: added `tests/test_application_review_smoke.py` covering application creation, proposal persistence, linked detail lookup, explicit Proposal acceptance, new Profile output, resume PDF rendering, and evidence snapshot persistence.
- **Fix**: `apply_material_proposal` now supports append patches (`bullets[i]` with i == len) and marks stale targets as CONFLICTED instead of raising.
- **Verification**: full `tests/` 516/516, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Known next work**: consolidate the uncommitted work into a reviewed commit, then continue absorbing `offerPilot` interview-review proposal patterns and re-evaluate external project deletion.

## 1.10 Stage 10 In-Repo Consistency & Service Hardening (2026-09-24)
- **Selftest**: normalized stage counters to a single `[n/11]` denominator (previously `/6`, `/8`, `/11` mixed).
- **Service layer**: `ProposalService` now persists `CONFLICTED` state when acceptance fails (matching CLI behavior) and supports `with ProposalService(...)` context usage.
- **Docs**: `SKILL.md` CLI Quickstart documents `application` and `proposal` command groups and refreshes test counts (516→518, 203→552 stale values fixed).
- **Import order**: `cli.py` and `core/__init__.py` new symbols placed in alphabetical order.
- **Tests**: added `TestProposalService` covering service roundtrip, context manager, `KeyError` on unknown IDs, and conflict persistence.
- **Verification**: full `tests/` 518/518, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Source path correction**: the external repository directory is available at `D:\User Hub\GitHub\简历\` (26 repositories). The earlier E: drive check was correct, but the conclusion that the source was unavailable was mistaken; the folder's garbled name in terminal output was `简历`. External projects remain unmodified.
- **Known next work**: obtain explicit commit authorization to consolidate the uncommitted work; continue with offerPilot interview-review proposal patterns; optionally extend `application show` with lifecycle history timeline rendering.

## 1.12 Stage 12 Evidence-Grounded Interview Review Contract (2026-09-24)
- **Codebase comparison**: OfferGet already has interview diagnosis/revision (`core/interview_debrief.py`), transcript review (`core/post_interview.py`), and fact guard. The non-duplicate gap was strict structured review payload validation and proof that evidence excerpts exist in the frozen interview note.
- **Absorbed pattern**: adapted offerPilot's evidence-ref contract: exact payload fields, unique IDs, bounded list/reference counts, whitelisted note paths, source labels, excerpt matching, and a fixed safe-empty fallback. No model/provider or SQLAlchemy dependency was added.
- **Implementation**: added `core/interview_review_contract.py` with snapshot construction and deterministic proposal validation.
- **Tests**: `tests/test_interview_review_contract.py` covers snapshot whitelisting, valid evidence, forged excerpts/paths, duplicate IDs, unexpected fields, collection bounds, and safe fallback behavior.
- **Verification**: full `tests/` 529/529, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.

## 1.13 Stage 13 RenderCV JSON Interoperability (2026-09-24)
- **Source comparison**: RenderCV (MIT) uses a typed root model (`cv`, `design`, `locale`, `settings`) with section entries; OfferGet already owns the canonical Profile and rendering pipeline.
- **Implementation**: added dependency-free `core/rendercv_adapter.py` for common identity, social links, experience, education, projects, skills, and publications mappings.
- **Loss boundary**: unsupported RenderCV sections are preserved under `rendercv_import_metadata` and reported as warnings; YAML is intentionally rejected by the adapter unless converted to JSON by RenderCV, avoiding an extra parser dependency.
- **CLI**: added `rendercv import` and `rendercv export`; this is a data interchange layer, not a second resume renderer.
- **Tests**: added adapter round-trip, unsupported-section, invalid-shape, JSON path, file-write, and CLI smoke coverage.
- **Verification**: full `tests/` 534/534, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Known next work**: compare SigmaCV's application-facing schema and decide whether its job-specific resume version metadata adds value beyond current MaterialProposal/ApplicationStore.

## 1.14 Stage 14 Application-Linked Resume Versions (2026-09-24)
- **Source comparison**: SigmaCV's strongest reusable pattern is freeze-time content hashing and immutable snapshot metadata, not its web/publication infrastructure.
- **Implementation**: added `ResumeVersion` and SQLite Schema v6 `resume_versions` table. Metadata includes application/proposal links, Profile/JD hashes, theme, output paths, label, creation time, and deterministic version ID.
- **Workflow integration**: `proposal accept` now registers a version after writing the new Profile and optional rendered files; `application show` includes `resume_versions`.
- **Integrity boundary**: linked versions require an existing application; duplicate exact writes replay; same ID with different content is rejected. The Profile document remains outside the database and is never mutated in place.
- **Tests**: added schema migration, round-trip, orphan-link, collision, and end-to-end detail assertions.
- **Verification**: full `tests/` 537/537, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Known next work**: add a human-readable `application versions` CLI view and compare SigmaCV's provenance/diff semantics before expanding the version model.

## 1.15 Stage 15 Resume Version Query and Metadata Diff (2026-09-24)
- **CLI**: added `application versions [APPLICATION_ID]` and `application version-diff BEFORE_VERSION_ID AFTER_VERSION_ID`.
- **Diff boundary**: compares only persisted metadata, Profile/JD hashes, theme, labels, and output-path changes. It explicitly returns `content_diff_available: false` because the current store does not retain Profile snapshots.
- **Service**: added `ResumeVersionService` for list/get/compare operations.
- **Tests**: added deterministic metadata diff assertions and CLI list coverage.
- **Verification**: full `tests/` 538/538, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
- **Known next work**: only add content-level Profile diffs if the user explicitly wants snapshot retention; otherwise keep hash-only comparison to avoid silently expanding personal-data persistence.

## 1.16 Stage 16 Real CLI End-to-End Acceptance (2026-09-25)
- **Temporary database flow**: verified `application add` → `review --proposal-db --application-id` → `proposal list` → `proposal accept --build-resume` → `application show` → `application versions` → `application outcome` → `application insights`.
- **Observed artifacts**: Proposal transitioned to `accepted`; tailored Profile, HTML, and PDF were written; one application-linked ResumeVersion was registered; one interview rejection outcome and two feedback tags were aggregated.
- **Isolation**: all acceptance artifacts were written under a temporary directory and no repository fixture or external resume project was modified.
- **Verification**: post-commit `tests/` 538/538 and the real CLI flow passed; working tree remained clean before this ledger-only update.

## 1.17 Stage 17 Application Detail Feedback View (2026-09-25)
- **Application detail**: `application show` now returns linked outcome feedback alongside Proposals and ResumeVersions.
- **Workflow**: the detail view can now expose the full local loop for one application: generated material, immutable output metadata, interview result, reflection, next action, and feedback tags.
- **Tests**: extended the end-to-end application smoke flow to record an outcome and verify it appears in `application show`.
- **Verification**: full `tests/` 538/538, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.

## 1.18 Stage 18 Proposal Artifact Integrity (2026-09-25)
- **Schema v7**: ResumeVersion now records `artifact_status`, `artifact_hashes`, and `accept_phase`.
- **Accept boundary**: `proposal accept` writes the Profile, renders optional outputs, inspects every registered artifact, and only registers a completed ResumeVersion when every artifact is present and readable.
- **Integrity**: artifact hashes use streaming SHA-256; missing/unreadable outputs are reported before ResumeVersion persistence.
- **Migration**: v6→v7 handles both existing `resume_versions` tables and legacy databases where that table is absent.
- **Tests**: added artifact hash/status and migration coverage; full `tests/` 540/540, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.

## 1.19 Stage 19 CLI Error Contract Convergence (2026-09-25)
- **Shared helper**: added `fail_cli`, a thin adapter over `exit_cli_error` that selects JSON or terminal output from command arguments.
- **Coverage**: Proposal, Application, and RenderCV command error paths now use stable `error_type` values and the same JSON envelope; text-mode behavior remains compatible.
- **Error types**: standardized not-found, invalid input, persistence, render/import/export, version lookup, and artifact validation failures.
- **Tests**: added JSON error assertions for Application and RenderCV commands.
- **Verification**: full `tests/` 542/542, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.

## 1.11 Stage 11 Application Outcome Feedback Loop (2026-09-24)
- **Source pattern**: adapted offerPilot's controlled outcome stages/results/feedback tags, outcome reflection fields, and aggregate feedback insights to OfferGet's SQLite `ApplicationStore`; no SQLAlchemy or source files were copied.
- **Schema v5**: added `application_outcomes` with deterministic content-derived idempotency keys and indexed application/time lookup.
- **Domain contract**: `OutcomeStage`, `OutcomeResult`, `FEEDBACK_TAGS`, and `OutcomeRecord` validate canonical values, accept documented Chinese aliases, deduplicate tags, and reject forged outcome IDs. Existing outcomes are immutable; exact replays are idempotent.
- **Store/service/CLI**: added record/list/insights operations and `ApplicationOutcomeService`; CLI commands are `application outcome`, `application outcomes`, and `application insights`.
- **Tests**: added migration, vocabulary, validation, orphan, idempotency, immutability, insight aggregation, service facade, and CLI coverage.
- **Verification**: full `tests/` 523/523, `ApexResume/tests/` 34/34, `python cli.py selftest` 11/11, `git diff --check` clean.
