"""
OfferGet Baoyan Auditor Module
Academic Integrity Guard & 3-Tier Word Count Adaptive Compressor for Baoyan Applications.
OfferGet native academic integrity verification and multi-tier word budget optimization engine.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants & Specification Standards
# ---------------------------------------------------------------------------

from core.lexicon import (
    FORBIDDEN_BUZZWORDS,
    BAOYAN_SPEC_RANGES as SPEC_RANGES,
    BAOYAN_SPEC_ALIASES as SPEC_ALIASES,
    FORBIDDEN_DASHES,
    FORBIDDEN_QUOTES,
    FORBIDDEN_DOUBLE_HYPHEN,
    BAOYAN_LEAD_ROLES as LEAD_ROLES,
    BAOYAN_CORE_ROLES as CORE_ROLES,
    BAOYAN_ESCALATED_VERBS as ESCALATED_VERBS,
    BAOYAN_LEADER_ONLY_VERBS as LEADER_ONLY_VERBS,
    SIMULATION_TERMS,
    REAL_CLUSTER_TERMS,
    EXPECTED_OUTCOME_TERMS,
    ACQUIRED_OUTCOME_TERMS,
)


# ---------------------------------------------------------------------------
# BaoyanAuditor Class
# ---------------------------------------------------------------------------

class BaoyanAuditor:
    """
    Baoyan Academic Integrity Guard & Word Count Compressor.
    Provides strict verification of resume/application claims:
      1. simulation_vs_real_cluster: flags conflating simulation with physical hardware/clusters.
      2. expected_vs_acquired_outcomes: flags writing pending/expected outcomes as accepted/published.
      3. role_verb_hierarchy: checks role vs verbs (e.g. non-lead/core cannot use 主导, 负责, etc.).
      4. academic_buzzwords_forbidden: flags empty vanity superlatives (首创, 颠覆, etc.).
      5. typography: disallows em dashes, curly quotes, double hyphens.
      6. word_count: verifies 3-tier word count boundaries.
      7. compressor: multi-stage adaptive word count compressor.
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def count_words(text: str) -> int:
        """
        Mixed counting formula: Chinese characters + digit sequences + English words.
        Accurately aligns with Chinese resume and academic application length perception.
        """
        if not text:
            return 0
        han = len(re.findall(r"[\u4e00-\u9fff]", text))
        digits = len(re.findall(r"\d+(?:\.\d+)?", text))
        en = len(re.findall(r"[A-Za-z]+", text))
        return han + digits + en

    # -----------------------------------------------------------------------
    # 1. Academic Integrity Check: Simulation vs Real Cluster
    # -----------------------------------------------------------------------
    def check_simulation_vs_real_cluster(self, text: str) -> Dict[str, Any]:
        """
        Strictly flag if simulation code/environments (Gazebo, Gym, PyBullet, Toy dataset, 纯仿真)
        are conflated or exaggerated as real physical clusters or hardware deployments (万卡集群, 物理机, 实测, 产线实测).
        """
        if not text:
            return {
                "passed": True,
                "status": "PASS",
                "message": "Empty text provided.",
                "simulation_terms": [],
                "real_cluster_terms": []
            }

        text_lower = text.lower()
        matched_sim = []
        for term in SIMULATION_TERMS:
            if term in text_lower or term in text:
                if term not in matched_sim:
                    matched_sim.append(term)

        matched_real = []
        for term in REAL_CLUSTER_TERMS:
            if term in text_lower or term in text:
                if term not in matched_real:
                    matched_real.append(term)

        # Flag if both simulation keywords and real deployment/cluster keywords are present
        if matched_sim and matched_real:
            return {
                "passed": False,
                "status": "FAIL",
                "message": (
                    f"Academic Integrity Violation [simulation_vs_real_cluster]: Simulation environment "
                    f"{matched_sim} conflated with physical cluster/hardware deployment {matched_real}. "
                    f"Baoyan standards strictly forbid conflating simulation results with real hardware/cluster deployments."
                ),
                "simulation_terms": matched_sim,
                "real_cluster_terms": matched_real
            }

        return {
            "passed": True,
            "status": "PASS",
            "message": "Pass: No simulation and physical cluster/hardware conflation detected.",
            "simulation_terms": matched_sim,
            "real_cluster_terms": matched_real
        }

    # -----------------------------------------------------------------------
    # 2. Academic Integrity Check: Expected vs Acquired Outcomes
    # -----------------------------------------------------------------------
    def check_expected_vs_acquired_outcomes(self, text: str) -> Dict[str, Any]:
        """
        Strictly flag if in-submission, under review, expected outcomes (在投, 准备投稿, 预计录用, 拟发表, 待审)
        are written as accepted/published (已录用, 已见刊, 已发表).
        """
        if not text:
            return {
                "passed": True,
                "status": "PASS",
                "message": "Empty text provided.",
                "expected_terms": [],
                "acquired_terms": []
            }

        text_lower = text.lower()
        matched_expected = []
        for term in EXPECTED_OUTCOME_TERMS:
            if term in text_lower or term in text:
                if term not in matched_expected:
                    matched_expected.append(term)

        matched_acquired = []
        for term in ACQUIRED_OUTCOME_TERMS:
            if term in text_lower or term in text:
                if term not in matched_acquired:
                    matched_acquired.append(term)

        # Flag if both are present in the same bullet/entry
        if matched_expected and matched_acquired:
            return {
                "passed": False,
                "status": "FAIL",
                "message": (
                    f"Academic Integrity Violation [expected_vs_acquired_outcomes]: Expected/in-submission terms "
                    f"{matched_expected} conflated with accepted/published terms {matched_acquired}. "
                    f"In Baoyan materials, expected outcomes (在投/拟发表) must never be written as accepted/published (已录用/已见刊)."
                ),
                "expected_terms": matched_expected,
                "acquired_terms": matched_acquired
            }

        return {
            "passed": True,
            "status": "PASS",
            "message": "Pass: Outcome statuses are consistent and free of expected vs acquired conflation.",
            "expected_terms": matched_expected,
            "acquired_terms": matched_acquired
        }

    # -----------------------------------------------------------------------
    # 3. Academic Integrity Check: Role Verb Hierarchy
    # -----------------------------------------------------------------------
    def check_role_verb_hierarchy(self, text: str, role: Optional[str] = None) -> Dict[str, Any]:
        """
        Check role level ('项目负责人', '核心成员', '参赛队员', '辅助成员').
        If not lead/core, strictly flag escalated verbs ('主导', '负责', '统筹', '独立完成').
        """
        if not text:
            return {
                "passed": True,
                "status": "PASS",
                "role": role,
                "message": "Empty text provided.",
                "escalated_verbs": []
            }

        if not role:
            # If no role provided, we check if text itself claims non-lead role with escalated verb
            # or simply pass with informational notice
            return {
                "passed": True,
                "status": "PASS",
                "role": None,
                "message": "Notice: No role specified for role verb hierarchy check.",
                "escalated_verbs": []
            }

        role_clean = role.strip()
        matched_escalated = [v for v in ESCALATED_VERBS if v in text]

        is_lead = role_clean in LEAD_ROLES
        is_core = role_clean in CORE_ROLES
        is_lead_or_core = is_lead or is_core

        if not is_lead_or_core:
            # Strictly flag any escalated verbs for non-lead/core (参赛队员, 辅助成员, etc.)
            if matched_escalated:
                return {
                    "passed": False,
                    "status": "FAIL",
                    "role": role_clean,
                    "message": (
                        f"Role Verb Escalation Violation [role_verb_hierarchy]: Role '{role_clean}' is not lead/core, "
                        f"but escalated verbs {matched_escalated} were found. "
                        f"Recommended: use collaborative verbs like 参与, 协助, 配合, 完成数据采集/实验测试."
                    ),
                    "escalated_verbs": matched_escalated
                }
        else:
            # For 核心成员, check if leader-only verbs (主导, 统筹) were used
            if is_core and not is_lead:
                leader_verbs_used = [v for v in LEADER_ONLY_VERBS if v in text]
                if leader_verbs_used:
                    return {
                        "passed": False,
                        "status": "FAIL",
                        "role": role_clean,
                        "message": (
                            f"Role Verb Escalation Violation [role_verb_hierarchy]: Core member role '{role_clean}' "
                            f"used leader-exclusive verbs {leader_verbs_used}. "
                            f"Recommended: use core verbs like 负责, 实现, 承担, 验证, 求解 (主导/统筹 are reserved for 项目负责人)."
                        ),
                        "escalated_verbs": leader_verbs_used
                    }

        return {
            "passed": True,
            "status": "PASS",
            "role": role_clean,
            "message": f"Pass: Verbs in text align with role level '{role_clean}'.",
            "escalated_verbs": matched_escalated
        }

    # -----------------------------------------------------------------------
    # 4. Academic Integrity Check: Academic Buzzwords Forbidden
    # -----------------------------------------------------------------------
    def check_academic_buzzwords_forbidden(self, text: str) -> Dict[str, Any]:
        """
        Strictly flag empty vanity superlatives ('首创', '颠覆', '国际先进', '世界一流', '填补空白', '独家', '最优解', '全能').
        """
        if not text:
            return {
                "passed": True,
                "status": "PASS",
                "message": "Empty text provided.",
                "forbidden_words": []
            }

        matched_buzzwords = [w for w in FORBIDDEN_BUZZWORDS if w in text]

        if matched_buzzwords:
            return {
                "passed": False,
                "status": "FAIL",
                "message": (
                    f"Academic Buzzword Violation [academic_buzzwords_forbidden]: Forbidden vanity superlatives "
                    f"{matched_buzzwords} detected. Baoyan resumes strictly forbid empty marketing superlatives "
                    f"without third-party official appraisal."
                ),
                "forbidden_words": matched_buzzwords
            }

        return {
            "passed": True,
            "status": "PASS",
            "message": "Pass: Free of empty vanity superlatives.",
            "forbidden_words": []
        }

    # -----------------------------------------------------------------------
    # Punctuation & Typography Audit
    # -----------------------------------------------------------------------
    def check_typography(self, text: str) -> Dict[str, Any]:
        """
        Audit typography: disallow em dashes (——, —, –), curly quotes (“ ” ‘ ’), and double hyphens (--).
        """
        if not text:
            return {
                "passed": True,
                "status": "PASS",
                "message": "Empty text provided.",
                "issues": [],
                "sanitized_text": ""
            }

        issues = []
        for ch, name in FORBIDDEN_DASHES.items():
            if ch in text:
                issues.append(f"{name}")

        for ch, name in FORBIDDEN_QUOTES.items():
            if ch in text:
                issues.append(f"{name}")

        if FORBIDDEN_DOUBLE_HYPHEN in text:
            issues.append("double hyphen (--)")

        sanitized = self.sanitize_typography(text)

        if issues:
            return {
                "passed": False,
                "status": "FAIL",
                "message": f"Typography Violation: Forbidden punctuation detected: {', '.join(issues)}.",
                "issues": issues,
                "sanitized_text": sanitized
            }

        return {
            "passed": True,
            "status": "PASS",
            "message": "Pass: No forbidden dashes, curly quotes, or double hyphens found.",
            "issues": [],
            "sanitized_text": sanitized
        }

    def sanitize_typography(self, text: str) -> str:
        """Cleanly sanitize forbidden typography into standard academic resume punctuation."""
        if not text:
            return ""

        res = text
        # Replace Chinese em dashes and variations with commas or clean separators
        res = res.replace("——", "，")
        for ch in ["\u2014", "\u2013", "\u2015", "\u2212", "\u2e3a", "\u2e3b"]:
            res = res.replace(ch, "，")

        # Replace double hyphens
        res = res.replace("--", "-")

        # Strip curly quotes or replace with clean phrasing
        for ch in ["\u201c", "\u201d", "\u2018", "\u2019"]:
            res = res.replace(ch, "")

        # Clean redundant commas
        res = re.sub(r"，{2,}", "，", res)
        res = re.sub(r"^[，,]\s*", "", res)
        return res.strip()

    # -----------------------------------------------------------------------
    # Word Count Range Verification
    # -----------------------------------------------------------------------
    def check_word_count(self, text: str, target_tier: str = "简历版") -> Dict[str, Any]:
        """
        Check if word count falls strictly into the specified tier:
          - '摘要版': (40, 60)
          - '简历版': (80, 110)
          - '陈述版': (150, 220)
        """
        canonical_tier = SPEC_ALIASES.get(target_tier.strip(), "简历版")
        min_len, max_len = SPEC_RANGES[canonical_tier]
        count = self.count_words(text)

        if min_len <= count <= max_len:
            return {
                "passed": True,
                "status": "PASS",
                "count": count,
                "tier": canonical_tier,
                "tier_range": (min_len, max_len),
                "message": f"Pass: Word count {count} is within target {canonical_tier} range [{min_len}, {max_len}]."
            }

        status = "WARN"
        if count < min_len:
            msg = f"Word count {count} is below {canonical_tier} minimum {min_len}. Consider expanding technical details."
        else:
            msg = f"Word count {count} exceeds {canonical_tier} maximum {max_len}. Adaptive compression recommended."

        return {
            "passed": False,
            "status": status,
            "count": count,
            "tier": canonical_tier,
            "tier_range": (min_len, max_len),
            "message": msg
        }

    # -----------------------------------------------------------------------
    # Numerical Provenance Verification (Fact Guard Integration)
    # -----------------------------------------------------------------------
    def check_numerical_provenance(self, text: str, material: str) -> Dict[str, Any]:
        """
        Verify that all numerical metrics claimed in the resume entry can be traced
        back to the underlying material, preventing metric hallucination.
        """
        if not text or not material:
            return {
                "passed": True,
                "status": "PASS",
                "missing_numbers": [],
                "message": "No material provided or empty text."
            }

        nums = re.findall(r"\d+(?:\.\d+)?", text)
        missing = []
        for n in set(nums):
            # Exclude standard standalone calendar years like 2023, 2024, 2025 from strict missing check
            if re.fullmatch(r"20[12]\d", n):
                continue
            if n not in material:
                missing.append(n)

        if missing:
            return {
                "passed": False,
                "status": "WARN",
                "missing_numbers": missing,
                "message": f"Numerical Provenance Warning: Numbers not found in source material: {', '.join(missing[:8])}."
            }

        return {
            "passed": True,
            "status": "PASS",
            "missing_numbers": [],
            "message": "Pass: All numerical metrics traced in source material."
        }

    # -----------------------------------------------------------------------
    # Comprehensive Audit Entry
    # -----------------------------------------------------------------------
    def audit_entry(
        self,
        text: str,
        role: Optional[str] = None,
        target_tier: str = "简历版",
        material: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform a comprehensive Baoyan audit covering all 4 integrity checks,
        typography audit, word count check, and optional numerical provenance.
        """
        sim_check = self.check_simulation_vs_real_cluster(text)
        outcomes_check = self.check_expected_vs_acquired_outcomes(text)
        role_check = self.check_role_verb_hierarchy(text, role)
        buzzwords_check = self.check_academic_buzzwords_forbidden(text)
        typo_check = self.check_typography(text)
        wc_check = self.check_word_count(text, target_tier)

        checks = {
            "simulation_vs_real_cluster": sim_check,
            "expected_vs_acquired_outcomes": outcomes_check,
            "role_verb_hierarchy": role_check,
            "academic_buzzwords_forbidden": buzzwords_check,
            "typography": typo_check,
            "word_count": wc_check,
        }

        if material is not None:
            checks["numerical_provenance"] = self.check_numerical_provenance(text, material)

        violations = []
        warnings = []

        for name, res in checks.items():
            if res.get("status") == "FAIL":
                violations.append(f"[{name}] {res.get('message')}")
            elif res.get("status") == "WARN":
                warnings.append(f"[{name}] {res.get('message')}")

        has_fail = len(violations) > 0
        overall_status = "FAIL" if has_fail else ("WARN" if warnings else "PASS")
        overall_passed = not has_fail

        summary_lines = [
            f"Baoyan Entry Audit: {overall_status} (Length: {self.count_words(text)} words, Target: {wc_check['tier']})"
        ]
        if violations:
            summary_lines.append(f"Failures ({len(violations)}):")
            for v in violations:
                summary_lines.append(f"  - {v}")
        if warnings:
            summary_lines.append(f"Warnings ({len(warnings)}):")
            for w in warnings:
                summary_lines.append(f"  - {w}")
        if not violations and not warnings:
            summary_lines.append("All academic integrity and formatting checks PASSED.")

        return {
            "passed": overall_passed,
            "status": overall_status,
            "word_count": self.count_words(text),
            "target_tier": wc_check["tier"],
            "checks": checks,
            "violations": violations,
            "warnings": warnings,
            "summary": "\n".join(summary_lines)
        }

    # -----------------------------------------------------------------------
    # 3-Tier Word Count Adaptive Compressor
    # -----------------------------------------------------------------------
    def compress_entry(self, text: str, target_tier: str = "简历版") -> Dict[str, Any]:
        """
        Multi-tier adaptive word count compressor:
          - '摘要版': (40, 60) for summer camp online form limit
          - '简历版': (80, 110) for single-page resume bullets
          - '陈述版': (150, 220) for personal statements / research narratives
        Compresses text while preserving key technical contributions, metrics, and outcomes.
        """
        canonical_tier = SPEC_ALIASES.get(target_tier.strip(), "简历版")
        min_len, max_len = SPEC_RANGES[canonical_tier]

        original_count = self.count_words(text)
        steps_applied: List[str] = []

        # Step 1: Sanitize typography
        current = self.sanitize_typography(text)
        if current != text:
            steps_applied.append("sanitize_typography")

        # Step 2: Strip forbidden buzzwords
        for bw in FORBIDDEN_BUZZWORDS:
            if bw in current:
                current = current.replace(bw, "")
                steps_applied.append(f"remove_buzzword:{bw}")

        # Step 3: Remove academic fluff phrases
        fluff_phrases = [
            "针对当前复杂的", "针对当前", "针对上述痛点", "针对上述难题", "针对上述问题", "针对上述",
            "在本项目中", "在此项目中", "在此过程中", "在此基础上", "进一步地", "值得一提的是",
            "总的来说", "显而易见的是", "通过深入研究", "在导师指导下", "在导师的指导下",
            "结合具体实际情况", "结合实际情况", "结合实际场景", "为了更好地解决", "为了更好地",
            "面对这一严峻挑战", "作为主要抓手", "进行了充分的", "有效促进了", "充分证明了其",
            "具有显著的推广价值", "在实际开发与测试中", "在实际应用中", "在实验过程中",
            "经过大量的实验探索", "经过反复对比验证", "取得了令人满意的成果", "有效提升了整体"
        ]
        for fluff in fluff_phrases:
            if fluff in current:
                current = current.replace(fluff, "")
                steps_applied.append(f"remove_fluff:{fluff}")

        # Step 4: Condense verbose verb constructions
        verbosity_maps = [
            ("进行了深入分析", "深入分析"),
            ("进行了系统开发", "系统开发"),
            ("进行了全面测试", "全面测试"),
            ("展开深入研究", "研究"),
            ("展开对比实验", "对比实验"),
            ("设计并实现了", "设计实现"),
            ("研发并实现了", "研发实现"),
            ("提出并构建了", "提出构建"),
            ("搭建并实现了", "搭建实现"),
            ("算法模型", "算法"),
            ("模型算法", "算法"),
            ("代码编写工作", "代码编写"),
            ("研发工作", "研发"),
            ("开发工作", "开发"),
            ("优化工作", "优化"),
            ("测试工作", "测试"),
            ("搭建了一套", "搭建"),
            ("构建了一套", "构建"),
            ("设计了一套", "设计"),
            ("提出了一种", "提出"),
            ("研发了一种", "研发"),
            ("实现了一种", "实现"),
            ("采用了一种", "采用"),
            ("利用了一种", "利用"),
            ("测试结果表明", "测试表明"),
            ("实验结果表明", "实验表明"),
            ("最终实测表明", "实测表明"),
            ("最终测试表明", "测试表明"),
            ("仿真实验表明", "仿真表明"),
            ("显著提升了", "提升"),
            ("显著提升", "提升"),
            ("极大地改善了", "改善"),
            ("极大地改善", "改善"),
            ("高效地完成了", "完成"),
            ("高效地完成", "完成"),
            ("成功实现了", "实现"),
            ("成功完成了", "完成"),
            ("有效降低了", "降低"),
            ("有效降低", "降低"),
            ("有效提高了", "提高"),
            ("有效提高", "提高"),
            ("成功构建了", "构建"),
            ("优化前后对比", "对比"),
            ("自主研发并设计", "研发设计"),
        ]
        for src, dst in verbosity_maps:
            if src in current:
                current = current.replace(src, dst)
                steps_applied.append(f"condense:{src}->{dst}")

        # Clean punctuation formatting
        current = re.sub(r"，{2,}", "，", current)
        current = re.sub(r"^[，,；;]\s*", "", current)
        current = current.strip()

        current_count = self.count_words(current)

        # If already within range, finish
        if min_len <= current_count <= max_len:
            return {
                "original_text": text,
                "compressed_text": current,
                "target_tier": canonical_tier,
                "tier_range": (min_len, max_len),
                "original_count": original_count,
                "compressed_count": current_count,
                "is_in_range": True,
                "compression_ratio": round(current_count / max(1, original_count), 3),
                "steps_applied": steps_applied
            }

        # Step 5: Intelligent clause-level compression if still exceeding max_len
        if current_count > max_len:
            current, clause_steps = self._compress_by_clauses(current, canonical_tier, min_len, max_len)
            steps_applied.extend(clause_steps)
            current_count = self.count_words(current)

        # Step 6: Fine-tuning token pruning if still slightly above max_len
        if current_count > max_len:
            current, fine_steps = self._fine_tune_prune(current, max_len)
            steps_applied.extend(fine_steps)
            current_count = self.count_words(current)

        is_in_range = min_len <= current_count <= max_len

        return {
            "original_text": text,
            "compressed_text": current,
            "target_tier": canonical_tier,
            "tier_range": (min_len, max_len),
            "original_count": original_count,
            "compressed_count": current_count,
            "is_in_range": is_in_range,
            "compression_ratio": round(current_count / max(1, original_count), 3),
            "steps_applied": steps_applied
        }

    def _compress_by_clauses(
        self,
        text: str,
        tier: str,
        min_len: int,
        max_len: int
    ) -> Tuple[str, List[str]]:
        """Prunes and prioritizes clauses to achieve tier target."""
        steps: List[str] = []
        # Split into clauses by punctuation: 。, ；, ，
        raw_clauses = re.split(r"([。；，])", text)
        clauses = []
        for i in range(0, len(raw_clauses) - 1, 2):
            clause_text = raw_clauses[i].strip()
            punct = raw_clauses[i + 1]
            if clause_text:
                clauses.append({"text": clause_text, "punct": punct})
        if len(raw_clauses) % 2 == 1 and raw_clauses[-1].strip():
            clauses.append({"text": raw_clauses[-1].strip(), "punct": "。"})

        if not clauses:
            return text, steps

        # Score clauses based on academic value
        for c in clauses:
            t = c["text"]
            score = 0
            # Metric presence has highest priority
            if re.search(r"\d+(?:\.\d+)?(?:%|ms|s|fps|倍|n=|m|km|h|min)?", t):
                score += 15
            # Outcome presence (awards, publications)
            if any(k in t for k in ["奖", "录用", "发表", "见刊", "授权", "软著", "专利", "一等奖"]):
                score += 12
            # Core technical methodology
            if any(k in t for k in ["提出", "构建", "设计", "研发", "实现", "搭建", "优化", "算法", "模型"]):
                score += 8
            # Role mention
            if any(k in t for k in ["作为", "负责人", "核心成员", "队员"]):
                score += 4
            # Background / problem fluff has negative or low score
            if any(k in t for k in ["针对", "为了", "面向", "背景", "痛点", "难题", "瓶颈", "随着"]):
                score -= 5
            c["score"] = score
            c["count"] = self.count_words(t)

        # Tier-specific strategy:
        # For '摘要版', background clauses are pruned first
        if tier == "摘要版":
            filtered = [c for c in clauses if not any(k in c["text"] for k in ["针对", "为了", "面向", "背景", "难题"])]
            if filtered:
                clauses = filtered
                steps.append("prune_background_for_summary")

        # Assemble clauses while keeping count <= max_len
        # We start with the highest scoring essential clauses (metrics, outcomes, core method)
        # and assemble in original sequential order
        essential_indices = set()
        # Top scored clauses
        sorted_clauses = sorted(enumerate(clauses), key=lambda x: x[1]["score"], reverse=True)
        running_count = 0

        for idx, c in sorted_clauses:
            if running_count + c["count"] <= max_len:
                essential_indices.add(idx)
                running_count += c["count"]

        # Ensure we maintain original sequential clause order
        selected = [clauses[i] for i in sorted(essential_indices)]
        assembled = "".join(f"{c['text']}{c['punct']}" for c in selected)
        # Ensure trailing period
        if assembled and not assembled.endswith(("。", "！")):
            assembled = assembled.rstrip("，；") + "。"

        steps.append(f"clause_assembly:{len(selected)}/{len(clauses)}_clauses")
        return assembled, steps

    def _fine_tune_prune(self, text: str, max_len: int) -> Tuple[str, List[str]]:
        """Fine-grained word reduction to squeeze into max_len."""
        steps: List[str] = []
        curr = text
        particles = ["并在", "以及", "同时", "从而", "其中", "通过", "进而", "在此基础上", "基于此", "以此"]
        for p in particles:
            if p in curr:
                curr = curr.replace(p, "")
                steps.append(f"remove_particle:{p}")
                if self.count_words(curr) <= max_len:
                    break

        curr = re.sub(r"，{2,}", "，", curr)
        curr = re.sub(r"^[，,；;]\s*", "", curr)
        return curr.strip(), steps


# ---------------------------------------------------------------------------
# Convenience Top-Level Functions
# ---------------------------------------------------------------------------

def audit_baoyan_entry(
    entry: str,
    role: Optional[str] = None,
    target_tier: str = "简历版",
    material: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to audit a Baoyan resume/application entry.
    Checks:
      1. simulation_vs_real_cluster
      2. expected_vs_acquired_outcomes
      3. role_verb_hierarchy
      4. academic_buzzwords_forbidden
      5. punctuation & typography
      6. word count boundaries
      7. (optional) numerical provenance against material
    """
    auditor = BaoyanAuditor()
    return auditor.audit_entry(
        text=entry,
        role=role,
        target_tier=target_tier,
        material=material
    )


def compress_baoyan_entry(
    text: str,
    target_tier: str = "简历版"
) -> Dict[str, Any]:
    """
    Convenience function to adaptively compress a Baoyan resume/application entry
    to match the target tier length:
      - '摘要版': (40, 60)
      - '简历版': (80, 110)
      - '陈述版': (150, 220)
    """
    auditor = BaoyanAuditor()
    return auditor.compress_entry(text=text, target_tier=target_tier)


def count_baoyan_words(text: str) -> int:
    """Convenience function for Chinese resume mixed word counting."""
    return BaoyanAuditor.count_words(text)
