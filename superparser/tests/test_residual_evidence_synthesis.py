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
        r8 = next(r for r in rows if r["index"] == 8)
        self.assertEqual(r8["sampled_local_rejection_evidence"]
                         ["unscoped_replay"]["independent_local_probe"]
                         ["witnesses"][0]["source_span"], [30, 34])
        self.assertEqual(r8["canonical_status"], "no_structural_root")
        with self.assertRaisesRegex(ValueError, "Unscoped replay identity"):
            synthesize(*args, extra[:1], extra_summary)

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
