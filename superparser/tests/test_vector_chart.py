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
        self.assertEqual(result.stats["kbest_ms"], 0.0)

    def test_ambiguity_is_packed_before_feature_unification(self) -> None:
        result = self.parser.parse("I saw the man with the telescope.").result
        self.assertTrue(result.completed)
        best_attempts = result.stats["unification_attempts"]
        self.assertGreaterEqual(len(result.alternatives(limit=2)), 2)
        self.assertGreaterEqual(result.stats["unification_attempts"], best_attempts)
        self.assertGreater(result.stats["kbest_ms"], 0.0)

    def test_semantic_roles_survive_delayed_materialization(self) -> None:
        best = self.parser.parse("John gave Mary the box.").result.best()
        self.assertIsNotNone(best)
        assert best is not None
        relations = {edge.relation for edge in best.semantic.graph.relations}
        self.assertIn("RECIPIENT", relations)
        self.assertIn("THEME", relations)


if __name__ == "__main__":
    unittest.main()
