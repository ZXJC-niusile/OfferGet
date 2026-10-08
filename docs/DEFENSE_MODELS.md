# Public defense chain models

The defense package has two deliberately distinct chain schemas. Use their
descriptive public names in new code:

```python
from core.defense import (
    DefenseQuestionChain,
    DefenseSimulator,
    ProjectInterrogationChain,
    QuestionChainType,
    QuestionFollowUpChain,
)

questions = DefenseQuestionChain.generate_chain(QuestionChainType.INNOVATION)
assert isinstance(questions, QuestionFollowUpChain)
for question in questions.questions:
    print(question.question_text)

result = DefenseSimulator().simulate("Built a Python API and reduced latency by 50%.")
for chain in result.follow_up_chains:
    assert isinstance(chain, ProjectInterrogationChain)
    for round_ in chain.rounds:
        print(round_.question)
```

The example is synthetic input for generating challenges; it is not verified evidence.

## Question progression

`QuestionFollowUpChain` is the type returned by `DefenseQuestionChain.generate_chain()`.
Its dataclass fields remain `chain_type`, `title`, `questions`, and `role`.
`chain_type` and `role` use `QuestionChainType` and `DefenseRole` enums. Its `to_dict()`
keys remain `chain_type`, `title`, `role`, and `questions`.

`core.job_flow.generate_defense_followup_chain()` returns this model's dictionary,
not the simulator's rounds schema.

## Project interrogation

`ProjectInterrogationChain` is the element type of
`DefenseSimulationResult.follow_up_chains`. Its dataclass fields and `to_dict()` keys
remain `chain_id`, `target_claim_id`, `target_claim`, `category`, `gap`, `risk_basis`,
`risk_level`, `role`, `rounds`, and `defensive_strategy`. It retains claim/evidence
context and each round's interviewer intent and vulnerability probe.

The schemas are not interchangeable. No automatic conversion is provided because
it would discard meaning or require inventing missing fields.

## Historical imports remain stable

- `core.defense.FollowUpChain` and `core.defense.chain.FollowUpChain` remain the
  question model, identical to `QuestionFollowUpChain`.
- `core.defense.simulator.FollowUpChain` remains the rounds model, identical to
  `ProjectInterrogationChain`.
- The existing `core.defense.ProjectInterrogationChain` export is unchanged.
- Both class names, modules, constructor field order, serialization, and pickle
  identities remain unchanged. The descriptive names are aliases, not subclasses
  or replacement classes.

Do not test simulator chains against `core.defense.FollowUpChain`; use
`ProjectInterrogationChain` for that API.
