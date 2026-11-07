"""P1: conservative quoted-clause subject/predicate agreement evidence."""
from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.engine import Parser, ParserResources

DATA = Path(__file__).resolve().parents[1] / "data"


class MarkedFiniteAgreementTests(unittest.TestCase):
    @staticmethod
    def _walk(node):
        yield node
        for child in node.children:
            yield from MarkedFiniteAgreementTests._walk(child)

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(DATA), cache_size=0)

    def verify_marked(self, text, rule_id, feature, expected, observed, subject, predicate, head):
        strict = self.parser.parse(text).result
        self.assertEqual(strict.usage_deviations(), ())
        marked = self.parser.parse(text, allow_marked_deviations=True).result
        self.assertTrue(marked.completed, marked.stats)
        self.assertEqual(marked.as_dict()["grammatical_status"], "nonstandard_attested")
        deviations = marked.usage_deviations()
        self.assertEqual(len(deviations), 1)
        deviation = deviations[0]
        self.assertEqual(deviation.rule_id, rule_id)
        self.assertEqual(deviation.relation, "subject_to_finite_predicate")
        self.assertEqual((deviation.feature, deviation.expected, deviation.observed),
                         (feature, expected, observed))
        self.assertEqual(deviation.subject_surface, subject)
        self.assertEqual(deviation.predicate_surface, predicate)
        self.assertEqual(deviation.intent, "unknown")
        self.assertEqual(deviation.register, "unknown")
        proof = marked.as_dict(reference_span=lambda a, b: (a, b))["usage_deviations"][0]
        self.assertEqual(proof["evidence"]["type"], "explicit_marked_grammar_rule")
        self.assertEqual(proof["subject"]["reference_mapping"], "exact")
        self.assertEqual(proof["predicate"]["reference_mapping"], "exact")
        bearer = proof["evidence"]["predicate_head"]
        self.assertEqual(bearer["surface"], head)
        self.assertEqual(bearer["features"][feature], observed)
        self.assertEqual(bearer["reference_mapping"], "exact")
        self.assertEqual(bearer["analysis_span"], bearer["reference_span"])
        self.assertEqual(text[slice(*bearer["analysis_span"])], head)
        node = marked.best()
        for i in proof["evidence"]["parent"]["path"]:
            node = node.children[i]
        self.assertEqual(node.rule_id, rule_id)
        self.assertEqual(node.category, "MARKED-FINITE-CLAUSE")
        self.assertEqual([c.category for c in node.children], ["NP", "VP"])
        quoted = [n for n in self._walk(marked.best()) if n.rule_id in {
            "dialogue_quote_marked_finite_clause_stop",
            "dialogue_quote_marked_finite_clause_comma",
        }]
        self.assertEqual(len(quoted), 1)
        self.assertEqual(quoted[0].children[1], node)
        self.assertIn(quoted[0].children[2].category, {"COMMA", "SPEECH-STOP"})
        # Quote punctuation can project a syntactic COMMA from a written dot;
        # neither the source character nor its span is rewritten.
        punctuation = quoted[0].children[2]
        self.assertEqual(text[punctuation.start:punctuation.end], ".")
        leaf = marked.best()
        for i in bearer["path"]:
            leaf = leaf.children[i]
        self.assertIsNotNone(leaf.lexical_candidate)
        self.assertEqual(leaf.lexical_candidate.features.as_dict()[feature], observed)

    def test_number_mismatch_plural_subject_singular_finite(self):
        self.verify_marked('"They exclaims."',
                           "marked_clause_3pl_subject_3sg_finite",
                           "number", "plural", "singular", "They", "exclaims", "exclaims")

    def test_person_mismatch_third_subject_first_finite(self):
        self.verify_marked('"She am happy."',
                           "marked_clause_3sg_subject_1sg_finite",
                           "person", "3", "1", "She", "am happy", "am")

    def test_ordinary_quoted_controls_remain_unmarked(self):
        for text in ('"They exclaim."', '"She is happy."', '"I am happy."',
                     '"You are happy."', '"They were happy."'):
            with self.subTest(text=text):
                strict = self.parser.parse(text).result
                marked = self.parser.parse(text, allow_marked_deviations=True).result
                self.assertTrue(strict.completed, strict.stats)
                self.assertEqual(strict.usage_deviations(), ())
                self.assertEqual(marked.usage_deviations(), ())
                self.assertEqual(marked.as_dict()["grammatical_status"], "standard")

    def test_nonfinite_fragments_do_not_acquire_false_finite_conflicts(self):
        for text in ('"They running."', '"She been happy."'):
            with self.subTest(text=text):
                self.assertEqual(self.parser.parse(text, allow_marked_deviations=True)
                                 .result.usage_deviations(), ())

    def test_no_marked_parse_without_explicit_quotation(self):
        for text in ("They exclaims.", "She am happy."):
            with self.subTest(text=text):
                marked = self.parser.parse(text, allow_marked_deviations=True).result
                self.assertEqual(marked.usage_deviations(), ())
                self.assertFalse(marked.stats.get("marked_mode", False))


if __name__ == "__main__":
    unittest.main()
