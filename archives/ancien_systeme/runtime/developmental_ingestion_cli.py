"""CLI bornée du pont d'ingestion vers le nouveau cœur."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cognitive_formal_analysis import FormalAnalysisPolicy, build_formal_runtime
from .cognitive_ingestion import (
    IngestionPolicy,
    records_from_dictionary_file,
    records_from_text_file,
)
from .cognitive_ingestion_session import CognitiveIngestionSession
from .contracts import ContractError
from .developmental_ingestion_session import DevelopmentalIngestionSession


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingère une source dans les analyseurs puis le cœur développemental"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/the_map_of_everything_nlp_novel.txt"),
    )
    parser.add_argument(
        "--input-format", choices=("auto", "text", "dictionary-jsonl"), default="auto"
    )
    parser.add_argument("--max-records", type=int, default=1)
    parser.add_argument("--max-text-chars", type=int, default=2_000)
    parser.add_argument("--max-units-per-observation", type=int, default=1)
    parser.add_argument("--max-this-run", type=int)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    try:
        if args.resume and args.checkpoint is None:
            raise ContractError("ingestion développementale: --resume exige --checkpoint")
        ingestion_policy = IngestionPolicy(
            max_records=args.max_records, max_text_chars=args.max_text_chars
        )
        formal_policy = FormalAnalysisPolicy(
            max_units_per_observation=args.max_units_per_observation
        )
        input_format = args.input_format
        if input_format == "auto":
            input_format = (
                "dictionary-jsonl" if args.input.suffix == ".jsonl" else "text"
            )
        records = (
            records_from_dictionary_file(args.input, policy=ingestion_policy)
            if input_format == "dictionary-jsonl"
            else records_from_text_file(args.input, policy=ingestion_policy)
        )
        runtime = build_formal_runtime(
            Path(__file__).resolve().parent.parent,
            ingestion_policy=ingestion_policy,
            formal_policy=formal_policy,
        )
        if args.resume:
            if not args.checkpoint.is_file():
                raise ContractError("ingestion développementale: checkpoint absent")
            session = DevelopmentalIngestionSession.restore(
                args.checkpoint,
                records=records,
                registry=runtime.registry,
                modules=runtime.modules,
            )
        else:
            analysis_session = CognitiveIngestionSession(
                runtime=runtime,
                records=records,
                policy=ingestion_policy,
                session_id=f"developmental-ingestion:{args.input.resolve()}",
            )
            session = DevelopmentalIngestionSession(
                analysis_session=analysis_session
            )
        bundles = session.run(max_records=args.max_this_run)
        if args.checkpoint is not None:
            session.checkpoint(args.checkpoint)
        report = session.report(bundles)
        if args.checkpoint is not None:
            report["checkpoint"] = str(args.checkpoint)
    except (ContractError, OSError) as exc:
        print(json.dumps({"status": "NO-GO", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "GO-DEVELOPMENTAL-INGESTION-BRIDGE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

