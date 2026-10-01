"""
OfferGet Validator Engine
Audits HTML reports for bilingual twin parity and checks career narratives for Anti-AI-Slop violations.
"""

import os
import re
from typing import Dict, Any


from core.registry import QualityRuleRegistry

BANNED_SLOP_PATTERNS = QualityRuleRegistry.BANNED_SLOP_PATTERNS


def validate_bilingual_html(html_or_path: str) -> Dict[str, Any]:
    """
    Validates HTML against OfferGet's strict twin-language rules:
    1. <html lang="en"> must be present.
    2. Number of data-lang="en" must strictly equal data-lang="zh".
    3. Minimum threshold: en_count >= 80.
    """
    if os.path.exists(html_or_path):
        with open(html_or_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = html_or_path

    en_count = len(re.findall(r'data-lang=["\']en["\']', content))
    zh_count = len(re.findall(r'data-lang=["\']zh["\']', content))
    root_en = bool(re.search(r'<html[^>]*lang=["\']en["\']', content))

    errors = []
    if not root_en:
        errors.append("Root <html lang=\"en\"> is missing or improperly set.")
    if en_count != zh_count:
        errors.append(f"Language twin mismatch: data-lang=\"en\" ({en_count}) != data-lang=\"zh\" ({zh_count}).")
    if en_count < 80:
        errors.append(f"Insufficient bilingual twins: found {en_count}, minimum required is 80.")

    return {
        "passed": len(errors) == 0,
        "en_count": en_count,
        "zh_count": zh_count,
        "root_lang_en": root_en,
        "errors": errors
    }


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
