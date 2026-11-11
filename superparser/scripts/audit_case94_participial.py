"""Isolate the source-context and participial-attachment gaps in frozen case 94.

Reference WordNet 3.0, unchanged public Parser.parse budgets. The actual
Gutenberg source is parsed ONLY through parse_corpus_case with v2 extraction.
All shorter independent probes are synthetic controls, not benchmark cases.
No grammatical correction or new success is claimed by this audit.
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
    "She gently chid me for being rude; and, keeping me close to her shawl, "
    "turned to thank the gentleman for taking so much trouble as to bring her home."
)
PROBES = (
    ("matrix_left", "She gently chid me for being rude."),
    ("matrix_right", "She turned to thank the gentleman for taking so much trouble as to bring her home."),
    ("simple_right", "She turned to thank the gentleman."),
    ("participial_resultative_finite", "She kept me close to her shawl."),
    ("front_participial", "Keeping me close to her shawl, she turned to thank the gentleman."),
    ("simple_coordination", "She gently chid me for being rude; and turned to thank the gentleman."),
    ("short_coordination", "She chid me and turned."),
    ("resultative_coordination", "She kept me close to her shawl and turned."),
    ("short_participial_incise", "She chid me; and, keeping me close to her shawl, turned."),
    ("generic_participial_incise", "The teacher scolded the boy; and, holding his hand, turned to thank the helper."),
    ("generic_simple_incise", "The teacher scolded the boy; and, smiling, turned to thank the helper."),
    ("negative_changed_subject", "She chid me; and, keeping me close to her shawl, he turned."),
)


def tree(node, source):
    return {
        "category": node.category,
        "rule_id": node.rule_id,
        "span": [node.start, node.end],
        "source": source[node.start:node.end],
        "children": [tree(ch, source) for ch in node.children],
    }


def record(label, source, result, tokens):
    best = result.best()
    alternatives = ([tree(root, source) for root in result.alternatives(limit=3)]
                    if result.completed else [])
    return {
        "label": label,
        "source": source,
        "tokens": len(tokens),
        "completed": result.completed,
        "forest_nodes": result.stats.get("forest_nodes"),
        "partial_states": result.stats.get("partial_states"),
        "budget_exceeded": result.stats.get("budget_exceeded"),
        "root": best.rule_id if best else None,
        "alternatives": alternatives,
    }


def audit(wordnet_dir: str, output: Path):
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    assert resources.lexicon.has_wordnet, "WordNet 3.0 is required"
    parser = Parser(resources, cache_size=0, max_items=50_000)
    book = Book(766, "David Copperfield", "Charles Dickens", "train")
    v1, _ = extract(book, SOURCE, length_min=1, length_max=100, segmentation_version=1)
    v2, _ = extract(book, SOURCE, length_min=1, length_max=100, segmentation_version=2)
    assert len(v1) == 2 and len(v2) == 1, "historical split vs prospective reunification"
    assert v2[0]["source_text"] == SOURCE
    prepared, lattice, result = parse_corpus_case(
        parser, v2[0], max_items=50_000, kbest_work_limit=500_000,
    )
    assert prepared.source_text == SOURCE
    assert prepared.analysis_text == SOURCE
    assert not result.stats.get("budget_exceeded"), "case 94 was not resource censored"
    rows = [record("v2_contiguous_gutenberg_94", prepared.analysis_text,
                   result, lattice.tokens)]
    for label, sentence in PROBES:
        report = parser.parse(sentence, kbest_work_limit=500_000)
        rows.append(record(label, sentence, report.result, report.lattice.tokens))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "frozen_index": 94,
        "frozen_baseline": "no_structural_root",
        "research_only": True,
        "source_preserved": True,
        "v1_units": [x["source_text"] for x in v1],
        "v2_source": v2[0]["source_text"],
        "probes": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    for row in rows:
        print("CASE94_PROBE", json.dumps({
            key: value for key, value in row.items() if key != "alternatives"
        }, ensure_ascii=False), flush=True)


def main():
    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument("--wordnet-dir", required=True)
    argp.add_argument("--out", type=Path, required=True)
    args = argp.parse_args()
    audit(args.wordnet_dir, args.out)


if __name__ == "__main__":
    main()
