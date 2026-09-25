# OfferGet 外部知识与仓库吸收治理总账 (Knowledge Absorption Ledger)
本文档为 `E:\github\简历\` 下全部 26 个外部仓库的吸收、留存、归档与安全门禁总账。
遵循最高治理原则：**“先统一底层契约，再逐个吸收，最后备份归档，确认后删除”**。
---
## 一、 治理底线与删除安全门禁 (Governance & Deletion Gates)
> [!IMPORTANT]
> **当前删除审批状态**: `delete-approved = 0`。
> 严禁在未获用户显式点名授权、未建立完整 Git Bundle、未通过 OfferGet 全量测试前移动或删除任何外部仓库。
> 全部 26 个外部仓库当前物理保存在 `E:\github\简历\`，完整无损。

任何外部项目若要进入归档或删除阶段，必须同时满足以下 **6 项安全准则**：
1. **规则与逻辑完整性**: 核心算法、规则、数据模型与事实边界已在 OfferGet 原生 Python 中实现，不再依赖外部脚本。
2. **资产去重与保留**: 独有资产（如题库、模板、评测集）已迁移至 OfferGet 或已正式确认无保留价值。
3. **零外部引用**: OfferGet 代码库内（含文档与测试）通过 `rg` 检索确认已无对源仓库物理路径的任何依赖。
4. **自动化测试对齐**: OfferGet 内部已建立针对性测试套件，全量测试 100% 通过且无回归。
5. **离线备份校验**: 已生成包含全部 refs 的完整 Git Bundle，且通过 `git bundle verify` 与 `list-heads` 校验。
6. **用户显式书面批准**: 获得用户针对该具体仓库的明确删除指令，且工作区无未提交修改（`King-of-Pigeon` 因存在未跟踪文件被永久拦截直至清理）。

---
## 二、 OfferGet 当前修改保护与测试基线 (OfferGet Baseline Freeze)
- **仓库根目录**: `E:/github/OfferGet`
- **工作区变更边界分层说明** (基于 `git status --short --branch` 严格核验):
  1. **用户原始未提交业务修复 (PR4 修复，7 个核心业务/测试文件)**:
     - 路径: `core/fact_guard.py`, `core/interview_debrief.py`, `core/job_flow.py`, `presentation/commands/review_cmd.py`, `tests/test_career_review.py`, `tests/test_fact_guard.py`, `tests/test_interview_debrief.py`
     - 保护快照: `patches/uncommitted_pr4_fixes.patch` (114,152 bytes, 105,087 chars, SHA-256 `57cd1272b6f75795cd0fa04f117f1d4c94ba85a2ae68d3c1a44ca759aac82133`)
  2. **M0 治理与审查产物**:
     - 文档: `docs/EXECUTION_STATE.md`, `docs/ABSORPTION_LEDGER.md`
     - 数据: `docs/repos_inspection.json` (26 个外部仓库机器可读审查元数据)
     - 保护快照: `patches/uncommitted_pr4_fixes.patch`
  3. **M1 内部公共层收敛与增量 (6 个核心实现与测试文件)**:
     - 路径: `core/ats_checker.py`, `core/services.py`, `tests/test_ats_checker.py`, `tests/test_services_and_router.py`, `tests/test_jd_compat.py`, `tests/test_registry.py`
     - 保护快照: `patches/m1_incremental.patch` (23,629 bytes, 23,072 chars, SHA-256 `313a83e89a530b6e5f84211a6e5b38d7e66a95a6a12df75d762961f2665397c0`)
  4. **M2 ASu-resume-skills 核心吸收**:
     - 路径: `core/evidence/` (models, metrics, extractor, auditor, schema, __init__), `core/fact_guard.py`, `tests/test_evidence_*`
     - 保护快照: `patches/m2_asu_absorption.patch` (125,497 bytes, SHA-256 `8bb355d6f3067257666a1a8b8e5f0539140cc9ca242a8aebe8f2fc88d321c1b1`)
  5. **M3 defense-beating-simulator 核心吸收**:
     - 路径: `core/defense/` (models, rubrics, chain, evaluator, __init__), `core/interview_debrief.py`, `core/job_flow.py`, `tests/test_defense_*`
     - 保护快照: `patches/m3_defense_absorption.patch` (79,161 bytes, SHA-256 `43103210dd9eb13ff18588d48e1e01e39cbf98551828ad404c371bd1dbc910ff`)
  6. **M4 QualityRuleRegistry 质量规则中心收敛**:
     - 路径: `core/registry.py`, `core/lexicon.py`, `ApexResume/core/audit.py`, `core/validator.py`, `core/ats_checker.py`, `core/baoyan_auditor.py`, `tests/test_registry.py`
     - 保护快照: `patches/m4_registry_unification.patch` (41,905 bytes, SHA-256 `6b5184a5aa7562ab6507842bad42909e66d4bd201b3348bf3cf4a3398c496dee`)
  7. **M5 job-description-skill 投递决策引擎吸收**:
     - 路径: `core/jd_decision.py`, `core/jd_compat.py`, `core/services.py`, `tests/test_jd_decision.py`
     - 保护快照: `patches/m5_jd_decision_absorption.patch` (7,900 bytes, SHA-256 `1a546e214f28c0ac9ae83c3acac33c41d5242c18cb14c81fd4431966006ae348`)
  8. **M6 ats-optimized-resume-agent-skill 单栏 DOCX 生成器吸收**:
     - 路径: `core/ats_docx_renderer.py`, `core/resume_builder.py`, `tests/test_ats_docx.py`
     - 保护快照: `patches/m6_ats_docx_absorption.patch` (1,451 bytes, SHA-256 `2ddd508c9de29ccc4031e270a0baddd61b4cd5fb41597c68ba0e94986808d08b`)
  9. **M7 resume-jd-optimizer-cn 中文企业招聘 4 大正交量表吸收**:
     - 路径: `core/cn_rubrics.py`, `core/services.py`, `tests/test_cn_rubrics.py`
     - 保护快照: `patches/m7_cn_rubrics_absorption.patch` (2,089 bytes, SHA-256 `bba6ab46744c2b4206376b4a78735c3999b6e7490bbf1ff42187fb27eb0edbc2`)
   10. **M8 baoyan-skills 保研资料包与自荐/套磁全流程吸收**:
      - 路径: `core/baoyan_package.py`, `core/services.py`, `tests/test_baoyan_package.py`
      - 保护快照: `patches/m8_baoyan_package.patch` (916 bytes, SHA-256 `ce53361cda7b380e4d57b5ec170df07659ca78b485f54b154c98d74f9788959d`)
   11. **M10-M14 核心业务能力综合收敛与剩余项目收束**:
      - 路径: `core/offer_comparator.py`, `core/communication_kit.py`, `core/post_interview.py`, `core/duplicate_guard.py`, `core/academic_sync.py`, `core/services.py`, `core/resume_builder.py`, `tests/test_offer_comparator.py`, `tests/test_communication_kit.py`, `tests/test_post_interview.py`, `tests/test_duplicate_guard.py`, `tests/test_academic_sync.py`, `tests/test_services_and_router.py`
      - 保护快照: `patches/m10_m14_convergence.patch` (104,422 bytes, SHA-256 `7d2bcde081a59133605f69fcf38d6a08c0ad1356ab201448645c8aa192021465`)
- **测试基线状态** (当前会话实测全量通过):
  - `tests/` (全仓测试): **482 passed** (退出码 0, 100% 通过)
  - `ApexResume/tests/`: **34 passed** (退出码 0, 100% 通过)
  - `python cli.py selftest`: **11/11 passed** (退出码 0, 100% 通过)
  - `git diff --check`: **0 errors** (代码格式与空白规范完全合规)

---
## 三、 26 仓库吸收状态总表 (Absorption Matrix)

| 源项目 | 规则已吸收 | 代码已吸收 | 测试已吸收 | 资产已吸收 | 可归档 | 可删除 | 处置分类 | Git Commit | 工作区状态 | 许可证 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `academic-homepage-cv-sync` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `9098872` | `CLEAN` | MIT |
| `Academic-Resume-Template` | 部分 | 否 | 部分 | 否 | 否 | 否 | `retained` | `11f74bf` | `CLEAN` | MIT |
| `academic-skills` | 部分 | 否 | 部分 | 否 | 否 | 否 | `retained` | `71e9c42` | `CLEAN` | MIT |
| `applyr` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `3796bb6` | `CLEAN` | Apache-2.0 |
| `ASu-resume-skills` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `f460582` | `CLEAN` | Apache-2.0 |
| `ats-optimized-resume-agent-skill` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `153209b` | `CLEAN` | MIT |
| `baoyan-resume-writing` | 是 | 部分 | 是 | 否 | 否 | 否 | `retained` | `31980bd` | `CLEAN` | CC-BY-NC-4.0 |
| `baoyan-skill` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `95a331a` | `CLEAN` | MIT |
| `baoyan-skills` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `1e88e5c` | `CLEAN` | MIT |
| `Chinese-resume-template-postgraduate` | 部分 | 否 | 部分 | 否 | 否 | 否 | `retained` | `9bf0063` | `CLEAN` | MIT |
| `defense-beating-simulator` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `d1f4682` | `CLEAN` | MIT |
| `job-description-skill` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `ae4c050` | `CLEAN` | MIT |
| `King-of-Pigeon` | 部分 | 否 | 部分 | 否 | 否 | 否 | `partial-absorption` | `915a33b` | **?? old_readme.md** | MIT |
| `latex-resume-template` | 部分 | 否 | 部分 | 否 | 否 | 否 | `retained` | `13fd88d` | `CLEAN` | MIT |
| `offerPilot` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `c0a447b` | `CLEAN` | GPL-3.0 |
| `PostInterviewAI` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `0500456` | `CLEAN` | MIT |
| `rendercv` | 是 | 否 | 是 | 否 | 否 | 否 | `retained` | `1d4b87b` | `CLEAN` | MIT |
| `rendercv-skill` | 是 | 否 | 是 | 否 | 否 | 否 | `retained` | `fc14e72` | `CLEAN` | MIT |
| `resume-assistant-mcp` | 是 | 否 | 是 | 否 | 否 | 否 | `retained` | `5b2badf` | `CLEAN` | MIT |
| `resume-jd-optimizer-cn` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `114c85c` | `CLEAN` | MIT |
| `resume-tailor-plugin` | 是 | 否 | 是 | 否 | 否 | 否 | `retained` | `a9eb11f` | `CLEAN` | MIT |
| `resume-toolkit` | 部分 | 否 | 部分 | 否 | 否 | 否 | `retained` | `ebbb5f0` | `CLEAN` | MIT |
| `resume-typst` | 部分 | 否 | 部分 | 否 | 否 | 否 | `retained` | `b9dec6b` | `CLEAN` | MIT |
| `ResumeSkills` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `74ae19e` | `CLEAN` | MIT |
| `sigmacv` | 是 | 否 | 是 | 否 | 否 | 否 | `retained` | `461227a` | `CLEAN` | AGPL-3.0 |
| `vanceling-skills` | 是 | 是 | 是 | 否 | 否 | 否 | `archive-candidate` | `5f4f042` | `CLEAN` | MIT |

### offerPilot outcome-feedback pattern absorption (2026-09-24)
- **Source**: `D:\User Hub\GitHub\简历\offerPilot\src\offerpilot\repositories\application_outcomes.py` (GPL-3.0 project; adapted the domain pattern, did not copy source code).
- **Absorbed pattern**: controlled outcome stages/results/feedback tags, replay-safe outcome writes, reflection and next-action fields, and cross-application feedback aggregation.
- **OfferGet implementation**: `core/application_tracker.py` (`OutcomeStage`, `OutcomeResult`, `FEEDBACK_TAGS`, `OutcomeRecord`, `ApplicationStore` schema v5) and `tests/test_application_outcomes.py`.
- **Boundary**: no SQLAlchemy dependency; outcomes are local SQLite records and require an existing application ID.

### offerPilot interview-review proposal contract absorption (2026-09-24)
- **Source**: `D:\User Hub\GitHub\简历\offerPilot\src\offerpilot\ai\interview_review_proposals.py` (GPL-3.0 project; adapted the evidence-validation pattern, no source copied).
- **Existing overlap**: OfferGet already had interview diagnosis, conservative answer revision, transcript analysis, and claim references in `core/interview_debrief.py` and `core/post_interview.py`.
- **Gap absorbed**: strict review payload shape, globally unique item IDs, bounded collection sizes, evidence-source/path allowlisting, frozen-note excerpt verification, and safe-empty fallback.
- **OfferGet implementation**: `core/interview_review_contract.py`; validation is deterministic and provider-independent.
- **Tests**: `tests/test_interview_review_contract.py` covers forged evidence, invalid paths, duplicate IDs, unexpected fields, size bounds, snapshot whitelisting, and empty-note fallback.

### RenderCV JSON interoperability absorption (2026-09-24)
- **Source**: `D:\User Hub\GitHub\简历\rendercv` (MIT; adapted the public data-model boundary, no renderer source copied).
- **OfferGet implementation**: `core/rendercv_adapter.py` plus `presentation/commands/rendercv_cmd.py`.
- **Supported mapping**: identity/social links, experience, education, projects, skills, and publications between RenderCV JSON and the canonical OfferGet Profile.
- **Boundary**: unsupported sections are retained in `rendercv_import_metadata` with warnings; YAML parsing and rendering remain owned by RenderCV and are not duplicated.
- **Tests**: `tests/test_rendercv_adapter.py`; full suite verified at 534 tests.

### SigmaCV frozen resume-version pattern absorption (2026-09-24)
- **Source**: `D:\User Hub\GitHub\简历\sigmacv\src\lib\cv\snapshotHash.ts` and `snapshots.ts` (AGPL-3.0 project; adapted the content-hash and immutable metadata pattern, no source copied).
- **OfferGet implementation**: `ResumeVersion` and `ApplicationStore` Schema v6 `resume_versions` table; Proposal acceptance registers generated Profile/render outputs against the application.
- **Boundary**: only local metadata and deterministic hashes are absorbed; SigmaCV's account, public-page, database, research, and web infrastructure are not imported.
- **Tests**: `tests/test_resume_versions.py` and end-to-end application review smoke coverage.
- **Follow-up**: added metadata-only version listing and diff (`core/resume_version_diff.py`, `application versions`, `application version-diff`); content-level Profile diff remains intentionally unavailable without explicit snapshot-retention scope.

---
## 四、 核心候选项目文件级清单与资产拆分 (Candidate Project Dossiers)

### 4.1 `ASu-resume-skills`
- **Git Commit**: `f460582b1a48c7770496d7999ae3a14a2ce0452b`
- **工作区状态**: `CLEAN`
- **许可证**: `LICENSE` (Apache-2.0)
- **文件总数**: 36 个文件 (共 742,777 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 动词层级体系与强动词/弱动词字典 (`core/registry.py:VERB_HIERARCHY`)
- 简历 Bullet 事实核验与未锚定指标检测 (`core/fact_guard.py`)
- Bullet 结构完整性审计 (Action + Context + Metric) (`core/ats_checker.py`)
- **原子主张模型 (Atomic Claim Model)**: 主张与证据源路径映射、A/B/C/D 来源分层、Owner/Contributor/Core Author 角色边界 (`core/evidence/models.py`, `core/evidence/extractor.py`)
- **确定性指标复算**: 分子、分母、比例、基线、结果、变化类型 (相对变化/百分点) 容差计算 (`core/evidence/metrics.py`)
- **夸大模式防御分类**: 角色升格、全系统叙事/范围漂白、伪精确、没有比较全集的最高级 (`core/evidence/auditor.py`)
- **自包含审计报告规范**: 与 ASu `report-schema.md` 兼容的 JSON 结构与字段引用校验 (`core/evidence/schema.py`)
- **测试套件**: 移植并扩展 ASu 全部校验反例与单元测试 (`tests/test_evidence_models.py`, `tests/test_evidence_metrics.py`, `tests/test_evidence_auditor.py`)

#### 未吸收资产 (待收纳 / Pending Assets)
- **报告与简历 HTML/CSS 模板**: `skills/asu-resume-audit-skill/assets/report_template.html`, `skills/asu-resume-skill/assets/resume_template.html`
- **静态资源与样例**: `assets/asu-circle.png`, `assets/hr-intro-example.jpg`, `examples/asu-resume-audit-example.html`, `examples/asu-resume-example.html`
- **案例与文案参考**: `skills/asu-resume-audit-skill/references/asu-case-study.md`, `skills/asu-resume-audit-skill/references/education-branding-audit.md`
- **处置状态**: 核心代码与规则已吸收完毕；外部模板与示例资产标记为待收纳，进入归档观察期，保持 `delete-approved = 0`。


#### 文件级清单 (File-level Inventory)
```text
.codex-plugin\plugin.json                                    (   1,466 bytes)
.github\workflows\validate.yml                               (   2,209 bytes)
.gitignore                                                   (      87 bytes)
LICENSE                                                      (   1,088 bytes)
README.md                                                    (   7,009 bytes)
THIRD_PARTY_LICENSES\Hisn00w-ASu-skills-LICENSE              (   1,085 bytes)
assets\asu-circle.png                                        ( 220,325 bytes)
assets\hr-intro-example.jpg                                  ( 174,078 bytes)
examples\asu-resume-audit-example.html                       (  39,605 bytes)
examples\asu-resume-audit-example.pdf                        (  33,115 bytes)
examples\asu-resume-example.html                             (  37,985 bytes)
examples\asu-resume-example.pdf                              (  19,867 bytes)
examples\audit-report.example.json                           (  26,328 bytes)
examples\resume-data.example.json                            (  30,974 bytes)
skills\asu-resume-audit-skill\SKILL.md                       (  12,497 bytes)
skills\asu-resume-audit-skill\agents\openai.yaml             (     346 bytes)
skills\asu-resume-audit-skill\assets\report_template.html    (  18,861 bytes)
skills\asu-resume-audit-skill\evals\evals.json               (   1,605 bytes)
skills\asu-resume-audit-skill\references\asu-case-study.md   (   5,420 bytes)
skills\asu-resume-audit-skill\references\education-branding-audit.md (   2,241 bytes)
skills\asu-resume-audit-skill\references\evidence-methodology.md (   3,308 bytes)
skills\asu-resume-audit-skill\references\inflation-patterns.md (   3,364 bytes)
skills\asu-resume-audit-skill\references\open-source-audit.md (   3,624 bytes)
skills\asu-resume-audit-skill\references\report-schema.md    (   4,771 bytes)
skills\asu-resume-audit-skill\scripts\render_report.py       (  18,345 bytes)
skills\asu-resume-audit-skill\scripts\validate_report.py     (   7,710 bytes)
skills\asu-resume-skill\SKILL.md                             (   8,630 bytes)
skills\asu-resume-skill\agents\openai.yaml                   (     450 bytes)
skills\asu-resume-skill\assets\resume_template.html          (  15,728 bytes)
skills\asu-resume-skill\evals\evals.json                     (   2,052 bytes)
skills\asu-resume-skill\references\resume-schema.md          (   2,539 bytes)
skills\asu-resume-skill\references\style-guide.md            (   4,381 bytes)
skills\asu-resume-skill\scripts\render_resume.py             (  17,179 bytes)
skills\asu-resume-skill\scripts\validate_resume.py           (   6,960 bytes)
tests\test_validate_report.py                                (   5,222 bytes)
tests\test_validators.py                                     (   2,323 bytes)
```

### 4.2 `defense-beating-simulator`
- **Git Commit**: `d1f4682a65ebdcdb56ff644f279bb7aaec046ace`
- **工作区状态**: `CLEAN`
- **许可证**: `LICENSE` (MIT)
- **文件总数**: 41 个文件 (共 116,277 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 三级答辩质询强度分类 (gentle, standard, rigorous)
- 基础证据交叉比对与防守测试基线 (`tests/test_defense_simulator.py`)
- **材料支持状态与风险来源标签**: `EvidenceStatus` (Material-supported, Material-implied, Material-missing) 与 `RiskBasis` (Material-derived, Risk-inferred, Combined) (`core/defense/rubrics.py`)
- **九大薄弱维度 (Weakness Dimensions)**: 项目定位、技术深度、数据支撑、结果展示、个人贡献、创新表达、可复现性、风险表述、答辩安全性 (`core/defense/rubrics.py`)
- **2-4 层连续深度追问机制**: 数据真实性、个人贡献、项目边界、结果可靠性、创新点五大追问链与多角色语气适配 (`core/defense/chain.py`, `core/job_flow.py`)
- **100分制回答评分规则与五步稳妥应答框架**: 6 维度评分、过度承诺拦截与稳妥防守改写 (`core/defense/evaluator.py`, `core/interview_debrief.py`)
- **测试套件**: 16 个定向单元与集成测试 (`tests/test_defense_rubrics.py`, `tests/test_defense_chain.py`, `tests/test_defense_evaluator.py`)

#### 未吸收资产 (待收纳 / Pending Assets)
- **答辩模板与作弊条**: `assets/defense-cheatsheet.template.md`, `assets/weakness-report.template.md`, `assets/question-bank.template.md`, `assets/project-summary.template.md`
- **案例参考**: `examples/campus-energy-system/`, `examples/github-skill-review/`, `examples/yolo-pv-defect-detection/`
- **领域参考文档**: `references/domain-*.md`, `references/project-rubrics.md`, `references/question-patterns.md`
- **处置状态**: 核心代码与规则已吸收完毕；模板与参考资产标记为待收纳，进入归档观察期，保持 `delete-approved = 0`。


#### 文件级清单 (File-level Inventory)
```text
.github\workflows\validate.yml                               (   1,891 bytes)
.gitignore                                                   (     215 bytes)
AGENTS.md                                                    (   3,286 bytes)
CLAUDE.md                                                    (     822 bytes)
GEMINI.md                                                    (     760 bytes)
LICENSE                                                      (   1,084 bytes)
README.en.md                                                 (   6,728 bytes)
README.md                                                    (  11,028 bytes)
README.zh-CN.md                                              (      88 bytes)
SKILL.md                                                     (  11,301 bytes)
agents\openai.yaml                                           (     397 bytes)
assets\defense-cheatsheet.template.md                        (     775 bytes)
assets\project-summary.template.md                           (     984 bytes)
assets\question-bank.template.md                             (   1,332 bytes)
assets\weakness-report.template.md                           (   1,439 bytes)
evals\README.md                                              (   1,104 bytes)
evals\expected_checks.yaml                                   (   1,149 bytes)
evals\prompts.csv                                            (   2,674 bytes)
examples\campus-energy-system\expected-output-chat.md        (   4,370 bytes)
examples\campus-energy-system\expected-question-bank.md      (   1,007 bytes)
examples\campus-energy-system\expected-weakness-report.md    (   1,459 bytes)
examples\campus-energy-system\input-project-summary.md       (     904 bytes)
examples\github-skill-review\expected-output-chat.md         (   2,296 bytes)
examples\github-skill-review\input-readme.md                 (     642 bytes)
examples\yolo-pv-defect-detection\expected-defense-cheatsheet.md (   1,390 bytes)
examples\yolo-pv-defect-detection\expected-output-chat.md    (   4,110 bytes)
examples\yolo-pv-defect-detection\input-project-summary.md   (     708 bytes)
install.ps1                                                  (   3,875 bytes)
install.sh                                                   (   3,048 bytes)
pyproject.toml                                               (     736 bytes)
references\domain-ai-projects.md                             (   1,740 bytes)
references\domain-course-design.md                           (   1,289 bytes)
references\domain-engineering-simulation.md                  (   1,448 bytes)
references\domain-research-prototype.md                      (   1,322 bytes)
references\domain-web-showcase.md                            (   1,516 bytes)
references\project-rubrics.md                                (   6,549 bytes)
references\question-patterns.md                              (   3,913 bytes)
scripts\__init__.py                                          (      69 bytes)
scripts\evaluate_response.py                                 (   4,352 bytes)
scripts\validate_skill.py                                    (  15,526 bytes)
tests\test_skill_package.py                                  (   6,951 bytes)
```

### 4.3 `job-description-skill`
- **Git Commit**: `ae4c0506ca261befb09c049c66ca65184887aec6`
- **工作区状态**: `CLEAN`
- **许可证**: `NO_LICENSE_FILE`
- **文件总数**: 27 个文件 (共 35,430,268 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 5 层 JD 深度结构化解构 (`modules/jd_analyst/decoder.py`)
- 32 行业黑话/暗号翻译器与风险提示 (`modules/jd_analyst/redflags.py`)
- 显式评分矩阵与求职概率预测 (`modules/jd_analyst/predictor.py`)

#### 未吸收资产 (Unabsorbed Assets & Pending Capabilities)
- **Decode-before-match 流程门禁**: 强制先解码后匹配的流水线拦截 (计划在 M5 吸收)
- **Should I Apply 决策框架与 6 周行动计划** (计划在 M5 吸收)
- **JD Bank 与策略报告模板**: `jd-bank/`, `frameworks/offer-strategy-report.md`

#### 文件级清单 (File-level Inventory)
```text
.gitignore                                                   (     508 bytes)
README.md                                                    (   9,498 bytes)
README.zh.md                                                 (   8,834 bytes)
SKILL.md                                                     (  11,712 bytes)
docs\en\.gitkeep                                             (     128 bytes)
docs\en\demo.mp4                                             (15,990,005 bytes)
docs\en\openai-report.png                                    ( 589,602 bytes)
docs\en\preview.gif                                          (1,102,811 bytes)
docs\report-preview-en.png                                   ( 589,602 bytes)
docs\report-preview-zh.png                                   ( 407,274 bytes)
docs\zh\.gitkeep                                             (     112 bytes)
docs\zh\demo.mp4                                             (14,603,431 bytes)
docs\zh\openai-report.png                                    ( 629,955 bytes)
docs\zh\preview.gif                                          (1,346,021 bytes)
examples\offer-strategy-template.html                        (  54,639 bytes)
frameworks\decode-patterns.md                                (   6,402 bytes)
frameworks\go-no-go.md                                       (   5,950 bytes)
frameworks\match-rubric.md                                   (   5,607 bytes)
frameworks\offer-strategy-report.md                          (  24,155 bytes)
frameworks\resume-tailoring.md                               (   7,729 bytes)
jd-bank\_index.md                                            (   3,649 bytes)
jd-bank\_jd-template.md                                      (   3,033 bytes)
prompts\interview-predictor.md                               (   5,347 bytes)
prompts\jd-decoder.md                                        (   6,236 bytes)
prompts\match-score.md                                       (   5,282 bytes)
prompts\resume-tailor.md                                     (   5,713 bytes)
prompts\should-i-apply.md                                    (   7,033 bytes)
```

### 4.4 `ats-optimized-resume-agent-skill`
- **Git Commit**: `153209b510e6ca168ab50a6b0d4f19e380979d73`
- **工作区状态**: `CLEAN`
- **许可证**: `LICENSE`
- **文件总数**: 38 个文件 (共 372,314 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 四维 ATS 审计体系 (格式安全、关键词密度、时序规范、量化证据) (`core/ats_checker.py`)
- 排版风险模式检测 (表格、多栏、特殊字符) (`core/ats_checker.py`)

#### 未吸收资产 (Unabsorbed Assets & Pending Capabilities)
- **DOCX Schema 校验与渲染能力**: 单栏 ATS 规范 DOCX 输出 (计划在 M6 评估)
- **Master Resume + JD + Company 强类型输入契约** (计划在 M6 吸收)

#### 文件级清单 (File-level Inventory)
```text
.claude-plugin\marketplace.json                              (   1,049 bytes)
.claude-plugin\plugin.json                                   (     610 bytes)
.gitignore                                                   (     399 bytes)
LICENSE                                                      (   1,086 bytes)
PRIVACY.md                                                   (   1,572 bytes)
README.md                                                    (  41,979 bytes)
SKILL.md                                                     (  18,351 bytes)
bin\resume-skill                                             (   1,074 bytes)
bin\resume-skill.cmd                                         (     419 bytes)
install.ps1                                                  (   4,332 bytes)
install.sh                                                   (   4,084 bytes)
renderer\examples\output\alex_chen_no_skills.docx            (  39,213 bytes)
renderer\examples\output\alex_chen_stripe.docx               (  39,441 bytes)
renderer\examples\output\alex_chen_stripe_v2.docx            (  39,419 bytes)
renderer\examples\output\install_test.docx                   (  39,419 bytes)
renderer\examples\output\manual_install_test.docx            (  39,419 bytes)
renderer\examples\run_example.py                             (   4,750 bytes)
renderer\examples\sample_jd.md                               (   2,675 bytes)
renderer\examples\sample_master_resume.md                    (   4,675 bytes)
renderer\examples\sample_resume_json.json                    (   5,110 bytes)
renderer\pyproject.toml                                      (   1,041 bytes)
renderer\requirements.txt                                    (      33 bytes)
renderer\src\__init__.py                                     (       0 bytes)
renderer\src\cli.py                                          (   2,683 bytes)
renderer\src\main.py                                         (   2,953 bytes)
renderer\src\rendering\__init__.py                           (       0 bytes)
renderer\src\rendering\config.py                             (   5,179 bytes)
renderer\src\rendering\render_docx.py                        (  25,343 bytes)
renderer\src\schemas\__init__.py                             (       0 bytes)
renderer\src\schemas\resume_schema.py                        (   5,593 bytes)
renderer\src\utils\__init__.py                               (       0 bytes)
renderer\src\utils\utils.py                                  (     817 bytes)
renderer\src\validation\__init__.py                          (       0 bytes)
renderer\src\validation\validate_output.py                   (   7,087 bytes)
renderer\tests\__init__.py                                   (       0 bytes)
renderer\tests\test_rendering.py                             (   9,579 bytes)
renderer\tests\test_validation.py                            (   4,579 bytes)
skills\build-tailored-resume\SKILL.md                        (  18,351 bytes)
```

### 4.5 `resume-jd-optimizer-cn`
- **Git Commit**: `114c85c32dc77bc9ec7315976a21a1f761868664`
- **工作区状态**: `CLEAN`
- **许可证**: `LICENSE`
- **文件总数**: 70 个文件 (共 176,243 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 中文核心技能同义词别名注册表 (`core/registry.py:AliasRegistry`)
- 角色等级与伪从0到1夸大模式 (`core/registry.py:QualityRuleRegistry`)

#### 未吸收资产 (Unabsorbed Assets & Pending Capabilities)
- **覆盖度四态**: 已覆盖 / 弱覆盖 / 未覆盖 / 不建议硬凑 (计划在 M7 吸收)
- **三方审查机制**: HR视角、面试官视角、真实性底线视角 (计划在 M7 吸收)

#### 文件级清单 (File-level Inventory)
```text
.github\ISSUE_TEMPLATE\bug_report.yml                        (   1,532 bytes)
.github\ISSUE_TEMPLATE\feature_request.yml                   (   1,016 bytes)
.github\ISSUE_TEMPLATE\resume_case.yml                       (   1,534 bytes)
.github\PULL_REQUEST_TEMPLATE.md                             (     777 bytes)
.github\workflows\markdown-lint.yml                          (     457 bytes)
.gitignore                                                   (      71 bytes)
.markdownlint-cli2.jsonc                                     (     162 bytes)
CHANGELOG.md                                                 (     692 bytes)
CODE_OF_CONDUCT.md                                           (   1,087 bytes)
CONTRIBUTING.md                                              (   2,088 bytes)
FAQ.md                                                       (   2,674 bytes)
LICENSE                                                      (   1,085 bytes)
README.en.md                                                 (   2,695 bytes)
README.md                                                    (  12,956 bytes)
RELEASE_NOTES.md                                             (   4,558 bytes)
ROADMAP.md                                                   (   1,288 bytes)
SECURITY.md                                                  (   1,122 bytes)
SKILL.md                                                     (  11,450 bytes)
agents\openai.yaml                                           (     286 bytes)
assets\demo-before-after.md                                  (   3,751 bytes)
assets\demo-before-after.svg                                 (   5,037 bytes)
assets\screenshot-script.md                                  (   4,557 bytes)
docs\chinese_job_market_context.md                           (   1,918 bytes)
docs\examples.md                                             (   3,783 bytes)
docs\installation.md                                         (  14,561 bytes)
docs\metric_dictionary.md                                    (   3,099 bytes)
docs\privacy-and-truthfulness.md                             (   2,004 bytes)
docs\quickstart.md                                           (   8,351 bytes)
docs\resume_truthfulness_policy.md                           (   3,017 bytes)
docs\role_taxonomy.md                                        (  11,277 bytes)
docs\star-us.md                                              (     757 bytes)
docs\use-cases.md                                            (   1,894 bytes)
docs\workflow.md                                             (   4,501 bytes)
examples\demo_ai_product_transition.md                       (   5,605 bytes)
examples\demo_data_analyst.md                                (   4,947 bytes)
examples\demo_product_manager.md                             (   5,525 bytes)
examples\sample_final_report.md                              (   1,256 bytes)
examples\sample_jd_ai_product_manager.md                     (     462 bytes)
examples\sample_jd_data_analyst.md                           (     407 bytes)
examples\sample_jd_product_manager.md                        (     478 bytes)
examples\sample_resume_ai_product_manager_after.md           (   1,085 bytes)
examples\sample_resume_ai_product_manager_before.md          (     648 bytes)
examples\sample_resume_data_analyst_after.md                 (     917 bytes)
examples\sample_resume_data_analyst_before.md                (     594 bytes)
examples\sample_resume_product_manager_after.md              (   1,035 bytes)
examples\sample_resume_product_manager_before.md             (     783 bytes)
prompts\ats_checker.md                                       (   1,371 bytes)
prompts\experience_interviewer.md                            (   1,697 bytes)
prompts\final_report_generator.md                            (     916 bytes)
prompts\gap_analyzer.md                                      (   1,648 bytes)
prompts\hr_reviewer.md                                       (     897 bytes)
prompts\interview_question_generator.md                      (   1,251 bytes)
prompts\jd_parser.md                                         (     980 bytes)
prompts\resume_parser.md                                     (   1,806 bytes)
prompts\resume_rewriter.md                                   (   2,778 bytes)
prompts\risk_checker.md                                      (   1,161 bytes)
rubrics\ats_score.md                                         (     749 bytes)
rubrics\credibility_score.md                                 (     614 bytes)
rubrics\hr_score.md                                          (     809 bytes)
rubrics\interview_readiness_score.md                         (     598 bytes)
rubrics\jd_match_score.md                                    (   1,342 bytes)
templates\ats_plain_text_resume_template.md                  (   1,076 bytes)
templates\boss_intro_template.md                             (     450 bytes)
templates\headhunter_intro_template.md                       (     403 bytes)
templates\interview_story_template.md                        (     379 bytes)
templates\jd_match_report_template.md                        (     894 bytes)
templates\optimized_resume_template.md                       (     783 bytes)
tests\evaluation_checklist.md                                (   3,705 bytes)
tests\failure_modes.md                                       (   2,785 bytes)
tests\test_cases.md                                          (   7,372 bytes)
```

### 4.6 `baoyan-resume-writing`
- **Git Commit**: `31980bdde4c563efb67a6f3770b0b04272e711b6`
- **工作区状态**: `CLEAN`
- **许可证**: `LICENSE`
- **文件总数**: 12 个文件 (共 2,321,502 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 4 大保研学术诚信红线 (仿真造假、已投冒充已中、角色夸大、套话) (`core/baoyan_auditor.py`)
- 3 级字数自适应压缩引擎 (摘要版 40-60字, 简历版 80-110字, 陈述版 150-220字) (`core/baoyan_auditor.py`)

#### 未吸收资产 (Unabsorbed Assets & Pending Capabilities)
- 高校官方申请 Word 模板与表格排版资产 (独立保留)

#### 文件级清单 (File-level Inventory)
```text
LICENSE                                                      (   1,090 bytes)
README.md                                                    (   6,098 bytes)
SKILL.md                                                     (  15,041 bytes)
assets\banner.png                                            (2,260,593 bytes)
letter_template.md                                           (   3,123 bytes)
samples.md                                                   (   7,163 bytes)
scripts\build_letter.py                                      (   8,873 bytes)
scripts\build_resume_docx.py                                 (   2,954 bytes)
scripts\check_entry.py                                       (   4,686 bytes)
scripts\extract_material.py                                  (   4,229 bytes)
scripts\parse_professor.py                                   (   4,400 bytes)
scripts\redact_pii.py                                        (   3,252 bytes)
```

### 4.7 `baoyan-skill`
- **Git Commit**: `95a331a825b9c27b1040b2ae0c93cbbb3785bea6`
- **工作区状态**: `CLEAN`
- **许可证**: `LICENSE`
- **文件总数**: 48 个文件 (共 269,364 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 夏令营/预推免申请材料清单核验 (`core/baoyan_pipeline.py`)
- 学术履历状态机转换逻辑 (`core/baoyan_pipeline.py`)

#### 未吸收资产 (Unabsorbed Assets & Pending Capabilities)
- 高校通知爬虫 (`tools/notice_scraper.py`)、摄像头模拟练习 Web 门户 (`web/`) (独立保留)

#### 文件级清单 (File-level Inventory)
```text
.gitignore                                                   (     839 bytes)
LICENSE                                                      (   1,077 bytes)
README.md                                                    (   8,350 bytes)
SKILL.md                                                     (   7,017 bytes)
config\schools.yaml                                          (   6,069 bytes)
data\exam_topics.json                                        (   7,741 bytes)
data\experiences\.gitkeep                                    (       0 bytes)
data\feedback\.gitkeep                                       (       0 bytes)
data\hnu_courses.json                                        (   9,056 bytes)
data\notices\.gitkeep                                        (       0 bytes)
data\questions\.gitkeep                                      (       0 bytes)
data\school_templates.json                                   (   6,034 bytes)
output\compare\.gitkeep                                      (       0 bytes)
output\email\.gitkeep                                        (       0 bytes)
output\exam\.gitkeep                                         (       0 bytes)
output\ps\.gitkeep                                           (       0 bytes)
output\questions\.gitkeep                                    (       0 bytes)
output\recommend\.gitkeep                                    (       0 bytes)
output\resume\.gitkeep                                       (       0 bytes)
prompts\advisor_email_cn.md                                  (   3,755 bytes)
prompts\advisor_search.md                                    (   2,939 bytes)
prompts\course_review.md                                     (   2,655 bytes)
prompts\exam_prep.md                                         (   2,951 bytes)
prompts\experience_summary.md                                (   2,192 bytes)
prompts\interview_questions_cn.md                            (   2,698 bytes)
prompts\interview_questions_en.md                            (   2,522 bytes)
prompts\notice_analysis.md                                   (   2,233 bytes)
prompts\personal_statement_cn.md                             (   3,630 bytes)
prompts\recommendation_letter_cn.md                          (   3,062 bytes)
prompts\resume_translate_en.md                               (   4,896 bytes)
prompts\school_compare.md                                    (   3,211 bytes)
requirements.txt                                             (     265 bytes)
start_server.bat                                             (     120 bytes)
tools\experience_store.py                                    (   6,918 bytes)
tools\feedback_worker.py                                     (   5,923 bytes)
tools\notice_scraper.py                                      (  17,573 bytes)
tools\pdf_generator.py                                       (   4,172 bytes)
tools\question_store.py                                      (  11,766 bytes)
tools\web_server.py                                          (  18,792 bytes)
web\assets\README.md                                         (   1,848 bytes)
web\css\style.css                                            (  10,399 bytes)
web\index.html                                               (  18,659 bytes)
web\js\app.js                                                (  21,603 bytes)
web\js\camera.js                                             (   9,030 bytes)
web\js\question_loader.js                                    (  10,747 bytes)
web\notices.html                                             (  24,667 bytes)
web\practice.html                                            (   9,727 bytes)
web\results.html                                             (  14,228 bytes)
```

### 4.8 `baoyan-skills`
- **Git Commit**: `1e88e5c66a75bab71dd9bf1dd6389d8a58d44ee2`
- **工作区状态**: `CLEAN`
- **许可证**: `NO_LICENSE_FILE`
- **文件总数**: 41 个文件 (共 367,062 字节)

#### 已吸收能力 (Absorbed Capabilities)
- 导师匹配与重合度计算 (`core/advisor_matcher.py`)
- 高情商学术套磁信框架 (`core/advisor_matcher.py`)

#### 未吸收资产 (Unabsorbed Assets & Pending Capabilities)
- 材料包打包脚本 (`skills/baoyan-application-package/scripts/build_package.py`) (独立保留)

#### 文件级清单 (File-level Inventory)
```text
.github\workflows\validate.yml                               (     383 bytes)
.gitignore                                                   (     466 bytes)
README.md                                                    (  12,044 bytes)
docs\privacy.md                                              (   2,151 bytes)
examples\application-package\README.md                       (   1,259 bytes)
examples\application-package\config.json                     (   1,396 bytes)
examples\application-package\demo-output\example-university-package.pdf ( 178,031 bytes)
examples\application-package\demo-output\previews\cover.png  (  73,074 bytes)
examples\application-package\demo-output\previews\toc.png    (  34,384 bytes)
examples\application-package\example-university-logo.svg     (     640 bytes)
examples\application-package\make_demo_materials.py          (   1,742 bytes)
examples\application-package\materials\award.pdf             (   1,954 bytes)
examples\application-package\materials\project.pdf           (   1,963 bytes)
examples\application-package\materials\resume.pdf            (   1,984 bytes)
examples\application-package\materials\transcript.pdf        (   1,935 bytes)
examples\application-package\prompt.md                       (     219 bytes)
examples\personal-statement\README.md                        (     688 bytes)
examples\personal-statement\input-facts.md                   (     570 bytes)
examples\personal-statement\output-excerpt.md                (     832 bytes)
examples\personal-statement\prompt.md                        (     298 bytes)
examples\taocixin-outreach\README.md                         (     853 bytes)
examples\taocixin-outreach\advisor-profile.md                (     352 bytes)
examples\taocixin-outreach\ledger.csv                        (     226 bytes)
examples\taocixin-outreach\letter-body.txt                   (     883 bytes)
examples\taocixin-outreach\prompt.md                         (     297 bytes)
requirements.txt                                             (      61 bytes)
scripts\audit_privacy.py                                     (   3,163 bytes)
scripts\install.ps1                                          (     858 bytes)
scripts\install.sh                                           (     509 bytes)
scripts\validate_skills.py                                   (   1,699 bytes)
skills\baoyan-application-package\SKILL.md                   (   5,183 bytes)
skills\baoyan-application-package\agents\openai.yaml         (     295 bytes)
skills\baoyan-application-package\assets\package-config.example.json (   1,934 bytes)
skills\baoyan-application-package\references\config-schema.md (   1,808 bytes)
skills\baoyan-application-package\references\format-spec.md  (   2,116 bytes)
skills\baoyan-application-package\scripts\build_package.py   (  16,045 bytes)
skills\baoyan-personal-statement\SKILL.md                    (   4,634 bytes)
skills\baoyan-personal-statement\agents\openai.yaml          (     299 bytes)
skills\baoyan-taocixin-outreach\SKILL.md                     (   5,554 bytes)
skills\baoyan-taocixin-outreach\agents\openai.yaml           (     309 bytes)
skills\baoyan-taocixin-outreach\scripts\create_taocixin_docx.py (   3,971 bytes)
```

---
## 五、 备份与归档操作规程 (Bundle & Archival Protocol)

当某仓库的所有规则、代码、测试及必要资产均已完全吸收并完成 OfferGet 测试验证后，执行归档两步走：

### 步骤 1: 生成并校验 Git Bundle
```powershell
# 以 ASu-resume-skills 为例
git -C "D:\User Hub\GitHub\简历\ASu-resume-skills" bundle create "D:\User Hub\GitHub\OfferGet\archives\ASu-resume-skills_f460582.bundle" --all
git bundle verify "D:\User Hub\GitHub\OfferGet\archives\ASu-resume-skills_f460582.bundle"
git bundle list-heads "D:\User Hub\GitHub\OfferGet\archives\ASu-resume-skills_f460582.bundle"
```

### 步骤 2: 移入归档观察区
```powershell
# 建立归档目录并移动，进入为期不少于 14 天的零依赖观察期
New-Item -ItemType Directory -Force "D:\User Hub\GitHub\简历归档"
Move-Item "D:\User Hub\GitHub\简历\ASu-resume-skills" "D:\User Hub\GitHub\简历归档\ASu-resume-skills"
```

### 步骤 3: 最终物理删除（必须用户显式批准）
只有在观察期无问题、未吸收资产确认无价值、OfferGet 测试全绿且用户发出指令后方可执行。
