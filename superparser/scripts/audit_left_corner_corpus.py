"""Fixed-cohort evaluation of experimental lexical left-corner pruning.

One public Parser.parse per sentence. Does not modify the pinned corpus or
the production parser default; emits source-aligned, inspectable parse trees
so newly recovered parses can be checked for grammatical plausibility.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import signal
from time import perf_counter

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import (
    EXPECTED_500_COHORT_SHA256, classify, select_cases,
)
from seman_parser.engine import Parser, ParserResources

ROOT = Path(__file__).resolve().parents[1]


class Deadline(Exception):
    pass


def _alarm(_signal, _frame):
    raise Deadline("per-sentence research deadline")


def _tree(item):
    if item is None:
        return None
    return {
        "span": [item.start, item.end],
        "category": item.category,
        "rule": item.rule_id,
        "lexical": ({
            "category": item.lexical_candidate.category,
            "lemma": item.lexical_candidate.lemma,
            "source": item.lexical_candidate.source,
        } if item.lexical_candidate else None),
        "children": [_tree(child) for child in item.children],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--wordnet-dir", required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--max-items", type=int, default=50000)
    p.add_argument("--kbest-work-limit", type=int, default=500000)
    p.add_argument("--seconds", type=float, default=10.0)
    opts = p.parse_args()
    cases, _sources = select_cases(500)
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    # Same byte-for-byte cohort pin as official diagnostic.
    cohort = opts.out_dir / "cohort.jsonl"
    with cohort.open("w", encoding="utf8") as stream:
        for index, case in enumerate(cases):
            stream.write(json.dumps({
                "index": index, "book_id": case["book_id"],
                "ordinal": case["ordinal"], "band": case["band"],
                "tokens": case["tokens"], "sentence": case["text"],
                "source_text": case.get("source_text", case["text"]),
                "semicolon_split": bool(case.get("semicolon_split")),
                "synthetic_prefix": case.get("synthetic_prefix", ""),
                "synthetic_suffix": case.get("synthetic_suffix", ""),
                "synthetic_terminal": bool(case.get("synthetic_terminal")),
            }, ensure_ascii=False) + "\n")
    digest = sha256(cohort.read_bytes()).hexdigest()
    if digest != EXPECTED_500_COHORT_SHA256:
        raise AssertionError(
            f"Fixed 500-cohort signature mismatch: {digest}"
        )

    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=opts.wordnet_dir)
    parser = Parser(resources, max_items=opts.max_items, cache_size=0,
                    lexical_left_corner_pruning=True)
    parser.parse("John opened the box.")  # Same warm-up as canonical diagnostic
    old_handler = signal.signal(signal.SIGALRM, _alarm)
    counts = Counter()
    summed = Counter()
    out = opts.out_dir / "per_sentence.jsonl"
    try:
        with out.open("w", encoding="utf8") as stream:
            for index, case in enumerate(cases):
                began = perf_counter()
                signal.setitimer(signal.ITIMER_REAL, opts.seconds)
                try:
                    _input, lattice, result = parse_corpus_case(
                        parser, case, max_items=opts.max_items,
                        kbest_work_limit=opts.kbest_work_limit,
                    )
                    stats = result.stats
                    dialogue = stats.get("dialogue_attempt") or {}
                    row = {
                        "index": index,
                        "book_id": case["book_id"],
                        "source": case["text"],
                        "analysis": lattice.text,
                        "status": classify(result.completed, stats),
                        "completed": result.completed,
                        "root_rule": result.best().rule_id if result.best() else None,
                        "tree": _tree(result.best()),
                        "partial_states": stats.get("partial_states", 0),
                        "forest_nodes": stats.get("forest_nodes", 0),
                        "structural_root_nodes": stats.get("structural_root_nodes", 0),
                        "budget_exceeded": bool(stats.get("budget_exceeded")),
                        "dialogue_budget_exceeded": bool(
                            dialogue.get("budget_exceeded")),
                        "unreachable_prefix_proposals": stats.get(
                            "unreachable_prefix_proposals", 0),
                        "dialogue_unreachable_prefix_proposals": dialogue.get(
                            "unreachable_prefix_proposals", 0),
                    }
                except Deadline:
                    row = {
                        "index": index, "book_id": case["book_id"],
                        "status": "timeout", "completed": False,
                        "source": case["text"],
                    }
                except Exception as exc:
                    row = {
                        "index": index, "book_id": case["book_id"],
                        "status": "error", "completed": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "source": case["text"],
                    }
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                row["wall_ms"] = round(1000 * (perf_counter() - began), 2)
                counts[row["status"]] += 1
                summed["wall_ms"] += row["wall_ms"]
                for key in ("partial_states", "forest_nodes",
                            "unreachable_prefix_proposals",
                            "dialogue_unreachable_prefix_proposals"):
                    summed[key] += row.get(key) or 0
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                if index % 25 == 24:
                    print("LEFT_CORNER_PROGRESS", json.dumps({
                        "seen": index + 1,
                        "complete": counts["complete"],
                        "counts": dict(counts),
                    }), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)

    summary = {
        "n": len(cases),
        "cohort_sha256": digest,
        "counts": dict(counts),
        "completed": counts["complete"],
        "totals": dict(summed),
        "experimental": True,
    }
    (opts.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    print("LEFT_CORNER_FULL_CORPUS", json.dumps(summary), flush=True)
    if counts["error"]:
        raise AssertionError(f"Unexpected parser exceptions: {counts['error']}")


if __name__ == "__main__":
    main()
