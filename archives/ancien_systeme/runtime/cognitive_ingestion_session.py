"""Boucle d'ingestion suspendable avec checkpoint cognitif coordonné."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping

from .cognitive_ingestion import IngestionPolicy, IngestionRecord, ingest_records
from .cognitive_runtime import CognitiveRuntime
from .cognitive_scheduler import ModuleSpec
from .cognitive_artifacts import ArtifactTypeRegistry
from .contracts import ContractError, canonical_json


SESSION_FORMAT = "seman2-ingestion-session-checkpoint"


class CognitiveIngestionSession:
    def __init__(
        self,
        *,
        runtime: CognitiveRuntime,
        records: Iterable[IngestionRecord],
        policy: IngestionPolicy,
        session_id: str,
        next_record_index: int = 0,
    ) -> None:
        self.runtime = runtime
        self.records = tuple(records)
        self.policy = policy
        self.session_id = session_id
        self.next_record_index = next_record_index
        if len(self.records) > policy.max_records:
            raise ContractError("session ingestion: source au-delà de max_records")
        if not 0 <= next_record_index <= len(self.records):
            raise ContractError("session ingestion: curseur invalide")
        if len({row.record_id for row in self.records}) != len(self.records):
            raise ContractError("session ingestion: record_id dupliqué")

    @property
    def complete(self) -> bool:
        return self.next_record_index == len(self.records)

    def run(self, *, max_records: int | None = None) -> int:
        if max_records is not None and max_records <= 0:
            raise ContractError("session ingestion: max_records doit être positif")
        processed = 0
        while not self.complete and (max_records is None or processed < max_records):
            record = self.records[self.next_record_index]
            # Une observation est stabilisée avant l'avancement du curseur.
            ingest_records(
                self.runtime,
                (record,),
                policy=self.policy,
                session_id=self.session_id,
                starting_wave=self.next_record_index,
            )
            self.next_record_index += 1
            processed += 1
        return processed

    def snapshot(self) -> dict[str, Any]:
        if self.runtime.scheduler.pending_count:
            raise ContractError("session ingestion: checkpoint avec tâches pendantes")
        return {
            "format": SESSION_FORMAT,
            "runtime": self.runtime.snapshot(),
            "session": {
                "session_id": self.session_id,
                "next_record_index": self.next_record_index,
                "record_ids": [row.record_id for row in self.records],
                "policy": {
                    "max_records": self.policy.max_records,
                    "max_text_chars": self.policy.max_text_chars,
                },
            },
        }

    def checkpoint(self, path: str | os.PathLike[str]) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = self.snapshot()
        envelope = {
            "payload": payload,
            "sha256": hashlib.sha256(canonical_json(payload).encode()).hexdigest(),
        }
        encoded = (canonical_json(envelope) + "\n").encode()
        maximum = self.runtime.control.limits.max_checkpoint_mib * 1024 * 1024
        if len(encoded) > maximum:
            raise ContractError("session ingestion: checkpoint hors limite d'espace")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return destination

    @classmethod
    def restore(
        cls,
        path: str | os.PathLike[str],
        *,
        records: Iterable[IngestionRecord],
        registry: ArtifactTypeRegistry,
        modules: Iterable[ModuleSpec],
    ) -> "CognitiveIngestionSession":
        try:
            envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"checkpoint session illisible: {exc}") from exc
        payload = envelope.get("payload")
        if not isinstance(payload, Mapping):
            raise ContractError("checkpoint session: payload absent")
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        if envelope.get("sha256") != digest:
            raise ContractError("checkpoint session: empreinte invalide")
        if payload.get("format") != SESSION_FORMAT:
            raise ContractError("checkpoint session: format incompatible")
        rows = tuple(records)
        session = payload["session"]
        if [row.record_id for row in rows] != session["record_ids"]:
            raise ContractError("checkpoint session: source ou ordre incompatible")
        policy = IngestionPolicy(**session["policy"])
        runtime = CognitiveRuntime.restore_snapshot(
            payload["runtime"], registry=registry, modules=modules
        )
        return cls(
            runtime=runtime,
            records=rows,
            policy=policy,
            session_id=session["session_id"],
            next_record_index=session["next_record_index"],
        )
