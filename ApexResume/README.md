# 🚀 ApexResume（顶峰技术简历锻造系统）

> **工业级、高信号密度、跨平台自适应的技术简历锻造与防伪审计一体化工具套件。**
> 专为冲刺一线顶级 Offer 的技术人才（重点赋能 AI / 大模型 / Agent / 算法工程师）量身打造。

---

## 一、 项目背景：取其精华，去其糟粕

在深入剖析技术圈最具代表性的三大简历开源项目后，我们汲取了各自的灵魂长处，并彻底解决了其固有痛点：

| 对比维度 | GodSU（外部参考） | ASu-resume-skills（外部参考） | sushen（外部参考） | 🌟 **ApexResume（OfferGet 子系统）** |
|:---|:---|:---|:---|:---|
| **核心精华 (取)** | 11 战术手法 + 13 句式模板，逆向顶级校招的高压视觉骨架 | 司法级 A-D 证据链，确定性指标重算，14 类夸大模式库 | 双模流水线 (Forge/Audit)，像素测量初探 | **全盘吸纳三者精髓，升维为一体化工业套件** |
| **致命痛点 (去)** | 脚本硬编码 Mac 路径；缺乏代码校验；单一样式极易被识破 | ReportLab 渲染死板生硬；内部经历普遍无法核验 | 仅 1 套蓝黑主题，严重同质化；排版仍需反复手动调参 | **四大革新突破（见下文）** |

---

## 二、 四大核心突破与创新

### 1. 🎨 多主题视觉矩阵（彻底根绝“见光死与模板撞车”）
当前全网许多技术简历都在套用同一套“Georgia衬线体 + #2563EB 科技蓝 + 灰带”，已被大量大厂一线专家熟知，直接套用存在被一眼看穿为“AI包装模板”的风险。
ApexResume 首创多主题工业级模板体系：
- **`classic-tech.html`**：经典高密度蓝黑（原版逆向，视觉冲击力满分）。
- **`silicon-clean.html`（强力推荐）**：**硅谷极简墨黑风**。采用现代纯黑灰无衬线排版，质感极其冷峻严谨，**彻底消除模板痕迹**，面试官完全无法将其与网络模板关联。
- **`modern-navy.html`**：现代雅致藏蓝风。专为技术总监、首席架构师打造的高级商务科技风。
- **`ats-plain.md`**：ATS 机筛友好纯文本规范。完美兼容 Moka、北森、Lever、Greenhouse 等招聘管理系统。

### 2. ⚡ AutoFit 智能自动压页引擎（告别手动调 CSS 的痛苦）
- **传统痛点**：内容超出一页多出十几像素时，用户必须手动去改 CSS 的 line-height、padding，改一次测一次，痛苦且低效。
- **独创算法**：`core/autofit.py` 实现了自适应阶梯紧缩算法。能够自动测量真实像素高度，在不破坏版面美感的安全阈值内（行高 1.6 $\to$ 1.5，边距 9 $\to$ 7mm）**自动微调 CSS 变量，100% 自动化精准压入 A4 单页**！

### 3. 🛡️ 确定性双闸门防伪门禁（只放大，不虚构）
- **闸门 A（代码硬校验）**：`core/audit.py` 用绝对确定性的数学算法重算分子分母、百分比、相对变化量与百分点差值；使用最长前缀算法严卡角色 0-3 级边界；静态扫描黄色 `.todo` 与未绑超链接的裸露 URL。
- **闸门 B（模拟面试答辩）**：Agent 模拟苛刻面试官对成稿进行 3 层深挖追问，答不上来的虚高表述当场拦截，**保证写上去的每一句话都能在现场守住 15 分钟**。

### 4. 💻 原生全平台自适应（Windows / macOS / Linux）
- 彻底摒弃硬编码 shell 脚本，核心引擎使用标准 Python 编写。
- 在 **Windows**（自动检测 Chrome / Edge）、**macOS**、**Linux** 均可开箱即用，无需配置复杂的无头环境。

---

## 三、 目录架构与文件导航

```text
ApexResume/
├── README.md                      # 本文档
├── SKILL.md                       # AI Agent 主编排指令 (Claude / Antigravity / Cursor)
├── cli.py                         # 统一跨平台命令行总入口
│
├── core/                          # 核心确定性引擎
│   ├── render.py                  # 跨平台无头浏览器 PDF 渲染器 (支持 Chrome/Edge)
│   ├── audit.py                   # 确定性防伪校验器 (数学重算、角色门禁、夸大模式)
│   └── autofit.py                 # 独创：智能自适应阶梯压页引擎
│
├── themes/                        # 印刷级 HTML/CSS 视觉主题库
│   ├── classic-tech.html          # 主题1：经典科技蓝黑
│   ├── silicon-clean.html         # 主题2：硅谷极简黑白 (抗同质化力荐)
│   ├── modern-navy.html           # 主题3：现代雅致藏青 (架构师商务风)
│   └── ats-plain.md               # 主题4：ATS 机筛纯文本规范
│
├── references/                    # 知识库与方法论体系
│   ├── claim-ledger-schema.md     # 原子主张事实台账规范 (4维拆解、Schema与状态机)
│   ├── jd-matrix-framework.md     # 8维细粒度JD解码与要求-证据矩阵 (硬门槛物理隔离)
│   ├── hr-pitch-guide.md          # 大厂直聘黄金三段式触达、猎头Pitch与首屏1/3法则
│   ├── methods-11.md              # 11 个战术改写手法详解 (What to do)
│   ├── sentence-patterns.md       # 13 个经典高密度句式骨架 (How to write)
│   ├── ai-agent-lexicon.md        # AI / 大模型 / Agent 全链路术语与 Benchmark 字典
│   ├── evidence-rules.md          # 角色 0-3 级边界与 A-D 级证据法则
│   └── inflation-patterns.md      # 14 类夸大模式自查与尽调清单
│
├── examples/                      # 示范数据集
│   ├── resume-data.json           # 大模型算法工程师示范履历数据
│   ├── claims.json                # 原子主张核验文件范例
│   ├── sample-resume.html         # 完整 HTML 范例
│   └── sample-resume.pdf          # 编译出的高品质 A4 单页 PDF
│
└── tests/                         # 自动化单元测试
    ├── test_audit.py              # 数学、角色、动词层级与沙盒防伪 30+ 项测试
    └── test_autofit.py            # 压页引擎测试
```

---

## 四、 快速上手指南 (Quick Start)

### 1. 环境验证与一键自检
在终端运行自检命令，验证 Python、本地浏览器与全部测试用例：
```bash
python cli.py selftest
```

### 2. 核心命令手册

#### ① 渲染 HTML 为 A4 PDF（并检测溢出像素）
```bash
python cli.py render examples/sample-resume.html resume.pdf --measure
```

#### ② 自动单页压页（AutoFit 一键搞定）
```bash
python cli.py autofit resume.html resume_fit.html --pdf resume.pdf
```

#### ③ 防伪与质量审计
```bash
# 审计原子主张中的数学、动词层级与数据深度/成果证据等级
python cli.py audit --claims examples/claims.json

# 静态扫描 HTML 中的占位符、裸链接与过长粗体
python cli.py audit --html resume.html

# 底稿沙盒防伪校验：比对 HTML 成稿与原始底稿，拦截 LLM 幻觉数字
python cli.py audit --html resume.html --source draft.txt
```

---

## 五、 三大工作流模式推荐

配合 AI Agent（如 Antigravity / Claude Code / Cursor）使用时，输入指令唤醒对应模式：

- **模式 A：极速锻造 (Quick Forge)**
  - *适用*：已有较完整材料，追求极速成型。
  - *动作*：提炼高密度技术方案 $\to$ 挑选主题 $\to$ AutoFit 自动压页 $\to$ 交付单页 PDF。
- **模式 B：深度重构 (Pro Forge - 推荐)**
  - *适用*：目标头部技术大厂 40–70K 高薪档位。
  - *动作*：**S1 挖料 6 问** $\to$ **S2 头部信号重排** $\to$ **S3 Mini-RFC 叙事** $\to$ **S4 双闸门防伪答辩** $\to$ **S5 AutoFit 印刷交付**。
- **模式 C：独立审计 (Self Audit)**
  - *适用*：求职投递前深度自审、背调排雷，或技术主管面试把关。
  - *动作*：拆解原子 Claim $\to$ 运行 `audit.py` $\to$ 对照 14 类夸大模式出具体检报告。

---

## 六、 免责与实战建议

1. **去个性化建议**：在实际面试投递中，推荐优先选用 `silicon-clean.html`（硅谷极简黑白）主题，彻底规避市面常见模板的视觉特征。
2. **底线原则**：包装的本质是“把真实做过的事情以工业界方案的规格说清楚”，而非捏造事实。务必在面试前认真完成 **S4 阶段的模拟答辩**，确保对每一个工程参数和架构决策都能脱稿深入阐述！
