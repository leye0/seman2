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
                direction.start() + 1, len(source), "d0",
                "directional_modifier",
                "explicit_bearing_participle_source_span",
            ),
        ))
    # Source-matched quotation spans, with overt reporting verbs as edges.
    for j, (a, b) in enumerate(quotation_spans):
        if b-a <= 2:
            continue
        masked = source[:a] + " "*(b-a) + source[b:]
        match = _REPORT.search(masked)
        governor, relation = "u0", "direct_speech"
        if match:
            # The reporting CLAUSE includes its overt speaker NP where one is
            # present; do not mislabel the verb alone as an entire clause.
            before = masked[:match.start()]
            boundary = max(
                before.rfind(","), before.rfind("."), before.rfind("!"),
                before.rfind("?"), before.rfind(";"),
            )
            first = boundary + 1
            while first < match.start() and masked[first].isspace():
                first += 1
            after = masked[match.end():]
            following = re.search(r"[,;.!?]", after)
            last = match.end() + (following.start() if following else len(after))
            while last > match.end() and masked[last-1].isspace():
                last -= 1
            governor, relation = f"r{j}", "reported_content"
            cs.append(StructuralConstituent(
                governor, "reporting_clause", first, last,
                "u0", "reporting_predicate",
                "overt_reporting_verb_and_clause_span",
            ))
        cs.append(StructuralConstituent(
            f"q{j}", "direct_speech", a, b, governor, relation,
            "matched_original_quotation_marks",
        ))
    # Detect fronted subordinate adjunct with the conventional dependent
    # clause + main-clause comma boundary. Do not claim its NP attachments.
    head = source.lstrip("\"'“‘ ")
    if _INTRO.match(head):
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
