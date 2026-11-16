"""Source-faithful paragraph preanalysis, BEFORE complete grammar parsing.

A sentence is an entire utterance: never cut at semicolons or in the middle
of an unclosed source quotation. A span graph records high-level descriptive
grammatical functions with explicit governors and evidence. The functions
are provisional hypotheses, NOT validated full parse-tree attachments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from seman_parser.sentence_boundaries import _abbreviation_at
from seman_parser.structural_units import review_semicolon_boundaries, skeleton
from seman_parser.discourse_roles import classify_discourse
from seman_parser.quoted_discourse import analyze_dialogue
from seman_parser.finite_temporal_scope import finite_temporal_span
from seman_parser.nominal_temporal_scope import nominal_temporal_spans
from seman_parser.shared_by_coordination import shared_by_match
from seman_parser.semicolon_triplet import semicolon_triplet_spans
from seman_parser.inverted_object_control import inverted_control_spans
from seman_parser.negative_perfect import negative_perfect_span
from seman_parser.comparative_content_coordination import comparative_content_spans
from seman_parser.extraposed_scalar_content import extraposed_scalar_spans
from seman_parser.degree_concessive import degree_concession_spans
from seman_parser.paired_clause_supplements import paired_supplement_spans
from seman_parser.measured_voice_coordination import measured_voice_spans
from seman_parser.coordination_with_initial_pp import source_spans as right_initial_pp_spans

_OPEN_TO_CLOSE = {"“": "”", "‘": "’", '"': '"', "'": "'"}
_INTRO = re.compile(r"(?i)^(?:because|although|though|unless|until|while|"
                    r"whereas|since|if|when|whenever|as)\b")
_REPORT = re.compile(r"(?i)\b(?:said|replied|asked|cried|muttered|whispered|"
                     r"exclaimed|returned|answered|observed|continued|"
                     r"added|remarked|declared|called|shouted)\b")
_PARTICIPLE = re.compile(r"(?i)^(?:merely\s+|simply\s+)?[a-z-]+ing\b")
_INFINITIVE = re.compile(r"(?i)^(?:(?:and|or)\s+)?to\s+[a-z-]+\b")
_PP = re.compile(r"(?i)^(?:(?:and|or)\s+)?(?:in|on|at|with|from|under|"
                 r"over|through|without|by|beneath|beside|beyond|between)\b")
_COORD = re.compile(r"(?i)^(?:and|but|or|nor)\b")


@dataclass(frozen=True, slots=True)
class StructuralConstituent:
    id: str
    function: str
    start: int
    end: int
    governor: str | None
    relation: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PreanalyzedSentence:
    text: str
    source_start: int
    source_end: int
    quotation_status: str
    structural_status: str
    constituents: tuple[StructuralConstituent, ...]
    eligible_for_parse: bool
    paragraph_index: int = -1
    core_start: int = -1
    core_end: int = -1
    discourse_function: str = "clausal_utterance_candidate"
    discourse_relation: str = "independent_or_complex_clause"
    discourse_evidence: str = "no_conclusive_fragment_or_documentary_evidence"
    discourse_antecedent_policy: str = "none"
    # The actual preceding-source anchor is assigned by the book streamer,
    # NEVER synthesized as missing text inside this sentence.
    discourse_governor_core_span: tuple[int, int] | None = None
    discourse_governor_paragraph_index: int | None = None

    @property
    def source_text(self) -> str:
        return self.text

    @property
    def semicolon_split(self) -> bool:
        # Semicolons express clausal relations INSIDE a complete utterance.
        return False

    @property
    def synthetic_prefix(self) -> str:
        return ""

    @property
    def synthetic_suffix(self) -> str:
        return ""

    @property
    def synthetic_terminal(self) -> bool:
        return False


def quote_scan(text: str) -> tuple[list[int], list[tuple[int, int]], int]:
    """Paired actual source quotes, nested; never fabricate a missing mark.

    A lexical apostrophe between alphanumeric characters, a possessive
    apostrophe, and a trailing dialect apostrophe (o') are not delimiters.
    """
    stack: list[tuple[str, int]] = []
    depth: list[int] = []
    spans: list[tuple[int, int]] = []
    unmatched = 0
    for i, ch in enumerate(text):
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        lexical = (ch in ("'", "’") and prev.isalnum() and nxt.isalnum())
        clipped = (ch in ("'", "’") and prev.isalnum()
                   and (not stack or stack[-1][0] not in ("'", "‘")))
        if lexical or clipped:
            depth.append(len(stack))
            continue
        if ch in ("“", "‘"):
            stack.append((ch, i))
        elif ch in ("”", "’"):
            expected = "“" if ch == "”" else "‘"
            if stack and stack[-1][0] == expected:
                _, first = stack.pop()
                spans.append((first, i + 1))
            else:
                unmatched += 1
        elif ch in ('"', "'"):
            if stack and stack[-1][0] == ch:
                _, first = stack.pop()
                spans.append((first, i + 1))
            elif ch == "'" and (prev.isalnum() or not nxt or not nxt.isalnum()):
                pass
            else:
                stack.append((ch, i))
        depth.append(len(stack))
    return depth, sorted(spans), len(stack) + unmatched


def sentence_spans(paragraph: str) -> tuple[tuple[int, int], ...]:
    """Top-level punctuation segmentation, keeping complete quoted speech.

    The source offsets refer to the supplied whitespace-normalized paragraph.
    Semicolons are not sentence boundaries, ever; they remain clause edges.
    """
    if not paragraph.strip():
        return ()
    depth, _, _ = quote_scan(paragraph)
    n = len(paragraph)
    start = 0
    spans: list[tuple[int, int]] = []
    i = 0
    while i < n:
        mark = paragraph[i]
        if mark not in ".!?":
            i += 1
            continue
        if mark == "." and (
            (i + 1 < n and paragraph[i + 1] == ".")
            or (i > 0 and i + 1 < n and paragraph[i-1].isdigit()
                and paragraph[i+1].isdigit())
        ):
            i += 1
            continue
        end = i + 1
        while end < n and paragraph[end] in "\"'”’)]}":
            end += 1
        if end == n or not paragraph[end].isspace():
            i += 1
            continue
        nxt = end
        while nxt < n and paragraph[nxt].isspace():
            nxt += 1
        first = nxt
        while first < n and paragraph[first] in "\"'“‘([{":
            first += 1
        if first >= n or not paragraph[first].isupper():
            i += 1
            continue
        next_word = paragraph[first:first+20].split(maxsplit=1)[0]
        if mark == "." and _abbreviation_at(paragraph, i, next_word):
            i += 1
            continue
        # An inner sentence inside one continuous quoted speech act does
        # not become a broken standalone quotation.
        if depth[end-1]:
            i += 1
            continue
        a = start
        while a < end and paragraph[a].isspace():
            a += 1
        if a < end:
            spans.append((a, end))
        start = nxt
        i = nxt
    a = start
    while a < n and paragraph[a].isspace():
        a += 1
    b = n
    while b > a and paragraph[b-1].isspace():
        b -= 1
    if a < b:
        spans.append((a, b))
    return tuple(spans)


def _role(text: str, i: int, count: int, reason: str | None) -> tuple[str, str]:
    head = text.strip().lstrip("\"'“‘([{ ")
    if reason in ("contrasting_locative_nominal_ellipsis",
                  "parallel_valediction"):
        return "elliptical_clause", "parallel_ellipsis"
    if reason == "sentential_relative_antecedent":
        return "supplementary_relative_clause", "relative_modifier"
    if reason in ("coordinated_predicate_without_overt_subject",
                  "coordinated_infinitive_without_overt_matrix"):
        return "coordinate_predicate", "shared_subject"
    if reason in ("nonfinite_supplement_without_matrix",
                  "shared_subject_participle_series"):
        return "nonfinite_clause", "supplement"
    if reason == "causal_coordinator_refers_back":
        return "coordinate_clause", "causal_coordination"
    if _INTRO.match(head):
        return "adverbial_subordinate_clause", "adverbial_modifier"
    if _PARTICIPLE.match(head):
        return "nonfinite_clause", "supplement"
    if _INFINITIVE.match(head):
        return "infinitival_clause", "control_or_coordination"
    if _PP.match(head) and i < count-1:
        return "prepositional_phrase", "preposed_adjunct"
    if _COORD.match(head):
        return "coordinate_clause", "coordination"
    if i:
        return "independent_clause", "parataxis"
    return "matrix_clause", "root"


def constituency(source: str, quotation_spans: list[tuple[int, int]]
                 ) -> tuple[StructuralConstituent, ...]:
    """A source-span graph of provisional functions, with governor links."""
    cs = [StructuralConstituent(
        "u0", "utterance", 0, len(source), None, "root",
        "top_level_source_punctuation",
    )]
    parts = source.split(";")
    offsets = [i for i, ch in enumerate(source) if ch == ";"]
    decisions = {d.offset: d for d in review_semicolon_boundaries(source)}
    # When a preposed PP chain precedes a finite main clause, its rightmost
    # member governs the adverbial series rather than the first PP.
    final_matrix = (
        len(parts) > 1
        and all(_PP.match(p.strip()) for p in parts[:-1])
        and skeleton(parts[-1]).finite_predicate_candidate
    )
    main = f"s{len(parts)-1}" if final_matrix else "s0"
    cursor = 0
    for i, part in enumerate(parts):
        a, b = cursor, cursor+len(part)
        while a < b and source[a].isspace():
            a += 1
        while b > a and source[b-1].isspace():
            b -= 1
        if a < b:
            prev = decisions.get(offsets[i-1]) if i else None
            reason = prev.reason if prev and prev.merge else None
            function, relation = _role(source[a:b], i, len(parts), reason)
            governor = main
            if f"s{i}" == main:
                function, relation, governor = "matrix_clause", "matrix_of", "u0"
            elif relation in ("parataxis", "coordination", "causal_coordination",
                              "shared_subject", "parallel_ellipsis"):
                governor = f"s{i-1}"
            cs.append(StructuralConstituent(
                f"s{i}", function, a, b, governor, relation,
                reason or ("initial_clause" if i == 0 else "semicolon_skeleton"),
            ))
        cursor += len(part)+1
    # Preserve internal structure of source documents: these are not full
    # narrative matrix clauses, yet may contain an interpretable grammatical
    # clause or participial direction. All spans are literal source offsets.
    frame = re.match(r"(?i)^(?:P\.\s?S\.|P\.\s?P\.\s?S\.)\s*(?:--|—|:)\s*", source)
    if frame and frame.end() < len(source):
        cs.extend((
            StructuralConstituent(
                "d0", "document_marker", 0, frame.end(), "u0",
                "documentary_frame", "postscript_marker_source_span",
            ),
            StructuralConstituent(
                "d1", "document_content_clause_candidate",
                frame.end(), len(source), "d0",
                "document_content", "postscript_content_source_span",
            ),
        ))
    direction = re.search(r"(?i),\s*bearing\b", source)
    if direction and classify_discourse(source).function == "documentary_navigation_notation":
        cs.extend((
            StructuralConstituent(
                "d0", "document_nominal_reference", 0, direction.start(),
                "u0", "documentary_label",
                "map_reference_nominal_source_span",
            ),
            StructuralConstituent(
                "d1", "directional_participial_supplement",
                direction.end() - len("bearing"), len(source), "d0",
                "directional_modifier",
                "explicit_bearing_participle_source_span",
            ),
        ))
    # Quote spans are speech contents, not automatically separate sentences
    # and not automatically attributed to any reporting verb in the paragraph.
    # This graph explicitly records interrupted speech turns, intercalated
    # speech tags, clause-level material inside quotes, and embedded speech.
    for part in analyze_dialogue(source, quotation_spans):
        cs.append(StructuralConstituent(
            part.id, part.function, part.start, part.end,
            part.governor, part.relation, part.evidence,
        ))
    # Literal outermost parentheses outside speech are source constituents,
    # not sentence boundaries or proof that their contents are finite.
    quote_index = 0
    stack: list[int] = []
    for offset, char in enumerate(source):
        while (quote_index < len(quotation_spans)
               and quotation_spans[quote_index][1] <= offset):
            quote_index += 1
        if (quote_index < len(quotation_spans)
                and quotation_spans[quote_index][0] <= offset < quotation_spans[quote_index][1]):
            continue
        if char == "(":
            stack.append(offset)
        elif char == ")" and stack:
            start = stack.pop()
            if stack or not source[start + 1:offset].strip():
                continue
            end = offset + 1
            host = next((node for node in cs if node.id.startswith("s")
                         and node.start <= start < end <= node.end), None)
            if host is not None:
                cs.append(StructuralConstituent(
                    f"p{start}", "parenthetical_candidate", start, end, host.id,
                    "parenthetical_supplement", "balanced_literal_parentheses",
                ))
    shared_by = shared_by_match(source) if not quotation_spans else None
    if shared_by:
        cs.append(StructuralConstituent(
            "b0", "shared_preposition_candidate",
            shared_by.start("both"), shared_by.end("second"), main,
            "prepositional_modifier", "overt_both_by_and_candidate",
        ))
    triplet = semicolon_triplet_spans(source) if len(parts) == 2 and not quotation_spans else None
    if triplet and main == "s0":
        middle, right = triplet
        cs.extend((
            StructuralConstituent("st0", "finite_conjunct_candidate", *middle, "s1",
                                  "first_conjunct", "semicolon_then_comma_and"),
            StructuralConstituent("st1", "finite_conjunct_candidate", *right, "st0",
                                  "coordination", "semicolon_then_comma_and"),
        ))
    inverted = inverted_control_spans(source) if len(parts) == 1 and not quotation_spans else None
    if inverted:
        question, obj = inverted
        cs.extend((
            StructuralConstituent("iq0", "interrogative_conjunct_candidate", *question, main,
                                  "coordination", "adversative_with_inverted_modal"),
            StructuralConstituent("iq1", "supplemented_object_candidate", *obj, "iq0",
                                  "object", "degree_phrases_after_nominal"),
        ))
    negated = negative_perfect_span(source) if len(parts) == 1 and not quotation_spans else None
    if negated:
        cs.append(StructuralConstituent(
            "ni0", "negative_inversion_candidate", *negated, main,
            "declarative_scope", "negative_licensor_before_perfect_auxiliary",
        ))
    measured = measured_voice_spans(source) if len(parts) == 1 and not quotation_spans else None
    if measured:
        cs.extend(StructuralConstituent(
            f"mv{i}", "coordinate_predicate", *span, main,
            "shared_subject", "measured_passive_then_finite_active",
        ) for i, span in enumerate(measured))
    paired = paired_supplement_spans(source) if len(parts) == 1 and not quotation_spans else None
    if paired:
        left, discourse, right, spatial = paired
        cs.extend((
            StructuralConstituent("cs0", "finite_conjunct_candidate", *left, main,
                                  "first_conjunct", "paired_medial_supplements"),
            StructuralConstituent("csd", "medial_supplement_candidate", *discourse, "cs0",
                                  "discourse_modifier", "comma_delimited_additive_adverb"),
            StructuralConstituent("cs1", "finite_conjunct_candidate", *right, main,
                                  "coordination", "paired_medial_supplements"),
            StructuralConstituent("csp", "medial_supplement_candidate", *spatial, "cs1",
                                  "circumstantial_modifier", "comma_delimited_spatial_phrase"),
        ))
    right_initial = right_initial_pp_spans(source) if not quotation_spans else None
    if right_initial:
        left, right, fronted = right_initial
        cs.extend((
            StructuralConstituent("rc0", "finite_conjunct_candidate", *left, main,
                                  "first_conjunct", "coordinator_with_comma_bounded_pp"),
            StructuralConstituent("rc1", "finite_conjunct_candidate", *right, "rc0",
                                  "coordination", "overt_subject_after_fronted_pp"),
            StructuralConstituent("rcp", "prepositional_phrase", *fronted, "rc1",
                                  "preposed_adjunct", "paired_commas_after_coordinator"),
        ))
    degree = degree_concession_spans(source) if len(parts) == 1 and not quotation_spans else None
    if degree:
        concessive, adjective, content = degree
        cs.extend((
            StructuralConstituent("gc0", "adverbial_subordinate_clause", *concessive,
                                  main, "concessive_modifier", "fronted_degree_predicate"),
            StructuralConstituent("gc2", "predicative_adjective_candidate", *adjective,
                                  main, "attribute", "finite_copula_with_adjective_content"),
            StructuralConstituent("gc1", "adjective_content_candidate", *content,
                                  "gc2", "complement", "overt_that_after_predicative_adjective"),
        ))
    extraposed = extraposed_scalar_spans(source) if len(parts) == 1 and not quotation_spans else None
    if extraposed:
        infinitive, content, subject = extraposed
        cs.extend((
            StructuralConstituent("xs0", "nonfinite_clause", *infinitive,
                                  main, "extraposed_subject_candidate", "anticipatory_it_copula_to"),
            StructuralConstituent("xs1", "finite_content_candidate", *content,
                                  "xs0", "complement", "overt_that_after_infinitival_verb"),
            StructuralConstituent("xs2", "subject_candidate", *subject,
                                  "xs1", "subject", "scalar_modifier_before_modal"),
        ))
    comparison = comparative_content_spans(source) if len(parts) == 1 and not quotation_spans else None
    if comparison:
        left, standard, content, right = comparison
        cs.extend((
            StructuralConstituent("kc0", "finite_conjunct_candidate", *left, main,
                                  "first_conjunct", "negative_degree_then_wh_content"),
            StructuralConstituent("kc1", "comparative_standard_candidate", *standard, "kc0",
                                  "comparison_standard", "than_and_overt_do"),
            StructuralConstituent("kc2", "finite_content_candidate", *content, "kc0",
                                  "complement", "where_after_comparative_standard"),
            StructuralConstituent("kc3", "finite_conjunct_candidate", *right, main,
                                  "coordination", "comma_then_adversative"),
        ))
    # Detect fronted subordinate adjunct with the conventional dependent
    # clause + main-clause comma boundary. Do not claim its NP attachments.
    head = source.lstrip("\"'“‘ ")
    temporal = finite_temporal_span(source) if not quotation_spans else None
    nominal_temporal = nominal_temporal_spans(source) if not quotation_spans else None
    if nominal_temporal:
        a, b, start, end = nominal_temporal
        cs.extend((
            StructuralConstituent("n0", "nominal_modifier_candidate", a, b, main,
                                  "embedded_nominal_modifier", "bounded_overt_nominal_modifier"),
            StructuralConstituent("a0", "adverbial_subordinate_clause", start, end, "n0",
                                  "adverbial_modifier", "bounded_nominal_temporal_candidate"),
        ))
    elif temporal:
        a, b = temporal
        cs.append(StructuralConstituent(
            "a0", "adverbial_subordinate_clause", a, b, main,
            "adverbial_modifier", "bounded_finite_temporal_candidate",
        ))
    elif _INTRO.match(head):
        a = source.find(head)
        b = source.find(",", a)
        if 0 < b < len(source)-2:
            cs.append(StructuralConstituent(
                "a0", "adverbial_subordinate_clause", a, b,
                main, "adverbial_modifier", "subordinator_preposed_comma",
            ))
    return tuple(cs)


def analyze_paragraph(paragraph: str) -> tuple[PreanalyzedSentence, ...]:
    """Build complete source units and high-level grammatical graphs."""
    result: list[PreanalyzedSentence] = []
    for a, b in sentence_spans(paragraph):
        text = paragraph[a:b]
        _, quotes, faults = quote_scan(text)
        quote_status = ("balanced" if not faults
                        else "unresolved_source_quotation")
        terminal = bool(re.search(r"""[.!?]["'”’)\]}]*$""", text))
        prior_text = result[-1].text if result else None
        role = classify_discourse(text, previous_utterance=prior_text)
        viable = terminal and not faults and role.parse_as_standalone_clause
        if role.function.startswith("documentary_"):
            structural_status = "nonprose_documentary"
        elif not viable:
            structural_status = "requires_source_context"
        else:
            structural_status = "provisional_complete_utterance"
        cs = list(constituency(text, quotes))
        if role.function != "clausal_utterance_candidate":
            # A formulaic reply or a compass-bearing document line must NOT
            # be falsely described as a full matrix clause.
            from dataclasses import replace
            for i, node in enumerate(cs):
                if node.id == "s0" and node.function == "matrix_clause":
                    cs[i] = replace(
                        node,
                        function=role.function,
                        relation=role.relation,
                        evidence=role.evidence,
                    )
                    break
        result.append(PreanalyzedSentence(
            text=text, source_start=a, source_end=b,
            quotation_status=quote_status,
            structural_status=structural_status,
            constituents=tuple(cs),
            eligible_for_parse=viable,
            discourse_function=role.function,
            discourse_relation=role.relation,
            discourse_evidence=role.evidence,
            discourse_antecedent_policy=role.antecedent_policy,
        ))
    return tuple(result)
