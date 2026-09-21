"""
Tests for OfferGet Defense Question Chains.
Verifies 2-4 layer follow-up chains across 5 dimensions and role-adapted phrasing.
"""

import pytest

from core.defense.chain import (
    DefenseQuestionChain,
    DefenseRole,
    FollowUpChain,
    QuestionChainType,
)
from core.job_flow import generate_defense_followup_chain


class TestDefenseQuestionChain:
    def test_all_five_chain_types(self):
        for ct in QuestionChainType:
            chain = DefenseQuestionChain.generate_chain(ct, num_layers=3)
            assert isinstance(chain, FollowUpChain)
            assert chain.chain_type == ct
            assert len(chain.questions) == 3
            assert chain.questions[0].layer == 1
            assert chain.questions[1].layer == 2
            assert chain.questions[2].layer == 3

    def test_layer_bounds_enforced(self):
        # Min 2 layers
        chain_min = DefenseQuestionChain.generate_chain(QuestionChainType.DATA_AUTHENTICITY, num_layers=1)
        assert len(chain_min.questions) == 2

        # Max 4 layers
        chain_max = DefenseQuestionChain.generate_chain(QuestionChainType.DATA_AUTHENTICITY, num_layers=10)
        assert len(chain_max.questions) == 4

    def test_context_text_injection(self):
        ctx = "基于 Ray 优化分布式调度"
        chain = DefenseQuestionChain.generate_chain(QuestionChainType.PROJECT_BOUNDARY, context_text=ctx, num_layers=2)
        assert ctx in chain.questions[0].question_text

    def test_role_phrasing(self):
        q_raw = "数据来源是实测还是公开数据集？"
        for role in DefenseRole:
            phrased = DefenseQuestionChain.get_role_phrasing(q_raw, role)
            assert q_raw in phrased
            assert "【" in phrased and "】" in phrased

    def test_followup_chain_to_dict(self):
        chain = DefenseQuestionChain.generate_chain(QuestionChainType.INNOVATION, num_layers=3)
        d = chain.to_dict()
        assert d["chain_type"] == "innovation"
        assert len(d["questions"]) == 3
        assert d["questions"][0]["layer"] == 1
        assert "dimension" in d["questions"][0]
        assert "intent" in d["questions"][0]


class TestJobFlowIntegration:
    def test_generate_defense_followup_chain_helper(self):
        res = generate_defense_followup_chain(
            context_text="Megatron-LM 并行优化",
            chain_type="personal_contribution",
            role="tech_interviewer",
            num_layers=3,
        )
        assert isinstance(res, dict)
        assert res["chain_type"] == "personal_contribution"
        assert len(res["questions"]) == 3
        assert "Megatron-LM" in res["questions"][0]["question"]
