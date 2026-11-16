"""Reproduce the deterministic 96-case replay and 48-case blind control.

Pinned source identities exclude derived structural annotations. Neither
sample selects or drops a case based on the parser's output.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import signal

from research.verbnet_lr.gutenberg_novels import extract
from scripts.corpus_samples import BANDS
from scripts.evaluate_novel_transfer import (
    MAX_ITEMS, ROOT, SOURCES, _deadline, _serialized_cohort, cohort_identity,
    measure, normalized_identity, select_cases, select_transfer_cases,
    source_body, verify_source,
)
from seman_parser.engine import Parser, ParserResources

REPLAY_SHA = "5bb2c0bc51e92b3ed9b00ce84f81ed363305960bb3b306e294eff763ae718df6"
BLIND_SHA = "704a8e94ffbb4e0de9d5ff7ea9fa9979a4a78249dab44be62e1e5ee967bdefc3"


def sample(books_dir, previous, *, count_per_band, salt, expected_sha):
    seen = {normalized_identity(r["source_text"]) for r in (*previous, *select_cases(500)[0])}
    used_paragraphs = {(r["book_id"], r["structural_paragraph_index"]) for r in previous}
    rows = []
    for book, digest, first, heading in SOURCES:
        source = source_body((books_dir / f"pg{book.ebook_id}.txt").read_bytes(),
                             book.ebook_id, digest, first)
        paragraphs = re.split(r"\n\s*\n", source)
        candidates, _ = extract(book, source, length_min=4, length_max=32)
        pool = []
        for case in candidates:
            i = case["structural_paragraph_index"]
            identity = normalized_identity(case["source_text"])
            if (heading.fullmatch(paragraphs[i].strip())
                    or (book.ebook_id, i) in used_paragraphs or identity in seen):
                continue
            seen.add(identity)
            pool.append(case)
        for band, lo, hi in BANDS:
            in_band = [case for case in pool if lo <= case["tokens"] <= hi]
            in_band.sort(key=lambda case: sha256(
                f'{book.ebook_id}:{case["ordinal"]}:{salt}'.encode()
            ).digest())
            if len(in_band) < count_per_band:
                raise ValueError(f"Insufficient source cases for {book.ebook_id}/{band}")
            for case in in_band[:count_per_band]:
                picked = {**case, "band": band,
                          "transfer_id": f'U{book.ebook_id}-{case["ordinal"]:04d}'}
                verify_source(picked, source)
                rows.append(picked)
    if cohort_identity(rows) != expected_sha:
        raise ValueError(f"Unexpected source identities in {salt}")
    return rows


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--books-dir", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--wordnet-dir", type=Path)
    cli.add_argument("--sample-only", action="store_true")
    args = cli.parse_args()
    if not args.sample_only and args.wordnet_dir is None:
        cli.error("--wordnet-dir is required for measurement")
    initial, _ = select_transfer_cases(args.books_dir)
    replay = sample(args.books_dir, initial, count_per_band=12,
                    salt="seman2-untuned-v1", expected_sha=REPLAY_SHA)
    blind = sample(args.books_dir, initial + replay, count_per_band=6,
                   salt="seman2-untuned-v2", expected_sha=BLIND_SHA)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("replay", replay), ("blind", blind)):
        (args.out_dir / f"{name}_cohort.jsonl").write_bytes(_serialized_cohort(rows))
    if args.sample_only:
        return
    parser = Parser(ParserResources.from_dir(ROOT / "data", wordnet_dict=args.wordnet_dir),
                    cache_size=0, max_items=MAX_ITEMS)
    parser.parse("John opened the box.")
    handler = signal.signal(signal.SIGALRM, _deadline)
    try:
        for name, rows in (("replay", replay), ("blind", blind)):
            with (args.out_dir / f"{name}_parses.jsonl").open("w", encoding="utf-8", buffering=1) as out:
                for case in rows:
                    result = measure(parser, case)
                    out.write(json.dumps({"transfer_id": case["transfer_id"], **result}, ensure_ascii=False) + "\n")
    finally:
        signal.signal(signal.SIGALRM, handler)


if __name__ == "__main__":
    main()
