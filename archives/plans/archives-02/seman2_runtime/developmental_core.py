"""Noyau représentationnel développemental indépendant du NLP.

Ce module implémente les premières gates de l'architecture active : contextes,
identités, relations n-aires, événements, états, transitions génériques et
formes distribuées traçables. Il ne contient aucune connaissance lexicale ou
fonction sémantique propre à un mot.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
import hashlib
import math
from typing import Any, Iterable, Mapping

import numpy as np

from .contracts import ContractError, canonical_json
from .cognitive_memory import CognitiveMemory, MemoryPolicy


def _required(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field_name} requis")
    return value


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(values)
    if len(result) != len(set(result)):
        raise ContractError("références dupliquées")
    return result


def _stable_id(prefix: str, content: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(content).encode()).hexdigest()
    return f"{prefix}:{digest[:24]}"


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


class ContextKind(str, Enum):
    CURRENT = "current"
    NARRATED = "narrated"
    ATTRIBUTED = "attributed"
    HYPOTHETICAL = "hypothetical"
    FICTION = "fiction"
    COUNTERFACTUAL = "counterfactual"
    DIALOGUE = "dialogue"
    PLAN = "plan"


class EpistemicState(str, Enum):
    OBSERVED = "observed"
    ATTRIBUTED = "attributed"
    HYPOTHESIS = "hypothesis"
    CONSOLIDATED = "consolidated"
    CONTESTED = "contested"
    SUSPENDED = "suspended"
    EXPECTED = "expected"


class Polarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class RelationEffectKind(str, Enum):
    OPEN = "open"
    CLOSE = "close"


@dataclass(frozen=True)
class ContextFrame:
    context_id: str
    kind: ContextKind
    parent_context_ref: str | None = None
    attribution_ref: str | None = None
    support_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.context_id, "context_id")
        object.__setattr__(self, "support_refs", _unique(self.support_refs))
        if self.kind is ContextKind.ATTRIBUTED and not self.attribution_ref:
            raise ContractError("contexte attribué: attribution_ref requis")


@dataclass(frozen=True)
class IdentityAnchor:
    identity_id: str
    origin_context_ref: str
    support_refs: tuple[str, ...]
    surface_aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.identity_id, "identity_id")
        _required(self.origin_context_ref, "origin_context_ref")
        object.__setattr__(self, "support_refs", _unique(self.support_refs))
        object.__setattr__(self, "surface_aliases", tuple(self.surface_aliases))
        if not self.support_refs:
            raise ContractError("identité: support requis")


@dataclass(frozen=True)
class SituatedFacet:
    facet_id: str
    identity_ref: str
    context_ref: str
    active_relation_refs: tuple[str, ...] = ()
    active_state_refs: tuple[str, ...] = ()
    active_role_refs: tuple[str, ...] = ()
    distributed_form_ref: str | None = None
    support_refs: tuple[str, ...] = ()
    temporal_start: int | None = None
    temporal_end: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("facet_id", "identity_ref", "context_ref"):
            _required(getattr(self, field_name), field_name)
        for field_name in (
            "active_relation_refs",
            "active_state_refs",
            "active_role_refs",
            "support_refs",
        ):
            object.__setattr__(self, field_name, _unique(getattr(self, field_name)))
        if not self.support_refs:
            raise ContractError("facette située: support requis")
        if self.temporal_start is not None and self.temporal_start < 0:
            raise ContractError("facette située: début temporel négatif")
        if self.temporal_end is not None and (
            self.temporal_start is None or self.temporal_end < self.temporal_start
        ):
            raise ContractError("facette située: étendue temporelle invalide")


@dataclass(frozen=True)
class RoleBinding:
    role_ref: str
    value_ref: str

    def __post_init__(self) -> None:
        _required(self.role_ref, "role_ref")
        _required(self.value_ref, "value_ref")


def _bindings(values: Iterable[RoleBinding]) -> tuple[RoleBinding, ...]:
    result = tuple(values)
    if not result:
        raise ContractError("au moins un binding est requis")
    pairs = [(item.role_ref, item.value_ref) for item in result]
    if len(pairs) != len(set(pairs)):
        raise ContractError("binding dupliqué")
    return result


@dataclass(frozen=True)
class RelationOccurrence:
    relation_occurrence_id: str
    relation_form_ref: str
    bindings: tuple[RoleBinding, ...]
    context_ref: str
    temporal_index: int
    polarity: Polarity
    modality: str
    attribution_ref: str | None
    support_refs: tuple[str, ...]
    contradiction_refs: tuple[str, ...]
    epistemic_state: EpistemicState

    def __post_init__(self) -> None:
        _required(self.relation_occurrence_id, "relation_occurrence_id")
        _required(self.relation_form_ref, "relation_form_ref")
        _required(self.context_ref, "context_ref")
        _required(self.modality, "modality")
        if self.temporal_index < 0:
            raise ContractError("relation: index temporel négatif")
        object.__setattr__(self, "bindings", _bindings(self.bindings))
        object.__setattr__(self, "support_refs", _unique(self.support_refs))
        object.__setattr__(
            self, "contradiction_refs", _unique(self.contradiction_refs)
        )
        if not self.support_refs:
            raise ContractError("relation: support requis")


@dataclass(frozen=True)
class StateFacet:
    state_id: str
    bearer_ref: str
    dimension_ref: str
    value_ref: str
    context_ref: str
    opened_at: int
    support_refs: tuple[str, ...]
    epistemic_state: EpistemicState
    supersedes_state_ref: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "state_id",
            "bearer_ref",
            "dimension_ref",
            "value_ref",
            "context_ref",
        ):
            _required(getattr(self, field_name), field_name)
        if self.opened_at < 0:
            raise ContractError("état: index temporel négatif")
        object.__setattr__(self, "support_refs", _unique(self.support_refs))
        if not self.support_refs:
            raise ContractError("état: support requis")


@dataclass(frozen=True)
class EventOccurrence:
    event_id: str
    event_form_ref: str
    bindings: tuple[RoleBinding, ...]
    context_ref: str
    temporal_index: int
    support_refs: tuple[str, ...]
    epistemic_state: EpistemicState = EpistemicState.OBSERVED

    def __post_init__(self) -> None:
        for field_name in ("event_id", "event_form_ref", "context_ref"):
            _required(getattr(self, field_name), field_name)
        if self.temporal_index < 0:
            raise ContractError("événement: index temporel négatif")
        object.__setattr__(self, "bindings", _bindings(self.bindings))
        object.__setattr__(self, "support_refs", _unique(self.support_refs))
        if not self.support_refs:
            raise ContractError("événement: support requis")


@dataclass(frozen=True)
class StateCondition:
    bearer_ref: str
    dimension_ref: str
    expected_value_ref: str
    context_ref: str


@dataclass(frozen=True)
class StateEffect:
    bearer_ref: str
    dimension_ref: str
    value_ref: str
    context_ref: str


@dataclass(frozen=True)
class RelationEffect:
    kind: RelationEffectKind
    relation_form_ref: str
    bindings: tuple[RoleBinding, ...]
    context_ref: str
    epistemic_state: EpistemicState = EpistemicState.OBSERVED

    def __post_init__(self) -> None:
        _required(self.relation_form_ref, "relation_form_ref")
        _required(self.context_ref, "context_ref")
        object.__setattr__(self, "bindings", _bindings(self.bindings))


@dataclass(frozen=True)
class TransitionCandidate:
    transition_id: str
    trigger_event_ref: str
    preconditions: tuple[StateCondition, ...] = ()
    state_effects: tuple[StateEffect, ...] = ()
    relation_effects: tuple[RelationEffect, ...] = ()
    invariant_state_refs: tuple[str, ...] = ()
    support_occurrence_refs: tuple[str, ...] = ()
    exception_occurrence_refs: tuple[str, ...] = ()
    confidence: float = 1.0

    def __post_init__(self) -> None:
        _required(self.transition_id, "transition_id")
        _required(self.trigger_event_ref, "trigger_event_ref")
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(self, "state_effects", tuple(self.state_effects))
        object.__setattr__(self, "relation_effects", tuple(self.relation_effects))
        object.__setattr__(
            self, "invariant_state_refs", _unique(self.invariant_state_refs)
        )
        object.__setattr__(
            self, "support_occurrence_refs", _unique(self.support_occurrence_refs)
        )
        object.__setattr__(
            self,
            "exception_occurrence_refs",
            _unique(self.exception_occurrence_refs),
        )
        if not self.state_effects and not self.relation_effects:
            raise ContractError("transition sans effet")
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractError("transition: confiance hors [0,1]")


@dataclass(frozen=True)
class TransitionResult:
    transition_ref: str
    applied_at: int
    closed_state_refs: tuple[str, ...]
    opened_state_refs: tuple[str, ...]
    closed_relation_refs: tuple[str, ...]
    opened_relation_refs: tuple[str, ...]
    support_refs: tuple[str, ...]


@dataclass(frozen=True)
class QueryResult:
    status: str
    value_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    explanation: str


class RelationalUniverse:
    """Univers append-only avec fermetures temporelles séparées des faits."""

    def __init__(self) -> None:
        self.contexts: dict[str, ContextFrame] = {}
        self.identities: dict[str, IdentityAnchor] = {}
        self.facets: dict[str, SituatedFacet] = {}
        self.relations: dict[str, RelationOccurrence] = {}
        self.states: dict[str, StateFacet] = {}
        self.events: dict[str, EventOccurrence] = {}
        self.transitions: dict[str, TransitionCandidate] = {}
        self.transition_results: list[TransitionResult] = []
        self._state_closed_at: dict[str, int] = {}
        self._relation_closed_at: dict[str, int] = {}

    def add_context(self, context: ContextFrame) -> None:
        if context.context_id in self.contexts:
            if self.contexts[context.context_id] != context:
                raise ContractError("contexte: identité en conflit")
            return
        if context.parent_context_ref and context.parent_context_ref not in self.contexts:
            raise ContractError("contexte: parent absent")
        self.contexts[context.context_id] = context

    def add_identity(self, identity: IdentityAnchor) -> None:
        self._require_context(identity.origin_context_ref)
        self._insert_unique(self.identities, identity.identity_id, identity, "identité")

    def add_facet(self, facet: SituatedFacet) -> None:
        self._require_context(facet.context_ref)
        if facet.identity_ref not in self.identities:
            raise ContractError("facette située: identité absente")
        for relation_ref in facet.active_relation_refs:
            if relation_ref not in self.relations:
                raise ContractError("facette située: relation absente")
        for state_ref in facet.active_state_refs:
            if state_ref not in self.states:
                raise ContractError("facette située: état absent")
        self._insert_unique(self.facets, facet.facet_id, facet, "facette située")

    def add_relation(self, relation: RelationOccurrence) -> None:
        self._require_context(relation.context_ref)
        if relation.attribution_ref and relation.attribution_ref not in self.identities:
            raise ContractError("relation: attribution inconnue")
        self._insert_unique(
            self.relations,
            relation.relation_occurrence_id,
            relation,
            "relation",
        )

    def add_state(self, state: StateFacet) -> None:
        self._require_context(state.context_ref)
        if state.supersedes_state_ref and state.supersedes_state_ref not in self.states:
            raise ContractError("état: état remplacé absent")
        self._insert_unique(self.states, state.state_id, state, "état")

    def add_event(self, event: EventOccurrence) -> None:
        self._require_context(event.context_ref)
        self._insert_unique(self.events, event.event_id, event, "événement")

    def add_transition(self, transition: TransitionCandidate) -> None:
        if transition.trigger_event_ref not in self.events:
            raise ContractError("transition: événement déclencheur absent")
        for state_ref in transition.invariant_state_refs:
            if state_ref not in self.states:
                raise ContractError("transition: invariant absent")
        self._insert_unique(
            self.transitions, transition.transition_id, transition, "transition"
        )

    def current_state(
        self,
        *,
        bearer_ref: str,
        dimension_ref: str,
        context_ref: str,
        at: int | None = None,
    ) -> QueryResult:
        self._require_context(context_ref)
        candidates = [
            state
            for state in self.states.values()
            if state.bearer_ref == bearer_ref
            and state.dimension_ref == dimension_ref
            and state.context_ref == context_ref
            and (at is None or state.opened_at <= at)
            and (
                state.state_id not in self._state_closed_at
                or (at is not None and self._state_closed_at[state.state_id] > at)
            )
        ]
        if not candidates:
            return QueryResult(
                status="unknown",
                value_refs=(),
                evidence_refs=(),
                explanation="aucun état soutenu dans ce contexte et à cet instant",
            )
        latest = max(state.opened_at for state in candidates)
        candidates = [state for state in candidates if state.opened_at == latest]
        values = tuple(sorted({state.value_ref for state in candidates}))
        return QueryResult(
            status="supported" if len(values) == 1 else "ambiguous",
            value_refs=values,
            evidence_refs=tuple(sorted(state.state_id for state in candidates)),
            explanation="état courant reconstruit depuis les facettes encore ouvertes",
        )

    def query_relations(
        self,
        *,
        relation_form_ref: str | None = None,
        required_bindings: Iterable[RoleBinding] = (),
        context_ref: str,
        at: int | None = None,
    ) -> tuple[RelationOccurrence, ...]:
        self._require_context(context_ref)
        required = set(required_bindings)
        rows = []
        for relation in self.relations.values():
            if relation.context_ref != context_ref:
                continue
            if relation_form_ref and relation.relation_form_ref != relation_form_ref:
                continue
            if at is not None and relation.temporal_index > at:
                continue
            if relation.relation_occurrence_id in self._relation_closed_at and (
                at is None
                or self._relation_closed_at[relation.relation_occurrence_id] <= at
            ):
                continue
            if not required <= set(relation.bindings):
                continue
            rows.append(relation)
        return tuple(sorted(rows, key=lambda row: (row.temporal_index, row.relation_occurrence_id)))

    def replay_transition(self, transition_ref: str) -> TransitionResult:
        """Calcule le delta attendu sans modifier l'univers."""
        transition = self._transition(transition_ref)
        event = self.events[transition.trigger_event_ref]
        self._check_preconditions(transition, event.temporal_index)
        closed_states: list[str] = []
        opened_states: list[str] = []
        for effect in transition.state_effects:
            current = self.current_state(
                bearer_ref=effect.bearer_ref,
                dimension_ref=effect.dimension_ref,
                context_ref=effect.context_ref,
                at=event.temporal_index,
            )
            closed_states.extend(current.evidence_refs)
            opened_states.append(self._state_effect_id(transition, effect))
        closed_relations: list[str] = []
        opened_relations: list[str] = []
        for effect in transition.relation_effects:
            if effect.kind is RelationEffectKind.CLOSE:
                closed_relations.extend(
                    row.relation_occurrence_id
                    for row in self.query_relations(
                        relation_form_ref=effect.relation_form_ref,
                        required_bindings=effect.bindings,
                        context_ref=effect.context_ref,
                        at=event.temporal_index,
                    )
                )
            else:
                opened_relations.append(self._relation_effect_id(transition, effect))
        return TransitionResult(
            transition_ref=transition.transition_id,
            applied_at=event.temporal_index,
            closed_state_refs=tuple(sorted(set(closed_states))),
            opened_state_refs=tuple(opened_states),
            closed_relation_refs=tuple(sorted(set(closed_relations))),
            opened_relation_refs=tuple(opened_relations),
            support_refs=(event.event_id,) + transition.support_occurrence_refs,
        )

    def apply_transition(self, transition_ref: str) -> TransitionResult:
        transition = self._transition(transition_ref)
        result = self.replay_transition(transition_ref)
        if any(row.transition_ref == transition_ref for row in self.transition_results):
            return next(
                row for row in self.transition_results if row.transition_ref == transition_ref
            )
        event = self.events[transition.trigger_event_ref]
        for state_ref in result.closed_state_refs:
            self._state_closed_at[state_ref] = event.temporal_index
        for effect, state_id in zip(transition.state_effects, result.opened_state_refs):
            superseded = next(
                (
                    state_ref
                    for state_ref in result.closed_state_refs
                    if self.states[state_ref].bearer_ref == effect.bearer_ref
                    and self.states[state_ref].dimension_ref == effect.dimension_ref
                    and self.states[state_ref].context_ref == effect.context_ref
                ),
                None,
            )
            self.add_state(
                StateFacet(
                    state_id=state_id,
                    bearer_ref=effect.bearer_ref,
                    dimension_ref=effect.dimension_ref,
                    value_ref=effect.value_ref,
                    context_ref=effect.context_ref,
                    opened_at=event.temporal_index,
                    support_refs=result.support_refs,
                    epistemic_state=EpistemicState.OBSERVED,
                    supersedes_state_ref=superseded,
                )
            )
        for relation_ref in result.closed_relation_refs:
            self._relation_closed_at[relation_ref] = event.temporal_index
        opening_effects = [
            effect
            for effect in transition.relation_effects
            if effect.kind is RelationEffectKind.OPEN
        ]
        for effect, relation_id in zip(opening_effects, result.opened_relation_refs):
            self.add_relation(
                RelationOccurrence(
                    relation_occurrence_id=relation_id,
                    relation_form_ref=effect.relation_form_ref,
                    bindings=effect.bindings,
                    context_ref=effect.context_ref,
                    temporal_index=event.temporal_index,
                    polarity=Polarity.POSITIVE,
                    modality="actual",
                    attribution_ref=None,
                    support_refs=result.support_refs,
                    contradiction_refs=(),
                    epistemic_state=effect.epistemic_state,
                )
            )
        self.transition_results.append(result)
        return result

    def as_dict(self) -> dict[str, Any]:
        def rows(store: Mapping[str, Any]) -> list[dict[str, Any]]:
            return [_plain(store[key]) for key in sorted(store)]

        return {
            "contexts": rows(self.contexts),
            "identities": rows(self.identities),
            "relations": rows(self.relations),
            "states": rows(self.states),
            "events": rows(self.events),
            "transitions": rows(self.transitions),
            "facets": rows(self.facets),
            "transition_results": [_plain(row) for row in self.transition_results],
            "state_closed_at": dict(sorted(self._state_closed_at.items())),
            "relation_closed_at": dict(sorted(self._relation_closed_at.items())),
        }

    @classmethod
    def restore(cls, payload: Mapping[str, Any]) -> "RelationalUniverse":
        try:
            universe = cls()
            pending_contexts = list(payload["contexts"])
            while pending_contexts:
                ready = [
                    row
                    for row in pending_contexts
                    if not row.get("parent_context_ref")
                    or row["parent_context_ref"] in universe.contexts
                ]
                if not ready:
                    raise ContractError(
                        "univers relationnel: parents de contextes absents ou cycliques"
                    )
                for row in ready:
                    universe.add_context(
                        ContextFrame(
                            context_id=row["context_id"],
                            kind=ContextKind(row["kind"]),
                            parent_context_ref=row.get("parent_context_ref"),
                            attribution_ref=row.get("attribution_ref"),
                            support_refs=tuple(row["support_refs"]),
                        )
                    )
                    pending_contexts.remove(row)
            for row in payload["identities"]:
                universe.add_identity(
                    IdentityAnchor(
                        identity_id=row["identity_id"],
                        origin_context_ref=row["origin_context_ref"],
                        support_refs=tuple(row["support_refs"]),
                        surface_aliases=tuple(row["surface_aliases"]),
                    )
                )
            for row in payload["relations"]:
                universe.add_relation(_relation_from_dict(row))
            for row in payload["states"]:
                universe.add_state(
                    StateFacet(
                        **{
                            **row,
                            "support_refs": tuple(row["support_refs"]),
                            "epistemic_state": EpistemicState(row["epistemic_state"]),
                        }
                    )
                )
            for row in payload["events"]:
                universe.add_event(
                    EventOccurrence(
                        **{
                            **row,
                            "bindings": _bindings_from_dict(row["bindings"]),
                            "support_refs": tuple(row["support_refs"]),
                            "epistemic_state": EpistemicState(row["epistemic_state"]),
                        }
                    )
                )
            for row in payload["transitions"]:
                universe.add_transition(_transition_from_dict(row))
            for row in payload["facets"]:
                universe.add_facet(
                    SituatedFacet(
                        **{
                            **row,
                            "active_relation_refs": tuple(row["active_relation_refs"]),
                            "active_state_refs": tuple(row["active_state_refs"]),
                            "active_role_refs": tuple(row["active_role_refs"]),
                            "support_refs": tuple(row["support_refs"]),
                        }
                    )
                )
            universe.transition_results = [
                TransitionResult(
                    **{
                        **row,
                        "closed_state_refs": tuple(row["closed_state_refs"]),
                        "opened_state_refs": tuple(row["opened_state_refs"]),
                        "closed_relation_refs": tuple(row["closed_relation_refs"]),
                        "opened_relation_refs": tuple(row["opened_relation_refs"]),
                        "support_refs": tuple(row["support_refs"]),
                    }
                )
                for row in payload["transition_results"]
            ]
            universe._state_closed_at = {
                str(key): int(value)
                for key, value in payload["state_closed_at"].items()
            }
            universe._relation_closed_at = {
                str(key): int(value)
                for key, value in payload["relation_closed_at"].items()
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError(f"univers relationnel: snapshot invalide: {exc}") from exc
        return universe

    def _check_preconditions(
        self, transition: TransitionCandidate, temporal_index: int
    ) -> None:
        failures = []
        for condition in transition.preconditions:
            result = self.current_state(
                bearer_ref=condition.bearer_ref,
                dimension_ref=condition.dimension_ref,
                context_ref=condition.context_ref,
                at=temporal_index,
            )
            if result.status != "supported" or result.value_refs != (
                condition.expected_value_ref,
            ):
                failures.append(condition)
        if failures:
            raise ContractError(f"transition: préconditions non satisfaites: {failures}")

    @staticmethod
    def _state_effect_id(
        transition: TransitionCandidate, effect: StateEffect
    ) -> str:
        return _stable_id(
            "state",
            {
                "transition_ref": transition.transition_id,
                "bearer_ref": effect.bearer_ref,
                "dimension_ref": effect.dimension_ref,
                "value_ref": effect.value_ref,
                "context_ref": effect.context_ref,
            },
        )

    @staticmethod
    def _relation_effect_id(
        transition: TransitionCandidate, effect: RelationEffect
    ) -> str:
        return _stable_id(
            "relation",
            {
                "transition_ref": transition.transition_id,
                "kind": effect.kind.value,
                "relation_form_ref": effect.relation_form_ref,
                "bindings": [vars(row) for row in effect.bindings],
                "context_ref": effect.context_ref,
            },
        )

    def _require_context(self, context_ref: str) -> None:
        if context_ref not in self.contexts:
            raise ContractError(f"contexte absent: {context_ref}")

    def _transition(self, transition_ref: str) -> TransitionCandidate:
        try:
            return self.transitions[transition_ref]
        except KeyError as exc:
            raise ContractError(f"transition absente: {transition_ref}") from exc

    @staticmethod
    def _insert_unique(
        store: dict[str, Any], identifier: str, value: Any, kind: str
    ) -> None:
        if identifier in store and store[identifier] != value:
            raise ContractError(f"{kind}: identité en conflit")
        store[identifier] = value


@dataclass(frozen=True)
class FormFactor:
    factor_ref: str
    value_ref: str
    context_ref: str
    role_ref: str | None = None
    position: int | None = None
    weight: float = 1.0
    support_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("factor_ref", "value_ref", "context_ref"):
            _required(getattr(self, field_name), field_name)
        if self.position is not None and self.position < 0:
            raise ContractError("facteur: position négative")
        if not math.isfinite(self.weight) or self.weight <= 0:
            raise ContractError("facteur: poids positif fini requis")
        object.__setattr__(self, "support_refs", _unique(self.support_refs))


@dataclass(frozen=True)
class DistributedForm:
    form_id: str
    vector: np.ndarray = field(repr=False, compare=False)
    factors: tuple[FormFactor, ...]
    losses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.form_id, "form_id")
        vector = np.asarray(self.vector, dtype=np.float64).copy()
        if vector.ndim != 1 or not vector.size or not np.isfinite(vector).all():
            raise ContractError("forme distribuée: vecteur 1D fini requis")
        vector.setflags(write=False)
        object.__setattr__(self, "vector", vector)
        object.__setattr__(self, "factors", tuple(self.factors))
        object.__setattr__(self, "losses", tuple(self.losses))
        if not self.factors:
            raise ContractError("forme distribuée: facteurs requis")


@dataclass(frozen=True)
class DecodedFactor:
    factor_ref: str
    score: float
    traced: bool


class VectorSymbolicMemory:
    """VSA bipolaire déterministe avec trace relationnelle obligatoire."""

    def __init__(self, *, dimension: int = 1024, seed: str = "seman2") -> None:
        if dimension < 64:
            raise ContractError("VSA: dimension minimale 64")
        self.dimension = dimension
        self.seed = _required(seed, "seed")
        self._anchors: dict[str, np.ndarray] = {}
        self._forms: dict[str, DistributedForm] = {}

    def anchor(self, ref: str) -> np.ndarray:
        _required(ref, "ancre")
        if ref not in self._anchors:
            raw = hashlib.shake_256(f"{self.seed}|{ref}".encode()).digest(
                (self.dimension + 7) // 8
            )
            bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[: self.dimension]
            vector = np.where(bits == 0, -1.0, 1.0).astype(np.float64)
            vector.setflags(write=False)
            self._anchors[ref] = vector
        return self._anchors[ref]

    def bind(self, left: np.ndarray, right: np.ndarray) -> np.ndarray:
        self._validate_vector(left)
        self._validate_vector(right)
        return np.multiply(left, right)

    def permute(self, vector: np.ndarray, position: int) -> np.ndarray:
        self._validate_vector(vector)
        if position < 0:
            raise ContractError("VSA: position négative")
        return np.roll(vector, (position * 131) % self.dimension)

    def similarity(self, left: np.ndarray, right: np.ndarray) -> float:
        self._validate_vector(left)
        self._validate_vector(right)
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        return 0.0 if denominator == 0 else float(np.dot(left, right) / denominator)

    def encode(self, form_id: str, factors: Iterable[FormFactor]) -> DistributedForm:
        factor_tuple = tuple(factors)
        if not factor_tuple:
            raise ContractError("VSA: aucun facteur à encoder")
        terms = [self._term(factor) * factor.weight for factor in factor_tuple]
        vector = np.sum(terms, axis=0)
        norm = float(np.linalg.norm(vector))
        if norm == 0:
            raise ContractError("VSA: superposition nulle")
        form = DistributedForm(form_id, vector / norm, factor_tuple)
        if form_id in self._forms and not self.equivalent(self._forms[form_id], form):
            raise ContractError("VSA: identité de forme en conflit")
        self._forms[form_id] = form
        return form

    def get(self, form_id: str) -> DistributedForm:
        try:
            return self._forms[form_id]
        except KeyError as exc:
            raise ContractError(f"VSA: forme absente {form_id}") from exc

    def decode(
        self,
        form: DistributedForm,
        candidates: Iterable[FormFactor],
        *,
        limit: int | None = None,
    ) -> tuple[DecodedFactor, ...]:
        candidate_tuple = tuple(candidates)
        traced_refs = {factor.factor_ref for factor in form.factors}
        decoded = [
            DecodedFactor(
                factor_ref=candidate.factor_ref,
                score=self.similarity(form.vector, self._term(candidate)),
                traced=candidate.factor_ref in traced_refs,
            )
            for candidate in candidate_tuple
        ]
        decoded.sort(key=lambda row: (-row.score, row.factor_ref))
        return tuple(decoded if limit is None else decoded[:limit])

    def unbind_role(
        self,
        form: DistributedForm,
        role_ref: str,
        candidate_value_refs: Iterable[str],
    ) -> tuple[tuple[str, float], ...]:
        role = self.anchor(f"role:{role_ref}")
        estimate = self.bind(form.vector, role)
        results = [
            (value_ref, self.similarity(estimate, self.anchor(f"value:{value_ref}")))
            for value_ref in candidate_value_refs
        ]
        return tuple(sorted(results, key=lambda row: (-row[1], row[0])))

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "seed": self.seed,
            "forms": [
                {
                    "form_id": form.form_id,
                    "factors": [_plain(factor) for factor in form.factors],
                    "losses": list(form.losses),
                }
                for form in sorted(self._forms.values(), key=lambda row: row.form_id)
            ],
        }

    @classmethod
    def restore(cls, payload: Mapping[str, Any]) -> "VectorSymbolicMemory":
        try:
            memory = cls(dimension=int(payload["dimension"]), seed=payload["seed"])
            for row in payload["forms"]:
                factors = tuple(
                    FormFactor(
                        **{
                            **factor,
                            "support_refs": tuple(factor["support_refs"]),
                        }
                    )
                    for factor in row["factors"]
                )
                encoded = memory.encode(row["form_id"], factors)
                if row["losses"]:
                    memory._forms[row["form_id"]] = DistributedForm(
                        encoded.form_id,
                        encoded.vector,
                        encoded.factors,
                        tuple(row["losses"]),
                    )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError(f"VSA: snapshot invalide: {exc}") from exc
        return memory

    @staticmethod
    def equivalent(left: DistributedForm, right: DistributedForm) -> bool:
        return left.factors == right.factors and np.array_equal(left.vector, right.vector)

    def _term(self, factor: FormFactor) -> np.ndarray:
        value = self.anchor(f"value:{factor.value_ref}")
        if factor.position is not None:
            value = self.permute(value, factor.position)
        if factor.role_ref:
            value = self.bind(self.anchor(f"role:{factor.role_ref}"), value)
        context = self.bind(
            self.anchor("role:context"), self.anchor(f"context:{factor.context_ref}")
        )
        # Le contexte contribue sans rendre impossible la déliaison rôle/valeur.
        return value + (0.35 * context)

    def _validate_vector(self, vector: np.ndarray) -> None:
        if np.asarray(vector).shape != (self.dimension,):
            raise ContractError(
                f"VSA: dimension invalide {np.asarray(vector).shape}, "
                f"attendu {(self.dimension,)}"
            )


@dataclass(frozen=True)
class ContributionTrace:
    consumer_ref: str
    input_factor_ref: str
    operation: str
    effect_on_output: str
    context_ref: str
    source_refs: tuple[str, ...]
    weight_change: float | None = None
    reason_if_ignored: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "consumer_ref",
            "input_factor_ref",
            "operation",
            "effect_on_output",
            "context_ref",
        ):
            _required(getattr(self, field_name), field_name)
        object.__setattr__(self, "source_refs", _unique(self.source_refs))
        if not self.source_refs:
            raise ContractError("trace de contribution: source requise")
        if self.weight_change is not None and not math.isfinite(self.weight_change):
            raise ContractError("trace de contribution: poids non fini")


class DevelopmentalCore:
    """Façade minimale synchronisant univers relationnel et formes."""

    def __init__(
        self,
        *,
        vector_dimension: int = 1024,
        seed: str = "seman2",
        memory_policy: MemoryPolicy | None = None,
    ) -> None:
        self.universe = RelationalUniverse()
        self.forms = VectorSymbolicMemory(dimension=vector_dimension, seed=seed)
        self.memory = CognitiveMemory(memory_policy)
        self.contribution_traces: list[ContributionTrace] = []

    def encode_form(
        self, form_id: str, factors: Iterable[FormFactor]
    ) -> DistributedForm:
        factor_tuple = tuple(factors)
        for factor in factor_tuple:
            self.universe._require_context(factor.context_ref)
        form = self.forms.encode(form_id, factor_tuple)
        for factor in factor_tuple:
            self.contribution_traces.append(
                ContributionTrace(
                    consumer_ref=form_id,
                    input_factor_ref=factor.factor_ref,
                    operation="bind-superpose",
                    effect_on_output="distributed-form-component",
                    context_ref=factor.context_ref,
                    source_refs=factor.support_refs or (factor.factor_ref,),
                    weight_change=factor.weight,
                )
            )
        return form

    def explain_form(self, form_id: str) -> tuple[ContributionTrace, ...]:
        self.forms.get(form_id)
        return tuple(
            trace for trace in self.contribution_traces if trace.consumer_ref == form_id
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": "seman2-developmental-core",
            "universe": self.universe.as_dict(),
            "forms": self.forms.as_dict(),
            "memory": self.memory.as_dict(),
            "contribution_traces": [
                _plain(row) for row in self.contribution_traces
            ],
        }

    @classmethod
    def restore(cls, payload: Mapping[str, Any]) -> "DevelopmentalCore":
        if payload.get("format") != "seman2-developmental-core":
            raise ContractError("cœur développemental: format incompatible")
        try:
            forms = VectorSymbolicMemory.restore(payload["forms"])
            core = cls(
                vector_dimension=forms.dimension,
                seed=forms.seed,
                memory_policy=MemoryPolicy(**payload["memory"]["policy"]),
            )
            core.universe = RelationalUniverse.restore(payload["universe"])
            core.forms = forms
            core.memory = CognitiveMemory.restore(payload["memory"])
            core.contribution_traces = [
                ContributionTrace(
                    **{
                        **row,
                        "source_refs": tuple(row["source_refs"]),
                    }
                )
                for row in payload["contribution_traces"]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError(f"cœur développemental: snapshot invalide: {exc}") from exc
        return core


def _bindings_from_dict(rows: Iterable[Mapping[str, Any]]) -> tuple[RoleBinding, ...]:
    return tuple(RoleBinding(**row) for row in rows)


def _relation_from_dict(row: Mapping[str, Any]) -> RelationOccurrence:
    return RelationOccurrence(
        **{
            **row,
            "bindings": _bindings_from_dict(row["bindings"]),
            "polarity": Polarity(row["polarity"]),
            "support_refs": tuple(row["support_refs"]),
            "contradiction_refs": tuple(row["contradiction_refs"]),
            "epistemic_state": EpistemicState(row["epistemic_state"]),
        }
    )


def _transition_from_dict(row: Mapping[str, Any]) -> TransitionCandidate:
    return TransitionCandidate(
        **{
            **row,
            "preconditions": tuple(
                StateCondition(**item) for item in row["preconditions"]
            ),
            "state_effects": tuple(
                StateEffect(**item) for item in row["state_effects"]
            ),
            "relation_effects": tuple(
                RelationEffect(
                    **{
                        **item,
                        "kind": RelationEffectKind(item["kind"]),
                        "bindings": _bindings_from_dict(item["bindings"]),
                        "epistemic_state": EpistemicState(item["epistemic_state"]),
                    }
                )
                for item in row["relation_effects"]
            ),
            "invariant_state_refs": tuple(row["invariant_state_refs"]),
            "support_occurrence_refs": tuple(row["support_occurrence_refs"]),
            "exception_occurrence_refs": tuple(row["exception_occurrence_refs"]),
        }
    )
