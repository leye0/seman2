from __future__ import annotations

import unittest

from seman2_runtime.contracts import ContractError
from seman2_runtime.curriculum import (
    CurriculumController,
    CurriculumExperience,
    CurriculumStage,
    EvaluationCriterion,
    EvaluationProbe,
)


def controller() -> CurriculumController:
    experiences = (
        CurriculumExperience.from_text(
            "experience:apple-1", "This apple is a fruit.", ("lexicon:fruit",), 0
        ),
        CurriculumExperience.from_text(
            "experience:apple-2", "Maya ate an apple.", ("event:eating",), 1
        ),
    )
    criteria = (
        EvaluationCriterion("criterion:relation", "relational-understanding", 0.8),
        EvaluationCriterion(
            "criterion:explanation", "explanation-quality", 0.7, evaluator_kind="external-llm"
        ),
    )
    probes = (
        EvaluationProbe.from_text(
            "probe:apple",
            "What kind of thing was the apple in the lesson?",
            ("criterion:relation", "criterion:explanation"),
            ("experience:apple-1",),
            ("lexicon:fruit", "query:classification"),
        ),
    )
    stages = (
        CurriculumStage(
            "stage:one",
            (),
            ("experience:apple-1", "experience:apple-2"),
            ("probe:apple",),
            ("criterion:relation", "criterion:explanation"),
        ),
    )
    return CurriculumController(
        experiences=experiences, criteria=criteria, probes=probes, stages=stages
    )


class CurriculumTests(unittest.TestCase):
    def test_tutor_cannot_probe_content_not_yet_ingested(self) -> None:
        curriculum = controller()
        with self.assertRaises(ContractError):
            curriculum.available_probe("probe:apple")
        curriculum.present("experience:apple-1")
        self.assertEqual(
            curriculum.available_probe("probe:apple").probe_ref, "probe:apple"
        )

    def test_probe_content_cannot_leak_into_training_experiences(self) -> None:
        repeated = "same exact content"
        with self.assertRaises(ContractError):
            CurriculumController(
                experiences=(
                    CurriculumExperience.from_text("experience:1", repeated, (), 0),
                ),
                criteria=(EvaluationCriterion("criterion:1", "test", 0.5),),
                probes=(
                    EvaluationProbe.from_text(
                        "probe:1", repeated, ("criterion:1",), ("experience:1",), ()
                    ),
                ),
                stages=(
                    CurriculumStage(
                        "stage:1", (), ("experience:1",), ("probe:1",), ("criterion:1",)
                    ),
                ),
            )

    def test_external_evaluation_cannot_add_criteria_or_write_runtime(self) -> None:
        curriculum = controller()
        curriculum.present("experience:apple-1")
        with self.assertRaises(ContractError):
            curriculum.record_evaluation(
                stage_ref="stage:one",
                probe_ref="probe:apple",
                evaluator="openrouter:model",
                criterion_scores={"criterion:invented-after-results": 1.0},
                evidence_refs=("answer:1",),
            )
        record = curriculum.record_evaluation(
            stage_ref="stage:one",
            probe_ref="probe:apple",
            evaluator="openrouter:model",
            criterion_scores={
                "criterion:relation": 0.9,
                "criterion:explanation": 0.8,
            },
            evidence_refs=("answer:1",),
        )
        self.assertFalse(record.runtime_write_performed)
        self.assertEqual(record.rubric_digest, curriculum.rubric_digest)
        self.assertTrue(curriculum.decide_stage("stage:one").promoted)

    def test_failed_gate_returns_targeted_reinforcement(self) -> None:
        curriculum = controller()
        curriculum.present("experience:apple-1")
        curriculum.record_evaluation(
            stage_ref="stage:one",
            probe_ref="probe:apple",
            evaluator="deterministic+openrouter:model",
            criterion_scores={
                "criterion:relation": 0.9,
                "criterion:explanation": 0.4,
            },
            evidence_refs=("answer:weak",),
        )
        decision = curriculum.decide_stage("stage:one")

        self.assertFalse(decision.promoted)
        self.assertEqual(decision.failed_criteria, ("criterion:explanation",))
        self.assertIn("query:classification", decision.reinforcement_tags)
        self.assertNotIn("stage:one", curriculum.completed_stage_refs)


if __name__ == "__main__":
    unittest.main()
