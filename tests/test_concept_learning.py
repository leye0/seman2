from __future__ import annotations

import unittest

from seman2_runtime.concept_learning import (
    ConceptInducer,
    InductionPolicy,
    StructuralOccurrence,
)
from seman2_runtime.developmental_core import ContextFrame, ContextKind, DevelopmentalCore


def occurrence(
    ref: str,
    factors: tuple[str, ...],
    outcome: str,
    *,
    context: str = "ctx:lesson",
) -> StructuralOccurrence:
    return StructuralOccurrence(
        occurrence_ref=ref,
        structural_factors=factors,
        context_refs=(context,),
        outcome_refs=(outcome,),
        support_refs=(f"obs:{ref}",),
    )


class ConceptInducerTests(unittest.TestCase):
    def test_anonymous_structure_generalizes_to_held_out_combination(self) -> None:
        inducer = ConceptInducer()
        inducer.observe(
            occurrence(
                "apple-1",
                ("role:patient", "event:eat", "outcome:nourished", "shape:round"),
                "outcome:nourished",
            )
        )
        inducer.observe(
            occurrence(
                "pear-1",
                ("role:patient", "event:eat", "outcome:nourished", "shape:elongated"),
                "outcome:nourished",
            )
        )
        inducer.observe(
            occurrence(
                "ball-1",
                ("role:theme", "event:throw", "outcome:play", "shape:round"),
                "outcome:play",
            )
        )
        structures = inducer.induce()
        target = next(
            row
            for row in structures
            if {"role:patient", "event:eat", "outcome:nourished"}
            <= set(row.structural_pattern)
        )

        self.assertTrue(target.learned_structure_id.startswith("learned:"))
        self.assertNotIn("fruit", target.learned_structure_id)
        matches = inducer.match(
            ("role:patient", "event:eat", "outcome:nourished", "colour:purple")
        )
        held_out = next(row for row in matches if row.structure_ref == target.learned_structure_id)
        self.assertTrue(held_out.full_match)
        ball_match = inducer.match(("role:theme", "event:throw", "outcome:play"))
        self.assertFalse(
            next(row for row in ball_match if row.structure_ref == target.learned_structure_id).full_match
        )

    def test_divergent_outcomes_propose_explainable_specializations(self) -> None:
        inducer = ConceptInducer(
            InductionPolicy(minimum_support=2, minimum_specialization_support=2)
        )
        for ref, domain, outcome, extra in (
            ("physical-1", "domain:physical", "outcome:liquid-held", "material:rigid"),
            ("physical-2", "domain:physical", "outcome:liquid-held", "material:rigid"),
            ("digital-1", "domain:digital", "outcome:data-held", "interface:file"),
            ("digital-2", "domain:digital", "outcome:data-held", "interface:file"),
        ):
            inducer.observe(
                occurrence(
                    ref,
                    ("structure:container", "role:content", domain, extra),
                    outcome,
                )
            )
        structures = inducer.induce()
        parent = next(
            row
            for row in structures
            if set(row.structural_pattern) == {"structure:container", "role:content"}
        )
        proposals = inducer.propose_specializations(parent.learned_structure_id)

        self.assertEqual({row.outcome_ref for row in proposals}, {"outcome:data-held", "outcome:liquid-held"})
        self.assertEqual({row.support_count for row in proposals}, {2})
        self.assertIn(
            "domain:physical",
            next(row for row in proposals if row.outcome_ref == "outcome:liquid-held").differentiating_pattern,
        )
        self.assertIn(
            "domain:digital",
            next(row for row in proposals if row.outcome_ref == "outcome:data-held").differentiating_pattern,
        )

    def test_learned_structure_reenters_forms_and_cognitive_memory(self) -> None:
        core = DevelopmentalCore(vector_dimension=512, seed="concept-test")
        core.universe.add_context(ContextFrame("ctx:lesson", ContextKind.CURRENT))
        inducer = ConceptInducer()
        for ref, colour in (("one", "colour:red"), ("two", "colour:blue")):
            inducer.observe(
                occurrence(
                    ref,
                    ("role:patient", "event:roll", "shape:round", colour),
                    "outcome:moved",
                )
            )
        target = next(
            row
            for row in inducer.induce()
            if {"role:patient", "event:roll", "shape:round"}
            <= set(row.structural_pattern)
        )
        form = inducer.materialize_distributed_prototype(
            target.learned_structure_id, core=core, context_ref="ctx:lesson"
        )

        self.assertEqual(form.form_id, f"form:{target.learned_structure_id}")
        self.assertEqual(
            inducer.structures[target.learned_structure_id].distributed_prototype_ref,
            form.form_id,
        )
        self.assertTrue(core.memory.accessible(target.learned_structure_id))
        self.assertEqual(
            len(core.explain_form(form.form_id)), len(target.structural_pattern)
        )


if __name__ == "__main__":
    unittest.main()
