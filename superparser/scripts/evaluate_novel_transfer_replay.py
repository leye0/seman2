"""Reproduce frozen literary transfer, control, and development cohorts.

The exact source coordinates are pinned even when extraction ordinals
change. Marker-only documentary dispositions are recorded, not parsed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal

from scripts.evaluate_novel_transfer import (
    MAX_ITEMS, ROOT, _deadline, _serialized_cohort, measure,
)
from seman_parser.engine import Parser, ParserResources
from scripts.transfer_source_anchors import resolve_anchors

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--books-dir", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--wordnet-dir", type=Path)
    cli.add_argument("--sample-only", action="store_true")
    args = cli.parse_args()
    if not args.sample_only and args.wordnet_dir is None:
        cli.error("--wordnet-dir is required for measurement")
    cohorts = resolve_anchors(args.books_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in cohorts.items():
        (args.out_dir / f"{name}_cohort.jsonl").write_bytes(_serialized_cohort(rows))
    if args.sample_only:
        return
    parser = Parser(ParserResources.from_dir(ROOT / "data", wordnet_dict=args.wordnet_dir),
                    cache_size=0, max_items=MAX_ITEMS)
    parser.parse("John opened the box.")
    handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        for name, rows in cohorts.items():
            with (args.out_dir / f"{name}_parses.jsonl").open("w", encoding="utf-8", buffering=1) as out:
                for case in rows:
                    result = (
                        {"status": case["disposition"], "tree": None}
                        if case.get("disposition") else measure(parser, case)
                    )
                    out.write(json.dumps({"transfer_id": case["transfer_id"], **result}, ensure_ascii=False) + "\n")
    finally:
        signal.signal(signal.SIGALRM, handler)


if __name__ == "__main__":
    main()
