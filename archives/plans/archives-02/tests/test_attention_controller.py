from __future__ import annotations

import unittest

from seman2_runtime.attention_controller import (
    ProgressiveAttentionController,
    RetrievalControlPolicy,
    RetrievalLevel,
    RetrievalStopReason,
)
from seman2_runtime.cognitive_memory import CognitiveMemory, MemoryPolicy, RetrievalRequest


class ProgressiveAttentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = CognitiveMemory(
            MemoryPolicy(focal_capacity=2, consolidation_exposures=2)
        )
        for content_ref, features, context in (
            (
                "meaning:residence",
                ("form:house", "role:residence", "domain:material", "event:purchase"),
                "ctx:purchase",
            ),
            (
                "meaning:religious",
                ("form:house", "domain:religious", "construction:house-of-deity"),
                "ctx:sermon",
            ),
            (
                "meaning:dog-command",
                ("form:house", "speech-act:command", "addressee:dog"),
                "ctx:training",
            ),
        ):
            self.memory.remember(
                content_ref,
                kind="meaning",
                features=features,
                context_refs=(context,),
                support_refs=(f"episode:{content_ref}",),
            )

    def test_clear_local_context_stops_before_remote_associations(self) -> None:
        levels = (
            RetrievalLevel(
                0,
                "local-bindings",
                RetrievalRequest(
                    goal_ref="interpret:house",
                    anchor_features=(
                        "form:house",
                        "role:residence",
                        "event:purchase",
                    ),
                    required_features=("form:house",),
                    context_refs=("ctx:purchase",),
                    maximum_results=3,
                ),
            ),
            RetrievalLevel(
                5,
                "remote-associations",
                RetrievalRequest(
                    goal_ref="interpret:house",
                    anchor_features=("form:house",),
                    required_features=("form:house",),
                    maximum_results=3,
                ),
            ),
        )
        result = ProgressiveAttentionController().run(
            self.memory, levels, project_selected=True
        )

        self.assertEqual(result.stop_reason, RetrievalStopReason.GOAL_SATISFIED)
        self.assertEqual(result.deepest_level, 0)
        self.assertEqual(result.selected_ref, "meaning:residence")
        self.assertEqual(result.projected_to_focus, ("meaning:residence",))
        self.assertEqual(len(result.steps), 1)

    def test_impasse_expands_until_context_disambiguates(self) -> None:
        policy = RetrievalControlPolicy(
            support_threshold=0.48,
            decisiveness_margin=0.05,
            minimum_marginal_gain=0.0,
        )
        levels = (
            RetrievalLevel(
                0,
                "surface-only",
                RetrievalRequest(
                    goal_ref="interpret:house-command",
                    anchor_features=("form:house",),
                    required_features=("form:house",),
                    maximum_results=3,
                ),
            ),
            RetrievalLevel(
                2,
                "dialogue-and-addressee",
                RetrievalRequest(
                    goal_ref="interpret:house-command",
                    anchor_features=(
                        "form:house",
                        "speech-act:command",
                        "addressee:dog",
                    ),
                    required_features=("form:house",),
                    context_refs=("ctx:training",),
                    maximum_results=3,
                ),
            ),
        )
        result = ProgressiveAttentionController(policy).run(self.memory, levels)

        self.assertEqual(result.stop_reason, RetrievalStopReason.GOAL_SATISFIED)
        self.assertEqual(result.deepest_level, 2)
        self.assertEqual(result.selected_ref, "meaning:dog-command")
        self.assertEqual(len(result.steps), 2)

    def test_unresolved_tie_requests_clarification_under_budget(self) -> None:
        levels = (
            RetrievalLevel(
                0,
                "surface-only",
                RetrievalRequest(
                    goal_ref="interpret:bare-house",
                    anchor_features=("form:house",),
                    required_features=("form:house",),
                    maximum_results=3,
                ),
            ),
            RetrievalLevel(
                1,
                "same-evidence",
                RetrievalRequest(
                    goal_ref="interpret:bare-house",
                    anchor_features=("form:house",),
                    required_features=("form:house",),
                    maximum_results=3,
                ),
            ),
        )
        result = ProgressiveAttentionController().run(self.memory, levels)

        self.assertEqual(result.stop_reason, RetrievalStopReason.CLARIFICATION)
        self.assertIsNone(result.selected_ref)
        self.assertEqual(result.deepest_level, 1)


if __name__ == "__main__":
    unittest.main()
