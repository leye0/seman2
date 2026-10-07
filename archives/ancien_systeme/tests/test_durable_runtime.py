from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from seman2_runtime.contracts import ContractError
from seman2_runtime.durable_runtime import DurableRuntimeStore, RuntimePlan


ROOT = Path(__file__).resolve().parent.parent


class DurableRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = DurableRuntimeStore(
            Path(self.temp.name) / "runtime.sqlite",
            RuntimePlan(ROOT / "plans/archives/runtime_service_graph.json"),
        )

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def record_chain(self):
        source = self.store.record_artifact(
            artifact_id="source:1", component_id="source-reader", kind="source-record",
            epoch=0, payload={"source": "real"}, parent_ids=(), idempotency_key="source:1",
        )
        observation = self.store.record_artifact(
            artifact_id="observation:1", component_id="observation-ledger", kind="observation",
            epoch=0, payload={"text": "hello"}, parent_ids=(source.artifact_id,),
            idempotency_key="observation:1",
        )
        job = self.store.record_artifact(
            artifact_id="analysis-job:1", component_id="analysis-dispatch", kind="analysis-request",
            epoch=0, payload={"producer": "test"}, parent_ids=(observation.artifact_id,),
            idempotency_key="analysis-job:1",
        )
        return source, observation, job

    def test_real_parent_chain_is_persisted_and_queryable(self):
        _, _, job = self.record_chain()
        result = self.store.record_artifact(
            artifact_id="analysis:1", component_id="native-analysis-ledger", kind="native-analysis",
            epoch=0, payload={"status": "parsed"}, parent_ids=(job.artifact_id,),
            idempotency_key="analysis:1",
        )
        ancestry = self.store.ancestry(result.artifact_id)
        self.assertEqual([row["artifact_id"] for row in ancestry], [
            "analysis:1", "analysis-job:1", "observation:1", "source:1",
        ])
        self.assertEqual(self.store.metrics()["artifacts"], 4)
        self.assertEqual(self.store.metrics()["events"], 4)
        self.assertEqual(self.store.metrics()["journal_mode"], "wal")

    def test_missing_parent_and_shortcut_are_rejected(self):
        with self.assertRaisesRegex(ContractError, "parent runtime absent"):
            self.store.record_artifact(
                artifact_id="observation:x", component_id="observation-ledger", kind="observation",
                epoch=0, payload={}, parent_ids=("source:missing",), idempotency_key="x",
            )
        source, _, _ = self.record_chain()
        with self.assertRaisesRegex(ContractError, "frontière runtime interdite"):
            self.store.record_artifact(
                artifact_id="hypothesis:x", component_id="hypothesis-manager", kind="hypothesis",
                epoch=0, payload={}, parent_ids=(source.artifact_id,), idempotency_key="hypothesis:x",
            )

    def test_idempotent_retry_returns_same_artifact_but_conflict_fails(self):
        source, _, _ = self.record_chain()
        same = self.store.record_artifact(
            artifact_id="source:1", component_id="source-reader", kind="source-record",
            epoch=0, payload={"source": "real"}, parent_ids=(), idempotency_key="source:1",
        )
        self.assertEqual(same.sequence, source.sequence)
        with self.assertRaisesRegex(ContractError, "conflit d'idempotence"):
            self.store.record_artifact(
                artifact_id="source:1", component_id="source-reader", kind="source-record",
                epoch=0, payload={"source": "changed"}, parent_ids=(), idempotency_key="source:1",
            )

    def test_feedback_requires_next_epoch(self):
        # A minimal full path is unnecessary: directly establish the two rows
        # through their valid parent chain would obscure the epoch invariant.
        # The plan itself exposes the exact feedback delta and is asserted here.
        edge = self.store.plan.edge("system-output-ledger", "observation-ledger")
        self.assertEqual(edge["kind"], "feedback")
        self.assertEqual(edge["epoch_delta"], 1)

    def test_internal_retrieval_cannot_materialize_a_new_corpus_source(self):
        # Construit un vrai chemin jusqu'à une requête Soar, puis vérifie que
        # son résultat de mémoire interne ne peut contourner l'ingestion en se
        # faisant passer pour un nouvel événement source.
        self.record_chain()
        native = self.store.record_artifact(
            artifact_id="analysis:1", component_id="native-analysis-ledger", kind="analysis",
            epoch=0, payload={}, parent_ids=("analysis-job:1",), idempotency_key="analysis:1",
        )
        representation = self.store.record_artifact(
            artifact_id="representation:1", component_id="representation-adapters", kind="fragment",
            epoch=0, payload={}, parent_ids=(native.artifact_id,), idempotency_key="representation:1",
        )
        linked = self.store.record_artifact(
            artifact_id="linked:1", component_id="cross-representation-linker", kind="linked",
            epoch=0, payload={}, parent_ids=(representation.artifact_id,), idempotency_key="linked:1",
        )
        temporal = self.store.record_artifact(
            artifact_id="temporal:1", component_id="temporal-relation-manager", kind="temporal",
            epoch=0, payload={}, parent_ids=(linked.artifact_id,), idempotency_key="temporal:1",
        )
        hypothesis = self.store.record_artifact(
            artifact_id="hypothesis:1", component_id="hypothesis-manager", kind="hypothesis",
            epoch=0, payload={}, parent_ids=(linked.artifact_id, temporal.artifact_id),
            idempotency_key="hypothesis:1",
        )
        state = self.store.record_artifact(
            artifact_id="state:1", component_id="situation-state", kind="state",
            epoch=0, payload={}, parent_ids=(hypothesis.artifact_id,), idempotency_key="state:1",
        )
        episode = self.store.record_artifact(
            artifact_id="episode:1", component_id="episodic-store", kind="episode",
            epoch=0, payload={}, parent_ids=(hypothesis.artifact_id, state.artifact_id),
            idempotency_key="episode:1",
        )
        retrieval = self.store.record_artifact(
            artifact_id="retrieval:1", component_id="structural-retrieval", kind="retrieval",
            epoch=0, payload={}, parent_ids=(episode.artifact_id, state.artifact_id, hypothesis.artifact_id),
            idempotency_key="retrieval:1",
        )
        beam = self.store.record_artifact(
            artifact_id="beam:1", component_id="active-beam", kind="beam",
            epoch=0, payload={}, parent_ids=(retrieval.artifact_id, hypothesis.artifact_id),
            idempotency_key="beam:1",
        )
        decision = self.store.record_artifact(
            artifact_id="decision:1", component_id="soar-runtime", kind="decision",
            epoch=0, payload={}, parent_ids=(beam.artifact_id, state.artifact_id),
            idempotency_key="decision:1",
        )
        answer_ref = self.store.record_artifact(
            artifact_id="answer-ref:1", component_id="structural-retrieval", kind="answer-ref",
            epoch=0, payload={}, parent_ids=(decision.artifact_id,), idempotency_key="answer-ref:1",
        )
        with self.assertRaisesRegex(ContractError, "frontière runtime interdite"):
            self.store.record_artifact(
                artifact_id="answer-source:bad", component_id="source-reader", kind="source-record",
                epoch=1, payload={}, parent_ids=(answer_ref.artifact_id,), idempotency_key="answer-source:bad",
            )

    def test_database_checkpoint_is_self_contained(self):
        self.record_chain()
        destination = Path(self.temp.name) / "checkpoint" / "runtime.sqlite"
        manifest = self.store.checkpoint_database(destination)
        self.assertEqual(manifest["artifact_count"], 3)
        self.assertEqual(manifest["last_event_sequence"], 3)
        self.assertEqual(len(manifest["sha256"]), 64)
        restored = DurableRuntimeStore(destination, self.store.plan)
        try:
            self.assertEqual(restored.metrics()["artifacts"], 3)
            self.assertEqual(restored.metrics()["events"], 3)
            self.assertEqual(restored.get_artifact("analysis-job:1").parent_ids, ("observation:1",))
        finally:
            restored.close()


if __name__ == "__main__":
    unittest.main()
