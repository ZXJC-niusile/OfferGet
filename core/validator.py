"""
OfferGet Validator Engine
Checks career narratives for Anti-AI-Slop violations.
"""

import re
from typing import Dict, Any


from core.registry import QualityRuleRegistry

BANNED_SLOP_PATTERNS = QualityRuleRegistry.BANNED_SLOP_PATTERNS


def validate_anti_ai_slop(text: str) -> Dict[str, Any]:
    """
    Audits resume or report text against Anti-AI-Slop patterns.
    """
    violations = []
    for pattern, reason in BANNED_SLOP_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            violations.append({
                "reason": reason,
                "pattern": pattern,
                "matches": matches[:3]
            })

    return {
        "passed": len(violations) == 0,
        "violation_count": len(violations),
        "violations": violations
    }
