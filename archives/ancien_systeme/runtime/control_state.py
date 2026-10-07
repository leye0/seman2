"""État de contrôle vivant et enveloppe de sûreté du runtime cognitif."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import ContractError


@dataclass(frozen=True)
class SafetyLimits:
    """Bornes non négociables, distinctes des paramètres cognitifs adaptables."""

    max_derivation_depth: int = 64
    max_hypothesis_beam_width: int = 256
    max_active_entities: int = 100_000
    max_retrieval_budget: int = 10_000
    max_module_work_per_wave: int = 50_000
    max_repair_budget: int = 1_000
    max_novelty_reserve: int = 10_000
    max_induction_trigger: int = 100_000
    max_process_ram_mib: int = 4_096
    max_worker_count: int = 8
    max_input_batch: int = 1_000
    max_worker_timeout_seconds: int = 600
    max_checkpoint_mib: int = 8_192

    def __post_init__(self) -> None:
        if any(value <= 0 for value in asdict(self).values()):
            raise ContractError("les limites de sûreté doivent être strictement positives")


@dataclass(frozen=True)
class CognitiveParameters:
    max_derivation_depth: int = 24
    activation_floor: float = 0.15
    hypothesis_beam_width: int = 32
    novelty_reserve: int = 128
    max_active_entities: int = 20_000
    retrieval_budget: int = 512
    per_module_work_budget: int = 5_000
    induction_trigger: int = 200
    consolidation_pressure: float = 0.50
    decay_policy: str = "activation-weighted"
    repair_budget: int = 64


@dataclass(frozen=True)
class ControlAdjustment:
    revision: int
    wave: int
    actor_id: str
    reason: str
    changes: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "changes", MappingProxyType(dict(self.changes)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "wave": self.wave,
            "actor_id": self.actor_id,
            "reason": self.reason,
            "changes": dict(self.changes),
        }


class ControlState:
    """Paramètres modifiables, validés à chaque transition et historisés."""

    def __init__(
        self,
        *,
        limits: SafetyLimits | None = None,
        parameters: CognitiveParameters | None = None,
    ) -> None:
        self.limits = limits or SafetyLimits()
        self._parameters = parameters or CognitiveParameters()
        self._history: list[ControlAdjustment] = []
        self._revision = 0
        self._validate(self._parameters)

    @property
    def parameters(self) -> CognitiveParameters:
        return self._parameters

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def history(self) -> tuple[ControlAdjustment, ...]:
        return tuple(self._history)

    def adjust(
        self,
        changes: Mapping[str, Any],
        *,
        actor_id: str,
        wave: int,
        reason: str,
    ) -> CognitiveParameters:
        if not actor_id or not reason:
            raise ContractError("ajustement de contrôle: acteur et raison requis")
        if wave < 0:
            raise ContractError("ajustement de contrôle: vague négative")
        if not changes:
            raise ContractError("ajustement de contrôle vide")
        known = set(asdict(self._parameters))
        unknown = sorted(set(changes) - known)
        if unknown:
            raise ContractError(f"paramètres de contrôle inconnus: {unknown}")
        candidate = replace(self._parameters, **dict(changes))
        self._validate(candidate)
        effective = {
            key: getattr(candidate, key)
            for key in changes
            if getattr(candidate, key) != getattr(self._parameters, key)
        }
        if not effective:
            return self._parameters
        self._revision += 1
        self._parameters = candidate
        self._history.append(
            ControlAdjustment(
                revision=self._revision,
                wave=wave,
                actor_id=actor_id,
                reason=reason,
                changes=effective,
            )
        )
        return self._parameters

    def _validate(self, value: CognitiveParameters) -> None:
        integer_bounds = {
            "max_derivation_depth": self.limits.max_derivation_depth,
            "hypothesis_beam_width": self.limits.max_hypothesis_beam_width,
            "novelty_reserve": self.limits.max_novelty_reserve,
            "max_active_entities": self.limits.max_active_entities,
            "retrieval_budget": self.limits.max_retrieval_budget,
            "per_module_work_budget": self.limits.max_module_work_per_wave,
            "induction_trigger": self.limits.max_induction_trigger,
            "repair_budget": self.limits.max_repair_budget,
        }
        for field_name, upper in integer_bounds.items():
            current = getattr(value, field_name)
            if isinstance(current, bool) or not isinstance(current, int):
                raise ContractError(f"{field_name} doit être un entier")
            if current <= 0 or current > upper:
                raise ContractError(f"{field_name} hors enveloppe de sûreté (1..{upper})")
        for field_name in ("activation_floor", "consolidation_pressure"):
            current = getattr(value, field_name)
            if isinstance(current, bool) or not isinstance(current, (int, float)):
                raise ContractError(f"{field_name} doit être numérique")
            if not 0.0 <= float(current) <= 1.0:
                raise ContractError(f"{field_name} hors [0,1]")
        if value.decay_policy not in {
            "none",
            "linear",
            "exponential",
            "activation-weighted",
        }:
            raise ContractError(f"politique de décroissance inconnue: {value.decay_policy}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "limits": asdict(self.limits),
            "parameters": asdict(self._parameters),
            "revision": self._revision,
            "history": [item.as_dict() for item in self._history],
        }

    @classmethod
    def restore(cls, snapshot: Mapping[str, Any]) -> "ControlState":
        state = cls(
            limits=SafetyLimits(**snapshot["limits"]),
            parameters=CognitiveParameters(**snapshot["parameters"]),
        )
        expected_revision = snapshot.get("revision", 0)
        rows = snapshot.get("history", [])
        if expected_revision != len(rows):
            raise ContractError("restore Control State: historique discontinu")
        for expected, row in enumerate(rows, start=1):
            if row["revision"] != expected:
                raise ContractError("restore Control State: révision discontinue")
            state._history.append(
                ControlAdjustment(
                    revision=row["revision"],
                    wave=row["wave"],
                    actor_id=row["actor_id"],
                    reason=row["reason"],
                    changes=dict(row["changes"]),
                )
            )
        state._revision = expected_revision
        return state
