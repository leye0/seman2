"""Source-anchored discourse-syntactic constituents within quoted prose.

A dialogue turn may consist of several separate quotation spans interrupted by
a reporting clause (intercalated reporting tag), and each uninterrupted quoted
span may itself contain multiple sentence-level speech acts. This module
records those separate functions and links without rewriting the text.

Terminology:
  direct speech, split quotation, reporting clause / quotative frame,
  reporting intercalation, speech-clause candidate, embedded quotation,
  paratactic speech continuation.

These labels are *provisional surface analyses*, not certified grammar trees,
speaker identity, semantic coreference, or fabricated missing words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DialoguePart:
    id: str
    function: str
    start: int
    end: int
    governor: str
    relation: str
    evidence: str


_REPORTING_VERB = re.compile(
    r"(?i)\b(?:said|replied|answered|asked|cried|muttered|whispered|"
    r"exclaimed|returned|observed|continued|added|remarked|declared|"
    r"called|shouted|inquired)\b"
)
# At most one *local* attribution, not a distant narrative mention of
# someone who happened to have spoken at another point in the paragraph.
_TAG_LIMIT = 150
_ABBREVIATION = re.compile(
    r"(?i)\b(?:Mr|Mrs|Ms|Dr|Prof|St|Mme|Mlle|Capt|Rev)\.$"
)


def _trim(source: str, a: int, b: int) -> tuple[int, int]:
    while a < b and source[a].isspace():
        a += 1
    while b > a and source[b-1].isspace():
        b -= 1
    return a, b


def _top_level_quotes(
    quotes: list[tuple[int, int]],
) -> tuple[list[int], dict[int, int]]:
    """Return disjoint outer quotation indexes and actual embedding parents."""
    top = []
    parents = {}
    for k, (a, b) in enumerate(quotes):
        enclosing = [
            (j, e-s) for j, (s, e) in enumerate(quotes)
            if j != k and s < a and b < e
        ]
        if enclosing:
            parents[k] = min(enclosing, key=lambda x: x[1])[0]
        else:
            top.append(k)
    return top, parents


def _local_reporting_tag(
    source: str, a: int, b: int,
) -> tuple[int, int, int] | None:
    """Find an overt reporting predicate in a genuine between-quote gap.

    The returned tag includes the source subject when present, without
    mistaking a speech verb for the whole reporting clause.
    """
    a, b = _trim(source, a, b)
    if not a < b or b-a > _TAG_LIMIT:
        return None
    gap = source[a:b]
    verb = _REPORTING_VERB.search(gap)
    if verb is None:
        return None
    # Do not claim an attribution across an independent complete
    # narration sentence. One intercalated tag may have an em-dash aside.
    # Its inner aside is annotated independently below.
    if re.search(r"[.!?]\s+[A-Z]", gap[:verb.start()]):
        return None
    # A clause separated from the reporter by an em-dash belongs to the
    # surrounding narration, not to the reporting clause itself.
    marker = gap.find("--", verb.end())
    if marker < 0:
        marker = gap.find("—", verb.end())
    if marker >= 0:
        b = a+marker
    # A reporting tag may finish with a comma or period, which is not
    # itself part of the reporting clause's lexical source span.
    while b > a and source[b-1] in " \t,;.!?":
        b -= 1
    if b <= a:
        return None
    return a, b, a+verb.start()


def _speech_sentences(
    source: str, start: int, end: int,
) -> list[tuple[int, int]]:
    """Source spans of spoken sentences *inside* a single quote pair.

    Split only at a likely genuine speech sentence-final punctuation, not
    abbreviations, decimal notation, contractions or internal punctuation.
    The original quotation enclosing these spans is kept unchanged.
    """
    a, b = _trim(source, start+1, end-1)
    if a >= b:
        return []
    spans = []
    cursor = a
    i = a
    while i < b:
        char = source[i]
        if char not in ".!?":
            i += 1
            continue
        if char == "." and (
            _ABBREVIATION.search(source[max(a, i-14):i+1])
            or (i+1 < b and source[i+1] == ".")
            or (i > a and i+1 < b and source[i-1].isdigit()
                and source[i+1].isdigit())
        ):
            i += 1
            continue
        j = i+1
        while j < b and source[j] in "\"'”’)]}":
            j += 1
        if j < b and not source[j].isspace():
            i += 1
            continue
        next_a = j
        while next_a < b and source[next_a].isspace():
            next_a += 1
        if next_a >= b or not source[next_a].isupper():
            i += 1
            continue
        x, y = _trim(source, cursor, j)
        if x < y:
            spans.append((x, y))
        cursor = next_a
        i = next_a
    x, y = _trim(source, cursor, b)
    if x < y:
        spans.append((x, y))
    return spans


def analyze_dialogue(
    source: str,
    quotation_spans: list[tuple[int, int]],
) -> tuple[DialoguePart, ...]:
    """Annotate split speech and reporting tags with exact source relations.

    The quote spans come from the paragraph's source quote scanner, so no
    inferred or synthetic closing delimiters can ever enter this graph.
    """
    if not quotation_spans:
        return ()
    outer, embedded = _top_level_quotes(quotation_spans)
    parts: list[DialoguePart] = []
    for j, (a, b) in enumerate(quotation_spans):
        parent = embedded.get(j)
        parts.append(DialoguePart(
            id=f"q{j}",
            function="embedded_quotation" if parent is not None else "direct_speech",
            start=a, end=b,
            governor=f"q{parent}" if parent is not None else "u0",
            relation="embedded_reported_content" if parent is not None
                     else "unattributed_speech",
            evidence="paired_original_quotation_delimiters",
        ))
        # Nested content may share punctuation with its enclosing source
        # quote. Enumerate sentence spans only for the outer source speech.
        if parent is not None:
            continue
        for number, (sa, sb) in enumerate(_speech_sentences(source, a, b)):
            parts.append(DialoguePart(
                id=f"qc{j}_{number}",
                function="spoken_clause_candidate",
                start=sa, end=sb, governor=f"q{j}",
                relation="clause_in_direct_speech",
                evidence="source_internal_sentence_punctuation"
                         if number else "source_quotation_content",
            ))
    # Reporting predicates in gaps between adjacent top-level quotation
    # spans are direct evidence of a split speech turn. Do not group
    # unrelated quoted sentences by their quote characters alone.
    associations: dict[int, set[int]] = {}
    tags = []
    for x, y in zip(outer, outer[1:]):
        gap = _local_reporting_tag(source, quotation_spans[x][1],
                                   quotation_spans[y][0])
        if gap:
            tags.append((gap, (x, y), "intercalated_reporting_clause"))
    associated = {index for _tag, pair, _label in tags for index in pair}
    for q in outer:
        if q in associated:
            continue
        a, b = quotation_spans[q]
        prev = quotation_spans[outer[outer.index(q)-1]][1] if outer.index(q) else 0
        next_ = (
            quotation_spans[outer[outer.index(q)+1]][0]
            if outer.index(q)+1 < len(outer) else len(source)
        )
        # Prefer a contiguous source attribution after speech. Fall back to
        # the overt reporting clause before a preposed quotation.
        post = _local_reporting_tag(source, b, next_)
        pre = _local_reporting_tag(source, prev, a)
        if post:
            tags.append((post, (q,), "postposed_reporting_clause"))
        elif pre:
            tags.append((pre, (q,), "preposed_reporting_clause"))
    claimed = set()
    for tag_number, (tag, members, evidence) in enumerate(tags):
        lo, hi, verb_at = tag
        if any(q in claimed for q in members):
            # Avoid competing incompatible speaker assignments; such cases
            # remain unattributed until a higher-level analysis resolves.
            continue
        claimed.update(members)
        reporter_id = f"r{tag_number}"
        parts.append(DialoguePart(
            id=reporter_id, function="reporting_clause", start=lo, end=hi,
            governor="u0", relation="quotative_frame",
            evidence=evidence,
        ))
        for q in members:
            original = next(x for x in parts if x.id == f"q{q}")
            parts[parts.index(original)] = DialoguePart(
                id=original.id, function=original.function,
                start=original.start, end=original.end,
                governor=reporter_id, relation="reported_content",
                evidence="source_reporting_verb_and_quote_adjacency",
            )
        if len(members) >= 2:
            first, last = quotation_spans[members[0]], quotation_spans[members[-1]]
            group_id = f"t{tag_number}"
            parts.append(DialoguePart(
                id=group_id, function="split_direct_speech_turn",
                start=first[0], end=last[1], governor="u0",
                relation="reporting_intercalation",
                evidence="one_overt_reporting_clause_between_two_source_quotes",
            ))
            previous_reporter = parts[-(len(members)+1)] if False else None
            for k, value in enumerate(parts):
                if value.id == reporter_id:
                    parts[k] = DialoguePart(
                        id=value.id, function=value.function,
                        start=value.start, end=value.end,
                        governor=group_id, relation="intercalated_speech_tag",
                        evidence=value.evidence,
                    )
                    break
            # Reporting clause may have a parenthetical narrative aside
            # between its source span and the next quote.
            interlude = source[hi:last[0]]
            dash = re.search(r"(?:--|—)(.+?)(?:--|—)\s*$", interlude, re.S)
            if dash and dash.group(1).strip():
                x = hi+dash.start(1)
                y = hi+dash.end(1)
                x, y = _trim(source, x, y)
                parts.append(DialoguePart(
                    id=f"a{tag_number}", function="narratorial_parenthetical",
                    start=x, end=y, governor=group_id,
                    relation="narratorial_interpolation",
                    evidence="source_double_dash_parenthesis_between_quote_parts",
                ))
    return tuple(parts)
