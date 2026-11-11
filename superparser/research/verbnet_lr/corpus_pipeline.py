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
    if mode is CorpusParseMode.HISTORICAL_REFERENCE:
        return PreparedCorpusInput(
            analysis_text=reference,
            reference_text=reference,
            source_text=source,
            synthetic_prefix=case.get("synthetic_prefix", ""),
            synthetic_suffix=case.get("synthetic_suffix", ""),
            synthetic_terminal=bool(case.get("synthetic_terminal", False)),
            mode=mode,
            structural_constituents=structure,
            structural_status=case.get("structural_status", "not_supplied"),
            quotation_status=case.get("quotation_status", "not_supplied"),
        )
    return PreparedCorpusInput(
        analysis_text=balanced,
        reference_text=reference,
        source_text=source,
        synthetic_prefix=prefix,
        synthetic_suffix=suffix,
        synthetic_terminal=bool(case["balanced_synthetic_terminal"]),
        mode=mode,
        structural_constituents=structure,
        structural_status=case.get("structural_status", "not_supplied"),
        quotation_status=case.get("quotation_status", "not_supplied"),
    )


def parse_corpus_case(
    parser: Any,
    case: Mapping[str, Any],
    *,
    mode: CorpusParseMode = CorpusParseMode.QUOTE_BALANCED,
    max_items: int | None = None,
    kbest_work_limit: int | None = None,
    diagnostic_k: int | None = None,
    allow_marked_deviations: bool = False,
    rejection_trace_limit: int = 0,
    preflight_diagnostics: bool = False,
):
    """One canonical way to parse a novel case, including quotation context.

    Returns (PreparedCorpusInput, LexicalLattice, ParseResult). A new caller
    automatically analyzes the balanced text. Explicit historical mode keeps
    legacy 500-case measurements comparable without changing their SHA.
    """
    prepared = prepare_corpus_input(case, mode=mode)
    options = {"max_items": max_items, "kbest_work_limit": kbest_work_limit}
    if diagnostic_k is not None:
        if not 1 <= diagnostic_k <= 64:
            raise ValueError("diagnostic_k must be 1..64 in corpus research")
        options["diagnostic_k"] = diagnostic_k
    if allow_marked_deviations:
        options["allow_marked_deviations"] = True
    if rejection_trace_limit:
        options["rejection_trace_limit"] = rejection_trace_limit
    if preflight_diagnostics:
        options["preflight_diagnostics"] = True
    report = parser.parse(prepared.analysis_text, **options)
    # The diagnostic sees EXACTLY the lexical lattice used by the parser,
    # not a separately rebuilt or differently configured approximation.
    lattice = report.lattice
    if lattice is None:
        raise AssertionError("Parser.parse did not expose its lexical lattice")
    if lattice.text != prepared.analysis_text or report.result.text != prepared.analysis_text:
        raise AssertionError(
            "Public parser changed corpus analysis text: quote context "
            "and source spans must never be silently stripped or replaced"
        )
    return prepared, lattice, report.result
