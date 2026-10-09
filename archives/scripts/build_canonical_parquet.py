#!/usr/bin/env python3
"""Build canonical Reddit and Stack Overflow Parquet datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ensure_local_python() -> None:
    """Re-execute this script with the project-local Python when needed."""
    local_python = ROOT / ".venv/bin/python"
    if Path(sys.prefix).resolve() == (ROOT / ".venv").resolve():
        return
    if os.environ.get("SEMAN2_LOCAL_BOOTSTRAPPED") == "1":
        return
    if not local_python.is_file():
        raise RuntimeError(
            "Environnement local absent; exécuter ./scripts/seman2 verify."
        )
    environment = os.environ.copy()
    environment["SEMAN2_LOCAL_BOOTSTRAPPED"] = "1"
    os.execve(
        local_python,
        [str(local_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        environment,
    )


ensure_local_python()

import duckdb  # noqa: E402  (import après sélection de l'environnement local)


SCHEMA_VERSION = 1
TRANSFORMATION_VERSION = "1.0.0"


def sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parquet_rows(connection: duckdb.DuckDBPyConnection, path: Path) -> int:
    return connection.execute(
        f"SELECT count(*) FROM read_parquet({sql_string(path)})"
    ).fetchone()[0]


def atomic_copy(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    destination: Path,
    force: bool,
) -> None:
    if destination.exists() and not force:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection.execute(
        f"COPY ({query}) TO {sql_string(temporary)} "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    os.replace(temporary, destination)


def provenance(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def build_reddit(
    connection: duckdb.DuckDBPyConnection,
    force: bool,
    write_manifest_file: bool = True,
) -> dict:
    source_root = ROOT / "data/reddit-arctic-2018-05"
    output_root = ROOT / "data/parquet/reddit/schema_version=1"
    sources: list[dict] = []
    outputs: list[dict] = []

    for kind in ("submissions", "comments"):
        files = sorted((source_root / "data" / kind / "2018" / "05").glob("*.parquet"))
        for source in files:
            source_rel = provenance(source, ROOT)
            destination = output_root / kind / f"part-{source.stem}.parquet"
            source_sql = sql_string(source)
            source_rel_sql = sql_string(source_rel)

            if kind == "submissions":
                query = f"""
                    SELECT
                        id AS submission_id,
                        subreddit,
                        CASE WHEN author IS NULL OR author = '' THEN 'unknown' ELSE author END AS author_name,
                        CASE
                            WHEN author = '[deleted]' THEN 'deleted'
                            WHEN author IS NULL OR author = '' THEN 'unknown'
                            ELSE 'present'
                        END AS author_state,
                        created_at,
                        created_utc,
                        title,
                        selftext AS body,
                        url,
                        score AS native_vote_score,
                        NULL::BOOLEAN AS is_edited,
                        NULL::TIMESTAMP AS edited_at,
                        CASE
                            WHEN selftext = '[deleted]' THEN 'deleted'
                            WHEN selftext = '[removed]' THEN 'removed'
                            ELSE 'present'
                        END AS moderation_state,
                        num_comments,
                        over_18,
                        link_flair_text,
                        author_flair_text,
                        {source_rel_sql} AS source_file,
                        file_row_number::BIGINT AS source_position,
                        id AS source_record_id
                    FROM read_parquet({source_sql}, file_row_number=true)
                """
            else:
                query = f"""
                    SELECT
                        id AS comment_id,
                        regexp_replace(link_id, '^t3_', '') AS submission_id,
                        regexp_replace(parent_id, '^(t1_|t3_)', '') AS parent_id,
                        CASE
                            WHEN starts_with(parent_id, 't1_') THEN 'comment'
                            WHEN starts_with(parent_id, 't3_') THEN 'submission'
                            ELSE 'unknown'
                        END AS parent_kind,
                        CASE WHEN author IS NULL OR author = '' THEN 'unknown' ELSE author END AS author_name,
                        CASE
                            WHEN author = '[deleted]' THEN 'deleted'
                            WHEN author IS NULL OR author = '' THEN 'unknown'
                            ELSE 'present'
                        END AS author_state,
                        created_at,
                        created_utc,
                        body,
                        score AS native_vote_score,
                        NULL::BOOLEAN AS is_edited,
                        NULL::TIMESTAMP AS edited_at,
                        CASE
                            WHEN body = '[deleted]' THEN 'deleted'
                            WHEN body = '[removed]' THEN 'removed'
                            ELSE 'present'
                        END AS moderation_state,
                        distinguished,
                        author_flair_text,
                        link_id AS raw_link_id,
                        parent_id AS raw_parent_id,
                        {source_rel_sql} AS source_file,
                        file_row_number::BIGINT AS source_position,
                        id AS source_record_id
                    FROM read_parquet({source_sql}, file_row_number=true)
                """

            atomic_copy(connection, query, destination, force)
            sources.append(
                {
                    "file": source_rel,
                    "bytes": source.stat().st_size,
                    "rows": parquet_rows(connection, source),
                    "sha256": sha256(source),
                }
            )
            outputs.append(
                {
                    "table": kind,
                    "file": provenance(destination, ROOT),
                    "bytes": destination.stat().st_size,
                    "rows": parquet_rows(connection, destination),
                    "sha256": sha256(destination),
                }
            )
            print(f"reddit/{kind}: {source.name} -> {destination.name}", flush=True)

    manifest = make_manifest("reddit", sources, outputs)
    if write_manifest_file:
        write_manifest(output_root / "manifest.json", manifest)
    return manifest


def stackoverflow_question_id() -> str:
    return "CAST(CAST(regexp_extract(name, '^stackoverflow_([0-9]+)_', 1) AS UBIGINT) AS VARCHAR)"


def build_stackoverflow(
    connection: duckdb.DuckDBPyConnection,
    force: bool,
    write_manifest_file: bool = True,
) -> dict:
    source_root = ROOT / "data/stackoverflow"
    output_root = ROOT / "data/parquet/stackoverflow/schema_version=1"
    sources: list[dict] = []
    outputs: list[dict] = []
    question_id = stackoverflow_question_id()

    for source in sorted(source_root.glob("*.parquet")):
        source_rel = provenance(source, ROOT)
        source_sql = sql_string(source)
        source_rel_sql = sql_string(source_rel)
        part = source.name.split("-of-")[0].replace("train-", "")
        question_destination = output_root / "questions" / f"part-{part}.parquet"
        answer_destination = output_root / "answers" / f"part-{part}.parquet"

        question_query = f"""
            SELECT
                {question_id} AS question_id,
                title,
                question AS body,
                tags,
                NULL::BIGINT AS native_vote_score,
                NULL::VARCHAR AS accepted_answer_id,
                NULL::TIMESTAMP AS created_at,
                (list_count(answers) + list_count(non_answers))::BIGINT AS answer_count,
                {source_rel_sql} AS source_file,
                file_row_number::BIGINT AS source_position,
                name AS source_record_id
            FROM read_parquet({source_sql}, file_row_number=true)
        """
        answer_query = f"""
            WITH source AS (
                SELECT *, file_row_number::BIGINT AS source_position
                FROM read_parquet({source_sql}, file_row_number=true)
            ), flattened AS (
                SELECT
                    {question_id} AS question_id,
                    unnest(answers) AS body,
                    unnest(answers_scores)::BIGINT AS native_vote_score,
                    generate_subscripts(answers, 1)::INTEGER AS source_ordinal,
                    'answers'::VARCHAR AS source_group,
                    source_position,
                    name AS source_record_id
                FROM source
                UNION ALL
                SELECT
                    {question_id} AS question_id,
                    unnest(non_answers) AS body,
                    unnest(non_answers_scores)::BIGINT AS native_vote_score,
                    generate_subscripts(non_answers, 1)::INTEGER AS source_ordinal,
                    'non_answers'::VARCHAR AS source_group,
                    source_position,
                    name AS source_record_id
                FROM source
            )
            SELECT
                question_id || ':' || source_group || ':' || source_ordinal::VARCHAR AS answer_id,
                false AS answer_id_is_native,
                question_id,
                body,
                native_vote_score,
                NULL::BOOLEAN AS is_accepted,
                NULL::VARCHAR AS author_name,
                NULL::TIMESTAMP AS created_at,
                source_group,
                source_ordinal,
                {source_rel_sql} AS source_file,
                source_position,
                source_record_id
            FROM flattened
        """

        atomic_copy(connection, question_query, question_destination, force)
        atomic_copy(connection, answer_query, answer_destination, force)
        sources.append(
            {
                "file": source_rel,
                "bytes": source.stat().st_size,
                "rows": parquet_rows(connection, source),
                "sha256": sha256(source),
            }
        )
        for table, destination in (
            ("questions", question_destination),
            ("answers", answer_destination),
        ):
            outputs.append(
                {
                    "table": table,
                    "file": provenance(destination, ROOT),
                    "bytes": destination.stat().st_size,
                    "rows": parquet_rows(connection, destination),
                    "sha256": sha256(destination),
                }
            )
        print(
            f"stackoverflow: {source.name} -> {question_destination.name}, {answer_destination.name}",
            flush=True,
        )

    manifest = make_manifest("stackoverflow", sources, outputs)
    if write_manifest_file:
        write_manifest(output_root / "manifest.json", manifest)
    return manifest


def make_manifest(dataset: str, sources: list[dict], outputs: list[dict]) -> dict:
    return {
        "dataset": dataset,
        "schema_version": SCHEMA_VERSION,
        "transformation_version": TRANSFORMATION_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compression": "zstd",
        "sources": sources,
        "outputs": outputs,
        "totals": {
            "source_files": len(sources),
            "source_bytes": sum(item["bytes"] for item in sources),
            "source_rows": sum(item["rows"] for item in sources),
            "output_files": len(outputs),
            "output_bytes": sum(item["bytes"] for item in outputs),
            "output_rows": sum(item["rows"] for item in outputs),
        },
    }


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", choices=("all", "reddit", "stackoverflow"), default="all"
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="ne pas remplacer le manifeste de corpus versionné",
    )
    args = parser.parse_args()

    connection = duckdb.connect()
    connection.execute("SET threads = 4")
    connection.execute("SET memory_limit = '4GB'")
    connection.execute("SET preserve_insertion_order = false")

    if args.dataset in ("all", "reddit"):
        build_reddit(connection, args.force, not args.no_manifest)
    if args.dataset in ("all", "stackoverflow"):
        build_stackoverflow(connection, args.force, not args.no_manifest)


if __name__ == "__main__":
    main()
