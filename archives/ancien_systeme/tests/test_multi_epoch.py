from __future__ import annotations

from pathlib import Path
import unittest

from seman2_runtime.contracts import ContractError
from seman2_runtime.durable_runtime import RuntimePlan


ROOT = Path(__file__).resolve().parent.parent


class MultiEpochRuntimeTests(unittest.TestCase):
    def test_internal_retrieval_has_no_edge_to_corpus_reader(self):
        plan = RuntimePlan(ROOT / "plans/archives/runtime_service_graph.json")
        with self.assertRaisesRegex(ContractError, "frontière runtime interdite"):
            plan.edge("structural-retrieval", "source-reader")

    def test_state_and_episode_have_explicit_continuity_edges(self):
        plan = RuntimePlan(ROOT / "plans/archives/runtime_service_graph.json")
        self.assertEqual(plan.edge("situation-state", "situation-state")["epoch_delta"], 1)
        self.assertEqual(plan.edge("episodic-store", "episodic-store")["epoch_delta"], 1)


if __name__ == "__main__":
    unittest.main()
