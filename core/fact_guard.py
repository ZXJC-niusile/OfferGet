"""
OfferGet Fact Verification Guard Module
Strictly anchors tailored resume bullets against candidate SSOT (candidate_profile.json)
to prevent AI hallucination, metric inflation, and ungrounded claims.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ---------------------------------------------------------------------------
# Technology & Version Whitelist & Inflation Lexicons (Centralized SSOT)
# ---------------------------------------------------------------------------
from core.profile_adapter import (
    ProfileEvidenceIndex,
    build_profile_evidence_index,
)
from core.registry import (
    MetricPatternRegistry,
    QualityRuleRegistry,
)

NON_METRIC_TECH_PATTERNS = MetricPatternRegistry.NON_METRIC_TECH_PATTERNS
INFLATION_PATTERNS = QualityRuleRegistry.INFLATION_PATTERNS
FORBIDDEN_BUZZWORDS = QualityRuleRegistry.FORBIDDEN_BUZZWORDS
METRIC_TYPE_TO_TOPICS: Dict[str, Set[str]] = MetricPatternRegistry.METRIC_TYPE_TO_TOPICS



# ---------------------------------------------------------------------------
# FactVerificationGuard Class
# ---------------------------------------------------------------------------

class FactVerificationGuard:
    """
    Fact Verification Guard for tailored resume bullets.
    Anchors claims against SSOT master profile (candidate_profile.json) to detect:
      - METRIC_INFLATION_DRIFT: Claimed number exceeds verified SSOT baseline.
      - UNVERIFIED_NUMERICAL_CLAIM: Number has no factual anchor in SSOT.
    """

    def __init__(self, master_profile: Optional[Union[dict, str, Path]] = None):
        """Initialize the guard with an optional master profile."""
        self.master_profile: Optional[dict] = None
        self.evidence_index: Optional[ProfileEvidenceIndex] = None
        self.baseline_anchors: List[Dict[str, Any]] = []
        self.all_verified_numbers: Set[float] = set()

        if master_profile is not None:
            self.load_profile(master_profile)

    def load_profile(self, master_profile: Union[dict, str, Path]) -> None:
        """Loads and indexes the candidate's Single Source of Truth (SSOT) profile."""
        if isinstance(master_profile, (str, Path)):
            path = Path(master_profile)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self.master_profile = json.load(f)
            else:
                self.master_profile = json.loads(str(master_profile))
        elif isinstance(master_profile, dict):
            self.master_profile = copy.deepcopy(master_profile)
        else:
            raise TypeError(f"Expected dict, str, or Path, got {type(master_profile).__name__}")

        self._index_master_profile()

    def _index_master_profile(self) -> None:
        """Extracts structured metric anchors and verified baseline numbers from SSOT."""
        self.baseline_anchors = []
        self.all_verified_numbers = set()

        if not self.master_profile:
            return

        # 1. Build immutable ProfileEvidenceIndex to unify normalized profile representation
        self.evidence_index = build_profile_evidence_index(self.master_profile)
        norm_profile = self.evidence_index.profile

        # Candidate metadata
        cand = norm_profile.get("candidate", {})
        if isinstance(cand, dict):
            yoe = cand.get("years_of_experience")
            if yoe is not None:
                try:
                    yoe_val = float(yoe)
                    self.baseline_anchors.append({
                        "anchor_id": "candidate:years_of_experience",
                        "topic": "experience_years",
                        "keywords": ["年", "years", "经验", "yoe", "研发经验", "工作经验"],
                        "baseline_value": yoe_val,
                        "baseline_raw": f"{int(yoe_val)}年",
                        "unit": "年",
                        "metric_type": "years"
                    })
                    self.all_verified_numbers.add(yoe_val)
                except (ValueError, TypeError):
                    pass

        # 2. Narrative summaries
        narrative = norm_profile.get("narrative", {})
        if isinstance(narrative, dict):
            for text_key in ["summary_zh", "summary_en"]:
                text = narrative.get(text_key, "")
                if text:
                    self._extract_and_index_text_metrics(text, f"narrative:{text_key}")

        # 3. Experience Highlights & Verified Metrics
        for exp in norm_profile.get("experience", []):

            if not isinstance(exp, dict):
                continue
            for h in exp.get("highlights", []):
                if not isinstance(h, dict):
                    continue
                claim_id = h.get("claim_id", "EXP")
                claim_zh = h.get("claim_zh", "")
                claim_en = h.get("claim_en", "")
                verified_metrics = h.get("verified_metrics", {})

                context_words = self._extract_keywords(f"{claim_zh} {claim_en}")

                # Index explicit verified_metrics dict
                if isinstance(verified_metrics, dict):
                    self._index_verified_metrics_dict(verified_metrics, claim_id, context_words)

                # Index text metrics
                if claim_zh:
                    self._extract_and_index_text_metrics(claim_zh, f"{claim_id}:claim_zh", context_words)
                if claim_en:
                    self._extract_and_index_text_metrics(claim_en, f"{claim_id}:claim_en", context_words)

        # 4. Projects
        for proj in norm_profile.get("projects", []):
            if not isinstance(proj, dict):
                continue
            proj_name = proj.get("name", "Project")
            p_kw = self._extract_keywords(proj_name)

            stars = proj.get("stars")
            if stars is not None:
                try:
                    s_val = float(stars)
                    self.baseline_anchors.append({
                        "anchor_id": f"{proj_name}:stars",
                        "topic": "stars",
                        "keywords": list(p_kw | {"star", "stars", "星", "关注", "标星"}),
                        "baseline_value": s_val,
                        "baseline_raw": f"{int(s_val)} stars",
                        "unit": "stars",
                        "metric_type": "stars"
                    })
                    self.all_verified_numbers.add(s_val)
                except (ValueError, TypeError):
                    pass

            for desc_k in ["description_zh", "description_en"]:
                d_text = proj.get(desc_k, "")
                if d_text:
                    self._extract_and_index_text_metrics(d_text, f"{proj_name}:{desc_k}", p_kw)

        # 5. Publications
        for pub in norm_profile.get("publications", []):
            if isinstance(pub, dict):
                p_text = f"{pub.get('title', '')} {pub.get('highlight', '')}"
                self._extract_and_index_text_metrics(p_text, "publications")

        # 6. Constraints / Compute Floor
        constraints = self.master_profile.get("constraints_and_assumptions", {}) or norm_profile.get("constraints_and_assumptions", {})

        if isinstance(constraints, dict):
            compute_floor = constraints.get("compute_floor", "")
            if compute_floor:
                self._extract_and_index_text_metrics(compute_floor, "constraints:compute_floor")

    def _extract_keywords(self, text: str) -> Set[str]:
        """Extracts searchable tokens from text."""
        tokens = set(re.findall(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fa5]{2,4}", text))
        return {t.lower() for t in tokens if len(t) > 1}

    def _index_verified_metrics_dict(
        self, verified_metrics: Dict[str, Any], claim_id: str, context_keywords: Set[str]
    ) -> None:
        """Indexes explicit verified_metrics key-values into structured anchors."""
        for key, val in verified_metrics.items():
            val_str = str(val).strip()

            # 1. Cluster size (e.g. 1024)
            if "cluster" in key or key == "cluster_size":
                m = re.search(r"(\d+)", val_str)
                if m:
                    num = float(m.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "cluster_size",
                        "keywords": list(context_keywords | {"卡", "gpu", "gpus", "h800", "h100", "集群", "cluster", "node", "节点"}),
                        "baseline_value": num,
                        "baseline_raw": f"{int(num)} 卡",
                        "unit": "卡",
                        "metric_type": "cluster_size"
                    })
                    self.all_verified_numbers.add(num)

            # 2. MFU metrics (e.g. mfu_before: 38.5%, mfu_after: 54.2%)
            elif "mfu" in key:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                if m:
                    num = float(m.group(1))
                    subtopic = "mfu_before" if "before" in key else "mfu_after"
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "mfu",
                        "subtopic": subtopic,
                        "keywords": list(context_keywords | {"mfu", "flops", "utilization", "利用率", "算力利用率"}),
                        "baseline_value": num,
                        "baseline_raw": f"{num}%",
                        "unit": "%",
                        "metric_type": "percentage"
                    })
                    self.all_verified_numbers.add(num)

            # 3. Downtime metrics (e.g. downtime_before: 2.4h/day, downtime_after: <8min/day)
            elif "downtime" in key:
                if "before" in key:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|h|hours?)", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self.baseline_anchors.append({
                            "anchor_id": f"{claim_id}:{key}",
                            "topic": "downtime_before",
                            "keywords": list(context_keywords | {"downtime", "中断", "故障", "有效中断", "日均中断", "慢卡", "慢节点"}),
                            "baseline_value": num,
                            "baseline_raw": f"{num} 小时",
                            "unit": "小时",
                            "metric_type": "time_hours"
                        })
                        self.all_verified_numbers.add(num)
                else:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:分钟|min|minutes?)", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self.baseline_anchors.append({
                            "anchor_id": f"{claim_id}:{key}",
                            "topic": "downtime_after",
                            "keywords": list(context_keywords | {"downtime", "中断", "故障", "压减至", "以内"}),
                            "baseline_value": num,
                            "baseline_raw": f"{num} 分钟",
                            "unit": "分钟",
                            "metric_type": "time_minutes"
                        })
                        self.all_verified_numbers.add(num)

            # 4. Uptime (e.g. 99.4%)
            elif "uptime" in key or "availability" in key:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                if m:
                    num = float(m.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "uptime",
                        "keywords": list(context_keywords | {"uptime", "可用率", "训练可用率", "在线率"}),
                        "baseline_value": num,
                        "baseline_raw": f"{num}%",
                        "unit": "%",
                        "metric_type": "percentage"
                    })
                    self.all_verified_numbers.add(num)

            # 5. Annual Savings / Compute Cost (e.g. 38,000,000 RMB / 3800 万元)
            elif "savings" in key or "annual_savings" in key:
                # Dynamically parse value and unit from val_str
                # e.g., "38,000,000 RMB" -> 3800.0 万元 (normalized to 万元 for comparison) or "3800 万元"
                raw_num = val_str.replace(",", "").strip()
                m_curr = re.search(r"(\d+(?:\.\d+)?)\s*(万元|万|亿元|M\s*RMB|m\s*rmb|million\s*rmb|RMB|usd|美元)?", raw_num, re.IGNORECASE)
                if m_curr:
                    amount = float(m_curr.group(1))
                    curr_unit = (m_curr.group(2) or "").strip().lower()
                    # Normalize to 万元
                    if "亿" in curr_unit:
                        baseline_wan = amount * 10000.0
                    elif "million" in curr_unit or "m rmb" in curr_unit or curr_unit.startswith("m"):
                        # e.g. 38M RMB, 38m -> 38 * 100 = 3800 万元
                        baseline_wan = amount * 100.0
                    elif "万" in curr_unit:
                        baseline_wan = amount
                    elif amount >= 10000.0:  # e.g. 38,000,000 RMB -> 3800 万元
                        baseline_wan = amount / 10000.0
                    else:
                        baseline_wan = amount

                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "savings",
                        "keywords": list(context_keywords | {"节省", "降本", "成本", "开销", "savings", "cost", "算力开销", "云算力", "万元"}),
                        "baseline_value": baseline_wan,
                        "baseline_raw": f"{int(baseline_wan) if baseline_wan.is_integer() else baseline_wan} 万元",
                        "unit": "万元",
                        "metric_type": "currency"
                    })
                    self.all_verified_numbers.add(baseline_wan)
                    self.all_verified_numbers.add(amount)
                    if baseline_wan > 0:
                        self.all_verified_numbers.add(baseline_wan * 10000.0)
                        self.all_verified_numbers.add(baseline_wan / 100.0)

            elif "cost" in key:
                m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                if m_pct:
                    num = float(m_pct.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "cost_reduction",
                        "keywords": list(context_keywords | {"成本", "降本", "cost", "单token"}),
                        "baseline_value": num,
                        "baseline_raw": f"{num}%",
                        "unit": "%",
                        "metric_type": "percentage"
                    })
                    self.all_verified_numbers.add(num)

            # 6. Latency / TTFT metrics
            elif "latency" in key:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                if m:
                    num = float(m.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "latency_reduction",
                        "keywords": list(context_keywords | {"延迟", "latency", "p99", "p99延迟"}),
                        "baseline_value": num,
                        "baseline_raw": f"{num}%",
                        "unit": "%",
                        "metric_type": "percentage"
                    })
                    self.all_verified_numbers.add(num)

            elif "ttft" in key:
                if "before" in key:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|s|sec)", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self.baseline_anchors.append({
                            "anchor_id": f"{claim_id}:{key}",
                            "topic": "ttft_before",
                            "keywords": list(context_keywords | {"ttft", "首字", "首字响应", "首字延迟"}),
                            "baseline_value": num,
                            "baseline_raw": f"{num}s",
                            "unit": "s",
                            "metric_type": "time_s"
                        })
                        self.all_verified_numbers.add(num)
                else:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*ms", val_str, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        self.baseline_anchors.append({
                            "anchor_id": f"{claim_id}:{key}",
                            "topic": "ttft_after",
                            "keywords": list(context_keywords | {"ttft", "首字", "首字响应", "首字延迟"}),
                            "baseline_value": num,
                            "baseline_raw": f"{int(num)}ms",
                            "unit": "ms",
                            "metric_type": "time_ms"
                        })
                        self.all_verified_numbers.add(num)

            # 7. Time saved (e.g. 3 weeks)
            elif "time" in key:
                m = re.search(r"(\d+)\s*(?:周|weeks?)", val_str, re.IGNORECASE)
                if m:
                    num = float(m.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "time_saved",
                        "keywords": list(context_keywords | {"提前", "节省时间", "周", "weeks", "里程碑"}),
                        "baseline_value": num,
                        "baseline_raw": f"{int(num)} 周",
                        "unit": "周",
                        "metric_type": "time_weeks"
                    })
                    self.all_verified_numbers.add(num)

            # 8. VRAM Reduction & Benchmark gains
            elif "vram" in key or "memory" in key:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                if m:
                    num = float(m.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "vram_reduction",
                        "keywords": list(context_keywords | {"显存", "vram", "显存消耗", "memory"}),
                        "baseline_value": num,
                        "baseline_raw": f"{num}%",
                        "unit": "%",
                        "metric_type": "percentage"
                    })
                    self.all_verified_numbers.add(num)

            elif "gsm8k" in key:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                if m:
                    num = float(m.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "gsm8k_gain",
                        "keywords": list(context_keywords | {"gsm8k", "数学", "推理", "准确率"}),
                        "baseline_value": num,
                        "baseline_raw": f"{num}%",
                        "unit": "%",
                        "metric_type": "percentage"
                    })
                    self.all_verified_numbers.add(num)

            elif "math" in key:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", val_str)
                if m:
                    num = float(m.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:{key}",
                        "topic": "math_gain",
                        "keywords": list(context_keywords | {"math", "代码推理", "准确率"}),
                        "baseline_value": num,
                        "baseline_raw": f"{num}%",
                        "unit": "%",
                        "metric_type": "percentage"
                    })
                    self.all_verified_numbers.add(num)

            # Model params (e.g. 230B MoE, 64B, 32B)
            elif "model_params" in key or "params" in key:
                for pm in re.finditer(r"(\d+)\s*[bB]", val_str):
                    p_num = float(pm.group(1))
                    self.baseline_anchors.append({
                        "anchor_id": f"{claim_id}:model_param_{int(p_num)}B",
                        "topic": "model_params",
                        "keywords": list(context_keywords | {"参数", "dense", "moe", "基座大模型"}),
                        "baseline_value": p_num,
                        "baseline_raw": f"{int(p_num)}B",
                        "unit": "B",
                        "metric_type": "model_param"
                    })
                    self.all_verified_numbers.add(p_num)

    def _extract_and_index_text_metrics(
        self, text: str, source_id: str, extra_keywords: Optional[Set[str]] = None
    ) -> None:
        """Scans arbitrary narrative or description text to index all verified numbers."""
        kw = self._extract_keywords(text)
        if extra_keywords:
            kw.update(extra_keywords)

        extracted = self._extract_raw_metrics_from_text(text)
        for m in extracted:
            self.all_verified_numbers.add(m["value"])
            self.baseline_anchors.append({
                "anchor_id": f"{source_id}:{m['raw']}",
                "topic": m.get("type", "generic"),
                "keywords": list(kw),
                "baseline_value": m["value"],
                "baseline_raw": m["raw"],
                "unit": m.get("unit", ""),
                "metric_type": m.get("type", "generic")
            })

    def _extract_raw_metrics_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts all quantified numerical metrics from a text string using regex.
        Filters out non-metric technical identifiers (C++20, FlashAttention-2, ZeRO-3, etc.).
        Delegates to MetricPatternRegistry.extract_raw_metrics (SSOT).
        """
        return MetricPatternRegistry.extract_raw_metrics(text)


    def verify_facts(
        self, tailored_text_or_dict: Union[str, dict, list], master_profile: Optional[dict] = None
    ) -> dict:
        """
        Inspects tailored resume bullets or text against master profile.

        Returns:
            dict containing:
              - passed: bool (True if zero drifts and zero ungrounded metrics)
              - score: float (0 - 100)
              - drifts: list of detected metric exaggerations (bullet, claimed_metric, verified_baseline)
              - unverified_claims: list of ungrounded numbers
              - verified_bullets: list of bullets that passed verification
              - verdict: 'FACT_CHECK_PASSED' or 'FACT_DRIFT_DETECTED'
        """
        if master_profile is not None:
            self.load_profile(master_profile)

        if not self.master_profile:
            raise ValueError("Master profile is required for fact verification.")

        bullets = self._extract_bullets(tailored_text_or_dict)

        drifts: List[Dict[str, Any]] = []
        unverified_claims: List[Dict[str, Any]] = []
        verified_bullets: List[str] = []

        for bullet in bullets:
            bullet_clean = bullet.strip()
            if not bullet_clean:
                continue

            bullet_drifts, bullet_unverified = self._verify_single_bullet(bullet_clean)

            if bullet_drifts:
                drifts.extend(bullet_drifts)
            if bullet_unverified:
                unverified_claims.extend(bullet_unverified)

            if not bullet_drifts and not bullet_unverified:
                verified_bullets.append(bullet_clean)

        passed = (len(drifts) == 0 and len(unverified_claims) == 0)
        verdict = "FACT_CHECK_PASSED" if passed else "FACT_DRIFT_DETECTED"

        score = 100.0
        if not passed:
            penalty = len(drifts) * 25.0 + len(unverified_claims) * 15.0
            score = max(0.0, round(100.0 - penalty, 1))

        return {
            "passed": passed,
            "score": score,
            "drifts": drifts,
            "unverified_claims": unverified_claims,
            "verified_bullets": verified_bullets,
            "verdict": verdict,
            "summary": {
                "total_bullets_checked": len(bullets),
                "verified_bullets_count": len(verified_bullets),
                "drift_count": len(drifts),
                "unverified_claims_count": len(unverified_claims)
            }
        }

    def _verify_single_bullet(
        self, bullet: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Verifies all numerical assertions in a single bullet point against SSOT baseline."""
        bullet_drifts: List[Dict[str, Any]] = []
        bullet_unverified: List[Dict[str, Any]] = []

        metrics = self._extract_raw_metrics_from_text(bullet)
        if not metrics:
            return bullet_drifts, bullet_unverified

        for met in metrics:
            val = met["value"]
            raw_str = met["raw"]
            met_type = met.get("type", "")

            anchor = self._find_matching_anchor(met, bullet)

            if anchor is not None:
                is_drift, baseline_str = self._check_metric_drift(met, anchor)
                if is_drift:
                    bullet_drifts.append({
                        "bullet": bullet,
                        "claimed_metric": raw_str,
                        "verified_baseline": baseline_str,
                        "metric_type": anchor.get("topic", met_type)
                    })
            else:
                # Check if exact number exists in SSOT
                if val in self.all_verified_numbers:
                    continue

                # No anchor and number not verified -> UNVERIFIED_NUMERICAL_CLAIM
                bullet_unverified.append({
                    "bullet": bullet,
                    "claimed_metric": raw_str,
                    "reason": "Numerical metric has no corresponding anchor in SSOT profile"
                })

        return bullet_drifts, bullet_unverified

    def _find_matching_anchor(
        self, metric: Dict[str, Any], bullet_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the corresponding SSOT anchor for a metric using local window context and type checking.
        """
        met_type = metric.get("type", "")
        allowed_topics = METRIC_TYPE_TO_TOPICS.get(met_type, set())
        if not allowed_topics:
            return None

        # Extract local context around metric
        start = metric.get("start", 0)
        end = metric.get("end", len(bullet_text))
        window_start = max(0, start - 30)
        window_end = min(len(bullet_text), end + 30)
        local_window = bullet_text[window_start:window_end].lower()
        bullet_lower = bullet_text.lower()

        # Immediate prefix window (preceding 15 chars) to determine before vs after direction
        prefix_window = bullet_text[max(0, start - 15):start].lower()

        is_before_context = bool(re.search(r"(?:从|起始|from)\s*$", prefix_window))
        is_after_context = bool(re.search(r"(?:至|到|压减至|优化至|提升至|达到|下降至|boost|to)\s*$", prefix_window))

        best_anchor = None
        best_score = 0

        for anchor in self.baseline_anchors:
            topic = anchor.get("topic", "")
            if topic not in allowed_topics:
                continue

            score = 1  # Base score for matching type

            # Keyword matching in local window and full bullet
            anchor_kw = anchor.get("keywords", [])
            for kw in anchor_kw:
                kw_l = kw.lower()
                if kw_l in local_window:
                    score += 5
                elif kw_l in bullet_lower:
                    score += 2

            # Subtopic discrimination for before vs after
            subtopic = anchor.get("subtopic")
            if subtopic == "mfu_before":
                if is_before_context:
                    score += 15
                elif is_after_context:
                    score -= 10
            elif subtopic == "mfu_after":
                if is_after_context:
                    score += 15
                elif is_before_context:
                    score -= 10
            elif topic == "downtime_before":
                if is_before_context:
                    score += 15
                elif is_after_context:
                    score -= 10
            elif topic == "downtime_after":
                if is_after_context:
                    score += 15
                elif is_before_context:
                    score -= 10
            elif topic == "ttft_before":
                if is_before_context:
                    score += 15
                elif is_after_context:
                    score -= 10
            elif topic == "ttft_after":
                if is_after_context:
                    score += 15
                elif is_before_context:
                    score -= 10

            # Specific topic keywords affinity
            if met_type == "percentage":
                if "gsm8k" in local_window and topic == "gsm8k_gain":
                    score += 20
                elif "math" in local_window and topic == "math_gain":
                    score += 20
                elif ("显存" in local_window or "vram" in local_window) and topic == "vram_reduction":
                    score += 20
                elif ("p99" in local_window or "延迟" in local_window) and topic == "latency_reduction":
                    score += 20
                elif ("单token" in local_window or "成本" in local_window) and topic == "cost_reduction":
                    score += 20
                elif ("可用率" in local_window or "uptime" in local_window) and topic == "uptime":
                    score += 20
                elif "mfu" in local_window and topic == "mfu":
                    score += 20

            # Unit match bonus
            if metric.get("unit") and metric.get("unit") == anchor.get("unit"):
                score += 3

            if score > best_score:
                best_score = score
                best_anchor = anchor

        return best_anchor if best_score >= 3 else None

    def _check_metric_drift(
        self, claimed_metric: Dict[str, Any], anchor: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Determines whether claimed metric represents an inflation drift."""
        claimed_val = claimed_metric["value"]
        baseline_val = anchor["baseline_value"]
        baseline_raw = anchor.get("baseline_raw", str(baseline_val))
        topic = anchor.get("topic", "")

        # Allow small floating point rounding tolerance
        if abs(claimed_val - baseline_val) < 0.2:
            return False, baseline_raw

        # Model params: check if exact match or exceeding verified max
        if topic == "model_params":
            if claimed_val in self.all_verified_numbers:
                return False, baseline_raw
            if claimed_val > baseline_val:
                return True, baseline_raw

        # MFU
        elif topic == "mfu":
            if claimed_val > baseline_val + 0.2:
                return True, baseline_raw

        # Cluster size
        elif topic == "cluster_size":
            if claimed_val > baseline_val:
                return True, baseline_raw

        # Downtime before
        elif topic == "downtime_before":
            if claimed_val > baseline_val:
                return True, baseline_raw

        # Downtime after
        elif topic == "downtime_after":
            # If claimed downtime after is worse than baseline (e.g. baseline 8 min, claimed 20 min)
            if claimed_val > baseline_val:
                return True, baseline_raw

        # Annual Savings
        elif topic == "savings":
            if claimed_val > baseline_val:
                return True, baseline_raw

        # Percentage reductions / gains
        elif topic in ("latency_reduction", "cost_reduction", "vram_reduction", "gsm8k_gain", "math_gain", "uptime"):
            if claimed_val > baseline_val + 0.2:
                return True, baseline_raw

        # Experience years & stars
        elif topic in ("experience_years", "stars"):
            if claimed_val > baseline_val:
                return True, baseline_raw

        elif claimed_val > baseline_val:
            return True, baseline_raw

        return False, baseline_raw

    def _extract_bullets(self, tailored_text_or_dict: Union[str, dict, list]) -> List[str]:
        """Extracts individual bullet lines from string, dict, or list input."""
        bullets: List[str] = []

        if isinstance(tailored_text_or_dict, list):
            for item in tailored_text_or_dict:
                bullets.extend(self._extract_bullets(item))
            return bullets

        if isinstance(tailored_text_or_dict, dict):
            if "bullets" in tailored_text_or_dict and isinstance(tailored_text_or_dict["bullets"], list):
                return self._extract_bullets(tailored_text_or_dict["bullets"])

            for exp in tailored_text_or_dict.get("experience", []):
                if isinstance(exp, dict):
                    for h in exp.get("highlights", []):
                        if isinstance(h, dict):
                            if h.get("claim_zh"):
                                bullets.append(h["claim_zh"])
                            if h.get("claim_en"):
                                bullets.append(h["claim_en"])
                        elif isinstance(h, str):
                            bullets.append(h)

            narrative = tailored_text_or_dict.get("narrative", {})
            if isinstance(narrative, dict):
                for k in ["summary_zh", "summary_en"]:
                    if narrative.get(k):
                        bullets.append(narrative[k])

            for p in tailored_text_or_dict.get("projects", []):
                if isinstance(p, dict):
                    for k in ["description_zh", "description_en"]:
                        if p.get(k):
                            bullets.append(p[k])

            return bullets

        # Plain text or markdown
        text = str(tailored_text_or_dict).strip()
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            clean = re.sub(r"^[-*•·▪▫►✔✓\d\.\)]+\s*", "", s).strip()
            if clean:
                bullets.append(clean)

        return bullets


# ---------------------------------------------------------------------------
# Top-Level Convenience Function
# ---------------------------------------------------------------------------

def verify_resume_facts(
    tailored_text_or_dict: Union[str, dict, list], master_profile: Union[dict, str, Path]
) -> dict:
    """
    Convenience function to verify tailored resume bullets against SSOT master profile.

    Args:
        tailored_text_or_dict: Resume text, list of bullets, or resume profile dictionary.
        master_profile: SSOT candidate_profile.json dictionary or filepath.

    Returns:
        dict with verification report: passed, score, drifts, unverified_claims, verified_bullets, verdict.
    """
    guard = FactVerificationGuard(master_profile)
    return guard.verify_facts(tailored_text_or_dict)
