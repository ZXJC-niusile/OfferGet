"""
OfferGet Defense Simulator Module
Project Defense Interrogation & Red-Team Simulator for Technical/Resume Interviews,
Thesis Defenses, Competitions, and Project Reviews.

Core Capabilities:
1. Claim-Evidence Matrix Generator:
   - Extracts claims across 4 dimensions (Architecture, Metric, Novelty, Personal Contribution).
   - Verifies against candidate profile SSOT / project materials.
   - Assigns Evidence Status (Material-supported, Material-implied, Material-missing).
   - Assigns Risk Basis (Material-derived, Risk-inferred, Material-derived + Risk-inferred).
   - Assigns Risk Level (High, Medium, Low).
2. 3 Interrogation Intensity Levels:
   - 先热个身 (Warm-up): Friendly confirmation of background, problem setup, basic definitions.
   - 开始挑刺 (Critical): Probes data sources, baseline comparison, why this method vs alternatives.
   - 严刑拷打 (Hell-mode Grilling): Sharp attacks on baseline ablation controls, individual vs open-source code,
     extreme edge case failures, and 15-minute clean environment reproducibility.
3. 3-Round Progressive Follow-up Chains:
   - Deep multi-turn interrogation trees for top 3-5 weak spots.
4. Defensible Answering Strategy & Defense Cheat Sheet (答辩速查卡):
   - Structured 5-step defense ("正面回应 + 说明依据 + 划清边界 + 合理解释 + 给出改进").
   - Prohibited hyperbole vs defensive framing.
   - Ready-to-use cheat sheet cards for defense under pressure.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ---------------------------------------------------------------------------
# Enums and Constants
# ---------------------------------------------------------------------------

from .rubrics import EvidenceStatus, RiskBasis


class RiskLevel:
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class IntensityLevel:
    WARMUP = "先热个身"
    CRITICAL = "开始挑刺"
    HELL = "严刑拷打"


INTENSITY_ALIASES = {
    "warmup": IntensityLevel.WARMUP,
    "warm-up": IntensityLevel.WARMUP,
    "low": IntensityLevel.WARMUP,
    "热身": IntensityLevel.WARMUP,
    "先热个身": IntensityLevel.WARMUP,
    "critical": IntensityLevel.CRITICAL,
    "medium": IntensityLevel.CRITICAL,
    "挑刺": IntensityLevel.CRITICAL,
    "开始挑刺": IntensityLevel.CRITICAL,
    "hell": IntensityLevel.HELL,
    "grilling": IntensityLevel.HELL,
    "high": IntensityLevel.HELL,
    "严刑拷打": IntensityLevel.HELL,
    "高压": IntensityLevel.HELL
}

DEFAULT_SCENARIO = "技术 / 简历面试"

SCENARIO_ROLES = {
    "技术 / 简历面试": ["资深技术面试官", "大模型系统架构师", "技术委员会评审"],
    "保研 / 复试": ["保研复试导师", "学术委员会评委", "严苛审稿人"],
    "课程答辩 / 毕设": ["课程主讲教授", "毕业设计答辩组长", "工程实践导师"],
    "竞赛答辩": ["创新创业竞赛评委", "行业技术专家", "投资与产业评委"],
    "GitHub 项目审查": ["开源社区核心维护者", "架构安全审计员", "底层性能工程师"]
}

# ---------------------------------------------------------------------------
# Heuristic Pattern Signatures
# ---------------------------------------------------------------------------

ARCHITECTURE_KEYWORDS = [
    "架构", "设计", "构建", "分布式", "并行", "引擎", "Megatron", "vLLM", "DeepSpeed",
    "Pipeline", "中间件", "调度", "算子", "协议", "GraphRAG", "MCP", "DFA",
    "Prefill", "Batching", "MoE", "GRPO", "PRM", "MLA", "Triton", "CUDA",
    "NCCL", "ECC", "ZeRO", "微服务", "异步", "缓存", "KV-Cache", "FlashAttention",
    "RoPE", "SwiGLU", "GQA", "PPO", "DPO", "拓扑", "解耦", "集群", "模型"
]

METRIC_PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?%"),                           # 54.2%, 48%
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:x|倍)\b", re.I),         # 2.8x, 3倍
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|毫秒|s|秒|min|分钟|小时|h)\b", re.I), # 320ms, 2.4h
    re.compile(r"\b\d+(?:,\d{3})*\s*(?:万|亿|万元|Token|卡|GPU|节点)\b"), # 1024卡, 3800万元
    re.compile(r"(?:提升|降低|减少|优化至|压减至|节约|节省|达到)\s*[\+\-]?\d+(?:\.\d+)?%?"),
    re.compile(r"\b(?:MFU|P99|TTFT|GSM8K|MATH|QPS|TPS|BLEU|ROUGE|mAP|Acc|Accuracy)\b", re.I)
]

NOVELTY_KEYWORDS = [
    "首创", "独创", "主导自研", "自研", "创新", "提出", "攻坚", "突破", "原创",
    "移植并开源", "深度适配", "协同算子", "无辅助损失", "零精度损失", "从零到一",
    "自适应路由", "自愈", "突破性", "独家", "全新"
]

CONTRIBUTION_KEYWORDS = [
    "主导", "负责", "独立", "牵头", "发起人", "第一作者", "一作", "核心开发",
    "设计并落地", "攻坚", "排查", "独立完成", "主导设计", "主导攻坚"
]

OVERCLAIM_PATTERNS = [
    (re.compile(r"完全实现(?:了)?"), "宣称完全实现，易被攻击未覆盖的边界工况与边缘异常"),
    (re.compile(r"(?:全量|完全|100%|彻底)自研"), "宣称全量自研，易被质疑开源依赖与代码所有权占比"),
    (re.compile(r"(?:零故障|绝对稳定|100%可用)"), "宣称零故障，易招致极端网络分区与硬件掉卡压力测试"),
    (re.compile(r"(?:最优|业界最高|彻底解决)"), "宣称最优或彻底解决，易被要求严格数学证明或权威SOTA消融对比"),
    (re.compile(r"(?:全部由我独立完成|单人全流程)"), "宣称单人全权独立，易被追问团队协作分工与开源借用界限")
]

PROHIBITED_TO_SAFE_REPLACEMENTS = [
    ("完全实现了大模型分布式训练", "当前版本重点攻坚了 Sequence/Context Parallel 融合链路与通信掩盖"),
    ("全量自研推理加速引擎", "基于开源主流架构（如 vLLM/Megatron）独立定制了核心算子与调度流"),
    ("系统达到零故障秒级自愈", "针对单卡掉线等典型故障实现了秒级探针隔离，复杂网络分区仍在工程化迭代"),
    ("模型效果业界最优", "在 GSM8K 与 MATH 等特定评测集上相比基线取得明显增益"),
    ("全部核心代码由我独立编写", "我主要负责核心算法设计、关键 Kernel 实现与实验闭环，底层依赖社区成熟设施")
]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ClaimItem:
    """Represents a single project claim and its empirical evidence status."""
    id: str
    category: str              # architecture, metric, novelty, personal_contribution
    category_zh: str           # 架构设计, 量化指标, 创新突破, 个人贡献
    claim_text: str            # Original claim statement
    evidence_source: str       # SSOT location, code path, or "未提供可定位材料"
    evidence_status: str       # Material-supported, Material-implied, Material-missing
    gap: str                   # Concrete gap or missing proof
    risk_basis: str            # Material-derived, Risk-inferred, or Combined
    risk_level: str            # High, Medium, Low
    extracted_keywords: List[str] = field(default_factory=list)
    corroborating_data: Dict[str, Any] = field(default_factory=dict)

    def to_matrix_row(self) -> Dict[str, str]:
        """Returns row dictionary matching the Claim-Evidence Matrix schema."""
        status_val = self.evidence_status.value if hasattr(self.evidence_status, "value") else str(self.evidence_status)
        basis_val = self.risk_basis.value if hasattr(self.risk_basis, "value") else str(self.risk_basis)
        return {
            "Claim / 项目说法": self.claim_text,
            "Evidence / 材料依据": self.evidence_source,
            "Evidence status / 证据状态": status_val,
            "Gap / 缺口": self.gap,
            "Risk basis / 风险依据": basis_val,
            "Risk": self.risk_level
        }

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if hasattr(self.evidence_status, "value"):
            data["evidence_status"] = self.evidence_status.value
        if hasattr(self.risk_basis, "value"):
            data["risk_basis"] = self.risk_basis.value
        return data


@dataclass
class FollowUpRound:
    """A single round within a progressive interrogation chain."""
    round_index: int
    title: str
    interviewer_role: str
    question: str
    interviewer_intent: str
    vulnerability_probed: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FollowUpChain:
    """A realistic 3-round progressive follow-up interrogation chain targeting a weak spot."""
    chain_id: str
    target_claim_id: str
    target_claim: str
    category: str
    gap: str
    risk_basis: str
    risk_level: str
    role: str
    rounds: List[FollowUpRound] = field(default_factory=list)
    defensive_strategy: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["rounds"] = [r.to_dict() if isinstance(r, FollowUpRound) else r for r in self.rounds]
        return data


@dataclass
class DefenseCheatSheet:
    """答辩速查卡: High-density defensive cards for rapid review under pressure."""
    elevator_pitch: str
    top_vulnerabilities: List[Dict[str, str]]
    metric_audit_sheet: List[Dict[str, str]]
    contribution_boundaries: List[Dict[str, str]]
    fifteen_minute_reproducibility: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DefenseSimulationResult:
    """Comprehensive output of the project defense simulation."""
    project_name: str
    one_sentence_positioning: str
    intensity: str
    scenario: str
    matrix: List[ClaimItem] = field(default_factory=list)
    high_risk_gaps: List[Dict[str, Any]] = field(default_factory=list)
    follow_up_chains: List[FollowUpChain] = field(default_factory=list)
    intensity_questions: List[Dict[str, str]] = field(default_factory=list)
    defensible_strategy: Dict[str, Any] = field(default_factory=dict)
    material_repairs: List[Dict[str, Any]] = field(default_factory=list)
    defense_cheat_sheet: Optional[DefenseCheatSheet] = None
    summary_stats: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["matrix"] = [c.to_dict() for c in self.matrix]
        data["follow_up_chains"] = [fc.to_dict() for fc in self.follow_up_chains]
        if self.defense_cheat_sheet:
            data["defense_cheat_sheet"] = self.defense_cheat_sheet.to_dict()
        return data

    def to_markdown(self) -> str:
        """
        Generates the mandatory 7-section full review Markdown report in exact order:
        1. 项目一句话定位
        2. Claim-Evidence Matrix
        3. 高风险缺口（最多 5 项）
        4. 连续追问链
        5. 防守型回答策略
        6. 材料修复清单
        7. 答辩速查卡
        """
        lines: List[str] = []

        # 1. 项目一句话定位
        lines.append(f"# 项目答辩红蓝对抗审计报告: {self.project_name}")
        lines.append(f"> **答辩场景**: {self.scenario} | **对抗强度**: `{self.intensity}` | **审计状态**: 已完成\n")
        lines.append("## 1. 项目一句话定位")
        lines.append(f"{self.one_sentence_positioning}\n")

        # 2. Claim-Evidence Matrix
        lines.append("## 2. Claim-Evidence Matrix")
        lines.append("| Claim / 项目说法 | Evidence / 材料依据 | Evidence status / 证据状态 | Gap / 缺口 | Risk basis / 风险依据 | Risk |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for claim in self.matrix:
            row = claim.to_matrix_row()
            c_text = row["Claim / 项目说法"].replace("|", "\\|").replace("\n", " ")
            e_text = row["Evidence / 材料依据"].replace("|", "\\|").replace("\n", " ")
            s_text = row["Evidence status / 证据状态"]
            g_text = row["Gap / 缺口"].replace("|", "\\|").replace("\n", " ")
            b_text = row["Risk basis / 风险依据"]
            r_text = row["Risk"]
            lines.append(f"| {c_text} | {e_text} | {s_text} | {g_text} | {b_text} | {r_text} |")
        lines.append("")

        # 3. 高风险缺口（最多 5 项）
        lines.append("## 3. 高风险缺口")
        if not self.high_risk_gaps:
            lines.append("经证据链交叉审计，暂无致命高风险证据断裂缺口。\n")
        else:
            for idx, gap in enumerate(self.high_risk_gaps[:5], 1):
                lines.append(f"### 缺口 {idx:02d}: [{gap.get('risk_level', 'High')}] {gap.get('category_zh', '')} - {gap.get('title', '')}")
                lines.append(f"- **核心原话**: `{gap.get('claim_text', '')}`")
                lines.append(f"- **证据状态**: `{gap.get('evidence_status', '')}` (依据: {gap.get('evidence_source', '')})")
                lines.append(f"- **具体软肋**: {gap.get('gap', '')}")
                lines.append(f"- **风险判定**: `{gap.get('risk_basis', '')}`")
                lines.append(f"- **高危攻击点**: {gap.get('attack_vector', '')}\n")

        # 4. 连续追问链
        lines.append("## 4. 连续追问链")
        lines.append(f"> 基于 `{self.intensity}` 强度设定，针对最薄弱的证据缺口展开角色化连环追问：\n")

        # First output intensity general questions
        lines.append(f"### 【{self.intensity}】通用开场与审问切入")
        for q in self.intensity_questions:
            lines.append(f"- **[{q.get('role', '面试官')}]**: {q.get('question', '')}")
            lines.append(f"  *考核意图*: {q.get('intent', '')}")
        lines.append("")

        # Then output sequential 3-round progressive chains
        for chain in self.follow_up_chains:
            lines.append(f"### 追问链 {chain.chain_id}: 针对「{chain.target_claim[:30]}...」")
            lines.append(f"- **主审角色**: {chain.role} | **风险等级**: `{chain.risk_level}` | **证据基础**: `{chain.risk_basis}`")
            lines.append(f"- **核心缺口**: {chain.gap}\n")
            for r in chain.rounds:
                round_obj = r if isinstance(r, FollowUpRound) else FollowUpRound(**r)
                lines.append(f"#### {round_obj.title}")
                lines.append(f"**提问**: “{round_obj.question}”")
                lines.append(f"- *提问意图*: {round_obj.interviewer_intent}")
                lines.append(f"- *试探软肋*: {round_obj.vulnerability_probed}\n")

            if chain.defensive_strategy:
                lines.append(f"> **防守破局支点**: {chain.defensive_strategy.get('pivot_focus', '')}")
                lines.append(f"> **推荐回答话术**: {chain.defensive_strategy.get('recommended_response', '')}\n")

        # 5. 防守型回答策略
        lines.append("## 5. 防守型回答策略")
        lines.append("遵循 **“承认边界 + 说明依据 + 强调真实贡献 + 给出改进”** 五步法黄金防守模型：\n")
        strat = self.defensible_strategy
        lines.append("### 5.1 黄金五步防守法则 (5-Step Grounded Framework)")
        for step in strat.get("golden_steps", []):
            lines.append(f"1. **{step.get('step', '')}**: {step.get('desc', '')} (示范: *“{step.get('example', '')}”*)")
        lines.append("")

        lines.append("### 5.2 答辩高危雷区 vs 安全防守表达对照 (Overclaim vs Safe Framing)")
        lines.append("| 高危夸大词 (严禁) | 稳妥防守话术 (推荐) | 规避的审查风险 |")
        lines.append("| --- | --- | --- |")
        for item in strat.get("safe_framing_pairs", []):
            c_bad = item.get("bad", "").replace("|", "\\|")
            c_good = item.get("good", "").replace("|", "\\|")
            c_why = item.get("risk", "").replace("|", "\\|")
            lines.append(f"| {c_bad} | {c_good} | {c_why} |")
        lines.append("")

        # 6. 材料修复清单
        lines.append("## 6. 材料修复清单")
        lines.append("针对上述审计出的证据断链，建议在答辩前完成以下定向材料修补（按优先级排列）：\n")
        for idx, repair in enumerate(self.material_repairs, 1):
            lines.append(f"### 修补项 {idx:02d}: [{repair.get('location', '代码/文档')}] {repair.get('action', '')}")
            lines.append(f"- **优先级**: `{repair.get('priority', 'P1')}` | **预估耗时**: {repair.get('effort', '1小时')}")
            lines.append(f"- **修补依据**: 闭合针对「{repair.get('target_gap', '')}」的质疑")
            lines.append(f"- **执行方案**: {repair.get('detail', '')}\n")

        # 7. 答辩速查卡
        lines.append("## 7. 答辩速查卡")
        lines.append("> 供候选人在上场答辩前 5 分钟快速扫视，强化防守记忆，防止现场被击穿。\n")
        if self.defense_cheat_sheet:
            cs = self.defense_cheat_sheet
            lines.append("```text")
            lines.append(f"【卡片 1 · 核心定位与技术护城河】\n{cs.elevator_pitch}\n")
            lines.append("【卡片 2 · 三大软肋防守底线】")
            for item in cs.top_vulnerabilities:
                lines.append(f"• 质疑点: {item.get('vulnerability', '')}")
                lines.append(f"  底线表态: {item.get('bottom_line', '')}")
            lines.append("\n【卡片 3 · 数据指标与基线口径速查】")
            for item in cs.metric_audit_sheet:
                lines.append(f"• 指标: {item.get('metric', '')} | 基线: {item.get('baseline', '')} | 依据: {item.get('source', '')}")
            lines.append("\n【卡片 4 · 个人贡献与开源依赖界限】")
            for item in cs.contribution_boundaries:
                lines.append(f"• 模块: {item.get('module', '')} | 自研/负责: {item.get('personal', '')} | 开源/团队: {item.get('external', '')}")
            lines.append("\n【卡片 5 · 15分钟干净环境复现自救预案】")
            repro = cs.fifteen_minute_reproducibility
            lines.append(f"• 启动入口: {repro.get('command', 'bash scripts/reproduce.sh')}")
            lines.append(f"• 核心单测: {repro.get('test_target', 'pytest tests/test_core_engine.py')}")
            lines.append(f"• 兜底解释: {repro.get('fallback_pivot', '若因网络或依赖超时，主动展示本地预备好的离线日志与 profiler 抓包追踪文件。')}")
            lines.append("```\n")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# DefenseSimulator Class
# ---------------------------------------------------------------------------

class DefenseSimulator:
    """
    DefenseSimulator Engine.
    Executes red-team interrogations and audits project defense claims against evidence.
    """

    def __init__(self, profile_context: Optional[Union[dict, str, Path]] = None):
        self.profile_data: Optional[Dict[str, Any]] = None
        self.verified_numbers: Set[float] = set()
        self.verified_metrics_map: Dict[str, Any] = {}
        self.verified_competencies: Set[str] = set()
        self.verified_projects: List[Dict[str, Any]] = []
        self.verified_publications: List[Dict[str, Any]] = []

        if profile_context is not None:
            self.load_profile(profile_context)

    def load_profile(self, profile_context: Union[dict, str, Path]) -> None:
        """Loads and indexes the candidate's Single Source of Truth (SSOT) profile."""
        if isinstance(profile_context, (str, Path)):
            path = Path(profile_context)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self.profile_data = json.load(f)
            else:
                self.profile_data = json.loads(str(profile_context))
        elif isinstance(profile_context, dict):
            self.profile_data = copy.deepcopy(profile_context)
        else:
            raise TypeError(f"Expected dict, str, or Path, got {type(profile_context).__name__}")

        self._index_profile()

    def _index_profile(self) -> None:
        """Extracts structured baseline facts from profile context for claim corroboration."""
        self.verified_numbers.clear()
        self.verified_metrics_map.clear()
        self.verified_competencies.clear()
        self.verified_projects.clear()
        self.verified_publications.clear()

        if not self.profile_data:
            return

        # 1. Publications
        for pub in self.profile_data.get("publications", []):
            self.verified_publications.append(pub)

        # 2. Projects
        for proj in self.profile_data.get("projects", []):
            self.verified_projects.append(proj)
            if "stars" in proj and isinstance(proj["stars"], (int, float)):
                self.verified_numbers.add(float(proj["stars"]))

        # 3. Competencies
        comp = self.profile_data.get("competencies", {})
        for cat, items in comp.items():
            if isinstance(items, list):
                for item in items:
                    self.verified_competencies.add(str(item).lower())

        # 4. Experience & Verified Metrics
        for exp in self.profile_data.get("experience", []):
            for hl in exp.get("highlights", []):
                v_metrics = hl.get("verified_metrics", {})
                for k, v in v_metrics.items():
                    self.verified_metrics_map[k] = v
                    # Extract numeric values
                    if isinstance(v, (int, float)):
                        self.verified_numbers.add(float(v))
                    elif isinstance(v, str):
                        for num_match in re.findall(r"\b\d+(?:\.\d+)?\b", v):
                            try:
                                self.verified_numbers.add(float(num_match))
                            except ValueError:
                                pass

        # Years of experience
        cand = self.profile_data.get("candidate", {})
        if "years_of_experience" in cand:
            self.verified_numbers.add(float(cand["years_of_experience"]))

    # -----------------------------------------------------------------------
    # Primary Simulation Entry Point
    # -----------------------------------------------------------------------

    def simulate(
        self,
        project_input: Union[str, List[Any], Dict[str, Any]],
        intensity: str = IntensityLevel.CRITICAL,
        scenario: str = DEFAULT_SCENARIO,
        project_name: Optional[str] = None
    ) -> DefenseSimulationResult:
        """
        Executes a complete project defense audit and red-team interrogation simulation.
        """
        norm_intensity = INTENSITY_ALIASES.get(intensity.lower().strip(), IntensityLevel.CRITICAL)
        norm_scenario = scenario if scenario in SCENARIO_ROLES else DEFAULT_SCENARIO

        # 1. Normalize input into structured project claims and text
        extracted_info = self._normalize_project_input(project_input, project_name)
        proj_name = extracted_info["name"]
        raw_claims = extracted_info["raw_claims"]
        one_sentence_pos = extracted_info["positioning"]

        # 2. Generate Claim-Evidence Matrix across 4 dimensions
        matrix_items = self._build_claim_evidence_matrix(raw_claims, extracted_info)

        # 3. Identify Top High-Risk Gaps (max 5)
        high_risk_gaps = self._identify_high_risk_gaps(matrix_items)

        # 4. Generate 3-Round Progressive Follow-up Chains for top weak spots
        follow_up_chains = self._generate_follow_up_chains(high_risk_gaps, norm_scenario, norm_intensity)

        # 5. Generate Interrogation Questions for the current intensity level
        intensity_questions = self._generate_intensity_questions(matrix_items, norm_intensity, norm_scenario)

        # 6. Formulate Defensible Answering Strategy & Cheat Sheet
        defensible_strategy = self._build_defensible_strategy(matrix_items, high_risk_gaps)
        material_repairs = self._build_material_repairs(high_risk_gaps)
        cheat_sheet = self._build_cheat_sheet(proj_name, one_sentence_pos, high_risk_gaps, matrix_items)

        # 7. Calculate summary stats
        summary_stats = {
            "total_claims": len(matrix_items),
            "supported_count": sum(1 for m in matrix_items if m.evidence_status == EvidenceStatus.MATERIAL_SUPPORTED),
            "implied_count": sum(1 for m in matrix_items if m.evidence_status == EvidenceStatus.MATERIAL_IMPLIED),
            "missing_count": sum(1 for m in matrix_items if m.evidence_status == EvidenceStatus.MATERIAL_MISSING),
            "high_risk_count": sum(1 for m in matrix_items if m.risk_level == RiskLevel.HIGH),
            "medium_risk_count": sum(1 for m in matrix_items if m.risk_level == RiskLevel.MEDIUM),
            "low_risk_count": sum(1 for m in matrix_items if m.risk_level == RiskLevel.LOW)
        }

        return DefenseSimulationResult(
            project_name=proj_name,
            one_sentence_positioning=one_sentence_pos,
            intensity=norm_intensity,
            scenario=norm_scenario,
            matrix=matrix_items,
            high_risk_gaps=high_risk_gaps,
            follow_up_chains=follow_up_chains,
            intensity_questions=intensity_questions,
            defensible_strategy=defensible_strategy,
            material_repairs=material_repairs,
            defense_cheat_sheet=cheat_sheet,
            summary_stats=summary_stats
        )

    # -----------------------------------------------------------------------
    # Input Normalization
    # -----------------------------------------------------------------------

    def _normalize_project_input(
        self,
        project_input: Union[str, List[Any], Dict[str, Any]],
        override_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Normalizes various input formats (text, list, dict, candidate profile) into claims."""
        proj_name = override_name or "重点研发项目"
        positioning = ""
        raw_claims: List[Dict[str, Any]] = []

        if isinstance(project_input, str):
            # Check if it's a file path
            path = Path(project_input)
            if path.exists() and path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    try:
                        parsed = json.loads(content)
                        return self._normalize_project_input(parsed, override_name)
                    except json.JSONDecodeError:
                        text = content
                except Exception:
                    text = project_input
            else:
                text = project_input

            # Extract project title or use override
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines and not override_name:
                first_line = lines[0]
                if len(first_line) < 50 and any(kw in first_line for kw in ["系统", "引擎", "平台", "框架", "库", "算子", "OS", "项目"]):
                    proj_name = first_line.lstrip("#").strip()
            
            # Split into sentence-level claims
            raw_claims = self._split_text_into_claims(text)
            positioning = self._synthesize_positioning(proj_name, text, raw_claims)

        elif isinstance(project_input, list):
            # List of strings or claim dicts
            for item in project_input:
                if isinstance(item, str):
                    raw_claims.append({"claim_text": item, "source": "用户输入声明列表"})
                elif isinstance(item, dict):
                    c_text = item.get("claim_text") or item.get("claim_zh") or item.get("claim") or str(item)
                    c_src = item.get("source") or item.get("evidence") or "输入材料"
                    raw_claims.append({"claim_text": c_text, "source": c_src, "metadata": item})
            positioning = f"针对包含 {len(raw_claims)} 项核心论断的技术方案与工程实现。"

        elif isinstance(project_input, dict):
            # Check if it's a full candidate profile
            if "projects" in project_input or "experience" in project_input:
                # If override_name specified, locate it
                target_proj = None
                if override_name and "projects" in project_input:
                    for p in project_input["projects"]:
                        if override_name.lower() in p.get("name", "").lower():
                            target_proj = p
                            break
                if not target_proj and project_input.get("projects"):
                    target_proj = project_input["projects"][0]

                if target_proj:
                    return self._normalize_project_input(target_proj, target_proj.get("name", override_name))
                elif project_input.get("experience"):
                    first_exp = project_input["experience"][0]
                    proj_name = override_name or first_exp.get("company", "核心工程项目")
                    for hl in first_exp.get("highlights", []):
                        raw_claims.append({
                            "claim_text": hl.get("claim_zh", ""),
                            "source": f"经验亮点 [{hl.get('claim_id', 'EXP')}]",
                            "verified_metrics": hl.get("verified_metrics", {})
                        })
                    positioning = f"{first_exp.get('role', '负责人')}在{proj_name}主导的核心技术落地与性能攻坚。"
            else:
                # Single project dict
                proj_name = project_input.get("name") or override_name or "重点研发项目"
                desc = project_input.get("description_zh") or project_input.get("description") or ""
                role = project_input.get("role", "")
                
                # Add role claim if available
                if role:
                    raw_claims.append({
                        "claim_text": f"作为{role}，主导并推进该项目的架构设计与核心技术实现",
                        "source": "项目角色声明",
                        "category_hint": "personal_contribution"
                    })

                # Add description claims
                desc_claims = self._split_text_into_claims(desc, source=f"项目描述 [{proj_name}]")
                raw_claims.extend(desc_claims)

                # Add highlights or bullets
                for hl in project_input.get("highlights", []):
                    if isinstance(hl, str):
                        raw_claims.append({"claim_text": hl, "source": "项目亮点清单"})
                    elif isinstance(hl, dict):
                        raw_claims.append({
                            "claim_text": hl.get("claim_zh") or hl.get("claim") or str(hl),
                            "source": "项目结构化亮点",
                            "verified_metrics": hl.get("verified_metrics", {})
                        })

                # Add github stars if available
                if "stars" in project_input:
                    raw_claims.append({
                        "claim_text": f"开源项目在 GitHub 获得 {project_input['stars']} Stars 关注并合并至上游生态",
                        "source": f"GitHub 仓库证据 ({project_input.get('github', '')})",
                        "category_hint": "metric",
                        "corroborated": True
                    })

                positioning = desc[:120] + ("..." if len(desc) > 120 else "")

        return {
            "name": proj_name,
            "positioning": positioning or f"{proj_name}：面向实际业务的高性能系统/算法工程实现。",
            "raw_claims": raw_claims
        }

    def _split_text_into_claims(self, text: str, source: str = "输入文本材料") -> List[Dict[str, Any]]:
        """Splits narrative paragraphs into atomic claim statements."""
        claims: List[Dict[str, Any]] = []
        # Split on sentence boundaries
        sentences = re.split(r"(?<=[。；;!\n])\s*", text)
        for s in sentences:
            clean_s = s.strip().lstrip("•-*0123456789. ")
            if len(clean_s) >= 8:
                claims.append({"claim_text": clean_s, "source": source})
        return claims

    def _synthesize_positioning(self, name: str, text: str, claims: List[Dict[str, Any]]) -> str:
        """Synthesizes a 1-sentence precise project positioning statement."""
        if len(claims) > 0:
            first_claim = claims[0]["claim_text"]
            if len(first_claim) < 100:
                return f"{name}：{first_claim}"
        return f"{name}：面向核心业务场景构建的高可用、高性能系统工程与关键算法实现方案。"

    # -----------------------------------------------------------------------
    # Claim-Evidence Matrix Generation
    # -----------------------------------------------------------------------

    def _build_claim_evidence_matrix(
        self,
        raw_claims: List[Dict[str, Any]],
        extracted_info: Dict[str, Any]
    ) -> List[ClaimItem]:
        """
        Audits raw claims across the 4 core dimensions:
        Architecture, Metric, Novelty, Personal Contribution.
        """
        matrix: List[ClaimItem] = []
        claim_counter = 1

        for item in raw_claims:
            c_text = item.get("claim_text", "").strip()
            c_src = item.get("source", "材料依据未明")
            hint = item.get("category_hint")
            meta = item.get("metadata", {})
            v_metrics = item.get("verified_metrics", {})

            # Decompose composite claims into sub-dimensional atomic claims if appropriate
            sub_claims = self._decompose_composite_claim(c_text, hint)

            for cat, claim_fragment, kws in sub_claims:
                claim_id = f"CLM-{claim_counter:02d}"
                claim_counter += 1

                category_zh_map = {
                    "architecture": "架构设计与系统方案",
                    "metric": "量化收益与性能指标",
                    "novelty": "技术创新与自研突破",
                    "personal_contribution": "个人贡献与职责边界"
                }

                # Evaluate evidence status, gap, risk basis, and risk level
                ev_status, ev_source, gap, risk_basis, risk_lvl = self._evaluate_claim_evidence(
                    category=cat,
                    claim_text=claim_fragment,
                    original_source=c_src,
                    v_metrics=v_metrics,
                    meta=meta
                )

                matrix.append(ClaimItem(
                    id=claim_id,
                    category=cat,
                    category_zh=category_zh_map.get(cat, "通用技术方案"),
                    claim_text=claim_fragment,
                    evidence_source=ev_source,
                    evidence_status=ev_status,
                    gap=gap,
                    risk_basis=risk_basis,
                    risk_level=risk_lvl,
                    extracted_keywords=kws,
                    corroborating_data={"metrics": v_metrics}
                ))

        # Ensure all 4 dimensions are represented in the matrix
        matrix = self._ensure_all_dimensions_represented(matrix, extracted_info)
        return matrix

    def _decompose_composite_claim(
        self,
        text: str,
        hint: Optional[str] = None
    ) -> List[Tuple[str, str, List[str]]]:
        """
        Analyzes a sentence and extracts sub-claims corresponding to the 4 core dimensions.
        """
        results: List[Tuple[str, str, List[str]]] = []

        # Check for metric patterns
        has_metric = any(p.search(text) for p in METRIC_PATTERNS)
        # Check for architecture keywords
        arch_matches = [w for w in ARCHITECTURE_KEYWORDS if w.lower() in text.lower()]
        # Check for novelty keywords
        novelty_matches = [w for w in NOVELTY_KEYWORDS if w in text]
        # Check for contribution keywords
        contrib_matches = [w for w in CONTRIBUTION_KEYWORDS if w in text]

        if hint:
            results.append((hint, text, arch_matches or novelty_matches or contrib_matches))
            return results

        # 1. Personal contribution extraction
        if contrib_matches:
            results.append(("personal_contribution", text, contrib_matches))

        # 2. Metric extraction
        if has_metric:
            results.append(("metric", text, ["数值指标", "收益验证"]))

        # 3. Novelty extraction
        if novelty_matches:
            results.append(("novelty", text, novelty_matches))

        # 4. Architecture extraction
        if arch_matches and not (contrib_matches and not novelty_matches and not has_metric):
            results.append(("architecture", text, arch_matches[:4]))

        # Fallback if unclassified
        if not results:
            results.append(("architecture", text, []))

        # Deduplicate if single claim matches multiple, or keep atomic
        return results

    def _evaluate_claim_evidence(
        self,
        category: str,
        claim_text: str,
        original_source: str,
        v_metrics: Dict[str, Any],
        meta: Dict[str, Any]
    ) -> Tuple[str, str, str, str, str]:
        """
        Evaluates a claim against the Single Source of Truth and domain rules.
        Returns: (evidence_status, evidence_source, gap, risk_basis, risk_level)
        """
        ev_status = EvidenceStatus.MATERIAL_MISSING
        ev_source = original_source
        gap = ""
        risk_basis = RiskBasis.COMBINED
        risk_lvl = RiskLevel.MEDIUM

        # Check for overclaims
        is_overclaim = False
        overclaim_reason = ""
        for pattern, reason in OVERCLAIM_PATTERNS:
            if pattern.search(claim_text):
                is_overclaim = True
                overclaim_reason = reason
                break

        # Check explicit limitation / scope boundary statements (can be Material-supported)
        is_explicit_boundary = any(w in claim_text for w in [
            "当前版本主要", "属于后续改进", "面向课程设计", "科研原型", "尚未达到", "主要用于展示", "基于典型工况"
        ])
        if is_explicit_boundary:
            return (
                EvidenceStatus.MATERIAL_SUPPORTED,
                f"{original_source} (显式声明边界)",
                "已明确当前版本边界，后续需补充生产级演进步骤与极限压力测试计划",
                RiskBasis.MATERIAL_DERIVED,
                RiskLevel.LOW
            )

        # -------------------------------------------------------------------
        # Category-Specific Corroboration
        # -------------------------------------------------------------------
        if category == "metric":
            # Extract numbers from claim
            claim_nums: List[float] = []
            for m in re.findall(r"\b\d+(?:\.\d+)?\b", claim_text):
                try:
                    claim_nums.append(float(m))
                except ValueError:
                    pass

            # Check if numbers are grounded in verified profile metrics
            grounded_count = sum(1 for n in claim_nums if n in self.verified_numbers)
            has_ssot_metrics = bool(v_metrics or grounded_count > 0)

            if has_ssot_metrics:
                ev_status = EvidenceStatus.MATERIAL_SUPPORTED
                ev_source = f"SSOT 认证指标库 / {original_source}"
                gap = "指标虽有 SSOT 校验记录，但材料未详述 Baseline 对照组基线配置、硬件拓扑与极端长序列下的消融细节"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.LOW if not is_overclaim else RiskLevel.MEDIUM
            elif claim_nums:
                # Has numbers, but NOT verified in SSOT
                ev_status = EvidenceStatus.MATERIAL_MISSING
                ev_source = "未提供可定位支撑材料 (仅见口头断言)"
                gap = "高收益指标缺乏对照组基线（Baseline）、标准测试集来源说明与严格变量消融实验支撑"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.HIGH
            else:
                ev_status = EvidenceStatus.MATERIAL_IMPLIED
                gap = "性能收益属于定性描述，缺少量化指标、统计显著性检验与吞吐延迟测试数据"
                risk_basis = RiskBasis.RISK_INFERRED
                risk_lvl = RiskLevel.MEDIUM

        elif category == "novelty":
            # Check if publications or open source stars back the novelty
            has_pub = any(pub.get("title", "").lower() in claim_text.lower() or
                          any(w in pub.get("title", "").lower() for w in ["routing", "moe", "speculative", "attention"])
                          for pub in self.verified_publications)
            has_oss_repo = any(p.get("name", "").lower() in claim_text.lower() for p in self.verified_projects)

            if has_pub:
                ev_status = EvidenceStatus.MATERIAL_SUPPORTED
                ev_source = "顶会论文发表记录 (NeurIPS/ICLR)"
                gap = "算法创新已被顶会收录，但工程落地的硬件吞吐、通信开销与算子调度适配仍可能被深度拷问"
                risk_basis = RiskBasis.MATERIAL_DERIVED
                risk_lvl = RiskLevel.LOW
            elif has_oss_repo:
                ev_status = EvidenceStatus.MATERIAL_SUPPORTED
                ev_source = "开源项目公开代码仓库及生态合并记录"
                gap = "已开源并获社区关注，但需明确自研算子内核与借用开源模板的代码量边界"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.MEDIUM
            elif any(w in claim_text for w in ["首创", "独创", "全量自研", "突破"]):
                ev_status = EvidenceStatus.MATERIAL_MISSING
                ev_source = "未提供可定位论文或专利佐证"
                gap = "宣称独创/自研重大突破，但材料中未见开源 PR 链接、论文索引或与业界 SOTA 主流方案的技术断代差异说明"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.HIGH
            else:
                ev_status = EvidenceStatus.MATERIAL_IMPLIED
                gap = "技术创新更偏向工程集成与成熟模块组装，难以支撑算法原生理论创新断言"
                risk_basis = RiskBasis.RISK_INFERRED
                risk_lvl = RiskLevel.MEDIUM

        elif category == "personal_contribution":
            # Check if role matches verified profile
            cand_title = self.profile_data.get("candidate", {}).get("title_zh", "") if self.profile_data else ""
            is_lead = any(w in claim_text for w in ["主导", "负责人", "架构师", "发起人"])

            if is_overclaim:
                ev_status = EvidenceStatus.MATERIAL_MISSING
                ev_source = "材料中的绝对化口头断言"
                gap = overclaim_reason or "个人贡献表述过满，未剥离开源复用代码、前人工作遗产与团队协作成果"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.HIGH
            elif is_lead and (cand_title or self.verified_projects):
                ev_status = EvidenceStatus.MATERIAL_SUPPORTED
                ev_source = "SSOT 履历与职位职级记录"
                gap = "虽具备 Tech Lead 职责凭证，但在超大规模团队协作中，个人亲自编写的核心代码行数与架构总控界限易被现场追问"
                risk_basis = RiskBasis.RISK_INFERRED
                risk_lvl = RiskLevel.MEDIUM
            else:
                ev_status = EvidenceStatus.MATERIAL_IMPLIED
                gap = "团队与个人职责边界不够具象，未明确个人在算法设计、代码编写、调优调试中的确切百分比"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.MEDIUM

        elif category == "architecture":
            # Architecture design check
            has_comp = any(w in self.verified_competencies for w in ["megatron-lm", "vllm", "distributed parallelism", "cuda", "mcp"])
            if has_comp:
                ev_status = EvidenceStatus.MATERIAL_SUPPORTED
                ev_source = "SSOT 核心专业技能池与代码工程记录"
                gap = "架构方案宏观逻辑完整，但缺少微架构内核实现、NCCL 通信链路时序与单卡故障隔离的时序细节"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.MEDIUM
            elif is_overclaim:
                ev_status = EvidenceStatus.MATERIAL_MISSING
                ev_source = "材料仅给出高层抽象命名"
                gap = "缺乏底层通信原语、存储拓扑与高并发下的瓶颈压测数据支撑"
                risk_basis = RiskBasis.COMBINED
                risk_lvl = RiskLevel.HIGH
            else:
                ev_status = EvidenceStatus.MATERIAL_IMPLIED
                gap = "技术选型罗列了业界流行框架，但缺乏'为何选用此方案而非替代方案（如 ZeRO-3 vs TP/PP）'的严谨选型依据"
                risk_basis = RiskBasis.RISK_INFERRED
                risk_lvl = RiskLevel.MEDIUM

        # Elevate risk if overclaim
        if is_overclaim and risk_lvl != RiskLevel.HIGH:
            risk_lvl = RiskLevel.HIGH

        return ev_status, ev_source, gap, risk_basis, risk_lvl

    def _ensure_all_dimensions_represented(
        self,
        matrix: List[ClaimItem],
        extracted_info: Dict[str, Any]
    ) -> List[ClaimItem]:
        """Ensures that all 4 dimensions (architecture, metric, novelty, contribution) are present."""
        existing_cats = {m.category for m in matrix}
        counter = len(matrix) + 1
        proj_name = extracted_info.get("name", "项目")

        fallback_definitions = [
            ("architecture", "架构设计与系统方案",
             f"{proj_name} 采用分布式并行调度与解耦架构，支撑生产级吞吐与稳定计算",
             "材料宏观架构章节", EvidenceStatus.MATERIAL_IMPLIED,
             "未在材料中给出跨节点通信拓扑图、算子融合流水线与故障隔离机制细节",
             RiskBasis.RISK_INFERRED, RiskLevel.MEDIUM),

            ("metric", "量化收益与性能指标",
             f"{proj_name} 在生产/仿真测试中显著提升系统吞吐与可用率，达成预定业务目标",
             "未提供可定位材料", EvidenceStatus.MATERIAL_MISSING,
             "缺少端到端量化收益对照基准、硬件测试环境配置与置信区间测试记录",
             RiskBasis.COMBINED, RiskLevel.HIGH),

            ("novelty", "技术创新与自研突破",
             f"针对核心工程瓶颈提出自研优化策略与自适应调度方案，攻克长序列/慢卡瓶颈",
             "材料创新点自述", EvidenceStatus.MATERIAL_IMPLIED,
             "需界定属于原生算法架构创新还是成熟开源组件的工程化组合调优",
             RiskBasis.COMBINED, RiskLevel.MEDIUM),

            ("personal_contribution", "个人贡献与职责边界",
             f"主导或作为核心研发推进 {proj_name} 的算法设计、系统开发与调试闭环",
             "个人履历自陈", EvidenceStatus.MATERIAL_IMPLIED,
             "未在材料中严格剥离团队协作、开源脚手架与个人独立编写的核心代码行数",
             RiskBasis.RISK_INFERRED, RiskLevel.MEDIUM)
        ]

        for cat, cat_zh, text, src, status, gap, basis, lvl in fallback_definitions:
            if cat not in existing_cats:
                matrix.append(ClaimItem(
                    id=f"CLM-{counter:02d}",
                    category=cat,
                    category_zh=cat_zh,
                    claim_text=text,
                    evidence_source=src,
                    evidence_status=status,
                    gap=gap,
                    risk_basis=basis,
                    risk_level=lvl,
                    extracted_keywords=[]
                ))
                counter += 1

        return matrix

    # -----------------------------------------------------------------------
    # High-Risk Gap Identification
    # -----------------------------------------------------------------------

    def _identify_high_risk_gaps(self, matrix: List[ClaimItem]) -> List[Dict[str, Any]]:
        """Identifies top 3-5 weak spots ranked by risk level and gap severity."""
        # Rank: High risk first, then Medium risk; Material-missing before Material-implied
        def sort_key(item: ClaimItem):
            r_score = 3 if item.risk_level == RiskLevel.HIGH else (2 if item.risk_level == RiskLevel.MEDIUM else 1)
            s_score = 3 if item.evidence_status == EvidenceStatus.MATERIAL_MISSING else (2 if item.evidence_status == EvidenceStatus.MATERIAL_IMPLIED else 1)
            return (r_score, s_score)

        sorted_items = sorted(matrix, key=sort_key, reverse=True)
        gaps: List[Dict[str, Any]] = []

        attack_vectors = {
            "metric": "质疑基线（Baseline）选择的合法性、对照消融实验严谨性、以及极端工况下指标是否断崖式崩塌。",
            "novelty": "质疑自研成分的真实含金量，要求白板默写核心算子并指出与开源主流 PR 的本质差异。",
            "personal_contribution": "要求脱稿划定个人独立代码量与团队/开源借用代码的精确边界，考察现场动手调试排错能力。",
            "architecture": "高压攻击单卡故障、网络分区与显存带宽饥饿等极限异常场景下的容错自愈链路。"
        }

        for item in sorted_items[:5]:
            gaps.append({
                "claim_id": item.id,
                "title": item.claim_text[:35] + ("..." if len(item.claim_text) > 35 else ""),
                "claim_text": item.claim_text,
                "category": item.category,
                "category_zh": item.category_zh,
                "evidence_status": item.evidence_status,
                "evidence_source": item.evidence_source,
                "gap": item.gap,
                "risk_basis": item.risk_basis,
                "risk_level": item.risk_level,
                "attack_vector": attack_vectors.get(item.category, "追问底层实现细节与量化验证依据。")
            })

        return gaps

    # -----------------------------------------------------------------------
    # 3 Interrogation Intensity Levels Questions
    # -----------------------------------------------------------------------

    def _generate_intensity_questions(
        self,
        matrix: List[ClaimItem],
        intensity: str,
        scenario: str
    ) -> List[Dict[str, str]]:
        """
        Generates interrogation questions tailored to the chosen intensity level:
        - 先热个身 (Warm-up): Friendly confirmation of background, problem setup, basic definitions.
        - 开始挑刺 (Critical): Probes data sources, baseline comparison, why this method vs alternatives.
        - 严刑拷打 (Hell-mode Grilling): Sharp attacks on baseline ablation controls, individual vs open-source code,
          extreme edge case failures, and 15-minute clean environment reproducibility.
        """
        questions: List[Dict[str, str]] = []
        roles = SCENARIO_ROLES.get(scenario, SCENARIO_ROLES[DEFAULT_SCENARIO])
        lead_role = roles[0]

        if intensity == IntensityLevel.WARMUP:
            questions = [
                {
                    "role": lead_role,
                    "question": "能否请你先用通俗、凝练的语言，为答辩组介绍一下这个项目的立项初衷、业务背景以及核心要解决的技术痛点？",
                    "intent": "考察候选人对项目全貌的理解广度与技术概括表达能力。"
                },
                {
                    "role": roles[1] if len(roles) > 1 else lead_role,
                    "question": "在项目启动初期，你在技术架构和框架选型上做过哪些初步评估？核心模块的基本概念与拓扑是如何定义的？",
                    "intent": "验证技术方案设计的理性思考过程与核心概念边界。"
                },
                {
                    "role": lead_role,
                    "question": "在这个项目的整体研发周期中，你在团队中主要承担什么样的定位与具体分工？",
                    "intent": "友好建立候选人的职责基线，为后续深入技术细节做铺垫。"
                }
            ]

        elif intensity == IntensityLevel.CRITICAL:
            # Pick representative claims
            metric_claim = next((c for c in matrix if c.category == "metric"), None)
            arch_claim = next((c for c in matrix if c.category == "architecture"), None)
            novelty_claim = next((c for c in matrix if c.category == "novelty"), None)

            m_text = metric_claim.claim_text if metric_claim else "性能提升"
            a_text = arch_claim.claim_text if arch_claim else "架构方案"
            n_text = novelty_claim.claim_text if novelty_claim else "自研创新"

            questions = [
                {
                    "role": lead_role,
                    "question": f"关于你提到的「{m_text[:30]}...」，你们的对照组 Baseline 具体是如何设置的？是在同等算力拓扑与数据分布下严格对齐测试的吗？",
                    "intent": "审查量化收益的真实性与对照实验严密性，防止虚高包装。"
                },
                {
                    "role": roles[1] if len(roles) > 1 else lead_role,
                    "question": f"在「{a_text[:30]}...」这套设计中，为什么不直接采用开源社区成熟的标准方案（例如开源标准调度器或已有算子），而一定要自研此套方案？两者对比量化代价如何？",
                    "intent": "深挖技术选型的 Trade-off，辨别是否存在为了自研而自研的过度设计。"
                },
                {
                    "role": roles[2] if len(roles) > 2 else lead_role,
                    "question": f"你主张的「{n_text[:30]}...」，其核心创新点究竟是算法层面的机理创新，还是工程层面的模块串联与参数微调？与已有顶会/业界工作本质差异在哪？",
                    "intent": "戳破包装泡沫，检验创新性的真实含金量与边界意识。"
                },
                {
                    "role": lead_role,
                    "question": "项目使用的数据集来源是什么？是公开权威基准、真实业务采样还是实验室构造？是否存在测试集数据泄漏或分布偏移问题？",
                    "intent": "审查数据源真实性与结果可信度。"
                }
            ]

        else: # 严刑拷打 (Hell-mode Grilling)
            questions = [
                {
                    "role": lead_role,
                    "question": "【消融实验与变量控制】你说性能指标大幅优化，请拿出脱稿能讲清的消融实验（Ablation Study）数据！如果关掉你自研的优化模块，仅保留框架自带的基础优化，指标会跌掉多少？你如何排除编译器优化或集群网络偶然抖动带来的假象？",
                    "intent": "极限高压测试候选人对对照实验控制变量的掌握程度，无情击穿虚浮指标。"
                },
                {
                    "role": roles[1] if len(roles) > 1 else lead_role,
                    "question": "【自研代码占比 vs 开源胶水】据我所知主流开源库早就合并了类似 PR。请你现场说出你独立编写的核心代码精确行数与目录路径！如果今天把借用的开源底座全部剥离，你亲手写的这部分逻辑还能独立跑起来吗？你到底算架构师还是开源胶水工？",
                    "intent": "直击代码所有权与个人真实技术贡献边界，粉碎模糊夸大。"
                },
                {
                    "role": roles[2] if len(roles) > 2 else lead_role,
                    "question": "【极端灾难与边界崩溃】如果在千卡级/生产级运行中，突然发生两台机器 NVLink 静默掉卡或跨交换机持续丢包，你的系统会出现死锁吗？你的慢节点检测探针会不会误杀正常卡导致整个分布式任务雪崩？你亲手处理过最严重的线上事故是什么？",
                    "intent": "压测极端非理想工况下的工程鲁棒性、故障容灾机制与实际排障经验。"
                },
                {
                    "role": lead_role,
                    "question": "【15分钟全新裸机端到端复现】如果现场给你一台刚装好操作系统的全新裸机 GPU 实例，完全没有你的私有镜像，你能否在 15 分钟内通过 clean script 拉起环境并跑通单测重现你的实验结果？如果现场报 CUDA 符号不匹配，你第一步排查哪一层？",
                    "intent": "现场检验工程可复现性底线，彻底撕开'PPT 架构师'与实战专家的差距。"
                }
            ]

        return questions

    # -----------------------------------------------------------------------
    # 3-Round Progressive Follow-up Chains
    # -----------------------------------------------------------------------

    def _generate_follow_up_chains(
        self,
        high_risk_gaps: List[Dict[str, Any]],
        scenario: str,
        intensity: str
    ) -> List[FollowUpChain]:
        """
        Generates realistic 3-round sequential follow-up interrogation chains
        for the top 3-5 weak spots:
        - Round 1: 摸底探查 - 事实核验与公式推导 (Missing fact, mechanism, baseline)
        - Round 2: 机制深挖 - 剥离依赖与选型替代 (Stripping dependencies, alternative challenge)
        - Round 3: 终局施压 - 极限工况/消融伪证/15分钟复现 (Edge case failure, clean reproduction)
        """
        chains: List[FollowUpChain] = []
        roles = SCENARIO_ROLES.get(scenario, SCENARIO_ROLES[DEFAULT_SCENARIO])
        lead_role = roles[0]

        for idx, gap_info in enumerate(high_risk_gaps[:5], 1):
            chain_id = f"CHAIN-{idx:02d}"
            c_text = gap_info["claim_text"]
            cat = gap_info["category"]
            c_gap = gap_info["gap"]
            risk_lvl = gap_info["risk_level"]
            risk_basis = gap_info["risk_basis"]

            rounds: List[FollowUpRound] = []

            if cat == "metric":
                rounds.append(FollowUpRound(
                    round_index=1,
                    title="第一轮：指标真实性与基线对齐摸底 (Baseline Alignment Probe)",
                    interviewer_role=lead_role,
                    question=f"你在材料中提到「{c_text}」。请问你当时选取的 Baseline 对照组是业界的哪一个具体开源版本？测试集规模多大？在这个基准下你的初始开销是多少？",
                    interviewer_intent="摸清指标基线来源，防止候选人拿优化后的高配环境去打未优化的低配甚至是故意劣化过的基线。",
                    vulnerability_probed="未在材料中披露 Baseline 硬件拓扑、超参数配置与测试基准版本。"
                ))
                rounds.append(FollowUpRound(
                    round_index=2,
                    title="第二轮：严密消融与变量剥离测试 (Ablation & Independence Challenge)",
                    interviewer_role=roles[1] if len(roles) > 1 else lead_role,
                    question="在消融实验中，你有没有做过严格的单变量对照？如果把通用的算子融合和硬件被动增益剥离掉，仅由你提出的算法逻辑带来的净提升到底有多少？是否有方差与置信区间？",
                    interviewer_intent="考察指标提升是否混杂了框架原生优化、硬件红利或运气成分，验证模块的独立贡献价值。",
                    vulnerability_probed="缺少单变量控制实验，收益归因可能存在偷换概念。"
                ))
                rounds.append(FollowUpRound(
                    round_index=3,
                    title="第三轮：极限工况衰退与端到端复现验证 (Worst-case & Live Reproducibility)",
                    interviewer_role=lead_role,
                    question="如果在极端长序列或分布外（OOD）脏数据冲击下，这个指标会不会发生断崖式暴跌？如果现场要求你在干净环境拉起脚本复现这一曲线，你能在 15 分钟内交付可信结果吗？",
                    interviewer_intent="施压极限长尾工况下的工程健壮性与现场可复现度，检验是否只挑选了最好的一次运行汇报。",
                    vulnerability_probed="缺乏失败案例分析、极端压力测试与一键可复现脚本。"
                ))
                strat = {
                    "pivot_focus": "承认基线选取的特定业务上下文，亮出可复现日志与实际硬件配置，主动界定该指标在特定工况下的适用边界。",
                    "recommended_response": "正面回答指标产生于特定硬件拓扑与序列长度区间；坦诚在更通用的未知分布下增益会有所收敛；说明当前数据经过 3 次独立复跑均值校验，并已归档消融配置文件可供复查。"
                }

            elif cat == "novelty":
                rounds.append(FollowUpRound(
                    round_index=1,
                    title="第一轮：创新机理与差异化核验 (Mechanism & Novelty Differentiation)",
                    interviewer_role=lead_role,
                    question=f"你声称在项目中实现了「{c_text}」的核心创新。请具体解释其底层数学/系统调度原理是什么？它与业界主流工作（如社区开源方案）的根本差异在哪两行关键代码？",
                    interviewer_intent="核查创新是否停留在名字包装，要求讲清本质机理与微观差异。",
                    vulnerability_probed="缺少与同类竞品的微架构机理对比与量化代差说明。"
                ))
                rounds.append(FollowUpRound(
                    round_index=2,
                    title="第二轮：剥离开源依赖与选型质疑 (Open-source Dependency Challenge)",
                    interviewer_role=roles[1] if len(roles) > 1 else lead_role,
                    question="这套所谓的创新方案，在开源框架里是否已有类似的实验性分支或社区 PR？你在实现时借用了开源项目多少现成代码？如果直接用标准库，性能会差多少？",
                    interviewer_intent="检验是否属于开源代码缝合怪，迫使候选人承认开源借鉴成分。",
                    vulnerability_probed="个人原生自研与开源社区复用边界模糊。"
                ))
                rounds.append(FollowUpRound(
                    round_index=3,
                    title="第三轮：白板推导与极限失败场景剖析 (Whiteboard & Failure Mode Deep-dive)",
                    interviewer_role=lead_role,
                    question="请你在白板上画出该模块在显存/通信冲突时的仲裁时序！此外，请指出这项创新在什么极限条件下会彻底失效，甚至反而导致性能劣化？你如何防范？",
                    interviewer_intent="检验候选人是否真正吃透技术底层，深挖创新背后的代价（Trade-off）与失败模式。",
                    vulnerability_probed="缺乏失败模式（Failure Modes）与系统退化保护策略。"
                ))
                strat = {
                    "pivot_focus": "不贪图'原生学术理论第一人'虚名，将创新定位在'特定生产环境下的工程架构与关键算子落地定制'，强调解决实际瓶颈的工程价值。",
                    "recommended_response": "坦率说明算法骨架借鉴了业界最佳实践，核心贡献在于针对本业务的自研定制内核与冲突仲裁；明确指出在序列过短时存在启动开销，因而设计了自动旁路降级开关。"
                }

            elif cat == "personal_contribution":
                rounds.append(FollowUpRound(
                    round_index=1,
                    title="第一轮：职责范围与团队分工摸底 (Role & Team Boundary Probe)",
                    interviewer_role=lead_role,
                    question=f"关于「{c_text}」，整个团队在这个项目上投入了多少人力？你个人在其中独立负责的具体模块是哪几部分？核心算法是你设计的还是导师/上级制定的？",
                    interviewer_intent="核实个人在团队大项目中的真实贡献权重，剔除挂名或边缘协助成分。",
                    vulnerability_probed="未在材料中剥离团队集体成果与个人独立产出。"
                ))
                rounds.append(FollowUpRound(
                    round_index=2,
                    title="第二轮：独立代码量与动手能力质疑 (Code Ownership & Hands-on Depth)",
                    interviewer_role=roles[1] if len(roles) > 1 else lead_role,
                    question="如果在现场关闭网络搜索并断开 AI 编程插件，要求你现场手写该模块的核心单元测试与调度循环，你能否在 20 分钟内写出 Bug-free 的实现？你的核心代码量占整个系统的多少？",
                    interviewer_intent="高压测试候选人的真实编码与排错功底，识破依赖 AI 或借用他人代码的包装。",
                    vulnerability_probed="缺少可审计的代码仓库提交记录与独立编写凭据。"
                ))
                rounds.append(FollowUpRound(
                    round_index=3,
                    title="第三轮：重大事故复盘与危机攻坚验证 (Production Incident & Crisis Ownership)",
                    interviewer_role=lead_role,
                    question="既然由你主导并深度负责，请复盘一次你亲手定位并解决的最严重的生产事故或底层死锁 Bug。当时从告警出现到定位到根因耗时多久？排查的系统调用与工具链是什么？",
                    interviewer_intent="通过最真实的灾难现场排查细节，验证候选人是否真正在一线打过硬仗。",
                    vulnerability_probed="缺乏真实排障与生产事故复盘细节证据。"
                ))
                strat = {
                    "pivot_focus": "严格遵守诚信边界，诚恳区分团队分工与个人独立攻坚部分；用极为具体的事故排障经历展现不可替代的工程实战力。",
                    "recommended_response": "明确指出系统整体由团队协同完成，自己专注攻关核心算法模块与通信瓶颈排障；详述定位一次真实死锁的抓包与时序排查全流程，证明一线工程深度。"
                }

            else: # Architecture
                rounds.append(FollowUpRound(
                    round_index=1,
                    title="第一轮：架构选型依据与拓扑推导 (Topology & Selection Rationale)",
                    interviewer_role=lead_role,
                    question=f"针对「{c_text}」，请给出该架构的端到端数据流向与调度拓扑。为什么不采用行业内更为通用的现成架构？你的选型推导依据是什么？",
                    interviewer_intent="审查架构设计的技术决策理性，防止照搬教程或生搬硬套。",
                    vulnerability_probed="缺少端到端时序拓扑与严肃选型对比依据。"
                ))
                rounds.append(FollowUpRound(
                    round_index=2,
                    title="第二轮：单点瓶颈与通信开销深挖 (Bottlenecks & Communication Overhead)",
                    interviewer_role=roles[1] if len(roles) > 1 else lead_role,
                    question="在大规模扩展到几十台甚至上百台机器时，你这套架构的中央协调节点或全局通信环会不会成为吞吐瓶颈？通信掩盖比率在不同 batch size 下如何变化？",
                    interviewer_intent="测试架构的横向可扩展性（Scalability）与通信开销瓶颈。",
                    vulnerability_probed="未给出通信开销分析与大规模横向扩展评测数据。"
                ))
                rounds.append(FollowUpRound(
                    round_index=3,
                    title="第三轮：混沌工程与网络分区容灾 (Chaos Engineering & Partition Tolerance)",
                    interviewer_role=lead_role,
                    question="如果系统在满载运行时遭遇网络脑裂（Split-Brain）或下游微服务响应超时，你的架构是如何防止雪崩的？是否做过注入延迟和丢包的混沌测试？",
                    interviewer_intent="考察生产级架构的高可用容灾底线与真实业务韧性。",
                    vulnerability_probed="缺少混沌容灾测试与降级熔断机制说明。"
                ))
                strat = {
                    "pivot_focus": "说明架构在当前业务规模下的性价比平衡，承认超大规模下的潜在瓶颈，并给出清晰的分阶段解耦路线图。",
                    "recommended_response": "阐明当前设计是研发周期与硬件成本约束下的最优解；坦诚在规模翻倍时通信环需升级为层次化拓扑，并已设计了心跳自愈与本地缓存降级方案。"
                }

            chains.append(FollowUpChain(
                chain_id=chain_id,
                target_claim_id=gap_info["claim_id"],
                target_claim=c_text,
                category=cat,
                gap=c_gap,
                risk_basis=risk_basis,
                risk_level=risk_lvl,
                role=lead_role,
                rounds=rounds,
                defensive_strategy=strat
            ))

        return chains

    # -----------------------------------------------------------------------
    # Defensible Answering Strategy & Cheat Sheet
    # -----------------------------------------------------------------------

    def _build_defensible_strategy(
        self,
        matrix: List[ClaimItem],
        high_risk_gaps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Formulates structured defensible answering frameworks and phrasing pairs."""
        golden_steps = [
            {
                "step": "第一步：正面回应，不绕圈子 (Direct Response)",
                "desc": "以客观冷静的态度直接回答评委的核心疑问，严禁顾左右而言他或反问对抗。",
                "example": "老师您指出的 Baseline 对齐与消融严格性非常关键，我先直接回答这个数据的测试前提……"
            },
            {
                "step": "第二步：说明依据，锁定事实 (Grounded Fact)",
                "desc": "阐明当前版本在真实实验中确实验证过的数据、环境参数与复现代码路径。",
                "example": "在当时 1024 卡 H800 的测试环境下，我们记录的端到端 MFU 确由 38.5% 提升至 54.2%，对应日志在仓库 logs 目录下完整归档。"
            },
            {
                "step": "第三步：主动划界，承认局限 (Bounded Limitation)",
                "desc": "主动承认测试工况的特定性、未覆盖的长尾边界或暂未支持的边缘场景，防止被逼入死角。",
                "example": "但必须承认，这一收益目前是在特定的大 batch size 与序列长度下测得的，在极短序列或小集群上，算子启动开销会削弱这一增益。"
            },
            {
                "step": "第四步：合理解释，权衡取舍 (Trade-off & Rationale)",
                "desc": "结合工程资源、研发交付周期或业务 ROI，合理解释为何在当前阶段采取此设计。",
                "example": "项目当时的核心优先级是保障千亿 Token 训练里程碑按时交付，因此优先攻坚了主要瓶颈，暂未做全量硬件平台的广泛泛化测试。"
            },
            {
                "step": "第五步：给出改进，落到实处 (Concrete Next Step)",
                "desc": "给出具体可行的技术演进动作，说明先改哪一步、如何闭环验证，化被动防守为主动进取。",
                "example": "针对您提到的极端网络抖动容错，我们在下一期迭代中已规划引入层次化心跳与轻量级重算机制，预计可在下个月完成压测。"
            }
        ]

        safe_framing_pairs = [
            {
                "bad": "这套框架完全由我从零到一独立全量研发",
                "good": "我独立主导了该框架的核心算法架构设计与关键融合算子编写，底层通信与编译环境复用了成熟开源基座",
                "risk": "被质疑代码所有权占比与现场默写难度"
            },
            {
                "bad": "我们的模型和算法效果全面领先业界所有 SOTA",
                "good": "在本次重点评测的公开基准与特定业务工况下，相对基线取得了预期的显著收敛与提效",
                "risk": "被要求给出严密数学证明与全方位竞品消融"
            },
            {
                "bad": "系统做到了秒级自愈与绝对零故障高可用",
                "good": "在单卡故障与慢节点抖动等已知高频场景下实现了自动剔除隔离，在更复杂的网络分区下正持续完善容错策略",
                "risk": "招致网络脑裂与静默掉卡等混沌故障高压拷问"
            },
            {
                "bad": "数据全部来自真实生产环境实测",
                "good": "当前评测数据由典型生产工况脱敏采样与标准公开基准构成，具备较好的方案论证与趋势验证价值",
                "risk": "数据权限、合规性与标注一致性审计"
            }
        ]

        return {
            "golden_steps": golden_steps,
            "safe_framing_pairs": safe_framing_pairs
        }

    def _build_material_repairs(self, high_risk_gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generates concrete location-specific material repair items."""
        repairs: List[Dict[str, Any]] = [
            {
                "location": "README.md / 代码仓库根目录",
                "action": "补充 15 分钟极简复现单测脚本与 requirements 锁版本文件",
                "priority": "P0 (最高)",
                "effort": "30分钟",
                "target_gap": "可复现性与干净环境运行验证",
                "detail": "新增 `scripts/reproduce_eval.sh`，包含单卡/模拟小规模端到端测试入口，固化 PyTorch/CUDA/NCCL 精确版本号。"
            },
            {
                "location": "PPT / 答辩汇报材料 第 8-10 页",
                "action": "增加 Baseline 对照组配置表格与消融实验（Ablation）控制变量柱状图",
                "priority": "P0 (最高)",
                "effort": "45分钟",
                "target_gap": "指标真实性与消融严密性",
                "detail": "明确标注 Baseline 的硬件型号、网络拓扑、batch size 与具体参数，展示移除核心自研模块后的性能回退曲线。"
            },
            {
                "location": "简历 / 个人项目陈述段落",
                "action": "精确修正个人贡献动词，剥离团队与开源依赖界限",
                "priority": "P1 (重要)",
                "effort": "20分钟",
                "target_gap": "个人贡献夸大与代码所有权",
                "detail": "将'全量主导自研'修正为'主导核心算子与调度链路落地'，并在附录中注明自研代码目录与所基于的开源基座分支。"
            },
            {
                "location": "技术报告 / 论文附录",
                "action": "补充已知局限性（Limitations）与失败模式（Failure Cases）分析章节",
                "priority": "P1 (重要)",
                "effort": "1小时",
                "target_gap": "边界意识与工程鲁棒性",
                "detail": "主动列出在短序列或高丢包率等非理想工况下的性能退化表现，展现专业严谨的学术/工程诚信。"
            }
        ]
        return repairs

    def _build_cheat_sheet(
        self,
        proj_name: str,
        positioning: str,
        high_risk_gaps: List[Dict[str, Any]],
        matrix: List[ClaimItem]
    ) -> DefenseCheatSheet:
        """Constructs the high-density defense cheat sheet (答辩速查卡)."""
        # Card 1: Elevator pitch
        elevator_pitch = f"{proj_name}：{positioning}\n核心杀手锏：在真实工程约束下打通关键瓶颈链路，兼顾高吞吐与高可用稳定性。"

        # Card 2: Top vulnerabilities & bottom line
        top_vulnerabilities: List[Dict[str, str]] = []
        for gap in high_risk_gaps[:3]:
            top_vulnerabilities.append({
                "vulnerability": f"[{gap.get('category_zh', '')}] {gap.get('title', '')}",
                "bottom_line": f"守住真实工况底线：承认当前测试是在特定硬件拓扑下展开，不夸大为全场景无条件最优。"
            })
        if not top_vulnerabilities:
            top_vulnerabilities.append({
                "vulnerability": "消融实验与基线对齐严密性",
                "bottom_line": "亮出明确 Baseline 参数与测试脚本，强调工程增益的真实可信度。"
            })

        # Card 3: Metric audit sheet
        metric_audit: List[Dict[str, str]] = []
        metric_items = [m for m in matrix if m.category == "metric"]
        for m in metric_items[:3]:
            metric_audit.append({
                "metric": m.claim_text[:30],
                "baseline": "同等集群规模开源标准实现（如标准 Megatron/vLLM）",
                "source": m.evidence_source
            })
        if not metric_audit:
            metric_audit.append({
                "metric": "端到端 MFU / 延迟降低比率",
                "baseline": "未优化前原生实现或开源 Baseline",
                "source": "本地训练日志与监控抓包归档"
            })

        # Card 4: Contribution boundaries
        contribution_boundaries: List[Dict[str, str]] = [
            {
                "module": "核心算法与调度逻辑",
                "personal": "独立负责设计、关键算子实现与端到端调优",
                "external": "基于开源社区成熟基座与分布式通信库"
            },
            {
                "module": "集群基础设施与辅助运维",
                "personal": "提出心跳探针需求并协同联调",
                "external": "团队基础架构组与系统工程师共同支撑"
            }
        ]

        # Card 5: 15-minute reproducibility
        reproducibility = {
            "command": "bash scripts/reproduce_eval.sh --quick-test",
            "test_target": "pytest tests/test_core_engine.py -k 'test_throughput'",
            "fallback_pivot": "若现场因网络限制无法拉取外部镜像，从容展示预先打包好的离线 Docker 镜像与本地 Profiler 追踪日志（Trace JSON）。"
        }

        return DefenseCheatSheet(
            elevator_pitch=elevator_pitch,
            top_vulnerabilities=top_vulnerabilities,
            metric_audit_sheet=metric_audit,
            contribution_boundaries=contribution_boundaries,
            fifteen_minute_reproducibility=reproducibility
        )


# ---------------------------------------------------------------------------
# Top-Level Convenience Function
# ---------------------------------------------------------------------------

def simulate_project_defense(
    project_input: Union[str, List[Any], Dict[str, Any]],
    profile_context: Optional[Union[dict, str, Path]] = None,
    intensity: str = IntensityLevel.CRITICAL,
    scenario: str = DEFAULT_SCENARIO,
    output_format: str = "dict"
) -> Union[Dict[str, Any], str]:
    """
    Top-level convenience function for project defense interrogation and red-team simulation.

    Args:
        project_input: Project description text, claim list, or candidate profile project dict.
        profile_context: Optional SSOT candidate profile (dict or path to candidate_profile.json).
        intensity: "先热个身" (Warm-up), "开始挑刺" (Critical, default), or "严刑拷打" (Hell-mode Grilling).
        scenario: Defense scenario, e.g. "技术 / 简历面试", "保研 / 复试", "课程答辩 / 毕设", "竞赛答辩", "GitHub 项目审查".
        output_format: "dict" (default) for structured dictionary, or "markdown" / "md" for full 7-section report.

    Returns:
        Structured dictionary or formatted Markdown string.
    """
    simulator = DefenseSimulator(profile_context=profile_context)
    result = simulator.simulate(
        project_input=project_input,
        intensity=intensity,
        scenario=scenario
    )

    if output_format.lower() in ("markdown", "md", "text"):
        return result.to_markdown()
    return result.to_dict()


ProjectInterrogationChain = FollowUpChain

__all__ = [
    "ARCHITECTURE_KEYWORDS",
    "CONTRIBUTION_KEYWORDS",
    "ClaimItem",
    "DEFAULT_SCENARIO",
    "DefenseCheatSheet",
    "DefenseSimulationResult",
    "DefenseSimulator",
    "EvidenceStatus",
    "FollowUpChain",
    "FollowUpRound",
    "INTENSITY_ALIASES",
    "IntensityLevel",
    "METRIC_PATTERNS",
    "NOVELTY_KEYWORDS",
    "OVERCLAIM_PATTERNS",
    "PROHIBITED_TO_SAFE_REPLACEMENTS",
    "ProjectInterrogationChain",
    "RiskBasis",
    "RiskLevel",
    "SCENARIO_ROLES",
    "simulate_project_defense",
]
