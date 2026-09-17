"""
OfferGet Report Generator
Renders industrial-grade bilingual HTML reports with dynamic SVG gauges, credential cards, and interview banks.
"""

import os
import html as html_lib
from datetime import date
from typing import Dict, Any


def generate_report(decoded_jd: Dict[str, Any], match_result: Dict[str, Any], template_path: str, output_path: str) -> str:
    """
    Renders Offer Strategy Report HTML by populating templates/offer_strategy.html.
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found at: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    meta = decoded_jd.get("metadata", {})
    layers = decoded_jd.get("layers", {})
    verdict = match_result.get("verdict", {})
    breakdown = match_result.get("breakdown", {})

    match_score = match_result.get("overall_match_score")
    interview_prob = match_result.get("interview_prob")
    match_score = float(match_score) if isinstance(match_score, (int, float)) else 0.0
    interview_prob = float(interview_prob) if isinstance(interview_prob, (int, float)) else 0.0

    # Semi-circle gauge stroke calculation:
    # Full arc length = 251.32. Offset = 251.32 * (1 - score / 100)
    match_gauge_offset = round(251.32 * (1 - match_score / 100), 1)
    prob_gauge_offset = round(251.32 * (1 - interview_prob / 100), 1)

    today_str = date.today().strftime("%Y-%m-%d")

    replacements = {
        "{{COMPANY}}": meta.get("company") or "未提供",
        "{{ROLE}}": meta.get("role") or "未提供",
        "{{ROLE_TITLE}}": meta.get("role") or "未提供",
        "{{LEVEL}}": meta.get("level") or "未提供",
        "{{LOCATION}}": meta.get("location") or "未提供",
        "{{COMP_BAND}}": meta.get("comp_band") or "未提供",
        "{{DEPARTMENT}}": meta.get("department") or "未提供",
        "{{ARCHITECTURE_LAYER}}": meta.get("architecture_layer") or "未提供",
        "{{CANDIDATE_NAME}}": match_result.get("candidate_name") or "未提供",
        "{{REPORT_DATE}}": today_str,

        "{{VERDICT_TITLE_EN}}": verdict.get("title_en") or "Insufficient data",
        "{{VERDICT_TITLE_ZH}}": verdict.get("title_zh") or "信息不足，无法判断",
        "{{VERDICT_DESC_EN}}": verdict.get("desc_en") or "No conclusion is generated without matching evidence.",
        "{{VERDICT_DESC_ZH}}": verdict.get("desc_zh") or "缺少匹配证据时不生成投递结论。",

        "{{MATCH_SCORE_NUM}}": str(match_score),
        "{{INTERVIEW_PROB_NUM}}": str(interview_prob),
        "{{MATCH_GAUGE_OFFSET}}": str(match_gauge_offset),
        "{{PROB_GAUGE_OFFSET}}": str(prob_gauge_offset),

        "{{MUST_HAVE_SCORE}}": str(breakdown.get("must_have", 0)),
        "{{NICE_HAVE_SCORE}}": str(breakdown.get("nice_have", 0)),
        "{{HIDDEN_FIT_SCORE}}": str(breakdown.get("hidden_fit", 0)),

        # 5 Layers replacements
        "{{L1_JD_TEXT_ZH}}": layers.get("layer_1", {}).get("jd_text_zh", ""),
        "{{L1_JD_TEXT_EN}}": layers.get("layer_1", {}).get("jd_text_en", ""),
        "{{L1_REALITY_ZH}}": layers.get("layer_1", {}).get("reality_zh", ""),
        "{{L1_REALITY_EN}}": layers.get("layer_1", {}).get("reality_en", ""),

        "{{L2_JD_TEXT_ZH}}": layers.get("layer_2", {}).get("jd_text_zh", ""),
        "{{L2_JD_TEXT_EN}}": layers.get("layer_2", {}).get("jd_text_en", ""),
        "{{L2_REALITY_ZH}}": layers.get("layer_2", {}).get("reality_zh", ""),
        "{{L2_REALITY_EN}}": layers.get("layer_2", {}).get("reality_en", ""),

        "{{L3_JD_TEXT_ZH}}": layers.get("layer_3", {}).get("jd_text_zh", ""),
        "{{L3_JD_TEXT_EN}}": layers.get("layer_3", {}).get("jd_text_en", ""),
        "{{L3_REALITY_ZH}}": layers.get("layer_3", {}).get("reality_zh", ""),
        "{{L3_REALITY_EN}}": layers.get("layer_3", {}).get("reality_en", ""),

        "{{L4_JD_TEXT_ZH}}": layers.get("layer_4", {}).get("jd_text_zh", ""),
        "{{L4_JD_TEXT_EN}}": layers.get("layer_4", {}).get("jd_text_en", ""),
        "{{L4_REALITY_ZH}}": layers.get("layer_4", {}).get("reality_zh", ""),
        "{{L4_REALITY_EN}}": layers.get("layer_4", {}).get("reality_en", ""),

        "{{L5_JD_TEXT_ZH}}": layers.get("layer_5", {}).get("jd_text_zh", ""),
        "{{L5_JD_TEXT_EN}}": layers.get("layer_5", {}).get("jd_text_en", ""),
        "{{L5_REALITY_ZH}}": layers.get("layer_5", {}).get("reality_zh", ""),
        "{{L5_REALITY_EN}}": layers.get("layer_5", {}).get("reality_en", "")
    }

    for key, val in replacements.items():
        # Values like offsets and numbers are safe; string fields escape special characters
        safe_val = html_lib.escape(str(val)) if not key.endswith("_OFFSET}}") and not key.endswith("_NUM}}") and not key.endswith("_SCORE}}") else str(val)
        html = html.replace(key, safe_val)

    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
