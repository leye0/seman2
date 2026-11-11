"""Inspect case96's free locative, modal relative and comma-coordinated NP.

Only the actual Gutenberg quotation goes through extract + parse_corpus_case.
Other examples are independent synthetic controls through the same Parser.parse
public entry. No grammar changes, no benchmark inflation.
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
    "‘And there I shall take you to the stage-cutch, and the stage-cutch "
    "that’ll take you to--wherever it is.’"
)
PROBES = (
    ("matrix_simple", "I shall take you to the stage-cutch.", "CLAUSE"),
    ("matrix_deictic", "And there I shall take you to the stage-cutch.", "CLAUSE"),
    ("paired_np_no_comma", "I shall take you to the coach and the train.", "CLAUSE"),
    ("paired_np_with_comma", "I shall take you to the coach, and the train.", "CLAUSE"),
    ("paired_same_np", "I shall take you to the coach, and the coach.", "CLAUSE"),
    ("relative_modal_town", "The coach that'll take you to the town arrived.", "CLAUSE"),
    ("relative_modal_where", "The coach that'll take you to where it is arrived.", "CLAUSE"),
    ("relative_modal_wherever", "The coach that'll take you to wherever it is arrived.", "CLAUSE"),
    ("relative_modal_dash", "The coach that'll take you to--wherever it is arrived.", "CLAUSE"),
    ("rel_np_town", "the coach that'll take you to the town", "NP"),
    ("rel_np_wherever", "the coach that'll take you to wherever it is", "NP"),
    ("rel_np_dash", "the coach that'll take you to--wherever it is", "NP"),
    ("wherever_np", "wherever it is", "NP"),
    ("wherever_clause", "Wherever it is, I will go.", "CLAUSE"),
    ("wherever_destination", "I shall take you to wherever it is.", "CLAUSE"),
    ("where_destination", "I shall take you to where it is.", "CLAUSE"),
    ("dash_destination", "I shall take you to--wherever it is.", "CLAUSE"),
    ("full_synthetic_no_quote", "And there I shall take you to the coach, and the coach that'll take you to--wherever it is.", "CLAUSE"),
    ("full_synthetic_no_dash", "And there I shall take you to the coach, and the coach that'll take you to wherever it is.", "CLAUSE"),
    ("full_synthetic_town", "And there I shall take you to the coach, and the coach that'll take you to the town.", "CLAUSE"),
    ("full_synthetic_longdash", "And there I shall take you to the coach, and the coach that'll take you to—wherever it is.", "CLAUSE"),
)

def selected_tree(item, text):
    return {
        "category": item.category, "rule_id": item.rule_id,
        "span": [item.start, item.end],
        "source": text[item.start:item.end],
        "children": [selected_tree(child, text) for child in item.children],
    }

def inspect(label, source, result, lattice):
    alts = (
        [selected_tree(tree, source) for tree in result.alternatives(limit=3)]
        if result.completed else []
    )
    return {
        "label": label, "source": source,
        "completed": result.completed,
        "tokens": len(lattice.tokens),
        "root_rule": alts[0]["rule_id"] if alts else None,
        "forest_nodes": result.stats.get("forest_nodes"),
        "partial_states": result.stats.get("partial_states"),
        "budget_exceeded": result.stats.get("budget_exceeded"),
        "alternatives": alts,
    }

def audit(wordnet_dir, output):
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    assert resources.lexicon.has_wordnet
    parser = Parser(resources, cache_size=0, max_items=50000)
    np_parser = Parser(resources, goal_category="NP", cache_size=0, max_items=50000)
    book = Book(766, "David Copperfield", "Charles Dickens", "train")
    rows, _ = extract(book, SOURCE, length_min=1, length_max=100)
    assert len(rows) == 1 and rows[0]["source_text"] == SOURCE
    prepared, lattice, result = parse_corpus_case(
        parser, rows[0], max_items=50000, kbest_work_limit=500000,
    )
    assert prepared.source_text == SOURCE
    records = [inspect("frozen96_source", prepared.analysis_text, result, lattice)]
    for label, sentence, goal in PROBES:
        current = np_parser if goal == "NP" else parser
        report = current.parse(sentence, max_items=50000, kbest_work_limit=500000)
        records.append(inspect(label, sentence, report.result, report.lattice))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "research_only": True, "source_preserved": True,
        "frozen_index": 96, "wordnet_reference": "3.0",
        "probes": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    for record in records:
        print("CASE96_PROBE", json.dumps({
            key: value for key, value in record.items() if key != "alternatives"
        }, ensure_ascii=False), flush=True)

def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--wordnet-dir", required=True)
    args.add_argument("--out", type=Path, required=True)
    opt = args.parse_args()
    audit(opt.wordnet_dir, opt.out)

if __name__ == "__main__":
    main()
