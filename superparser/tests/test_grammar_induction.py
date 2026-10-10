"""Focused tests for the parser-backed grammar induction experiment."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research.induction.grammar_induction import (
    GrammarHypothesisRegistry,
    ProductionObservation,
    SentenceGrammarObservation,
    observe_parse,
)
from seman_parser import Parser


DATA = Path(__file__).resolve().parents[1] / "data"


class GrammarInductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def test_observation_reuses_lattice_tree_and_shared_forest(self):
        result = self.parser.parse("The young man opened the door.").result
        observation = observe_parse("example-1", result, self.parser.resources.grammar)
        self.assertTrue(observation.completed)
        self.assertGreater(observation.forest_nodes, 0)
        self.assertGreaterEqual(observation.forest_derivations, observation.forest_nodes)
        self.assertTrue(observation.token_vectors)
        self.assertTrue(any(row.lhs == "NP" for row in observation.productions))
        self.assertTrue(any(row.kind == "macro" for row in observation.productions))

    def test_registry_is_incremental_persistent_and_keeps_macros_experimental(self):
        registry = GrammarHypothesisRegistry(self.parser.resources.grammar)
        row = ProductionObservation(
            "NP", ("DET", "ADJ", "N", "PP", "PP"), (),
            ((), (), (), (), ()), "macro", ("np_det_nom", "nom_adj_n"),
        )
        for index in range(3):
            registry.ingest(SentenceGrammarObservation(
                f"obs-{index}", f"example {index}", True, (), (row,), (), 1, 1, (),
            ))
        hypotheses = registry.hypotheses(min_support=3)
        self.assertEqual(len(hypotheses), 1)
        self.assertEqual(hypotheses[0].classification, "macro")
        with TemporaryDirectory() as directory:
            target = Path(directory) / "registry.json"
            registry.save(target)
            restored = GrammarHypothesisRegistry.load(target, self.parser.resources.grammar)
            self.assertEqual(restored.hypotheses(min_support=3), hypotheses)


if __name__ == "__main__":
    unittest.main()
