"""Contrats transportés entre les proto-services.

Le contrat est volontairement petit. Il impose les identifiants, la causalité,
la provenance et les pertes à toutes les frontières, sans imposer une ontologie
cognitive aux valeurs natives des analyseurs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping


class ContractError(ValueError):
    """Une frontière de service a refusé une donnée incompatible."""


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ContractError(f"payload non sérialisable en JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    input_kind: str
    output_kind: str
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("name", "input_kind", "output_kind"):
            if not getattr(self, field_name).strip():
                raise ContractError(f"ServiceSpec.{field_name} est vide")
        if self.name in self.dependencies:
            raise ContractError(f"{self.name} dépend de lui-même")


@dataclass(frozen=True)
class Envelope:
    """Message immuable et chaîné remis d'un service au suivant."""

    kind: str
    message_id: str
    correlation_id: str
    producer: str
    parent_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    provenance: tuple[str, ...] = ()
    losses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("kind", "message_id", "correlation_id", "producer"):
            if not getattr(self, field_name).strip():
                raise ContractError(f"Envelope.{field_name} est vide")
        if len(set(self.parent_ids)) != len(self.parent_ids):
            raise ContractError("parent_ids contient un doublon")
        canonical_json(self.payload)
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @property
    def sha256(self) -> str:
        return digest(self.as_dict(include_digest=False))

    def as_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = {
            "kind": self.kind,
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "producer": self.producer,
            "parent_ids": list(self.parent_ids),
            "payload": dict(self.payload),
            "provenance": list(self.provenance),
            "losses": list(self.losses),
        }
        if include_digest:
            value["sha256"] = digest(value)
        return value


def require_fields(envelope: Envelope, *fields: str) -> None:
    missing = [field for field in fields if field not in envelope.payload]
    if missing:
        raise ContractError(f"{envelope.kind}: champs requis absents: {', '.join(missing)}")


def output_envelope(
    *,
    spec: ServiceSpec,
    source: Envelope,
    message_id: str,
    payload: Mapping[str, Any],
    provenance: tuple[str, ...] = (),
    losses: tuple[str, ...] = (),
) -> Envelope:
    if source.kind != spec.input_kind:
        raise ContractError(
            f"{spec.name} attend {spec.input_kind}, reçu {source.kind}"
        )
    return Envelope(
        kind=spec.output_kind,
        message_id=message_id,
        correlation_id=source.correlation_id,
        producer=spec.name,
        parent_ids=(source.message_id,),
        payload=payload,
        provenance=tuple(dict.fromkeys((*source.provenance, source.sha256, *provenance))),
        losses=losses,
    )
