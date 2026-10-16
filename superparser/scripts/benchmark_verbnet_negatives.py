"""Independent negative minimal-pair diagnostic for experimental Seman2 L→R.

A completed parse of a manually labeled ungrammatical sentence is a false
acceptance under *this test set*. A failed parse is merely INCOMPLETE, not a
proof of ungrammaticality. The test set is small, curated and NOT used to
modify the grammar, tune scores or construct grammar rules.

From repository root:
 PYTHONPATH=superparser .venv-popper/bin/python \
   superparser/scripts/benchmark_verbnet_negatives.py --wordnet-dir /path/to/dict
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader


ROOT = Path(__file__).resolve().parents[1]


def chosen_tree_facts(node):
    """Read only the *chosen* completed analysis, never alternative trees."""
    if node is None:
        return {}
    rule_ids = []
    leaves = []
    stack = [node]
    while stack:
        current = stack.pop()
        rule = getattr(current, "rule_id", None)
        if rule:
            rule_ids.append(rule)
        lex = getattr(current, "lexical_candidate", None)
        if lex is not None:
            feats = lex.features.as_dict() if hasattr(lex.features, "as_dict") else lex.features
            leaves.append({
                "surface": lex.surface,
                "lemma": lex.lemma,
                "category": lex.category,
                "features": {str(k): str(v) for k, v in feats.items()
                             if k in {"number", "person", "vform", "subcat"}},
            })
        stack.extend(reversed(getattr(current, "children", ())))
    return {"rules": sorted(set(rule_ids)), "lexemes": leaves}


MODES = (
    ("A_baseline", 0),
    ("N_local_snapshot1", 1),
    ("O_local_snapshot2", 2),
    ("P_local_snapshot3", 3),
)


def run(wordnet_dir=None, corpus=None, repetitions=2):
    corpus = Path(corpus or ROOT / "research" / "verbnet_lr" / "negative_minimal_pairs.jsonl")
    cases = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not cases or len({x["id"] for x in cases}) != len(cases):
        raise ValueError("Empty or duplicate negative case IDs")
    for case in cases:
        if case["label"] != "ungrammatical_standard_written_english":
            raise ValueError("Negative labels must be explicit and separate")
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    machines = {
        name: SemanCompiledReader(
            resources, checkpoint_budget=budget, stack_checkpoints=bool(budget))
        for name, budget in MODES
    }
    # Warm each unique sentence equally for all modes; measure end-to-end
    # processing excluding the initial grammar compilation.
    for case in cases:
        for machine in machines.values():
            machine.parse(case["text"])
            machine.parse(case["contrast"])
    observations = defaultdict(list)
    for repeat in range(repetitions):
        for case in cases:
            for name, machine in machines.items():
                # Rotating positive/negative order mitigates cache effects.
                order = ("text", "contrast") if (repeat + len(case["id"])) % 2 else ("contrast", "text")
                for kind in order:
                    started = perf_counter()
                    result = machine.parse(case[kind])
                    elapsed = 1000 * (perf_counter() - started)
                    observations[name].append({
                        "id": case["id"], "family": case["family"],
                        "kind": "negative" if kind == "text" else "contrast_positive",
                        "complete": bool(result.complete),
                        "time_ms": round(elapsed, 5),
                        "reason": result.outcome.reason if not result.complete else "",
                        "chosen_analysis": (chosen_tree_facts(result.item)
                                            if kind == "text" and result.complete and repeat == 0
                                            else None),
                    })

    summary = {}
    by_case = {}
    for mode, records in observations.items():
        negatives = [r for r in records if r["kind"] == "negative"]
        contrasts = [r for r in records if r["kind"] == "contrast_positive"]
        by_case[mode] = {}
        for case in cases:
            neg = [r for r in negatives if r["id"] == case["id"]]
            pos = [r for r in contrasts if r["id"] == case["id"]]
            by_case[mode][case["id"]] = {
                "family": case["family"], "negative": case["text"],
                "contrast": case["contrast"],
                "negative_accepts": sum(r["complete"] for r in neg),
                "contrast_completes": sum(r["complete"] for r in pos),
                "accepted_negative_analysis": next(
                    (r["chosen_analysis"] for r in neg if r["chosen_analysis"] is not None),
                    None),
            }
        summary[mode] = {
            "negative_cases": len(cases),
            "negative_false_accepts": sum(by_case[mode][c["id"]]["negative_accepts"] > 0 for c in cases),
            "positive_contrast_completes": sum(by_case[mode][c["id"]]["contrast_completes"] > 0 for c in cases),
            "by_family": {
                family: {
                    "cases": sum(c["family"] == family for c in cases),
                    "negative_false_accepts": sum(
                        by_case[mode][c["id"]]["negative_accepts"] > 0
                        for c in cases if c["family"] == family),
                    "contrast_completes": sum(
                        by_case[mode][c["id"]]["contrast_completes"] > 0
                        for c in cases if c["family"] == family),
                }
                for family in sorted({c["family"] for c in cases})
            },
            "negative_median_ms": round(median(r["time_ms"] for r in negatives), 5),
            "contrast_median_ms": round(median(r["time_ms"] for r in contrasts), 5),
        }
    baseline = {
        cid for cid, data in by_case["A_baseline"].items()
        if data["negative_accepts"] > 0
    }
    for mode in summary:
        found = {cid for cid, data in by_case[mode].items()
                 if data["negative_accepts"] > 0}
        summary[mode]["new_false_accepts_vs_baseline"] = sorted(found - baseline)
        summary[mode]["lost_false_accepts_vs_baseline"] = sorted(baseline - found)
    return {
        "schema": 1,
        "corpus": str(corpus),
        "repetitions": repetitions,
        "summary": summary,
        "cases": by_case,
        "limitations": [
            "Hand-curated small standard-written-English negatives, not a representative test set",
            "Negative failure means incomplete or unsupported, NOT proof of ungrammaticality",
            "Positive contrast completion is not a checked syntactic tree",
            "No grammatical gold used during parsing, score ranking or checkpoint selection",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wordnet-dir")
    parser.add_argument("--cases")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--report", default=str(ROOT / "research" / "verbnet_lr" / "negative_report.json"))
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    report = run(args.wordnet_dir, args.cases, args.repetitions)
    dest = Path(args.report)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"report": str(dest), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
