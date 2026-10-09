from __future__ import annotations

import unittest

from seman2_runtime.cognitive_memory import MemoryPolicy
from seman2_runtime.cognitive_query import (
    AnswerStatus,
    AutobiographicalResponder,
    RelationalQuestion,
    StateQuestion,
)
from seman2_runtime.developmental_core import (
    ContextFrame,
    ContextKind,
    DevelopmentalCore,
    EpistemicState,
    Polarity,
    RelationOccurrence,
    RoleBinding,
    StateFacet,
)


def model_with_context() -> DevelopmentalCore:
    core = DevelopmentalCore(
        vector_dimension=256,
        memory_policy=MemoryPolicy(
            focal_capacity=2,
            peripheral_capacity=2,
            intermediate_capacity=2,
            long_term_capacity=2,
        ),
    )
    core.universe.add_context(ContextFrame("ctx:model", ContextKind.CURRENT))
    return core


def teach_relation(
    core: DevelopmentalCore,
    relation_ref: str,
    subject: str,
    value: str,
    *,
    epistemic_state: EpistemicState = EpistemicState.CONSOLIDATED,
    distinctiveness: float = 0.5,
) -> None:
    relation = RelationOccurrence(
        relation_ref,
        "relation:kind-of",
        (RoleBinding("subject", subject), RoleBinding("class", value)),
        "ctx:model",
        0,
        Polarity.POSITIVE,
        "actual",
        None,
        (f"experience:{relation_ref}",),
        (),
        epistemic_state,
    )
    core.universe.add_relation(relation)
    core.memory.remember(
        relation_ref,
        kind="relation",
        features=("relation:kind-of", f"subject:{subject}", f"class:{value}"),
        context_refs=("ctx:model",),
        support_refs=relation.support_refs,
        distinctiveness=distinctiveness,
    )


class CognitiveQueryTests(unittest.TestCase):
    def test_models_with_different_lives_answer_differently(self) -> None:
        informed = model_with_context()
        uninformed = model_with_context()
        teach_relation(
            informed,
            "relation:apple-fruit",
            "concept:apple",
            "concept:fruit",
        )
        question = RelationalQuestion(
            "question:apple",
            "relation:kind-of",
            (RoleBinding("subject", "concept:apple"),),
            "class",
            "ctx:model",
        )

        known = AutobiographicalResponder(informed).answer_relation(question)
        unknown = AutobiographicalResponder(uninformed).answer_relation(question)
        self.assertEqual(known.status, AnswerStatus.SUPPORTED)
        self.assertEqual(known.value_refs, ("concept:fruit",))
        self.assertEqual(unknown.status, AnswerStatus.UNKNOWN)
        self.assertEqual(unknown.communicative_act, "acknowledge-ignorance")
        self.assertFalse(known.external_source_consulted)
        self.assertFalse(unknown.external_source_consulted)

    def test_hypothesis_is_qualified_instead_of_asserted(self) -> None:
        core = model_with_context()
        teach_relation(
            core,
            "relation:possible",
            "concept:object",
            "concept:category",
            epistemic_state=EpistemicState.HYPOTHESIS,
        )
        answer = AutobiographicalResponder(core).answer_relation(
            RelationalQuestion(
                "question:possible",
                "relation:kind-of",
                (RoleBinding("subject", "concept:object"),),
                "class",
                "ctx:model",
            )
        )
        self.assertEqual(answer.status, AnswerStatus.HYPOTHETICAL)
        self.assertEqual(answer.epistemic_qualification, "hypothesis-or-expectation-only")

    def test_forgotten_content_cannot_reappear_from_universe(self) -> None:
        core = model_with_context()
        teach_relation(
            core,
            "relation:old",
            "concept:old",
            "concept:memory",
            distinctiveness=0.0,
        )
        # Trois faibles souvenirs dépassent les capacités et rendent au moins
        # l'ancien contenu cognitivement inaccessible, même si l'audit conserve
        # encore sa relation immuable.
        for index in range(5):
            core.memory.remember(
                f"noise:{index}",
                kind="episode",
                features=(f"noise:{index}",),
                context_refs=("ctx:model",),
                support_refs=(f"obs:noise:{index}",),
                distinctiveness=1.0,
            )
        self.assertFalse(core.memory.accessible("relation:old"))
        self.assertIn("relation:old", core.universe.relations)
        answer = AutobiographicalResponder(core).answer_relation(
            RelationalQuestion(
                "question:old",
                "relation:kind-of",
                (RoleBinding("subject", "concept:old"),),
                "class",
                "ctx:model",
            )
        )
        self.assertEqual(answer.status, AnswerStatus.UNKNOWN)

    def test_state_answer_keeps_temporal_provenance(self) -> None:
        core = model_with_context()
        state = StateFacet(
            "state:lamp-on",
            "object:lamp",
            "dimension:power",
            "value:on",
            "ctx:model",
            2,
            ("experience:switch",),
            EpistemicState.OBSERVED,
        )
        core.universe.add_state(state)
        core.memory.remember(
            state.state_id,
            kind="state",
            features=("dimension:power", "value:on"),
            context_refs=("ctx:model",),
            support_refs=state.support_refs,
        )
        answer = AutobiographicalResponder(core).answer_state(
            StateQuestion(
                "question:lamp",
                "object:lamp",
                "dimension:power",
                "ctx:model",
            )
        )
        self.assertEqual(answer.status, AnswerStatus.SUPPORTED)
        self.assertEqual(answer.value_refs, ("value:on",))
        self.assertEqual(answer.evidence_refs, ("state:lamp-on",))


if __name__ == "__main__":
    unittest.main()
