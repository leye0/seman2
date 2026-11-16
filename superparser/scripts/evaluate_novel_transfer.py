"""Measure rank-one parser output on a separate 24-utterance literary sample.

Run with PYTHONPATH=superparser python -m scripts.evaluate_novel_transfer.
The Novel-500 pin and grammar are inputs, never outputs.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import signal
from time import perf_counter
import unicodedata

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import (
    Book, TEST_BOOKS, TRAIN_BOOKS, extract, strip_gutenberg,
)
from scripts.audit_novel_tree_quality import display_tree
from scripts.corpus_samples import BANDS, sample_spread
from scripts.diagnose_novel_parses import (
    ROOT, SentenceDeadline, _deadline, classify, compact_stats, select_cases, tally,
)
from seman_parser.engine import ParseReport, Parser, ParserResources

MAX_ITEMS = 50_000
KBEST_WORK_LIMIT = 500_000
DEADLINE_SECONDS = 10
PER_BOOK_BAND = 3
# Identity pins the exact ordered source units; typed constituents are
# observable outputs of the preanalyzer and can evolve independently.
TRANSFER_COHORT_VERSION = "source-typography-v2"
EXPECTED_COHORT_SHA256 = "0d6439dc568a49f8b7b6dcc48d7f2c323fd2bacd9c0815d4c74f0eca3293b4a5"
# Editions are pinned before sampling. Update only for a new experiment.
SOURCES = (
    (
        Book(35, "The Time Machine", "H. G. Wells", "transfer"),
        "2892e919000e17c83e1dac51b30f4675db50536b644d7579fe8a89bb399a9bdc",
        re.compile(r"(?m)^ I\.\n Introduction[ \t]*$"),
        re.compile(r"(?:[IVXLCDM]+\.\s+[^\n]+|Epilogue)", re.IGNORECASE),
    ),
    (
        Book(45, "Anne of Green Gables", "L. M. Montgomery", "transfer"),
        "89a5e9fb2e0bb44562a969785385366f94e1da736aebee7d9cdf459eb0b5f9f6",
        re.compile(r"(?m)^CHAPTER I\. Mrs\. Rachel Lynde Is Surprised[ \t]*$"),
        re.compile(r"CHAPTER [IVXLCDM]+\.\s+[^\n]+"),
    ),
)
SOURCE_URL = "https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.txt"


def normalized_identity(text: str) -> str:
    """Catch text duplicates even when punctuation or typography differs."""
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold()))


def source_body(raw: bytes, ebook_id: int, expected_sha: str,
                first_chapter: re.Pattern) -> str:
    if sha256(raw).hexdigest() != expected_sha:
        raise ValueError(f"Source SHA-256 mismatch for Gutenberg #{ebook_id}")
    text = strip_gutenberg(raw.decode("utf-8-sig").replace("\r\n", "\n"))
    match = first_chapter.search(text)
    if match is None:
        raise ValueError(f"First narrative section not found for Gutenberg #{ebook_id}")
    # Keep contiguous narrative text. Source spans are relative to this body.
    return text[match.start():]


def verify_source(case: dict, core: str) -> None:
    start, end = case["structural_core_source_span"]
    if not 0 <= start < end <= len(core) or (
        " ".join(core[start:end].split()) != case["source_text"]
        or case["source_text"] != case["text"]
        or case["synthetic_prefix"] or case["synthetic_suffix"] or case["synthetic_terminal"]
    ):
        raise ValueError(f"Non-source-exact transfer case: {case['transfer_id']}")


def select_transfer_cases(books_dir: Path) -> tuple[list[dict], list[dict]]:
    existing = TRAIN_BOOKS + TEST_BOOKS
    existing_books = {book.ebook_id for book in existing}
    existing_authors = {book.author for book in existing}
    pinned, _ = select_cases(500)
    previous = {normalized_identity(row["source_text"]) for row in pinned}
    seen: set[str] = set()
    selected, sources = [], []
    for book, expected_sha, first_chapter, heading in SOURCES:
        if book.ebook_id in existing_books or book.author in existing_authors:
            raise ValueError(f"Gutenberg #{book.ebook_id} overlaps configured books or authors")
        raw = (books_dir / f"pg{book.ebook_id}.txt").read_bytes()
        core = source_body(raw, book.ebook_id, expected_sha, first_chapter)
        cases, counts = extract(book, core, length_min=BANDS[0][1], length_max=BANDS[-1][2])
        headings = {
            paragraph_index
            for paragraph_index, paragraph in enumerate(re.split(r"\n\s*\n", core))
            if heading.fullmatch(paragraph.strip())
        }
        filtered = []
        excluded = Counter()
        for case in cases:
            if case["structural_paragraph_index"] in headings:
                excluded["paratext"] += 1
                continue
            key = normalized_identity(case["source_text"])
            if key in previous or key in seen:
                excluded["duplicate_normalized"] += 1
                continue
            seen.add(key)
            filtered.append(case)
        source = {
            "book_id": book.ebook_id, "title": book.title, "author": book.author,
            "url": SOURCE_URL.format(ebook_id=book.ebook_id), "raw_sha256": expected_sha,
            "body_sha256": sha256(core.encode()).hexdigest(),
            "extraction_counts": counts, "extra_exclusions": dict(excluded),
            "eligible_by_band": {},
        }
        for band, lower, upper in BANDS:
            pool = [case for case in filtered if lower <= case["tokens"] <= upper]
            source["eligible_by_band"][band] = len(pool)
            for case in sample_spread(pool, PER_BOOK_BAND):
                ident = f"T{book.ebook_id}-{case['ordinal']:04d}"
                picked = {**case, "band": band, "transfer_id": ident}
                verify_source(picked, core)
                selected.append(picked)
        sources.append(source)
    return selected, sources


def _serialized_cohort(cases: list[dict]) -> bytes:
    return "".join(
        json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in cases
    ).encode("utf-8")


def cohort_identity(cases: list[dict]) -> str:
    identity = [{k: v for k, v in case.items() if k != "structural_constituents"}
                for case in cases]
    return sha256(_serialized_cohort(identity)).hexdigest()


def measure(parser: Parser, case: dict, *, with_semantics: bool = False) -> dict:
    started = perf_counter()
    signal.setitimer(signal.ITIMER_REAL, DEADLINE_SECONDS)
    try:
        _, lattice, result = parse_corpus_case(
            parser, case, max_items=MAX_ITEMS, kbest_work_limit=KBEST_WORK_LIMIT,
        )
        stats = result.stats
        scoped = stats.get("dialogue_attempt") or {}
        best = result.best() if result.completed else None
        if result.completed and best is None:
            raise AssertionError("Completed parse has no selected tree")
        row = {
            **compact_stats(stats),
            "status": classify(result.completed, stats),
            "forest_budget_exceeded": bool(stats.get("budget_exceeded") or scoped.get("budget_exceeded")),
            "kbest_budget_exceeded": bool(stats.get("kbest_budget_exceeded") or scoped.get("kbest_budget_exceeded")),
            "root_rule": best.rule_id if best else None,
            "tree": best.as_dict() if best else None,
            "display_tree": display_tree(best, result.text) if best else None,
        }
        if with_semantics and best is not None:
            # Use the same resources as the public parse report. Ordinary
            # hierarchy also sets structural metadata, but not the verified
            # source composition flag used by these two source-aware routes.
            resources = ((parser._quoted_sentence_resources or parser.resources)
                         if stats.get("structural_composition") else
                         (parser._dialogue_resources or parser.resources)
                         if stats.get("dialogue_scoped") else parser.resources)
            row["selected_graph"] = ParseReport(result, resources, lattice).best_semantic_graph()
    except SentenceDeadline:
        row = {"status": "timeout"}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return {**row, "wall_ms": round((perf_counter() - started) * 1000, 2)}


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--books-dir", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--wordnet-dir", type=Path, help="Path to a WordNet 3.0 dictionary")
    cli.add_argument("--sample-only", action="store_true")
    args = cli.parse_args()
    if not args.sample_only and args.wordnet_dir is None:
        cli.error("--wordnet-dir is required for measurement")
    cases, sources = select_transfer_cases(args.books_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cohort = args.out_dir / "cohort.jsonl"
    cohort_bytes = _serialized_cohort(cases)
    digest = cohort_identity(cases)
    preanalysis_digest = sha256(cohort_bytes).hexdigest()
    if digest != EXPECTED_COHORT_SHA256:
        raise ValueError(
            f"Transfer cohort changed: expected {EXPECTED_COHORT_SHA256}, got {digest}. "
            "Use a separate baseline for a different cohort."
        )
    cohort.write_bytes(cohort_bytes)
    print(f"{len(cases)} transfer cases, source cohort SHA-256 {digest}, "
          f"with annotations {preanalysis_digest}", flush=True)
    if args.sample_only:
        return
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=args.wordnet_dir)
    parser = Parser(resources, cache_size=0, max_items=MAX_ITEMS)
    parser.parse("John opened the box.")  # Match the canonical diagnostic warm-up.

    rows = []
    old_handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        with (args.out_dir / "per_sentence.jsonl").open("w", encoding="utf-8", buffering=1) as stream:
            for case in cases:
                measured = measure(parser, case)
                row = {**case, **measured}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows.append(row)
                print(f"{row['transfer_id']} [{row['band']}] {row['status']}", flush=True)
    finally:
        signal.signal(signal.SIGALRM, old_handler)

    summary = {
        "cohort_version": TRANSFER_COHORT_VERSION,
        "cohort_sha256": digest, "cohort_with_preanalysis_sha256": preanalysis_digest,
        "max_items": MAX_ITEMS,
        "kbest_work_limit": KBEST_WORK_LIMIT, "deadline_seconds": DEADLINE_SECONDS,
        "sources": sources, "total": tally(rows),
        "by_book": {
            str(book.ebook_id): tally([row for row in rows if row["book_id"] == book.ebook_id])
            for book, *_ in SOURCES
        },
        "by_band": {
            band: tally([row for row in rows if row["band"] == band]) for band, *_ in BANDS
        },
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


if __name__ == "__main__":
    main()
