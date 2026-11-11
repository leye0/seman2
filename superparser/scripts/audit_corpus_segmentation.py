"""Measure current source-unit segmentation independently of grammar coverage.

This does not claim gold sentence-boundary accuracy; it checks exact source
round-trips and records the distribution of units, lengths and quote transfers.
Run with PYTHONPATH=superparser python -m scripts.audit_corpus_segmentation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from research.verbnet_lr.clean_novel_corpus import load_cleaned, read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, analysis_units, CHAPTER
from seman_parser.sentence_boundaries import has_final_punctuation, split_prose_analysis_units, split_prose_sentences
from seman_parser.segmentation import tokenize
from seman_parser.structural_units import review_semicolon_boundaries


def measure() -> dict:
    books = {b.ebook_id: b for b in TRAIN_BOOKS}
    overall = Counter()
    by_book = {}
    by_structural_reason = Counter()
    for record in read_manifest()["books"]:
        book = books[record["ebook_id"]]
        text, _ = load_cleaned(book)
        totals = Counter()
        for paragraph in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
            lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
            if not lines or CHAPTER.match(lines[0]):
                continue
            joined = re.sub(r"\s+", " ", " ".join(lines))
            if not has_final_punctuation(joined) and (
                    joined.isupper() or len(joined) < 45):
                continue
            for sentence in split_prose_sentences(joined):
                for decision in review_semicolon_boundaries(sentence):
                    if decision.merge:
                        by_structural_reason[decision.reason] += 1
            units = split_prose_analysis_units(joined)
            reconstructed = " ".join(u.source_text for u in units)
            # AnalysisUnit.source_text is individually stripped, so joining
            # may introduce one separator at an originally adjacent boundary.
            # Assert *character* conservation, and measure whitespace drift
            # separately instead of asserting fictional byte-exact recovery.
            if not units or re.sub(r"\s+", "", reconstructed) != re.sub(r"\s+", "", joined):
                raise AssertionError(
                    f"Loss of non-whitespace source characters in {book.ebook_id}: "
                    f"original={joined[:160]!r}; reconstructed={reconstructed[:160]!r}"
                )
            totals["boundary_whitespace_normalizations"] += int(reconstructed != joined)
            totals["paragraphs"] += 1
            totals["analysis_units"] += len(units)
            for unit in units:
                totals["semicolons_cut"] += int(unit.semicolon_split)
                totals["transferred_open_quotes"] += len(unit.synthetic_prefix)
                totals["transferred_close_quotes"] += len(unit.synthetic_suffix)
                totals["synthetic_terminal"] += int(unit.synthetic_terminal)
                totals["units_over_32_tokens"] += int(len(tokenize(unit.text)) > 32)
        # Sanity check: the production extractor and the direct paragraph
        # segmenter create identical unit counts across the cleaned book.
        direct = sum(1 for _ in analysis_units(text, balance_sentence_quotes=True))
        if direct != totals["analysis_units"]:
            raise AssertionError(f"Extractor/segmenter boundaries diverged for {book.ebook_id}")
        by_book[str(book.ebook_id)] = dict(sorted(totals.items()))
        overall.update(totals)

    # Independent source-specific guards; these are not gold corpus labels.
    fixtures = [
        ("sentential_relative",
         "I promised to return; which I accordingly did."),
        ("coordinated_participial",
         "She gently chid me for being rude; and, keeping me close to her "
         "shawl, turned to thank the gentleman for taking so much trouble "
         "as to bring her home."),
        ("nested_quote_coordination",
         "Mr. Creakle whispered, ‘Hah! What’s this?’ and bent his eyes "
         "upon me, as if he would have burnt me up with them."),
        ("nested_quote_causal",
         "‘Says Em’ly, “Martha, is it you? Oh, Martha, can it be you?”"
         "--for they had sat at work together, many a day, at Mr. Omer’s.’"),
    ]
    for label, source in fixtures:
        units = split_prose_analysis_units(source)
        if len(units) != 1 or units[0].source_text != source:
            raise AssertionError(f"Current segmenter orphaned {label}")
    for source in (
            "She left; he returned.",
            "He whispered, ‘Oh! What now?’ Then he left.",
            "“What?” “Nothing!”"):
        units = split_prose_analysis_units(source)
        if len(units) < 2 or " ".join(u.source_text for u in units) != source:
            raise AssertionError("Current segmenter incorrectly merged independent sentences")
    return {
        "schema": "seman2-current-segmentation-audit-v1",
        "policy": "single-source-preserving-segmenter",
        "counts": dict(sorted(overall.items())),
        "structural_links_by_reason": dict(sorted(by_structural_reason.items())),
        "by_book": by_book,
        "non_whitespace_source_characters_preserved": True,
        "byte_exact_round_trip_not_asserted": True,
        "positive_context_examples": [name for name, _ in fixtures],
        "negative_independent_examples": 3,
        "grammatical_tree_quality_certified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = measure()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    print("CURRENT_SEGMENTATION_AUDIT", json.dumps(result, ensure_ascii=False),
          flush=True)


if __name__ == "__main__":
    main()
