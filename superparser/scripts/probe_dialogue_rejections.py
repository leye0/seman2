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
# Independent positive controls and independently pinned marked-use cases.
STRICT_CONTROL_INDICES = (76, 244)
MARKED_COMPARISON_INDICES = (463, 480)



def map_trace_to_reference(trace: dict[str, Any] | None, prepared) -> dict[str, Any] | None:
    """Preserve analysis offsets, map only spans proven original by the corpus gateway."""
    if trace is None:
        return None
    mapped = dict(trace)

    def mapped_frame(frame: dict[str, Any], spans: tuple[tuple[str, str], ...]) -> dict[str, Any]:
        output = dict(frame)
        for source_field, target_field in spans:
            span = frame.get(source_field)
            if isinstance(span, list) and len(span) == 2:
                original = prepared.reference_span(*span)
                output[target_field] = list(original) if original is not None else None
                output[target_field + "_mapping"] = (
                    "exact" if original is not None else "unavailable")
        return output

    events = []
    for raw in trace.get("events", []):
        event = mapped_frame(raw, (
            ("analysis_span", "reference_span"),
            ("child_span", "child_reference_span"),
        ))
        if "request_chain" in raw:
            event["request_chain"] = [
                mapped_frame(frame, (("analysis_span", "reference_span"),))
                for frame in raw["request_chain"]
            ]
        events.append(event)
    mapped["events"] = events
    local = trace.get("validated_local_constituents")
    if isinstance(local, dict):
        local_mapped = dict(local)
        witnesses = []
        for witness in local.get("witnesses", []):
            item = mapped_frame(witness, (("analysis_span", "reference_span"),))
            item["children"] = [
                mapped_frame(child, (("analysis_span", "reference_span"),))
                for child in witness.get("children", [])
            ]
            witnesses.append(item)
        local_mapped["witnesses"] = witnesses
        mapped["validated_local_constituents"] = local_mapped
    mapped["reference_scope"] = "frozen_case_text_exact_only"
    return mapped


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


def comparison_targets(rows: list[dict[str, Any]]) -> list[tuple[int, str]]:
    """Fixed independent controls; verify their canonical status before replay."""
    if len(rows) != 500:
        raise ValueError("Comparator selection requires the canonical 500")
    targets: list[tuple[int, str]] = []
    for index in STRICT_CONTROL_INDICES:
        if rows[index]["index"] != index or rows[index]["status"] != "complete":
            raise ValueError(f"Strict successful control {index} is no longer complete")
        targets.append((index, "successful_strict_control"))
    for index in MARKED_COMPARISON_INDICES:
        if rows[index]["index"] != index or rows[index]["status"] == "complete":
            raise ValueError(f"Pinned marked comparison {index} is no longer a strict residual")
        targets.append((index, "marked_opt_in"))
    return targets


def comparison_summary(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cases": len(comparisons),
        "outcomes_by_kind": {
            kind: dict(sorted(Counter(x["replay_outcome"]
                                     for x in comparisons if x["kind"] == kind).items()))
            for kind in ("successful_strict_control", "marked_opt_in")
        },
        "positive_evidence_events_sampled": sum(
            event["stage"].startswith("positive_evidence_")
            for row in comparisons
            for trace in row.get("traces", {}).values()
            if isinstance(trace, dict)
            for event in trace.get("events", ())
        ),
        "paired_observation_only": True,
        "no_causal_or_sentence_level_error_inference": True,
    }


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
            priority = [e for e in trace["events"]
                        if e["stage"].startswith("positive_evidence_")
                        or e["stage"] == "child_context_exhausted"]
            # Present constraint/proof observations before ordinary pruning.
            preview = (priority + [e for e in trace["events"] if e not in priority])[:8]
            for sample in preview:
                compact = (
                    f"  - `{sample['stage']}` on `{sample['category']}` "
                    f"{sample['analysis_span']}"
                )
                if sample.get("reference_span") is not None:
                    compact += f"; original span {sample['reference_span']}"
                if sample.get("rule_id"):
                    compact += f", rule `{sample['rule_id']}`"
                if sample.get("direct_atom_conflicts"):
                    compact += ", explicit atoms " + json.dumps(
                        sample["direct_atom_conflicts"], ensure_ascii=False)
                if sample.get("missing_positive_features"):
                    compact += ", missing proof " + json.dumps(
                        sample["missing_positive_features"], ensure_ascii=False)
                elif sample.get("required_positive_features"):
                    compact += ", required proof " + json.dumps(
                        sample["required_positive_features"], ensure_ascii=False)
                if sample.get("request_chain"):
                    compact += ", request chain " + " → ".join(
                        f"{frame['category']} {frame['analysis_span']}" +
                        (f" via {frame['via_rule_id']}[{frame['via_child_index']}]"
                         if frame.get("via_rule_id") else "")
                        for frame in sample["request_chain"]
                    )
                out.append(compact)
            out.append("")
    return "\n".join(out) + "\n"



def replay_comparisons(
    parser: Parser, cases: list[dict[str, Any]],
    rows: list[dict[str, Any]], args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Separate controls and marked alternatives; original 500 remain unchanged."""
    results = []
    for index, kind in comparison_targets(rows):
        case, original = cases[index], rows[index]
        row: dict[str, Any] = {
            "index": index, "kind": kind, "case_id": original["case_id"],
            "canonical_status": original["status"],
            "analysis_text": original["canonical_analysis_text"],
            "source_text": original["source_text"],
            "marked_opt_in": kind == "marked_opt_in",
            "same_canonical_budgets": True,
            "independent_replay": True,
            "grammatical_fault_established": False,
            "traces": {},
        }
        signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
        try:
            prepared, _lattice, parsed = parse_corpus_case(
                parser, case,
                max_items=args.max_items,
                kbest_work_limit=args.kbest_work_limit,
                allow_marked_deviations=kind == "marked_opt_in",
                rejection_trace_limit=args.trace_limit,
            )
            if prepared.analysis_text != row["analysis_text"]:
                raise ValueError("Comparator quote-balanced text mismatch")
            stats = parsed.stats
            row["replay_outcome"] = classify(parsed.completed, stats)
            row["selected_rule"] = parsed.best().rule_id if parsed.completed else None
            row["selected_usage_deviation_count"] = (
                len(parsed.usage_deviations()) if parsed.completed else None
            )
            attempt = stats.get("dialogue_attempt") or {}
            for name, trace in (
                ("scoped_failed_dialogue_attempt", attempt.get("rejection_trace")),
                ("selected_or_fallback", stats.get("rejection_trace")),
            ):
                if isinstance(trace, dict):
                    row["traces"][name] = map_trace_to_reference(trace, prepared)
        except SentenceDeadline:
            row["replay_outcome"] = "deadline_censored"
            row["selected_rule"] = None
            row["selected_usage_deviation_count"] = None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        results.append(row)
    return results


def render_comparisons(rows: list[dict[str, Any]]) -> str:
    out = [
        "# Controls and marked alternatives — independent diagnostic runs", "",
        "Cases 76 and 244 are strict-parser *success controls*. Cases 463 and",
        "480 are separately parsed in opt-in marked mode. No canonical status",
        "or selected tree in the first 500-case pass is replaced.", "",
        "| Index | Comparison | Canonical | Replay | Selected rule | Attested deviations |",
        "|---:|---|---|---|---|---:|",
    ]
    for row in rows:
        out.append(
            f"| {row['index']} | {row['kind']} | {row['canonical_status']} | "
            f"{row['replay_outcome']} | {row['selected_rule'] or '—'} | "
            f"{row['selected_usage_deviation_count'] if row['selected_usage_deviation_count'] is not None else '—'} |"
        )
    out += [
        "", "All rejections above and in the JSONL are **candidate-local**.",
        "Do not interpret a higher/lower rejection count as a causal proof:",
        "strict and marked grammars need not explore identical alternatives.",
    ]
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
                scoped = dict(stats.get("dialogue_attempt") or {})
                if "rejection_trace" in scoped:
                    scoped["rejection_trace"] = map_trace_to_reference(
                        scoped["rejection_trace"], prepared)
                record["scoped_dialogue"] = scoped
                record["ordinary_fallback"] = {
                    "structural_root_nodes": int(stats.get("structural_root_nodes", 0)),
                    "rejection_trace": map_trace_to_reference(
                        stats.get("rejection_trace"), prepared),
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

    # The original signal handler was restored after the seven ordinary
    # replays. Explicitly install it again for the four separate comparators.
    control_handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        comparators = replay_comparisons(parser, all_cases, rows, args)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, control_handler)
    summary = summary_for(records)
    summary["comparisons"] = comparison_summary(comparators)
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
    (args.out_dir / "dialogue_rejection_comparators.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in comparators),
        encoding="utf8",
    )
    (args.out_dir / "dialogue_rejection_comparators.md").write_text(
        render_comparisons(comparators), encoding="utf8",
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
