# OfferGet Execution State & Handover Ledger

## 1. Product Objective & Active Milestone
- **Core Product Objective**:
  JD 拆解 → 用户事实整理 → 基于事实的简历建议 → 至少三道针对性问题 → 用户真实作答 → 一轮具体反馈。
  重点打磨：基于真实经历、岗位要求和证据边界的面试训练。
- **Active Milestone**:
  - `M0`: Baseline confirmation, issue ledger establishment, subagent delegation.
  - `M1`: Fact constraints fix, prohibit fabricating optimization actions after removing numbers, ResumePatch contract hardening.
  - `M2`: Interview 3-question targeted generation, concrete feedback, and session loop.
  - `M3`: Public component convergence, default user workflow.
  - `M4`: Quality benchmark (24 scenarios), installation verification, performance evidence.

## 2. Baseline & Code Snapshot
- **Repository Root**: `E:/github/OfferGet`
- **Current HEAD**: `ea71f4406ed54bfb86a4cdd3d26d24d05964c812` (PR #3: feat(release-candidate))
- **Merged Main**: `e311ef1adb41d3c9cee809422cc1c4599c8060d8`
- **Working Tree State**: Clean (0 uncommitted changes at baseline)
- **Python Runtime**: 3.13.11 (win32)
- **Chrome Path**: `C:\Program Files\Google\Chrome\Application\chrome.exe`

## 3. Issue Ledger

| issue_id | priority | code_location | user_impact | evidence_grade | owner | status | acceptance_test | log_or_artifact |
|:---|:---:|:---|:---|:---:|:---:|:---:|:---|:---|
| issue_id | priority | code_location | user_impact | evidence_grade | owner | status | acceptance_test | log_or_artifact |
|:---|:---:|:---|:---|:---:|:---:|:---:|:---|:---|
| `ISSUE-01` | P0 | `core/fact_guard.py`, `core/job_flow.py`, `tests/test_career_review.py:371` | 简历改写在数值保持 20% 时，无依据注入 `Megatron-LM` 与通信算子重构被误判为 verified 并应用 | CODE_CONFIRMED | Subagent A / Primary | RESOLVED | `tests/test_career_review.py:test_18`, `tests/test_fact_guard.py:test_11-13` | `core/fact_guard.py` |
| `ISSUE-02` | P0 | `core/interview_debrief.py:88` | 候选人答案中去除未核验数字后，系统自动补造“进行结构化优化”伪造动作 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_02` | `core/interview_debrief.py` |
| `ISSUE-03` | P1 | `core/interview_debrief.py:49,154` | `verification_status` 默认为 `"verified"`，未经充分核验即被标为已核验 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_03` | `core/interview_debrief.py` |
| `ISSUE-04` | P1 | `core/interview_debrief.py:53,231` | `refined_answer` 为空时用 `coaching_advice` 充当回答，混淆指导建议与口头回答 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_04` | `core/interview_debrief.py` |
| `ISSUE-05` | P1 | `core/interview_debrief.py:198` | 包含“没做过”等边界词时整段跳过事实检查，导致“没做过A但做了B提升50%”中的B逃避核验 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_05` | `core/interview_debrief.py` |
| `ISSUE-06` | P1 | `core/interview_debrief.py:147` | 任意技术词即可命中相关性，导致答非所问被误判为切题 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_06` | `core/interview_debrief.py` |
| `ISSUE-07` | P1 | `core/interview_debrief.py:171` | 回答字数超过 80 字即可绕过不相关检查，直接被判定为 WELL_DEFENDED | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_07` | `core/interview_debrief.py` |
| `ISSUE-08` | P1 | `core/interview_debrief.py:150,151` | 单个字母 `'s'` 或中文 `'从'` 误触发指标和基线判断 | CODE_CONFIRMED | Subagent B | RESOLVED | `tests/test_interview_debrief.py:test_issue_08` | `core/interview_debrief.py` |
| `ISSUE-09` | P1 | `core/job_flow.py` | 面试题目按 idx 机械分配标签，缺乏题目意图与统一岗位要求-证据映射 | CODE_CONFIRMED | Subagent B / Primary | RESOLVED | `tests/test_career_review.py:test_21` | `core/job_flow.py` |
| `ISSUE-10` | P1 | `core/job_flow.py` | 会话管理未接入真实 CLI 入口，缺乏可恢复的最小本地会话状态机 | CODE_CONFIRMED | Subagent B / Primary | RESOLVED | `tests/test_career_review.py:test_22,test_23` | `core/job_flow.py`, `core/services.py`, `presentation/commands/review_cmd.py`, `cli.py` |

## 4. Subagent Delegation Ledger

| task_id | native_agent_id | role | target_files (whitelist) | dependencies | status | deliverables |
|:---|:---|:---|:---|:---|:---:|:---|
| `TASK-A01` | subagent-fact-consistency | Subagent A: Fact & Data Consistency | `core/fact_guard.py`, `core/profile_adapter.py`, `tests/test_fact_guard.py`, `tests/test_career_review.py` | None | VERIFIED | Non-metric hallucination detection, ResumePatch validation, grounding tests |
| `TASK-B01` | subagent-interview-quality | Subagent B: Interview Quality | `core/interview_debrief.py`, `tests/test_interview_debrief.py` | None | VERIFIED | Remove fabricated actions, separate coaching from answer, fix boundary/relevance/metric regex |
| `TASK-B02` | primary-agent | Primary Agent: Question Grounding & Session Loop | `core/job_flow.py`, `core/services.py`, `presentation/commands/review_cmd.py`, `cli.py`, `tests/test_career_review.py` | TASK-A01, TASK-B01 | VERIFIED | 3 fixed dimension questions, session save/load/validate, CLI flags --session/--save-session |

## 5. Verification Results
- `tests/test_fact_guard.py`: 13/13 passed
- `tests/test_career_review.py`: 23/23 passed
- `tests/test_interview_debrief.py`: 13/13 passed
- Complete test suite (`tests/`): 371/371 passed (0 failed, 0 skipped, 124.64s)
- `ApexResume/tests/`: 34/34 passed
- `python cli.py selftest`: 11/11 passed, production ready

