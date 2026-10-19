"""Focused contract tests for the integrated vector parser."""

from pathlib import Path
import unittest
import os

from seman_parser import Parser
from seman_parser.engine import ParserResources


DATA = Path(__file__).resolve().parents[1] / "data"


class VectorChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = Parser(ParserResources.from_dir(DATA, wordnet_dict=os.environ.get('WORDNET_DICT')), cache_size=0)

    def test_parser_uses_vector_engine_and_retains_shared_forest(self) -> None:
        result = self.parser.parse("John opened the box.").result
        self.assertTrue(result.completed)
        self.assertEqual(result.stats["engine"], "vector-lazy-kbest")
        self.assertIsNotNone(result.shared_forest)
        self.assertGreater(result.stats["structural_derivations"], 1)
        self.assertGreater(result.stats["structural_root_nodes"], 0)
        self.assertEqual(result.stats["duplicate_partial_proposals"], 0)
        self.assertGreater(result.stats["duplicate_transitions_avoided"], 0)
        self.assertEqual(result.stats["kbest_ms"], 0.0)

    def test_ambiguity_is_packed_before_feature_unification(self) -> None:
        result = self.parser.parse("I saw the man with the telescope.").result
        self.assertTrue(result.completed)
        best_attempts = result.stats["unification_attempts"]
        self.assertGreaterEqual(len(result.alternatives(limit=2)), 2)
        self.assertGreaterEqual(result.stats["unification_attempts"], best_attempts)
        self.assertGreater(result.stats["hint_compatibility_cache_hits"], 0)
        self.assertGreater(result.stats["kbest_ms"], 0.0)

    def test_diagnostic_mode_exposes_a_wider_root_view(self) -> None:
        result = self.parser.parse_diagnostic(
            "I saw the man with the telescope.", alternatives=16,
        ).result
        self.assertTrue(result.completed)
        self.assertTrue(result.stats["diagnostic_mode"])
        self.assertEqual(result.stats["diagnostic_k"], 16)
        self.assertGreaterEqual(len(result.alternatives(limit=16)), 2)

    def test_semantic_roles_survive_delayed_materialization(self) -> None:
        report = self.parser.parse("John gave Mary the box.")
        best = report.result.best()
        self.assertIsNotNone(best)
        assert best is not None
        relations = {edge.relation for edge in report.interpret(best).graph.relations}
        self.assertIn("RECIPIENT", relations)
        self.assertIn("THEME", relations)

    def test_long_clause_list_uses_hierarchical_coordination(self) -> None:
        text = (
            "Mom worked during the day, Dad sometimes worked from home, "
            "Eli was learning to read longer sentences, and somebody always "
            "needed the bathroom when somebody else was late."
        )
        result = self.parser.parse(text).result
        best = result.best()
        self.assertTrue(result.completed)
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(result.stats["engine"], "vector-hierarchical-lazy-kbest")
        self.assertEqual(result.stats["segment_count"], 4)
        self.assertEqual(best.rule_id, "clause_list4")

        interfaces = []
        agenda = [best]
        while agenda:
            item = agenda.pop()
            if item.rule_id == "segment_interface":
                interfaces.append(item)
            agenda.extend(item.children)
        self.assertEqual(len(interfaces), 4)
        self.assertTrue(all("event" in item.syntax.anchors for item in interfaces))
        self.assertEqual(
            sorted((item.start, item.end) for item in interfaces),
            [(0, 25), (27, 57), (59, 100), (106, 169)],
        )
        relations = [edge.relation for edge in self.parser.parse(text).interpret(best).graph.relations]
        self.assertEqual(relations.count("CONJUNCT"), 3)
        self.assertIn("TEMPORAL", relations)
        self.assertLess(result.stats["combinations_visited_for_best"], 1_000)
        self.assertIsInstance(result.shared_forest, dict)
        self.assertEqual(len(result.shared_forest["segments"]), 4)

        agenda = [best]
        while agenda:
            item = agenda.pop()
            for anchor in item.syntax.anchors.values():
                if not anchor.startswith("lex:"):
                    continue
                _prefix, start, end, _category, _lemma = anchor.split(":", 4)
                self.assertGreaterEqual(int(start), item.start)
                self.assertLessEqual(int(end), item.end)
            if item.lexical_candidate is not None:
                candidate = item.lexical_candidate
                self.assertEqual(text[candidate.span_start:candidate.span_end], candidate.surface)
            agenda.extend(item.children)

    def test_comma_delimited_relative_falls_back_to_global_parse(self) -> None:
        result = self.parser.parse("John, who left, opened the box.").result
        self.assertTrue(result.completed)
        self.assertNotEqual(result.stats["engine"], "vector-hierarchical-lazy-kbest")

    def test_nominal_enumeration_falls_back_to_global_parse(self) -> None:
        report = self.parser.parse("John bought apples, oranges, and pears.")
        result = report.result
        self.assertTrue(result.completed)
        self.assertNotEqual(result.stats["engine"], "vector-hierarchical-lazy-kbest")
        best = result.best()
        assert best is not None
        relations = [edge.relation for edge in report.interpret(best).graph.relations]
        self.assertGreaterEqual(relations.count("CONJUNCT"), 2)

    def test_coordinated_bare_imperatives_are_full_clauses(self) -> None:
        # Shared subject belongs to both imperatives; no dummy finite verb.
        for sentence in ("Come and see him.", "Open the box and close it."):
            with self.subTest(sentence=sentence):
                report = self.parser.parse(sentence)
                self.assertTrue(report.result.completed, report.result.stats)
                agenda = [report.result.best()]
                rule_ids = set()
                while agenda:
                    item = agenda.pop()
                    rule_ids.add(item.rule_id)
                    agenda.extend(item.children)
                self.assertIn("vpnp_bare_coord", rule_ids)

    def test_postposed_discourse_adverb_requires_comma(self) -> None:
        for sentence in ("John opened the box, too.", "John opened the box, however."):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                agenda = [result.best()]
                rules = set()
                while agenda:
                    item = agenda.pop()
                    rules.add(item.rule_id)
                    agenda.extend(item.children)
                self.assertIn("clause_post_adv_comma", rules)

    def test_bare_imperative_accepts_regular_adverbial_modification(self) -> None:
        report = self.parser.parse("Open the box carefully.")
        self.assertTrue(report.result.completed, report.result.stats)
        stack = [report.result.best()]
        ids = set()
        while stack:
            item = stack.pop()
            ids.add(item.rule_id)
            stack.extend(item.children)
        self.assertIn("vpnp_post_adv", ids)

    def test_kbest_work_budget_never_claims_incomplete_parse_as_success(self) -> None:
        from seman_parser.segmentation import build_lattice
        text="John opened the box."
        parser=self.parser
        lattice=build_lattice(text,parser.resources.lexicon,multiword_max=1)
        engine=parser._vector_grammar
        limited=engine.parse_lattice(
            lattice,beam=parser.beam,max_items=20000,
            goal_category=parser.goal_category,kbest_work_limit=1)
        self.assertFalse(limited.completed)
        self.assertTrue(limited.stats["kbest_budget_exceeded"])
        self.assertGreater(limited.stats["structural_root_nodes"], 0)
        # A one-unit budget may stop before the first combination.
        # The failed branch must still export the actual counters.
        self.assertEqual(
            limited.stats["combinations_visited_for_best"],
            limited.stats["combinations_visited_total"],
        )
        self.assertGreater(limited.stats["kbest_work_units"], 1)
        self.assertEqual(limited.stats["kbest_work_limit"],1)
        self.assertIsNone(limited.best())
        # A sufficient budget must recover precisely the normal complete
        # parse, not change the scorer or grammar.
        unlimited=engine.parse_lattice(
            lattice,beam=parser.beam,max_items=20000,
            goal_category=parser.goal_category)
        full=engine.parse_lattice(
            lattice,beam=parser.beam,max_items=20000,
            goal_category=parser.goal_category,kbest_work_limit=1_000_000)
        self.assertTrue(unlimited.completed)
        self.assertTrue(full.completed)
        self.assertFalse(full.stats["kbest_budget_exceeded"])
        self.assertEqual(full.best().signature(),unlimited.best().signature())

    def test_required_evidence_prunes_impossible_kbest_branches(self) -> None:
        sentinels = (
            "In the first, everybody followed her initial idea.",
            "Without those labels, the shapes suggested more agreement "
            "than the numbers actually provided.",
        )
        for text in sentinels:
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                self.assertIsNotNone(result.best())
                self.assertLess(
                    result.stats["combinations_visited_for_best"], 100,
                )


if __name__ == "__main__":
    unittest.main()
