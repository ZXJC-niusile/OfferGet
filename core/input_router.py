"""
OfferGet Input Router (core/input_router.py)
============================================
Adaptive stage routing based on provided inputs (JD, Candidate Profile, or both).
Absorbs stage routing patterns from resume-jd-optimizer-cn to govern executable
stages, blocked stages, missing inputs, and next-step actions across OfferGet pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Sequence, Union


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
        return stage in self.executable_stages

    def is_blocked(self, stage: str) -> bool:
        return stage in self.blocked_stages

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
        if isinstance(jd, (list, tuple)):
            valid_items = [item for item in jd if cls._is_present(item)]
            return len(valid_items) > 1
        return False

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

        # Both are present
        if is_multi:
            return RouteDecision(
                mode=InputMode.MULTI_JD_AND_PROFILE.value,
                executable_stages=[
                    "multi_jd_decode",
                    "profile_audit",
                    "batch_match",
                    "cross_jd_gap_matrix",
                    "comparative_analysis",
                    "resume_build",
                    "tailored_resume",
                    "report_generation",
                ],
                blocked_stages=[],
                missing_inputs=[],
                next_steps=[
                    "多岗位与候选人数据均已就绪，可执行多岗位批量对比、横向适配度排序与批量简历定制。",
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


__all__ = ["InputMode", "RouteDecision", "InputRouter", "InvalidInputError"]
