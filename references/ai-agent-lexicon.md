# AI / 大模型 / Agent 全链路前沿技术术语字典与 Benchmark 规范

在大模型（LLM）、智能体（Autonomous Agents）与算法系统领域，专业术语不仅是简历信息密度的核心载体，更是面试官评估候选人技术纵深与工程沉淀的第一标尺。

本字典覆盖大模型研发与落地全生命周期：从 **数据管线 (Data) → 模型架构 (Model) → 训练微调 (Training) → 推理服务 (Serving) → 智能体工程 (Agent) → 评测与观测 (Eval)**，并规范工业级标准评测集与核心指标口径。

---

## 目录索引

1. [一、全链路技术架构全景图](#一一全链路技术架构全景图)
2. [二、数据工程与表征 (Data & Context Pipeline)](#二数据工程与表征-data--context-pipeline)
3. [三、基座与模型表征 (Model & Representation)](#三基座与模型表征-model--representation)
4. [四、训练与后对齐优化 (Training & Post-Training Alignment)](#四训练与后对齐优化-training--post-training-alignment)
5. [五、高性能推理与服务化 (Serving & High-Performance Inference)](#五高性能推理与服务化-serving--high-performance-inference)
6. [六、智能体架构与上下文工程 (Agent, Memory & Harness)](#六智能体架构与上下文工程-agent-memory--harness)
7. [七、权威评测基准与指标规范 (Benchmark & Metric Standards)](#七权威评测基准与指标规范-benchmark--metric-standards)
8. [八、面试官深挖追问清单与标准应答手册](#八面试官深挖追问清单与标准应答手册)

---

## 一、全链路技术架构全景图

工业级大模型与 Agent 应用开发遵循以下端到端闭环流水线：

```text
[Data Pipeline]
Raw Multimodal Corpus / Logs / Schemas
    ↓ (MinHash Deduplication, Heuristic Filters, Self-Instruct / Evol-Instruct Synthetics)
High-Quality SFT & Alignment Datasets (ChatML / ShareGPT Format)
    ↓
[Training & Alignment]
Pre-trained Foundation (Dense / MoE / MLA)
    ↓ (Full SFT / LoRA / DoRA -> DPO / KTO / GRPO Reinforcement Learning with PRM)
Aligned Reasoning / Instruction Model
    ↓
[Serving & Optimization]
AWQ / FP8 Quantization -> vLLM / SGLang Engine (RadixAttention, Chunked Prefill)
    ↓ (High-Throughput, Low TTFT REST / gRPC API)
[Agent & Harness Architecture]
Coordinator / Planner -> Context Engineering (Write / Select / Compress / Isolate)
    ↓ (MCP Protocol, Sandboxed Shell / Python Execution, Multi-Agent Collaboration)
Execution Artifacts (PRs, SQL, Reports, Actions)
    ↓
[Eval & Observability]
SWE-bench / GAIA / BIRD -> Trajectory Tracing (Failure Onset, Evidence-to-Action Gap)
    ↓ (LLM-as-Judge with Rubric -> Continuous Feedback Loop to Data Pipeline)
```

---

## 二、数据工程与表征 (Data & Context Pipeline)

| 术语 / 概念 | 英文全称 / 标准缩写 | 核心原理解析与工程实践 | 简历高频搭配场景 |
|:---|:---|:---|:---|
| **去重与清洗** | Deduplication (MinHash, SimHash) | 利用 MinHash + LSH（局部敏感哈希）或向量相似度聚类对百亿级海量文本进行文档级与句级去重，消除数据冗余与数据偏置。 | `海量语料清洗`、`TB级清洗流水线` |
| **合成数据** | Synthetic Data Generation | 运用 Evol-Instruct、Self-Instruct 或 Mix Diverse GPTs 策略，通过多智能体角色互搏或进化提示词生成跨领域的高难度、多样化长程推理问答。 | `高质量样本合成`、`解决冷启动问题` |
| **数据污染检测** | Data Contamination Detection | 在训练集与开源 Benchmark（如 HumanEval、SWE-bench、GSM8K）之间运行 n-gram 重叠度或嵌入距离检测，确保评测零泄露。 | `严谨评测闭环`、`防模型刷榜过拟合` |
| **模式链接** | Schema Linking | 在 NL2SQL 或复杂 API 调用中，将自然语言意图精准映射至数据库表结构名、列字段名、外键关系及 API JSON Schema 的前置语义对齐技术。 | `NL2SQL全链路`、`企业知识库检索` |
| **难样本挖掘** | Hard Negative Mining | 在对比学习或检索匹配中，主动从模型推导失败的候选集、相似混淆实体中提取负样本，迫使模型学习细粒度判别边界。 | `多模态检索`、`Embedding重排` |
| **对话格式对齐** | ShareGPT / ChatML Protocol | 结构化多轮对话序列化规范（`system`, `user`, `assistant`, `tool_call`, `tool_result`），支持精准的状态与时间序列记录。 | `数据标准化`、`模型微调输入` |

---

## 三、基座与模型表征 (Model & Representation)

| 术语 / 概念 | 英文全称 / 标准缩写 | 核心原理解析与工程实践 | 简历高频搭配场景 |
|:---|:---|:---|:---|
| **混合专家模型** | MoE (Mixture of Experts) | 采用稀疏激活路由（Sparse Gating / Top-k Routing），每个 Token 仅激活少数专家网络（如 8 选 2），在扩大总参数量的同时大幅降低推理计算成本（FLOPs）。 | `MoE架构优化`、`长文本高吞吐` |
| **多头潜在注意力** | MLA (Multi-Head Latent Attention) | 如 DeepSeek 系列所采用，将注意力键值对（KV）联合压缩为低维潜在向量，将推理期显存中 KV Cache 大小锐减 80% 以上。 | `极致推理显存压缩`、`超长上下文支持` |
| **高效注意力机制** | FlashAttention-2 / FlashAttention-3 | 深入 GPU SRAM 硬件层级的分块（Tiling）算法，避免频繁对全局 HBM（高带宽显存）读写注意力权重矩阵，实现显存降低 $O(N)$ 与速度倍增。 | `底层算子加速`、`训练吞吐调优` |
| **长文本位置编码** | RoPE / YaRN / LongRoPE | 旋转位置编码（Rotary Position Embedding）及其插值扩展变体，通过基频调整与非均匀缩放将模型有效上下文窗口扩展至 128k ~ 1M tokens。 | `超长文档问答`、`百万Token架构` |
| **跨模态表征对齐** | CLIP, LanguageBind, VideoLLaVA | 通过双塔对比学习将文本、图像、音频与视频模态映射至统一潜空间；利用时空 Transformer 提取视频分帧切片的多维表征。 | `多模态营销理解`、`视频意图识别` |
| **投机草稿模型** | Small Speculative Draft Model | 使用参数极小的辅助小模型先行快速生成候选 Token 序列，再由大模型一次性并行验证，打破自回归解码的顺序时钟墙。 | `Speculative Decoding`、`延迟敏感服务` |

---

## 四、训练与后对齐优化 (Training & Post-Training Alignment)

| 术语 / 概念 | 英文全称 / 标准缩写 | 核心原理解析与工程实践 | 简历高频搭配场景 |
|:---|:---|:---|:---|
| **全量监督微调** | Full Parameter SFT | 更新所有模型权重参数的端到端监督微调，通常用于特定纵深工业场景或基座知识深度灌注。 | `领域基座垂直对齐` |
| **低秩自适应微调** | LoRA / QLoRA / DoRA | 在线性层旁路冻结原始权重引入低秩分解矩阵 $A \times B$；QLoRA 结合 4-bit NormalFloat 量化；DoRA 解耦权重幅值与方向，极低显存达成全量微调性能。 | `轻量微调`、`单卡/多卡消费级适配` |
| **直接偏好优化** | DPO (Direct Preference Optimization) | 跳过显式奖励模型（Reward Model）的训练，直接通过解析闭式解将人类偏好成对数据（Chosen vs Rejected）转换为隐式强化学习梯度更新。 | `对齐与安全围栏`、`少幻觉优化` |
| **群体相对策略优化** | GRPO (Group Relative Policy Optimization) | 消除传统 PPO 算法中独立的 Value Network（节省巨额显存），通过针对同一 Query 采样一组输出（Group），以组内平均奖励作为相对 Baseline 计算 Advantage 进行策略梯度更新。 | `复杂数学推理`、`Coding Agent对齐` |
| **过程奖励模型** | PRM (Process Reward Model) | 区别于仅看终局对错的结果奖励（ORM），PRM 对思维链（CoT）中的每一个步骤进行独立细粒度打分，精准定位步骤性逻辑错误。 | `Step-by-step推理强化`、`数学证明` |
| **思维链演进** | Short CoT vs Long CoT | 短 CoT 聚焦高精炼语法输出以节省 Token 与延迟；长 CoT 允许模型自主生成反思（Reflection）、回溯验证与多路径推演，突破复杂逻辑瓶颈。 | `NL2SQL精炼`、`复杂算法解题` |

---

## 五、高性能推理与服务化 (Serving & High-Performance Inference)

| 术语 / 概念 | 英文全称 / 标准缩写 | 核心原理解析与工程实践 | 简历高频搭配场景 |
|:---|:---|:---|:---|
| **高性能推理引擎** | vLLM / SGLang / TensorRT-LLM | 业内主流高性能推理框架；SGLang 特别擅长复杂结构化生成、多轮 Agent 交互以及前缀树显存复用调度。 | `生产级推理网关`、`高性能API设计` |
| **分页注意力** | PagedAttention | 借鉴操作系统虚拟内存分页思想，将离散的 KV Cache 存放在非连续物理显存块中，消除显存碎片，将单卡并发吞吐量提升 2~4 倍。 | `显存利用率打满`、`高并发系统架构` |
| **基数树缓存复用** | RadixAttention | 在多轮对话与多智能体分叉中，将已计算的 Prompt KV Cache 组织为前缀基数树，命中已生成前缀时完全跳过 Prefill 计算，延迟趋近于 0。 | `多轮Agent推理优化`、`大幅降低TTFT` |
| **分块预填充** | Chunked Prefill | 将超长 Prompt 的 Prefill 阶段拆分为多个较小的计算块，与正在进行的 Decode 阶段混合 Batching，解决大请求导致的推理管线微顿挫。 | `平滑长尾延时`、`保障SLA稳定性` |
| **首字时间与吞吐** | TTFT / ITL / TPS | **TTFT** (Time to First Token): 首个 Token 返回耗时；**ITL** (Inter-Token Latency): 生成阶段相邻 Token 耗时；**TPS**: 单卡/集群每秒吐字数。 | `压测指标冠名`、`SLA服务质量承诺` |
| **先进权重激活量化** | AWQ / GPTQ / FP8 (W8A8) / FP4 | **AWQ**: 保护 1% 最重要显著权重的前提下对矩阵进行 4-bit 缩放量化；**FP8**: 利用 Hopper 架构 Native 硬件单元实现近乎无损的 2x 推理加速。 | `大模型端侧/边缘部署`、`算力成本降低` |

---

## 六、智能体架构与上下文工程 (Agent, Memory & Harness)

| 术语 / 概念 | 英文全称 / 标准缩写 | 核心原理解析与工程实践 | 简历高频搭配场景 |
|:---|:---|:---|:---|
| **推理行动协同范式** | ReAct (Reasoning + Acting) | 智能体经典的 `Thought -> Action -> Observation` 循环，将内在的逻辑演绎与外部环境的工具感知深度交织。 | `自主智能体基础架构` |
| **模型上下文协议** | MCP (Model Context Protocol) | 由 Anthropic 推出的行业开放标准协议，为大模型统一接入本地文件系统、数据库、GitHub API 及沙箱工具提供标准化 RPC/JSON 规范。 | `前沿插件生态`、`标准化工具编排` |
| **长程智能体测试框架** | Long-Horizon Agent Harness | 负责管理长程智能体执行生命周期（超 50+ 轮交互）的运行底座，包含状态机调度、环境沙箱管理、日志打点与错误恢复。 | `企业级自主Agent`、`SWE-bench系统` |
| **上下文工程四分法** | Context Engineering (Write / Select / Compress / Isolate) | 处理长上下文的核心架构范式：**Write** 持久化写盘；**Select** 精准预算切片；**Compress** 语义压缩蒸馏；**Isolate** 子智能体物理上下文隔离。 | `避免注意力沉沦`、`长程续跑稳定性` |
| **微压缩与滚动记忆** | Micro-Compaction & Rolling Buffer | 当 Token 触及安全警戒线（如 80%）时，在不打断推理会话的前提下，静默对过去多轮工具调用的输出进行截断与语义摘要折叠。 | `无限轮次对话`、`杜绝OOM崩溃` |
| **快照断点与回滚** | Checkpoint & Rollback | 在智能体调用具有破坏性副作用（如写文件、执行 Shell、提交 Git）前对环境与记忆进行 Snapshot 固化，失败时原子回滚状态。 | `沙箱执行一致性`、`防止脏状态蔓延` |
| **代码执行沙箱** | Execution Sandboxing (Docker / Firecracker) | 提供轻量隔离虚拟化环境，供智能体安全执行 Shell、运行测试用例、编译依赖并捕获标准输入输出（stdout/stderr/exitcode）。 | `安全代码修复`、`自动化测试在环` |

---

## 七、权威评测基准与指标规范 (Benchmark & Metric Standards)

### 7.1 权威评测集矩阵

| 领域分类 | 评测集名称 | 评测维度与考查核心 | 工业界权威基线 / 顶级水平参考 |
|:---|:---|:---|:---|
| **代码与真实工程修复** | **SWE-bench (Verified / Lite)** | 考验 Agent 在复杂实际 GitHub Python 仓库中定位 Issue 并生成可合并通过单元测试的 Patch 补丁能力。 | 行业主流顶尖水平介于 25% ~ 50% 之间（Pass@1） |
| **基础算法与编程逻辑** | **HumanEval / MBPP** | 考查单函数级别的 Python 代码生成与自动化单测通过率。 | SOTA 模型通常达到 85% ~ 95%+ |
| **复杂逻辑与数学推理** | **MATH / GSM8K** | 考查小学至高中/竞赛级数学多步推导求解能力。 | GSM8K SOTA > 95%，MATH SOTA > 70% |
| **真实世界通用智能体** | **GAIA (General AI Assistants)** | 综合考查网页浏览、多格式文件处理、多模态图表阅读与长程工具编排能力。 | 行业顶尖水平介于 35% ~ 65% |
| **网页交互与GUI操作** | **WebArena / Mind2Web** | 在高度仿真的全功能电商、社交、论坛网站中完成端到端任务操作的成功率。 | 行业领先水平约为 15% ~ 35% |
| **工具调用与API路由** | **ToolBench / Berkeley FC** | 考查在 10,000+ 真实外部 REST API 中进行意图检索、参数填充与多步骤调用的鲁棒性。 | Win Rate & Pass Rate |
| **关系型数据库与SQL** | **Spider / BIRD-SQL** | 真实大规模数据库上的跨表复杂 SQL 生成与执行准确率（Execution Accuracy）。 | BIRD-SQL EX 领先水平在 65% ~ 75% |

### 7.2 核心量化指标统计口径规范

1. **Pass@1 vs Pass@k**：
   - **Pass@1**：每个任务仅采样 1 次输出，通过单测即算成功（最贴近线上真实成本与体验）；
   - **Pass@k**：每个任务采样 $k$ 个候选解，只要有 1 个通过即算成功；简历中必须显式标明是 Pass@1 还是 Pass@k。
2. **执行准确率 (Execution Accuracy, EX)**：
   - 区别于单纯比较 SQL 文本相似度的 Exact Match (EM)；EX 要求将生成的代码/SQL 注入真实测试数据库执行，比对真实返回值集合是否 100% 一致。
3. **成本与显存口径 (Cost-per-Task / Token-Efficiency)**：
   - 标注指标时，应写明每解决单个任务消耗的平均 Token 数、API 调用花销（USD / 任务）以及峰值显存降低百分比。

---

## 八、面试官深挖追问清单与标准应答手册

### Q1：你在简历里写了 GRPO，它和 PPO 的根本区别是什么？为什么选择 GRPO？
- **标准回答切入点**：
  1. **架构差异**：传统 PPO 需要额外训练一个参数量相当的 Critic/Value Network 来估计状态价值 $V(s)$；而 GRPO 完全移除了 Value Network，直接从同一 Prompt 采样的一组候选输出（Group）的平均奖励作为基线，大幅削减了显存占用；
  2. **显存优势**：在分布式大模型训练中，无需维护 Critic 模型的反向传播与优化器状态，显著提升批处理大小（Batch Size）；
  3. **适用场景**：在规则确定、有明确单测或编译结果（Rule-based Verifier）的代码与数学任务中，组内相对优势（Group Relative Advantage）收敛极为稳定。

### Q2：RadixAttention 是如何利用基数树提升多轮 Agent 推理性能的？
- **标准回答切入点**：
  1. **状态维护**：传统推理引擎在会话结束后往往释放 KV Cache；而 RadixAttention 将所有完成的请求及其 Token 序列作为前缀路径保存在前缀树（Radix Tree）结构中；
  2. **零开销复用**：当后续 Agent 执行、分叉子智能体或多轮对话发起时，系统在树上进行前缀匹配；匹配到的 Token 历史的 KV Cache 直接重用其物理显存指针，免去 Prefill 阶段的高额矩阵乘法；
  3. **驱逐策略**：当显存水位达到警戒线时，采用 LRU 算法逐出叶子节点的 Cache，兼顾长程对话命中率与系统吞吐。

### Q3：什么是 Evidence-to-Action Gap？你们在工程上是如何解决的？
- **标准回答切入点**：
  1. **现象定义**：指 Agent 能够通过检索或阅读代码精准找到引发 bug 的文件与行号（Evidence 已在上下文中），但在最终调用 Patch 工具或执行修改时，模型给出了错误的参数格式、遗漏了前置依赖或产生了臆想的语法（Action 失败）；
  2. **工程解法**：采用**“两阶段决策分离”**——第一阶段让模型输出纯文本的反思与修改规划（Plan/COT）；第二阶段通过强类型 Schema 注入与专有参数解析器（Argument Parsing Layer）进行受限采样，配合轻量级沙箱的 Test-in-the-Loop 进行前置语法干预，消除格式断层。

### Q4：Context Engineering 的“Write/Select/Compress/Isolate”四分法具体如何落地？
- **标准回答切入点**：
  1. **Write**：将 Agent 每一轮运行产生的长文本中间结果（如执行 500 行的 Shell 输出）落入沙箱虚拟磁盘文件，上下文只保留摘要与引用路径；
  2. **Select**：在下一轮思考时，通过向量余弦距离 + BM25 混合检索，只检索与当前子任务强相关的记忆切片；
  3. **Compress**：上下文超过预设窗口（如 180k）时，触发异步总结机制，将历史多轮轨迹沉淀为标准状态变更表（Status Ledger）；
  4. **Isolate**：父子智能体通信时，子智能体运行在纯净上下文容器中，仅获取任务指令与输入产物，防止父智能体沉重的历史上下文对子任务产生注意力干扰。
