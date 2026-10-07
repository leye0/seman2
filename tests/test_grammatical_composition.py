from __future__ import annotations

import hashlib
import unittest

from seman2_runtime.cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
)
from seman2_runtime.cognitive_query import AnswerStatus, AutobiographicalResponder, RelationalQuestion
from seman2_runtime.developmental_core import ContextFrame, ContextKind, DevelopmentalCore, RoleBinding
from seman2_runtime.grammatical_composition import MRSGrammaticalComposer
from seman2_runtime.semantic_admission import AdmissionStatus, SemanticAdmissionLedger


def semantic_artifact(
    *,
    session: str,
    observation_ref: str,
    subject_predicate: str,
    complement_predicate: str,
):
    registry = ArtifactTypeRegistry()
    registry.register(
        ArtifactTypeSpec(
            "semantic-structure",
            "test/semantic",
            0,
            root_allowed=True,
            allowed_producers=frozenset({"semantic-composer"}),
        )
    )
    registry.freeze()
    return ArtifactArena(registry).publish(
        ArtifactProposal(
            artifact_type="semantic-structure",
            producer_id="semantic-composer",
            producer_build="test",
            configuration_digest=hashlib.sha256(session.encode()).hexdigest(),
            mode="ingestion",
            session_id=session,
            wave=0,
            parent_ids=(),
            observation_refs=(observation_ref,),
            payload_native={
                "entities": [
                    {"id": "x3", "sort": "x", "properties": {}},
                    {"id": "x8", "sort": "x", "properties": {}},
                ],
                "events": [{"id": "e2", "sort": "e", "properties": {}}],
                "predicates": [
                    {
                        "predicate": subject_predicate,
                        "arguments": {"ARG0": "x3"},
                        "constant": None,
                    },
                    {
                        "predicate": "_be_v_id",
                        "arguments": {"ARG0": "e2", "ARG1": "x3", "ARG2": "x8"},
                        "constant": None,
                    },
                    {
                        "predicate": complement_predicate,
                        "arguments": {"ARG0": "x8"},
                        "constant": None,
                    },
                ],
                "mrs_index": "e2",
            },
            payload_projection={"truth_asserted": False},
            idempotency_key=f"semantic:{session}",
        )
    )


class GrammaticalCompositionTests(unittest.TestCase):
    def test_copular_rule_is_lexeme_independent(self) -> None:
        artifact = semantic_artifact(
            session="wug",
            observation_ref="experience:wug",
            subject_predicate="_wug_n_1",
            complement_predicate="_dax_n_1",
        )
        candidates = MRSGrammaticalComposer().compose(
            artifact, target_context_ref="ctx:model"
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.composition_kind, "copular-class-predication")
        self.assertEqual(candidate.semantic_candidate.relation_form_ref, "relation:kind-of")
        self.assertEqual(
            candidate.semantic_candidate.bindings,
            (
                RoleBinding("subject", "concept-form:external:mrs:_wug_n_1"),
                RoleBinding("class", "concept-form:external:mrs:_dax_n_1"),
            ),
        )
        self.assertFalse(candidate.selected)

    def test_two_parses_of_same_experience_do_not_consolidate(self) -> None:
        composer = MRSGrammaticalComposer()
        ledger = SemanticAdmissionLedger()
        for session in ("parse-a", "parse-b"):
            artifact = semantic_artifact(
                session=session,
                observation_ref="experience:same",
                subject_predicate="_apple_n_1",
                complement_predicate="_fruit_n_1",
            )
            composer.register_evidence(
                ledger, composer.compose(artifact, target_context_ref="ctx:model")
            )
        candidate_ref = next(iter(ledger.candidates))
        assessment = ledger.assess(candidate_ref)
        self.assertEqual(assessment.status, AdmissionStatus.PENDING)
        self.assertEqual(
            assessment.independent_support_experiences, ("experience:same",)
        )

    def test_repeated_copular_experiences_can_support_autobiographical_answer(self) -> None:
        composer = MRSGrammaticalComposer()
        ledger = SemanticAdmissionLedger()
        for session, experience in (("lesson-a", "experience:1"), ("lesson-b", "experience:2")):
            artifact = semantic_artifact(
                session=session,
                observation_ref=experience,
                subject_predicate="_apple_n_1",
                complement_predicate="_fruit_n_1",
            )
            composer.register_evidence(
                ledger, composer.compose(artifact, target_context_ref="ctx:model")
            )
        candidate_ref = next(iter(ledger.candidates))
        core = DevelopmentalCore(vector_dimension=256)
        core.universe.add_context(ContextFrame("ctx:model", ContextKind.CURRENT))
        ledger.project(core, candidate_ref, temporal_index=2)
        answer = AutobiographicalResponder(core).answer_relation(
            RelationalQuestion(
                "question:apple-kind",
                "relation:kind-of",
                (RoleBinding("subject", "concept-form:external:mrs:_apple_n_1"),),
                "class",
                "ctx:model",
            )
        )

        self.assertEqual(answer.status, AnswerStatus.SUPPORTED)
        self.assertEqual(
            answer.value_refs, ("concept-form:external:mrs:_fruit_n_1",)
        )
        self.assertEqual(len(answer.evidence_refs), 1)

if __name__ == "__main__":
    unittest.main()
