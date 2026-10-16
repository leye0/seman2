"""A/B/C: actual Seman2 compiled Left-to-Right reader with optional VerbNet.

No fallback to packed-forest production Parser; these are *single-path*
completion measurements, not grammatical accuracy or gold syntax judgments.
Can reuse full_corpus_report + .json.gz index built by benchmark_verbnet_lr.py.

From repo root (WordNet dictionary must be available):
  PYTHONPATH=superparser .venv-popper/bin/python superparser/scripts/benchmark_verbnet_reader.py \
      --index superparser/research/verbnet_lr/verbnet34.compiled.json.gz \
      --wordnet-dir /path/to/WordNet-3.0/dict
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
from time import perf_counter

from research.verbnet_lr import read_index
from research.verbnet_lr.tree_evidence import observe_vp_frames
from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader

ROOT = Path(__file__).resolve().parents[1]


def quantiles(values):
    values = sorted(values)
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    return {name: round(values[min(len(values) - 1, int((len(values) - 1) * q))], 5)
            for name, q in (("p50", .50), ("p95", .95), ("p99", .99))}


def sentence_cases(corpus: Path, max_cases: int):
    by_split = defaultdict(list)
    for line in corpus.read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            by_split[str(case.get("split", "other"))].append(case)
    # Represent dev/validation/holdout without evaluating *only* dev.
    groups = [iter(by_split[split]) for split in sorted(by_split)]
    chosen = []
    while groups and len(chosen) < max_cases:
        remaining = []
        for group in groups:
            try:
                chosen.append(next(group))
            except StopIteration:
                continue
            remaining.append(group)
            if len(chosen) >= max_cases:
                break
        groups = remaining
    return chosen


def trace(result):
    return [(e.action, e.expected, e.detail) for e in result.outcome.events
            if e.action in {"CONSUME", "COMPLETE"}]


def syntax_assertions(case, result):
    """Score explicit gold assertions; completion alone is not correctness."""
    required = set(case.get("required", ()))
    forbidden = set(case.get("forbidden", ()))
    pos = case.get("pos", {})
    constituents = case.get("constituents", ())
    checks = bool(required or forbidden or pos or constituents)
    if not result.complete:
        return {"has_assertions": checks, "pass": False if checks else None,
                "checks": {"complete": False}}
    completes = {e.detail for e in result.outcome.events if e.action == "COMPLETE"}
    consumed = {(e.word.casefold(), e.expected)
                for e in result.outcome.events if e.action == "CONSUME"}
    tree_spans = set()
    def visit(item):
        tree_spans.add((item.category, case["text"][item.start:item.end].casefold()))
        for child in getattr(item, "children", ()):
            visit(child)
    if result.item is not None:
        visit(result.item)
    scored = {
        "required_rules": all(name in completes for name in required),
        "forbidden_rules": all(name not in completes for name in forbidden),
        "lexical_pos": all((surface.casefold(), category) in consumed for surface, category in pos.items()),
        "constituents": all((category, surface.casefold()) in tree_spans
                            for category, surface in constituents),
    }
    return {"has_assertions": checks, "pass": all(scored.values()) if checks else None,
            "checks": scored, "required_rules": sorted(required),
            "missing_required": sorted(required - completes)}


def run(index_file: str, *, wordnet_dir: str | None, max_cases: int,
        repetitions: int, corpus: Path) -> dict:
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    index = read_index(index_file)
    machines = {
        "A_baseline": SemanCompiledReader(resources),
        "B_lemma_hints": SemanCompiledReader(resources, verbnet_index=index, verbnet_mode="lemma"),
        "C_sense_hints": SemanCompiledReader(resources, verbnet_index=index, verbnet_mode="exact"),
        "D_structural2": SemanCompiledReader(resources, structural_lookahead=2),
        "E_structural2_sense": SemanCompiledReader(
            resources, verbnet_index=index, verbnet_mode="exact", structural_lookahead=2),
        "F_structural3": SemanCompiledReader(resources, structural_lookahead=3),
        "G_structural3_sense": SemanCompiledReader(
            resources, verbnet_index=index, verbnet_mode="exact", structural_lookahead=3),
        "H_checkpoint1": SemanCompiledReader(resources, checkpoint_budget=1),
        "I_checkpoint3": SemanCompiledReader(resources, checkpoint_budget=3),
        "J_checkpoint3_verbnet": SemanCompiledReader(
            resources, verbnet_index=index, verbnet_mode="exact", checkpoint_budget=3),
        "K_lazy_checkpoint1": SemanCompiledReader(
            resources, checkpoint_budget=1, lazy_checkpoints=True),
        "L_lazy_checkpoint3": SemanCompiledReader(
            resources, checkpoint_budget=3, lazy_checkpoints=True),
        "M_lazy_checkpoint2": SemanCompiledReader(
            resources, checkpoint_budget=2, lazy_checkpoints=True),
    }
    cases = sentence_cases(corpus, max_cases)
    if not cases:
        raise RuntimeError("No sentences to benchmark")
    raw = {key: [] for key in machines}
    results = {key: {} for key in machines}
    # Warm the lexical cache and readers with all test sentences, not merely
    # the first mode. Do not time this. Full parser complexity remains bounded
    # by compiled reader's own event limits.
    for case in cases:
        for machine in machines.values():
            machine.parse(case["text"])
    # Rotate mode order to avoid systematic CPU/cache bias.
    modes = tuple(machines)
    for repeat in range(repetitions):
        for i, case in enumerate(cases):
            rotate = (i + repeat) % len(modes)
            ordered = modes[rotate:] + modes[:rotate]
            for mode in ordered:
                t = perf_counter()
                item = machines[mode].parse(case["text"])
                total_ms = (perf_counter() - t) * 1000
                # Post-parse diagnosis happens OUTSIDE the timing window.
                # Never affects the chosen structure, rank or latency figures.
                observations = observe_vp_frames(item.item, index) if item.complete else ()
                structural_evidence = [
                    {"lemma": ob.lemma, "rule": ob.rule_id,
                     "events": list(ob.events), "status": ob.status,
                     "confidence": ob.confidence,
                     "matching_frames": ob.matching_frames}
                    for ob in observations
                ]
                counters = item.outcome.counters
                record = {
                    "id": case["id"], "split": case.get("split", "other"),
                    "complete": bool(item.complete),
                    "reason": item.outcome.reason if not item.complete else "",
                    "total_ms": round(total_ms, 5),
                    "lexical_ms": round(item.lexical_ms, 5),
                    "reading_ms": round(item.reading_ms, 5),
                    "materialize_ms": round(item.materialization_ms, 5),
                    "consumptions": counters.get("consumptions", 0),
                    "unifications": counters.get("unifications", 0),
                    "events": counters.get("events", 0),
                    "verbnet_scoring_calls": counters.get("verbnet_scoring_calls", 0),
                    "verbnet_positive_hints": counters.get("verbnet_positive_hints", 0),
                    "two_token_probes": counters.get("two_token_probes", 0),
                    "two_token_witnesses": counters.get("two_token_witnesses", 0),
                    "min_yield_rejections": counters.get("min_yield_rejections", 0),
                    "edge_witness_hits": counters.get("edge_witness_hits", 0),
                    "edge_witness_probes": counters.get("edge_witness_probes", 0),
                    "checkpoint_attempts": counters.get("checkpoint_attempts", 1),
                    "checkpoint_replays": counters.get("checkpoint_replays", 0),
                    "checkpoint_options_seen": counters.get("checkpoint_options_seen", 0),
                    "trace": trace(item),
                    "last_events": [event.as_dict() for event in item.outcome.events[-12:]],
                    "gold": syntax_assertions(case, item),
                    "verbnet_vp_observations": structural_evidence,
                }
                raw[mode].append(record)
                if repeat == 0:
                    results[mode][case["id"]] = record
    summary = {}
    for mode, entries in raw.items():
        successes = sum(v["complete"] for v in entries)
        gold_entries = [v for v in entries if v["gold"]["has_assertions"]]
        observations = [(entry, obs)
                        for entry in entries
                        for obs in entry["verbnet_vp_observations"]]
        summary[mode] = {
            "evaluations": len(entries),
            "complete": successes,
            "explicit_gold_assertion_cases": len(gold_entries),
            "explicit_gold_assertion_passed": sum(v["gold"]["pass"] is True for v in gold_entries),
            "verbnet_tree_evidence": {
                "vp_observations": len(observations),
                "status": dict(Counter(obs["status"] for _, obs in observations)),
                "confidence": dict(Counter(obs["confidence"] for _, obs in observations)),
                "attested_with_explicit_gold_pass": sum(
                    obs["status"] == "ATTESTED" and entry["gold"]["pass"] is True
                    for entry, obs in observations),
                "attested_with_explicit_gold_fail": sum(
                    obs["status"] == "ATTESTED" and entry["gold"]["pass"] is False
                    for entry, obs in observations),
            },
            "coverage_percent": round(100 * successes / len(entries), 2),
            "total_ms": quantiles([v["total_ms"] for v in entries]),
            "reading_ms": quantiles([v["reading_ms"] for v in entries]),
            "mean_unifications": round(statistics.mean(v["unifications"] for v in entries), 3),
            "mean_events": round(statistics.mean(v["events"] for v in entries), 3),
            "verbnet_scoring_calls": sum(v["verbnet_scoring_calls"] for v in entries),
            "verbnet_positive_hints": sum(v["verbnet_positive_hints"] for v in entries),
            "two_token_probes": sum(v["two_token_probes"] for v in entries),
            "two_token_witnesses": sum(v["two_token_witnesses"] for v in entries),
            "min_yield_rejections": sum(v["min_yield_rejections"] for v in entries),
            "edge_witness_hits": sum(v["edge_witness_hits"] for v in entries),
            "edge_witness_probes": sum(v["edge_witness_probes"] for v in entries),
            "checkpoint_replays": sum(v["checkpoint_replays"] for v in entries),
            "checkpoint_attempts": sum(v["checkpoint_attempts"] for v in entries),
            "checkpoint_options_seen": sum(v["checkpoint_options_seen"] for v in entries),
            "stop_reasons": dict(Counter(v["reason"] for v in entries if not v["complete"])),
        }
    diffs = {}
    for mode in modes[1:]:
        changed = []
        for case in cases:
            baseline = results["A_baseline"][case["id"]]
            guided = results[mode][case["id"]]
            if baseline["complete"] != guided["complete"] or baseline["trace"] != guided["trace"]:
                changed.append({
                    "id": case["id"], "split": case.get("split", "other"),
                    "text": case["text"],
                    "baseline_complete": baseline["complete"],
                    "guided_complete": guided["complete"],
                    "baseline_reason": baseline["reason"],
                    "guided_reason": guided["reason"],
                    "baseline_gold": baseline["gold"],
                    "guided_gold": guided["gold"],
                    "baseline_trace": baseline["trace"],
                    "guided_trace": guided["trace"],
                })
        diffs[mode] = {"changed_count": len(changed), "changes": changed}
    failures = []
    for case in cases:
        record = results["A_baseline"][case["id"]]
        if not record["complete"] and len(failures) < 24:
            failures.append({"id": case["id"], "text": case["text"],
                             "reason": record["reason"],
                             "gold": record["gold"],
                             "last_events": record["last_events"],
                             "trace": record["trace"]})
    split_metrics = {}
    for mode in modes:
        split_metrics[mode] = {}
        for split in sorted({case.get("split", "other") for case in cases}):
            subset = [results[mode][case["id"]] for case in cases
                      if case.get("split", "other") == split]
            split_metrics[mode][split] = {
                "cases": len(subset),
                "complete": sum(r["complete"] for r in subset),
                "explicit_gold_passed": sum(r["gold"]["pass"] is True for r in subset),
                "verbnet_vp_observations": sum(len(r["verbnet_vp_observations"]) for r in subset),
                "attested_vp_observations": sum(
                    obs["status"] == "ATTESTED" for r in subset
                    for obs in r["verbnet_vp_observations"]),
            }
    baseline_evidence = [
        {"id": case["id"], "split": case.get("split", "other"),
         "text": case["text"],
         "complete": results["A_baseline"][case["id"]]["complete"],
         "explicit_gold_pass": results["A_baseline"][case["id"]]["gold"]["pass"],
         "verbnet_vp_observations": results["A_baseline"][case["id"]]["verbnet_vp_observations"]}
        for case in cases
        if results["A_baseline"][case["id"]]["verbnet_vp_observations"]
    ]
    return {
        "schema": 1,
        "per_split": split_metrics,
        "baseline_verbnet_tree_evidence_by_case": baseline_evidence,
        "baseline_failure_diagnostics": failures,
        "method": "A/B/C/D/E/F/G/H/I/J/K/L/M compiled left-to-right Seman2 reader; fixed lexical resource and corpus",
        "cases": len(cases), "repetitions": repetitions, "splits": dict(Counter(c.get("split") for c in cases)),
        "index_lemmas": index.lemmas(),
        "summary": summary, "diffs": diffs,
        "limits": [
            "A path can stop without proving the sentence ungrammatical",
            "Positive corpus completion is not gold structural accuracy",
            "The lexical lookahead can only *rank*, never reject",
            "VerbNet VP tree evidence is post-parse positive support, never gold structural truth",
            "No production parser or packed forest was invoked",
            "Checkpoint modes may replay from the beginning, cost included in wall time",
            "Checkpoint attempts are strictly budgeted; only the final tree is retained",
            "Full-parser 5 ms target cannot be inferred from trie lookup timings",
            "Mixed WordNet lexical cache is warmed before A/B/C measurements",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True)
    parser.add_argument("--wordnet-dir")
    parser.add_argument("--cases", default=str(ROOT / "data" / "syntax_correctness_validation.jsonl"))
    parser.add_argument("--max-cases", type=int, default=36)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--report", default=str(ROOT / "research" / "verbnet_lr" / "reader_ablation.json"))
    args = parser.parse_args()
    if args.max_cases < 1 or args.repetitions < 1:
        parser.error("max-cases and repetitions must be positive")
    report = run(args.index, wordnet_dir=args.wordnet_dir, max_cases=args.max_cases,
                 repetitions=args.repetitions, corpus=Path(args.cases))
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": args.report, "cases": report["cases"],
                      "summary": report["summary"],
                      "changes": {k: v["changed_count"] for k, v in report["diffs"].items()}},
                     indent=2))


if __name__ == "__main__":
    main()
