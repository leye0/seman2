"""Case 497: a corrective nominal *of*-complement with a discourse incise.

The correction belongs inside the existential pivot NP; it is not a
clause-final prepositional adjunct or an independent clause.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser, ParserResources


DATA = Path(__file__).resolve().parents[1] / "data"
CORRECTIVE = "np_of_complement_corrective_with_incise"


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


class Case497CorrectivePPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(DATA), cache_size=0,
                            max_items=50000)

    def test_pinned_case_is_not_a_clause_final_pp(self):
        case = select_cases(500)[0][497]
        prepared, _, result = parse_corpus_case(
            self.parser, case, max_items=50000,
            kbest_work_limit=500000, diagnostic_k=3,
        )
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.text, prepared.analysis_text)
        best = result.best()
        self.assertIsNotNone(best)
        corrective = [n for n in walk(best) if n.rule_id == CORRECTIVE]
        self.assertEqual(len(corrective), 1)
        nominal = corrective[0]
        self.assertEqual(nominal.category, "NP")
        self.assertEqual(result.text[nominal.start:nominal.end],
                         "no sign of reawakening courage in his followers, "
                         "rather, indeed, of growing terror at the irreverence "
                         "of his words")
        self.assertEqual([n.category for n in nominal.children],
                         ["NP", "COMMA", "OF-CORRECTION-TAIL"])
        original = nominal.children[0]
        self.assertEqual(original.rule_id, "np_det_n_of")
        self.assertEqual(result.text[original.children[3].start:
                                     original.children[3].end],
                         "reawakening courage in his followers")
        tail = nominal.children[2]
        self.assertEqual(tail.rule_id, "of_correction_tail_incise_with_pp")
        replacement = tail.children[-2]
        self.assertEqual(replacement.category, "NP")
        self.assertEqual(result.text[replacement.start:replacement.end],
                         "growing terror")
        modifier = tail.children[-1]
        self.assertEqual(modifier.category, "PP")
        self.assertEqual(result.text[modifier.start:modifier.end],
                         "at the irreverence of his words")

    def test_independent_corrective_and_negative_operator(self):
        positive = self.parser.parse(
            "There was no trace of progress, rather, indeed, of decline.",
            max_items=50000, kbest_work_limit=500000,
        ).result
        self.assertTrue(positive.completed, positive.stats)
        self.assertIn(CORRECTIVE,
                      {n.rule_id for n in walk(positive.best())})

        negative = self.parser.parse(
            "There was no trace of progress, rather, suddenly, of decline.",
            max_items=50000, kbest_work_limit=500000,
        ).result
        self.assertNotIn(CORRECTIVE,
                         {n.rule_id for tree in negative.alternatives(limit=4)
                          for n in walk(tree)})


if __name__ == "__main__":
    unittest.main()
