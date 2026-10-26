#!/usr/bin/env python3
"""Evaluate explicit syntactic assertions, separately by annotation family."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PARSER_ROOT = Path(os.environ.get("SUPERPARSER_PYTHON_ROOT", ROOT))
sys.path.insert(0, str(PARSER_ROOT))

from seman_parser import Parser  # noqa: E402


def walk(item: Any) -> Iterable[Any]:
    yield item
    for child in item.children:
        yield from walk(child)


def rule_ids(item: Any) -> set[str]:
    return {node.rule_id for node in walk(item) if node.rule_id}


def anchor_lemma(anchor: str | None) -> str | None:
    if not anchor or not anchor.startswith("lex:"):
        return None
    parts = anchor.split(":", 4)
    return parts[4].casefold() if len(parts) == 5 else None


def main_predicate(item: Any) -> str | None:
    anchors = item.syntax.anchors
    for name in ("main", "event", "predicate"):
        lemma = anchor_lemma(anchors.get(name))
        if lemma:
            return lemma
    # Some coordination/subordination rules export the head only on a child.
    for child in item.children:
        lemma = main_predicate(child)
        if lemma:
            return lemma
    return None


def matches_structure(item: Any, pattern: dict[str, Any], text: str) -> bool:
    """Match an ordered subtree without depending on production rule names.

    Children, when specified, are the exact immediate children: a matching
    word elsewhere in the sentence cannot satisfy an attachment assertion.
    Lexical lemmas and features are checked on the selected analysis only.
    """
    unknown = set(pattern) - {"category", "surface", "lemma", "features", "children"}
    if unknown:
        raise ValueError(f"Unknown structure assertion fields: {sorted(unknown)}")
    category = pattern.get("category")
    if category is not None:
        categories = category if isinstance(category, list) else [category]
        if item.category not in categories:
            return False
    if "surface" in pattern and text[item.start:item.end].casefold() != pattern["surface"].casefold():
        return False
    if "lemma" in pattern:
        lexical = item.lexical_candidate
        if lexical is None or lexical.lemma.casefold() != pattern["lemma"].casefold():
            return False
    features = item.features.as_dict()
    if any(features.get(key) != value for key, value in pattern.get("features", {}).items()):
        return False
    if "children" in pattern:
        children = pattern["children"]
        if len(item.children) != len(children):
            return False
        if not all(matches_structure(child, expected, text)
                   for child, expected in zip(item.children, children)):
            return False
    return True


def checks_for(item: Any, row: dict[str, Any], text: str) -> dict[str, list[bool]]:
    nodes = tuple(walk(item))
    rules = rule_ids(item)
    checks: dict[str, list[bool]] = defaultdict(list)

    if "voice" in row:
        features = item.features.as_dict()
        actual = "passive" if item.rule_id == "clause_passive" or features.get("voice") == "passive" else "active"
        checks["voice"].append(actual == row["voice"])
    if "predicate" in row:
        checks["predicate"].append(main_predicate(item) == row["predicate"].casefold())
    for required in row.get("required", ()):
        checks["required_rules"].append(required in rules)
    for forbidden in row.get("forbidden", ()):
        checks["forbidden_rules"].append(forbidden not in rules)
    for pattern in row.get("structures", ()):
        checks["structures"].append(any(matches_structure(node, pattern, text) for node in nodes))
    for category, surface in row.get("constituents", ()):
        checks["constituents"].append(any(
            node.category == category and text[node.start:node.end].casefold() == surface.casefold()
            for node in nodes
        ))
    leaves = [node.lexical_candidate for node in nodes if node.lexical_candidate is not None]
    for surface, category in row.get("pos", {}).items():
        checks["pos"].append(any(
            leaf.surface.casefold() == surface.casefold() and leaf.category == category
            for leaf in leaves
        ))
    return dict(checks)


def all_pass(checks: dict[str, list[bool]]) -> bool:
    return bool(checks) and all(value for values in checks.values() for value in values)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.999999)))
    return ordered[index]


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    rows = [json.loads(line) for line in args.corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.split != "all":
        rows = [row for row in rows if row["split"] == args.split]
    parser = Parser.from_dir(args.data_dir, cache_size=0)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    durations: list[float] = []
    details: list[dict[str, Any]] = []
    complete = top1 = kbest = 0

    for row in rows:
        started = perf_counter()
        result = parser.parse(row["text"]).result
        best = result.best()
        duration_ms = (perf_counter() - started) * 1000
        durations.append(duration_ms)
        if result.completed and best is not None:
            complete += 1
            checks = checks_for(best, row, row["text"])
            best_ok = all_pass(checks)
            top1 += int(best_ok)
            alternatives = result.alternatives(limit=args.k)
            kbest_ok = any(all_pass(checks_for(item, row, row["text"])) for item in alternatives)
            kbest += int(kbest_ok)
        else:
            checks = {}
            best_ok = kbest_ok = False
        for family, values in checks.items():
            totals[family][0] += sum(values)
            totals[family][1] += len(values)
        details.append({
            "id": row["id"], "split": row["split"], "text": row["text"],
            "complete": result.completed, "top1": best_ok, "kbest": kbest_ok,
            "duration_ms": round(duration_ms, 3),
            "failed": {family: values for family, values in checks.items() if not all(values)},
            "root_rule": best.rule_id if best else None,
            "predicate": main_predicate(best) if best else None,
        })

    count = len(rows)
    return {
        "corpus": str(args.corpus), "split": args.split, "sentences": count, "k": args.k,
        "coverage": {"passed": complete, "total": count, "rate": complete / count if count else 0.0},
        "top1_all_annotations": {"passed": top1, "total": count, "rate": top1 / count if count else 0.0},
        "kbest_all_annotations": {"passed": kbest, "total": count, "rate": kbest / count if count else 0.0},
        "by_family": {
            family: {"passed": passed, "total": total, "rate": passed / total if total else 0.0}
            for family, (passed, total) in sorted(totals.items())
        },
        "duration_ms": {
            "median": statistics.median(durations) if durations else 0.0,
            "p50": percentile(durations, 0.50), "p90": percentile(durations, 0.90),
            "p95": percentile(durations, 0.95), "p99": percentile(durations, 0.99),
        },
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data" / "syntax_correctness_validation.jsonl")
    parser.add_argument("--split", choices=("dev", "validation", "holdout", "all"), default="all")
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "details"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
