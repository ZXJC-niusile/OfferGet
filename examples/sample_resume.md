# 张晨曦
186-0000-8899 | alex.zhang.ai@alumni.tsinghua.edu.cn | 北京 | GitHub: https://github.com/alex-zhang-ai | 7年工作经验

## 求职意向
资深大模型算法架构师 / Tech Lead

## 个人总结
7 年前沿深度学习与大规模分布式计算研发经验，主导过多款千亿参数基座模型与混合专家模型（MoE）从零到一的预训练、强化学习对齐（GRPO/DPO）及万卡集群工程治理。精通 Megatron-LM 与 vLLM 底层源码，主导自研 FP8 高吞吐量推理服务引擎与基于 Model Context Protocol (MCP) 的企业级 Agent 集群架构，曾为核心业务带来年均 3800 万元的直接算力降本与 45% 的推理延迟改善。

## 教育背景
清华大学 · 计算机科学与技术 · 博士 | 2016.09 - 2021.06
清华大学 · 软件工程 · 本科 | 2012.09 - 2016.06

## 专业技能
- 编程语言: Python, C++17/20, CUDA, Triton, Shell, SQL
- 框架与系统: PyTorch, Megatron-LM, DeepSpeed, FlashAttention-2/3, vLLM, SGLang, Docker, Kubernetes
- 核心算法: Transformer, Mixture of Experts (MoE), RLHF (GRPO/PPO/DPO), Long-Context, RAG, Multi-Agent

## 工作经历
### 智谱前沿 AI 实验室 · 大模型预训练与对齐算法负责人 (2023.03 - 至今)
- 主导 64B Dense 及 230B MoE 基座大模型在 1024 卡集群上的预训练全流程，端到端 MFU 提升至 54.2%。
- 深入定制 Megatron-LM 底层通信算子，消除跨节点 All-to-All 通信瓶颈，训练吞吐提升 31.5%。
- 主导构建基于 GRPO 的长推理链强化学习对齐系统，在数学与代码基准测试上实现 18.4% 胜率提升。

### 阿里巴巴集团达摩院 · 资深算法专家 (2021.07 - 2023.02)
- 负责电商万亿级多模态图文检索与大模型推理优化，重构推理 Serving 引擎。
- 基于 FlashAttention 与 PagedAttention 设计动态批处理机制，P99 延迟降低 45ms，单机 QPS 提升 2.8 倍。

## 项目经历
### 基于 MCP 协议的企业级多智能体协同引擎
- **角色**：核心设计与研发负责人 | 2023.10 - 2024.05
- 设计基于 Model Context Protocol 的高并发工具调用总线，支持 50+ 异构工具动态挂载与热插拔。
- 引入 LangGraph 编排多 Agent 循环规划与反思校验，任务完成率提升 40%，年均节约 3800 万元算力成本。

## 荣誉奖项
- 国家奖学金 (2018, 2020)
- ACM-ICPC 区域赛金牌 (2015)
- 阿里巴巴集团优秀员工“技术突破奖” (2022)
