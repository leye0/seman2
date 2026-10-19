"""Conservative, lossless prose sentence boundaries for Seman2 corpora.

Keeps dialogue quote characters, abbreviations and personal initials intact.
Not a gold-standard sentence segmenter: prefer *not* splitting an ambiguous
period over manufacturing a bogus sentence from an initial.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

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


def split_prose_sentences(paragraph: str) -> list[str]:
    """Split while preserving every non-whitespace character, including quotes.

    A quote after terminal punctuation belongs to the preceding sentence.
    A lower-case reporting clause remains attached to quoted speech.
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


def _advance_quotes(text: str, stack: list[tuple[str, str]]) -> None:
    """Track nested quotation boundaries, ignoring word-internal apostrophes."""
    for index, char in enumerate(text):
        if char not in _QUOTE_PAIRS and char not in {'”', '’'}:
            continue
        before = text[index - 1] if index else ""
        after = text[index + 1] if index + 1 < len(text) else ""
        if char in {"'", "’"} and before.isalnum() and after.isalnum():
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


def split_analysis_units(sentence: str) -> list[AnalysisUnit]:
    """Split on every semicolon and rewrap quotations on both sides.

    No text is rewritten in the checked-in novels. The original punctuation
    and delimiters survive in source_text for error analysis and provenance.
    """
    text = sentence.strip()
    if not text:
        return []
    if ';' not in text:
        return [AnalysisUnit(text=text, source_text=text)]
    units: list[AnalysisUnit] = []
    stack: list[tuple[str, str]] = []
    left = 0
    for index in range(len(text) + 1):
        if index < len(text) and text[index] != ';':
            continue
        raw = text[left:index]
        source = (text[left:index + 1] if index < len(text) else raw).strip()
        active_before = tuple(stack)
        _advance_quotes(raw, stack)
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
                semicolon_split=True,
                synthetic_prefix=opening,
                synthetic_suffix=closing,
                synthetic_terminal=synthetic_terminal,
            ))
        left = index + 1
    return units
