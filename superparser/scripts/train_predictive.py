#!/usr/bin/env python3
"""Train persistent predictive counters from independently validated parses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "superparser"))

from scripts.evaluate_reference_300 import normalized_gold, normalized_parser  # noqa: E402
from seman_parser import Parser  # noqa: E402
from seman_parser.predictive import PredictiveGrammar, TransitionModel  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=ROOT / "data" / "seman2_reference_300_compact.json")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "superparser" / "data")
    ap.add_argument("--output", type=Path, default=ROOT / "superparser" / "data" / "predictive_transitions.json")
    ap.add_argument("--alpha", type=float, default=4.0)
    ap.add_argument("--candidate-weight", type=float, default=0.25)
    args = ap.parse_args()

    rows = json.loads(args.corpus.read_text(encoding="utf-8"))["sentences"]
    parser = Parser.from_dir(args.data_dir, cache_size=0)
    model = TransitionModel(alpha=args.alpha)
    compiled = PredictiveGrammar(parser.resources.grammar)
    started = perf_counter()
    rejected = coverage_failures = 0
    for index, row in enumerate(rows, 1):
        best = parser.parse(row["text"]).result.best()
        valid = best is not None and normalized_parser(best) == normalized_gold(row["tree"])
        if best is None:
            coverage_failures += 1
        elif valid:
            model.observe_tree(best, validated=True, compiled=compiled)
        else:
            rejected += 1
            model.observe_tree(
                best, validated=False, weight=args.candidate_weight, compiled=compiled,
            )
        if index % 25 == 0:
            print(f"trained {index}/{len(rows)}", file=sys.stderr, flush=True)
    model.metadata.update({
        "source": str(args.corpus),
        "sentences": len(rows),
        "rejected_non_exact": rejected,
        "coverage_failures": coverage_failures,
        "training_seconds": round(perf_counter() - started, 3),
        "policy": "normalized-exact=1.0; complete non-exact=silver candidate",
        "candidate_weight": args.candidate_weight,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.output)
    print(json.dumps(model.metadata, indent=2))


if __name__ == "__main__":
    main()
