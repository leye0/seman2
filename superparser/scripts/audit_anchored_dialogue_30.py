"""Immutable *real* dialogue-failure evaluation set on the active 500 cohort.

These are ALL 30 source-quoted failures from the PR #42 green CI run
43102702010, not cherry-picked toy examples. Each anchor preserves the
original source book, exact SHA-derived case ID, original failure status,
and actual structural dialogue subtype. Evaluate the same 30 cases *after*
the canonical 500-case run: no alternative segmentation, budget, grammar,
wordnet configuration, scoring method or corpus sampling.

All results are observations, not grammar gold. A successful parse still
requires rank-1 tree/attachment review before being accepted as a
linguistically correct repair. This set is the regression/evidence target,
NOT an invitation to add phrase-specific rules.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import argparse
import json
from pathlib import Path

from seman_parser.structural_preanalysis import analyze_paragraph
from seman_parser.structural_composition import QuotedSentenceComposer

EXPECTED_COHORT_SHA = "d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f"
BASELINE_RUN = "https://github.com/leye0/seman2/actions/runs/43102702010"

@dataclass(frozen=True)
class DialogueWitness:
    index: int
    case_id: str
    baseline_status: str
    subtype: str


# The complete, SHA-pinned 30/30 sample from actual novel failures.
WITNESSES = tuple(DialogueWitness(*x) for x in (
    (11, '766:7aeedec565c8d7f5', 'roots_without_valid_analysis', 'nested_quotation'),
    (41, '766:0889d247438b5ebb', 'no_structural_root', 'single_quote_with_reporting_clause'),
    (56, '766:daaca15c309a8606', 'no_structural_root', 'single_quote_with_reporting_clause'),
    (66, '766:64bab268f9f84142', 'roots_without_valid_analysis', 'split_speech_with_intercalated_reporting_clause'),
    (96, '766:20c2b53ad2e4e57a', 'roots_without_valid_analysis', 'split_speech_with_intercalated_reporting_clause'),
    (99, '766:e32c8b16607f2eca', 'forest_budget_exceeded', 'multisentence_quotation'),
    (109, '766:4948b167f2e21291', 'forest_budget_exceeded', 'nested_quotation'),
    (137, '1342:4fd376ffc6f86353', 'roots_without_valid_analysis', 'unattributed_single_quotation'),
    (157, '1342:d6918ea88c026ca8', 'roots_without_valid_analysis', 'single_quote_with_reporting_clause'),
    (200, '1342:d5153e50bf9baae7', 'roots_without_valid_analysis', 'single_quote_with_reporting_clause'),
    (209, '1342:22e3d31ffb030c03', 'roots_without_valid_analysis', 'unattributed_single_quotation'),
    (222, '1342:b586990ccc19b524', 'roots_without_valid_analysis', 'split_speech_with_intercalated_reporting_clause'),
    (223, '1342:84466f9018ea02d2', 'forest_budget_exceeded', 'multisentence_quotation'),
    (229, '1342:b54417eaf6fcbf18', 'forest_budget_exceeded', 'multisentence_quotation'),
    (235, '1342:904690daa85fd414', 'roots_without_valid_analysis', 'split_speech_with_intercalated_reporting_clause'),
    (237, '1342:2c6eaa263fc3d9af', 'no_structural_root', 'split_speech_with_intercalated_reporting_clause'),
    (241, '1342:84c4c4a94e815882', 'roots_without_valid_analysis', 'unattributed_single_quotation'),
    (247, '1342:8f0fdbd687462614', 'no_structural_root', 'unattributed_single_quotation'),
    (359, '84:9738e2ce2b387e0f', 'roots_without_valid_analysis', 'unattributed_single_quotation'),
    (384, '120:a7e247552ca805e8', 'roots_without_valid_analysis', 'unattributed_single_quotation'),
    (408, '120:1b5dc896fe97ebd3', 'roots_without_valid_analysis', 'single_quote_with_reporting_clause'),
    (413, '120:2314d915cde45d24', 'no_structural_root', 'single_quote_with_reporting_clause'),
    (441, '120:b20b1c50bc030311', 'roots_without_valid_analysis', 'split_speech_with_intercalated_reporting_clause'),
    (445, '120:3d812d09ecccb8e0', 'no_structural_root', 'single_quote_with_reporting_clause'),
    (456, '120:c680ad0d5761a767', 'no_structural_root', 'split_speech_with_intercalated_reporting_clause'),
    (464, '120:108e97de304b05fa', 'no_structural_root', 'multisentence_quotation'),
    (466, '120:990233ea73026451', 'roots_without_valid_analysis', 'single_quote_with_reporting_clause'),
    (475, '120:9a48d5865aa9fa96', 'forest_budget_exceeded', 'multisentence_quotation'),
    (495, '120:8d4410e91edbd9ed', 'roots_without_valid_analysis', 'unattributed_single_quotation'),
    (498, '120:d3bd7df004f99f45', 'forest_budget_exceeded', 'multisentence_quotation'),
))

assert len(WITNESSES) == len({w.index for w in WITNESSES}) == 30
assert Counter(w.subtype for w in WITNESSES) == {
    "nested_quotation": 2,
    "single_quote_with_reporting_clause": 8,
    "split_speech_with_intercalated_reporting_clause": 7,
    "multisentence_quotation": 6,
    "unattributed_single_quotation": 7,
}


def audit(rows: list[dict], *, cohort_sha: str) -> dict:
    """Build a real before/after paired verdict for the 30 fixed anchors."""
    if cohort_sha != EXPECTED_COHORT_SHA:
        raise ValueError("The dialogue-30 evaluation cannot migrate cohorts silently")
    by_index = {r["index"]: r for r in rows}
    if len(rows) != 500 or len(by_index) != 500:
        raise ValueError("The original complete 500-passage cohort is required")
    results = []
    for witness in WITNESSES:
        row = by_index[witness.index]
        if row.get("case_id") != witness.case_id:
            raise AssertionError(
                f"Source passage or ordering changed at {witness.index}: "
                f"{row.get('case_id')} != {witness.case_id}"
            )
        if row.get("quotation_status") != "balanced":
            raise AssertionError("A baseline source quote was silently made incomplete")
        if "direct_speech" not in row.get("structural_functions", ()):
            raise AssertionError("A source quotation disappeared from the structural graph")
        success = row["status"] == "complete"
        source = row["source_text"]
        units = analyze_paragraph(source)
        if len(units) != 1 or units[0].text != source:
            raise AssertionError(
                "Source discourse boundary drifted for anchored dialogue "
                f"{witness.index}"
            )
        source_parts = [c.to_dict() for c in units[0].constituents]
        all_nodes = {p["id"]: p for p in source_parts}
        for part in source_parts:
            if source[part["start"]:part["end"]].strip() == "":
                raise AssertionError("Empty quotation or grammatical source span")
            if (part["governor"] is not None
                    and part["governor"] not in all_nodes):
                raise AssertionError("Unresolved grammatical source governor")
        # These are source-span *plans*, never independently proven grammar
        # trees. Actual parse success still comes only from the normal
        # full parser status in the canonical 500-case diagnostic.
        plan_specs = (
            ("multi_clause_quote", QuotedSentenceComposer._plan),
            ("intercalated_two_finite_clauses",
             QuotedSentenceComposer._intercalation_plan),
            ("postposed_vocative_with_reporter",
             QuotedSentenceComposer._postposed_minor_reply_plan),
            ("nested_nominal_title",
             QuotedSentenceComposer._nested_nominal_title_plan),
        )
        proposals = []
        for label, fn in plan_specs:
            plan = fn(source, source_parts)
            if plan is not None:
                proposals.append(label)
        results.append({
            "index": witness.index,
            "case_id": witness.case_id,
            "book_id": row["book_id"],
            "source_text": row["source_text"],
            "subtype": witness.subtype,
            "baseline_status": witness.baseline_status,
            "current_status": row["status"],
            "new_complete": success,
            "root_rule": row.get("root_rule") if success else None,
            "structural_functions": row.get("structural_functions", []),
            "structural_relations": row.get("structural_relations", []),
            "engine": row.get("engine"),
            "wall_ms": row.get("wall_ms"),
            "full_grammar_tree_review_required": success,
            "source_composition_plans_not_proofs": proposals,
            "all_quote_and_reporting_constituents": [
                {
                    "id": p["id"],
                    "function": p["function"],
                    "relation": p["relation"],
                    "governor": p["governor"],
                    "evidence": p["evidence"],
                    "span": [p["start"], p["end"]],
                    "exact_source_text": source[p["start"]:p["end"]],
                }
                for p in source_parts
                if p["function"] in (
                    "direct_speech", "embedded_quotation",
                    "spoken_clause_candidate", "reporting_clause",
                    "split_direct_speech_turn", "narratorial_parenthetical"
                )
            ],

        })
    by_subtype = {}
    for kind in sorted({w.subtype for w in WITNESSES}):
        subset = [r for r in results if r["subtype"] == kind]
        by_subtype[kind] = {
            "baseline_failed": len(subset),
            "still_failed": sum(not x["new_complete"] for x in subset),
            "now_complete": sum(x["new_complete"] for x in subset),
        }
    plan_counts = Counter(
        plan for case in results
        for plan in case["source_composition_plans_not_proofs"]
    )
    return {
        "schema": "seman2-anchored-real-dialogue-30-v2",
        "cohort_sha256": cohort_sha,
        "baseline_run": BASELINE_RUN,
        "total": len(results),
        "baseline_failed": 30,
        "now_complete": sum(x["new_complete"] for x in results),
        "still_failed": sum(not x["new_complete"] for x in results),
        "by_subtype": by_subtype,
        "source_composition_candidate_plans": dict(plan_counts),
        "not_currently_planned": sum(
            not x["source_composition_plans_not_proofs"] for x in results
        ),
        "cases": results,
        "method": "exact 30 original source passages, normal corpus parse route and identical budgets",
        "caveat": "Source plans are ONLY structural proposals. Completion plus manual rank-1 syntax/semantic attachment review is required for verified grammatical repairs.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diagnostics", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    rows = [json.loads(line) for line in args.diagnostics.read_text().splitlines()
            if line.strip()]
    summary = json.loads(args.summary.read_text())
    result = audit(rows, cohort_sha=summary["cohort_sha256"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print("ANCHORED_DIALOGUE_30", json.dumps({
        k: v for k, v in result.items() if k != "cases"
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
