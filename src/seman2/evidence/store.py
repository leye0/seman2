"""SQLite/WAL journal for evidence, processing and immutable derivations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator, Mapping, Sequence
import uuid

from .model import EvidenceUnit, ProcessingJob
from ..interpretation.model import AnalysisBundle


SCHEMA_VERSION = 1


class EvidenceStoreError(RuntimeError):
    """Raised when a journal invariant would be violated."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


class EvidenceStore:
    """Owns the append-only level-1 journal and its interpretation queue."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            check_same_thread=False,
            timeout=30,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 30000")
        mode = self._connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if str(mode).lower() != "wal":
            raise EvidenceStoreError(f"SQLite WAL unavailable for {self.path}")
        self._connection.execute("PRAGMA synchronous = NORMAL")
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "EvidenceStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def journal_mode(self) -> str:
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0])

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except BaseException:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def _initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS schema_info (
            version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS evidence_units (
            evidence_id TEXT PRIMARY KEY,
            stream_id TEXT NOT NULL,
            sequence_number INTEGER NOT NULL CHECK (sequence_number >= 0),
            kind TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            raw_sha256 TEXT NOT NULL,
            source_json TEXT NOT NULL,
            observed_at TEXT,
            context_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            UNIQUE (stream_id, sequence_number)
        );

        CREATE INDEX IF NOT EXISTS evidence_stream_order
            ON evidence_units(stream_id, sequence_number);

        CREATE TABLE IF NOT EXISTS interpretation_jobs (
            job_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL REFERENCES evidence_units(evidence_id),
            interpreter_key TEXT NOT NULL,
            generation INTEGER NOT NULL CHECK (generation >= 0),
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'processing', 'complete', 'failed')
            ),
            attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            available_at TEXT NOT NULL,
            leased_until TEXT,
            lease_token TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (evidence_id, interpreter_key, generation)
        );

        CREATE INDEX IF NOT EXISTS interpretation_queue
            ON interpretation_jobs(interpreter_key, status, available_at, created_at);

        CREATE TABLE IF NOT EXISTS analysis_bundles (
            analysis_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL REFERENCES evidence_units(evidence_id),
            job_id TEXT NOT NULL UNIQUE REFERENCES interpretation_jobs(job_id),
            analyzer TEXT NOT NULL,
            analyzer_version TEXT,
            configuration_json TEXT NOT NULL,
            raw_payload BLOB NOT NULL,
            raw_content_type TEXT NOT NULL,
            raw_sha256 TEXT NOT NULL,
            bundle_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS analyses_by_evidence
            ON analysis_bundles(evidence_id, created_at);

        CREATE TABLE IF NOT EXISTS interpretation_hypotheses (
            hypothesis_id TEXT PRIMARY KEY,
            analysis_id TEXT NOT NULL REFERENCES analysis_bundles(analysis_id),
            segment_index INTEGER NOT NULL,
            rank_number INTEGER NOT NULL,
            initial_score REAL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hypothesis_revisions (
            revision_id TEXT PRIMARY KEY,
            hypothesis_id TEXT NOT NULL
                REFERENCES interpretation_hypotheses(hypothesis_id),
            evidence_id TEXT NOT NULL REFERENCES evidence_units(evidence_id),
            score REAL NOT NULL,
            operation TEXT NOT NULL,
            derivation_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS revisions_by_hypothesis
            ON hypothesis_revisions(hypothesis_id, created_at);

        CREATE TRIGGER IF NOT EXISTS evidence_units_no_update
        BEFORE UPDATE ON evidence_units BEGIN
            SELECT RAISE(ABORT, 'evidence is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS evidence_units_no_delete
        BEFORE DELETE ON evidence_units BEGIN
            SELECT RAISE(ABORT, 'evidence is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS analysis_bundles_no_update
        BEFORE UPDATE ON analysis_bundles BEGIN
            SELECT RAISE(ABORT, 'analysis is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS analysis_bundles_no_delete
        BEFORE DELETE ON analysis_bundles BEGIN
            SELECT RAISE(ABORT, 'analysis is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS hypotheses_no_update
        BEFORE UPDATE ON interpretation_hypotheses BEGIN
            SELECT RAISE(ABORT, 'hypothesis is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS hypotheses_no_delete
        BEFORE DELETE ON interpretation_hypotheses BEGIN
            SELECT RAISE(ABORT, 'hypothesis is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS revisions_no_update
        BEFORE UPDATE ON hypothesis_revisions BEGIN
            SELECT RAISE(ABORT, 'revision is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS revisions_no_delete
        BEFORE DELETE ON hypothesis_revisions BEGIN
            SELECT RAISE(ABORT, 'revision is immutable');
        END;
        """
        with self._transaction() as connection:
            connection.executescript(schema)
            rows = connection.execute("SELECT version FROM schema_info").fetchall()
            if not rows:
                connection.execute(
                    "INSERT INTO schema_info(version) VALUES (?)", (SCHEMA_VERSION,)
                )
            elif len(rows) != 1 or int(rows[0][0]) != SCHEMA_VERSION:
                raise EvidenceStoreError("unsupported evidence schema version")

    def append(
        self,
        raw: str,
        *,
        stream_id: str,
        kind: str = "text",
        source: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
        context: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        sequence: int | None = None,
        interpreter_key: str = "trips",
    ) -> EvidenceUnit:
        if not isinstance(raw, str) or not raw:
            raise EvidenceStoreError("evidence raw text must be a non-empty string")
        if not stream_id.strip() or not kind.strip() or not interpreter_key.strip():
            raise EvidenceStoreError("stream, kind and interpreter key are required")
        source_value = dict(source or {})
        metadata_value = dict(metadata or {})
        caller_context = dict(context or {})
        # Validate before opening the transaction.
        canonical_json(source_value)
        canonical_json(metadata_value)
        canonical_json(caller_context)
        raw_digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        recorded_at = utc_now()

        with self._transaction() as connection:
            previous = connection.execute(
                """
                SELECT evidence_id, sequence_number
                FROM evidence_units
                WHERE stream_id = ?
                ORDER BY sequence_number DESC
                LIMIT 1
                """,
                (stream_id,),
            ).fetchone()
            next_sequence = 0 if previous is None else int(previous["sequence_number"]) + 1
            active_sequence = next_sequence if sequence is None else sequence
            if active_sequence < 0:
                raise EvidenceStoreError("evidence sequence cannot be negative")
            if previous is not None and active_sequence <= int(previous["sequence_number"]):
                raise EvidenceStoreError("evidence sequence must advance monotonically")

            context_value = {
                "previous": previous["evidence_id"] if previous else None,
                **caller_context,
            }
            identity_material = canonical_json(
                {
                    "stream": stream_id,
                    "sequence": active_sequence,
                    "raw_sha256": raw_digest,
                    "source": source_value,
                }
            )
            evidence_id = "ev_" + hashlib.sha256(
                identity_material.encode("utf-8")
            ).hexdigest()[:32]
            connection.execute(
                """
                INSERT INTO evidence_units(
                    evidence_id, stream_id, sequence_number, kind, raw_text,
                    raw_sha256, source_json, observed_at, context_json,
                    metadata_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    stream_id,
                    active_sequence,
                    kind,
                    raw,
                    raw_digest,
                    canonical_json(source_value),
                    observed_at,
                    canonical_json(context_value),
                    canonical_json(metadata_value),
                    recorded_at,
                ),
            )
            self._insert_job(
                connection,
                evidence_id=evidence_id,
                interpreter_key=interpreter_key,
                generation=0,
                now=recorded_at,
            )

        return EvidenceUnit(
            evidence_id=evidence_id,
            stream_id=stream_id,
            sequence=active_sequence,
            kind=kind,
            raw=raw,
            raw_sha256=raw_digest,
            source=source_value,
            observed_at=observed_at,
            context=context_value,
            metadata=metadata_value,
            recorded_at=recorded_at,
        )

    @staticmethod
    def _insert_job(
        connection: sqlite3.Connection,
        *,
        evidence_id: str,
        interpreter_key: str,
        generation: int,
        now: str,
    ) -> str:
        job_id = "job_" + uuid.uuid4().hex
        connection.execute(
            """
            INSERT INTO interpretation_jobs(
                job_id, evidence_id, interpreter_key, generation, status,
                available_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (job_id, evidence_id, interpreter_key, generation, now, now, now),
        )
        return job_id

    def enqueue_replay(self, evidence_id: str, *, interpreter_key: str) -> str:
        now = utc_now()
        with self._transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM evidence_units WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
            if not exists:
                raise KeyError(evidence_id)
            row = connection.execute(
                """
                SELECT COALESCE(MAX(generation), -1) + 1
                FROM interpretation_jobs
                WHERE evidence_id = ? AND interpreter_key = ?
                """,
                (evidence_id, interpreter_key),
            ).fetchone()
            return self._insert_job(
                connection,
                evidence_id=evidence_id,
                interpreter_key=interpreter_key,
                generation=int(row[0]),
                now=now,
            )

    def get(self, evidence_id: str) -> EvidenceUnit:
        row = self._connection.execute(
            "SELECT * FROM evidence_units WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        return self._evidence_from_row(row)

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row) -> EvidenceUnit:
        return EvidenceUnit(
            evidence_id=row["evidence_id"],
            stream_id=row["stream_id"],
            sequence=int(row["sequence_number"]),
            kind=row["kind"],
            raw=row["raw_text"],
            raw_sha256=row["raw_sha256"],
            source=json.loads(row["source_json"]),
            observed_at=row["observed_at"],
            context=json.loads(row["context_json"]),
            metadata=json.loads(row["metadata_json"]),
            recorded_at=row["recorded_at"],
        )

    def context_before(self, evidence_id: str, *, limit: int) -> tuple[EvidenceUnit, ...]:
        if limit < 0:
            raise ValueError("context limit cannot be negative")
        if limit == 0:
            return ()
        target = self.get(evidence_id)
        rows = self._connection.execute(
            """
            SELECT * FROM (
                SELECT * FROM evidence_units
                WHERE stream_id = ? AND sequence_number < ?
                ORDER BY sequence_number DESC
                LIMIT ?
            ) ORDER BY sequence_number ASC
            """,
            (target.stream_id, target.sequence, limit),
        ).fetchall()
        return tuple(self._evidence_from_row(row) for row in rows)

    def list_stream(self, stream_id: str) -> tuple[EvidenceUnit, ...]:
        rows = self._connection.execute(
            """
            SELECT * FROM evidence_units
            WHERE stream_id = ? ORDER BY sequence_number
            """,
            (stream_id,),
        ).fetchall()
        return tuple(self._evidence_from_row(row) for row in rows)

    def claim_next(
        self, *, interpreter_key: str, lease_seconds: float = 60.0
    ) -> ProcessingJob | None:
        if lease_seconds <= 0:
            raise ValueError("lease must be positive")
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat(timespec="microseconds")
        leased_until = (now_dt + timedelta(seconds=lease_seconds)).isoformat(
            timespec="microseconds"
        )
        token = uuid.uuid4().hex
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM interpretation_jobs
                WHERE interpreter_key = ?
                  AND available_at <= ?
                  AND (
                    status = 'pending'
                    OR (status = 'processing' AND leased_until < ?)
                  )
                ORDER BY created_at, generation
                LIMIT 1
                """,
                (interpreter_key, now, now),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE interpretation_jobs
                SET status = 'processing', attempts = attempts + 1,
                    leased_until = ?, lease_token = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (leased_until, token, now, row["job_id"]),
            )
            return ProcessingJob(
                job_id=row["job_id"],
                evidence_id=row["evidence_id"],
                interpreter_key=row["interpreter_key"],
                generation=int(row["generation"]),
                status="processing",
                attempts=int(row["attempts"]) + 1,
                lease_token=token,
            )

    def fail_job(
        self,
        job: ProcessingJob,
        error: str,
        *,
        retry: bool = False,
        retry_after_seconds: float = 0,
    ) -> None:
        if not job.lease_token:
            raise EvidenceStoreError("cannot fail an unleased job")
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat(timespec="microseconds")
        available = (now_dt + timedelta(seconds=retry_after_seconds)).isoformat(
            timespec="microseconds"
        )
        with self._transaction() as connection:
            result = connection.execute(
                """
                UPDATE interpretation_jobs
                SET status = ?, available_at = ?, leased_until = NULL,
                    lease_token = NULL, last_error = ?, updated_at = ?
                WHERE job_id = ? AND status = 'processing' AND lease_token = ?
                """,
                (
                    "pending" if retry else "failed",
                    available,
                    error[:4000],
                    now,
                    job.job_id,
                    job.lease_token,
                ),
            )
            if result.rowcount != 1:
                raise EvidenceStoreError("job lease is no longer owned")

    def persist_analysis(self, job: ProcessingJob, bundle: AnalysisBundle) -> None:
        if not job.lease_token:
            raise EvidenceStoreError("cannot complete an unleased job")
        if bundle.evidence_id != job.evidence_id:
            raise EvidenceStoreError("analysis targets a different evidence unit")
        if hashlib.sha256(bundle.raw_payload).hexdigest() != bundle.raw_sha256:
            raise EvidenceStoreError("analysis raw payload digest mismatch")
        created_at = utc_now()
        serialized = canonical_json(bundle.as_dict())
        with self._transaction() as connection:
            owned = connection.execute(
                """
                SELECT 1 FROM interpretation_jobs
                WHERE job_id = ? AND status = 'processing' AND lease_token = ?
                """,
                (job.job_id, job.lease_token),
            ).fetchone()
            if not owned:
                raise EvidenceStoreError("job lease is no longer owned")
            connection.execute(
                """
                INSERT INTO analysis_bundles(
                    analysis_id, evidence_id, job_id, analyzer,
                    analyzer_version, configuration_json, raw_payload,
                    raw_content_type, raw_sha256, bundle_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.analysis_id,
                    bundle.evidence_id,
                    job.job_id,
                    bundle.analyzer,
                    bundle.analyzer_version,
                    canonical_json(bundle.analyzer_configuration),
                    bundle.raw_payload,
                    bundle.raw_content_type,
                    bundle.raw_sha256,
                    serialized,
                    created_at,
                ),
            )
            for segment in bundle.segments:
                for hypothesis in segment.hypotheses:
                    connection.execute(
                        """
                        INSERT INTO interpretation_hypotheses(
                            hypothesis_id, analysis_id, segment_index,
                            rank_number, initial_score, payload_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            hypothesis.hypothesis_id,
                            bundle.analysis_id,
                            segment.segment_index,
                            hypothesis.rank,
                            hypothesis.score,
                            canonical_json(hypothesis.as_dict()),
                            created_at,
                        ),
                    )
            connection.execute(
                """
                UPDATE interpretation_jobs
                SET status = 'complete', leased_until = NULL, lease_token = NULL,
                    last_error = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                (created_at, job.job_id),
            )

    def load_analysis(self, analysis_id: str) -> AnalysisBundle:
        row = self._connection.execute(
            "SELECT * FROM analysis_bundles WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        if row is None:
            raise KeyError(analysis_id)
        return AnalysisBundle.from_dict(
            json.loads(row["bundle_json"]), raw_payload=bytes(row["raw_payload"])
        )

    def analyses_for(self, evidence_id: str) -> tuple[AnalysisBundle, ...]:
        rows = self._connection.execute(
            """
            SELECT analysis_id FROM analysis_bundles
            WHERE evidence_id = ? ORDER BY created_at, rowid
            """,
            (evidence_id,),
        ).fetchall()
        return tuple(self.load_analysis(row[0]) for row in rows)

    def revise(
        self,
        hypothesis_id: str,
        *,
        evidence_id: str,
        score: float,
        operation: str,
        derivation: Mapping[str, Any] | None = None,
    ) -> str:
        if not operation.strip():
            raise EvidenceStoreError("revision operation is required")
        if not isinstance(score, (float, int)):
            raise EvidenceStoreError("revision score must be numeric")
        derivation_value = dict(derivation or {})
        canonical_json(derivation_value)
        identity = canonical_json(
            {
                "hypothesis": hypothesis_id,
                "evidence": evidence_id,
                "score": float(score),
                "operation": operation,
                "derivation": derivation_value,
                "nonce": uuid.uuid4().hex,
            }
        )
        revision_id = "rev_" + hashlib.sha256(identity.encode()).hexdigest()[:32]
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO hypothesis_revisions(
                    revision_id, hypothesis_id, evidence_id, score, operation,
                    derivation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    hypothesis_id,
                    evidence_id,
                    float(score),
                    operation,
                    canonical_json(derivation_value),
                    utc_now(),
                ),
            )
        return revision_id

    def hypothesis_history(self, hypothesis_id: str) -> tuple[dict[str, Any], ...]:
        initial = self._connection.execute(
            """
            SELECT hypothesis_id, initial_score, created_at
            FROM interpretation_hypotheses WHERE hypothesis_id = ?
            """,
            (hypothesis_id,),
        ).fetchone()
        if initial is None:
            raise KeyError(hypothesis_id)
        history: list[dict[str, Any]] = [
            {
                "kind": "initial",
                "score": initial["initial_score"],
                "created_at": initial["created_at"],
            }
        ]
        rows = self._connection.execute(
            """
            SELECT * FROM hypothesis_revisions
            WHERE hypothesis_id = ? ORDER BY created_at, rowid
            """,
            (hypothesis_id,),
        ).fetchall()
        history.extend(
            {
                "kind": "revision",
                "revision_id": row["revision_id"],
                "evidence_id": row["evidence_id"],
                "score": row["score"],
                "operation": row["operation"],
                "derivation": json.loads(row["derivation_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        )
        return tuple(history)

    def trace(self, evidence_id: str) -> dict[str, Any]:
        evidence = self.get(evidence_id)
        jobs = self._connection.execute(
            """
            SELECT job_id, interpreter_key, generation, status, attempts,
                   last_error, created_at, updated_at
            FROM interpretation_jobs
            WHERE evidence_id = ? ORDER BY created_at, generation
            """,
            (evidence_id,),
        ).fetchall()
        analyses = self.analyses_for(evidence_id)
        hypothesis_rows: list[dict[str, Any]] = []
        for bundle in analyses:
            for hypothesis in bundle.hypotheses:
                hypothesis_rows.append(
                    {
                        "id": hypothesis.hypothesis_id,
                        "analysis_id": bundle.analysis_id,
                        "history": list(self.hypothesis_history(hypothesis.hypothesis_id)),
                    }
                )
        return {
            "evidence": evidence.as_dict(),
            "jobs": [dict(row) for row in jobs],
            "analyses": [bundle.as_dict() for bundle in analyses],
            "hypotheses": hypothesis_rows,
        }

    def counts(self) -> dict[str, int]:
        tables: Sequence[str] = (
            "evidence_units",
            "interpretation_jobs",
            "analysis_bundles",
            "interpretation_hypotheses",
            "hypothesis_revisions",
        )
        return {
            table: int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }
