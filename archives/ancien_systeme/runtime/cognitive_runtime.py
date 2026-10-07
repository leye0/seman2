"""Assemblage et checkpoint coordonné du cœur cognitif en mémoire vive."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactTypeRegistry,
    CognitiveArtifact,
    Residency,
)
from .cognitive_scheduler import CognitiveScheduler, ModuleSpec
from .contracts import ContractError, canonical_json
from .control_state import ControlState


CHECKPOINT_FORMAT = "seman2-cognitive-runtime-checkpoint"


class CognitiveRuntime:
    """Même cœur pour ingestion et chatbot; seul le flux d'entrée diffère."""

    def __init__(
        self,
        *,
        registry: ArtifactTypeRegistry,
        modules: Iterable[ModuleSpec],
        control: ControlState | None = None,
    ) -> None:
        self.registry = registry
        self.modules = tuple(modules)
        self.control = control or ControlState()
        self.arena = ArtifactArena(registry)
        self.scheduler = CognitiveScheduler(
            registry=registry,
            arena=self.arena,
            control=self.control,
            modules=self.modules,
        )

    def submit(self, proposal: ArtifactProposal) -> CognitiveArtifact:
        return self.scheduler.submit(proposal)

    def run(self, *, max_tasks: int | None = None) -> int:
        return self.scheduler.run(max_tasks=max_tasks)

    def consolidate_active_memory(self) -> int:
        """Demote old matter at quiescence without deleting cognitive history."""
        if self.scheduler.pending_count:
            raise ContractError("mémoire active: consolidation avec tâches pendantes")
        active = list(self.arena.query(residency=Residency.ACTIVE))
        maximum = self.control.parameters.max_active_entities
        if len(active) <= maximum:
            return 0
        active.sort(key=lambda row: row.created_sequence)
        demoted = active[: len(active) - maximum]
        for artifact in demoted:
            self.arena.set_residency(
                artifact.artifact_id,
                Residency.LATENT,
                activation=min(
                    self.arena.activation(artifact.artifact_id).activation,
                    self.control.parameters.activation_floor,
                ),
                reason="pression de mémoire de travail après quiescence",
            )
        return len(demoted)

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": CHECKPOINT_FORMAT,
            "registry_digest": self.registry.digest,
            "control": self.control.as_dict(),
            "arena": self.arena.as_dict(),
            "scheduler": self.scheduler.as_dict(),
        }

    def checkpoint(self, path: str | os.PathLike[str]) -> Path:
        """Écrit un snapshot atomique vérifiable sans altérer l'état vivant."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = self.snapshot()
        envelope = {
            "payload": payload,
            "sha256": hashlib.sha256(canonical_json(payload).encode()).hexdigest(),
        }
        encoded = (canonical_json(envelope) + "\n").encode()
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
            directory_descriptor = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
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
        registry: ArtifactTypeRegistry,
        modules: Iterable[ModuleSpec],
    ) -> "CognitiveRuntime":
        try:
            envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"checkpoint cognitif illisible: {exc}") from exc
        payload = envelope.get("payload")
        if not isinstance(payload, Mapping):
            raise ContractError("checkpoint cognitif: payload absent")
        actual_digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        if envelope.get("sha256") != actual_digest:
            raise ContractError("checkpoint cognitif: empreinte invalide")
        return cls.restore_snapshot(payload, registry=registry, modules=modules)

    @classmethod
    def restore_snapshot(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: ArtifactTypeRegistry,
        modules: Iterable[ModuleSpec],
    ) -> "CognitiveRuntime":
        """Restaure depuis un payload déjà vérifié par un coordinateur externe."""
        if payload.get("format") != CHECKPOINT_FORMAT:
            raise ContractError("checkpoint cognitif: format incompatible")
        if payload.get("registry_digest") != registry.digest:
            raise ContractError("checkpoint cognitif: registre incompatible")

        module_tuple = tuple(modules)
        runtime = cls.__new__(cls)
        runtime.registry = registry
        runtime.modules = module_tuple
        runtime.control = ControlState.restore(payload["control"])
        runtime.arena = ArtifactArena.restore(registry, payload["arena"])
        runtime.scheduler = CognitiveScheduler.restore(
            payload["scheduler"],
            registry=registry,
            arena=runtime.arena,
            control=runtime.control,
            modules=module_tuple,
        )
        return runtime
