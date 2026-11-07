"""Corpus 473: rank-one, non-lexical coordination of two headed relatives."""

from __future__ import annotations

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser, ParserResources


DATA = Path(__file__).resolve().parents[1] / "data"


def walk(item):
    yield item
    for child in item.children:
        yield from walk(child)


def uniquely(item, rule_id):
    matches = [child for child in walk(item) if child.rule_id == rule_id]
    assert len(matches) == 1, (rule_id, len(matches))
    return matches[0]


class CoordinatedSupplementaryRelativesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(DATA), cache_size=0)

    def test_pinned_473_has_two_relative_gaps_on_one_antecedent(self):
        case = select_cases(500)[0][473]
        prepared, lattice, result = parse_corpus_case(self.parser, case)
        self.assertEqual(prepared.analysis_text, lattice.text)
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertEqual(result.usage_deviations(), ())

        best = result.best()
        self.assertEqual(best.rule_id, "clause_np_vp")
        self.assertEqual(best.children[1].rule_id, "vp_cop_np")
        self.assertEqual(prepared.analysis_text[best.children[0].start:best.children[0].end],
                         "the rest")

        head = uniquely(best, "n_compound")
        self.assertEqual(prepared.analysis_text[head.start:head.end], "revenue officers")
        self.assertEqual([prepared.analysis_text[c.start:c.end] for c in head.children],
                         ["revenue", "officers"])

        nominal = uniquely(best, "np_relative_pp_comma")
        self.assertEqual(prepared.analysis_text[nominal.children[1].start:nominal.children[1].end],
                         ",")
        coordinated = uniquely(best, "rel_pp_coordinated_with_object_relative")
        self.assertIs(nominal.children[2], coordinated)
        self.assertEqual([c.category for c in coordinated.children],
                         ["REL-CLAUSE-OBJ", "COMMA", "COORD", "REL-CLAUSE-PP"])
        self.assertEqual(prepared.analysis_text[coordinated.children[1].start:coordinated.children[1].end],
                         ",")
        self.assertEqual(prepared.analysis_text[coordinated.children[2].start:coordinated.children[2].end],
                         "and")

        object_rel, _, _, pp_rel = coordinated.children
        self.assertEqual(object_rel.rule_id, "rel_obj_overt_wh_perfect_gap_with_pp")
        self.assertEqual(prepared.analysis_text[object_rel.start:object_rel.end],
                         "whom he had met by the way")
        self.assertEqual([c.category for c in object_rel.children],
                         ["WH-REL-OBL", "NP", "HAVE", "V", "PP"])
        self.assertEqual(pp_rel.rule_id, "rel_pp_finite_np_vp")
        self.assertEqual(prepared.analysis_text[pp_rel.start:pp_rel.end],
                         "with whom he had had the intelligence to return at once")

        infinitive = uniquely(pp_rel, "np_inf_rel")
        self.assertEqual(prepared.analysis_text[infinitive.start:infinitive.end],
                         "the intelligence to return at once")
        self.assertEqual(prepared.analysis_text[infinitive.children[0].start:infinitive.children[0].end],
                         "the intelligence")
        self.assertEqual(prepared.analysis_text[infinitive.children[2].start:infinitive.children[2].end],
                         "return at once")
        self.assertFalse(any(item.rule_id == "vp_cop_np_inf" for item in walk(best)))
        self.assertFalse(any(item.rule_id == "np_relative_pp_comma_pair" for item in walk(best)),
                         "A terminal period cannot serve as the second comma")

    def test_independent_noun_heads_and_transitive_verbs(self):
        positives = (
            "The visitors were teachers, whom she had met by the river, and with whom she had had the courage to return at once.",
            "The sailors were coffee traders, whom she had met in the town, and with whom she had had the courage to sail at once.",
        )
        for sentence in positives:
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                best = result.best()
                self.assertEqual(best.children[1].rule_id, "vp_cop_np")
                group = uniquely(best, "rel_pp_coordinated_with_object_relative")
                self.assertEqual(group.children[0].rule_id,
                                 "rel_obj_overt_wh_perfect_gap_with_pp")
                self.assertEqual(group.children[3].rule_id, "rel_pp_finite_np_vp")
                self.assertEqual(len([n for n in walk(group.children[3]) if n.rule_id == "np_inf_rel"]), 1)
                self.assertEqual(result.usage_deviations(), ())

    def test_anaphoric_rest_keeps_both_attested_agreement_readings(self):
        for sentence in ("The rest were officers.", "The rest was water."):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, "clause_np_vp")
                self.assertEqual(result.usage_deviations(), ())

    def test_compound_head_number_does_not_promote_determiner_homographs(self):
        noun_parser = Parser(self.parser.resources, goal_category="NP", cache_size=0)
        for phrase in ("revenue officers", "coffee traders", "school bus driver"):
            with self.subTest(phrase=phrase):
                result = noun_parser.parse(phrase).result
                self.assertTrue(result.completed, result.stats)
                self.assertIn("n_compound", {item.rule_id for item in walk(result.best())})
        self.assertFalse(noun_parser.parse("a heavy gales").result.completed)
        self.assertFalse(self.parser.parse("He does not likes coffee.").result.completed,
                         "A false noun compound cannot rescue unlicensed auxiliary agreement")

    def test_no_wrong_agreement_or_intransitive_object_gap(self):
        negatives = (
            "The officer were revenue officers, whom he had met by the way, and with whom he had had the intelligence to return at once.",
            "The visitors were teachers, whom she had slept by the river, and with whom she had had the courage to return at once.",
        )
        for sentence in negatives:
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertFalse(result.completed, result.stats)
                self.assertEqual(result.usage_deviations(), ())

    def test_quote_budget_witness_359_stays_complete(self):
        case = select_cases(500)[0][359]
        _, _, result = parse_corpus_case(self.parser, case)
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.best().rule_id, "dialogue_unattributed")


if __name__ == "__main__":
    unittest.main()
