"""Generic structures shared by every linguistic adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """A half-open parser-input span, optionally mapped back to evidence."""

    start: int
    end: int
    evidence_id: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None
    unit: str = "unicode-codepoint"

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "unit": self.unit,
            "evidence_id": self.evidence_id,
            "evidence_start": self.evidence_start,
            "evidence_end": self.evidence_end,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceSpan":
        return cls(
            start=int(value["start"]),
            end=int(value["end"]),
            evidence_id=value.get("evidence_id"),
            evidence_start=value.get("evidence_start"),
            evidence_end=value.get("evidence_end"),
            unit=str(value.get("unit", "unicode-codepoint")),
        )


@dataclass(frozen=True, slots=True)
class ProjectionNode:
    node_id: str
    category: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    span: SourceSpan | None = None
    native_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "category": self.category,
            "attributes": dict(self.attributes),
            "span": self.span.as_dict() if self.span else None,
            "native_path": self.native_path,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProjectionNode":
        raw_span = value.get("span")
        return cls(
            node_id=str(value["id"]),
            category=str(value["category"]),
            attributes=dict(value.get("attributes", {})),
            span=SourceSpan.from_dict(raw_span) if raw_span else None,
            native_path=value.get("native_path"),
        )


@dataclass(frozen=True, slots=True)
class ProjectionEdge:
    source_id: str
    target_id: str
    relation: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "relation": self.relation,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProjectionEdge":
        return cls(
            source_id=str(value["source"]),
            target_id=str(value["target"]),
            relation=str(value["relation"]),
            attributes=dict(value.get("attributes", {})),
        )


@dataclass(frozen=True, slots=True)
class Projection:
    projection_id: str
    family: str
    nodes: tuple[ProjectionNode, ...]
    edges: tuple[ProjectionEdge, ...]
    roots: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.projection_id,
            "family": self.family,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
            "roots": list(self.roots),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Projection":
        return cls(
            projection_id=str(value["id"]),
            family=str(value["family"]),
            nodes=tuple(ProjectionNode.from_dict(row) for row in value.get("nodes", ())),
            edges=tuple(ProjectionEdge.from_dict(row) for row in value.get("edges", ())),
            roots=tuple(str(item) for item in value.get("roots", ())),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class InterpretationHypothesis:
    hypothesis_id: str
    rank: int
    score: float | None
    semantic: Projection
    structural: Projection
    cross_links: tuple[ProjectionEdge, ...] = ()
    parser_attributes: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.hypothesis_id,
            "rank": self.rank,
            "score": self.score,
            "semantic": self.semantic.as_dict(),
            "structural": self.structural.as_dict(),
            "cross_links": [edge.as_dict() for edge in self.cross_links],
            "parser_attributes": dict(self.parser_attributes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InterpretationHypothesis":
        return cls(
            hypothesis_id=str(value["id"]),
            rank=int(value["rank"]),
            score=float(value["score"]) if value.get("score") is not None else None,
            semantic=Projection.from_dict(value["semantic"]),
            structural=Projection.from_dict(value["structural"]),
            cross_links=tuple(
                ProjectionEdge.from_dict(row) for row in value.get("cross_links", ())
            ),
            parser_attributes=dict(value.get("parser_attributes", {})),
        )


@dataclass(frozen=True, slots=True)
class InterpretationSegment:
    segment_index: int
    status: str
    hypotheses: tuple[InterpretationHypothesis, ...]
    span: SourceSpan | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "segment_index": self.segment_index,
            "status": self.status,
            "span": self.span.as_dict() if self.span else None,
            "hypotheses": [item.as_dict() for item in self.hypotheses],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InterpretationSegment":
        raw_span = value.get("span")
        return cls(
            segment_index=int(value["segment_index"]),
            status=str(value["status"]),
            span=SourceSpan.from_dict(raw_span) if raw_span else None,
            hypotheses=tuple(
                InterpretationHypothesis.from_dict(row)
                for row in value.get("hypotheses", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class AnalysisBundle:
    analysis_id: str
    evidence_id: str
    context_evidence_ids: tuple[str, ...]
    analyzer: str
    analyzer_version: str | None
    analyzer_configuration: Mapping[str, Any]
    input_text: str
    input_spans: tuple[SourceSpan, ...]
    raw_payload: bytes
    raw_content_type: str
    raw_sha256: str
    segments: tuple[InterpretationSegment, ...]
    request_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def hypotheses(self) -> tuple[InterpretationHypothesis, ...]:
        return tuple(item for segment in self.segments for item in segment.hypotheses)

    def as_dict(self) -> dict[str, Any]:
        """Serialize derived data; the raw payload is stored in its own BLOB."""
        return {
            "analysis_id": self.analysis_id,
            "evidence_id": self.evidence_id,
            "context_evidence_ids": list(self.context_evidence_ids),
            "analyzer": self.analyzer,
            "analyzer_version": self.analyzer_version,
            "analyzer_configuration": dict(self.analyzer_configuration),
            "input_text": self.input_text,
            "input_spans": [span.as_dict() for span in self.input_spans],
            "raw_content_type": self.raw_content_type,
            "raw_sha256": self.raw_sha256,
            "segments": [segment.as_dict() for segment in self.segments],
            "request_metadata": dict(self.request_metadata),
        }

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, raw_payload: bytes
    ) -> "AnalysisBundle":
        return cls(
            analysis_id=str(value["analysis_id"]),
            evidence_id=str(value["evidence_id"]),
            context_evidence_ids=tuple(value.get("context_evidence_ids", ())),
            analyzer=str(value["analyzer"]),
            analyzer_version=value.get("analyzer_version"),
            analyzer_configuration=dict(value.get("analyzer_configuration", {})),
            input_text=str(value["input_text"]),
            input_spans=tuple(
                SourceSpan.from_dict(row) for row in value.get("input_spans", ())
            ),
            raw_payload=raw_payload,
            raw_content_type=str(value["raw_content_type"]),
            raw_sha256=str(value["raw_sha256"]),
            segments=tuple(
                InterpretationSegment.from_dict(row)
                for row in value.get("segments", ())
            ),
            request_metadata=dict(value.get("request_metadata", {})),
        )
