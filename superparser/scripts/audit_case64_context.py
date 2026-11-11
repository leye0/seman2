"""Prospective, source-preserving case-64 dialogue-context probe.

The frozen 500-case record stays untouched. This does not certify a
grammatical analysis; selected trees must be reviewed for exact attachments.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from seman_parser.engine import Parser, ParserResources

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    "Mr. Creakle whispered, ‘Hah! What’s this?’ and bent his eyes "
    "upon me, as if he would have burnt me up with them."
)


def selected_tree(node, source: str):
    return {
        "category": node.category,
        "rule_id": node.rule_id,
        "span": [node.start, node.end],
        "source": source[node.start:node.end],
        "children": [selected_tree(child, source) for child in node.children],
    }


def audit(wordnet_dir: str, output: Path):
    book = Book(766, "David Copperfield", "Charles Dickens", "train")
    old, _ = extract(book, SOURCE, length_min=1, length_max=100,
                     segmentation_version=1)
    new, _ = extract(book, SOURCE, length_min=1, length_max=100,
                     segmentation_version=2)
    assert len(old) == 2
    assert len(new) == 1 and new[0]["source_text"] == SOURCE
    assert new[0]["balanced_analysis_text"] == SOURCE
    assert " ".join(c["source_text"] for c in old) == SOURCE

    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    assert resources.lexicon.has_wordnet, "reference WordNet 3.0 required"
    parser = Parser(resources, cache_size=0, max_items=50_000)
    prepared, lattice, result = parse_corpus_case(
        parser, new[0], max_items=50_000, kbest_work_limit=500_000,
    )
    assert prepared.source_text == SOURCE
    assert prepared.analysis_text == SOURCE
    assert prepared.reference_span(0, len(SOURCE)) == (0, len(SOURCE))

    best = result.best()
    record = {
        "research_only": True,
        "frozen_index": 64,
        "canonical_baseline_comparable": False,
        "segmentation_version": 2,
        "wordnet_loaded": resources.lexicon.has_wordnet,
        "source_text": SOURCE,
        "analysis_text": prepared.analysis_text,
        "v1_sources": [c["source_text"] for c in old],
        "v2_source": new[0]["source_text"],
        "tokens": len(lattice.tokens),
        "completed": result.completed,
        "forest_nodes": result.stats.get("forest_nodes"),
        "partial_states": result.stats.get("partial_states"),
        "budget_exceeded": result.stats.get("budget_exceeded"),
        "selected_root_rule": best.rule_id if best else None,
        "diagnostic_status": (
            "no_complete_tree" if not result.completed
            else "resource_censored_tree" if result.stats.get("budget_exceeded")
            else "uncertified_complete_tree"
        ),
        "selected_tree": selected_tree(best, SOURCE) if best else None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf8")
    print("CASE64_CONTEXT_AUDIT", json.dumps({
        key: value for key, value in record.items()
        if key != "selected_tree"
    }, ensure_ascii=False), flush=True)


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--wordnet-dir", required=True)
    args.add_argument("--out", type=Path, required=True)
    options = args.parse_args()
    audit(options.wordnet_dir, options.out)


if __name__ == "__main__":
    main()
