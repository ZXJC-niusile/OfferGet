# ApexResume ATS 纯文本 / Markdown 规范与通用模板

## 1. 概述与设计目标

在国内外现代招聘管理系统（ATS, Applicant Tracking System，如国内的 **Moka、北森、飞书招聘、智联、猎聘、牛客**，以及海外的 **Lever、Greenhouse、Workday、Taleo、Ashby**）中，简历通常首先经过自然语言实体识别（NER）引擎与规则解析器的抽取，转换成结构化数据供 HR 搜索、初筛与打分。

复杂的 PDF 排版（多栏并排、嵌入表格、文本框、浮动图标、特殊字符）经常导致解析器出现**“列文字混杂串行”、“字段错位”、“工作年限识别失败”、“技术栈丢失”**等灾难性问题。

**ATS-Plain 规范**旨在提供一套格式标准化、解析鲁棒、零视觉噪音的纯文本/Markdown 履历模板，确保在各类 ATS 系统的字段匹配率达到 **99.9%**。

---

## 2. ATS 结构化解析核心规则

### 2.1 目录与模块命名映射 (Section Name Standard)
ATS 依赖关键词字典匹配模块起始位置，**严禁使用生僻词或无分割连续文本**。统一采用以下标准一级/二级标题：

| 推荐标准标题 | 英文 ATS 映射 (Lever / Workday) | 严禁使用的别名/花哨词 |
|:---|:---|:---|
| `## 个人信息` 或头部三段式 | `Contact Information` | `关于我`, `Whoami`, `个人概况` |
| `## 教育背景` | `Education` | `求学生涯`, `象牙塔`, `Academic` |
| `## 工作经历` / `## 实习经历` | `Work Experience` / `Employment History` | `职业轨迹`, `江湖路远`, `Professional Timeline` |
| `## 项目经历` | `Project Experience` / `Projects` | `作品集`, `攻坚战役`, `Portfolio` |
| `## 专业技能` | `Technical Skills` / `Skills` | `兵器库`, `武艺`, `Tech Arsenal` |
| `## 荣誉奖项` / `## 开源贡献` | `Honors & Awards` / `Open Source & Publications` | `光辉时刻`, `荣誉殿堂` |

### 2.2 接触信息标准格式 (Contact Pattern)
- 电话号码：保持国内 11 位连续或连字符格式，如 `13800138000` 或 `(+86) 138-0013-8000`。
- 邮箱地址：标准格式 `name@domain.com`，避免在 ATS 输入框中附带多余中文备注。
- 个人链接：完整协议头 `https://github.com/username`，避免直接裸写非标准文本。
- 所在城市：标准格式 `中国 · 北京` 或 `Beijing, China`。

### 2.3 时间与日期标准化 (Date Time Pattern)
ATS 解析引擎使用正则提取起止时间。推荐格式：
- `YYYY.MM - YYYY.MM`（例：`2024.03 - 2025.06`）
- `YYYY.MM - 至今`（海外系统：`2024.03 - Present`）
- **严禁格式**：`24年春 - 25年夏`、`2024/3/1至2025/6/30`、混用中文句号与逗号。

### 2.4 严禁破坏解析的排版元素
1. **严禁嵌套复杂 HTML 表格**：绝大多数 ATS 解析表格时按行连缀读取，导致左列公司名与右列项目内容错位拼接。
2. **严禁分栏 (Multi-column)**：分栏会导致跨栏左右折行混流。
3. **严禁图片化文本**：避免把公司 Logo、学历证书截图当成内容主体。
4. **统一列表符号**：正文统一使用单层无序列表 `- `，避免使用 Emoji（如 🚀, 💡, 🔥）替代 Bullet，防止部分老旧系统字符编码乱码（`\ufffd`）。

---

## 3. ATS-Plain Markdown 标准模板

```markdown
# [真实姓名]

[手机号] | [电子邮箱] | [城市地区] | GitHub: [https://github.com/yourhandle] | LinkedIn: [https://linkedin.com/in/yourhandle]

---

## 核心定位与技术主线
- **核心定位**：[大模型 / Agent 算法工程师 / 架构师]（[目标年限/跳级/全职] · 具有从 0 到 1 架构设计与模型全链路落地经验）
- **主线概括**：深耕 [技术方向1] 与 [技术方向2]，主导从 [起点架构/模型] 到 [演进形态/长程系统] 的端到端闭环工程。

---

## 工作经历

### [公司名称] | [所属部门] | [职位名称 / 角色]
**任职时间**：2024.03 - 至今  
**主要职责**：[模块级 Owner / 策略架构负责人]，负责 [最小闭环范围]，打通 [Data -> Model -> Training -> Serving -> Agent -> Eval] 全链路。

- **[主导核心链路或演进项目名称]**
  - **业务痛点**：[描述原系统关键瓶颈，如吞吐瓶颈、长程漂移、幻觉率高]，难以支撑 [具体业务指标/QPS]。
  - **技术方案**：主导设计 [系统/模块名称]，引入 [前沿算法/方法论]，实现从 [旧架构] 到 [新架构] 的演进。
  - **落地细节**：
    - 数据与训练：通过 [数据清洗策略/合成样本] + [SFT / LoRA / GRPO]，优化 [核心损失/对齐效果]。
    - 推理与系统：采用 [vLLM / SGLang / AWQ / 算子优化]，将单任务端到端延时从 [X ms] 压缩至 [Y ms]。
    - Agent与状态：构建 [Context Engineering 四分法 / MCP 协议扩展]，实现 [并发/会话管理/容错重试]。
  - **量化收益**：在 [标准测试集/生产线] 上，[核心指标] 提升约 [X%+]，推理算力成本降低约 [Y%+]，稳定支撑日均 [Z 万次] 线上请求。

---

## 项目经历

### [项目名称 1]（[开源/独立研发/商用]）
**项目角色**：项目 Owner / 核心开发者  
**项目周期**：2023.09 - 2024.02  
**项目链接**：https://github.com/org/repo (Stars: 10k+)

- **架构设计**：完全负责从 0 到 1 架构设计与实现（CLI 入口：`cli run --mode=eval`），构建 [核心模块1] 与 [核心模块2]。
- **技术突破**：
  - 针对 [特定现象/Evidence-to-Action Gap 等诊断问题]，提出 [解决方案]，解决长上下文推理遗忘问题。
  - 沉淀评测闭环流水线（Benchmark Suite），覆盖 [A/B/C/D] 关键失败用例集。
- **评测与成果**：SWE-bench 系列难题解决率较基线提升约 [25%+]，获行业知名技术社区周榜第 1 名，被 [多家机构/厂商] 采纳部署。

---

## 教育背景

### [学校名称] | [院系专业] | [学位（本科/硕士/博士）]
**就读时间**：2020.09 - 2024.06  
**院校属性**：[国家“双一流” / 985 / 211 / 国际高校联盟成员]  
**学业表现**：GPA: [3.8/4.0] (前 5%) | 核心课程：数据结构、分布式系统、深度学习、计算机体系结构

---

## 专业技能

- **大模型与算法**：精通 Transformer 架构、MoE 原理、注意力机制优化（FlashAttention-2/3）、Post-training 对齐（SFT, DPO, GRPO, PRM）。
- **Agent 与上下文工程**：深入理解 ReAct 范式、Model Context Protocol (MCP)、Context Engineering（Write/Select/Compress/Isolate）、长程任务状态机与记忆滚动。
- **高性能推理与部署**：熟练运用 vLLM、SGLang、TGI、TensorRT-LLM，具备 Chunked Prefill、Speculative Decoding、AWQ/FP8 量化调优经验。
- **工程与编程语言**：Python (精通，深入源码与异步并发)、C++ / CUDA (基础算子实现与加速)、Go / Rust、Linux、Docker、Kubernetes。

---

## 荣誉与资质

- **开源贡献**：[Apache 顶级项目 Committer / 某大厂开源项目 Maintainer]，累计提交并合并 PR [X] 个。
- **竞赛与奖项**：[国家奖学金 / 顶级算法挑战赛全国前 1% / 创新黑客松一等奖]。
- **学术成果**：在 [ACL / CVPR / NeurIPS / ICLR] 发表论文 [X] 篇（[第一作者/共同作者]）。
```

---

## 4. ATS-Plain 实战示范样例（AI Agent 架构师范本）

```markdown
# 张若澜 (Alan Zhang)

(+86) 138-0018-8888 | alan.zhang@ai-nexus.tech | 中国 · 北京 | GitHub: https://github.com/alanzhang-ai

---

## 核心定位
- **定位**：Full-Stack AI Agent 算法工程师 / 架构负责人（Apache 顶级项目 Committer · 具有千万级流量系统从 0 到 1 落地经验）
- **技术链路**：主导构建从“模型微调推理”到“长程复杂智能体任务 Harness 与状态机持久化”全链路。

---

## 工作经历

### 智元未来人工智能研究院 | 基础模型与智能体工程部 | AI Agent 策略架构 Owner
**任职时间**：2024.04 - 至今  
**职责范围**：独立负责企业级 Autonomous Coding Agent 核心引擎研发，覆盖 Data Cleaning、GRPO 强化学习、AWQ 量化加速及 Context Engineering 全流程。

- **企业级长程代码智能体（Code-Harness Engine）架构演进**
  - **业务痛点**：原有 1.0 架构采用散落的 Prompt 胶水代码，存在严峻的上下文溢出漂移与工具调用死循环，平均多轮交互成功率仅 26.9%。
  - **架构重构**：从 0 到 1 主导设计 2.0 模块化中间件流水线（CLI: `agent-harness run --task=repo-fix`），将系统解耦为 Coordinator（意图识别）、Planner（任务拆解）、Worker（MCP 工具执行）与 Inspector（反思校验）四层架构，实现推理调度核心零侵入扩展。
  - **关键技术**：
    - 上下文工程：落地 Context Engineering 四分法（Write 中间状态、Select 预算切片、Compress 轻量摘要、Isolate 子智能体上下文隔离），将 250k+ 超长历史稳定压缩至 12k 精准上下文。
    - 强化对齐：构建基于真实执行反馈的 GRPO 奖励模型，以单元测试通过与 Lint 零报错为奖励信号，有效弥合“证据-行动断层（Evidence-to-Action Gap）”。
    - 高性能推理：部署 SGLang + RadixAttention，集成 AWQ W4A16 量化，首 Token 延迟（TTFT）降低 42%，吞吐量提升 2.6 倍。
  - **落地成果**：SWE-bench 复杂任务解决率较原始全量重跑提升约 28.5%+，单任务 API 显存与 Token 推理成本降低约 35%+，日均支撑研发团队自动修复 Issue 200+ 例。

---

## 项目经历

### Nexus-Agent: 高性能多智能体协同框架（开源）
**项目角色**：开源发起人 & 核心 Maintainer  
**项目周期**：2023.10 - 2024.03  
**项目仓库**：https://github.com/nexus-ai/nexus-agent (Stars: 8.4k)

- **系统设计**：完全负责基于 Model Context Protocol (MCP) 的动态工具调用运行时设计，支持开发者以热插拔方式注册外部 API 与本地沙箱容器。
- **状态一致性**：引入事件驱动的 Snapshot & Rollback 机制，在 Agent 执行外部副作用（如数据库写、文件篡改）前自动留存可回滚断点，彻底杜绝脏状态蔓延。
- **社会证明**：GitHub Trending 日榜全球第 3 名，累计合并社区 PR 140+ 个，被 5 家一线 AI 初创企业作为核心底层 Agent 框架引入生产环境。

---

## 教育背景

### 北京航空航天大学 | 软件学院 | 软件工程 (工学学士)
**就读时间**：2020.09 - 2024.06  
**学校属性**：国家“双一流”建设高校 · 原“985工程”优势学科创新平台  
**主修课程**：分布式系统设计、现代操作系统原理、编译原理、自然语言处理、算法设计与分析

---

## 专业技能

- **模型与训练**：熟悉 Transformer 原理，熟练掌握 PyTorch、DeepSpeed、Megatron-LM；有 LoRA、DPO、GRPO 完整调优经验。
- **Agent 与上下文**：精通 ReAct 模式、Tool Calling 协议机制、Model Context Protocol (MCP)、长程任务状态机与记忆压缩策略。
- **部署与系统优化**：熟练掌握 vLLM、SGLang、Triton Inference Server、CUDA 基础优化、Docker 容器沙箱隔离。
- **工程与编程语言**：精通 Python、Rust、C++；熟练使用 Linux、Git、CI/CD 自动化流水线。
```

---

## 5. ATS 兼容性自检清单 (Pre-Flight Checklist)

在将简历投递或导入招聘系统前，请逐项核对：

- [ ] **无隐藏字符**：未包含不可见 Unicode 字符、零宽空格、非标准控制字符。
- [ ] **无嵌套表格**：未采用 Markdown Table 或 HTML `<table>` 承载核心工作经历或技能详情。
- [ ] **标准时间格式**：所有经历均具备明确且标准的 `YYYY.MM - YYYY.MM` 格式。
- [ ] **标准职位与公司名**：公司名使用工商注册全称或业界权威公认名称，职位名对齐行业通用标准（如：算法工程师、后端架构师）。
- [ ] **标准关键词密度**：技术栈包含行业主流缩写与全称（如：`PyTorch`、`vLLM`、`GRPO`、`Transformer`），方便系统全文倒排索引秒级召回。
- [ ] **单栏线性排布**：自上而下顺次阅读，符合自然段落逻辑流。
