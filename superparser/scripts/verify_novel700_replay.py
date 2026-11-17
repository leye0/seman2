"""Verify Novel-700's repaired cohort against both frozen prior rungs.

Refuse any changed existing rank-one tree/graph signature, source identity,
budget, or newly saturated old case. Emit small log-safe chunks only after
the full exact-source replay passes.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.novel_ladder import (
    LADDER, load_sources, read_ladder, result_cases, compare_rows, read_json
)

EXPECTED_REPAIRED = {
    624: "structural_semicolon_parataxis_with_participial_cause_and_relative",
    625: "dialogue_structural_contrast_and_semicolon_existential_relative",
    639: "dialogue_structural_existential_with_dashed_nominal_reformulation",
    643: "dialogue_structural_intercalated_reported_two_questions",
    647: "structural_coordinated_superlative_with_instrument_cleft",
    648: "structural_semicolon_progressive_with_participial_and_result",
    649: "structural_evaluative_parallel_how_and_with_what_manner",
    660: "dialogue_structural_negative_reprise_vocative_and_modal_gerund",
    661: "dialogue_structural_dialectal_vocative_question_and_epistemic_tag",
    669: "structural_topical_as_to_with_reported_emotive_modal_question",
    672: "dialogue_structural_forgotten_exception_and_elliptic_wish",
    691: "dialogue_structural_intercalated_affect_reprise_and_emphatic_question",
}

def assert_equal(left, right, label):
    if left != right:
        raise AssertionError(f"{label}: {left!r} != {right!r}")

def verify(out_dir: Path) -> dict:
    cohorts, _, _ = read_ladder(LADDER, load_sources())
    by_end = {cases[-1]["ladder_index"]: (cohort, cases)
              for cohort, cases in cohorts}
    assert set(by_end) == {600, 700}, by_end.keys()
    source600, cases600 = by_end[600]
    source700, cases700 = by_end[700]
    observed600 = read_json(out_dir / "novel-600-result.json")
    observed700 = read_json(out_dir / "novel-700-result.json")
    pin600 = read_json(LADDER / "novel-600-accepted.json")
    previous700 = read_json(LADDER / "novel-700-current.json")
    initial700 = read_json(LADDER / "novel-700-initial.json")

    old600 = result_cases(pin600, source600, 600)
    new600 = result_cases(observed600, source600, 600)
    assert_equal(new600, old600, "all Novel-600 protected signatures")
    assert_equal(observed600["counts"], pin600["counts"], "Novel-600 counts")
    prior700 = result_cases(previous700, source700, 700)
    measured700 = result_cases(observed700, source700, 700)
    baseline700 = result_cases(initial700, source700, 700)
    if any(baseline700[i]["status"] == "complete"
           and prior700[i]["status"] != "complete"
           for i in prior700):
        raise AssertionError("Earlier corrections regressed before replay")
    mismatches = compare_rows(prior700, measured700, sealed=False)
    if mismatches:
        raise AssertionError(f"Novel-700 existing-tree regressions: {mismatches}")
    protected700 = {i for i, r in prior700.items() if r["status"] == "complete"}
    assert_equal(len(protected700), 88, "pre-repair complete cases")
    for i in protected700:
        assert_equal(measured700[i], prior700[i], f"previously complete N{i}")
    newly_complete = {
        i for i, r in measured700.items()
        if r["status"] == "complete" and prior700[i]["status"] != "complete"
    }
    assert_equal(newly_complete, set(EXPECTED_REPAIRED),
                 "twelve exactly predicted recoveries")
    for i, target in EXPECTED_REPAIRED.items():
        r = measured700[i]
        assert_equal(r["root_rule"], target, f"N{i} root")
        if not r["rank_one_sha256"] or not r["selected_graph_sha256"]:
            raise AssertionError(f"N{i} missing complete selected tree/graph")
        if r["forest_budget_exceeded"] or r["kbest_budget_exceeded"]:
            raise AssertionError(f"N{i} remains budget saturated")
    assert_equal(observed700["counts"], {"complete": 100},
                 "Novel-700 all cases complete")
    if any(r["status"] != "complete" for r in measured700.values()):
        raise AssertionError("Uncompleted Novel-700 case")
    print("NOVEL_700_REPLAY_VERIFIED",
          json.dumps({
              "newly_complete": sorted(newly_complete),
              "newly_complete_count": len(newly_complete),
              "complete_700": sum(r["status"] == "complete"
                                  for r in measured700.values()),
              "unchanged_protected_700": len(protected700),
              "unchanged_accepted_600": len(old600),
              "cohort_700_sha256": observed700["cohort_sha256"],
          }, sort_keys=True), flush=True)
    return observed700

def main():
    import argparse
    cli=argparse.ArgumentParser()
    cli.add_argument("--out-dir",type=Path,required=True)
    args=cli.parse_args()
    result=verify(args.out_dir)
    compact=json.dumps(result,ensure_ascii=False,separators=(",",":"))
    for i in range(0,len(compact),5000):
        print(f"SEMAN2_N700_JSON_CHUNK_{i//5000:03d}::{compact[i:i+5000]}",flush=True)

if __name__ == "__main__":
    main()
