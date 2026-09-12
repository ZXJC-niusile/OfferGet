import unittest
from core.asu_modeler import AsuModeler, ChangeType, AuditRiskLevel
from core.jd_decoder import decode_jd, classify_jd_role_taxonomy

class TestAsuModeler(unittest.TestCase):
    def setUp(self):
        self.modeler = AsuModeler()

    def test_decompose_to_6links(self):
        sample_bullets = [
            "采用 Schema Linking 与 Hard Negative 挖掘构建高质量评测集",
            "设计 Transformer 混合 MLA 架构与 Modality Projection 跨模态投影",
            "通过 Full SFT 与 GRPO 强化学习对齐任务，损失函数平稳收敛",
            "基于 vLLM Continuous Batching 与 PagedAttention 压榨推理显存",
            "实现 ReAct 智能体与 Checkpoint Resume 断点状态恢复",
            "在 SWE-Bench 与 GSM8K 基准上执行 Rubric Eval，完成 5 层失败分析"
        ]
        links = self.modeler.decompose_to_6links(sample_bullets)
        self.assertEqual(len(links["Data"]), 1)
        self.assertEqual(len(links["Model"]), 1)
        self.assertEqual(len(links["Training"]), 1)
        self.assertEqual(len(links["Serving"]), 1)
        self.assertEqual(len(links["Agent"]), 1)
        self.assertEqual(len(links["Eval"]), 1)

    def test_minimal_owner_narrative_rules(self):
        # 0->1 from scratch
        header1 = self.modeler.generate_project_narrative_header(
            module_name="轨迹合成",
            is_from_scratch=True,
            user_role_strength="module_owner"
        )
        self.assertIn("轨迹合成模块 Owner · 从 0→1 架构落地", header1["subtitle"])

        # X->Y evolution
        header2 = self.modeler.generate_project_narrative_header(
            module_name="规则过滤引擎",
            is_from_scratch=False,
            base_arch="规则匹配",
            target_arch="LLM ReAct Workflow"
        )
        self.assertIn("规则匹配 → LLM ReAct Workflow 演进重构", header2["subtitle"])

    def test_metric_arithmetic_verifier(self):
        # Valid percentage
        valid, msg = self.modeler.verify_metric_arithmetic(
            numerator=30.0, denominator=120.0, displayed_percent=25.0
        )
        self.assertTrue(valid)

        # Invalid percentage (> 0.5% tolerance)
        invalid, msg = self.modeler.verify_metric_arithmetic(
            numerator=30.0, denominator=120.0, displayed_percent=35.0
        )
        self.assertFalse(invalid)
        self.assertIn("比例算术不符", msg)

        # Valid relative change
        valid_change, _ = self.modeler.verify_metric_arithmetic(
            baseline=50.0, result=75.0, displayed_change=50.0, change_type=ChangeType.RELATIVE_PERCENT
        )
        self.assertTrue(valid_change)

        # Invalid relative change
        invalid_change, _ = self.modeler.verify_metric_arithmetic(
            baseline=50.0, result=75.0, displayed_change=25.0, change_type=ChangeType.RELATIVE_PERCENT
        )
        self.assertFalse(invalid_change)

    def test_audit_bullet_inflation(self):
        # P1: Unqualified strong term
        issues = self.modeler.audit_bullet_inflation(
            text="主导完成全网分布式计算系统研发",
            user_declared_role="contributor"
        )
        self.assertTrue(any(i["pattern"] == "P1_SCOPE_INFLATION" for i in issues))

        # Qualified strong term (pass)
        issues_ok = self.modeler.audit_bullet_inflation(
            text="作为轨迹合成模块 Owner，负责核心调度研发",
            user_declared_role="contributor"
        )
        self.assertFalse(any(i["pattern"] == "P1_SCOPE_INFLATION" for i in issues_ok))

        # P2: Superlative
        issues_sup = self.modeler.audit_bullet_inflation(text="打造业内首个超大规模系统")
        self.assertTrue(any(i["pattern"] == "P2_UNBOUNDED_SUPERLATIVE" for i in issues_sup))

        # P3: Planned vs Past
        issues_planned = self.modeler.audit_bullet_inflation(
            text="当前规划重点探索主导上线新一代模型",
            verification="planned"
        )
        self.assertTrue(any(i["pattern"] == "P3_TEMPORAL_CONFUSION" for i in issues_planned))

    def test_education_branding_normalization(self):
        res = self.modeler.normalize_education_branding(
            institution="上海大学",
            user_declared_titles=["国家“双一流”建设高校", "原“211工程”", "全球顶级野鸡认证"]
        )
        self.assertIn("国家“双一流”建设高校", res["validated_titles"])
        self.assertIn("原“211工程”", res["validated_titles"])
        self.assertIn("全球顶级野鸡认证", res["rejected_titles"])
        self.assertFalse(res["is_fully_compliant"])


class TestJdTaxonomy(unittest.TestCase):
    def test_role_taxonomy_classification(self):
        jd_backend = "我们需要招聘高级后端开发工程师，熟练掌握 Java/Go、gRPC、Kafka 消息队列、Redis 分布式缓存与 MySQL 分库分表。"
        info = classify_jd_role_taxonomy(jd_backend)
        self.assertEqual(info["role_key"], "backend_distributed")
        self.assertIn("后端与分布式高并发架构", info["taxonomy"]["title"])

    def test_decode_jd_with_taxonomy(self):
        sample_jd = """
        【岗位名称】大模型推理引擎架构师
        【所属部门】AI平台部
        岗位要求：
        1. 精通 Transformer 架构与 vLLM / SGLang 推理加速。
        2. 熟悉 CUDA / Triton 底层算子。
        3. 自驱力强，能够独立推进从0到1搭建体系。
        """
        decoded = decode_jd(sample_jd)
        self.assertIn("role_category", decoded["metadata"])
        self.assertIn("dimensions", decoded["metadata"])
        # Should detect hidden signals
        self.assertTrue(len(decoded["detected_signals"]) >= 2)

if __name__ == "__main__":
    unittest.main()
