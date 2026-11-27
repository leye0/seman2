"""Mandatory corpus-case parsing gateway.

Novel extraction already balances quotes across semicolons and sentence
boundaries. This module consumes its recorded output; NEVER invent or repair
quotation marks here. Corpus analyses must not pass case["text"] directly to
Parser, because that skips intentional quotation context transfer.

The 500-case reference is deliberately immutable. Historical text can still
be parsed for paired research, but only by EXPLICITLY requesting that mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Any



class CorpusParseMode(str, Enum):
    QUOTE_BALANCED = "quote_balanced"
    HISTORICAL_REFERENCE = "historical_reference"


@dataclass(frozen=True, slots=True)
class PreparedCorpusInput:
    """Immutable analysis text and its independently preserved provenance."""
    analysis_text: str
    reference_text: str
    source_text: str
    synthetic_prefix: str
    synthetic_suffix: str
    synthetic_terminal: bool
    mode: CorpusParseMode
    structural_constituents: tuple[Mapping[str, Any], ...] = ()
    structural_status: str = "not_supplied"
    quotation_status: str = "not_supplied"
    source_paragraph_index: int | None = None
    source_paragraph_span: tuple[int, int] | None = None
    cleaned_book_span: tuple[int, int] | None = None
    discourse_function: str = "not_supplied"
    discourse_relation: str = "not_supplied"
    discourse_evidence: str = "not_supplied"
    discourse_governor_core_span: tuple[int, int] | None = None
    discourse_governor_paragraph_index: int | None = None

    def source_component(self, component_id: str) -> str:
        """Return exact source text for a documented grammatical function."""
        for part in self.structural_constituents:
            if part["id"] == component_id:
                return self.source_text[part["start"]:part["end"]]
        raise KeyError(component_id)

    def reference_span(self, analysis_start: int, analysis_end: int) -> tuple[int, int] | None:
        """Map a non-synthetic analysis span to the frozen reference exactly.

        A span inside a transferred quote has no original character position.
        Refuse mappings when the prepared core differs from the reference;
        never guess original offsets from a normalized or altered string.
        """
        core_start = len(self.synthetic_prefix)
        core_end = len(self.analysis_text) - len(self.synthetic_suffix)
        if not (core_start <= analysis_start < analysis_end <= core_end):
            return None
        if self.analysis_text[core_start:core_end] != self.reference_text:
            return None
        return (analysis_start - core_start, analysis_end - core_start)


def prepare_corpus_input(
    case: Mapping[str, Any],
    *,
    mode: CorpusParseMode = CorpusParseMode.QUOTE_BALANCED,
) -> PreparedCorpusInput:
    """Select prepared quote-balanced text by default, never silently raw.

    Only the extractor in gutenberg_novels may synthesize delimiters. The
    historical-reference mode is for the existing SHA-pinned benchmark.
    """
    if not isinstance(mode, CorpusParseMode):
        raise ValueError("Use an explicit CorpusParseMode enum, never a boolean")
    required = ("text", "source_text", "balanced_analysis_text",
                "balanced_synthetic_prefix", "balanced_synthetic_suffix",
                "balanced_synthetic_terminal")
    missing = [key for key in required if key not in case]
    if missing:
        raise ValueError(
            "Corpus case lacks quote-transfer provenance " + repr(missing)
            + "; create it with gutenberg_novels.extract(), not raw strings"
        )
    reference = case["text"]
    source = case["source_text"]
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("Empty/invalid fixed-cohort reference")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Missing original novel source span")
    balanced = case["balanced_analysis_text"]
    prefix = case["balanced_synthetic_prefix"]
    suffix = case["balanced_synthetic_suffix"]
    if not all(isinstance(piece, str) for piece in (balanced, prefix, suffix)):
        raise ValueError("Quote-transfer fields must be strings")
    if not balanced.startswith(prefix) or not balanced.endswith(suffix):
        raise ValueError("Quote-transfer prefix/suffix do not match analysis text")
    structure = tuple(case.get("structural_constituents", ()))
    if structure:
        if any(not isinstance(part, Mapping) for part in structure):
            raise ValueError("Malformed structural constituent")
        identifiers = [part.get("id") for part in structure]
        if len(set(identifiers)) != len(identifiers) or "u0" not in identifiers:
            raise ValueError("Structural constituent IDs must be unique and rooted")
        for part in structure:
            if not isinstance(part, Mapping):
                raise ValueError("Malformed structural constituent")
            a, b = part.get("start"), part.get("end")
            if not isinstance(a, int) or not isinstance(b, int) or not (0 <= a < b <= len(source)):
                raise ValueError("Structural source span lies outside the actual text")
            if part.get("governor") is not None and part["governor"] not in identifiers:
                raise ValueError("Structural governor cannot point outside this source unit")
            if not part.get("function") or not part.get("relation"):
                raise ValueError("Structural functions and relations are required")
        # Every provisional constituent, including split speech resumption,
        # must have one acyclic path to the actual source utterance root.
        # Governor edges are discourse dependencies, NOT necessarily spatial
        # containment (two non-overlapping speech parts may share a turn).
        by_id = {part["id"]: part for part in structure}
        if by_id["u0"].get("governor") is not None:
            raise ValueError("The source utterance root cannot have a governor")
        for identifier in identifiers:
            seen = set()
            parent = identifier
            while parent != "u0":
                if parent in seen:
                    raise ValueError("Cycle in structural governor references")
                seen.add(parent)
                governor = by_id[parent].get("governor")
                if governor is None:
                    raise ValueError("Unrooted structural governor chain")
                parent = governor
        if reference != source or balanced != source or prefix or suffix:
            raise ValueError("A structured unit cannot include synthetic text")
        if case.get("quotation_status") != "balanced":
            raise ValueError("Unresolved quotation cannot enter complete grammar parsing")
        if case.get("structural_status") != "provisional_complete_utterance":
            raise ValueError("Only structurally coherent source utterances may be parsed")
    paragraph_span = case.get("structural_source_span")
    book_span = case.get("structural_core_source_span")
    paragraph_index = case.get("structural_paragraph_index")
    if structure:
        if not (
            isinstance(paragraph_index, int) and paragraph_index >= 0
            and isinstance(paragraph_span, (list, tuple))
            and len(paragraph_span) == 2
            and all(isinstance(v, int) for v in paragraph_span)
            and 0 <= paragraph_span[0] < paragraph_span[1]
            and paragraph_span[1]-paragraph_span[0] == len(source)
            and isinstance(book_span, (list, tuple))
            and len(book_span) == 2
            and all(isinstance(v, int) for v in book_span)
            and 0 <= book_span[0] < book_span[1]
        ):
            raise ValueError("Source paragraph and cleaned-book offsets required")
    discourse_governor = case.get("discourse_governor_core_span")
    discourse_paragraph = case.get("discourse_governor_paragraph_index")
    if discourse_governor is not None:
        if not (isinstance(discourse_governor, (tuple, list))
                and len(discourse_governor) == 2
                and all(isinstance(i, int) for i in discourse_governor)
                and 0 <= discourse_governor[0] < discourse_governor[1]
                and book_span is not None
                and discourse_governor[1] <= book_span[0]
                and isinstance(discourse_paragraph, int)
                and discourse_paragraph <= paragraph_index):
            raise ValueError("Discourse governor must precede its exact source span")
    if structure and case.get("discourse_function", "") in (
            "elliptical_supplement", "reported_speech_continuation",
            "documentary_navigation_notation", "documentary_postscript"):
        raise ValueError("Non-prose or context-dependent text cannot enter standalone parsing")
    common = {
        "structural_constituents": structure,
        "structural_status": case.get("structural_status", "not_supplied"),
        "quotation_status": case.get("quotation_status", "not_supplied"),
        "source_paragraph_index": paragraph_index,
        "source_paragraph_span": tuple(paragraph_span) if paragraph_span else None,
        "cleaned_book_span": tuple(book_span) if book_span else None,
        "discourse_function": case.get("discourse_function", "not_supplied"),
        "discourse_relation": case.get("discourse_relation", "not_supplied"),
        "discourse_evidence": case.get("discourse_evidence", "not_supplied"),
        "discourse_governor_core_span": tuple(discourse_governor)
                                      if discourse_governor else None,
        "discourse_governor_paragraph_index": discourse_paragraph,
    }
    if mode is CorpusParseMode.HISTORICAL_REFERENCE:
        return PreparedCorpusInput(
            analysis_text=reference,
            reference_text=reference,
            source_text=source,
            synthetic_prefix=case.get("synthetic_prefix", ""),
            synthetic_suffix=case.get("synthetic_suffix", ""),
            synthetic_terminal=bool(case.get("synthetic_terminal", False)),
            mode=mode,
            **common,
        )
    return PreparedCorpusInput(
        analysis_text=balanced,
        reference_text=reference,
        source_text=source,
        synthetic_prefix=prefix,
        synthetic_suffix=suffix,
        synthetic_terminal=bool(case["balanced_synthetic_terminal"]),
        mode=mode,
        **common,
    )

def parse_corpus_case(parser, case, *, parse_components=True):
    """Validate original source and invoke ERG; no competing grammar."""
    prepared = prepare_corpus_input(case)
    return prepared, parser.parse_unit(prepared.analysis_text,
        prepared.structural_constituents, parse_components=parse_components)
