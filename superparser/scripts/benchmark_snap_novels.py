"""Novel-scale whole-sentence syntax snapping experiment (research only).

Sources: complete public-domain Project Gutenberg classic novels, downloaded
live; author-disjoint holdout novels. We ingest up to 60,000 short-to-medium
novel sentence observations, and run bounded Earley on exactly every tenth
eligible training observation, outside parsing. All other observations are
counted, not misleadingly called verified.

No novel text is stored in reports or committed to Git. Grammar witnesses
are NOT human gold. Held-out metrics test cross-author transfer, grammatical
negatives, corpus-level length strata and Seman2 explicit syntax assertions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.gutenberg_novels import (
    TRAIN_BOOKS, TEST_BOOKS, download, extract,
    holdout_stratified, length_band, spread_training,
)
from research.verbnet_lr.full_structure_snap import (
    FullStructureSnapIndex, SnappingResearchReader,
)
from research.verbnet_lr.sampled_teacher import VerificationSamplingQueue
from scripts.benchmark_snap_learning_curve import _gold, _quantile, _train_teacher
from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def _normalized(text):
    return " ".join(text.casefold().split())


def _seed(index, resources, seconds):
    rows = [
        json.loads(line) for line in
        (ROOT / "data/syntax_correctness_validation.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    baseline = SemanCompiledReader(resources, token_only_lattice=True)
    stats = Counter()
    for case in rows:
        if case.get("split") != "dev":
            continue
        lattice = build_lattice(
            case["text"], resources.lexicon, multiword_max=1)
        result = baseline.parse(case["text"], lattice=lattice)
        if result.complete:
            try:
                index.observe(result.item, lattice=lattice, evidence="candidate")
                stats["lr_complete_and_added"] += 1
            except ValueError:
                stats["lr_tree_unsupported"] += 1
        status = _train_teacher(index, lattice, seconds=seconds)
        stats["teacher_" + status] += 1
    return dict(stats), rows


def _test_set(books_to_rows, max_per_bin):
    test = holdout_stratified(
        books_to_rows, per_book_per_band=max_per_bin)
    if not test:
        raise RuntimeError("No held-out fiction sentences could be extracted")
    return test


def _evaluate(index, resources, novel_test, seman_cases, negatives):
    machine = SnappingResearchReader(
        resources, index=index,
        fallback=SemanCompiledReader(resources, token_only_lattice=True))
    bands = defaultdict(lambda: Counter())
    novel_results = Counter()
    timing = []
    by_book = defaultdict(Counter)
    for case in novel_test:
        t0 = perf_counter()
        result, route = machine.parse(case["text"])
        latency = (perf_counter() - t0) * 1000
        timing.append(latency)
        band = length_band(case["tokens"])
        complete = bool(result.complete)
        hit = route == "snap"
        for counter in (bands[band], by_book[str(case["book_id"])], novel_results):
            counter["tested"] += 1
            counter["snapped"] += int(hit)
            counter["completed"] += int(complete)
        if hit:
            bands[band]["snapped_incomplete"] += int(result.incomplete)

    seman_results = Counter()
    for case in seman_cases:
        result, route = machine.parse(case["text"])
        seman_results["tested"] += 1
        seman_results["snapped"] += int(route == "snap")
        seman_results["completed"] += int(result.complete)
        seman_results["explicit_annotation_pass"] += int(
            _gold(case, result, route) is True)
    negative_details = []
    for case in negatives:
        result, route = machine.parse(case["text"])
        negative_details.append({"id": case["id"], "accepted": result.complete,
                                 "route": route})
    return {
        "novel_holdout": dict(novel_results),
        "holdout_by_length": {k: dict(v) for k,v in sorted(bands.items())},
        "holdout_by_book": {k: dict(v) for k,v in sorted(by_book.items())},
        "novel_hybrid_p50_ms": _quantile(timing, .50),
        "novel_hybrid_p95_ms": _quantile(timing, .95),
        "novel_hybrid_p99_ms": _quantile(timing, .99),
        "seman2_holdout": dict(seman_results),
        "negative_false_accepts_24": sum(r["accepted"] for r in negative_details),
        "negative_false_accept_ids": [r["id"] for r in negative_details if r["accepted"]],
    }


def run(*, wordnet_dir, max_train=60_000,
        checkpoints=(0, 5_000, 20_000, 60_000), tenth=10,
        teacher_seconds=.055, seed_seconds=.35,
        per_book_band=75, max_teacher_tokens=32):
    checkpoints = tuple(sorted(set(checkpoints)))
    if (max_train < 100 or not checkpoints or checkpoints[0] != 0
            or checkpoints[-1] > max_train or tenth < 1
            or max_teacher_tokens < 4
            or teacher_seconds <= 0 or per_book_band < 1):
        raise ValueError("Invalid training, budget or evaluation settings")

    # Keep all known evaluation strings disjoint from training, even if
    # a Gutenberg book happens to reproduce a familiar phrase verbatim.
    seman_all = [
        json.loads(line) for line in
        (ROOT / "data/syntax_correctness_validation.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    seman_test = [r for r in seman_all if r.get("split") != "dev"]
    negatives = [
        json.loads(line) for line in
        (ROOT / "research/verbnet_lr/negative_minimal_pairs.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    forbidden = {_normalized(r["text"]) for r in seman_all}
    forbidden.update(_normalized(r["text"]) for r in negatives)
    forbidden.update(_normalized(r["contrast"]) for r in negatives)

    catalog = []
    train_books = {}
    heldout_books = {}
    for book in (*TRAIN_BOOKS, *TEST_BOOKS):
        core, metadata = download(book)
        cases, metrics = extract(book, core, length_min=4, length_max=45)
        metadata["extraction"] = metrics
        catalog.append(metadata)
        if book.role == "train":
            train_books[book.ebook_id] = cases
        else:
            heldout_books[book.ebook_id] = cases
        print(f"BOOK {book.ebook_id}: {book.title}: "
              f"{metrics['fragments']} fragments, "
              f"{metrics['eligible']} candidate sentences", flush=True)

    holdout = _test_set(heldout_books, per_book_band)
    # Never train on held-out books (author-disjoint), and exclude any
    # identical text found in the separate benchmark negatives/holdout.
    holdout_texts = {_normalized(r["text"]) for r in holdout}
    forbidden.update(holdout_texts)
    all_train = {}
    filtered = Counter()
    seen = set()
    for book_id,rows in train_books.items():
        allowed=[]
        for case in rows:
            normalized = _normalized(case["text"])
            if normalized in forbidden or normalized in seen:
                filtered["exact_duplicate_or_test_overlap"] += 1
                continue
            seen.add(normalized)
            if case["tokens"] > max_teacher_tokens:
                filtered["too_long_for_bounded_teacher"] += 1
                continue
            allowed.append(case)
        all_train[book_id] = allowed
    selected = spread_training(all_train, max_train)
    if len(selected) < checkpoints[-1]:
        raise RuntimeError(
            f"Expected {checkpoints[-1]} train sentences, "
            f"only {len(selected)} eligible; do not silently reduce sample")
    if {_normalized(x["text"]) for x in selected} & forbidden:
        raise RuntimeError("Train/test leakage detected")
    if {x["book_id"] for x in selected} & {x["book_id"] for x in holdout}:
        raise RuntimeError("Book-level test leakage detected")
    if {x["author"] for x in selected} & {x["author"] for x in holdout}:
        raise RuntimeError("Author-level test leakage detected")

    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    index = FullStructureSnapIndex(resources)
    seed_stats, _ = _seed(index, resources, seed_seconds)
    sampler = VerificationSamplingQueue(
        every=tenth, phase=0, max_pending=2)
    sampled_tokens = Counter()
    teacher_status = Counter()
    learning = []
    novel_baseline = None

    def record(n):
        print(f"EVALUATE {n}/{len(selected)}: {len(index.templates)} templates",
              flush=True)
        measurement = _evaluate(index, resources, holdout, seman_test, negatives)
        learning.append({
            "train_observations_seen": n,
            "sample_rate": f"1/{tenth}",
            "sampled": sampler.sampled,
            "teacher_processed": sampler.processed,
            "teacher_added_witnesses": sampler.grammar_witnesses,
            "teacher_status": dict(teacher_status),
            "template_index": index.summary(),
            "eval": measurement,
        })
        print("MILESTONE " + json.dumps({
            "seen": n, "sampled": sampler.sampled,
            "teacher_status": dict(teacher_status),
            "patterns": len(index.templates),
            "novel": measurement["novel_holdout"],
            "seman": measurement["seman2_holdout"],
            "negatives": measurement["negative_false_accepts_24"],
            "hybrid_p50": measurement["novel_hybrid_p50_ms"],
            "hybrid_p95": measurement["novel_hybrid_p95_ms"],
        }), flush=True)

    record(0)
    for i,case in enumerate(selected, 1):
        # Do not even build a lexical lattice for unselected novel sentences:
        # they are observed, but NOT misreported as parsed/verified.
        sampled = sampler.seen % tenth == sampler.phase
        lattice = (build_lattice(case["text"], resources.lexicon,
                                 multiword_max=1) if sampled else None)
        sampler.enqueue(case["text"], lattice)
        if sampled:
            sampled_tokens[length_band(case["tokens"])] += 1
            result = sampler.drain_teacher(
                index, max_cases=1, max_seconds=teacher_seconds)
            if result["grammar_witnesses"]:
                teacher_status["FOUND"] += 1
            elif result["unsupported"]:
                teacher_status["UNSUPPORTED"] += 1
            else:
                teacher_status["UNKNOWN_OR_REJECTED"] += 1
        if i % 10_000 == 0:
            print(f"TRAIN {i}: sampled={sampler.sampled}, "
                  f"witnesses={sampler.grammar_witnesses}, "
                  f"templates={len(index.templates)}", flush=True)
        if i in checkpoints:
            record(i)

    return {
        "schema": "seman2-gutenberg-novel-scale-v1",
        "training_book_ids": [b.ebook_id for b in TRAIN_BOOKS],
        "testing_book_ids": [b.ebook_id for b in TEST_BOOKS],
        "catalog": catalog,
        "counted_total_fragments": sum(
            v["extraction"]["fragments"] for v in catalog),
        "counted_total_candidate_sentences": sum(
            v["extraction"]["eligible"] for v in catalog),
        "train_eligible_after_exclusion": sum(map(len, all_train.values())),
        "train_sampled_for_observation": len(selected),
        "train_exclusion_counts": dict(filtered),
        "novel_holdout_evaluation_cases": len(holdout),
        "holdout_case_counts": dict(Counter(
            f"{r['book_id']}:{length_band(r['tokens'])}" for r in holdout)),
        "seman2_holdout_cases": len(seman_test),
        "seman2_negative_cases": len(negatives),
        "teacher_seconds_budget_each": teacher_seconds,
        "teacher_max_sentence_tokens": max_teacher_tokens,
        "sampling_every": tenth,
        "sampler": sampler.summary(),
        "seed": seed_stats,
        "sampled_lengths": dict(sampled_tokens),
        "learning_curve": learning,
        "limitations": [
            "Gutenberg public-domain-in-the-US English editions downloaded live; SHA-256 records exact bytes.",
            "Plain-text narrative sentence splitting is heuristic, NOT human annotation; extraction rejects many fragments.",
            "Training, observed sentences and Earley-verified sentence counts are separate; only 1/10 are sent to Earley.",
            "Test novels and authors are entirely separate; no held-out novel sentences enter the cache.",
            "Held-out novels have NO syntactic gold: snapped is NOT equivalent to correctly parsed.",
            "Seman2 explicit annotations cover selected phenomena, not full linguistic gold.",
            "Earley FOUND is one grammar-compatible witness, not a uniquely correct analysis.",
            "UNKNOWN and category-rejected are abstentions, never proof of grammatical impossibility.",
            "No LLM is involved; long inputs beyond bounded teacher length are counted, not trained.",
            "The same fixed 24 grammatical negatives are monitored, but avoiding test overfitting requires additional unseen negative suites.",
            "Memory and latency from a small learned cache are NOT a 20-million-structure scalability proof.",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--wordnet-dir", required=True)
    p.add_argument("--max-train", type=int, default=60_000)
    p.add_argument("--checkpoints", default="0,5000,20000,60000")
    p.add_argument("--every", type=int, default=10)
    p.add_argument("--teacher-seconds", type=float, default=.055)
    p.add_argument("--seed-seconds", type=float, default=.35)
    p.add_argument("--per-book-band", type=int, default=75)
    p.add_argument("--max-teacher-tokens", type=int, default=32)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = run(
        wordnet_dir=args.wordnet_dir, max_train=args.max_train,
        checkpoints=tuple(int(x) for x in args.checkpoints.split(",")),
        tenth=args.every, teacher_seconds=args.teacher_seconds,
        seed_seconds=args.seed_seconds,
        per_book_band=args.per_book_band,
        max_teacher_tokens=args.max_teacher_tokens)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("FINAL " + json.dumps({
        "total_fragments": result["counted_total_fragments"],
        "total_candidate_sentences": result["counted_total_candidate_sentences"],
        "train_observed": result["train_sampled_for_observation"],
        "holdout": result["novel_holdout_evaluation_cases"],
        "sampler": result["sampler"],
        "learning_curve": [{
            "observed": row["train_observations_seen"],
            "templates": row["template_index"]["templates"],
            "novel_hits": row["eval"]["novel_holdout"]["snapped"],
            "novel_completed": row["eval"]["novel_holdout"]["completed"],
            "seman2_gold": row["eval"]["seman2_holdout"]["explicit_annotation_pass"],
            "negative_false_accepts": row["eval"]["negative_false_accepts_24"],
        } for row in result["learning_curve"]],
    }), flush=True)


if __name__ == "__main__":
    main()
