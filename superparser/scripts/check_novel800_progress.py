"""Verify Novel-800 exploratory progress without changing frozen prior tree digests."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
from scripts import novel_ladder as ladder
from scripts.evaluate_novel_transfer import ROOT

DIR=ROOT/"research"/"novel_800_exploration"

def check(directory:Path,expect_new:set[int]):
    manifest=ladder.read_json(DIR/"novel-800-candidate-cohort.json")
    old=ladder.read_json(DIR/"novel-800-candidate-current.json")
    initial=ladder.read_json(DIR/"novel-800-candidate-initial.json")
    now=ladder.read_json(directory/"novel-800-candidate-current.json")
    baseline=ladder.result_cases(initial,manifest,800)
    previous=ladder.result_cases(old,manifest,800)
    observed=ladder.result_cases(now,manifest,800)
    if initial["counts"]!={"complete":85,"roots_without_valid_analysis":10,
                             "no_structural_root":4,"forest_budget_exceeded":1}:
        raise AssertionError("Frozen original N800 baseline changed")
    if any(initial["cases"][i-701]!=previous[i] for i in range(701,801) if baseline[i]["status"]=="complete"):
        raise AssertionError("Original complete N800 signature previously changed")
    protected=[i for i in range(701,801) if previous[i]["status"]=="complete"]
    for i in protected:
        if previous[i]!=observed[i]:
            raise AssertionError(f"N{i} previously completed rank-one tree/graph changed")
    newly={i for i in range(701,801)
           if previous[i]["status"]!="complete" and observed[i]["status"]=="complete"}
    if newly!=expect_new:
        raise AssertionError(f"Unexpected newly complete IDs {sorted(newly)}; expected {sorted(expect_new)}")
    for i in newly:
        row=observed[i]
        if (not row["rank_one_sha256"] or not row["selected_graph_sha256"]
                or row["forest_budget_exceeded"] or row["kbest_budget_exceeded"]):
            raise AssertionError(f"N{i} lacks complete unsaturated tree and graph")
    problems=ladder.compare_rows(previous,observed)
    if problems:
        raise AssertionError(f"Novel-800 regression: {problems}")
    counts=now["counts"]
    if counts.get("complete")!=len(protected)+len(newly):
        raise AssertionError(f"Inconsistent completion count {counts}")
    result={"initial_complete":85,"previous_complete":len(protected),
            "newly_complete":sorted(newly),"current_complete":counts["complete"],
            "remaining":100-counts["complete"],"counts":counts,
            "source_sha256":manifest["cohort_sha256"],
            "unchanged_previous_trees":len(protected),
            "reviewed_trees":0,"candidate_only":True}
    print("N800_INCREMENTAL_VERIFIED",json.dumps(result,sort_keys=True),flush=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--expected-new",type=int,nargs="*",default=[])
    a=p.parse_args()
    check(a.out_dir,set(a.expected_new))
if __name__=="__main__":main()
