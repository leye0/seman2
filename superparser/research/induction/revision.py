"""POC-10: immutable hypothesis lineage, retirement and contextual splitting."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RevisionEvidence:
    evidence_id: str
    hypothesis_id: str
    context_id: str
    supports: bool
    source_id: str
    reliability: float = 1.0


@dataclass(frozen=True, slots=True)
class HypothesisRevision:
    revision_id: str
    hypothesis_id: str
    version: int
    parent_revision_id: str | None
    specialization_of: str | None
    context_id: str | None
    status: str
    payload_json: str
    evidence_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    ignored_evidence_ids: tuple[str, ...]
    confidence: float
    reason: str

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        assert isinstance(value, dict)
        return value


class HypothesisReviser:
    def __init__(
        self,
        *,
        min_support: int = 5,
        min_confidence: float = 0.8,
        min_source_reliability: float = 0.5,
    ) -> None:
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_source_reliability = min_source_reliability
        self.revisions: list[HypothesisRevision] = []
        self._evidence: dict[str, list[RevisionEvidence]] = {}

    def register(
        self,
        hypothesis_id: str,
        payload: Mapping[str, Any],
        evidence: Sequence[RevisionEvidence],
    ) -> HypothesisRevision:
        if any(row.hypothesis_id == hypothesis_id for row in self.revisions):
            raise ValueError(f"hypothesis already registered: {hypothesis_id}")
        self._evidence[hypothesis_id] = list(evidence)
        revision = self._make_revision(
            hypothesis_id,
            payload,
            version=1,
            parent=None,
            specialization_of=None,
            context=None,
            status="active",
            evidence=self._evidence[hypothesis_id],
            reason="initial",
        )
        self.revisions.append(revision)
        return revision

    def revise(
        self,
        hypothesis_id: str,
        evidence: Sequence[RevisionEvidence],
    ) -> tuple[HypothesisRevision, ...]:
        current = self.latest(hypothesis_id)
        if current.status != "active":
            raise ValueError("only an active hypothesis can be revised")
        if any(row.hypothesis_id != hypothesis_id for row in evidence):
            raise ValueError("evidence targets another hypothesis")
        known_ids = {row.evidence_id for rows in self._evidence.values() for row in rows}
        if known_ids.intersection(row.evidence_id for row in evidence):
            raise ValueError("duplicate evidence id")
        combined = [*self._evidence[hypothesis_id], *evidence]
        self._evidence[hypothesis_id] = combined
        reliable = [row for row in combined if row.reliability >= self.min_source_reliability]
        confidence = _confidence(reliable)
        support = sum(row.supports for row in reliable)
        next_version = current.version + 1
        if support >= self.min_support and confidence >= self.min_confidence:
            revision = self._make_revision(
                hypothesis_id,
                current.payload,
                next_version,
                current.revision_id,
                current.specialization_of,
                current.context_id,
                "active",
                combined,
                "confirmed",
            )
            self.revisions.append(revision)
            return (revision,)

        retired = self._make_revision(
            hypothesis_id,
            current.payload,
            next_version,
            current.revision_id,
            current.specialization_of,
            current.context_id,
            "retired",
            combined,
            "counterevidence",
        )
        self.revisions.append(retired)
        created = [retired]
        contexts = sorted({row.context_id for row in reliable})
        for context in contexts:
            contextual = [row for row in reliable if row.context_id == context]
            if sum(row.supports for row in contextual) < self.min_support:
                continue
            if _confidence(contextual) < self.min_confidence:
                continue
            child_id = hypothesis_id + "@" + sha256(context.encode()).hexdigest()[:10]
            self._evidence[child_id] = contextual
            child = self._make_revision(
                child_id,
                current.payload,
                1,
                retired.revision_id,
                hypothesis_id,
                context,
                "active",
                contextual,
                "contextual_split",
            )
            self.revisions.append(child)
            created.append(child)
        return tuple(created)

    def latest(self, hypothesis_id: str) -> HypothesisRevision:
        rows = [row for row in self.revisions if row.hypothesis_id == hypothesis_id]
        if not rows:
            raise KeyError(hypothesis_id)
        return max(rows, key=lambda row: row.version)

    @property
    def active(self) -> tuple[HypothesisRevision, ...]:
        identifiers = {row.hypothesis_id for row in self.revisions}
        return tuple(
            sorted(
                (self.latest(identifier) for identifier in identifiers if self.latest(identifier).status == "active"),
                key=lambda row: row.hypothesis_id,
            )
        )

    def lineage(self, hypothesis_id: str) -> tuple[HypothesisRevision, ...]:
        related = []
        frontier = {hypothesis_id}
        while frontier:
            current = frontier.pop()
            rows = [row for row in self.revisions if row.hypothesis_id == current]
            related.extend(rows)
            frontier.update(
                row.hypothesis_id
                for row in self.revisions
                if row.specialization_of == current
            )
        return tuple(sorted(related, key=lambda row: (row.hypothesis_id, row.version)))

    def _make_revision(
        self, hypothesis_id, payload, version, parent, specialization_of,
        context, status, evidence, reason,
    ) -> HypothesisRevision:
        reliable = [row for row in evidence if row.reliability >= self.min_source_reliability]
        body = [hypothesis_id, version, parent, context, status, [row.evidence_id for row in evidence]]
        revision_id = "revision_" + sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]
        return HypothesisRevision(
            revision_id,
            hypothesis_id,
            version,
            parent,
            specialization_of,
            context,
            status,
            json.dumps(dict(payload), sort_keys=True, separators=(",", ":")),
            tuple(row.evidence_id for row in reliable if row.supports),
            tuple(row.evidence_id for row in reliable if not row.supports),
            tuple(row.evidence_id for row in evidence if row.reliability < self.min_source_reliability),
            _confidence(reliable),
            reason,
        )


def _confidence(evidence: Sequence[RevisionEvidence]) -> float:
    return sum(row.supports for row in evidence) / len(evidence) if evidence else 0.0
