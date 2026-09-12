"""
Unit Test Suite for OfferGet Defense Simulator Module.
Tests:
1. Claim-Evidence Matrix generation across 4 core dimensions (Architecture, Metric, Novelty, Contribution).
2. Evidence status classification (Material-supported, Material-implied, Material-missing).
3. Risk basis (Material-derived, Risk-inferred, Combined) and Risk levels (High, Medium, Low).
4. 3 Interrogation Intensity Levels (先热个身, 开始挑刺, 严刑拷打).
5. 3-Round Progressive Follow-up Chains (Round 1: 事实摸底, Round 2: 依赖剥离, Round 3: 极限复现).
6. Defensible Answering Strategy & Defense Cheat Sheet (答辩速查卡).
7. Mandatory 7-section Markdown report generation and compliance.
8. Top-level convenience function `simulate_project_defense()` and various input types.
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.defense_simulator import (
    DefenseSimulator,
    simulate_project_defense,
    EvidenceStatus,
    RiskBasis,
    RiskLevel,
    IntensityLevel
)


class TestDefenseSimulatorMatrixGeneration(unittest.TestCase):
    """Tests for the Claim-Evidence Matrix Generator."""

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        self.simulator = DefenseSimulator(self.profile_data)

    def test_01_claim_extraction_and_four_dimensions(self):
        """Verify claims are extracted and categorized across the 4 core dimensions."""
        project_text = (
            "主导 64B Dense 及 230B MoE 基座大模型在 1024 卡 H800 集群上的预训练全流程，"
            "基于 Megatron-LM 实现 Sequence Parallel 与 Context Parallel 深度融合，"
            "端到端 MFU 从 38.5% 优化至 54.2%，提前 3 周完成千亿 Token 训练里程碑。"
        )
        result = self.simulator.simulate(project_text, intensity="开始挑刺")
        categories = {item.category for item in result.matrix}

        self.assertIn("architecture", categories)
        self.assertIn("metric", categories)
        self.assertIn("novelty", categories)
        self.assertIn("personal_contribution", categories)
        self.assertGreaterEqual(len(result.matrix), 4)

    def test_02_material_supported_with_ssot_anchors(self):
        """Verify that grounded numbers present in SSOT profile get Material-supported status."""
        grounded_claim = (
            "主导 64B Dense 及 230B MoE（激活 32B）基座大模型在 1024 卡 H800 集群上的预训练全流程，"
            "端到端 MFU 从 38.5% 优化至 54.2%，训练可用率达 99.4%。"
        )
        result = self.simulator.simulate(grounded_claim, intensity="开始挑刺")
        metric_claims = [c for c in result.matrix if c.category == "metric"]
        self.assertTrue(any(c.evidence_status == EvidenceStatus.MATERIAL_SUPPORTED for c in metric_claims))

        supported_metric = next(c for c in metric_claims if c.evidence_status == EvidenceStatus.MATERIAL_SUPPORTED)
        self.assertIn("SSOT", supported_metric.evidence_source)
        self.assertIn(supported_metric.risk_level, [RiskLevel.LOW, RiskLevel.MEDIUM])

    def test_03_material_missing_and_high_risk_for_unverified_overclaims(self):
        """Verify that unverified metric inflation and overclaiming get Material-missing and High risk."""
        overclaim_text = (
            "完全实现了万卡集群零通信开销，独创自研全新分布式优化器突破物理极限，"
            "训练吞吐相比业界标准提升 300%，单人独立完成全部核心算子开发与全量部署上线。"
        )
        result = self.simulator.simulate(overclaim_text, intensity="严刑拷打")
        missing_claims = [c for c in result.matrix if c.evidence_status == EvidenceStatus.MATERIAL_MISSING]
        self.assertGreater(len(missing_claims), 0)

        high_risk_claims = [c for c in result.matrix if c.risk_level == RiskLevel.HIGH]
        self.assertGreater(len(high_risk_claims), 0)

        # Verify overclaim detection
        for c in high_risk_claims:
            self.assertIn(c.risk_basis, [RiskBasis.COMBINED, RiskBasis.MATERIAL_DERIVED, RiskBasis.RISK_INFERRED])

    def test_04_explicit_boundary_statements_are_supported(self):
        """Verify that explicit scope and limitation statements are Material-supported and Low risk."""
        boundary_statement = (
            "当前版本主要用于高校课程设计与科研原型验证，基于典型工况数据用于展示系统运行逻辑，"
            "尚未达到实际工程部署级别，属于后续演进方向。"
        )
        result = self.simulator.simulate(boundary_statement, intensity="开始挑刺")
        boundary_claims = [c for c in result.matrix if "当前版本主要" in c.claim_text or "尚未达到" in c.claim_text]
        if boundary_claims:
            for c in boundary_claims:
                self.assertEqual(c.evidence_status, EvidenceStatus.MATERIAL_SUPPORTED)
                self.assertEqual(c.risk_level, RiskLevel.LOW)

    def test_05_input_formats_flexibility(self):
        """Verify simulator handles string, list of claims, project dict, and file paths."""
        # 1. List of claim strings
        claims_list = [
            "基于 Anthropic MCP 协议构建工业级多智能体编排引擎",
            "引入 DFA 驱动的 Grammar-Guided Decoding 实现 100% 结构化 JSON Schema 约束",
            "单 Token 推理成本降低 62%，P99 延迟降低 45%"
        ]
        res_list = self.simulator.simulate(claims_list)
        self.assertGreaterEqual(len(res_list.matrix), 3)

        # 2. Candidate profile project dict
        proj_dict = self.profile_data["projects"][0]
        res_dict = self.simulator.simulate(proj_dict)
        self.assertIn("Enterprise-Agent-OS", res_dict.project_name)
        self.assertGreaterEqual(len(res_dict.matrix), 4)

        # 3. File path input
        res_file = self.simulator.simulate(str(self.profile_path))
        self.assertTrue(len(res_file.matrix) > 0)


class TestDefenseSimulatorIntensityLevels(unittest.TestCase):
    """Tests for the 3 Interrogation Intensity Levels."""

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        self.simulator = DefenseSimulator(self.profile_data)
        self.proj_text = self.profile_data["experience"][0]["highlights"][0]["claim_zh"]

    def test_01_warmup_intensity(self):
        """Verify 先热个身 generates friendly confirmation questions on background and definitions."""
        result = self.simulator.simulate(self.proj_text, intensity="先热个身")
        self.assertEqual(result.intensity, IntensityLevel.WARMUP)
        self.assertGreaterEqual(len(result.intensity_questions), 3)
        questions_text = " ".join(q["question"] for q in result.intensity_questions)
        self.assertTrue(any(kw in questions_text for kw in ["介绍", "初衷", "背景", "选型", "分工"]))

    def test_02_critical_intensity(self):
        """Verify 开始挑刺 probes data sources, baseline comparison, and novelty authenticity."""
        result = self.simulator.simulate(self.proj_text, intensity="开始挑刺")
        self.assertEqual(result.intensity, IntensityLevel.CRITICAL)
        self.assertGreaterEqual(len(result.intensity_questions), 3)
        questions_text = " ".join(q["question"] for q in result.intensity_questions)
        self.assertTrue(any(kw in questions_text for kw in ["Baseline", "基线", "替代方案", "选型", "创新", "数据"]))

    def test_03_hell_mode_grilling_intensity(self):
        """
        Verify 严刑拷打 launches sharp attacks on:
        - baseline ablation controls
        - individual vs borrowed open-source code
        - extreme edge case failures
        - 15-minute clean environment reproducibility
        """
        result = self.simulator.simulate(self.proj_text, intensity="严刑拷打")
        self.assertEqual(result.intensity, IntensityLevel.HELL)
        self.assertGreaterEqual(len(result.intensity_questions), 4)

        questions_text = " ".join(q["question"] for q in result.intensity_questions)
        self.assertTrue(any(kw in questions_text for kw in ["消融", "Ablation", "控制变量"]), "Must test baseline ablation")
        self.assertTrue(any(kw in questions_text for kw in ["开源", "代码行数", "胶水", "所有权"]), "Must test code ownership")
        self.assertTrue(any(kw in questions_text for kw in ["事故", "死锁", "掉卡", "雪崩", "分区"]), "Must test edge case failure")
        self.assertTrue(any(kw in questions_text for kw in ["15 分钟", "15分钟", "复现", "裸机", "单测"]), "Must test 15-minute reproducibility")

    def test_04_intensity_alias_handling(self):
        """Verify aliases such as 'warmup', 'critical', 'hell' correctly map to standard labels."""
        res_warm = self.simulator.simulate(self.proj_text, intensity="warmup")
        self.assertEqual(res_warm.intensity, IntensityLevel.WARMUP)

        res_crit = self.simulator.simulate(self.proj_text, intensity="critical")
        self.assertEqual(res_crit.intensity, IntensityLevel.CRITICAL)

        res_hell = self.simulator.simulate(self.proj_text, intensity="hell")
        self.assertEqual(res_hell.intensity, IntensityLevel.HELL)


class TestDefenseSimulatorFollowUpChains(unittest.TestCase):
    """Tests for 3-Round Progressive Follow-up Chains."""

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        self.simulator = DefenseSimulator(self.profile_data)

    def test_01_top_weak_spots_and_chain_structure(self):
        """Verify top weak spots generate realistic 3-round sequential follow-up chains."""
        target_text = (
            "主导全新自研混合专家大模型分布式训练，端到端 MFU 从 38.5% 优化至 54.2%，"
            "完全消除集群慢节点通信开销，训练速度相比开源框架提升 2.5 倍。"
        )
        result = self.simulator.simulate(target_text, intensity="严刑拷打")
        self.assertGreaterEqual(len(result.follow_up_chains), 2)
        self.assertLessEqual(len(result.follow_up_chains), 5)

        for chain in result.follow_up_chains:
            self.assertEqual(len(chain.rounds), 3, "Each chain must contain exactly 3 sequential rounds")
            r1, r2, r3 = chain.rounds

            # Round 1: Missing fact or baseline probe
            self.assertEqual(r1.round_index, 1)
            self.assertTrue(any(kw in r1.title for kw in ["摸底", "事实", "基线", "机理", "分工", "拓扑"]))

            # Round 2: Dependency stripping / alternative challenge
            self.assertEqual(r2.round_index, 2)
            self.assertTrue(any(kw in r2.title for kw in ["消融", "剥离", "依赖", "质疑", "代码量", "瓶颈"]))

            # Round 3: Edge case collapse / clean reproducibility
            self.assertEqual(r3.round_index, 3)
            self.assertTrue(any(kw in r3.title for kw in ["极限", "复现", "灾难", "白板", "事故", "容灾"]))

            # Check defensive strategy for each chain
            self.assertIn("pivot_focus", chain.defensive_strategy)
            self.assertIn("recommended_response", chain.defensive_strategy)
            self.assertTrue(len(chain.defensive_strategy["recommended_response"]) > 20)


class TestDefensibleStrategyAndCheatSheet(unittest.TestCase):
    """Tests for Defensible Answering Strategy & Defense Cheat Sheet."""

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)
        self.simulator = DefenseSimulator(self.profile_data)

    def test_01_golden_defense_framework_and_safe_framing(self):
        """Verify 5-step golden defense model and prohibited vs safe framing pairs."""
        target_text = "主导 Fast-Megatron-MLA 研发，KV-Cache 显存降低 75%，合并至知名开源仓库。"
        result = self.simulator.simulate(target_text, intensity="开始挑刺")
        strat = result.defensible_strategy

        self.assertIn("golden_steps", strat)
        self.assertEqual(len(strat["golden_steps"]), 5)

        # Check 5 golden steps exist
        step_names = [s["step"] for s in strat["golden_steps"]]
        self.assertTrue(any("正面回应" in s for s in step_names))
        self.assertTrue(any("说明依据" in s for s in step_names))
        self.assertTrue(any("主动划界" in s or "承认局限" in s for s in step_names))
        self.assertTrue(any("合理解释" in s for s in step_names))
        self.assertTrue(any("给出改进" in s for s in step_names))

        # Check safe framing pairs
        self.assertIn("safe_framing_pairs", strat)
        self.assertGreaterEqual(len(strat["safe_framing_pairs"]), 3)

    def test_02_defense_cheat_sheet_contents(self):
        """Verify Defense Cheat Sheet (答辩速查卡) contains all 5 high-density cards."""
        target_text = "主导 Enterprise-Agent-OS 架构设计，基于 MCP 构建工业级多 Agent 调度编排系统，GitHub 3400 stars。"
        result = self.simulator.simulate(target_text, intensity="严刑拷打")
        cs = result.defense_cheat_sheet
        self.assertIsNotNone(cs)

        # Card 1: Pitch & moat
        self.assertTrue(len(cs.elevator_pitch) > 10)
        # Card 2: Top vulnerabilities & bottom line
        self.assertGreaterEqual(len(cs.top_vulnerabilities), 1)
        self.assertIn("bottom_line", cs.top_vulnerabilities[0])
        # Card 3: Metric audit sheet
        self.assertGreaterEqual(len(cs.metric_audit_sheet), 1)
        self.assertIn("baseline", cs.metric_audit_sheet[0])
        # Card 4: Contribution boundaries
        self.assertGreaterEqual(len(cs.contribution_boundaries), 1)
        self.assertIn("personal", cs.contribution_boundaries[0])
        self.assertIn("external", cs.contribution_boundaries[0])
        # Card 5: 15-minute reproducibility
        self.assertIn("command", cs.fifteen_minute_reproducibility)
        self.assertIn("test_target", cs.fifteen_minute_reproducibility)
        self.assertIn("fallback_pivot", cs.fifteen_minute_reproducibility)


class TestFullReviewMarkdownContract(unittest.TestCase):
    """Tests for the 7 Mandatory Sections in Markdown Output."""

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

    def test_01_seven_mandatory_sections_in_exact_order(self):
        """Verify the Markdown report contains all 7 mandatory sections in exact order."""
        proj_text = self.profile_data["projects"][0]["description_zh"]
        md_report = simulate_project_defense(
            project_input=proj_text,
            profile_context=self.profile_data,
            intensity="严刑拷打",
            output_format="markdown"
        )

        mandatory_sections = [
            "项目一句话定位",
            "Claim-Evidence Matrix",
            "高风险缺口",
            "连续追问链",
            "防守型回答策略",
            "材料修复清单",
            "答辩速查卡"
        ]

        positions = [md_report.find(sec) for sec in mandatory_sections]
        for idx, pos in enumerate(positions):
            self.assertGreaterEqual(pos, 0, f"Missing mandatory section: {mandatory_sections[idx]}")

        # Check exact ascending order
        self.assertEqual(positions, sorted(positions), "Mandatory sections are not in the required order")

    def test_02_claim_evidence_matrix_headers_and_labels(self):
        """Verify the Markdown table has required headers and standard labels."""
        proj_text = self.profile_data["experience"][0]["highlights"][0]["claim_zh"]
        md_report = simulate_project_defense(
            project_input=proj_text,
            profile_context=self.profile_data,
            intensity="开始挑刺",
            output_format="markdown"
        )

        # Required headers
        required_headers = [
            "Claim / 项目说法",
            "Evidence / 材料依据",
            "Evidence status / 证据状态",
            "Gap / 缺口",
            "Risk basis / 风险依据",
            "Risk"
        ]
        for h in required_headers:
            self.assertIn(h, md_report, f"Missing matrix header: {h}")

        # Evidence status labels
        self.assertTrue(
            any(status in md_report for status in ["Material-supported", "Material-implied", "Material-missing"])
        )
        # Risk basis labels
        self.assertTrue(
            any(basis in md_report for basis in ["Material-derived", "Risk-inferred"])
        )

    def test_03_convenience_function_dict_and_markdown(self):
        """Verify top-level `simulate_project_defense()` outputs both dict and markdown formats."""
        proj_text = "主导设计大规模高并发大模型推理服务中台，定制扩展 vLLM 架构，P99 延迟降低 45%。"

        # Dict format
        res_dict = simulate_project_defense(proj_text, intensity="开始挑刺", output_format="dict")
        self.assertIsInstance(res_dict, dict)
        self.assertIn("matrix", res_dict)
        self.assertIn("high_risk_gaps", res_dict)
        self.assertIn("follow_up_chains", res_dict)
        self.assertIn("defensible_strategy", res_dict)
        self.assertIn("defense_cheat_sheet", res_dict)

        # Markdown format
        res_md = simulate_project_defense(proj_text, intensity="先热个身", output_format="markdown")
        self.assertIsInstance(res_md, str)
        self.assertIn("## 1. 项目一句话定位", res_md)
        self.assertIn("## 7. 答辩速查卡", res_md)


if __name__ == "__main__":
    unittest.main()
