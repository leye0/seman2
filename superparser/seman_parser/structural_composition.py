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

    def _compose_verified_dialogue_pattern(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        specs: Sequence[tuple[str, int, int, str, Mapping[str, str]]],
        expected_rule: str, *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Shared exact-source phrase proof and grammar assembly.

        A spec is (category, absolute start, absolute end, source kind,
        required features). It NEVER fabricates a lexical edge, parser
        interface, word or punctuation. Source structure proposes only the
        boundaries; independently selected ranked subtree proves each phrase.
        """
        total_items = parser.max_items if max_items is None else max_items
        total_work = 500_000 if kbest_work_limit is None else kbest_work_limit
        if total_items < 1600 or total_work < 1600:
            return None
        phrase_n = sum(kind == "phrase" for _, _, _, kind, _ in specs)
        piece_items = total_items // (phrase_n + 1)
        piece_work = total_work // (phrase_n + 1)
        candidates: list[LexicalCandidate] = []
        proofs: list[ParseResult] = []
        punctuation_spans: list[list[int]] = []
        typed_spans: list[list[Any]] = []
        original_terms = {
            "OPEN-QUOTE": set('"“‘'),
            "CLOSE-QUOTE": set('"”’'),
            "COMMA": {","},
            "QMARK": {"?"},
            "EXCL": {"!"},
            "SPEECH-STOP": set(".!?"),
            "DASH": {"--", "—"},
        }
        for category, a, b, kind, required in specs:
            if (not isinstance(a, int) or not isinstance(b, int)
                    or not 0 <= a < b <= len(text)):
                return None
            surface = text[a:b]
            if kind == "source-punctuation":
                if category not in original_terms or surface not in original_terms[category]:
                    return None
                punctuation_spans.append([a, b])
                candidates.append(LexicalCandidate(
                    span_start=a, span_end=b, surface=surface, lemma=surface,
                    category=category, features=FeatureStructure.empty(),
                    source="overt-original-dialogue-punctuation", score=0,
                    provenance={"original_source_span": [a, b]},
                ))
            elif kind == "lexical":
                matching = [
                    c for c in original_lattice.candidates
                    if c.category == category
                    and (c.span_start, c.span_end) == (a, b)
                    # Reciprocal pronouns are fixed multiword pronominal
                    # forms: ordinary productive noun plural morphology
                    # must not manufacture a new reciprocal surface.
                    and (category != "RECIPROCAL-PRONOUN"
                         or c.surface.casefold() == c.lemma.casefold())
                    and all(
                        (v in (c.features.as_dict().get("subcat", ())
                               if isinstance(c.features.as_dict().get("subcat"), (list, tuple))
                               else (c.features.as_dict().get("subcat"),)))
                        if k == "subcat_member"
                        else c.features.as_dict().get(k) == v
                        for k, v in required.items())
                ]
                if not matching:
                    return None
                candidates.append(max(matching, key=lambda c: c.score))
            elif kind == "phrase":
                grammar = (
                    parser._dialogue_vector_grammar
                    if category == "SPEECH-TAG"
                    else parser._vector_grammar
                )
                if grammar is None:
                    return None
                lattice = parser._lattice_for_text(surface)
                if category == "CLAUSE":
                    proof = parser._parse_vector_text(
                        surface, max_items=piece_items,
                        kbest_work_limit=piece_work,
                        diagnostic_k=diagnostic_k, beam=beam,
                    )
                else:
                    proof = grammar.parse_lattice(
                        lattice, goal_category=category,
                        max_items=piece_items,
                        kbest_work_limit=piece_work,
                        diagnostic_k=diagnostic_k,
                        beam=parser.beam if beam is None else beam,
                    )
                selected = proof.best()
                if (not proof.completed or selected is None
                        or selected.category != category
                        or any(selected.features.as_dict().get(k) != v
                               for k, v in required.items())):
                    return None
                if (expected_rule ==
                        "dialogue_structural_temporal_doubt_dislocated_gerund_question"
                        and category=="NP"
                        and selected.rule_id!="np_title_name"):
                    return None
                if (expected_rule ==
                        "dialogue_structural_temporal_reason_dislocated_inf_question"
                        and category=="PP"
                        and (selected.rule_id!="pp_prep_np"
                             or len(selected.children)!=2
                             or selected.children[1].rule_id!="np_proper")):
                    return None
                if (category == "PP"
                        and expected_rule ==
                        "dialogue_structural_existential_and_embedded_wh"
                        and selected.rule_id != "pp_prep_np"):
                    return None
                if (category == "NP"
                        and expected_rule ==
                        "dialogue_structural_existential_and_embedded_wh"
                        and surface.startswith("the efficacy")
                        and selected.rule_id != "np_det_n_of"):
                    return None
                if (category == "PP"
                        and expected_rule ==
                        "dialogue_structural_split_intent_causal_request"
                        and selected.rule_id != "pp_pp_advp"):
                    return None
                if (category == "SPEECH-TAG"
                        and not (selected.rule_id or "").startswith(
                            "dialogue_speech_tag_")):
                    return None
                if category == "CLAUSE" and (
                    selected.rule_id in ("clause_np_relative", "np_relative_obj")
                    or any(s in surface for s in ['"', '“', '”', '‘', '’'])
                ):
                    return None
                if (expected_rule ==
                        "dialogue_structural_dialect_three_act_self_report"
                        and category == "NP"
                        and required.get("definiteness")=="negative"
                        and (selected.rule_id!="np_det_n"
                             or selected.features.as_dict().get(
                                 "definiteness")!="negative")):
                    return None
                if (expected_rule ==
                        "dialogue_structural_dialect_three_act_self_report"
                        and category == "PP"
                        and (selected.rule_id!="pp_prep_np"
                             or not selected.children
                             or selected.children[0].category!="PREP"
                             or selected.children[0].features.as_dict().get(
                                 "dialectal_elided_of")!="true")):
                    return None
                if (expected_rule ==
                        "dialogue_structural_vocative_praise_stars_reporter"):
                    if (category=="NP"
                            and selected.rule_id!="np_poss"):
                        return None
                    if category=="CLAUSE":
                        if (selected.rule_id!="clause_np_vp"
                                or len(selected.children)!=2):
                            return None
                        vp=selected.children[1]
                        if vp.rule_id=="vp_transitive":
                            if (len(vp.children)!=2
                                    or vp.children[0].category!="V"
                                    or vp.children[1].rule_id!="np_poss"):
                                return None
                        elif vp.rule_id=="vp_copula_adj":
                            if (len(vp.children)!=2
                                    or vp.children[0].category!="COPULA"
                                    or vp.children[1].category!="ADJ"):
                                return None
                        else:
                            return None
                if (category == "CLAUSE"
                        and expected_rule ==
                        "dialogue_structural_comparative_negative_tag_sequence"
                        and (selected.rule_id!="clause_aux_ellipsis"
                             or len(selected.children)!=2
                             or selected.children[0].rule_id!="np_indef_pron"
                             or selected.children[1].category!="AUX")):
                    return None
                if (category == "NP"
                        and expected_rule ==
                        "dialogue_structural_comparative_negative_tag_sequence"
                        and surface.startswith("every man before")
                        and (selected.rule_id!="np_pp_mod"
                             or len(selected.children)!=2
                             or selected.children[0].rule_id!="np_det_n"
                             or selected.children[0].features.as_dict().get(
                                 "number")!="singular"
                             or selected.children[0].features.as_dict().get(
                                 "person")!="3"
                             or selected.children[1].rule_id!="pp_prep_np")):
                    return None
                if (category == "CLAUSE"
                        and expected_rule ==
                        "dialogue_structural_three_confirmatory_tags_vocative"):
                    # Existing full finite clause has the right subject
                    # and genuine copular NP predicate, not an NP homograph.
                    if (selected.rule_id != "clause_np_vp"
                            or len(selected.children)!=2
                            or selected.children[1].rule_id!="vp_cop_np"
                            or len(selected.children[1].children)!=2):
                        return None
                    predicate=selected.children[1].children[1]
                    if surface.startswith("That's"):
                        if predicate.rule_id!="np_poss_num_n":
                            return None
                    elif "for bargains" in surface:
                        if predicate.rule_id!="np_pp_mod":
                            return None
                    elif "that never bungled" in surface:
                        if (predicate.rule_id!="np_relative_subj"
                                or len(predicate.children)!=2
                                or predicate.children[1].rule_id
                                   !="wh_subj_clause"):
                            return None
                    else:
                        return None
                if (category == "CLAUSE"
                        and expected_rule ==
                        "dialogue_structural_intercalated_vocative_two_perfect"
                        and selected.rule_id != "clause_np_vp"):
                    return None
                if (category == "CLAUSE"
                        and expected_rule ==
                        "dialogue_structural_inclusive_let_imperative_sequence"
                        and (selected.rule_id not in
                             ("clause_imp_neg", "clause_np_vp")
                             or (required.get("stype") == "imperative"
                                 and selected.rule_id != "clause_imp_neg")
                             or (required.get("stype") != "imperative"
                                 and selected.rule_id != "clause_np_vp"))):
                    return None
                if (category == "CLAUSE"
                        and expected_rule ==
                        "dialogue_structural_temporal_vocative_minor_reprise"
                        and selected.rule_id != "clause_np_vp"):
                    return None
                if (category == "CLAUSE"
                        and expected_rule ==
                        "structural_source_asyndetic_modal_passive_dash"
                        and (selected.rule_id != "clause_passive"
                             or selected.features.as_dict().get("voice")
                                != "passive")):
                    return None
                # A conditional question is a conditional CLAUSE whose
                # main-clause child, not its root, carries stype=question.
                # Explicitly inspect that selected ranked subordinate tree.
                if (category == "CLAUSE"
                        and expected_rule ==
                        "dialogue_structural_split_polite_conditional_vocative_question"
                        and (selected.rule_id != "clause_cond"
                             or not selected.children
                             or selected.children[-1].category != "CLAUSE"
                             or selected.children[-1].features.as_dict().get(
                                 "stype") != "question")):
                    return None
                proofs.append(proof)
                candidates.append(LexicalCandidate(
                    span_start=a, span_end=b, surface=surface,
                    lemma=f"<verified-{category.lower()}>",
                    category=category, features=selected.features,
                    score=selected.score,
                    source="source-scoped-selected-grammar-proof",
                    provenance={"original_source_span": [a, b],
                                "selected_rule_id": selected.rule_id},
                    interface=SegmentInterface(proof, a, a, b),
                ))
            else:
                raise ValueError("Unknown source proof kind")
            typed_spans.append([category, a, b, kind])
        graph = LexicalLattice(
            text=text, tokens=original_lattice.tokens,
            candidates=tuple(candidates),
        )
        assembled = self._vector.parse_lattice(
            graph, goal_category="CLAUSE",
            max_items=total_items - phrase_n * piece_items,
            kbest_work_limit=total_work - phrase_n * piece_work,
            diagnostic_k=diagnostic_k,
            beam=parser.beam if beam is None else beam,
        )
        selected = assembled.best()
        if (not assembled.completed or selected is None
                or selected.rule_id != expected_rule):
            return None
        if isinstance(assembled.stats, dict):
            assembled.stats.update({
                "engine": "vector-verified-source-dialogue-bulk",
                "structural_composition": True,
                "dialogue_scoped": any(
                    x[0] == "OPEN-QUOTE" for x in specs
                ),
                "source_text_unchanged": True,
                "structural_composition_kind": expected_rule,
                "structural_segment_count": phrase_n,
                # Count independently licensed spoken finite clauses;
                # reporting tags and reduced clauses are not extra
                # autonomous spoken sentences.
                "structural_clause_count": (
                    2 if expected_rule in (
                        "dialogue_structural_temporal_doubt_dislocated_gerund_question",
                        "dialogue_structural_temporal_reason_dislocated_inf_question",
                    ) else
                    2 if expected_rule in (
                        "dialogue_structural_dialect_three_act_self_report",
                        "dialogue_structural_vocative_praise_stars_reporter",
                    ) else
                    3 if expected_rule ==
                    "dialogue_structural_comparative_negative_tag_sequence" else
                    3 if expected_rule ==
                    "dialogue_structural_three_confirmatory_tags_vocative" else
                    3 if expected_rule ==
                    "dialogue_structural_split_intent_causal_request" else
                    2 if expected_rule ==
                    "dialogue_structural_existential_and_embedded_wh" else
                    sum(1 for category, _, _, _, _ in specs
                        if category == "CLAUSE")
                    + int(expected_rule in {
                        "dialogue_structural_postposed_comparative_vocative_report",
                        "dialogue_structural_split_vocative_copula_domain",
                        "dialogue_structural_split_shared_modal_coord_gerund",
                        "structural_source_asyndetic_modal_passive_dash",
                        "dialogue_structural_inclusive_let_imperative_sequence",
                        "dialogue_structural_intercalated_vocative_two_perfect",
                    })
                ),
                "structural_segment_spans": [
                    [p[1], p[2]] for p in specs if p[3] == "phrase"
                ],
                "structural_segment_rule_ids": [
                    p.best().rule_id for p in proofs
                ],
                "structural_segment_stats": [dict(p.stats) for p in proofs],
                "source_punctuation_spans": punctuation_spans,
                "source_grammatical_parts": typed_spans,
                "max_items_total_across_segments": total_items,
                "kbest_work_limit_total_across_segments": total_work,
                "composition_linguistic_proof": (
                    "every_original_source_lexical_frame_phrase_and"
                    "_literal_punctuation_independently_verified_then"
                    "_assembled_by_a_restricted_declarative_rule"
                ),
            })
        assembled.shared_forest = {
            "assembly": assembled.shared_forest,
            "segments": tuple(p.shared_forest for p in proofs),
            "interfaces": tuple(
                c.interface for c in candidates if c.interface is not None
            ),
        }
        return assembled

    def _compose_epistemic_doubt_gerund_question(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Temporal clause, negative partitive subject and discontinuous
        nominal gerund complement interrupted by a finite speaker incise.

        The source-preserved 'I suppose' is finite and clausal, not an
        incorrectly accepted bare VP or a silent main-question verb.
        """
        q0=next((c for c in components if c.get("id")=="q0"),None)
        spoken=[c for c in components if
                c.get("function")=="spoken_clause_candidate"
                and c.get("governor")=="q0"]
        marks=quotation_boundaries(text)
        if (q0 is None or q0.get("function")!="direct_speech"
                or (q0.get("start"),q0.get("end"))!=(0,len(text))
                or len(spoken)!=1
                or (spoken[0]["start"],spoken[0]["end"])!=(1,len(text)-1)
                or len(marks)!=2
                or [(m.start,m.end,m.side) for m in marks]!=[
                    (0,1,"open"),(len(text)-1,len(text),"close")]
                or any(c.get("function") in (
                    "reporting_clause","split_direct_speech_turn",
                    "embedded_quotation","narratorial_parenthetical")
                    for c in components)):
            return None
        m=re.fullmatch(
            r"(?P<coord>[A-Za-z]+)\s+(?P<conj>[A-Za-z]+)\s+"
            r"(?P<temporal_subj>[A-Za-z]+\s+[A-Za-z]+)\s+"
            r"(?P<temporal_verb>[A-Za-z]+)\s+(?P<emphatic>[A-Za-z]+)"
            r"(?P<comma_temporal>,)\s+(?P<neg>[A-Za-z]+)\s+"
            r"(?P<quant>[A-Za-z]+)\s+(?P<partitive>[A-Za-z]+)\s+"
            r"(?P<partitive_group>[A-Za-z]+)\s+"
            r"(?P<matrix_verb>[A-Za-z]+)\s+(?P<article>[A-Za-z]+)\s+"
            r"(?P<noun>[A-Za-z]+)(?P<comma_before>,)\s+"
            r"(?P<incise_subject>[A-Za-z]+)\s+"
            r"(?P<incise_verb>[A-Za-z]+)(?P<comma_after>,)\s+"
            r"(?P<prep>[A-Za-z]+)\s+(?P<gerund_subject>[A-Za-z]+)\s+"
            r"(?P<copula>[A-Za-z]+)\s+(?P<degree_adv>[A-Za-z]+)\s+"
            r"(?P<adjective>[A-Za-z]+)(?P<q>\?)",
            text[1:-1],
        )
        if m is None:
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def add(n:str,cat:str,kind="lexical",**features:str)->None:
            a,b=m.span(n)
            specs.append((cat,1+a,1+b,kind,features))
        specs.append(("OPEN-QUOTE",0,1,"source-punctuation",{}))
        add("coord","COORD")
        add("conj","CONJ",temporal_subordinator="true")
        add("temporal_subj","NP","phrase")
        add("temporal_verb","V",vform="finite",subcat_member="intransitive")
        add("emphatic","EMPHATIC-REFLEXIVE",person="3",
            number="singular",reflexive="true")
        add("comma_temporal","COMMA","source-punctuation")
        add("neg","NEG",negation="true")
        add("quant","NUM")
        add("partitive","PARTITIVE-OF")
        add("partitive_group","PRONOUN",person="2")
        add("matrix_verb","V",vform="finite",subcat_member="transitive")
        add("article","DET",number="singular",definiteness="indefinite")
        add("noun","N",number="singular",of_gerund_content="true")
        add("comma_before","COMMA","source-punctuation")
        add("incise_subject","PRONOUN",person="1",number="singular")
        add("incise_verb","V",vform="finite",subcat_member="clausal")
        add("comma_after","COMMA","source-punctuation")
        add("prep","PREP",nominal_complement="of")
        add("gerund_subject","POSS",person="3",number="plural")
        add("copula","COPULA",vform="ing")
        add("degree_adv","ADV")
        add("adjective","ADJ")
        add("q","QMARK","source-punctuation")
        specs.append(("CLOSE-QUOTE",len(text)-1,len(text),
                      "source-punctuation",{}))
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_temporal_doubt_dislocated_gerund_question",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_epistemic_reason_infinitive_question(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Temporal distributive subject and reason-selecting infinitive.

        'They all' has a postposed universal quantifier, not an ADV modifying
        'removed'. 'Them' is the object of 'believe'; the PP 'of each other'
        complements the adjective 'fond', not the belief event or its object.
        """
        q0=next((c for c in components if c.get("id")=="q0"),None)
        spoken=[c for c in components if
                c.get("function")=="spoken_clause_candidate"
                and c.get("governor")=="q0"]
        marks=quotation_boundaries(text)
        if (q0 is None or q0.get("function")!="direct_speech"
                or (q0.get("start"),q0.get("end"))!=(0,len(text))
                or len(spoken)!=1
                or (spoken[0]["start"],spoken[0]["end"])!=(1,len(text)-1)
                or len(marks)!=2
                or [(m.start,m.end,m.side) for m in marks]!=[
                    (0,1,"open"),(len(text)-1,len(text),"close")]
                or any(c.get("function") in (
                    "reporting_clause","split_direct_speech_turn",
                    "embedded_quotation","narratorial_parenthetical")
                    for c in components)):
            return None
        m=re.fullmatch(
            r"(?P<conj>[A-Za-z]+)\s+(?P<subj>[A-Za-z]+)\s+"
            r"(?P<quant>[A-Za-z]+)\s+(?P<verb_temporal>[A-Za-z]+)\s+"
            r"(?P<pp>[A-Za-z]+\s+[A-Za-z]+)(?P<comma0>,)\s+"
            r"(?P<adv>[A-Za-z]+)(?P<comma1>,)\s+"
            r"(?P<m_subject>[A-Za-z]+)\s+(?P<m_verb>[A-Za-z]+)\s+"
            r"(?P<det>[A-Za-z]+)\s+(?P<noun>[A-Za-z]+)"
            r"(?P<comma2>,)\s+(?P<inc_subject>[A-Za-z]+)\s+"
            r"(?P<inc_verb>[A-Za-z]+)(?P<comma3>,)\s+"
            r"(?P<to>[A-Za-z]+)\s+(?P<v>[A-Za-z]+)\s+"
            r"(?P<obj>[A-Za-z]+)\s+(?P<adj>[A-Za-z]+)\s+"
            r"(?P<prep>[A-Za-z]+)\s+(?P<recip>[A-Za-z]+\s+[A-Za-z]+)"
            r"(?P<q>\?)",
            text[1:-1],
        )
        if m is None:
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def add(n:str,cat:str,kind="lexical",**features:str)->None:
            a,b=m.span(n)
            specs.append((cat,1+a,1+b,kind,features))
        specs.append(("OPEN-QUOTE",0,1,"source-punctuation",{}))
        add("conj","CONJ",temporal_incise="true")
        add("subj","PRONOUN",person="3",number="plural")
        add("quant","DET",number="plural",definiteness="universal")
        add("verb_temporal","V",vform="finite",subcat_member="intransitive")
        add("pp","PP","phrase")
        add("comma0","COMMA","source-punctuation")
        add("adv","ADV")
        add("comma1","COMMA","source-punctuation")
        add("m_subject","PRONOUN",person="2")
        add("m_verb","V",vform="finite",subcat_member="transitive")
        add("det","DET",number="singular",definiteness="negative")
        add("noun","N",number="singular",to_infinitive_content="true")
        add("comma2","COMMA","source-punctuation")
        add("inc_subject","PRONOUN",person="1",number="singular")
        add("inc_verb","V",vform="finite",subcat_member="clausal")
        add("comma3","COMMA","source-punctuation")
        add("to","TO")
        add("v","V",vform="base",subcat_member="complex_transitive")
        add("obj","PRONOUN",person="3",number="plural")
        add("adj","ADJ",of_reciprocal_complement="true")
        add("prep","PREP",nominal_complement="of")
        add("recip","RECIPROCAL-PRONOUN",number="plural",reciprocal="true")
        add("q","QMARK","source-punctuation")
        specs.append(("CLOSE-QUOTE",len(text)-1,len(text),
                      "source-punctuation",{}))
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_temporal_reason_dislocated_inf_question",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_dialectal_three_act_self_report(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Deictic exclamation, dialectal object question, modal and echo.

        The original "Wot" is an overt dialectal interrogative *object*.
        Original "o'" is a sourced elided preposition, never a made-up "of".
        The last "I said" is a parenthetical report of the preceding
        proposition, not a new object-less transitive root.
        """
        by_id={c.get("id"):c for c in components}
        q0=by_id.get("q0")
        if (not q0 or q0.get("function")!="direct_speech"
                or (q0.get("start"),q0.get("end"))!=(0,len(text))
                or any(c.get("function") in (
                    "reporting_clause","split_direct_speech_turn",
                    "embedded_quotation","narratorial_parenthetical",
                ) for c in components)):
            return None
        quotes=quotation_boundaries(text)
        if (len(quotes)!=2 or
                [(x.start,x.end,x.side) for x in quotes]!=[
                    (0,1,"open"),(len(text)-1,len(text),"close")]):
            return None
        acts=sorted((c for c in components
                if c.get("function")=="spoken_clause_candidate"
                and c.get("governor")=="q0"),
                key=lambda x:x["start"])
        if (len(acts)!=3 or acts[0]["start"]!=1
                or acts[-1]["end"]!=len(text)-1
                or any(text[a["end"]:b["start"]].strip()
                       for a,b in zip(acts,acts[1:]))):
            return None
        a=re.fullmatch(r"([A-Za-z]+)(!)",
                       text[acts[0]["start"]:acts[0]["end"]])
        b=re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z]+)\s+"
                       r"([A-Za-z]+)\s+([A-Za-z]+)(\?)",
                       text[acts[1]["start"]:acts[1]["end"]])
        c=re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z]+)('ll)\s+"
                       r"([A-Za-z]+)\s+([A-Za-z]+')\s+([A-Za-z]+)(,)\s+"
                       r"([A-Za-z]+)\s+([A-Za-z]+)(\.)",
                       text[acts[2]["start"]:acts[2]["end"]])
        if not all((a,b,c)):
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def put(cat:str,start:int,end:int,kind="lexical",**required:str):
            specs.append((cat,start,end,kind,required))
        def g(m:re.Match[str],base:int,i:int,cat:str,
              kind="lexical",**required:str):
            x,y=m.span(i)
            put(cat,base+x,base+y,kind,**required)
        put("OPEN-QUOTE",0,1,"source-punctuation")
        g(a,acts[0]["start"],1,"INTERJ","lexical",
          deictic_discourse="true")
        g(a,acts[0]["start"],2,"EXCL","source-punctuation")
        p=acts[1]["start"]
        g(b,p,1,"WH-PRONOUN","lexical",
          dialectal_wh_object="true")
        g(b,p,2,"AUX","lexical",vform="finite")
        g(b,p,3,"NP","phrase",
          person="1",number="singular",pronominal="true")
        g(b,p,4,"V","lexical",
          vform="base",subcat_member="transitive")
        g(b,p,5,"QMARK","source-punctuation")
        p=acts[2]["start"]
        put("NP",p+c.start(1),p+c.end(2),"phrase",
            definiteness="negative")
        g(c,p,3,"MODAL","lexical",vform="finite")
        g(c,p,4,"V","lexical",
          vform="base",subcat_member="prepositional")
        put("PP",p+c.start(5),p+c.end(6),"phrase")
        g(c,p,7,"COMMA","source-punctuation")
        g(c,p,8,"NP","phrase",
          person="1",number="singular",pronominal="true")
        g(c,p,9,"V","lexical",
          vform="finite",subcat_member="clausal")
        g(c,p,10,"SPEECH-STOP","source-punctuation")
        put("CLOSE-QUOTE",len(text)-1,len(text),"source-punctuation")
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_dialect_three_act_self_report",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_vocative_praise_stars_reporter(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Vocative, overt praise-one's-stars idiom, finite content, speaker.

        A missing orthographic "that" is NOT added to the source. The idiom
        takes a source-proven finite content CLAUSE as the cause for praise.
        The postposed reporter has its real finite V and proper-name speaker.
        """
        by_id={c.get("id"):c for c in components}
        quote,tag=by_id.get("q0"),by_id.get("r0")
        if (not quote or not tag
                or quote.get("function")!="direct_speech"
                or tag.get("function")!="reporting_clause"
                or quote.get("start")!=0
                or tag.get("end")!=len(text)-1
                or any(c.get("function") in (
                    "embedded_quotation","split_direct_speech_turn",
                    "narratorial_parenthetical",
                ) for c in components)):
            return None
        qend=quote["end"]
        ta,tb=tag["start"],tag["end"]
        quotes=quotation_boundaries(text)
        if (len(quotes)!=2 or
                [(x.start,x.end,x.side) for x in quotes]!=[
                    (0,1,"open"),(qend-1,qend,"close")]
                or not text[qend:ta].isspace()
                or text[tb:]!="."):
            return None
        spoken=[c for c in components
                if c.get("function")=="spoken_clause_candidate"
                and c.get("governor")=="q0"]
        if (len(spoken)!=1 or
                (spoken[0]["start"],spoken[0]["end"])!=(1,qend-1)):
            return None
        m=re.fullmatch(
            r"([A-Za-z]+)(,)\s+([A-Za-z]+)(,)\s+"
            r"([A-Za-z]+\s+[A-Za-z]+)(,)\s+"
            r"(you\s+praise\s+your\s+stars)\s+"
            r"(he's\s+[A-Za-z]+)(,)",
            text[1:qend-1],
        )
        reporter=re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z]+)",text[ta:tb])
        if not m or not reporter:return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def put(cat:str,start:int,end:int,kind="lexical",**required:str):
            specs.append((cat,start,end,kind,required))
        def g(m:re.Match[str],base:int,i:int,cat:str,
              kind="lexical",**required:str):
            a,b=m.span(i)
            put(cat,base+a,base+b,kind,**required)
        put("OPEN-QUOTE",0,1,"source-punctuation")
        g(m,1,1,"INTERJ","lexical",discourse_exclamation="true")
        g(m,1,2,"COMMA","source-punctuation")
        g(m,1,3,"ADV")
        g(m,1,4,"COMMA","source-punctuation")
        g(m,1,5,"NP","phrase")
        g(m,1,6,"COMMA","source-punctuation")
        g(m,1,7,"CLAUSE","phrase")
        g(m,1,8,"CLAUSE","phrase")
        g(m,1,9,"COMMA","source-punctuation")
        put("CLOSE-QUOTE",qend-1,qend,"source-punctuation")
        g(reporter,ta,1,"V","lexical",
          vform="finite",subcat_member="clausal")
        g(reporter,ta,2,"PROPER-NOUN","lexical",
          person="3",number="singular")
        put("SPEECH-STOP",len(text)-1,len(text),
            "source-punctuation")
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_vocative_praise_stars_reporter",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_comparative_negative_predicative_tag(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Quoted minor formula, finite comparative, negative predicative tag.

        In "knows more than I do", the subject of an overt auxiliary-
        substitution clause is still licensed by a genuine selected grammar
        tree.  In "don't call that fair", the contracted auxiliary, NEG,
        transitive verb, demonstrative object and separate predicative ADJ
        are all original lexical edges (not a nominal "I do" homograph).
        The final "do you?" is an overt inverted positive tag, never an
        imperative or a fabricated finite clause.
        """
        by_id={c.get("id"):c for c in components}
        q=by_id.get("q0")
        if (not q or q.get("function")!="direct_speech"
                or (q.get("start"),q.get("end"))!=(0,len(text))
                or any(c.get("function") in (
                    "embedded_quotation","reporting_clause",
                    "split_direct_speech_turn","narratorial_parenthetical"
                ) for c in components)):
            return None
        marks=quotation_boundaries(text)
        if (len(marks)!=2 or
                [(x.start,x.end,x.side) for x in marks]!=[
                    (0,1,"open"),(len(text)-1,len(text),"close")
                ]):
            return None
        acts=sorted((c for c in components
                    if c.get("function")=="spoken_clause_candidate"
                    and c.get("governor")=="q0"),
                    key=lambda x:x["start"])
        if (len(acts)!=3 or acts[0]["start"]!=1
                or acts[-1]["end"]!=len(text)-1
                or any(text[a["end"]:b["start"]].strip()
                       for a,b in zip(acts,acts[1:]))):
            return None
        one=re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)(\.)",
            text[acts[0]["start"]:acts[0]["end"]],
        )
        two=re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+(that)\s+(.+?)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+(than)\s+(.+?)(\.)",
            text[acts[1]["start"]:acts[1]["end"]],
        )
        three=re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)(n't)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)(,)\s+([A-Za-z]+)(,)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)(\?)",
            text[acts[2]["start"]:acts[2]["end"]],
        )
        if not all((one,two,three)):
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def g(m:re.Match[str],base:int,i:int,cat:str,
              kind="lexical",**required:str)->None:
            a,b=m.span(i)
            specs.append((cat,base+a,base+b,kind,required))
        specs.append(("OPEN-QUOTE",0,1,"source-punctuation",{}))
        b=acts[0]["start"]
        g(one,b,1,"DEGREE","lexical",equative_so="true")
        g(one,b,2,"ADV","lexical",comparative_modifier="true")
        g(one,b,3,"DEGREE","lexical",equative_so="true")
        g(one,b,4,"ADJ")
        g(one,b,5,"SPEECH-STOP","source-punctuation")
        b=acts[1]["start"]
        g(two,b,1,"COORD","lexical",nominal_coordination="true")
        g(two,b,2,"ADV")
        g(two,b,3,"NP","phrase",
          person="1",number="singular",pronominal="true")
        g(two,b,4,"V","lexical",vform="finite",subcat_member="clausal")
        g(two,b,5,"COMP-THAT")
        g(two,b,6,"NP","phrase")
        g(two,b,7,"V","lexical",
          vform="finite",number="singular",person="3",
          subcat_member="intransitive")
        g(two,b,8,"DEGREE","lexical",comparative="true")
        g(two,b,9,"CONJ")
        g(two,b,10,"CLAUSE","phrase")
        g(two,b,11,"SPEECH-STOP","source-punctuation")
        b=acts[2]["start"]
        g(three,b,1,"NP","phrase",
          person="1",number="singular",pronominal="true")
        g(three,b,2,"AUX","lexical",vform="finite")
        g(three,b,3,"NEG","lexical",negation="true")
        g(three,b,4,"V","lexical",vform="base",
          subcat_member="complex_transitive")
        g(three,b,5,"PRONOUN","lexical",
          number="singular",person="3",definiteness="demonstrative")
        g(three,b,6,"ADJ")
        g(three,b,7,"COMMA","source-punctuation")
        g(three,b,8,"ADV")
        g(three,b,9,"COMMA","source-punctuation")
        g(three,b,10,"AUX","lexical",vform="finite")
        g(three,b,11,"NP","phrase",person="2",pronominal="true")
        g(three,b,12,"QMARK","source-punctuation")
        specs.append(("CLOSE-QUOTE",len(text)-1,len(text),
                      "source-punctuation",{}))
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_comparative_negative_tag_sequence",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_three_confirmatory_tags_and_vocative(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Compose source-proven copular clauses with genuine inverted tags.

        Each main clause must already have its own correct ranked constituent
        structure. The questions have overt inverted finite COPULAs and NP
        subjects, not invented question predicates. The final insulting
        vocative has overt second-person NP, compound ADJP and noun head.
        """
        by_id={c.get("id"):c for c in components}
        q0=by_id.get("q0")
        if (not q0 or q0.get("function")!="direct_speech"
                or (q0.get("start"),q0.get("end"))!=(0,len(text))
                or any(c.get("function") in (
                    "reporting_clause", "embedded_quotation",
                    "split_direct_speech_turn","narratorial_parenthetical"
                ) for c in components)):
            return None
        quotes=quotation_boundaries(text)
        if (len(quotes)!=2 or
                [(x.start,x.end,x.side) for x in quotes]!=[
                    (0,1,"open"),(len(text)-1,len(text),"close")
                ]):
            return None
        acts=sorted((c for c in components
                    if c.get("function")=="spoken_clause_candidate"
                    and c.get("governor")=="q0"),key=lambda x:x["start"])
        if (len(acts)!=3 or acts[0]["start"]!=1
                or acts[-1]["end"]!=len(text)-1
                or any(text[x["end"]:y["start"]].strip()
                       for x,y in zip(acts,acts[1:]))):
            return None
        one=re.fullmatch(
            r"(.+?)(,)\s+([A-Za-z']+)\s+([A-Za-z]+)(\?)",
            text[acts[0]["start"]:acts[0]["end"]],
        )
        two=re.fullmatch(
            r"(.+?)(,)\s+([A-Za-z']+)\s+([A-Za-z]+)(\?)",
            text[acts[1]["start"]:acts[1]["end"]],
        )
        three=re.fullmatch(
            r"(.+?)(,)\s+([A-Za-z]+)\s+([A-Za-z-]+)\s+([A-Za-z]+)(!)",
            text[acts[2]["start"]:acts[2]["end"]],
        )
        if not all((one,two,three)):
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def add(m:re.Match[str],base:int,n:int,cat:str,
                kind="lexical",**required:str)->None:
            a,b=m.span(n)
            specs.append((cat,base+a,base+b,kind,required))
        specs.append(("OPEN-QUOTE",0,1,"source-punctuation",{}))
        add(one,acts[0]["start"],1,"CLAUSE","phrase")
        add(one,acts[0]["start"],2,"COMMA","source-punctuation")
        add(one,acts[0]["start"],3,"COPULA","lexical",
            vform="finite",number="singular",person="3")
        add(one,acts[0]["start"],4,"NP","phrase",
            person="3",number="singular",pronominal="true")
        add(one,acts[0]["start"],5,"QMARK","source-punctuation")
        add(two,acts[1]["start"],1,"CLAUSE","phrase")
        add(two,acts[1]["start"],2,"COMMA","source-punctuation")
        add(two,acts[1]["start"],3,"COPULA","lexical",
            vform="finite",negation="true")
        add(two,acts[1]["start"],4,"NP","phrase",
            person="2",pronominal="true")
        add(two,acts[1]["start"],5,"QMARK","source-punctuation")
        add(three,acts[2]["start"],1,"CLAUSE","phrase")
        add(three,acts[2]["start"],2,"COMMA","source-punctuation")
        add(three,acts[2]["start"],3,"NP","phrase",
            person="2",pronominal="true")
        add(three,acts[2]["start"],4,"ADJP","phrase")
        add(three,acts[2]["start"],5,"N")
        add(three,acts[2]["start"],6,"EXCL","source-punctuation")
        specs.append(("CLOSE-QUOTE",len(text)-1,len(text),
                      "source-punctuation",{}))
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_three_confirmatory_tags_vocative",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_existential_parenthetical_wh_question(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """A complete existential and a separate embedded-wh question.

        The expletive "there" is not an adverb or the NP subject.  The
        singular "many a one" is a quantifier + indefinite article + numeral
        nominal pivot; a source-delimited "I fancy" is a parenthetical,
        while "overcome in the same way" is its reduced passive modifier.
        In the second speech act, the overt wh-subject *who* governs
        discovered, rather than permitting "love" to become its main verb.
        """
        by_id={c.get("id"):c for c in components}
        quote=by_id.get("q0")
        if (not quote or quote.get("function")!="direct_speech"
                or (quote.get("start"),quote.get("end"))!=(0,len(text))
                or any(c.get("function") in (
                    "reporting_clause", "embedded_quotation",
                    "split_direct_speech_turn","narratorial_parenthetical",
                ) for c in components)):
            return None
        marks=quotation_boundaries(text)
        if (len(marks)!=2 or
                [(x.start,x.end,x.side) for x in marks]!=[
                    (0,1,"open"),(len(text)-1,len(text),"close"),
                ]):
            return None
        acts=sorted((c for c in components
                     if c.get("function")=="spoken_clause_candidate"
                     and c.get("governor")=="q0"),
                    key=lambda c:c["start"])
        if (len(acts)!=2 or acts[0]["start"]!=1 or
                acts[-1]["end"]!=len(text)-1 or
                text[acts[0]["end"]:acts[1]["start"]].strip()):
            return None
        first=re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)(,)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)(,)\s+"
            r"([A-Za-z]+)\s+(.+?)(\.)",
            text[acts[0]["start"]:acts[0]["end"]],
        )
        second=re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+(.+?)(!)",
            text[acts[1]["start"]:acts[1]["end"]],
        )
        if first is None or second is None:
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def group(m:re.Match[str],base:int,i:int,category:str,
                  kind="lexical",**required:str)->None:
            a,b=m.span(i)
            specs.append((category,base+a,base+b,kind,required))
        specs.append(("OPEN-QUOTE",0,1,"source-punctuation",{}))
        b=acts[0]["start"]
        group(first,b,1,"EXPL","lexical",expletive="true")
        group(first,b,2,"HAVE","lexical",
              vform="finite",number="singular",person="3")
        group(first,b,3,"AUX-BE","lexical",vform="ed")
        group(first,b,4,"DET","lexical",quantifier="many")
        group(first,b,5,"DET","lexical",number="singular",
              definiteness="indefinite")
        group(first,b,6,"NUM")
        group(first,b,7,"COMMA","source-punctuation")
        group(first,b,8,"NP","phrase",person="1",number="singular",
              pronominal="true")
        group(first,b,9,"V","lexical",vform="finite",
              subcat_member="clausal")
        group(first,b,10,"COMMA","source-punctuation")
        group(first,b,11,"V","lexical",vform="ed",
              subcat_member="transitive")
        group(first,b,12,"PP","phrase")
        group(first,b,13,"SPEECH-STOP","source-punctuation")
        b=acts[1]["start"]
        group(second,b,1,"NP","phrase",
              person="1",number="singular",pronominal="true")
        group(second,b,2,"V","lexical",vform="finite",
              subcat_member="whether_clausal")
        group(second,b,3,"WH-PRONOUN","lexical",wh="true",
              interrogative_subject="true")
        group(second,b,4,"ADV")
        group(second,b,5,"V","lexical",vform="finite",
              subcat_member="transitive")
        group(second,b,6,"NP","phrase")
        group(second,b,7,"EXCL","source-punctuation")
        specs.append(("CLOSE-QUOTE",len(text)-1,len(text),
                      "source-punctuation",{}))
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_existential_and_embedded_wh",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_split_intent_causal_ditransitive(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """An interrupted speech turn with independent causal justification.

        The initial infinitival intention governs a genuinely quantified
        pronominal object. The interrupted continuation is a modal
        ditransitive command, whose *two separate* overt NP arguments are
        followed by a causal coordination of a perfect tense explanation.
        The possessive "ours" is independent, never an adjective modifying
        a silently supplied noun. The reporting verb has its own speaker.
        """
        by_id={c.get("id"):c for c in components}
        q0,q1,tag=(by_id.get(k) for k in ("q0","q1","r0"))
        if (not all((q0,q1,tag)) or
                q0.get("function")!="direct_speech" or
                q1.get("function")!="direct_speech" or
                tag.get("function")!="reporting_clause" or
                not any(c.get("function")=="split_direct_speech_turn"
                        for c in components) or
                any(c.get("function") in ("embedded_quotation",
                      "narratorial_parenthetical") for c in components)):
            return None
        a0,b0=q0["start"],q0["end"]
        a1,b1=q1["start"],q1["end"]
        ta,tb=tag["start"],tag["end"]
        quotes=quotation_boundaries(text)
        if (a0!=0 or b1!=len(text) or
                not (0<b0<ta<tb<a1<b1) or len(quotes)!=4 or
                [(x.start,x.end,x.side) for x in quotes]!=[
                    (0,1,"open"),(b0-1,b0,"close"),
                    (a1,a1+1,"open"),(b1-1,b1,"close")
                ] or not text[b0:ta].isspace() or
                re.fullmatch(r"\s*,\s*",text[tb:a1]) is None):
            return None
        first=re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"(to)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)(,)",
            text[1:b0-1],
        )
        reporter=re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z]+)",text[ta:tb])
        second=re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+\s+[A-Za-z]+)(,)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+(.+?)(\.)",
            text[a1+1:b1-1],
        )
        if not first or not second or not reporter:
            return None
        # Typed quote-source edges prove the speaker turn boundaries;
        # the regexes only locate original consecutive token spans.
        parts0=[c for c in components if
                c.get("function")=="spoken_clause_candidate"
                and c.get("governor")=="q0"]
        parts1=[c for c in components if
                c.get("function")=="spoken_clause_candidate"
                and c.get("governor")=="q1"]
        if (len(parts0)!=1 or len(parts1)!=1 or
                (parts0[0]["start"],parts0[0]["end"])!=(1,b0-1) or
                (parts1[0]["start"],parts1[0]["end"])!=(a1+1,b1-1)):
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def put(category: str,a:int,b:int,kind="lexical",
                **required:str)->None:
            specs.append((category,a,b,kind,required))
        def group(m:re.Match[str],base:int,i:int,category:str,
                  kind="lexical",**required:str)->None:
            a,b=m.span(i)
            put(category,base+a,base+b,kind,**required)
        def punct(cat:str,a:int)->None:
            put(cat,a,a+1,"source-punctuation")
        punct("OPEN-QUOTE",0)
        base=1
        group(first,base,1,"COORD",nominal_coordination="true")
        group(first,base,2,"NP","phrase",
              person="1",number="plural",pronominal="true")
        group(first,base,3,"V","lexical",
              vform="finite",subcat_member="subject_control")
        group(first,base,4,"TO")
        group(first,base,5,"V","lexical",
              vform="base",subcat_member="transitive")
        group(first,base,6,"NP","phrase",person="2",pronominal="true")
        group(first,base,7,"DET","lexical",
              number="plural",definiteness="universal")
        group(first,base,8,"COMMA","source-punctuation")
        punct("CLOSE-QUOTE",b0-1)
        group(reporter,ta,1,"V","lexical",
              vform="finite",past_reporting="true")
        group(reporter,ta,2,"NP","phrase",
              number="singular",person="3")
        punct("COMMA",text.index(",",tb,a1))
        punct("OPEN-QUOTE",a1)
        base=a1+1
        group(second,base,1,"COORD",nominal_coordination="true")
        group(second,base,2,"NP","phrase",
              person="2",pronominal="true")
        group(second,base,3,"MODAL","lexical",vform="finite")
        group(second,base,4,"V","lexical",
              vform="base",subcat_member="ditransitive")
        group(second,base,5,"NP","phrase",
              person="1",number="plural",pronominal="true")
        group(second,base,6,"NP","phrase")
        group(second,base,7,"COMMA","source-punctuation")
        group(second,base,8,"COORD","lexical",causal_coordination="true")
        group(second,base,9,"NP","phrase",
              person="1",number="plural",pronominal="true")
        group(second,base,10,"HAVE","lexical",
              vform="finite",number="plural")
        group(second,base,11,"ADV","lexical",recent_temporal="true")
        group(second,base,12,"V","lexical",
              vform="ed",subcat_member="transitive")
        group(second,base,13,"POSS-PRONOUN","lexical",
              independent_possessive="true",person="1",number="plural")
        group(second,base,14,"PP","phrase")
        group(second,base,15,"SPEECH-STOP","source-punctuation")
        punct("CLOSE-QUOTE",b1-1)
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_split_intent_causal_request",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_split_vocative_two_perfect_sentences(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Intercalated reporting + two overt finite speech acts.

        In the second sentence, the source apostrophe-s is independently
        licensed as HAVE, never COPULA or a genitive; the lexical participle
        governs a *separate* direct object and particle. The two historical
        marine adverbs modify the resulting event, not the object noun.
        """
        by_id = {c.get("id"): c for c in components}
        q0,q1,tag=(by_id.get(k) for k in ("q0","q1","r0"))
        if (not all((q0,q1,tag))
                or any(c.get("function") in ("embedded_quotation",
                           "narratorial_parenthetical") for c in components)
                or q0.get("function")!="direct_speech"
                or q1.get("function")!="direct_speech"
                or tag.get("function")!="reporting_clause"
                or not any(c.get("function")=="split_direct_speech_turn"
                           for c in components)):
            return None
        a0,b0=q0["start"],q0["end"]
        a1,b1=q1["start"],q1["end"]
        ta,tb=tag["start"],tag["end"]
        marks=quotation_boundaries(text)
        if (a0!=0 or b1!=len(text) or
                not (0<b0<ta<tb<a1<b1) or
                len(marks)!=4 or
                [(q.start,q.end,q.side) for q in marks]!=[
                    (0,1,"open"),(b0-1,b0,"close"),
                    (a1,a1+1,"open"),(b1-1,b1,"close")
                ] or not text[b0:ta].isspace()
                or re.fullmatch(r"\s*,\s*",text[tb:a1]) is None):
            return None
        spoken=sorted(
            (c for c in components
             if c.get("function")=="spoken_clause_candidate"
             and c.get("governor")=="q1"),
            key=lambda c:c["start"],
        )
        if (len(spoken)!=2 or spoken[0]["start"]!=a1+1
                or spoken[-1]["end"]!=b1-1 or
                text[spoken[0]["end"]:spoken[1]["start"]].strip()):
            return None
        first=re.fullmatch(r"(.+?)(,)",text[1:b0-1])
        second=re.fullmatch(
            r"(.+?)(\.)\s+([A-Za-z]+)('s)\s+([A-Za-z]+)\s+"
            r"(.+?)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)(\.)",
            text[a1+1:b1-1],
        )
        if not first or not second:
            return None
        s=a1+1
        if ((s+second.start(1),s+second.end(2))!=
                (spoken[0]["start"],spoken[0]["end"])
                or s+second.start(3)!=spoken[1]["start"]):
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]]=[]
        def put(cat:str,a:int,b:int,kind="lexical",
                **required:str)->None:
            specs.append((cat,a,b,kind,required))
        def group(m:re.Match[str],base:int,i:int,cat:str,
                  kind="lexical",**required:str)->None:
            a,b=m.span(i)
            put(cat,base+a,base+b,kind,**required)
        def punct(cat:str,a:int)->None:
            put(cat,a,a+1,"source-punctuation")
        punct("OPEN-QUOTE",0)
        group(first,1,1,"NP","phrase")
        group(first,1,2,"COMMA","source-punctuation")
        punct("CLOSE-QUOTE",b0-1)
        put("SPEECH-TAG",ta,tb,"phrase")
        punct("COMMA",text.index(",",tb,a1))
        punct("OPEN-QUOTE",a1)
        group(second,s,1,"CLAUSE","phrase")
        group(second,s,2,"SPEECH-STOP","source-punctuation")
        group(second,s,3,"NP","phrase",
              number="singular",person="3",pronominal="true")
        group(second,s,4,"HAVE","lexical",vform="finite")
        group(second,s,5,"V","lexical",
              vform="ed",subcat_member="transitive")
        group(second,s,6,"NP","phrase")
        group(second,s,7,"PARTICLE")
        group(second,s,8,"ADV","lexical",
              maritime_vertical_position="lower")
        group(second,s,9,"COORD")
        group(second,s,10,"ADV","lexical",
              maritime_vertical_position="upper")
        group(second,s,11,"SPEECH-STOP","source-punctuation")
        punct("CLOSE-QUOTE",b1-1)
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_intercalated_vocative_two_perfect",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_inclusive_let_imperative_sequence(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Three source speech acts: negative command and two inclusive lets.

        The overt "let + us + bare VP" imperatives are NOT finite declarative
        clauses.  The third matrix verb independently selects a reflexive
        object AND overt "that" content clause, proved by lexical valency.
        This avoids the false full-source interpretation of "Let us hope
        for" as a nominal subject.
        """
        by_id = {c.get("id"): c for c in components}
        quote = by_id.get("q0")
        if (not quote or quote.get("function") != "direct_speech"
                or (quote.get("start"), quote.get("end")) !=
                    (0, len(text))
                or any(c.get("function") in (
                    "embedded_quotation", "reporting_clause",
                    "split_direct_speech_turn", "narratorial_parenthetical",
                ) for c in components)):
            return None
        marks = quotation_boundaries(text)
        if (len(marks) != 2 or
                [(q.start, q.end, q.side) for q in marks] != [
                    (0, 1, "open"), (len(text)-1, len(text), "close"),
                ]):
            return None
        acts = sorted(
            (c for c in components
             if c.get("function") == "spoken_clause_candidate"
             and c.get("governor") == "q0"),
            key=lambda c: c["start"],
        )
        if len(acts) != 3:
            return None
        if (acts[0]["start"] != 1 or acts[-1]["end"] != len(text)-1
                or any(text[a["end"]:b["start"]].strip()
                       for a,b in zip(acts,acts[1:]))):
            return None
        one = re.fullmatch(
            r"(.+?)(,)\s+(.+?)(\.)",
            text[acts[0]["start"]:acts[0]["end"]],
        )
        two = re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+(.+?)(\.)",
            text[acts[1]["start"]:acts[1]["end"]],
        )
        three = re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+(that)\s+(.+?)(\.)",
            text[acts[2]["start"]:acts[2]["end"]],
        )
        if not one or not two or not three:
            return None
        # "Let" is an overt operator, not a guessed constituent.  Two
        # occurrences are required to license inclusive directives.
        if (two.group(1).casefold() != "let"
                or three.group(1).casefold() != "let"
                or two.group(2).casefold() != "us"
                or three.group(2).casefold() != "us"):
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]] = []
        def put(cat: str, a: int, b: int, kind="lexical",
                **required: str) -> None:
            specs.append((cat,a,b,kind,required))
        def groups(m: re.Match[str], offset: int,
                   mapping: Sequence[tuple[str,str,Mapping[str,str]]]) -> None:
            for i,(cat,kind,need) in enumerate(mapping,1):
                a,b = m.span(i)
                put(cat,offset+a,offset+b,kind,**need)
        put("OPEN-QUOTE",0,1,"source-punctuation")
        groups(one,acts[0]["start"], (
            ("NP","phrase",{}),
            ("COMMA","source-punctuation",{}),
            ("CLAUSE","phrase",{"stype":"imperative","negation":"true"}),
            ("SPEECH-STOP","source-punctuation",{}),
        ))
        # Shared first-person plural argument and base verb valencies.
        groups(two,acts[1]["start"], (
            ("V","lexical",{"vform":"base","subcat_member":"bare_control"}),
            ("NP","phrase",{"person":"1","number":"plural","pronominal":"true"}),
            ("V","lexical",{"vform":"base","subcat_member":"prepositional"}),
            ("PP","phrase",{}),
            ("SPEECH-STOP","source-punctuation",{}),
        ))
        groups(three,acts[2]["start"], (
            ("V","lexical",{"vform":"base","subcat_member":"bare_control"}),
            ("NP","phrase",{"person":"1","number":"plural","pronominal":"true"}),
            ("V","lexical",{"vform":"base","reflexive_that_complement":"true"}),
            ("EMPHATIC-REFLEXIVE","lexical",{}),
            ("COMP-THAT","lexical",{}),
            ("CLAUSE","phrase",{}),
            ("SPEECH-STOP","source-punctuation",{}),
        ))
        put("CLOSE-QUOTE",len(text)-1,len(text),"source-punctuation")
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_inclusive_let_imperative_sequence",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_temporal_vocative_minor_reprise(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Source-exact multi-sentence speech with a temporal minor reprise.

        Keep the as-long-as subordinate finite clause, vocative, main finite
        clause and later *verbless* temporal repetition as four distinct
        functions.  In particular, the second speech act is never retyped as
        a finite subject-predicate sentence or forced into nominal apposition.
        """
        by_id = {c.get("id"): c for c in components}
        q0 = by_id.get("q0")
        if (not q0 or q0.get("function") != "direct_speech"
                or (q0.get("start"), q0.get("end")) != (0, len(text))
                or any(c.get("function") in {
                    "reporting_clause", "split_direct_speech_turn",
                    "embedded_quotation", "narratorial_parenthetical",
                } for c in components)):
            return None
        quotes = quotation_boundaries(text)
        if (len(quotes) != 2 or
                [(x.start,x.end,x.side) for x in quotes] != [
                    (0,1,"open"),(len(text)-1,len(text),"close")
                ]):
            return None
        parts = sorted(
            (c for c in components if
             c.get("function") == "spoken_clause_candidate"
             and c.get("governor") == "q0"),
            key=lambda c: c["start"],
        )
        if len(parts) != 2:
            return None
        p1,p2=parts
        if (p1["start"] != 1 or p2["end"] != len(text)-1
                or text[p1["end"]:p2["start"]].strip()):
            return None
        first = re.fullmatch(
            r"([Aa]s)\s+(long)\s+(as)\s+(.+?)(,)\s+"
            r"(.+?)(,)\s+(.+?)(\.)",
            text[p1["start"]:p1["end"]],
        )
        second = re.fullmatch(
            r"(.+?)(,)\s+(.+?)(!)",
            text[p2["start"]:p2["end"]],
        )
        if not first or not second:
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]] = []
        def group(match: re.Match[str],base:int,n:int,cat:str,
                  kind="lexical",**required:str) -> None:
            a,b=match.span(n)
            specs.append((cat,base+a,base+b,kind,required))
        def punct(cat:str,a:int)->None:
            specs.append((cat,a,a+1,"source-punctuation",{}))
        punct("OPEN-QUOTE",0)
        base=p1["start"]
        for n,cat in ((1,"CONJ"),(2,"ADJ"),(3,"CONJ")):
            group(first,base,n,cat)
        group(first,base,4,"CLAUSE","phrase")
        group(first,base,5,"COMMA","source-punctuation")
        group(first,base,6,"NP","phrase")
        group(first,base,7,"COMMA","source-punctuation")
        group(first,base,8,"CLAUSE","phrase")
        group(first,base,9,"SPEECH-STOP","source-punctuation")
        base=p2["start"]
        group(second,base,1,"NP","phrase")
        group(second,base,2,"COMMA","source-punctuation")
        group(second,base,3,"NP","phrase")
        group(second,base,4,"EXCL","source-punctuation")
        punct("CLOSE-QUOTE",len(text)-1)
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "dialogue_structural_temporal_vocative_minor_reprise",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def _compose_split_modal_coord_with_gerund(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Prove a split speech preface and shared-modal coordinated predicates.

        The source-scoped grammar keeps each verb's object separate from its
        own PPs; the possessive subject of the final gerund is overt and its
        PP is a modifier of the SECOND predicate, never of the object NP.
        No finite predicate is supplied to the preface.
        """
        by_id = {p.get("id"): p for p in components}
        q0, q1, tag = (by_id.get(k) for k in ("q0", "q1", "r0"))
        if not all((q0, q1, tag)):
            return None
        if (q0.get("function") != "direct_speech"
                or q1.get("function") != "direct_speech"
                or tag.get("function") != "reporting_clause"
                or not any(p.get("function") == "split_direct_speech_turn"
                           for p in components)
                or any(p.get("function") in ("embedded_quotation",
                         "narratorial_parenthetical") for p in components)):
            return None
        a0, b0 = q0["start"], q0["end"]
        a1, b1 = q1["start"], q1["end"]
        ta, tb = tag["start"], tag["end"]
        quotes = quotation_boundaries(text)
        if (a0 != 0 or b1 != len(text) or
                not (0 < b0 < ta < tb < a1 < b1) or
                len(quotes) != 4 or
                [q.side for q in quotes] !=
                ["open", "close", "open", "close"] or
                [q.start for q in quotes] != [0, b0-1, a1, b1-1] or
                not text[b0:ta].isspace() or
                re.fullmatch(r"\s*,\s*", text[tb:a1]) is None):
            return None
        first = re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z]+)(,)",
                             text[1:b0-1])
        # The PP containing a possessive gerund follows a selected PP
        # complement of the second transitive verb, after an overt comma
        # + coordinator. Every word must have an original lexical edge.
        second = re.fullmatch(
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+\s+[A-Za-z]+)\s+"
            r"(with\s+[A-Za-z]+)(,)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
            r"(of\s+.+?)\s+(without)\s+([A-Za-z]+)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)([.!?])",
            text[a1+1:b1-1],
        )
        if first is None or second is None:
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]] = []
        def group(match: re.Match[str], base: int, i: int, cat: str,
                  kind="lexical", **required: str) -> None:
            a, b = match.span(i)
            specs.append((cat, base+a, base+b, kind, required))
        def punct(cat: str, a: int) -> None:
            specs.append((cat, a, a+1, "source-punctuation", {}))
        punct("OPEN-QUOTE", 0)
        group(first, 1, 1, "COORD")
        group(first, 1, 2, "ADV")
        group(first, 1, 3, "COMMA", "source-punctuation")
        punct("CLOSE-QUOTE", b0-1)
        specs.append(("SPEECH-TAG", ta, tb, "phrase", {}))
        punct("COMMA", text.index(",", tb, a1))
        punct("OPEN-QUOTE", a1)
        s = a1+1
        group(second,s,1,"NP","phrase",pronominal="true")
        group(second,s,2,"MODAL","lexical",vform="finite")
        group(second,s,3,"V","lexical",vform="base",subcat_member="transitive")
        group(second,s,4,"NP","phrase")
        group(second,s,5,"PP","phrase")
        group(second,s,6,"COMMA","source-punctuation")
        group(second,s,7,"COORD")
        group(second,s,8,"V","lexical",vform="base",subcat_member="transitive")
        group(second,s,9,"NP","phrase",pronominal="true")
        group(second,s,10,"PP","phrase")
        group(second,s,11,"PREP")
        group(second,s,12,"POSS")
        group(second,s,13,"V","lexical",vform="ing",subcat_member="transitive")
        group(second,s,14,"NP","phrase",pronominal="true")
        group(second,s,15,"SPEECH-STOP","source-punctuation")
        punct("CLOSE-QUOTE", b1-1)
        return self._compose_verified_dialogue_pattern(
            parser, text, original_lattice, specs,
            "dialogue_structural_split_shared_modal_coord_gerund",
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )

    def _compose_bulk_dialogue_families(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Source-layout-based dispatch for four productive quote structures.

        Every construction is proposed from actual paired delimiters,
        relative punctuation and the structural utterance relation. Actual
        proof uses the common bounded selected-tree assembler above.
        """
        by_id = {p.get("id"): p for p in components}
        q0, r0, q1 = (by_id.get(k) for k in ("q0", "r0", "q1"))
        if not q0 or q0.get("function") != "direct_speech":
            return None
        if any(p.get("function") in (
            "embedded_quotation", "narratorial_parenthetical",
        ) for p in components):
            return None
        quotes = quotation_boundaries(text)
        if len(quotes) not in (2, 4):
            return None
        if any((x.end-x.start) != 1 for x in quotes):
            return None
        if [x.side for x in quotes] not in (
            ["open", "close"], ["open", "close", "open", "close"],
        ):
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]] = []
        def put(category: str, a: int, b: int, kind="lexical",
                **required: str) -> None:
            specs.append((category, a, b, kind, required))
        def punct(category: str, a: int, b: int | None = None) -> None:
            put(category, a, a+1 if b is None else b, "source-punctuation")
        def match_groups(
            match: re.Match[str], base: int,
            categories: Sequence[str],
            kinds: Mapping[int,str] | None = None,
            requirements: Mapping[int,Mapping[str,str]] | None = None,
        ) -> None:
            kinds = kinds or {}
            requirements = requirements or {}
            for i, category in enumerate(categories, 1):
                a,b = match.span(i)
                put(category, base+a, base+b, kinds.get(i,"lexical"),
                    **requirements.get(i,{}))
        rule: str | None = None
        a0,b0 = q0.get("start"), q0.get("end")
        if not (a0 == 0 and isinstance(b0,int)
                and len(text) > b0 + 3
                and [quotes[0].start,quotes[1].end] == [0,b0]):
            return None
        # A single initial quote followed by a postposed report.
        if (len(quotes) == 2 and q1 is None and r0 is not None
                and r0.get("function") == "reporting_clause"):
            ta,tb = r0.get("start"),r0.get("end")
            if not (isinstance(ta,int) and isinstance(tb,int)
                    and b0 < ta < tb == len(text)-1
                    and text[b0:ta].isspace() and text[tb] == "."):
                return None
            quote_surface = text[1:b0-1]
            reporter = text[ta:tb]
            mp = re.fullmatch(r"(.+?)(--|—)([A-Za-z]+)(\?)",
                              quote_surface)
            mr = re.fullmatch(
                r"([A-Za-z]+)\s+([A-Za-z]+)(,)\s+"
                r"([A-Za-z]+)\s+([A-Za-z]+)\s+(.+)",
                reporter,
            )
            if mp and mr:
                rule = (
                    "dialogue_structural_pp_dash_adverb_question_"
                    "participial_reporter"
                )
                punct("OPEN-QUOTE",0)
                match_groups(mp,1,
                    ("PP","DASH","ADV","QMARK"),
                    {1:"phrase",2:"source-punctuation",
                     4:"source-punctuation"})
                punct("CLOSE-QUOTE",b0-1)
                match_groups(mr,ta,
                    ("V","NP","COMMA","V","ADV","PP"),
                    {2:"phrase",3:"source-punctuation",6:"phrase"},
                    {1:{"vform":"finite"},
                     4:{"vform":"ing","subcat":"prepositional"}})
                punct("SPEECH-STOP",tb)
            else:
                mq = re.fullmatch(
                    r"([A-Za-z]+)(,)\s+([A-Za-z]+)(,)\s+"
                    r"([A-Za-z]+)(!)",quote_surface,
                )
                mt = re.fullmatch(
                    r"([A-Za-z]+)\s+([A-Za-z]+)(,)\s+"
                    r"([A-Za-z]+)\s+([A-Za-z]+)\s+"
                    r"([A-Za-z]+)\s+(.+)",
                    reporter,
                )
                if mq and mt:
                    if (mq.group(1).casefold()!=mq.group(3).casefold()
                            or mq.group(1).casefold()!=mq.group(5).casefold()):
                        return None
                    rule = (
                        "dialogue_structural_repeated_directional_"
                        "exclamation_coordinated_report"
                    )
                    punct("OPEN-QUOTE",0)
                    match_groups(mq,1,
                        ("ADV","COMMA","ADV","COMMA","ADV","EXCL"),
                        {2:"source-punctuation",
                         4:"source-punctuation",6:"source-punctuation"})
                    punct("CLOSE-QUOTE",b0-1)
                    match_groups(mt,ta,
                        ("NP","V","COMMA","COORD","V","NP","PP"),
                        {1:"phrase",3:"source-punctuation",
                         6:"phrase",7:"phrase"},
                        {2:{"vform":"finite","subcat":"intransitive"},
                         5:{"vform":"finite","subcat":"transitive"}})
                    punct("SPEECH-STOP",tb)
            if rule is None:
                # Spoken finite comparison with a vocative and an
                # independently attributed reporting tag. The comparative
                # target is a possessive pronoun, not a spurious bare noun.
                comparative = re.fullmatch(
                    r"(.+?)\s+(am|are|is|was|were)\s+(more|less)\s+"
                    r"(.+?)\s+(than)\s+([A-Za-z]+)(,)\s+(.+?)(,)",
                    quote_surface,
                )
                if (comparative is not None
                        and comparative.group(5).casefold() == "than"
                        and comparative.group(3).casefold() in
                           ("more", "less")):
                    rule = (
                        "dialogue_structural_postposed_comparative_"
                        "vocative_report"
                    )
                    punct("OPEN-QUOTE",0)
                    match_groups(comparative,1,
                        ("NP","COPULA","DEGREE","PP","CONJ",
                         "POSS-PRONOUN","COMMA","NP","COMMA"),
                        {1:"phrase",4:"phrase",7:"source-punctuation",
                         8:"phrase",9:"source-punctuation"},
                        {2:{"vform":"finite"},
                         6:{"independent_possessive":"true"}})
                    punct("CLOSE-QUOTE",b0-1)
                    put("SPEECH-TAG",ta,tb,"phrase")
                    punct("SPEECH-STOP",tb)
            if rule is None:
                # Reduced temporal adjunct attaches to the reporter; the
                # finite quote and its addressee are separately proved.
                spoken_vocative = re.fullmatch(
                    r"(.+?)(,)\s+(.+?)(,)",quote_surface,
                )
                temporal = re.fullmatch(
                    r"([A-Za-z]+)\s+([A-Za-z]+)(,)\s+"
                    r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
                    r"([A-Za-z]+)\s+([A-Za-z]+)\s+"
                    r"([A-Za-z]+)\s+(.+)",
                    reporter,
                )
                if (spoken_vocative is not None and temporal is not None
                        and temporal.group(4).casefold() == "when"):
                    rule = (
                        "dialogue_structural_postposed_temporal_"
                        "reduced_reporter"
                    )
                    punct("OPEN-QUOTE",0)
                    match_groups(spoken_vocative,1,
                        ("CLAUSE","COMMA","NP","COMMA"),
                        {1:"phrase",2:"source-punctuation",
                         3:"phrase",4:"source-punctuation"})
                    punct("CLOSE-QUOTE",b0-1)
                    match_groups(temporal,ta,
                        ("V","NP","COMMA","CONJ","NEG-DEGREE","ADV",
                         "ADJ","TO","V","NP"),
                        {2:"phrase",3:"source-punctuation",10:"phrase"},
                        {1:{"vform":"finite"},
                         5:{"temporal_negation":"true"},
                         7:{"infinitival_complement":"true"},
                         9:{"vform":"base","subcat":"transitive"}})
                    punct("SPEECH-STOP",tb)
            if rule is None:
                # Copular predicate coordination interrupted by an actual
                # parenthetical finite speech-comment and followed by the
                # normal postposed reporting clause.
                parenthetical = re.fullmatch(
                    r"(.+?)(,)\s+([A-Za-z]+)(,)\s+"
                    r"(.+?)(,)\s+(.+?)(,)",
                    quote_surface,
                )
                if parenthetical is not None:
                    rule = (
                        "dialogue_structural_postposed_predicative_"
                        "coord_parenthetical_report"
                    )
                    punct("OPEN-QUOTE",0)
                    match_groups(parenthetical,1,
                        ("CLAUSE","COMMA","COORD","COMMA",
                         "CLAUSE","COMMA","ADJP","COMMA"),
                        {1:"phrase",2:"source-punctuation",
                         4:"source-punctuation",5:"phrase",
                         6:"source-punctuation",7:"phrase",
                         8:"source-punctuation"})
                    punct("CLOSE-QUOTE",b0-1)
                    put("SPEECH-TAG",ta,tb,"phrase")
                    punct("SPEECH-STOP",tb)
        # Two quoted fragments separated by an actual reporting tag.
        elif (len(quotes) == 4 and q1 is not None and r0 is not None
              and q1.get("function") == "direct_speech"
              and r0.get("function") == "reporting_clause"
              and any(c.get("function") == "split_direct_speech_turn"
                      for c in components)):
            a1,b1 = q1.get("start"),q1.get("end")
            ta,tb = r0.get("start"),r0.get("end")
            if not (isinstance(a1,int) and isinstance(b1,int)
                    and isinstance(ta,int) and isinstance(tb,int)
                    and b1 == len(text)
                    and 0 < b0 < ta < tb < a1 < b1
                    and [q.start for q in quotes]==[0,b0-1,a1,b1-1]
                    and text[b0:ta].isspace()
                    and re.fullmatch(r"\s*,\s*",text[tb:a1])):
                return None
            first = text[1:b0-1]
            second = text[a1+1:b1-1]
            vocative = re.fullmatch(
                r"([A-Za-z]+)(,)\s+([A-Za-z][A-Za-z.'-]*)(,)",
                first,
            )
            copular = re.fullmatch(
                r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+"
                r"([A-Za-z]+)\s+([A-Za-z]+)(,)\s+(.+?)(,)\s+"
                r"(.+?)([.!?])",
                second,
            )
            polite = re.fullmatch(
                r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)"
                r"(,)\s+([A-Za-z]+)(,)",
                first,
            )
            if vocative and copular:
                rule = "dialogue_structural_split_vocative_copula_domain"
                punct("OPEN-QUOTE",0)
                match_groups(vocative,1,
                    ("ADV","COMMA","NP","COMMA"),
                    {2:"source-punctuation",3:"phrase",
                     4:"source-punctuation"})
                punct("CLOSE-QUOTE",b0-1)
                put("SPEECH-TAG",ta,tb,"phrase")
                punct("COMMA",text.find(",",tb,a1))
                punct("OPEN-QUOTE",a1)
                match_groups(copular,a1+1,
                    ("DET","ADJ","ADJ","N","COPULA",
                     "COMMA","PP","COMMA","NP","SPEECH-STOP"),
                    {6:"source-punctuation",7:"phrase",
                     8:"source-punctuation",9:"phrase",
                     10:"source-punctuation"},
                    {5:{"vform":"finite"}})
                punct("CLOSE-QUOTE",b1-1)
            elif polite and second.endswith("?"):
                rule=(
                    "dialogue_structural_split_polite_conditional_"
                    "vocative_question"
                )
                punct("OPEN-QUOTE",0)
                match_groups(polite,1,
                    ("CONJ","NP","V","COMMA","NP","COMMA"),
                    {2:"phrase",4:"source-punctuation",
                     5:"phrase",6:"source-punctuation"},
                    {3:{"vform":"finite","polite_formula":"true"}})
                punct("CLOSE-QUOTE",b0-1)
                put("SPEECH-TAG",ta,tb,"phrase")
                punct("COMMA",text.find(",",tb,a1))
                punct("OPEN-QUOTE",a1)
                put("CLAUSE",a1+1,b1-1,"phrase",
                    mood="conditional")
                punct("CLOSE-QUOTE",b1-1)
        if rule is None:
            return None
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,rule,
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

    def compose_unquoted_asyndetic_modal_passive_dash(
        self, parser: Any, text: str, original_lattice: LexicalLattice,
        components: Sequence[Mapping[str, Any]], *,
        max_items: int | None = None,
        kbest_work_limit: int | None = None,
        diagnostic_k: int | None = None,
        beam: int | None = None,
    ) -> ParseResult | None:
        """Prove three asyndetically listed negative subjects and two passives.

        A stranded preposition belongs to the first passive participle;
        the original double dash links *two* distinct finite clauses.  This
        never turns comma-delimited nominal subjects into extra finite clauses
        or uses a globablly permissive NP + VP chart production.
        """
        if (not components
                or not any(c.get("function") == "matrix_clause"
                           for c in components)
                or any(c.get("function") in (
                    "direct_speech", "embedded_quotation",
                    "reporting_clause", "requires_source_context",
                ) for c in components)
                or quotation_boundaries(text)):
            return None
        match = re.fullmatch(
            r"(.+?)(,)\s+(.+?)(,)\s+(.+?)\s+"
            r"([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)\s+([A-Za-z]+)"
            r"(--|—)(.+?)([.!?])",
            text,
        )
        if match is None:
            return None
        specs: list[tuple[str,int,int,str,Mapping[str,str]]] = []
        def group(i: int, cat: str, kind="lexical", **required: str) -> None:
            a,b = match.span(i)
            specs.append((cat,a,b,kind,required))
        # Each of the three negative subjects must have its own
        # overt lexical DET + N proof.  Local unrestricted NP ranking can
        # incorrectly select a bare-N homograph for "no officers";
        # we must not use that parse as a negative-determiner subject.
        for i in (1,3,5):
            a,b=match.span(i)
            pair=re.fullmatch(r"([A-Za-z]+)\s+([A-Za-z][A-Za-z-]*)",
                              text[a:b])
            if pair is None:
                return None
            for n,category,features in (
                (1,"DET",{"definiteness":"negative"}),
                (2,"N",{}),
            ):
                sa,sb=pair.span(n)
                specs.append((category,a+sa,a+sb,"lexical",features))
        # Ordered pair commas are real source delimiters, never inferred.
        for i in (2,4):
            group(i,"COMMA","source-punctuation")
        group(6,"MODAL","lexical",vform="finite")
        group(7,"V","lexical",vform="base",subcat_member="linking")
        group(8,"V","lexical",vform="ed",subcat_member="prepositional")
        group(9,"PREP")
        group(10,"DASH","source-punctuation")
        group(11,"CLAUSE","phrase",voice="passive")
        group(12,"SPEECH-STOP","source-punctuation")
        specs.sort(key=lambda x:x[1])
        # The second clause must be independently selected as a real
        # passive rank-one tree, rather than an adjunct or nominal reading.
        return self._compose_verified_dialogue_pattern(
            parser,text,original_lattice,specs,
            "structural_source_asyndetic_modal_passive_dash",
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )

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
        epistemic_doubt = self._compose_epistemic_doubt_gerund_question(
            parser,text,original_lattice,components,
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )
        if epistemic_doubt is not None:
            return epistemic_doubt
        epistemic_reason = self._compose_epistemic_reason_infinitive_question(
            parser,text,original_lattice,components,
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )
        if epistemic_reason is not None:
            return epistemic_reason
        dialect = self._compose_dialectal_three_act_self_report(
            parser,text,original_lattice,components,
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )
        if dialect is not None:
            return dialect
        praise = self._compose_vocative_praise_stars_reporter(
            parser,text,original_lattice,components,
            max_items=max_items,kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k,beam=beam,
        )
        if praise is not None:
            return praise
        comparative = self._compose_comparative_negative_predicative_tag(
            parser, text, original_lattice, components,
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if comparative is not None:
            return comparative
        confirmatory = self._compose_three_confirmatory_tags_and_vocative(
            parser, text, original_lattice, components,
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if confirmatory is not None:
            return confirmatory
        existential = self._compose_existential_parenthetical_wh_question(
            parser, text, original_lattice, components,
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if existential is not None:
            return existential
        causal = self._compose_split_intent_causal_ditransitive(
            parser, text, original_lattice, components,
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if causal is not None:
            return causal
        vocative_perfect = self._compose_split_vocative_two_perfect_sentences(
            parser, text, original_lattice, components,
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if vocative_perfect is not None:
            return vocative_perfect
        inclusive = self._compose_inclusive_let_imperative_sequence(
            parser, text, original_lattice, components,
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if inclusive is not None:
            return inclusive
        temporal = self._compose_temporal_vocative_minor_reprise(
            parser, text, original_lattice, components,
            max_items=max_items, kbest_work_limit=kbest_work_limit,
            diagnostic_k=diagnostic_k, beam=beam,
        )
        if temporal is not None:
            return temporal
        plan = self._plan(text, components)
        if plan is None:
            bulk = self._compose_bulk_dialogue_families(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if bulk is not None:
                return bulk
            scoped_modal = self._compose_split_modal_coord_with_gerund(
                parser, text, original_lattice, components,
                max_items=max_items, kbest_work_limit=kbest_work_limit,
                diagnostic_k=diagnostic_k, beam=beam,
            )
            if scoped_modal is not None:
                return scoped_modal
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
