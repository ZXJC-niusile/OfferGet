"""
Unit tests for Baoyan Academic Integrity Guard & Word Count Compressor.
Exhaustively tests:
  1. simulation_vs_real_cluster check
  2. expected_vs_acquired_outcomes check
  3. role_verb_hierarchy check
  4. academic_buzzwords_forbidden check
  5. punctuation & typography audit
  6. word count boundaries (摘要版, 简历版, 陈述版)
  7. 3-tier adaptive word count compression
  8. numerical provenance & convenience functions
"""

import unittest
from core.baoyan_auditor import (
    BaoyanAuditor,
    audit_baoyan_entry,
    compress_baoyan_entry,
    count_baoyan_words,
    SPEC_RANGES
)


class TestSimulationVsRealCluster(unittest.TestCase):
    """Exhaustive tests for simulation_vs_real_cluster integrity check."""

    def setUp(self):
        self.auditor = BaoyanAuditor()

    def test_conflation_gazebo_physical_cluster(self):
        text = "基于Gazebo平台搭建仿真实验，并在物理机集群上实测，机械臂抓取成功率达96.5%。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("gazebo", [s.lower() for s in res["simulation_terms"]])
        self.assertTrue(any(r in res["real_cluster_terms"] for r in ["物理机", "物理机集群", "实测"]))

    def test_conflation_pybullet_wanka_cluster(self):
        text = "使用PyBullet开发强化学习策略，并在万卡集群上进行产线实测验证。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("pybullet", [s.lower() for s in res["simulation_terms"]])
        self.assertIn("万卡集群", res["real_cluster_terms"])

    def test_conflation_gym_chanxian_shice(self):
        text = "在OpenAI Gym环境中训练智能体，完成产线实测部署。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("gym", [s.lower() for s in res["simulation_terms"]])
        self.assertIn("产线实测", res["real_cluster_terms"])

    def test_conflation_toy_dataset_shice(self):
        text = "基于Toy dataset完成模型验证，并在产线部署实测获得98%准确率。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("toy dataset", [s.lower() for s in res["simulation_terms"]])

    def test_conflation_pure_simulation_physical_machine(self):
        text = "采用纯仿真算法架构，在物理机环境实机部署测试。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("纯仿真", res["simulation_terms"])
        self.assertIn("物理机", res["real_cluster_terms"])

    def test_legitimate_pure_simulation_passes(self):
        text = "在Gazebo仿真环境与PyBullet中完成机械臂轨迹规划验证，仿真抓取成功率达95.2%。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["real_cluster_terms"]), 0)

    def test_legitimate_real_cluster_deployment_passes(self):
        text = "在万卡集群物理机网络上完成分布式通信架构调优，实测通信延迟降低22.4%。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["simulation_terms"]), 0)

    def test_neutral_text_passes(self):
        text = "设计动态局部路径规划算法，优化目标函数并在开源测试集上验证性能。"
        res = self.auditor.check_simulation_vs_real_cluster(text)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")


class TestExpectedVsAcquiredOutcomes(unittest.TestCase):
    """Exhaustive tests for expected_vs_acquired_outcomes integrity check."""

    def setUp(self):
        self.auditor = BaoyanAuditor()

    def test_conflation_zaitou_and_yilluyong(self):
        text = "相关成果在投IEEE T-PAMI，目前已录用。"
        res = self.auditor.check_expected_vs_acquired_outcomes(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("在投", res["expected_terms"])
        self.assertIn("已录用", res["acquired_terms"])

    def test_conflation_zhunbeitougou_and_yijiankan(self):
        text = "准备投稿CVPR顶会，论文已见刊于会议专刊。"
        res = self.auditor.check_expected_vs_acquired_outcomes(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("准备投稿", res["expected_terms"])
        self.assertIn("已见刊", res["acquired_terms"])

    def test_conflation_nifabiao_and_yifabiao(self):
        text = "研究成果拟发表于顶刊，目前已发表于自动化期刊。"
        res = self.auditor.check_expected_vs_acquired_outcomes(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("拟发表", res["expected_terms"])
        self.assertIn("已发表", res["acquired_terms"])

    def test_conflation_yujiluyong_and_yijiankan(self):
        text = "工作预计录用，现已见刊。"
        res = self.auditor.check_expected_vs_acquired_outcomes(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("预计录用", res["expected_terms"])
        self.assertIn("已见刊", res["acquired_terms"])

    def test_conflation_daishen_and_yiluyong(self):
        text = "第一作者论文待审中，已录用待刊。"
        res = self.auditor.check_expected_vs_acquired_outcomes(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("待审", res["expected_terms"])

    def test_honest_pending_outcome_passes(self):
        text = "第一作者论文在投CVPR 2025（审稿中）。"
        res = self.auditor.check_expected_vs_acquired_outcomes(text)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")
        self.assertIn("在投", res["expected_terms"])
        self.assertEqual(len(res["acquired_terms"]), 0)

    def test_honest_acquired_outcome_passes(self):
        text = "第一作者论文已发表并见刊于IEEE T-PAMI，获国家发明专利已授权。"
        res = self.auditor.check_expected_vs_acquired_outcomes(text)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["expected_terms"]), 0)


class TestRoleVerbHierarchy(unittest.TestCase):
    """Exhaustive tests for role_verb_hierarchy check."""

    def setUp(self):
        self.auditor = BaoyanAuditor()

    def test_lead_role_with_escalated_verbs_passes(self):
        for verb in ["主导", "负责", "统筹", "独立完成"]:
            text = f"作为项目负责人，{verb}算法架构设计与全流程优化。"
            res = self.auditor.check_role_verb_hierarchy(text, role="项目负责人")
            self.assertTrue(res["passed"], f"Lead role should allow {verb}")
            self.assertEqual(res["status"], "PASS")

    def test_core_member_with_permitted_verbs_passes(self):
        for verb in ["负责", "实现", "承担", "验证", "求解"]:
            text = f"作为核心成员，{verb}核心模型推导与实验方案验证。"
            res = self.auditor.check_role_verb_hierarchy(text, role="核心成员")
            self.assertTrue(res["passed"], f"Core member should allow {verb}")
            self.assertEqual(res["status"], "PASS")

    def test_core_member_with_leader_only_verbs_fails(self):
        for verb in ["主导", "统筹"]:
            text = f"作为核心成员，{verb}整体项目开发与多部门协调。"
            res = self.auditor.check_role_verb_hierarchy(text, role="核心成员")
            self.assertFalse(res["passed"], f"Core member should not use {verb}")
            self.assertEqual(res["status"], "FAIL")

    def test_contestant_with_escalated_verbs_fails(self):
        for verb in ["主导", "负责", "统筹", "独立完成"]:
            text = f"作为参赛队员，{verb}模型训练与算法测试。"
            res = self.auditor.check_role_verb_hierarchy(text, role="参赛队员")
            self.assertFalse(res["passed"], f"Contestant must not use {verb}")
            self.assertEqual(res["status"], "FAIL")
            self.assertIn(verb, res["escalated_verbs"])

    def test_auxiliary_member_with_escalated_verbs_fails(self):
        for verb in ["主导", "负责", "统筹", "独立完成"]:
            text = f"作为辅助成员，{verb}数据集构建与清洗。"
            res = self.auditor.check_role_verb_hierarchy(text, role="辅助成员")
            self.assertFalse(res["passed"], f"Auxiliary member must not use {verb}")
            self.assertEqual(res["status"], "FAIL")

    def test_contestant_with_cooperative_verbs_passes(self):
        text = "作为参赛队员，参与数据清洗，协助完成对比实验与测试报告撰写。"
        res = self.auditor.check_role_verb_hierarchy(text, role="参赛队员")
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")

    def test_auxiliary_member_with_cooperative_verbs_passes(self):
        text = "作为辅助成员，协助整理实验数据并配合完成模型测试。"
        res = self.auditor.check_role_verb_hierarchy(text, role="辅助成员")
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")


class TestAcademicBuzzwordsForbidden(unittest.TestCase):
    """Exhaustive tests for academic_buzzwords_forbidden check."""

    def setUp(self):
        self.auditor = BaoyanAuditor()

    def test_forbidden_buzzwords_each_triggers_fail(self):
        buzzwords = ["首创", "颠覆", "国际先进", "世界一流", "填补空白", "独家", "最优解", "全能"]
        for bw in buzzwords:
            text = f"该研究提出了{bw}算法，彻底解决了传统方法的性能缺陷。"
            res = self.auditor.check_academic_buzzwords_forbidden(text)
            self.assertFalse(res["passed"], f"Buzzword '{bw}' should be strictly flagged")
            self.assertEqual(res["status"], "FAIL")
            self.assertIn(bw, res["forbidden_words"])

    def test_academic_rigorous_wording_passes(self):
        text = "提出改进注意力网络与分层特征融合方法，实验表明识别准确率提升15.3%，延迟降低18ms。"
        res = self.auditor.check_academic_buzzwords_forbidden(text)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["forbidden_words"]), 0)


class TestTypographyAudit(unittest.TestCase):
    """Tests for punctuation and typography audit."""

    def setUp(self):
        self.auditor = BaoyanAuditor()

    def test_em_dash_fails(self):
        text = "提出新型导航算法——在复杂动态环境下依然具备鲁棒性。"
        res = self.auditor.check_typography(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any("em dash" in i for i in res["issues"]))

    def test_curly_quotes_fail(self):
        text = "构建“多源异构”传感器融合网络，精度提升12%。"
        res = self.auditor.check_typography(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any("quote" in i for i in res["issues"]))

    def test_double_hyphen_fails(self):
        text = "优化路径规划模型--收敛速度提升25%。"
        res = self.auditor.check_typography(text)
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any("double hyphen" in i for i in res["issues"]))

    def test_clean_typography_passes(self):
        text = "优化路径规划模型，收敛速度提升25%，达到设计预期。"
        res = self.auditor.check_typography(text)
        self.assertTrue(res["passed"])
        self.assertEqual(res["status"], "PASS")

    def test_sanitize_typography(self):
        dirty = "提出“高维鲁棒”算法——针对动态场景--性能提升20%。"
        clean = self.auditor.sanitize_typography(dirty)
        self.assertNotIn("“", clean)
        self.assertNotIn("”", clean)
        self.assertNotIn("——", clean)
        self.assertNotIn("--", clean)
        self.assertTrue(self.auditor.check_typography(clean)["passed"])


class TestWordCountRanges(unittest.TestCase):
    """Tests for 3-tier word count boundaries."""

    def setUp(self):
        self.auditor = BaoyanAuditor()

    def test_word_count_calculation(self):
        # 汉字 + 数字串 + 英文词
        text = "采用改进PPO算法（收敛速度提升35%），实现成功率96.5%，获一等奖。"
        count = self.auditor.count_words(text)
        self.assertGreater(count, 20)
        self.assertIsInstance(count, int)

    def test_summary_tier_range(self):
        # 40-60 字
        lo, hi = SPEC_RANGES["摘要版"]
        self.assertEqual((lo, hi), (40, 60))

        # Too short (30 words)
        short_text = "设计动态路径规划算法，实现机械臂抓取避障，成功率达95%。"
        res = self.auditor.check_word_count(short_text, target_tier="摘要版")
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "WARN")

        # In range (approx 50 words)
        in_range_text = "提出基于改进PPO与动态局部规划融合算法，优化奖励函数加速收敛；仿真避障成功率达94.8%，延迟降至32ms，获国家一等奖。"
        res = self.auditor.check_word_count(in_range_text, target_tier="摘要版")
        self.assertTrue(res["passed"], f"Count {res['count']} should be in [40, 60]")
        self.assertEqual(res["status"], "PASS")

    def test_resume_tier_range(self):
        # 80-110 字
        lo, hi = SPEC_RANGES["简历版"]
        self.assertEqual((lo, hi), (80, 110))

        in_range_text = (
            "针对未知复杂动态环境下的自主导航难题，作为核心成员，提出基于改进PPO与局部路径规划的融合算法。"
            "优化网络结构与奖励函数，显著加速训练收敛；仿真测试表明避障成功率达94.8%，延迟降至32ms，获国家一等奖。"
        )
        res = self.auditor.check_word_count(in_range_text, target_tier="简历版")
        self.assertTrue(res["passed"], f"Count {res['count']} should be in [80, 110]")


class TestAdaptiveCompressor(unittest.TestCase):
    """Exhaustive tests for 3-tier adaptive word count compression."""

    def setUp(self):
        self.auditor = BaoyanAuditor()
        self.long_sample = (
            "针对移动机器人在未知复杂动态环境下的自主导航与避障难题，在本项目中，作为核心成员，"
            "设计并实现了一种基于深度强化学习与动态局部路径规划融合的导航算法。搭建仿真测试平台，"
            "通过深入研究改进PPO算法的网络结构与奖励函数，显著提升了训练收敛速度。最终仿真测试表明，"
            "局部避障成功率达到94.8%，规划延迟降低至32ms，相关成果已录用为竞赛技术报告，荣获国家一等奖。"
        )

    def test_compress_to_resume_tier(self):
        # Target: 简历版 (80-110 words)
        res = self.auditor.compress_entry(self.long_sample, target_tier="简历版")
        compressed = res["compressed_text"]
        count = res["compressed_count"]
        self.assertLess(count, res["original_count"])
        self.assertTrue(res["is_in_range"], f"Count {count} not in range (80, 110). Text: {compressed}")
        # Core technical metrics and outcomes preserved
        self.assertIn("94.8%", compressed)
        self.assertIn("32ms", compressed)
        self.assertIn("一等奖", compressed)
        # Typography clean
        typo_res = self.auditor.check_typography(compressed)
        self.assertTrue(typo_res["passed"])

    def test_compress_to_summary_tier(self):
        # Target: 摘要版 (40-60 words)
        res = self.auditor.compress_entry(self.long_sample, target_tier="摘要版")
        compressed = res["compressed_text"]
        count = res["compressed_count"]
        self.assertLess(count, res["original_count"])
        self.assertTrue(res["is_in_range"], f"Count {count} not in range (40, 60). Text: {compressed}")
        # Key metric preserved
        self.assertTrue("94.8%" in compressed or "32ms" in compressed)
        self.assertIn("一等奖", compressed)

    def test_compress_statement_tier_already_in_range(self):
        # Narrative in 150-220 range
        res = self.auditor.compress_entry(self.long_sample, target_tier="陈述版")
        self.assertEqual(res["target_tier"], "陈述版")
        self.assertIsNotNone(res["compressed_text"])

    def test_compress_sanitizes_dirty_typography(self):
        dirty_text = (
            "针对“复杂多变”的动态环境——作为核心成员，设计并实现了基于改进PPO的避障算法--收敛速度提升30%，"
            "在本项目中，仿真测试表明避障成功率达到95.5%，规划延迟降至25ms，荣获全国一等奖。"
        )
        res = self.auditor.compress_entry(dirty_text, target_tier="简历版")
        compressed = res["compressed_text"]
        self.assertNotIn("——", compressed)
        self.assertNotIn("“", compressed)
        self.assertNotIn("--", compressed)


class TestComprehensiveAuditAndConvenience(unittest.TestCase):
    """Tests for full audit_entry and top-level convenience functions."""

    def test_clean_entry_passes_all(self):
        clean_entry = (
            "针对移动机器人在未知复杂环境下的避障难题，作为核心成员，设计基于改进PPO与局部路径规划的融合算法。"
            "重构网络结构并优化奖励函数；最终仿真测试表明避障成功率达94.8%，规划延迟降至32ms，荣获国家一等奖。"
        )
        report = audit_baoyan_entry(clean_entry, role="核心成员", target_tier="简历版")
        self.assertTrue(report["passed"])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["violations"]), 0)
        self.assertEqual(len(report["warnings"]), 0)

    def test_multiple_violations_detected(self):
        dirty_entry = (
            "作为参赛队员，主导首创的强化学习算法——在Gazebo环境中开发并在万卡集群上产线实测，"
            "论文在投CVPR且已见刊发表。"
        )
        report = audit_baoyan_entry(dirty_entry, role="参赛队员", target_tier="简历版")
        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "FAIL")

        checks = report["checks"]
        # 1. Simulation vs real cluster
        self.assertFalse(checks["simulation_vs_real_cluster"]["passed"])
        # 2. Expected vs acquired
        self.assertFalse(checks["expected_vs_acquired_outcomes"]["passed"])
        # 3. Role verb hierarchy (参赛队员 used 主导)
        self.assertFalse(checks["role_verb_hierarchy"]["passed"])
        # 4. Academic buzzwords (首创)
        self.assertFalse(checks["academic_buzzwords_forbidden"]["passed"])
        # 5. Typography (——)
        self.assertFalse(checks["typography"]["passed"])

        self.assertGreaterEqual(len(report["violations"]), 5)

    def test_compress_baoyan_entry_convenience(self):
        text = (
            "针对未知复杂动态环境下的自主导航难题，在本项目中，作为核心成员，设计并实现了一种基于改进PPO的导航算法。"
            "搭建仿真测试平台，通过深入研究，显著提升了收敛速度。最终仿真测试表明，避障成功率达94.8%，延迟降至32ms，获一等奖。"
        )
        res = compress_baoyan_entry(text, target_tier="摘要版")
        self.assertEqual(res["target_tier"], "摘要版")
        self.assertTrue(res["is_in_range"])

    def test_count_baoyan_words_convenience(self):
        cnt = count_baoyan_words("测试中文123英文ABC")
        self.assertEqual(cnt, 6 + 1 + 1)  # 6 hanzi (测试中文 + 英文) + 1 digit (123) + 1 en (ABC) = 8

    def test_numerical_provenance_check(self):
        auditor = BaoyanAuditor()
        material = "该系统经500组仿真实验，局部避障成功率为94.8%，单次规划时间为32ms。"
        text_with_provenance = "仿真实验表明避障成功率达94.8%，规划延迟32ms。"
        res = auditor.check_numerical_provenance(text_with_provenance, material)
        self.assertTrue(res["passed"])

        text_with_hallucination = "仿真测试表明避障成功率达到99.9%，规划延迟仅1ms。"
        res2 = auditor.check_numerical_provenance(text_with_hallucination, material)
        self.assertFalse(res2["passed"])
        self.assertIn("99.9", res2["missing_numbers"])
        self.assertIn("1", res2["missing_numbers"])


if __name__ == "__main__":
    unittest.main()
