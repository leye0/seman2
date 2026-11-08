"""Rejection probes explain failed *attempts*, never a grammatical fault."""
from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.engine import Parser
from seman_parser.features import Atom, FeatureStructure
from seman_parser.vector_chart import ForestNode, _RejectionTrace
from scripts.probe_dialogue_rejections import (
    eligible_dialogue_residuals, summary_for, map_trace_to_reference,
    comparison_targets, comparison_summary, STRICT_CONTROL_INDICES,
    MARKED_COMPARISON_INDICES,
)
from research.verbnet_lr.corpus_pipeline import PreparedCorpusInput, CorpusParseMode


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

    def test_priority_sampling_retains_later_exhausted_child_over_hint_flood(self):
        node = ForestNode(0, 2, 15, 0, "VP", 0)
        trace = _RejectionTrace(4)
        # Four independent pruning classes can exhaust the bounded pool
        # before any materialized evidence is available.
        initial = (
            "lexical_hint_unification", "rule_hint_unification",
            "positive_evidence_lexical_hint_missing",
            "positive_evidence_rule_hint_impossible",
        )
        for stage in initial:
            trace.record(stage, node)
        self.assertEqual(trace.as_dict()["sampled_events"], 4)
        trace.record("child_context_exhausted", node,
                     rule_id="dialogue_tag", child_index=1,
                     required_positive=())
        trace.record("positive_evidence_materialized_missing", node,
                     required_positive=(), witnessed_positive=())
        saved = trace.as_dict()
        self.assertEqual(saved["sampled_events"], 4)
        self.assertEqual(saved["observed_events"], 6)
        self.assertEqual(saved["sampling_policy"],
                         "per_stage_cap_with_priority_replacement")
        preserved = {e["stage"] for e in saved["events"]}
        self.assertIn("child_context_exhausted", preserved)
        self.assertIn("positive_evidence_materialized_missing", preserved)
        self.assertEqual(saved["observed_by_stage"]["lexical_hint_unification"], 1)
        self.assertTrue(saved["truncated"])
        self.assertFalse(saved["grammatical_fault_established"])

        # Later low-priority noise must never displace stronger witnesses.
        for _ in range(10):
            trace.record("lexical_hint_unification", node)
        later = {e["stage"] for e in trace.as_dict()["events"]}
        self.assertIn("child_context_exhausted", later)
        self.assertIn("positive_evidence_materialized_missing", later)

    def test_stage_cap_and_sample_count_remain_bounded_after_replacement(self):
        node = ForestNode(0, 0, 3, 0, "NP", 0)
        trace = _RejectionTrace(8)
        for kind in (
            "lexical_hint_unification",
            "rule_hint_unification",
            "positive_evidence_lexical_hint_missing",
            "positive_evidence_rule_hint_impossible",
        ):
            for _ in range(9):
                trace.record(kind, node)
        for _ in range(11):
            trace.record("child_context_exhausted", node)
        saved = trace.as_dict()
        self.assertEqual(saved["observed_events"], 47)
        self.assertLessEqual(saved["sampled_events"], 8)
        from collections import Counter
        sampled_by_stage = Counter(e["stage"] for e in saved["events"])
        self.assertLessEqual(max(sampled_by_stage.values()), 2)
        self.assertEqual(sampled_by_stage["child_context_exhausted"], 2)

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
        if not observed.completed and not observed.stats.get("kbest_budget_exceeded"):
            probe = trace["independent_local_probe"]
            self.assertIsNotNone(probe)
            self.assertTrue(probe["canonical_work_budget_unchanged"])
            self.assertLessEqual(probe["sampled_local_constituents"], 16)
            self.assertGreaterEqual(probe["selected_structural_nodes"],
                                    probe["attempted_structural_nodes"])
        with self.assertRaisesRegex(ValueError, "rejection_trace_limit"):
            parser.parse(text, rejection_trace_limit=101)

    def test_failed_global_parse_keeps_local_probes_diagnostic_only(self):
        parser = Parser.from_dir(Path(__file__).resolve().parents[1] / "data", cache_size=0)
        # Pinned corpus residual #94 has a valid local participial/nominal
        # structure but no independent main-clause subject in this segment.
        source = ("and, keeping me close to her shawl, turned to thank the "
                  "gentleman for taking so much trouble as to bring her home.")
        ordinary = parser.parse(source).result
        observed = parser.parse(source, rejection_trace_limit=24).result
        self.assertFalse(ordinary.completed)
        self.assertEqual(observed.completed, ordinary.completed)
        self.assertEqual(observed.stats.get("kbest_work_units"),
                         ordinary.stats.get("kbest_work_units"))
        probe = observed.stats["rejection_trace"]["independent_local_probe"]
        self.assertIsNotNone(probe)
        self.assertTrue(probe["canonical_work_budget_unchanged"])
        self.assertGreater(probe["sampled_local_constituents"], 0)
        roles = probe["validated_local_role_pairs"]
        self.assertEqual(roles["schema"], "seman2-local-resolved-role-pairs-v1")
        self.assertLessEqual(roles["sampled_pairs"], 24)
        self.assertFalse(roles["global_tree_proven"])
        self.assertFalse(roles["grammatical_conflict_proven"])
        self.assertTrue(all(not witness["global_tree_selected"]
                            and not witness["whole_sentence_grammaticality_proven"]
                            for witness in probe["witnesses"]))

    def test_successful_local_compositions_are_separate_from_rejections(self):
        parser = Parser.from_dir(Path(__file__).resolve().parents[1] / "data", cache_size=0)
        ordinary = parser.parse("John opened the box.")
        observed = parser.parse("John opened the box.", rejection_trace_limit=16)
        self.assertEqual(observed.result.completed, ordinary.result.completed)
        self.assertEqual(observed.result.best().signature(), ordinary.result.best().signature())
        self.assertNotIn("rejection_trace", ordinary.result.stats)
        proofs = observed.result.stats["rejection_trace"]["validated_local_constituents"]
        self.assertGreater(proofs["observed_materialized_rule_analyses"], 0)
        self.assertGreater(proofs["sampled_local_constituents"], 0)
        self.assertLessEqual(proofs["sampled_local_constituents"], 16)
        self.assertTrue(all(w["rule_id"] and w["children"] and
                            w["proof_basis"] == "materialized_rule_after_context_unification"
                            for w in proofs["witnesses"]))
        self.assertFalse(proofs["global_tree_proven"])
        self.assertFalse(proofs["sentence_grammatical_fault_established"])

    def test_reference_mapping_only_for_nonsynthetic_original_characters(self):
        prepared = PreparedCorpusInput(
            analysis_text='"They says."',
            reference_text="They says.",
            source_text="They says.",
            synthetic_prefix='"', synthetic_suffix='"',
            synthetic_terminal=False, mode=CorpusParseMode.QUOTE_BALANCED,
        )
        original_trace = {"events": [
            {"analysis_span": [1, 5], "child_span": [6, 10]},
            {"analysis_span": [0, 1], "child_span": [11, 12]},
        ], "exhaustive": False}
        mapped = map_trace_to_reference(original_trace, prepared)
        self.assertEqual(mapped["events"][0]["reference_span"], [0, 4])
        self.assertEqual(mapped["events"][0]["child_reference_span"], [5, 9])
        self.assertEqual(mapped["events"][0]["reference_span_mapping"], "exact")
        self.assertIsNone(mapped["events"][1]["reference_span"])
        self.assertEqual(mapped["events"][1]["reference_span_mapping"],
                         "unavailable")
        self.assertIsNone(mapped["events"][1]["child_reference_span"])
        self.assertEqual(original_trace["events"][0]["analysis_span"], [1, 5])
        self.assertFalse(mapped["exhaustive"])

    def test_local_rule_proofs_map_every_child_only_at_exact_original_spans(self):
        prepared = PreparedCorpusInput(
            analysis_text='"They says."', reference_text="They says.",
            source_text="They says.", synthetic_prefix='"', synthetic_suffix='"',
            synthetic_terminal=False, mode=CorpusParseMode.QUOTE_BALANCED,
        )
        source = {"events": [], "validated_local_constituents": {
            "schema": "seman2-local-constituent-proof-sample-v1",
            "observed_materialized_rule_analyses": 1,
            "sampled_local_constituents": 1, "exhaustive": False,
            "global_tree_proven": False,
            "sentence_grammatical_fault_established": False,
            "witnesses": [{
                "proof_basis": "materialized_rule_after_context_unification",
                "analysis_span": [0, 12], "category": "CLAUSE", "rule_id": "clause_np_vp",
                "children": [{"analysis_span": [1, 5], "category": "NP", "rule_id": None},
                             {"analysis_span": [11, 12], "category": "PUNCT", "rule_id": None}],
                "verified_features": {}, "required_context_features": {},
            }],
        }}
        mapped = map_trace_to_reference(source, prepared)
        witness = mapped["validated_local_constituents"]["witnesses"][0]
        self.assertIsNone(witness["reference_span"])
        self.assertEqual(witness["reference_span_mapping"], "unavailable")
        self.assertEqual(witness["children"][0]["reference_span"], [0, 4])
        self.assertIsNone(witness["children"][1]["reference_span"])
        self.assertEqual(witness["children"][1]["reference_span_mapping"], "unavailable")
        source["independent_local_probe"] = source["validated_local_constituents"]
        source["independent_local_probe"]["validated_local_role_pairs"] = {
            "pairs": [{
                "analysis_span": [0, 12],
                "subject": {"child_analysis_span": [1, 5],
                            "head_analysis_span": [1, 5]},
                "predicate": {"child_analysis_span": [11, 12],
                              "head_analysis_span": [11, 12]},
            }],
        }
        independent = map_trace_to_reference(source, prepared)["independent_local_probe"]
        self.assertEqual(independent["witnesses"][0]["children"][0]["reference_span"],
                         [0, 4])
        self.assertIsNone(independent["witnesses"][0]["reference_span"])
        linked = independent["validated_local_role_pairs"]["pairs"][0]
        self.assertEqual(linked["subject"]["head_reference_span"], [0, 4])
        self.assertIsNone(linked["predicate"]["head_reference_span"])
        self.assertEqual(linked["predicate"]["head_reference_span_mapping"],
                         "unavailable")


    def test_late_exhausted_child_displaces_early_hint_noise(self):
        trace = _RejectionTrace(8)
        node = ForestNode(0, 0, 12, 0, "CLAUSE", 0)
        # Four early high-volume stages would otherwise completely
        # occupy the retained window before useful children are examined.
        for stage in (
            "lexical_hint_unification",
            "rule_hint_unification",
            "positive_evidence_lexical_hint_missing",
            "positive_evidence_rule_hint_impossible",
        ):
            for _ in range(20):
                trace.record(stage, node)
        before = trace.as_dict()
        self.assertEqual(before["sampled_events"], 8)
        self.assertNotIn("child_context_exhausted",
                         {x["stage"] for x in before["events"]})

        trace.record("child_context_exhausted", node,
                     rule_id="clause_np_vp", child_index=1,
                     child_node=ForestNode(1, 4, 12, 1, "VP", 0))
        trace.record("positive_evidence_materialized_missing", node)
        after = trace.as_dict()
        self.assertEqual(after["sampled_events"], 8)
        self.assertEqual(after["observed_events"], 82)
        self.assertIn("child_context_exhausted",
                      {x["stage"] for x in after["events"]})
        self.assertIn("positive_evidence_materialized_missing",
                      {x["stage"] for x in after["events"]})
        self.assertEqual(after["sampling_policy"],
                         "per_stage_cap_with_priority_replacement")
        self.assertTrue(after["truncated"])
        self.assertFalse(after["exhaustive"])

    def test_positive_evidence_tracks_required_witnessed_and_missing(self):
        from seman_parser.symbols import intern

        trace = _RejectionTrace(10)
        node = ForestNode(0, 2, 7, 0, "VP", 0)
        trace.record(
            "positive_evidence_materialized_missing", node,
            required_positive=(intern("person"), intern("number")),
            witnessed_positive=(intern("person"), intern("vform")),
            evidence_basis="materialized_analysis",
        )
        evidence = trace.as_dict()["events"][0]
        self.assertEqual(evidence["required_positive_features"],
                         ["number", "person"])
        self.assertEqual(evidence["witnessed_positive_features"],
                         ["person", "vform"])
        self.assertEqual(evidence["missing_positive_features"], ["number"])
        self.assertEqual(evidence["evidence_basis"], "materialized_analysis")
        self.assertNotIn("direct_atom_conflicts", evidence)
        self.assertFalse(trace.as_dict()["grammatical_fault_established"])

    def test_request_ancestry_is_bounded_and_not_a_causal_claim(self):
        trace = _RejectionTrace(10)
        trace.requests.extend([
            {"category": "CLAUSE", "analysis_span": [0, 35]},
            {"category": "SPEECH-TAG", "analysis_span": [8, 35],
             "via_rule_id": "tag_inverted", "via_child_index": 1},
            {"category": "VP", "analysis_span": [18, 35],
             "via_rule_id": "vp_finite", "via_child_index": 2},
        ])
        node = ForestNode(0, 18, 35, 0, "VP", 0)
        trace.record("positive_evidence_rule_impossible", node,
                     rule_id="vp_nonfinite", required_positive=(),
                     evidence_basis="rule_static_may_provide_check")
        evt = trace.as_dict()["events"][0]
        self.assertEqual([x["category"] for x in evt["request_chain"]],
                         ["CLAUSE", "SPEECH-TAG", "VP"])
        self.assertEqual(evt["request_chain"][-1]["via_rule_id"], "vp_finite")
        self.assertFalse(evt["request_chain_truncated"])
        trace.requests[-1]["analysis_span"][0] = 20
        self.assertEqual(evt["request_chain"][-1]["analysis_span"], [18, 35])

        trace.requests = [{"category": f"L{i}", "analysis_span": [i, i+1]}
                          for i in range(12)]
        trace.record("child_context_exhausted", node)
        chain = trace.as_dict()["events"][1]["request_chain"]
        self.assertEqual(len(chain), 6)
        self.assertEqual(chain[0]["category"], "L6")
        self.assertTrue(trace.as_dict()["events"][1]["request_chain_truncated"])

    def test_original_source_mapping_of_request_chain_remains_exact(self):
        prepared = PreparedCorpusInput(
            analysis_text='"They says."',
            reference_text="They says.",
            source_text="They says.",
            synthetic_prefix='"', synthetic_suffix='"',
            synthetic_terminal=False, mode=CorpusParseMode.QUOTE_BALANCED,
        )
        mapped = map_trace_to_reference({"events": [{
            "analysis_span": [1, 5],
            "request_chain": [
                {"category": "QUOTED", "analysis_span": [0, 12]},
                {"category": "NP", "analysis_span": [1, 5]},
            ],
        }]}, prepared)
        event = mapped["events"][0]
        self.assertIsNone(event["request_chain"][0]["reference_span"])
        self.assertEqual(event["request_chain"][0]["reference_span_mapping"],
                         "unavailable")
        self.assertEqual(event["request_chain"][1]["reference_span"], [0, 4])

    def test_comparison_targets_are_pinned_and_require_correct_control_status(self):
        rows = [{"index": i, "status": "complete"} for i in range(500)]
        for i in MARKED_COMPARISON_INDICES:
            rows[i]["status"] = "roots_without_valid_analysis"
        targets = comparison_targets(rows)
        self.assertEqual(targets, [
            (76, "successful_strict_control"),
            (244, "successful_strict_control"),
            (463, "marked_opt_in"),
            (480, "marked_opt_in"),
        ])
        rows[244]["status"] = "no_structural_root"
        with self.assertRaisesRegex(ValueError, "no longer complete"):
            comparison_targets(rows)

        report = comparison_summary([
            {"kind": "successful_strict_control", "replay_outcome": "complete",
             "traces": {}},
            {"kind": "marked_opt_in", "replay_outcome": "complete",
             "traces": {"selected_or_fallback": {"events": [
                 {"stage": "positive_evidence_materialized_missing"}
             ]}}},
        ])
        self.assertEqual(report["positive_evidence_events_sampled"], 1)
        self.assertTrue(report["paired_observation_only"])

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
