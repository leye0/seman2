"""Proven local roles only when real syntax occurrence handles resolved."""
from __future__ import annotations

from types import SimpleNamespace as Obj
import unittest

from seman_parser.local_role_proofs import resolved_local_subject_predicate_pairs


def item(*, links, children=None):
    if children is None:
        children = (Obj(start=0, end=4, category="NP"),
                    Obj(start=5, end=16, category="VP"))
    return Obj(rule_id="clause_np_vp", category="CLAUSE", start=0, end=16,
               children=children, syntax=Obj(links=tuple(links)))


class LocalResolvedRoleTests(unittest.TestCase):
    def test_pair_requires_both_resolved_occurrence_anchors_same_rule(self):
        analysis = item(links=[
            Obj(relation="subject", target="lex:0:4:PROPER-NOUN:John", child_index=0),
            Obj(relation="event", target="lex:5:11:V:opened", child_index=1),
        ])
        pairs = resolved_local_subject_predicate_pairs(analysis)
        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual(pair["subject"]["head_analysis_span"], [0, 4])
        self.assertEqual(pair["predicate"]["head_analysis_span"], [5, 11])
        self.assertEqual(pair["subject"]["child_analysis_span"], [0, 4])
        self.assertTrue(pair["same_accepted_local_composition"])
        self.assertFalse(pair["whole_sentence_relation_proven"])
        self.assertFalse(pair["grammatical_conflict_proven"])

    def test_unresolved_declaration_or_missing_subject_is_not_a_link(self):
        self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[])), [])
        self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="event", target="lex:5:11:V:opened", child_index=1),
        ])), [])
        self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="subject", target="unknown", child_index=0),
            Obj(relation="event", target="lex:5:11:V:opened", child_index=1),
        ])), [])

    def test_resolved_non_nominal_anchor_cannot_prove_subject_head(self):
        # Real 500-cohort counterexamples: 480 exported an opening quote
        # as the NP referent; 115 exported a copula from a local NP.
        for category in ("OPEN-QUOTE", "COPULA"):
            with self.subTest(category=category):
                self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[
                    Obj(relation="subject", target=f"lex:0:4:{category}:wrong",
                        child_index=0),
                    Obj(relation="event", target="lex:5:11:V:opened", child_index=1),
                ])), [])
        self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="subject", target="lex:0:4:N:John", child_index=0),
            Obj(relation="event", target="lex:5:11:COMMA:comma", child_index=1),
        ])), [])

    def test_rejects_spans_outside_exporting_child_or_same_child(self):
        self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="subject", target="lex:0:8:N:wrong", child_index=0),
            Obj(relation="event", target="lex:5:11:V:opened", child_index=1),
        ])), [])
        self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="subject", target="lex:0:4:N:John", child_index=0),
            Obj(relation="event", target="lex:0:4:N:John", child_index=0),
        ])), [])
        self.assertEqual(resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="subject", target="lex:0:4:N:John", child_index=0),
            Obj(relation="event", target="lex:5:11:V:opened", child_index=2),
        ])), [])

    def test_explicit_predicate_role_precedes_auxiliary_event(self):
        analysis = item(links=[
            Obj(relation="subject", target="lex:0:4:N:John", child_index=0),
            Obj(relation="event", target="lex:5:11:V:opened", child_index=1),
            Obj(relation="predicate", target="lex:5:11:V:opened", child_index=1),
        ])
        pairs = resolved_local_subject_predicate_pairs(analysis)
        self.assertEqual([x["predicate"]["role"] for x in pairs],
                         ["predicate"])


if __name__ == "__main__":
    unittest.main()
