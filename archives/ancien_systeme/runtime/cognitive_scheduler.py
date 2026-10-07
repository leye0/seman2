"""Ordonnanceur bottom-up déterministe pour les modules cognitifs."""

from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import hashlib
import heapq
import json
from typing import Any, Callable, Iterable, Mapping

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactTypeRegistry,
    CognitiveArtifact,
    Residency,
)
from .contracts import ContractError, canonical_json
from .control_state import ControlState


@dataclass(frozen=True)
class ModuleContext:
    arena: ArtifactArena
    control: ControlState
    scheduled_wave: int
    module_id: str


ModuleHandler = Callable[
    [CognitiveArtifact, ModuleContext], Iterable[ArtifactProposal]
]


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    layer: int
    modes: frozenset[str]
    consumes: frozenset[str]
    produces: frozenset[str]
    producer_build: str
    configuration_digest: str
    handler: ModuleHandler = field(compare=False, repr=False)
    feedback_delay: int = 0
    parallel_safe: bool = False

    def __post_init__(self) -> None:
        for name in ("modes", "consumes", "produces"):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        if not self.module_id or not self.producer_build:
            raise ContractError("module cognitif: identifiant et build requis")
        if self.layer < 0:
            raise ContractError("module cognitif: couche négative")
        if not self.modes or not self.modes <= {"ingestion", "chatbot"}:
            raise ContractError(f"module cognitif: modes invalides {self.modes}")
        if not self.consumes or not self.produces:
            raise ContractError("module cognitif: entrées et sorties requises")
        if self.feedback_delay < 0:
            raise ContractError("module cognitif: délai de feedback négatif")
        if not isinstance(self.parallel_safe, bool):
            raise ContractError("module cognitif: parallel_safe doit être booléen")
        if len(self.configuration_digest) != 64 or not all(
            char in "0123456789abcdef" for char in self.configuration_digest
        ):
            raise ContractError("module cognitif: configuration_digest SHA-256 requis")

    def manifest(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "layer": self.layer,
            "modes": sorted(self.modes),
            "consumes": sorted(self.consumes),
            "produces": sorted(self.produces),
            "producer_build": self.producer_build,
            "configuration_digest": self.configuration_digest,
            "feedback_delay": self.feedback_delay,
            "parallel_safe": self.parallel_safe,
        }


@dataclass(order=True, frozen=True)
class ScheduledTask:
    wave: int
    layer: int
    sequence: int
    module_id: str = field(compare=False)
    trigger_id: str = field(compare=False)

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.module_id, self.trigger_id, self.wave)

    def as_dict(self) -> dict[str, Any]:
        return {
            "wave": self.wave,
            "layer": self.layer,
            "sequence": self.sequence,
            "module_id": self.module_id,
            "trigger_id": self.trigger_id,
        }


class CognitiveScheduler:
    """Exécute des frontières parallélisables, dans un ordre rejouable."""

    def __init__(
        self,
        *,
        registry: ArtifactTypeRegistry,
        arena: ArtifactArena,
        control: ControlState,
        modules: Iterable[ModuleSpec],
    ) -> None:
        if arena.registry.digest != registry.digest:
            raise ContractError("scheduler: registre et Artifact Arena incompatibles")
        self.registry = registry
        self.arena = arena
        self.control = control
        self._modules: dict[str, ModuleSpec] = {}
        self._consumers: dict[str, list[str]] = {}
        self._queue: list[ScheduledTask] = []
        self._queued_keys: set[tuple[str, str, int]] = set()
        self._completed_keys: set[tuple[str, str, int]] = set()
        self._task_sequence = 0
        self._frontier_sequence = 0
        self._work_by_module_wave: dict[tuple[str, int], int] = {}
        self._trace: list[dict[str, Any]] = []
        for module in modules:
            self._register(module)
        if not self._modules:
            raise ContractError("scheduler: aucun module")

    def _register(self, module: ModuleSpec) -> None:
        if module.module_id in self._modules:
            raise ContractError(f"scheduler: module dupliqué {module.module_id}")
        for artifact_type in module.consumes | module.produces:
            self.registry.get(artifact_type)
        for output_type in module.produces:
            output = self.registry.get(output_type)
            if output.layer != module.layer:
                raise ContractError(
                    f"{module.module_id}: sortie {output_type} en L{output.layer}, "
                    f"module déclaré L{module.layer}"
                )
            if output.allowed_producers and module.module_id not in output.allowed_producers:
                raise ContractError(
                    f"{module.module_id}: producteur non autorisé pour {output_type}"
                )
        descends = any(
            self.registry.get(input_type).layer
            > self.registry.get(output_type).layer
            for input_type in module.consumes
            for output_type in module.produces
        )
        if descends and module.feedback_delay < 1:
            raise ContractError(
                f"{module.module_id}: un feedback descendant exige un délai >= 1"
            )
        self._modules[module.module_id] = module
        for input_type in module.consumes:
            self._consumers.setdefault(input_type, []).append(module.module_id)
            self._consumers[input_type].sort()

    @property
    def module_manifest_digest(self) -> str:
        manifest = [
            self._modules[key].manifest() for key in sorted(self._modules)
        ]
        return hashlib.sha256(canonical_json(manifest).encode()).hexdigest()

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def trace(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            dict(row) for row in json.loads(canonical_json(self._trace))
        )

    def submit(self, proposal: ArtifactProposal) -> CognitiveArtifact:
        """Publie une racine/entrée et déclenche ses consommateurs admissibles."""
        artifact = self.arena.publish(proposal)
        self._apply_activation_policy(artifact, proposal.activation)
        self._enqueue_consumers(artifact)
        return artifact

    def _apply_activation_policy(
        self, artifact: CognitiveArtifact, activation: float
    ) -> None:
        if activation < self.control.parameters.activation_floor:
            self.arena.set_residency(
                artifact.artifact_id,
                Residency.LATENT,
                activation=activation,
                reason="sous le seuil d'activation de la mémoire de travail",
            )

    def _enqueue_consumers(self, artifact: CognitiveArtifact) -> None:
        record = self.arena.activation(artifact.artifact_id)
        if record.residency is not Residency.ACTIVE:
            return
        if artifact.derivation_depth >= self.control.parameters.max_derivation_depth:
            return
        for module_id in self._consumers.get(artifact.artifact_type, ()):
            module = self._modules[module_id]
            if artifact.mode not in module.modes:
                continue
            wave = artifact.wave + module.feedback_delay
            key = (module_id, artifact.artifact_id, wave)
            if key in self._queued_keys or key in self._completed_keys:
                continue
            self._task_sequence += 1
            task = ScheduledTask(
                wave=wave,
                layer=module.layer,
                sequence=self._task_sequence,
                module_id=module_id,
                trigger_id=artifact.artifact_id,
            )
            heapq.heappush(self._queue, task)
            self._queued_keys.add(key)

    def run(self, *, max_tasks: int | None = None) -> int:
        if max_tasks is not None and max_tasks <= 0:
            raise ContractError("scheduler: max_tasks doit être positif")
        executed = 0
        while self._queue and (max_tasks is None or executed < max_tasks):
            first = self._queue[0]
            capacity = None if max_tasks is None else max_tasks - executed
            frontier: list[ScheduledTask] = []
            while self._queue:
                candidate = self._queue[0]
                if (candidate.wave, candidate.layer) != (first.wave, first.layer):
                    break
                if capacity is not None and len(frontier) >= capacity:
                    break
                task = heapq.heappop(self._queue)
                self._queued_keys.remove(task.key)
                frontier.append(task)
            self._frontier_sequence += 1
            trace_row: dict[str, Any] = {
                "frontier": self._frontier_sequence,
                "wave": first.wave,
                "layer": first.layer,
                "parallel_tasks": [task.as_dict() for task in frontier],
                "results": [],
            }
            prepared: dict[ScheduledTask, tuple[ArtifactProposal, ...]] = {}
            immediate: dict[ScheduledTask, dict[str, Any]] = {}
            eligible: list[ScheduledTask] = []
            for task in frontier:
                exhausted = self._reserve_budget(task)
                if exhausted is not None:
                    immediate[task] = exhausted
                else:
                    eligible.append(task)

            parallel = [
                task for task in eligible if self._modules[task.module_id].parallel_safe
            ]
            sequential = [task for task in eligible if task not in parallel]
            if len(parallel) > 1:
                worker_count = min(
                    len(parallel), self.control.limits.max_worker_count
                )
                with ThreadPoolExecutor(
                    max_workers=worker_count,
                    thread_name_prefix="seman2-frontier",
                ) as executor:
                    futures = {
                        task: executor.submit(self._invoke, task) for task in parallel
                    }
                    # Lecture dans l'ordre causal, indépendamment de l'ordre de fin.
                    for task in parallel:
                        prepared[task] = futures[task].result()
                trace_row["execution"] = "concurrent"
                trace_row["worker_count"] = worker_count
            else:
                for task in parallel:
                    prepared[task] = self._invoke(task)
                trace_row["execution"] = "sequential"
                trace_row["worker_count"] = 1 if parallel else 0
            for task in sequential:
                prepared[task] = self._invoke(task)

            for task in frontier:
                result = immediate.get(task)
                if result is None:
                    result = self._commit(task, prepared[task])
                trace_row["results"].append(result)
                executed += 1
            self._trace.append(trace_row)
        return executed

    def _reserve_budget(self, task: ScheduledTask) -> dict[str, Any] | None:
        module = self._modules[task.module_id]
        trigger = self.arena.get(task.trigger_id)
        budget_key = (module.module_id, task.wave)
        used = self._work_by_module_wave.get(budget_key, 0)
        if used >= self.control.parameters.per_module_work_budget:
            self._completed_keys.add(task.key)
            return {
                "module_id": module.module_id,
                "trigger_id": trigger.artifact_id,
                "status": "budget-exhausted",
                "produced": [],
            }
        self._work_by_module_wave[budget_key] = used + 1
        return None

    def _invoke(self, task: ScheduledTask) -> tuple[ArtifactProposal, ...]:
        module = self._modules[task.module_id]
        trigger = self.arena.get(task.trigger_id)
        context = ModuleContext(
            arena=self.arena,
            control=self.control,
            scheduled_wave=task.wave,
            module_id=module.module_id,
        )
        return tuple(module.handler(trigger, context))

    def _commit(
        self, task: ScheduledTask, proposals: tuple[ArtifactProposal, ...]
    ) -> dict[str, Any]:
        module = self._modules[task.module_id]
        trigger = self.arena.get(task.trigger_id)
        for proposal in proposals:
            self._validate_output(module, trigger, task, proposal)
        produced: list[str] = []
        for proposal in proposals:
            artifact = self.arena.publish(proposal)
            if artifact.derivation_depth > self.control.parameters.max_derivation_depth:
                raise ContractError(
                    f"{module.module_id}: profondeur de dérivation hors budget"
                )
            self._apply_activation_policy(artifact, proposal.activation)
            self._enqueue_consumers(artifact)
            produced.append(artifact.artifact_id)
        self._completed_keys.add(task.key)
        return {
            "module_id": module.module_id,
            "trigger_id": trigger.artifact_id,
            "status": "completed",
            "produced": produced,
        }

    def _validate_output(
        self,
        module: ModuleSpec,
        trigger: CognitiveArtifact,
        task: ScheduledTask,
        proposal: ArtifactProposal,
    ) -> None:
        if proposal.artifact_type not in module.produces:
            raise ContractError(
                f"{module.module_id}: sortie non déclarée {proposal.artifact_type}"
            )
        if proposal.producer_id != module.module_id:
            raise ContractError(f"{module.module_id}: producteur de sortie falsifié")
        if proposal.producer_build != module.producer_build:
            raise ContractError(f"{module.module_id}: build de sortie incompatible")
        if proposal.configuration_digest != module.configuration_digest:
            raise ContractError(f"{module.module_id}: configuration de sortie incompatible")
        if proposal.mode != trigger.mode or proposal.session_id != trigger.session_id:
            raise ContractError(f"{module.module_id}: session ou mode de sortie incompatible")
        if proposal.wave != task.wave:
            raise ContractError(
                f"{module.module_id}: sortie vague {proposal.wave}, attendu {task.wave}"
            )
        if trigger.artifact_id not in proposal.parent_ids:
            raise ContractError(
                f"{module.module_id}: le déclencheur doit être un parent causal"
            )
        parent_depth = max(
            self.arena.get(parent_id).derivation_depth
            for parent_id in proposal.parent_ids
        )
        if parent_depth + 1 > self.control.parameters.max_derivation_depth:
            raise ContractError(f"{module.module_id}: profondeur de sortie hors budget")

    def as_dict(self) -> dict[str, Any]:
        return {
            "module_manifest_digest": self.module_manifest_digest,
            "task_sequence": self._task_sequence,
            "frontier_sequence": self._frontier_sequence,
            "queue": [task.as_dict() for task in sorted(self._queue)],
            "completed_keys": [list(key) for key in sorted(self._completed_keys)],
            "work_by_module_wave": [
                {"module_id": key[0], "wave": key[1], "count": count}
                for key, count in sorted(self._work_by_module_wave.items())
            ],
            "trace": json.loads(canonical_json(self._trace)),
        }

    @classmethod
    def restore(
        cls,
        snapshot: Mapping[str, Any],
        *,
        registry: ArtifactTypeRegistry,
        arena: ArtifactArena,
        control: ControlState,
        modules: Iterable[ModuleSpec],
    ) -> "CognitiveScheduler":
        scheduler = cls(
            registry=registry,
            arena=arena,
            control=control,
            modules=modules,
        )
        if snapshot.get("module_manifest_digest") != scheduler.module_manifest_digest:
            raise ContractError("restore scheduler: manifeste de modules incompatible")
        scheduler._task_sequence = snapshot.get("task_sequence", 0)
        scheduler._frontier_sequence = snapshot.get("frontier_sequence", 0)
        scheduler._completed_keys = {
            (str(row[0]), str(row[1]), int(row[2]))
            for row in snapshot.get("completed_keys", [])
        }
        for row in snapshot.get("queue", []):
            task = ScheduledTask(
                wave=row["wave"],
                layer=row["layer"],
                sequence=row["sequence"],
                module_id=row["module_id"],
                trigger_id=row["trigger_id"],
            )
            if task.module_id not in scheduler._modules:
                raise ContractError(f"restore scheduler: module absent {task.module_id}")
            scheduler.arena.get(task.trigger_id)
            if task.key in scheduler._completed_keys or task.key in scheduler._queued_keys:
                raise ContractError("restore scheduler: tâche dupliquée")
            heapq.heappush(scheduler._queue, task)
            scheduler._queued_keys.add(task.key)
        scheduler._work_by_module_wave = {
            (row["module_id"], row["wave"]): row["count"]
            for row in snapshot.get("work_by_module_wave", [])
        }
        scheduler._trace = [dict(row) for row in snapshot.get("trace", [])]
        return scheduler
