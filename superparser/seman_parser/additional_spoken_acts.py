"""Scoped source plans for commands, closings, and negative modal questions."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .dialogue import quotation_boundaries
from .dialogue_clause_plans import _specs
from .structural_units import skeleton

PLAN = "source_scoped_spoken_acts"
COMMAND = "dialogue_structural_command_then_closing"
MODAL_QUESTION = "dialogue_structural_contracted_negative_modal_perfect_question"
ADVERB_ELLIPSIS = "dialogue_structural_adverb_coordination_auxiliary_ellipsis"
CHEER_REPORT = "dialogue_structural_reported_cheer"
PROGRESSIVE_REPORT = "dialogue_structural_reported_progressive_with_weekday"
SHARED_MODAL = "dialogue_structural_exemplified_shared_modal"
NEGATIVE_COGNITION = "dialogue_structural_negative_cognition_then_contrast"

EXEMPLIFIERS = frozenset(("for instance", "for example"))
CHEERS = frozenset(("hurrah", "hurray", "hooray"))
CLOSINGS = frozenset(("good night", "goodnight", "goodbye", "good-bye", "farewell"))
_COMPARISON = re.compile(r"(?i) +(?=like +(?:a|an|the) +)")
_MODAL = re.compile(
    r"(?i)(?P<modal>could|would|should|might|must|may|need|ought)"
    r"(?P<neg>n['’]t) +(?P<subject>i|you|he|she|it|we|they) +"
    r"(?P<predicate>have +[\w'’ -]+)"
)


def command_closing_plan(text: str, spans: Sequence[tuple[int, int, int]]):
    if len(spans) != 2:
        return None
    (a, b, stop), (c, d, end) = spans
    if text[c:d].casefold() not in CLOSINGS or text[stop] not in ".!" or text[end] not in ".!":
        return None
    command = text[a:b]
    if not command or len(command.split()) > 18:
        return None
    shape = skeleton(command)
    if shape.starts_with_preposition or shape.starts_with_subordinator:
        return None
    # Ambiguous bare "like + nominal" can be a comparative fragment.
    if re.match(r"(?i)^like\b", command):
        return None
    comparison = _COMPARISON.search(command)
    specs, add, mark, _ = _specs()
    mark("OPEN-QUOTE", 0, 1)
    if comparison is None:
        add("VP-NP", a, b, "phrase", imperative_predicate_proof="true")
    else:
        add("VP-NP", a, a + comparison.start(), "phrase", imperative_predicate_proof="true")
        add("PP", a + comparison.end(), b, "phrase", comparative_pp_proof="true")
    mark("SPEECH-STOP", stop, stop + 1)
    add("CLOSING-FORMULA", c, d, "source-closing-formula")
    mark("SPEECH-STOP", end, end + 1)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


def _single_spoken_span(text: str, components: Sequence[Mapping[str, Any]], *, reported=False):
    by_id = {c.get("id"): c for c in components}
    quote = by_id.get("q0")
    if not quote or quote.get("function") != "direct_speech" or quote.get("start") != 0:
        return None
    end = quote["end"]
    if not 4 <= end <= len(text):
        return None
    if reported:
        reporter = by_id.get(quote.get("governor"))
        if (quote.get("relation") != "reported_content" or not reporter
                or reporter.get("function") != "reporting_clause"
                or reporter.get("evidence") != "postposed_reporting_clause"
                or reporter["end"] != len(text) - 1 or text[-1] not in ".!"
                or text[end:reporter["start"]].strip()):
            return None
    elif end != len(text) or quote.get("relation") != "unattributed_speech":
        return None
    else:
        reporter = None
    parts = [c for c in components if c.get("function") == "spoken_clause_candidate"
             and c.get("governor") == "q0"]
    if len(parts) != 1 or (parts[0]["start"], parts[0]["end"]) != (1, end - 1):
        return None
    marks = quotation_boundaries(text)
    if [(q.start, q.end, q.side) for q in marks] != [
        (0, 1, "open"), (end - 1, end, "close"),
    ]:
        return None
    return end - 2, reporter


def negative_modal_question_plan(text: str, components: Sequence[Mapping[str, Any]]):
    span = _single_spoken_span(text, components)
    if span is None or text[span[0]] != "?":
        return None
    stop, _ = span
    match = _MODAL.fullmatch(text[1:stop])
    if match is None or len(match["predicate"].split()) > 18:
        return None
    specs, add, mark, parts = _specs()
    mark("OPEN-QUOTE", 0, 1)
    parts(match, 1, (
        ("modal", "MODAL", "lexical", {"vform": "finite", "modal": "true"}),
        ("neg", "NEG", "lexical", {"negation": "true"}),
        ("subject", "NP", "subject-phrase", {}),
        ("predicate", "VP-NP", "phrase", {"perfect_predicate_proof": "true"}),
    ))
    mark("QMARK", len(text) - 2, len(text) - 1)
    mark("CLOSE-QUOTE", len(text) - 1, len(text))
    return specs


_PRONOUN = r"i|you|he|she|it|we|they"
_ADVERB_PAIR = re.compile(
    rf"(?i)(?P<first>[a-z]+) +(?P<coord>and|or) +(?P<second>[a-z]+) +"
    rf"(?P<ellipsis>(?P<subject>{_PRONOUN}) +(?P<aux>do|does|did))"
)
_NAME = r"[A-Z][a-z]+(?:[-’'][A-Z]?[a-z]+)*"
_INVERTED_REPORTER = re.compile(
    rf"(?P<verb>said|cried|exclaimed|shouted|replied|answered|whispered|vowed|promised)"
    rf" +(?P<name>{_NAME}(?: +{_NAME}){{0,2}})"
)
_WEEKDAY = r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_PROGRESSIVE = re.compile(
    rf"(?P<subject>(?i:{_PRONOUN}))(?P<modal>['’]ll| +will) +(?P<be>be) +"
    rf"(?P<verb>[a-zA-Z-]+ing) +(?P<object>.+?) +(?:(?P<on>on) +)?(?P<day>{_WEEKDAY})"
)


def adverb_coordination_ellipsis_plan(text, components):
    span = _single_spoken_span(text, components)
    if span is None or text[span[0]] not in ".!":
        return None
    stop, _ = span
    match = _ADVERB_PAIR.fullmatch(text[1:stop])
    if match is None:
        return None
    subject, auxiliary = match["subject"].casefold(), match["aux"].casefold()
    if auxiliary != "did" and ((auxiliary == "does") != (subject in ("he", "she", "it"))):
        return None
    specs, _, mark, parts = _specs()
    mark("OPEN-QUOTE", 0, 1)
    parts(match, 1, (
        ("first", "ADV", "lexical", {}),
        ("coord", "COORD", "lexical", {}),
        ("second", "ADV", "lexical", {}),
        ("ellipsis", "CLAUSE", "phrase", {"proof_rule": "clause_aux_ellipsis"}),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


def _add_reporter(text, reporter, add, parts):
    start = reporter["start"]
    match = _INVERTED_REPORTER.fullmatch(text[start:reporter["end"]])
    if match is None:
        return False
    parts(match, start, (
        ("verb", "V", "lexical-alternatives", {"vform": "finite",
            "lemma_in": "say|cry|exclaim|shout|reply|answer|whisper|vow|promise"}),
    ))
    names = list(re.finditer(_NAME, match["name"]))
    if len(names) == 1:
        add("NP", start + match.start("name"), start + match.end("name"), "proper-phrase")
    else:
        for name in names:
            a = start + match.start("name")
            add("PROPER-NOUN", a + name.start(), a + name.end(), "lexical-alternatives")
    return True


def reported_cheer_plan(text, components):
    span = _single_spoken_span(text, components, reported=True)
    if span is None:
        return None
    stop, reporter = span
    if text[stop] != "!" or text[1:stop].casefold() not in CHEERS:
        return None
    specs, add, mark, parts = _specs()
    mark("OPEN-QUOTE", 0, 1)
    add("CHEER", 1, stop, "source-cheer-formula")
    mark("EXCL", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    if not _add_reporter(text, reporter, add, parts):
        return None
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return specs


def reported_progressive_plan(text, components):
    span = _single_spoken_span(text, components, reported=True)
    if span is None or text[span[0]] != ",":
        return None
    comma, reporter = span
    match = _PROGRESSIVE.fullmatch(text[1:comma])
    if match is None or len(match["object"].split()) > 10:
        return None
    specs, add, mark, parts = _specs()
    mark("OPEN-QUOTE", 0, 1)
    # The actual modal token starts after whitespace in the uncontracted form.
    modal_a, modal_b = match.span("modal")
    modal_a += len(match["modal"]) - len(match["modal"].lstrip())
    add("MODAL", 1 + modal_a, 1 + modal_b, "lexical", vform="finite", modal="true")
    parts(match, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("be", "AUX-BE", "lexical", {"lemma_in": "be"}),
        ("verb", "V", "lexical-alternatives", {"vform": "ing", "subcat_member": "transitive"}),
        ("object", "NP", "phrase", {"grounded_object_proof": "true"}),
        ("day", "N", "lexical", {"lemma_in": match["day"].casefold()}),
    ))
    if match["on"]:
        parts(match, 1, (("on", "PREP", "lexical", {"lemma_in": "on"}),))
    mark("COMMA", comma, comma + 1)
    mark("CLOSE-QUOTE", comma + 1, comma + 2)
    if not _add_reporter(text, reporter, add, parts):
        return None
    mark("SPEECH-STOP", len(text) - 1, len(text))
    return sorted(specs, key=lambda spec: spec[1])


_SHARED_MODAL = re.compile(
    rf"(?i)(?P<subject>{_PRONOUN}|one) +"
    r"(?P<modal>can|could|may|might|must|shall|should|will|would) +"
    r"(?P<left>[^,;]+?) +(?P<coord>and|or) +"
    r"(?P<verb>[a-z-]+) +(?P<object>(?:the|a|an|my|your|his|her|its|our|their|this|that) +[^,;]+)"
    r"(?P<comma>,) +(?P<example>for instance|for example)"
)
_NEGATIVE_COGNITION = re.compile(
    rf"(?i)(?P<subject>{_PRONOUN}) +(?P<aux>do|does|did)(?P<neg>n['’]t) +"
    r"(?P<verb>think|believe|suppose|expect|imagine|say) +"
    r"(?P<complement>[^,;]+?) *(?P<dash>--|—) *(?P<coord>and|but) +(?P<right>[^,;]+)"
)


def shared_modal_plan(text, components):
    span = _single_spoken_span(text, components)
    if span is None or text[span[0]] not in ".!":
        return None
    stop, _ = span
    match = _SHARED_MODAL.fullmatch(text[1:stop])
    if match is None or len(match["object"].split()) > 14:
        return None
    specs, add, mark, parts = _specs()
    mark("OPEN-QUOTE", 0, 1)
    if match["subject"].casefold() == "one":
        a, b = match.span("subject")
        add("NP", 1 + a, 1 + b, "source-generic-one")
    else:
        parts(match, 1, (("subject", "NP", "subject-phrase", {}),))
    parts(match, 1, (
        ("modal", "MODAL", "lexical", {"vform": "finite", "modal": "true"}),
        ("left", "VP-NP", "phrase", {"bare_predicate_proof": "true"}),
        ("coord", "COORD", "lexical", {}),
        ("verb", "V", "lexical-alternatives", {"vform": "base", "subcat_member": "transitive"}),
        ("object", "NP", "phrase", {"demonstrated_full_nominal_proof": "true"}),
        ("comma", "COMMA", "source-punctuation", {}),
        ("example", "EXAMPLE-FORMULA", "source-exemplification-formula", {}),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs


def negative_cognition_plan(text, components):
    span = _single_spoken_span(text, components)
    if span is None or text[span[0]] not in ".!":
        return None
    stop, _ = span
    match = _NEGATIVE_COGNITION.fullmatch(text[1:stop])
    if match is None or any(len(match[group].split()) > 15 for group in ("complement", "right")):
        return None
    subject = match["subject"].casefold()
    aux = match["aux"].casefold()
    if aux != "did" and (aux == "does") != (subject in ("he", "she", "it")):
        return None
    specs, _, mark, parts = _specs()
    mark("OPEN-QUOTE", 0, 1)
    parts(match, 1, (
        ("subject", "NP", "subject-phrase", {}),
        ("aux", "AUX", "lexical", {"vform": "finite", "lemma_in": "do|does|did"}),
        ("neg", "NEG", "lexical", {"negation": "true"}),
        ("verb", "V", "lexical-alternatives", {"vform": "base", "subcat_member": "clausal"}),
        ("complement", "CLAUSE", "phrase", {"finite_statement_proof": "true"}),
        ("dash", "DASH", "source-punctuation", {}),
        ("coord", "COORD", "lexical", {}),
        ("right", "CLAUSE", "phrase", {"finite_statement_proof": "true"}),
    ))
    mark("SPEECH-STOP", stop, stop + 1)
    mark("CLOSE-QUOTE", stop + 1, stop + 2)
    return specs
