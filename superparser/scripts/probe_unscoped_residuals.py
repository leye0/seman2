"""Replay unscoped structural residuals for bounded local proofs, never root fixes.

Runs only after the unchanged canonical 500. Resource-censored examples
remain censored. All replays use parse_corpus_case -> Parser.parse and the
same canonical parse budgets, plus separate opt-in local evidence sampling.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import signal

ROOT = Path(__file__).resolve().parents[1]


def eligible_unscoped_residuals(rows: list[dict]) -> list[dict]:
    """Prove selection from canonical evidence, never from presumed faults."""
    return [row for row in rows
            if row.get("status") in {"no_structural_root", "roots_without_valid_analysis"}
            and int((row.get("dialogue_attempt") or {}).get("structural_root_nodes", 0)) == 0]


def summary_for(records: list[dict]) -> dict:
    return {
        "schema": "seman2-unscoped-local-probe-v1",
        "cases": len(records),
        "replay_outcomes": dict(sorted(Counter(r["replay_outcome"] for r in records).items())),
        "independent_witnesses": sum(
            ((r.get("rejection_trace") or {}).get("independent_local_probe") or {})
            .get("sampled_local_constituents", 0)
            for r in records),
        "cases_with_independent_witnesses": sum(
            ((r.get("rejection_trace") or {}).get("independent_local_probe") or {})
            .get("sampled_local_constituents", 0) > 0
            for r in records),
        "resource_censored_baseline_excluded": True,
        "canonical_completion_and_budgets_unchanged": True,
        "not_a_grammatical_fault_or_global_failure_proof": True,
    }


def render(records: list[dict], summary: dict) -> str:
    lines = [
        "# Independent local proofs for non-dialogue structural residuals", "",
        "Only baseline `no_structural_root` and `roots_without_valid_analysis`",
        "with **no valid scoped dialogue root** are replayed. The original",
        "500-case cohort and resource-censored statuses remain unchanged.", "",
        f"Cases: {summary['cases']}; independent witnesses: "
        f"{summary['independent_witnesses']}; cases with witnesses: "
        f"{summary['cases_with_independent_witnesses']}.", "",
    ]
    for r in records:
        local = (r.get("rejection_trace") or {}).get("independent_local_probe") or {}
        lines += [f"## #{r['index']} — `{r['case_id']}`", "",
                  f"> {r['source_text'].replace(chr(10), ' ')}", "",
                  f"Canonical: `{r['canonical_status']}`; diagnostic replay: "
                  f"`{r['replay_outcome']}`; local witnesses: "
                  f"{local.get('sampled_local_constituents', 0)}.", ""]
        for witness in local.get("witnesses", [])[:8]:
            lines.append(f"- `{witness['category']}` `{witness['rule_id']}` "
                         f"analysis {witness['analysis_span']}; "
                         f"reference {witness.get('reference_span')}; "
                         f"children {len(witness['children'])}")
        lines.append("")
    lines += ["No sampled subtree proves its matrix attachment, a whole",
              "sentence analysis, an author's intention or a grammatical error."]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict:
    # Import the full corpus/parser dependencies only for actual replays;
    # deterministic target selection and evidence summaries are pure.
    from research.verbnet_lr.corpus_pipeline import parse_corpus_case
    from scripts.diagnose_novel_parses import (
        EXPECTED_500_COHORT_SHA256, SentenceDeadline, _deadline, classify,
        select_cases,
    )
    from scripts.probe_dialogue_rejections import map_trace_to_reference
    from seman_parser.engine import Parser, ParserResources
    if not 1 <= args.trace_limit <= 100:
        raise ValueError("trace_limit must be in 1..100")
    if any(value <= 0 for value in (
            args.max_cases, args.max_items, args.kbest_work_limit, args.deadline_seconds)):
        raise ValueError("All parser budgets and maximum cases must be positive")
    if sha256(args.cohort.read_bytes()).hexdigest() != EXPECTED_500_COHORT_SHA256:
        raise ValueError("Frozen 500-case cohort checksum mismatch")
    all_cases, _ = select_cases(500)
    diagnostics = [json.loads(line) for line in args.diagnostics.read_text(encoding="utf8")
                   .splitlines() if line.strip()]
    if len(all_cases) != 500 or len(diagnostics) != 500:
        raise ValueError("Expected 500 frozen cases and canonical diagnostic rows")
    for i, (case, row) in enumerate(zip(all_cases, diagnostics)):
        if (row.get("index") != i or row.get("book_id") != case["book_id"]
                or row.get("ordinal") != case["ordinal"]
                or row.get("sentence") != case["text"]
                or row.get("source_text") != case["source_text"]):
            raise ValueError(f"Unscoped replay cohort mismatch at {i}")
    targets = eligible_unscoped_residuals(diagnostics)
    if len(targets) > args.max_cases:
        raise ValueError(f"Too many unscoped residual targets: {len(targets)}")
    parser = Parser(ParserResources.from_dir(
        ROOT / "data", wordnet_dict=args.wordnet_dir), cache_size=0,
        max_items=args.max_items)
    parser.parse("John opened the box.")  # warm lexical lookup, not a cohort row
    results = []
    old_handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        for row in targets:
            case = all_cases[row["index"]]
            record = {
                "index": row["index"], "case_id": row["case_id"],
                "source_text": row["source_text"],
                "analysis_text": row["canonical_analysis_text"],
                "canonical_status": row["status"],
                "independent_replay": True,
                "same_canonical_budgets": True,
                "grammatical_fault_established": False,
            }
            signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
            try:
                prepared, lattice, parsed = parse_corpus_case(
                    parser, case, max_items=args.max_items,
                    kbest_work_limit=args.kbest_work_limit,
                    rejection_trace_limit=args.trace_limit,
                )
                if prepared.analysis_text != record["analysis_text"]:
                    raise ValueError("Canonical quote-balanced text mismatch")
                record["replay_outcome"] = classify(parsed.completed, parsed.stats)
                record["rejection_trace"] = map_trace_to_reference(
                    parsed.stats.get("rejection_trace"), prepared, lattice)
            except SentenceDeadline:
                record["replay_outcome"] = "deadline_censored"
                record["rejection_trace"] = None
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            results.append(record)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    summary = summary_for(results)
    summary["target_indices"] = [r["index"] for r in results]
    summary["cohort_sha256"] = EXPECTED_500_COHORT_SHA256
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "unscoped_local_probes.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results),
        encoding="utf8")
    (args.out_dir / "unscoped_local_probe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    (args.out_dir / "unscoped_local_probe_report.md").write_text(
        render(results, summary), encoding="utf8")
    print("UNSCOPED_LOCAL_PROBE_SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    parser.add_argument("--wordnet-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--max-cases", type=int, default=16)
    parser.add_argument("--max-items", type=int, default=50000)
    parser.add_argument("--kbest-work-limit", type=int, default=500000)
    parser.add_argument("--deadline-seconds", type=float, default=10)
    parser.add_argument("--trace-limit", type=int, default=48)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
