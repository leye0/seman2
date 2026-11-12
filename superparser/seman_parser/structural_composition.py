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
            return self._compose_nested_nominal_title(
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
