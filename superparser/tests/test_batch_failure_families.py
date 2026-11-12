"""Selected-tree regressions for multiple grammar construction families.

This is NOT a surface-success suite: each attested 500-source case must be
parsed by the canonical corpus gateway with the same 50k/500k budgets.
"""
from __future__ import annotations

from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser
from scripts.diagnose_novel_parses import select_cases

DATA = Path(__file__).resolve().parents[1] / "data"


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


class BatchGrammarFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)
        cls.cases = select_cases(500)[0]

    def _attested(self, index, exact):
        case = self.cases[index]
        self.assertEqual(case["source_text"], exact)
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertEqual(prepared.source_text, exact)
        self.assertEqual(prepared.analysis_text, exact)
        self.assertEqual(lattice.text, exact)
        self.assertEqual(result.text, exact)
        self.assertFalse(prepared.synthetic_prefix)
        self.assertFalse(prepared.synthetic_suffix)
        return result

    def _rule(self, result, expected, exact=None):
        self.assertTrue(result.completed, result.stats)
        best = result.best()
        self.assertIsNotNone(best)
        nodes = [node for node in walk(best) if node.rule_id == expected]
        self.assertTrue(nodes, (expected, [(x.rule_id, x.category) for x in walk(best)]))
        if exact is not None:
            self.assertIn(exact, [result.text[n.start:n.end] for n in nodes])
        return nodes[0]

    def test_141_emphatic_reflexive_with_predicative_adverb(self):
        source = "The envelope itself was likewise full."
        result = self._attested(141, source)
        np = self._rule(result, "np_emphatic_reflexive_agreement", "The envelope itself")
        self.assertEqual([result.text[ch.start:ch.end] for ch in np.children],
                         ["The envelope", "itself"])
        vp = self._rule(result, "vp_copula_predicative_scope_adjective",
                        "was likewise full")
        self.assertEqual([x.category for x in vp.children],
                         ["COPULA", "ADV", "ADJ"])

    def test_270_source_left_unresolved_for_bounded_composition_research(self):
        # No broad NP+NP+V grammar fallback may be introduced just to
        # complete this case: it was proved to cause parser saturation.
        source = "This I hired."
        case = self.cases[270]
        self.assertEqual(case["source_text"], source)
        prepared, _, result = parse_corpus_case(
            self.parser, case, max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertEqual(prepared.source_text, result.text)
        if result.best() is not None:
            self.assertFalse(any(
                node.rule_id == "clause_object_topicalization_finite"
                for node in walk(result.best())
            ))

    def test_280_conventional_valediction_not_invented_finite_clause(self):
        source = "Good night, my sister."
        result = self._attested(280, source)
        root = self._rule(result, "clause_time_of_day_valediction_vocative")
        self.assertEqual(root.features.as_dict().get("minor_utterance"), "true")
        self.assertEqual(
            [result.text[ch.start:ch.end] for ch in root.children],
            ["Good", "night", ",", "my sister"],
        )
        self.assertEqual(
            [ch.category for ch in root.children],
            ["SALUTATION-MOD", "SALUTATION-TIME", "COMMA", "NP"],
        )

    def test_22_passive_adjectival_object_complement(self):
        source = "Our treasure was warranted sober and honest."
        result = self._attested(22, source)
        vp = self._rule(result, "vp_passive_resultative_predicative_adjp",
                        "was warranted sober and honest")
        self.assertEqual([ch.category for ch in vp.children],
                         ["AUX-BE", "V", "ADJP"])
        self.assertEqual(result.text[vp.children[-1].start:vp.children[-1].end],
                         "sober and honest")

    def test_positive_independent_construction_families(self):
        cases = (
            ("The letter itself was already open.",
             ("np_emphatic_reflexive_agreement",
              "vp_copula_predicative_scope_adjective")),
            ("Good evening, my friend.",
             ("clause_time_of_day_valediction_vocative",)),
            ("The product was deemed safe and effective.",
             ("vp_passive_resultative_predicative_adjp",)),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                result = self.parser.parse(
                    text, max_items=50_000,
                    kbest_work_limit=500_000,
                ).result
                for rule_id in expected:
                    self._rule(result, rule_id)

    def test_negative_licensing_and_agreement_controls(self):
        pairs = (
            ("The envelopes itself were already open.",
             "np_emphatic_reflexive_agreement"),
            ("Good table, my sister.",
             "clause_time_of_day_valediction_vocative"),
            ("The product was read safe and effective.",
             "vp_passive_resultative_predicative_adjp"),
            ("The letter was quickly open.",
             "vp_copula_predicative_scope_adjective"),
        )
        for text, forbidden in pairs:
            with self.subTest(text=text):
                result = self.parser.parse(
                    text, max_items=50_000,
                    kbest_work_limit=500_000,
                ).result
                for candidate in result.alternatives(limit=8):
                    self.assertFalse(
                        any(node.rule_id == forbidden for node in walk(candidate)),
                        (text, forbidden),
                    )


if __name__ == "__main__":
    unittest.main()
