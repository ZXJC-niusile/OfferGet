"""
OfferGet Evidence Metric Recalculator.
OfferGet native numerical recalculation and metric verification engine.
Provides deterministic numerical recalculation for:
  - Ratio consistency: numerator / denominator * 100 == displayed_percent (+-0.5)
  - Relative change: (result - baseline) / baseline * 100 == displayed_change (+-0.5)
  - Percentage points: result - baseline == displayed_change (+-0.5)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.evidence.models import MetricCheck


@dataclass
class MetricValidationResult:
    """Result of metric recalculation."""
    is_valid: bool
    error_message: Optional[str] = None
    expected_value: Optional[float] = None
    displayed_value: Optional[float] = None
    tolerance: float = 0.5


class MetricRecalculator:
    """
    Deterministic recalculation engine for resume metrics.
    Strictly follows explicit numbers without heuristic guessing.
    """

    @staticmethod
    def validate_ratio(
        numerator: Any, denominator: Any, displayed_percent: Any, tolerance: float = 0.5
    ) -> MetricValidationResult:
        """
        Validates ratio: numerator / denominator * 100 == displayed_percent.
        Allows absolute tolerance (default 0.5 percentage points).
        """
        try:
            num = float(numerator)
            den = float(denominator)
            disp = float(displayed_percent)
        except (TypeError, ValueError):
            return MetricValidationResult(
                is_valid=False,
                error_message="指标字段无法计算",
                tolerance=tolerance,
            )

        if den == 0:
            return MetricValidationResult(
                is_valid=False,
                error_message="指标字段无法计算",  # Standard error message
                tolerance=tolerance,
            )

        expected = (num / den) * 100.0
        if math.isclose(expected, disp, abs_tol=tolerance):
            return MetricValidationResult(
                is_valid=True,
                expected_value=expected,
                displayed_value=disp,
                tolerance=tolerance,
            )
        else:
            return MetricValidationResult(
                is_valid=False,
                error_message="百分比与分子分母不一致",
                expected_value=expected,
                displayed_value=disp,
                tolerance=tolerance,
            )

    @staticmethod
    def validate_change(
        baseline: Any,
        result: Any,
        change_type: str,
        displayed_change: Any,
        tolerance: float = 0.5,
    ) -> MetricValidationResult:
        """
        Validates change:
          - relative_percent: (result - baseline) / baseline * 100 == displayed_change
          - percentage_points: result - baseline == displayed_change
        Allows absolute tolerance (default 0.5).
        """
        try:
            base = float(baseline)
            res = float(result)
            disp = float(displayed_change)
        except (TypeError, ValueError):
            return MetricValidationResult(
                is_valid=False,
                error_message="变化字段无法计算",
                tolerance=tolerance,
            )

        if change_type == "relative_percent":
            if base == 0:
                return MetricValidationResult(
                    is_valid=False,
                    error_message="相对百分比变化的 baseline 不能为 0",
                    tolerance=tolerance,
                )
            expected = (res - base) / base * 100.0
        elif change_type == "percentage_points":
            expected = res - base
        else:
            return MetricValidationResult(
                is_valid=False,
                error_message=f"change_type 非法：{change_type}",
                tolerance=tolerance,
            )

        if math.isclose(expected, disp, abs_tol=tolerance):
            return MetricValidationResult(
                is_valid=True,
                expected_value=expected,
                displayed_value=disp,
                tolerance=tolerance,
            )
        else:
            return MetricValidationResult(
                is_valid=False,
                error_message="变化值与基线结果不一致",
                expected_value=expected,
                displayed_value=disp,
                tolerance=tolerance,
            )

    @classmethod
    def validate_metric(cls, metric: Dict[str, Any], claim_id: str = "<无编号>") -> List[str]:
        """
        Validates a metric dictionary strictly according to OfferGet validation rules.
        Returns list of error messages.
        """
        errors: List[str] = []
        if not isinstance(metric, dict):
            errors.append(f"{claim_id} metric 必须是对象")
            return errors

        # 1. Ratio check if numerator, denominator, displayed_percent are present
        ratio_keys = {"numerator", "denominator", "displayed_percent"}
        if ratio_keys <= set(metric):
            res = cls.validate_ratio(
                metric.get("numerator"),
                metric.get("denominator"),
                metric.get("displayed_percent"),
            )
            if not res.is_valid and res.error_message:
                errors.append(f"{claim_id} metric {res.error_message}")

        # 2. Change check if baseline, result, change_type, displayed_change are present
        change_keys = {"baseline", "result", "change_type", "displayed_change"}
        if change_keys <= set(metric):
            res = cls.validate_change(
                metric.get("baseline"),
                metric.get("result"),
                str(metric.get("change_type", "")),
                metric.get("displayed_change"),
            )
            if not res.is_valid and res.error_message:
                errors.append(f"{claim_id} metric {res.error_message}")

        return errors

    @classmethod
    def check_metric_check_instance(cls, mc: MetricCheck, claim_id: str = "<无编号>") -> List[str]:
        """Validates a typed MetricCheck instance."""
        return cls.validate_metric(mc.to_dict(), claim_id=claim_id)
