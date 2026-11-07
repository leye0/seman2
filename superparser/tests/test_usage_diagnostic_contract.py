"""P0: local, opt-in grammatical evidence is separate from parsing success.

These miniature trees test the diagnostic contract independently of WordNet
and of any particular novel.  End-to-end case 480 is checked separately.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from seman_parser.chart import ChartItem, ParseResult, Provenance
from seman_parser.features import FeatureStructure
from seman_parser.nonstandard import collect_usage_deviations


@dataclass
class _Lattice:
    text: str

    def as_dict(self):
        return {"text": self.text}


def leaf(start, end, category, number):
    return ChartItem(
        start=start, end=end, category=category,
        features=FeatureStructure.build({"number": number}),
        semantic=None, score=0.0, provenance=Provenance("lexicon"),
    )


def reporting_tag(start, end, subject, predicate, *, inverted=False, **template_changes):
    subject_index, predicate_index = (1, 0) if inverted else (0, 1)
    template = {
        "kind": "subject_verb_number_agreement",
        "relation": "speaker_to_reporting_verb",
        "subject_child": subject_index,
        "predicate_child": predicate_index,
        "feature": "number",
        "expected": "plural",
        "observed": "singular",
        "register": "literary_dialogue",
    }
    template.update(template_changes)
    children = (predicate, subject) if inverted else (subject, predicate)
    return ChartItem(
        start=start, end=end, category="SPEECH-TAG",
        features=FeatureStructure.empty(), semantic=None, score=1.0,
        provenance=Provenance("rule", {"usage_deviation": template}),
        children=children, rule_id="marked_tag_inverted" if inverted else "marked_tag",
    )


def result(text, root, *, completed=True, stats=None, other_roots=()):
    return ParseResult(
        text=text, lattice=_Lattice(text), packed={},
        roots=(root, *other_roots), completed=completed, stats=stats or {},
    )


class UsageDiagnosticContractTests(unittest.TestCase):
    def setUp(self):
        self.text = '"says they, they says"'
        first = reporting_tag(
            1, 10, leaf(6, 10, "NP", "plural"), leaf(1, 5, "V", "singular"),
            inverted=True,
        )
        second = reporting_tag(
            12, 21, leaf(12, 16, "NP", "plural"), leaf(17, 21, "V", "singular"),
        )
        self.root = ChartItem(
            start=0, end=22, category="CLAUSE",
            features=FeatureStructure.empty(), semantic=None, score=1.0,
            provenance=Provenance("rule"), children=(first, second),
            rule_id="two_reporting_tags",
        )

    def test_two_independent_conflicts_have_exact_tree_paths_and_source_mapping(self):
        parsed = result(self.text, self.root)
        summary = parsed.as_dict(reference_span=lambda a, b:
                                 (a - 1, b - 1) if 1 <= a < b <= 21 else None)
        self.assertEqual(summary["parse_status"], "complete")
        self.assertEqual(summary["grammatical_status"], "nonstandard_attested")
        self.assertEqual(summary["diagnostic_scope"], "selected_complete_tree")
        self.assertEqual(summary["search_limitations"], [])
        self.assertEqual(len(summary["usage_deviations"]), 2)
        one, two = summary["usage_deviations"]
        self.assertEqual(one["evidence"]["parent"]["path"], [0])
        self.assertEqual(one["evidence"]["subject"]["path"], [0, 1])
        self.assertEqual(one["evidence"]["predicate"]["path"], [0, 0])
        self.assertEqual(two["evidence"]["parent"]["path"], [1])
        self.assertEqual(two["evidence"]["subject"]["path"], [1, 0])
        self.assertEqual(two["evidence"]["predicate"]["path"], [1, 1])
        self.assertEqual(one["subject"]["reference_span"], [5, 9])
        self.assertEqual(one["predicate"]["reference_span"], [0, 4])
        self.assertEqual(two["subject"]["reference_span"], [11, 15])
        self.assertEqual(two["predicate"]["reference_span"], [16, 20])
        self.assertEqual(one["parent_reference_mapping"], "exact")
        self.assertEqual(one["intent"], "unknown")
        self.assertEqual(one["evidence"]["type"], "explicit_marked_grammar_rule")
        self.assertEqual(one["constraint"], "subject.number == predicate.number")

    def test_unmapped_offsets_do_not_pretend_to_be_source_positions(self):
        entry = result(self.text, self.root).as_dict()["usage_deviations"][0]
        self.assertIsNone(entry["subject"]["reference_span"])
        self.assertEqual(entry["subject"]["reference_mapping"], "not_provided")
        mapped = result(self.text, self.root).as_dict(
            reference_span=lambda a, b: None)["usage_deviations"][0]
        self.assertIsNone(mapped["subject"]["reference_span"])
        self.assertEqual(mapped["subject"]["reference_mapping"], "unavailable")

    def test_duplicate_evidence_is_collapsed_without_merging_distinct_occurrences(self):
        repeated = ChartItem(
            start=0, end=22, category="CLAUSE",
            features=FeatureStructure.empty(), semantic=None, score=0.0,
            provenance=Provenance("rule"),
            children=(self.root.children[0], self.root.children[0]),
            rule_id="shared_subtree",
        )
        self.assertEqual(len(collect_usage_deviations(repeated, self.text)), 1)
        self.assertEqual(len(collect_usage_deviations(self.root, self.text)), 2)

    def test_incomplete_parse_does_not_report_a_grammatical_fault(self):
        parsed = result(
            self.text, self.root, completed=False,
            stats={"budget_exceeded": True, "kbest_budget_exceeded": True,
                   "dialogue_attempt": {"budget_exceeded": True}},
        )
        self.assertEqual(parsed.usage_deviations(), ())
        reported = parsed.as_dict()
        self.assertFalse(reported["completed"])
        self.assertEqual(reported["parse_status"], "incomplete")
        self.assertEqual(reported["grammatical_status"], "inconclusive")
        self.assertIsNone(reported["best"])
        self.assertEqual(reported["usage_deviations"], [])
        self.assertEqual(reported["diagnostic_scope"], "none")
        self.assertCountEqual(reported["search_limitations"], (
            "recognition_budget_exceeded", "kbest_budget_exceeded",
            "dialogue_recognition_budget_exceeded", "no_certified_complete_analysis",
        ))

    def test_unmarked_alternative_makes_sentence_level_certainty_unwarranted(self):
        unmarked = ChartItem(
            start=0, end=22, category="CLAUSE",
            features=FeatureStructure.empty(), semantic=None, score=-1.0,
            provenance=Provenance("rule"), rule_id="alternative",
        )
        parsed = result(self.text, self.root, other_roots=(unmarked,))
        diagnostic = parsed.as_dict()
        self.assertEqual(diagnostic["grammatical_status"], "nonstandard_attested")
        self.assertEqual(diagnostic["diagnostic_scope"], "selected_complete_tree")
        self.assertEqual(diagnostic["ambiguity"], {
            "examined_complete_trees": 2, "unmarked_trees": 1,
            "marked_trees": 1, "exhaustive": False,
        })

    def test_rule_must_prove_both_sides_and_cannot_infer_author_intent(self):
        first = self.root.children[0]
        with self.assertRaisesRegex(ValueError, "contradicts"):
            collect_usage_deviations(reporting_tag(
                1, 10, leaf(6, 10, "NP", "singular"),
                leaf(1, 5, "V", "singular"), inverted=True,
            ), self.text)
        with self.assertRaisesRegex(ValueError, "distinct"):
            collect_usage_deviations(reporting_tag(
                1, 10, first.children[1], first.children[0],
                inverted=True, subject_child=0, predicate_child=0,
            ), self.text)
        with self.assertRaisesRegex(ValueError, "annotation provenance"):
            collect_usage_deviations(reporting_tag(
                1, 10, first.children[1], first.children[0],
                inverted=True, intent="deliberate",
            ), self.text)
        with self.assertRaisesRegex(ValueError, "outside"):
            collect_usage_deviations(reporting_tag(
                1, 8, first.children[1], first.children[0], inverted=True,
            ), self.text)


if __name__ == "__main__":
    unittest.main()
