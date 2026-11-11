"""Sentence 463: structural attachments and explicit dialectal agreement evidence."""

from __future__ import annotations

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from superparser.tests.attested_novel_cases import select_attested_cases as select_cases
from seman_parser.engine import Parser, ParserResources

DATA = Path(__file__).resolve().parents[1] / "data"
MARKED_RULE = "wh_clause_postposed_relative_marked_plural_subject_singular_copula"


def walk(item):
    yield item
    for child in item.children:
        yield from walk(child)


def node(item, rule_id):
    matching = [child for child in walk(item) if child.rule_id == rule_id]
    assert len(matching) == 1, (rule_id, len(matching))
    return matching[0]


class MarkedNonstandardUsageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(DATA), cache_size=0)

    def test_pinned_463_only_in_marked_mode_with_exact_relationships(self):
        case = select_cases(500)[0][463]
        prepared, lattice, strict = parse_corpus_case(self.parser, case)
        self.assertFalse(strict.completed, strict.stats)
        self.assertEqual(strict.usage_deviations(), ())
        self.assertEqual(prepared.analysis_text, lattice.text)

        prepared, lattice, marked = parse_corpus_case(
            self.parser, case, allow_marked_deviations=True,
        )
        self.assertTrue(marked.completed, marked.stats)
        self.assertEqual(prepared.analysis_text, marked.text)
        self.assertEqual(prepared.source_text, case["source_text"])
        self.assertTrue(marked.stats["marked_mode"])
        self.assertEqual(len(marked.usage_deviations()), 1)
        violation = marked.usage_deviations()[0].as_dict()
        self.assertEqual(violation["rule_id"], MARKED_RULE)
        self.assertEqual(violation["subject"]["analysis_span"], [64, 76])
        self.assertEqual(violation["predicate"]["analysis_span"], [77, 80])
        self.assertEqual(prepared.reference_span(64, 76), (63, 75))
        self.assertEqual(prepared.reference_span(77, 80), (76, 79))
        self.assertIsNone(prepared.reference_span(0, 1),
                          "Transferred quote has no original source span")
        self.assertEqual(violation["subject"]["features"]["number"], "plural")
        self.assertEqual(violation["predicate"]["features"]["number"], "singular")
        self.assertEqual((violation["expected"], violation["observed"]),
                         ("plural", "singular"))
        self.assertEqual(violation["intent"], "unknown")
        self.assertEqual(marked.as_dict()["grammatical_status"], "nonstandard_attested")

        best = marked.best()
        coordination = node(best, "clause_comma_coord")
        self.assertEqual(marked.text[coordination.children[1].start:coordination.children[1].end], ",")
        self.assertEqual(marked.text[coordination.children[2].start:coordination.children[2].end], "and")
        left = node(best, "vp_possessive_have_negative_correlative")
        self.assertEqual([c.category for c in left.children], ["HAVE-NEG-CORR", "NP-NEG-CORR"])
        self.assertEqual(marked.text[left.children[0].start:left.children[0].end], "'ve")
        neg = node(best, "np_negative_correlative_nor")
        self.assertEqual([c.category for c in neg.children], ["DET-NEG-CORR", "N", "COORD", "NP"])
        self.assertEqual(marked.text[neg.children[2].start:neg.children[2].end], "nor")

        matrix = node(best, "vp_complex_transitive_np_to_clausal_wh")
        self.assertEqual([c.category for c in matrix.children], ["V-COMPLEX-WH-INF", "NP", "TO", "V", "WH-CLAUSE"])
        self.assertEqual(marked.text[matrix.children[1].start:matrix.children[1].end], "it")
        self.assertEqual(marked.text[matrix.children[3].start:matrix.children[3].end], "fancy")
        embedded = node(best, MARKED_RULE)
        self.assertIs(matrix.children[4], embedded)
        self.assertEqual([c.category for c in embedded.children],
                         ["WH-NOM", "NP", "COPULA", "WH-SUBJ"])
        self.assertEqual(marked.text[embedded.children[1].start:embedded.children[1].end],
                         "your mothers")
        self.assertEqual(marked.text[embedded.children[3].start:embedded.children[3].end],
                         "that let you come to sea")
        self.assertEqual(embedded.children[3].rule_id, "wh_subj_clause")
        self.assertEqual({link.relation for link in embedded.syntax.links},
                         {"question_marker", "subject_and_relative_antecedent",
                          "locative_copula", "postposed_subject_relative"})
        terminal = node(best, "dialogue_quote_clause_comma").children[2]
        self.assertEqual((terminal.category, marked.text[terminal.start:terminal.end]),
                         ("COMMA", "."), "Retain established quotation punctuation ranking")

    def test_independent_structural_positives_and_negatives(self):
        for sentence in (
            "You've neither patience nor courage.",
            "You have neither courage nor patience.",
        ):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                node(result.best(), "vp_possessive_have_negative_correlative")

        for sentence in (
            "You've neither patience or courage.",
            "You've courage nor patience.",
        ):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                if result.best() is not None:
                    self.assertNotIn("np_negative_correlative_nor",
                                     {item.rule_id for item in walk(result.best())})

        for sentence in (
            "I leave it to imagine where the sailors were that let us go to sea.",
            "I leave it to fancy where the sailor was that let us go to sea.",
        ):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                node(result.best(), "vp_complex_transitive_np_to_clausal_wh")
                node(result.best(), "wh_clause_copula_postposed_subject_relative")
                self.assertEqual(result.usage_deviations(), ())

    def test_independent_marked_agreement_requires_explicit_opt_in_and_dialogue(self):
        text = '"I leave it to imagine where the sailors was that let us go to sea."'
        standard = self.parser.parse(text).result
        self.assertEqual(standard.usage_deviations(), ())
        marked = self.parser.parse(text, allow_marked_deviations=True).result
        self.assertTrue(marked.completed, marked.stats)
        deviation = marked.usage_deviations()
        self.assertEqual(len(deviation), 1)
        self.assertEqual(deviation[0].subject_surface, "the sailors")
        self.assertEqual(deviation[0].predicate_surface, "was")
        self.assertEqual(deviation[0].expected, "plural")
        self.assertEqual(deviation[0].observed, "singular")

        for text in ('"The sailors was."', "The sailors was.",
                     '"I leave it to imagine where the sailor were that let us go."'):
            with self.subTest(text=text):
                result = self.parser.parse(text, allow_marked_deviations=True).result
                self.assertEqual(result.usage_deviations(), ())


if __name__ == "__main__":
    unittest.main()
