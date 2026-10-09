"""Three-level runtime: evidence, interpretation and coupled learning."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from ..evidence.model import EvidenceUnit
from ..evidence.store import EvidenceStore
from ..interpretation.model import AnalysisBundle
from ..interpretation.trips_adapter import TripsAdapter
from ..learning.engine import CoupledLearningRuntime
from ..learning.generation import GenerationCandidate
from ..learning.revision import revision_proposals


class Interpreter(Protocol):
    key: str

    def interpret(
        self,
        evidence: EvidenceUnit,
        context: Sequence[EvidenceUnit] = (),
        *,
        request_id: str | None = None,
    ) -> AnalysisBundle: ...


class Seman2Runtime:
    """Coordinates technical operations without dispatching on learned content."""

    def __init__(
        self,
        store: EvidenceStore,
        interpreter: Interpreter,
        *,
        context_window: int = 4,
        max_attempts: int = 3,
        learner: CoupledLearningRuntime | None = None,
    ) -> None:
        if context_window < 0:
            raise ValueError("context window cannot be negative")
        if max_attempts < 1:
            raise ValueError("max attempts must be positive")
        self.store = store
        self.interpreter = interpreter
        self.context_window = context_window
        self.max_attempts = max_attempts
        self.learner = learner

    @classmethod
    def open(
        cls,
        database: str | Path,
        *,
        interpreter: Interpreter | None = None,
        context_window: int = 4,
        max_attempts: int = 3,
    ) -> "Seman2Runtime":
        evidence_store = EvidenceStore(database)
        learner = CoupledLearningRuntime.open(database)
        return cls(
            evidence_store,
            interpreter or TripsAdapter(),
            context_window=context_window,
            max_attempts=max_attempts,
            learner=learner,
        )

    def close(self) -> None:
        if self.learner is not None:
            self.learner.close()
        self.store.close()

    def __enter__(self) -> "Seman2Runtime":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def ingest(
        self,
        raw: str,
        *,
        stream_id: str,
        kind: str = "text",
        source: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
        context: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        sequence: int | None = None,
    ) -> EvidenceUnit:
        return self.store.append(
            raw,
            stream_id=stream_id,
            kind=kind,
            source=source,
            observed_at=observed_at,
            context=context,
            metadata=metadata,
            sequence=sequence,
            interpreter_key=self.interpreter.key,
        )

    def process_next(self) -> AnalysisBundle | None:
        job = self.store.claim_next(interpreter_key=self.interpreter.key)
        if job is None:
            return None
        evidence = self.store.get(job.evidence_id)
        context = self.store.context_before(
            job.evidence_id, limit=self.context_window
        )
        persisted = False
        try:
            bundle = self.interpreter.interpret(
                evidence, context, request_id=job.job_id
            )
            self.store.persist_analysis(job, bundle)
            persisted = True
        except BaseException as exc:
            if not persisted:
                self.store.fail_job(
                    job,
                    f"{type(exc).__name__}: {exc}",
                    retry=job.attempts < self.max_attempts,
                )
            raise

        if self.learner is not None:
            try:
                self.learner.observe(evidence, bundle)
                prior = tuple(
                    previous
                    for evidence_id in bundle.context_evidence_ids
                    for previous in self.store.analyses_for(evidence_id)[-1:]
                )
                for proposal in revision_proposals(bundle, prior):
                    self.store.revise(**proposal)
            except BaseException as exc:
                # Level 1 and the native analysis are already durable. Learning
                # is a downstream, replayable stage and must not corrupt them.
                self.learner.store.record_failure(
                    "observe", bundle.analysis_id, f"{type(exc).__name__}: {exc}"
                )
        return bundle

    def process_all(self, *, limit: int | None = None) -> tuple[AnalysisBundle, ...]:
        if limit is not None and limit < 0:
            raise ValueError("processing limit cannot be negative")
        bundles: list[AnalysisBundle] = []
        while limit is None or len(bundles) < limit:
            bundle = self.process_next()
            if bundle is None:
                break
            bundles.append(bundle)
        return tuple(bundles)

    def replay(self, evidence_id: str) -> str:
        return self.store.enqueue_replay(
            evidence_id, interpreter_key=self.interpreter.key
        )

    def revise(
        self,
        hypothesis_id: str,
        *,
        evidence_id: str,
        score: float,
        operation: str = "rerank",
        derivation: Mapping[str, Any] | None = None,
    ) -> str:
        return self.store.revise(
            hypothesis_id,
            evidence_id=evidence_id,
            score=score,
            operation=operation,
            derivation=derivation,
        )

    def trace(self, evidence_id: str) -> dict[str, Any]:
        trace = self.store.trace(evidence_id)
        if self.learner is not None:
            trace["learned_structures"] = [
                row.as_dict()
                for row in self.learner.store.structures_for_evidence(evidence_id)
            ]
        return trace

    def consolidate(
        self, *, minimum_support: int = 2, use_discodop: bool = True
    ) -> dict[str, Any]:
        if self.learner is None:
            raise RuntimeError("level-3 learning is disabled")
        return self.learner.consolidate(
            minimum_support=minimum_support, use_discodop=use_discodop
        )

    def reprocess(self, *, minimum_similarity: float = 0.0) -> dict[str, Any]:
        if self.learner is None:
            raise RuntimeError("level-3 learning is disabled")
        return self.learner.reprocess(minimum_similarity=minimum_similarity)

    def retro(self) -> dict[str, Any]:
        """Renvoie les segments d'arbres appris vers les analyses conservées."""
        if self.learner is None:
            raise RuntimeError("level-3 learning is disabled")
        return self.learner.retro()

    def generate(
        self,
        target: Mapping[str, Any],
        *,
        context: Mapping[str, Any] | None = None,
        bindings: Mapping[str, Any] | None = None,
        limit: int = 10,
        modes: Sequence[str] = ("retrieve", "instantiate"),
    ) -> tuple[GenerationCandidate, ...]:
        if self.learner is None:
            raise RuntimeError("level-3 learning is disabled")
        return self.learner.generate(
            target, context=context, bindings=bindings, limit=limit, modes=modes
        )

    def status(self) -> dict[str, Any]:
        return {
            "journal_mode": self.store.journal_mode,
            "evidence": self.store.counts(),
            "learning": self.learner.status() if self.learner else None,
        }

    def model_trace(self, structure_id: str) -> dict[str, Any]:
        if self.learner is None:
            raise RuntimeError("level-3 learning is disabled")
        return self.learner.store.trace(structure_id)
