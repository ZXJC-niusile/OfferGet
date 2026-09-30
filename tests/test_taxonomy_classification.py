"""
Unit Test Suite for OfferGet Domain Taxonomy, Engineering Chains, and Metric Auditing.
Uses pytest parameterization to rigorously verify:
1. 6-Link Engineering Chain Decomposition (Data, Model, Training, Serving, Agent, Eval).
2. Owner narrative generation (0->1 from scratch vs. X->Y evolution).
3. Arithmetic verification for metric integrity (percentages, relative changes, tolerances).
4. Experience inflation audit patterns (scope inflation, unanchored superlatives, temporal confusion).
5. Education branding normalization against accredited standards.
6. Role taxonomy classification across tech, product, data, QA, and growth verticals.
"""

from __future__ import annotations

import pytest

from core.asu_modeler import AsuModeler, AuditRiskLevel, ChangeType
from core.jd_decoder import classify_jd_role_taxonomy, decode_jd


@pytest.fixture
def modeler():
    return AsuModeler()


# ============================================================================
# 1. 6-Link Engineering Chain Decomposition
# ============================================================================

def test_decompose_to_6links(modeler):
    sample_bullets = [
        "采用 Schema Linking 与 Hard Negative 挖掘构建高质量评测集",
        "设计 Transformer 混合 MLA 架构与 Modality Projection 跨模态投影",
        "通过 Full SFT 与 GRPO 强化学习对齐任务，损失函数平稳收敛",
        "基于 vLLM Continuous Batching 与 PagedAttention 压榨推理显存",
        "实现 ReAct 智能体与 Checkpoint Resume 断点状态恢复",
        "在 SWE-Bench 与 GSM8K 基准上执行 Rubric Eval，完成 5 层失败分析",
    ]
    links = modeler.decompose_to_6links(sample_bullets)
    for expected_link in ("Data", "Model", "Training", "Serving", "Agent", "Eval"):
        assert len(links[expected_link]) == 1, f"Expected 1 bullet in {expected_link}"


# ============================================================================
# 2. Owner Narrative Generation
# ============================================================================

@pytest.mark.parametrize(
    "kwargs, expected_substring",
    [
        (
            {"module_name": "轨迹合成", "is_from_scratch": True, "user_role_strength": "module_owner"},
            "轨迹合成模块 Owner · 从 0→1 架构落地",
        ),
        (
            {"module_name": "规则过滤引擎", "is_from_scratch": False, "base_arch": "规则匹配", "target_arch": "LLM ReAct Workflow"},
            "规则匹配 → LLM ReAct Workflow 演进重构",
        ),
    ],
)
def test_project_narrative_headers(modeler, kwargs, expected_substring):
    header = modeler.generate_project_narrative_header(**kwargs)
    assert expected_substring in header["subtitle"]


# ============================================================================
# 3. Metric Arithmetic Verification (Parametrized)
# ============================================================================

@pytest.mark.parametrize(
    "kwargs, expected_valid",
    [
        ({"numerator": 30.0, "denominator": 120.0, "displayed_percent": 25.0}, True),
        ({"numerator": 30.0, "denominator": 120.0, "displayed_percent": 35.0}, False),
        ({"baseline": 50.0, "result": 75.0, "displayed_change": 50.0, "change_type": ChangeType.RELATIVE_PERCENT}, True),
        ({"baseline": 50.0, "result": 75.0, "displayed_change": 25.0, "change_type": ChangeType.RELATIVE_PERCENT}, False),
    ],
)
def test_metric_arithmetic_verifier(modeler, kwargs, expected_valid):
    valid, msg = modeler.verify_metric_arithmetic(**kwargs)
    assert valid == expected_valid
    if not expected_valid:
        assert len(msg) > 0


# ============================================================================
# 4. Bullet Inflation Pattern Auditing (Parametrized)
# ============================================================================

@pytest.mark.parametrize(
    "kwargs, expected_pattern, should_exist",
    [
        # P1: Unqualified strong term
        ({"text": "主导完成全网分布式计算系统研发", "user_declared_role": "contributor"}, "P1_SCOPE_INFLATION", True),
        # Qualified strong term passes
        ({"text": "作为轨迹合成模块 Owner，负责核心调度研发", "user_declared_role": "contributor"}, "P1_SCOPE_INFLATION", False),
        # P2: Superlative
        ({"text": "打造业内首个超大规模系统"}, "P2_UNBOUNDED_SUPERLATIVE", True),
        # P3: Planned vs Past
        ({"text": "当前规划重点探索主导上线新一代模型", "verification": "planned"}, "P3_TEMPORAL_CONFUSION", True),
    ],
)
def test_audit_bullet_inflation(modeler, kwargs, expected_pattern, should_exist):
    issues = modeler.audit_bullet_inflation(**kwargs)
    pattern_found = any(i["pattern"] == expected_pattern for i in issues)
    assert pattern_found == should_exist


# ============================================================================
# 5. Education Branding Normalization
# ============================================================================

def test_education_branding_normalization(modeler):
    res = modeler.normalize_education_branding(
        institution="上海大学",
        user_declared_titles=["国家“双一流”建设高校", "原“211工程”", "全球顶级野鸡认证"],
    )
    assert "国家“双一流”建设高校" in res["validated_titles"]
    assert "原“211工程”" in res["validated_titles"]
    assert "全球顶级野鸡认证" in res["rejected_titles"]
    assert not res["is_fully_compliant"]


# ============================================================================
# 6. Role Taxonomy Classification & JD Decoding (Parametrized)
# ============================================================================

@pytest.mark.parametrize(
    "jd_text, expected_role_key, expected_title_sub",
    [
        (
            "我们需要招聘高级后端开发工程师，熟练掌握 Java/Go、gRPC、Kafka 消息队列、Redis 分布式缓存与 MySQL 分库分表。",
            "backend_distributed",
            "后端与分布式高并发架构",
        ),
        (
            "诚聘资深数据分析师，熟练使用 SQL 取数、Tableau 看板设计，主导业务漏斗分析与 A/B 测试归因。",
            "data_analyst",
            "数据分析与商业智能",
        ),
        (
            "AI 产品经理，负责大模型落地场景探索，精通 Prompt 调优与 Agent 智能体架构，推进模型评测与 RAG 落地。",
            "ai_product",
            "AI 产品经理",
        ),
    ],
)
def test_role_taxonomy_classification(jd_text, expected_role_key, expected_title_sub):
    info = classify_jd_role_taxonomy(jd_text)
    assert info["role_key"] == expected_role_key
    assert expected_title_sub in info["taxonomy"]["title"]


def test_decode_jd_with_taxonomy():
    sample_jd = """
    【岗位名称】大模型推理引擎架构师
    【所属部门】AI平台部
    岗位要求：
    1. 精通 Transformer 架构与 vLLM / SGLang 推理加速。
    2. 熟悉 CUDA / Triton 底层算子。
    3. 自驱力强，能够独立推进从0到1搭建体系。
    """
    decoded = decode_jd(sample_jd)
    assert "role_category" in decoded["metadata"]
    assert "dimensions" in decoded["metadata"]
    assert len(decoded["detected_signals"]) >= 2
