"""Deterministic, auditable novel corpus for Seman2 whole-tree research.

Sources are Project Gutenberg public-domain-in-the-US English classics.
This loader never commits or publishes book text. The JSON benchmark retains
only metadata, source URL, file SHA-256, counts and aggregate scores.

Sentence detection is a standard-library HEURISTIC: report discards rather
than imply it supplies gold sentence boundaries or syntactic annotations.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import zip_longest
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from seman_parser.segmentation import tokenize
from seman_parser.sentence_boundaries import has_final_punctuation
from seman_parser.structural_preanalysis import analyze_paragraph


@dataclass(frozen=True)
class Book:
    ebook_id: int
    title: str
    author: str
    role: str


TRAIN_BOOKS = (
    Book(766, "David Copperfield", "Charles Dickens", "train"),
    Book(1400, "Great Expectations", "Charles Dickens", "train"),
    Book(730, "Oliver Twist", "Charles Dickens", "train"),
    Book(1342, "Pride and Prejudice", "Jane Austen", "train"),
    Book(158, "Emma", "Jane Austen", "train"),
    Book(161, "Sense and Sensibility", "Jane Austen", "train"),
    Book(2701, "Moby Dick", "Herman Melville", "train"),
    Book(345, "Dracula", "Bram Stoker", "train"),
    Book(84, "Frankenstein", "Mary Shelley", "train"),
    Book(514, "Little Women", "Louisa May Alcott", "train"),
    Book(1661, "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "train"),
    Book(120, "Treasure Island", "Robert Louis Stevenson", "train"),
)
TEST_BOOKS = (
    Book(1260, "Jane Eyre", "Charlotte Bronte", "test"),
    Book(145, "Middlemarch", "George Eliot", "test"),
)

START = re.compile(r"(?im)^\*{3}\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*{3}\s*$")
END = re.compile(r"(?im)^\*{3}\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*{3}\s*$")
CHAPTER = re.compile(
    r"(?i)^(?:(?:chapter|book|volume|part)\s+(?:\d+|[ivxlcdm]+)\b"
    r"|(?:contents|preface|illustrations?|index)\s*$)"
)

def download(book: Book, *, timeout: int = 75):
    urls = (
        f"https://www.gutenberg.org/cache/epub/{book.ebook_id}/pg{book.ebook_id}.txt",
        f"https://www.gutenberg.org/ebooks/{book.ebook_id}.txt.utf-8",
        f"https://www.gutenberg.org/files/{book.ebook_id}/{book.ebook_id}-0.txt",
    )
    failures = []
    for url in urls:
        try:
            request = Request(url, headers={
                "User-Agent": "Seman2-research-corpus/0.1 (educational reproducible parser benchmark)",
                "Accept": "text/plain"})
            with urlopen(request, timeout=timeout) as reply:
                raw = reply.read()
            if not 10_000 < len(raw) < 30_000_000:
                raise ValueError("unexpected text byte length")
            text = raw.decode("utf-8-sig")
            core = strip_gutenberg(text)
            return core, {"id": book.ebook_id, "title": book.title,
                          "author": book.author, "role": book.role,
                          "url": url, "sha256": sha256(raw).hexdigest(),
                          "raw_bytes": len(raw)}
        except (HTTPError, URLError, UnicodeError, ValueError) as err:
            failures.append(f"{url}: {type(err).__name__} {err}")
    raise RuntimeError(f"Failed downloading book {book.ebook_id}: " + "; ".join(failures))


def strip_gutenberg(text: str):
    start = START.search(text)
    if start is None:
        raise ValueError("Gutenberg start marker not found; refusing to read boilerplate")
    end = END.search(text, start.end())
    if end is None:
        raise ValueError("Gutenberg end marker not found; refusing to read license")
    core = text[start.end():end.start()].strip()
    if len(core) < 10_000:
        raise ValueError("Suspiciously short Gutenberg book body")
    return core


def _normalized_paragraph_with_offsets(paragraph: str) -> tuple[str, list[int]]:
    """Whitespace-normalized source and its exact original char offsets."""
    chars: list[str] = []
    offsets: list[int] = []
    matches = list(re.finditer(r"\s+|\S+", paragraph))
    for i, match in enumerate(matches):
        value = match.group()
        if value.isspace():
            if chars and i+1 < len(matches):
                chars.append(" ")
                offsets.append(match.start())
        else:
            chars.extend(value)
            offsets.extend(range(match.start(), match.end()))
    return "".join(chars), offsets


def analysis_units(
    core: str, *, balance_sentence_quotes: bool = False,
):
    """Complete utterances, typed spans and exact cleaned-book provenance.

    The quote flag remains for caller compatibility, but both views share
    source-exact text and punctuation. Every constituent span is relative to
    its unit; paragraph/core spans additionally reference the original book.
    """
    source = core.replace("\r\n", "\n")
    # Retain delimiter lengths while enumerating paragraph ordinals.
    parts = re.split(r"(\n\s*\n)", source)
    cursor = 0
    last_unit = None
    for paragraph_number, i in enumerate(range(0, len(parts), 2)):
        paragraph = parts[i]
        raw_start = cursor
        cursor += len(paragraph)
        if i+1 < len(parts):
            cursor += len(parts[i+1])
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines or CHAPTER.match(lines[0]):
            continue
        joined = re.sub(r"\s+", " ", " ".join(lines))
        if not has_final_punctuation(joined) and (
                joined.isupper() or len(joined) < 45):
            continue
        normalized, offsets = _normalized_paragraph_with_offsets(paragraph)
        if normalized != joined:
            raise AssertionError("Paragraph normalization drifted from original source")
        for unit in analyze_paragraph(joined):
            governor = None
            if unit.discourse_antecedent_policy == "preceding_utterance":
                # An afterthought is tied to an immediately preceding unit
                # in this SAME paragraph, not arbitrarily to other prose.
                if last_unit and last_unit.paragraph_index == paragraph_number:
                    governor = last_unit
            elif unit.discourse_antecedent_policy == "preceding_source_unit":
                # Candidate interparagraph antecedent, never synthetic quote
                # reconstruction nor an asserted grammatical attachment.
                governor = last_unit
            enriched = replace(
                unit,
                paragraph_index=paragraph_number,
                core_start=raw_start + offsets[unit.source_start],
                core_end=raw_start + offsets[unit.source_end-1] + 1,
                discourse_governor_core_span=(
                    (governor.core_start, governor.core_end) if governor else None
                ),
                discourse_governor_paragraph_index=(
                    governor.paragraph_index if governor else None
                ),
            )
            yield enriched
            last_unit = enriched


def sentences(core: str):
    """Source units from the current segmenter, not a parsing gateway.

    To analyze a selected case, use corpus_pipeline.parse_corpus_case so that
    sentence- and semicolon-spanning quotation state is always applied.
    """
    for unit in analysis_units(core):
        yield unit.text


def extract(book: Book, core: str, *, length_min=4, length_max=45):
    """Return candidates plus UNFILTERED counts; skips are transparent."""
    counters = {"fragments": 0, "too_short": 0, "too_long": 0,
                "non_ascii": 0, "non_sentence": 0, "duplicates": 0,
                "requires_source_context": 0,
                "nonprose_documentary": 0,
                "contextual_discourse_supplements": 0}
    eligible = []
    seen = set()
    for number, (unit, balanced) in enumerate(zip_longest(
        analysis_units(core),
        analysis_units(core, balance_sentence_quotes=True),
    )):
        if unit is None or balanced is None or unit.source_text != balanced.source_text:
            raise AssertionError("Balanced quote spans must preserve source segmentation")
        sentence = unit.text
        counters["fragments"] += 1
        if not unit.eligible_for_parse:
            if unit.structural_status == "nonprose_documentary":
                counters["nonprose_documentary"] += 1
            else:
                counters["requires_source_context"] += 1
                if unit.discourse_function in (
                    "elliptical_supplement", "reported_speech_continuation"
                ):
                    counters["contextual_discourse_supplements"] += 1
            continue
        # Unicode literary punctuation (including “ ” ‘ ’) is legitimate
        # text, not a reason to delete an entire dialogue sentence.
        if "\ufffd" in sentence:
            counters["non_ascii"] += 1
            continue
        tokens = tokenize(sentence)
        if len(tokens) < length_min:
            counters["too_short"] += 1
            continue
        if len(tokens) > length_max:
            counters["too_long"] += 1
            continue
        if not has_final_punctuation(sentence):
            counters["non_sentence"] += 1
            continue
        normalized = " ".join(sentence.lower().split())
        if normalized in seen:
            counters["duplicates"] += 1
            continue
        seen.add(normalized)
        eligible.append({"book_id": book.ebook_id, "author": book.author,
                         "ordinal": number, "text": sentence,
                         "source_text": unit.source_text,
                         "semicolon_split": unit.semicolon_split,
                         "synthetic_prefix": unit.synthetic_prefix,
                         "synthetic_suffix": unit.synthetic_suffix,
                         "synthetic_terminal": unit.synthetic_terminal,
                         "balanced_analysis_text": balanced.text,
                         "balanced_synthetic_prefix": balanced.synthetic_prefix,
                         "balanced_synthetic_suffix": balanced.synthetic_suffix,
                         "balanced_synthetic_terminal": balanced.synthetic_terminal,
                         "structural_status": unit.structural_status,
                         "quotation_status": unit.quotation_status,
                         "structural_source_span": [unit.source_start, unit.source_end],
                         "structural_paragraph_index": unit.paragraph_index,
                         "structural_core_source_span": [unit.core_start, unit.core_end],
                         "discourse_function": unit.discourse_function,
                         "discourse_relation": unit.discourse_relation,
                         "discourse_evidence": unit.discourse_evidence,
                         "discourse_governor_core_span": (
                             list(unit.discourse_governor_core_span)
                             if unit.discourse_governor_core_span else None
                         ),
                         "discourse_governor_paragraph_index": (
                             unit.discourse_governor_paragraph_index
                         ),
                         "structural_constituents": [c.to_dict() for c in unit.constituents],
                         "tokens": len(tokens)})
    counters["eligible"] = len(eligible)
    return eligible, counters


def length_band(n):
    if n <= 12:
        return "04-12"
    if n <= 24:
        return "13-24"
    if n <= 40:
        return "25-40"
    return "41+"


def spread_training(books_to_sentences, limit):
    """Deterministic interleaving across *books and positions*.

    Sorted by fixed SHA-256(book-id, paragraph-ordinal), avoiding a corpus
    dominated by first chapters or the largest book. No held-out text enters.
    """
    order = []
    for book_id, cases in books_to_sentences.items():
        ordered = sorted(cases, key=lambda c:
            sha256(f'{book_id}:{c["ordinal"]}'.encode()).digest())
        order.append(iter(ordered))
    selected = []
    for group in zip_longest(*order):
        for case in group:
            if case is not None:
                selected.append(case)
                if len(selected) >= limit:
                    return selected
    return selected


def holdout_stratified(books_to_sentences, *, per_book_per_band=80):
    """Unseen BOOKS AND AUTHORS; lengths span short through 41+ tokens."""
    chosen = []
    for book_id, rows in books_to_sentences.items():
        for band in ("04-12", "13-24", "25-40", "41+"):
            subset = [r for r in rows if length_band(r["tokens"]) == band]
            ordered = sorted(subset, key=lambda c:
                sha256(f'{book_id}:{c["ordinal"]}'.encode()).digest())
            chosen.extend(ordered[:per_book_per_band])
    return chosen
