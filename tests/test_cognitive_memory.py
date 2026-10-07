from __future__ import annotations

import unittest

from seman2_runtime.cognitive_memory import (
    CognitiveMemory,
    MemoryPolicy,
    MemoryTier,
    RetrievalRequest,
)


class CognitiveMemoryTests(unittest.TestCase):
    def test_focal_projection_is_bounded_and_demotes_instead_of_forgetting(self) -> None:
        memory = CognitiveMemory(
            MemoryPolicy(
                focal_capacity=2,
                peripheral_capacity=8,
                situation_capacity=4,
                intermediate_capacity=8,
                long_term_capacity=8,
            )
        )
        for index in range(3):
            memory.remember(
                f"episode:{index}",
                kind="episode",
                features=("participant:maya", f"index:{index}"),
                context_refs=("ctx:story",),
                support_refs=(f"obs:{index}",),
            )
            memory.focus(f"episode:{index}")

        self.assertEqual(len(memory.by_tier(MemoryTier.FOCAL)), 2)
        self.assertEqual(len(memory.by_tier(MemoryTier.PERIPHERAL)), 1)
        self.assertTrue(all(memory.accessible(f"episode:{i}") for i in range(3)))

    def test_goal_directed_retrieval_prefers_context_and_matching_features(self) -> None:
        memory = CognitiveMemory()
        memory.remember(
            "episode:house",
            kind="episode",
            features=("form:house", "role:residence", "participant:maya"),
            context_refs=("ctx:purchase",),
            support_refs=("obs:1",),
        )
        memory.remember(
            "episode:church",
            kind="episode",
            features=("form:house", "domain:religious"),
            context_refs=("ctx:sermon",),
            support_refs=("obs:2",),
        )
        memory.remember(
            "episode:dog-command",
            kind="episode",
            features=("form:house", "speech-act:command", "addressee:dog"),
            context_refs=("ctx:training",),
            support_refs=("obs:3",),
        )

        hits = memory.retrieve(
            RetrievalRequest(
                goal_ref="understand:purchase",
                anchor_features=("form:house", "role:residence", "participant:maya"),
                required_features=("form:house",),
                context_refs=("ctx:purchase",),
                maximum_results=2,
            )
        )
        self.assertEqual(hits[0].content_ref, "episode:house")
        self.assertTrue(hits[0].context_match)
        self.assertEqual(len(hits), 2)

    def test_repetition_consolidates_while_weak_content_can_be_forgotten(self) -> None:
        policy = MemoryPolicy(
            focal_capacity=1,
            peripheral_capacity=1,
            situation_capacity=1,
            intermediate_capacity=1,
            long_term_capacity=2,
            consolidation_strength=2.4,
            consolidation_exposures=2,
        )
        memory = CognitiveMemory(policy)
        common = dict(
            kind="episode",
            features=("event:repeat",),
            context_refs=("ctx:lesson",),
        )
        memory.remember("episode:repeated", support_refs=("obs:1",), **common)
        memory.remember("episode:repeated", support_refs=("obs:2",), **common)
        self.assertEqual(memory.get("episode:repeated").tier, MemoryTier.LONG_TERM)

        memory.remember(
            "episode:weak-1", support_refs=("obs:3",), distinctiveness=0.0, **common
        )
        memory.remember(
            "episode:weak-2", support_refs=("obs:4",), distinctiveness=0.0, **common
        )
        memory.remember(
            "episode:weak-3", support_refs=("obs:5",), distinctiveness=0.0, **common
        )
        self.assertTrue(memory.accessible("episode:repeated"))
        self.assertTrue(
            any(
                memory.get(ref).tier is MemoryTier.FORGOTTEN
                for ref in ("episode:weak-1", "episode:weak-2", "episode:weak-3")
            )
        )
        hits = memory.retrieve(
            RetrievalRequest(
                goal_ref="recall:lesson",
                anchor_features=("event:repeat",),
                maximum_results=10,
            )
        )
        forgotten = {
            ref
            for ref in ("episode:weak-1", "episode:weak-2", "episode:weak-3")
            if memory.get(ref).tier is MemoryTier.FORGOTTEN
        }
        self.assertFalse(forgotten & {hit.content_ref for hit in hits})

    def test_checkpoint_round_trip_preserves_behavior(self) -> None:
        memory = CognitiveMemory(MemoryPolicy(focal_capacity=2))
        memory.remember(
            "concept:one",
            kind="concept",
            features=("shape:round",),
            context_refs=("ctx:lesson",),
            support_refs=("episode:1",),
        )
        memory.focus("concept:one")
        memory.advance(2)
        restored = CognitiveMemory.restore(memory.as_dict())

        self.assertEqual(restored.as_dict(), memory.as_dict())
        request = RetrievalRequest(
            goal_ref="compare:shape", anchor_features=("shape:round",)
        )
        self.assertEqual(restored.retrieve(request), memory.retrieve(request))


if __name__ == "__main__":
    unittest.main()
