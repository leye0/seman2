"""Cheap, non-syntactic preflight signals before Parser.parse.

This is NOT a second recognizer, a grammar checker, or an acceptance decision.
The surface-only pass never loads WordNet, builds a lexical lattice, or
enumerates a forest. An *already available* lattice optionally contributes
candidate-local morphological observations without proving dependency links.

Route hints are research lanes, not decisions to skip or change parsing.
They are deliberately not enabled in the canonical 500-case parse.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .features import Atom
from .segmentation import LexicalLattice, Token, tokenize

SCHEMA = "seman2-fast-preflight-v1"
LONG_SENTENCE_TOKENS = 30  # Descriptive flag, NOT a fitted runtime cutoff.
FINITE_CATEGORIES = frozenset({"V", "COPULA", "AUX-BE", "AUX", "HAVE", "MODAL"})


@dataclass(frozen=True)
class FastPreflight:
    """A small JSON-compatible observation, with explicitly limited claims."""

    analysis_text: str
    signals: tuple[str, ...]
    lane: str
    evidence: tuple[dict[str, Any], ...]
    token_count: int
    phase: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "phase": self.phase,
            "analysis_text": self.analysis_text,
            "token_count": self.token_count,
            "signals": list(self.signals),
            "lane": self.lane,
            "evidence": list(self.evidence),
            "can_skip_full_parse": False,
            "grammatical_fault_established": False,
            "failure_cause_established": False,
            "exhaustive": False,
            "status": "preparse_hypothesis_only",
        }


def _has_quotation(text: str, prefix: str, suffix: str) -> bool:
    # ASCII apostrophes inside contractions are not quotation delimiters.
    # Curly right-single marks can be apostrophes; only left/open marks
    # are independently considered surface quote evidence.
    return any(mark in text or mark in prefix or mark in suffix
               for mark in ('"', "“", "”", "‘"))


def _atom(candidate: Any, key: str) -> str | None:
    value = candidate.features.get(key)
    return value.name if isinstance(value, Atom) else None


def _local_candidate_observations(
    tokens: Sequence[Token], lattice: LexicalLattice,
) -> list[dict[str, Any]]:
    """Look for *candidate-level* incompatibility of adjacent exact spans.

    No shallow sequence is sufficient to prove a syntactic subject-predicate
    relationship. Even unanimous lexical incompatibility is only a hypothesis.
    All finite inflection alternatives must be inspected, and missing/unknown
    features cannot be treated as disagreements.
    """
    exact: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for candidate in lattice.candidates:
        exact[(candidate.span_start, candidate.span_end)].append(candidate)
    evidence = []
    for left, right in zip(tokens, tokens[1:]):
        # An explicit punctuation gap or multiword candidate does not prove
        # a direct relation. Only adjacent word-shaped token spans qualify.
        if not (left.text.isalpha() and right.text.isalpha()):
            continue
        subjects = [
            c for c in exact.get((left.start, left.end), ())
            if c.category == "PRONOUN"
            and any(_atom(c, name) is not None for name in ("person", "number"))
        ]
        finites = [
            c for c in exact.get((right.start, right.end), ())
            if c.category in FINITE_CATEGORIES and _atom(c, "vform") == "finite"
        ]
        if not subjects or not finites:
            continue
        comparisons = []
        for subject in subjects:
            for finite in finites:
                conflicts = []
                for feature in ("number", "person"):
                    x = _atom(subject, feature)
                    y = _atom(finite, feature)
                    if x is not None and y is not None and x != y:
                        conflicts.append({
                            "feature": feature, "subject": x, "predicate": y,
                        })
                comparisons.append(conflicts)
        if comparisons and all(comparisons):
            # Keep this label distinct from the proven disagreement of an
            # actual selected-tree dependency.
            evidence.append({
                "kind": "adjacent_candidate_agreement_hypothesis",
                "subject_span": [left.start, left.end],
                "predicate_span": [right.start, right.end],
                "subject_text": left.text,
                "predicate_text": right.text,
                "candidate_pairs_examined": len(comparisons),
                "direct_atom_conflicts": comparisons[0],
                "dependency_proven": False,
                "ambiguity_exhausted": False,
            })
            if len(evidence) == 8:
                break
    return evidence


def fast_preflight(
    analysis_text: str,
    *,
    preceding_semicolon_part: bool = False,
    transferred_prefix: str = "",
    transferred_suffix: str = "",
    lattice: LexicalLattice | None = None,
) -> FastPreflight:
    """Emit fast routing *hints* without running or replacing Parser.parse.

    The caller must supply genuine source provenance for the semicolon flag
    and transferred delimiters, never guess them from a flattened corpus.
    If lattice is supplied, it must be the identical analyzed text and the
    exact lattice already prepared by the normal parser; building it here
    would defeat the constant-cheap surface stage.
    """
    if lattice is not None and lattice.text != analysis_text:
        raise ValueError("Preflight lattice must match the exact analyzed text")
    tokens = lattice.tokens if lattice is not None else tokenize(analysis_text)
    signals: set[str] = set()
    evidence: list[dict[str, Any]] = []
    if preceding_semicolon_part:
        signals.add("source_semicolon_continuation")
        evidence.append({
            "kind": "source_semicolon_continuation",
            "proof_scope": "source_adjacency_only_not_fragment_grammar",
        })
    # A quote delimiter alone is extremely common in grammatical dialogue.
    # Retain it as a feature, not as a reason to divert the normal parser.
    if _has_quotation(analysis_text, transferred_prefix, transferred_suffix):
        signals.add("dialogue_or_quote_surface")
        evidence.append({
            "kind": "dialogue_or_quote_surface",
            "transferred_quote_present": bool(transferred_prefix or transferred_suffix),
            "proof_scope": "surface_only_not_dialogue_parse",
        })
    if len(tokens) >= LONG_SENTENCE_TOKENS:
        signals.add("length_attention")
        evidence.append({
            "kind": "length_attention",
            "observed_tokens": len(tokens),
            "descriptive_threshold": LONG_SENTENCE_TOKENS,
            "runtime_causality_proven": False,
        })
    comma_count = sum(token.text == "," for token in tokens)
    if comma_count >= 3:
        signals.add("many_comma_boundaries")
        evidence.append({
            "kind": "many_comma_boundaries",
            "count": comma_count,
            "syntax_type_proven": False,
        })
    if lattice is not None:
        candidate_observations = _local_candidate_observations(tokens, lattice)
        if candidate_observations:
            signals.add("adjacent_candidate_agreement_hypothesis")
            evidence.extend(candidate_observations)
    if "adjacent_candidate_agreement_hypothesis" in signals:
        lane = "candidate_morphology_review"
    elif "source_semicolon_continuation" in signals:
        lane = "context_review"
    elif "length_attention" in signals or "many_comma_boundaries" in signals:
        lane = "complexity_attention"
    else:
        lane = "no_early_signal"
    return FastPreflight(
        analysis_text=analysis_text,
        signals=tuple(sorted(signals)),
        lane=lane,
        evidence=tuple(evidence),
        token_count=len(tokens),
        phase="existing_lattice" if lattice is not None else "surface_only",
    )
