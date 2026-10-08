"""Descriptive aliases must preserve both historical chain models exactly."""

import pickle
from dataclasses import fields
from typing import get_args, get_type_hints

from core import defense
from core.defense import chain, simulator
from core.job_flow import generate_defense_followup_chain


def test_public_aliases_preserve_historical_class_identities():
    assert defense.FollowUpChain is chain.FollowUpChain
    assert defense.QuestionFollowUpChain is chain.FollowUpChain
    assert chain.QuestionFollowUpChain is chain.FollowUpChain
    assert defense.ProjectInterrogationChain is simulator.FollowUpChain
    assert simulator.ProjectInterrogationChain is simulator.FollowUpChain
    assert defense.QuestionFollowUpChain is not defense.ProjectInterrogationChain
    assert "QuestionFollowUpChain" in defense.__all__
    assert "FollowUpChain" in defense.__all__
    assert "ProjectInterrogationChain" in defense.__all__


def test_question_generator_retains_schema_and_field_order():
    result = defense.DefenseQuestionChain.generate_chain(defense.QuestionChainType.INNOVATION)
    assert isinstance(result, defense.QuestionFollowUpChain)
    assert [field.name for field in fields(result)] == ["chain_type", "title", "questions", "role"]
    assert list(result.to_dict()) == ["chain_type", "title", "role", "questions"]
    assert len(result.questions) == 3
    assert isinstance(result.role, defense.DefenseRole)
    assert list(generate_defense_followup_chain("innovation")) == list(result.to_dict())


def test_simulator_public_result_uses_project_interrogation_model():
    result = defense.DefenseSimulator().simulate("Built a Python API and reduced response latency by 50%.")
    assert result.follow_up_chains
    expected = ["chain_id", "target_claim_id", "target_claim", "category", "gap", "risk_basis",
                "risk_level", "role", "rounds", "defensive_strategy"]
    for item in result.follow_up_chains:
        assert isinstance(item, defense.ProjectInterrogationChain)
        assert not isinstance(item, defense.QuestionFollowUpChain)
        assert [field.name for field in fields(item)] == expected
        assert list(item.to_dict()) == expected
        assert all(isinstance(round_, defense.FollowUpRound) for round_ in item.rounds)
    assert result.to_dict()["follow_up_chains"] == [item.to_dict() for item in result.follow_up_chains]


def test_descriptive_annotations_resolve_to_historical_models():
    assert get_type_hints(chain.DefenseQuestionChain.generate_chain)["return"] is chain.FollowUpChain
    assert get_args(get_type_hints(simulator.DefenseSimulationResult)["follow_up_chains"]) == (simulator.FollowUpChain,)
    assert get_args(get_type_hints(simulator.DefenseSimulator._generate_follow_up_chains)["return"]) == (simulator.FollowUpChain,)


def test_pickle_names_and_roundtrips_remain_compatible():
    question = defense.QuestionFollowUpChain(defense.QuestionChainType.INNOVATION, "Synthetic title")
    project = defense.ProjectInterrogationChain("chain", "claim", "Synthetic claim", "metric",
                                               "Evidence missing", "Material-derived", "High", "Interviewer")
    for instance, module in [(question, "core.defense.chain"), (project, "core.defense.simulator")]:
        cls = type(instance)
        assert cls.__name__ == cls.__qualname__ == "FollowUpChain"
        assert cls.__module__ == module
        serialized = pickle.dumps(instance, protocol=4)
        assert module.encode() in serialized
        assert b"FollowUpChain" in serialized
        assert b"QuestionFollowUpChain" not in serialized
        assert b"ProjectInterrogationChain" not in serialized
        restored = pickle.loads(serialized)
        assert type(restored) is cls
        assert restored == instance
        assert restored.to_dict() == instance.to_dict()
