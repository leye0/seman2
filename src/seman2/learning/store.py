"""Append-only durable ledger for the learned coupled model."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator, Mapping, Sequence

from ..evidence.store import canonical_json, utc_now
from .model import Derivation, LearnedRelation, LearnedStructure, Support


class LearningStore:
    """Durable provenance ledger and synchronization outbox for AtomSpace."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False, timeout=30
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 30000")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

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
        CREATE TABLE IF NOT EXISTS learned_structures (
            structure_id TEXT PRIMARY KEY,
            family TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            derivation_json TEXT NOT NULL,
            score REAL,
            parent_id TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS structures_by_family_fingerprint
            ON learned_structures(family, fingerprint, created_at);

        CREATE TABLE IF NOT EXISTS learned_relations (
            relation_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            derivation_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS relations_from
            ON learned_relations(source_id, relation, created_at);
        CREATE INDEX IF NOT EXISTS relations_to
            ON learned_relations(target_id, relation, created_at);

        CREATE TABLE IF NOT EXISTS structure_support (
            support_id INTEGER PRIMARY KEY AUTOINCREMENT,
            structure_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            analysis_id TEXT NOT NULL DEFAULT '',
            hypothesis_id TEXT NOT NULL DEFAULT '',
            span_json TEXT NOT NULL,
            weight REAL NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(structure_id, evidence_id, analysis_id, hypothesis_id, span_json)
        );
        CREATE INDEX IF NOT EXISTS support_by_structure
            ON structure_support(structure_id, created_at);

        CREATE TABLE IF NOT EXISTS learned_bindings (
            binding_id TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            bindings_json TEXT NOT NULL,
            derivation_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS bindings_by_pattern
            ON learned_bindings(pattern_id, created_at);

        CREATE TABLE IF NOT EXISTS context_statistics (
            statistic_id TEXT PRIMARY KEY,
            structure_id TEXT NOT NULL,
            context_fingerprint TEXT NOT NULL,
            context_json TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(structure_id, context_fingerprint, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS consolidation_runs (
            run_id TEXT PRIMARY KEY,
            algorithm TEXT NOT NULL,
            parameters_json TEXT NOT NULL,
            inputs_json TEXT NOT NULL,
            outputs_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS graph_sync_outbox (
            sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
            object_kind TEXT NOT NULL,
            object_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            synchronized_at TEXT,
            last_error TEXT,
            UNIQUE(object_kind, object_id)
        );

        CREATE TABLE IF NOT EXISTS generation_candidates (
            candidate_id TEXT PRIMARY KEY,
            target_fingerprint TEXT NOT NULL,
            surface_text TEXT NOT NULL,
            structure_json TEXT NOT NULL,
            bindings_json TEXT NOT NULL,
            support_json TEXT NOT NULL,
            score_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS learning_failures (
            failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT NOT NULL,
            input_id TEXT NOT NULL,
            error TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TRIGGER IF NOT EXISTS learned_structures_no_update
        BEFORE UPDATE ON learned_structures BEGIN
            SELECT RAISE(ABORT, 'learned structure is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS learned_structures_no_delete
        BEFORE DELETE ON learned_structures BEGIN
            SELECT RAISE(ABORT, 'learned structure is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS learned_relations_no_update
        BEFORE UPDATE ON learned_relations BEGIN
            SELECT RAISE(ABORT, 'learned relation is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS learned_relations_no_delete
        BEFORE DELETE ON learned_relations BEGIN
            SELECT RAISE(ABORT, 'learned relation is immutable');
        END;
        """
        with self._transaction() as connection:
            connection.executescript(schema)

    def put_structure(self, structure: LearnedStructure) -> bool:
        now = structure.created_at or utc_now()
        payload = canonical_json(structure.as_dict())
        with self._transaction() as connection:
            result = connection.execute(
                """
                INSERT OR IGNORE INTO learned_structures(
                    structure_id, family, fingerprint, payload_json,
                    derivation_json, score, parent_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    structure.structure_id,
                    structure.family,
                    structure.fingerprint,
                    canonical_json(structure.payload),
                    canonical_json(structure.derivation.as_dict()),
                    structure.score,
                    structure.parent_id,
                    now,
                ),
            )
            if result.rowcount:
                connection.execute(
                    """
                    INSERT INTO graph_sync_outbox(
                        object_kind, object_id, payload_json, created_at
                    ) VALUES ('structure', ?, ?, ?)
                    """,
                    (structure.structure_id, payload, now),
                )
            return bool(result.rowcount)

    def put_relation(self, relation: LearnedRelation) -> bool:
        now = relation.created_at or utc_now()
        payload = canonical_json(relation.as_dict())
        with self._transaction() as connection:
            result = connection.execute(
                """
                INSERT OR IGNORE INTO learned_relations(
                    relation_id, source_id, target_id, relation,
                    payload_json, derivation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation.relation_id,
                    relation.source_id,
                    relation.target_id,
                    relation.relation,
                    canonical_json(relation.payload),
                    canonical_json(relation.derivation.as_dict()),
                    now,
                ),
            )
            if result.rowcount:
                connection.execute(
                    """
                    INSERT INTO graph_sync_outbox(
                        object_kind, object_id, payload_json, created_at
                    ) VALUES ('relation', ?, ?, ?)
                    """,
                    (relation.relation_id, payload, now),
                )
            return bool(result.rowcount)

    def add_support(self, support: Support) -> bool:
        with self._transaction() as connection:
            result = connection.execute(
                """
                INSERT OR IGNORE INTO structure_support(
                    structure_id, evidence_id, analysis_id, hypothesis_id,
                    span_json, weight, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    support.structure_id,
                    support.evidence_id,
                    support.analysis_id or "",
                    support.hypothesis_id or "",
                    canonical_json(support.span),
                    support.weight,
                    utc_now(),
                ),
            )
            return bool(result.rowcount)

    def put_binding(
        self,
        binding_id: str,
        pattern_id: str,
        instance_id: str,
        bindings: Mapping[str, Any],
        derivation: Derivation,
    ) -> bool:
        with self._transaction() as connection:
            result = connection.execute(
                """
                INSERT OR IGNORE INTO learned_bindings(
                    binding_id, pattern_id, instance_id, bindings_json,
                    derivation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    binding_id,
                    pattern_id,
                    instance_id,
                    canonical_json(bindings),
                    canonical_json(derivation.as_dict()),
                    utc_now(),
                ),
            )
            return bool(result.rowcount)

    def put_context(
        self,
        statistic_id: str,
        structure_id: str,
        fingerprint: str,
        context: Mapping[str, Any],
        evidence_id: str,
    ) -> bool:
        with self._transaction() as connection:
            result = connection.execute(
                """
                INSERT OR IGNORE INTO context_statistics(
                    statistic_id, structure_id, context_fingerprint,
                    context_json, evidence_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    statistic_id,
                    structure_id,
                    fingerprint,
                    canonical_json(context),
                    evidence_id,
                    utc_now(),
                ),
            )
            return bool(result.rowcount)

    def structures(
        self,
        *,
        family: str | None = None,
        fingerprint: str | None = None,
        limit: int | None = None,
    ) -> tuple[LearnedStructure, ...]:
        clauses: list[str] = []
        values: list[Any] = []
        if family is not None:
            clauses.append("family = ?")
            values.append(family)
        if fingerprint is not None:
            clauses.append("fingerprint = ?")
            values.append(fingerprint)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        suffix = " LIMIT ?" if limit is not None else ""
        if limit is not None:
            values.append(limit)
        rows = self._connection.execute(
            "SELECT * FROM learned_structures" + where + " ORDER BY created_at, rowid" + suffix,
            values,
        ).fetchall()
        return tuple(self._structure_from_row(row) for row in rows)

    def get_structure(self, structure_id: str) -> LearnedStructure:
        row = self._connection.execute(
            "SELECT * FROM learned_structures WHERE structure_id = ?", (structure_id,)
        ).fetchone()
        if row is None:
            raise KeyError(structure_id)
        return self._structure_from_row(row)

    @staticmethod
    def _structure_from_row(row: sqlite3.Row) -> LearnedStructure:
        import json

        raw = json.loads(row["derivation_json"])
        return LearnedStructure(
            structure_id=row["structure_id"],
            family=row["family"],
            fingerprint=row["fingerprint"],
            payload=json.loads(row["payload_json"]),
            derivation=Derivation(
                algorithm=raw["algorithm"],
                version=raw["version"],
                parameters=raw.get("parameters", {}),
                inputs=tuple(raw.get("inputs", ())),
            ),
            score=row["score"],
            parent_id=row["parent_id"],
            created_at=row["created_at"],
        )

    def relations(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        import json

        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("source_id", source_id),
            ("target_id", target_id),
            ("relation", relation),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self._connection.execute(
            "SELECT * FROM learned_relations" + where + " ORDER BY created_at, rowid",
            values,
        ).fetchall()
        return tuple(
            {
                "id": row["relation_id"],
                "source": row["source_id"],
                "target": row["target_id"],
                "relation": row["relation"],
                "payload": json.loads(row["payload_json"]),
                "derivation": json.loads(row["derivation_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        )

    def support_count(self, structure_id: str) -> int:
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM structure_support WHERE structure_id = ?",
                (structure_id,),
            ).fetchone()[0]
        )

    def supports(self, structure_id: str) -> tuple[dict[str, Any], ...]:
        import json

        rows = self._connection.execute(
            """
            SELECT * FROM structure_support
            WHERE structure_id = ? ORDER BY created_at, support_id
            """,
            (structure_id,),
        ).fetchall()
        return tuple(
            {
                "evidence_id": row["evidence_id"],
                "analysis_id": row["analysis_id"] or None,
                "hypothesis_id": row["hypothesis_id"] or None,
                "span": json.loads(row["span_json"]),
                "weight": row["weight"],
                "created_at": row["created_at"],
            }
            for row in rows
        )

    def structures_for_evidence(self, evidence_id: str) -> tuple[LearnedStructure, ...]:
        rows = self._connection.execute(
            """
            SELECT DISTINCT s.*
            FROM learned_structures AS s
            JOIN structure_support AS p ON p.structure_id = s.structure_id
            WHERE p.evidence_id = ?
            ORDER BY s.created_at, s.rowid
            """,
            (evidence_id,),
        ).fetchall()
        return tuple(self._structure_from_row(row) for row in rows)

    def pending_sync(self, *, limit: int = 1000) -> tuple[dict[str, Any], ...]:
        import json

        rows = self._connection.execute(
            """
            SELECT * FROM graph_sync_outbox
            WHERE synchronized_at IS NULL ORDER BY sequence_number LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(
            {
                "sequence": row["sequence_number"],
                "kind": row["object_kind"],
                "id": row["object_id"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        )

    def mark_synchronized(self, sequence: int) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE graph_sync_outbox
                SET synchronized_at = ?, last_error = NULL
                WHERE sequence_number = ? AND synchronized_at IS NULL
                """,
                (utc_now(), sequence),
            )

    def mark_sync_error(self, sequence: int, error: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE graph_sync_outbox SET last_error = ? WHERE sequence_number = ?",
                (error[:4000], sequence),
            )

    def record_run(
        self,
        run_id: str,
        *,
        algorithm: str,
        parameters: Mapping[str, Any],
        inputs: Sequence[str],
        outputs: Sequence[str],
        status: str = "complete",
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO consolidation_runs(
                    run_id, algorithm, parameters_json, inputs_json,
                    outputs_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    algorithm,
                    canonical_json(parameters),
                    canonical_json(list(inputs)),
                    canonical_json(list(outputs)),
                    status,
                    utc_now(),
                ),
            )

    def put_generation(
        self,
        candidate_id: str,
        *,
        target_fingerprint: str,
        surface: str,
        structure: Mapping[str, Any],
        bindings: Mapping[str, Any],
        support: Sequence[str],
        score: Mapping[str, Any],
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO generation_candidates(
                    candidate_id, target_fingerprint, surface_text,
                    structure_json, bindings_json, support_json, score_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    target_fingerprint,
                    surface,
                    canonical_json(structure),
                    canonical_json(bindings),
                    canonical_json(list(support)),
                    canonical_json(score),
                    utc_now(),
                ),
            )

    def record_failure(self, stage: str, input_id: str, error: str) -> None:
        """Keep a durable diagnostic without invalidating persisted evidence."""
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO learning_failures(stage, input_id, error, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (stage, input_id, error[:8000], utc_now()),
            )

    def failures(self, *, limit: int = 100) -> tuple[dict[str, Any], ...]:
        rows = self._connection.execute(
            """
            SELECT failure_id, stage, input_id, error, created_at
            FROM learning_failures ORDER BY failure_id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def trace(self, structure_id: str) -> dict[str, Any]:
        structure = self.get_structure(structure_id)
        return {
            "structure": structure.as_dict(),
            "supports": list(self.supports(structure_id)),
            "incoming": list(self.relations(target_id=structure_id)),
            "outgoing": list(self.relations(source_id=structure_id)),
        }

    def counts(self) -> dict[str, int]:
        tables: Sequence[str] = (
            "learned_structures",
            "learned_relations",
            "structure_support",
            "learned_bindings",
            "context_statistics",
            "consolidation_runs",
            "graph_sync_outbox",
            "generation_candidates",
            "learning_failures",
        )
        return {
            table: int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }
