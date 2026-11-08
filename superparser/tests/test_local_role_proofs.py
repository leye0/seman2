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
        self.assertEqual(pair["subject"]["head_lemma"], "John")
        self.assertEqual(pair["predicate"]["head_lemma"], "opened")
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

    def test_child_features_are_observed_without_asserting_agreement(self):
        children = (
            Obj(start=0, end=4, category="NP", features=Obj(as_dict=lambda: {
                "number": "plural", "person": "3", "vform": ["finite", "base"],
            })),
            Obj(start=5, end=16, category="VP", features=Obj(as_dict=lambda: {
                "number": "singular", "person": "?unbound", "vform": "finite",
            })),
        )
        pair = resolved_local_subject_predicate_pairs(item(children=children, links=[
            Obj(relation="subject", target="lex:0:4:PRONOUN:they", child_index=0),
            Obj(relation="event", target="lex:5:11:V:says", child_index=1),
        ]))[0]
        self.assertEqual(pair["materialized_child_feature_atoms"], {
            "subject": {"number": "plural", "person": "3"},
            "predicate": {"number": "singular", "vform": "finite"},
        })
        self.assertEqual(pair["cross_child_grounded_atom_comparisons"], [{
            "feature": "number", "subject_atom": "plural",
            "predicate_atom": "singular", "same_atom": False,
        }])
        self.assertFalse(pair["grammatical_agreement_requirement_proven"])
        self.assertFalse(pair["grammatical_conflict_proven"])

    def test_selected_lexical_leaf_preserves_pre_unification_person(self):
        def features(**values):
            return Obj(as_dict=lambda: values)

        original_i = Obj(span_start=0, span_end=1, category="PRONOUN",
                         lemma="I", source="lexicon", features=features(
                             number="singular", person="1"))
        original_was = Obj(span_start=2, span_end=5, category="V",
                           lemma="be", source="wordnet", features=features(
                               number="singular", person="3", vform="finite"))
        children = (
            Obj(start=0, end=1, category="NP", features=features(
                number="singular", person="3"), children=(
                    Obj(lexical_candidate=original_i, children=()),)),
            Obj(start=2, end=5, category="VP", features=features(
                number="singular", person="3"), children=(
                    Obj(lexical_candidate=original_was, children=()),)),
        )
        analysis = Obj(rule_id="clause_np_vp", category="CLAUSE",
                       start=0, end=5, children=children, syntax=Obj(links=(
                           Obj(relation="subject", target="lex:0:1:PRONOUN:I", child_index=0),
                           Obj(relation="event", target="lex:2:5:V:be", child_index=1),
                       )))
        pair = resolved_local_subject_predicate_pairs(analysis)[0]
        lexical = pair["selected_lexical_head_feature_observations"]
        self.assertEqual(lexical["subject"]["candidate_feature_atoms"]["person"], "1")
        self.assertEqual(lexical["predicate"]["candidate_feature_atoms"]["person"], "3")
        self.assertEqual(pair["cross_lexical_candidate_atom_comparisons"], [
            {"feature": "number", "subject_lexical_candidate_atom": "singular",
             "predicate_lexical_candidate_atom": "singular", "same_atom": True},
            {"feature": "person", "subject_lexical_candidate_atom": "1",
             "predicate_lexical_candidate_atom": "3", "same_atom": False},
        ])
        self.assertIn({
            "role": "subject", "feature": "person", "lexical_candidate_atom": "1",
            "materialized_child_atom": "3", "same_atom": False,
        }, pair["lexical_candidate_vs_child_atom_comparisons"])
        # Even this discrepancy is about a selected lexical hypothesis,
        # not a proof that the source sentence is ill-formed.
        self.assertFalse(pair["grammatical_conflict_proven"])

    def test_unmatched_or_nonunique_selected_head_cannot_supply_atoms(self):
        def features(**values):
            return Obj(as_dict=lambda: values)

        candidate = Obj(span_start=0, span_end=4, category="PRONOUN",
                        lemma="they", source="lexicon",
                        features=features(number="plural"))
        leaves = (Obj(lexical_candidate=candidate, children=()),
                  Obj(lexical_candidate=candidate, children=()))
        subject = Obj(start=0, end=4, category="NP", children=leaves)
        predicate = Obj(start=5, end=9, category="VP", children=())
        pair = resolved_local_subject_predicate_pairs(item(children=(subject, predicate),
            links=[
                Obj(relation="subject", target="lex:0:4:PRONOUN:they", child_index=0),
                Obj(relation="event", target="lex:5:9:V:say", child_index=1),
            ]))[0]
        self.assertEqual(pair["selected_lexical_head_feature_observations"][
            "subject"]["status"], "not_uniquely_observed")
        self.assertEqual(pair["selected_lexical_head_feature_observations"][
            "subject"]["matching_selected_leaf_count"], 2)
        self.assertEqual(pair["cross_lexical_candidate_atom_comparisons"], [])

    def test_direct_rhs_agreement_proven_from_same_compiled_rule(self):
        def features(**data):
            return Obj(as_dict=lambda: data)

        rule = Obj(rule_id="clause_np_vp", rhs=(
            Obj(category="NP", features=features(number="?n", person="?p")),
            Obj(category="VP", features=features(number="?n", person="?p")),
        ))
        pair = resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="subject", target="lex:0:4:PRONOUN:they", child_index=0),
            Obj(relation="event", target="lex:5:11:V:says", child_index=1),
        ]), compiled_rule=rule)[0]
        contract = pair["local_rule_rhs_feature_constraints"]
        self.assertEqual(contract["explicit_shared_rhs_variable_equalities"], [
            {"feature": "number", "shared_rhs_variable": "?n",
             "basis": "same_unification_variable_on_both_rhs_children"},
            {"feature": "person", "shared_rhs_variable": "?p",
             "basis": "same_unification_variable_on_both_rhs_children"},
        ])
        self.assertFalse(contract["whole_sentence_agreement_proven"])
        self.assertFalse(pair["grammatical_conflict_proven"])

        # A rule that does not share variables is not silently credited
        # with an agreement obligation, even if its accepted children match.
        rule.rhs = (
            Obj(category="NP", features=features(number="?subject_n")),
            Obj(category="VP", features=features(number="?verb_n")),
        )
        no_direct = resolved_local_subject_predicate_pairs(item(links=[
            Obj(relation="subject", target="lex:0:4:PRONOUN:they", child_index=0),
            Obj(relation="event", target="lex:5:11:V:says", child_index=1),
        ]), compiled_rule=rule)[0]
        self.assertEqual(no_direct["local_rule_rhs_feature_constraints"][
            "explicit_shared_rhs_variable_equalities"], [])

    def test_different_compiled_rule_identity_or_rhs_fails_closed(self):
        analysis = item(links=[
            Obj(relation="subject", target="lex:0:4:N:John", child_index=0),
            Obj(relation="event", target="lex:5:11:V:opened", child_index=1),
        ])
        with self.assertRaisesRegex(ValueError, "identity"):
            resolved_local_subject_predicate_pairs(analysis,
                compiled_rule=Obj(rule_id="not_this_rule", rhs=[]))
        with self.assertRaisesRegex(ValueError, "compiled rule RHS"):
            resolved_local_subject_predicate_pairs(analysis,
                compiled_rule=Obj(rule_id="clause_np_vp", rhs=[Obj(category="CLAUSE")]))


if __name__ == "__main__":
    unittest.main()
