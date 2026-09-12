"""
OfferGet Report Generator
Renders industrial-grade bilingual HTML reports with dynamic SVG gauges, credential cards, and interview banks.
"""

import os
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

    match_score = match_result.get("overall_match_score", 92)
    interview_prob = match_result.get("interview_prob", 88)

    # Semi-circle gauge stroke calculation:
    # Full arc length = 251.32. Offset = 251.32 * (1 - score / 100)
    match_gauge_offset = round(251.32 * (1 - match_score / 100), 1)
    prob_gauge_offset = round(251.32 * (1 - interview_prob / 100), 1)

    today_str = date.today().strftime("%Y-%m-%d")

    replacements = {
        "{{COMPANY}}": meta.get("company", "Frontier AI Lab"),
        "{{ROLE}}": meta.get("role", "大模型算法架构师"),
        "{{ROLE_TITLE}}": meta.get("role", "大模型算法架构师 / 负责人 (Staff LLM Algorithm Architect)"),
        "{{LEVEL}}": meta.get("level", "Staff / Principal Level"),
        "{{LOCATION}}": meta.get("location", "北京 / 杭州 / 深圳"),
        "{{COMP_BAND}}": meta.get("comp_band", "150W - 260W RMB"),
        "{{DEPARTMENT}}": meta.get("department", "基础模型与智能体工程部"),
        "{{ARCHITECTURE_LAYER}}": meta.get("architecture_layer", "Foundation Models & Inference Infra"),
        "{{CANDIDATE_NAME}}": match_result.get("candidate_name", "张晨曦 (Dr. Alex Zhang)"),
        "{{REPORT_DATE}}": today_str,

        "{{VERDICT_TITLE_EN}}": verdict.get("title_en", "Strong Go · Benchmark Tier Candidate Match"),
        "{{VERDICT_TITLE_ZH}}": verdict.get("title_zh", "强烈建议投递 (Strong Go) · 标杆级匹配候选人"),
        "{{VERDICT_DESC_EN}}": verdict.get("desc_en", "Candidate achieves benchmark alignment across 1k-GPU cluster engineering and RL alignment."),
        "{{VERDICT_DESC_ZH}}": verdict.get("desc_zh", "候选人在千卡集群训练、纯强化学习推理及高性能推理服务化上达到顶尖水准。"),

        "{{MATCH_SCORE_NUM}}": str(match_score),
        "{{INTERVIEW_PROB_NUM}}": str(interview_prob),
        "{{MATCH_GAUGE_OFFSET}}": str(match_gauge_offset),
        "{{PROB_GAUGE_OFFSET}}": str(prob_gauge_offset),

        "{{MUST_HAVE_SCORE}}": str(breakdown.get("must_have", 98)),
        "{{NICE_HAVE_SCORE}}": str(breakdown.get("nice_have", 98)),
        "{{HIDDEN_FIT_SCORE}}": str(breakdown.get("hidden_fit", 92)),

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
        html = html.replace(key, str(val))

    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
