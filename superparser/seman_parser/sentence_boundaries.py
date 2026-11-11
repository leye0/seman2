"""Conservative, lossless prose sentence boundaries for Seman2 corpora.

Keeps dialogue quote characters, abbreviations and personal initials intact.
Not a gold-standard sentence segmenter: prefer *not* splitting an ambiguous
period over manufacturing a bogus sentence from an initial.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from seman_parser.structural_units import review_semicolon_boundaries

# Abbreviations normally followed by names, locations or identifiers.
_NONTERMINAL = frozenset({
    "mr.", "mrs.", "ms.", "dr.", "prof.", "rev.", "capt.", "col.",
    "gen.", "lt.", "sgt.", "st.", "mt.", "hon.", "messrs.", "mme.",
    "mlle.", "no.", "nos.", "fig.", "vol.", "ch.", "dept.", "vs.",
    "e.g.", "i.e.",
})
_CLOSERS = frozenset("\"'”’)]}")
_OPENERS = frozenset("\"'“‘([{")
_INITIAL = re.compile(r"(?<![A-Za-z.])[A-Za-z]\.$")

def _abbreviation_at(text: str, period: int, next_word: str) -> bool:
    # Inspect only the last few words of the local paragraph.
    pre = text[max(0, period - 35):period + 1]
    token = re.search(r"[A-Za-z.]+$", pre)
    if not token:
        return False
    word = token.group(0)
    if word.casefold() in _NONTERMINAL:
        return word.casefold() not in {"vs.", "e.g.", "i.e."} or next_word[:1].islower()
    # Initials in names: J. R. R. Tolkien, J. Smith, A. B. Carter.
    # Single-letter initials are ambiguous; prefer under-segmentation.
    if _INITIAL.search(pre) and next_word[:1].isupper():
        return True
    # Compact abbreviation U.S. / Ph.D. followed by lowercase continuation.
    if "." in word[:-1] and next_word[:1].islower():
        return True
    return False


def _quote_continues_into_coordination(text: str, end: int) -> bool:
    """Keep a short multi-sentence quote with its following coordinator.

    This source-unit heuristic does not independently certify syntax.
    """
    open_quotes: list[tuple[str, str]] = []
    _advance_quotes(text[:end], open_quotes, balance_sentence_boundary=True)
    if len(open_quotes) != 1:
        return False
    closing_quote = open_quotes[0][1]
    closing = text.find(closing_quote, end)
    while closing >= 0:
        before = text[closing - 1] if closing else ""
        after = text[closing + 1] if closing + 1 < len(text) else ""
        if closing_quote in {"'", "’"} and before.isalnum() and after.isalnum():
            closing = text.find(closing_quote, closing + 1)
            continue
        break
    if closing < 0 or closing == end:
        return False
    # Only join a single, immediately following complete quoted sentence.
    quoted_tail = text[end:closing]
    if len(re.findall(r"[.!?]", quoted_tail)) != 1 or quoted_tail[-1] not in ".!?":
        return False
    return bool(re.match(r"\s*,?\s+(?:and|but|or)\b", text[closing + 1:]))


def _quote_continues_into_causal_aside(text: str, end: int) -> bool:
    """Keep an inner quoted sentence with a following dash-led explanation.

    An internal question can be one utterance in a nested reported quote:
    'She said, "Is it you? Can it be?"--for they had met before.'
    Splitting at the first '?' strands the second question and the explanatory
    aside. Only join when the next complete quoted sentence closes the same
    quote AND a dash-led causal continuation follows that closing delimiter.
    The historical implementation remains in Git history, not this path.
    """
    stack: list[tuple[str, str]] = []
    _advance_quotes(text[:end], stack, balance_sentence_boundary=True)
    if not stack:
        return False
    closer = stack[-1][1]
    closing = text.find(closer, end)
    while closing >= 0:
        before = text[closing - 1] if closing else ""
        after = text[closing + 1] if closing + 1 < len(text) else ""
        if closer in {"'", "’"} and before.isalnum() and after.isalnum():
            closing = text.find(closer, closing + 1)
            continue
        break
    if closing < 0:
        return False
    quoted_tail = text[end:closing].rstrip()
    if (not quoted_tail or quoted_tail[-1] not in ".!?"
            or len(re.findall(r"[.!?]", quoted_tail)) != 1):
        return False
    return bool(re.match(
        r"\s*(?:--|—|–)\s*(?:for|because)\b",
        text[closing + 1:], flags=re.IGNORECASE,
    ))


def split_prose_sentences(
    paragraph: str,
) -> list[str]:
    """Split while preserving every non-whitespace character, including quotes.

    A quote after terminal punctuation belongs to the preceding sentence.
    A lower-case reporting clause remains attached to quoted speech.
    Keep source-contiguous quoted continuations with external coordination
    or a dash-led causal explanation; this is the sole production splitter.
    """
    text = paragraph.strip()
    if not text:
        return []
    spans: list[str] = []
    left = 0
    n = len(text)
    i = 0
    while i < n:
        mark = text[i]
        if mark not in ".!?":
            i += 1
            continue
        if mark == "." and i + 1 < n and text[i + 1] == ".":
            i += 1  # process only the last period in an ellipsis
            continue
        if mark == "." and 0 < i < n - 1 and text[i - 1].isdigit() and text[i + 1].isdigit():
            i += 1
            continue
        end = i + 1
        while end < n and text[end] in _CLOSERS:
            end += 1
        if end == n or not text[end].isspace():
            i += 1
            continue
        scan = end
        while scan < n and text[scan].isspace():
            scan += 1
        if scan == n:
            break
        while scan < n and text[scan] in _OPENERS:
            scan += 1
        if scan >= n or not text[scan].isupper():
            i += 1
            continue
        next_word = text[scan:scan + 20].split(maxsplit=1)[0]
        if mark == "." and _abbreviation_at(text, i, next_word):
            i += 1
            continue
        if (_quote_continues_into_coordination(text, end)
                or _quote_continues_into_causal_aside(text, end)):
            i += 1
            continue
        spans.append(text[left:end].strip())
        # Keep the opening quotes/brackets of the next sentence.
        left = end
        while left < n and text[left].isspace():
            left += 1
        i = left
    tail = text[left:].strip()
    if tail:
        spans.append(tail)
    return spans


def has_final_punctuation(sentence: str) -> bool:
    """Recognize terminal .!? followed by closing quotes or brackets."""
    return re.search(r"""[.!?]["'”’)\]}]*$""", sentence) is not None


@dataclass(frozen=True)
class AnalysisUnit:
    """An analysis-ready text unit and its unmodified source segment."""
    text: str
    source_text: str
    semicolon_split: bool = False
    synthetic_prefix: str = ""
    synthetic_suffix: str = ""
    synthetic_terminal: bool = False


_QUOTE_PAIRS = {'“': '”', '‘': '’', '"': '"', "'": "'"}


def _advance_quotes(
    text: str, stack: list[tuple[str, str]], *,
    balance_sentence_boundary: bool = False,
) -> None:
    """Track quotation state across semicolons and, optionally, sentences.

    Unbalanced and quote-balanced views use the same structural boundaries.
    Synthetic marks are recorded separately, not inserted into source_text.
    """
    for index, char in enumerate(text):
        if char not in _QUOTE_PAIRS and char not in {'”', '’'}:
            continue
        before = text[index - 1] if index else ""
        after = text[index + 1] if index + 1 < len(text) else ""
        if char in {"'", "’"} and before.isalnum() and after.isalnum():
            continue
        # A trailing English possessive ("three days' rest") is not an
        # opening dialogue delimiter. Likewise, a closing double quote
        # stranded at a fragment's end must not become a new opening quote.
        # A clipped colloquial word ("o' that", "an' then") has a
        # trailing apostrophe even when the surrounding speech uses double
        # quotation marks.  The earlier not-stack guard misread that apostrophe
        # as an opening SINGLE quote inside an open DOUBLE quote, then
        # fabricated an extra quote at the next sentence boundary.
        # Keep the genuine closing single quote in 'word' / 'father.' when
        # a matching single-quote delimiter is actually on top of the stack.
        if (balance_sentence_boundary and char == "'" and before.isalnum()
                and (not stack or stack[-1][1] != "'")):
            continue
        if balance_sentence_boundary and char == '"' and not stack and before in ".!?" and not after:
            continue
        if char in {'”', '’'}:
            if stack and stack[-1][1] == char:
                stack.pop()
            continue
        if char in {'"', "'"} and stack and stack[-1][1] == char:
            stack.pop()
        else:
            stack.append((char, _QUOTE_PAIRS[char]))


def _supply_terminal(text: str) -> tuple[str, bool]:
    """Add an analysis-only period before any final dialogue closers."""
    if has_final_punctuation(text):
        return text, False
    suffix = re.search(r"""["'”’)\]}]*$""", text)
    position = suffix.start() if suffix else len(text)
    return text[:position] + "." + text[position:], True


def split_analysis_units(
    sentence: str, *,
    quote_context: tuple[tuple[str, str], ...] = (),
    balance_sentence_boundary: bool = False,
) -> list[AnalysisUnit]:
    """Split at independent semicolon boundaries and rewrap quotations.

    No text is rewritten in the checked-in novels. The original punctuation
    and delimiters survive in source_text for error analysis and provenance.
    The old splitting behavior is only available in Git history.
    """
    text = sentence.strip()
    if not text:
        return []
    if ';' not in text and not balance_sentence_boundary:
        return [AnalysisUnit(text=text, source_text=text)]
    # Typographic semicolons are proposals. The structural layer keeps
    # dependent constructions with their source context before quote transfer.
    boundaries = [
        decision.offset for decision in review_semicolon_boundaries(text)
        if not decision.merge
    ]
    is_semicolon_split = bool(boundaries)
    units: list[AnalysisUnit] = []
    stack: list[tuple[str, str]] = list(quote_context)
    left = 0
    for index in [*boundaries, len(text)]:
        raw = text[left:index]
        source = (text[left:index + 1] if index < len(text) else raw).strip()
        active_before = tuple(stack)
        _advance_quotes(raw, stack, balance_sentence_boundary=balance_sentence_boundary)
        active_after = tuple(stack)
        opening = ''.join(pair[0] for pair in active_before)
        closing = ''.join(pair[1] for pair in reversed(active_after))
        core = raw.strip()
        if core:
            if index < len(text):
                core, synthetic_terminal = _supply_terminal(core)
            else:
                synthetic_terminal = False
            units.append(AnalysisUnit(
                text=opening + core + closing,
                source_text=source,
                semicolon_split=is_semicolon_split,
                synthetic_prefix=opening,
                synthetic_suffix=closing,
                synthetic_terminal=synthetic_terminal,
            ))
        left = index + 1
    return units



def split_prose_analysis_units(
    paragraph: str,
) -> list[AnalysisUnit]:
    """Reuse the semicolon quote balancer across .!? sentence boundaries.

    The source spans stay verbatim; synthetic quotation marks appear only in
    analysis text and are individually recorded. The quote stack advances
    only through ORIGINAL characters, never through the synthetic delimiters.
    """
    context: list[tuple[str, str]] = []
    units: list[AnalysisUnit] = []
    for sentence in split_prose_sentences(paragraph):
        units.extend(split_analysis_units(
            sentence, quote_context=tuple(context),
            balance_sentence_boundary=True,
        ))
        _advance_quotes(sentence, context, balance_sentence_boundary=True)
    return units

