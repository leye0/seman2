"""Artefacts cognitifs typés et arène vivante principalement en RAM.

Ce noyau ne connaît aucun concept du domaine. Il garantit l'identité, la
causalité, les couches, les vagues, l'immutabilité et l'idempotence de la
matière produite par les systèmes cognitifs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .contracts import ContractError, canonical_json


JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | tuple["JSONValue", ...] | Mapping[str, "JSONValue"]


def freeze_json(value: Any) -> JSONValue:
    """Copie récursivement une valeur JSON dans des conteneurs immuables."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("valeur cognitive flottante non finie")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        frozen = {str(key): freeze_json(item) for key, item in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    raise ContractError(f"valeur cognitive non JSON: {type(value).__name__}")


def thaw_json(value: JSONValue) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


class ArtifactStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class Residency(str, Enum):
    ACTIVE = "active"
    LATENT = "latent"
    COLD = "cold"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ArtifactTypeSpec:
    artifact_type: str
    schema_id: str
    layer: int
    root_allowed: bool = False
    allowed_modes: frozenset[str] = frozenset({"ingestion", "chatbot"})
    allowed_producers: frozenset[str] = frozenset()
    parent_types: frozenset[str] = frozenset()
    feedback_parent_types: frozenset[str] = frozenset()
    required_native_fields: frozenset[str] = frozenset()
    required_projection_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for name in (
            "allowed_modes",
            "allowed_producers",
            "parent_types",
            "feedback_parent_types",
            "required_native_fields",
            "required_projection_fields",
        ):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        if not self.artifact_type or not self.schema_id:
            raise ContractError("type d'artefact: nom et schema_id requis")
        if self.layer < 0:
            raise ContractError("type d'artefact: couche négative")
        if not self.allowed_modes <= {"ingestion", "chatbot"}:
            raise ContractError(f"type d'artefact: modes invalides {self.allowed_modes}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "schema_id": self.schema_id,
            "layer": self.layer,
            "root_allowed": self.root_allowed,
            "allowed_modes": sorted(self.allowed_modes),
            "allowed_producers": sorted(self.allowed_producers),
            "parent_types": sorted(self.parent_types),
            "feedback_parent_types": sorted(self.feedback_parent_types),
            "required_native_fields": sorted(self.required_native_fields),
            "required_projection_fields": sorted(self.required_projection_fields),
        }


class ArtifactTypeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, ArtifactTypeSpec] = {}
        self._frozen = False

    def register(self, spec: ArtifactTypeSpec) -> None:
        if self._frozen:
            raise ContractError("registre de types figé")
        if spec.artifact_type in self._types:
            raise ContractError(f"type d'artefact dupliqué: {spec.artifact_type}")
        self._types[spec.artifact_type] = spec

    def freeze(self) -> None:
        unknown: dict[str, list[str]] = {}
        known = set(self._types)
        for spec in self._types.values():
            absent = sorted((spec.parent_types | spec.feedback_parent_types) - known)
            if absent:
                unknown[spec.artifact_type] = absent
        if unknown:
            raise ContractError(f"registre: types parents inconnus: {unknown}")
        self._frozen = True

    def get(self, artifact_type: str) -> ArtifactTypeSpec:
        try:
            return self._types[artifact_type]
        except KeyError as exc:
            raise ContractError(f"type d'artefact inconnu: {artifact_type}") from exc

    @property
    def frozen(self) -> bool:
        return self._frozen

    @property
    def digest(self) -> str:
        value = [self._types[key].as_dict() for key in sorted(self._types)]
        return hashlib.sha256(canonical_json(value).encode()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "frozen": self._frozen,
            "digest": self.digest,
            "types": [self._types[key].as_dict() for key in sorted(self._types)],
        }


@dataclass(frozen=True)
class ArtifactProposal:
    artifact_type: str
    producer_id: str
    producer_build: str
    configuration_digest: str
    mode: str
    session_id: str
    wave: int
    parent_ids: tuple[str, ...]
    observation_refs: tuple[str, ...] = ()
    episode_refs: tuple[str, ...] = ()
    context_refs: tuple[str, ...] = ()
    source_anchors: tuple[Mapping[str, Any], ...] = ()
    resource_cost: Mapping[str, Any] = field(default_factory=dict)
    payload_native: Mapping[str, Any] = field(default_factory=dict)
    payload_projection: Mapping[str, Any] = field(default_factory=dict)
    status: ArtifactStatus = ArtifactStatus.SUCCESS
    justification_ids: tuple[str, ...] = ()
    contradiction_ids: tuple[str, ...] = ()
    losses: tuple[str, ...] = ()
    idempotency_key: str = ""
    activation: float = 1.0

    def __post_init__(self) -> None:
        for name in (
            "parent_ids",
            "observation_refs",
            "episode_refs",
            "context_refs",
            "justification_ids",
            "contradiction_ids",
            "losses",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(
            self,
            "source_anchors",
            tuple(freeze_json(dict(item)) for item in self.source_anchors),
        )
        object.__setattr__(self, "payload_native", freeze_json(dict(self.payload_native)))
        object.__setattr__(self, "resource_cost", freeze_json(dict(self.resource_cost)))
        object.__setattr__(
            self, "payload_projection", freeze_json(dict(self.payload_projection))
        )
        if not isinstance(self.status, ArtifactStatus):
            raise ContractError("proposition d'artefact: status invalide")
        for name in (
            "artifact_type",
            "producer_id",
            "producer_build",
            "configuration_digest",
            "session_id",
            "idempotency_key",
        ):
            if not str(getattr(self, name)).strip():
                raise ContractError(f"proposition d'artefact: {name} requis")
        if self.mode not in {"ingestion", "chatbot"}:
            raise ContractError(f"proposition d'artefact: mode invalide {self.mode!r}")
        if self.wave < 0:
            raise ContractError("proposition d'artefact: vague négative")
        if not 0.0 <= self.activation <= 1.0:
            raise ContractError("proposition d'artefact: activation hors [0,1]")
        for name in (
            "parent_ids", "observation_refs", "episode_refs",
            "context_refs",
            "justification_ids", "contradiction_ids",
        ):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ContractError(f"proposition d'artefact: doublon dans {name}")
        canonical_json(self.as_content_dict())

    def as_content_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "producer_id": self.producer_id,
            "producer_build": self.producer_build,
            "configuration_digest": self.configuration_digest,
            "mode": self.mode,
            "session_id": self.session_id,
            "wave": self.wave,
            "parent_ids": list(self.parent_ids),
            "observation_refs": list(self.observation_refs),
            "episode_refs": list(self.episode_refs),
            "context_refs": list(self.context_refs),
            "source_anchors": [thaw_json(item) for item in self.source_anchors],
            "resource_cost": thaw_json(self.resource_cost),
            "payload_native": thaw_json(self.payload_native),
            "payload_projection": thaw_json(self.payload_projection),
            "status": self.status.value,
            "justification_ids": list(self.justification_ids),
            "contradiction_ids": list(self.contradiction_ids),
            "losses": list(self.losses),
            "idempotency_key": self.idempotency_key,
            "activation": self.activation,
        }


@dataclass(frozen=True)
class CognitiveArtifact:
    artifact_id: str
    artifact_type: str
    schema_id: str
    producer_id: str
    producer_build: str
    configuration_digest: str
    mode: str
    session_id: str
    observation_refs: tuple[str, ...]
    episode_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    wave: int
    derivation_depth: int
    source_anchors: tuple[JSONValue, ...]
    resource_cost: JSONValue
    parent_ids: tuple[str, ...]
    payload_native: JSONValue
    payload_projection: JSONValue
    status: ArtifactStatus
    justification_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    losses: tuple[str, ...]
    created_sequence: int
    content_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "schema_id": self.schema_id,
            "producer_id": self.producer_id,
            "producer_build": self.producer_build,
            "producer_revision": self.producer_build,
            "configuration_digest": self.configuration_digest,
            "mode": self.mode,
            "session_id": self.session_id,
            "observation_refs": list(self.observation_refs),
            "episode_refs": list(self.episode_refs),
            "context_refs": list(self.context_refs),
            "wave": self.wave,
            "derivation_depth": self.derivation_depth,
            "source_anchors": [thaw_json(item) for item in self.source_anchors],
            "resource_cost": thaw_json(self.resource_cost),
            "parent_ids": list(self.parent_ids),
            "payload_native": thaw_json(self.payload_native),
            "payload_projection": thaw_json(self.payload_projection),
            "status": self.status.value,
            "justification_ids": list(self.justification_ids),
            "contradiction_ids": list(self.contradiction_ids),
            "losses": list(self.losses),
            "created_sequence": self.created_sequence,
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class ActivationRecord:
    residency: Residency
    activation: float
    reason: str | None = None


class ArtifactArena:
    """Arène append-only en RAM avec indexes et état d'activation séparé."""

    def __init__(self, registry: ArtifactTypeRegistry) -> None:
        if not registry.frozen:
            raise ContractError("ArtifactArena exige un registre figé")
        self.registry = registry
        self._artifacts: dict[str, CognitiveArtifact] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, str]] = {}
        self._artifact_idempotency: dict[str, str] = {}
        self._by_type: dict[str, list[str]] = {}
        self._by_session: dict[str, list[str]] = {}
        self._children: dict[str, list[str]] = {}
        self._activation: dict[str, ActivationRecord] = {}
        self._sequence = 0

    def __len__(self) -> int:
        return len(self._artifacts)

    def publish(self, proposal: ArtifactProposal) -> CognitiveArtifact:
        spec = self.registry.get(proposal.artifact_type)
        if proposal.mode not in spec.allowed_modes:
            raise ContractError(f"{proposal.artifact_type}: mode {proposal.mode} interdit")
        if spec.allowed_producers and proposal.producer_id not in spec.allowed_producers:
            raise ContractError(
                f"{proposal.artifact_type}: producteur interdit {proposal.producer_id}"
            )
        if (
            len(proposal.configuration_digest) != 64
            or not all(char in "0123456789abcdef" for char in proposal.configuration_digest)
        ):
            raise ContractError("configuration_digest doit être un SHA-256 hexadécimal")
        if not proposal.parent_ids and not spec.root_allowed:
            raise ContractError(f"{proposal.artifact_type}: parent requis")

        parents: list[CognitiveArtifact] = []
        for parent_id in proposal.parent_ids:
            parent = self.get(parent_id)
            if parent.session_id != proposal.session_id:
                raise ContractError("artefact: parent d'une autre session")
            if parent.mode != proposal.mode:
                raise ContractError("artefact: parent d'un autre mode")
            parent_spec = self.registry.get(parent.artifact_type)
            is_feedback = parent.artifact_type in spec.feedback_parent_types
            if spec.parent_types and parent.artifact_type not in spec.parent_types and not is_feedback:
                raise ContractError(
                    f"{proposal.artifact_type}: parent {parent.artifact_type} interdit"
                )
            if parent_spec.layer > spec.layer and not is_feedback:
                raise ContractError(
                    f"raccourci descendant interdit: L{parent_spec.layer} -> L{spec.layer}"
                )
            minimum_wave = parent.wave + (1 if is_feedback else 0)
            if proposal.wave < minimum_wave:
                raise ContractError(
                    f"{proposal.artifact_type}: vague {proposal.wave}, minimum {minimum_wave}"
                )
            parents.append(parent)

        native_keys = set(proposal.payload_native)
        projection_keys = set(proposal.payload_projection)
        if missing := sorted(spec.required_native_fields - native_keys):
            raise ContractError(f"{proposal.artifact_type}: champs natifs absents {missing}")
        if missing := sorted(spec.required_projection_fields - projection_keys):
            raise ContractError(f"{proposal.artifact_type}: projections absentes {missing}")

        depth = 0 if not parents else max(parent.derivation_depth for parent in parents) + 1
        content = proposal.as_content_dict() | {
            "schema_id": spec.schema_id,
            "derivation_depth": depth,
        }
        content_hash = hashlib.sha256(canonical_json(content).encode()).hexdigest()
        key = (proposal.producer_id, proposal.idempotency_key)
        if existing := self._idempotency.get(key):
            artifact_id, existing_hash = existing
            if existing_hash != content_hash:
                raise ContractError("conflit d'idempotence dans l'Artifact Arena")
            return self.get(artifact_id)

        identity = hashlib.sha256(canonical_json({
            "producer_id": proposal.producer_id,
            "idempotency_key": proposal.idempotency_key,
            "session_id": proposal.session_id,
            "artifact_type": proposal.artifact_type,
        }).encode()).hexdigest()
        artifact_id = f"ca:{proposal.artifact_type}:{identity[:24]}"
        if artifact_id in self._artifacts:
            raise ContractError(f"collision d'identifiant cognitive: {artifact_id}")
        self._sequence += 1
        artifact = CognitiveArtifact(
            artifact_id=artifact_id,
            artifact_type=proposal.artifact_type,
            schema_id=spec.schema_id,
            producer_id=proposal.producer_id,
            producer_build=proposal.producer_build,
            configuration_digest=proposal.configuration_digest,
            mode=proposal.mode,
            session_id=proposal.session_id,
            observation_refs=tuple(proposal.observation_refs),
            episode_refs=tuple(proposal.episode_refs),
            context_refs=tuple(proposal.context_refs),
            wave=proposal.wave,
            derivation_depth=depth,
            source_anchors=tuple(freeze_json(dict(item)) for item in proposal.source_anchors),
            resource_cost=freeze_json(dict(proposal.resource_cost)),
            parent_ids=tuple(proposal.parent_ids),
            payload_native=freeze_json(dict(proposal.payload_native)),
            payload_projection=freeze_json(dict(proposal.payload_projection)),
            status=proposal.status,
            justification_ids=tuple(proposal.justification_ids),
            contradiction_ids=tuple(proposal.contradiction_ids),
            losses=tuple(proposal.losses),
            created_sequence=self._sequence,
            content_sha256=content_hash,
        )
        self._artifacts[artifact_id] = artifact
        self._idempotency[key] = (artifact_id, content_hash)
        self._artifact_idempotency[artifact_id] = proposal.idempotency_key
        self._by_type.setdefault(artifact.artifact_type, []).append(artifact_id)
        self._by_session.setdefault(artifact.session_id, []).append(artifact_id)
        for parent_id in artifact.parent_ids:
            self._children.setdefault(parent_id, []).append(artifact_id)
        self._activation[artifact_id] = ActivationRecord(
            Residency.ACTIVE, proposal.activation
        )
        return artifact

    def get(self, artifact_id: str) -> CognitiveArtifact:
        try:
            return self._artifacts[artifact_id]
        except KeyError as exc:
            raise ContractError(f"artefact cognitif absent: {artifact_id}") from exc

    def activation(self, artifact_id: str) -> ActivationRecord:
        self.get(artifact_id)
        return self._activation[artifact_id]

    def set_residency(
        self,
        artifact_id: str,
        residency: Residency,
        *,
        activation: float | None = None,
        reason: str | None = None,
    ) -> None:
        current = self.activation(artifact_id)
        value = current.activation if activation is None else activation
        if not 0.0 <= value <= 1.0:
            raise ContractError("activation hors [0,1]")
        if residency is Residency.REJECTED and not reason:
            raise ContractError("une hypothèse rejetée exige une raison")
        self._activation[artifact_id] = ActivationRecord(residency, value, reason)

    def query(
        self,
        *,
        artifact_type: str | None = None,
        session_id: str | None = None,
        wave_at_most: int | None = None,
        residency: Residency | None = None,
    ) -> tuple[CognitiveArtifact, ...]:
        if artifact_type is not None:
            identifiers: Iterable[str] = self._by_type.get(artifact_type, ())
        elif session_id is not None:
            identifiers = self._by_session.get(session_id, ())
        else:
            identifiers = self._artifacts
        rows = []
        for identifier in identifiers:
            artifact = self._artifacts[identifier]
            if session_id is not None and artifact.session_id != session_id:
                continue
            if wave_at_most is not None and artifact.wave > wave_at_most:
                continue
            if residency is not None and self._activation[identifier].residency is not residency:
                continue
            rows.append(artifact)
        return tuple(sorted(rows, key=lambda row: row.created_sequence))

    def children(self, artifact_id: str) -> tuple[CognitiveArtifact, ...]:
        self.get(artifact_id)
        return tuple(self.get(identifier) for identifier in self._children.get(artifact_id, ()))

    def ancestry(self, artifact_id: str) -> tuple[CognitiveArtifact, ...]:
        pending = [artifact_id]
        seen: set[str] = set()
        rows = []
        while pending:
            identifier = pending.pop(0)
            if identifier in seen:
                continue
            seen.add(identifier)
            artifact = self.get(identifier)
            rows.append(artifact)
            pending.extend(artifact.parent_ids)
        return tuple(rows)

    def as_dict(self) -> dict[str, Any]:
        return {
            "registry_digest": self.registry.digest,
            "sequence": self._sequence,
            "artifacts": [
                artifact.as_dict()
                | {"_idempotency_key": self._artifact_idempotency[artifact.artifact_id]}
                for artifact in sorted(
                    self._artifacts.values(), key=lambda row: row.created_sequence
                )
            ],
            "activation": {
                identifier: {
                    "residency": record.residency.value,
                    "activation": record.activation,
                    "reason": record.reason,
                }
                for identifier, record in sorted(self._activation.items())
            },
        }

    @classmethod
    def restore(
        cls, registry: ArtifactTypeRegistry, snapshot: Mapping[str, Any]
    ) -> "ArtifactArena":
        if snapshot.get("registry_digest") != registry.digest:
            raise ContractError("restore Artifact Arena: registre incompatible")
        arena = cls(registry)
        for row in snapshot.get("artifacts", []):
            proposal = ArtifactProposal(
                artifact_type=row["artifact_type"],
                producer_id=row["producer_id"],
                producer_build=row["producer_build"],
                configuration_digest=row["configuration_digest"],
                mode=row["mode"],
                session_id=row["session_id"],
                wave=row["wave"],
                parent_ids=tuple(row["parent_ids"]),
                observation_refs=tuple(row["observation_refs"]),
                episode_refs=tuple(row["episode_refs"]),
                context_refs=tuple(row.get("context_refs", ())),
                source_anchors=tuple(row["source_anchors"]),
                resource_cost=row.get("resource_cost", {}),
                payload_native=row["payload_native"],
                payload_projection=row["payload_projection"],
                status=ArtifactStatus(row["status"]),
                justification_ids=tuple(row["justification_ids"]),
                contradiction_ids=tuple(row["contradiction_ids"]),
                losses=tuple(row["losses"]),
                idempotency_key=_restore_idempotency_key(row),
                activation=snapshot["activation"][row["artifact_id"]]["activation"],
            )
            artifact = arena.publish(proposal)
            if artifact.artifact_id != row["artifact_id"] or artifact.content_sha256 != row["content_sha256"]:
                raise ContractError("restore Artifact Arena: identité ou contenu divergent")
            activation = snapshot["activation"][artifact.artifact_id]
            arena.set_residency(
                artifact.artifact_id,
                Residency(activation["residency"]),
                activation=activation["activation"],
                reason=activation["reason"],
            )
        if arena._sequence != snapshot.get("sequence"):
            raise ContractError("restore Artifact Arena: séquence divergente")
        return arena


def _restore_idempotency_key(row: Mapping[str, Any]) -> str:
    """Reconstitue la clé stable encodée dans l'identité d'un snapshot.

    Le snapshot public ne doit pas deviner cette clé. Elle est donc enregistrée
    dans la représentation checkpoint par le runtime avant restauration. Cette
    fonction centralise la vérification du champ réservé.
    """
    try:
        return row["_idempotency_key"]
    except KeyError as exc:
        raise ContractError("restore Artifact Arena: clé d'idempotence absente") from exc
