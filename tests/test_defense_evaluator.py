"""
Tests for OfferGet Defense Answer Evaluator and Debrief Integration.
Verifies 100-point answer rubric scoring, overclaiming defenses,
5-step safe answer reframing, and interview debrief integration.
"""

import pytest

from core.defense.evaluator import DefenseEvaluator
from core.interview_debrief import InterviewDebriefEngine


class TestDefenseEvaluator:
    def test_evasive_short_answer_low_score(self):
        q = "请详细介绍你在集群训练中如何处理慢卡隔离？"
        a = "没怎么做。"
        res = DefenseEvaluator.evaluate(q, a)
        assert res.total_score < 60.0
        assert "direct_response" in res.deductions
        assert len(res.main_problems) > 0

    def test_overclaiming_without_negation_penalized(self):
        q = "你在该项目中起到了什么作用？"
        a = "该系统全部由我完成，完全实现了最优控制，效果大幅领先业内现有竞品。"
        res = DefenseEvaluator.evaluate(q, a)
        assert "avoids_overclaiming" in res.deductions
        assert res.dimension_scores["avoids_overclaiming"] < 15.0
        assert any("全部由我完成" in p for p in res.main_problems)

    def test_overclaiming_with_negation_not_penalized(self):
        q = "你在该项目中起到了什么作用？"
        a = "我负责了核心调度逻辑开发。本项目目前并未完全实现所有极限场景的自动化处理，目前主要用于典型工况的原型验证。"
        res = DefenseEvaluator.evaluate(q, a)
        assert "avoids_overclaiming" not in res.deductions
        assert res.dimension_scores["avoids_overclaiming"] == 15.0
        assert res.dimension_scores["acknowledges_boundary"] == 15.0

    def test_well_defended_answer_high_score(self):
        q = "请说明你的通信算子优化方案、测试基线及当前局限？"
        a = (
            "针对通信算子优化问题：我主要负责基于 NCCL 原语的通信重构工作。在 1024 卡集群上，"
            "我们对比了原版 Baseline，通信开销降低了 20%，MFU 提升至 52%。"
            "当前版本主要面向密集大模型训练场景，局限在于对偶发网络抖动的自适应重传机制仍在持续优化中，"
            "团队其他成员负责监控看板与日志分析。"
        )
        res = DefenseEvaluator.evaluate(q, a)
        assert res.total_score >= 85.0
        assert res.dimension_scores["direct_response"] == 20.0
        assert res.dimension_scores["technical_details"] == 20.0
        assert res.dimension_scores["acknowledges_boundary"] == 15.0
        assert res.dimension_scores["highlights_personal_contribution"] == 15.0
        assert res.dimension_scores["avoids_overclaiming"] == 15.0

    def test_safe_answer_generation_5_steps(self):
        q = "你的系统真的达到工业级高可用了吗？"
        raw = "我们完全实现了高可用，绝对领先。"
        safe = DefenseEvaluator.generate_safe_answer(q, raw)
        lines = [l for l in safe.splitlines() if l.strip()]
        assert len(lines) == 5
        assert "正面回应" in lines[0]
        assert "实际实现" in lines[1]
        assert "边界与局限" in lines[2]
        assert "原因说明" in lines[3]
        assert "改进规划" in lines[4]


class TestInterviewDebriefIntegration:
    def test_analyze_question_attaches_defense_score(self):
        engine = InterviewDebriefEngine()
        q = "请问你在分布式训练调度中如何做慢节点剔除？"
        a = "我负责设计了心跳探针机制，在 1024 卡集群上检测慢节点，当前版本主要基于固定阈值过滤，局限在于动态阈值仍在调优。"
        item = engine.analyze_question(q, a)

        assert item.defense_score is not None
        assert isinstance(item.defense_score, dict)
        assert "total_score" in item.defense_score
        assert "dimension_scores" in item.defense_score
        assert item.defense_score["total_score"] >= 80.0
