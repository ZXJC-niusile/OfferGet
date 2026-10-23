# OfferGet 架构规范与分层设计 (Architecture Specification)

## 一、 核心设计哲学与治理底线

OfferGet 是一个以本地规则与证据约束为基础的求职与学术推免工具。规则检查只覆盖已实现的检查项，事实仍需对照源材料核验。系统采用以下治理准则：

1. **唯一事实源 (Single Source of Truth, SSOT)**:
   - 候选人画像与底稿事实由 `core/profile_adapter.py` 的 `ProfileContext` 与 `ProfileEvidenceIndex` 唯一承载。
   - 岗位要求规范由 `core.jd_analyst.models.DecodedJD` 唯一承载，入站网关统一为 `core.jd_compat.to_canonical()`。
2. **本地确定性规则**:
   - 核心规则审计、四维打分、算术对账与字数压缩均采用本地确定性算法，不依赖外部付费大模型 API。
   - 展现层、编排层与核心层之间实行清晰解耦。
3. **严格分层与单向依赖**:
   - 展现层（Presentation）$\longrightarrow$ 应用服务层（Application Services）$\longrightarrow$ 领域核心（Domain Core）$\longleftarrow$ 适配层（Adapters）
   - 基础设施层（Infrastructure）为各层提供纯净的 I/O、哈希与存储支持，禁止领域逻辑倒灌。

---

## 二、 五层架构蓝图

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Presentation Layer (展现层)                          │
│   - cli.py: 顶层命令行解析与入口                                       │
│   - presentation/commands/*_cmd.py: 命令处理器 (参数校验、调用、输出)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 调用
┌──────────────────────────────────▼─────────────────────────────────────┐
│              Application Services Layer (用例编排层)                   │
│   - services/jd_service.py: JD 解析与职能分类                          │
│   - services/profile_service.py: 画像加载与证据索引                    │
│   - services/match_service.py: 岗位匹配与差距分析                      │
│   - services/review_service.py: 职业复盘与面试答辩循环                 │
│   - services/resume_service.py: 简历构建与版本快照                     │
│   - services/offer_service.py: 薪酬评估、多 Offer 决策与谈判           │
│   - services/academic_service.py: 保研推免、导师匹配与学术自述         │
│   - services/report_service.py: 战略分析报告生成                       │
│   - core/services.py: 现行公共符号的延迟导出门面         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 调用
┌──────────────────────────────────▼─────────────────────────────────────┐
│                    Domain Core Layer (领域核心层)                      │
│   - ProfileContext / ProfileEvidenceIndex: 候选人事实 SSOT             │
│   - DecodedJD / CandidateProfile: 岗位与匹配实体模型                   │
│   - core/evidence/: EvidenceGraph, AuditClaim, MetricCheck             │
│   - core/fact_guard.py: 事实与指标一致性检查                             │
│   - core/registry.py: QualityRuleRegistry, Taxonomy 规则注册中心       │
│   - core/resume_view_model.py: 简历排版视图模型                        │
│   - core/resume_themes.py: 主题注册表                                  │
└──────────────────┬───────────────────────────────────┬─────────────────┘
                   │                                   │
┌─────────────────────────────────────┐ ┌─────────────────────────────────┐
│  Compatibility Gateway (入站与兼容) │ │  Infrastructure Layer (基础设施) │
│ - core/jd_compat.py:                │ │ - core/artifacts.py: 原子写入   │
│   JD 入站网关、旧字典格式兼容        │ │ - core/paths.py: 资源路径定位   │
│ - core/profile_adapter.py:          │ │ - core/fingerprints.py: 确定性  │
│   候选人非标画像别名与字段标准化    │ │   SHA-256 结构体与内容指纹      │
│ - core/rendercv_adapter.py:         │ │ - core/application_tracker.py: │
│   RenderCV 导入导出转换器           │ │   SQLite Schema v9 持久化引擎 │
└─────────────────────────────────────┘ │ - core/browser_renderer.py: 渲染 │
                                        └─────────────────────────────────┘
```

---

## 三、 Canonical 与 Legacy API 映射规范

| 领域 / 职责 | Canonical 规范入口 (主路径) | Legacy 兼容入口 (保留) | 说明 |
|:---|:---|:---|:---|
| **JD 解析入站** | `core.jd_compat.to_canonical(input)` | `core.jd_compat.decode_legacy(text)` | 接收 str, Path, dict, 统一输出 `DecodedJD` |
| **JD 匹配评估** | `JDMatcher.match(canonical_jd, profile)` | `core.jd_compat.match_legacy(jd_dict, prof_dict)` | Canonical 结果包含强弱要求判定与预测 |
| **候选人画像** | `ProfileContext.from_profile(data)` | `core.profile_adapter.normalize_candidate_profile(data)` | 全流程只解析构建一次，多处防御性投影 |
| **证据事实项** | `ProfileEvidenceIndex.claims` (`EvidenceClaim`) | 历史散落字典 `profile["projects"][i]["highlights"]` | 底稿中的客观事实凭证 |
| **简历主张审计** | `core.evidence.AuditClaim` / `EvidenceAuditor` | 历史基于整段文字的模糊正则匹配 | 从简历提取并核验的原子命题 |
| **证据推进状态** | `core.evidence.graph.EvidenceGraph` | `job_flow.py` 内联状态判断 | 单向单调跃迁状态机与 `can_apply()` 门禁 |
| **本地文件写入** | `core.artifacts.write_text_atomic` / `write_json_atomic` | 直接 `open(..., 'w')` / `Path.write_text()` | 确保同目录临时文件原子替换，防止损坏 |
| **资源路径定位** | `core.paths.get_template_path()` / `get_project_root()` | 硬编码 `Path(__file__).resolve().parent.parent` | 统一解耦，支持源码运行与打包运行 |
| **用例服务调用** | `services.<domain>_service` (如 `CareerReviewService`) | `core.services.*` 顶层导出 | 推荐使用细粒度服务，顶层门面保留现行公共符号 |

---

## 四、 错误处理与 CLI 输出契约

1. **Stdout 纯净性**: 当携带 `--json` 参数时，`sys.stdout` 保证**只输出格式化 JSON**，严禁任何诊断、调试日志或 ANSI 控制符混入 stdout。
2. **Stderr 诊断输出**: 所有日志、进度指示、警告均走 `sys.stderr`。
3. **统一错误 Envelope**:
   ```json
   {
     "status": "error",
     "error_type": "io_error",
     "message": "文件读取失败，请检查路径与访问权限后重试。",
     "exit_code": 1
   }
   ```
读取入口保留权限和 I/O 错误，不将文件路径当作正文。错误类型还包括
`input_not_found`、`invalid_json`、`invalid_input`、`invalid_answers`、`session_conflict`；
具体值由命令和失败阶段决定。

4. **退出码 (Exit Codes)**:
   - `0`: 成功完成；
   - `1`: 通用业务/输入/验证错误；
   - `2`: CLI 参数解析失败（argparse 默认）。

## 五、入口迁移

简历审计与浏览器渲染直接使用 `core.resume_auditor` 和
`core.browser_renderer`；保研材料构建使用 `core.baoyan_pipeline`。
旧的 `core.audit`、`core.render`、`core.baoyan_package` 转发模块已删除。
简历命令调度入口为 `cmd_resume_dispatch`。
主题目录统一为 `themes/`，不再回退到已移除的嵌套项目目录。
`core.services` 与 `core.lexicon` 仍提供现行公共接口；前者延迟加载具体实现，
后者引用注册中心中的同一份规则数据，不复制词典。

## 六、匹配、预测与输出边界

- 匹配的基础权重为核心要求 0.6、加分要求 0.2、隐含信号 0.2。
  仅对 JD 中存在的维度归一化；`unavailable_dimensions` 标明缺失维度，
  `dimension_weights` 给出实际权重，全部缺失时不生成正向匹配分。
- 未提供经过校准的招聘结果模型。默认 `interview_prob`、
  `interview_probability_range`、投递决策中的 `probability_range` 均为 `null`，
  渠道分布为空；`probability_status` 和 `probability_basis` 解释原因。
  这是未知值，不等价于测得的 0%。外部提供的估计在报告中单独标注来源边界。
- `interview` 与 `review` 的面试题统一围绕当前简历中的项目和工作经历；JD 用于岗位匹配与材料建议。
- 输出安全检查拒绝全部内联事件处理器，包括照片回退脚本。
  溢出测量的降级渲染失败时抛出异常，由调用方记录为未核验，不记录为零溢出。

## 七、可继续的复盘工作目录

`review --workspace <目录>` 将输入路径、目标、会话、回答模板和提案数据库关联起来。
`CareerReviewService.persist_proposal` 统一处理保存、终态恢复和摘要刷新，CLI 负责输入与展示。
`build_review_summary` 是各调用入口的下一步判断来源；提案已确认/拒绝时不再显示为待确认。
面试题以简历原文为依据，`practice_queue` 给出基于回答诊断的追问。同一简历续答保持题目 ID；材料变化后重建题目，不沿用旧回答。确认提案后，工作目录的履历输入切换为实际输出文件；通过数据库、源材料指纹与产物校验关联会话。原始材料后续有改动时重新分析原始材料。
工作目录继续保存源文件路径；修改材料后会刷新会话，已有简历在同一输出目录覆盖。
回答模板绑定材料与题目版本，已填写的版本保留，新轮次使用单独模板；提交时必须匹配当前版本。会话与模板禁止影子写入，文件占用时明确报错；普通导出返回实际保存路径。

提案覆盖履历前，将恢复所需原稿保存在提案数据库中，不随公开提案导出。失败后可重试原命令；只接受原稿或该提案的确认结果，仍拒绝其他材料改动。会话接通、产物检查和版本登记全部成功后才标记完成。

显式指定的会话不存在或路径指向目录时，接受流程报错并保留恢复状态，不标记完成。回答编号在查询当前题目之前检查类型，避免错误输入触发未处理异常。
