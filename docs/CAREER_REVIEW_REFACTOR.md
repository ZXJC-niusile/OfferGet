# OfferGet 轻量求职审查 Agent / Skill 重构与深磨技术报告 (Career Review Refactor Report)

## 一、项目定位与重构目标

将 OfferGet 收敛为纯本地、零外部数据库、零外部 LLM API 依赖的**轻量求职 Agent / Skill**，聚焦高置信度全闭环：
$$\text{岗位 JD 拆解} \longrightarrow \text{基于真实事实的简历建议} \longrightarrow \text{针对性面试问题 (≥3 题)} \longrightarrow \text{用户真实作答} \longrightarrow \text{基于证据边界的具体反馈}$$

**本轮主打深磨焦点**：
**基于真实经历与证据边界的面试训练（Interview Training Grounded in Truthful Experience and Evidence Boundaries）**。

---

## 二、P0 核心问题修复与重构前后对比

### [P0.A] 面试复盘真值性与证据边界重构 (`core/interview_debrief.py`)

* **原有缺陷**：
  1. 当候选人坦诚回答“没做过/不了解”时，系统粗暴判定为致命缺陷 `FATAL_GAP`，并在 `refined_answer` 中注入虚构模板话术：“*但我深入实践过与之底层相通的架构...*”，诱导候选人在面试中虚构相邻经验；
  2. 辅导建议（`coaching_advice`）与精修答案（`revised_answer`）字段语义混淆；
  3. 当候选人回答完全偏离主题（例如“今天天气不错我吃了一碗面”）时，系统误判为 `WELL_DEFENDED`。
* **重构方案**：
  1. 新增 `QuestionDiagnosis.EXPERIENCE_BOUNDARY`（客观界定经验边界）与 `QuestionDiagnosis.UNCERTAIN`（偏离主题/无法诊断）；
  2. 彻底拆分 `coaching_advice`（面试官视角战术辅导）与 `revised_answer`（基于候选人原话与底稿事实的保守精修表达）；
  3. 彻底删除“底层相通架构”虚构说辞。当坦诚“没做过”时，生成保守回答：“坦诚说明未在实际项目中主导过该技术，避免强行推测细节；可说明所掌握的相通底层原理（如有），并阐述面对未知技术时的调研路径与攻坚方法”；
  4. 候选人回答偏离核心考查点时诊断为 `UNCERTAIN`，拒绝盲目发绿牌。

### [P0.B] 结构化 `ResumePatch` 与防篡改改写门禁 (`core/job_flow.py`)

* **原有缺陷**：
  1. `generate_tailored_profile_from_review` 在找不到经历锚点时，使用 `target_exp_indices.append(0)` 盲目将技能建议（如 `PyTorch`、`Framework Internals...`）塞入候选人第一段工作经历；
  2. 缺乏防篡改门禁：如果上游 advice 产生指标虚标（如 20% -> 35%），会直接被写进 `tailored_profile`；
  3. 重复执行会导致 bullet 冗余追加（非幂等）。
* **重构方案**：
  1. 定义严格的 `ResumePatch` 数据模型（含 `source_claim_id`, `target_path`, `before`, `after`, `evidence_refs`, `validation_status`, `reason`, `unresolved_risks`）；
  2. 废除 `experience[0]` 兜底盲插：凡无法定位到明确经历或项目锚点的条目，记录为 `validation_status="rejected"` 并附带审计原因；
  3. 增量核验门禁：在将改写文本注入经历前，调用 `FactVerificationGuard.verify_facts` 校验改写内容，指标虚增直接判定 `rejected`，阻止污染；
  4. 幂等性保障：若经历中已存在目标条目，标记为 `validation_status="already_applied"`，不重复追加。

### [P0.C] 事实守卫数值绑定与防跨项目借用 (`core/fact_guard.py`)

* **原有缺陷**：
  在 `core/fact_guard.py` 的 `_verify_single_bullet` 中，存在全域白名单旁路：
  `if val in self.all_verified_numbers: continue`
  导致候选人档案只要在 A 项目中包含过某个数字（如 48% 显存优化），在 B 项目中虚构“带领 48 位工程师团队”也能直接绕过核验放行。
* **重构方案**：
  1. 彻底删除 `if val in self.all_verified_numbers: continue` 全局白名单旁路；
  2. 所有数值必须在本地滑动窗口（Local Context Window）和技术主题（Topic/Keywords Affinity）下成功锚定到 SSOT Profile 的特定经历或项目锚点；
  3. 修正 `_check_metric_drift` 中 `model_params` 的跨项校验，确保只能比对模型参数锚点；
  4. 完善 `core/registry.py` 中 `METRIC_TYPE_TO_TOPICS`，支持通用百分比及各类型自反匹配。

---

## 三、测试验证记录与三阶段对比

### 1. 三阶段测试结果对比矩阵

| 测试阶段 | 运行命令 | 预期目标 | 实际结果 | 状态 |
|---|---|---|---|---|
| **阶段 1：基线测试** | `pytest tests -q`<br>`pytest ApexResume/tests -q`<br>`python cli.py selftest` | 确认修改前基线健康度 | 333 passed in 92.80s<br>34 passed in 1.68s<br>11/11 stages passed | PASS |
| **阶段 2：入口与路径修复** | `jd_cmd.py`, `resume_cmd.py`, `selftest_cmd.py` 相对路径修复 | 根路径锚定，解除工作目录依赖 | 命令行全局任意目录均可无异常调度 | PASS |
| **阶段 3：P0 实施后全量回归** | `python -m unittest tests/test_career_review.py`<br>`python -m unittest tests/test_fact_guard.py`<br>`pytest tests -q`<br>`pytest ApexResume/tests -q`<br>`python cli.py selftest` | 验证 P0 门禁严密性与零破坏性回退 | **20/20 passed** (36.17s)<br>**10/10 passed** (0.09s)<br>**334 passed** (100%)<br>**34 passed** (100%)<br>**11/11 stages passed** | **ALL PASS** |

### 2. 核心单元测试修复细节 (`tests/test_career_review.py`)
- `test_04_answer_feedback_with_fatal_gap`: 验证诚实作答“没做过”被诊断为 `experience_boundary`，且精修答案绝不编造“底层相通架构”；
- `test_11_evidence_matrix_and_claim_risk_gate`: 验证未核验指标保留弱证据（`coverage="weak"`），未提供证明前动作锁定为 `ask_user`；
- `test_17_career_review_build_resume_e2e`: 验证端到端改写经历严格引用已核验的真实中文经历，不将技能标签作为经历 bullet 注入；
- `test_18_generate_tailored_profile_from_review_unit`:
  * 指标虚标（20% -> 35%）被事实门禁拦截，记录 `validation_status="rejected"`；
  * 指标保真（保持 20%）成功改写，记录 `validation_status="applied"`；
  * 重复应用同一补丁保证幂等性，记录 `validation_status="already_applied"`；
- `test_20_synthetic_sqlite_case_interview_and_resume`: 合成真实案例全链路断言。

---

## 四、合成真实案例运行输出验证

### 案例输入
* **目标 JD** (`examples/synthetic_intern_jd.txt`)：
  职位：Python 后端实习生
  职责：HTTP 查询接口开发与维护、编写高效 SQL 查询配合 SQLite/MySQL、了解 Redis 缓存机制。
* **候选人底稿** (`examples/synthetic_intern_profile.json`)：
  高校课程管理系统（Python, SQLite, SQL 查询接口），**无 Redis，无压测数据**。
* **候选人回答** (`examples/synthetic_intern_answers.json`)：
  “我负责查询接口，访问速度提升了 50%。”

### 实际运行命令
```bash
python cli.py review examples/synthetic_intern_jd.txt --profile examples/synthetic_intern_profile.json --answers examples/synthetic_intern_answers.json --json
```

### 实际生成诊断结果 (节选自标准输出)
```json
{
  "question_id": 1,
  "question_zh": "你在材料中提到过【Python】，请选一个真实项目，说明背景、个人动作、方案取舍、结果口径以及证据来源。",
  "target_dimension": "core_responsibility",
  "candidate_answer": "我负责查询接口，访问速度提升了 50%。",
  "status": "evaluated",
  "diagnosis": "metric_drift",
  "analysis": "回答中的数字或指标未通过事实核验（声称指标 50% 缺少底稿依据），易被判定为指标虚标或口径不实。",
  "coaching_advice": "所有指标必须严格基于底稿真实基线、单位和统计周期；若缺乏严密压测或监控数据，应客观陈述方案本身，不建议主观推定具体提升幅度。",
  "revised_answer": "我负责查询接口，访问速度进行结构化优化（具体提升幅度因缺乏基线压测数据不作主观量化）。",
  "can_revise": true,
  "verification_status": "verified",
  "missing_elements": [
    "指标基线",
    "指标来源与统计口径",
    "限制或失败复盘"
  ],
  "follow_up_questions": [
    "该指标的 baseline、单位、统计周期和数据来源是什么？",
    "这组数字来自哪份日志、看板或评测集，统计窗口多长？",
    "该方案在哪些场景会失效？你经历过什么失败并如何修正？"
  ]
}
```

### 简历建议落地验证
- **Python / SQLite / SQL**：锚定到项目中真实实现的查询接口，安全改写；
- **Redis / MySQL**：状态标注为 `unsupported`，动作设定为 `ask_user`，`safe_bullet` 严格为空字符串，**绝无凭空捏造的 Redis 缓存经历或虚构压测基准**。

---

## 五、改动文件清单

1. `core/fact_guard.py`：消除全局数值白名单漏洞，强化本地窗口锚定，完善指标漂移类型支持；
2. `core/interview_debrief.py`：实现 `EXPERIENCE_BOUNDARY` 与 `UNCERTAIN`，拆分战术建议与精修答案，剔除虚假架构模板；
3. `core/job_flow.py`：引入 `ResumePatch` 数据结构，移除 `experience[0]` 盲插，建立防篡改事实校验门禁与幂等机制，建立会话指纹；
4. `core/profile_adapter.py`：提取 `bullets` 与 `internships`，优化中文事实优先排序；
5. `core/registry.py`：在 `METRIC_TYPE_TO_TOPICS` 中补齐自反类型与通用类型；
6. `modules/jd_analyst/decoder.py`：在通用领域分类字典中补充数据库核心词表；
7. `presentation/commands/{jd_cmd.py, resume_cmd.py, selftest_cmd.py}`：基于 `PROJECT_ROOT` 规范化绝对路径寻址；
8. `tests/test_career_review.py`：重构断言并新增合成案例测试（总计 20 项单测全部通过）；
9. `SKILL.md` / `README.md`：更新轻量求职 Agent 核心闭环与事实门禁文档。
