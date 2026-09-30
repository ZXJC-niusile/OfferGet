# OfferGet · 本地确定性求职审查与学术材料工程操作系统

<p align="center">
  <b>面向工业级技术求职与学术升学的本地规则型分析与材料工程平台</b><br>
  穿透解码 JD · 锚定单一事实真值源 · 拦截 AI 虚辞与伪精确吹嘘 · 模拟高压答辩攻防 · 驱动数据化投递与 Offer 决策
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Tests-580%2B%20passed%20locally-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Architecture-Dual--Track%20(Industry%20%2B%20Academic)-indigo.svg" alt="Architecture">
  <img src="https://img.shields.io/badge/Security-Reversible%20Anonymization-blue.svg" alt="Security">
  <img src="https://img.shields.io/badge/Integrity-Fact%20Verification%20Guard-red.svg" alt="Integrity">
  <img src="https://img.shields.io/badge/License-MIT-gray.svg" alt="License">
</p>

---

## 🎯 项目核心定位与解决的痛点

在企业招聘内卷化与高校保研学术竞争白热化的今天，求职者与深造学子正面临双向信息不对称与信用挤压：

1. **企业端：JD 修辞虚构与“伪精确”吹嘘泛滥**：招聘启事充斥着公关套话与伪算力承诺，而大量候选人使用通用大模型生成充满 AI 腔调（破折号、空洞动词、编造指标）的简历，遭遇 ATS 过滤系统与资深技术考官的“一票否决”。
2. **面试端：缺乏真实抗压与证据防守能力**：写在简历上的“主导架构”、“从 0 到 1”经不住技术总监或复试专家连续 3 轮白板追问与边界探针。
3. **学术端：保研学术失信与导师博弈风险**：夏令营报名系统存在严苛字数限制，学生常犯“在投论文虚报、仿真模型混充真实落地、空洞大词”等红线错误；在联系导师时缺乏学术范式认知，容易遭遇口头承诺毁约（被鸽或鸽导师）等信誉危机。
4. **决策端：薪酬陷阱隐蔽与有效时薪失真**：大厂高薪往往包裹着严苛的“绩效对半拆分、期权悬崖、单边竞业、无效加班”，缺乏科学的多 Offer 真实时薪折算模型。

**OfferGet** 打造了一套**“双轨制（Dual-Track）工业级技术求职与学术深造操作系统”**：
- **企业求职轨（Industry Track）**：5 图层 JD 语义穿透、6 联全链路工程叙事建模、指标数学一致性对账（容差 $\le 0.5\%$）、ATS 机器可读性质量门禁与三态技能台账、真实时薪折算与 6 大合同陷阱雷达；
- **学术深造轨（Academic Track）**：保研全生命周期状态机、4 大学术诚信红线审查、3 级自适应字数压缩、导师近 3 年学术范式跃迁匹配与高情商外联、21 项推免物料合规清单；
- **实战攻防与复盘轨（Defense & Debrief Track）**：Claim-Evidence 事实证据链矩阵、3 级拷打烈度压力测试、5 步防守策略与速查卡、面试实录长文本切分诊断与下一轮备战清单；
- **投递与版本追踪轨（Tracker & Lifecycle Track）**：6 阶段投递看板状态机、不可变证据快照与指纹、Proposal 人工确认机制、产物 SHA-256 审计与版本差异追踪。

---

## 🏛️ 全景系统架构 (Full-Spectrum System Architecture)

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                   OfferGet Master Operating System                                                     │
├────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┤
│                     【企业求职与工程交付轨】                      │                             【学术深造与保研答辩轨】                             │
├──────────────────────────┬─────────────────────────────┼──────────────────────────┬──────────────────────────┬─────────────────────────┤
│   JD Analyst & Decoder   │  Engineering Chain Modeler  │   Baoyan Auditor & Comp  │  Advisor Match & Comm    │  Defense Red-Team Sim   │
├──────────────────────────┼─────────────────────────────┼──────────────────────────┼──────────────────────────┼─────────────────────────┤
│ • 5 图层纵向语义穿透拆解    │ • Data->Eval 6 联工程链路建模 │ • 4 大学术诚信红线审查    │ • 导师近3年学术范式跃迁   │ • Claim-Evidence 证据矩阵│
│ • 6 大标准领域核心能力树   │ • 0→1 vs X→Y 架构演进规约   │ • 仿真/在投/动词越权拦截  │ • 技术交集加权匹配 (0-100)│ • 3 级拷打烈度压力测试  │
│ • 32 项企业黑话潜台词词典  │ • 确定性算术重算 (容差≤0.5%) │ • 3 级自适应字数压缩引擎  │ • 高情商外联/套磁邮件生成 │ • 5 步防守策略与速查卡   │
│ • 硬门槛物理隔离与加权打分 │ • 6 类夸大模式静态拦截      │ • 标点符号与学术排版规范  │ • 防鸽承诺矩阵与体面拒信  │ • 递进式追问链 (3-Round)│
│ • 岗位隐性现实与探针问题   │ • 高校官方 Title 防伪白名单  │ • 21 项夏令营物料核对清单 │ • 强弱 Committee 决策机制 │ • 面试长文本实录全复盘   │
├──────────────────────────┴─────────────────────────────┴──────────────────────────┴──────────────────────────┴─────────────────────────┤
│                                                【投递决策、版本追踪与底层支撑基石】                                                      │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ • Application Tracker & Store: 6 阶段投递看板 (pending->offer->closed)、转化分析、标签洞察与 SQLite 持久化                               │
│ • Offer Matrix: 多 Offer 真实时薪折算模型 (通勤扣减、年终折损、双边公积金)、6 大劳动合同陷阱雷达与博弈策略                                  │
│ • ApexResume Engine: 11 种表达手法、13 种黄金句式模板、Mini-RFC 架构叙事、无头 Chrome 像素级 A4 单页压制                                 │
│ • Privacy Anonymizer: 双向可逆去隐私化脱敏网关 (支持 Standard 与 Strict 双层保护模式)                                                    │
│ • Fact Verification Guard & Evidence Graph: 单源真值 (SSOT) 事实证据图谱、不可变指纹快照与严格防篡改门禁                                 │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 核心能力与关键模块详解

### 1. 5 图层 JD 穿透解码与标准岗位族图谱 (`modules/jd_analyst/` & `core/jd_decoder.py`)
- **5 图层纵向语义穿透**：将一段非结构化岗位描述自顶向下拆解为：
  1. `Base Profile`：岗位基础属性、层级、Base 地点；
  2. `Hard Thresholds`：学历、专业、年限、强制技术项等物理红线；
  3. `Core Skills`：区分为必须具备（`must_have`）与加分项（`nice_to_have`）；
  4. `Implicit Signals`：从“高并发/重构/海量数据/抗压”等潜台词中反推业务真实痛点；
  5. `Domain Capabilities`：归属到标准六大核心技术族群（AI 算法工程、分布式后端高并发、前端与跨端、移动端、大数据湖仓、SRE 云原生平台），并动态扩展数据分析、AI 产品经理、测试保障、UI/UX、用户增长等领域。
- **邻近技能容差匹配（Adjacent Skills）**：支持主流技术栈等价置换（如 Kafka $\leftrightarrow$ RocketMQ，React $\leftrightarrow$ Vue，Flink $\leftrightarrow$ Spark Streaming 等），杜绝单字死板过滤。

### 2. 6 联全链路工程叙事建模与算术一致性核验 (`core/asu_modeler.py`)
- **6 联全链路拆解**：针对工程与算法项目，严格按 `Data (数据工程) -> Model (模型设计) -> Training (训练加速) -> Serving (推理与高并发部署) -> Agent (编排落地) -> Eval (严密评测与失败归因)` 六个环节进行经历模块化归位。
- **架构演进与最小 Owner 规约**：强制规约“0 $\to$ 1 从无到有原型搭建”与“X $\to$ Y 既有系统重构演进”的措辞规范，严禁普通贡献者直接标榜“全网架构负责人”。
- **确定性算术防伪对账**：
  - 机器重新计算分子分母比值与百分比，容差严格限制在 $\le 0.5\%$；
  - 校验优化前后基线变化（相对百分比 vs 绝对百分点），拦截指标自相矛盾；
  - 拦截缺乏横向基准对比的“业内最高/全球领先”等未锚定绝对最高级。
- **教育部高校官方 Title 白名单**：对“985/211/双一流/省属重点”等资质进行官方白名单校验，拦截非法包装。

### 3. ATS 四维可读性质量门禁与三态技能台账 (`core/ats_checker.py`)
- **四维打分模型**：满分 100 分，按“关键词密度与契合度、排版结构与格式规范、经历叙事量化深度、个人信息完整性”进行打分，给出 `READY_TO_SEND / CONDITIONAL_PASS / REVISE_REQUIRED` 明确裁决。
- **三态技能台账（Three-State Skill Ledger）**：
  - `Verified Skills`：在底层项目与经历中具备确凿实测数据与产物支撑的技能；
  - `Claimed Skills`：仅在个人技能清单中提及、在实际项目无佐证的主张；
  - `Gap Skills`：岗位核心要求中尚未满足的技术缺口。

### 4. 答辩红蓝对抗模拟与面试实录复盘 (`core/defense/` & `core/interview_debrief.py`)
- **Claim-Evidence 矩阵构建**：对项目陈述提取断言，划分为 `Material-supported（有据支撑）`、`Material-implied（合理推断）`、`Material-missing（缺乏依据）`。
- **3 级拷打烈度压力测试**：
  - `先热个身`：事实摸底，询问基础配置与基线口径；
  - `开始挑刺`：依赖剥离，追问架构设计权衡与竞品选型理由；
  - `严刑拷打`：极限复现，针对高并发极限、故障恢复与工程局限性展开步步紧逼。
- **5 步防守型应答框架**：`[正面回应] -> [实际实现] -> [边界与局限] -> [原因说明] -> [改进规划]`，彻底杜绝虚假自夸。
- **面试实录长文本切分与 (N+1) 面清单**：输入面试录音转录或文本记录，自动识别问答轮次，进行盲区诊断，输出薄弱项安全应答应急预案。

### 5. 保研推免学术审查与导师外联决策 (`core/baoyan_*.py` & `core/advisor_matcher.py`)
- **4 大学术诚信红线**：
  1. 仿真模拟混充真实物理系统落地；
  2. 论文在投阶段虚报为录用/发表；
  3. 动词越权（将实验参与者虚报为主持人/通讯作者）；
  4. 空洞无凭最高级与学术修饰过当。
- **3 级自适应字数压缩引擎**：在不破坏主谓宾与事实数据的前提下，自动压缩为“摘要版（40-60字）”、“简历版（80-110字）”、“申请表陈述版（150-220字）”，完美适配各高校系统字数限制。
- **导师研究范式跃迁匹配与防鸽承诺**：基于导师近 3 年学术成果分析其技术演进方向，计算契合度，生成高情商学术自荐信与学术礼貌拒信。

### 6. 投递追踪看板、Proposal 人工确认与版本元数据 (`core/application_tracker.py`)
- **6 阶段投递看板状态机**：`pending -> applied -> written_test -> interview -> offer -> closed`，具备单向递进与合规跳流校验。
- **Proposal 人工确认机制**：所有针对候选人档案的修订建议先以 `MaterialProposal` 草稿形态暂存，只有经过候选人显式执行 `proposal accept` 才会落地入库。
- **版本元数据与产物防篡改**：记录每次投递的 Profile Hash、JD Hash、渲染主题，并在本地严格校验产物文件 SHA-256 签名，生成确定性版本差异。

### 7. 多 Offer 真实时薪折算与 6 大合同陷阱雷达 (`core/offer_*.py`)
- **真实时薪折算模型**：
  $$\text{真实时薪} = \frac{\text{现金底薪} + \text{保障年终} \times \text{折损率} + \text{双边公积金} - \text{通勤租房差额}}{(52 \text{周} - \text{年假}) \times (\text{每周工时} + \text{每日通勤} \times \text{工作天数})}$$
  剔除“996 伪高薪”幻象，还原单位精力产出。
- **6 大劳动合同陷阱雷达**：
  1. `TRAP_01_PROBATION`：试用期超长（如 6 个月）或打折超标、不缴社保；
  2. `TRAP_02_NON_COMPETE`：全员笼统竞业、将法定竞业补偿揉入月薪发放；
  3. `TRAP_03_SALARY_SPLIT`：薪酬大比例拆分（固定薪资 50% + 浮动绩效 50%）；
  4. `TRAP_04_EQUITY_CLIFF`：期权 4 年长周期、回购定价不透明；
  5. `TRAP_05_OVERTIME`：不定时工作制规避法定加班费；
  6. `TRAP_06_SALARY_DISCREPANCY`：HR 宣称大包与合同实际签署金额严重背离。
- **薪酬博弈与证据门禁**：生成带有竞品 Offer 门限与真实量化支撑的高情商薪酬争取邮件与口头谈判脚本。

### 8. ApexResume 像素级单页压制引擎 (`ApexResume/`)
- 包含 11 个表达手法与 13 个黄金句式模板；
- 采用 Mini-RFC 架构表达技术经历；
- 集成无头 Chrome 驱动，像素级控制边距、行高、字符间距与分页截断，确保 A4 单页完美压制。

---

## 🛠️ 快速上手与 CLI 指南

### 1. 环境准备与全量自检
OfferGet 采用纯 Python 工业化架构，核心分析不依赖任何外部付费 API。
```bash
# 1. 克隆并进入项目
cd OfferGet

# 2. 创建并激活虚拟环境 (推荐 Python 3.9+)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux / macOS

# 3. 本地可编辑安装与依赖同步
python -m pip install -e . pytest

# 4. 执行全系统环境自检 (包含浏览器渲染与测试套件验证)
python cli.py selftest
```

---

### 2. 企业求职全流程命令

#### Step 1: 轻量审查全闭环 (JD拆解 -> 事实建议 -> 针对性面试题)
```bash
python cli.py review examples/synthetic_intern_jd.txt \
  --profile examples/synthetic_intern_profile.json \
  --json
```

#### Step 2: 深入穿透解码企业 JD
```bash
python cli.py jd decode examples/sample_ai_jd.txt
```

#### Step 3: 严格匹配候选人画像 (输出加权匹配分与雷达)
```bash
python cli.py jd match examples/sample_ai_jd.txt \
  --profile examples/candidate_profile.json
```

#### Step 4: 执行 ATS 机器可读性四维质检
```bash
python cli.py ats audit examples/candidate_profile.json \
  --jd examples/sample_ai_jd.txt
```

#### Step 5: 事实防伪校验 (严格拦截夸大虚报)
```bash
python cli.py fact verify examples/candidate_profile.json
```

#### Step 6: 生成中英双语战略战报 HTML
```bash
python cli.py jd report examples/sample_ai_jd.txt \
  --profile examples/candidate_profile.json \
  --output strategy_report.html
```

---

### 3. 项目答辩与红蓝对抗模拟

```bash
# 针对候选人项目经历执行高压答辩拷打模拟 (支持: 先热个身 / 开始挑刺 / 严刑拷打)
python cli.py defense simulate \
  --project "主导 64B Dense 及 230B MoE 基座大模型在 1024 卡集群上的预训练全流程，端到端 MFU 提升至 54.2%" \
  --intensity "严刑拷打" \
  --profile examples/candidate_profile.json \
  --output defense_report.md
```

---

### 4. 学术保研与推免审查命令

```bash
# 1. 保研经历学术诚信审查与 4 大红线拦截
python cli.py baoyan audit examples/sample_baoyan_entry.txt

# 2. 三级自适应字数压缩 (针对高校申报系统)
python cli.py baoyan compress examples/sample_baoyan_entry.txt --tier 简历版

# 3. 导师近 3 年学术范式匹配与高情商外联邮件生成
python cli.py baoyan advisor examples/sample_advisor.json \
  --profile examples/academic_profile.json \
  --scenario summer_camp

# 4. 夏令营 21 项物料合规动态核查
python cli.py baoyan checklist examples/academic_profile.json \
  --stage 夏令营 --track 直博
```

---

### 5. 投递追踪看板与版本管理

```bash
# 1. 创建投递记录
python cli.py application add APP-2026-001 --company "星河科技" --role "后端架构师" --db applications.db

# 2. 结合 Review 流程生成待确认 Proposal
python cli.py review examples/sample_ai_jd.txt \
  --profile examples/candidate_profile.json \
  --proposal-db applications.db --application-id APP-2026-001 \
  --output review.json --json

# 3. 人工审查并显式接受 Proposal (生成新 Profile 并触发简历构建)
python cli.py proposal accept PROPOSAL_ID \
  --profile examples/candidate_profile.json \
  --jd examples/sample_ai_jd.txt \
  --output tailored_profile.json --build-resume \
  --db applications.db --json

# 4. 更新投递状态为面试中
python cli.py application status APP-2026-001 interview --db applications.db

# 5. 录入面试结果反馈、复盘反思与标签
python cli.py application outcome APP-2026-001 \
  --stage interview --result rejected \
  --feedback "系统设计容量预估不充分" \
  --reflection "需加强极端流量缓存穿透场景的理论准备" \
  --tags system_design,technical_depth \
  --db applications.db

# 6. 查看求职转化洞察分析
python cli.py application insights --db applications.db --json
```

---

### 6. 多 Offer 真实时薪折算与薪酬博弈

```bash
# 1. 评估单个 Offer 薪酬包并扫描 6 大合同陷阱
python cli.py offer evaluate examples/sample_offer.json --profile examples/candidate_profile.json

# 2. 生成高情商 Counter-Offer 谈判信与口头博弈话术
python cli.py offer counter examples/sample_offer.json \
  --target-base 85000 \
  --profile examples/candidate_profile.json
```

---

## 🧪 质量工程与测试矩阵

OfferGet 采用模块化测试工程，全量单测覆盖各个核心模块，在本地保持 100% 绿灯：

```bash
# 运行 OfferGet 全量单元测试套件
python -m pytest tests -q

# 运行 ApexResume 独立渲染单测
python -m pytest ApexResume/tests -q

# 运行全链路系统级端到端自测
python cli.py selftest
```

### 核心测试套件分布
| 测试套件 | 验证的核心业务逻辑 |
|:---|:---|
| **`tests/test_taxonomy_classification.py`** | 6 联工程链路拆解、Owner 表述规范、容差 $\le 0.5\%$ 指标对账、经历膨胀审计与六大岗位族分类 |
| **`tests/test_evidence_engine.py`** | 证据链不可变模型、比率与变化值校验、开源贡献深度等级划分（Level 0-4）、HTML 审计战报渲染 |
| **`tests/test_defense_simulator.py`** | Claim-Evidence 证据矩阵生成、3 级拷打烈度递进追问链、100 分制防守评估与 5 步防守速查卡 |
| **`tests/test_application_tracker.py`** | 证据图单调状态机、不可变指纹快照、SQLite 数据库模式迁移（v1-v7）、投递结果反馈与简历版本元数据审计 |
| **`tests/test_offer_matrix.py`** | 多 Offer 真实时薪折算模型（年终折损率、通勤扣减、公积金比例）、6 大合同陷阱雷达与证据门禁博弈脚本 |
| **`tests/test_baoyan_*.py`** | 保研学术诚信 4 大红线、3 级自适应字数压缩、夏令营 21 项物料合规清单与全生命周期状态机 |
| **`tests/test_advisor_matcher.py`** | 导师研究范式跃迁提取、候选人技术交集加权计算、防鸽承诺矩阵与高情商自荐信 |
| **`tests/test_ats_checker.py`** | ATS 机器可读性四维打分、三态技能台账（Verified/Claimed/Gap）、排版合规门禁 |
| **`tests/test_fact_guard.py`** | 事实防伪守护、经历级别作用域锚定、未佐证指标拦截与零漂移保真 |
| **`ApexResume/tests/`** | 11 种表达手法、13 种黄金句式、DOM 高度与视口测量、无头 Chrome A4 像素级单页压制 |

---

## 🔒 核心设计哲学与边界准则

1. **事实单一真值源（SSOT）**：`CandidateProfile` 是唯一真实底稿。所有改写建议、匹配计算、雷达报告及证据图谱均是纯只读或派生视图，绝不未经人工确认擅自篡改候选人真实履历。
2. **人工确认护栏（Human-in-the-Loop）**：任何求职建议仅以 `MaterialProposal` 存在，必须经由候选人手动 `proposal accept` 后才被持久化。
3. **本地计算与隐私优先**：全流程提供双向可逆脱敏（`PrivacyAnonymizer`），所有算术校验、词典匹配、规则审计均在本地完成，杜绝敏感经历泄漏。
4. **恪守学术道德与合规底线**：系统技术性拦截一切伪造学历、编造虚假实验、篡改在投论文状态等不端行为；所有 Offer 劳动法律提示均保持客观中立并附带合规免责声明。

---

## 📄 许可证与免责声明

本项目基于 **[MIT License](LICENSE)** 开源。

> **免责声明**：OfferGet 致力于提升求职者与升学学子的真实表达质量与职场信息对称度。系统提供的匹配得分、时薪测算、合同陷阱提示及防守策略仅作为个人材料准备与决策辅助工具，不构成任何形式的法律建议、保研录取承诺或招聘保证。用户对其提交的一切申请材料真实性与法律后果负全责。
