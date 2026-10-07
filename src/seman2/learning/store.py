"""Memory-first ledger for the learned coupled model.

The active working set (the "conscience") lives in RAM under a configurable
capacity. SQLite is the cold, durable archive: writes are batched, rare
lookups fall through to disk. Nothing is lost on eviction — only the RAM
copy is dropped after a flush.
"""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Iterator, Mapping, Sequence

from ..evidence.store import canonical_json, utc_now
from .model import Derivation, LearnedRelation, LearnedStructure, Support


DEFAULT_WORKING_SET_CAPACITY = 250_000

# Families that constitute the active model ("conscience"): they stay in RAM
# unless the working set is under extreme pressure. Observations evict first.
STICKY_FAMILIES = frozenset(
    {
        "dop-fragment",
        "pattern",
        "alignment",
        "fragment-match",
        "structural-fragment",
        "coupled-pattern",
    }
)


class LearningStore:
    """RAM working set plus a batched, append-only SQLite archive."""

    def __init__(
        self,
        path: str | Path,
        *,
        capacity: int = DEFAULT_WORKING_SET_CAPACITY,
        flush_interval: float = 15.0,
    ) -> None:
        if capacity < 1:
            raise ValueError("working-set capacity must be positive")
        if flush_interval <= 0:
            raise ValueError("flush interval must be positive")
        self.flush_interval = flush_interval
        self._last_flush = time.monotonic()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.capacity = capacity
        self._lock = threading.RLock()
        self._batch_depth = 0
        self._connection = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False, timeout=30
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 30000")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

        # Working set: id -> record. OrderedDict gives cheap LRU.
        self._structures: OrderedDict[str, LearnedStructure] = OrderedDict()
        self._relations: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._supports: dict[str, list[dict[str, Any]]] = {}
        self._bindings: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._contexts: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._runs: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._generations: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._failures: list[dict[str, Any]] = []
        self._pending: list[tuple[str, tuple[Any, ...]]] = []
        self._synced: set[str] = set()
        self._sync_errors: dict[str, str] = {}
        self._structure_order: list[str] = []
        self._by_family: dict[str, list[str]] = {}
        self._by_evidence: dict[str, set[str]] = {}
        self._support_keys: dict[str, set[tuple[Any, ...]]] = {}
        self._families_loaded: set[str] = set()
        # Off unless AtomSpace is present: the outbox doubles every write.
        self.outbox_enabled = False

    def close(self) -> None:
        with self._lock:
            self.flush()
            self._connection.close()

    # ------------------------------------------------------------------
    # Memory / disk split
    # ------------------------------------------------------------------

    @property
    def working_set_size(self) -> int:
        return (
            len(self._structures)
            + len(self._relations)
            + len(self._bindings)
            + len(self._contexts)
        )

    def _remember_structure(self, structure: LearnedStructure) -> bool:
        if structure.structure_id in self._structures:
            self._structures.move_to_end(structure.structure_id)
            return False
        self._structures[structure.structure_id] = structure
        self._structure_order.append(structure.structure_id)
        self._by_family.setdefault(structure.family, []).append(structure.structure_id)
        return True

    def _remember_support(self, structure_id: str, row: dict[str, Any]) -> bool:
        rows = self._supports.setdefault(structure_id, [])
        key = (
            row["evidence_id"],
            row.get("analysis_id") or "",
            row.get("hypothesis_id") or "",
            canonical_json(row.get("span")),
        )
        index = self._support_keys.setdefault(structure_id, set())
        if key in index:
            return False
        index.add(key)
        rows.append(row)
        evidence_id = row["evidence_id"]
        linked = self._by_evidence.setdefault(evidence_id, set())
        linked.add(structure_id)
        return True

    def structures_in_memory(
        self,
        *,
        family: str | None = None,
        limit: int | None = None,
    ) -> tuple[LearnedStructure, ...]:
        """Hot-path read: working set only, never touches disk."""
        with self._lock:
            if family is not None:
                ids = self._by_family.get(family, ())
                rows = [self._structures[i] for i in ids if i in self._structures]
            else:
                rows = list(self._structures.values())
            if limit is not None:
                rows = rows[:limit]
            return tuple(rows)

    def load_family(self, family: str) -> int:
        """Pull one family from the cold archive into the working set."""
        with self._lock:
            if family in self._families_loaded:
                return 0
            self.flush()
            rows = self._connection.execute(
                "SELECT * FROM learned_structures WHERE family = ? ORDER BY created_at, rowid",
                (family,),
            ).fetchall()
            loaded = 0
            for row in rows:
                if self._remember_structure(self._structure_from_row(row)):
                    loaded += 1
            self._families_loaded.add(family)
            self._evict_if_needed()
            return loaded

    def structures_for_evidence_in_memory(self, evidence_id: str) -> tuple[LearnedStructure, ...]:
        with self._lock:
            ids = self._by_evidence.get(evidence_id, ())
            return tuple(self._structures[i] for i in ids if i in self._structures)

    def _evict_if_needed(self) -> None:
        """Drop oldest non-sticky RAM copies once flushed; data remains in SQLite."""
        if self.working_set_size <= self.capacity:
            return
        # Drop cheap caches first, in bulk, without re-scan per item.
        excess = self.working_set_size - self.capacity
        for table in (self._bindings, self._contexts, self._relations):
            while excess > 0 and table:
                table.popitem(last=False)
                excess -= 1
        if excess <= 0:
            return
        # Then non-sticky structures, walking the LRU order once.
        victims = [
            structure_id
            for structure_id, structure in self._structures.items()
            if structure.family not in STICKY_FAMILIES
        ]
        for structure_id in victims[:excess]:
            structure = self._structures.pop(structure_id, None)
            if structure is None:
                continue
            ids = self._by_family.get(structure.family)
            if ids and structure_id in ids:
                ids.remove(structure_id)
            self._supports.pop(structure_id, None)
            self._support_keys.pop(structure_id, None)
            for linked in self._by_evidence.values():
                linked.discard(structure_id)

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Defer disk I/O; the caller may also use this as a semantic marker."""
        with self._lock:
            self._batch_depth += 1
            try:
                yield
            finally:
                self._batch_depth -= 1
                if self._batch_depth == 0:
                    self.flush()

    def flush(self) -> dict[str, int]:
        """Write everything queued in RAM to SQLite in one transaction."""
        with self._lock:
            if self._batch_depth > 0:
                return {"written": 0, "deferred": len(self._pending)}
            if not self._pending:
                return {"written": 0}
            written = 0
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                for kind, args in self._pending:
                    written += self._write(kind, args)
            except BaseException:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
            self._pending.clear()
            self._last_flush = time.monotonic()
            self._evict_if_needed()
            return {"written": written}

    def _write(self, kind: str, args: tuple[Any, ...]) -> int:
        connection = self._connection
        if kind == "structure":
            (
                structure_id,
                family,
                fingerprint,
                payload_json,
                derivation_json,
                score,
                parent_id,
                created_at,
                sync_payload,
            ) = args
            result = connection.execute(
                """
                INSERT OR IGNORE INTO learned_structures(
                    structure_id, family, fingerprint, payload_json,
                    derivation_json, score, parent_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    structure_id,
                    family,
                    fingerprint,
                    payload_json,
                    derivation_json,
                    score,
                    parent_id,
                    created_at,
                ),
            )
            if result.rowcount and self.outbox_enabled:
                connection.execute(
                    """
                    INSERT INTO graph_sync_outbox(
                        object_kind, object_id, payload_json, created_at
                    ) VALUES ('structure', ?, ?, ?)
                    """,
                    (structure_id, sync_payload, created_at),
                )
            return int(result.rowcount)
        if kind == "relation":
            (
                relation_id,
                source_id,
                target_id,
                relation,
                payload_json,
                derivation_json,
                created_at,
                sync_payload,
            ) = args
            result = connection.execute(
                """
                INSERT OR IGNORE INTO learned_relations(
                    relation_id, source_id, target_id, relation,
                    payload_json, derivation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    source_id,
                    target_id,
                    relation,
                    payload_json,
                    derivation_json,
                    created_at,
                ),
            )
            if result.rowcount and self.outbox_enabled:
                connection.execute(
                    """
                    INSERT INTO graph_sync_outbox(
                        object_kind, object_id, payload_json, created_at
                    ) VALUES ('relation', ?, ?, ?)
                    """,
                    (relation_id, sync_payload, created_at),
                )
            return int(result.rowcount)
        if kind == "support":
            return int(
                connection.execute(
                    """
                    INSERT OR IGNORE INTO structure_support(
                        structure_id, evidence_id, analysis_id, hypothesis_id,
                        span_json, weight, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    args,
                ).rowcount
            )
        if kind == "binding":
            return int(
                connection.execute(
                    """
                    INSERT OR IGNORE INTO learned_bindings(
                        binding_id, pattern_id, instance_id, bindings_json,
                        derivation_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    args,
                ).rowcount
            )
        if kind == "context":
            return int(
                connection.execute(
                    """
                    INSERT OR IGNORE INTO context_statistics(
                        statistic_id, structure_id, context_fingerprint,
                        context_json, evidence_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    args,
                ).rowcount
            )
        if kind == "run":
            return int(
                connection.execute(
                    """
                    INSERT OR IGNORE INTO consolidation_runs(
                        run_id, algorithm, parameters_json, inputs_json,
                        outputs_json, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    args,
                ).rowcount
            )
        if kind == "generation":
            return int(
                connection.execute(
                    """
                    INSERT OR IGNORE INTO generation_candidates(
                        candidate_id, target_fingerprint, surface_text,
                        structure_json, bindings_json, support_json, score_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    args,
                ).rowcount
            )
        if kind == "failure":
            return int(
                connection.execute(
                    """
                    INSERT INTO learning_failures(stage, input_id, error, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    args,
                ).rowcount
            )
        if kind == "sync-ok":
            sequence, now = args
            connection.execute(
                """
                UPDATE graph_sync_outbox
                SET synchronized_at = ?, last_error = NULL
                WHERE sequence_number = ? AND synchronized_at IS NULL
                """,
                (now, sequence),
            )
            return 1
        if kind == "sync-error":
            sequence, error = args
            connection.execute(
                "UPDATE graph_sync_outbox SET last_error = ? WHERE sequence_number = ?",
                (error, sequence),
            )
            return 1
        raise ValueError(f"unknown pending kind: {kind}")

    # ------------------------------------------------------------------
    # Schema (cold archive)
    # ------------------------------------------------------------------

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
        with self._lock:
            self._connection.executescript(schema)

    # ------------------------------------------------------------------
    # Writes (RAM first, queued for disk)
    # ------------------------------------------------------------------

    def put_structure(self, structure: LearnedStructure) -> bool:
        with self._lock:
            created = self._remember_structure(structure)
            if not created:
                return False
            now = structure.created_at or utc_now()
            self._pending.append(
                (
                    "structure",
                    (
                        structure.structure_id,
                        structure.family,
                        structure.fingerprint,
                        canonical_json(structure.payload),
                        canonical_json(structure.derivation.as_dict()),
                        structure.score,
                        structure.parent_id,
                        now,
                        canonical_json(structure.as_dict()) if self.outbox_enabled else "",
                    ),
                )
            )
            self._maybe_autoflush()
            return True

    def put_relation(self, relation: LearnedRelation) -> bool:
        with self._lock:
            if relation.relation_id in self._relations:
                self._relations.move_to_end(relation.relation_id)
                return False
            now = relation.created_at or utc_now()
            record = relation.as_dict()
            self._relations[relation.relation_id] = record
            self._pending.append(
                (
                    "relation",
                    (
                        relation.relation_id,
                        relation.source_id,
                        relation.target_id,
                        relation.relation,
                        canonical_json(relation.payload),
                        canonical_json(relation.derivation.as_dict()),
                        now,
                        canonical_json(record) if self.outbox_enabled else "",
                    ),
                )
            )
            self._maybe_autoflush()
            return True

    def add_support(self, support: Support) -> bool:
        with self._lock:
            created = self._remember_support(support.structure_id, support.as_dict())
            if not created:
                return False
            self._pending.append(
                (
                    "support",
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
            )
            self._maybe_autoflush()
            return True

    def put_binding(
        self,
        binding_id: str,
        pattern_id: str,
        instance_id: str,
        bindings: Mapping[str, Any],
        derivation: Derivation,
    ) -> bool:
        with self._lock:
            if binding_id in self._bindings:
                self._bindings.move_to_end(binding_id)
                return False
            self._bindings[binding_id] = {
                "id": binding_id,
                "pattern_id": pattern_id,
                "instance_id": instance_id,
                "bindings": dict(bindings),
                "derivation": derivation.as_dict(),
            }
            self._pending.append(
                (
                    "binding",
                    (
                        binding_id,
                        pattern_id,
                        instance_id,
                        canonical_json(bindings),
                        canonical_json(derivation.as_dict()),
                        utc_now(),
                    ),
                )
            )
            self._maybe_autoflush()
            return True

    def put_context(
        self,
        statistic_id: str,
        structure_id: str,
        fingerprint: str,
        context: Mapping[str, Any],
        evidence_id: str,
    ) -> bool:
        with self._lock:
            if statistic_id in self._contexts:
                self._contexts.move_to_end(statistic_id)
                return False
            self._contexts[statistic_id] = {
                "id": statistic_id,
                "structure_id": structure_id,
                "context_fingerprint": fingerprint,
                "context": dict(context),
                "evidence_id": evidence_id,
            }
            self._pending.append(
                (
                    "context",
                    (
                        statistic_id,
                        structure_id,
                        fingerprint,
                        canonical_json(context),
                        evidence_id,
                        utc_now(),
                    ),
                )
            )
            self._maybe_autoflush()
            return True

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
        with self._lock:
            if run_id in self._runs:
                return
            self._runs[run_id] = {
                "run_id": run_id,
                "algorithm": algorithm,
                "parameters": dict(parameters),
                "inputs": list(inputs),
                "outputs": list(outputs),
                "status": status,
            }
            self._pending.append(
                (
                    "run",
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
            )
            self._maybe_autoflush()

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
        with self._lock:
            if candidate_id in self._generations:
                return
            self._generations[candidate_id] = {
                "id": candidate_id,
                "target_fingerprint": target_fingerprint,
                "surface": surface,
                "structure": dict(structure),
                "bindings": dict(bindings),
                "support": list(support),
                "score": dict(score),
            }
            self._pending.append(
                (
                    "generation",
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
            )
            self._maybe_autoflush()

    def record_failure(self, stage: str, input_id: str, error: str) -> None:
        with self._lock:
            row = {
                "stage": stage,
                "input_id": input_id,
                "error": error[:8000],
                "created_at": utc_now(),
            }
            self._failures.append(row)
            self._pending.append(
                ("failure", (stage, input_id, error[:8000], row["created_at"]))
            )
            self._maybe_autoflush()

    def _maybe_autoflush(self) -> None:
        if self._batch_depth > 0:
            return
        # Only flush on volume. Time-based flush is for idle safety, not for
        # interrupting a hot loop: the working set is the live model.
        if len(self._pending) >= 20000:
            self.flush()
        elif self._pending and time.monotonic() - self._last_flush >= self.flush_interval:
            self.flush()

    # ------------------------------------------------------------------
    # Reads (RAM first, rare fall-through to disk)
    # ------------------------------------------------------------------

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

    def get_structure(self, structure_id: str) -> LearnedStructure:
        with self._lock:
            hit = self._structures.get(structure_id)
            if hit is not None:
                self._structures.move_to_end(structure_id)
                return hit
            self.flush()
            row = self._connection.execute(
                "SELECT * FROM learned_structures WHERE structure_id = ?", (structure_id,)
            ).fetchone()
            if row is None:
                raise KeyError(structure_id)
            structure = self._structure_from_row(row)
            self._remember_structure(structure)
            return structure

    def structures(
        self,
        *,
        family: str | None = None,
        fingerprint: str | None = None,
        limit: int | None = None,
    ) -> tuple[LearnedStructure, ...]:
        with self._lock:
            # During a batch the disk copy may lag behind the working set, so
            # merge RAM and disk rather than depending on a flush.
            self.flush()
            memory_rows = self.structures_in_memory(family=family)
            if fingerprint is not None:
                memory_rows = tuple(
                    row for row in memory_rows if row.fingerprint == fingerprint
                )
            seen = {row.structure_id for row in memory_rows}
            clauses: list[str] = []
            values: list[Any] = []
            if family is not None:
                clauses.append("family = ?")
                values.append(family)
            if fingerprint is not None:
                clauses.append("fingerprint = ?")
                values.append(fingerprint)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            rows = self._connection.execute(
                "SELECT * FROM learned_structures" + where + " ORDER BY created_at, rowid",
                values,
            ).fetchall()
            disk_rows = tuple(
                self._structure_from_row(row)
                for row in rows
                if row["structure_id"] not in seen
            )
            for structure in disk_rows:
                self._remember_structure(structure)
            result = memory_rows + disk_rows
            if limit is not None:
                result = result[:limit]
            return result

    def relations(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        import json

        with self._lock:
            self.flush()
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
        with self._lock:
            rows = self._supports.get(structure_id)
            if rows is not None:
                return len(rows)
            self.flush()
            return int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM structure_support WHERE structure_id = ?",
                    (structure_id,),
                ).fetchone()[0]
            )

    def supports(self, structure_id: str) -> tuple[dict[str, Any], ...]:
        with self._lock:
            rows = self._supports.get(structure_id)
            if rows is not None:
                return tuple(rows)
            self.flush()
            disk_rows = self._connection.execute(
                """
                SELECT * FROM structure_support
                WHERE structure_id = ? ORDER BY created_at, support_id
                """,
                (structure_id,),
            ).fetchall()
            result = tuple(
                {
                    "evidence_id": row["evidence_id"],
                    "analysis_id": row["analysis_id"] or None,
                    "hypothesis_id": row["hypothesis_id"] or None,
                    "span": __import__("json").loads(row["span_json"]),
                    "weight": row["weight"],
                    "created_at": row["created_at"],
                }
                for row in disk_rows
            )
            self._supports[structure_id] = list(result)
            return result

    def structures_for_evidence(self, evidence_id: str) -> tuple[LearnedStructure, ...]:
        with self._lock:
            self.flush()
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
        with self._lock:
            self.flush()
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
                    "payload": __import__("json").loads(row["payload_json"]),
                }
                for row in rows
            )

    def mark_synchronized(self, sequence: int) -> None:
        with self._lock:
            self._pending.append(("sync-ok", (sequence, utc_now())))
            self._maybe_autoflush()

    def mark_sync_error(self, sequence: int, error: str) -> None:
        with self._lock:
            self._pending.append(("sync-error", (sequence, error[:4000])))
            self._maybe_autoflush()

    def failures(self, *, limit: int = 100) -> tuple[dict[str, Any], ...]:
        with self._lock:
            if self._failures:
                return tuple(self._failures[-limit:])
            self.flush()
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
        with self._lock:
            self.flush()
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
            disk = {
                table: int(
                    self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in tables
            }
            disk["working_set"] = self.working_set_size
            disk["pending"] = len(self._pending)
            disk["capacity"] = self.capacity
            return disk
