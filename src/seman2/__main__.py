"""Command line entry point for the V3 runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from .evidence.stream import dialogue_tsv, ingest_records, text_blocks
from .interpretation.kqml import LocalTripsTransport
from .interpretation.trips_adapter import TripsAdapter
from .runtime.engine import Seman2Runtime


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def json_value(value: str) -> dict[str, Any]:
    """Accept either inline JSON or the path of a UTF-8 JSON document."""
    candidate = Path(value)
    raw = candidate.read_text(encoding="utf-8") if candidate.is_file() else value
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("la valeur JSON doit être un objet")
    return parsed


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="seman2", description="Runtime Seman2 V3")
    root.add_argument(
        "--database", type=Path, default=Path("data/evidence.sqlite")
    )
    root.add_argument("--trips-host", default="127.0.0.1")
    root.add_argument("--trips-port", type=int, default=6200)
    root.add_argument("--context-window", type=int, default=4)
    root.add_argument(
        "--parses-desired",
        type=int,
        default=1,
        help="nombre d'analyses TRIPS par phrase (1 = profil rapide)",
    )
    commands = root.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="initialise le journal SQLite/WAL")

    ingest = commands.add_parser("ingest", help="journalise une observation")
    ingest.add_argument("text")
    ingest.add_argument("--stream", required=True)
    ingest.add_argument("--source-id", default="command-line")
    ingest.add_argument("--process", action="store_true")

    file_command = commands.add_parser(
        "ingest-file", help="journalise un fichier UTF-8 en flux borné"
    )
    file_command.add_argument("path", type=Path)
    file_command.add_argument("--stream", required=True)
    file_command.add_argument("--mode", choices=("paragraph", "line", "sentence", "dialogue-tsv"), default="paragraph")
    file_command.add_argument("--limit", type=int)
    file_command.add_argument("--max-unit-bytes", type=int, default=1_000_000)
    file_command.add_argument("--process", action="store_true")

    run = commands.add_parser("run", help="vide la file d'interprétation")
    run.add_argument("--limit", type=int)

    awake = commands.add_parser("awake", help="exécute le cycle éveillé continu")
    awake.add_argument("--poll-seconds", type=float, default=0.25)
    awake.add_argument("--consolidate-every", type=int, default=100)
    awake.add_argument("--minimum-support", type=int, default=2)

    replay = commands.add_parser("replay", help="programme une nouvelle analyse")
    replay.add_argument("evidence_id")
    replay.add_argument("--process", action="store_true")

    trace = commands.add_parser("trace", help="affiche la provenance d'une observation")
    trace.add_argument("evidence_id")

    consolidate = commands.add_parser(
        "consolidate", help="induit les motifs récurrents et synchronise le graphe"
    )
    consolidate.add_argument("--minimum-support", type=int, default=2)
    consolidate.add_argument("--without-discodop", action="store_true")

    reprocess = commands.add_parser(
        "reprocess", help="réapplique les abstractions aux observations conservées"
    )
    reprocess.add_argument("--minimum-similarity", type=float, default=0.0)

    retro = commands.add_parser(
        "retro",
        help="renvoie les segments d'arbres appris vers les analyses conservées",
    )
    retro.add_argument("--evidence-id")

    generate = commands.add_parser(
        "generate", help="génère par inversion des alignements appris"
    )
    generate.add_argument("target", type=json_value)
    generate.add_argument("--context", type=json_value)
    generate.add_argument("--bindings", type=json_value)
    generate.add_argument("--limit", type=int, default=10)
    generate.add_argument(
        "--modes",
        default="retrieve,instantiate",
        help="modes de génération séparés par des virgules",
    )

    model_trace = commands.add_parser(
        "model-trace", help="affiche la provenance d'une structure apprise"
    )
    model_trace.add_argument("structure_id")

    commands.add_parser("status", help="affiche les volumes du journal")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    adapter = TripsAdapter(
        LocalTripsTransport(args.trips_host, args.trips_port),
        number_parses_desired=args.parses_desired,
    )
    with Seman2Runtime.open(
        args.database,
        interpreter=adapter,
        context_window=args.context_window,
    ) as runtime:
        if args.command == "init":
            emit({"database": str(args.database), "journal_mode": runtime.store.journal_mode})
        elif args.command == "ingest":
            unit = runtime.ingest(
                args.text,
                stream_id=args.stream,
                source={"type": "command-line", "source_id": args.source_id},
            )
            bundle = runtime.process_next() if args.process else None
            emit(
                {
                    "evidence": unit.as_dict(),
                    "analysis_id": bundle.analysis_id if bundle else None,
                }
            )
        elif args.command == "ingest-file":
            if args.mode == "dialogue-tsv":
                records = dialogue_tsv(
                    args.path,
                    max_units=args.limit,
                    max_line_bytes=args.max_unit_bytes,
                )
            else:
                records = text_blocks(
                    args.path,
                    mode=args.mode,
                    max_units=args.limit,
                    max_unit_bytes=args.max_unit_bytes,
                )
            units = ingest_records(runtime, records, stream_id=args.stream)
            bundles = runtime.process_all(limit=len(units)) if args.process else ()
            emit(
                {
                    "evidence_ids": [unit.evidence_id for unit in units],
                    "analysis_ids": [bundle.analysis_id for bundle in bundles],
                    "counts": runtime.store.counts(),
                }
            )
        elif args.command == "run":
            bundles = runtime.process_all(limit=args.limit)
            emit(
                {
                    "analysis_ids": [bundle.analysis_id for bundle in bundles],
                    "processed": len(bundles),
                    "counts": runtime.store.counts(),
                }
            )
        elif args.command == "awake":
            if args.poll_seconds <= 0 or args.consolidate_every < 1:
                raise SystemExit("poll-seconds et consolidate-every doivent être positifs")
            processed = 0
            try:
                while True:
                    bundle = runtime.process_next()
                    if bundle is None:
                        time.sleep(args.poll_seconds)
                        continue
                    processed += 1
                    if processed % args.consolidate_every == 0:
                        runtime.consolidate(minimum_support=args.minimum_support)
            except KeyboardInterrupt:
                emit({"stopped": True, "processed": processed, "status": runtime.status()})
        elif args.command == "replay":
            job_id = runtime.replay(args.evidence_id)
            bundle = runtime.process_next() if args.process else None
            emit(
                {
                    "job_id": job_id,
                    "analysis_id": bundle.analysis_id if bundle else None,
                }
            )
        elif args.command == "trace":
            emit(runtime.trace(args.evidence_id))
        elif args.command == "consolidate":
            emit(
                runtime.consolidate(
                    minimum_support=args.minimum_support,
                    use_discodop=not args.without_discodop,
                )
            )
        elif args.command == "reprocess":
            emit(runtime.reprocess(minimum_similarity=args.minimum_similarity))
        elif args.command == "retro":
            emit(runtime.retro())
        elif args.command == "generate":
            emit(
                {
                    "candidates": [
                        row.as_dict()
                        for row in runtime.generate(
                            args.target,
                            context=args.context,
                            bindings=args.bindings,
                            limit=args.limit,
                            modes=tuple(
                                item.strip()
                                for item in args.modes.split(",")
                                if item.strip()
                            ),
                        )
                    ]
                }
            )
        elif args.command == "model-trace":
            emit(runtime.model_trace(args.structure_id))
        elif args.command == "status":
            emit({"database": str(args.database), **runtime.status()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
