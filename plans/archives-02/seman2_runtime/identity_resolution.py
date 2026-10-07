"""Continuité d'identité contextuelle avec décisions révisables et expliquées."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

from .contracts import ContractError, canonical_json
from .developmental_core import DevelopmentalCore, IdentityAnchor, SituatedFacet


@dataclass(frozen=True)
class IdentityResolutionPolicy:
    selection_threshold: float = 0.7
    selection_margin: float = 0.15
    maximum_candidates: int = 5

    def __post_init__(self) -> None:
        if not 0.0 <= self.selection_threshold <= 1.0:
            raise ContractError("identité: seuil hors [0,1]")
        if not 0.0 <= self.selection_margin <= 1.0:
            raise ContractError("identité: marge hors [0,1]")
        if self.maximum_candidates < 1:
            raise ContractError("identité: maximum_candidates invalide")


@dataclass(frozen=True)
class MentionOccurrence:
    mention_ref: str
    context_ref: str
    discourse_ref: str
    temporal_index: int
    surface_aliases: tuple[str, ...]
    grammatical_features: tuple[tuple[str, str], ...]
    role_refs: tuple[str, ...]
    support_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("mention_ref", "context_ref", "discourse_ref"):
            if not getattr(self, name):
                raise ContractError(f"identité: {name} requis")
        if self.temporal_index < 0:
            raise ContractError("identité: index temporel négatif")
        for name in ("surface_aliases", "role_refs", "support_refs"):
            values = tuple(getattr(self, name))
            if len(values) != len(set(values)):
                raise ContractError("identité: valeurs dupliquées")
            object.__setattr__(self, name, values)
        features = tuple(sorted(self.grammatical_features))
        if len({key for key, _ in features}) != len(features):
            raise ContractError("identité: trait grammatical dupliqué")
        object.__setattr__(self, "grammatical_features", features)
        if not self.support_refs:
            raise ContractError("identité: support requis")


@dataclass(frozen=True)
class IdentityProfile:
    identity_ref: str
    mention_refs: tuple[str, ...]
    surface_aliases: tuple[str, ...]
    discourse_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    grammatical_features: tuple[tuple[str, str], ...]
    last_temporal_index: int


@dataclass(frozen=True)
class IdentityCandidate:
    candidate_ref: str
    identity_ref: str | None
    score: float
    support_signals: tuple[str, ...]
    conflict_signals: tuple[str, ...]
    creates_new_identity: bool


@dataclass(frozen=True)
class IdentityResolutionDecision:
    mention_ref: str
    candidates: tuple[IdentityCandidate, ...]
    selected_candidate_ref: str | None
    selected_identity_ref: str | None
    status: str
    rationale: str


class IdentityResolver:
    def __init__(
        self,
        core: DevelopmentalCore,
        policy: IdentityResolutionPolicy | None = None,
    ) -> None:
        self.core = core
        self.policy = policy or IdentityResolutionPolicy()
        self.profiles: dict[str, IdentityProfile] = {}
        self.mentions: dict[str, MentionOccurrence] = {}

    def propose(self, mention: MentionOccurrence) -> IdentityResolutionDecision:
        if mention.context_ref not in self.core.universe.contexts:
            raise ContractError("identité: contexte de mention absent")
        existing = self.mentions.get(mention.mention_ref)
        if existing and existing != mention:
            raise ContractError("identité: mention en conflit")
        self.mentions[mention.mention_ref] = mention
        candidates = [self._score(mention, profile) for profile in self.profiles.values()]
        new_ref = _new_identity_ref(mention)
        new_score = 0.65 if candidates else 1.0
        candidates.append(
            IdentityCandidate(
                candidate_ref=f"identity-candidate:new:{new_ref}",
                identity_ref=new_ref,
                score=new_score,
                support_signals=("new-identity-always-available",),
                conflict_signals=(),
                creates_new_identity=True,
            )
        )
        candidates.sort(key=lambda row: (-row.score, row.candidate_ref))
        bounded = tuple(candidates[: self.policy.maximum_candidates])
        best = bounded[0]
        runner_up = bounded[1].score if len(bounded) > 1 else 0.0
        if (
            best.score >= self.policy.selection_threshold
            and best.score - runner_up >= self.policy.selection_margin
        ):
            return IdentityResolutionDecision(
                mention_ref=mention.mention_ref,
                candidates=bounded,
                selected_candidate_ref=best.candidate_ref,
                selected_identity_ref=best.identity_ref,
                status="decisive-candidate",
                rationale="support et marge suffisants; décision encore explicite",
            )
        return IdentityResolutionDecision(
            mention_ref=mention.mention_ref,
            candidates=bounded,
            selected_candidate_ref=None,
            selected_identity_ref=None,
            status="ambiguous",
            rationale="plusieurs identités restent compatibles ou support insuffisant",
        )

    def commit(
        self,
        decision: IdentityResolutionDecision,
        *,
        candidate_ref: str | None = None,
        distributed_form_ref: str | None = None,
    ) -> IdentityProfile:
        selected_ref = candidate_ref or decision.selected_candidate_ref
        if selected_ref is None:
            raise ContractError("identité: sélection explicite requise")
        try:
            candidate = next(
                row for row in decision.candidates if row.candidate_ref == selected_ref
            )
        except StopIteration as exc:
            raise ContractError("identité: candidat absent du beam") from exc
        mention = self.mentions[decision.mention_ref]
        identity_ref = candidate.identity_ref
        if identity_ref is None:
            raise ContractError("identité: référence candidate absente")
        if candidate.creates_new_identity:
            self.core.universe.add_identity(
                IdentityAnchor(
                    identity_id=identity_ref,
                    origin_context_ref=mention.context_ref,
                    support_refs=mention.support_refs,
                    surface_aliases=mention.surface_aliases,
                )
            )
            profile = IdentityProfile(
                identity_ref=identity_ref,
                mention_refs=(mention.mention_ref,),
                surface_aliases=tuple(sorted(set(mention.surface_aliases))),
                discourse_refs=(mention.discourse_ref,),
                context_refs=(mention.context_ref,),
                grammatical_features=mention.grammatical_features,
                last_temporal_index=mention.temporal_index,
            )
        else:
            profile = self.profiles[identity_ref]
            profile = IdentityProfile(
                identity_ref=identity_ref,
                mention_refs=tuple(sorted(set(profile.mention_refs) | {mention.mention_ref})),
                surface_aliases=tuple(
                    sorted(set(profile.surface_aliases) | set(mention.surface_aliases))
                ),
                discourse_refs=tuple(
                    sorted(set(profile.discourse_refs) | {mention.discourse_ref})
                ),
                context_refs=tuple(
                    sorted(set(profile.context_refs) | {mention.context_ref})
                ),
                grammatical_features=_merge_compatible_features(
                    profile.grammatical_features, mention.grammatical_features
                ),
                last_temporal_index=max(
                    profile.last_temporal_index, mention.temporal_index
                ),
            )
        self.profiles[identity_ref] = profile
        facet_ref = _facet_ref(identity_ref, mention)
        self.core.universe.add_facet(
            SituatedFacet(
                facet_id=facet_ref,
                identity_ref=identity_ref,
                context_ref=mention.context_ref,
                active_role_refs=mention.role_refs,
                distributed_form_ref=distributed_form_ref,
                support_refs=mention.support_refs,
                temporal_start=mention.temporal_index,
            )
        )
        return profile

    def _score(
        self, mention: MentionOccurrence, profile: IdentityProfile
    ) -> IdentityCandidate:
        support = []
        conflicts = []
        score = 0.0
        aliases = {value.casefold() for value in mention.surface_aliases}
        known_aliases = {value.casefold() for value in profile.surface_aliases}
        if aliases and aliases & known_aliases:
            score += 0.55
            support.append("surface-alias-match")
        if mention.discourse_ref in profile.discourse_refs:
            score += 0.20
            support.append("same-discourse")
        distance = abs(mention.temporal_index - profile.last_temporal_index)
        if distance <= 2:
            score += 0.10
            support.append("nearby-episode")
        old_features = dict(profile.grammatical_features)
        new_features = dict(mention.grammatical_features)
        shared = set(old_features) & set(new_features)
        incompatible = sorted(
            key for key in shared if old_features[key] != new_features[key]
        )
        if incompatible:
            score -= 0.60
            conflicts.extend(f"feature-conflict:{key}" for key in incompatible)
        elif shared:
            score += 0.15
            support.append("grammatical-features-compatible")
        score = max(0.0, min(1.0, score))
        return IdentityCandidate(
            candidate_ref=f"identity-candidate:existing:{profile.identity_ref}",
            identity_ref=profile.identity_ref,
            score=score,
            support_signals=tuple(support),
            conflict_signals=tuple(conflicts),
            creates_new_identity=False,
        )


def _new_identity_ref(mention: MentionOccurrence) -> str:
    digest = hashlib.sha256(
        canonical_json(
            {
                "mention_ref": mention.mention_ref,
                "context_ref": mention.context_ref,
                "support_refs": mention.support_refs,
            }
        ).encode()
    ).hexdigest()
    return f"identity:learned:{digest[:24]}"


def _facet_ref(identity_ref: str, mention: MentionOccurrence) -> str:
    digest = hashlib.sha256(
        canonical_json(
            {
                "identity_ref": identity_ref,
                "mention_ref": mention.mention_ref,
                "context_ref": mention.context_ref,
            }
        ).encode()
    ).hexdigest()
    return f"facet:{digest[:24]}"


def _merge_compatible_features(
    old: tuple[tuple[str, str], ...], new: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    merged = dict(old)
    for key, value in new:
        if key in merged and merged[key] != value:
            raise ContractError("identité: fusion de traits incompatibles")
        merged[key] = value
    return tuple(sorted(merged.items()))

