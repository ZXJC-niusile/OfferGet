# OfferGet 🎯

> **本地优先的技术求职材料审计与自适应简历排版引擎**  
> Local-First Career Toolkit & Adaptive Resume Engine

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Tests-1898%20Passed-success.svg" alt="Tests Status">
  <img src="https://img.shields.io/badge/Themes-12%20Templates-purple.svg" alt="Themes">
  <img src="https://img.shields.io/badge/Output-Auto--Desktop-blueviolet.svg" alt="Output">
  <img src="https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-orange.svg" alt="License">
</p>

---

## 💡 为什么选择 OfferGet？

在技术求职与学术保研中，通用大模型生成的材料往往充斥着**假大空的 AI 腔调**，而手动排版简历时又常遭遇**多出 3 行导致尴尬空白跨页**的问题。

**OfferGet** 是一套运行在本地的轻量级确定性工具库：
1. **真实防伪与反 AI 虚标**：基于单一事实源（SSOT）审计简历，严查虚假指标、动词夸大与 AI 八股套话。
2. **像素级单页自适应排版 (AutoFit)**：支持 Markdown/JSON 简历一键直出高颜值 PDF，自动微调间距与字体（严格保护可读性底线），**默认直接生成至桌面「个人简历」文件夹**。
3. **企业求职与学术保研双轨支持**：涵盖 JD 潜台词深度解码、人岗匹配、高校推免学术诚信审查、字数无损压缩及答辩抗压模拟。
4. **100% 本地隐私安全**：无需上传任何简历至三方云端，内置双向脱敏网关，零数据泄露风险。

---

## 🚀 极速上手 (Quick Start)

### 1. 环境准备

```bash
git clone https://github.com/ZXJC-niusile/OfferGet.git
cd OfferGet
pip install -e .

# 环境自检（检查无头浏览器与可选排版工具）
python cli.py doctor
```

### 2. 简历排版与生成（直出桌面）

无需手写复杂 JSON，**直接使用 Markdown 简历**（参考 `examples/sample_resume.md`）：

```bash
# 一键编译简历（自动输出至桌面「个人简历/」目录，生成 HTML 与 PDF）
python cli.py resume build examples/sample_resume.md

# 切换为经典黑白工程师主题（classic-tech），严格强制 1 页单页排版
python cli.py resume build examples/sample_resume.md --theme classic-tech --pages 1

# 生成学术推免专属 LaTeX 模版并编译为 PDF
python cli.py resume build examples/academic_profile.json --theme academic-latex

# 生成严格脱敏版本（自动打码手机、邮箱与真实机构名，适合公开分享）
python cli.py resume build examples/sample_resume.md --anonymize strict
```

> 📁 **查看成果**：生成完成后，直接打开电脑桌面上的 **`个人简历`** 文件夹，即可获取以候选人姓名命名的 `【姓名】_个人简历.pdf`。

### 3. JD 穿透解码与人岗匹配

```bash
# 穿透解码招聘启事（识别技术栈硬要求、32 项职场黑话潜台词与暗坑）
python cli.py jd decode examples/sample_ai_jd.txt

# 计算人岗加权匹配分与技能缺口
python cli.py jd match examples/sample_ai_jd.txt --profile examples/sample_resume.md
```

### 4. 4 维 ATS 审计与防伪质检

```bash
# 从排版规范、技能契合、量化成果与反 AI 指纹四大维度给出 100 分制评级
python cli.py ats audit examples/sample_resume.md --jd examples/sample_ai_jd.txt
```

---

## 🎨 简历排版生态 (内置 12 款精选主题)

| 主题名称 (`--theme`) | 渲染引擎 | 适用人群与风格定位 | 核心排版特色 |
| :--- | :---: | :--- | :--- |
| **`modern-navy`** *(默认)* | HTML/PDF | 现代科技独角兽、外企、前沿技术岗 | 海军蓝主题、模块化徽章、现代排版栅格 |
| **`classic-tech`** | HTML/PDF | 互联网大厂后端/算法/全栈工程师 | 经典灰黑基调、高信息密度、标准 Bullet 树 |
| **`silicon-clean`** | HTML/PDF | 硅谷外企、开源社区、国际化团队 | 极简留白、西文排版微调、GitHub 徽标集成 |
| **`asu-dense`** | HTML/PDF | 资深技术专家、全栈架构师 | 极限信息密度、双列紧凑布局、最大化空间利用 |
| **`sidebar-clean`** | HTML/PDF | 产品经理、项目经理、综合复合型人才 | 左右不对称分栏、技能/证书可视化侧边栏 |
| **`modern-corporate`** | HTML/PDF | 国央企、金融科技、传统企业技术部 | 严谨庄重商务风、正规证件照卡位、层次分明 |
| **`academic-postgraduate`**| HTML/PDF | 国内保研、考研复试、高校求职 | 中文严谨排版、突出论文发表与学术荣誉位次 |
| **`engineering-sb2nov`** | HTML/PDF | Overleaf 极客圈经典模板复刻 | 纯正 LaTeX 经典质感 HTML 完美复刻 |
| **`academic-latex`** | XeLaTeX | 计算机/数学系海外申博、顶尖夏令营 | 原生 XeLaTeX 编译，支持公式、宏包与排版规范 |
| **`academic-typst`** | Typst | 新一代高性能学术排版 | 毫秒级极速编译、现代化学术美学 |
| **`ats-plain`** | Text/HTML | 招聘网站直投（Boss直聘/猎聘/Workday） | 极简单列文本结构，确保 ATS 解析率 100% |
| **`ats-docx`** | Word DOCX| 猎头报备、企业内部 HR 审批流 | 兼容 Microsoft Word，段落样式标准化 |

---

## 📋 常用核心命令速查

```bash
# ─── 简历与档案 ─────────────────────────────────────────────────────────────
python cli.py profile parse <resume.md>                 # 将 Markdown 简历解析为标准 JSON
python cli.py resume build <profile>                    # 默认编译 modern-navy（输出至桌面）
python cli.py resume build <profile> --theme all        # 批量导出全部 12 款主题对比

# ─── 岗位分析与匹配 ─────────────────────────────────────────────────────────
python cli.py jd decode <jd.txt>                        # 解码 JD 真实技术栈与潜台词
python cli.py jd match <jd.txt> --profile <profile>     # 人岗匹配度打分与缺口雷达
python cli.py gap roi <jd.txt> --profile <profile>      # 技能差距投入产出比分析

# ─── 审计与答辩防守 ─────────────────────────────────────────────────────────
python cli.py ats audit <profile> --jd <jd.txt>         # 4 维 ATS 评分与反 AI 痕迹审计
python cli.py fact verify "<描述文本>" --profile <prof> # 核验经历陈述是否与底稿事实相符
python cli.py defense simulate <profile>                # 模拟技术面试官发起连续 3 轮白板追问

# ─── 学术保研推免 ───────────────────────────────────────────────────────────
python cli.py baoyan audit "<经历文本>"                 # 学术经历 4 大诚信红线核查（在投/仿真）
python cli.py baoyan compress <file.txt> --tier 摘要版   # 高校系统 100 字文本框自适应压缩
python cli.py baoyan advisor <advisor.json>             # 导师画像契合度计算与高情商自荐信

# ─── Offer 决策与合同审查 ───────────────────────────────────────────────────
python cli.py offer evaluate <offer.json>               # 测算真实有效时薪，排查 6 大合同陷阱
python cli.py offer counter <offer.json> --target 25k   # 生成中英双语薪酬谈判策略与邮件话术
```

---

## 🤖 作为 AI 智能体 Skill 使用

OfferGet 原生符合 Agent Skill 规范，仓库根目录自带 `SKILL.md`。您可以直接挂载到 **Antigravity / Codex / Claude** 等智能体中，通过自然语言对话驱动所有能力：

* 💬 *“帮我解析这段 JD 的暗坑与潜台词，并评估我当前的匹配度。”*
* 💬 *“检查我的项目经历，拦截所有假大空的 AI 词汇，按 STAR 原则改写并生成变更台账。”*
* 💬 *“针对我的简历生成一份经典黑白工程师主题的单页 PDF，直接放到桌面。”*

挂载方式详见 [SKILL.md](SKILL.md)。

---

## 📚 进阶资料与参考索引

<details>
<summary><b>📦 预置开箱测试用例 (点击展开 examples/ 索引)</b></summary>

| 文件路径 | 场景说明 |
| :--- | :--- |
| [`examples/sample_resume.md`](examples/sample_resume.md) | **Markdown 个人简历范本**（开箱即用，支持直接构建与修改） |
| [`examples/candidate_profile.json`](examples/candidate_profile.json) | 互联网资深研发候选人完整标准档案 |
| [`examples/candidate_product_intern.json`](examples/candidate_product_intern.json) | 互联网产品经理 / 日常实习生画像样本 |
| [`examples/academic_profile.json`](examples/academic_profile.json) | 计算机学术保研与直博推免候选人画像 |
| [`examples/sample_advisor.json`](examples/sample_advisor.json) | 重点实验室博导学术画像与招收偏好样本 |
| [`examples/sample_ai_jd.txt`](examples/sample_ai_jd.txt) | 头部大厂 AI / 分布式架构师真实招聘 JD |
| [`examples/sample_offer.json`](examples/sample_offer.json) | 包含期权、试用期与竞业协议的真实 Offer 结构 |

</details>

<details>
<summary><b>📖 方法论与求职军火库 (点击展开 references/ 词典索引)</b></summary>

| 文档名称 | 核心内容 |
| :--- | :--- |
| [`references/anti-ai-slop.md`](references/anti-ai-slop.md) | **反 AI 写作指纹规范**：拦截虚词套话，强化硬核 CAR 事实因果重构 |
| [`references/hidden-signals-lexicon.md`](references/hidden-signals-lexicon.md) | **32 项大厂潜台词词典**：解码“弹性工作制”、“扁平管理”等背后真相 |
| [`references/red-flags-guide.md`](references/red-flags-guide.md) | **技术陷阱与反问指南**：5 大招聘红旗与 15 道黄金面试反问问题 |
| [`references/sentence-patterns.md`](references/sentence-patterns.md) | **简历战术句式库**：动词五级阶梯与高转化工程成果量化句型 |
| [`references/inflation-patterns.md`](references/inflation-patterns.md) | **虚标膨胀防伪基准**：算力欺诈识别与真实锚定法则 |
| [`references/interview-questions-bank.md`](references/interview-questions-bank.md) | **大模型技术面试 Top 20 深度题库**：3D 并行、MoE 路由、PagedAttention |

</details>

---

## 🧪 自动化测试与工程质量

OfferGet 拥有全面的自动化测试套件（覆盖核心求解器、布局防漂移、隐私网关与排版引擎）：

```bash
# 运行已安装包的基础可用性检查 (Smoke Check)
python cli.py selftest

# 运行完整开发者单元测试套件（1890+ 案例）
python -m pytest tests -q
```

---

## 📄 许可证 (License)

本项目遵循 **[CC BY-NC-SA 4.0](LICENSE)** (署名-非商业性使用-相同方式共享 4.0 国际) 协议开源。
