#!/usr/bin/env python3
"""Export one compact syntax record per sentence of the novel corpus.

The output is JSON Lines so it remains streamable.  Each sentence record
contains the source text, wall/phase timings, parser statistics, tokens, and
the best materialized syntax tree.  A final summary record closes the file.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import statistics
from time import perf_counter
from typing import Any, Sequence

from seman_parser import Parser
from seman_parser.coverage import extract_sentences


class SentenceTimeout(Exception):
    """Raised when one sentence exceeds the benchmark ceiling."""


def _alarm(_signum: int, _frame: Any) -> None:
    raise SentenceTimeout()


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def _distribution(values: Sequence[float]) -> dict[str, float | None]:
    return {
        "p50": _rounded(_percentile(values, 0.50)),
        "p90": _rounded(_percentile(values, 0.90)),
        "p95": _rounded(_percentile(values, 0.95)),
        "p99": _rounded(_percentile(values, 0.99)),
        "mean": _rounded(statistics.fmean(values)) if values else None,
        "max": _rounded(max(values)) if values else None,
    }


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _tokens(result: Any) -> list[dict[str, Any]]:
    return [
        {"index": token.index, "start": token.start, "end": token.end, "text": token.text}
        for token in result.lattice.tokens
    ]


def export(args: argparse.Namespace) -> dict[str, Any]:
    cases = extract_sentences(args.corpus)
    parser = Parser.from_dir(args.data, cache_size=0)
    parser.parse("The woman opened a box.")  # Warm WordNet; excluded from output.
    signal.signal(signal.SIGALRM, _alarm)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    completed = incomplete = timeouts = 0
    errors: list[dict[str, Any]] = []
    durations: list[float] = []
    run_started = perf_counter()

    with temporary.open("w", encoding="utf-8") as stream:
        metadata = {
            "record_type": "metadata",
            "format": "seman2-syntax-jsonl-v1",
            "corpus": str(args.corpus),
            "sentence_count": len(cases),
            "timeout_seconds": args.timeout,
            "parse_cache_enabled": False,
            "semantic_interpretation_requested": False,
        }
        stream.write(json.dumps(metadata, ensure_ascii=False) + "\n")

        for position, case in enumerate(cases, start=1):
            started = perf_counter()
            signal.setitimer(signal.ITIMER_REAL, args.timeout)
            try:
                report = parser.parse(case.text)
                duration_ms = (perf_counter() - started) * 1000
                signal.setitimer(signal.ITIMER_REAL, 0)
                result = report.result
                best = result.best()
                status = "complete" if result.completed else "incomplete"
                completed += int(result.completed)
                incomplete += int(not result.completed)
                durations.append(duration_ms)
                stats = dict(result.stats)
                row = {
                    "record_type": "sentence",
                    "index": case.index,
                    "source_line": case.source_line,
                    "text": case.text,
                    "status": status,
                    "duration_ms": round(duration_ms, 4),
                    "timings_ms": {
                        "lexical": stats.get("lexical_ms"),
                        "recognition": stats.get("recognition_ms"),
                        "best_tree": stats.get("best_ms"),
                    },
                    "tokens": _tokens(result),
                    "lexical_candidate_count": len(result.lattice.candidates),
                    "structure_stats": {
                        key: stats.get(key)
                        for key in (
                            "forest_nodes",
                            "structural_derivations",
                            "partial_states",
                            "partial_derivations",
                            "materialized_items",
                            "combinations_visited_for_best",
                            "budget_exceeded",
                        )
                    },
                    "best_analysis": best.as_dict() if best is not None else None,
                }
            except SentenceTimeout:
                signal.setitimer(signal.ITIMER_REAL, 0)
                timeouts += 1
                row = {
                    "record_type": "sentence",
                    "index": case.index,
                    "source_line": case.source_line,
                    "text": case.text,
                    "status": "timeout",
                    "duration_ms": round(args.timeout * 1000, 4),
                    "best_analysis": None,
                }
            except Exception as exc:  # Keep the corpus export exhaustive.
                signal.setitimer(signal.ITIMER_REAL, 0)
                error = {"type": type(exc).__name__, "message": str(exc)}
                errors.append({"index": case.index, **error})
                row = {
                    "record_type": "sentence",
                    "index": case.index,
                    "source_line": case.source_line,
                    "text": case.text,
                    "status": "error",
                    "duration_ms": round((perf_counter() - started) * 1000, 4),
                    "error": error,
                    "best_analysis": None,
                }
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            if position % 100 == 0 or position == len(cases):
                stream.flush()
                print(
                    f"{position}/{len(cases)} complete={completed} "
                    f"incomplete={incomplete} timeout={timeouts} errors={len(errors)}",
                    flush=True,
                )

        summary = {
            "record_type": "summary",
            "sentences": len(cases),
            "completed": completed,
            "incomplete": incomplete,
            "timeouts": timeouts,
            "errors": len(errors),
            "coverage_percent": round(100 * completed / len(cases), 4),
            "total_seconds": round(perf_counter() - run_started, 4),
            "duration_ms_returned": _distribution(durations),
            "error_details": errors,
        }
        stream.write(json.dumps(summary, ensure_ascii=False) + "\n")

    os.replace(temporary, args.output)
    return summary


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        "--corpus", type=Path,
        default=root / "data" / "the_map_of_everything_nlp_novel.txt",
    )
    argument_parser.add_argument(
        "--data", type=Path, default=root / "superparser" / "data",
    )
    argument_parser.add_argument(
        "--output", type=Path,
        default=root / "output" / "the_map_of_everything_syntax.jsonl",
    )
    argument_parser.add_argument("--timeout", type=float, default=1.0)
    args = argument_parser.parse_args()
    summary = export(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
