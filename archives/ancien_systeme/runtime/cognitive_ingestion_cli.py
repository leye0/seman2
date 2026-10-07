"""Exécute la fondation Source -> Observation sur un texte réel borné."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cognitive_ingestion import (
    IngestionPolicy,
    build_foundation_runtime,
    ingest_records,
    records_from_dictionary_file,
    records_from_text_file,
)
from .contracts import ContractError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingère séquentiellement un petit échantillon textuel réel"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/the_map_of_everything_nlp_novel.txt"),
    )
    parser.add_argument("--max-records", type=int, default=16)
    parser.add_argument("--max-text-chars", type=int, default=5_000)
    parser.add_argument(
        "--input-format",
        choices=("auto", "text", "dictionary-jsonl"),
        default="auto",
    )
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    policy = IngestionPolicy(
        max_records=args.max_records,
        max_text_chars=args.max_text_chars,
    )
    try:
        input_format = args.input_format
        if input_format == "auto":
            input_format = "dictionary-jsonl" if args.input.suffix == ".jsonl" else "text"
        records = (
            records_from_dictionary_file(args.input, policy=policy)
            if input_format == "dictionary-jsonl"
            else records_from_text_file(args.input, policy=policy)
        )
        runtime = build_foundation_runtime(policy)
        report = ingest_records(
            runtime,
            records,
            policy=policy,
            session_id=f"text-ingestion:{args.input.stem}",
        )
        if args.checkpoint:
            runtime.checkpoint(args.checkpoint)
    except ContractError as exc:
        print(json.dumps({"status": "NO-GO", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                **report,
                "input": str(args.input),
                "input_format": input_format,
                "input_bytes": args.input.stat().st_size,
                "text_characters_ingested": sum(len(row.text) for row in records),
                "checkpoint": str(args.checkpoint) if args.checkpoint else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
