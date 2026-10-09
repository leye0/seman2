"""Adapter: seman_parser -> AnalysisBundle (evidence level 2b).

Connects the symbolic parser to the immutable evidence stream so an
analysis is no longer ephemeral. Output uses the same
``InterpretationHypothesis`` contract as the TRIPS adapter: a structural
projection, a semantic projection, and cross-links between them.

No linguistic content is hardcoded here — categories, roles and types
all come from the parser's data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..evidence.model import EvidenceUnit
from .model import (
    AnalysisBundle,
    InterpretationHypothesis,
    InterpretationSegment,
    Projection,
    ProjectionEdge,
    ProjectionNode,
    SourceSpan,
)


class SemanParserError(RuntimeError):
    """Adapter boundary failure."""


@dataclass(frozen=True, slots=True)
class SemanParserResponse:
    body: bytes
    content_type: str
    status: int


def _node_id(prefix: str, counter: list[int]) -> str:
    counter[0] += 1
    return f"{prefix}{counter[0]}"


class SemanParserAdapter:
    """Project seman_parser output into the evidence interpretation schema."""

    def __init__(
        self,
        parser: Any,
        *,
        analyzer_key: str = "seman-parser",
        analyzer_version: str | None = None,
        configuration: Mapping[str, Any] | None = None,
    ) -> None:
        self.parser = parser
        self.analyzer_key = analyzer_key
        self.analyzer_version = analyzer_version or "0.1.0"
        self.configuration = dict(configuration or {})

    @property
    def key(self) -> str:
        """Interpreter key required by the runtime protocol."""
        return self.analyzer_key

    @classmethod
    def from_dir(cls, data_dir: str, **kwargs: Any) -> "SemanParserAdapter":
        import os
        import sys

        # seman_parser lives as a sibling package of src/seman2.
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        seman_path = os.path.join(root, "seman_parser")
        if seman_path not in sys.path:
            sys.path.insert(0, seman_path)
        from seman_parser.engine import Parser  # type: ignore

        return cls(Parser.from_dir(data_dir), **kwargs)

    def configuration_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.configuration, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def interpret(
        self,
        evidence: EvidenceUnit,
        context: Sequence[EvidenceUnit] = (),
        *,
        request_id: str | None = None,
    ) -> AnalysisBundle:
        """Run the parser and package every hypothesis as a projection pair.

        Signature matches the TRIPS adapter so the runtime can swap
        interpreters without special cases.
        """
        report = self.parser.parse(evidence.raw)
        raw_payload = json.dumps(report.as_dict(), ensure_ascii=False, default=str).encode("utf-8")
        raw_sha = hashlib.sha256(raw_payload).hexdigest()

        hypotheses = self._project_hypotheses(report, evidence)
        status = "parsed" if report.result.completed else "unparsed"
        segment = InterpretationSegment(
            segment_index=0,
            status=status,
            hypotheses=hypotheses,
            span=SourceSpan(start=0, end=len(evidence.raw)),
        )

        return AnalysisBundle(
            analysis_id=f"seman:{evidence.evidence_id}:{self.configuration_digest()[:12]}",
            evidence_id=evidence.evidence_id,
            context_evidence_ids=tuple(e.evidence_id for e in context),
            analyzer=self.analyzer_key,
            analyzer_version=self.analyzer_version,
            analyzer_configuration=dict(self.configuration),
            input_text=evidence.raw,
            input_spans=(SourceSpan(start=0, end=len(evidence.raw)),),
            raw_payload=raw_payload,
            raw_content_type="application/json",
            raw_sha256=raw_sha,
            segments=(segment,),
            request_metadata={
                "engine": "seman_parser",
                "request_id": request_id,
                "completed": report.result.completed,
                "stats": dict(report.result.stats or {}),
            },
        )

    # -- projections ---------------------------------------------------

    def _project_hypotheses(
        self,
        report: Any,
        evidence: EvidenceUnit,
    ) -> tuple[InterpretationHypothesis, ...]:
        alternatives = report.result.alternatives(limit=32)
        if not alternatives:
            # Keep the evidence link even when nothing parsed.
            empty = Projection(
                projection_id="empty",
                family="structural",
                nodes=(),
                edges=(),
            )
            return (
                InterpretationHypothesis(
                    hypothesis_id=f"seman-{evidence.evidence_id[-12:]}-h0",
                    rank=0,
                    score=None,
                    semantic=empty,
                    structural=empty,
                    cross_links=(),
                    parser_attributes={"completed": False},
                ),
            )

        out: list[InterpretationHypothesis] = []
        prefix = evidence.evidence_id[-12:]
        for rank, item in enumerate(alternatives):
            counter = [0]
            structural = self._structural_projection(item, counter)
            semantic = self._semantic_projection(item, counter, evidence)
            links = self._cross_links(item, structural, semantic)
            out.append(
                InterpretationHypothesis(
                    hypothesis_id=f"seman-{prefix}-h{rank}",
                    rank=rank,
                    score=float(item.score),
                    semantic=semantic,
                    structural=structural,
                    cross_links=links,
                    parser_attributes={
                        "rule_id": item.rule_id,
                        "category": item.category,
                        "span": [item.start, item.end],
                        "features": item.features.as_dict() if item.features else {},
                        "provenance": item.provenance.as_dict() if item.provenance else {},
                    },
                )
            )
        return tuple(out)

    def _structural_projection(self, item: Any, counter: list[int]) -> Projection:
        nodes: list[ProjectionNode] = []
        edges: list[ProjectionEdge] = []

        def walk(node: Any, parent_id: str | None) -> str:
            nid = _node_id("t", counter)
            detail = node.provenance.detail if node.provenance else {}
            nodes.append(
                ProjectionNode(
                    node_id=nid,
                    category=node.category,
                    attributes={
                        "rule_id": node.rule_id,
                        "score": node.score,
                        "features": node.features.as_dict() if node.features else {},
                        "surface": detail.get("surface"),
                        "lemma": detail.get("lemma"),
                    },
                    span=SourceSpan(start=node.start, end=node.end),
                )
            )
            if parent_id is not None:
                edges.append(
                    ProjectionEdge(
                        source_id=parent_id,
                        target_id=nid,
                        relation="child",
                    )
                )
            for child in node.children:
                walk(child, nid)
            return nid

        root_id = walk(item, None)
        return Projection(
            projection_id="structural",
            family="structural",
            nodes=tuple(nodes),
            edges=tuple(edges),
            roots=(root_id,),
        )

    def _semantic_projection(
        self,
        item: Any,
        counter: list[int],
        evidence: EvidenceUnit,
    ) -> Projection:
        graph = item.semantic.graph
        nodes: list[ProjectionNode] = []
        edges: list[ProjectionEdge] = []
        id_map: dict[str, str] = {}

        for orig_id, node in graph.nodes.items():
            nid = _node_id("s", counter)
            id_map[orig_id] = nid
            span = None
            if node.span:
                span = SourceSpan(start=node.span[0], end=node.span[1])
            nodes.append(
                ProjectionNode(
                    node_id=nid,
                    category=node.kind,
                    attributes={
                        "type": node.type_name,
                        "surface": node.surface,
                        **dict(node.attributes or {}),
                    },
                    span=span,
                    native_path=f"evidence:{evidence.evidence_id}",
                )
            )

        for edge in graph.relations:
            source = id_map.get(edge.source, edge.source)
            target = id_map.get(edge.target, edge.target)
            edges.append(
                ProjectionEdge(
                    source_id=source,
                    target_id=target,
                    relation=edge.relation,
                    attributes=dict(edge.attributes or {}),
                )
            )

        return Projection(
            projection_id="semantic",
            family="semantic",
            nodes=tuple(nodes),
            edges=tuple(edges),
            roots=tuple(id_map.get(v, v) for v in item.semantic.handles.values()),
            metadata={"handles": dict(item.semantic.handles)},
        )

    def _cross_links(
        self,
        item: Any,
        structural: Projection,
        semantic: Projection,
    ) -> tuple[ProjectionEdge, ...]:
        """Link structural nodes to semantic nodes via shared spans."""
        links: list[ProjectionEdge] = []
        by_span: dict[tuple[int, int], list[str]] = {}
        for node in semantic.nodes:
            if node.span is not None:
                by_span.setdefault((node.span.start, node.span.end), []).append(node.node_id)

        for tnode in structural.nodes:
            if tnode.span is None:
                continue
            for sid in by_span.get((tnode.span.start, tnode.span.end), ()):
                links.append(
                    ProjectionEdge(
                        source_id=tnode.node_id,
                        target_id=sid,
                        relation="aligns",
                        attributes={"basis": "span"},
                    )
                )
        return tuple(links)
