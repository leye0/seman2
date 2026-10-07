"""Session coordonnée entre analyse formelle et nouveau cœur développemental."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping

from .cognitive_artifacts import ArtifactTypeRegistry
from .cognitive_ingestion import IngestionPolicy, IngestionRecord
from .cognitive_ingestion_session import CognitiveIngestionSession, SESSION_FORMAT
from .cognitive_runtime import CognitiveRuntime
from .cognitive_scheduler import ModuleSpec
from .contracts import ContractError, canonical_json
from .developmental_core import ContextFrame, ContextKind, DevelopmentalCore
from .formal_core_adapter import AdaptedSemanticBundle, adapt_semantic_artifact


DEVELOPMENTAL_SESSION_FORMAT = "seman2-developmental-ingestion-session"


class DevelopmentalIngestionSession:
    def __init__(
        self,
        *,
        analysis_session: CognitiveIngestionSession,
        core: DevelopmentalCore | None = None,
        adapted_semantic_refs: Iterable[str] = (),
    ) -> None:
        self.analysis_session = analysis_session
        self.core = core or DevelopmentalCore()
        self.adapted_semantic_refs = set(adapted_semantic_refs)
        self._ensure_model_context()

    @property
    def complete(self) -> bool:
        return self.analysis_session.complete

    @property
    def next_record_index(self) -> int:
        return self.analysis_session.next_record_index

    @property
    def model_context_ref(self) -> str:
        digest = hashlib.sha256(self.analysis_session.session_id.encode()).hexdigest()
        return f"ctx:model:{digest[:24]}"

    def run(self, *, max_records: int | None = None) -> tuple[AdaptedSemanticBundle, ...]:
        if max_records is not None and max_records <= 0:
            raise ContractError("ingestion développementale: max_records doit être positif")
        adapted = []
        processed = 0
        while not self.complete and (max_records is None or processed < max_records):
            before = self.analysis_session.next_record_index
            count = self.analysis_session.run(max_records=1)
            if count != 1 or self.analysis_session.next_record_index != before + 1:
                raise ContractError("ingestion développementale: avancement non atomique")
            adapted.extend(self._adapt_new_semantics())
            self.core.memory.advance()
            processed += 1
        return tuple(adapted)

    def _adapt_new_semantics(self) -> tuple[AdaptedSemanticBundle, ...]:
        rows = [
            row
            for row in self.analysis_session.runtime.arena.query(
                artifact_type="semantic-structure",
                session_id=self.analysis_session.session_id,
            )
            if row.artifact_id not in self.adapted_semantic_refs
        ]
        bundles = []
        for artifact in rows:
            observation_ref = (
                artifact.observation_refs[0]
                if artifact.observation_refs
                else artifact.artifact_id
            )
            experience_context_ref = f"ctx:experience:{observation_ref}"
            self.core.universe.add_context(
                ContextFrame(
                    context_id=experience_context_ref,
                    kind=ContextKind.NARRATED,
                    parent_context_ref=self.model_context_ref,
                    support_refs=(observation_ref,),
                )
            )
            bundle = adapt_semantic_artifact(
                self.core,
                artifact,
                parent_context_ref=experience_context_ref,
                temporal_index=artifact.wave,
            )
            self.adapted_semantic_refs.add(artifact.artifact_id)
            bundles.append(bundle)
        return tuple(bundles)

    def snapshot(self) -> dict[str, Any]:
        if self.analysis_session.runtime.scheduler.pending_count:
            raise ContractError(
                "ingestion développementale: checkpoint avec tâches pendantes"
            )
        return {
            "format": DEVELOPMENTAL_SESSION_FORMAT,
            "analysis_session": self.analysis_session.snapshot(),
            "developmental_core": self.core.as_dict(),
            "adapted_semantic_refs": sorted(self.adapted_semantic_refs),
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
        maximum = (
            self.analysis_session.runtime.control.limits.max_checkpoint_mib
            * 1024
            * 1024
        )
        if len(encoded) > maximum:
            raise ContractError("ingestion développementale: checkpoint hors limite")
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
    ) -> "DevelopmentalIngestionSession":
        try:
            envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(
                f"checkpoint développemental illisible: {exc}"
            ) from exc
        payload = envelope.get("payload")
        if not isinstance(payload, Mapping):
            raise ContractError("checkpoint développemental: payload absent")
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        if envelope.get("sha256") != digest:
            raise ContractError("checkpoint développemental: empreinte invalide")
        if payload.get("format") != DEVELOPMENTAL_SESSION_FORMAT:
            raise ContractError("checkpoint développemental: format incompatible")

        base = payload["analysis_session"]
        if base.get("format") != SESSION_FORMAT:
            raise ContractError("checkpoint développemental: session de base invalide")
        rows = tuple(records)
        session_payload = base["session"]
        if [row.record_id for row in rows] != session_payload["record_ids"]:
            raise ContractError("checkpoint développemental: source ou ordre incompatible")
        analysis_session = CognitiveIngestionSession(
            runtime=CognitiveRuntime.restore_snapshot(
                base["runtime"], registry=registry, modules=modules
            ),
            records=rows,
            policy=IngestionPolicy(**session_payload["policy"]),
            session_id=session_payload["session_id"],
            next_record_index=session_payload["next_record_index"],
        )
        return cls(
            analysis_session=analysis_session,
            core=DevelopmentalCore.restore(payload["developmental_core"]),
            adapted_semantic_refs=payload["adapted_semantic_refs"],
        )

    def report(self, bundles: Iterable[AdaptedSemanticBundle]) -> dict[str, Any]:
        bundle_tuple = tuple(bundles)
        unadapted = [
            row.artifact_id
            for row in self.analysis_session.runtime.arena.query(
                artifact_type="semantic-structure",
                session_id=self.analysis_session.session_id,
            )
            if row.artifact_id not in self.adapted_semantic_refs
        ]
        valid = (
            bool(self.adapted_semantic_refs)
            and not unadapted
            and not self.analysis_session.runtime.scheduler.pending_count
            and all(bundle.relation_refs for bundle in bundle_tuple)
            and all(bundle.distributed_form_refs for bundle in bundle_tuple)
        )
        return {
            "status": (
                "GO-DEVELOPMENTAL-INGESTION-BRIDGE"
                if valid
                else "NO-GO-DEVELOPMENTAL-INGESTION-BRIDGE"
            ),
            "complete": self.complete,
            "next_record_index": self.next_record_index,
            "semantic_analyses_adapted_total": len(self.adapted_semantic_refs),
            "semantic_analyses_adapted_this_run": len(bundle_tuple),
            "unadapted_semantic_refs": unadapted,
            "contexts": len(self.core.universe.contexts),
            "identities": len(self.core.universe.identities),
            "relations": len(self.core.universe.relations),
            "events": len(self.core.universe.events),
            "distributed_forms": len(self.core.forms.as_dict()["forms"]),
            "cognitive_memory_items": len(self.core.memory.as_dict()["items"]),
            "developmental_core_sha256": hashlib.sha256(
                canonical_json(self.core.as_dict()).encode()
            ).hexdigest(),
            "analysis_arena_sha256": hashlib.sha256(
                canonical_json(
                    self.analysis_session.runtime.arena.as_dict()
                ).encode()
            ).hexdigest(),
            "pending_analysis_tasks": self.analysis_session.runtime.scheduler.pending_count,
            "raw_source_queried_by_high_level": False,
            "analysis_candidates_committed_as_truth": False,
        }

    def _ensure_model_context(self) -> None:
        self.core.universe.add_context(
            ContextFrame(self.model_context_ref, ContextKind.CURRENT)
        )
