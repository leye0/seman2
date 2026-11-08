"""Independent joining and evidence-boundary tests; no WordNet required."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.synthesize_residual_evidence import synthesize, render, main

HISTORICAL = (8, 64, 94, 96, 105, 109, 115, 116, 167, 182, 194, 220,
              226, 233, 235, 243, 248, 312, 344, 347, 463, 466, 480,
              487, 491, 497)
UNRESOLVED = {8: "no_structural_root", 312: "timeout",
              463: "roots_without_valid_analysis",
              480: "roots_without_valid_analysis"}


def trace(*, exact=True):
    result = {
        "exhaustive": False, "grammatical_fault_established": False,
        "observed_events": 100, "sampled_events": 2, "truncated": True,
        "events": [
            {"stage": "unify_rule", "rule_id": "UNRELATED", "category": "NP",
             "analysis_span": [1, 5], "reference_span": [30, 34],
             "reference_span_mapping": "exact" if exact else "unavailable",
             "direct_atom_conflicts": [{"expected": "plural", "actual": "singular"}]},
            {"stage": "positive_evidence_require", "rule_id": "PROOF", "category": "VP",
             "analysis_span": [0, 5], "reference_span": [0, 5],
             "reference_span_mapping": "exact"},
        ],
        "validated_local_constituents": {
            "schema": "seman2-local-constituent-proof-sample-v1",
            "observed_materialized_rule_analyses": 4,
            "sampled_local_constituents": 1,
            "truncated": True,
            "exhaustive": False, "global_tree_proven": False,
            "sentence_grammatical_fault_established": False,
            "witnesses": [{
                "proof_basis": "materialized_rule_after_context_unification",
                "rule_id": "vp_finite", "category": "VP", "analysis_span": [1, 5],
                "reference_span_mapping": "exact" if exact else "unavailable",
                "reference_span": [30, 34] if exact else None,
                "verified_features": {"number": "plural"},
                "required_context_features": {"vform": "finite"},
                "required_positive_features": ["number"],
                "witnessed_positive_features": ["number", "vform"],
                "children": [{"category": "V", "rule_id": None,
                              "analysis_span": [2, 4],
                              "reference_span_mapping": "unavailable",
                              "reference_span": None}],
                "global_tree_selected": False,
                "whole_sentence_grammaticality_proven": False,
            }],
        },
    }
    result["independent_local_probe"] = {
        **deepcopy(result["validated_local_constituents"]),
        "probe_kind": "independent_unconstrained_local_subtree_search",
        "selected_structural_nodes": 7,
        "attempted_structural_nodes": 4,
        "accepted_requested_nodes": 2,
        "separate_work_units": 85,
        "separate_work_limit": 12000,
        "probe_budget_exceeded": False,
        "not_exhaustive_or_a_global_failure_proof": True,
        "canonical_work_budget_unchanged": True,
    }
    def framed(span, mapped):
        return {"analysis_span": span,
                "reference_span_mapping": "exact" if exact else "unavailable",
                "reference_span": mapped if exact else None}
    result["independent_local_probe"]["witnesses"] = [{
        **deepcopy(result["validated_local_constituents"]["witnesses"][0]),
        "rule_id": "clause_np_vp", "category": "CLAUSE",
        **framed([1, 10], [30, 39]),
        "children": [
            {"category": "NP", "rule_id": "np_pronoun", **framed([1, 5], [30, 34])},
            {"category": "VP", "rule_id": "vp_finite", **framed([6, 10], [35, 39])},
        ],
    }]
    result["independent_local_probe"]["validated_local_role_pairs"] = {
        "schema": "seman2-local-resolved-role-pairs-v1",
        "proof_basis": "accepted_local_rule_with_resolved_syntax_links",
        "sample_limit": 48, "observed_pairs": 1, "sampled_pairs": 1,
        "truncated": False, "bounded_post_materialization_of_retained_proofs": True,
        "exhaustive": False, "global_tree_proven": False,
        "grammatical_conflict_proven": False,
        "pairs": [{
            "proof_basis": "accepted_local_rule_with_resolved_syntax_links",
            "rule_id": "clause_np_vp", "category": "CLAUSE",
            **framed([1, 10], [30, 39]),
            "subject": {
                "role": "subject", "child_index": 0, "child_category": "NP",
                "child_analysis_span": [1, 5],
                "child_reference_span_mapping": "exact" if exact else "unavailable",
                "child_reference_span": [30, 34] if exact else None,
                "head_analysis_span": [1, 4], "head_lexical_category": "PRONOUN",
                "head_reference_span_mapping": "exact" if exact else "unavailable",
                "head_reference_span": [30, 33] if exact else None,
            },
            "predicate": {
                "role": "event", "child_index": 1, "child_category": "VP",
                "child_analysis_span": [6, 10],
                "child_reference_span_mapping": "exact" if exact else "unavailable",
                "child_reference_span": [35, 39] if exact else None,
                "head_analysis_span": [6, 9], "head_lexical_category": "V",
                "head_reference_span_mapping": "exact" if exact else "unavailable",
                "head_reference_span": [35, 38] if exact else None,
            },
            "same_accepted_local_composition": True,
            "global_tree_proven": False, "whole_sentence_relation_proven": False,
            "grammatical_conflict_proven": False,
        }],
    }
    return result


def fixture():
    register = []
    for i in HISTORICAL:
        status = UNRESOLVED.get(i, "complete")
        register.append({
            "index": i, "case_id": f"case:{i}", "book_id": 766,
            "source_text": f"Source {i}",
            "analysis_text": f"Balanced {i}", "original_26_member": True,
            "current_status": status,
            "current_outcome": "complete" if status == "complete" else
            "resource_censored" if status == "timeout" else "structural_unresolved",
            "trajectory": "recovered" if status == "complete" else "unresolved",
            "research_tracks": ["notation_or_genre"] if i == 167 else ["finite_syntax"],
            "hypothesis": "Check overt finite structure" if i == 115 else "Provisional review",
            "hypothesis_assessment": "provisional_hypothesis",
            "test_reference": None,
            "observed_evidence": {
                "lexical_diagnostic": None if i == 312 else {
                    "words_without_any_candidate": [], "candidate_count": 2},
                "dialogue_attempt": {"structural_root_nodes": 3} if i == 463 else None,
                "source_context": {"semicolon_part_index": 1 if i == 8 else 0,
                                   "preceding_semicolon_part": "Earlier;" if i == 8 else None,
                                   "full_unsplit_sentence": f"Source {i}"},
            },
        })
    statuses = {i: UNRESOLVED.get(i, "complete") for i in range(500)}
    preflight = [{
        "index": i, "case_id": f"case:{i}", "canonical_status": statuses[i],
        "source_text": f"Source {i}",
        "preflight": {"lane": "review" if i == 8 else "no_early_signal",
                      "signals": ["source_semicolon_continuation"] if i == 8 else []},
    } for i in range(500)]
    lexical = [{
        "index": i, "case_id": f"case:{i}", "canonical_status": statuses[i],
        "analysis_text": f"Balanced {i}",
        "lexical_candidates": 2, "candidate_agreement_hypothesis": i == 463,
    } for i in (*UNRESOLVED, 76, 244)]
    dialogue = [{
        "index": 463, "case_id": "case:463", "canonical_status": statuses[463],
        "analysis_text": "Balanced 463", "source_text": "Source 463",
        "canonical_dialogue_root_nodes": 3, "replay_outcome": "roots_without_valid_analysis",
        "independent_replay": True,
        "scoped_dialogue": {"rejection_trace": trace(exact=False)},
        "ordinary_fallback": {"rejection_trace": None},
    }]
    comparisons = [{
        "index": i, "kind": "marked_opt_in" if i in (463, 480)
        else "successful_strict_control",
        "case_id": f"case:{i}", "canonical_status": statuses[i],
        "analysis_text": f"Balanced {i}", "source_text": f"Source {i}",
        "replay_outcome": "complete", "selected_rule": "CLAUSE",
        "selected_usage_deviation_count": 2 if i == 480 else 1,
        "traces": {"selected_or_fallback": trace()} if i == 480 else {},
    } for i in (76, 244, 463, 480)]
    return (register,
            {"cohort_sha256": "frozen", "cohort_size": 500, "original_residuals": 26},
            preflight, lexical, dialogue,
            {"cohort_sha256": "frozen", "cases": 1, "target_indices": [463]},
            comparisons)


class ResidualEvidenceSynthesisTests(unittest.TestCase):
    def test_all_26_retained_with_independent_evidence_and_no_fault_inference(self):
        rows, summary = synthesize(*fixture())
        self.assertEqual(len(rows), 26)
        self.assertEqual(summary["original_26_retained"], 26)
        self.assertEqual(summary["current_unresolved"], 4)
        self.assertEqual(summary["marked_opt_in_comparisons"], 2)
        self.assertEqual(summary["scoped_dialogue_replays"], 1)
        self.assertEqual(summary["independent_local_probe_witnesses_sampled"], 2)
        self.assertEqual(summary["incomplete_replays_with_independent_local_proofs"], 1)
        self.assertEqual(summary["resolved_local_subject_predicate_pairs_sampled"], 2)
        self.assertEqual(summary["distinct_resolved_local_role_pairs_by_case"], 2)
        self.assertEqual(summary["local_role_pairs_with_child_feature_observation_sampled"], 0)
        self.assertEqual(
            summary["cases_with_multiple_local_subject_candidates_for_shared_predicate"], 0)
        self.assertTrue(summary["source_identity_validated"])
        by_index = {r["index"]: r for r in rows}
        self.assertEqual(by_index[312]["canonical_outcome"], "resource_censored")
        self.assertIsNone(by_index[312]["canonical_lexical_diagnostic"])
        self.assertEqual(by_index[480]["canonical_status"],
                         "roots_without_valid_analysis")
        self.assertEqual(by_index[480]["marked_comparator"]["selected_deviation_count"], 2)
        self.assertIn("compare_source_continuation_with_independent_finite_clauses",
                      by_index[8]["suggested_checks_not_diagnoses"])
        self.assertIn("inspect_constituents_valence_and_selected_attachments",
                      by_index[8]["suggested_checks_not_diagnoses"])
        self.assertEqual(by_index[115]["research_hypothesis"],
                         "Check overt finite structure")
        self.assertIn("inspect_register_or_notation_without_forcing_a_finite_clause",
                      by_index[167]["suggested_checks_not_diagnoses"])
        self.assertTrue(all(not r["grammatical_fault_established"] and
                            not r["unique_failure_cause_established"] and
                            not r["exhaustive"] for r in rows))
        self.assertIn("source", render(rows, summary).lower())

    def test_local_rejections_remain_attempts_and_exact_source_mapping_is_guarded(self):
        rows, _ = synthesize(*fixture())
        scoped = next(r for r in rows if r["index"] == 463)[
            "sampled_local_rejection_evidence"]["scoped_dialogue"]
        self.assertEqual(scoped["sampled_events"], 2)
        self.assertEqual(scoped["observed_events"], 100)
        self.assertEqual(scoped["local_atom_conflicts_in_retained_sample"], 1)
        self.assertEqual(scoped["examples"][0]["rule_id"], "PROOF")
        self.assertIsNone(scoped["examples"][1]["reference_span"])
        local = scoped["validated_local_constituents"]
        self.assertEqual(local["sampled_local_constituents"], 1)
        self.assertEqual(local["witnesses"][0]["rule_id"], "vp_finite")
        self.assertIsNone(local["witnesses"][0]["source_span"])
        self.assertFalse(local["sentence_grammatical_fault_established"])
        self.assertFalse(scoped["sentence_fault_proven"])
        self.assertFalse(scoped["failure_cause_proven"])
        independent = scoped["independent_local_probe"]
        self.assertEqual(independent["accepted_requested_nodes"], 2)
        self.assertEqual(independent["sampled_local_constituents"], 1)
        self.assertTrue(independent["canonical_work_budget_unchanged"])
        self.assertEqual(independent["resolved_local_role_pairs"]["sampled_pairs"], 1)
        self.assertIsNone(independent["resolved_local_role_pairs"]["pairs"][0]
                          ["subject"]["head_source_span"])
        self.assertIn("Independent failed-root local probes", render(*synthesize(*fixture())))

    def test_new_failure_remains_unreviewed_and_joined(self):
        args = fixture()
        args[0].append({**deepcopy(args[0][0]), "index": 42, "case_id": "case:42",
                        "source_text": "Source 42", "analysis_text": "Balanced 42",
                        "original_26_member": False, "trajectory": "new_unreviewed_failure"})
        args[2][42]["canonical_status"] = "no_structural_root"
        args[3].append({"index": 42, "case_id": "case:42",
                        "canonical_status": "no_structural_root",
                        "analysis_text": "Balanced 42",
                        "lexical_candidates": 1, "candidate_agreement_hypothesis": False})
        rows, summary = synthesize(*args)
        self.assertEqual(len(rows), 27)
        self.assertEqual(summary["new_unreviewed_failures"], 1)

    def test_unscoped_structural_replays_join_only_eligible_cases(self):
        args = fixture()
        eligible = (8, 480)  # Other fixture residuals: timeout or scoped dialogue.
        extra = [{
            "index": i, "case_id": f"case:{i}",
            "canonical_status": UNRESOLVED[i],
            "source_text": f"Source {i}", "analysis_text": f"Balanced {i}",
            "independent_replay": True, "same_canonical_budgets": True,
            "grammatical_fault_established": False,
            "replay_outcome": "no_structural_root",
            "rejection_trace": trace(exact=True),
        } for i in eligible]
        extra_summary = {"cohort_sha256": "frozen", "cases": len(extra),
                         "target_indices": list(eligible)}
        rows, summary = synthesize(*args, extra, extra_summary)
        self.assertEqual(summary["unscoped_structural_replays"], 2)
        self.assertEqual(summary["independent_local_probe_witnesses_sampled"], 4)
        self.assertEqual(summary["incomplete_replays_with_independent_local_proofs"], 3)
        # #480's marked and unscoped reports refer to the *same* source
        # heads and rule, so they cannot count as two distinct links.
        self.assertEqual(summary["distinct_resolved_local_role_pairs_by_case"], 3)
        r8 = next(r for r in rows if r["index"] == 8)
        self.assertEqual(r8["sampled_local_rejection_evidence"]
                         ["unscoped_replay"]["independent_local_probe"]
                         ["witnesses"][0]["source_span"], [30, 39])
        self.assertEqual(r8["sampled_local_rejection_evidence"]
                         ["unscoped_replay"]["independent_local_probe"]
                         ["resolved_local_role_pairs"]["pairs"][0]
                         ["subject"]["head_source_span"], [30, 33])
        self.assertEqual(r8["canonical_status"], "no_structural_root")
        with self.assertRaisesRegex(ValueError, "Unscoped replay identity"):
            synthesize(*args, extra[:1], extra_summary)

    def test_shared_source_predicate_multiple_local_subjects_are_not_faults(self):
        args = fixture()
        first = trace(exact=True)
        second = trace(exact=True)
        second_role = second["independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
        second_role["subject"]["head_analysis_span"] = [2, 4]
        second_role["subject"]["head_reference_span"] = [31, 33]
        args[4][0]["scoped_dialogue"]["rejection_trace"] = first
        args[4][0]["ordinary_fallback"]["rejection_trace"] = second
        rows, summary = synthesize(*args)
        self.assertEqual(summary["resolved_local_subject_predicate_pairs_sampled"], 3)
        self.assertEqual(summary["distinct_resolved_local_role_pairs_by_case"], 3)
        self.assertEqual(
            summary["cases_with_multiple_local_subject_candidates_for_shared_predicate"], 1)
        self.assertEqual(summary["shared_predicate_heads_with_multiple_local_subject_candidates"], 1)
        item = next(r for r in rows if r["index"] == 463)
        alternatives = item["shared_predicate_local_subject_candidates"]
        self.assertEqual(alternatives[0]["predicate_head_source_span"], [35, 38])
        self.assertEqual([head["source_span"] for head in alternatives[0]["candidate_subject_heads"]],
                         [[30, 33], [31, 33]])
        self.assertFalse(alternatives[0]["whole_sentence_ambiguity_proven"])
        self.assertFalse(alternatives[0]["grammatical_conflict_proven"])
        self.assertFalse(item["grammatical_fault_established"])
        self.assertIn("Distinct local subject candidates", render(rows, summary))

    def test_exact_role_source_must_match_its_accepted_local_constituent(self):
        for change in (
            lambda role: role["subject"].update(head_reference_span=[29, 32]),
            lambda role: role["subject"].update(child_reference_span=[29, 33]),
            lambda role: role.update(reference_span=[31, 40]),
        ):
            with self.subTest(change=change):
                args = fixture()
                local = trace(exact=True)
                role = local["independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
                change(role)
                args[4][0]["scoped_dialogue"]["rejection_trace"] = local
                with self.assertRaisesRegex(ValueError, "no matching validated local subtree"):
                    synthesize(*args)

    def test_lattice_head_evidence_is_not_contextual_or_grammatical_proof(self):
        args = fixture()
        local = args[4][0]["scoped_dialogue"]["rejection_trace"]
        pair = local["independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
        for name, surface in (("subject", "ala"), ("predicate", "ed ")):
            role = pair[name]
            role["head_lemma"] = name
            role["lexical_lattice_evidence"] = {
                "schema": "seman2-local-head-lattice-audit-v1",
                "basis": "same_public_parse_original_lexical_lattice",
                "head_analysis_span": role["head_analysis_span"],
                "head_lexical_category": role["head_lexical_category"],
                "head_lemma": name,
                "head_analysis_surface": surface,
                "matching_head_candidate_count": 1,
                "matching_candidate_sources": ["lexicon"],
                "all_same_span_candidate_categories": [role["head_lexical_category"]],
                "alternate_same_span_categories": [],
                "head_lexical_candidate_present": True,
                "contextual_plausibility_proven": False,
                "grammatical_conflict_proven": False,
            }
        pair["subject"]["lexical_lattice_evidence"]["all_same_span_candidate_categories"] = [
            "PREP", "PRONOUN"]
        pair["subject"]["lexical_lattice_evidence"]["alternate_same_span_categories"] = [
            "PREP"]
        rows, summary = synthesize(*args)
        self.assertEqual(summary["local_role_heads_with_lattice_audit_sampled"], 2)
        self.assertEqual(summary["local_role_heads_with_cross_category_alternatives_sampled"], 1)
        self.assertEqual(summary["local_role_heads_without_matching_lattice_candidate_sampled"], 0)
        self.assertFalse(next(row for row in rows if row["index"] == 463)[
            "grammatical_fault_established"])
        for field, value in (("contextual_plausibility_proven", True),
                             ("head_analysis_surface", "not-in-source"),
                             ("matching_head_candidate_count", 0)):
            with self.subTest(field=field):
                changed = deepcopy(args)
                changed[4][0]["scoped_dialogue"]["rejection_trace"][
                    "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0][
                    "subject"]["lexical_lattice_evidence"][field] = value
                with self.assertRaises(ValueError):
                    synthesize(*changed)

    def test_grounded_child_atoms_are_compared_without_inventing_grammar_requirement(self):
        args = fixture()
        pair = args[4][0]["scoped_dialogue"]["rejection_trace"][
            "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
        pair["materialized_child_feature_atoms"] = {
            "subject": {"number": "plural", "person": "3"},
            "predicate": {"number": "singular", "vform": "finite"},
        }
        pair["cross_child_grounded_atom_comparisons"] = [{
            "feature": "number", "subject_atom": "plural",
            "predicate_atom": "singular", "same_atom": False,
        }]
        pair["grammatical_agreement_requirement_proven"] = False
        rows, summary = synthesize(*args)
        self.assertEqual(summary["local_role_pairs_with_child_feature_observation_sampled"], 1)
        self.assertEqual(summary["local_role_pairs_with_comparable_grounded_number_atoms_sampled"], 1)
        annotated = next(row for row in rows if row["index"] == 463)[
            "sampled_local_rejection_evidence"]["scoped_dialogue"][
                "independent_local_probe"]["resolved_local_role_pairs"]["pairs"][0][
                    "local_child_feature_observation"]
        self.assertFalse(annotated["grammatical_conflict_proven"])
        self.assertFalse(annotated["grammatical_agreement_requirement_proven"])
        for field, value in (("same_atom", True),):
            with self.subTest(field=field):
                bad = deepcopy(args)
                bad[4][0]["scoped_dialogue"]["rejection_trace"][
                    "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0][
                        "cross_child_grounded_atom_comparisons"][0][field] = value
                with self.assertRaisesRegex(ValueError, "comparisons"):
                    synthesize(*bad)
        bad = deepcopy(args)
        bad[4][0]["scoped_dialogue"]["rejection_trace"][
            "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0][
                "materialized_child_feature_atoms"]["subject"]["number"] = "?unknown"
        with self.assertRaisesRegex(ValueError, "ungrounded"):
            synthesize(*bad)

    def test_rule_rhs_shared_variable_proof_is_local_and_recomputed(self):
        args = fixture()
        pair = args[4][0]["scoped_dialogue"]["rejection_trace"][
            "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
        pair["local_rule_rhs_feature_constraints"] = {
            "proof_basis": "exact_compiled_rule_rhs_for_accepted_local_composition",
            "subject_rhs_feature_terms": {"number": "?n", "person": "?p"},
            "predicate_rhs_feature_terms": {"number": "?n", "person": "?p"},
            "explicit_shared_rhs_variable_equalities": [
                {"feature": "number", "shared_rhs_variable": "?n",
                 "basis": "same_unification_variable_on_both_rhs_children"},
                {"feature": "person", "shared_rhs_variable": "?p",
                 "basis": "same_unification_variable_on_both_rhs_children"},
            ],
            "other_indirect_constraints_excluded_from_this_audit": True,
            "whole_sentence_agreement_proven": False,
        }
        rows, summary = synthesize(*args)
        self.assertEqual(summary["local_role_pairs_with_direct_rhs_number_equality_sampled"], 1)
        self.assertEqual(summary["local_role_pairs_with_direct_rhs_person_equality_sampled"], 1)
        annotated = next(row for row in rows if row["index"] == 463)[
            "sampled_local_rejection_evidence"]["scoped_dialogue"][
                "independent_local_probe"]["resolved_local_role_pairs"]["pairs"][0]
        self.assertEqual(len(annotated["local_rule_rhs_feature_constraints"][
            "explicit_shared_rhs_variable_equalities"]), 2)
        self.assertFalse(annotated["grammatical_conflict_proven"])

        bad = deepcopy(args)
        bad_pair = bad[4][0]["scoped_dialogue"]["rejection_trace"][
            "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
        bad_pair["local_rule_rhs_feature_constraints"]["predicate_rhs_feature_terms"][
            "number"] = "?different"
        with self.assertRaisesRegex(ValueError, "equalities"):
            synthesize(*bad)

        bad = deepcopy(args)
        bad_pair = bad[4][0]["scoped_dialogue"]["rejection_trace"][
            "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
        bad_pair["local_rule_rhs_feature_constraints"]["whole_sentence_agreement_proven"] = True
        with self.assertRaisesRegex(ValueError, "provenance"):
            synthesize(*bad)

    def test_selected_lexical_candidate_atoms_not_confused_with_unified_children(self):
        args = fixture()
        pair = args[4][0]["scoped_dialogue"]["rejection_trace"][
            "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
        for side in ("subject", "predicate"):
            pair[side]["head_lemma"] = side
        pair["materialized_child_feature_atoms"] = {
            "subject": {"number": "singular", "person": "3"},
            "predicate": {"number": "singular", "person": "3"},
        }
        pair["cross_child_grounded_atom_comparisons"] = [
            {"feature": feature, "subject_atom": value,
             "predicate_atom": value, "same_atom": True}
            for feature, value in (("number", "singular"), ("person", "3"))]
        pair["grammatical_agreement_requirement_proven"] = False
        pair["selected_lexical_head_feature_observations"] = {
            side: {
                "proof_basis": "selected_materialized_child_lexical_leaf_exact_match",
                "status": "unique_selected_lexical_leaf",
                "head_analysis_span": pair[side]["head_analysis_span"],
                "head_lexical_category": pair[side]["head_lexical_category"],
                "head_lemma": side,
                "matching_selected_leaf_count": 1,
                "candidate_feature_atoms": {"number": "singular", "person": person},
                "candidate_source": "lexicon",
                "whole_sentence_grammaticality_proven": False,
            } for side, person in (("subject", "1"), ("predicate", "3"))}
        pair["lexical_candidate_vs_child_atom_comparisons"] = [
            {"role": side, "feature": feature,
             "lexical_candidate_atom": atom,
             "materialized_child_atom": child_atom,
             "same_atom": atom == child_atom}
            for side, person in (("subject", "1"), ("predicate", "3"))
            for feature, atom, child_atom in (("number", "singular", "singular"),
                                             ("person", person, "3"))]
        pair["cross_lexical_candidate_atom_comparisons"] = [
            {"feature": "number", "subject_lexical_candidate_atom": "singular",
             "predicate_lexical_candidate_atom": "singular", "same_atom": True},
            {"feature": "person", "subject_lexical_candidate_atom": "1",
             "predicate_lexical_candidate_atom": "3", "same_atom": False},
        ]
        pair["lexical_candidate_conflict_proven"] = False
        rows, summary = synthesize(*args)
        self.assertEqual(summary["local_role_heads_with_unique_selected_lexical_leaf_sampled"], 2)
        self.assertEqual(summary[
            "local_role_pairs_with_comparable_selected_lexical_number_atoms_sampled"], 1)
        self.assertEqual(summary[
            "local_selected_lexical_candidate_vs_child_atom_differences_sampled"], 1)
        result = next(row for row in rows if row["index"] == 463)[
            "sampled_local_rejection_evidence"]["scoped_dialogue"][
                "independent_local_probe"]["resolved_local_role_pairs"]["pairs"][0]
        evidence = result["selected_lexical_head_feature_evidence"]
        self.assertEqual(evidence["selected_lexical_head_feature_observations"][
            "subject"]["candidate_feature_atoms"]["person"], "1")
        self.assertFalse(evidence["whole_sentence_grammaticality_proven"])
        for mutate in (
            lambda p: p["lexical_candidate_vs_child_atom_comparisons"][1].update(
                same_atom=True),
            lambda p: p["selected_lexical_head_feature_observations"]["subject"].update(
                status="not_uniquely_observed"),
            lambda p: p.update(lexical_candidate_conflict_proven=True),
        ):
            bad = deepcopy(args)
            bad_pair = bad[4][0]["scoped_dialogue"]["rejection_trace"][
                "independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
            mutate(bad_pair)
            with self.assertRaises(ValueError):
                synthesize(*bad)

    def test_wrong_identity_status_targets_and_trace_claims_fail_closed(self):
        mutators = [
            lambda a: a[1].update(cohort_sha256="other"),
            lambda a: a[2][8].update(case_id="wrong"),
            lambda a: a[3][0].update(canonical_status="complete"),
            lambda a: a[4][0].update(canonical_dialogue_root_nodes=0),
            lambda a: a[5].update(target_indices=[]),
            lambda a: a[6].pop(),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"].update(exhaustive=True),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"]["events"][0].update(
                reference_span_mapping="exact", reference_span=None),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"]
                ["validated_local_constituents"]["witnesses"][0].update(
                    whole_sentence_grammaticality_proven=True),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"]
                ["independent_local_probe"].update(canonical_work_budget_unchanged=False),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"]
                ["independent_local_probe"].update(accepted_requested_nodes=5),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"]
                ["independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
                ["subject"].update(head_analysis_span=[0, 11]),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"]
                ["independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
                .update(grammatical_conflict_proven=True),
            lambda a: a[4][0]["scoped_dialogue"]["rejection_trace"]
                ["independent_local_probe"]["validated_local_role_pairs"]["pairs"][0]
                ["subject"].update(head_lexical_category="OPEN-QUOTE"),
            lambda a: a[4][0].update(analysis_text="wrong projection"),
        ]
        for change in mutators:
            with self.subTest(change=change):
                args = deepcopy(fixture())
                change(args)
                with self.assertRaises(ValueError):
                    synthesize(*args)

    def test_cli_materializes_all_three_reproducible_artifacts(self):
        names = ("register", "register-summary", "preflight", "lexical",
                 "dialogue", "dialogue-summary", "comparators")
        with TemporaryDirectory() as location:
            folder = Path(location)
            argv = ["synthesize_residual_evidence"]
            for name, payload in zip(names, fixture()):
                file = folder / (name + ".json")
                file.write_text(
                    ("".join(json.dumps(r) + "\n" for r in payload)
                     if isinstance(payload, list) else json.dumps(payload)),
                    encoding="utf8")
                argv += ["--" + name, str(file)]
            argv += ["--out-dir", str(folder / "out")]
            with patch("sys.argv", argv):
                main()
            output = folder / "out"
            lines = (output / "residual_evidence_synthesis.jsonl").read_text(
                encoding="utf8").splitlines()
            self.assertEqual(len(lines), 26)
            self.assertEqual(json.loads(lines[0])["index"], 8)
            self.assertEqual(json.loads((output / "residual_evidence_summary.json")
                                        .read_text(encoding="utf8"))["original_26_retained"], 26)
            self.assertIn("## Interpretation limits", (output / "residual_evidence_report.md")
                          .read_text(encoding="utf8"))


if __name__ == "__main__":
    unittest.main()
