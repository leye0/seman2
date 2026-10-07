from __future__ import annotations

import unittest

from seman2_runtime.open_vocabulary import (
    FormEvidence,
    FormInterpretationCandidate,
    InterpretationKind,
    LexicalAction,
    ObservedForm,
    OpenVocabularyBuilder,
    RepairBeam,
    SurfaceEdit,
    UtteranceRepairHypothesis,
)


class OpenVocabularyTests(unittest.TestCase):
    def test_unknown_form_still_has_syntactic_and_semantic_slots(self) -> None:
        observed = ObservedForm("obs:1", "ctx:1", "glorped", 5, 12)
        placeholder = OpenVocabularyBuilder().build(
            observed,
            phonological_candidates=("ɡlɔɹpt",),
            morphological_candidates=("glorp", "-ed"),
            category_candidates=("verb", "adjective"),
            syntactic_slots=("predicate",),
            semantic_role_slots=("ARG0:event", "ARG1:participant"),
        )
        decision = OpenVocabularyBuilder().decide(placeholder)

        self.assertEqual(placeholder.observed.surface, "glorped")
        self.assertEqual(
            placeholder.semantic_role_slots,
            ("ARG0:event", "ARG1:participant"),
        )
        self.assertEqual(decision.action, LexicalAction.PRESERVE_AS_NEW)
        self.assertIsNone(decision.selected_ref)

    def test_ambiguous_agreement_repairs_remain_concurrent(self) -> None:
        text = "The duck are sick"
        noun_edit = SurfaceEdit(
            4, 8, "duck", "ducks", InterpretationKind.AGREEMENT_REPAIR
        )
        verb_edit = SurfaceEdit(
            9, 12, "are", "is", InterpretationKind.AGREEMENT_REPAIR
        )
        beam = RepairBeam(
            text,
            (
                UtteranceRepairHypothesis(
                    "repair:noun",
                    (noun_edit,),
                    ("grammar:number-plural",),
                    0.71,
                    InterpretationKind.AGREEMENT_REPAIR,
                ),
                UtteranceRepairHypothesis(
                    "repair:verb",
                    (verb_edit,),
                    ("grammar:number-singular",),
                    0.70,
                    InterpretationKind.AGREEMENT_REPAIR,
                ),
            ),
        )

        self.assertEqual(beam.observed_text, text)
        self.assertEqual(beam.render("repair:noun"), "The ducks are sick")
        self.assertEqual(beam.render("repair:verb"), "The duck is sick")
        self.assertEqual(len(beam.hypotheses), 2)

    def test_observed_surface_survives_standard_repair_candidate(self) -> None:
        text = "The stars is singing"
        beam = RepairBeam(
            text,
            (
                UtteranceRepairHypothesis(
                    "repair:standard",
                    (
                        SurfaceEdit(
                            10,
                            12,
                            "is",
                            "are",
                            InterpretationKind.AGREEMENT_REPAIR,
                        ),
                    ),
                    ("grammar:plural-agreement",),
                    0.81,
                    InterpretationKind.AGREEMENT_REPAIR,
                ),
            ),
        )

        self.assertEqual(beam.observed_text, text)
        self.assertEqual(beam.render("repair:standard"), "The stars are singing")

    def test_interpretive_repair_does_not_trigger_social_correction(self) -> None:
        observed = ObservedForm("obs:2", "ctx:2", "teh", 0, 3)
        evidence = FormEvidence(
            "evidence:edit", "pynini", "edit-path", "the", 0.95, "obs:2"
        )
        candidate = FormInterpretationCandidate(
            "interpretation:the",
            InterpretationKind.TYPO_REPAIR,
            ("the",),
            ("determiner",),
            ("specifier",),
            (),
            (evidence.evidence_ref,),
            0.95,
            True,
        )
        placeholder = OpenVocabularyBuilder().build(
            observed, evidence=(evidence,), interpretations=(candidate,)
        )
        decision = OpenVocabularyBuilder().decide(placeholder)

        self.assertEqual(decision.selected_ref, candidate.interpretation_ref)
        self.assertEqual(decision.action, LexicalAction.ALIGN_WITH_KNOWN)
        self.assertFalse(decision.correction_should_be_said)
        self.assertEqual(placeholder.observed.surface, "teh")


if __name__ == "__main__":
    unittest.main()
