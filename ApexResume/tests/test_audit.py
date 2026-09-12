#!/usr/bin/env python3
"""Unit tests for ApexResume Deterministic Verification & Anti-Inflation Audit Engine."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from core.audit import (
    ResumeAuditor,
    Finding,
    ROLE_RANKS,
    SUPERLATIVES,
    VERB_HIERARCHY,
    DATA_DEPTH_LEVELS,
    RESULT_EVIDENCE_LEVELS,
)


class TestResumeAuditor(unittest.TestCase):
    """Test suite for ResumeAuditor covering metrics, roles, and static HTML scans."""

    def setUp(self):
        self.auditor = ResumeAuditor()

    # -------------------------------------------------------------------------
    # 1. Ratio Checks (Numerator / Denominator)
    # -------------------------------------------------------------------------
    def test_ratio_accuracy_valid(self):
        """Valid ratio calculation (420/500 = 84.0%) should pass without findings."""
        metric = {"numerator": 420, "denominator": 500, "displayed_percent": 84.0}
        self.auditor.check_metrics("claim-01", "420/500 (84.0%)", metric)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["critical_count"], 0)

    def test_ratio_discrepancy_detected(self):
        """Ratio discrepancy (400/500 = 80.0% vs displayed 85.0%) flags critical error."""
        metric = {"numerator": 400, "denominator": 500, "displayed_percent": 85.0}
        self.auditor.check_metrics("claim-02", "400/500 (85.0%)", metric)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["critical_count"], 1)
        self.assertIn("Percentage discrepancy", summary["findings"][0]["message"])

    def test_zero_denominator_detected(self):
        """Zero denominator (10/0) flags critical math error."""
        metric = {"numerator": 10, "denominator": 0, "displayed_percent": 10.0}
        self.auditor.check_metrics("claim-03", "10/0", metric)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertIn("Zero denominator", summary["findings"][0]["message"])

    # -------------------------------------------------------------------------
    # 2. Relative Change vs Percentage Points
    # -------------------------------------------------------------------------
    def test_relative_change_valid(self):
        """Valid relative change from 100 to 150 (+50.0%) passes cleanly."""
        metric = {
            "baseline": 100.0,
            "result": 150.0,
            "reported_change_percent": 50.0,
            "change_type": "relative",
        }
        self.auditor.check_metrics("claim-04", "from 100 to 150 (+50%)", metric)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["critical_count"], 0)

    def test_relative_change_discrepancy(self):
        """Discrepancy in relative change calculation flags critical error."""
        metric = {
            "baseline": 100.0,
            "result": 150.0,
            "reported_change_percent": 80.0,
            "change_type": "relative",
        }
        self.auditor.check_metrics("claim-05", "wrong relative change", metric)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertIn("Relative change discrepancy", summary["findings"][0]["message"])

    def test_percentage_points_confused_with_relative(self):
        """Detects confusing percentage points (+10pp) with relative increase (+10%)."""
        metric = {
            "baseline": 20.0,
            "result": 30.0,
            "reported_change_percent": 10.0,
            "change_type": "relative",
        }
        self.auditor.check_metrics("claim-06", "from 20% to 30% (+10%)", metric)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertIn("Confused percentage points with relative change", summary["findings"][0]["message"])

    def test_percentage_points_valid(self):
        """Valid percentage point specification (+10.0pp) passes cleanly."""
        metric = {
            "baseline": 20.0,
            "result": 30.0,
            "reported_change_percent": 10.0,
            "change_type": "percentage_points",
        }
        self.auditor.check_metrics("claim-07", "from 20% to 30% (+10 percentage points)", metric)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["critical_count"], 0)

    def test_percentage_points_discrepancy(self):
        """Discrepancy in percentage points flags critical error."""
        metric = {
            "baseline": 20.0,
            "result": 30.0,
            "reported_change_percent": 15.0,
            "change_type": "percentage_points",
        }
        self.auditor.check_metrics("claim-08", "wrong percentage points", metric)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertIn("Percentage points discrepancy", summary["findings"][0]["message"])

    def test_zero_baseline_relative_change(self):
        """Relative percentage change with zero baseline flags critical error."""
        metric = {
            "baseline": 0.0,
            "result": 50.0,
            "reported_change_percent": 50.0,
            "change_type": "relative",
        }
        self.auditor.check_metrics("claim-09", "zero baseline", metric)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertIn("Relative percentage change with zero baseline", summary["findings"][0]["message"])

    # -------------------------------------------------------------------------
    # 3. Role Integrity & Ownership Boundaries
    # -------------------------------------------------------------------------
    def test_role_elevation_detected(self):
        """Claiming rank 2 ('主导') when ground truth is rank 1 ('参与') flags critical error."""
        claim = {
            "text": "主导模型架构设计",
            "role_claimed": "主导",
            "ground_truth_role_level": 1,
        }
        self.auditor.check_role_integrity("claim-10", claim)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertIn("Role elevation", summary["findings"][0]["message"])

    def test_role_level_consistent_pass(self):
        """Claiming rank 1 ('参与') with ground truth rank 2 passes cleanly."""
        claim = {
            "text": "参与分布式数据清洗工程",
            "role_claimed": "参与",
            "ground_truth_role_level": 2,
        }
        self.auditor.check_role_integrity("claim-11", claim)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])

    def test_planning_tense_violation(self):
        """Planning or exploratory claims using completed verbs flag critical tense violation."""
        claim = {
            "text": "预研下一代 Agent 架构，已上线服务百强客户",
            "role_claimed": "预研",
            "status": "planned",
            "ground_truth_role_level": 0,
        }
        self.auditor.check_role_integrity("claim-12", claim)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertIn("Tense violation in planned claim", summary["findings"][0]["message"])

    def test_unbounded_owner_scope_warning(self):
        """Claiming rank 3 ('独立负责' / '从0到1') without bounded scope flags warning."""
        claim = {
            "text": "从0到1负责企业级基础大模型平台",
            "role_claimed": "从0到1",
            "ground_truth_role_level": 3,
            "scope": "",
        }
        self.auditor.check_role_integrity("claim-13", claim)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])  # Warnings do not fail overall passed state
        self.assertEqual(summary["warning_count"], 1)
        self.assertIn("Unbounded owner scope", summary["findings"][0]["message"])

    def test_bounded_owner_scope_pass(self):
        """Claiming rank 3 with well-defined minimal scope passes without warnings."""
        claim = {
            "text": "从0到1搭建 Tool-Calling 结构化解码沙箱",
            "role_claimed": "从0到1",
            "ground_truth_role_level": 3,
            "scope": "限定于评测与沙箱验证模块",
        }
        self.auditor.check_role_integrity("claim-14", claim)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["warning_count"], 0)

    # -------------------------------------------------------------------------
    # 4. Static HTML Quality Scans
    # -------------------------------------------------------------------------
    def test_html_todo_placeholder_scan(self):
        """Flags critical finding when unconfirmed <span class="todo"> placeholders exist."""
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write('<html><body><p>线上 P99 延迟为 <span class="todo">待确认</span> ms</p></body></html>')
            tmp_path = Path(f.name)

        try:
            self.auditor.audit_html_file(tmp_path)
            summary = self.auditor.summary()
            self.assertFalse(summary["passed"])
            self.assertIn("unconfirmed '<span class=\"todo\">'", summary["findings"][0]["message"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_html_jinja_placeholder_scan(self):
        """Flags critical finding when unrendered {{...}} template tokens exist."""
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write("<html><body><h1>{{NAME}}</h1></body></html>")
            tmp_path = Path(f.name)

        try:
            self.auditor.audit_html_file(tmp_path)
            summary = self.auditor.summary()
            self.assertFalse(summary["passed"])
            self.assertIn("unrendered template placeholders", summary["findings"][0]["message"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_html_naked_url_scan(self):
        """Flags warning when naked URLs are not wrapped in anchor tags."""
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write("<html><body><p>个人主页：github.com/myname/project</p></body></html>")
            tmp_path = Path(f.name)

        try:
            self.auditor.audit_html_file(tmp_path)
            summary = self.auditor.summary()
            self.assertEqual(summary["warning_count"], 1)
            self.assertIn("naked URL(s)", summary["findings"][0]["message"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_html_long_bold_span_scan(self):
        """Flags warning when bold text exceeds 40 characters."""
        long_bold = "这是一个非常长非常长非常长非常长非常长非常长非常长非常长非常长超过四十个字的加粗文案"
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(f"<html><body><p><b>{long_bold}</b></p></body></html>")
            tmp_path = Path(f.name)

        try:
            self.auditor.audit_html_file(tmp_path)
            summary = self.auditor.summary()
            self.assertEqual(summary["warning_count"], 1)
            self.assertIn("Overly long bold span", summary["findings"][0]["message"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_html_superlatives_scan(self):
        """Flags warning when unbounded superlatives like '全网第一' appear in HTML."""
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write("<html><body><p>研发了业内全网第一的高并发推理架构</p></body></html>")
            tmp_path = Path(f.name)

        try:
            self.auditor.audit_html_file(tmp_path)
            summary = self.auditor.summary()
            self.assertEqual(summary["warning_count"], 1)
            self.assertIn("Extreme superlative '全网第一'", summary["findings"][0]["message"])
        finally:
            tmp_path.unlink(missing_ok=True)

    # -------------------------------------------------------------------------
    # 5. Verb Hierarchy (支持/协助 < 参与 < 负责 < 推动 < 主导)
    # -------------------------------------------------------------------------
    def test_verb_hierarchy_ordering(self):
        """Verifies strictly ordered levels: 支持/协助 < 参与 < 负责 < 推动 < 主导."""
        self.assertLess(VERB_HIERARCHY["协助"], VERB_HIERARCHY["参与"])
        self.assertLess(VERB_HIERARCHY["参与"], VERB_HIERARCHY["负责"])
        self.assertLess(VERB_HIERARCHY["负责"], VERB_HIERARCHY["推动"])
        self.assertLess(VERB_HIERARCHY["推动"], VERB_HIERARCHY["主导"])

    def test_verb_hierarchy_elevation_detected(self):
        """Claiming Level 5 ('主导') with ground truth Level 2 ('参与') flags critical error."""
        claim = {
            "text": "主导长上下文多模态预训练系统架构优化",
            "verb": "主导",
            "ground_truth_verb_level": 2,
        }
        self.auditor.check_verb_hierarchy("claim-v1", claim)
        summary = self.auditor.summary()
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["critical_count"], 1)
        self.assertIn("Verb hierarchy elevation", summary["findings"][0]["message"])

    def test_strong_verb_warning_without_decision_evidence(self):
        """Using strong verb (Level 4 '推动' or Level 5 '主导') without planning/decision proof flags warning."""
        claim = {
            "text": "推动多集群算力跨机房容灾调度",
            "role_claimed": "推动",
        }
        self.auditor.check_verb_hierarchy("claim-v2", claim)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])  # Warning does not fail passed status
        self.assertEqual(summary["warning_count"], 1)
        self.assertIn("without explicit scheme decision or planning evidence", summary["findings"][0]["message"])

    def test_strong_verb_pass_with_decision_evidence(self):
        """Strong verb with explicit decision proof passes without warnings."""
        claim = {
            "text": "推动多集群算力跨机房容灾调度",
            "role_claimed": "推动",
            "has_decision_evidence": True,
        }
        self.auditor.check_verb_hierarchy("claim-v3", claim)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["warning_count"], 0)

    def test_strong_verb_pass_with_planning_keyword_in_text(self):
        """Strong verb with decision/planning keyword in text (e.g. 技术选型) passes without warnings."""
        claim = {
            "text": "主导大模型在线推理框架技术选型与架构设计",
            "role_claimed": "主导",
        }
        self.auditor.check_verb_hierarchy("claim-v4", claim)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["warning_count"], 0)

    # -------------------------------------------------------------------------
    # 6. Data Depth (D0-D4) & Result Evidence (R0-R3) Levels
    # -------------------------------------------------------------------------
    def test_depth_and_result_levels_valid(self):
        """Valid D4 prescriptive and R3 production tier counts properly and passes cleanly."""
        claim = {
            "text": "基于强化学习自适应优化调度算法，线上 P99 降低 40ms",
            "data_depth_level": "D4",
            "result_evidence_level": "R3",
            "metric": {"baseline": 100, "result": 60, "reported_change_percent": -40.0, "change_type": "relative"},
        }
        self.auditor.check_depth_and_result_levels("claim-dr1", claim)
        summary = self.auditor.summary()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["depth_distribution"]["D4"], 1)
        self.assertEqual(summary["result_distribution"]["R3"], 1)

    def test_depth_high_without_methodology_warning(self):
        """Claiming D3/D4 without predictive/prescriptive methodology in text flags warning."""
        claim = {
            "text": "查看大盘监控折线图与指标统计",
            "data_depth_level": "D3",
        }
        self.auditor.check_depth_and_result_levels("claim-dr2", claim)
        summary = self.auditor.summary()
        self.assertEqual(summary["warning_count"], 1)
        self.assertIn("High data depth D3 claimed", summary["findings"][0]["message"])

    def test_result_r0_production_term_warning(self):
        """Theoretical result (R0) asserting completed production terms flags warning."""
        claim = {
            "text": "基于理论预估，该算法方案已上线全量生产环境，降低成本 20%",
            "result_evidence_level": "R0",
        }
        self.auditor.check_depth_and_result_levels("claim-dr3", claim)
        summary = self.auditor.summary()
        self.assertEqual(summary["warning_count"], 1)
        self.assertIn("R0 (Theoretical) claim", summary["findings"][0]["message"])

    def test_invalid_depth_and_result_level_strings(self):
        """Invalid depth or result level codes trigger warnings."""
        claim = {
            "text": "常规任务开发",
            "data_depth_level": "D99",
            "result_evidence_level": "R99",
        }
        self.auditor.check_depth_and_result_levels("claim-dr4", claim)
        summary = self.auditor.summary()
        self.assertEqual(summary["warning_count"], 2)

    # -------------------------------------------------------------------------
    # 7. Entity & Number Source Sandbox Anti-Hallucination Verification
    # -------------------------------------------------------------------------
    def test_sandbox_audit_all_matched_pass(self):
        """When all numbers and percentages in HTML trace back to raw draft, verification passes."""
        source_text = (
            "长上下文优化项目：\n"
            "前缀缓存命中 420/500，端到端延迟由 120ms 降至 60ms。\n"
            "代码评测集测试结果由 68.0% 提升至 81.5%。"
        )
        html_content = (
            "<html><body>"
            "<p>前缀缓存命中 420/500（84.0%），端到端 P99 延迟由 120ms 降至 60ms（相对降低 50.0%）。</p>"
            "<p>代码评测基准从 68.0% 提升至 81.5%，绝对提升 13.5 个百分点。</p>"
            "</body></html>"
        )

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f_src:
            f_src.write(source_text)
            src_path = Path(f_src.name)

        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f_html:
            f_html.write(html_content)
            html_path = Path(f_html.name)

        try:
            res = self.auditor.audit_source_sandbox(html_path, src_path)
            self.assertTrue(res["passed"])
            self.assertEqual(res["hallucinated_count"], 0)
            self.assertGreaterEqual(res["verified_count"], 4)
            summary = self.auditor.summary()
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["critical_count"], 0)
        finally:
            src_path.unlink(missing_ok=True)
            html_path.unlink(missing_ok=True)

    def test_sandbox_audit_hallucination_intercepted(self):
        """When HTML introduces numbers not present or derivable from source draft, intercept with critical error."""
        source_text = "长上下文优化项目：缓存命中 420/500，延迟从 120ms 降至 60ms。"
        html_content = (
            "<html><body>"
            "<p>前缀缓存命中 420/500，延迟降至 60ms。</p>"
            "<p>线上推理吞吐提升 10x，高并发准确率达 99.9%，故障率直降 45%。</p>"
            "</body></html>"
        )

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f_src:
            f_src.write(source_text)
            src_path = Path(f_src.name)

        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f_html:
            f_html.write(html_content)
            html_path = Path(f_html.name)

        try:
            res = self.auditor.audit_source_sandbox(html_path, src_path)
            self.assertFalse(res["passed"])
            self.assertGreaterEqual(res["hallucinated_count"], 2)
            hallucinated_tokens = [h["token"] for h in res["hallucinated_numbers"]]
            self.assertTrue(any("99.9%" in t for t in hallucinated_tokens))
            self.assertTrue(any("10x" in t for t in hallucinated_tokens))

            summary = self.auditor.summary()
            self.assertFalse(summary["passed"])
            self.assertGreaterEqual(summary["critical_count"], 2)
            sandbox_findings = [f for f in summary["findings"] if f["category"] == "sandbox"]
            self.assertGreaterEqual(len(sandbox_findings), 2)
        finally:
            src_path.unlink(missing_ok=True)
            html_path.unlink(missing_ok=True)

    # -------------------------------------------------------------------------
    # 8. Dataset End-to-End Audit
    # -------------------------------------------------------------------------
    def test_claims_file_audit_e2e(self):
        """Audits claims file and verifies detection of violations."""
        claims_file = Path(__file__).resolve().parent.parent / "examples" / "claims.json"
        if claims_file.exists():
            summary = self.auditor.audit_claims_file(claims_file)
            self.assertFalse(summary["passed"])
            self.assertGreaterEqual(summary["critical_count"], 4)
            self.assertGreaterEqual(summary["warning_count"], 1)


if __name__ == "__main__":
    unittest.main()
