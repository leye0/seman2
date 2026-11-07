"""Benchmark cheap *preparse* routing hints against the frozen 500-case audit.

Consumes already-measured canonical outcomes only as labels AFTER predictions;
never changes Parser.parse, runs an alternative recognizer, or fits thresholds
on the 26 failures. A quick signal is NOT a diagnosed grammatical anomaly.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns
from typing import Any, Mapping

from scripts.diagnose_novel_parses import EXPECTED_500_COHORT_SHA256
from seman_parser.fast_preflight import fast_preflight
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()
            if line.strip()]


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    sequence = sorted(values)
    # Nearest-rank percentile, stable without numpy.
    index = max(0, (len(sequence) * percentile + 99) // 100 - 1)
    return round(sequence[index], 3)


def _summarize_measurements(
    records: list[dict[str, Any]], samples_us: list[float],
) -> dict[str, Any]:
    lane_counts: dict[str, Counter[str]] = defaultdict(Counter)
    signal_counts: dict[str, Counter[str]] = defaultdict(Counter)
    failed = []
    complete = []
    for row in records:
        group = "complete" if row["canonical_status"] == "complete" else "noncomplete"
        lane_counts[row["preflight"]["lane"]][group] += 1
        for signal in row["preflight"]["signals"]:
            signal_counts[signal][group] += 1
        (complete if group == "complete" else failed).append(row)
    reviewed = [x for x in records if x["preflight"]["lane"] != "no_early_signal"]
    reviewed_failures = [x for x in reviewed if x["canonical_status"] != "complete"]
    canonical_times = [float(row["canonical_wall_ms"]) for row in records
                       if isinstance(row.get("canonical_wall_ms"), (float, int))]
    return {
        "schema": "seman2-fast-preflight-audit-v1",
        "cohort_sha256": EXPECTED_500_COHORT_SHA256,
        "total_cases": len(records),
        "canonical_complete": len(complete),
        "canonical_noncomplete": len(failed),
        "review_lane_cases": len(reviewed),
        "review_lane_noncomplete": len(reviewed_failures),
        "review_lane_complete": len(reviewed) - len(reviewed_failures),
        "noncomplete_without_early_signal": [
            r["index"] for r in failed if r["preflight"]["lane"] == "no_early_signal"
        ],
        "per_lane": {k: dict(sorted(v.items())) for k, v in sorted(lane_counts.items())},
        "per_signal": {k: dict(sorted(v.items())) for k, v in sorted(signal_counts.items())},
        "surface_only_benchmark_us": {
            "observations": len(samples_us),
            "median": round(median(samples_us), 3),
            "p95": _percentile(samples_us, 95),
            "p99": _percentile(samples_us, 99),
            "maximum": round(max(samples_us), 3) if samples_us else 0.0,
            "excludes_parser_lexical_grammar_and_file_io": True,
        },
        "canonical_parser_wall_ms_for_context_only": {
            "observations": len(canonical_times),
            "median": round(median(canonical_times), 3) if canonical_times else 0.0,
            "p95": _percentile(canonical_times, 95),
            "not_an_apples_to_apples_speedup": True,
        },
        "measured_but_not_causal": True,
        "grammatical_gold_labels_available": False,
        "noncompletion_is_not_an_anomaly_label": True,
        "review_lane_is_not_grammatical_error_prediction": True,
        "no_parse_skipping_or_strategy_changes": True,
        "thresholds_not_fitted_on_corpus": True,
    }


def audit(
    diagnostics: list[Mapping[str, Any]],
    contexts: list[Mapping[str, Any]],
    *,
    repetitions: int = 7,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    if len(diagnostics) != 500 or len(contexts) != 500:
        raise ValueError("Only the immutable 500-case cohort may be compared")
    observations = []
    samples_us: list[float] = []
    for i, (row, ctx) in enumerate(zip(diagnostics, contexts)):
        if not (
            row.get("index") == ctx.get("index") == i
            and row.get("book_id") == ctx.get("book_id")
            and row.get("ordinal") == ctx.get("ordinal")
            and row.get("source_text") == ctx.get("source_text")
            and row.get("status") == ctx.get("status")
        ):
            raise ValueError(f"Source/corpus provenance mismatch at {i}")
        text = row["canonical_analysis_text"]
        kwargs = {
            "preceding_semicolon_part": bool(
                ctx["context"]["semicolon_part_index"] > 0),
            "transferred_prefix": row["canonical_synthetic_prefix"],
            "transferred_suffix": row["canonical_synthetic_suffix"],
        }
        prediction = fast_preflight(text, **kwargs)
        # Warm-up is excluded. Repeat only the small classifier itself,
        # not the prior canonical parse or any WordNet data preparation.
        for _ in range(repetitions):
            started = perf_counter_ns()
            second = fast_preflight(text, **kwargs)
            samples_us.append((perf_counter_ns() - started) / 1000)
            if second.signals != prediction.signals or second.lane != prediction.lane:
                raise AssertionError("Non-deterministic fast preflight prediction")
        observations.append({
            "index": i, "case_id": row["case_id"], "book_id": row["book_id"],
            "canonical_status": row["status"], "canonical_wall_ms": row["wall_ms"],
            "source_text": row["source_text"], "preflight": prediction.as_dict(),
            "preflight_is_not_gold": True,
        })
    return observations, _summarize_measurements(observations, samples_us)



def _spotcheck_indices(
    rows: list[Mapping[str, Any]], control_count: int,
) -> list[int]:
    """Deterministic, outcome-stratified spotcheck; NOT a grammatical gold set."""
    if control_count < 0:
        raise ValueError("control_count must be nonnegative")
    noncomplete = [i for i, r in enumerate(rows) if r["status"] != "complete"]
    complete = [i for i, r in enumerate(rows) if r["status"] == "complete"]
    if control_count > len(complete):
        raise ValueError("control_count exceeds canonical completions")
    # Uniform ordinal coverage among successes without selecting easy cases
    # or fitting a feature threshold to the same cohort.
    controls = [
        complete[(2*i + 1) * len(complete) // (2*control_count)]
        for i in range(control_count)
    ] if control_count else []
    return sorted(noncomplete + controls)


def lexical_spotcheck(
    diagnostics: list[Mapping[str, Any]],
    contexts: list[Mapping[str, Any]],
    wordnet_dir: Path,
    *,
    control_count: int = 26,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Charge the real lexical resources once; never invoke syntactic parsing."""
    resources = ParserResources.from_dir(
        ROOT / "data", wordnet_dict=wordnet_dir)
    build_lattice("John opened the box.", resources.lexicon)  # lexical warm-up
    outcomes = []
    indices = _spotcheck_indices(diagnostics, control_count)
    for index in indices:
        row, ctx = diagnostics[index], contexts[index]
        text = row["canonical_analysis_text"]
        start = perf_counter_ns()
        lattice = build_lattice(text, resources.lexicon)
        lattice_us = (perf_counter_ns() - start) / 1000
        start = perf_counter_ns()
        prediction = fast_preflight(
            text,
            lattice=lattice,
            preceding_semicolon_part=(
                ctx["context"]["semicolon_part_index"] > 0),
            transferred_prefix=row["canonical_synthetic_prefix"],
            transferred_suffix=row["canonical_synthetic_suffix"],
        )
        classification_us = (perf_counter_ns() - start) / 1000
        outcomes.append({
            "index": index, "case_id": row["case_id"],
            "canonical_status": row["status"],
            "analysis_text": text,
            "lexical_candidates": len(lattice.candidates),
            "lexical_preparation_us": round(lattice_us, 3),
            "classifier_existing_lattice_us": round(classification_us, 3),
            "lexical_preparation_is_additional_if_no_cached_lattice": True,
            "candidate_agreement_hypothesis": (
                "adjacent_candidate_agreement_hypothesis" in prediction.signals),
            "preflight": prediction.as_dict(),
        })
    lexical_times = [r["lexical_preparation_us"] for r in outcomes]
    candidate_times = [r["classifier_existing_lattice_us"] for r in outcomes]
    candidate_cases = [
        r["index"] for r in outcomes if r["candidate_agreement_hypothesis"]
    ]
    return outcomes, {
        "sample_size": len(outcomes),
        "all_26_current_noncompletions_reexamined": len([
            r for r in outcomes if r["canonical_status"] != "complete"
        ]),
        "success_controls": len([
            r for r in outcomes if r["canonical_status"] == "complete"
        ]),
        "candidate_conflict_hypothesis_indices": candidate_cases,
        "candidate_conflict_on_noncompletions": [
            r["index"] for r in outcomes if r["candidate_agreement_hypothesis"]
            and r["canonical_status"] != "complete"
        ],
        "candidate_conflict_on_success_controls": [
            r["index"] for r in outcomes if r["candidate_agreement_hypothesis"]
            and r["canonical_status"] == "complete"
        ],
        "lexical_build_median_us": round(median(lexical_times), 3) if lexical_times else 0.,
        "lexical_build_p95_us": _percentile(lexical_times, 95),
        "existing_lattice_preflight_median_us": (
            round(median(candidate_times), 3) if candidate_times else 0.
        ),
        "existing_lattice_preflight_p95_us": _percentile(candidate_times, 95),
        "not_a_gold_grammar_evaluation": True,
        "no_syntactic_parser_called": True,
        "no_automatic_parse_skips": True,
    }


def render(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    t = summary["surface_only_benchmark_us"]
    lines = [
        "# Cheap preflight — longitudinal research audit", "",
        "Surface-only preflight NEVER calls Parser.parse, constructs a lattice,",
        "loads WordNet or explores a grammar. This report retrospectively joins",
        "its predictions to the unmodified canonical 500-case run.", "",
        f"**Median** {t['median']} µs, **p95** {t['p95']} µs,",
        f"**p99** {t['p99']} µs per call in the repeated microbenchmark.",
        "These timings exclude imports, lexical lookup and file IO; the canonical",
        "per-sentence parser wall times are **not** directly comparable.", "",
        f"Complete: **{summary['canonical_complete']}** / 500; not complete: "
        f"**{summary['canonical_noncomplete']}**.",
        f"Review lane assigned: **{summary['review_lane_cases']}**; among them "
        f"**{summary['review_lane_noncomplete']}** unfinished and "
        f"**{summary['review_lane_complete']}** completed normally.", "",
        "**A review lane is NOT an error alert**. A completed parse is not",
        "ground-truth grammaticality, and a noncompleted parse is not an error.",
        "This audit cannot calculate grammatical false-positive rates.", "",
        "## Signal counts versus canonical completion", "",
        "| Signal | Incomplete | Complete |", "|---|---:|---:|",
    ]
    for signal, groups in summary["per_signal"].items():
        lines.append(
            f"| `{signal}` | {groups.get('noncomplete', 0)} | "
            f"{groups.get('complete', 0)} |"
        )
    lines.extend(["", "## Original 26 unresolved cases", "",
                  "| Index | Canonical outcome | Preflight lane | Surface signals |",
                  "|---:|---|---|---|"])
    for row in rows:
        if row["canonical_status"] == "complete":
            continue
        pred = row["preflight"]
        signals = ", ".join(pred["signals"]) or "none"
        lines.append(
            f"| {row['index']} | {row['canonical_status']} | "
            f"{pred['lane']} | {signals} |"
        )
    spot = summary.get("lexical_spotcheck")
    if spot:
        lines.extend([
            "", "## Optional lexical spotcheck — 26 failures + independent controls", "",
            f"Prepared lexical lattices: **{spot['sample_size']}**. "
            f"Lexical-build median: **{spot['lexical_build_median_us']} µs**, "
            f"p95: **{spot['lexical_build_p95_us']} µs**.",
            f"Preflight with existing lexical lattice: median "
            f"**{spot['existing_lattice_preflight_median_us']} µs**, "
            f"p95 **{spot['existing_lattice_preflight_p95_us']} µs**.",
            "These costs must be kept separate: building a lattice solely "
            "for triage is NOT free. A future parser integration must reuse "
            "the canonical lattice, not build a duplicate.",
            f"Candidate-local agreement hypotheses among failures: "
            f"{spot['candidate_conflict_on_noncompletions']}. "
            f"Among the sampled successful controls: "
            f"{spot['candidate_conflict_on_success_controls']}.",
            "A pair of adjacent lexical candidates never proves a "
            "subject-verb relationship or an author error.", "",
        ])
    lines.extend([
        "", "## Limits of interpretation", "",
        "- These are coarse, nonexclusive *surface* signals, not discovered",
        "  causal explanations of any of the 26 failures.",
        "- Absent surface signals do not imply a sentence is correct or easy.",
        "- Source adjacency is based on actual semicolon provenance, not a",
        "  guessed missing clause or rewritten quote.",
        "- A lexical candidate agreement hypothesis is available only when",
        "  the caller **already** has a lexical lattice. It is not included",
        "  in this surface-only timing or evaluation.",
        "- No automatic grammar relaxation, parser skipping, rescheduling",
        "  or classifier threshold fitting takes place.",
    ])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    digest = sha256(args.cohort.read_bytes()).hexdigest()
    if digest != EXPECTED_500_COHORT_SHA256:
        raise ValueError(f"Canonical cohort changed: {digest}")
    diagnostics = _load_rows(args.diagnostics)
    contexts = _load_rows(args.contexts)
    summary = json.loads(args.canonical_summary.read_text(encoding="utf8"))
    if summary.get("cohort_sha256") != digest:
        raise ValueError("Canonical diagnostic summary checksum mismatch")
    observations, result = audit(
        diagnostics, contexts, repetitions=args.repetitions)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.wordnet_dir is not None:
        lexical_rows, lexical_summary = lexical_spotcheck(
            diagnostics, contexts, args.wordnet_dir,
            control_count=args.lexical_controls,
        )
        result["lexical_spotcheck"] = lexical_summary
        (args.out_dir / "fast_preflight_lexical_spotcheck.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n"
                    for row in lexical_rows), encoding="utf8",
        )
        (args.out_dir / "fast_preflight_lexical_spotcheck_summary.json").write_text(
            json.dumps(lexical_summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf8",
        )
    (args.out_dir / "fast_preflight_cases.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n"
                for row in observations), encoding="utf8")
    (args.out_dir / "fast_preflight_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (args.out_dir / "fast_preflight_report.md").write_text(
        render(observations, result), encoding="utf8")
    print("FAST_PREFLIGHT_AUDIT", json.dumps({
        "complete": result["canonical_complete"],
        "noncomplete": result["canonical_noncomplete"],
        "review_lane_cases": result["review_lane_cases"],
        "review_lane_noncomplete": result["review_lane_noncomplete"],
        "noncomplete_without_early_signal": result["noncomplete_without_early_signal"],
        "microseconds": result["surface_only_benchmark_us"],
        "lexical_spotcheck": result.get("lexical_spotcheck"),
        "no_automatic_parser_changes": True,
    }, ensure_ascii=False), flush=True)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", required=True, type=Path)
    p.add_argument("--diagnostics", required=True, type=Path)
    p.add_argument("--contexts", required=True, type=Path)
    p.add_argument("--canonical-summary", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--repetitions", type=int, default=7)
    p.add_argument("--wordnet-dir", type=Path)
    p.add_argument("--lexical-controls", type=int, default=26)
    run(p.parse_args())


if __name__ == "__main__":
    main()
