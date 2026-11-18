# OfferGet 架构规范与精简设计 (Skill Architecture Specification)

## 一、定位与设计边界

OfferGet 定位为**本地简历制作 Skill + 一组确定性 Python 工具**，不维护投递 CRM、工作区审批数据库、谈薪/保研业务系统、RenderCV 双向适配、交互式审计报告系统或面试对抗状态机。规则检查只覆盖已实现的确定性检查项，源材料事实仍需由用户与 Agent 共同核验。

1. **唯一事实源与对话审批边界**:
   - 候选人原始资料与结构化档案由 [core/profile_adapter.py](../core/profile_adapter.py) 的 `ProfileContext` 与 `ProfileEvidenceIndex` 承载。
   - **对话确认与可核查权衡**：用对话确认取代代码级/SQLite 审批状态机以降低概念复杂度；作为补偿，原始底稿必须保持不改写，所有修改建议均须另存为独立修订稿，并在渲染前经公开范围检查、`fact verify` 与 `diff audit` 核验。
   - **学术 CV 作为核心简历能力**：作者顺序保留、候选人姓名加粗、发表状态、用户提供的论文链接，以及 `.bib` 解析与 LaTeX/Typst 导出直接内建于主干简历模型与渲染器中。
2. **本地确定性工具分工（三条主流程 + 按需独立审计）**:
   - [SKILL.md](../SKILL.md) 收敛为三条主路线：整理资料、现有资料编译（无需 JD）、按 JD（文本或截图）走全流程；独立核查命令按需直接调用。
   - **输入解析与参考召回**：`core/resume_parser.py`（支持 `.md/.txt/.docx/.html/.pdf/.bib/.json`）、`core/academic_sync.py`（`BibTexPublicationParser`）、`core/reference_index.py`（`reference-only` 分块检索）。
   - **事实、差异、隐私与 ATS 校验**：`core/fact_guard.py`（含锚点防漂移与句内比率/基线结果重算校验）、`core/diff_ledger.py`、`core/resume_auditor.py`、`core/ats_checker.py`、`core/anonymizer.py`、`core/security_gate.py`。
   - **渲染、排版与单页收敛**：`core/resume_view_model.py`、`core/resume_builder.py`、`core/autofit.py`、`core/layout_solver.py`、`core/browser_renderer.py`、`core/ats_docx_renderer.py`、`core/academic_exporter.py`、`themes/`。
   - **诚实失败报告**：排版通过不代表外部事实真实或 ATS 必定通过；无头浏览器或原生编译器缺失时由 `doctor` 暴露未核验阶段，不伪造已完成 PDF。
3. **扁平调用链**:
   - `cli.py` $\longrightarrow$ `presentation/commands/*_cmd.py` $\longrightarrow$ `core/*`
   - 已移除 `services/` 应用服务包装层与 `core/services.py` 兼容门面。

---

## 二、目录职责总览

```text
OfferGet/
├── SKILL.md                       # Skill 三路线入口与硬边界
├── references/                    # 按需加载的工作流、证据、改写与去模板化规范
├── cli.py                         # 统一 CLI 入口 (profile/resume/ats/fact/diff/anon/selftest/doctor)
├── presentation/
│   ├── commands/                  # 轻量命令行处理器，直接调用 core/*
│   └── diagnostic_data/           # 安装包内建合成诊断样例
├── core/
│   ├── resume_parser.py           # 多格式解析 (.md/.txt/.docx/.html/.pdf/.bib/.json)
│   ├── profile_adapter.py         # 档案规范化、公开范围校验与证据索引
│   ├── reference_index.py         # reference-only 本地参考文档分块检索
│   ├── academic_sync.py           # BibTeX 文献解析 (AcademicPublication, BibTexPublicationParser)
│   ├── fact_guard.py              # 指标与事实防漂移检查及句内比率/变化重算
│   ├── diff_ledger.py             # 基线与改写稿差异台账
│   ├── ats_checker.py             # ATS 结构、可读性、关键词覆盖与可见性过滤
│   ├── resume_auditor.py          # 数学重算、动词/角色层级与静态 HTML 检查
│   ├── anonymizer.py              # 可逆脱敏与还原
│   ├── security_gate.py           # 输出安全与 XSS/LaTeX/Typst 转义门控
│   ├── resume_view_model.py       # 统一排版视图模型（含学术作者排序/加粗、发表状态与链接）
│   ├── resume_builder.py          # 14 套主题渲染与构建编排
│   ├── autofit.py / layout_solver.py / browser_renderer.py / ats_docx_renderer.py / academic_exporter.py
│   ├── registry.py / lexicon.py   # 共享别名、指标正则与质量规则注册中心
│   └── artifacts.py / atomic_writer.py / cli_helpers.py / fingerprints.py / paths.py / validator.py
└── themes/                        # 10 套 HTML/PDF 主题与 ats-plain.md
```

---

## 三、CLI 错误与输出契约

1. **Stdout 纯净性**：携带 `--json` 时 `sys.stdout` 仅输出合法 JSON；诊断与警告输出至 `sys.stderr`。
2. **统一错误结构**：`{"status": "error", "error_type": "...", "message": "...", "exit_code": 1}`，涵盖 `input_not_found`、`invalid_json`、`invalid_input`、`io_error`。
3. **退出码**：`0` 成功；`1` 业务/输入/校验失败；`2` CLI 参数语法错误。
4. **渲染与安全边界**：输出安全检查拒绝全部内联事件处理器（含照片回退脚本）；无头浏览器缺失或溢出检测失败时明确报告未核验阶段，不假定通过。
