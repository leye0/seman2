"""Contextual, append-only reranking proposals."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..interpretation.model import AnalysisBundle
from .ranking import structural_similarity


def revision_proposals(
    current: AnalysisBundle,
    prior: Sequence[AnalysisBundle],
) -> tuple[dict[str, Any], ...]:
    """Compare neighboring analyses without assigning human semantic labels."""
    current_payloads = [
        hypothesis.semantic.as_dict() for hypothesis in current.hypotheses
    ]
    if not current_payloads:
        return ()
    proposals: list[dict[str, Any]] = []
    for bundle in prior:
        for hypothesis in bundle.hypotheses:
            similarities = [
                structural_similarity(hypothesis.semantic.as_dict(), payload)
                for payload in current_payloads
            ]
            fit = max(similarities, default=0.0)
            initial = hypothesis.score if hypothesis.score is not None else 0.0
            score = 0.8 * float(initial) + 0.2 * fit
            proposals.append(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "evidence_id": current.evidence_id,
                    "score": score,
                    "operation": "contextual-rerank",
                    "derivation": {
                        "algorithm": "projection-neighborhood-similarity",
                        "version": "1",
                        "current_analysis_id": current.analysis_id,
                        "prior_analysis_id": bundle.analysis_id,
                        "fit": fit,
                    },
                }
            )
    return tuple(proposals)
