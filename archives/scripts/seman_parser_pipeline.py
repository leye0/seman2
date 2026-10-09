"""Ingest -> analyze -> persist, with seman_parser as the interpreter.

Replaces the ephemeral parse by a durable analysis written to the
evidence stream, so a session can stop and be resumed from the snapshot
the database already provides.

Usage:
    python scripts/seman_parser_pipeline.py \\
        --database output/seman_parser.sqlite \\
        --stream book:map \\
        --limit 20 \\
        data/the_map_of_everything_nlp_novel.txt
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(description="seman_parser -> evidence pipeline")
    ap.add_argument("source", help="text file to ingest sentence by sentence")
    ap.add_argument("--database", default="output/seman_parser.sqlite")
    ap.add_argument("--stream", default="demo")
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--data", default="seman_parser/data", help="parser resources")
    ap.add_argument("--report", default="", help="optional JSONL output path")
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "src"))
    sys.path.insert(0, os.path.join(root, "seman_parser"))

    from seman2.interpretation.seman_adapter import SemanParserAdapter
    from seman2.runtime.engine import Seman2Runtime

    os.makedirs(os.path.dirname(os.path.abspath(args.database)) or ".", exist_ok=True)
    adapter = SemanParserAdapter.from_dir(args.data)
    runtime = Seman2Runtime.open(args.database, interpreter=adapter)
    print(f"runtime open  db={args.database}  interpreter={adapter.key}", flush=True)

    from seman_parser.coverage import extract_sentences

    cases = extract_sentences(args.source, limit=args.limit or None)
    print(f"source: {len(cases)} sentences", flush=True)

    t0 = time.perf_counter()
    analyzed = 0
    parsed = 0
    report = open(args.report, "w", encoding="utf-8") if args.report else None
    try:
        for i, case in enumerate(cases):
            runtime.ingest(case.text, stream_id=args.stream, kind="text")
            # Drain the queue so the analysis is persisted before we move on.
            bundle = runtime.process_next()
            analyzed += 1
            if bundle is not None and bundle.segments and bundle.segments[0].status == "parsed":
                parsed += 1
            if report is not None and bundle is not None:
                report.write(json.dumps({
                    "index": i,
                    "text": case.text,
                    "analysis_id": bundle.analysis_id,
                    "status": bundle.segments[0].status if bundle.segments else None,
                    "hypotheses": len(bundle.hypotheses),
                }, ensure_ascii=False) + "\n")
            if (i + 1) % 25 == 0:
                el = time.perf_counter() - t0
                print(f"  {i+1:4d}/{len(cases)}  parsed={parsed}  {el:.0f}s", flush=True)
    finally:
        if report is not None:
            report.close()

    elapsed = time.perf_counter() - t0
    status = runtime.status()
    print(f"\n=== done ===", flush=True)
    print(f"analyzed  {analyzed}", flush=True)
    print(f"parsed    {parsed}  ({parsed/analyzed:.1%})" if analyzed else "parsed 0", flush=True)
    print(f"temps     {elapsed:.1f}s  ({elapsed/analyzed*1000:.0f} ms/phrase)" if analyzed else "", flush=True)
    print(f"status    {json.dumps(status, default=str)[:300]}", flush=True)
    runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
