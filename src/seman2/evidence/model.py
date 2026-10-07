"""Generic, domain-free records for the evidence level."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


JsonObject = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class EvidenceUnit:
    """An immutable observation and its directly observable context."""

    evidence_id: str
    stream_id: str
    sequence: int
    kind: str
    raw: str
    raw_sha256: str
    source: JsonObject
    observed_at: str | None
    context: JsonObject
    metadata: JsonObject
    recorded_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.evidence_id,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "raw": self.raw,
            "raw_sha256": self.raw_sha256,
            "source": dict(self.source),
            "observed_at": self.observed_at,
            "context": dict(self.context),
            "metadata": dict(self.metadata),
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class ProcessingJob:
    """A leased request to derive a new analysis from an evidence unit."""

    job_id: str
    evidence_id: str
    interpreter_key: str
    generation: int
    status: str
    attempts: int
    lease_token: str | None

