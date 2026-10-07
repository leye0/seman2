"""Contrôle progressif et borné de la profondeur de retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .cognitive_memory import CognitiveMemory, RetrievalHit, RetrievalRequest
from .contracts import ContractError


class RetrievalStopReason(str, Enum):
    GOAL_SATISFIED = "goal-satisfied"
    MARGINAL_GAIN = "marginal-gain-insufficient"
    WORK_BUDGET = "work-budget-exhausted"
    DEPTH_EXHAUSTED = "depth-exhausted"
    CLARIFICATION = "clarification-required"


@dataclass(frozen=True)
class RetrievalControlPolicy:
    maximum_depth: int = 5
    maximum_total_hits: int = 24
    maximum_work_units: int = 64
    support_threshold: float = 0.48
    decisiveness_margin: float = 0.06
    minimum_marginal_gain: float = 0.01

    def __post_init__(self) -> None:
        if not 0 <= self.maximum_depth <= 5:
            raise ContractError("attention: profondeur hors [0,5]")
        if self.maximum_total_hits < 1 or self.maximum_work_units < 1:
            raise ContractError("attention: budgets positifs requis")
        for name in (
            "support_threshold",
            "decisiveness_margin",
            "minimum_marginal_gain",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ContractError(f"attention: {name} hors [0,1]")


@dataclass(frozen=True)
class RetrievalLevel:
    depth: int
    label: str
    request: RetrievalRequest

    def __post_init__(self) -> None:
        if not 0 <= self.depth <= 5:
            raise ContractError("attention: niveau hors [0,5]")
        if not self.label:
            raise ContractError("attention: label de niveau requis")


@dataclass(frozen=True)
class RetrievalStep:
    depth: int
    label: str
    hits: tuple[RetrievalHit, ...]
    new_content_refs: tuple[str, ...]
    marginal_gain: float
    cumulative_work: int


@dataclass(frozen=True)
class ProgressiveRetrievalResult:
    goal_ref: str
    steps: tuple[RetrievalStep, ...]
    ranked_hits: tuple[RetrievalHit, ...]
    selected_ref: str | None
    stop_reason: RetrievalStopReason
    deepest_level: int
    projected_to_focus: tuple[str, ...] = ()


class ProgressiveAttentionController:
    def __init__(self, policy: RetrievalControlPolicy | None = None) -> None:
        self.policy = policy or RetrievalControlPolicy()

    def run(
        self,
        memory: CognitiveMemory,
        levels: tuple[RetrievalLevel, ...],
        *,
        project_selected: bool = False,
    ) -> ProgressiveRetrievalResult:
        if not levels:
            raise ContractError("attention: plan de retrieval vide")
        if tuple(sorted(level.depth for level in levels)) != tuple(
            level.depth for level in levels
        ):
            raise ContractError("attention: niveaux non ordonnés")
        goal = levels[0].request.goal_ref
        if any(level.request.goal_ref != goal for level in levels):
            raise ContractError("attention: buts divergents dans un plan")

        all_hits: dict[str, RetrievalHit] = {}
        steps = []
        work = 0
        previous_best = 0.0
        stop_reason = RetrievalStopReason.DEPTH_EXHAUSTED
        selected_ref = None

        for level in levels:
            if level.depth > self.policy.maximum_depth:
                stop_reason = RetrievalStopReason.WORK_BUDGET
                break
            remaining_hits = self.policy.maximum_total_hits - len(all_hits)
            remaining_work = self.policy.maximum_work_units - work
            if remaining_hits <= 0 or remaining_work <= 0:
                stop_reason = RetrievalStopReason.WORK_BUDGET
                break
            hits = memory.retrieve(level.request)
            allowed = hits[: min(remaining_hits, remaining_work)]
            work += len(allowed)
            new_refs = []
            for hit in allowed:
                previous = all_hits.get(hit.content_ref)
                if previous is None:
                    new_refs.append(hit.content_ref)
                    all_hits[hit.content_ref] = hit
                elif hit.score > previous.score:
                    all_hits[hit.content_ref] = hit
            ranked = _ranked(all_hits)
            best = ranked[0].score if ranked else 0.0
            marginal_gain = best - previous_best
            steps.append(
                RetrievalStep(
                    depth=level.depth,
                    label=level.label,
                    hits=tuple(allowed),
                    new_content_refs=tuple(new_refs),
                    marginal_gain=marginal_gain,
                    cumulative_work=work,
                )
            )
            previous_best = max(previous_best, best)

            if _decisive(ranked, self.policy):
                selected_ref = ranked[0].content_ref
                stop_reason = RetrievalStopReason.GOAL_SATISFIED
                break
            if level.depth > 0 and marginal_gain < self.policy.minimum_marginal_gain:
                stop_reason = (
                    RetrievalStopReason.CLARIFICATION
                    if len(ranked) > 1
                    else RetrievalStopReason.MARGINAL_GAIN
                )
                break
            if work >= self.policy.maximum_work_units:
                stop_reason = RetrievalStopReason.WORK_BUDGET
                break
        else:
            ranked = _ranked(all_hits)
            if not _decisive(ranked, self.policy) and len(ranked) > 1:
                stop_reason = RetrievalStopReason.CLARIFICATION

        ranked = _ranked(all_hits)
        projected: tuple[str, ...] = ()
        if project_selected and selected_ref:
            memory.focus(selected_ref)
            projected = (selected_ref,)
        deepest = steps[-1].depth if steps else -1
        return ProgressiveRetrievalResult(
            goal_ref=goal,
            steps=tuple(steps),
            ranked_hits=ranked,
            selected_ref=selected_ref,
            stop_reason=stop_reason,
            deepest_level=deepest,
            projected_to_focus=projected,
        )


def _ranked(hits: dict[str, RetrievalHit]) -> tuple[RetrievalHit, ...]:
    return tuple(sorted(hits.values(), key=lambda row: (-row.score, row.content_ref)))


def _decisive(
    ranked: tuple[RetrievalHit, ...], policy: RetrievalControlPolicy
) -> bool:
    if not ranked or ranked[0].score < policy.support_threshold:
        return False
    runner_up = ranked[1].score if len(ranked) > 1 else 0.0
    return ranked[0].score - runner_up >= policy.decisiveness_margin

