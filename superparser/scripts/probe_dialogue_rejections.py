"""Replay scoped-dialogue residuals with bounded k-best rejection evidence.

The canonical 500-case run is untouched. A second, separate run uses the
same public Parser.parse through parse_corpus_case on original balanced cases.
A rejection of one candidate is NOT a proof of an ill-formed sentence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import signal
from typing import Any

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import (
    EXPECTED_500_COHORT_SHA256, SentenceDeadline, _deadline, classify, select_cases,
)
from seman_parser.engine import Parser, ParserResources

ROOT = Path(__file__).resolve().parents[1]


def eligible_dialogue_residuals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose by *observed* scoped roots, never by presumed grammar mistakes."""
    result = []
    for row in rows:
        scoped = row.get("dialogue_attempt")
        if (row.get("status") != "complete"
                and isinstance(scoped, dict)
                and int(scoped.get("structural_root_nodes", 0)) > 0):
            result.append(row)
    return result


def summary_for(records: list[dict[str, Any]]) -> dict[str, Any]:
    sampled = []
    for row in records:
        for scope in ("scoped_dialogue", "ordinary_fallback"):
            trace = row.get(scope, {}).get("rejection_trace")
            if isinstance(trace, dict):
                sampled.extend(trace.get("events", []))
    return {
        "schema": "seman2-dialogue-rejection-probe-v1",
        "cases": len(records),
        "replay_outcomes": dict(sorted(Counter(
            record["replay_outcome"] for record in records).items())),
        "events_sampled": len(sampled),
        "direct_atom_conflicts_sampled": sum(
            len(event.get("direct_atom_conflicts", ())) for event in sampled),
        "stage_counts_in_sample": dict(sorted(Counter(
            event["stage"] for event in sampled).items())),
        "not_a_grammar_error_classifier": True,
        "not_a_causal_proof": True,
        "not_exhaustive": True,
    }


def render(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    out = [
        "# Scoped dialogue rejection probes — observational only", "",
        "These are separate diagnostic replays, never changes to the frozen",
        "500-case canonical completion score. Every event concerns one attempted",
        "derivation; rejected lexical readings are normal and do not establish",
        "a grammatical error or a unique cause of noncompletion.", "",
        f"Cases replayed: {summary['cases']}; sampled observations: "
        f"{summary['events_sampled']}; local atom conflicts in the sample: "
        f"{summary['direct_atom_conflicts_sampled']}.", "",
    ]
    for row in records:
        out.extend([
            f"## Case {row['index']} — {row['case_id']}", "",
            f"Canonical: `{row['canonical_status']}`; replay: "
            f"`{row['replay_outcome']}`.", "",
            f"> {row['source_text'].replace(chr(10), ' ')}", "",
        ])
        for scope in ("scoped_dialogue", "ordinary_fallback"):
            value = row.get(scope, {})
            trace = value.get("rejection_trace")
            if not isinstance(trace, dict):
                out.extend([f"- {scope}: no completed trace in this replay.", ""])
                continue
            out.append(
                f"- {scope}: {trace['observed_events']} observed attempts, "
                f"{trace['sampled_events']} retained; truncated="
                f"{trace['truncated']}; exhaustive=false."
            )
            for sample in trace["events"][:5]:
                compact = (
                    f"  - `{sample['stage']}` on `{sample['category']}` "
                    f"{sample['analysis_span']}"
                )
                if sample.get("rule_id"):
                    compact += f", rule `{sample['rule_id']}`"
                if sample.get("direct_atom_conflicts"):
                    compact += ", explicit atoms " + json.dumps(
                        sample["direct_atom_conflicts"], ensure_ascii=False)
                out.append(compact)
            out.append("")
    return "\n".join(out) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not 1 <= args.trace_limit <= 100:
        raise ValueError("trace_limit must be in 1..100")
    if args.deadline_seconds <= 0 or args.max_items <= 0 or args.kbest_work_limit <= 0:
        raise ValueError("Parsing budgets and deadline must be positive")
    if sha256(args.cohort.read_bytes()).hexdigest() != EXPECTED_500_COHORT_SHA256:
        raise ValueError("Frozen 500-case cohort checksum mismatch")

    all_cases, _ = select_cases(500)
    rows = [json.loads(line) for line in args.diagnostics.read_text(
        encoding="utf8").splitlines() if line.strip()]
    if len(all_cases) != 500 or len(rows) != 500:
        raise ValueError("Expected exactly 500 canonical cases")
    for index, (case, row) in enumerate(zip(all_cases, rows)):
        if (row.get("index") != index
                or row.get("book_id") != case["book_id"]
                or row.get("ordinal") != case["ordinal"]
                or row.get("sentence") != case["text"]
                or row.get("source_text") != case["source_text"]):
            raise ValueError(f"Replayed cohort diverges at index {index}")
    targets = eligible_dialogue_residuals(rows)
    if len(targets) > args.max_cases:
        raise ValueError(f"Too many scoped dialogue residuals: {len(targets)}")
    parser = Parser(ParserResources.from_dir(
        ROOT / "data", wordnet_dict=args.wordnet_dir), cache_size=0,
        max_items=args.max_items)
    parser.parse("John opened the box.")  # warm lexical lookup
    records = []
    old_handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        for row in targets:
            index = row["index"]
            case = all_cases[index]
            record = {
                "index": index, "case_id": row["case_id"],
                "canonical_status": row["status"],
                "source_text": row["source_text"],
                "analysis_text": row["canonical_analysis_text"],
                "canonical_dialogue_root_nodes": int(
                    row["dialogue_attempt"]["structural_root_nodes"]),
                "independent_replay": True,
                "same_canonical_budgets": True,
                "grammatical_fault_established": False,
            }
            signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
            try:
                prepared, _lattice, parsed = parse_corpus_case(
                    parser, case, max_items=args.max_items,
                    kbest_work_limit=args.kbest_work_limit,
                    rejection_trace_limit=args.trace_limit,
                )
                if prepared.analysis_text != record["analysis_text"]:
                    raise ValueError("Quoted analysis text differs from canonical")
                stats = parsed.stats
                record["replay_outcome"] = classify(parsed.completed, stats)
                record["scoped_dialogue"] = stats.get("dialogue_attempt") or {}
                record["ordinary_fallback"] = {
                    "structural_root_nodes": int(stats.get("structural_root_nodes", 0)),
                    "rejection_trace": stats.get("rejection_trace"),
                }
            except SentenceDeadline:
                record["replay_outcome"] = "deadline_censored"
                record["scoped_dialogue"] = {}
                record["ordinary_fallback"] = {}
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            records.append(record)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)

    summary = summary_for(records)
    summary["target_indices"] = [record["index"] for record in records]
    summary["cohort_sha256"] = EXPECTED_500_COHORT_SHA256
    summary["original_500_reparsed"] = False
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "dialogue_rejection_probes.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        encoding="utf8",
    )
    (args.out_dir / "dialogue_rejection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (args.out_dir / "dialogue_rejection_report.md").write_text(
        render(records, summary), encoding="utf8",
    )
    print("DIALOGUE_REJECTION_PROBE_SUMMARY",
          json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--wordnet-dir", type=Path, required=True)
    parser.add_argument("--max-items", type=int, default=50000)
    parser.add_argument("--kbest-work-limit", type=int, default=500000)
    parser.add_argument("--deadline-seconds", type=float, default=10)
    parser.add_argument("--trace-limit", type=int, default=48)
    parser.add_argument("--max-cases", type=int, default=12)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
