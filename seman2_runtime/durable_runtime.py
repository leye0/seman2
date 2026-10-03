"""Noyau durable minimal du graphe runtime événementiel.

Ce module ne contient aucune cognition. Il garantit que les composants ne
peuvent publier que des artefacts attribués, reliés à leurs vrais parents et
autorisés par le graphe runtime cible.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .contracts import ContractError, canonical_json


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    component_id: str
    kind: str
    epoch: int
    payload: dict[str, Any]
    parent_ids: tuple[str, ...]
    payload_sha256: str
    sequence: int


class RuntimePlan:
    def __init__(self, path: Path) -> None:
        value = json.loads(path.read_text())
        self.path = path
        self.nodes = {row["id"]: row for row in value["nodes"]}
        self.edges = {
            (row["from"], row["to"]): row
            for row in value["edges"]
        }
        if len(self.nodes) != len(value["nodes"]):
            raise ContractError("runtime plan: composant dupliqué")
        if len(self.edges) != len(value["edges"]):
            raise ContractError("runtime plan: frontière dupliquée")

    def edge(self, source: str, target: str) -> dict:
        try:
            return self.edges[(source, target)]
        except KeyError as exc:
            raise ContractError(f"frontière runtime interdite: {source} -> {target}") from exc


class DurableRuntimeStore:
    """Store SQLite append-only avec journal et dépendances explicites."""

    def __init__(self, path: Path, plan: RuntimePlan) -> None:
        self.path = path
        self.plan = plan
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "DurableRuntimeStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id TEXT NOT NULL UNIQUE,
                component_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                epoch INTEGER NOT NULL CHECK(epoch >= 0),
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS artifact_parents (
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                parent_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                ordinal INTEGER NOT NULL,
                PRIMARY KEY(artifact_id, parent_id),
                UNIQUE(artifact_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS runtime_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                epoch INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                component_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                payload_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS component_offsets (
                component_id TEXT PRIMARY KEY,
                last_event_sequence INTEGER NOT NULL,
                last_artifact_id TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def record_artifact(
        self,
        *,
        artifact_id: str,
        component_id: str,
        kind: str,
        epoch: int,
        payload: dict[str, Any],
        parent_ids: tuple[str, ...],
        idempotency_key: str,
    ) -> ArtifactRecord:
        if component_id not in self.plan.nodes:
            raise ContractError(f"composant runtime inconnu: {component_id}")
        if not artifact_id or not kind or not idempotency_key:
            raise ContractError("artefact runtime: identifiant, type et clé d'idempotence requis")
        if epoch < 0:
            raise ContractError("artefact runtime: epoch négative")
        if len(set(parent_ids)) != len(parent_ids):
            raise ContractError("artefact runtime: parent dupliqué")
        # Une source peut démarrer une session sans parent ou être matérialisée
        # en réponse à une récupération contrôlée à l'époque précédente. Dans
        # ce second cas, la frontière de feedback du plan est vérifiée comme
        # toutes les autres ci-dessous.
        if component_id != "source-reader" and not parent_ids:
            raise ContractError(f"{component_id}: au moins un parent bas niveau est requis")

        payload_json = canonical_json(payload)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        with self.transaction():
            existing = self.connection.execute(
                "SELECT artifact_id, payload_sha256 FROM artifacts WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing["artifact_id"] != artifact_id or existing["payload_sha256"] != payload_hash:
                    raise ContractError("conflit d'idempotence: même clé, contenu différent")
                return self.get_artifact(existing["artifact_id"])

            parents = []
            for parent_id in parent_ids:
                parent = self.connection.execute(
                    "SELECT artifact_id, component_id, epoch FROM artifacts WHERE artifact_id=?",
                    (parent_id,),
                ).fetchone()
                if parent is None:
                    raise ContractError(f"parent runtime absent: {parent_id}")
                edge = self.plan.edge(parent["component_id"], component_id)
                required_epoch = parent["epoch"] + edge["epoch_delta"]
                if epoch != required_epoch:
                    raise ContractError(
                        f"epoch incompatible {parent_id} -> {artifact_id}: attendu {required_epoch}, reçu {epoch}"
                    )
                parents.append(parent)

            cursor = self.connection.execute(
                """
                INSERT INTO artifacts(
                    artifact_id, component_id, kind, epoch, payload_json,
                    payload_sha256, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, component_id, kind, epoch, payload_json, payload_hash, idempotency_key),
            )
            for ordinal, parent_id in enumerate(parent_ids):
                self.connection.execute(
                    "INSERT INTO artifact_parents(artifact_id, parent_id, ordinal) VALUES (?, ?, ?)",
                    (artifact_id, parent_id, ordinal),
                )
            event_id = f"event:{artifact_id}"
            event = self.connection.execute(
                """
                INSERT INTO runtime_events(
                    event_id, epoch, event_type, component_id, artifact_id, payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, epoch, "artifact-committed", component_id, artifact_id, payload_hash),
            )
            self.connection.execute(
                """
                INSERT INTO component_offsets(component_id, last_event_sequence, last_artifact_id)
                VALUES (?, ?, ?)
                ON CONFLICT(component_id) DO UPDATE SET
                    last_event_sequence=excluded.last_event_sequence,
                    last_artifact_id=excluded.last_artifact_id
                """,
                (component_id, event.lastrowid, artifact_id),
            )
            sequence = cursor.lastrowid
        return ArtifactRecord(
            artifact_id, component_id, kind, epoch, payload, parent_ids, payload_hash, sequence
        )

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        row = self.connection.execute(
            "SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)
        ).fetchone()
        if row is None:
            raise ContractError(f"artefact runtime absent: {artifact_id}")
        parents = self.connection.execute(
            "SELECT parent_id FROM artifact_parents WHERE artifact_id=? ORDER BY ordinal",
            (artifact_id,),
        ).fetchall()
        return ArtifactRecord(
            artifact_id=row["artifact_id"],
            component_id=row["component_id"],
            kind=row["kind"],
            epoch=row["epoch"],
            payload=json.loads(row["payload_json"]),
            parent_ids=tuple(parent["parent_id"] for parent in parents),
            payload_sha256=row["payload_sha256"],
            sequence=row["sequence"],
        )

    def list_artifacts(
        self,
        *,
        component_id: str | None = None,
        kind: str | None = None,
        epoch: int | None = None,
    ) -> list[ArtifactRecord]:
        clauses: list[str] = []
        parameters: list[Any] = []
        for column, value in (
            ("component_id", component_id),
            ("kind", kind),
            ("epoch", epoch),
        ):
            if value is not None:
                clauses.append(f"{column}=?")
                parameters.append(value)
        sql = "SELECT artifact_id FROM artifacts"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY sequence"
        return [
            self.get_artifact(row["artifact_id"])
            for row in self.connection.execute(sql, parameters).fetchall()
        ]

    def ancestry(self, artifact_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            WITH RECURSIVE ancestors(artifact_id, depth) AS (
                SELECT ?, 0
                UNION ALL
                SELECT p.parent_id, a.depth + 1
                FROM ancestors a JOIN artifact_parents p ON p.artifact_id = a.artifact_id
            )
            SELECT a.artifact_id, min(a.depth) AS depth, r.component_id, r.kind,
                   r.epoch, r.payload_sha256
            FROM ancestors a JOIN artifacts r USING(artifact_id)
            GROUP BY a.artifact_id, r.component_id, r.kind, r.epoch, r.payload_sha256
            ORDER BY depth, a.artifact_id
            """,
            (artifact_id,),
        ).fetchall()
        if not rows:
            raise ContractError(f"artefact runtime absent: {artifact_id}")
        return [dict(row) for row in rows]

    def metrics(self) -> dict[str, Any]:
        artifact_count = self.connection.execute("SELECT count(*) FROM artifacts").fetchone()[0]
        event_count = self.connection.execute("SELECT count(*) FROM runtime_events").fetchone()[0]
        epochs = self.connection.execute("SELECT count(DISTINCT epoch) FROM artifacts").fetchone()[0]
        return {
            "artifacts": artifact_count,
            "events": event_count,
            "epochs": epochs,
            "sqlite_bytes": self.path.stat().st_size if self.path.exists() else 0,
            "journal_mode": self.connection.execute("PRAGMA journal_mode").fetchone()[0],
            "foreign_keys": bool(self.connection.execute("PRAGMA foreign_keys").fetchone()[0]),
        }

    def checkpoint_database(self, destination: Path) -> dict[str, Any]:
        """Crée une copie SQLite cohérente sans exposer le WAL au restaurateur."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        if temporary.exists():
            temporary.unlink()
        target = sqlite3.connect(temporary)
        try:
            self.connection.backup(target)
        finally:
            target.close()
        temporary.replace(destination)
        digest = hashlib.sha256()
        with destination.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return {
            "path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": digest.hexdigest(),
            "last_event_sequence": self.connection.execute(
                "SELECT coalesce(max(sequence), 0) FROM runtime_events"
            ).fetchone()[0],
            "artifact_count": self.connection.execute("SELECT count(*) FROM artifacts").fetchone()[0],
        }
