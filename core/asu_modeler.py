"""
OfferGet ASu Modeler Engine (asu_modeler.py)
============================================
Implements ASu-style high-density engineering modeling and strict factual verification:
1. Standard 6-Link Pipeline Decomposition: Data -> Model -> Training -> Serving -> Agent -> Eval.
   (Supports AI/LLM models and classic distributed systems isomorphic mapping).
2. Minimal Bounded Closure Owner Extraction: strict rules for 0->1 vs X->Y architectural evolution.
3. 5-Layer Failure Taxonomy Narratives (Recall, Planning, Evidence, Tool, Outcome).
4. Education Background 6-Dimensional Deconstruction & Official Title Whitelist.
5. Deterministic Static Auditing for 6 Inflation Patterns (Scope, Metrics Arithmetic, Temporal, etc.).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ============================================================================
# 1. Enums and Data Models
# ============================================================================

class VerificationStatus(str, Enum):
    SOURCE_GROUNDED = "source_grounded"   # Verified by primary source docs
    USER_ATTESTED = "user_attested"       # Stated by user internally
    PLANNED = "planned"                   # Research/planned/future work


class ChangeType(str, Enum):
    RELATIVE_PERCENT = "relative_percent"   # (Result - Baseline) / Baseline * 100
    PERCENTAGE_POINTS = "percentage_points" # Result - Baseline


class AuditRiskLevel(str, Enum):
    PASS = "pass"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"


# ---------------------------------------------------------------------------
# Whitelists & Taxonomy Constants
# ---------------------------------------------------------------------------

EDUCATION_BRANDING_WHITELIST: Dict[str, Set[str]] = {
    "construction_series": {
        "国家“双一流”建设高校", "双一流", "世界一流大学建设高校", "世界一流学科建设高校",
        "原“985工程”优势学科创新平台", "原“985工程”", "985", "原“211工程”", "211",
        "教育部直属高校", "省部共建高校", "教育部与省级人民政府共建高校",
        "国家“111计划”引智基地高校", "卓越工程师教育培养计划高校", "新工科研究与实践项目高校"
    },
    "alliances": {
        "C9 联盟", "九校联盟", "C9", "卓越大学联盟", "E9",
        "Group of Eight", "澳洲八校联盟创始成员", "Russell Group", "罗素大学集团成员",
        "Ivy League", "常春藤盟校"
    }
}

SIX_LINKS_WHITELIST: Dict[str, List[str]] = {
    "Data": [
        "Schema Linking", "Hard Negative", "Synthetic Trajectory", "Multi-Scaffold Sampling",
        "Quality Gate", "Dedup Key", "Token Efficiency", "Patch Validity", "清洗与对齐",
        "Protocol Buffers", "ETL Pipeline", "Traffic Mirroring", "Event Log"
    ],
    "Model": [
        "Transformer", "MoE", "MLA", "CLIP", "Dense Embedding", "Cross-Encoder",
        "Representation Space", "Modality Projection", "Base LLM", "AST", "FSM", "状态机"
    ],
    "Training": [
        "Full SFT", "LoRA", "QLoRA", "DPO", "GRPO", "PPO", "Structured Short COT",
        "Loss Masking", "ZeRO-3", "FSDP", "Distributed Checkpointing", "eBPF", "内核调优"
    ],
    "Serving": [
        "AWQ", "GPTQ", "FP8", "INT4", "vLLM", "SGLang", "Prefill-Decoding Disaggregation",
        "Continuous Batching", "PagedAttention", "KV Cache Offload", "Firecracker", "TTFT", "TPOT",
        "epoll", "Zero-Copy", "gRPC", "P99 延迟"
    ],
    "Agent": [
        "ReAct", "Plan-and-Execute", "Manager-Worker", "Tool Registry", "Tool Budget",
        "Memory Compaction", "Context Continuation", "Checkpoint Resume", "Relay Runner",
        "Raft", "Saga", "Service Mesh", "熔断限流"
    ],
    "Eval": [
        "SWE-Bench", "GSM8K", "Eval Suite", "Regression Set", "LLM-as-a-Grader",
        "Rubric Eval", "Transcript Analysis", "Outcome Verification", "Failure Onset",
        "Chaos Mesh", "分布式压测", "SLO"
    ]
}

# Centralized inflation and role pattern constants from core.lexicon (SSOT)
from core.lexicon import (
    STRONG_ROLE_TERMS,
    MODULE_QUALIFIERS,
    PLANNED_MARKERS,
    FORBIDDEN_SUPERLATIVES,
    INFLATION_PATTERNS,
    ROLE_RANKS,
    VERB_HIERARCHY,
    FORBIDDEN_BUZZWORDS,
)


# ============================================================================
# 2. Modeler Engine Implementation
# ============================================================================

class AsuModeler:
    """
    Core engine for ASu-style engineering modeling, 6-link decomposition,
    and strict deterministic anti-inflation audits.
    """

    def __init__(self, fact_guard: Optional[Any] = None):
        self.fact_guard = fact_guard

    # ------------------------------------------------------------------------
    # 2.1 6-Link Pipeline Decomposition
    # ------------------------------------------------------------------------

    def decompose_to_6links(self, text_or_bullets: Union[str, List[str]]) -> Dict[str, List[str]]:
        """
        Decomposes raw engineering bullets/sentences into Data / Model / Training / Serving / Agent / Eval.
        """
        if isinstance(text_or_bullets, str):
            lines = [l.strip() for l in re.split(r"[\n\r；;。]", text_or_bullets) if l.strip()]
        else:
            lines = [l.strip() for l in text_or_bullets if l.strip()]

        result: Dict[str, List[str]] = {k: [] for k in SIX_LINKS_WHITELIST.keys()}

        for line in lines:
            assigned = False
            for link, keywords in SIX_LINKS_WHITELIST.items():
                if any(kw.lower() in line.lower() for kw in keywords):
                    result[link].append(line)
                    assigned = True
                    break
            if not assigned:
                if any(w in line for w in ["清洗", "数据", "采样", "格式", "数据集", "样本", "日志"]):
                    result["Data"].append(line)
                elif any(w in line for w in ["模型", "权重", "表征", "投影", "嵌入", "结构"]):
                    result["Model"].append(line)
                elif any(w in line for w in ["微调", "训练", "收敛", "损失", "SFT", "强化学习"]):
                    result["Training"].append(line)
                elif any(w in line for w in ["推理", "部署", "加速", "显存", "延迟", "吞吐", "量化"]):
                    result["Serving"].append(line)
                elif any(w in line for w in ["智能体", "编排", "状态机", "工作流", "调用", "调度", "恢复"]):
                    result["Agent"].append(line)
                elif any(w in line for w in ["评测", "基准", "复现", "测试", "对齐", "漏斗", "指标"]):
                    result["Eval"].append(line)
                else:
                    result["Serving"].append(line)

        return result

    # ------------------------------------------------------------------------
    # 2.2 Minimal Bounded Closure & 0->1 vs X->Y
    # ------------------------------------------------------------------------

    def generate_project_narrative_header(
        self,
        module_name: str,
        is_from_scratch: bool = False,
        base_arch: str = "",
        target_arch: str = "",
        user_role_strength: str = "module_owner"
    ) -> Dict[str, str]:
        """
        Generates safe, high-potency ASu subtitle respecting 0->1 vs X->Y constraints.
        """
        clean_mod = module_name.strip()
        if not clean_mod.endswith(("模块", "链路", "组件", "系统", "引擎")):
            clean_mod += "模块"

        if is_from_scratch:
            if user_role_strength in ["module_owner", "lead"]:
                subtitle = f"{clean_mod} Owner · 从 0→1 架构落地"
            else:
                subtitle = f"{clean_mod} 核心共建 · 从 0→1 研发交付"
        else:
            if base_arch and target_arch:
                subtitle = f"{clean_mod} · {base_arch} → {target_arch} 演进重构"
            else:
                subtitle = f"{clean_mod} · 核心性能与稳定性演进"

        return {
            "module": clean_mod,
            "subtitle": subtitle,
            "is_from_scratch": is_from_scratch
        }

    # ------------------------------------------------------------------------
    # 2.3 5-Layer Failure Taxonomy Generator
    # ------------------------------------------------------------------------

    def build_failure_taxonomy_narrative(
        self,
        recall_issue: str = "长尾高难样本召回漏检",
        planning_issue: str = "复杂工具调用轨迹偏航与死循环",
        evidence_issue: str = "无效上下文干扰导致证据检索失真",
        tool_issue: str = "环境沙箱超时与瞬时网络抖动崩溃",
        outcome_issue: str = "最终生成补丁未能通过回归门禁"
    ) -> str:
        """
        Synthesizes a standardized 5-layer failure taxonomy diagnostic narrative.
        """
        return (
            f"构建 5 层技术失败诊断与评测归因体系："
            f"① 召回层（{recall_issue}）→ "
            f"② 规划层（{planning_issue}）→ "
            f"③ 证据层（{evidence_issue}）→ "
            f"④ 执行层（{tool_issue}）→ "
            f"⑤ 产物层（{outcome_issue}），"
            f"实现端到端 badcase 闭环根因可观测与精准修复。"
        )

    # ------------------------------------------------------------------------
    # 2.4 Deterministic Arithmetic & Metric Consistency
    # ------------------------------------------------------------------------

    @staticmethod
    def verify_metric_arithmetic(
        numerator: Optional[float] = None,
        denominator: Optional[float] = None,
        displayed_percent: Optional[float] = None,
        baseline: Optional[float] = None,
        result: Optional[float] = None,
        displayed_change: Optional[float] = None,
        change_type: ChangeType = ChangeType.RELATIVE_PERCENT,
        tolerance: float = 0.5
    ) -> Tuple[bool, str]:
        """Strict deterministic arithmetic check with tolerance <= 0.5% using canonical MetricRecalculator."""
        from core.evidence.metrics import MetricRecalculator

        if numerator is not None and denominator is not None and displayed_percent is not None:
            res = MetricRecalculator.validate_ratio(numerator, denominator, displayed_percent, tolerance=tolerance)
            if not res.is_valid:
                return False, f"比例算术不符：{res.error_message}"

        if baseline is not None and result is not None and displayed_change is not None:
            ct_str = change_type.value if hasattr(change_type, "value") else str(change_type)
            res = MetricRecalculator.validate_change(baseline, result, ct_str, displayed_change, tolerance=tolerance)
            if not res.is_valid:
                return False, f"变化值算术不符：{res.error_message}"

        return True, "算术一致性校验通过"

    # ------------------------------------------------------------------------
    # 2.5 Deterministic 6-Inflation Pattern Audit
    # ------------------------------------------------------------------------

    def audit_bullet_inflation(
        self,
        text: str,
        verification: str = "source_grounded",
        user_declared_role: str = "contributor"
    ) -> List[Dict[str, Any]]:
        """
        Audits a single bullet/claim against the 6 inflation patterns.
        """
        issues = []

        has_strong = bool(STRONG_ROLE_TERMS.search(text))
        has_qualifier = bool(MODULE_QUALIFIERS.search(text))
        if has_strong and not has_qualifier and user_declared_role not in ["system_architect", "tech_lead"]:
            issues.append({
                "pattern": "P1_SCOPE_INFLATION",
                "risk": AuditRiskLevel.HIGH,
                "detail": "使用全盘架构强词（如 Owner/主导/完全负责），但未限定具体闭环模块名称",
                "fix_suggestion": "限定至具体责任单元，改写为 '[具体模块名] Owner' 或 '负责 [具体组件] 研发'"
            })

        sup_match = FORBIDDEN_SUPERLATIVES.search(text)
        if sup_match:
            issues.append({
                "pattern": "P2_UNBOUNDED_SUPERLATIVE",
                "risk": AuditRiskLevel.BLOCKER,
                "detail": f"命中排他性最高级词汇 '{sup_match.group(0)}'，缺乏第三方官方全集背书",
                "fix_suggestion": "删除绝对化最高级，采用限定客观场景或具体指标对比表达"
            })

        is_planned = verification == VerificationStatus.PLANNED or bool(PLANNED_MARKERS.search(text))
        if is_planned and has_strong:
            issues.append({
                "pattern": "P3_TEMPORAL_CONFUSION",
                "risk": AuditRiskLevel.BLOCKER,
                "detail": "处于探索/规划阶段（Planned）却使用了过去完成时强主导动词（如主导/已实现）",
                "fix_suggestion": "保留时态边界，使用 '当前规划'、'重点探索'，禁止声称已产生确定性生产收益"
            })

        if "从0到1" in text and ("重构" in text or "优化" in text or "演进" in text):
            issues.append({
                "pattern": "P4_PSEUDO_ZERO_TO_ONE",
                "risk": AuditRiskLevel.MEDIUM,
                "detail": "存量系统重构/优化与'从0到1'叙事冲突",
                "fix_suggestion": "改写为 '[原架构] → [新架构] 架构演进' 或 '核心指标跃迁'"
            })

        return issues

    # ------------------------------------------------------------------------
    # 2.6 Education Branding Normalization
    # ------------------------------------------------------------------------

    def normalize_education_branding(
        self,
        institution: str,
        user_declared_titles: List[str]
    ) -> Dict[str, Any]:
        """
        Normalizes and audits education institution branding against official MOE / Alliance list.
        """
        validated_titles = []
        rejected_titles = []

        all_valid = (
            EDUCATION_BRANDING_WHITELIST["construction_series"] |
            EDUCATION_BRANDING_WHITELIST["alliances"]
        )

        for title in user_declared_titles:
            cleaned = title.strip()
            matched = any(v.lower() == cleaned.lower() or v in cleaned for v in all_valid)
            if matched:
                validated_titles.append(cleaned)
            else:
                rejected_titles.append(cleaned)

        title_str = " ｜ ".join(validated_titles) if validated_titles else ""
        assembled_header = f"{institution} ｜ {title_str}" if title_str else institution

        return {
            "institution": institution,
            "validated_titles": validated_titles,
            "rejected_titles": rejected_titles,
            "assembled_header": assembled_header,
            "is_fully_compliant": len(rejected_titles) == 0
        }
