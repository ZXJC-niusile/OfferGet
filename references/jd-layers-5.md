# 5 图层 JD 拆解标准与 AI 大模型岗位专属定义

> **OfferGet 核心方法论**：任何一份职位描述（Job Description, JD）都不是平铺直叙的任务清单，而是组织权力结构、技术焦虑、资源壁垒与招聘妥协的聚合投影。
> 本框架将任意 JD 纵向切分为 **5 个物理与逻辑图层**，帮助候选人穿透 HR 格式化模板，直达用人团队（Hiring Manager, HM）的真实诉求与考核红线。

---

## 5 图层总览架构

```
┌────────────────────────────────────────────────────────┐
│  Layer 1: 组织坐标与业务护城河 (Organization & Mission)   │ 
├────────────────────────────────────────────────────────┤
│  Layer 2: 核心硬性技术与架构能力 (Hard Tech & System)     │
├────────────────────────────────────────────────────────┤
│  Layer 3: 产研协同、商业落地与软素质 (Product & Impact)   │
├────────────────────────────────────────────────────────┤
│  Layer 4: 隐性门槛与招聘潜台词 (Implicit Filters)        │
├────────────────────────────────────────────────────────┤
│  Layer 5: 红旗陷阱与成败考核指标 (Red Flags & OKR Reality)│
└────────────────────────────────────────────────────────┘
```

---

## Layer 1: 组织坐标与业务护城河 (Organization & Mission)

### 1.1 核心定义
该图层回答：**这个团队在公司版图中处于什么地位？为什么在当下节点设立此 HC？**
- **业务属性**：核心现金流业务 / 战略孵化业务 / 边缘降本业务 / 技术品牌宣发业务。
- **汇报关系**：向 CTO / 首席科学家 / 业务线 VP / 基础架构 Head 汇报。汇报层级越高，战略定力通常越强；向传统业务线转型的二线主管汇报，容易陷入“短期指标考核陷阱”。
- **商业护城河**：公司依靠什么变现？大模型在此环节是核心发动机（Core Engine）还是包装外壳（Wrapper）？

### 1.2 AI 大模型团队组织坐标分类

| 团队类型 | 核心使命 | 典型资源配置 | 招聘偏好 |
|---|---|---|---|
| **Infra & 算力底座** | 打造高性能训练/推理异构集群，降低单 Token 成本 | 万卡/千卡独占集群、自建机房、RDMA 网络 | 极致工程追求，精通 CUDA、NCCL、Megatron、网络拓扑 |
| **Foundation Pre-training** | 研发下一代基座多模态/大语言模型，刷榜与突破 Scaling Law | 充足算力预算，自建百 TB 高质量语料库 | Top 会议一作（ICLR/NeurIPS）、数理基础极深、对 Loss 敏感 |
| **Post-training & Alignment** | SFT、RLHF、GRPO、DPO、长文本与数学/代码推理强化 | 数百至数千卡资源，自建人工评估团队 | 算法与数据敏感度高，精通 PPO/DPO/GRPO 调优与奖励建模 |
| **Agentic & 应用落地** | 垂直业务场景（代码生成、企业搜索、具身规划、自动化工作流） | API Token 额度、中小型推理集群、微调资源 | 全栈与系统架构能力强，精通 RAG、MCP、Tool-Calling、内存管理 |
| **端侧/推理部署组** | 端侧量化（NPU/Mobile）、极致低延迟、投机采样、长上下文缓存 | 异构硬件测试机、移动端芯片、算子优化工具 | 精通 INT4/AWQ/FP8、TensorRT-LLM、vLLM、算子手撕优化 |

---

## Layer 2: 核心硬性技术与架构能力 (Hard Tech & System)

### 2.1 核心定义
该图层定义岗位的 **Must-Have 硬指标**。是初筛简历机审与首轮技术面手撕代码/系统设计的硬门槛。

### 2.2 AI 大模型核心技术雷达拆解

#### A. 模型架构与算法原理 (Modeling & Algorithms)
- **Transformer 变体**：RoPE、ALiBi、SwiGLU、RMSNorm、Grouped-Query Attention (GQA)、Multi-Head Latent Attention (MLA)。
- **稀疏化架构 (MoE)**：Top-K Expert Routing、Load Balancing Loss、Shared Experts 机制。
- **对齐与强化学习**：PPO (Actor-Critic 架构)、Direct Preference Optimization (DPO)、Group Relative Policy Optimization (GRPO)、KTO。

#### B. 分布式并行与大规模工程 (Distributed Training & Infra)
- **3D/4D 并行体系**：Tensor Parallel (TP)、Pipeline Parallel (PP)、Sequence Parallel (SP)、Context Parallel (CP)、Zero Redundancy Optimizer (ZeRO 1/2/3)。
- **主流框架**：Megatron-LM 底层源码改造、DeepSpeed、FlashAttention-2/3 算子调优。
- **故障自愈与容错**：千卡训练 Checkpoint 秒级保存/恢复、慢节点检测（Straggler Detection）、通信重叠（Overlap）。

#### C. 高性能推理与服务化 (Inference & Serving)
- **推理引擎**：vLLM、TensorRT-LLM、SGLang、TGI。
- **量化与压缩**：FP8 (E4M3/E5M2)、AWQ、GPTQ、SmoothQuant、KV-Cache 量化（INT8/FP8）。
- **解码优化**：PagedAttention、Chunked Prefill、投机采样 (Speculative Decoding)、Prefix Caching。

#### D. Agent 与上下文工程 (Agentic Systems & Context)
- **协议与框架**：Model Context Protocol (MCP)、ReAct 循环、Plan-and-Solve、LangGraph。
- **RAG 演进**：GraphRAG、混合检索（稠密+稀疏 BM25）、重排模型（Reranker）、自适应分块。
- **状态与记忆**：Long-term Vector Memory、Session State KV 压缩、Reflection 自省机制。

---

## Layer 3: 产研协同、商业落地与软素质 (Product & Impact)

### 3.1 核心定义
该图层回答：**候选人能否将技术能力转化为真实的业务与组织价值？**
大模型技术极其昂贵，企业最怕“拿着顶级算力刷学术玩具、却对业务成本与转化率毫无感知”的候选人。

### 3.2 核心考核维度
1. **ROI 与成本核算意识**：
   - 是否关注单请求成本（Cost per 1k tokens）？
   - 是否具备在小模型（7B/14B）微调与超大模型（70B+）API 之间进行权衡架构决策的能力？
2. **生产环境稳定性与防护 (Safety & Guardrails)**：
   - 越狱攻击防御、幻觉抑制、敏感词过滤、输出格式强校验（JSON Schema 保证）。
3. **跨学科与产研推进力**：
   - 能否向非技术业务方解释模型能力的边界？
   - 能否推动产品设计妥协以适配大模型的概率性输出特性？

---

## Layer 4: 隐性门槛与招聘潜台词 (Implicit Filters)

### 4.1 核心定义
JD 上没有公开写明、或写得极其含蓄，但在面试官心里具有“一票否决权”或“极大加分权”的潜规则。

### 4.2 AI 岗位典型隐性门槛
1. **算力体量脱敏背书**：
   - 字面：*“有分布式训练经验”*
   - 隐性真实要求：**真正烧过 128 卡以上独占集群**，踩过实际挂卡、NCCL 超时、梯度爆炸、Loss Spike 真实故障。只在学校 2 张 3090 上跑 LoRA 会被直接降档。
2. **顶会一作与学术圈人脉**：
   - 核心前沿算法组通常只招收特定实验室（清华、北大、上交、浙大、中科院计算所、CMU、Stanford 等）或知名导师的门生。
3. **开源生态与 GitHub 影响力**：
   - 是否在 HuggingFace、vLLM、Megatron、LlamaIndex 等官方库提交过 PR 或获得过 Merged？这是碾压普通面试者的王牌凭证。

---

## Layer 5: 红旗陷阱与成败考核指标 (Red Flags & OKR Reality)

### 5.1 核心定义
该图层用于**求职者避险**：识别团队可能存在的死局，以及入职后前 6 个月的生死考核线。

### 5.2 考核期生存法则 (First 180 Days)
- **Day 30**：跑通现有 Baseline 代码，完成首次模型评测或推理服务压测。
- **Day 90**：产出第一套可量化优化的成果（如：SFT 评测指标提升 3 个百分点，或推理 P99 延迟下降 25%）。
- **Day 180**：主导的模块完整上线投产，具备明确的业务归因收益或核心技术文档沉淀。

### 5.3 致命红旗快速诊断
- 团队总算力不足 8 张 H100/A100，却声称要“研发自主可控垂直领域多模态基座大模型”。
- 面试官无法清晰回答：“团队当前模型最大的技术瓶颈是什么？上一任为什么离职？”
- 业务完全依赖海外 API 封装，且没有明确的自研数据飞轮。

---

## 5 图层分析实战操作流程表

| 步骤 | 操作动作 | 产出物 |
|---|---|---|
| Step 1 | 通读 JD，划出公司名、团队名、技术名词与数字要求 | 实体关键词表 |
| Step 2 | 将文本归类映射入 5 个图层容器 | 5-Layer 初稿 |
| Step 3 | 对照 `hidden-signals-lexicon.md` 解码隐性词汇 | 真实诉求对照表 |
| Step 4 | 运行 `red-flags-guide.md` 进行陷阱筛查 | 风险评级与反问清单 |
| Step 5 | 结合候选人 `candidate_profile.json` 生成逐条 Match Matrix | 录取概率与 Gap 修复建议 |
