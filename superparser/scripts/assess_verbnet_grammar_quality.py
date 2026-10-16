"""Produce a reproducible correctness-first performance gate from research reports.

This is a *benchmark classification*, not a parser feature. It never alters
rules or parser choices. CI runtime timing is informative: hardware variance
can change absolute thresholds, so report separately from correctness gates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def assess(main: dict, negative: dict, median_target_ms: float = 5.0) -> dict:
    modes = ("A_baseline", "N_local_snapshot1", "O_local_snapshot2", "P_local_snapshot3",
             "R_guard0", "S_guard1", "T_guard2", "U_guard3",
             "V_fast_baseline", "W_fast_guard1", "X_fast_guard3",
             "Y_early_guard1", "Z_early_guard2", "AA_early_guard3")
    comparisons = {}
    base = main["summary"]["A_baseline"]
    negative_baseline = negative["summary"]["A_baseline"]
    for mode in modes:
        row = main["summary"][mode]
        neg = negative["summary"][mode]
        changes = main.get("diffs", {}).get(mode, {}).get("changes", ())
        regressions = sorted(c["id"] for c in changes
                             if c["baseline_gold"]["pass"] is True
                             and c["guided_gold"]["pass"] is not True)
        improved = sorted(c["id"] for c in changes
                          if c["baseline_gold"]["pass"] is not True
                          and c["guided_gold"]["pass"] is True)
        median_ms = row["total_ms"]["p50"]
        tests = {
            "nonregression_on_explicit_positive_gold": not regressions,
            "gold_passes_at_least_baseline": (
                row["explicit_gold_assertion_passed"] >= base["explicit_gold_assertion_passed"]),
            "no_new_negative_false_acceptances": not neg["new_false_accepts_vs_baseline"],
            "median_at_or_below_target": median_ms <= median_target_ms,
        }
        comparisons[mode] = {
            "total_positive_cases": main["cases"],
            "gold_passed_cases": row["explicit_gold_assertion_passed"] // main["repetitions"],
            "completed_positive_cases": row["complete"] // main["repetitions"],
            "complete_but_nonconforming_cases": row["complete_but_nonconforming"] // main["repetitions"],
            "positive_gold_improvements": improved,
            "positive_gold_regressions": regressions,
            "negative_cases": neg["negative_cases"],
            "negative_false_accepts": neg["negative_false_accepts"],
            "new_negative_false_acceptances": neg["new_false_accepts_vs_baseline"],
            "baseline_negative_false_accepts": negative_baseline["negative_false_accepts"],
            "positive_median_ms": median_ms,
            "positive_p95_ms": row["total_ms"]["p95"],
            "tests": tests,
            "quality_gate": all(value for key, value in tests.items()
                                if key != "median_at_or_below_target"),
            "performance_target_met": tests["median_at_or_below_target"],
        }
    return {
        "schema": 1,
        "median_target_ms": median_target_ms,
        "focus": "Grammar correctness, false acceptances, then latency",
        "comparisons": comparisons,
        "warning": [
            "Gold assertions are incomplete annotations, not independently gold parsed trees.",
            "Failed negative parsing does not prove grammatical rejection.",
            "Absolute timings are GitHub runner measurements with machine-to-machine variability.",
            "The holdout is for reporting only; do not tune parser rules on holdout errors.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = ROOT / "research" / "verbnet_lr"
    parser.add_argument("--positive", default=str(root / "reader_ablation.json"))
    parser.add_argument("--negative", default=str(root / "negative_report.json"))
    parser.add_argument("--out", default=str(root / "grammar_quality_gate.json"))
    parser.add_argument("--median-target-ms", type=float, default=5.0)
    args = parser.parse_args()
    pos = json.loads(Path(args.positive).read_text(encoding="utf8"))
    neg = json.loads(Path(args.negative).read_text(encoding="utf8"))
    report = assess(pos, neg, args.median_target_ms)
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(json.dumps({k: {
        "quality": v["quality_gate"], "median_target": v["performance_target_met"],
        "gold": v["gold_passed_cases"], "neg_false_accepts": v["negative_false_accepts"],
        "p50_ms": v["positive_median_ms"]
    } for k, v in report["comparisons"].items()}, indent=2))


if __name__ == "__main__":
    main()
