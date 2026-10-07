"""Generic proposals between the two projections of one analysis."""

from __future__ import annotations

from typing import Any

from ..interpretation.model import InterpretationHypothesis, ProjectionNode
from .structures import digest


def _span_overlap(left: ProjectionNode, right: ProjectionNode) -> tuple[int, int] | None:
    if left.span is None or right.span is None:
        return None
    start = max(left.span.start, right.span.start)
    end = min(left.span.end, right.span.end)
    return (start, end) if start < end else None


def propose_alignments(hypothesis: InterpretationHypothesis) -> tuple[dict[str, Any], ...]:
    proposals: list[dict[str, Any]] = []
    for structural in hypothesis.structural.nodes:
        for semantic in hypothesis.semantic.nodes:
            overlap = _span_overlap(structural, semantic)
            if overlap is None:
                continue
            assert structural.span is not None and semantic.span is not None
            union = max(structural.span.end, semantic.span.end) - min(
                structural.span.start, semantic.span.start
            )
            intersection = overlap[1] - overlap[0]
            coverage = intersection / union if union else 1.0
            payload = {
                "structural_node": structural.node_id,
                "semantic_node": semantic.node_id,
                "span_overlap": {"start": overlap[0], "end": overlap[1]},
                "coverage": coverage,
                "structural_path": structural.native_path,
                "semantic_path": semantic.native_path,
            }
            proposals.append(
                {
                    "alignment_id": digest("align", payload),
                    "payload": payload,
                    "score": coverage,
                }
            )
    return tuple(sorted(proposals, key=lambda row: (-row["score"], row["alignment_id"])))
