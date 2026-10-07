from __future__ import annotations

import hashlib
import unittest

from seman2_runtime.cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
)
from seman2_runtime.developmental_core import ContextFrame, ContextKind, DevelopmentalCore, EpistemicState
from seman2_runtime.formal_core_adapter import adapt_semantic_artifact


class FormalCoreAdapterTests(unittest.TestCase):
    def _semantic_artifact(self):
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
        arena = ArtifactArena(registry)
        return arena.publish(
            ArtifactProposal(
                artifact_type="semantic-structure",
                producer_id="semantic-composer",
                producer_build="test",
                configuration_digest=hashlib.sha256(b"adapter").hexdigest(),
                mode="ingestion",
                session_id="test",
                wave=0,
                parent_ids=(),
                observation_refs=("observation:1",),
                source_anchors=({"start": 0, "end": 21},),
                payload_native={
                    "entities": [{"id": "x1", "sort": "x", "properties": {}}],
                    "events": [{"id": "e2", "sort": "e", "properties": {}}],
                    "predicates": [
                        {
                            "predicate": "_maya_n_1",
                            "constant": "Maya",
                            "arguments": {"ARG0": "x1"},
                        },
                        {
                            "predicate": "_sleep_v_1",
                            "constant": None,
                            "arguments": {"ARG0": "e2", "ARG1": "x1"},
                        },
                    ],
                    "mrs_index": "e2",
                },
                payload_projection={"truth_asserted": False},
                idempotency_key="semantic:1",
            )
        )

    def test_candidate_becomes_attributed_relations_forms_and_event(self) -> None:
        core = DevelopmentalCore(vector_dimension=512, seed="adapter")
        core.universe.add_context(ContextFrame("ctx:observation", ContextKind.NARRATED))
        artifact = self._semantic_artifact()
        bundle = adapt_semantic_artifact(
            core,
            artifact,
            parent_context_ref="ctx:observation",
            temporal_index=4,
        )

        self.assertEqual(len(bundle.identity_refs), 1)
        self.assertEqual(len(bundle.relation_refs), 2)
        self.assertEqual(len(bundle.event_refs), 1)
        self.assertEqual(len(bundle.distributed_form_refs), 2)
        self.assertEqual(core.universe.contexts[bundle.context_ref].kind, ContextKind.HYPOTHETICAL)
        self.assertEqual(
            core.universe.identities[bundle.identity_refs[0]].surface_aliases,
            ("Maya",),
        )
        self.assertTrue(
            all(
                core.universe.relations[ref].epistemic_state is EpistemicState.HYPOTHESIS
                for ref in bundle.relation_refs
            )
        )
        self.assertEqual(bundle.contribution.native_artifact_ref, artifact.artifact_id)
        self.assertFalse(
            core.universe.query_relations(
                relation_form_ref="external:mrs:_sleep_v_1",
                context_ref="ctx:observation",
            )
        )
        self.assertEqual(
            len(
                core.universe.query_relations(
                    relation_form_ref="external:mrs:_sleep_v_1",
                    context_ref=bundle.context_ref,
                )
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
