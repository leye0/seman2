from __future__ import annotations

import unittest

from seman2_runtime.contracts import ContractError
from seman2_runtime.developmental_core import (
    ContextFrame,
    ContextKind,
    DevelopmentalCore,
    EpistemicState,
    RoleBinding,
)
from seman2_runtime.semantic_admission import (
    AdmissionStatus,
    EvidenceOccurrence,
    EvidencePolarity,
    SemanticAdmissionLedger,
    SemanticCandidate,
)


def evidence(
    ref: str,
    experience: str,
    analysis: str,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> EvidenceOccurrence:
    return EvidenceOccurrence(
        ref,
        "candidate:apple-fruit",
        experience,
        analysis,
        f"source:{experience}",
        polarity,
        1.0,
        "linguistic-observation",
    )


class SemanticAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = SemanticAdmissionLedger()
        self.candidate = SemanticCandidate(
            "candidate:apple-fruit",
            "relation:kind-of",
            (
                RoleBinding("subject", "concept:apple"),
                RoleBinding("class", "concept:fruit"),
            ),
            "ctx:model",
        )
        self.ledger.register_candidate(self.candidate)

    def test_multiple_parses_of_one_experience_count_once(self) -> None:
        self.ledger.observe(evidence("evidence:parse-1", "experience:1", "mrs:1"))
        self.ledger.observe(evidence("evidence:parse-2", "experience:1", "mrs:2"))
        self.ledger.observe(evidence("evidence:parse-3", "experience:1", "mrs:3"))
        assessment = self.ledger.assess(self.candidate.candidate_ref)

        self.assertEqual(assessment.status, AdmissionStatus.PENDING)
        self.assertEqual(assessment.independent_support_experiences, ("experience:1",))
        self.assertEqual(assessment.support_weight, 1.0)

    def test_independent_repetition_consolidates_and_projects_relation(self) -> None:
        self.ledger.observe(evidence("evidence:1", "experience:1", "mrs:1"))
        self.ledger.observe(evidence("evidence:2", "experience:2", "mrs:2"))
        assessment = self.ledger.assess(self.candidate.candidate_ref)
        core = DevelopmentalCore(vector_dimension=256)
        core.universe.add_context(ContextFrame("ctx:model", ContextKind.CURRENT))
        projection = self.ledger.project(core, self.candidate.candidate_ref, temporal_index=2)

        self.assertEqual(assessment.status, AdmissionStatus.CONSOLIDATED)
        relation = core.universe.relations[projection.relation_occurrence_ref]
        self.assertEqual(relation.epistemic_state, EpistemicState.CONSOLIDATED)
        self.assertTrue(core.memory.accessible(relation.relation_occurrence_id))

    def test_contradiction_adds_contested_projection_without_rewriting_past(self) -> None:
        self.ledger.observe(evidence("evidence:1", "experience:1", "mrs:1"))
        self.ledger.observe(evidence("evidence:2", "experience:2", "mrs:2"))
        core = DevelopmentalCore(vector_dimension=256)
        core.universe.add_context(ContextFrame("ctx:model", ContextKind.CURRENT))
        first = self.ledger.project(core, self.candidate.candidate_ref, temporal_index=2)
        self.ledger.observe(
            evidence(
                "evidence:contradiction",
                "experience:3",
                "correction:1",
                EvidencePolarity.CONTRADICTION,
            )
        )
        second = self.ledger.project(core, self.candidate.candidate_ref, temporal_index=3)

        self.assertEqual(second.assessment.status, AdmissionStatus.CONTESTED)
        self.assertIn(first.relation_occurrence_ref, core.universe.relations)
        self.assertEqual(
            core.universe.relations[first.relation_occurrence_ref].epistemic_state,
            EpistemicState.CONSOLIDATED,
        )
        self.assertEqual(
            core.universe.relations[second.relation_occurrence_ref].epistemic_state,
            EpistemicState.CONTESTED,
        )
        self.assertEqual(second.previous_projection_refs, (first.relation_occurrence_ref,))
        self.assertEqual(len(self.ledger.assessment_history[self.candidate.candidate_ref]), 2)

    def test_pending_candidate_cannot_be_projected(self) -> None:
        self.ledger.observe(evidence("evidence:1", "experience:1", "mrs:1"))
        core = DevelopmentalCore(vector_dimension=256)
        core.universe.add_context(ContextFrame("ctx:model", ContextKind.CURRENT))
        with self.assertRaises(ContractError):
            self.ledger.project(core, self.candidate.candidate_ref, temporal_index=1)


if __name__ == "__main__":
    unittest.main()
