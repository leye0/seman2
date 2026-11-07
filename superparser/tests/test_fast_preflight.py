"""Fast preflight must be cheaper than syntax and must never diagnose errors."""
from __future__ import annotations

import unittest

from seman_parser.fast_preflight import fast_preflight, LONG_SENTENCE_TOKENS
from seman_parser.segmentation import LexicalCandidate, LexicalLattice, tokenize
from seman_parser.features import FeatureStructure
from scripts.audit_fast_preflight import audit, _spotcheck_indices


def _lattice(text: str, subject: dict, predicates: list[dict]) -> LexicalLattice:
    tokens = tokenize(text)
    assert len(tokens) == 2
    left, right = tokens
    candidates = [LexicalCandidate(
        left.start, left.end, left.text, "they", "PRONOUN",
        FeatureStructure.build(subject),
    )]
    for pred in predicates:
        candidates.append(LexicalCandidate(
            right.start, right.end, right.text, "say", "V",
            FeatureStructure.build(pred),
        ))
    return LexicalLattice(text, tokens, tuple(candidates))


class FastPreflightTests(unittest.TestCase):
    def test_surface_no_lexicon_no_parse_and_no_error_assertions(self):
        output = fast_preflight("John opened the box.").as_dict()
        self.assertEqual(output["phase"], "surface_only")
        self.assertEqual(output["lane"], "no_early_signal")
        self.assertEqual(output["signals"], [])
        self.assertFalse(output["can_skip_full_parse"])
        self.assertFalse(output["grammatical_fault_established"])
        self.assertFalse(output["failure_cause_established"])
        self.assertEqual(output["analysis_text"], "John opened the box.")

    def test_apostrophe_and_transferred_quotes_are_not_conflated(self):
        self.assertNotIn(
            "dialogue_or_quote_surface",
            fast_preflight("John's book is here.").signals)
        self.assertIn(
            "dialogue_or_quote_surface",
            fast_preflight("‘Hello,’ she said.", transferred_prefix="‘").signals)
        self.assertIn(
            "dialogue_or_quote_surface",
            fast_preflight("They will go.", transferred_prefix="“").signals)
        self.assertNotIn(
            "source_semicolon_continuation",
            fast_preflight("John left; Mary remained.").signals)

    def test_quote_alone_is_metadata_not_reason_to_divert_parser(self):
        q = fast_preflight('"Hello!"')
        self.assertIn("dialogue_or_quote_surface", q.signals)
        self.assertEqual(q.lane, "no_early_signal")
        self.assertFalse(q.as_dict()["can_skip_full_parse"])

    def test_actual_source_dependency_does_not_prove_grammar_ellipsis(self):
        a = fast_preflight("which I accordingly did.")
        b = fast_preflight("which I accordingly did.",
                           preceding_semicolon_part=True)
        self.assertEqual(a.lane, "no_early_signal")
        self.assertEqual(b.lane, "context_review")
        self.assertEqual(b.evidence[0]["proof_scope"],
                         "source_adjacency_only_not_fragment_grammar")
        self.assertFalse(b.as_dict()["grammatical_fault_established"])

    def test_length_flag_is_descriptive_and_is_not_budget_failure(self):
        text = " ".join(["he"] * LONG_SENTENCE_TOKENS)
        event = fast_preflight(text)
        self.assertIn("length_attention", event.signals)
        self.assertEqual(event.lane, "complexity_attention")
        self.assertFalse(event.evidence[0]["runtime_causality_proven"])
        self.assertFalse(event.as_dict()["can_skip_full_parse"])

    def test_local_lexical_agreement_hypothesis_only_if_all_pairs_contradict(self):
        bad = _lattice("They says", {"person": "3", "number": "plural"},
                       [{"vform": "finite", "person": "3", "number": "singular"}])
        pred = fast_preflight(bad.text, lattice=bad)
        self.assertEqual(pred.lane, "candidate_morphology_review")
        evidence = next(x for x in pred.evidence if
                        x["kind"] == "adjacent_candidate_agreement_hypothesis")
        self.assertFalse(evidence["dependency_proven"])
        self.assertFalse(evidence["ambiguity_exhausted"])
        self.assertEqual(evidence["direct_atom_conflicts"], [{
            "feature": "number", "subject": "plural", "predicate": "singular",
        }])
        self.assertFalse(pred.as_dict()["grammatical_fault_established"])

        good = _lattice("They say", {"person": "3", "number": "plural"},
                        [{"vform": "finite", "person": "3", "number": "plural"}])
        self.assertEqual(fast_preflight(good.text, lattice=good).lane,
                         "no_early_signal")
        alternatives = _lattice(
            "You are", {"person": "2", "number": "singular"}, [
                {"vform": "finite", "person": "2", "number": "plural"},
                {"vform": "finite", "person": "2", "number": "singular"},
            ])
        self.assertEqual(fast_preflight(alternatives.text, lattice=alternatives).lane,
                         "no_early_signal")

    def test_plural_nominal_adjacent_to_singular_finite_is_only_hypothesis(self):
        text = "mothers was"
        left, right = tokenize(text)
        lattice = LexicalLattice(text, (left, right), (
            LexicalCandidate(left.start, left.end, left.text, "mother",
                             "N", FeatureStructure.build({"number": "plural"})),
            LexicalCandidate(right.start, right.end, right.text, "be",
                             "COPULA", FeatureStructure.build(
                                 {"vform": "finite", "number": "singular"})),
        ))
        output = fast_preflight(text, lattice=lattice)
        self.assertEqual(output.lane, "candidate_morphology_review")
        self.assertIn("N", output.evidence[0]["nominal_candidate_categories"])
        self.assertFalse(output.evidence[0]["dependency_proven"])
        self.assertFalse(output.as_dict()["grammatical_fault_established"])

    def test_unbound_morphology_and_wrong_lattice_must_abstain(self):
        indeterminate = _lattice(
            "They say", {"person": "3", "number": "plural"},
            [{"vform": "finite", "person": "?p"}])
        self.assertNotIn(
            "adjacent_candidate_agreement_hypothesis",
            fast_preflight(indeterminate.text, lattice=indeterminate).signals)
        with self.assertRaisesRegex(ValueError, "exact analyzed text"):
            fast_preflight("Other text", lattice=indeterminate)

    def test_spotcheck_includes_all_noncompletions_and_uniform_controls(self):
        rows = [{"status": "no_structural_root" if i in (8, 463, 480)
                 else "complete"} for i in range(500)]
        indices = _spotcheck_indices(rows, 25)
        self.assertEqual(len(indices), 28)
        for i in (8, 463, 480):
            self.assertIn(i, indices)
        self.assertEqual(len(indices), len(set(indices)))
        with self.assertRaisesRegex(ValueError, "control_count"):
            _spotcheck_indices(rows, -1)

    def test_audit_joins_only_consistent_500_rows_without_reparsing(self):
        diagnostics, contexts = [], []
        for i in range(500):
            status = "no_structural_root" if i in (8, 94) else "complete"
            sentence = "which I accordingly did." if i == 8 else "John left."
            diagnostics.append({
                "index": i, "book_id": 766, "ordinal": i,
                "case_id": f"test:{i}", "source_text": sentence,
                "canonical_analysis_text": sentence,
                "canonical_synthetic_prefix": "",
                "canonical_synthetic_suffix": "",
                "status": status, "wall_ms": 3.2,
            })
            contexts.append({
                "index": i, "book_id": 766, "ordinal": i,
                "source_text": sentence, "status": status,
                "context": {"semicolon_part_index": 1 if i == 8 else 0},
            })
        rows, result = audit(diagnostics, contexts, repetitions=1)
        self.assertEqual(result["canonical_complete"], 498)
        self.assertEqual(result["canonical_noncomplete"], 2)
        self.assertEqual(result["review_lane_noncomplete"], 1)
        self.assertEqual(result["noncomplete_without_early_signal"], [94])
        self.assertEqual(rows[8]["preflight"]["lane"], "context_review")
        self.assertTrue(result["no_parse_skipping_or_strategy_changes"])
        self.assertTrue(result["noncompletion_is_not_an_anomaly_label"])
        contexts[10]["source_text"] = "tampered"
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            audit(diagnostics, contexts, repetitions=1)


if __name__ == "__main__":
    unittest.main()
