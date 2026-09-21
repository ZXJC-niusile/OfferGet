"""
OfferGet Defense Rubrics and Weakness Dimensions.
Absorbed and formalized from defense-beating-simulator (MIT).
Provides evidence status labels, risk basis labels, 9 weakness dimensions,
and a 100-point answer scoring rubric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class EvidenceStatus(str, Enum):
    """
    Evidence status for claims in project materials.
    Do not mix evidence status with risk origin.
    """
    MATERIAL_SUPPORTED = "Material-supported"  # 材料中有直接、可查证依据或明确限定了范围/局限
    MATERIAL_IMPLIED = "Material-implied"      # 材料有所暗示但未明确说明，需澄清
    MATERIAL_MISSING = "Material-missing"      # 提出主张但无任何依据佐证


class RiskBasis(str, Enum):
    """
    Origin basis for identified risks.
    """
    MATERIAL_DERIVED = "Material-derived"                      # 风险直接来自材料矛盾、遗漏或表述夸大
    RISK_INFERRED = "Risk-inferred"                            # 风险来自答辩经验与攻防推断
    COMBINED = "Material-derived + Risk-inferred"              # 兼具材料依据与经验推断


class DefenseWeaknessDimension(str, Enum):
    """
    9 weakness dimensions to check in every project defense review.
    """
    PROJECT_POSITIONING = "项目定位"    # 是否说清楚项目定位，是否存在“仿真/优化/实时/部署”说法过大
    TECHNICAL_DEPTH = "技术深度"        # 是否有算法、模型、计算逻辑、工程依据，还是仅展示与集成
    DATA_PROVENANCE = "数据支撑"        # 数据来源、构造逻辑、可信边界、可替换真实数据的路径
    RESULTS_PRESENTATION = "结果展示"   # 是否有图表、截图、指标、对比、误差、失败案例
    PERSONAL_CONTRIBUTION = "个人贡献"  # 是否能区分本人工作、团队工作、开源复用、AI辅助
    INNOVATION_FRAMING = "创新表达"     # 哪些是真创新，哪些是工程集成或展示方式优化
    REPRODUCIBILITY = "可复现性"        # README、运行命令、依赖、示例数据、Demo、许可证
    RISK_PHRASING = "风险表述"          # 是否有夸大、模糊、偷换概念、不严谨表述
    DEFENSE_SAFETY = "答辩安全性"       # 哪些问题最容易引出致命连续追问


@dataclass
class AnswerScoreResult:
    """
    Result of 100-point defense answer scoring rubric.
    """
    total_score: float
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    deductions: Dict[str, str] = field(default_factory=dict)
    main_problems: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    safe_answer: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_score": round(self.total_score, 1),
            "dimension_scores": dict(self.dimension_scores),
            "deductions": dict(self.deductions),
            "main_problems": list(self.main_problems),
            "suggestions": list(self.suggestions),
            "safe_answer": self.safe_answer,
        }


class AnswerScoringRubric:
    """
    100-point rubric for evaluating defense answers.
    Dimensions:
      1. 正面回答问题 (20 pts)
      2. 有技术或材料细节 (20 pts)
      3. 承认项目边界 (15 pts)
      4. 突出个人贡献 (15 pts)
      5. 避免夸大 (15 pts)
      6. 表达清晰 (15 pts)
    """

    MAX_SCORES = {
        "direct_response": 20.0,
        "technical_details": 20.0,
        "acknowledges_boundary": 15.0,
        "highlights_personal_contribution": 15.0,
        "avoids_overclaiming": 15.0,
        "clarity": 15.0,
    }

    DIMENSION_NAMES = {
        "direct_response": "正面回答问题",
        "technical_details": "有技术或材料细节",
        "acknowledges_boundary": "承认项目边界",
        "highlights_personal_contribution": "突出个人贡献",
        "avoids_overclaiming": "避免夸大",
        "clarity": "表达清晰",
    }
