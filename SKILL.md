---
name: offerget
description: Industrial-grade Job Description Decoding, Candidate Matching, ATS Quality Gate, Three-State Skill Ledger, and Offer Strategy OS.
allowed-tools: Read Write Edit Bash Glob Grep WebSearch WebFetch
license: MIT
---

# OfferGet · 轻量求职 Agent 与战略操作系统 (Offer Strategy OS)

OfferGet 是面向前沿技术岗位（大模型算法、分布式基础架构、AI Agent、高性能计算与系统工程）的**轻量求职 Agent / Skill**，聚焦高置信度闭环：

$$\text{岗位 JD 拆解} \longrightarrow \text{基于真实事实的简历建议} \longrightarrow \text{针对性面试问题 (≥3 题)} \longrightarrow \text{用户真实作答} \longrightarrow \text{基于证据边界的具体反馈}$$

主打深磨：**基于真实经历与证据边界的面试训练（Interview Training Grounded in Truthful Experience and Evidence Boundaries）**。系统基于确定性规则与单事实源（SSOT）真实凭证底稿运行，绝无外部数据库或黑盒 LLM API 依赖。

---

## 核心架构与 5 大模块拓扑 (5-Module Full-Spectrum Topology)

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                   OfferGet Master Operating System                                                    │
├──────────────────────────┬──────────────────────────┬──────────────────────────┬──────────────────────────┬───────────────────────────┤
│   Module 1: JDAnalyst    │   Module 2: ApexResume   │   Module 3: ATSAuditor   │  Module 4: Privacy & Fact│  Module 5: Strategy & Nego│
├──────────────────────────┼──────────────────────────┼──────────────────────────┼──────────────────────────┼───────────────────────────┤
│ • 5 图层纵向语义穿透拆解 │ • 单事实源 (SSOT) 凭证账本│ • 4 维加权 ATS 评分模型  │ • 双向可逆去隐私化脱敏网关│ • 技能差距 ROI 杠杆计算   │
│ • 32 项大厂黑话潜台词词典│ • Mini-RFC 架构叙事改写  │ • 三态技能台账防伪审查   │ • 标准/严格双层脱敏引擎   │ • 50-80% 错失区间跃迁建议 │
│ • 5 大技术红旗与反问探针 │ • 动词五级阶梯与证据约束 │ • 可见度系统多变体隔离   │ • 事实锚点提取与虚标拦截 │ • 6 大劳动合同陷阱深度识别│
│ • Top 20 硬核面试真题库  │ • AutoFit 像素级压页算法 │ • 四大反 AI 指纹拦截过滤 │ • 指标漂移 (Anti-Drift)   │ • 高情商薪酬博弈与反制谈判│
│ • 渠道权重与 Ghost Job   │ • 34 项独立单测 100% 覆盖│ • 成对双胞胎双语合规核验 │ • 确定性真实底稿核验门禁 │ • 中英双语薪酬对谈策略信  │
└──────────────────────────┴──────────────────────────┴──────────────────────────┴──────────────────────────┴───────────────────────────┘
```

---

## 七阶段硬门禁工作流 (7-Stage Guardrailed Workflow with Gates)

本 Skill 采用**硬门禁工作流（Guardrailed Workflow with Gates）**设计，涵盖从岗位解析、技能跃迁、隐私脱敏、事实核验、ATS 质检到 Offer 谈判的全周期。**门禁为绝对阻塞式断言，条件未达成严禁跨阶段流转！**

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Stage 1: Intake │       │ Stage 2: Skill  │       │ Stage 3: Privacy│       │ Stage 4: Profile│
│ & 5-Layer Decode│─GATE 1─> Gap ROI Analysis│─GATE 2─> Anonymization  │─GATE 3─> Visibility     │─GATE 4─┐
│                 │       │ (Near-Miss Ops) │       │ Gateway (Mask)  │       │ Filtering       │        │
└─────────────────┘       └─────────────────┘       └─────────────────┘       └─────────────────┘        │
                                                                                                         │
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐                                  │
│ Stage 7: Offer  │       │ Stage 6: ATS    │       │ Stage 5: Fact   │                                  │
│ Negotiation &   │<GATE 7─│ Auditor & Skill │<GATE 6─│ Guard Metric    │<─────────────────────────────────┘
│ Contract Review │       │ Ledger Gate     │       │ Drift Audit     │  (Zero Metric Inflation
└─────────────────┘       └─────────────────┘       └─────────────────┘   Fact Check Passed)
```

在执行交互时，Agent 必须在进入每个阶段前明确宣告状态：
```text
=== [Stage X: Stage Name] ===
```

---

### Stage 1: Intake & 5-Layer Decoding (Required)

#### 1.1 输入捕获与归一化
- **必选输入**：
  - 目标岗位招聘描述（Job Description, 文本或文件路径）
  - 目标公司与业务线名称（如未注明需通过文本上下文推断）
  - 候选人主档案（Master Profile / 原始简历库 / SSOT 数据源）
- **可选输入**：
  - 投递渠道偏好（内推 / HR 直聘 / 猎头 / 官网海投）
  - 目标职级预期（P7/P8、L5/L6、Staff/Principal Engineer）

#### 1.2 5 图层纵向语义拆解引擎 (5-Layer Decoding)
调用 `modules/jd_analyst/decoder.py` 进行规范化拆解；`core/jd_decoder.py` 仅保留历史 CLI 的兼容包装：
1. **Layer 1: 组织坐标与业务护城河 (Organization & Business Moat)**：
   - 研判团队是“核心战略造核骨干”还是“外围探索/边缘试水”。
   - 解析部门核心考核 KPI 是商业变现（ROI）、模型打榜，还是基建降本。
2. **Layer 2: 核心硬性技术架构 (Hard Technical Architecture)**：
   - 提取计算基座、训练框架（Megatron-LM / DeepSpeed / FSDP / Ray）、推理引擎（vLLM / TensorRT-LLM / SGLang）。
   - 锚定底层通信优化（RDMA / InfiniBand / NCCL / Ring-AllReduce）与模型结构创新（MLA / MoE / FlashAttention）。
3. **Layer 3: 业务协同与工程落地 (Business Impact & Product Sense)**：
   - 梳理产品闭环、算法上线的端到端链路及高并发 SLA 指标（TTFT / P99 吞吐）。
4. **Layer 4: 隐性门槛与黑话潜台词 (Implicit Filters & Hidden Signals)**：
   - 对照 [hidden-signals-lexicon.md](references/hidden-signals-lexicon.md) 检索 32 项大厂潜台词（如“极客精神” $\to$ 缺基建通宵排障；“千卡经验” $\to$ 慢节点故障定位与容灾）。
5. **Layer 5: 红旗陷阱与成败考核指标 (Red Flags & KPI Reality)**：
   - 对照 [red-flags-guide.md](references/red-flags-guide.md) 识别算力欺诈、套壳包装、伪大模型等致命风险，准备 15 道反问探针。

#### 🛑 GATE 1 检查清单 (必须全部勾选通过)
- [ ] JD 原始文本与元数据（职位、公司、职级、技术栈）解析完整
- [ ] 5 个图层均已输出结构化分析，无一遗漏
- [ ] 至少扫描并匹配了隐性信号词典与红旗探针
- [ ] 提炼出 5-8 个高信号硬核技术考核点

---

### Stage 2: Master Profile Filtering via Visibility System (Required)

#### 2.1 可见度系统规范 (Visibility System Schema)
候选人单事实源（SSOT）主档案包含全量技术经历、项目与技能。针对不同目标岗位，必须通过可见度系统做确定性过滤与隔离：

| 可见度标签 (`Visibility`) | 语义与应用场景 | 处理行为 |
|---|---|---|
| `always` | 核心主干竞争力（如大模型全栈架构、顶尖学术成果、知名大厂核心技术经验） | 任何岗位变体均保留入选池 |
| `variant-specific` | 强垂直领域经验（如仅针对 `llm_infra`、`rl_alignment`、`agent_system`、`fintech_algo`） | 仅当目标岗位变体与经历定义的 `Variants` 匹配时包含 |
| `on-request` | 次要经历或补充项目（如早期泛后端、边缘支持工作、传统 CRUD 模块） | 默认排除，除非用户明确要求展示全景或弥补特定经历断层 |
| `reference-only` | 底层真值事实证据（Git Commit、RFC 文档编号、内部 Benchmark 凭证、离线实验日志） | 严禁直接输出到公开简历，仅作为台账防伪支撑 |

#### 2.2 变体推断与排除报告 (Resolution & Excluded Report)
- 根据 Stage 1 解码出的技术主域（`TechDomain`），自动选定当前投递变体；
- 统计被过滤排除的项目或条目，生成《排除条目审计表》，向用户明确说明过滤理由（如：“过滤了传统 Web 开发项目以确保大模型算力经验获得 100% 版面权重”）。

#### 🛑 GATE 2 检查清单 (必须全部勾选通过)
- [ ] 目标岗位技术变体选定明确（如 `llm_pretraining_infra` 或 `agent_runtime`）
- [ ] 所有 Master 经历严格按 `Visibility` 规则完成过滤
- [ ] 输出了过滤说明报告，未发生关键技术亮点被误删
- [ ] 候选人提取后的技能与项目池与 JD Layer 2/3 高度对齐

---

### Stage 3: ApexResume Content Tailoring & Anti-AI Humanization (Required)

#### 3.1 Mini-RFC 架构叙事改写
调用 ApexResume 方法论将经历重构为高势能叙事（痛点 $\to$ 演进 $\to$ 链路 $\to$ 商业指标）：
- **动词五级阶梯硬门禁**：
  $$\text{支持/协助 (Level 1)} < \text{参与 (Level 2)} < \text{负责 (Level 3)} < \text{推动 (Level 4)} < \text{主导 (Level 5)}$$
  - 声明 Level 4（推动）或 Level 5（主导/从0到1）的条目，**必须在 SSOT 事实库中存在方案决策（Decision）或架构评审（RFC）证据**。
- **双重指标锚定 (Dual-Anchor Metrics)**：
  - 必须给出基线（Baseline）与达成结果（Result）；
  - 必须保留分子与分母（如 $420/500$），区分百分点提升（pp）与相对提升（%）；
  - 标定数据深度（D0-D4）与成果证据等级（R0-R3）。

#### 3.2 四大反 AI 写作指纹严苛拦截 (Anti-AI Slop Pass)
运行 `core/validator.py` 严格查杀以下 4 类机器套话指纹：
1. **严禁破折号修饰滥用**：禁止 `——` 或 `--` 充当 AI 式递进。
2. **严禁排比三段论假大空**：禁止“不仅...而且...更...”句式。
3. **严禁无量化虚高形容动词**：禁止“深度赋能”、“全面革新”、“强力驱动”、“革命性突破”、“显著提高”、“大幅优化”、“卓越成效”、“无缝打通”、“全方位重塑”。
4. **严禁空洞同位语与外文套话**：禁止“作为一名深耕...的专家”、“delve into”、“pivotal role”、“testament to”、“intricate tapestry”。

#### 🛑 GATE 3 检查清单 (必须全部勾选通过)
- [ ] 所有 Bullet 经历均基于 Mini-RFC 结构完成改写
- [ ] 动词层级严格对应真实职责，无无证据的“主导”或“从0到1”
- [ ] 反 AI 写作指纹检测 **100% Passed (0 处违规)**
- [ ] 语言节奏自然真实，可通过“脱稿 30 秒技术答辩”心智测试

---

### Stage 4: ATS Auditor & Three-State Skill Ledger (Required)

#### 4.1 4 维加权 ATS 评分模型 (4-Dimension ATS Quality Model)
ATS 综合评分由四大确定性维度加权计算：
$$S_{\text{ATS}} = 0.30 \times S_{\text{threshold}} + 0.25 \times S_{\text{keyword}} + 0.20 \times S_{\text{layout}} + 0.25 \times S_{\text{evidence}}$$

1. **硬性门槛对齐度 ($S_{\text{threshold}}$, 权重 30%)**：学历、工龄、核心专业背景与硬门槛 0/1 判定。
2. **高信号关键词密度 ($S_{\text{keyword}}$, 权重 25%)**：高频技术栈、算子名、框架名在语境中的自然展现（拒绝无意义堆砌）。
3. **标准排版与可解析性 ($S_{\text{layout}}$, 权重 20%)**：标准 ATS 模块标题、无嵌套不可解析表格、规范日期与联系方式。
4. **指标与凭证密度 ($S_{\text{evidence}}$, 权重 25%)**：D0-D4 数据深度与 R0-R3 成果证据覆盖率。

#### 4.2 三态技能台账系统 (Three-State Skill Ledger)
对成稿中出现的每一项核心技能与成果主张，挂载三态判定：

```text
┌────────────────────────────────────────────────────────────────────────┐
│                     Three-State Skill Ledger (三态技能台账)             │
├───────────────────┬────────────────────────────────────────────────────┤
│ 状态              │ 判定准则与处理动作                                 │
├───────────────────┼────────────────────────────────────────────────────┤
│ 1. VERIFIED       │ SSOT 事实库中有直接且充分证据 (代码、RFC、评测日志)│
│    (已核验真值)   │ 准予全绿放行，作为面试主力进攻锚点                 │
├───────────────────┼────────────────────────────────────────────────────┤
│ 2. CLAIMED        │ 候选人主观陈述但证据链处于待补足状态               │
│    (声称待佐证)   │ 允许保留，但必须自动生成 3 层面试防御卡进行答辩准备│
├───────────────────┼────────────────────────────────────────────────────┤
│ 3. UNSUPPORTED    │ 事实库中无记录，属于大模型自作主张的凭空编造       │
│    (虚构无支撑)   │ 【绝对红线】一票否决！立即强制拦截并从成稿中剔除！ │
└───────────────────┴────────────────────────────────────────────────────┘
```

#### 4.3 终审裁决状态机 (Verdict State Machine)
- **`READY_TO_SEND`**：ATS 综合得分 $\ge 75$、`UNSUPPORTED` 数量 $= 0$、无未解决红旗陷阱。
- **`NEEDS_REVISION`**：$60 \le \text{ATS 得分} < 75$，或存在 1-2 条待降级动词。
- **`BLOCKED`**：ATS 得分 $< 60$、存在 `UNSUPPORTED` 编造项、或触发硬门槛一票否决。

#### 🛑 GATE 4 检查清单 (必须全部勾选通过)
- [ ] ATS 综合得分计算完毕且 $\ge 75$
- [ ] 三态技能台账审计完成，`UNSUPPORTED` 计数严格为 0
- [ ] 终审判定状态严格为 `READY_TO_SEND`
- [ ] 针对所有 `CLAIMED` 项已装配 3 层面试防御卡

---

### Stage 5: Compilation & Bilingual Delivery (Required)

#### 5.1 双线工程编译输出 (Dual Delivery Pipeline)
1. **ApexResume 单页 A4 简历**：
   - 调用 AutoFit 算法引擎（`python cli.py resume autofit`），动态微调行高、段间距与字号；
   - Headless Chrome 像素级测距，确保**溢出像素 $\le 0$**，生成无瑕疵单页 A4 PDF。
2. **OfferGet 双语 HTML 战略决策全景报告**：
   - 装配 `templates/offer_strategy.html`，输出单文件全自包含战略报告；
   - 验证成对双胞胎（Bilingual Twins）规范：
     - 根标签必须为 `<html lang="en">`；
     - `data-lang="en"` 与 `data-lang="zh"` 标签数量**严格相等且 $\ge 80$ 对**；
     - 动态 SVG 半环仪表盘渲染能力契合度与通过概率；
     - 内置纯客户端 DOM-to-MD 一键导出器。
3. **ATS 纯文本 / Word DOCX 格式**：
   - 导出 `ats-plain.md` 或标准 ATS 排版文档，供招聘系统快速解析。

#### 🛑 GATE 5 检查清单 (必须全部勾选通过)
- [ ] ApexResume 单页压页判定完成（`overflow <= 0`）
- [ ] PDF 渲染成功，排版无分页断行瑕疵
- [ ] 双语 HTML 报告通过 `validate_bilingual_html` 审查
- [ ] 向用户交付可直接投递的成果文件清单与链接

---

## 严禁红线 (Strict 'Do NOT' Rules)

1. **严禁凭空捏造数据 (No Hallucinating Metrics)**：
   - 绝不能无中生有地添加用户未提供的百分比、吞吐量、机器卡数或基准提升。无真实数字时，使用具体维度（如架构改动、协议实现）替代。
2. **严禁关键词堆砌 (No Keyword Stuffing)**：
   - 严禁在简历底栏、背景色块或段落末尾利用不可见字符或无关词串堆砌技术关键词。所有命中词必须自然嵌入真实项目上下文。
3. **严禁越级跳过门禁 (No Bypassing Gates)**：
   - 在 Gate 1 通过前不得生成正文；在 Gate 4 判定为 `READY_TO_SEND` 之前不得输出最终简历。
4. **严禁非标模块命名 (No Non-Standard Headings in ATS Resumes)**：
   - ATS 模块标题必须严格使用标准规范：`Summary`、`Experience`、`Education`、`Skills`、`Projects`、`Certifications`。
5. **严禁角色越级声称 (No Role Inflation)**：
   - 无架构方案选型或规划主导证据的条目，严禁使用“主导”、“统筹”、“从0到1”、“端到端负责”。

---

## 命令行操作指南 (CLI Quickstart)

```bash
# 1. 5 图层 JD 深度解码
python cli.py jd decode examples/sample_ai_jd.txt

# 2. 输出解码 JSON 结构
python cli.py jd decode examples/sample_ai_jd.txt --json

# 3. 候选人档案事实匹配与缺口评估
python cli.py jd match examples/sample_ai_jd.txt --profile examples/candidate_profile.json

# 4. 技能差距 ROI 引擎：分析 50%-80% 错失岗位，计算高杠杆技能提升收益
python cli.py gap roi examples/sample_ai_jd.txt --profile examples/candidate_profile.json

# 5. 隐私去标识化脱敏网关 (支持 standard 与 strict 模式，可逆映射还原)
python cli.py anon mask examples/candidate_profile.json --map deanon_map.json --output anon_profile.json
python cli.py anon unmask anon_profile.json --map deanon_map.json --output restored_profile.json

# 6. 事实防伪守卫与抗指标漂移核验 (严禁 AI 虚标改写数字)
python cli.py fact verify "主导 1024 卡 H800 集群预训练，端到端 MFU 优化至 54.2%。" --profile examples/candidate_profile.json

# 7. ATS 4 维质量审计与三态技能台账核验
python cli.py ats audit examples/candidate_profile.json --jd examples/sample_ai_jd.txt

# 8. 过滤主档案可见度系统 (支持 ai_pretrain / agentic_systems / cluster_infra 等标签)
python cli.py ats filter examples/candidate_profile.json --tag ai_pretrain --output tailored_profile.json

# 9. 生成工业级单文件双语 HTML 战略全景报告
python cli.py jd report examples/sample_ai_jd.txt --profile examples/candidate_profile.json --output report.html

# 10. Offer 评估与 6 大劳动合同陷阱识别
python cli.py offer evaluate examples/sample_offer.json --profile examples/candidate_profile.json

# 11. 生成高情商薪酬谈判信与口头对谈脚本
python cli.py offer counter examples/sample_offer.json --target-base 95000 --profile examples/candidate_profile.json

# 12. 调用 ApexResume 简历子系统：确定性防伪审计
python cli.py resume audit --claims ApexResume/examples/claims.json --html ApexResume/examples/sample-resume.html

# 13. 调用 ApexResume 简历子系统：AutoFit 像素级单页压页与 PDF 导出
python cli.py resume autofit ApexResume/examples/sample-resume.html output_fit.html --pdf my_resume.pdf

# 14. 全局统一环境与自动化测试套件自检（OfferGet 538 项 + ApexResume 34 项，共 572 项）
python cli.py selftest

# 15. 持久化投递管理：创建投递记录，跟踪状态与证据快照
python cli.py application add "APP-001" --company "示例科技" --role "后端工程师"
python cli.py application list --status pending
python cli.py application show "APP-001"
python cli.py application status "APP-001" interview --note "已进入一面"

# 16. 证据门禁材料提案（HITL）：review 生成草稿，人工确认后才可落地改写
python cli.py review examples/sample_ai_jd.txt --profile examples/candidate_profile.json \
  --proposal-db offers.db --application-id "APP-001" --output review.json --json
python cli.py proposal list --status draft --application-id "APP-001"
python cli.py proposal accept "MP-xxxx" --profile examples/candidate_profile.json \
  --jd examples/sample_ai_jd.txt --output tailored_profile.json --build-resume
python cli.py proposal reject "MP-xxxx"

# 17. 投递结果反馈闭环：受控阶段/结果/标签、复盘和下一步行动，并聚合跨申请洞察
python cli.py application outcome "APP-001" --stage interview --result rejected \
  --feedback "系统设计深度不足" --reflection "容量估算不充分" \
  --next-action "练习缓存与分片设计" --tags system_design,technical_depth
python cli.py application outcomes "APP-001" --json
python cli.py application insights --json

# 18. RenderCV JSON 互通：导入为 OfferGet Profile，或导出为 RenderCV JSON
python cli.py rendercv import rendercv.json --output profile.json
python cli.py rendercv export profile.json --output rendercv.json

# 19. 记录不可变的岗位关联简历版本元数据
python cli.py application show APP-001 --json
python cli.py application versions APP-001 --json
python cli.py application version-diff VERSION_A VERSION_B --json
```

---

## 跨 Agent 平台调用指引 (Cross-Agent Invocation)

OfferGet 遵循开放 Agent Skill 规范，可在各大前沿智能编程助手与智能体框架中无缝协同：

### 1. Cursor
在工作区 `.cursorrules` 或 `.cursor/rules/offerget.mdc` 中声明引用：
```markdown
---
description: OfferGet 简历战略与 JD 解码总控系统
globs: ["**/*.md", "**/*.html", "**/*.json"]
---
当用户要求匹配岗位、优化简历或评估 JD 时，严格遵循 OfferGet 5 阶段硬门禁工作流。
首先运行 `python cli.py jd decode <jd_file>`，并通过三态技能台账与反 AI 指纹审计。
```

### 2. Claude Code
作为项目或全局技能注入：
- 复制本 Skill 目录至 `.claude/skills/offerget`；
- 在会话中通过自然语言或斜杠命令唤起：
  ```bash
  /skill offerget "请帮我针对这个大模型架构师 JD 评估我的经历并生成双语报告"
  ```

### 3. Google Antigravity
在 Agent System Prompt 或 Skill 声明中挂载 `offerget`：
```python
# 通过 invoke_subagent 或直接工具调用
invoke_subagent(
    TypeName="offerget",
    Role="Career Strategy Architect",
    Prompt="解码 target_jd.txt，比对 candidate_profile.json，执行 ATSAuditor 门禁并输出 report.html"
)
```

### 4. GitHub Copilot
在工作区 `.github/copilot-instructions.md` 中配置：
```markdown
# OfferGet Workflow Integration
在处理求职、简历撰写、JD 分析任务时：
1. 必须使用 OfferGet 5 图层模型拆解岗位；
2. 过滤主档案时严格遵守 Visibility System；
3. 执行反 AI 写作指纹审查，严禁破折号滥用与排比三段论；
4. 运行 `python cli.py selftest` 验证产出物符合工业级标准。
```

---

## 纯中文学术深造与保研/考研复试战略双轨 (Chinese Academic Track)

针对国内高校顶尖保研夏令营、预推免、九推与考研复试，OfferGet 原生集成了四大核心引擎：

### 1. 学术诚信与字数自适应审计器 (Baoyan Auditor)
- **4 大学术诚信红线**：
  1. `simulation_vs_real_cluster`: 严禁将 Gazebo/Gym/PyBullet 仿真环境或 Toy dataset 混淆为物理机/万卡集群产线实测。
  2. `expected_vs_acquired_outcomes`: 严禁将在投 (under review) 或预备投稿论文写成已录用/已见刊。
  3. `role_verb_hierarchy`: 依据团队位次（项目负责人/核心成员/参赛队员/辅助成员）严格授权动词，严禁非负责人滥用“主导”、“统筹”。
  4. `academic_buzzwords_forbidden`: 拦截“首创”、“颠覆”、“国际先进”、“填补空白”等空洞大词。
- **3 级自适应字数压缩器**：
  - `摘要版` (40-60 字，高校网申表格限制)
  - `简历版` (80-110 字，单页学术简历)
  - `陈述版` (150-220 字，个人自述信)
- **CLI 示例**：
  ```bash
  offerget baoyan audit "负责 8 卡 A100 集群微调实验，实测吞吐提升 34.2%，成果已整理在投。" --role 核心成员 --tier 简历版
  offerget baoyan compress "长段学术经历描述..." --tier 摘要版
  ```

### 2. 国内高校导师画像与高情商套磁信 (Advisor Matcher)
- **多阶段学术时间线分析**：追踪导师从传统方法向现代深度学习/大模型/具身智能的学术范式跃迁。
- **严谨交集计算与零幻觉防线**：依据候选人项目、论文与基础课程计算契合度，**绝不凭空捏造论文或虚构精读事实**。
- **防鸽与学术信誉红线**：提供 4 级口头承诺效力矩阵（弱好感/面试意向/导师口头/强锁定）、24-48小时决断原则、礼貌拒信模板与母校声誉保护机制。
- **CLI 示例**：
  ```bash
  offerget baoyan advisor examples/sample_advisor.json --profile examples/academic_profile.json --scenario summer_camp
  ```

### 3. 保研/考研全周期申请工作台 (Baoyan Pipeline)
- **状态机流转**：`COLLECTING_NOTICES` $\to$ `CONTACTING_ADVISOR` $\to$ `CAMP_APPLIED` $\to$ `CAMP_ACCEPTED` $\to$ `PRE_RECOMMENDED` $\to$ `FINAL_OFFER_LOCKED`。
- **动态材料清单**：针对直博、学硕、专硕及不同录取阶段（夏令营、预推免、九推、统考复试）生成五大类动态准备清单。
- **CLI 示例**：
  ```bash
  offerget baoyan checklist --profile examples/academic_profile.json --stage 夏令营 --track 直博
  ```

### 4. 项目答辩红蓝对抗模拟器 (Defense Simulator)
- **Claim-Evidence 对抗矩阵**：提取项目主张，标记 `Material-supported`、`Material-implied`、`Material-missing`。
- **3 级拷打烈度**：`先热个身` (基本定义与问题背景)、`开始挑刺` (Baseline 对比与选型动机)、`严刑拷打` (消融控制、独立代码行、极端工况与 15 分钟干净环境复现)。
- **答辩速查卡**：提炼软肋与不退让技术底线，提供实事求是的防守策略。
- **CLI 示例**：
  ```bash
  offerget defense simulate "面向长序列大语言模型的高效分布式 KV-Cache 压缩机制" --profile examples/academic_profile.json --intensity 严刑拷打
  ```

### 5. 轻量求职闭环审查工作台 (Career Review Agent / Skill v1)
- **标准化契约**：严格遵循 `career-review.v1` 输出协议，纯 Python 确定性规则引擎，无外部 API/LLM 依赖。
- **全流程五步闭环**：
  1. **岗位 JD 精细化拆解 (`jd_breakdown`)**：结构化拆解职责、必备硬门槛（学历/年限/专业）、核心技术技能、加分项与待确认信息。
  2. **基于真实事实的简历建议 (`resume_advice`)**：严格锚定候选人真实凭证路径（`source_path`），区分直接 (`direct`)、相邻 (`adjacent`)、弱证据 (`weak`) 和缺失 (`missing`)；严禁编造经历、技能或业绩，`unsupported` 严格不生成 safe_bullet。通过 `ResumePatch` 结构化实施，杜绝跨项目数字借用与无锚点经验污染。
  3. **针对性面试问题生成 (`interview_questions`)**：至少 3 道针对当前岗位与候选人的面试问题，涵盖核心职责验证 (`core_responsibility`)、项目深入挖掘 (`project_deep_dive`) 与技能边界考查 (`gap_boundary`)，自带考查意图、备考要点与关联证据。
  4. **一轮问答复盘反馈 (`answer_feedback`)**：接收候选人作答并进行确定性诊断：
     - `awaiting_answer`: 候选人尚未提交回答时的待提交状态；
     - `metric_drift`: 识别未在底稿中核验的量化指标与百分比漂移，输出保守修正答案并剥离虚高数字；
     - `experience_boundary`: 当候选人诚实说明“没做过/不了解”时，客观界定经验边界，指导如何沟通底层相通原理与技术调研路径，彻底废除模板化虚构说辞；
     - `well_defended`: 当回答具备明确基线、数据来源、个人因果归因与复盘时，予以认可并提炼进攻防守要点；
     - `uncertain`: 回答偏离主题或与问题不相关时，提醒重新聚焦核心考查点。
  5. **终面防守重点打磨 (`polish_focus`: "interview_defense")**：深挖指标 baseline 真实性、个人贡献边界与底层推导，输出针对性追问清单。
- **CLI 示例**：
  ```bash
  python cli.py review examples/synthetic_intern_jd.txt --profile examples/synthetic_intern_profile.json --answers examples/synthetic_intern_answers.json --output review.json --json
  ```

---

## 知识库速查映射 (Reference Catalog)

| 规范文件 | 核心内容与应用场景 |
|---|---|
| [jd-layers-5.md](references/jd-layers-5.md) | **5 图层 JD 拆解标准**：组织定位、硬核技术架构、商业影响、隐性黑话、红旗考核指标。 |
| [hidden-signals-lexicon.md](references/hidden-signals-lexicon.md) | **32 项黑话潜台词词典**：大厂话术对照真相与候选人应对战术。 |
| [red-flags-guide.md](references/red-flags-guide.md) | **技术陷阱与反问求证指南**：5 大致命红旗与 15 道黄金面试反问探针。 |
| [anti-ai-slop.md](references/anti-ai-slop.md) | **反 AI 写作指纹规范**：四大特征拦截、硬指标双重锚定与 CAR 事实因果重构。 |
| [interview-questions-bank.md](references/interview-questions-bank.md) | **大厂大模型面试 Top 20 深度题库**：3D 并行、MLA、MoE 路由、GRPO、PagedAttention、投机采样等。 |
| [claim-ledger-schema.md](references/claim-ledger-schema.md) | **原子主张事实台账规范**：4 维解耦、JSON Schema、证据定级与置信状态机。 |
| [methods-11.md](references/methods-11.md) | **ApexResume 战术手法 11 讲**：Mini-RFC、参数威慑、动词定级、因果反事实基线。 |
| [evidence-rules.md](references/evidence-rules.md) | **凭证等级与核验法则**：Level A/B/C/D 证据链支撑体系。 |
