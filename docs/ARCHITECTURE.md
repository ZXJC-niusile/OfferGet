# OfferGet 架构规范与分层设计 (Architecture Specification)

## 一、 核心设计哲学与治理底线

OfferGet 是一个“高确定性、零幻觉、强证据约束”的求职与学术推免战略操作系统。
在吸收了 ASu-resume-skills、resume-jd-optimizer-cn、ApexResume、King-of-Pigeon、applyr 等外部开源项目的规则与协议后，确立以下系统级治理准则：

1. **唯一事实源 (Single Source of Truth, SSOT)**:
   - 候选人画像与底稿事实由 `core/profile_adapter.py` 的 `ProfileContext` 与 `ProfileEvidenceIndex` 唯一承载。
   - 岗位要求规范由 `modules.jd_analyst.models.DecodedJD` 唯一承载，入站网关统一为 `core.jd_compat.to_canonical()`。
2. **外部项目只作规范与测试资产参考，不复制运行时实现**:
   - `D:\User Hub\GitHub\简历` 下的 26 个外部项目严格保持只读，`delete-approved = 0`。
   - 仅吸收其分层数据契约（Schema）、测试用例集（Fixtures）与评分量表，不在内部无序堆砌第三方运行时。
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
│   - presentation/commands/cmd_context.py: 命令执行上下文               │
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
│   - core/services.py: 100% 向后兼容的薄门面 (Facade Re-export)         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 调用
┌──────────────────────────────────▼─────────────────────────────────────┐
│                    Domain Core Layer (领域核心层)                      │
│   - ProfileContext / ProfileEvidenceIndex: 候选人事实 SSOT             │
│   - DecodedJD / CandidateProfile: 岗位与匹配实体模型                   │
│   - core/evidence/: EvidenceGraph, AuditClaim, MetricCheck             │
│   - core/fact_guard.py: 零漂移事实核验卫士                             │
│   - core/registry.py: QualityRuleRegistry, Taxonomy 规则注册中心       │
│   - core/resume_view_model.py: 简历排版视图模型                        │
└──────────────────┬───────────────────────────────────┬─────────────────┘
                   │                                   │
┌─────────────────────────────────────┐ ┌─────────────────────────────────┐
│  Compatibility Gateway (入站与兼容) │ │  Infrastructure Layer (基础设施) │
│ - core/jd_compat.py:                │ │ - core/artifacts.py: 原子写入   │
│   JD 入站网关、旧字典格式兼容        │ │ - core/paths.py: 资源路径定位   │
│ - core/profile_adapter.py:          │ │ - core/fingerprints.py: 确定性  │
│   候选人非标画像别名与字段标准化    │ │   SHA-256 结构体与内容指纹      │
│ - core/rendercv_adapter.py:         │ │ - core/application_tracker.py: │
│   RenderCV 导入导出转换器           │ │   SQLite Schema v7 持久化引擎 │
└─────────────────────────────────────┘ │ - ApexResume/: 排版基础引擎     │
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
| **用例服务调用** | `services.<domain>_service` (如 `ReviewService`) | `core.services.*` 顶层导出 | 推荐使用细粒度服务，顶层门面永久兼容 |

---

## 四、 错误处理与 CLI 输出契约

1. **Stdout 纯净性**: 当携带 `--json` 参数时，`sys.stdout` 保证**只输出格式化 JSON**，严禁任何诊断、调试日志或 ANSI 控制符混入 stdout。
2. **Stderr 诊断输出**: 所有日志、进度指示、警告均走 `sys.stderr`。
3. **统一错误 Envelope**:
   ```json
   {
     "status": "error",
     "error_type": "FileNotFoundError | ValidationError | SchemaError",
     "message": "清晰且具可读性的中文错误描述",
     "exit_code": 1
   }
   ```
4. **退出码 (Exit Codes)**:
   - `0`: 成功完成；
   - `1`: 通用业务/输入/验证错误；
   - `2`: CLI 参数解析失败（argparse 默认）。
