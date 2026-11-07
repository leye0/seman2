"""Safety contract for opt-in preflight routing to the existing lazy trie."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from seman_parser.complexity_routing import ComplexityPolicy
from seman_parser.engine import Parser, ParserResources
from seman_parser.fast_preflight import (
    PreflightTriePolicy, PreflightTrieRouter, fast_preflight,
)
from seman_parser.segmentation import build_lattice


DATA = Path(__file__).resolve().parents[1] / "data"
HARD = (
    "John opened the box, and Mary gave the book to Robert while the other "
    "children waited near the doorway for their parents to arrive near the "
    "old stone bridge on the quiet country road beside the church.",
    "The doctor opened the door, and the old man stood beside the table "
    "while the younger children waited quietly in the hallway and the "
    "neighbors gathered in the street before the morning sun appeared.",
)
UNSEGMENTED_LONG = (
    "John opened the box in the room near the window across the house "
    "behind the church beside the river on the road before the old stone "
    "bridge under the cloudy sky over the hills."
)


class PreflightRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = ParserResources.from_dir(DATA)
        cls.normal = Parser(cls.resources, cache_size=0, max_items=50000)
        cls.routed = Parser(
            cls.resources, cache_size=0, max_items=50000,
            preflight_route_policy=PreflightTriePolicy(minimum_tokens=17),
        )

    def test_opt_in_only_and_no_mixed_routing_policies(self):
        self.assertIsNone(self.normal._preflight_router)
        self.assertIsNone(self.normal._difficult_vector_grammar)
        self.assertIsNotNone(self.routed._preflight_router)
        self.assertTrue(self.routed._difficult_vector_grammar.lazy_trie_recognition)
        with self.assertRaisesRegex(ValueError, "Choose one experimental"):
            Parser(
                self.resources,
                complexity_policy=ComplexityPolicy(rule_start_threshold=1),
                preflight_route_policy=PreflightTriePolicy(minimum_tokens=17),
            )
        for value in (0, -1):
            with self.assertRaisesRegex(ValueError, "positive minimum_tokens"):
                PreflightTriePolicy(minimum_tokens=value)
        for route_on in ((), ("length_attention", "length_attention"),
                         ("adjacent_candidate_agreement_hypothesis",),
                         ("dialogue_or_quote_surface",)):
            with self.assertRaises(ValueError):
                PreflightTriePolicy(minimum_tokens=17, route_on=route_on)

    def test_cheap_short_sentence_is_canonical_and_never_runs_signal_probe(self):
        text = "John opened the box."
        lattice = build_lattice(text, self.resources.lexicon)
        router = self.routed._preflight_router
        with patch("seman_parser.fast_preflight.fast_preflight",
                   side_effect=AssertionError("Short must not probe")):
            decision = router.choose(lattice)
        self.assertEqual(decision.strategy, "canonical")
        self.assertEqual(decision.reason, "preflight_below_minimum_tokens")
        self.assertEqual(decision.measured_ms, 0.0)
        normal = self.normal.parse(text, max_items=50000, kbest_work_limit=500000)
        routed = self.routed.parse(text, max_items=50000, kbest_work_limit=500000)
        self.assertEqual(routed.result.stats["complexity_route"], "canonical")
        self.assertFalse(routed.result.stats["lazy_trie_recognition"])
        self.assertEqual(normal.result.best().as_dict(),
                         routed.result.best().as_dict())

    def test_quoted_prose_remains_canonical_even_when_very_long(self):
        text = '"John opened the box, and Mary opened the door, and Robert took "the keys" from the house," said the older man.'
        lattice = build_lattice(text, self.resources.lexicon)
        router = self.routed._preflight_router
        self.assertEqual(router.choose(lattice, dialogue=True).reason,
                         "preflight_dialogue_preserved")
        decision = router.choose(lattice)
        self.assertEqual(decision.strategy, "canonical")
        self.assertEqual(decision.reason, "preflight_quote_preserved")
        chosen = self.routed.parse(text, max_items=50000, kbest_work_limit=500000)
        self.assertFalse(chosen.result.stats["lazy_trie_recognition"])

    def test_long_sentence_uses_trie_without_losing_selected_tree(self):
        for sentence in HARD:
            with self.subTest(sentence=sentence):
                normal = self.normal.parse(
                    sentence, max_items=50000, kbest_work_limit=500000).result
                routed = self.routed.parse(
                    sentence, max_items=50000, kbest_work_limit=500000).result
                self.assertEqual(routed.stats["complexity_route"], "trie")
                self.assertEqual(routed.stats["complexity_router_source"],
                                 "fast_preflight_surface")
                self.assertTrue(routed.stats["lazy_trie_recognition"])
                self.assertEqual(normal.completed, routed.completed)
                if not (normal.stats.get("budget_exceeded")
                        or routed.stats.get("budget_exceeded")):
                    self.assertEqual(
                        normal.best().as_dict() if normal.completed else None,
                        routed.best().as_dict() if routed.completed else None)

    def test_punctuation_route_is_independent_of_morphological_hypothesis(self):
        text = "John opened the box, and Mary opened the door, and Robert took the keys, and the doctor looked away."
        lattice = build_lattice(text, self.resources.lexicon)
        summary = fast_preflight(text, lattice=lattice,
                                 include_candidate_hypotheses=False)
        self.assertEqual(summary.phase, "existing_lattice_surface_only")
        self.assertNotIn("adjacent_candidate_agreement_hypothesis",
                         summary.signals)
        decision = PreflightTrieRouter(
            PreflightTriePolicy(
                minimum_tokens=10,
                route_on=("many_comma_boundaries",),
            )).choose(lattice, observation=summary.as_dict())
        self.assertEqual(decision.strategy, "trie")
        self.assertIn("many_comma_boundaries", decision.reason)
        with self.assertRaisesRegex(ValueError, "does not match lattice"):
            self.routed._preflight_router.choose(
                lattice, observation={"analysis_text": "other", "signals": []})

    def test_diagnostic_preflight_observation_is_reused_by_router(self):
        sentence = UNSEGMENTED_LONG
        with patch.object(self.routed._preflight_router, "choose",
                          wraps=self.routed._preflight_router.choose) as choose:
            result = self.routed.parse(
                sentence, max_items=50000, kbest_work_limit=500000,
                preflight_diagnostics=True,
            ).result
        self.assertEqual(result.stats["complexity_route"], "trie")
        self.assertEqual(choose.call_count, 1)
        self.assertIs(choose.call_args.kwargs["observation"],
                      result.stats["fast_preflight"])
        self.assertEqual(result.stats["fast_preflight"]["phase"],
                         "existing_lattice")

    def test_warm_only_timing_ignores_initial_cache_outliers(self):
        from scripts.benchmark_preflight_trie_pilot import summarize

        pilot = [
            {"index": 1, "expected_route": "trie"},
            {"index": 2, "expected_route": "canonical"},
        ]
        records = []
        for index, expected in ((1, "trie"), (2, "canonical")):
            for rep in range(4):
                # Simulate a severe first-use lexical cache asymmetry in an
                # otherwise identical canonical control path.
                baseline_ms = 300 if index == 2 and rep == 0 else 100
                experiment_ms = (
                    50 if index == 1 else 30 if rep == 0 else 100
                )
                for policy, duration, route in (
                    ("canonical", baseline_ms, None),
                    ("preflight", experiment_ms, expected),
                ):
                    records.append({
                        "index": index, "repeat": rep,
                        "policy": policy, "expected_route": expected,
                        "status": "complete",
                        "selected_signature": "same-tree",
                        "complexity_route": route,
                        "forest_or_kbest_budget_exceeded": False,
                        "full_parse_ms": duration,
                    })
        result = summarize(records, pilot)
        self.assertEqual(result["pairs"], 8)
        self.assertEqual(result["uncensored_pairs"], 8)
        self.assertEqual(result["timing_trie_routed_warm_only"]
                         ["median_paired_ratio"], 0.5)
        self.assertEqual(result["timing_nonrouted_control_warm_only"]
                         ["median_paired_ratio"], 1.0)
        self.assertEqual(result["warm_control_adjusted_ratio"], 0.5)
        self.assertEqual(result["cold_control_outlier_indices"], [2])
        self.assertEqual(result["completed_canonical_lost_indices"], [])
        self.assertEqual(result["unsaturated_tree_change_indices"], [])

    def test_quote_routing_does_not_activate_marked_grammar(self):
        text = '"The boys was playing," said Mary.'
        routed = self.routed.parse(
            text, max_items=50000, kbest_work_limit=500000).result
        canonical = self.normal.parse(
            text, max_items=50000, kbest_work_limit=500000).result
        self.assertEqual(routed.completed, canonical.completed)
        self.assertEqual(routed.stats.get("marked_mode"),
                         canonical.stats.get("marked_mode"))
        self.assertFalse(routed.stats["lazy_trie_recognition"])


if __name__ == "__main__":
    unittest.main()
