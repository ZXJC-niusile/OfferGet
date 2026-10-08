"""Source-grounded resume comparison and audit reporting.

Records exact input values, detected guard findings, and supplied layout metadata.
The ledger does not apply corrections or independently verify rendered output.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Categories and Severities
# ---------------------------------------------------------------------------

class DiffCategory(str, Enum):
    """Classification of changes and verifications in the Diff Ledger."""
    ROLE_HIERARCHY = "ROLE_HIERARCHY"            # 职务与头衔对齐
    METRIC_SCOPE = "METRIC_SCOPE"                # 数据统计口径
    CREDENTIAL_FIDELITY = "CREDENTIAL_FIDELITY"  # 证书与课程保真
    LAYOUT_ACTION = "LAYOUT_ACTION"              # 排版自适应微调动作
    GENERAL_FACT = "GENERAL_FACT"                # 通用事实核验状态


class DiffSeverity(str, Enum):
    """Significance / compliance level of a recorded diff entry."""
    INFO = "INFO"                                # 常规说明/排版动作
    ALIGNED = "ALIGNED"                          # 完美对齐基线/核验合规
    CAUTION = "CAUTION"                          # 需候选人留意的微调/边界差异
    INFLATION_PREVENTED = "INFLATION_PREVENTED"  # 成功拦截AI虚假拔高/范围漂移/无凭换算


DIFF_CATEGORY_META: Dict[DiffCategory, Dict[str, str]] = {
    DiffCategory.ROLE_HIERARCHY: {
        "title_zh": "职务与头衔层级对齐",
        "title_en": "Role Hierarchy Alignment",
        "icon": "🎖️",
        "description": "严格核查原职务与改写英文职务对应关系，杜绝越级提拔与领域漂移。",
        "alert_type": "IMPORTANT",
        "alert_text": "职务头衔严禁跨级跳跃。实习生、普通成员不得拔高为 Specialist / Lead / Manager；志愿服务与班级职务严禁脱离本职泛化为全权管理职责。",
    },
    DiffCategory.METRIC_SCOPE: {
        "title_zh": "数据统计口径与边界核验",
        "title_en": "Metric Scope & Fidelity",
        "icon": "📊",
        "description": "严格校准量化统计口径，杜绝场次偷换、受众升维、峰值篡改及无凭换算。",
        "alert_type": "IMPORTANT",
        "alert_text": "数据严禁发生维度偷换：场次不得偷换为物料件数；个人潜在用户不得漂移为企业客户；单篇最高阅读量不得虚构成累计总量；人民币不得随意增添未经锚定的美元换算；未官方认证的 GPA 严禁脑补满分分母。",
    },
    DiffCategory.CREDENTIAL_FIDELITY: {
        "title_zh": "证书与课程保真性",
        "title_en": "Credential & Coursework Fidelity",
        "icon": "📜",
        "description": "保证官方考试科目名称全称与核心专业课国际规范术语完整留存。",
        "alert_type": "NOTE",
        "alert_text": "官方考试科目与专业课学术术语具有强严肃性，严禁为单行排版强行破坏科目术语完整性（如完整保留 NCRE Level 2 — WPS Office 及工科核心课规范全称）。",
    },
    DiffCategory.LAYOUT_ACTION: {
        "title_zh": "排版自适应微调动作",
        "title_en": "Adaptive Layout Micro-adjustments",
        "icon": "📐",
        "description": "记录单页自适应微调引擎的调优轨迹（字号底线、孤字消除、弹性间距）。",
        "alert_type": "TIP",
        "alert_text": "排版参数与求解器报告不等于最终渲染测量；未提供测量时，字号、孤行和分页状态均不能据此认定通过。",
    },
    DiffCategory.GENERAL_FACT: {
        "title_zh": "通用事实核验状态",
        "title_en": "General Fact Verification",
        "icon": "🔍",
        "description": "针对经历陈述、技术栈与数值锚点的综合事实核验明细。",
        "alert_type": "NOTE",
        "alert_text": "字段相同仅表示来源一致；检测结果和建议不代表已修复，也不替代人工核实事实。",
    },
}

DIFF_SEVERITY_BADGES: Dict[DiffSeverity, str] = {
    DiffSeverity.INFLATION_PREVENTED: "🛡️ 拦截虚高",
    DiffSeverity.ALIGNED: "✅ 基线对齐",
    DiffSeverity.CAUTION: "⚠️ 提示留意",
    DiffSeverity.INFO: "ℹ️ 信息记录",
}


# ---------------------------------------------------------------------------
# DiffEntry Data Class
# ---------------------------------------------------------------------------

@dataclass
class DiffEntry:
    """Represents a single traceable change or verification event."""
    category: DiffCategory
    field: str
    baseline_zh: str
    tailored_en: str
    severity: DiffSeverity
    explanation: str
    action_taken: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.category, str):
            self.category = DiffCategory(self.category)
        if isinstance(self.severity, str):
            self.severity = DiffSeverity(self.severity)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry into serializable dictionary."""
        return {
            "category": self.category.value,
            "field": self.field,
            "baseline_zh": self.baseline_zh,
            "tailored_en": self.tailored_en,
            "severity": self.severity.value,
            "explanation": self.explanation,
            "action_taken": self.action_taken,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DiffEntry:
        """Instantiate entry from serialized dictionary."""
        return cls(
            category=DiffCategory(data["category"]),
            field=data.get("field", ""),
            baseline_zh=data.get("baseline_zh", ""),
            tailored_en=data.get("tailored_en", ""),
            severity=DiffSeverity(data.get("severity", "ALIGNED")),
            explanation=data.get("explanation", ""),
            action_taken=data.get("action_taken", ""),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# DiffLedger Class
# ---------------------------------------------------------------------------

class DiffLedger:
    """
    Diff Ledger & Change Traceability Ledger for Resume Rewriting.
    Reports input differences and supplied audit findings without changing input.
    Source equality, detection, and reported actions remain distinct.
    """

    def __init__(
        self,
        candidate_name: str = "",
        title: str = "改动溯源与口径对齐报告 (Diff Ledger)",
        created_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.candidate_name = candidate_name
        self.title = title
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.metadata = metadata or {}
        self.entries: List[DiffEntry] = []

    def add_entry(
        self,
        entry: Optional[Union[DiffEntry, DiffCategory, str]] = None,
        field: str = "",
        baseline_zh: str = "",
        tailored_en: str = "",
        severity: Union[DiffSeverity, str] = DiffSeverity.ALIGNED,
        explanation: str = "",
        action_taken: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        *,
        category: Optional[Union[DiffCategory, str]] = None,
        **kwargs: Any,
    ) -> DiffEntry:
        """Adds an entry to the ledger, accepting either an entry instance or discrete attributes."""
        if isinstance(entry, DiffEntry):
            diff_entry = entry
        else:
            cat_val = category if category is not None else entry
            if cat_val is None:
                raise ValueError("Either entry (DiffEntry), category, or positional category must be provided.")
            cat = DiffCategory(cat_val) if isinstance(cat_val, str) else cat_val
            sev = DiffSeverity(severity) if isinstance(severity, str) else severity
            f_val = kwargs.get("field", field)
            b_val = kwargs.get("baseline_zh", baseline_zh)
            t_val = kwargs.get("tailored_en", tailored_en)
            exp_val = kwargs.get("explanation", explanation)
            act_val = kwargs.get("action_taken", action_taken)
            meta_val = kwargs.get("metadata", metadata) or {}

            diff_entry = DiffEntry(
                category=cat,
                field=f_val,
                baseline_zh=b_val,
                tailored_en=t_val,
                severity=sev,
                explanation=exp_val,
                action_taken=act_val,
                metadata=meta_val,
            )
        self.entries.append(diff_entry)
        return diff_entry

    def get_entries_by_category(self, category: Union[DiffCategory, str]) -> List[DiffEntry]:
        """Filters entries by their category."""
        cat = DiffCategory(category) if isinstance(category, str) else category
        return [e for e in self.entries if e.category == cat]

    def get_entries_by_severity(self, severity: Union[DiffSeverity, str]) -> List[DiffEntry]:
        """Filters entries by their severity."""
        sev = DiffSeverity(severity) if isinstance(severity, str) else severity
        return [e for e in self.entries if e.severity == sev]

    def count_by_severity(self) -> Dict[str, int]:
        """Returns entry counts grouped by severity."""
        return {
            sev.value: sum(1 for e in self.entries if e.severity == sev)
            for sev in DiffSeverity
        }

    def count_by_category(self) -> Dict[str, int]:
        """Returns entry counts grouped by category."""
        return {
            cat.value: sum(1 for e in self.entries if e.category == cat)
            for cat in DiffCategory
        }

    def to_dict(self) -> Dict[str, Any]:
        """Converts ledger into a structured dictionary."""
        return {
            "title": self.title,
            "candidate_name": self.candidate_name,
            "created_at": self.created_at,
            "summary": {
                "total_entries": len(self.entries),
                "inflations_prevented": sum(1 for e in self.entries if e.severity == DiffSeverity.INFLATION_PREVENTED),
                "issues_detected": sum(e.metadata.get("event_status") == "detected" for e in self.entries),
                "observed_changes": sum(e.metadata.get("event_status") == "observed_change" for e in self.entries),
                "actions_applied": sum(e.metadata.get("event_status") == "applied" for e in self.entries),
                "aligned": sum(1 for e in self.entries if e.severity == DiffSeverity.ALIGNED),
                "caution": sum(1 for e in self.entries if e.severity == DiffSeverity.CAUTION),
                "info": sum(1 for e in self.entries if e.severity == DiffSeverity.INFO),
            },
            "category_counts": self.count_by_category(),
            "metadata": self.metadata,
            "entries": [e.to_dict() for e in self.entries],
        }

    def generate_json(self, indent: int = 2) -> str:
        """Generates a structured JSON string for frontend or CI pipelines."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_fact_guard_result(
        cls,
        guard_result: Optional[Union[Dict[str, Any], Any]] = None,
        baseline_profile: Optional[Union[Dict[str, Any], Any]] = None,
        tailored_data: Optional[Union[Dict[str, Any], str]] = None,
        candidate_name: Optional[str] = None,
        layout_metadata: Optional[Dict[str, Any]] = None,
    ) -> DiffLedger:
        """
        Report source values and detected findings without applying any changes.

        Legacy baseline_zh/tailored_en keys hold the actual input values regardless
        of language. A guard suggestion is not evidence of an applied correction.
        """
        # Resolve candidate name
        c_name = candidate_name or ""
        if not c_name and isinstance(baseline_profile, dict):
            cand_dict = baseline_profile.get("candidate", {})
            if isinstance(cand_dict, dict):
                c_name = cand_dict.get("name") or baseline_profile.get("name") or ""
            elif isinstance(baseline_profile.get("name"), str):
                c_name = baseline_profile["name"]

        meta = {
            "fact_verification": {
                "status": "reported" if isinstance(guard_result, dict) else "unknown",
                "coverage": guard_result.get("coverage", "not_reported") if isinstance(guard_result, dict) else "not_reported",
            }
        }
        if layout_metadata is not None:
            meta["layout_metadata"] = layout_metadata

        ledger = cls(candidate_name=c_name, metadata=meta)

        # 1. Ingest explicit issues from FactGuard audit output if available
        if isinstance(guard_result, dict):
            # 1a. Role inflations detected by guard
            for r in guard_result.get("role_inflations", []):
                claimed = r.get("claimed_role", "")
                base = r.get("baseline_role", "")
                reason = r.get("reason", "职务越级或领域漂移")
                fix = r.get("fix_suggestion", "")
                
                # Canonical field mapping
                base_clean = base.strip().lower()
                if "推广" in base_clean:
                    field_key = "role.promotion"
                elif "志愿" in base_clean:
                    field_key = "role.volunteer"
                elif "心理" in base_clean:
                    field_key = "role.mental_health"
                elif "编辑" in base_clean:
                    field_key = "role.editorial"
                else:
                    field_key = r.get("scope") or f"role.{base_clean}"

                ledger.add_entry(
                    category=DiffCategory.ROLE_HIERARCHY,
                    field=field_key,
                    baseline_zh=base,
                    tailored_en=claimed,
                    severity=DiffSeverity.CAUTION,
                    explanation=reason,
                    action_taken=f"检测到风险，未应用修正。建议: {fix}" if fix else "检测到风险，未应用修正。",
                    metadata={**r, "event_status": "detected"},
                )

            # 1b. Drifts detected by guard (metric scope & numerical inflations)
            for d in guard_result.get("drifts", []):
                rule_id = d.get("rule_id", "")
                if rule_id == "SCOPE_EVENT_TO_ASSET":
                    cat = DiffCategory.METRIC_SCOPE
                    field_key = "metric.livestream_sessions"
                elif rule_id == "SCOPE_USER_TO_ENTERPRISE":
                    cat = DiffCategory.METRIC_SCOPE
                    field_key = "metric.prospective_users"
                elif rule_id == "SCOPE_PEAK_TO_CUMULATIVE":
                    cat = DiffCategory.METRIC_SCOPE
                    field_key = "metric.peak_readership"
                elif rule_id == "SCOPE_UNAUTHORIZED_CURRENCY":
                    cat = DiffCategory.METRIC_SCOPE
                    field_key = "metric.gmv_currency"
                elif rule_id == "SCOPE_UNANCHORED_DENOMINATOR":
                    cat = DiffCategory.METRIC_SCOPE
                    field_key = "metric.gpa_denominator"
                elif rule_id.startswith("SCOPE_") or "scope" in rule_id.lower():
                    cat = DiffCategory.METRIC_SCOPE
                    field_key = rule_id
                else:
                    cat = DiffCategory.GENERAL_FACT
                    field_key = d.get("metric_type", "metric_drift")

                claimed_val = next((d[key] for key in ("claimed_snippet", "claimed_metric", "claimed_text") if key in d), "")
                base_val = d.get("verified_baseline", d.get("baseline_raw", ""))
                reason = d.get("reason", "度量口径偏离SSOT基线")
                fix = d.get("fix_suggestion", "")

                ledger.add_entry(
                    category=cat,
                    field=field_key,
                    baseline_zh=str(base_val),
                    tailored_en=str(claimed_val),
                    severity=DiffSeverity.CAUTION,
                    explanation=reason,
                    action_taken=f"检测到风险，未应用修正。建议: {fix}" if fix else "检测到风险，未应用修正。",
                    metadata={**d, "event_status": "detected"},
                )

            # 1c. Unverified claims
            for u in guard_result.get("unverified_claims", []):
                claimed = u.get("claimed_metric", u.get("claimed_text", ""))
                reason = u.get("reason", "未经SSOT基线佐证的数值或技术声称")
                ledger.add_entry(
                    category=DiffCategory.GENERAL_FACT,
                    field=u.get("metric_type", "unverified_claim"),
                    baseline_zh="无SSOT基线佐证 (Unanchored)",
                    tailored_en=str(claimed),
                    severity=DiffSeverity.CAUTION,
                    explanation=reason,
                    action_taken="标记待确认事实，需候选人补充支撑材料",
                    metadata={**u, "event_status": "detected"},
                )

        # 2. Comprehensive Substantive Profile & Alignment Extraction
        cls._audit_substantive_alignments(ledger, baseline_profile, tailored_data)

        # 3. Layout Micro-actions Traceability
        cls._audit_layout_actions(ledger, layout_metadata)

        return ledger

    @staticmethod
    def _source_fields(data: Any, path: str = "") -> Dict[str, Any]:
        """Keep each leaf (including empty containers) at its exact source path."""
        fields: Dict[str, Any] = {}
        if isinstance(data, dict) and data:
            for key, value in data.items():
                suffix = str(key) if str(key).isidentifier() else f"[{json.dumps(key, ensure_ascii=False)}]"
                child = f"{path}.{suffix}" if path and not suffix.startswith("[") else f"{path}{suffix}"
                fields.update(DiffLedger._source_fields(value, child))
        elif isinstance(data, list) and data:
            for index, value in enumerate(data):
                fields.update(DiffLedger._source_fields(value, f"{path}[{index}]"))
        else:
            fields[path or "$"] = data
        return fields

    @staticmethod
    def _display_value(value: Any) -> str:
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _field_category(path: str, before: Any, after: Any) -> DiffCategory:
        key = path.rsplit(".", 1)[-1]
        if key in {"role", "title", "position"}:
            return DiffCategory.ROLE_HIERARCHY
        if any(term in path.lower() for term in ("certification", "credential", "coursework", "degree")):
            return DiffCategory.CREDENTIAL_FIDELITY
        if re.search(r"\d", f"{before} {after}"):
            return DiffCategory.METRIC_SCOPE
        return DiffCategory.GENERAL_FACT

    @classmethod
    def _audit_substantive_alignments(
        cls,
        ledger: DiffLedger,
        baseline_profile: Optional[Union[Dict[str, Any], Any]],
        tailored_data: Optional[Union[Dict[str, Any], str]],
    ) -> None:
        """Compare actual fields; never substitute example facts or translations."""
        if baseline_profile is None or tailored_data is None:
            ledger.metadata["comparison"] = {"status": "unknown", "reason": "Both inputs are required."}
            return
        structured = isinstance(baseline_profile, dict) and isinstance(tailored_data, dict)
        ledger.metadata["comparison"] = {
            "status": "complete" if structured else "text_only",
            "basis": "exact_source_values",
            "limitation": "Equality is not independent factual verification; list entries are compared by position.",
        }
        baseline = cls._source_fields(baseline_profile) if structured else {"document": baseline_profile}
        tailored = cls._source_fields(tailored_data) if structured else {"document": tailored_data}
        for path in sorted(baseline.keys() | tailored.keys()):
            before_present, after_present = path in baseline, path in tailored
            before, after = baseline.get(path), tailored.get(path)
            equal = before_present and after_present and type(before) is type(after) and before == after
            change = "unchanged" if equal else "added" if not before_present else "removed" if not after_present else "modified"
            ledger.add_entry(
                category=cls._field_category(path, before, after),
                field=path,
                baseline_zh=cls._display_value(before) if before_present else "",
                tailored_en=cls._display_value(after) if after_present else "",
                severity=DiffSeverity.ALIGNED if equal else DiffSeverity.CAUTION,
                explanation="输入字段值相同；不代表独立事实核实。" if equal else f"观察到字段变化 ({change})，需核对来源。",
                action_taken="仅比较输入，未应用修改。",
                metadata={
                    "event_status": "unchanged" if equal else "observed_change",
                    "change_type": change,
                    "baseline_present": before_present,
                    "tailored_present": after_present,
                    "baseline_value": before,
                    "tailored_value": after,
                },
            )

    @classmethod
    def _audit_layout_actions(
        cls,
        ledger: DiffLedger,
        layout_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Report supplied solver metadata without claiming rendered outcomes."""
        ledger.metadata["layout_verification"] = "unknown"
        ledger.add_entry(
            category=DiffCategory.LAYOUT_ACTION,
            field="layout.verification",
            severity=DiffSeverity.CAUTION,
            explanation="未验证最终渲染的字号、孤行或分页；排版参数不等于测量结果。",
            action_taken="未执行渲染测量。",
            metadata={"event_status": "unknown"},
        )
        if not isinstance(layout_metadata, dict):
            return
        for key, value in sorted(layout_metadata.items()):
            ledger.add_entry(
                category=DiffCategory.LAYOUT_ACTION,
                field=f"layout.{key}",
                tailored_en=cls._display_value(value),
                severity=DiffSeverity.CAUTION if key == "solved" and value is False else DiffSeverity.INFO,
                explanation="调用方提供的排版记录；未独立验证最终渲染结果。",
                action_taken="仅记录元数据，未应用或验证排版修改。",
                metadata={"event_status": "reported", "source": "layout_metadata", "reported_value": value},
            )

    def generate_markdown(self) -> str:
        """
        Generates a visually rich, GitHub-flavored Markdown report.
        Includes GitHub alert blocks, KPI executive summary, and categorized tables.
        """
        total = len(self.entries)
        inflations = sum(1 for e in self.entries if e.severity == DiffSeverity.INFLATION_PREVENTED)
        aligned = sum(1 for e in self.entries if e.severity == DiffSeverity.ALIGNED)
        caution = sum(1 for e in self.entries if e.severity == DiffSeverity.CAUTION)
        layout_count = len(self.get_entries_by_category(DiffCategory.LAYOUT_ACTION))

        lines: List[str] = []

        # Header & Alerts
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"> **候选人 SSOT**：`{self.candidate_name or '全流程核验候选人'}` &nbsp;|&nbsp; **报告生成时间**：`{self.created_at}`")
        lines.append("")

        lines.append("> [!NOTE]")
        lines.append("> **报告范围**：记录输入字段的实际差异、检测到的问题及调用方提供的排版元数据。")
        lines.append("> 本报告不应用修正；字段相同不等于事实已获独立验证。未提供的测量结果保持未知。")
        lines.append("")

        lines.append("> [!IMPORTANT]")
        lines.append("> **四大对齐红线 (Core Alignment Guardrails)**：")
        lines.append("> 1. **职务层级不越级**：普通成员/干事绝不虚标为 Specialist / Lead / Manager；")
        lines.append("> 2. **量化口径不漂移**：服务场次严禁偷换为物料产出，个人受众严禁漂移为企业客户，单篇峰值严禁篡改为累计总量，原币种严禁臆造美元汇率，未授权 GPA 严禁脑补满分分母；")
        lines.append("> 3. **证书学术不缩水**：国家级考试科目与专业课学术全称完整保真，绝不为单行排版暴力缩减；")
        lines.append("> 4. **版面需测量**：字号、孤行和分页需要检查最终渲染文件；配置值或求解器状态不能代替测量。")
        lines.append("")

        lines.append("> [!TIP]")
        lines.append(f"> **本次比较概览**：共 **{total}** 条记录，**{aligned}** 项输入值相同，**{caution}** 项需复核。检测和建议不代表修正已应用。")
        lines.append("")

        # Executive Summary Table
        lines.append("## 📊 审计概览 (Executive Summary)")
        lines.append("")
        lines.append("| 统计指标 (Metric) | 数量 (Count) | 状态解读 (Assessment) |")
        lines.append("| :--- | :---: | :--- |")
        lines.append(f"| **审计条目总数 (Total Entries Audited)** | **{total}** | 仅包含本次实际比较和收到的记录 |")
        lines.append(f"| **拦截虚假拔高/范围漂移 (Inflations Prevented)** | **{inflations}** | 仅统计明确记录为已拦截的事件；检测不计入 |")
        lines.append(f"| **输入值相同 (Input Values Match)** | **{aligned}** | ✅ 输入值相同；不是独立事实认证 |")
        lines.append(f"| **需候选人留意思项 (Caution / Review)** | **{caution}** | ⚠️ 存在待确认或边界微调项 |")
        lines.append(f"| **排版自适应优化动作 (Layout Actions)** | **{layout_count}** | ℹ️ 排版记录数量；不代表已应用或渲染验证 |")
        lines.append("")

        # Categorized Tables
        category_order = [
            DiffCategory.ROLE_HIERARCHY,
            DiffCategory.METRIC_SCOPE,
            DiffCategory.CREDENTIAL_FIDELITY,
            DiffCategory.LAYOUT_ACTION,
            DiffCategory.GENERAL_FACT,
        ]

        for idx, cat in enumerate(category_order, 1):
            cat_entries = self.get_entries_by_category(cat)
            if not cat_entries:
                continue

            meta = DIFF_CATEGORY_META.get(cat, {})
            title_zh = meta.get("title_zh", cat.value)
            title_en = meta.get("title_en", cat.value)
            icon = meta.get("icon", "📌")
            alert_type = meta.get("alert_type", "NOTE")
            alert_text = meta.get("alert_text", "")

            lines.append(f"## {icon} {idx}. {title_zh} ({title_en})")
            lines.append("")
            if alert_text:
                lines.append(f"> [!{alert_type}]")
                lines.append(f"> {alert_text}")
                lines.append("")

            # Category-specific table rendering
            if cat == DiffCategory.ROLE_HIERARCHY:
                lines.append("| 经历/模块 | 原中文职务 (Baseline) | 改写英文职务 (Tailored) | 状态 | 评估与溯源说明 | 采取对齐动作 |")
                lines.append("| :--- | :--- | :--- | :---: | :--- | :--- |")
                for e in cat_entries:
                    badge = DIFF_SEVERITY_BADGES.get(e.severity, e.severity.value)
                    lines.append(f"| `{e.field}` | {e.baseline_zh} | **{e.tailored_en}** | {badge} | {e.explanation} | {e.action_taken} |")

            elif cat == DiffCategory.METRIC_SCOPE:
                lines.append("| 业务字段 | 原量化基线 (Baseline) | 改写表述 (Tailored) | 状态 | 口径比对说明 | 采取对齐动作 |")
                lines.append("| :--- | :--- | :--- | :---: | :--- | :--- |")
                for e in cat_entries:
                    badge = DIFF_SEVERITY_BADGES.get(e.severity, e.severity.value)
                    lines.append(f"| `{e.field}` | {e.baseline_zh} | **{e.tailored_en}** | {badge} | {e.explanation} | {e.action_taken} |")

            elif cat == DiffCategory.CREDENTIAL_FIDELITY:
                lines.append("| 项目/科目 | 原基线内容 (Baseline) | 改写英文呈现 (Tailored) | 状态 | 保真说明 | 采取对齐动作 |")
                lines.append("| :--- | :--- | :--- | :---: | :--- | :--- |")
                for e in cat_entries:
                    badge = DIFF_SEVERITY_BADGES.get(e.severity, e.severity.value)
                    lines.append(f"| `{e.field}` | {e.baseline_zh} | **{e.tailored_en}** | {badge} | {e.explanation} | {e.action_taken} |")

            elif cat == DiffCategory.LAYOUT_ACTION:
                lines.append("| 调优维度 | 规则底线 (Baseline Rule) | 提供的记录 (Reported Value) | 状态 | 调优说明与收益 |")
                lines.append("| :--- | :--- | :--- | :---: | :--- |")
                for e in cat_entries:
                    badge = DIFF_SEVERITY_BADGES.get(e.severity, e.severity.value)
                    lines.append(f"| `{e.field}` | {e.baseline_zh} | **{e.tailored_en}** | {badge} | {e.explanation} |")

            else:  # GENERAL_FACT
                lines.append("| 审计范围 | 基线锚点 (Baseline) | 改写呈现 (Tailored) | 状态 | 核验结论 | 采取行动 |")
                lines.append("| :--- | :--- | :--- | :---: | :--- | :--- |")
                for e in cat_entries:
                    badge = DIFF_SEVERITY_BADGES.get(e.severity, e.severity.value)
                    lines.append(f"| `{e.field}` | {e.baseline_zh} | **{e.tailored_en}** | {badge} | {e.explanation} | {e.action_taken} |")

            lines.append("")

        lines.append("---")
        lines.append("*本报告由 [OfferGet](https://github.com/OfferGet) 改动溯源与口径对齐引擎 (Diff Ledger Engine) 自动生成。*")
        lines.append("")

        return "\n".join(lines)

    def generate_cli_summary(self) -> str:
        """Generates an eye-catching terminal summary."""
        total = len(self.entries)
        inflations = sum(1 for e in self.entries if e.severity == DiffSeverity.INFLATION_PREVENTED)
        aligned = sum(1 for e in self.entries if e.severity == DiffSeverity.ALIGNED)
        layout_count = len(self.get_entries_by_category(DiffCategory.LAYOUT_ACTION))

        c_name = self.candidate_name or "未指定"

        border = "=" * 80
        sub_border = "-" * 80

        lines = [
            border,
            "           OfferGet 改动溯源与口径对齐报告 (Diff Ledger Summary)",
            border,
            f"候选人: {c_name} | 审计总计: {total} | 🛡️ 拦截风险: {inflations} | ✅ 输入相同: {aligned} | 📐 排版记录: {layout_count}",
            sub_border,
        ]

        # Group entries by category
        role_entries = self.get_entries_by_category(DiffCategory.ROLE_HIERARCHY)
        if role_entries:
            lines.append("[🎖️ 职务层级对齐 (Role Hierarchy)]")
            for e in role_entries:
                badge = DIFF_SEVERITY_BADGES.get(e.severity, e.severity.value)
                lines.append(f"  - {badge}: 原“{e.baseline_zh}” -> {e.tailored_en} ({e.action_taken})")

        metric_entries = self.get_entries_by_category(DiffCategory.METRIC_SCOPE)
        if metric_entries:
            lines.append("[📊 数据口径对齐 (Metric Scope)]")
            for e in metric_entries:
                lines.append(f"  - {DIFF_SEVERITY_BADGES[e.severity]}: {e.baseline_zh} -> {e.tailored_en} ({e.action_taken})")

        cred_entries = self.get_entries_by_category(DiffCategory.CREDENTIAL_FIDELITY)
        if cred_entries:
            lines.append("[📜 证书课程保真 (Credential & Coursework)]")
            for e in cred_entries:
                lines.append(f"  - {DIFF_SEVERITY_BADGES[e.severity]}: {e.baseline_zh} -> {e.tailored_en} ({e.action_taken})")

        layout_entries = self.get_entries_by_category(DiffCategory.LAYOUT_ACTION)
        if layout_entries:
            lines.append("[📐 排版自适应动作 (Adaptive Layout)]")
            for e in layout_entries:
                lines.append(f"  - {e.field}: {e.tailored_en} ({e.explanation})")

        general_entries = self.get_entries_by_category(DiffCategory.GENERAL_FACT)
        if general_entries:
            lines.append("[🔍 通用事实核验 (General Facts)]")
            for e in general_entries:
                lines.append(f"  - 🔍 事实状态: {e.baseline_zh} -> {e.tailored_en} ({e.explanation})")

        lines.append(border)
        return "\n".join(lines)

    def save(self, output_dir: Union[Path, str], base_name: str = "resume") -> Dict[str, Path]:
        """
        Saves the Diff Ledger as both markdown and JSON into output_dir.

        Returns:
            Dict containing Path objects for 'markdown' and 'json'.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        md_file = out_path / f"{base_name}_diff_ledger.md"
        json_file = out_path / f"{base_name}_diff_ledger.json"

        md_content = self.generate_markdown()
        json_content = self.generate_json()

        md_file.write_text(md_content, encoding="utf-8")
        json_file.write_text(json_content, encoding="utf-8")

        return {
            "markdown": md_file,
            "json": json_file,
        }


__all__ = [
    "DiffCategory",
    "DiffSeverity",
    "DiffEntry",
    "DiffLedger",
    "DIFF_CATEGORY_META",
    "DIFF_SEVERITY_BADGES",
]
