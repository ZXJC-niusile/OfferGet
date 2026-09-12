# 反 AI 写作指纹规范 (Anti-AI-Slop Standard)

> **OfferGet 铁律**：大模型生成的职业文书、简历描述与求职分析，天然携带一种“光滑而空洞的假大空感”（业内称之为 AI Slop / AI 机器废话）。
> 一线顶级科技公司 HR 与技术总监在阅读了数千份 ChatGPT 生成的求职材料后，已对此形成极高的免疫力与厌恶感。
> 本规范制定了严格的**反 AI 指纹拦截准则与文本脱水重塑协议**。

---

## AI 废话四大经典特征指纹 (The 4 Tell-Tale AI Fingerprints)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 泛滥破折号与空洞同位语 (The Dash & Appositive Syndrome)     │
│ 2. 排比三段论与假大空结构 (The Rule-of-Three Rhythm)         │
│ 3. 虚高宏大动词与无量化修饰 (Hyperbolic Verbs Without Data)   │
│ 4. 8-Gram 句式查重与套话复用 (8-Gram Cliche Duplication)       │
└─────────────────────────────────────────────────────────────┘
```

---

### 指纹 1：泛滥破折号与空洞同位语 (The Dash & Appositive Syndrome)
- **典型机器特征**：习惯使用中文全角破折号（——）或英文 Em-dash（—）制造“史诗感”，并在前后插入极其空洞的自封头衔。
- **典型 AI Slop 范例**：
  > ❌ *“负责主导公司前沿 AI 引擎的研发 —— 作为连接尖端深度学习算法与大规模生产环境的神经中枢 —— 实现了端到端性能的巨大跃升。”*
- **人工真实技术写作规范**：
  > ✅ **立即删除所有破折号与自吹自擂的同位语修饰**。技术写作只陈述客观事实、技术选型与具体动作。
  > 改造后：*“研发基于 C++ 与 Triton 的大模型推理调度引擎，打通模型权重量化至 Kubernetes 集群自动化部署的全流程。”*

### 指纹 2：排比三段论与假大空结构 (The Rule-of-Three Rhythm)
- **典型机器特征**：喜欢强行凑齐三句并列排比：“不仅……，而且……，更彻底……”；或者“提升了 X，优化了 Y，重塑了 Z”。
- **典型 AI Slop 范例**：
  > ❌ *“通过全方位优化分布式训练架构，不仅极大降低了显存开销，显著加速了模型收敛周期，更彻底重塑了团队在前沿具身智能领域的研发效率。”*
- **人工真实技术写作规范**：
  > ✅ **拆解为具体的量化事实与因果链条（CAR 模型：Context - Action - Result）**。
  > 改造后：*“在 512 卡 H800 集群上采用 FlashAttention-3 算子与 ZeRO-3 显存切分，将千亿参数模型单步训练迭代耗时从 4.2s 缩短至 2.8s，训练总周期缩短 33%。”*

### 指纹 3：虚高宏大动词与无量化修饰 (Hyperbolic Verbs Without Data)
- **典型机器特征**：使用充满玄学色彩的抽象词汇，但缺乏哪怕一个真实的技术参数、吞吐量或对比基线。
- **禁用高危词汇库 (Banned AI Vocabulary List)**：
  - 中文禁用：`深度赋能`、`全面革新`、`强力驱动`、`革命性突破`、`显著提高`、`大幅优化`、`卓越成效`、`顶层设计`、`无缝打通`、`全方位重塑`。
  - 英文禁用：`spearheaded revolutionized`、`pioneered synergy`、`delved into the intricate tapestry of`、`testament to`、`game-changing transformation`。
- **人工真实技术写作规范**：
  > ✅ 任何一个改进动词必须强制绑定：**[基准 Baseline] + [优化手段 Method] + [最终数据 Metric]**。
  > 改造前：*“深度优化模型推理性能，取得卓越成效。”*
  > 改造后：*“针对 LLaMA-70B 采用 AWQ 4-bit 权重激活量化与 PagedAttention，单卡吞吐量由 18 tokens/s 提升至 52 tokens/s（提升 188%），且在 MMLU 基准测试中精度损失小于 0.4%。”*

### 指纹 4：8-Gram 句式查重与套话复用 (8-Gram Cliche Duplication)
- **查重定义**：任意连续 8 个字（中文）或连续 6 个词（英文），如果与通用 LLM 的高频套话完全匹配，直接判定为 AI Slop 并强制触发告警。
- **常见连续高频套话拦截特征**：
  - `作为一名深耕[X]领域的`
  - `凭借着对前沿技术的敏锐`
  - `致力于将复杂的业务需求`
  - `为业务的高速增长奠定了`
  - `不仅展现了卓越的技术实力`
  - `In today's fast-paced technological landscape`
  - `plays a pivotal role in bridging the gap`
  - `demonstrating an unwavering commitment to`

---

## 5 条脱水改造重写原则 (The 5 Dehydration Rules)

| 原则 | 规则说明 | 校验方法 |
|---|---|---|
| **Rule 1: 绝对禁止破折号** | 无论中文段落还是英文段落，正文中严禁使用 `——` 或 `—` 作为修辞连接符。 | 正则匹配 `[—\u2014\u2013]`，命中即报错。 |
| **Rule 2: 动词降温原则** | 将“引领、重构、颠覆”降级为真实的工程动词：“重构、迁移、编写、量化、压测、定位、排查”。 | 对照动词白名单审核。 |
| **Rule 3: 硬指标双重锚定** | 每一个业绩点必须同时包含**相对比例（%）**与**绝对数量（吞吐量/卡数/延迟/金额）**。 | 检查句子是否包含数字与单位（ms, tokens/s, GB, %）。 |
| **Rule 4: 机制颗粒度落地** | 严禁只写“优化了性能”，必须交代清楚牺牲了什么、依赖了什么核心算法机制（如：采用剪枝牺牲 0.2% 精度换取 2.4 倍吞吐）。 | 检查是否包含核心算法/架构专有名词。 |
| **Rule 5: 真实工程痛点回溯** | 真实优秀工程师的描述必然充满工程妥协与踩坑印记（如 NCCL 超时重试、梯度裁剪阈值调整、长上下文溢出边界控制）。 | 是否具有不可伪造的工程细节。 |

---

## 代码级自动化 Lint 校验规则库 (Anti-Slop Linter Spec)

```python
# 核心校验正则伪代码
BANNED_PATTERNS = [
    r"[—\u2014\u2013]{1,2}",                     # 禁用破折号修饰
    r"(不仅.*而且.*更.*)",                         # 禁用排比三段论
    r"(深度赋能|全面革新|强力驱动|革命性突破|显著提高|大幅优化|卓越成效|无缝打通)", # 禁用空洞副词动词
    r"(作为一名深耕.*的)",                         # 禁用空洞自封同位语
    r"(delve|testament|pivotal role|game-changer|intricate tapestry)" # 禁用英文高危词
]

def audit_text(text: str) -> list[str]:
    violations = []
    for pattern in BANNED_PATTERNS:
        if re.search(pattern, text):
            violations.append(f"Slop Violation detected: {pattern}")
    return violations
```
