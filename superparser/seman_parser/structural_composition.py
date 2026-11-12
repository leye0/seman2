"""Conservative, *grammatically validated* composition of quoted sentences.

Accept only an original single quotation enclosing 2 or 3 distinct, overtly
punctuated finite subject-predicate clauses. The typed source spans select
subexpressions; the *existing* vector grammar verifies each subexpression.
A separate declarative source-quote grammar then unifies the verified CLAUSE
interfaces with real quote and terminal punctuation. No missing word, quote
delimiter, finite predicate, or semantic role is invented.

This route is deliberately narrow. Interrupted speech with a reporting tag,
embedded quotations, questions, vocatives and contextual ellipses still use
the full dialogue grammar until their own compositional licensing exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .chart import ParseResult
from .dialogue import quotation_boundaries
from .features import FeatureStructure
from .grammar import load_grammar
from .segmentation import LexicalCandidate, LexicalLattice
from .vector_chart import SegmentInterface, VectorGrammar
from .structural_units import skeleton


@dataclass(frozen=True, slots=True)
class _ClauseSpan:
    start: int
    end: int
    stop: int


class QuotedSentenceComposer:
    """Compiled grammar assembly with real independently parsed children."""

    def __init__(self, rules_path: str | Path) -> None:
        self._vector = VectorGrammar(
            load_grammar(rules_path),
            preserve_quote_delimiters=True,
        )

    def _compose_quoted_modal_zero_clausal_complement(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Source-scoped quoted finite modal selecting an overt finite clause.

        The unrestricted V[base,clausal]+CLAUSE production was explicitly
        rejected: it saturated unrelated already-correct literary quotes.
        This pathway instead requires the *actual* printed contraction,
        lexical modal and valency edges, and independently ranked NP and
        subordinate CLAUSE parses before composing declarative interfaces.
        """
        if (not components
                or not any(c.get("function") == "direct_speech"
                           and (c.get("start"), c.get("end")) ==
                           (0, len(text)) for c in components)
                or any(c.get("function") in (
                    "embedded_quotation", "reporting_clause",
                    "split_direct_speech_turn",
                ) for c in components)):
            return None
        marks = quotation_boundaries(text)
        if len(marks) != 2 or (
            marks[0].start, marks[0].end, marks[0].side,
            marks[1].start, marks[1].end, marks[1].side,
        ) != (0, 1, "open", len(text)-1, len(text), "close"):
            return None
        # A productive spelling-level gate, NOT an attested-book string.
        # Group 2 is the actual apostrophe+ll with its original source span.
        match = re.fullmatch(
            r"([A-Za-z]+)(['’]ll)\s+([A-Za-z]+)\s+"
            r'''([A-Za-z][^'’"“”‘’!?]*?)([.!?])''',
            text[1:-1],
        )
        if match is None:
            return None
        subject = tuple(1+v for v in match.span(1))
        modal = tuple(1+v for v in match.span(2))
        verb = tuple(1+v for v in match.span(3))
        complement = tuple(1+v for v in match.span(4))
        stop = 1+match.start(5)
        if (not all(text[a:b] and text[a:b] == text[a:b].strip()
                    for a, b in (subject, modal, verb, complement))
                or stop != len(text)-2
                or not skeleton(text[slice(*complement)]).finite_predicate_candidate):
            return None
        def lexical(category: str, span: tuple[int, int],
                    needed: Mapping[str, str]) -> LexicalCandidate | None:
            for candidate in original_lattice.candidates:
                if (candidate.category == category
                        and (candidate.span_start, candidate.span_end) == span
                        and all(candidate.features.as_dict().get(k) == v
                                for k, v in needed.items())):
                    return candidate
            return None
        modal_edge = lexical("MODAL", modal, {"vform": "finite"})
        verb_edge = lexical("V", verb, {
            "vform": "base", "subcat": "clausal",
        })
        if modal_edge is None or verb_edge is None:
            return None
        total_items = parser.max_items if max_items is None else max_items
        total_work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1200 or total_work < 1200:
            return None
        piece_items, piece_work = total_items // 3, total_work // 3
        proofs: list[ParseResult] = []
        candidates: list[LexicalCandidate] = [modal_edge, verb_edge]
        for category, (a, b) in (("NP", subject), ("CLAUSE", complement)):
            fragment = text[a:b]
            if category == "CLAUSE":
                proof = parser._parse_vector_text(
                    fragment, max_items=piece_items,
                    kbest_work_limit=piece_work,
                    diagnostic_k=diagnostic_k, beam=beam,
                )
            else:
                proof = parser._vector_grammar.parse_lattice(
                    parser._lattice_for_text(fragment),
                    goal_category=category,
                    max_items=piece_items, kbest_work_limit=piece_work,
                    diagnostic_k=diagnostic_k,
                    beam=parser.beam if beam is None else beam,
                )
            selected = proof.best()
            if not proof.completed or selected is None:
                return None
            if category == "NP":
                if (selected.category != "NP"
                        or selected.features.as_dict().get("pronominal")
                           != "true"
                        or selected.rule_id != "np_indef_pron"):
                    return None
            else:
                if (selected.category != "CLAUSE" or len(selected.children) < 2
                        or selected.children[0].category != "NP"
                        or selected.children[1].category not in
                           {"VP", "VP-NP"}):
                    return None
            proofs.append(proof)
            candidates.append(LexicalCandidate(
                span_start=a, span_end=b, surface=fragment,
                lemma=f"<proved-{category.lower()}>",
                category=category, features=selected.features,
                score=selected.score, source="source-scoped-clausal-proof",
                provenance={"original_source_span":[a,b],
                            "selected_rule_id":selected.rule_id},
                interface=SegmentInterface(proof, a, a, b),
            ))
        for where, category in (
            (0, "OPEN-QUOTE"), (stop, "SPEECH-STOP"),
            (len(text)-1, "CLOSE-QUOTE"),
        ):
            candidates.append(LexicalCandidate(
                span_start=where, span_end=where+1,
                surface=text[where], lemma=text[where],
                category=category, features=FeatureStructure.empty(),
                source="overt-source-punctuation", score=0,
                provenance={"original_source_span":[where,where+1]},
            ))
        graph = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        assembled = self._vector.parse_lattice(
            graph, goal_category="CLAUSE",
            max_items=total_items - 2*piece_items,
            kbest_work_limit=total_work - 2*piece_work,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        selected = assembled.best()
        if (not assembled.completed or selected is None
                or selected.rule_id !=
                   "dialogue_structural_quoted_modal_zero_clausal_complement"):
            return None
        if isinstance(assembled.stats, dict):
            assembled.stats.update({
                "engine": "vector-source-scoped-modal-clausal-quotation",
                "structural_composition": True,
                "structural_composition_kind": "quoted_finite_modal_zero_clausal",
                "dialogue_scoped": True,
                "source_text_unchanged": True,
                "structural_clause_count": 2,
                "structural_segment_count": 2,
                "structural_segment_spans": [
                    list(subject), list(complement),
                ],
                "structural_segment_rule_ids": [
                    p.best().rule_id for p in proofs
                ],
                "structural_segment_stats": [
                    dict(p.stats) for p in proofs
                ],
                "source_modal_span": list(modal),
                "source_verb_span": list(verb),
                "source_punctuation_spans": [
                    [0,1], [stop,stop+1], [len(text)-1,len(text)],
                ],
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": total_work,
                "composition_linguistic_proof": (
                    "overt_pronominal_subject_finite_modal_lexically"
                    "_clausal_base_verb_and_independently_parsed_finite"
                    "_complement_without_invented_that"
                ),
            })
        assembled.shared_forest = {
            "assembly": assembled.shared_forest,
            "segments": tuple(p.shared_forest for p in proofs),
            "interfaces": tuple(c.interface for c in candidates
                                if c.interface is not None),
        }
        return assembled

    def compose_unquoted_emphatic_subject(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Source-gated number/person-unifying intensifier; NO NP-first chart rule.

        The old broad NP+REFLEXIVE grammar experiment demonstrably exhausted
        unrelated long literary parses. Here, *existing lexical evidence* for
        one overt reflexive, exact character bounds and independently proven
        nominal and finite predicative subtrees license one assembly only.
        """
        if (not components
                or not any(c.get("function") == "matrix_clause"
                           for c in components)
                or any(c.get("function") in (
                    "direct_speech", "embedded_quotation",
                    "reporting_clause", "split_direct_speech_turn",
                ) for c in components)
                or not text.endswith(".")
                or any(ch in text for ch in "\"“”‘’")):
            return None
        reflexives = [
            c for c in original_lattice.candidates
            if c.category == "EMPHATIC-REFLEXIVE"
            and c.features.as_dict().get("reflexive") == "true"
        ]
        if len(reflexives) != 1:
            return None
        intensifier = reflexives[0]
        x, y = intensifier.span_start, intensifier.span_end
        stop = len(text) - 1
        # Exact source-separated NP / intensifier / finite VP, with no
        # deleted quote, comma, incise, added word or fabricated punctuation.
        if (x < 2 or y >= stop - 2
                or text[x:y] != intensifier.surface
                or text[x - 1] != " " or text[y] != " "):
            return None
        np_text = text[:x].rstrip()
        vp_start = y
        while vp_start < stop and text[vp_start] == " ":
            vp_start += 1
        vp_text = text[vp_start:stop]
        if (not np_text or not vp_text or np_text != np_text.strip()
                or vp_text != vp_text.strip()
                or any(ch in np_text + vp_text for ch in ",;:!?()")):
            return None
        total_items = parser.max_items if max_items is None else max_items
        total_work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1000 or total_work < 1000:
            return None
        slice_items = total_items // 3
        slice_work = total_work // 3
        components_proved: list[ParseResult] = []
        assembly_candidates: list[LexicalCandidate] = []
        for category, fragment, a, b in (
            ("NP", np_text, 0, len(np_text)),
            ("VP", vp_text, vp_start, stop),
        ):
            lattice = parser._lattice_for_text(fragment)
            proof = parser._vector_grammar.parse_lattice(
                lattice, goal_category=category,
                max_items=slice_items, kbest_work_limit=slice_work,
                diagnostic_k=diagnostic_k,
                beam=parser.beam if beam is None else beam,
            )
            selected = proof.best()
            if (not proof.completed or selected is None
                    or selected.category != category):
                return None
            if (category == "VP" and
                    selected.features.as_dict().get("vform") != "finite"):
                return None
            components_proved.append(proof)
            assembly_candidates.append(LexicalCandidate(
                span_start=a, span_end=b, surface=fragment,
                lemma=f"<proved-{category.casefold()}>",
                category=category, features=selected.features,
                score=selected.score, source="scoped-source-grammar-proof",
                provenance={"source_span": [a, b],
                            "proof_rule_id": selected.rule_id},
                interface=SegmentInterface(proof, a, a, b),
            ))
        assembly_candidates.insert(1, intensifier)
        assembly_candidates.append(LexicalCandidate(
            span_start=stop, span_end=stop + 1, surface=text[stop],
            lemma=text[stop], category="SPEECH-STOP",
            features=FeatureStructure.empty(), score=0.0,
            source="original-sentence-delimiter",
            provenance={"source_span": [stop, stop + 1]},
        ))
        scoped_lattice = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(assembly_candidates),
        )
        result = self._vector.parse_lattice(
            scoped_lattice, goal_category="CLAUSE",
            max_items=total_items - slice_items * 2,
            kbest_work_limit=total_work - slice_work * 2,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        selected = result.best()
        if (not result.completed or selected is None
                or selected.rule_id !=
                   "structural_emphatic_reflexive_subject_predicate"):
            return None
        if isinstance(result.stats, dict):
            result.stats.update({
                "engine": "vector-source-scoped-emphatic-subject",
                "structural_composition": True,
                "source_text_unchanged": True,
                "structural_composition_kind": "coreferential_emphatic_subject",
                "structural_segment_count": 2,
                "structural_segment_spans": [
                    [0, len(np_text)], [vp_start, stop],
                ],
                "structural_segment_rule_ids": [
                    p.best().rule_id for p in components_proved
                ],
                "structural_segment_stats": [
                    dict(p.stats) for p in components_proved
                ],
                "source_reflexive_span": [x, y],
                "source_punctuation_spans": [[stop, stop + 1]],
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": total_work,
                "composition_linguistic_proof": (
                    "source_exact_subject_nominal_and_finite_predicate"
                    "_plus_overt_reflexive_with_unified_number_and_person"
                ),
            })
        result.shared_forest = {
            "assembly": result.shared_forest,
            "segments": tuple(p.shared_forest for p in components_proved),
            "interfaces": tuple(c.interface for c in assembly_candidates
                                if c.interface is not None),
        }
        return result

    def compose_unquoted_topical(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Bounded finite object fronting from actual source spans and proofs.

        The broad NP+NP+V production is intentionally NOT part of the global
        grammar: its partial states exhaust existing long literary parses.
        This source-scoped path works only when the original source has a
        complete, unquoted matrix utterance with overt demonstrative object,
        pronominal subject and a finite transitive lexical predicate.
        """
        if (not components
                or not any(p.get("function") == "matrix_clause"
                           for p in components)
                or any(p.get("function") in (
                    "direct_speech", "embedded_quotation",
                    "reporting_clause", "split_direct_speech_turn",
                ) for p in components)):
            return None
        match = re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\.", text
        )
        if match is None or match.group(1).casefold() not in (
                "this", "that", "these", "those"):
            return None
        if not (all(text[match.start(i):match.end(i)] ==
                    text[match.start(i):match.end(i)].strip()
                    for i in (1, 2, 3))
                and match.end(3) == len(text)-1):
            return None
        total_items = parser.max_items if max_items is None else max_items
        total_work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1000 or total_work < 1000:
            return None
        piece_items = total_items // 4
        piece_work = total_work // 4
        pieces = []
        candidates: list[LexicalCandidate] = []
        for position, goal in ((1, "NP"), (2, "NP"), (3, "V")):
            a, b = match.span(position)
            fragment = text[a:b]
            original = parser._lattice_for_text(fragment)
            if position == 1:
                # Only the lexically proven demonstrative determiner can be
                # projected by existing np_demonstrative; do not assume that
                # every superficially similar word is an object NP.
                chosen = tuple(c for c in original.candidates
                    if c.category == "DET"
                    and c.features.as_dict().get("definiteness")
                    == "demonstrative")
            elif position == 3:
                # Constrain by independently supplied verb valency and
                # inflection, never by a fabricated omitted object.
                chosen = tuple(c for c in original.candidates
                    if c.category == "V"
                    and c.features.as_dict().get("vform") == "finite"
                    and c.features.as_dict().get("subcat") == "transitive")
            else:
                chosen = original.candidates
            if not chosen:
                return None
            scoped_lattice = LexicalLattice(
                text=fragment, tokens=original.tokens, candidates=chosen,
            )
            proof = parser._vector_grammar.parse_lattice(
                scoped_lattice, goal_category=goal,
                max_items=piece_items, kbest_work_limit=piece_work,
                diagnostic_k=diagnostic_k,
                beam=parser.beam if beam is None else beam,
            )
            if not proof.completed or proof.best() is None:
                return None
            selected = proof.best()
            features = selected.features.as_dict()
            if selected.category != goal:
                return None
            if position == 1 and (
                    selected.rule_id != "np_demonstrative"
                    or features.get("definiteness") != "demonstrative"):
                return None
            if position == 2 and (
                    selected.rule_id != "np_indef_pron"
                    or features.get("pronominal") != "true"):
                return None
            if position == 3 and (
                    features.get("vform") != "finite"
                    or features.get("subcat") != "transitive"):
                return None
            pieces.append(proof)
            candidates.append(LexicalCandidate(
                span_start=a, span_end=b, surface=fragment,
                lemma=f"<verified-{goal.lower()}>",
                category=goal, features=selected.features,
                score=selected.score, source="scoped-source-grammar-proof",
                provenance={"source_span":[a,b],
                            "proof_rule_id":selected.rule_id},
                interface=SegmentInterface(proof, a, a, b),
            ))
        # Exact final punctuation belongs to the source, not to a synthetic
        # sentence repair or unbalanced quotation workaround.
        stop = len(text)-1
        candidates.append(LexicalCandidate(
            span_start=stop, span_end=stop+1, surface=text[stop],
            lemma=text[stop], category="SPEECH-STOP",
            features=FeatureStructure.empty(), score=0,
            source="original-sentence-delimiter",
            provenance={"source_span":[stop,stop+1]},
        ))
        assembly = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        result = self._vector.parse_lattice(
            assembly, goal_category="CLAUSE",
            max_items=total_items-piece_items*3,
            kbest_work_limit=total_work-piece_work*3,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if (not result.completed or result.best() is None
                or result.best().rule_id !=
                   "structural_topical_finite_demonstrative"):
            return None
        if isinstance(result.stats, dict):
            result.stats.update({
                "engine": "vector-source-scoped-finite-topicalization",
                "structural_composition": True,
                "source_text_unchanged": True,
                "structural_composition_kind": "demonstrative_object_fronting",
                "structural_clause_count": 1,
                "structural_segment_count": 3,
                "structural_segment_spans": [
                    list(match.span(i)) for i in (1, 2, 3)
                ],
                "structural_segment_rule_ids": [
                    p.best().rule_id for p in pieces
                ],
                "structural_segment_stats": [
                    dict(p.stats) for p in pieces
                ],
                "source_punctuation_spans": [[stop,stop+1]],
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": total_work,
                "composition_linguistic_proof": (
                    "demonstrative_nominal_and_pronominal_subject"
                    "_and_finite_transitive_lexical_valency_all_independently"
                    "_proven_under_a_source_exact_declarative_rule"
                ),
            })
        result.shared_forest = {
            "assembly": result.shared_forest,
            "segments": tuple(p.shared_forest for p in pieces),
            "interfaces": tuple(c.interface for c in candidates
                                if c.interface is not None),
        }
        return result

    @staticmethod
    def _plan(
        text: str, components: Sequence[Mapping[str, Any]],
    ) -> tuple[_ClauseSpan, ...] | None:
        by_id = {p.get("id"): p for p in components}
        q0 = by_id.get("q0")
        if not q0 or q0.get("function") != "direct_speech":
            return None
        if (q0.get("start"), q0.get("end")) != (0, len(text)):
            return None
        if any(p.get("function") in {
                "embedded_quotation", "split_direct_speech_turn",
                "reporting_clause", "narratorial_parenthetical",
        } for p in components):
            return None
        quotes = quotation_boundaries(text)
        if len(quotes) != 2 or (
            quotes[0].start, quotes[0].end, quotes[0].side,
            quotes[1].start, quotes[1].end, quotes[1].side,
        ) != (0, 1, "open", len(text)-1, len(text), "close"):
            return None
        clause_parts = sorted(
            (p for p in components
             if p.get("function") == "spoken_clause_candidate"
             and p.get("governor") == "q0"),
            key=lambda p: p["start"],
        )
        if len(clause_parts) not in (2, 3):
            return None
        previous = 1
        plan = []
        for part in clause_parts:
            a, b = part["start"], part["end"]
            if (not isinstance(a, int) or not isinstance(b, int)
                    or not (previous <= a < b <= len(text)-1)):
                return None
            if text[previous:a].strip():
                return None
            stop = b - 1
            if text[stop] not in ".!?":
                return None
            # We prove only explicit finite clauses. A subordinate, speech
            # continuation or bare NP cannot be promoted by the interface.
            body = text[a:stop]
            if not body or body != body.strip() or any(
                    ch in body for ch in "\"“”‘’"
            ):
                return None
            plan.append(_ClauseSpan(a, stop, stop))
            previous = b
        if text[previous:-1].strip():
            return None
        return tuple(plan)

    def compose(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        plan = self._plan(text, components)
        if plan is None:
            intercalated = self._compose_intercalated(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if intercalated is not None:
                return intercalated
            complement = self._compose_intercalated_that_complement(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if complement is not None:
                return complement
            minor = self._compose_minor_response(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if minor is not None:
                return minor
            postposed = self._compose_postposed_minor_reply(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if postposed is not None:
                return postposed
            nominal = self._compose_nested_nominal_title(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if nominal is not None:
                return nominal
            finite_modal = self._compose_quoted_modal_zero_clausal_complement(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if finite_modal is not None:
                return finite_modal
            return self._compose_modal_ellipsis_response(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
        # Bounded total allocations, not 3x the public parser's budget.
        total_items = parser.max_items if max_items is None else max_items
        work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1000 or work < 1000:
            return None
        piece_items = total_items // (len(plan) + 1)
        piece_work = work // (len(plan) + 1)
        candidates: list[LexicalCandidate] = []
        results: list[ParseResult] = []
        for clause in plan:
            fragment = text[clause.start:clause.end]
            # No broad speculation on long clauses; the normal full parser
            # remains the fallback and no structural success is claimed.
            if len(fragment.split()) > 22:
                return None
            parsed = parser._parse_vector_text(
                fragment,
                max_items=piece_items,
                kbest_work_limit=piece_work,
                diagnostic_k=diagnostic_k,
                beam=beam,
            )
            if not parsed.completed:
                return None
            best = parsed.best()
            # Prove a finite subject-predicate construction on each side:
            # do not count a nominal, elliptical or homographic root.
            if (best is None or best.category != "CLAUSE"
                    or best.rule_id != "clause_np_vp"):
                return None
            results.append(parsed)
            interface = SegmentInterface(
                parsed, clause.start, clause.start, clause.end,
            )
            candidates.append(LexicalCandidate(
                span_start=clause.start, span_end=clause.end,
                surface=fragment, lemma="<verified-clause>",
                category="CLAUSE", features=best.features,
                source="source-structural-clause-interface",
                score=best.score,
                provenance={"source_span":[clause.start, clause.end],
                            "proof_rule_id":best.rule_id},
                interface=interface,
            ))
            candidates.append(LexicalCandidate(
                span_start=clause.stop, span_end=clause.stop+1,
                surface=text[clause.stop], lemma=text[clause.stop],
                category="SPEECH-STOP", features=FeatureStructure.empty(),
                source="dialogue-delimiter", score=0,
                provenance={"source_stop":clause.stop},
            ))
        for where, category in ((0, "OPEN-QUOTE"), (len(text)-1, "CLOSE-QUOTE")):
            candidates.append(LexicalCandidate(
                span_start=where, span_end=where+1,
                surface=text[where], lemma=text[where],
                category=category, features=FeatureStructure.empty(),
                source="dialogue-delimiter", score=0,
                provenance={"source_delimiter":where},
            ))
        graph = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        assembled = self._vector.parse_lattice(
            graph, goal_category="CLAUSE",
            max_items=total_items - piece_items * len(plan),
            kbest_work_limit=work - piece_work * len(plan),
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not assembled.completed or assembled.best() is None:
            return None
        if isinstance(assembled.stats, dict):
            assembled.stats.update({
                "engine": "vector-structurally-composed-quoted-sentences",
                "structural_composition": True,
                "dialogue_scoped": True,
                "source_text_unchanged": True,
                "composition_linguistic_proof": (
                    "each_child_selected_complete_clausal_np_vp_tree"
                    "_plus_declarative_quote_sentence_sequence_grammar"
                ),
                "structural_segment_count": len(plan),
                "structural_clause_count": len(plan),
                "structural_segment_spans": [
                    [c.start, c.end] for c in plan
                ],
                "structural_segment_rule_ids": [
                    r.best().rule_id for r in results
                ],
                "structural_segment_stats": [
                    dict(r.stats) for r in results
                ],
                "source_punctuation_spans": [
                    [c.stop, c.stop+1] for c in plan
                ],
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": work,
            })
        assembled.shared_forest = {
            "assembly": assembled.shared_forest,
            "segments": tuple(r.shared_forest for r in results),
            "interfaces": tuple(
                c.interface for c in candidates
                if c.interface is not None
            ),
        }
        return assembled


    @staticmethod
    def _intercalation_plan(
        text: str, components: Sequence[Mapping[str, Any]],
    ) -> tuple[_ClauseSpan, _ClauseSpan, tuple[int, int], int] | None:
        """Exact quote, tag, and punctuation spans of one split turn.

        Only independently finite spoken clauses are admitted here. A split
        subject + predicate across tags is NOT considered a pair of clauses
        and cannot use this construction.
        """
        by_id = {p.get("id"): p for p in components}
        first, second, tag = (by_id.get(name) for name in ("q0", "q1", "r0"))
        if not all((first, second, tag)):
            return None
        if not (
            first.get("function") == second.get("function") == "direct_speech"
            and tag.get("function") == "reporting_clause"
            and any(p.get("function") == "split_direct_speech_turn"
                    for p in components)
            and second.get("relation") == "resumption_of_split_speech"
            and second.get("governor") == "q0"
        ):
            return None
        if any(p.get("function") in {
            "embedded_quotation", "narratorial_parenthetical"
        } for p in components):
            return None
        q = quotation_boundaries(text)
        if len(q) != 4 or [x.side for x in q] != [
            "open", "close", "open", "close"
        ]:
            return None
        a0, b0 = first["start"], first["end"]
        a1, b1 = second["start"], second["end"]
        ta, tb = tag["start"], tag["end"]
        if not (a0 == 0 and b1 == len(text) and
                0 < b0 < ta < tb < a1 < b1):
            return None
        if [q[0].start, q[1].end, q[2].start, q[3].end] != [
            a0, b0, a1, b1
        ]:
            return None
        # The commas must be literally printed in their proper places:
        # first belongs to quoted speech, second terminates the speaker tag.
        stop0, stop1 = b0-2, b1-2
        if text[stop0] != "," or text[stop1] not in ".!?":
            return None
        if text[b0:ta].strip():
            return None
        separator = text[tb:a1]
        if not re.fullmatch(r"\s*,\s*", separator):
            return None
        tag_comma = tb + separator.index(",")
        clause0 = _ClauseSpan(a0+1, stop0, stop0)
        clause1 = _ClauseSpan(a1+1, stop1, stop1)
        if not (clause0.start < clause0.end
                and clause1.start < clause1.end):
            return None
        for clause in (clause0, clause1):
            body = text[clause.start:clause.end]
            if (body != body.strip() or len(body.split()) > 22
                    or any(ch in body for ch in "\"“”‘’")):
                return None
        if text[ta:tb] != text[ta:tb].strip():
            return None
        return clause0, clause1, (ta, tb), tag_comma

    def _compose_intercalated(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Same unification recognizer validates clause/tag/clause interfaces."""
        plan = self._intercalation_plan(text, components)
        if plan is None:
            return None
        clause0, clause1, (ta, tb), tag_comma = plan
        dialogue_grammar = getattr(parser, "_dialogue_vector_grammar", None)
        if dialogue_grammar is None:
            return None
        total_items = parser.max_items if max_items is None else max_items
        work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1000 or work < 1000:
            return None
        piece_items = total_items // 4
        piece_work = work // 4
        results = []
        candidates: list[LexicalCandidate] = []

        def accept_interface(
            category: str, a: int, b: int, result: ParseResult,
            expected_rule: str | None = None,
        ) -> bool:
            if not result.completed:
                return False
            best = result.best()
            if (best is None or best.category != category
                    or (expected_rule is not None
                        and best.rule_id != expected_rule)):
                return False
            interface = SegmentInterface(result, a, a, b)
            candidates.append(LexicalCandidate(
                span_start=a, span_end=b,
                surface=text[a:b], lemma=f"<verified-{category.lower()}>",
                category=category, features=best.features,
                source="source-structural-grammar-proof",
                score=best.score,
                provenance={
                    "source_span": [a, b],
                    "proof_rule_id": best.rule_id,
                },
                interface=interface,
            ))
            results.append(result)
            return True

        for clause in (clause0, clause1):
            outcome = parser._parse_vector_text(
                text[clause.start:clause.end],
                max_items=piece_items,
                kbest_work_limit=piece_work,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if not accept_interface(
                "CLAUSE", clause.start, clause.end,
                outcome, "clause_np_vp",
            ):
                return None
        tag_lattice = parser._lattice_for_text(text[ta:tb])
        tag_result = dialogue_grammar.parse_lattice(
            tag_lattice,
            goal_category="SPEECH-TAG",
            max_items=piece_items,
            kbest_work_limit=piece_work,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not accept_interface("SPEECH-TAG", ta, tb, tag_result):
            return None
        if not (tag_result.best().rule_id or "").startswith(
                "dialogue_speech_tag_"):
            return None

        def punctuation(where: int, category: str):
            candidates.append(LexicalCandidate(
                span_start=where, span_end=where+1,
                surface=text[where], lemma=text[where],
                category=category, features=FeatureStructure.empty(),
                source="dialogue-delimiter", score=0,
                provenance={"source_punctuation":where},
            ))

        # In order: " finite-clause , " reporting-tag , " finite-clause . "
        punct = (
            (0, "OPEN-QUOTE"), (clause0.stop, "COMMA"),
            (clause0.stop+1, "CLOSE-QUOTE"), (tag_comma, "COMMA"),
            (clause1.start-1, "OPEN-QUOTE"),
            (clause1.stop, "SPEECH-STOP"),
            (len(text)-1, "CLOSE-QUOTE"),
        )
        for where, category in punct:
            punctuation(where, category)
        lattice = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        assembled = self._vector.parse_lattice(
            lattice, goal_category="CLAUSE",
            max_items=total_items-piece_items*3,
            kbest_work_limit=work-piece_work*3,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not assembled.completed or assembled.best() is None:
            return None
        if isinstance(assembled.stats, dict):
            assembled.stats.update({
                "engine": "vector-structurally-composed-quoted-split-turn",
                "structural_composition": True,
                "dialogue_scoped": True,
                "source_text_unchanged": True,
                "structural_composition_kind": "intercalated_reporting_clause",
                "composition_linguistic_proof": (
                    "two_complete_finite_np_vp_clauses_and_one_"
                    "source_attributed_speech_tag_proven_by_grammar"
                ),
                "structural_segment_count": 3,
                "structural_clause_count": 2,
                "structural_segment_spans": [
                    [clause0.start, clause0.end],
                    [ta, tb],
                    [clause1.start, clause1.end],
                ],
                "structural_segment_rule_ids": [
                    r.best().rule_id for r in results
                ],
                "structural_segment_stats": [
                    dict(r.stats) for r in results
                ],
                "source_punctuation_spans": [
                    [where, where+1] for where, _ in punct
                ],
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": work,
            })
        assembled.shared_forest = {
            "assembly": assembled.shared_forest,
            "segments": tuple(r.shared_forest for r in results),
            "interfaces": tuple(
                c.interface for c in candidates if c.interface is not None
            ),
        }
        return assembled



    @staticmethod
    def _intercalated_that_complement_plan(
        text: str, components: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[int, int], ...] | None:
        """Propose overt quoted head/vocative, attribution and resumed that-clause.

        This is a source plan, NOT a grammatical proof. The ordinary
        recognizer must independently prove the matrix predicate, vocative,
        reporter, complementizer and finite subordinate clause. In
        particular a quoted subordinate is never an independent second
        speech act.
        """
        base = QuotedSentenceComposer._intercalation_plan(text, components)
        if base is None:
            return None
        first, second, reporter, tag_comma = base
        # This construction requires an explicitly printed subordinate
        # complementizer, not a missing verb or a hypothesized "that".
        that_start = second.start
        that_end = that_start + 4
        if (text[that_start:that_end].casefold() != "that"
                or that_end >= second.end
                or not text[that_end].isspace()):
            return None
        complement_start = that_end
        while complement_start < second.end and text[complement_start].isspace():
            complement_start += 1
        if complement_start >= second.end:
            return None
        internal_comma = text.rfind(",", first.start, first.end)
        if internal_comma <= first.start:
            return None
        head = (first.start, internal_comma)
        voc_start = internal_comma + 1
        while voc_start < first.end and text[voc_start].isspace():
            voc_start += 1
        vocative = (voc_start, first.end)
        subordinate = (complement_start, second.end)
        if (not all(a < b for a, b in (head, vocative, subordinate))
                or len(text[slice(*head)].split()) > 18
                or len(text[slice(*vocative)].split()) > 5
                or len(text[slice(*subordinate)].split()) > 22
                or text[slice(*head)] != text[slice(*head)].strip()
                or text[slice(*vocative)] != text[slice(*vocative)].strip()
                or text[slice(*subordinate)] != text[slice(*subordinate)].strip()):
            return None
        return (head, vocative, reporter, (that_start, that_end),
                subordinate, (internal_comma, first.stop, first.stop+1,
                              tag_comma, second.start-1, second.stop,
                              len(text)-1))

    def _compose_intercalated_that_complement(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Compose a lexical-licensed copular that-complement across a tag."""
        plan = self._intercalated_that_complement_plan(text, components)
        if plan is None:
            return None
        head, vocative, reporter, comp, subordinate, punctuation = plan
        dialogue_grammar = getattr(parser, "_dialogue_vector_grammar", None)
        if dialogue_grammar is None:
            return None
        total_items = parser.max_items if max_items is None else max_items
        total_work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1200 or total_work < 1200:
            return None
        piece_items, piece_work = total_items // 6, total_work // 6
        candidates: list[LexicalCandidate] = []
        proofs: list[ParseResult] = []
        for category, (a, b), grammar in (
            ("CLAUSE", head, parser._vector_grammar),
            ("NP", vocative, parser._vector_grammar),
            ("SPEECH-TAG", reporter, dialogue_grammar),
            ("COMP-THAT", comp, parser._vector_grammar),
            ("CLAUSE", subordinate, parser._vector_grammar),
        ):
            fragment = text[a:b]
            if category == "CLAUSE":
                proof = parser._parse_vector_text(
                    fragment, max_items=piece_items,
                    kbest_work_limit=piece_work,
                    diagnostic_k=diagnostic_k, beam=beam,
                )
            else:
                proof = grammar.parse_lattice(
                    parser._lattice_for_text(fragment),
                    goal_category=category,
                    max_items=piece_items,
                    kbest_work_limit=piece_work,
                    diagnostic_k=diagnostic_k,
                    beam=parser.beam if beam is None else beam,
                )
            if not proof.completed or proof.best() is None:
                return None
            selected = proof.best()
            if selected.category != category:
                return None
            if category == "CLAUSE" and selected.rule_id != "clause_np_vp":
                return None
            if (category == "SPEECH-TAG"
                    and not (selected.rule_id or "").startswith(
                        "dialogue_speech_tag_")):
                return None
            if category == "CLAUSE" and (a, b) == head:
                # Only adjective predicates whose selected lexical reading
                # explicitly selects a finite that-complement may resume.
                # It is NOT enough for the matrix head merely to be a clause.
                if len(selected.children) != 2:
                    return None
                vp = selected.children[1]
                if (vp.rule_id != "vp_copula_adj"
                        or len(vp.children) != 2
                        or vp.children[1].category != "ADJ"
                        or vp.children[1].features.as_dict().get(
                            "that_clausal_complement") != "true"):
                    return None
            proofs.append(proof)
            candidates.append(LexicalCandidate(
                span_start=a, span_end=b, surface=fragment,
                lemma=f"<verified-{category.lower()}>",
                category=category, features=selected.features,
                source="source-structural-grammar-proof",
                score=selected.score,
                provenance={
                    "source_span": [a, b], "proof_rule_id": selected.rule_id,
                },
                interface=SegmentInterface(proof, a, a, b),
            ))
        for pos, category in zip(
            punctuation,
            ("COMMA", "COMMA", "CLOSE-QUOTE", "COMMA",
             "OPEN-QUOTE", "SPEECH-STOP", "CLOSE-QUOTE"),
        ):
            candidates.append(LexicalCandidate(
                span_start=pos, span_end=pos+1,
                surface=text[pos], lemma=text[pos],
                category=category, features=FeatureStructure.empty(),
                source="dialogue-delimiter", score=0,
                provenance={"source_punctuation":pos},
            ))
        candidates.append(LexicalCandidate(
            span_start=0, span_end=1, surface=text[0], lemma=text[0],
            category="OPEN-QUOTE", features=FeatureStructure.empty(),
            source="dialogue-delimiter", score=0,
            provenance={"source_punctuation":0},
        ))
        graph = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        assembled = self._vector.parse_lattice(
            graph, goal_category="CLAUSE",
            max_items=total_items-5*piece_items,
            kbest_work_limit=total_work-5*piece_work,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not assembled.completed or assembled.best() is None:
            return None
        if isinstance(assembled.stats, dict):
            assembled.stats.update({
                "engine": "vector-structural-intercalated-that-complement",
                "structural_composition": True,
                "dialogue_scoped": True,
                "source_text_unchanged": True,
                "structural_composition_kind": "intercalated_that_complement",
                "structural_clause_count": 2,
                "structural_segment_count": 5,
                "structural_segment_spans": [
                    list(span) for span in (head, vocative, reporter, comp,
                                            subordinate)
                ],
                "structural_segment_rule_ids": [
                    p.best().rule_id for p in proofs
                ],
                "structural_segment_stats": [dict(p.stats) for p in proofs],
                "source_punctuation_spans": [
                    [i, i+1] for i in (0, *punctuation)
                ],
                "composition_linguistic_proof": (
                    "selected_copular_adjective_lexically_selects_that_clause"
                    "_plus_verified_subject_predicate_complement_and_speech_tag"
                ),
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": total_work,
            })
        assembled.shared_forest = {
            "assembly": assembled.shared_forest,
            "segments": tuple(p.shared_forest for p in proofs),
            "interfaces": tuple(
                c.interface for c in candidates if c.interface is not None
            ),
        }
        return assembled

    def _compose_minor_response(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Adverbial answer + vocative: independently attest ADV and NP.

        This is a *minor conversational utterance* (not a finite matrix
        clause). The answer and addressee have separate grammatical roles;
        no silent copula or finite verb is supplied.
        """
        parts = {p.get("id"): p for p in components}
        root = parts.get("s0")
        quote = parts.get("q0")
        if not root or not quote:
            return None
        if not (
            root.get("function") == "minor_utterance"
            and root.get("relation") == "dialogue_response"
            and quote.get("function") == "direct_speech"
            and (quote["start"], quote["end"]) == (0, len(text))
            and len([p for p in components
                     if p.get("function") in ("direct_speech",
                                            "embedded_quotation")]) == 1
        ):
            return None
        marks = quotation_boundaries(text)
        if len(marks) != 2 or (
            marks[0].start, marks[0].end, marks[0].side,
            marks[1].start, marks[1].end, marks[1].side,
        ) != (0, 1, "open", len(text)-1, len(text), "close"):
            return None
        # Anchor exactly one independent source ADV and the overt vocative
        # nominal after the source comma, not a guessed missing predicate.
        match = re.fullmatch(
            r"(?i)([a-z]+)\s*,\s*([a-z][a-z'-]*)[.!?]",
            text[1:-1],
        )
        if match is None:
            return None
        a1, b1 = 1+match.start(1), 1+match.end(1)
        a2, b2 = 1+match.start(2), 1+match.end(2)
        comma = text.find(",", b1, a2)
        if comma < b1 or text[b2] not in ".!?":
            return None
        total_items = parser.max_items if max_items is None else max_items
        work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1000 or work < 1000:
            return None
        piece_items, piece_work = total_items//3, work//3
        proved = []
        candidates: list[LexicalCandidate] = []
        for cat, a, b in (("ADV", a1, b1), ("NP", a2, b2)):
            lattice = parser._lattice_for_text(text[a:b])
            parsed = parser._vector_grammar.parse_lattice(
                lattice,
                goal_category=cat,
                beam=parser.beam if beam is None else beam,
                max_items=piece_items,
                kbest_work_limit=piece_work,
                diagnostic_k=diagnostic_k,
            )
            if not parsed.completed or parsed.best() is None:
                return None
            selected = parsed.best()
            if selected.category != cat:
                return None
            proved.append(parsed)
            interface = SegmentInterface(parsed, a, a, b)
            candidates.append(LexicalCandidate(
                span_start=a, span_end=b,
                surface=text[a:b], lemma=f"<verified-{cat.lower()}>",
                category=cat, features=selected.features,
                source="source-structural-minor-utterance-proof",
                score=selected.score,
                provenance={"source_span":[a,b],
                            "grammar_proof": selected.rule_id},
                interface=interface,
            ))
        for pos, cat in (
            (0, "OPEN-QUOTE"), (comma, "COMMA"),
            (b2, "SPEECH-STOP"), (len(text)-1, "CLOSE-QUOTE"),
        ):
            candidates.append(LexicalCandidate(
                span_start=pos, span_end=pos+1,
                surface=text[pos], lemma=text[pos],
                category=cat, features=FeatureStructure.empty(),
                source="dialogue-delimiter",
                score=0, provenance={"source_span":[pos,pos+1]},
            ))
        graph = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        combined = self._vector.parse_lattice(
            graph, goal_category="CLAUSE",
            max_items=total_items-2*piece_items,
            kbest_work_limit=work-2*piece_work,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not combined.completed or combined.best() is None:
            return None
        if isinstance(combined.stats, dict):
            combined.stats.update({
                "engine": "vector-structurally-composed-minor-utterance",
                "structural_composition": True,
                "structural_composition_kind": "adverbial_answer_with_vocative",
                "structural_clause_count": 0,
                "structural_segment_count": 2,
                "structural_segment_spans": [[a1,b1],[a2,b2]],
                "structural_segment_rule_ids": [
                    p.best().rule_id for p in proved
                ],
                "structural_segment_stats": [dict(p.stats) for p in proved],
                "dialogue_scoped": True,
                "source_text_unchanged": True,
                "composition_linguistic_proof": (
                    "adverb_and_vocative_nominal_independently_parsed_"
                    "with_no_finite_predicate_invented"
                ),
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": work,
            })
        combined.shared_forest = {
            "assembly": combined.shared_forest,
            "segments": tuple(p.shared_forest for p in proved),
            "interfaces": tuple(c.interface for c in candidates
                                if c.interface is not None),
        }
        return combined


    @staticmethod
    def _postposed_minor_reply_plan(
        text: str, components: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int],
               tuple[int, ...]] | None:
        """Source-exact quoted head + vocative + postposed reporting clause.

        The initial head can be a fully proven finite CLAUSE or a verbless
        ADVP. Both are real grammatical constructs, with an overt vocative NP
        and a genuine reporting tag; no lexical word or verb is invented.
        This only proposes the source span boundaries; the unification parser
        MUST still independently prove every source-derived component.
        """
        by_id = {p.get("id"): p for p in components}
        quote, reporter = by_id.get("q0"), by_id.get("r0")
        if not quote or not reporter:
            return None
        if quote.get("function") != "direct_speech":
            return None
        if reporter.get("function") != "reporting_clause":
            return None
        if reporter.get("evidence") != "postposed_reporting_clause":
            return None
        if quote.get("governor") != "r0":
            return None
        if any(p.get("function") in (
            "embedded_quotation", "split_direct_speech_turn",
            "narratorial_parenthetical",
        ) for p in components):
            return None
        a, b = quote.get("start"), quote.get("end")
        ta, tb = reporter.get("start"), reporter.get("end")
        if not (
            a == 0 and isinstance(b, int)
            and isinstance(ta, int) and isinstance(tb, int)
            and 4 < b <= ta < tb < len(text)
            and text[b:ta].isspace()
            and text[tb:] == "."
        ):
            return None
        boundary = quotation_boundaries(text)
        if len(boundary) != 2 or [
            (x.start, x.end, x.side) for x in boundary
        ] != [(0, 1, "open"), (b - 1, b, "close")]:
            return None
        # The final source comma before a vocative separates the independent
        # spoken head from a nominal form of direct address. A finite clause
        # may itself contain earlier commas; only this final vocative boundary
        # is used to plan the source grammar.
        if text[b-2] != ",":
            return None
        first_comma = text.rfind(",", 1, b-2)
        if first_comma <= 1:
            return None
        adv_a, adv_b = 1, first_comma
        np_a, np_b = first_comma+1, b-2
        while np_a < np_b and text[np_a].isspace():
            np_a += 1
        while np_b > np_a and text[np_b-1].isspace():
            np_b -= 1
        if np_a >= np_b:
            return None
        if (text[adv_a:adv_b] != text[adv_a:adv_b].strip()
                or any(c in text[adv_a:adv_b]+text[np_a:np_b]
                       for c in "\"'“”‘’;!?")
                or len(text[adv_a:adv_b].split()) > 24
                or len(text[np_a:np_b].split()) > 5):
            return None
        return (adv_a, adv_b), (np_a, np_b), (ta, tb), (
            0, first_comma, b-2, b-1, len(text)-1,
        )

    def _compose_postposed_minor_reply(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        plan = self._postposed_minor_reply_plan(text, components)
        if plan is None:
            return None
        adverbial, vocative, reporter, punctuation = plan
        dialogue_grammar = getattr(parser, "_dialogue_vector_grammar", None)
        if dialogue_grammar is None:
            return None
        total_items = parser.max_items if max_items is None else max_items
        total_work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1000 or total_work < 1000:
            return None
        piece_items, piece_work = total_items // 4, total_work // 4
        candidates: list[LexicalCandidate] = []
        proofs: list[ParseResult] = []
        # Structural cues select which grammar category to attempt, never
        # prove it. The selected complete ranked tree is the sole authority.
        head_text = text[adverbial[0]:adverbial[1]]
        head_category = ("CLAUSE" if skeleton(head_text).finite_predicate_candidate
                         else "ADVP")
        for category, (a, b), grammar in (
            (head_category, adverbial, parser._vector_grammar),
            ("NP", vocative, parser._vector_grammar),
            ("SPEECH-TAG", reporter, dialogue_grammar),
        ):
            surface = text[a:b]
            if category == "CLAUSE":
                proof = parser._parse_vector_text(
                    surface, max_items=piece_items,
                    kbest_work_limit=piece_work,
                    diagnostic_k=diagnostic_k, beam=beam,
                )
            else:
                lattice = parser._lattice_for_text(surface)
                proof = grammar.parse_lattice(
                    lattice, goal_category=category,
                    max_items=piece_items,
                    kbest_work_limit=piece_work,
                    diagnostic_k=diagnostic_k,
                    beam=parser.beam if beam is None else beam,
                )
            if not proof.completed or proof.best() is None:
                return None
            selected = proof.best()
            if selected.category != category:
                return None
            if category == "CLAUSE" and selected.rule_id != "clause_np_vp":
                return None
            if (category == "SPEECH-TAG"
                    and not (selected.rule_id or "").startswith(
                        "dialogue_speech_tag_")):
                return None
            proofs.append(proof)
            candidates.append(LexicalCandidate(
                span_start=a, span_end=b, surface=surface,
                lemma=f"<verified-{category.lower()}>",
                category=category, features=selected.features,
                source="source-structural-grammar-proof",
                score=selected.score,
                provenance={
                    "source_span": [a, b],
                    "proof_rule": selected.rule_id,
                },
                interface=SegmentInterface(proof, a, a, b),
            ))
        quote_start, internal_comma, final_comma, close_quote, period = punctuation
        # Distinct terminals are necessary to preserve the two grammatical
        # commas (answer/vocative and quote/reporter) in the actual tree.
        for where, category in (
            (quote_start, "OPEN-QUOTE"),
            (internal_comma, "COMMA"),
            (final_comma, "COMMA"),
            (close_quote, "CLOSE-QUOTE"),
            (period, "SPEECH-STOP"),
        ):
            candidates.append(LexicalCandidate(
                span_start=where, span_end=where+1,
                surface=text[where], lemma=text[where],
                category=category, features=FeatureStructure.empty(),
                source="dialogue-delimiter", score=0,
                provenance={"original_source_span":[where,where+1]},
            ))
        graph = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        combined = self._vector.parse_lattice(
            graph, goal_category="CLAUSE",
            max_items=total_items - 3 * piece_items,
            kbest_work_limit=total_work - 3 * piece_work,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not combined.completed or combined.best() is None:
            return None
        if isinstance(combined.stats, dict):
            combined.stats.update({
                "engine": "vector-structural-vocative-with-postposed-reporter",
                "structural_composition": True,
                "structural_composition_kind": (
                    "finite_clause_vocative_with_postposed_reporting_clause"
                    if head_category == "CLAUSE" else
                    "adverbial_answer_vocative_with_postposed_reporting_clause"
                ),
                "source_text_unchanged": True,
                "dialogue_scoped": True,
                "structural_clause_count": int(head_category == "CLAUSE"),
                "structural_segment_count": 3,
                "structural_segment_spans": [
                    list(adverbial), list(vocative), list(reporter)
                ],
                "structural_segment_rule_ids": [
                    x.best().rule_id for x in proofs
                ],
                "structural_segment_stats": [
                    dict(x.stats) for x in proofs
                ],
                "source_punctuation_spans": [
                    [i, i+1] for i in punctuation
                ],
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": total_work,
                "composition_linguistic_proof": (
                    "source_finite_np_vp_clause_and_vocative_and_reporting_tag"
                    if head_category == "CLAUSE" else
                    "source_adverbial_and_vocative_and_reporting_tag"
                ) + "_each_independently_licensed_by_grammar",
            })
        combined.shared_forest = {
            "assembly": combined.shared_forest,
            "segments": tuple(x.shared_forest for x in proofs),
            "interfaces": tuple(
                x.interface for x in candidates if x.interface is not None
            ),
        }
        return combined


    @staticmethod
    def _nested_nominal_title_plan(
        text: str, components: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[int, int], tuple[int, int], tuple[int, ...]] | None:
        """Nominal/title utterance with an embedded source-quoted name.

        The exact original structure is:
          outer quotation [determiner [inner quotation nominal title]] stop.
        Both the determiner and embedded nominal must produce independent
        successful unification trees. This does not invent a finite clause,
        quotation closure, or a normalized replacement name.
        """
        by_id = {p.get("id"): p for p in components}
        outer, inner = by_id.get("q0"), by_id.get("q1")
        if not outer or not inner:
            return None
        if not (
            outer.get("function") == "direct_speech"
            and inner.get("function") == "embedded_quotation"
            and inner.get("governor") == "q0"
            and outer.get("start") == 0
            and outer.get("end") == len(text)
        ):
            return None
        if sum(p.get("function") == "embedded_quotation"
               for p in components) != 1:
            return None
        if any(p.get("function") in (
                "reporting_clause", "split_direct_speech_turn",
                "narratorial_parenthetical"
        ) for p in components):
            return None
        marks = quotation_boundaries(text)
        if len(marks) != 4 or [
            (p.start, p.end, p.side) for p in marks
        ] != [
            (0, 1, "open"),
            (inner["start"], inner["start"]+1, "open"),
            (inner["end"]-1, inner["end"], "close"),
            (len(text)-1, len(text), "close"),
        ]:
            return None
        # A single original terminal mark after the embedded title.
        stop = inner["end"]
        if stop != len(text)-2 or text[stop] not in ".!?":
            return None
        a, b = 1, inner["start"]
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b-1].isspace():
            b -= 1
        # A single lexical determiner and one inner NP title. This is a
        # syntactic construction, not a lexical exception for "Em'ly".
        if (not a < b or len(text[a:b].split()) != 1
                or text[1:a].strip() or text[b:inner["start"]].strip()):
            return None
        title_start, title_end = inner["start"]+1, inner["end"]-1
        if (not title_start < title_end
                or len(text[title_start:title_end].split()) > 7
                or text[title_start:title_end] !=
                   text[title_start:title_end].strip()):
            return None
        return ((a,b), (title_start,title_end),
                (0,inner["start"],inner["end"]-1,stop,len(text)-1))

    def _compose_nested_nominal_title(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        plan = self._nested_nominal_title_plan(text,components)
        if plan is None:
            return None
        determiner, name, punct = plan
        total_items = parser.max_items if max_items is None else max_items
        work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1000 or work < 1000:
            return None
        items, work_piece = total_items//3, work//3
        candidates: list[LexicalCandidate] = []
        proofs: list[ParseResult] = []
        for category,(start,end) in (("DET",determiner),("NP",name)):
            lattice=parser._lattice_for_text(text[start:end])
            parsed=parser._vector_grammar.parse_lattice(
                lattice,goal_category=category,
                max_items=items,kbest_work_limit=work_piece,
                diagnostic_k=diagnostic_k,
                beam=parser.beam if beam is None else beam,
            )
            if not parsed.completed or parsed.best() is None:
                return None
            best=parsed.best()
            if best.category != category:
                return None
            proofs.append(parsed)
            candidates.append(LexicalCandidate(
                span_start=start,span_end=end,
                surface=text[start:end],
                lemma=f"<verified-{category.lower()}>",
                category=category,features=best.features,
                source="source-structural-grammar-proof",
                score=best.score,
                provenance={"source_span":[start,end],
                            "proof_rule_id":best.rule_id},
                interface=SegmentInterface(parsed,start,start,end),
            ))
        # The exact punctuation is consumed in its source order.
        for idx,cat in zip(punct,(
            "OPEN-QUOTE","OPEN-QUOTE","CLOSE-QUOTE",
            "SPEECH-STOP","CLOSE-QUOTE"
        )):
            candidates.append(LexicalCandidate(
                span_start=idx,span_end=idx+1,surface=text[idx],
                lemma=text[idx],category=cat,
                features=FeatureStructure.empty(),
                source="dialogue-delimiter",score=0,
                provenance={"source_position":idx},
            ))
        graph=LexicalLattice(
            text=text,tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        combined=self._vector.parse_lattice(
            graph,goal_category="CLAUSE",
            max_items=total_items-2*items,
            kbest_work_limit=work-2*work_piece,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not combined.completed or combined.best() is None:
            return None
        if isinstance(combined.stats,dict):
            combined.stats.update({
                "engine":"vector-composed-nested-quoted-nominal-title",
                "structural_composition":True,
                "structural_composition_kind":"nominal_title_with_embedded_quote",
                "source_text_unchanged":True,
                "dialogue_scoped":True,
                "structural_clause_count":0,
                "structural_segment_count":2,
                "structural_segment_spans":[list(determiner),list(name)],
                "structural_segment_rule_ids":[p.best().rule_id for p in proofs],
                "source_punctuation_spans":[[i,i+1] for i in punct],
                "source_anaphoric_predicate_inserted":False,
                "max_items_total_across_segments":total_items,
                "kbest_work_limit_total_across_segments":work,
                "composition_linguistic_proof":
                    "source_determiner_plus_independently_verified"
                    "_embedded_nominal_title_in_balanced_nested_quotes",
            })
        combined.shared_forest={
            "assembly":combined.shared_forest,
            "segments":tuple(p.shared_forest for p in proofs),
            "interfaces":tuple(
                c.interface for c in candidates if c.interface is not None
            ),
        }
        return combined


    @staticmethod
    def _modal_ellipsis_plan(
        text: str, components: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[int,int], ...] | None:
        """Four overt tokens: topical demonstrative, subject, adverb, modal.

        A modal can license VP ellipsis when the missing lexical predicate is
        recoverable from prior discourse. The grammatical surface is analyzed
        without reconstructing or guessing that predicate. Reference to its
        antecedent remains explicitly unresolved.
        """
        by_id={c.get("id"):c for c in components}
        q=by_id.get("q0")
        if not q or q.get("function")!="direct_speech":
            return None
        if (q.get("start"),q.get("end"))!=(0,len(text)):
            return None
        if any(p.get("function") in (
            "reporting_clause","embedded_quotation",
            "split_direct_speech_turn","narratorial_parenthetical",
        ) for p in components):
            return None
        marks=quotation_boundaries(text)
        if len(marks)!=2 or [
            (m.start,m.end,m.side) for m in marks
        ]!=[(0,1,"open"),(len(text)-1,len(text),"close")]:
            return None
        if len(text)<9 or text[-2] not in ".!?":
            return None
        inside=text[1:-2]
        match=re.fullmatch(
            r"\s*([^\s,.;!?]+)\s+([^\s,.;!?]+)\s+"
            r"([^\s,.;!?]+)\s+([^\s,.;!?]+)\s*",
            inside,
        )
        if not match:
            return None
        words=[inside[match.start(k):match.end(k)] for k in (1,2,3,4)]
        # English demonstratives are a productive lexical class, not one
        # hardcoded literary expression. The grammar must still prove NP.
        if words[0].casefold() not in ("that","this","these","those"):
            return None
        return tuple((1+match.start(k),1+match.end(k))
                     for k in (1,2,3,4))

    def _compose_modal_ellipsis_response(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        spans=self._modal_ellipsis_plan(text,components)
        if spans is None:
            return None
        total_items=parser.max_items if max_items is None else max_items
        work=500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items<1000 or work<1000:
            return None
        budget_items,budget_work=total_items//5,work//5
        proofs: list[ParseResult]=[]
        candidates: list[LexicalCandidate]=[]
        for category,(a,b) in zip(("NP","NP","ADV","MODAL"),spans):
            source=text[a:b]
            lexical=parser._lattice_for_text(source)
            parsed=parser._vector_grammar.parse_lattice(
                lexical,goal_category=category,
                max_items=budget_items,kbest_work_limit=budget_work,
                diagnostic_k=diagnostic_k,
                beam=parser.beam if beam is None else beam,
            )
            if not parsed.completed or parsed.best() is None:
                return None
            best=parsed.best()
            if best.category!=category:
                return None
            proofs.append(parsed)
            candidates.append(LexicalCandidate(
                span_start=a,span_end=b,surface=source,
                lemma=f"<verified-{category.lower()}>",
                category=category,features=best.features,
                source="source-structural-grammar-proof",
                score=best.score,
                provenance={
                    "source_span":[a,b],
                    "grammar_proof_rule":best.rule_id,
                    "ellipsis_reference":"unresolved_source_antecedent"
                    if category=="MODAL" else None,
                },
                interface=SegmentInterface(parsed,a,a,b),
            ))
        stop=len(text)-2
        for pos,category in (
            (0,"OPEN-QUOTE"),(stop,"SPEECH-STOP"),
            (len(text)-1,"CLOSE-QUOTE"),
        ):
            candidates.append(LexicalCandidate(
                span_start=pos,span_end=pos+1,surface=text[pos],
                lemma=text[pos],category=category,
                features=FeatureStructure.empty(),score=0,
                source="dialogue-delimiter",
                provenance={"original_source_position":pos},
            ))
        graph=LexicalLattice(
            text=text,tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        assembled=self._vector.parse_lattice(
            graph,goal_category="CLAUSE",
            max_items=total_items-budget_items*4,
            kbest_work_limit=work-budget_work*4,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        if not assembled.completed or assembled.best() is None:
            return None
        if isinstance(assembled.stats,dict):
            assembled.stats.update({
                "engine":"vector-structural-modal-vp-ellipsis",
                "structural_composition":True,
                "structural_composition_kind":"topical_modal_vp_ellipsis",
                "source_text_unchanged":True,
                "dialogue_scoped":True,
                "structural_clause_count":1,
                "structural_segment_count":4,
                "structural_segment_spans":[list(s) for s in spans],
                "structural_segment_rule_ids":[p.best().rule_id for p in proofs],
                "source_punctuation_spans":[[0,1],[stop,stop+1],
                                            [len(text)-1,len(text)]],
                "elided_vp_lexical_content_inserted":False,
                "discourse_antecedent_resolved":False,
                "discourse_antecedent_policy":
                    "needs_prior_discourse_for_modal_vp_ellipsis",
                "max_items_total_across_segments":total_items,
                "kbest_work_limit_total_across_segments":work,
                "composition_linguistic_proof":
                    "grammatically_verified_topical_np_subject_np_"
                    "adverb_and_finite_modal_with_unresolved_vp_ellipsis",
            })
        assembled.shared_forest={
            "assembly":assembled.shared_forest,
            "segments":tuple(p.shared_forest for p in proofs),
            "interfaces":tuple(c.interface for c in candidates
                               if c.interface is not None),
        }
        return assembled
