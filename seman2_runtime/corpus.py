"""Échantillonnage déterministe et borné des Parquet canoniques réels."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
import resource
from typing import Any

import duckdb

from .contracts import ContractError, Envelope, digest, output_envelope, ServiceSpec


@dataclass(frozen=True)
class SamplingPolicy:
    shard_count: int = 5
    memory_limit: str = "256MB"
    threads: int = 1
    answers_per_question: int = 3
    max_question_chars: int = 1800
    max_answer_chars: int = 2400

    def __post_init__(self) -> None:
        if not 1 <= self.shard_count <= 10:
            raise ContractError("sampling: shard_count doit être compris entre 1 et 10")
        if self.threads != 1:
            raise ContractError("sampling: cette politique de sûreté exige threads=1")
        if not 1 <= self.answers_per_question <= 5:
            raise ContractError("sampling: answers_per_question doit être compris entre 1 et 5")


class _TextProjection(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def text_projection(raw_html: str) -> str:
    parser = _TextProjection()
    parser.feed(raw_html)
    parser.close()
    return parser.text()


class CorpusSamplingService:
    """Sélectionne trois phénomènes sur des shards espacés, sans scan global."""

    spec = ServiceSpec("corpus-sampling", "sampling-request", "corpus-sample-set")
    criteria = (
        (
            "code-and-competing-answers",
            "q.body LIKE '%<code>%' AND s.max_score > s.min_score",
        ),
        (
            "temporal-discourse",
            "regexp_matches(lower(q.title || ' ' || q.body), '\\b(before|after|when|then|until|while)\\b')",
        ),
        (
            "negation-or-uncertainty",
            "regexp_matches(lower(q.title || ' ' || q.body), '\\b(not|cannot|can.t|doesn.t|why|unclear|maybe)\\b')",
        ),
    )

    def __init__(self, root: Path, policy: SamplingPolicy | None = None) -> None:
        self.root = root.resolve()
        self.policy = policy or SamplingPolicy()

    def _shards(self) -> tuple[list[Path], list[Path]]:
        base = self.root / "data/parquet/stackoverflow/schema_version=1"
        questions = sorted((base / "questions").glob("*.parquet"))
        if not questions:
            raise ContractError("sampling: Parquet Stack Overflow absents; exécuter fetch-corpus")
        count = min(self.policy.shard_count, len(questions))
        indexes = sorted({round(i * (len(questions) - 1) / max(count - 1, 1)) for i in range(count)})
        selected_questions = [questions[index] for index in indexes]
        selected_answers = [base / "answers" / path.name for path in selected_questions]
        absent = [path for path in selected_answers if not path.is_file()]
        if absent:
            raise ContractError(f"sampling: shard de réponses absent: {absent[0]}")
        return selected_questions, selected_answers

    def handle(self, source: Envelope) -> Envelope:
        if source.kind != self.spec.input_kind:
            raise ContractError(f"{self.spec.name} attend {self.spec.input_kind}, reçu {source.kind}")
        questions, answers = self._shards()
        temp = self.root / ".local/state/phase3-duckdb-temp"
        temp.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect()
        try:
            connection.execute(f"SET threads={self.policy.threads}")
            connection.execute(f"SET memory_limit='{self.policy.memory_limit}'")
            connection.execute("SET preserve_insertion_order=false")
            connection.execute(f"SET temp_directory='{str(temp).replace(chr(39), chr(39) * 2)}'")
            connection.execute("SET max_temp_directory_size='512MB'")
            connection.execute("SET enable_progress_bar=false")
            selected: list[dict[str, Any]] = []
            excluded: list[str] = []
            for label, phenomenon_filter in self.criteria:
                shard_candidates: list[dict[str, Any]] = []
                for question_path, answer_path in zip(questions, answers):
                    exclusion = ""
                    parameters: list[Any] = [str(question_path), str(answer_path), label]
                    if excluded:
                        exclusion = "AND q.question_id NOT IN (SELECT unnest(?::VARCHAR[]))"
                        parameters.append(excluded)
                    query = f"""
                        WITH q AS (
                            SELECT question_id, title, body, tags, answer_count,
                                   source_file, source_position, source_record_id,
                                   filename AS canonical_file
                            FROM read_parquet(?, filename=true)
                            WHERE answer_count BETWEEN 2 AND 8
                              AND length(title) BETWEEN 25 AND 120
                              AND length(body) BETWEEN 250 AND {self.policy.max_question_chars}
                        ), s AS (
                            SELECT question_id, count(*) AS answer_rows,
                                   min(native_vote_score) AS min_score,
                                   max(native_vote_score) AS max_score
                            FROM read_parquet(?)
                            WHERE length(body) BETWEEN 120 AND {self.policy.max_answer_chars}
                            GROUP BY question_id
                        )
                        SELECT q.question_id, q.title, q.body, q.tags, q.answer_count,
                               q.source_file, q.source_position, q.source_record_id,
                               q.canonical_file, s.answer_rows, s.min_score, s.max_score,
                               md5(q.question_id || ?) AS sampling_rank
                        FROM q JOIN s USING (question_id)
                        WHERE s.answer_rows BETWEEN 2 AND 8
                          AND {phenomenon_filter}
                          {exclusion}
                        ORDER BY sampling_rank
                        LIMIT 1
                    """
                    try:
                        row = connection.execute(query, parameters).fetchone()
                    except duckdb.Error as exc:
                        raise ContractError(f"sampling: lecture bornée échouée: {exc}") from exc
                    if row is not None:
                        columns = [item[0] for item in connection.description]
                        shard_candidates.append(dict(zip(columns, row)))
                if not shard_candidates:
                    raise ContractError(f"sampling: aucun candidat réel pour {label}")
                record = min(shard_candidates, key=lambda item: item["sampling_rank"])
                excluded.append(record["question_id"])
                selected.append({"criterion": label, **record})

            answer_records: list[dict[str, Any]] = []
            for selected_record in selected:
                answer_path = (
                    self.root / "data/parquet/stackoverflow/schema_version=1/answers"
                    / Path(selected_record["canonical_file"]).name
                )
                rows = connection.execute(
                    f"""
                    SELECT answer_id, question_id, body, native_vote_score,
                           source_group, source_ordinal, source_file,
                           source_position, source_record_id, filename AS canonical_file
                    FROM read_parquet(?, filename=true)
                    WHERE question_id = ? AND length(body) <= {self.policy.max_answer_chars}
                    ORDER BY native_vote_score DESC, source_group, source_ordinal
                    LIMIT {self.policy.answers_per_question}
                    """,
                    [str(answer_path), selected_record["question_id"]],
                ).fetchall()
                columns = [item[0] for item in connection.description]
                answer_records.extend(dict(zip(columns, row)) for row in rows)
        finally:
            connection.close()

        ids = [row["question_id"] for row in selected]
        answers_by_question: dict[str, list[dict]] = {identifier: [] for identifier in ids}
        for answer in answer_records:
            answer["canonical_file"] = str(Path(answer["canonical_file"]).resolve().relative_to(self.root))
            answer["raw_body_sha256"] = digest(answer["body"])
            answer["text_projection"] = text_projection(answer["body"])
            answers_by_question[answer["question_id"]].append(answer)

        samples = []
        for record in selected:
            record.pop("sampling_rank")
            record["canonical_file"] = str(Path(record["canonical_file"]).resolve().relative_to(self.root))
            raw_body = record["body"]
            record["raw_body_sha256"] = digest(raw_body)
            record["text_projection"] = text_projection(raw_body)
            record["answers"] = answers_by_question[record["question_id"]]
            record["sample_id"] = f"stackoverflow:{record['question_id']}:{record['criterion']}"
            samples.append(record)

        scanned = [*questions, *answers]
        policy = {
            "engine": "DuckDB",
            "threads": self.policy.threads,
            "memory_limit": self.policy.memory_limit,
            "max_temp_directory_size": "512MB",
            "shards_scanned": len(scanned),
            "compressed_bytes_in_scope": sum(path.stat().st_size for path in scanned),
            "full_dataset_materialized": False,
            "question_rows_returned": len(samples),
            "answer_rows_returned": sum(len(row["answers"]) for row in samples),
            "process_max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"corpus-samples:{source.correlation_id}",
            payload={"samples": samples, "sampling_policy": policy},
            provenance=tuple(str(path.relative_to(self.root)) for path in scanned),
        )


def sampling_request(correlation_id: str = "phase3:corpus-sample") -> Envelope:
    return Envelope(
        kind="sampling-request",
        message_id=f"sampling-request:{correlation_id}",
        correlation_id=correlation_id,
        producer="integration-client",
        parent_ids=(),
        payload={"dataset": "stackoverflow", "purpose": "proto-service-integration"},
    )


def sample_to_json(root: Path, output: Path) -> dict:
    result = CorpusSamplingService(root).handle(sampling_request())
    value = {"status": "GO", "envelope": result.as_dict()}
    output.mkdir(parents=True, exist_ok=True)
    (output / "corpus-samples.json").write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    return value
