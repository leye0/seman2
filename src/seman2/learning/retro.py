"""Retro loop: feed learned complex tree segments back into analyses.

After consolidation produces recurring DOP fragments, those segments are
matched against stored structural trees. Matches are new data: bindings,
supports and alignments are appended, never merged into the native analysis.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .fragments import (
    FragmentMatch,
    FragmentNode,
    fragment_signature,
    match_fragment,
    parse_bracketed,
)
from .model import Derivation
from .structures import digest


def match_fragment_on_tree(
    fragment_source: str,
    tree_source: str,
    sentence: Sequence[str],
) -> tuple[FragmentMatch, ...]:
    """Locate every occurrence of a disco-dop fragment in one host tree."""
    fragment = parse_bracketed(fragment_source)
    host = parse_bracketed(tree_source, sentence=sentence)
    return match_fragment(fragment, host, sentence=sentence)


def match_fragments_on_tree(
    fragment_sources: Sequence[str],
    tree_source: str,
    sentence: Sequence[str],
) -> tuple[tuple[str, FragmentMatch], ...]:
    """Match many fragments against one host tree, parsing the host only once."""
    host = parse_bracketed(tree_source, sentence=sentence)
    found: list[tuple[str, FragmentMatch]] = []
    for source in fragment_sources:
        try:
            fragment = parse_bracketed(source)
        except ValueError:
            continue
        for match in match_fragment(fragment, host, sentence=sentence):
            found.append((source, match))
    return tuple(found)


def load_fragment_nodes(
    fragment_sources: Iterable[str],
) -> tuple[tuple[str, FragmentNode], ...]:
    parsed: list[tuple[str, FragmentNode]] = []
    for source in fragment_sources:
        parsed.append((source, parse_bracketed(source)))
    return tuple(parsed)


def match_payload(
    *,
    fragment_id: str,
    fragment_source: str,
    tree_structure_id: str,
    analysis_id: str | None,
    hypothesis_id: str | None,
    match: FragmentMatch,
) -> dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "fragment": fragment_source,
        "tree_structure_id": tree_structure_id,
        "analysis_id": analysis_id,
        "hypothesis_id": hypothesis_id,
        "root_path": match.root_path,
        "bindings": dict(match.bindings),
        "covered_leaves": list(match.covered_leaves),
        "host_bracketed": match.bracketed,
    }


def match_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fragment_id": payload["fragment_id"],
        "tree_structure_id": payload["tree_structure_id"],
        "root_path": payload["root_path"],
        "bindings": dict(payload["bindings"]),
    }


def binding_rows(
    *,
    fragment_id: str,
    tree_structure_id: str,
    match: FragmentMatch,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    """One binding record per frontier slot filled by the match."""
    rows: list[tuple[str, dict[str, Any]]] = []
    for slot, value in sorted(match.bindings.items()):
        binding_id = digest(
            "fragment-binding",
            {
                "fragment_id": fragment_id,
                "tree_structure_id": tree_structure_id,
                "slot": slot,
                "value": value,
            },
        )
        rows.append(
            (
                binding_id,
                {
                    "slot": slot,
                    "value": value,
                    "root_path": match.root_path,
                    "source": "fragment-match",
                },
            )
        )
    return tuple(rows)


def coverage_weights(
    matches: Sequence[tuple[str, Mapping[str, Any]]],
) -> dict[str, float]:
    """Aggregate fragment-match support per hypothesis without semantic labels."""
    weights: dict[str, float] = {}
    for _, payload in matches:
        key = str(payload.get("hypothesis_id") or payload.get("analysis_id") or "")
        if not key:
            continue
        weights[key] = weights.get(key, 0.0) + 1.0
    return weights


def coverage_revision_proposals(
    *,
    evidence_id: str,
    weights: Mapping[str, float],
    prior_scores: Mapping[str, float],
    algorithm: str = "fragment-coverage",
) -> tuple[dict[str, Any], ...]:
    """Rerank hypotheses by known complex-segment coverage.

    Scores stay append-only proposals; the native analysis is untouched.
    """
    if not weights:
        return ()
    maximum = max(weights.values()) or 1.0
    proposals: list[dict[str, Any]] = []
    for hypothesis_id, weight in sorted(weights.items()):
        coverage = weight / maximum
        initial = float(prior_scores.get(hypothesis_id, 0.0))
        score = 0.7 * initial + 0.3 * coverage
        proposals.append(
            {
                "hypothesis_id": hypothesis_id,
                "evidence_id": evidence_id,
                "score": score,
                "operation": "fragment-coverage-rerank",
                "derivation": {
                    "algorithm": algorithm,
                    "version": "1",
                    "coverage": coverage,
                    "match_count": weight,
                    "prior_score": initial,
                },
            }
        )
    return tuple(proposals)


def retro_derivation(
    *,
    algorithm: str = "dop-fragment-retro-match",
    parameters: Mapping[str, Any] | None = None,
    inputs: Sequence[str] = (),
) -> Derivation:
    return Derivation(
        algorithm=algorithm,
        version="1",
        parameters=dict(parameters or {}),
        inputs=tuple(inputs),
    )


def fragment_sources_from_payloads(
    payloads: Iterable[Mapping[str, Any]],
) -> tuple[str, ...]:
    sources: list[str] = []
    for payload in payloads:
        source = payload.get("fragment")
        if isinstance(source, str) and source:
            sources.append(source)
    return tuple(sources)
