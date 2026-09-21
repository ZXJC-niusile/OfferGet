#!/usr/bin/env python3
"""ApexResume Deterministic Verification & Anti-Inflation Audit Engine.

Performs mathematical recalculation, role strength gating, verb hierarchy checking,
data depth & outcome evidence tiering, static HTML quality inspection, and
source draft sandbox anti-hallucination verification without relying on probabilistic LLM outputs.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


@dataclass
class Finding:
    category: str  # "math", "role", "verb", "depth", "result", "html", "inflation", "sandbox"
    severity: str  # "critical", "warning", "info"
    message: str
    target: str
    details: Dict[str, Any] = field(default_factory=dict)


# Import SSOT QualityRuleRegistry from OfferGet
try:
    from core.registry import QualityRuleRegistry
except ImportError:
    import importlib.util
    _offerget_root = Path(__file__).resolve().parent.parent.parent
    _registry_path = _offerget_root / "core" / "registry.py"
    if _registry_path.exists():
        spec = importlib.util.spec_from_file_location("offerget_core_registry", str(_registry_path))
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        QualityRuleRegistry = _mod.QualityRuleRegistry
    else:
        raise

ROLE_RANKS = QualityRuleRegistry.ROLE_RANKS
VERB_HIERARCHY = QualityRuleRegistry.VERB_HIERARCHY
STRONG_VERBS_THRESHOLD = QualityRuleRegistry.STRONG_VERBS_THRESHOLD
DECISION_PLANNING_KEYWORDS = QualityRuleRegistry.DECISION_PLANNING_KEYWORDS
DATA_DEPTH_LEVELS = QualityRuleRegistry.DATA_DEPTH_LEVELS
RESULT_EVIDENCE_LEVELS = QualityRuleRegistry.RESULT_EVIDENCE_LEVELS
COMPLETED_VERBS_FORBIDDEN_IN_PLANNING = QualityRuleRegistry.COMPLETED_VERBS_FORBIDDEN_IN_PLANNING
SUPERLATIVES = QualityRuleRegistry.SUPERLATIVES


class ResumeAuditor:
    """Deterministic validation engine for resume claims and HTML outputs."""

    def __init__(self):
        self.findings: List[Finding] = []
        self.depth_counts: Dict[str, int] = {k: 0 for k in DATA_DEPTH_LEVELS}
        self.result_counts: Dict[str, int] = {k: 0 for k in RESULT_EVIDENCE_LEVELS}

    def clear(self):
        self.findings.clear()
        self.depth_counts = {k: 0 for k in DATA_DEPTH_LEVELS}
        self.result_counts = {k: 0 for k in RESULT_EVIDENCE_LEVELS}

    # -------------------------------------------------------------------------
    # 1. Mathematical Recalculation
    # -------------------------------------------------------------------------
    def check_metrics(self, claim_id: str, text: str, metric: Dict[str, Any]):
        """Verifies mathematical consistency of numbers, ratios, and percentages."""
        # 1. Ratio check (numerator / denominator)
        num = metric.get("numerator")
        den = metric.get("denominator")
        disp_pct = metric.get("displayed_percent")

        if num is not None and den is not None:
            if den == 0:
                self.findings.append(Finding(
                    category="math",
                    severity="critical",
                    message=f"Zero denominator in claim {claim_id}: {num}/{den}",
                    target=claim_id,
                ))
            else:
                calc_pct = (num / den) * 100
                if disp_pct is not None:
                    diff = abs(calc_pct - disp_pct)
                    if diff > 0.5:
                        self.findings.append(Finding(
                            category="math",
                            severity="critical",
                            message=(
                                f"Percentage discrepancy in {claim_id}: displayed {disp_pct}%, "
                                f"but calculated ({num}/{den}) = {calc_pct:.2f}% (diff {diff:.2f}%)"
                            ),
                            target=claim_id,
                            details={"calculated": calc_pct, "displayed": disp_pct}
                        ))

        # 2. Relative change vs Percentage point change
        baseline = metric.get("baseline")
        result = metric.get("result")
        reported_change = metric.get("reported_change_percent")
        change_type = metric.get("change_type", "relative")  # "relative" or "percentage_points"

        if baseline is not None and result is not None and reported_change is not None:
            if baseline == 0 and change_type == "relative":
                self.findings.append(Finding(
                    category="math",
                    severity="critical",
                    message=f"Relative percentage change with zero baseline in {claim_id}",
                    target=claim_id,
                ))
            elif baseline != 0:
                calc_rel = ((result - baseline) / baseline) * 100
                calc_pp = result - baseline

                if change_type == "relative":
                    diff = abs(calc_rel - reported_change)
                    if diff > 0.5:
                        # Check if user confused percentage points with relative percent
                        if abs(calc_pp - reported_change) <= 0.5:
                            self.findings.append(Finding(
                                category="math",
                                severity="critical",
                                message=(
                                    f"Confused percentage points with relative change in {claim_id}: "
                                    f"change from {baseline}% to {result}% is {calc_pp:+.1f} percentage points, "
                                    f"NOT a {reported_change}% relative increase (relative is {calc_rel:+.1f}%)"
                                ),
                                target=claim_id,
                            ))
                        else:
                            self.findings.append(Finding(
                                category="math",
                                severity="critical",
                                message=f"Relative change discrepancy in {claim_id}: expected {calc_rel:.2f}%, got {reported_change}%",
                                target=claim_id,
                            ))
                elif change_type == "percentage_points":
                    diff = abs(calc_pp - reported_change)
                    if diff > 0.5:
                        self.findings.append(Finding(
                            category="math",
                            severity="critical",
                            message=f"Percentage points discrepancy in {claim_id}: expected {calc_pp:.2f}pp, got {reported_change}pp",
                            target=claim_id,
                        ))

    # -------------------------------------------------------------------------
    # 2. Role Strength & Scope Boundaries
    # -------------------------------------------------------------------------
    def detect_role_rank(self, text: str) -> Tuple[Optional[int], Optional[str]]:
        """Finds role rank using longest-prefix matching to avoid substring collision."""
        lower = text.lower()
        sorted_keys = sorted(ROLE_RANKS.keys(), key=lambda k: len(k), reverse=True)
        for k in sorted_keys:
            if k.lower() in lower:
                return ROLE_RANKS[k], k
        return None, None

    def check_role_integrity(self, claim_id: str, claim: Dict[str, Any]):
        """Verifies role level against stated facts and tense constraints."""
        text = claim.get("text", "")
        role_claimed = claim.get("role_claimed", "")
        ground_truth_level = claim.get("ground_truth_role_level")  # 0, 1, 2, 3
        scope = claim.get("scope", "")

        claimed_rank, matched_term = self.detect_role_rank(role_claimed or text)

        # Check Rank 0: Planning tense violation
        if claimed_rank == 0 or claim.get("status") == "planned":
            for bad_word in COMPLETED_VERBS_FORBIDDEN_IN_PLANNING:
                if bad_word in text:
                    self.findings.append(Finding(
                        category="role",
                        severity="critical",
                        message=(
                            f"Tense violation in planned claim {claim_id}: uses completed word '{bad_word}' "
                            f"for a planned/exploratory item"
                        ),
                        target=claim_id,
                    ))

        # Check role elevation against ground truth
        if ground_truth_level is not None and claimed_rank is not None:
            if claimed_rank > ground_truth_level:
                self.findings.append(Finding(
                    category="role",
                    severity="critical",
                    message=(
                        f"Role elevation in {claim_id}: actual level is {ground_truth_level}, "
                        f"but claimed rank is {claimed_rank} ('{matched_term}')"
                    ),
                    target=claim_id,
                ))

        # Check Rank 3: Independent Owner requires strictly bounded scope
        if claimed_rank == 3 and not scope:
            self.findings.append(Finding(
                category="role",
                severity="warning",
                message=(
                    f"Unbounded owner scope in {claim_id}: claimed independent owner / from 0 to 1, "
                    f"but missing a strictly bounded minimal scope (e.g., '限定于评测流水线闭环')"
                ),
                target=claim_id,
            ))

    # -------------------------------------------------------------------------
    # 2.1 Verb Hierarchy Checking (支持/协助 < 参与 < 负责 < 推动 < 主导)
    # -------------------------------------------------------------------------
    def detect_verb_level(self, text: str) -> Tuple[Optional[int], Optional[str]]:
        """Detects verb level using longest-match first."""
        lower = text.lower()
        sorted_verbs = sorted(VERB_HIERARCHY.keys(), key=lambda k: len(k), reverse=True)
        for v in sorted_verbs:
            if v.lower() in lower:
                return VERB_HIERARCHY[v], v
        return None, None

    def check_verb_hierarchy(self, claim_id: str, claim: Dict[str, Any]):
        """Checks verb level hierarchy and validates evidence for strong verbs (推动, 主导)."""
        text = claim.get("text", "")
        verb_claimed = claim.get("verb") or claim.get("role_claimed") or ""

        # 1. Detect verb level
        level, matched_verb = self.detect_verb_level(verb_claimed)
        if level is None:
            level, matched_verb = self.detect_verb_level(text)

        # 2. Check verb level elevation if ground truth verb level provided
        gt_verb_level = claim.get("ground_truth_verb_level")
        if gt_verb_level is not None and level is not None:
            if level > gt_verb_level:
                self.findings.append(Finding(
                    category="verb",
                    severity="critical",
                    message=(
                        f"Verb hierarchy elevation in {claim_id}: ground truth is Level {gt_verb_level}, "
                        f"but claimed Level {level} ('{matched_verb}')"
                    ),
                    target=claim_id,
                    details={"claimed_level": level, "ground_truth": gt_verb_level, "verb": matched_verb}
                ))

        # 3. Check strong verb without scheme decision/planning evidence
        if level is not None and level >= STRONG_VERBS_THRESHOLD:
            has_decision = (
                claim.get("has_decision_evidence") is True
                or bool(claim.get("decision_evidence"))
                or claim.get("has_planning_evidence") is True
                or bool(claim.get("planning_evidence"))
                or any(kw in text.lower() for kw in DECISION_PLANNING_KEYWORDS)
            )
            if not has_decision:
                self.findings.append(Finding(
                    category="verb",
                    severity="warning",
                    message=(
                        f"Strong verb '{matched_verb}' (Level {level}) used in {claim_id} without explicit "
                        f"scheme decision or planning evidence. Risk of being challenged during technical defense."
                    ),
                    target=claim_id,
                    details={"verb": matched_verb, "level": level}
                ))

    # -------------------------------------------------------------------------
    # 2.2 Data Depth (D0-D4) & Result Evidence (R0-R3) Level Auditing
    # -------------------------------------------------------------------------
    def check_depth_and_result_levels(self, claim_id: str, claim: Dict[str, Any]):
        """Validates data analysis depth (D0-D4) and result evidence levels (R0-R3)."""
        text = claim.get("text", "")

        # Depth level
        depth = claim.get("data_depth_level") or claim.get("depth_level")
        if depth:
            depth_str = str(depth).upper()
            if depth_str not in DATA_DEPTH_LEVELS:
                self.findings.append(Finding(
                    category="depth",
                    severity="warning",
                    message=f"Invalid data analysis depth level '{depth}' in {claim_id}. Must be one of D0-D4.",
                    target=claim_id,
                ))
            else:
                self.depth_counts[depth_str] = self.depth_counts.get(depth_str, 0) + 1
                if depth_str in ("D3", "D4"):
                    methodology_kws = [
                        "预测", "因果", "建模", "优化", "强化学习", "运筹", "自适应",
                        "did", "psm", "回归", "评估模型", "策略网络", "grpo", "ppo", "dpo", "uplift"
                    ]
                    if not any(k in text.lower() for k in methodology_kws):
                        self.findings.append(Finding(
                            category="depth",
                            severity="warning",
                            message=(
                                f"High data depth {depth_str} claimed in {claim_id} without explicit "
                                f"predictive/prescriptive methodology in text."
                            ),
                            target=claim_id,
                            details={"depth_level": depth_str}
                        ))

        # Result level
        result = claim.get("result_evidence_level") or claim.get("result_level")
        if result:
            result_str = str(result).upper()
            if result_str not in RESULT_EVIDENCE_LEVELS:
                self.findings.append(Finding(
                    category="result",
                    severity="warning",
                    message=f"Invalid result evidence level '{result}' in {claim_id}. Must be one of R0-R3.",
                    target=claim_id,
                ))
            else:
                self.result_counts[result_str] = self.result_counts.get(result_str, 0) + 1
                if result_str == "R0":
                    prod_words = ["已上线", "生产环境", "全量", "线上", "降本"]
                    for pw in prod_words:
                        if pw in text:
                            self.findings.append(Finding(
                                category="result",
                                severity="warning",
                                message=f"R0 (Theoretical) claim {claim_id} asserts production term '{pw}' in text.",
                                target=claim_id,
                                details={"result_level": result_str, "term": pw}
                            ))
                            break
                elif result_str in ("R2", "R3"):
                    metric = claim.get("metric")
                    has_num = bool(re.search(r'\d+(?:\.\d+)?%?', text))
                    if not metric and not has_num:
                        self.findings.append(Finding(
                            category="result",
                            severity="warning",
                            message=f"Production result {result_str} in {claim_id} lacks quantitative metrics or baseline comparison.",
                            target=claim_id,
                            details={"result_level": result_str}
                        ))

    # -------------------------------------------------------------------------
    # 3. Static HTML Quality & Template Scanning
    # -------------------------------------------------------------------------
    def audit_html_file(self, html_path: str | Path):
        """Audits HTML file for unverified placeholders, naked links, and formatting bugs."""
        path = Path(html_path)
        if not path.exists():
            self.findings.append(Finding(
                category="html",
                severity="critical",
                message=f"Target HTML file does not exist: {path}",
                target=str(path),
            ))
            return

        content = path.read_text(encoding="utf-8")

        # 1. Unconfirmed placeholders (.todo, {{...}}, [待定])
        todo_matches = re.findall(r'<span[^>]*class="[^"]*todo[^"]*"[^>]*>(.*?)</span>', content, re.IGNORECASE | re.DOTALL)
        if todo_matches:
            self.findings.append(Finding(
                category="html",
                severity="critical",
                message=f"Found {len(todo_matches)} unconfirmed '<span class=\"todo\">' placeholders in HTML",
                target=str(path),
                details={"todos": [t.strip() for t in todo_matches[:5]]}
            ))

        jinja_matches = re.findall(r'\{\{([^\}]+)\}\}', content)
        if jinja_matches:
            self.findings.append(Finding(
                category="html",
                severity="critical",
                message=f"Found {len(jinja_matches)} unrendered template placeholders: {jinja_matches[:3]}",
                target=str(path),
            ))

        # 2. Naked URLs (e.g. github.com/xxx not wrapped in <a href>)
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
        body_text = body_match.group(1) if body_match else content

        # Strip all existing <a> tags first
        stripped_body = re.sub(r'<a\s+[^>]*>.*?</a>', '', body_text, flags=re.DOTALL | re.IGNORECASE)
        naked_urls = re.findall(r'(?:https?://|github\.com/)[^\s<"\']+', stripped_body)
        if naked_urls:
            self.findings.append(Finding(
                category="html",
                severity="warning",
                message=f"Found {len(naked_urls)} naked URL(s) without anchor link: {naked_urls[:3]}",
                target=str(path),
            ))

        # 3. Overly long bold spans (>40 chars)
        bold_matches = re.findall(r'<(?:b|strong)\b[^>]*>(.*?)</(?:b|strong)>', content, re.DOTALL | re.IGNORECASE)
        for b in bold_matches:
            plain_b = re.sub(r'<[^>]+>', '', b).strip()
            if len(plain_b) >= 40:
                self.findings.append(Finding(
                    category="html",
                    severity="warning",
                    message=f"Overly long bold span ({len(plain_b)} chars): '{plain_b[:35]}...'. Bolding should be reserved for key metrics and hotwords.",
                    target=str(path),
                ))

        # 4. Superlatives check
        for sup in SUPERLATIVES:
            if sup in body_text:
                self.findings.append(Finding(
                    category="inflation",
                    severity="warning",
                    message=f"Extreme superlative '{sup}' detected without bounding qualifiers. Risk of being challenged during interview.",
                    target=str(path),
                ))

    # -------------------------------------------------------------------------
    # 3.1 Entity & Number Source Sandbox Anti-Hallucination Verification
    # -------------------------------------------------------------------------
    def audit_source_sandbox(self, html_path: str | Path, source_text_path: str | Path) -> Dict[str, Any]:
        """Audits generated HTML against raw source text to intercept hallucinated metrics and numbers."""
        html_p = Path(html_path)
        source_p = Path(source_text_path)

        if not html_p.exists():
            f = Finding(category="sandbox", severity="critical", message=f"Target HTML file does not exist: {html_p}", target=str(html_p))
            self.findings.append(f)
            return {"passed": False, "error": f"HTML file not found: {html_p}"}

        if not source_p.exists():
            f = Finding(category="sandbox", severity="critical", message=f"Source draft file does not exist: {source_p}", target=str(source_p))
            self.findings.append(f)
            return {"passed": False, "error": f"Source draft file not found: {source_p}"}

        html_content = html_p.read_text(encoding="utf-8")
        source_content = source_p.read_text(encoding="utf-8")

        # 1. Clean HTML text
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        raw_html_body = body_match.group(1) if body_match else html_content
        clean_text = re.sub(r'<style[^>]*>.*?</style>', ' ', raw_html_body, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<script[^>]*>.*?</script>', ' ', clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<!--.*?-->', ' ', clean_text, flags=re.DOTALL)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        clean_text = clean_text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

        # 2. Extract facts, numbers, ratios, and relative changes from source_content
        source_lower = source_content.lower()

        # Direct raw numbers in source
        source_num_matches = re.findall(r'(\d+(?:\.\d+)?)', source_content)
        source_numbers: Set[float] = set()
        for s in source_num_matches:
            try:
                source_numbers.add(float(s))
            except ValueError:
                pass

        # Source ratios (e.g. 420/500)
        source_ratios = re.findall(r'(\d+)\s*/\s*(\d+)', source_content)
        for n_str, d_str in source_ratios:
            try:
                num = float(n_str)
                den = float(d_str)
                if den > 0:
                    pct = (num / den) * 100.0
                    source_numbers.add(round(pct, 1))
                    source_numbers.add(round(pct, 2))
                    source_numbers.add(pct)
            except ValueError:
                pass

        # Source number pairs for relative and absolute change derivations
        num_list = sorted(list(source_numbers))
        for i in range(len(num_list)):
            for j in range(len(num_list)):
                if i != j:
                    n1, n2 = num_list[i], num_list[j]
                    diff = abs(n2 - n1)
                    source_numbers.add(round(diff, 1))
                    source_numbers.add(round(diff, 2))
                    if n1 > 0:
                        rel = (abs(n2 - n1) / n1) * 100.0
                        source_numbers.add(round(rel, 1))
                        source_numbers.add(round(rel, 2))

        # Chinese unit numbers (e.g. 300万 -> 300, 3000000)
        chinese_units = re.findall(r'(\d+(?:\.\d+)?)\s*(万|亿|w)', source_content)
        for num_s, unit in chinese_units:
            try:
                v = float(num_s)
                if unit in ('万', 'w'):
                    source_numbers.add(v)
                    source_numbers.add(v * 10000)
                elif unit == '亿':
                    source_numbers.add(v)
                    source_numbers.add(v * 100000000)
            except ValueError:
                pass

        # 3. Extract candidate metrics from HTML
        candidate_tokens = []

        # Percentages (e.g. 84.0%, 50%, +13.5%)
        for m in re.finditer(r'[-+]?\d+(?:\.\d+)?%\+?', clean_text):
            candidate_tokens.append(("percentage", m.group(0)))

        # Ratios (e.g. 420/500)
        for m in re.finditer(r'\d+\s*/\s*\d+', clean_text):
            candidate_tokens.append(("ratio", m.group(0)))

        # Metrics with units (e.g. 120ms, 10x, 300万, 13.5pp)
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:ms|qps|pp|个百分点|x|万|亿)\b', clean_text, re.IGNORECASE):
            token_str = m.group(0)
            start_pos = m.start()
            if start_pos > 0 and clean_text[start_pos-1].lower() == 'p':
                continue
            candidate_tokens.append(("metric_unit", token_str))

        # Deduplicate candidate tokens
        seen_tokens = set()
        unique_candidates = []
        for kind, token in candidate_tokens:
            token_clean = token.strip()
            if token_clean not in seen_tokens:
                seen_tokens.add(token_clean)
                unique_candidates.append((kind, token_clean))

        verified = []
        hallucinations = []

        for kind, token_clean in unique_candidates:
            # 1. Exact string match in source
            if token_clean.lower() in source_lower:
                verified.append({"token": token_clean, "kind": kind, "reason": "exact_string_match"})
                continue

            # 2. Numeric value extraction
            num_match = re.search(r'[-+]?(\d+(?:\.\d+)?)', token_clean)
            if not num_match:
                continue
            num_val = float(num_match.group(1))

            # Skip benign date years (1990-2035) if not explicitly percentage or metric_unit
            if 1990 <= num_val <= 2035 and kind not in ("percentage", "ratio", "metric_unit"):
                continue

            # Check if num_val matches any source number (with float tolerance 0.01)
            matched = False
            for sn in source_numbers:
                if abs(num_val - sn) <= 0.01:
                    matched = True
                    break

            # Ratio check: e.g. 420/500
            if not matched and kind == "ratio":
                r_parts = re.findall(r'\d+', token_clean)
                if len(r_parts) == 2:
                    n1, n2 = float(r_parts[0]), float(r_parts[1])
                    if any(abs(n1 - sn) <= 0.01 for sn in source_numbers) and any(abs(n2 - sn) <= 0.01 for sn in source_numbers):
                        matched = True

            if matched:
                verified.append({"token": token_clean, "kind": kind, "value": num_val, "reason": "numeric_or_derived_match"})
            else:
                hallucinations.append({"token": token_clean, "kind": kind, "value": num_val})
                self.findings.append(Finding(
                    category="sandbox",
                    severity="critical",
                    message=f"Hallucinated number detected: '{token_clean}' in HTML has no corresponding origin in source text.",
                    target=str(html_path),
                    details={"token": token_clean, "value": num_val, "kind": kind}
                ))

        return {
            "passed": len(hallucinations) == 0,
            "total_candidates": len(unique_candidates),
            "verified_count": len(verified),
            "hallucinated_count": len(hallucinations),
            "verified_numbers": verified,
            "hallucinated_numbers": hallucinations,
        }

    # -------------------------------------------------------------------------
    # 4. Audit Claims Dataset
    # -------------------------------------------------------------------------
    def audit_claims_file(self, claims_path: str | Path) -> Dict[str, Any]:
        """Audits claims.json dataset."""
        path = Path(claims_path)
        if not path.exists():
            return {"error": f"Claims file not found: {path}"}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return {"error": f"JSON parse error: {str(e)}"}

        claims = data.get("claims", [])
        for claim in claims:
            cid = claim.get("id", "unknown")
            text = claim.get("text", "")
            metric = claim.get("metric")

            if metric:
                self.check_metrics(cid, text, metric)

            self.check_role_integrity(cid, claim)
            self.check_verb_hierarchy(cid, claim)
            self.check_depth_and_result_levels(cid, claim)

        return self.summary()

    def summary(self) -> Dict[str, Any]:
        critical = [f for f in self.findings if f.severity == "critical"]
        warnings = [f for f in self.findings if f.severity == "warning"]
        infos = [f for f in self.findings if f.severity == "info"]

        return {
            "passed": len(critical) == 0,
            "total_findings": len(self.findings),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "info_count": len(infos),
            "depth_distribution": dict(self.depth_counts),
            "result_distribution": dict(self.result_counts),
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "message": f.message,
                    "target": f.target,
                    "details": f.details,
                }
                for f in self.findings
            ],
        }


if __name__ == "__main__":
    auditor = ResumeAuditor()
    if len(sys.argv) < 2:
        print("Usage: python audit.py [--claims claims.json] [--html resume.html] [--source draft.txt]")
        sys.exit(1)

    i = 1
    claims_arg = None
    html_arg = None
    source_arg = None

    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--claims" and i + 1 < len(sys.argv):
            claims_arg = sys.argv[i + 1]
            i += 2
        elif arg == "--html" and i + 1 < len(sys.argv):
            html_arg = sys.argv[i + 1]
            i += 2
        elif arg == "--source" and i + 1 < len(sys.argv):
            source_arg = sys.argv[i + 1]
            i += 2
        else:
            print(f"Unknown argument: {arg}")
            i += 1

    if claims_arg:
        auditor.audit_claims_file(claims_arg)
    if html_arg:
        auditor.audit_html_file(html_arg)
    if source_arg:
        if not html_arg:
            print("[ApexResume ERROR] --source requires --html to be specified for sandbox verification.")
            sys.exit(1)
        auditor.audit_source_sandbox(html_arg, source_arg)

    res = auditor.summary()
    print("\n[ApexResume Audit Summary]")
    print(f"Passed: {res['passed']}")
    print(f"Critical: {res['critical_count']} | Warning: {res['warning_count']} | Info: {res['info_count']}")

    for f in res["findings"]:
        sev = f['severity'].upper()
        print(f"  [{sev}] [{f['category']}] {f['message']}")

    sys.exit(0 if res["passed"] else 1)
