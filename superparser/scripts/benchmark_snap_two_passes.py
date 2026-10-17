"""Two-pass Gutenberg memorization control for Seman2 whole-tree snapping.

Read exactly the same ordered corpus twice. First pass: actual compiled
grammar parsing and candidate tree learning. Second pass: baseline vs
snap+fallback on the same prebuilt lexical lattice. Report hit coverage,
tree/syntax parity, cumulative real wall-clock savings, p50/p75/p90.
Not a holdout, gold-accuracy, or statistical-significance experiment.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.full_structure_snap import (
    FullStructureSnapIndex, SnappingResearchReader,
)
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract, spread_training
from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import build_lattice


ROOT = Path(__file__).resolve().parents[1]


def percentile(values, q):
    if not values:
        return None
    s = sorted(values)
    index = (len(s) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(s) - 1)
    return round(s[lower] + (s[upper] - s[lower]) * (index - lower), 4)


def timing(values):
    return {
        "count": len(values),
        "p50_ms": percentile(values, .50),
        "p75_ms": percentile(values, .75),
        "p90_ms": percentile(values, .90),
        "p95_ms": percentile(values, .95),
        "mean_ms": round(sum(values) / len(values), 4) if values else None,
    }


def tree_shape(node):
    if node is None:
        return None
    if node.lexical_candidate is not None:
        c = node.lexical_candidate
        return ("leaf", node.category, c.lemma, c.sense_id,
                node.features.as_dict())
    return (node.category, node.rule_id, node.features.as_dict(),
            tuple(tree_shape(child) for child in node.children))


def syntax_shape(node):
    if node is None:
        return None
    return (node.syntax.as_dict(), tuple(syntax_shape(c) for c in node.children))


def reader(resources):
    return SemanCompiledReader(resources, token_only_lattice=True)


def run(wordnet_dir, *, max_sentences=50000, max_tokens=32, checkpoint=1000,
        max_templates_checked=512):
    if min(max_sentences, max_tokens, checkpoint, max_templates_checked) < 1:
        raise ValueError("All budgets must be positive")

    books = {}
    metadata = []
    for book in TRAIN_BOOKS:
        core, info = download(book)
        rows, counts = extract(book, core, length_min=4, length_max=max_tokens)
        books[book.ebook_id] = rows
        metadata.append({
            "book_id": book.ebook_id, "author": book.author,
            "source_sha256": info["sha256"], "source": info["url"],
            "eligible": len(rows), "extraction": counts,
        })
        print("BOOK " + str(book.ebook_id) + " " + str(len(rows)), flush=True)

    # Existing deterministic interleaving supplies the same exact sequence on
    # both passes. Cross-book duplicate text is excluded before sampling.
    stream = []
    fingerprints = set()
    for row in spread_training(books, max_sentences):
        fingerprint = sha256(" ".join(row["text"].casefold().split()).encode()).hexdigest()
        if fingerprint not in fingerprints:
            fingerprints.add(fingerprint)
            stream.append(row)
    if not stream:
        raise RuntimeError("No eligible sentences")
    print("CORPUS " + json.dumps({
        "selected": len(stream), "requested": max_sentences,
        "authors": len({r["author"] for r in stream}),
    }), flush=True)

    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    baseline = reader(resources)
    memory = FullStructureSnapIndex(resources)
    snapper = SnappingResearchReader(
        resources, index=memory, fallback=baseline,
        max_templates_checked=max_templates_checked,
        construction_guard=True,
    )

    first = Counter()
    learning_times = []
    first_times = []
    stored_ids = {}
    for i, row in enumerate(stream, 1):
        t0 = perf_counter()
        lattice = build_lattice(row["text"], resources.lexicon, multiword_max=1)
        parsed = baseline.parse(row["text"], lattice=lattice)
        t1 = perf_counter()
        first_times.append((t1 - t0) * 1000)
        first["read"] += 1
        first["complete"] += int(parsed.complete)
        t2 = perf_counter()
        if parsed.complete and parsed.item is not None:
            try:
                template_id = memory.observe(parsed.item, lattice=lattice,
                                             evidence="candidate")
                stored_ids[i] = template_id
                first["stored"] += 1
            except (ValueError, OverflowError):
                first["not_storable"] += 1
        learning_times.append((perf_counter() - t2) * 1000)
        if i % checkpoint == 0:
            print("LEARN " + json.dumps({
                "done": i, "complete": first["complete"],
                "stored": first["stored"],
                "templates": len(memory.templates),
            }), flush=True)

    baseline_lat = []
    snap_lat = []
    baseline_only = []
    snap_only = []
    lexical_lat = []
    hit_lat = []
    miss_lat = []
    curve = []
    counts = Counter()
    length_stats = defaultdict(Counter)
    cumulative_reference = 0.
    cumulative_hybrid = 0.
    cumulative_lexical = 0.
    training_cost = sum(learning_times)
    first_cost = sum(first_times)

    for i, row in enumerate(stream, 1):
        sentence = row["text"]
        t0 = perf_counter()
        lattice = build_lattice(sentence, resources.lexicon, multiword_max=1)
        lexical_ms = (perf_counter() - t0) * 1000

        # Alternate the timed order to avoid always favoring the second arm.
        if i % 2:
            t0 = perf_counter()
            hybrid, route = snapper.parse(sentence, lattice=lattice,
                                          learn_candidate=False)
            hybrid_ms = (perf_counter() - t0) * 1000
            t0 = perf_counter()
            reference = baseline.parse(sentence, lattice=lattice)
            reference_ms = (perf_counter() - t0) * 1000
        else:
            t0 = perf_counter()
            reference = baseline.parse(sentence, lattice=lattice)
            reference_ms = (perf_counter() - t0) * 1000
            t0 = perf_counter()
            hybrid, route = snapper.parse(sentence, lattice=lattice,
                                          learn_candidate=False)
            hybrid_ms = (perf_counter() - t0) * 1000

        lexical_lat.append(lexical_ms)
        baseline_only.append(reference_ms)
        snap_only.append(hybrid_ms)
        full_ref = lexical_ms + reference_ms
        full_snap = lexical_ms + hybrid_ms
        baseline_lat.append(full_ref)
        snap_lat.append(full_snap)
        cumulative_lexical += lexical_ms
        cumulative_reference += full_ref
        cumulative_hybrid += full_snap

        counts["tested"] += 1
        counts["reference_complete"] += int(reference.complete)
        counts["hybrid_complete"] += int(hybrid.complete)
        known = i in stored_ids
        counts["first_pass_storable"] += int(known)
        hit = route == "snap"
        counts["snap_hit"] += int(hit)
        counts["hit_with_known_template"] += int(hit and known)
        if hit:
            hit_lat.append(full_snap)
        else:
            miss_lat.append(full_snap)

        # Quality means comparison to the COMPLETE baseline derivation, NOT
        # independent linguistic correctness. Different valid attachments
        # remain explicit differences, never silently counted as equal.
        if bool(reference.complete) != bool(hybrid.complete):
            counts["completion_differences"] += 1
        if hit:
            if reference.item is None or hybrid.item is None:
                counts["unverifiable_hits"] += 1
            else:
                if tree_shape(reference.item) == tree_shape(hybrid.item):
                    counts["same_full_tree"] += 1
                else:
                    counts["different_full_tree"] += 1
                if syntax_shape(reference.item) == syntax_shape(hybrid.item):
                    counts["same_full_syntax"] += 1
                else:
                    counts["different_full_syntax"] += 1
            if known:
                own = stored_ids[i]
                counts["own_stored_template_matched"] += int(
                    any(m.template_id == own for m in hybrid.matches)
                )
                counts["other_template_chosen"] += int(
                    bool(hybrid.matches) and hybrid.matches[0].template_id != own
                )
        else:
            counts["fallback"] += 1
        band = ("04-12" if row["tokens"] <= 12 else
                "13-24" if row["tokens"] <= 24 else "25-32")
        length_stats[band]["tested"] += 1
        length_stats[band]["snap_hit"] += int(hit)
        length_stats[band]["known"] += int(known)
        length_stats[band]["reference_complete"] += int(reference.complete)

        if i % checkpoint == 0 or i == len(stream):
            saved = cumulative_reference - cumulative_hybrid
            overall_base = first_cost + cumulative_reference
            overall_hybrid = first_cost + training_cost + cumulative_hybrid
            point = {
                "sentences": i,
                "pass2_baseline_cumulative_s": round(cumulative_reference / 1000, 4),
                "pass2_hybrid_cumulative_s": round(cumulative_hybrid / 1000, 4),
                "pass2_net_saved_s": round(saved / 1000, 4),
                "pass2_time_saved_pct": round(100 * saved / cumulative_reference, 3)
                    if cumulative_reference else 0,
                "two_pass_net_saved_s": round((overall_base - overall_hybrid) / 1000, 4),
                "two_pass_time_saved_pct": round(
                    100 * (overall_base - overall_hybrid) / overall_base, 3)
                    if overall_base else 0,
                "hit_rate_pct": round(100 * counts["snap_hit"] / i, 3),
                "recall_of_stored_pct": round(
                    100 * counts["hit_with_known_template"] /
                    counts["first_pass_storable"], 3)
                    if counts["first_pass_storable"] else None,
                "snap_hits": counts["snap_hit"],
                "stored": counts["first_pass_storable"],
                "different_tree": counts["different_full_tree"],
                "different_syntax": counts["different_full_syntax"],
                "baseline_p50_ms": percentile(baseline_lat, .5),
                "baseline_p75_ms": percentile(baseline_lat, .75),
                "baseline_p90_ms": percentile(baseline_lat, .9),
                "hybrid_p50_ms": percentile(snap_lat, .5),
                "hybrid_p75_ms": percentile(snap_lat, .75),
                "hybrid_p90_ms": percentile(snap_lat, .9),
            }
            curve.append(point)
            print("CURVE " + json.dumps(point, separators=(",", ":")), flush=True)

    saved = cumulative_reference - cumulative_hybrid
    report = {
        "schema": "seman2-two-pass-identical-Gutenberg-v1",
        "interpretation": "Memorization upper-bound, NOT heldout generalization",
        "books": metadata,
        "corpus": {"selected_sentences": len(stream),
                   "min_tokens": 4, "max_tokens": max_tokens,
                   "same_order_both_passes": True,
                   "same_lexical_lattice_per_second_pass_comparison": True},
        "first_pass": {
            **dict(first), "templates": memory.summary(),
            "parsing_time_s": round(first_cost / 1000, 4),
            "indexing_time_s": round(training_cost / 1000, 4),
            "parse_latency": timing(first_times),
        },
        "second_pass": {
            **dict(counts),
            "recall_of_stored_pct": (
                round(100 * counts["hit_with_known_template"] /
                      counts["first_pass_storable"], 4)
                if counts["first_pass_storable"] else None),
            "hit_rate_pct": round(100 * counts["snap_hit"] / len(stream), 4),
            "baseline_latency": timing(baseline_lat),
            "hybrid_latency": timing(snap_lat),
            "baseline_parser_only": timing(baseline_only),
            "hybrid_parser_only": timing(snap_only),
            "lexical_common": timing(lexical_lat),
            "snap_hits_latency": timing(hit_lat),
            "fallback_latency": timing(miss_lat),
            "baseline_cumulative_s": round(cumulative_reference / 1000, 4),
            "hybrid_cumulative_s": round(cumulative_hybrid / 1000, 4),
            "net_saved_s": round(saved / 1000, 4),
            "net_saved_pct": round(100 * saved / cumulative_reference, 4),
            "two_pass_net_saved_s": round((saved - training_cost) / 1000, 4),
            "two_pass_net_saved_pct": round(
                100 * (saved - training_cost) / (first_cost + cumulative_reference),
                4),
            "by_length": {k: dict(v) for k, v in sorted(length_stats.items())},
        },
        "curve": curve,
        "quality_contract": [
            "Full-tree equivalence compares every rule, descendant, lexical lemma/sense and feature structure.",
            "Full-syntax equivalence compares all exported anchors and links at every constituent.",
            "Neither test proves independent human-gold linguistic correctness.",
            "Coverage can never reach 100% of ALL input sentences when the first-pass grammar did not complete them.",
            "Alternative trees may be valid; differences are counted, not called errors.",
            "Timing includes lattice construction; second-pass baseline checks are observational and excluded from hybrid cost.",
        ],
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wordnet-dir", required=True)
    parser.add_argument("--max-sentences", type=int, default=50000)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--checkpoint", type=int, default=1000)
    parser.add_argument("--max-templates-checked", type=int, default=512)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    result = run(a.wordnet_dir, max_sentences=a.max_sentences,
                 max_tokens=a.max_tokens, checkpoint=a.checkpoint,
                 max_templates_checked=a.max_templates_checked)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("FINAL " + json.dumps({
        "corpus": result["corpus"], "first_pass": result["first_pass"],
        "second_pass": {k: v for k, v in result["second_pass"].items()
                        if k not in ("by_length",)},
    }, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
