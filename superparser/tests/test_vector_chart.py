"""Focused contract tests for the integrated vector parser."""

from pathlib import Path
import unittest

from seman_parser import Parser


DATA = Path(__file__).resolve().parents[1] / "data"


class VectorChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def test_parser_uses_vector_engine_and_retains_shared_forest(self) -> None:
        result = self.parser.parse("John opened the box.").result
        self.assertTrue(result.completed)
        self.assertEqual(result.stats["engine"], "vector-lazy-kbest")
        self.assertIsNotNone(result.shared_forest)
        self.assertGreater(result.stats["structural_derivations"], 1)
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

    def test_semantic_roles_survive_delayed_materialization(self) -> None:
        best = self.parser.parse("John gave Mary the box.").result.best()
        self.assertIsNotNone(best)
        assert best is not None
        relations = {edge.relation for edge in best.semantic.graph.relations}
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
        self.assertTrue(all("event" in item.semantic.handles for item in interfaces))
        self.assertEqual(
            sorted((item.start, item.end) for item in interfaces),
            [(0, 25), (27, 57), (59, 100), (106, 169)],
        )
        relations = [edge.relation for edge in best.semantic.graph.relations]
        self.assertEqual(relations.count("CONJUNCT"), 3)
        self.assertIn("TEMPORAL", relations)
        self.assertLess(result.stats["combinations_visited_for_best"], 1_000)
        self.assertIsInstance(result.shared_forest, dict)
        self.assertEqual(len(result.shared_forest["segments"]), 4)

    def test_comma_delimited_relative_falls_back_to_global_parse(self) -> None:
        result = self.parser.parse("John, who left, opened the box.").result
        self.assertTrue(result.completed)
        self.assertNotEqual(result.stats["engine"], "vector-hierarchical-lazy-kbest")
        self.assertTrue(result.stats["segmentation_fallback"])

    def test_nominal_enumeration_falls_back_to_global_parse(self) -> None:
        result = self.parser.parse("John bought apples, oranges, and pears.").result
        self.assertTrue(result.completed)
        self.assertNotEqual(result.stats["engine"], "vector-hierarchical-lazy-kbest")
        self.assertTrue(result.stats["segmentation_fallback"])
        best = result.best()
        assert best is not None
        relations = [edge.relation for edge in best.semantic.graph.relations]
        self.assertGreaterEqual(relations.count("CONJUNCT"), 2)


if __name__ == "__main__":
    unittest.main()
