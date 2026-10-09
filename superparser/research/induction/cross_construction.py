"""POC-11: cross-construction transfer guided by learned opaque effects."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import permutations
import json
from typing import Any, Mapping, Sequence

from .partial_state import ReportedProposition
from .transitions import EffectTemplate


@dataclass(frozen=True, slots=True)
class ConstructionEvidence:
    observation_id: str
    construction_id: str
    arity: int
    effects: tuple[EffectTemplate, ...]
    residuals_json: str = "{}"

    @classmethod
    def build(cls, observation_id, construction_id, arity, effects, residuals=None):
        return cls(
            observation_id,
            construction_id,
            arity,
            tuple(sorted(effects)),
            json.dumps(dict(residuals or {}), sort_keys=True, separators=(",", ":")),
        )


@dataclass(frozen=True, slots=True)
class ConstructionProfile:
    construction_id: str
    arity: int
    effects: tuple[EffectTemplate, ...]
    support: int
    observation_ids: tuple[str, ...]
    residual_variants: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CrossConstructionAlignment:
    alignment_id: str
    left_id: str
    right_id: str
    left_to_right: tuple[int, ...]
    effects: tuple[EffectTemplate, ...]
    left_residuals: tuple[str, ...]
    right_residuals: tuple[str, ...]
    support: int

    def predict_right(self, right_arguments: Sequence[str]) -> tuple[ReportedProposition, ...]:
        if len(right_arguments) != len(self.left_to_right):
            raise ValueError("right argument arity differs")
        right_effects = tuple(_remap(effect, self.left_to_right) for effect in self.effects)
        return tuple(effect.instantiate(right_arguments) for effect in right_effects)


class CrossConstructionLearner:
    def __init__(self, *, min_support: int = 4) -> None:
        self.min_support = min_support
        self.profiles: tuple[ConstructionProfile, ...] = ()
        self.alignments: tuple[CrossConstructionAlignment, ...] = ()

    def fit(self, evidence: Sequence[ConstructionEvidence]) -> "CrossConstructionLearner":
        grouped: dict[str, list[ConstructionEvidence]] = {}
        for row in evidence:
            grouped.setdefault(row.construction_id, []).append(row)
        profiles = []
        for construction_id, rows in sorted(grouped.items()):
            arities = {row.arity for row in rows}
            if len(arities) != 1:
                continue
            signatures = Counter(row.effects for row in rows)
            effects, support = max(signatures.items(), key=lambda row: (row[1], repr(row[0])))
            if support < self.min_support or not effects:
                continue
            supporting = [row for row in rows if row.effects == effects]
            profiles.append(
                ConstructionProfile(
                    construction_id,
                    arities.pop(),
                    effects,
                    support,
                    tuple(row.observation_id for row in supporting),
                    tuple(sorted({row.residuals_json for row in supporting})),
                )
            )
        self.profiles = tuple(profiles)
        alignments = []
        for left_index, left in enumerate(profiles):
            for right in profiles[left_index + 1 :]:
                if left.arity != right.arity:
                    continue
                left_used = sorted({slot for effect in left.effects for slot in effect.argument_slots})
                right_used = sorted({slot for effect in right.effects for slot in effect.argument_slots})
                if len(left_used) != len(right_used):
                    continue
                for targets in permutations(right_used):
                    mutable_mapping = [-1] * left.arity
                    for source, target in zip(left_used, targets):
                        mutable_mapping[source] = target
                    mapping = tuple(mutable_mapping)
                    if tuple(sorted(_remap(effect, mapping) for effect in left.effects)) != right.effects:
                        continue
                    body = [left.construction_id, right.construction_id, mapping, [repr(row) for row in left.effects]]
                    alignment_id = "cross_alignment_" + sha256(
                        json.dumps(body, sort_keys=True).encode()
                    ).hexdigest()[:20]
                    alignments.append(
                        CrossConstructionAlignment(
                            alignment_id,
                            left.construction_id,
                            right.construction_id,
                            tuple(mapping),
                            left.effects,
                            left.residual_variants,
                            right.residual_variants,
                            min(left.support, right.support),
                        )
                    )
        self.alignments = tuple(sorted(alignments, key=lambda row: row.alignment_id))
        return self


def _remap(effect: EffectTemplate, left_to_right: Sequence[int]) -> EffectTemplate:
    return EffectTemplate(
        effect.relation_id,
        tuple(left_to_right[index] for index in effect.argument_slots),
        effect.truth,
    )
