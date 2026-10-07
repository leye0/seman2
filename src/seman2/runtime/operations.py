"""Small, content-agnostic API over the complete three-level runtime."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..evidence.model import EvidenceUnit
from ..interpretation.model import AnalysisBundle
from ..learning.generation import GenerationCandidate
from ..learning.patterns import instantiate, match_pattern
from .engine import Seman2Runtime


class Operations:
    """Names the architectural operations without semantic dispatch tables."""

    def __init__(self, runtime: Seman2Runtime) -> None:
        self.runtime = runtime

    def ingest(self, raw: str, **metadata: Any) -> EvidenceUnit:
        return self.runtime.ingest(raw, **metadata)

    def interpret(self) -> AnalysisBundle | None:
        return self.runtime.process_next()

    def store(self, structure_id: str) -> Mapping[str, Any]:
        return self.runtime.model_trace(structure_id)

    def match(self, pattern: Any, instance: Any) -> Mapping[str, Any] | None:
        return match_pattern(pattern, instance)

    def retrieve(self, *, family: str | None = None) -> Sequence[Any]:
        learner = self.runtime.learner
        if learner is None:
            return ()
        return learner.store.structures(family=family)

    def align(self, evidence_id: str) -> Sequence[Any]:
        learner = self.runtime.learner
        if learner is None:
            return ()
        return tuple(
            row
            for row in learner.store.structures_for_evidence(evidence_id)
            if row.family == "alignment"
        )

    def generalize(self, *, minimum_support: int = 2) -> Mapping[str, Any]:
        return self.runtime.consolidate(minimum_support=minimum_support)

    def instantiate(self, pattern: Any, bindings: Mapping[str, Any]) -> Any:
        return instantiate(pattern, bindings)

    def rank(self, target: Mapping[str, Any], *, limit: int = 10) -> Sequence[GenerationCandidate]:
        return self.runtime.generate(target, limit=limit)

    def revise(self, hypothesis_id: str, **revision: Any) -> str:
        return self.runtime.revise(hypothesis_id, **revision)

    def trace(self, evidence_id: str) -> Mapping[str, Any]:
        return self.runtime.trace(evidence_id)

    def generate(self, target: Mapping[str, Any], **options: Any) -> Sequence[GenerationCandidate]:
        return self.runtime.generate(target, **options)
