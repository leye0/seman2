from __future__ import annotations

from pathlib import Path
import unittest

from seman2_runtime.durable_runtime import RuntimePlan
from seman2_runtime.multi_epoch import _analysis_unit


ROOT = Path(__file__).resolve().parent.parent


class MultiEpochRuntimeTests(unittest.TestCase):
    def test_answer_segmentation_preserves_declared_source_span(self):
        text = "Rather than modify the string, define a function of type: code follows"
        unit, metadata = _analysis_unit(text)
        self.assertEqual(unit, "Rather than modify the string, define a function of type.")
        self.assertTrue(metadata["terminal_colon_normalized_to_period"])
        self.assertEqual(text[:metadata["source_character_end"]].strip(), unit[:-1] + ":")
        self.assertTrue(metadata["raw_text_preserved_in_source_artifact"])

    def test_answer_feedback_requires_retrieval_parent_and_next_epoch(self):
        plan = RuntimePlan(ROOT / "plans/runtime_service_graph.json")
        edge = plan.edge("structural-retrieval", "source-reader")
        self.assertEqual(edge["kind"], "feedback")
        self.assertEqual(edge["epoch_delta"], 1)

    def test_state_and_episode_have_explicit_continuity_edges(self):
        plan = RuntimePlan(ROOT / "plans/runtime_service_graph.json")
        self.assertEqual(plan.edge("situation-state", "situation-state")["epoch_delta"], 1)
        self.assertEqual(plan.edge("episodic-store", "episodic-store")["epoch_delta"], 1)


if __name__ == "__main__":
    unittest.main()
