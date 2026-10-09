"""POC-09: induction of opaque, argument-linked reported transitions."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from hashlib import sha256
import json
import math
from typing import Any, Sequence

from .partial_state import PartialState, ReportedProposition, compare_partial_states


@dataclass(frozen=True, slots=True)
class EventOccurrence:
    event_id: str
    component_id: str
    arguments: tuple[str, ...]
    source_id: str
    time_index: int
    polarity: bool = True
    mode: str = "asserted"


@dataclass(frozen=True, slots=True)
class TransitionEpisode:
    episode_id: str
    context_id: str
    before: PartialState
    event: EventOccurrence
    after: PartialState


@dataclass(frozen=True, slots=True, order=True)
class EffectTemplate:
    relation_id: str
    argument_slots: tuple[int, ...]
    truth: bool

    def instantiate(self, arguments: Sequence[str]) -> ReportedProposition:
        if self.argument_slots and max(self.argument_slots) >= len(arguments):
            raise ValueError("event does not provide every effect argument")
        return ReportedProposition(
            self.relation_id,
            tuple(arguments[index] for index in self.argument_slots),
            self.truth,
        )


@dataclass(frozen=True, slots=True)
class TransitionHypothesis:
    hypothesis_id: str
    component_id: str
    context_id: str
    effect: EffectTemplate
    support: int
    contradictions: int
    opportunities: int
    control_support: int
    control_opportunities: int
    confidence: float
    coverage: float
    lift: float
    evidence_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TransitionPrediction:
    event_id: str
    proposition: ReportedProposition
    hypothesis_id: str
    confidence: float
    lift: float
    evidence_ids: tuple[str, ...]

    @property
    def explanation_chain(self) -> tuple[str, ...]:
        return (*self.evidence_ids, self.hypothesis_id, self.event_id)


class TransitionInducer:
    def __init__(
        self,
        *,
        min_support: int = 5,
        min_confidence: float = 0.9,
        min_coverage: float = 0.5,
        min_lift: float = 1.5,
    ) -> None:
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_coverage = min_coverage
        self.min_lift = min_lift
        self.hypotheses: tuple[TransitionHypothesis, ...] = ()

    def fit(self, episodes: Sequence[TransitionEpisode]) -> "TransitionInducer":
        eligible = [episode for episode in episodes if _eligible(episode)]
        groups: dict[tuple[str, str], list[TransitionEpisode]] = {}
        observed: dict[tuple[str, str], set[EffectTemplate]] = {}
        observed_counts: dict[tuple[str, str], Counter[EffectTemplate]] = {}
        for episode in eligible:
            key = (episode.event.component_id, episode.context_id)
            groups.setdefault(key, []).append(episode)
            effects = _observed_effects(episode)
            observed.setdefault(key, set()).update(effects)
            observed_counts.setdefault(key, Counter()).update(effects)

        hypotheses = []
        for (component, context), group in sorted(groups.items()):
            controls = [
                episode for episode in eligible
                if episode.context_id == context and episode.event.component_id != component
            ]
            for effect in sorted(observed[(component, context)]):
                if observed_counts[(component, context)][effect] < self.min_support:
                    continue
                support_rows, contradiction_rows = _evaluate(effect, group)
                control_support, _ = _evaluate(effect, controls)
                support = len(support_rows)
                contradictions = len(contradiction_rows)
                evaluated = support + contradictions
                confidence = support / evaluated if evaluated else 0.0
                coverage = evaluated / len(group) if group else 0.0
                event_rate = (support + 1) / (len(group) + 2)
                control_rate = (len(control_support) + 1) / (len(controls) + 2)
                lift = event_rate / control_rate
                if (
                    support < self.min_support
                    or confidence < self.min_confidence
                    or coverage < self.min_coverage
                    or lift < self.min_lift
                ):
                    continue
                body = [component, context, effect.relation_id, effect.argument_slots, effect.truth]
                hypothesis_id = "transition_hypothesis_" + sha256(
                    json.dumps(body, sort_keys=True).encode()
                ).hexdigest()[:20]
                hypotheses.append(
                    TransitionHypothesis(
                        hypothesis_id,
                        component,
                        context,
                        effect,
                        support,
                        contradictions,
                        len(group),
                        len(control_support),
                        len(controls),
                        confidence,
                        coverage,
                        lift,
                        tuple(row.episode_id for row in support_rows),
                        tuple(row.episode_id for row in contradiction_rows),
                    )
                )
        self.hypotheses = tuple(sorted(hypotheses, key=lambda row: row.hypothesis_id))
        return self

    def predict(self, event: EventOccurrence, context_id: str) -> tuple[TransitionPrediction, ...]:
        if not event.polarity or event.mode != "asserted":
            return ()
        predictions = []
        for hypothesis in self.hypotheses:
            if hypothesis.component_id != event.component_id or hypothesis.context_id != context_id:
                continue
            try:
                proposition = hypothesis.effect.instantiate(event.arguments)
            except ValueError:
                continue
            predictions.append(
                TransitionPrediction(
                    event.event_id,
                    proposition,
                    hypothesis.hypothesis_id,
                    hypothesis.confidence,
                    hypothesis.lift,
                    hypothesis.evidence_ids,
                )
            )
        return tuple(predictions)


def _eligible(episode: TransitionEpisode) -> bool:
    event = episode.event
    return (
        event.polarity
        and event.mode == "asserted"
        and episode.before.source_id == event.source_id == episode.after.source_id
        and episode.before.time_index <= event.time_index <= episode.after.time_index
        and compare_partial_states(episode.before, episode.after).comparable
    )


def _observed_effects(episode: TransitionEpisode) -> set[EffectTemplate]:
    delta = compare_partial_states(episode.before, episode.after)
    propositions = list(delta.added) + [later for _, later in delta.explicitly_reversed]
    indexes: dict[str, int] = {}
    for index, argument in enumerate(episode.event.arguments):
        indexes.setdefault(argument, index)
    effects = set()
    for proposition in propositions:
        if not all(argument in indexes for argument in proposition.arguments):
            continue
        effects.add(
            EffectTemplate(
                proposition.relation_id,
                tuple(indexes[argument] for argument in proposition.arguments),
                proposition.truth,
            )
        )
    return effects


def _evaluate(effect: EffectTemplate, episodes: Sequence[TransitionEpisode]):
    support = []
    contradictions = []
    for episode in episodes:
        try:
            expected = effect.instantiate(episode.event.arguments)
        except ValueError:
            continue
        after = {row.atom: row.truth for row in episode.after.propositions}
        actual = after.get(expected.atom)
        if actual is expected.truth:
            support.append(episode)
        elif actual is not None:
            contradictions.append(episode)
    return support, contradictions
