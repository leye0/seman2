"""Upper-level compass-bearing notes from the frozen novel corpus (case 434).

No sentence-level verb is reconstructed from non-sentential chart/map data.
The standard 16-point compass is a genuine closed notation inventory, while
all original single-letter and period candidates retain their provenance.
"""

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from superparser.tests.attested_novel_cases import select_attested_cases as select_cases
from seman_parser.engine import Parser


DATA = Path(__file__).resolve().parents[1] / "data"
NOTATION_ROOT = "clause_notational_bearing_and_measure"


def nodes(root):
    yield root
    for child in root.children:
        yield from nodes(child)


class CompassNotationTests(unittest.TestCase):
    def setUp(self):
        self.parser = Parser.from_dir(DATA)

    def test_pinned_case_434_has_exact_field_boundaries_and_no_finite_predicate(self):
        case = select_cases(500)[0][434]
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000)
        self.assertEqual(prepared.source_text, case["source_text"])
        self.assertEqual(prepared.analysis_text, case["balanced_analysis_text"])
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])

        root = result.best()
        self.assertEqual(root.rule_id, NOTATION_ROOT)
        self.assertEqual(root.features.as_dict()["utterance_type"], "notational_record")
        self.assertEqual(root.features.as_dict()["finite_predicate"], "absent")
        self.assertEqual(root.features.as_dict()["context_required"], "true")
        self.assertEqual((root.start, root.end), (0, len(prepared.analysis_text)))
        reference, measurement = root.children
        self.assertEqual(reference.rule_id, "notation_reference_with_bearing")
        self.assertEqual(measurement.rule_id, "notation_measure_distance")
        location, bearing = reference.children
        self.assertEqual(location.category, "NP-NOTATION")
        self.assertEqual(location.rule_id, "notation_place_name_compound")
        self.assertEqual(result.text[location.start:location.end], "Skeleton Island")
        self.assertEqual(bearing.rule_id, "notation_compass_and_by_bearing")
        self.assertEqual(result.text[bearing.start:bearing.end], "E.S.E. and by E.")
        first, coordinator, step, second = bearing.children
        self.assertEqual([c.category for c in bearing.children],
                         ["COMPASS-POINT", "COORD", "PREP-BY", "COMPASS-POINT"])
        self.assertEqual([result.text[c.start:c.end] for c in bearing.children],
                         ["E.S.E.", "and", "by", "E."])
        self.assertEqual([result.text[c.start:c.end] for c in measurement.children],
                         ["Ten", "feet", "."])
        self.assertEqual(measurement.children[-1].category, "NOTATION-STOP")
        self.assertFalse(any(n.category in ("V", "VP", "COPULA", "AUX")
                             for n in nodes(root)))

        # Both whole-span directions are additional readings, not replacements.
        self.assertEqual({c.normalized for c in lattice.candidates
                          if c.category == "COMPASS-POINT"}, {"ESE", "E"})
        for span in [(16, 17), (17, 18), (18, 19), (19, 20),
                     (20, 21), (21, 22), (30, 31), (31, 32)]:
            self.assertTrue(lattice.covering(*span), span)
        for candidate in lattice.candidates:
            if candidate.category == "COMPASS-POINT":
                self.assertEqual(candidate.source, "compass-notation")
                self.assertEqual(candidate.provenance["system"], "16_point_compass_rose")
        self.assertTrue(any(c.category == "PROPER-NOUN" and c.span == (0, 8)
                            for c in lattice.candidates))
        self.assertTrue(any(c.category == "NOTATION-PLACE-START" and c.span == (0, 8)
                            for c in lattice.candidates))

    def test_other_place_names_directions_and_units_rank_first(self):
        for text, expected_place, expected_directions, expected_distance in (
            ("Beacon Ridge N.N.E. and by N. Fifteen yards.",
             "Beacon Ridge", ("N.N.E.", "N."), "Fifteen yards."),
            ("Black Point W.S.W. and by W. Twenty paces.",
             "Black Point", ("W.S.W.", "W."), "Twenty paces."),
        ):
            with self.subTest(text=text):
                result = self.parser.parse(
                    text, max_items=50_000, kbest_work_limit=500_000).result
                self.assertTrue(result.completed, result.stats)
                root = result.best()
                self.assertEqual(root.rule_id, NOTATION_ROOT)
                reference, measurement = root.children
                place, bearing = reference.children
                self.assertEqual(result.text[place.start:place.end], expected_place)
                self.assertEqual(
                    (result.text[bearing.children[0].start:bearing.children[0].end],
                     result.text[bearing.children[3].start:bearing.children[3].end]),
                    expected_directions)
                self.assertEqual(result.text[measurement.start:measurement.end],
                                 expected_distance)

    def test_incomplete_or_invalid_notes_do_not_get_the_notation_root(self):
        for text in (
            "Beacon Ridge N.E.W. and by N. Fifteen yards.",  # not a compass point
            "Beacon Ridge N.N.E. and with N. Fifteen yards.",  # not 'by'
            "Beacon Ridge N.N.E. and by N. Fifteen.",  # missing unit noun
            "Beacon Ridge N.N.E. and by N. Fifteen yards,",  # no terminal period
            "Beacon Ridge N.N.E. and by N. Fifteen yards",  # no terminal period
        ):
            with self.subTest(text=text):
                report = self.parser.parse(
                    text, max_items=50_000, kbest_work_limit=500_000)
                self.assertFalse(any(
                    tree.rule_id == NOTATION_ROOT
                    for tree in report.result.alternatives(limit=3)))

    def test_unrelated_initials_are_not_compass_note_records(self):
        text = "Mr. E. Smith was waiting outside."
        report = self.parser.parse(text)
        self.assertFalse(any(
            tree.rule_id == NOTATION_ROOT
            for tree in report.result.alternatives(limit=3)))


if __name__ == "__main__":
    unittest.main()
