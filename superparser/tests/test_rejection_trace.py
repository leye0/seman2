"""Rejection probes explain failed *attempts*, never a grammatical fault."""
from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.engine import Parser
from seman_parser.features import Atom, FeatureStructure
from seman_parser.vector_chart import ForestNode, _RejectionTrace
from scripts.probe_dialogue_rejections import eligible_dialogue_residuals, summary_for


class RejectionTraceTests(unittest.TestCase):
    def test_only_ground_atomic_conflicts_are_named(self):
        trace = _RejectionTrace(8)
        node = ForestNode(0, 0, 9, 0, "VP", 0)
        trace.record(
            "lexical_unification", node,
            expected=FeatureStructure.build(
                {"number": "plural", "person": "?subject_person"}),
            offered=FeatureStructure.build(
                {"number": "singular", "person": "3"}),
            surface="says",
        )
        event = trace.as_dict()["events"][0]
        self.assertEqual(event["direct_atom_conflicts"], [{
            "feature": "number", "required": "plural", "offered": "singular",
        }])
        self.assertEqual(event["analysis_span"], [0, 9])
        self.assertEqual(event["scope"], "attempted_derivation_only")
        self.assertFalse(trace.as_dict()["grammatical_fault_established"])

    def test_bound_variable_gives_local_conflict_but_unbound_does_not(self):
        node = ForestNode(0, 1, 4, 0, "V", 0)
        trace = _RejectionTrace(4)
        expected = FeatureStructure.build({"number": "?n"})
        offered = FeatureStructure.build({"number": "singular"})
        trace.record("test", node, expected=expected, offered=offered)
        trace.record("test", node, expected=expected, offered=offered,
                     bindings={"n": Atom.of("plural")})
        events = trace.as_dict()["events"]
        self.assertEqual(events[0]["direct_atom_conflicts"], [])
        self.assertEqual(events[1]["direct_atom_conflicts"], [{
            "feature": "number", "required": "plural", "offered": "singular",
        }])

    def test_bounded_stage_sampling_counts_unsampled_attempts(self):
        node = ForestNode(0, 0, 2, 0, "NP", 0)
        trace = _RejectionTrace(4)
        for _ in range(17):
            trace.record("lexical_unification", node)
        for _ in range(7):
            trace.record("child_context_exhausted", node, child_index=1)
        observed = trace.as_dict()
        self.assertEqual(observed["observed_events"], 24)
        self.assertLessEqual(observed["sampled_events"], 4)
        self.assertEqual(observed["observed_by_stage"], {
            "child_context_exhausted": 7, "lexical_unification": 17,
        })
        self.assertTrue(observed["truncated"])
        self.assertFalse(observed["exhaustive"])

    def test_public_parser_option_preserves_status_and_is_not_cached(self):
        parser = Parser.from_dir(
            Path(__file__).resolve().parents[1] / "data", cache_size=8)
        text = '"She am happy."'
        baseline = parser.parse(text).result
        observed = parser.parse(text, rejection_trace_limit=16).result
        self.assertEqual(observed.completed, baseline.completed)
        self.assertEqual(observed.diagnostic_summary()["grammatical_status"],
                         baseline.diagnostic_summary()["grammatical_status"])
        trace = observed.stats["rejection_trace"]
        self.assertEqual(trace["schema"], "seman2-rejection-trace-v1")
        self.assertLessEqual(trace["sampled_events"], 16)
        self.assertFalse(trace["grammatical_fault_established"])
        self.assertNotIn("rejection_trace", baseline.stats)
        with self.assertRaisesRegex(ValueError, "rejection_trace_limit"):
            parser.parse(text, rejection_trace_limit=101)

    def test_dialogue_selection_is_by_root_evidence_not_language_guess(self):
        cases = [
            {"index": 2, "status": "roots_without_valid_analysis",
             "dialogue_attempt": {"structural_root_nodes": 1}},
            {"index": 3, "status": "no_structural_root",
             "dialogue_attempt": {"structural_root_nodes": 0}},
            {"index": 4, "status": "complete",
             "dialogue_attempt": {"structural_root_nodes": 2}},
            {"index": 5, "status": "forest_budget_exceeded",
             "dialogue_attempt": {"structural_root_nodes": 1}},
            {"index": 6, "status": "roots_without_valid_analysis",
             "dialogue_attempt": None},
        ]
        self.assertEqual([x["index"] for x in eligible_dialogue_residuals(cases)],
                         [2, 5])
        synthetic_trace = {
            "events": [{
                "stage": "lexical_unification",
                "direct_atom_conflicts": [
                    {"feature": "number", "required": "plural", "offered": "singular"}
                ],
            }],
        }
        summary = summary_for([{
            "replay_outcome": "roots_without_valid_analysis",
            "scoped_dialogue": {"rejection_trace": synthetic_trace},
            "ordinary_fallback": {},
        }])
        self.assertEqual(summary["events_sampled"], 1)
        self.assertEqual(summary["direct_atom_conflicts_sampled"], 1)
        self.assertTrue(summary["not_a_causal_proof"])


if __name__ == "__main__":
    unittest.main()
