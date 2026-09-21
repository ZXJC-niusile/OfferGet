"""
Unit Test Suite for OfferGet Fact Verification Guard Module.
Tests baseline metric extraction from SSOT (candidate_profile.json),
metric inflation drift detection (54.2% -> 85%, 1024 -> 2048, 2.4h -> 10h),
unverified numerical claim flagging, tech term whitelisting, and scoring.
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

from core.fact_guard import FactVerificationGuard, verify_resume_facts


class TestFactVerificationGuard(unittest.TestCase):

    def setUp(self):
        self.profile_path = PROJECT_ROOT / "examples" / "candidate_profile.json"
        with open(self.profile_path, "r", encoding="utf-8") as f:
            self.profile_data = json.load(f)

        self.guard = FactVerificationGuard(self.profile_data)

    def test_01_baseline_metric_extraction(self):
        # Verify anchors were extracted from SSOT
        topics = {a["topic"] for a in self.guard.baseline_anchors}
        self.assertIn("cluster_size", topics)
        self.assertIn("mfu", topics)
        self.assertIn("downtime_before", topics)
        self.assertIn("downtime_after", topics)
        self.assertIn("savings", topics)
        self.assertIn("experience_years", topics)
        self.assertIn("stars", topics)

        # Check key baseline numbers in verified set
        self.assertIn(1024.0, self.guard.all_verified_numbers)
        self.assertIn(54.2, self.guard.all_verified_numbers)
        self.assertIn(38.5, self.guard.all_verified_numbers)
        self.assertIn(2.4, self.guard.all_verified_numbers)
        self.assertIn(8.0, self.guard.all_verified_numbers)
        self.assertIn(3800.0, self.guard.all_verified_numbers)
        self.assertIn(45.0, self.guard.all_verified_numbers)
        self.assertIn(48.0, self.guard.all_verified_numbers)
        self.assertIn(7.0, self.guard.all_verified_numbers)

    def test_02_strictly_grounded_bullets_pass(self):
        grounded_bullets = [
            "主导 64B Dense 及 230B MoE（激活 32B）基座大模型在 1024 卡 H800 集群上的预训练全流程，端到端 MFU 从 38.5% 优化至 54.2%，提前 3 周完成千亿 Token 训练里程碑。",
            "将大模型训练任务因单卡故障导致的日均有效中断时间从 2.4 小时压减至 8 分钟以內，训练可用率达 99.4%。",
            "在移除 Critic 网络的条件下显存消耗减少 48%，模型在 GSM8K 与 MATH 基准准确率分别提升 14.2% 与 11.6%。",
            "单 Token 推理成本降低 62%，P99 延迟降低 45%，年均节省云算力开销 3800 万元。",
            "TTFT（首字响应时间）均值从 1.8s 下降至 320ms。"
        ]

        res = self.guard.verify_facts(grounded_bullets)
        self.assertTrue(res["passed"])
        self.assertEqual(res["verdict"], "FACT_CHECK_PASSED")
        self.assertEqual(res["score"], 100.0)
        self.assertEqual(len(res["drifts"]), 0)
        self.assertEqual(len(res["unverified_claims"]), 0)
        self.assertEqual(len(res["verified_bullets"]), len(grounded_bullets))

    def test_03_detect_mfu_inflation_drift(self):
        # 54.2% -> 85%
        inflated_bullet = (
            "主导基座大模型在 1024 卡 H800 集群上的预训练全流程，"
            "端到端 MFU 从 38.5% 优化至 85%，提前 3 周完成训练里程碑。"
        )

        res = self.guard.verify_facts(inflated_bullet)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FACT_DRIFT_DETECTED")
        self.assertGreater(len(res["drifts"]), 0)

        drift = res["drifts"][0]
        self.assertIn("85%", drift["claimed_metric"])
        self.assertIn("54.2%", drift["verified_baseline"])
        self.assertEqual(drift["metric_type"], "mfu")

    def test_04_detect_cluster_size_inflation_drift(self):
        # 1024 -> 2048
        inflated_bullet = (
            "主导 230B MoE 基座大模型在 2048 卡 H800 集群上的预训练全流程，"
            "端到端 MFU 优化至 54.2%。"
        )

        res = self.guard.verify_facts(inflated_bullet)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FACT_DRIFT_DETECTED")
        self.assertGreater(len(res["drifts"]), 0)

        drift = [d for d in res["drifts"] if d["metric_type"] == "cluster_size"][0]
        self.assertIn("2048", drift["claimed_metric"])
        self.assertIn("1024", drift["verified_baseline"])

    def test_05_detect_downtime_inflation_drift(self):
        # 2.4小时 -> 10小时
        inflated_bullet = (
            "将大模型训练任务因单卡故障导致的日均有效中断时间从 10 小时压减至 8 分钟以內，"
            "训练可用率达 99.4%。"
        )

        res = self.guard.verify_facts(inflated_bullet)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FACT_DRIFT_DETECTED")
        self.assertGreater(len(res["drifts"]), 0)

        drift = [d for d in res["drifts"] if "downtime" in d["metric_type"]][0]
        self.assertIn("10", drift["claimed_metric"])
        self.assertIn("2.4", drift["verified_baseline"])

    def test_06_detect_savings_inflation_drift(self):
        # 3800 万元 -> 5000 万元
        inflated_bullet = "优化高并发推理服务中台，年均节省云算力开销 5000 万元。"

        res = self.guard.verify_facts(inflated_bullet)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FACT_DRIFT_DETECTED")
        self.assertGreater(len(res["drifts"]), 0)

        drift = res["drifts"][0]
        self.assertIn("5000", drift["claimed_metric"])
        self.assertIn("3800", drift["verified_baseline"])

    def test_07_detect_unverified_numerical_claim(self):
        # Numbers with no anchor in SSOT (e.g. 50 人, 99999 次)
        hallucinated_bullet = "负责跨部门敏捷管理，带领 50 位工程师，累计处理 99999 次系统请求。"

        res = self.guard.verify_facts(hallucinated_bullet)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FACT_DRIFT_DETECTED")
        self.assertGreater(len(res["unverified_claims"]), 0)

        claimed_numbers = [c["claimed_metric"] for c in res["unverified_claims"]]
        self.assertTrue(any("50" in c for c in claimed_numbers))
        self.assertTrue(any("99999" in c for c in claimed_numbers))

    def test_08_whitelist_tech_names_and_dates(self):
        # Technical identifiers like C++20, FlashAttention-2/3, ZeRO-3, GPT-4o, FP8, 2023.03
        # should NOT be flagged as ungrounded numerical claims
        bullet_with_tech_terms = (
            "精通 C++20 与 CUDA 编程，熟练运用 FlashAttention-2/3 与 ZeRO-3 框架，"
            "在 2020.08 - 2023.02 期间主导研发，适配 FP8 (E4M3) 与 GPT-4o 评测基准。"
        )

        res = self.guard.verify_facts(bullet_with_tech_terms)
        self.assertTrue(res["passed"])
        self.assertEqual(res["verdict"], "FACT_CHECK_PASSED")
        self.assertEqual(len(res["drifts"]), 0)
        self.assertEqual(len(res["unverified_claims"]), 0)

    def test_09_top_level_convenience_function(self):
        bullet = "主导 1024 卡集群预训练，MFU 优化至 54.2%，提前 3 周交付。"
        res = verify_resume_facts(bullet, self.profile_path)
        self.assertTrue(res["passed"])
        self.assertEqual(res["verdict"], "FACT_CHECK_PASSED")

        bad_bullet = "主导 2048 卡集群预训练，MFU 优化至 85%。"
        res_bad = verify_resume_facts(bad_bullet, self.profile_data)
        self.assertFalse(res_bad["passed"])
        self.assertEqual(res_bad["verdict"], "FACT_DRIFT_DETECTED")

    def test_10_dict_resume_verification(self):
        # Verifying a full dictionary containing highlights
        tailored_resume_dict = {
            "experience": [
                {
                    "company": "Frontier AI Lab",
                    "highlights": [
                        {"claim_zh": "主导 1024 卡 H800 集群预训练，端到端 MFU 优化至 54.2%，提前 3 周完成里程碑。"},
                        {"claim_zh": "慢卡秒级隔离系统，日均有效中断时间从 2.4 小时压减至 8 分钟以內，可用率达 99.4%。"}
                    ]
                }
            ]
        }

        res = self.guard.verify_facts(tailored_resume_dict)
        self.assertTrue(res["passed"])
        self.assertEqual(res["verdict"], "FACT_CHECK_PASSED")
        self.assertEqual(len(res["verified_bullets"]), 2)

    def test_11_detect_ungrounded_technology(self):
        # Candidate only has SQLite in profile, bullet introduces Redis
        profile_sqlite = {
            "candidate": {"name": "张同学", "title_zh": "后端开发"},
            "skills": ["Python", "SQLite"],
            "experience": [
                {
                    "company": "科技公司B",
                    "role": "后端开发",
                    "bullets": ["使用 SQLite 设计并实现课程数据表的 SQL 查询接口。"]
                }
            ]
        }
        guard = FactVerificationGuard(profile_sqlite)
        ungrounded_bullet = "基于 Redis 缓存热点数据，查询延迟降低 30%。"
        res = guard.verify_facts(ungrounded_bullet)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FACT_DRIFT_DETECTED")
        claimed_unv = [u["claimed_metric"] for u in res["unverified_claims"]]
        self.assertTrue(any("Redis" in c or "redis" in c.lower() for c in claimed_unv))

    def test_12_detect_ungrounded_method_and_framework_expansion(self):
        # Candidate only has "负责训练流水线优化，通信开销降低 20%。"
        base = {
            "candidate": {"name": "李四", "title_zh": "大模型算法工程师"},
            "experience": [
                {
                    "company": "科技公司A",
                    "role": "算法研究员",
                    "bullets": ["负责训练流水线优化，通信开销降低 20%。"]
                }
            ]
        }
        guard = FactVerificationGuard(base)
        # Bullet introduces Megatron-LM and operator refactoring
        hallucinated_bullet = "基于 Megatron-LM 重构并行训练通信算子，通信开销降低 20%。"
        res = guard.verify_facts(hallucinated_bullet)
        self.assertFalse(res["passed"])
        self.assertEqual(res["verdict"], "FACT_DRIFT_DETECTED")
        claimed_unv = [u["claimed_metric"] for u in res["unverified_claims"]]
        self.assertTrue(any("Megatron-LM" in c for c in claimed_unv))
        self.assertTrue(any("通信算子" in c or "算子重构" in c or "并行训练" in c for c in claimed_unv))

    def test_13_grounded_tech_and_method_pass(self):
        # Truly grounded rewrite without unsupported facts passes
        base = {
            "candidate": {"name": "李四", "title_zh": "大模型算法工程师"},
            "experience": [
                {
                    "company": "科技公司A",
                    "role": "算法研究员",
                    "bullets": ["负责训练流水线优化，通信开销降低 20%。"]
                }
            ]
        }
        guard = FactVerificationGuard(base)
        grounded_bullet = "负责训练流水线与通信优化，通信开销降低 20%。"
        res = guard.verify_facts(grounded_bullet)
        self.assertTrue(res["passed"])
        self.assertEqual(res["verdict"], "FACT_CHECK_PASSED")

        # When profile contains Megatron-LM and operator refactoring, it passes
        base_with_megatron = {
            "candidate": {"name": "李四", "title_zh": "大模型算法工程师"},
            "competencies": {"frameworks": ["Megatron-LM", "通信算子重构", "并行训练"]},
            "experience": [
                {
                    "company": "科技公司A",
                    "role": "算法研究员",
                    "bullets": ["负责训练流水线优化，通信开销降低 20%。"]
                }
            ]
        }
        guard_megatron = FactVerificationGuard(base_with_megatron)
        megatron_bullet = "基于 Megatron-LM 重构并行训练通信算子，通信开销降低 20%。"
        res_megatron = guard_megatron.verify_facts(megatron_bullet)
        self.assertTrue(res_megatron["passed"])
        self.assertEqual(res_megatron["verdict"], "FACT_CHECK_PASSED")

    def test_14_competency_cannot_authorize_specific_experience_expansion(self):
        # Counterexample 1: Candidate only has Redis / Megatron-LM in competencies.
        # Specific experience bullet only mentions "负责数据存储".
        # Rewritten bullet introducing Redis or Megatron-LM must be flagged as ungrounded under experience scope.
        profile = {
            "candidate": {"name": "张三", "title_zh": "后端开发工程师"},
            "competencies": {
                "frameworks": ["Redis", "Megatron-LM", "通信算子重构"]
            },
            "experience": [
                {
                    "company": "科技公司A",
                    "role": "后端开发",
                    "bullets": ["负责数据存储。"]
                }
            ]
        }
        guard = FactVerificationGuard(profile)

        # 1a. Bullet introducing Redis under experience scope
        redis_bullet = "负责基于 Redis 的数据缓存与持久化。"
        res_scope_str = guard.verify_bullet(redis_bullet, target_scope="experience[0]")
        self.assertFalse(res_scope_str["passed"])
        self.assertEqual(res_scope_str["verdict"], "FACT_DRIFT_DETECTED")
        claimed_unv_1 = [u["claimed_metric"] for u in res_scope_str["unverified_claims"]]
        self.assertTrue(any("Redis" in c or "redis" in c.lower() for c in claimed_unv_1))

        # Also test with company name scope
        res_company = guard.verify_bullet(redis_bullet, target_scope="科技公司A")
        self.assertFalse(res_company["passed"])

        # Also test with target_excerpt scope
        res_excerpt = guard.verify_bullet(redis_bullet, target_excerpt="负责数据存储。")
        self.assertFalse(res_excerpt["passed"])

        # 1b. Bullet introducing Megatron-LM / operator refactoring under experience scope
        megatron_bullet = "基于 Megatron-LM 重构并行训练通信算子，通信开销降低 20%。"
        res_megatron = guard.verify_bullet(megatron_bullet, target_scope="experience[0]")
        self.assertFalse(res_megatron["passed"])
        self.assertEqual(res_megatron["verdict"], "FACT_DRIFT_DETECTED")
        claimed_unv_2 = [u["claimed_metric"] for u in res_megatron["unverified_claims"]]
        self.assertTrue(any("Megatron-LM" in c for c in claimed_unv_2))

        # 1c. Positive case: when experience explicitly mentions Redis, it passes under experience scope
        profile_grounded = {
            "candidate": {"name": "张三", "title_zh": "后端开发工程师"},
            "competencies": {
                "frameworks": ["Redis"]
            },
            "experience": [
                {
                    "company": "科技公司A",
                    "role": "后端开发",
                    "bullets": ["负责基于 Redis 的数据存储与缓存架构。"]
                }
            ]
        }
        guard_grounded = FactVerificationGuard(profile_grounded)
        res_grounded = guard_grounded.verify_bullet(redis_bullet, target_scope="experience[0]")
        self.assertTrue(res_grounded["passed"])
        self.assertEqual(res_grounded["verdict"], "FACT_CHECK_PASSED")
        self.assertEqual(len(res_grounded["unverified_claims"]), 0)

    def test_15_project_a_tech_cannot_authorize_project_b(self):
        # Counterexample 2: Candidate Project A has Redis, Project B only has SQLite.
        # Project B rewrite cannot borrow Redis from Project A.
        profile = {
            "candidate": {"name": "李四", "title_zh": "全栈开发工程师"},
            "projects": [
                {
                    "name": "Project A",
                    "bullets": ["使用 Redis 实现高并发缓存系统。"]
                },
                {
                    "name": "Project B",
                    "bullets": ["使用 SQLite 设计并实现课程数据表的 SQL 查询接口。"]
                }
            ]
        }
        guard = FactVerificationGuard(profile)

        # Rewrite for Project B introducing Redis must fail under Project B scope
        bullet_b_redis = "基于 Redis 缓存热点数据，提高系统并发与响应能力。"
        res_b = guard.verify_bullet(bullet_b_redis, target_scope="projects[1]")
        self.assertFalse(res_b["passed"])
        self.assertEqual(res_b["verdict"], "FACT_DRIFT_DETECTED")
        claimed_unv = [u["claimed_metric"] for u in res_b["unverified_claims"]]
        self.assertTrue(any("Redis" in c or "redis" in c.lower() for c in claimed_unv))

        # Also fails with project name scope
        res_b_name = guard.verify_bullet(bullet_b_redis, target_scope="Project B")
        self.assertFalse(res_b_name["passed"])

        # Positive case: Project A rewrite using Redis passes under Project A scope
        bullet_a_redis = "基于 Redis 优化高并发缓存架构。"
        res_a = guard.verify_bullet(bullet_a_redis, target_scope="projects[0]")
        self.assertTrue(res_a["passed"])
        self.assertEqual(res_a["verdict"], "FACT_CHECK_PASSED")

        # Positive case: Project B rewrite using SQLite passes under Project B scope
        bullet_b_sqlite = "基于 SQLite 优化课程数据表的 SQL 查询接口与索引。"
        res_b_sqlite = guard.verify_bullet(bullet_b_sqlite, target_scope="projects[1]")
        self.assertTrue(res_b_sqlite["passed"])
        self.assertEqual(res_b_sqlite["verdict"], "FACT_CHECK_PASSED")

    def test_16_negated_or_planned_tech_cannot_authorize_expansion(self):
        # Negation case: Experience text says "调研了 Redis 但未采用"
        profile_negated = {
            "candidate": {"name": "王五", "title_zh": "后端开发工程师"},
            "experience": [
                {
                    "company": "科技公司C",
                    "role": "后端开发",
                    "bullets": [
                        "负责数据层架构选型，调研了 Redis 但未采用，最终基于 SQLite 完成单机存储方案开发。"
                    ]
                }
            ]
        }
        guard_neg = FactVerificationGuard(profile_negated)
        bullet_redis = "负责基于 Redis 的数据缓存与持久化。"
        res_neg = guard_neg.verify_bullet(bullet_redis, target_scope="experience[0]")
        self.assertFalse(res_neg["passed"])
        self.assertEqual(res_neg["verdict"], "FACT_DRIFT_DETECTED")
        claimed_unv_neg = [u["claimed_metric"] for u in res_neg["unverified_claims"]]
        self.assertTrue(any("Redis" in c or "redis" in c.lower() for c in claimed_unv_neg))

        # Planning case: Experience text says "计划后续引入 Megatron-LM"
        profile_planned = {
            "candidate": {"name": "赵六", "title_zh": "算法工程师"},
            "experience": [
                {
                    "company": "科技公司D",
                    "role": "算法工程师",
                    "bullets": [
                        "负责模型推理加速，计划后续引入 Megatron-LM 进行算子融合重构。"
                    ]
                }
            ]
        }
        guard_plan = FactVerificationGuard(profile_planned)
        bullet_megatron = "基于 Megatron-LM 重构并行训练通信算子。"
        res_plan = guard_plan.verify_bullet(bullet_megatron, target_scope="experience[0]")
        self.assertFalse(res_plan["passed"])
        self.assertEqual(res_plan["verdict"], "FACT_DRIFT_DETECTED")
        claimed_unv_plan = [u["claimed_metric"] for u in res_plan["unverified_claims"]]
        self.assertTrue(any("Megatron-LM" in c for c in claimed_unv_plan))


if __name__ == "__main__":
    unittest.main()
