"""Discourse structure for quoted coordinated ellipses (pinned case 414).

These are contextual fragments, not grammatical finite clauses invented from
lexical homographs. The target must retain the corpus quote provenance.
"""

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from superparser.tests.attested_novel_cases import select_attested_cases as select_cases
from seman_parser.dialogue import dialogue_lattice
from seman_parser.engine import Parser


DATA = Path(__file__).resolve().parents[1] / "data"
STRUCTURAL_ROOT = "dialogue_unattributed_coordinated_fragment_stop"


def nodes(root):
    yield root
    for child in root.children:
        yield from nodes(child)


class ContextualDialogueFragmentsTests(unittest.TestCase):
    def setUp(self):
        self.parser = Parser.from_dir(DATA)

    def test_pinned_case_414_keeps_contextual_ellipsis_and_exact_attachments(self):
        case = select_cases(500)[0][414]
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000,
            kbest_work_limit=500_000)
        self.assertEqual(prepared.source_text, case["source_text"])
        self.assertEqual(prepared.analysis_text, case["balanced_analysis_text"])
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])

        root = result.best()
        self.assertEqual(root.rule_id, STRUCTURAL_ROOT)
        self.assertEqual(root.features.as_dict()["context_required"], "true")
        self.assertEqual(root.features.as_dict()["ellipsis"],
                         "contextual_predicate")
        self.assertEqual(result.text[root.start:root.end],
                         case["balanced_analysis_text"])
        fragment, stop, close = root.children
        self.assertEqual((stop.category, close.category),
                         ("SPEECH-STOP", "CLOSE-QUOTE"))
        self.assertEqual(fragment.rule_id,
                         "dialogue_quoted_fragment_parenthetical_pp")
        core, comma, parenthetical = fragment.children
        self.assertEqual(core.rule_id,
                         "dialogue_quoted_coordinated_adverbial_pp_fragment")
        self.assertEqual(comma.category, "COMMA")
        self.assertEqual(result.text[parenthetical.start:parenthetical.end],
                         "in a manner of speaking")
        quote, coordinator, adverbials, situative = core.children
        self.assertEqual(quote.category, "OPEN-QUOTE-ELLIPTICAL-COORD")
        self.assertEqual(result.text[coordinator.start:coordinator.end], "and")
        self.assertEqual(adverbials.rule_id, "advp_adv_adv")
        self.assertEqual(result.text[adverbials.start:adverbials.end],
                         "now here")
        self.assertEqual(situative.rule_id, "pp_prep_np")
        self.assertEqual(result.text[situative.start:situative.end],
                         "on my own account")
        self.assertEqual(parenthetical.rule_id, "pp_prep_np")
        self.assertFalse(any(n.category in ("V", "VP", "COPULA", "AUX")
                             for n in nodes(root)),
                         "A contextual ellipsis must not invent a finite verb")

        expanded = dialogue_lattice(lattice)
        self.assertIsNotNone(expanded)
        typed = [c for c in expanded.candidates
                 if c.category == "OPEN-QUOTE-ELLIPTICAL-COORD"]
        self.assertEqual(len(typed), 1)
        self.assertTrue(any(
            c.category == "OPEN-QUOTE"
            and c.span_start == typed[0].span_start
            and c.span_end == typed[0].span_end
            and c.source == typed[0].source
            and c.sense_ids == typed[0].sense_ids
            for c in expanded.candidates))

    def test_unseen_vocabulary_generalizes_without_new_lexical_senses(self):
        for text, expected_adverbs, expected_pp in (
            ('"And later there with my family, for a while."',
             "later there", "with my family"),
            ('"And then here at the station, for the moment."',
             "then here", "at the station"),
        ):
            with self.subTest(text=text):
                result = self.parser.parse(
                    text, max_items=50_000,
                    kbest_work_limit=500_000).result
                self.assertTrue(result.completed, result.stats)
                self.assertFalse(result.stats["budget_exceeded"])
                root = result.best()
                self.assertEqual(root.rule_id, STRUCTURAL_ROOT)
                core = root.children[0].children[0]
                self.assertEqual(result.text[core.children[2].start:
                                             core.children[2].end],
                                 expected_adverbs)
                self.assertEqual(result.text[core.children[3].start:
                                             core.children[3].end], expected_pp)
                self.assertTrue(root.features.as_dict()["context_required"])

    def test_fragment_requires_overt_structural_evidence(self):
        valid = '"And now here at the station, for the moment."'
        invalid = (
            valid.replace('station, for', 'station for'),
            valid.replace('"And', '"Now'),
            valid.replace('now here at the station', 'now here'),
            valid.replace('moment."', 'moment"'),
        )
        for text in invalid:
            with self.subTest(text=text):
                report = self.parser.parse(
                    text, max_items=50_000,
                    kbest_work_limit=500_000)
                overlay = dialogue_lattice(report.lattice)
                if overlay is not None:
                    typed = [c for c in overlay.candidates
                             if c.category == "OPEN-QUOTE-ELLIPTICAL-COORD"]
                    if 'station, for' not in text or '"And' not in text:
                        self.assertFalse(typed)
                self.assertFalse(any(
                    item.rule_id == STRUCTURAL_ROOT
                    for item in report.result.alternatives(limit=3)))

    def test_359_dialogue_witness_retains_its_completed_root(self):
        case = select_cases(500)[0][359]
        prepared, _, result = parse_corpus_case(
            self.parser, case, max_items=50_000,
            kbest_work_limit=500_000)
        self.assertEqual(prepared.analysis_text, case["balanced_analysis_text"])
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.best().rule_id, "dialogue_unattributed")
        self.assertEqual(result.stats["forest_nodes"], 1472)
        self.assertEqual(result.stats["recognition_operations"], 49842)


if __name__ == "__main__":
    unittest.main()
