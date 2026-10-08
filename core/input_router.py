"""
OfferGet Input Router (core/input_router.py)
============================================
Adaptive stage routing based on provided inputs (JD, Candidate Profile, or both).
Governs executable stages, blocked stages, missing inputs, and next-step actions
across OfferGet native pipelines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.cli_helpers import load_json_or_text


class InputMode(str, Enum):
    JD_ONLY = "JD_ONLY"
    PROFILE_ONLY = "PROFILE_ONLY"
    JD_AND_PROFILE = "JD_AND_PROFILE"
    MULTI_JD_AND_PROFILE = "MULTI_JD_AND_PROFILE"
    INVALID = "INVALID"


class InvalidInputError(ValueError):
    """Raised when input routing fails fast due to missing or invalid inputs."""

    def __init__(self, message: str, decision: Optional[RouteDecision] = None):
        super().__init__(message)
        self.decision = decision


@dataclass
class RouteDecision:
    """Decision object describing what stages can and cannot be executed."""

    mode: str
    executable_stages: List[str] = field(default_factory=list)
    blocked_stages: List[str] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.mode != InputMode.INVALID.value

    def can_execute(self, stage: str) -> bool:
        return stage in self.executable_stages and stage not in self.blocked_stages

    def is_blocked(self, stage: str) -> bool:
        # Unadvertised stages are unsupported, not implicitly executable.
        return not self.can_execute(stage)

    def raise_if_blocked(self, stage: str) -> None:
        if self.is_blocked(stage):
            raise InvalidInputError(
                f"Stage '{stage}' is blocked in mode '{self.mode}'. "
                f"Missing inputs: {self.missing_inputs}. Next steps: {self.next_steps}",
                decision=self,
            )

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            raise InvalidInputError(
                f"Routing failed: invalid or empty inputs. Missing: {self.missing_inputs}. "
                f"Next steps: {'; '.join(self.next_steps)}",
                decision=self,
            )


class InputRouter:
    """Intelligent router inspecting JD and Profile inputs to determine pipeline flow."""

    @classmethod
    def _is_present(cls, val: Any) -> bool:
        if val is None:
            return False
        if isinstance(val, str):
            return bool(val.strip())
        if isinstance(val, (list, tuple, set, dict)):
            return len(val) > 0
        return True

    @classmethod
    def _is_multi_jd(cls, jd: Any) -> bool:
        # A sequence is a batch request even if it has only one nonempty item.
        # Single-JD services cannot safely turn its Python representation into JD text.
        return isinstance(jd, (list, tuple)) and bool(jd)

    @classmethod
    def route(
        cls,
        jd: Optional[Any] = None,
        profile: Optional[Any] = None,
        fail_fast: bool = False,
    ) -> RouteDecision:
        """Determines the appropriate pipeline route given JD and candidate profile inputs.

        Args:
            jd: JD text, file path, dict, or sequence of JDs.
            profile: Candidate profile dict, file path, or object.
            fail_fast: If True and inputs are invalid/empty, raises InvalidInputError immediately.

        Returns:
            RouteDecision indicating executable and blocked pipeline stages.
        """
        has_jd = cls._is_present(jd)
        has_profile = cls._is_present(profile)
        is_multi = has_jd and cls._is_multi_jd(jd)

        if not has_jd and not has_profile:
            decision = RouteDecision(
                mode=InputMode.INVALID.value,
                executable_stages=[],
                blocked_stages=[
                    "jd_decode",
                    "profile_audit",
                    "full_match",
                    "ats_matching_score",
                    "career_review",
                    "resume_build",
                    "report_generation",
                ],
                missing_inputs=["jd", "profile"],
                next_steps=[
                    "请至少提供目标 JD 文本（或文件路径）或候选人 Profile 数据。",
                    "若仅有岗位 JD，可执行 JD 深度解码与业务痛点解析。",
                    "若仅有简历 Profile，可执行简历质量审计与多主题排版导出。",
                ],
            )
            if fail_fast:
                decision.raise_if_invalid()
            return decision

        # Recognize JD collections without promising an unimplemented batch executor.
        if is_multi:
            return RouteDecision(
                mode=InputMode.MULTI_JD_AND_PROFILE.value if has_profile else InputMode.JD_ONLY.value,
                executable_stages=["profile_audit", "resume_build"] if has_profile else [],
                blocked_stages=[
                    "jd_decode", "multi_jd_decode", "full_match", "batch_match",
                    "ats_matching_score", "gap_analysis", "cross_jd_gap_matrix",
                    "comparative_analysis", "career_review", "tailored_resume",
                    "interview_prediction", "report_generation",
                ],
                missing_inputs=[] if has_profile else ["profile"],
                next_steps=[
                    "暂不支持多岗位批量处理，请每次提供一份 JD 文本、文件路径或字典。",
                    "Batch JD processing is unsupported; pass one JD text, path, or dictionary at a time.",
                ],
            )

        if has_jd and not has_profile:
            return RouteDecision(
                mode=InputMode.JD_ONLY.value,
                executable_stages=[
                    "jd_decode",
                    "pain_point_analysis",
                    "requirement_extraction",
                    "taxonomy_classification",
                    "implicit_signals",
                ],
                blocked_stages=[
                    "full_match",
                    "ats_matching_score",
                    "gap_analysis",
                    "career_review",
                    "resume_build",
                    "tailored_resume",
                    "report_generation",
                ],
                missing_inputs=["profile"],
                next_steps=[
                    "已就绪阶段：JD 深度解码、五图层拆解、能力图谱提取与业务痛点分析。",
                    "如需生成匹配度雷达与差距矩阵，请补充提供候选人 Profile (resume data)。",
                ],
            )

        if not has_jd and has_profile:
            return RouteDecision(
                mode=InputMode.PROFILE_ONLY.value,
                executable_stages=[
                    "profile_audit",
                    "resume_build",
                    "academic_export",
                    "anonymization",
                    "evidence_indexing",
                    "anti_ai_slop_check",
                ],
                blocked_stages=[
                    "jd_decode",
                    "jd_alignment",
                    "full_match",
                    "ats_matching_score",
                    "gap_analysis",
                    "career_review",
                ],
                missing_inputs=["jd"],
                next_steps=[
                    "已就绪阶段：简历合规审计、事实证据索引、六大主题简历构建与导出。",
                    "如需进行针对性岗位对齐、面试预测与一键复盘，请补充提供目标岗位 JD。",
                ],
            )

        return RouteDecision(
            mode=InputMode.JD_AND_PROFILE.value,
            executable_stages=[
                "jd_decode",
                "profile_audit",
                "full_match",
                "ats_matching_score",
                "gap_analysis",
                "career_review",
                "resume_build",
                "interview_prediction",
                "report_generation",
            ],
            blocked_stages=[],
            missing_inputs=[],
            next_steps=[
                "输入数据完备，已解锁 OfferGet 端到端全流程（JD 解码、深度匹配、闭环复盘、定制简历、策略报告）。",
            ],
        )


def parse_input(
    input_val: Any,
    expected_type: Optional[str] = None,
) -> Any:
    """Parses input from a file path, raw string, dict, or data object.

    Args:
        input_val: File path (str or Path), raw JSON or text string, dict, or object.
        expected_type: Optional hint ('json', 'text', 'dict').

    Returns:
        Parsed dict (if JSON/profile) or str (if text/JD), or the original object.
    """
    if input_val is None:
        return None

    # If it's already a dict or list or dataclass/model
    if isinstance(input_val, (dict, list)):
        return input_val
    if hasattr(input_val, "raw_profile") or hasattr(input_val, "normalized_profile"):
        return input_val
    if hasattr(input_val, "to_dict") and callable(input_val.to_dict):
        return input_val

    # If it's a Path or str
    if isinstance(input_val, (str, Path)):
        if expected_type in ("text",):
            parsed, text = load_json_or_text(input_val)
            # Keep JSON collection identity so routing cannot mistake a batch
            # file/string for one JD after serialization.
            return parsed if isinstance(parsed, list) else text
        parsed, text = load_json_or_text(input_val)
        if parsed is not None:
            return parsed
        if expected_type in ("json", "dict"):
            try:
                data = json.loads(text)
                if isinstance(data, (dict, list)):
                    return data
            except Exception as exc:
                raise ValueError(f"Expected JSON input could not be parsed: {exc}") from exc
            raise ValueError(f"Expected JSON object or list, got text")
        return text

    return input_val


@dataclass
class InputRouteResult:
    """Container holding parsed inputs and the routing decision."""

    jd: Any
    profile: Any
    decision: RouteDecision

    def __iter__(self):
        return iter((self.jd, self.profile, self.decision))

    @property
    def mode(self) -> str:
        return self.decision.mode

    @property
    def is_valid(self) -> bool:
        return self.decision.is_valid

    @property
    def executable_stages(self) -> List[str]:
        return self.decision.executable_stages

    @property
    def blocked_stages(self) -> List[str]:
        return self.decision.blocked_stages

    @property
    def missing_inputs(self) -> List[str]:
        return self.decision.missing_inputs

    @property
    def next_steps(self) -> List[str]:
        return self.decision.next_steps

    def can_execute(self, stage: str) -> bool:
        return self.decision.can_execute(stage)

    def is_blocked(self, stage: str) -> bool:
        return self.decision.is_blocked(stage)

    def raise_if_blocked(self, stage: str) -> None:
        return self.decision.raise_if_blocked(stage)

    def raise_if_invalid(self) -> None:
        return self.decision.raise_if_invalid()


def scan_unsubmitted_placeholders(profile_data: Any) -> Dict[str, Any]:
    """Scans candidate profile for unsubmitted placeholders and missing core fields.

    Finds {{...}}, <...>, [待填...] tokens, as well as missing essential candidate fields
    (name, phone, email, title, etc.), and generates a proactive inquiry prompt for the agent/user.
    """
    import re
    parsed = parse_input(profile_data, expected_type="json") if profile_data is not None else {}
    if not isinstance(parsed, dict):
        return {
            "has_placeholders": False,
            "placeholders": [],
            "missing_fields": ["profile_data"],
            "proactive_inquiry": "未提供有效的简历数据，请提供您的真实简历信息或档案文件。",
        }

    placeholders: List[Dict[str, str]] = []
    missing_fields: List[str] = []

    def _walk(obj: Any, path: str = ""):
        if isinstance(obj, str):
            matches = re.findall(r"\{\{([^}]+)\}\}|<([^>]+)>|\[(待[填补][^\]]*)\]", obj)
            for m in matches:
                token = next(filter(bool, m))
                placeholders.append({
                    "path": path,
                    "token": token,
                    "raw": obj,
                })
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, (list, tuple)):
            for idx, item in enumerate(obj):
                _walk(item, f"{path}[{idx}]")

    _walk(parsed)

    candidate = parsed.get("candidate", {})
    if isinstance(candidate, dict):
        for req in ["name", "phone", "email", "title"]:
            val = str(candidate.get(req, "")).strip()
            if not val or val.startswith("{{") or val.startswith("<") or val.startswith("[待"):
                if f"candidate.{req}" not in missing_fields:
                    missing_fields.append(f"candidate.{req}")

    has_placeholders = len(placeholders) > 0 or len(missing_fields) > 0

    inquiry_lines = []
    if has_placeholders:
        inquiry_lines.append("### ⚠️ 检测到未提交的关键信息与占位字段")
        inquiry_lines.append("为确保简历真实性并符合 ATS 事实核验质检门禁（严禁伪造事实或指标漂移），在继续生成前请补充以下真实信息：\n")
        
        seen_tokens = set()
        idx = 1
        if missing_fields:
            inquiry_lines.append(f"{idx}. **缺失核心字段**：{', '.join(missing_fields)}")
            idx += 1
            
        for p in placeholders:
            tok = p["token"]
            if tok not in seen_tokens:
                seen_tokens.add(tok)
                inquiry_lines.append(f"{idx}. **待填占位符** `{{{{{tok}}}}}` (位于 `{p['path']}`)")
                idx += 1

        inquiry_lines.append("\n👉 请直接回复提供真实数据，或明确告知“确认使用匿名占位符进行格式测试”。")

    return {
        "has_placeholders": has_placeholders,
        "placeholders": placeholders,
        "missing_fields": missing_fields,
        "proactive_inquiry": "\n".join(inquiry_lines),
    }


def detect_and_route_input(
    jd: Optional[Any] = None,
    profile: Optional[Any] = None,
    fail_fast: bool = False,
) -> InputRouteResult:
    """Automatically detects and routes JD and profile inputs (filepath or raw string/dict).

    Can be used directly as a RouteDecision proxy or unpacked as a 3-tuple (parsed_jd, parsed_profile, decision).
    """
    parsed_jd = parse_input(jd, expected_type="text") if jd is not None else None
    parsed_profile = parse_input(profile, expected_type="json") if profile is not None else None
    decision = InputRouter.route(jd=parsed_jd, profile=parsed_profile, fail_fast=fail_fast)
    return InputRouteResult(jd=parsed_jd, profile=parsed_profile, decision=decision)


__all__ = [
    "InputMode",
    "RouteDecision",
    "InputRouter",
    "InvalidInputError",
    "InputRouteResult",
    "parse_input",
    "detect_and_route_input",
    "scan_unsubmitted_placeholders",
]
