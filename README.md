# OfferGet · 本地确定性求职审查与学术材料工具箱

<p align="center">
  <b>面向技术求职与学术申请的本地规则型分析工具</b><br>
  拆解 JD · 映射候选人事实证据 · 给出可审计的简历建议 · 生成针对性面试问题与回答反馈
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Tests-run%20locally-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Architecture-Dual--Track%20(Industry%20%2B%20Academic)-indigo.svg" alt="Architecture">
  <img src="https://img.shields.io/badge/Security-Reversible%20Anonymization-blue.svg" alt="Security">
  <img src="https://img.shields.io/badge/Integrity-Fact%20Verification%20Guard-red.svg" alt="Integrity">
  <img src="https://img.shields.io/badge/License-MIT-gray.svg" alt="License">
</p>

---

## 🎯 项目核心定位与解决的痛点

在企业招聘内卷化与高校保研学术竞争白热化的今天，求职者与深造学子正面临双向信息不对称与信用挤压：
1. **企业端：JD 修辞虚构与“伪精确”吹嘘泛滥**：招聘启事充斥着公关套话与伪算力承诺，而大量候选人使用通用大模型生成充满 AI 腔调（破折号、空洞动词、编造指标）的简历，遭遇 ATS 过滤系统与资深面试官的“一票否决”。
2. **学术端：保研学术失信与导师博弈风险**：夏令营报名系统存在严苛字数限制，学生常犯“在投论文虚报、仿真模型混充真实落地、空洞大词”等红线错误；在联系导师时缺乏学术范式认知，容易遭遇口头承诺毁约（被鸽或鸽导师）等信誉危机。
3. **面试端：缺乏抗压防守能力**：写在简历上的“主导”、“从0到1”经不住技术总监或复试专家连续 3 轮白板追问。

**OfferGet** 打造了一套**“双轨制（Dual-Track）工业级技术求职与学术深造操作系统”**：
- **企业求职轨**：JD 穿透解码、6 大技术领域能力树、阿酥式（ASu）6 联全链路工程建模、严谨指标防伪算术对账、ATS 质量门禁与单页压制；
- **学术深造轨**：保研全生命周期状态机、4 大学术诚信红线审核、3 级自适应字数压缩、导师研究范式匹配与高情商外联、答辩面试红蓝对抗模拟。

---

## 🏛️ 全景系统架构 (Full-Spectrum System Architecture)

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                   OfferGet Master Operating System                                                    │
├───────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┤
│                     【企业求职与工程交付轨】                     │                             【学术深造与保研答辩轨】                            │
├──────────────────────────┬────────────────────────────┼──────────────────────────┬──────────────────────────┬─────────────────────────┤
│  JDAnalyst & Taxonomy    │ ASu Modeler & Fact Guard   │   Baoyan Auditor & Comp  │  Advisor Match & Pigeon  │ Defense Red-Team Sim    │
├──────────────────────────┼────────────────────────────┼──────────────────────────┼──────────────────────────┼─────────────────────────┤
│ • 5 图层纵向语义穿透拆解   │ • Data->Eval 6 联链路拆解  │ • 4 大学术诚信红线审查   │ • 导师近3年学术范式跃迁  │ • Claim-Evidence 矩阵   │
│ • 6 大技术领域能力树与权重│ • 0→1 vs X→Y 架构演进规约  │ • 仿真/在投/动词越权拦截 │ • 技术交集加权匹配 (0-100)│ • 3 级拷打烈度压力测试 │
│ • 32 项大厂黑话潜台词词典 │ • 确定性算术重算 (容差≤0.5%)│ • 3 级自适应字数压缩引擎 │ • 高情商外联/套磁邮件生成│ • 5 步防守策略与速查卡  │
│ • 硬门槛物理隔离与加权打分│ • 6 类夸大模式静态拦截     │ • 标点符号与版面排版规范 │ • 防鸽承诺矩阵与体面拒信 │ • 面试官追问链 (3-Round)│
│ • 岗位隐性现实与探针问题  │ • 高校官方 Title 防伪白名单│ • 21 项夏令营物料核对清单│ • 强弱 Committee 决策机制│ • 15分钟干净复现自查    │
├──────────────────────────┴────────────────────────────┴──────────────────────────┴──────────────────────────┴─────────────────────────┤
│                                             【底层支撑引擎与单页压制子系统】                                                             │
│  • ApexResume: 11 个手法、13 个句式模板、Mini-RFC 叙事、无头 Chrome 像素级 A4 单页压制                                                    │
│  • PrivacyAnonymizer: 双向可逆去隐私化脱敏网关 (支持 Standard 与 Strict 双层模式)                                                       │
│  • Automated Test Suite: 完整自动化测试矩阵 (OfferGet 根测试 + ApexResume 子系统 + 闭环自测流水线)                                      │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 💡 核心借鉴与技术资产吸收全景说明 (Absorption Catalog)

OfferGet 在演进过程中，系统性研读了本地简历生态中的 26 个开源项目，坚决摒弃了“爬虫轰炸、海外黑客工具、商业引流营销号、代码提示词副本”等违规/同质化陷阱，**将经筛选的标杆能力进行边界清晰的重构与测试**：

### 1. 企业求职与大厂岗位画像类
| 借鉴项目 | 原始项目核心价值 | OfferGet 的具体重构与吸收方式 | 落地代码模块 |
|:---|:---|:---|:---|
| **`resume-jd-optimizer-cn`** | 专为国内大厂打造的岗能分类、量化指标字典与真实性原则 | • 吸收并提炼 **6 大技术领域能力树**（AI算法、分布式后端、前端全栈、移动端、大数据湖仓、SRE云原生）与正交权重矩阵；<br>• 吸收 **8 大核心量化指标字典**（QPS、P99、MFU、显存利用率、收敛加速比等）严谨数学定义与防吹嘘公式；<br>• 提炼 20+ 条大厂公关黑话与隐性招聘潜台词穿透规则。 | `core/jd_decoder.py`<br>`core/jd_matcher.py` |
| **`ASu-resume-skills`** | 业界知名的“阿酥式”高密度架构叙事履历与证据审计 | • 提炼 **6 联全链路架构建模规范**（`Data / Model / Training / Serving / Agent / Eval`），支持 AI 与经典工程同构映射；<br>• 实现 **最小可闭环 Owner 提炼** 与“0→1 从无到有 vs X→Y 架构演进”叙事约束；<br>• 落地 **5 层失败分类学**（Recall → Planning → Evidence → Tool → Outcome）；<br>• 实现 **6 类夸大模式静态拦截**（绝对容差 $\le 0.5\%$ 机器对账、planned 时态互斥）；<br>• 建立 **教育部官方高校 Title 白名单防伪库**（985/211/双一流/高校联盟）。 | `core/asu_modeler.py`<br>`core/fact_guard.py` |
| **`ats-optimized-resume-agent-skill`** | 国内外现代 ATS 过滤规则与机器可读性标准 | • 提炼 ATS 评分模型（四维加权，满分 100 分）；<br>• 建立 **三态技能台账（Verified vs Claimed vs Gap）**；<br>• 拦截非标准单字排版与复杂的不可解析嵌套表格。 | `core/ats_checker.py` |
| **`resume-toolkit`** & **`job-description-skill`** | 简历关键信息抽取与标准化词表规范 | • 吸收了技术实体命名规范与技能同义词归一化映射字典。 | `core/jd_decoder.py` |

### 2. 学术保研、导师博弈与答辩审查类
| 借鉴项目 | 原始项目核心价值 | OfferGet 的具体重构与吸收方式 | 落地代码模块 |
|:---|:---|:---|:---|
| **`King-of-Pigeon` (鸽子王)** | 经典高情商保研文书与博弈沟通模板 | • 吸收 **高情商导师外联与套磁邮件架构**（Profile Hook、学术心得、价值主张）；<br>• 提炼 **防鸽与学术声誉保护矩阵**（口头承诺有效度评估、夏令营多 Offer 抉择策略、母校信誉保护）；<br>• 吸收 **学术礼貌拒信与报喜答谢信** 标杆范式。 | `core/advisor_matcher.py` |
| **`defense-beating-simulator`** | 项目答辩与保研复试红蓝对抗审查器 | • 吸收并实现了完整的 **Claim-Evidence 矩阵**（将架构、指标、创新点映射到材料依据，标注 `Material-supported / Material-implied / Material-missing` 状态）；<br>• 落地 **3 级拷打烈度**（先热个身、开始挑刺、严刑拷打）与 3 轮递进追问链；<br>• 提炼 **5 步防守应答策略**（正面回应+说明依据+划清边界+合理解释+给出改进）与“答辩速查卡（Cheat Sheet）”。 | `core/defense_simulator.py` |
| **`academic-skills`** | 顶会标准全流程学术套件 | • 提炼其 `professor-fit-analyser` 算法：根据导师近 3 年论文分析其**学术研究范式跃迁（Paradigm Shift）**，计算候选人与导师的研究兴趣交集分（0-100%）。 | `core/advisor_matcher.py` |
| **`baoyan-resume-writing`** & **`baoyan-skills`** | 保研学术简历规范与材料字数压缩算法 | • 落地 **4 大学术诚信红线审查**（仿真混充真实、在投冒充录用、动词越权夸大主导、空洞无凭最高级）；<br>• 实现 **3 级自适应字数压缩引擎**（摘要版 40-60 字、简历版 80-110 字、陈述版 150-220 字），严格保障报名系统字数合规；<br>• 标准化中文学术标点排版。 | `core/baoyan_auditor.py` |
| **`baoyan_workbench`** & **`CS-BAOYAN-Wiki`** | 跨院校保研流程追踪与高校考核机制 | • 吸收并构建了 **保研全流程状态机**（夏令营、预推免、九推、考研复试）；<br>• 落地 **21 项标准化保研物料核验清单**（覆盖盖章成绩单、排名证明、推荐信、代表作等）；<br>• 建模“强委员会制 (强 com)” 与 “导师一票制 (弱 com)” 的差异化应对策略。 | `core/baoyan_pipeline.py` |
| **`academic-homepage-cv-sync`** | 单源真值（Single Source of Truth）多端同步理念 | • 吸收其数据驱动架构：全局以单一标准数据模型（SSOT JSON）为真值源，下游统一派生纯文本、HTML 报告、LaTeX 源码与 PDF。 | 全局数据流架构 |

### 3. 极致排版与工程压制类
| 借鉴项目 | 原始项目核心价值 | OfferGet 的具体重构与吸收方式 | 落地代码模块 |
|:---|:---|:---|:---|
| **`GodSU / sushen` (酥神简历)** | 爆火校招简历逆向出来的高信号文案与视觉规范 | • 完整逆向并代码化实现 **11 个表达手法**（量化、对比、极值、收敛等）与 **13 个黄金句式模板**；<br>• 将其重构为具备 34 项独立单测的 **`ApexResume` 引擎**，结合无头 Chrome 打印实现一页 A4 完美压制。 | `ApexResume/` 子系统 |

---

## 🛠️ 快速上手与 CLI 命令指南

### 1. 环境准备
系统推荐 Python 3.9+。核心 `review` 流程只使用 Python 标准库；开发与测试可安装项目及 pytest：
```bash
cd OfferGet
python -m venv .venv
.venv\Scripts\activate  # Windows
python -m pip install -e . pytest
```

### 2. 执行测试
根测试与 ApexResume 子系统分开运行，实际收集数量以本机输出为准：
```bash
python -m pytest tests -q
python -m pytest ApexResume/tests -q
# 或运行包含浏览器环境检查的统一自检
python cli.py selftest
```

> **定位说明**：当前实现是本地确定性规则型求职工作流，无外部 LLM/API 依赖。匹配分与渠道区间属于材料诊断启发式，不是 ATS、面试或录用概率承诺。

### 3. 企业求职核心指令
```bash
# 1. 轻量求职审查全闭环 (岗位JD拆解 -> 真实事实简历建议 -> 3道针对性面试题)
python cli.py review examples/synthetic_intern_jd.txt --profile examples/synthetic_intern_profile.json --json

# 2. 提交一轮真实作答并获取具体诊断反馈 (指标核验、证据边界与保守精修)
python cli.py review examples/synthetic_intern_jd.txt --profile examples/synthetic_intern_profile.json --answers examples/synthetic_intern_answers.json --output review.json --json

# 2. 穿透解码企业 JD (提取 5 图层、6 大能力树与隐性黑话)
python cli.py jd decode examples/sample_ai_jd.txt

# 3. 严格匹配候选人画像 (输出加权匹配分与面试概率)
python cli.py jd match examples/sample_ai_jd.txt --profile examples/candidate_profile.json

# 4. 生成双语 HTML 战略对战报告
python cli.py jd report examples/sample_ai_jd.txt --profile examples/candidate_profile.json --output strategy_report.html

# 5. 执行 ATS 质量门禁与三态技能台账审计
python cli.py ats audit examples/candidate_profile.json --jd examples/sample_ai_jd.txt

# 6. 事实防伪校验 (严格核查指标虚报与算术不一致)
python cli.py fact verify examples/candidate_profile.json
```

### 4. 学术保研核心指令
```bash
# 1. 保研经历学术诚信审查与 4 大红线拦截
python cli.py baoyan audit examples/sample_baoyan_entry.txt

# 2. 三级自适应字数压缩 (针对高校系统字数限制)
python cli.py baoyan compress examples/sample_baoyan_entry.txt --tier 简历版

# 3. 导师近 3 年范式匹配与高情商套磁信生成
python cli.py baoyan advisor examples/sample_advisor.json --profile examples/academic_profile.json --scenario summer_camp

# 4. 夏令营 21 项物料清单动态核查
python cli.py baoyan checklist examples/academic_profile.json --stage 夏令营 --track 直博

# 5. 项目答辩红蓝对抗模拟 (生成 Claim-Evidence 矩阵与追问速查卡)
python cli.py baoyan defense examples/candidate_profile.json --intensity 严刑拷打
```

### 5. 投递、人工确认与版本追踪

OfferGet 将“分析建议”和“修改事实档案”分开：`review` 只生成可审计的
`MaterialProposal` 草稿，只有显式执行 `proposal accept` 才会写出新 Profile。
所有投递、提案、结果反馈和简历产物元数据都保存在本地 SQLite 中。

```bash
# 创建投递记录
python cli.py application add APP-001 --company "示例科技" --role "后端工程师" --db applications.db

# 生成并持久化待确认 Proposal
python cli.py review examples/sample_ai_jd.txt \
  --profile examples/candidate_profile.json \
  --proposal-db applications.db --application-id APP-001 \
  --output review.json --json

# 查看并人工确认
python cli.py proposal list --application-id APP-001 --db applications.db --json
python cli.py proposal accept PROPOSAL_ID \
  --profile examples/candidate_profile.json \
  --jd examples/sample_ai_jd.txt \
  --output tailored_profile.json --build-resume \
  --db applications.db --json

# 查看投递、简历版本和结果反馈
python cli.py application show APP-001 --db applications.db --json
python cli.py application versions APP-001 --db applications.db --json
python cli.py application outcome APP-001 --stage interview --result rejected \
  --feedback "系统设计深度不足" --reflection "容量估算不充分" \
  --next-action "练习缓存与分片设计" --tags system_design,technical_depth \
  --db applications.db
python cli.py application insights --db applications.db --json
```

### 6. RenderCV JSON 互通

RenderCV 负责自己的 YAML 解析和渲染；OfferGet 只提供无额外依赖的 JSON 数据互通。
未知 section 会保存在 `rendercv_import_metadata` 并通过 warnings 报告，不会静默丢弃。

```bash
python cli.py rendercv import rendercv.json --output profile.json --json
python cli.py rendercv export profile.json --output rendercv.json --json
```

### 7. 当前核心边界

- `ProfileContext` 是事实单一来源；渲染器、JD 分析和证据图都是派生视图。
- `EvidenceGraph` 与 `FactVerificationGuard` 负责事实边界；Proposal 是人工确认边界。
- `ApplicationStore` 负责投递生命周期、结果反馈和简历版本元数据。
- ResumeVersion 当前保存 Profile/JD hash 和输出产物路径，不保存完整 Profile 快照；因此 `version-diff` 只报告元数据差异，不声称内容级差异。
- ResumeVersion 同时保存产物存在状态与 SHA-256；`proposal accept` 只有在 Profile/HTML/PDF 产物均可读时才登记为 completed。
- 外部简历项目只作为规则和架构参考，OfferGet 不直接依赖其运行时、数据库或 Web 基础设施。

---

## 🧪 质量工程与测试矩阵

OfferGet 拥有覆盖率极高的自动化测试工程，保证每一个规则与算法均有确定性保障：
- **`tests/test_asu_and_taxonomy.py`**：测试 6 联链路拆解、Owner 命名规范、容差 $\le 0.5\%$ 算术核验、6 类夸大审计与大厂岗位分类；
- **`tests/test_baoyan_auditor.py`**：41 个测试覆盖学术诚信红线、标点符号审查与三级压缩；
- **`tests/test_advisor_matcher.py`**：11 个测试覆盖导师画像抽取、范式交集加权、防鸽承诺矩阵与礼貌拒信；
- **`tests/test_baoyan_pipeline.py`**：9 个测试覆盖保研全生命周期状态机与 21 项物料清单校验；
- **`tests/test_fact_guard.py`**：测试指标防漂移、未锚定数字拦截与真实性台账；
- **`ApexResume/tests/`**：覆盖无头浏览器单页压制、DOM 测量与 CSS 视觉规范；
- **测试基线**：不在文档中硬编码数量；以 `python -m pytest tests -q` 与 `python -m pytest ApexResume/tests -q` 的当前输出为准。

---

## 📄 许可证与免责声明
本项目基于 **MIT License** 开源。
- **免责声明**：OfferGet 致力于提升求职者与学子的真实表达深度与信息对称度。系统严格杜绝并技术性拦截一切伪造学历、虚构项目经历、篡改实验数据及学术不端行为。求职者须对其提交材料的真实性承担法律与道德责任。
