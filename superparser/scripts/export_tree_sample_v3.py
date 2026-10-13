#!/usr/bin/env python3
"""Export 25 diagnostically useful syntax trees in a compact JSONL form."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import signal
from time import perf_counter
from typing import Any, Iterable

from seman_parser import Parser
from seman_parser.coverage import extract_sentences
from seman_parser.segmentation import tokenize


class SentenceTimeout(Exception):
    pass


def _alarm(_signum: int, _frame: Any) -> None:
    raise SentenceTimeout()


def _target(anchor: str, text: str) -> dict[str, Any]:
    parts = anchor.split(":", 4)
    if len(parts) != 5 or parts[0] != "lex":
        return {"anchor": anchor}
    start, end = int(parts[1]), int(parts[2])
    return {
        "span": [start, end],
        "category": parts[3],
        "text": text[start:end],
    }


def compact_tree(item: Any, text: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "category": item.category,
        "span": [item.start, item.end],
    }
    if item.rule_id:
        row["rule"] = item.rule_id
    if item.syntax.links:
        row["relations"] = [
            {
                "relation": link.relation,
                "child": link.child_index,
                "target": _target(link.target, text),
            }
            for link in item.syntax.links
        ]
    if item.children:
        row["children"] = [compact_tree(child, text) for child in item.children]
    else:
        row["text"] = text[item.start:item.end]
    return row


def complexity(case: Any) -> tuple[int, int, int]:
    words = [token.text.casefold() for token in tokenize(case.text)]
    markers = {
        "although", "because", "before", "after", "when", "while", "whether",
        "which", "who", "that", "if", "until", "unless", "and", "but", "or",
    }
    return (
        len(words) + 4 * case.text.count(",") + 3 * sum(word in markers for word in words),
        len(words),
        -case.index,
    )


def candidate_groups(cases: Iterable[Any], seed: int) -> dict[str, list[Any]]:
    cases = list(cases)
    rng = random.Random(seed)
    ordinary = [case for case in cases if 5 <= len(tokenize(case.text)) <= 30]
    rng.shuffle(ordinary)
    short = sorted(
        (case for case in cases if 4 <= len(tokenize(case.text)) <= 9),
        key=lambda case: (len(tokenize(case.text)), case.index),
    )
    complex_cases = sorted(
        (case for case in cases if 15 <= len(tokenize(case.text)) <= 55),
        key=complexity,
        reverse=True,
    )
    return {"random": ordinary, "short": short, "complex": complex_cases}


def export(args: argparse.Namespace) -> dict[str, Any]:
    parser = Parser.from_dir(args.data, cache_size=0)
    parser.parse("The woman opened a box.").result.best()
    signal.signal(signal.SIGALRM, _alarm)
    groups = candidate_groups(extract_sentences(args.corpus), args.seed)
    quotas = {"random": 15, "short": 5, "complex": 5}
    selected: list[dict[str, Any]] = []
    used: set[int] = set()
    used_texts: set[str] = set()
    attempted = 0

    for kind in ("random", "short", "complex"):
        accepted = 0
        for case in groups[kind]:
            if accepted >= quotas[kind]:
                break
            text_key = " ".join(case.text.casefold().split())
            if case.index in used or text_key in used_texts:
                continue
            attempted += 1
            started = perf_counter()
            signal.setitimer(signal.ITIMER_REAL, args.timeout)
            try:
                result = parser.parse(case.text).result
                best = result.best()
            except SentenceTimeout:
                continue
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            if not result.completed or best is None:
                continue
            selected.append({
                "record_type": "tree",
                "selection": kind,
                "index": case.index,
                "source_line": case.source_line,
                "text": case.text,
                "token_count": len(result.lattice.tokens),
                "parse_duration_ms": round((perf_counter() - started) * 1000, 4),
                "tree": compact_tree(best, case.text),
            })
            used.add(case.index)
            used_texts.add(text_key)
            accepted += 1
        if accepted != quotas[kind]:
            raise RuntimeError(f"only selected {accepted}/{quotas[kind]} {kind} trees")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "record_type": "metadata",
            "format": "seman2-compact-tree-sample-v4",
            "corpus": str(args.corpus),
            "seed": args.seed,
            "selection": quotas,
            "tree_fields": ["category", "span", "rule", "relations", "children", "text"],
            "excluded": ["wordnet", "scores", "recursive_provenance", "features"],
        }, ensure_ascii=False) + "\n")
        for row in selected:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        summary = {
            "record_type": "summary",
            "trees": len(selected),
            "attempted": attempted,
            "counts": {
                kind: sum(row["selection"] == kind for row in selected)
                for kind in quotas
            },
        }
        stream.write(json.dumps(summary, ensure_ascii=False) + "\n")
    temporary.replace(args.output)
    return summary


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--corpus", type=Path, default=root / "data" / "the_map_of_everything_nlp_novel.txt")
    cli.add_argument("--data", type=Path, default=root / "superparser" / "data")
    cli.add_argument("--output", type=Path, default=root / "output" / "tree_sample.v4.jsonl")
    cli.add_argument("--seed", type=int, default=20261013)
    cli.add_argument("--timeout", type=float, default=2.0)
    args = cli.parse_args()
    print(json.dumps(export(args), ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
